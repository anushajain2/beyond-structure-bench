"""Matched PBE references for the thermal-failure study (docs/matched_dft_plan.md, sections 5-6).

PBE with Quantum ESPRESSO 7.6 and SSSP 1.3.0 PBE efficiency pseudopotentials, analysed with the study's own
functions (scripts/thermal_failure_study.py: gruneisen, special_point_gamma, qha_alpha), so that the PBE numbers
are computed exactly as the models' are.

  Si    the benchmark's route: 9 volumes (configs/benchmark.yaml thermal_qha), 4x4x4 primitive supercell
        (128 atoms), phonopy's 0.01 Å displacement; plus 0.985 / 1.015 V0 for gamma. Static E(V) from the
        primitive cell. The undisplaced reference supercell is not computed: its forces vanish by symmetry.
  GaAs  DFPT on the primitive cell at 0.985 / 1.0 / 1.015 V0, 4x4x4 q-grid (the q-points the benchmark's
        4x4x4 supercell samples). Born charges and the dielectric tensor are stripped before q2r.x, so the
        force constants carry no non-analytic correction, as in the MLIP pipeline.

V0 is PBE's own (vc-relax with the same settings): a = 10.33509 bohr (Si), 10.85723 bohr (GaAs).

Steps (QE runs happen outside Python, in the work directory; PYTHONPATH=src .venv/bin/python):
  prep     write QE inputs and the phonopy displacement metadata to --work
  analyze  parse QE outputs -> results/matched_dft/pbe_qe.csv and phonons/*.npz
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.build import bulk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thermal_failure_study as tfs  # noqa: E402

from chipff.materials import ROOT  # noqa: E402

OUT = ROOT / "results" / "matched_dft"
WORK = Path.home() / "chipff-dft"
PSEUDO = WORK / "sssp_1.3.0_pbe_eff"
RY_EV = 13.605693122994
RY_BOHR_EV_A = RY_EV / 0.529177210903
BOHR_A = 0.529177210903
GAMMA_SCALES = [0.985, 1.0, 1.015]
SETUP = {
    "Si": dict(a_bohr=10.33509, ecut=(30, 240), species=[("Si", 28.0855, "Si.pbe-n-rrkjus_psl.1.0.0.UPF")],
               k_prim=12, k_super=2),
    "GaAs": dict(a_bohr=10.85723, ecut=(70, 560), k_prim=8,
                 species=[("Ga", 69.723, "Ga.pbe-dn-kjpaw_psl.1.0.0.UPF"),
                          ("As", 74.9216, "As.pbe-n-rrkjus_psl.0.2.UPF")]),
}


def pw_input(atoms: Atoms, mid: str, kmesh: int, prefix: str, forces: bool) -> str:
    s = SETUP[mid]
    lines = ["&control", f" calculation='scf', prefix='{prefix}', outdir='./tmp', pseudo_dir='{PSEUDO}',",
             f" tprnfor={'.true.' if forces else '.false.'}", "/",
             "&system", f" ibrav=0, nat={len(atoms)}, ntyp={len(s['species'])}, ecutwfc={s['ecut'][0]}, "
             f"ecutrho={s['ecut'][1]}, occupations='fixed'", "/",
             "&electrons", " conv_thr=1e-10" if forces else " conv_thr=1e-12", "/", "ATOMIC_SPECIES"]
    lines += [f" {el} {m} {pp}" for el, m, pp in s["species"]]
    lines += ["CELL_PARAMETERS angstrom"] + [" %.10f %.10f %.10f" % tuple(v) for v in atoms.cell]
    lines += ["ATOMIC_POSITIONS crystal"]
    lines += [" %s %.10f %.10f %.10f" % (el, *p) for el, p in zip(atoms.get_chemical_symbols(),
                                                                   atoms.get_scaled_positions())]
    lines += ["K_POINTS automatic", f" {kmesh} {kmesh} {kmesh} 0 0 0"]
    return "\n".join(lines) + "\n"


def prim(mid: str) -> Atoms:
    from chipff.qha import _symmetrized

    a = SETUP[mid]["a_bohr"] * BOHR_A
    return _symmetrized(bulk("Si", "diamond", a=a)) if mid == "Si" else bulk("GaAs", "zincblende", a=a)


def scaled(p: Atoms, s: float) -> Atoms:
    c = p.copy()
    c.set_cell(np.asarray(p.cell) * s ** (1 / 3), scale_atoms=True)
    return c


def si_scales() -> list[float]:
    return sorted(set(tfs.BASE_SCALES) | set(GAMMA_SCALES))


def cmd_prep(a):
    from chipff.qha import _supercell_reps

    q = tfs.cfg_qha()
    # Si: supercell route
    p = prim("Si")
    reps = _supercell_reps(p, q["min_supercell_width_A"])
    meta = dict(scales=[], reps=reps, numbers=p.numbers.tolist(), cells=[], frac=[], disp_atoms=[], disp_vecs=[])
    for s in si_scales():
        c = scaled(p, s)
        d = a.work / "si" / f"v{s:.3f}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "prim.in").write_text(pw_input(c, "Si", SETUP["Si"]["k_prim"], "prim", forces=False))
        ph = tfs._phonopy(c, reps)
        ph.generate_displacements(distance=q["displacement_A"], is_plusminus="auto")
        for j, sc in enumerate(ph.supercells_with_displacements):
            at = Atoms(symbols=sc.symbols, cell=sc.cell, scaled_positions=sc.scaled_positions, pbc=True)
            (d / f"disp{j}.in").write_text(pw_input(at, "Si", SETUP["Si"]["k_super"], f"disp{j}", forces=True))
        meta["scales"].append(s)
        meta["cells"].append(np.asarray(c.cell).tolist())
        meta["frac"].append(c.get_scaled_positions().tolist())
        meta["disp_atoms"].append([int(x["number"]) for x in ph.dataset["first_atoms"]])
        meta["disp_vecs"].append([np.asarray(x["displacement"]).tolist() for x in ph.dataset["first_atoms"]])
    (a.work / "si" / "meta.json").write_text(json.dumps(meta, indent=1))
    # DFPT at the three gamma volumes: GaAs, and Si as a check on the supercell route
    for mid, sub in (("GaAs", "gaas"), ("Si", "si_dfpt")):
        dfpt_inputs(a.work, mid, sub, GAMMA_SCALES)
    print(f"inputs written under {a.work}")


def dfpt_inputs(work: Path, mid: str, sub: str, scales):
    p = prim(mid)
    k = 8 if mid == "Si" else SETUP[mid]["k_prim"]  # Si: 8x8x8, as the 2x2x2 mesh of the 4x4x4 supercell
    for s in scales:
        d = work / sub / f"v{s:.3f}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "scf.in").write_text(pw_input(scaled(p, s), mid, k, "gaas", forces=False))
        (d / "ph.in").write_text("phonons on the 4x4x4 grid\n&inputph\n prefix='gaas', outdir='./tmp', "
                                 "fildyn='gaas.dyn', tr2_ph=1e-16, ldisp=.true., nq1=4, nq2=4, nq3=4\n/\n")
        (d / "q2r.in").write_text("&input\n fildyn='nonac.dyn', zasr='simple', flfrc='gaas_nonac.fc'\n/\n")


def dfpt_row(work: Path, mid: str, sub: str, q: dict) -> dict | None:
    """C_V-weighted and zone-edge gamma from DFPT force constants at the three gamma volumes."""
    dirs = [work / sub / f"v{s:.3f}" for s in GAMMA_SCALES]
    if not all((d / "gaas_nonac.fc").exists() for d in dirs):
        return None
    p = prim(mid)
    pv = []
    for s, d in zip(GAMMA_SCALES, dirs):
        ph = gaas_phonopy(d / "gaas_nonac.fc", scaled(p, s))
        ph.run_mesh(q["mesh_length"])
        pv.append(dict(ph=ph, mesh=ph.mesh.mesh_numbers.tolist(), freqs=ph.get_mesh_dict()["frequencies"]))
        np.save(OUT / "phonons" / f"{mid}_pbe_qe_dfpt_fc_v{s:.3f}.npy", ph.force_constants)
    g = tfs.gruneisen(dict(scales=np.array(GAMMA_SCALES)), pv)
    sp = tfs.special_point_gamma(pv, GAMMA_SCALES, mid)
    return dict(material=mid, route="DFPT 4x4x4 q, no NAC", **g, **sp)


# --------------------------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------------------------
def pw_energy_eV(f: Path) -> float:
    m = re.findall(r"^!\s+total energy\s+=\s+(-?\d+\.\d+) Ry", f.read_text(), re.M)
    if not m:
        raise RuntimeError(f"no converged energy in {f}")
    return float(m[-1]) * RY_EV


def pw_forces_eVA(f: Path, nat: int) -> np.ndarray:
    t = f.read_text()
    if "convergence has been achieved" not in t:
        raise RuntimeError(f"SCF not converged in {f}")
    blk = t.split("Forces acting on atoms")[-1]
    rows = re.findall(r"atom\s+\d+\s+type\s+\d+\s+force\s+=\s+(\S+)\s+(\S+)\s+(\S+)", blk)[:nat]
    return np.array(rows, dtype=float) * RY_BOHR_EV_A


def strip_nac(src: Path, dst: Path):
    """Copy QE dynamical-matrix files, removing the dielectric tensor and Born charges from the Gamma file."""
    for f in sorted(src.parent.glob(src.name + "*")):
        txt = f.read_text()
        if "Dielectric Tensor" in txt:
            txt = re.sub(r"\n\s*Dielectric Tensor:.*?(?=\n\s*Diagonalizing the dynamical matrix)", "", txt, flags=re.S)
        (dst.parent / f.name.replace(src.name, dst.name)).write_text(txt)


def gaas_phonopy(fc_file: Path, cell: Atoms):
    from phonopy.interface.qe import PH_Q2R

    from chipff.qha import _phonopy_atoms

    q2r = PH_Q2R(str(fc_file))
    q2r.run(_phonopy_atoms(cell), is_full_fc=True)
    ph = tfs._phonopy(cell, q2r.dimension.tolist(), symmetry=True)
    ph.force_constants = q2r.fc * RY_EV / BOHR_A**2  # q2r.x writes Ry/bohr^2; the study's phonopy objects use eV/Å^2
    ph.symmetrize_force_constants()
    return ph


# --------------------------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------------------------
def si_dataset(work: Path) -> dict:
    meta = json.loads((work / "si" / "meta.json").read_text())
    d = dict(scales=np.array(meta["scales"]), reps=np.array(meta["reps"]), numbers=np.array(meta["numbers"]),
             cells=np.array(meta["cells"]), frac=np.array(meta["frac"]), symmetry=True)
    nsc = len(meta["numbers"]) * int(np.prod(meta["reps"]))
    E, V, n_disp = [], [], []
    for i, s in enumerate(meta["scales"]):
        vd = work / "si" / f"v{s:.3f}"
        E.append(pw_energy_eV(vd / "prim.out"))
        V.append(abs(np.linalg.det(np.array(meta["cells"][i]))))
        f = [pw_forces_eVA(vd / f"disp{j}.out", nsc) for j in range(len(meta["disp_atoms"][i]))]
        d[f"forces_{i}"] = np.array(f)  # reference forces are zero by symmetry
        d[f"disp_atoms_{i}"] = np.array(meta["disp_atoms"][i])
        d[f"disp_vecs_{i}"] = np.array(meta["disp_vecs"][i])
        n_disp.append(len(f))
    d.update(E=np.array(E), V=np.array(V), n_disp=np.array(n_disp))
    return d


def si_dfpt_qha(work: Path, q: dict) -> dict | None:
    """Full QHA for Si from DFPT force constants at every volume, through the study's per_volume and qha_alpha.

    Static energies are the primitive-cell SCFs of the supercell route (12x12x12 k)."""
    scales = si_scales()
    dirs = [work / "si_dfpt" / f"v{s:.3f}" for s in scales]
    if not all((d / "gaas_nonac.fc").exists() for d in dirs):
        return None
    p = prim("Si")
    cells = [scaled(p, s) for s in scales]
    phs = [gaas_phonopy(d / "gaas_nonac.fc", c) for d, c in zip(dirs, cells)]
    d = dict(scales=np.array(scales), reps=np.array([4, 4, 4]), V=np.array([c.get_volume() for c in cells]),
             E=np.array([pw_energy_eV(work / "si" / f"v{s:.3f}" / "prim.out") for s in scales]))
    orig = tfs.phonopy_at
    tfs.phonopy_at = lambda _d, i: phs[i]  # the study's per-volume analysis, on DFPT force constants
    try:
        T, pv = tfs.per_volume(d, q)
    finally:
        tfs.phonopy_at = orig
    r = tfs.qha_alpha(d, pv, T, tfs.BASE_SCALES, q, [500, 800], mode="clean")
    g = tfs.gruneisen(d, pv)
    return dict(material="Si", route="DFPT 4x4x4 q, full QHA (9 volumes)", alpha300=r["alpha300"],
                alpha_window_500_800=r["alpha_win"], KT300_GPa=r.get("KT300"), K0_static_GPa=r.get("K0"),
                V300=r.get("V300"), volumes_used=" ".join(map(str, r.get("volumes_used", []))),
                inside_scan=r.get("inside"), gamma=g["gamma"], cv_kB_per_atom=g["cv_kB_per_atom"])


def cmd_analyze(a):
    q = tfs.cfg_qha()
    (OUT / "phonons").mkdir(parents=True, exist_ok=True)
    rows = []
    if (a.work / "si" / "v1.080" / "disp0.out").exists():
        d = si_dataset(a.work)
        np.savez(OUT / "phonons" / "Si_pbe_qe.npz", **{k: v for k, v in d.items() if k != "symmetry"})
        T, pv = tfs.per_volume(d, q)
        r = tfs.qha_alpha(d, pv, T, tfs.BASE_SCALES, q, [500, 800], mode="clean")
        g = tfs.gruneisen(d, pv)
        sp = tfs.special_point_gamma(pv, list(np.round(d["scales"], 4)), "Si")
        rows.append(dict(material="Si", route="supercell 128 atoms, 0.01 Å", alpha300=r["alpha300"],
                         KT300_GPa=r.get("KT300"), K0_static_GPa=r.get("K0"), V300=r.get("V300"), **g, **sp))
    for mid, sub in (("Si", "si_dfpt"), ("GaAs", "gaas")):
        r = dfpt_row(a.work, mid, sub, q)
        if r:
            rows.append(r)
    r = si_dfpt_qha(a.work, q)
    if r:
        rows.append(r)
    if not rows:
        print("no finished QE outputs found")
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUT / "pbe_qe.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(rows, indent=1, default=float))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["prep", "analyze"])
    ap.add_argument("--work", type=Path, default=WORK)
    a = ap.parse_args()
    {"prep": cmd_prep, "analyze": cmd_analyze}[a.step](a)


if __name__ == "__main__":
    main()
