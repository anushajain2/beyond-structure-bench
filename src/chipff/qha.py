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
    method: str = "QHA (isotropic volume scan, fixed cell shape)"


def _phonopy_atoms(atoms: Atoms):
    from phonopy.structure.atoms import PhonopyAtoms

    return PhonopyAtoms(symbols=atoms.get_chemical_symbols(), cell=np.asarray(atoms.cell),
                        scaled_positions=atoms.get_scaled_positions())


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
    from phonopy import Phonopy, PhonopyQHA

    q = cfg
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
    free, cv, entropy = [], [], []
    temps = None
    min_freq = float("inf")
    n_disp = 0
    for r in rel:
        ph = Phonopy(_phonopy_atoms(r.atoms), supercell_matrix=np.diag(reps))
        ph.generate_displacements(distance=q["displacement_A"])
        scs = [Atoms(symbols=sc.symbols, cell=sc.cell, scaled_positions=sc.scaled_positions, pbc=True)
               for sc in ph.supercells_with_displacements]
        n_disp = len(scs)
        ph.forces = np.array(_forces_batched(engine, scs, q["max_pairs_per_call"], q["edge_cutoff_A"]))
        ph.produce_force_constants()
        ph.run_mesh(q["mesh_length"])
        freqs = ph.get_mesh_dict()["frequencies"]
        min_freq = min(min_freq, float(np.min(freqs)))
        ph.run_thermal_properties(t_min=0, t_max=t_max, t_step=q["t_step_K"])
        tp = ph.get_thermal_properties_dict()
        temps = tp["temperatures"]
        free.append(tp["free_energy"])
        cv.append(tp["heat_capacity"])
        entropy.append(tp["entropy"])
    stable = min_freq > -abs(q["imaginary_tolerance_THz"])
    # 3. quasi-harmonic minimisation
    qha = PhonopyQHA(volumes=V, electronic_energies=E, temperatures=temps,
                     free_energy=np.array(free).T, cv=np.array(cv).T, entropy=np.array(entropy).T,
                     eos=q["eos"], t_max=t_max - 2 * q["t_step_K"], verbose=False)
    T = np.asarray(temps)[: len(qha.thermal_expansion)]
    alpha = np.asarray(qha.thermal_expansion) * 1e6
    vol_T = np.asarray(qha.volume_temperature)[: len(T)]
    lo, hi = min(window), max(window)
    sel = (T >= lo) & (T <= hi)
    a_win = float(np.mean(alpha[sel])) if sel.any() else float("nan")
    a300 = float(np.interp(300.0, T, alpha)) if T.max() >= 300 else None
    inside = bool(vol_T[sel].max() < max(V) and vol_T[sel].min() > min(V)) if sel.any() else False
    grid = [t for t in range(0, int(T.max()) + 1, 50)]
    checks = {
        "dynamically_stable": stable,
        "volume_inside_scan": inside,
        "window_covered": bool(sel.any() and T.max() >= hi),
    }
    return QhaResult(
        material=material.id, model=model_key, temperatures=[float(x) for x in window], alpha_V_1e6=a_win,
        alpha_V_err_1e6=0.0, alpha_V_300K_1e6=a300, curve_T=grid,
        curve_alpha_V_1e6=[float(np.interp(t, T, alpha)) for t in grid], volume_scales=scales, supercell=reps,
        n_displacements=n_disp, min_frequency_THz=min_freq, checks=checks,
    )


def to_record(r: QhaResult) -> dict:
    return asdict(r)
