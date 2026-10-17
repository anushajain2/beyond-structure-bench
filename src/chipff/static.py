"""Zero-temperature properties: lattice constants and bulk modulus.

Three calculations per model, all through kUPS:

1. Lattice: relax atoms and cell from the Materials Project structure (L-BFGS,
   fmax 0.001 eV/Å, kUPS's Frechet cell filter). Check convergence and that the
   space group is unchanged.
2. Elastic tensor: apply the 24 standard strains MP uses (6 Voigt components ×
   ±0.5 %, ±1 %), relax atom positions at each fixed strained cell, read the
   stress from kUPS, and fit C_ij. Gives K_Voigt, K_Reuss, K_VRH and G_VRH.
   K_Reuss is the true hydrostatic bulk modulus of a single crystal; K_VRH is
   the definition Materials Project reports.
3. Equation of state: scale the relaxed cell to 9 volumes between −6 % and
   +6 %, relax positions at each, fit Birch–Murnaghan. The cell shape is held
   fixed, so this is exact for cubic crystals and an upper-bound-like estimate
   otherwise; it serves as an independent cross-check on (2).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

import numpy as np
from ase import Atoms

from chipff.engine import Engine
from chipff.materials import Material, mp_structure

log = logging.getLogger(__name__)

STRAINS = (-0.01, -0.005, 0.005, 0.01)
EOS_VOLUME_SCALES = tuple(np.linspace(0.94, 1.06, 9))


def _pmg(atoms: Atoms):
    from pymatgen.io.ase import AseAtomsAdaptor

    return AseAtomsAdaptor.get_structure(atoms)


def _ase(struct):
    from pymatgen.io.ase import AseAtomsAdaptor

    return AseAtomsAdaptor.get_atoms(struct)


def symmetry(atoms: Atoms) -> dict:
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    s = _pmg(atoms)
    out = {}
    for prec in (0.01, 0.1):
        sga = SpacegroupAnalyzer(s, symprec=prec)
        out[f"spg_{prec}"] = sga.get_space_group_number()
    sga = SpacegroupAnalyzer(s, symprec=0.1)
    out["symbol"] = sga.get_space_group_symbol()
    conv = sga.get_conventional_standard_structure()
    lat = conv.lattice
    out["conventional"] = {"a": lat.a, "b": lat.b, "c": lat.c, "alpha": lat.alpha, "beta": lat.beta, "gamma": lat.gamma}
    out["volume_per_atom"] = s.volume / len(s)
    return out


@dataclass
class LatticeResult:
    material: str
    model: str
    converged: bool
    fmax: float
    cell_grad: float
    steps: int
    energy_per_atom: float
    spg_start: int
    spg_end: int
    symmetry_kept: bool
    a: float
    b: float
    c: float
    alpha: float
    beta: float
    gamma: float
    volume_per_atom: float
    structure: dict  # relaxed structure (pymatgen dict), reused by later steps


def run_lattice(engine: Engine, materials: list[Material], fmax: float = 1e-3, max_steps: int = 2000) -> list[LatticeResult]:
    starts = [mp_structure(m.id) for m in materials]
    res = engine.relax(starts, optimize_cell=True, fmax=fmax, max_steps=max_steps)
    out = []
    for m, a0, r in zip(materials, starts, res):
        s0, s1 = symmetry(a0), symmetry(r.atoms)
        conv = s1["conventional"]
        out.append(
            LatticeResult(
                material=m.id, model=engine.model.key, converged=r.converged, fmax=r.fmax, cell_grad=r.max_cell_grad,
                steps=r.steps, energy_per_atom=r.energy / len(r.atoms), spg_start=s0["spg_0.1"], spg_end=s1["spg_0.1"],
                symmetry_kept=s0["spg_0.1"] == s1["spg_0.1"], volume_per_atom=s1["volume_per_atom"],
                structure=_pmg(r.atoms).as_dict(), **conv,
            )
        )
    return out


@dataclass
class ElasticResult:
    material: str
    model: str
    C_voigt_GPa: list  # 6x6
    K_voigt_GPa: float
    K_reuss_GPa: float
    K_vrh_GPa: float
    G_vrh_GPa: float
    min_eigenvalue_GPa: float
    mechanically_stable: bool
    asymmetry_rel: float  # max |C_ij - C_ji| / max |C|: large = nonlinear response, fit unreliable
    residual_stress_GPa: float  # |stress| of the unstrained relaxed cell
    fit_rms_GPa: float
    all_converged: bool


def elastic_moduli(C_raw) -> dict:
    """Moduli from the symmetrized stiffness matrix (Voigt notation, GPa)."""
    from pymatgen.analysis.elasticity import ElasticTensor

    C_raw = np.asarray(C_raw, float)
    C = 0.5 * (C_raw + C_raw.T)
    et = ElasticTensor.from_voigt(C)
    eig = float(np.min(np.linalg.eigvalsh(C)))
    return {
        "K_voigt_GPa": float(et.k_voigt), "K_reuss_GPa": float(et.k_reuss), "K_vrh_GPa": float(et.k_vrh),
        "G_vrh_GPa": float(et.g_vrh), "min_eigenvalue_GPa": eig, "mechanically_stable": eig > 0,
        "asymmetry_rel": float(np.max(np.abs(C_raw - C_raw.T)) / np.max(np.abs(C_raw))),
    }


def _batched(engine: Engine, structs: list[Atoms], fmax: float, chunk: int):
    """Positions-only relax + stress for many structures, in chunks of ``chunk``."""
    rel, stresses = [], []
    for i in range(0, len(structs), chunk):
        r = engine.relax(structs[i : i + chunk], optimize_cell=False, fmax=fmax, max_steps=1000)
        _, s = engine.stress([x.atoms for x in r])
        rel += r
        stresses += list(s)
    return rel, stresses


def run_elastic(
    engine: Engine, materials: list[Material], relaxed: dict[str, Atoms], fmax: float = 1e-3, chunk: int = 48
) -> list[ElasticResult]:
    from pymatgen.analysis.elasticity import ElasticTensor
    from pymatgen.analysis.elasticity.strain import Deformation, Strain
    from pymatgen.analysis.elasticity.stress import Stress

    plan, structs = [], []
    for m in materials:
        base = _pmg(relaxed[m.id])
        for comp in range(6):
            for d in STRAINS:
                v = np.zeros(6)
                v[comp] = d
                strain = Strain.from_voigt(v)
                plan.append((m.id, strain))
                structs.append(_ase(Deformation(strain.get_deformation_matrix()).apply_to_structure(base)))
    rel, stresses = _batched(engine, structs, fmax, chunk)
    _, eq_all = engine.stress([relaxed[m.id] for m in materials])

    out = []
    for k, m in enumerate(materials):
        idx = [i for i, (mid, _) in enumerate(plan) if mid == m.id]
        strains = [plan[i][1] for i in idx]
        st = [stresses[i] for i in idx]
        eq_stress = Stress(eq_all[k])
        et = ElasticTensor.from_independent_strains(
            [Strain(s) for s in strains], [Stress(s) for s in st], eq_stress=eq_stress, vasp=False, tol=1e-10
        )
        C_raw = np.asarray(et.voigt)
        # fit residual: how well linear elasticity reproduces the computed stresses
        pred = [np.asarray(et.calculate_stress(s)) + np.asarray(eq_stress) for s in strains]
        rms = float(np.sqrt(np.mean([(p - np.asarray(s)) ** 2 for p, s in zip(pred, st)])))
        moduli = elastic_moduli(C_raw)
        out.append(
            ElasticResult(
                material=m.id, model=engine.model.key, C_voigt_GPa=C_raw.round(3).tolist(), **moduli,
                residual_stress_GPa=float(np.abs(eq_all[k]).max()), fit_rms_GPa=rms,
                all_converged=all(rel[i].converged for i in idx),
            )
        )
        log.info("%s %s K_vrh=%.1f GPa", engine.model.key, m.id, et.k_vrh)
    return out


@dataclass
class EosResult:
    material: str
    model: str
    B0_GPa: float
    B0_prime: float
    V0_per_atom: float
    V0_vs_relaxed_pct: float  # self-check: EOS minimum vs relaxed volume
    r2: float
    max_rel_residual: float
    min_at_edge: bool  # flag a lopsided scan (minimum not inside the scanned range)
    volumes: list
    energies: list
    fit_ok: bool


def run_eos(
    engine: Engine, materials: list[Material], relaxed: dict[str, Atoms], fmax: float = 1e-3, chunk: int = 54
) -> list[EosResult]:
    from pymatgen.analysis.eos import EOS

    structs = []
    for m in materials:
        a0 = relaxed[m.id]
        for s in EOS_VOLUME_SCALES:
            a = a0.copy()
            a.set_cell(a.cell * s ** (1 / 3), scale_atoms=True)
            structs.append(a)
    rel = []
    for i in range(0, len(structs), chunk):
        rel += engine.relax(structs[i : i + chunk], optimize_cell=False, fmax=fmax, max_steps=1000)

    out = []
    nv = len(EOS_VOLUME_SCALES)
    for k, m in enumerate(materials):
        a0 = relaxed[m.id]
        n = len(a0)
        sl = slice(k * nv, (k + 1) * nv)
        V = np.array([a.get_volume() / n for a in structs[sl]])
        E = np.array([r.energy / n for r in rel[sl]])
        fit = EOS("birch_murnaghan").fit(V, E)
        Efit = np.array([fit.func(v) for v in V])
        ss_res = float(np.sum((E - Efit) ** 2))
        ss_tot = float(np.sum((E - E.mean()) ** 2))
        r2 = 1 - ss_res / ss_tot
        span = E.max() - E.min()
        max_rel = float(np.max(np.abs(E - Efit)) / span)
        v_relaxed = a0.get_volume() / n
        edge = int(np.argmin(E)) in (0, len(E) - 1)
        out.append(
            EosResult(
                material=m.id, model=engine.model.key, B0_GPa=float(fit.b0_GPa), B0_prime=float(fit.b1),
                V0_per_atom=float(fit.v0), V0_vs_relaxed_pct=100 * (fit.v0 / v_relaxed - 1), r2=r2,
                max_rel_residual=max_rel, min_at_edge=edge, volumes=V.round(5).tolist(), energies=E.round(7).tolist(),
                fit_ok=(r2 > 0.999 and max_rel < 0.01 and not edge),
            )
        )
    return out


def to_records(items) -> list[dict]:
    return [asdict(x) for x in items]
