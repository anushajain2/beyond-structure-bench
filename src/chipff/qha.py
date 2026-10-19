"""Thermal expansion from the quasi-harmonic approximation (QHA).

Why QHA and not NPT MD (docs/thermal_method.md): MD through kUPS on a free GPU ran
at ~0.35 s per step for MACE and ~1.2 s for Orb, putting the full set at well over
100 GPU-hours per model; and a fixed-volume check showed kUPS's isotropic barostat
holding cells at a volume where the true pressure is about -N k T / V, which adds a
spurious expansion proportional to temperature. QHA needs only static force
evaluations, avoids the barostat, and includes zero-point and quantum statistics, so
it is valid from room temperature without a Debye cutoff. It omits anharmonicity
beyond the volume dependence of the phonons, which matters most near melting.

Method, per model and material:

1. Scale the model's relaxed cell isotropically to N volumes (shape fixed) and relax
   the atoms at each volume, giving the static energy E(V).
2. At each volume, compute harmonic phonons with phonopy (finite displacements of
   0.01 Å in a supercell at least 10 Å across; forces from the model through kUPS)
   and the vibrational free energy F_vib(V, T) on a dense q-mesh.
3. Minimise E(V) + F_vib(V, T) at each T (phonopy's QHA with a Vinet equation of state)
   to get V(T), and from it alpha_V(T) = (1/V) dV/dT.
4. Average alpha_V over the same pre-registered temperature window used for every
   material, and compare with experiment averaged over that window.

Checks: no imaginary phonon frequencies at any volume (dynamical stability), V(T)
stays inside the scanned volume range, and the E(V) fit is clean.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass

import numpy as np
from ase import Atoms

log = logging.getLogger("chipff")


@dataclass
class QhaResult:
    material: str
    model: str
    temperatures: list           # the comparison window [T_low, T_mid, T_high]
    alpha_V_1e6: float           # mean alpha_V over the window, 1e-6/K
    alpha_V_err_1e6: float       # 0: QHA is deterministic (uncertainty is methodological)
    alpha_V_300K_1e6: float | None
    curve_T: list                # alpha_V(T) on a coarse grid, for plots and the MCP tool
    curve_alpha_V_1e6: list
    volume_scales: list
    supercell: list
    n_displacements: int
    min_frequency_THz: float
    checks: dict
    min_frequency_by_volume_THz: list | None = None
    volumes_used: list | None = None   # the contiguous stable volumes around V0 that enter the QHA fit
    interpolation_imaginary_fraction: list | None = None  # share of mesh modes imaginary, per volume
    method: str = "QHA (isotropic volume scan, fixed cell shape)"


def _phonopy_atoms(atoms: Atoms):
    from phonopy.structure.atoms import PhonopyAtoms

    return PhonopyAtoms(symbols=atoms.get_chemical_symbols(), cell=np.asarray(atoms.cell),
                        scaled_positions=atoms.get_scaled_positions())


def _symmetrized(atoms: Atoms, symprec: float = 1e-3) -> Atoms:
    """The same crystal as a clean standard primitive cell.

    Models that are not exactly equivariant leave ~1e-4 relative noise in a relaxed cell
    (e.g. 89.997 deg instead of 90 deg), which spglib then reads as P1 and which breaks
    phonopy's Brillouin-zone setup. Symmetrising at 1e-3 Å removes only noise of that size;
    genuine changes of crystal form are far larger and are excluded upstream.
    """
    from pymatgen.io.ase import AseAtomsAdaptor
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    s = AseAtomsAdaptor.get_structure(atoms)
    try:
        ref = SpacegroupAnalyzer(s, symprec=symprec).get_refined_structure()
        prim = SpacegroupAnalyzer(ref, symprec=symprec).get_primitive_standard_structure()
        if len(prim) == len(s):
            return AseAtomsAdaptor.get_atoms(prim)
    except Exception as err:  # fall back to the cell as relaxed, lattice-reduced
        log.warning("symmetrisation failed (%s); using the LLL-reduced relaxed cell", err)
    return AseAtomsAdaptor.get_atoms(s.get_reduced_structure("LLL"))


def _make_phonopy(atoms: Atoms, reps):
    """Phonopy object; falls back to a looser symmetry tolerance, then to no symmetry, if
    spglib cannot reduce a slightly distorted relaxed cell (more displacements, same physics)."""
    from phonopy import Phonopy

    for kwargs in ({}, {"symprec": 1e-3}, {"is_symmetry": False}):
        try:
            return Phonopy(_phonopy_atoms(atoms), supercell_matrix=np.diag(reps), **kwargs)
        except Exception as err:  # spglib errors (e.g. "Niggli reduction failed")
            log.warning("phonopy setup failed (%s); retrying with %s", err, kwargs or "looser symmetry")
    raise RuntimeError("phonopy could not be set up")


def _supercell_reps(atoms: Atoms, min_width: float) -> list[int]:
    cell = np.asarray(atoms.cell)
    vol = abs(np.linalg.det(cell))
    widths = [vol / np.linalg.norm(np.cross(cell[(i + 1) % 3], cell[(i + 2) % 3])) for i in range(3)]
    return [int(math.ceil(min_width / w)) for w in widths]


def _forces_batched(engine, structs: list[Atoms], budget_pairs: int, cutoff: float):
    """Forces for many supercells, packed under the same memory budget as MD batches."""
    from ase.neighborlist import neighbor_list

    if not structs:
        return []
    per = max(1, len(neighbor_list("i", structs[0], cutoff)))
    chunk = max(1, budget_pairs // per)
    out = []
    for i in range(0, len(structs), chunk):
        _, f = engine.forces(structs[i : i + chunk])
        out += f
    return out


def run_qha(engine, material, model_key: str, relaxed: Atoms, window: list[float], cfg: dict) -> QhaResult:
    from phonopy import PhonopyQHA

    q = cfg
    relaxed = _symmetrized(relaxed)
    scales = list(q["volume_scales"])
    t_max = float(q["t_max_K"])
    reps = _supercell_reps(relaxed, q["min_supercell_width_A"])
    # 1. static energies at each volume (atoms relaxed, shape fixed)
    cells = []
    for s in scales:
        a = relaxed.copy()
        a.set_cell(np.asarray(relaxed.cell) * s ** (1 / 3), scale_atoms=True)
        cells.append(a)
    rel = engine.relax(cells, optimize_cell=False, fmax=q["fmax_eV_per_A"], max_steps=1000)
    E = [r.energy for r in rel]
    V = [r.atoms.get_volume() for r in rel]
    # 2. phonons at each volume
    per_volume = []
    for r in rel:
        ph = _make_phonopy(r.atoms, reps)
        ph.generate_displacements(distance=q["displacement_A"])
        scs = [Atoms(symbols=sc.symbols, cell=sc.cell, scaled_positions=sc.scaled_positions, pbc=True)
               for sc in ph.supercells_with_displacements]
        if q.get("subtract_reference_forces", False):
            # forces of the undisplaced supercell (residual relaxation forces and the model's
            # numerical noise) are subtracted from every displaced one
            ref = Atoms(symbols=ph.supercell.symbols, cell=ph.supercell.cell,
                        scaled_positions=ph.supercell.scaled_positions, pbc=True)
            f_all = _forces_batched(engine, [ref] + scs, q["max_pairs_per_call"], q["edge_cutoff_A"])
            ph.forces = np.array(f_all[1:]) - f_all[0][None]
        else:
            ph.forces = np.array(_forces_batched(engine, scs, q["max_pairs_per_call"], q["edge_cutoff_A"]))
        ph.produce_force_constants()
        ph.symmetrize_force_constants()  # translational invariance and index symmetry
        # stability is judged at the q-points the supercell actually samples (commensurate);
        # imaginary modes that appear only between them are Fourier-interpolation artefacts
        # (common in polar crystals, whose long-range forces a finite supercell truncates)
        comm = np.array([[i / reps[0], j / reps[1], k / reps[2]]
                         for i in range(reps[0]) for j in range(reps[1]) for k in range(reps[2])])
        ph.run_qpoints(comm)
        fmin = float(np.min(ph.get_qpoints_dict()["frequencies"]))
        ph.run_mesh(q["mesh_length"])
        mesh_f = ph.get_mesh_dict()["frequencies"]
        interp_imag = float(np.mean(mesh_f < -abs(q["imaginary_tolerance_THz"])))
        ph.run_thermal_properties(t_min=0, t_max=t_max, t_step=q["t_step_K"])
        per_volume.append((ph.get_thermal_properties_dict(), fmin, len(scs), interp_imag))
    n_disp = per_volume[0][2]
    fmins = [pv[1] for pv in per_volume]
    tol = -abs(q["imaginary_tolerance_THz"])
    # keep the contiguous run of dynamically stable volumes around the equilibrium volume:
    # a strongly stretched or compressed cell can soften into instability without the crystal
    # ever reaching that volume in the temperature window, and such volumes would corrupt F(V)
    i0 = int(np.argmin(np.abs(np.asarray(scales) - 1.0)))
    stable_at_eq = fmins[i0] > tol
    keep = []
    if stable_at_eq:
        lo_i, hi_i = i0, i0
        while lo_i - 1 >= 0 and fmins[lo_i - 1] > tol:
            lo_i -= 1
        while hi_i + 1 < len(scales) and fmins[hi_i + 1] > tol:
            hi_i += 1
        keep = list(range(lo_i, hi_i + 1))
    lo, hi = min(window), max(window)
    checks = {"dynamically_stable": bool(stable_at_eq), "enough_stable_volumes": len(keep) >= q["min_volumes"]}
    interp = [pv[3] for pv in per_volume]
    if not all(checks.values()):
        checks.update(volume_inside_scan=False, window_covered=False)
        return QhaResult(
            material=material.id, model=model_key, temperatures=[float(x) for x in window], alpha_V_1e6=float("nan"),
            alpha_V_err_1e6=0.0, alpha_V_300K_1e6=None, curve_T=[], curve_alpha_V_1e6=[], volume_scales=scales,
            supercell=reps, n_displacements=n_disp, min_frequency_THz=float(min(fmins)), checks=checks,
            min_frequency_by_volume_THz=fmins, volumes_used=[scales[i] for i in keep],
            interpolation_imaginary_fraction=interp,
        )
    checks["interpolation_artefacts_small"] = bool(max(interp[i] for i in keep) < q.get("max_interp_imaginary_fraction", 0.02))
    tps = [per_volume[i][0] for i in keep]
    temps = tps[0]["temperatures"]
    # 3. quasi-harmonic minimisation over the stable volumes
    qha = PhonopyQHA(volumes=[V[i] for i in keep], electronic_energies=[E[i] for i in keep], temperatures=temps,
                     free_energy=np.array([tp["free_energy"] for tp in tps]).T,
                     cv=np.array([tp["heat_capacity"] for tp in tps]).T,
                     entropy=np.array([tp["entropy"] for tp in tps]).T,
                     eos=q["eos"], t_max=t_max - 2 * q["t_step_K"], verbose=False)
    T = np.asarray(temps)[: len(qha.thermal_expansion)]
    alpha = np.asarray(qha.thermal_expansion) * 1e6
    vol_T = np.asarray(qha.volume_temperature)[: len(T)]
    Vk = [V[i] for i in keep]
    sel = (T >= lo) & (T <= hi)
    a_win = float(np.mean(alpha[sel])) if sel.any() else float("nan")
    a300 = float(np.interp(300.0, T, alpha)) if T.max() >= 300 else None
    inside = bool(vol_T[sel].max() < max(Vk) and vol_T[sel].min() > min(Vk)) if sel.any() else False
    grid = [t for t in range(0, int(T.max()) + 1, 50)]
    checks.update(volume_inside_scan=inside, window_covered=bool(sel.any() and T.max() >= hi))
    return QhaResult(
        material=material.id, model=model_key, temperatures=[float(x) for x in window], alpha_V_1e6=a_win,
        alpha_V_err_1e6=0.0, alpha_V_300K_1e6=a300, curve_T=grid,
        curve_alpha_V_1e6=[float(np.interp(t, T, alpha)) for t in grid], volume_scales=scales, supercell=reps,
        n_displacements=n_disp, min_frequency_THz=float(min(fmins[i] for i in keep)), checks=checks,
        min_frequency_by_volume_THz=fmins, volumes_used=[scales[i] for i in keep],
        interpolation_imaginary_fraction=interp,
    )


def to_record(r: QhaResult) -> dict:
    return asdict(r)
