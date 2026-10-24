"""Axial thermal expansion (along a and c) for uniaxial crystals, in the quasi-harmonic Grüneisen approximation.

The published QHA (chipff.qha) scales the cell isotropically, so it gives only the volumetric alpha_V. A layer grown
on a substrate feels its *in-plane* expansion, which for wurtzite GaN and AlN, hcp Ru and sapphire differs from
alpha_V/3. This module computes alpha_a and alpha_c for those materials:

1. Take the model's relaxed cell (symmetrised as in chipff.qha) with its unique axis along z, and apply four small
   strains that keep the crystal's symmetry: in-plane biaxial (e_xx = e_yy = +/-delta) and axial (e_zz = +/-delta).
2. At each strained cell, relax the atoms, compute the static stress, and the harmonic phonons and vibrational free
   energy F_vib(T) exactly as chipff.qha does (finite displacements, reference forces subtracted, force constants
   symmetrised, Gamma acoustic modes excluded).
3. With mode coordinates m = (x, z) for the two strains, the vibrational "force" is g_m(T) = dF_vib/dm (central
   differences) and the static stiffness is H_mn = d(dE/dm)/dn, from the stresses (dE/dx = V(s_xx + s_yy),
   dE/dz = V s_zz). The thermal strain minimising E + F_vib is m(T) = -H^-1 g(T) + const, so
   alpha_a = dx/dT and alpha_c = dz/dT.

This first-order (Grüneisen) treatment neglects how the phonons change between the strained cells beyond the linear
term, so it is checked against the full isotropic QHA: 2 alpha_a + alpha_c should reproduce alpha_V near 300 K.
"""

from __future__ import annotations

import logging

import numpy as np
from ase import Atoms

log = logging.getLogger("chipff")

AXIAL_MATERIALS = ["GaN", "AlN", "Ru", "Al2O3"]   # uniaxial, with axis-resolved experimental expansion
DELTA = 0.005                                     # strain step (0.5 %)
KJ_PER_MOL_TO_EV = 0.010364269656262175
EV_PER_A3_TO_GPA = 160.21766208


def _strained(atoms: Atoms, mode: str, sign: int) -> Atoms:
    e = np.zeros((3, 3))
    if mode == "x":
        e[0, 0] = e[1, 1] = sign * DELTA
    else:
        e[2, 2] = sign * DELTA
    a = atoms.copy()
    a.set_cell(np.asarray(atoms.cell) @ (np.eye(3) + e), scale_atoms=True)
    return a


def _unique_axis_to_z(atoms: Atoms, symprec: float = 1e-3) -> Atoms:
    """Rotate the crystal so its highest-order rotation axis (3-, 4- or 6-fold) lies along z. Rhombohedral primitive
    cells (sapphire) otherwise have the three-fold axis off z, and in-plane strain in xy breaks their symmetry."""
    import spglib

    L = np.asarray(atoms.cell)
    ops = spglib.get_symmetry((L, atoms.get_scaled_positions(), atoms.numbers), symprec=symprec)["rotations"]
    best, order = None, 2
    for R in ops:
        if round(np.linalg.det(R)) != 1:
            continue
        Rc = L.T @ R @ np.linalg.inv(L.T)                               # Cartesian rotation
        n = next((k for k in range(1, 7) if np.allclose(np.linalg.matrix_power(Rc, k), np.eye(3), atol=1e-6)), 0)
        if n > order:
            w, v = np.linalg.eig(Rc)
            best, order = np.real(v[:, np.argmin(np.abs(w - 1))]), n
    a = atoms.copy()
    if best is not None and abs(abs(best[2]) - np.linalg.norm(best)) > 1e-6:
        a.rotate(best / np.linalg.norm(best), "z", rotate_cell=True)
    return a


def _spacegroup(atoms: Atoms, symprec: float = 1e-3) -> int:
    import spglib

    return spglib.get_symmetry_dataset((np.asarray(atoms.cell), atoms.get_scaled_positions(), atoms.numbers),
                                       symprec=symprec).number


def _phonon_free_energy(engine, atoms: Atoms, reps, q: dict, t_max: float):
    """F_vib(T) in eV per atom, and the lowest frequency at the supercell's commensurate q-points (THz)."""
    from chipff.qha import _forces_batched, _make_phonopy

    ph = _make_phonopy(atoms, reps)
    ph.generate_displacements(distance=q["displacement_A"])
    scs = [Atoms(symbols=sc.symbols, cell=sc.cell, scaled_positions=sc.scaled_positions, pbc=True)
           for sc in ph.supercells_with_displacements]
    ref = Atoms(symbols=ph.supercell.symbols, cell=ph.supercell.cell, scaled_positions=ph.supercell.scaled_positions,
                pbc=True)
    f_all = _forces_batched(engine, [ref] + scs, q["max_pairs_per_call"], q["edge_cutoff_A"])
    ph.forces = np.array(f_all[1:]) - f_all[0][None]
    ph.produce_force_constants()
    ph.symmetrize_force_constants()
    comm = np.array([[i / reps[0], j / reps[1], k / reps[2]]
                     for i in range(reps[0]) for j in range(reps[1]) for k in range(reps[2])])
    ph.run_qpoints(comm)
    fmin = float(np.min(ph.get_qpoints_dict()["frequencies"]))
    ph.run_mesh(q["mesh_length"])
    ph.run_thermal_properties(t_min=0, t_max=t_max, t_step=q["t_step_K"], exclude_gamma_acoustic=True)
    tp = ph.get_thermal_properties_dict()
    n = len(ph.primitive)
    return np.asarray(tp["temperatures"]), np.asarray(tp["free_energy"]) * KJ_PER_MOL_TO_EV / n, fmin, len(scs)


def run_axial(engine, material, model_key: str, relaxed: Atoms, cfg: dict) -> dict:
    from chipff.qha import _supercell_reps, _symmetrized

    q = cfg
    t_max = float(q["t_max_K"])
    a0 = _unique_axis_to_z(_symmetrized(relaxed))
    cell = np.asarray(a0.cell)
    # the strain modes assume the unique axis along z: in-plane biaxial strain must keep the symmetry
    sg0 = _spacegroup(a0)
    reps = _supercell_reps(a0, q["min_supercell_width_A"])
    keys = [("x", +1), ("x", -1), ("z", +1), ("z", -1)]
    cells = [_strained(a0, m, s) for m, s in keys]
    symmetry_kept = all(_spacegroup(c) == sg0 for c in cells)
    rel = engine.relax(cells, optimize_cell=False, fmax=q["fmax_eV_per_A"], max_steps=1000)
    strained = {k: r.atoms for k, r in zip(keys, rel)}
    _, S = engine.stress([strained[k] for k in keys])
    S = {k: s / EV_PER_A3_TO_GPA for k, s in zip(keys, S)}          # eV/Å^3, tensile positive
    v_atom = abs(np.linalg.det(cell)) / len(a0)
    # dE/dm per atom at each strained cell: dE/dx = V (s_xx + s_yy), dE/dz = V s_zz
    dEdm = {k: np.array([v_atom * (S[k][0, 0] + S[k][1, 1]), v_atom * S[k][2, 2]]) for k in keys}
    H = np.column_stack([(dEdm[("x", 1)] - dEdm[("x", -1)]) / (2 * DELTA),
                         (dEdm[("z", 1)] - dEdm[("z", -1)]) / (2 * DELTA)])
    H = 0.5 * (H + H.T)
    F, fmins, n_disp = {}, {}, {}
    for k in keys:
        T, F[k], fmins[k], n_disp[k] = _phonon_free_energy(engine, strained[k], reps, q, t_max)
    g = np.column_stack([(F[("x", 1)] - F[("x", -1)]) / (2 * DELTA), (F[("z", 1)] - F[("z", -1)]) / (2 * DELTA)])
    m = -np.linalg.solve(H, g.T).T                                     # thermal strain (x, z) at each T
    alpha = np.gradient(m, T, axis=0) * 1e6                            # 1e-6 / K
    alpha_a, alpha_c = alpha[:, 0], alpha[:, 1]
    tol = -abs(q["imaginary_tolerance_THz"])
    grid = list(range(0, int(T.max()) + 1, 50))
    at = lambda arr, t: float(np.interp(t, T, arr))  # noqa: E731
    checks = {"dynamically_stable": all(f > tol for f in fmins.values()), "symmetry_kept": bool(symmetry_kept),
              "stiffness_positive": bool(np.all(np.linalg.eigvalsh(H) > 0))}
    log.info("%s %s: axial alpha_a(300 K) = %.2f, alpha_c = %.2f e-6/K%s", model_key, material.id, at(alpha_a, 300),
             at(alpha_c, 300), "" if all(checks.values()) else f"  CHECK: {[c for c, v in checks.items() if not v]}")
    return {"material": material.id, "model": model_key, "supercell": reps, "delta": DELTA, "spacegroup": sg0,
            "n_displacements": {f"{m}{s:+d}": v for (m, s), v in n_disp.items()}, "min_frequency_THz": {f"{m}{s:+d}": v for (m, s), v in fmins.items()},
            "stiffness_eV_per_atom": H.tolist(), "checks": checks,
            "alpha_a_300K_1e6": at(alpha_a, 300), "alpha_c_300K_1e6": at(alpha_c, 300),
            "alpha_V_300K_1e6": at(2 * alpha_a + alpha_c, 300),
            "curve_T": grid, "curve_alpha_a_1e6": [at(alpha_a, t) for t in grid],
            "curve_alpha_c_1e6": [at(alpha_c, t) for t in grid],
            "method": "quasi-harmonic Grüneisen approximation, in-plane biaxial and axial strains of +/-0.5 %"}
