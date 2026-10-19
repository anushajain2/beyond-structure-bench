"""Controlled study of why MACE-MPA-0 and MatterSim v1 mispredict thermal expansion.

Reproduces docs/thermal_failure_study.md. Cases: Si, GaAs, Cu, Ta, InP, HfO2.

Every expensive step saves its raw output (energies, forces, displacement datasets) under
results/thermal_failure/, so the analysis step rebuilds every table without a force call.

Steps (each backend runs in the environment that has its package; PYTHONPATH=src):

  structures                       test structures for the native-vs-export comparison
  points  --backend B              energies, forces, stresses on those structures
  phonons --backend B --variant V  phonon data for QHA (V: grid, disp03, sc14)
  determinism --backend B --materials M --tag N   repeat single points and one phonon run (run 3x)
  analyze                          tables -> results/thermal_failure/*.csv, tables.md

Backends:
  mace-kups         MACE-MPA-0, CuspAI tojax export through kUPS (what the benchmark used)  [.venv]
  mace-torch        MACE-MPA-0, official mace-torch package, float64                         [.venv-mace]
  mace-torch32      the same in float32 (points only)                                        [.venv-mace]
  mattersim-native  MatterSim v1 5M, official mattersim package (what the benchmark used)    [.venv-mattersim]
  mattersim-kups    MatterSim v1 5M, kUPS tojax export (excluded from the benchmark; contrast)[.venv]

Phonon variants (all other settings from configs/benchmark.yaml thermal_qha):
  grid    volumes 0.94-1.12 V0 (the benchmark's 9 plus 0.94, 0.985, 1.10, 1.12), 10 A, 0.01 A
  disp03  the benchmark's 9 volumes, displacement 0.03 A
  sc14    the benchmark's 9 volumes, supercell >= 14 A

Example (from the repo root):
  PYTHONPATH=src .venv/bin/python scripts/thermal_failure_study.py structures
  PYTHONPATH=src .venv/bin/python scripts/thermal_failure_study.py points --backend mace-kups
  PYTHONPATH=src .venv-mattersim/bin/python scripts/thermal_failure_study.py phonons --backend mattersim-native --variant grid
  PYTHONPATH=src .venv/bin/python scripts/thermal_failure_study.py analyze
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import time
from types import SimpleNamespace

import numpy as np
from ase import Atoms
from ase.io import read, write

from chipff.materials import ROOT

OUT = ROOT / "results" / "thermal_failure"
CASES = ["Si", "GaAs", "Cu", "Ta", "InP", "HfO2"]
BENCH_MODEL = {"mace": "mace-mpa-0", "mattersim": "mattersim-5m-native"}  # whose relaxed cells are used
BASE_SCALES = [0.96, 0.975, 0.99, 1.0, 1.015, 1.03, 1.045, 1.06, 1.08]
GRID_SCALES = sorted(set(BASE_SCALES) | {0.94, 0.985, 1.10, 1.12})
VARIANTS = {
    "grid": dict(scales=GRID_SCALES, width=10.0, disp=0.01),
    "disp03": dict(scales=BASE_SCALES, width=10.0, disp=0.03),
    "sc14": dict(scales=BASE_SCALES, width=14.0, disp=0.01),
}
# volume scans analysed (subsets of the computed volumes); "bench" is the published setting
SCANS = {
    "bench": BASE_SCALES,
    "narrow": [0.975, 0.985, 0.99, 1.0, 1.015, 1.03, 1.045],
    "wide": GRID_SCALES,
}
log = logging.getLogger("thermal_failure")

# Experimental ingredients at ~300 K, per atom. alpha_V, K and the lattice come from the benchmark's
# own sourced records (data/experimental/*.json; alpha_V = 3 x linear for cubic); C_p from:
#   Si, Cu, Ta: NIST-JANAF (Chase 1998) solid-phase Shomate fits on the NIST WebBook, evaluated at 298.15 K
#   GaAs, InP:  Ioffe NSM archive thermal pages ("Specific heat 0.33 / 0.31 J g-1 °C-1")
#   HfO2:       Zhou, Shi, Woodfield & Navrotsky, J. Chem. Thermodyn. 43, 970 (2011), smoothed C_p(298.15 K)
#               = 57.73 J/K/mol, from NIST ThermoML (trc.nist.gov/ThermoML/10.1016/j.jct.2011.02.002.xml)
# K_S (adiabatic, from elastic constants) is converted to K_T = K_S / (1 + alpha_V gamma T) and
# C_V = C_p - alpha_V^2 K_T V T; both corrections are 0.3-3 %.
EXP = {
    "Si":   dict(alpha_V=7.854, K=98.0, K_kind="S", V_atom=5.431020511 ** 3 / 8, Cp=19.99),
    "GaAs": dict(alpha_V=17.19, K=75.3, K_kind="S", V_atom=5.65325 ** 3 / 8, Cp=0.33 * 144.645 / 2),
    "InP":  dict(alpha_V=12.57, K=71.1, K_kind="S", V_atom=5.8687 ** 3 / 8, Cp=0.31 * 145.795 / 2),
    "Cu":   dict(alpha_V=49.683, K=137.6, K_kind="S", V_atom=3.615 ** 3 / 4, Cp=24.47),
    "Ta":   dict(alpha_V=18.951, K=191.9, K_kind="S", V_atom=3.3058 ** 3 / 2, Cp=25.30),
    # HfO2: alpha_V = sum of TPRC axial interval means over 293-400 K (a 5.42 + b 0.75 + c 10.75), i.e.
    # centred at 346.5 K, the nearest to 300 K available; K is isothermal (EOS), +-23 GPa
    "HfO2": dict(alpha_V=16.92, K=185.0, K_kind="T",
                 V_atom=5.1156 * 5.1722 * 5.2948 * np.sin(np.radians(99.18)) / 12, Cp=57.73 / 3),
}
NA_A3 = 6.02214076e23 * 1e-30  # Å^3 per atom -> m^3 per mol of atoms


def exp_gamma(mid: str) -> dict:
    """Experimental thermodynamic Grueneisen parameter gamma = alpha_V K_T V / C_V at ~300 K."""
    e = EXP[mid]
    a, T, V = e["alpha_V"] * 1e-6, 300.0, e["V_atom"] * NA_A3
    g = 1.5
    for _ in range(20):
        KT = e["K"] / (1 + a * g * T) if e["K_kind"] == "S" else e["K"]
        Cv = e["Cp"] - a ** 2 * KT * 1e9 * V * T
        g = a * KT * 1e9 * V / Cv
    return dict(gamma=g, KT=KT, Cv_kB=Cv / 8.314462618, V_atom=e["V_atom"], alpha_V=e["alpha_V"])

KB_EV = 8.617333262e-5
THZ_TO_EV = 4.135667696e-3
EV_TO_KJMOL = 96.48533212


def family(backend: str) -> str:
    return "mace" if backend.startswith("mace") else "mattersim"


def cfg_qha() -> dict:
    from chipff.runner import config

    return config()["thermal_qha"]


# --------------------------------------------------------------------------------------------
# engines
# --------------------------------------------------------------------------------------------
def make_engine(backend: str):
    from chipff.models import get_model

    if backend == "mace-kups":
        from chipff.engine import Engine

        return Engine(get_model("mace-mpa-0"))
    if backend == "mattersim-kups":
        from chipff.engine import Engine

        return Engine(get_model("mattersim-5m"))
    if backend == "mattersim-native":
        from chipff.ase_engine import AseEngine

        return AseEngine(get_model("mattersim-5m-native"))
    if backend in ("mace-torch", "mace-torch32"):
        from mace.calculators import mace_mp

        from chipff.ase_engine import AseEngine

        eng = AseEngine.__new__(AseEngine)  # same relax/forces/stress code as MatterSim's reference engine
        eng.calc = mace_mp(model="medium-mpa-0", default_dtype="float64" if backend == "mace-torch" else "float32",
                           device="cpu")
        eng.device = "cpu"
        eng.model = SimpleNamespace(model_path="mace-torch medium-mpa-0", via_kups=False)
        return eng
    raise SystemExit(f"unknown backend {backend}")


def backend_versions(backend: str) -> dict:
    from importlib.metadata import PackageNotFoundError, version

    out = {}
    for p in ("kups", "jax", "torch", "mace-torch", "mattersim", "phonopy", "ase"):
        try:
            out[p] = version(p)
        except PackageNotFoundError:
            pass
    return out


def relaxed_cell(fam: str, mid: str) -> Atoms:
    from chipff.qha import _symmetrized
    from chipff.runner import relaxed_structures

    return _symmetrized(relaxed_structures(BENCH_MODEL[fam])[mid])


# --------------------------------------------------------------------------------------------
# 1. native vs export: identical structures, energies / forces / stresses
# --------------------------------------------------------------------------------------------
def cmd_structures(_a):
    """Per model family and material: relaxed primitive cell, the same at 0.96 and 1.06 V0, the
    benchmark's 10 A phonon supercell undisplaced and with its first 0.01 A displacement, and that
    supercell rattled by 0.03 A (seed 0)."""
    from chipff.qha import _make_phonopy, _supercell_reps

    for fam in BENCH_MODEL:
        d = OUT / "structures" / fam
        d.mkdir(parents=True, exist_ok=True)
        for mid in CASES:
            prim = relaxed_cell(fam, mid)
            reps = _supercell_reps(prim, 10.0)
            ph = _make_phonopy(prim, reps)
            ph.generate_displacements(distance=0.01)
            sc = ph.supercell
            ref = Atoms(symbols=sc.symbols, cell=sc.cell, scaled_positions=sc.scaled_positions, pbc=True)
            d1 = ph.supercells_with_displacements[0]
            disp = Atoms(symbols=d1.symbols, cell=d1.cell, scaled_positions=d1.scaled_positions, pbc=True)
            rat = ref.copy()
            rat.positions += np.random.default_rng(0).normal(0, 0.03, rat.positions.shape)
            frames = {"prim": prim, "prim_0.96": None, "prim_1.06": None, "sc_ref": ref, "sc_disp": disp,
                      "sc_rattle": rat}
            for s in (0.96, 1.06):
                a = prim.copy()
                a.set_cell(np.asarray(prim.cell) * s ** (1 / 3), scale_atoms=True)
                frames[f"prim_{s}"] = a
            for k, a in frames.items():
                a.info["label"] = k
            write(d / f"{mid}.extxyz", list(frames.values()))
            log.info("%s %s: %d frames, supercell %s (%d atoms)", fam, mid, len(frames), reps, len(ref))


def cmd_points(a):
    eng = make_engine(a.backend)
    fam = family(a.backend)
    res = {"backend": a.backend, "versions": backend_versions(a.backend), "materials": {}}
    for mid in CASES:
        frames = read(OUT / "structures" / fam / f"{mid}.extxyz", index=":")
        rec = {}
        for at in frames:
            label = at.info["label"]
            at = Atoms(numbers=at.numbers, positions=at.positions, cell=at.cell, pbc=True)
            E, S = eng.stress([at])
            _, F = eng.forces([at])
            rec[label] = {"energy_eV": float(E[0]), "stress_GPa": np.asarray(S[0]).tolist(),
                          "forces": np.asarray(F[0]).tolist(), "natoms": len(at)}
        if a.backend == "mattersim-native":  # run-to-run reproducibility of the reference itself
            at = frames[4]
            at = Atoms(numbers=at.numbers, positions=at.positions, cell=at.cell, pbc=True)
            _, F2 = eng.forces([at])
            rec["sc_disp_repeat"] = {"forces": np.asarray(F2[0]).tolist()}
        res["materials"][mid] = rec
        log.info("%s %s done", a.backend, mid)
    (OUT / "points").mkdir(parents=True, exist_ok=True)
    (OUT / "points" / f"{a.backend}.json").write_text(json.dumps(res))


# --------------------------------------------------------------------------------------------
# 2. phonon data for QHA (same steps as chipff.qha.run_qha, raw data kept)
# --------------------------------------------------------------------------------------------
def run_phonons(eng, prim: Atoms, scales, width, disp, q) -> dict:
    from chipff.qha import _forces_batched, _make_phonopy, _supercell_reps

    reps = _supercell_reps(prim, width)
    cells = []
    for s in scales:
        c = prim.copy()
        c.set_cell(np.asarray(prim.cell) * s ** (1 / 3), scale_atoms=True)
        cells.append(c)
    rel = eng.relax(cells, optimize_cell=False, fmax=q["fmax_eV_per_A"], max_steps=1000)
    out = dict(scales=np.array(scales), V=np.array([r.atoms.get_volume() for r in rel]),
               E=np.array([r.energy for r in rel]), reps=np.array(reps), numbers=prim.numbers,
               cells=np.array([np.asarray(r.atoms.cell) for r in rel]),
               frac=np.array([r.atoms.get_scaled_positions() for r in rel]),
               relax_fmax=np.array([r.fmax for r in rel]))
    forces, d_atoms, d_vecs = [], [], []
    for r in rel:
        ph = _make_phonopy(r.atoms, reps)
        ph.generate_displacements(distance=disp)
        scs = [Atoms(symbols=sc.symbols, cell=sc.cell, scaled_positions=sc.scaled_positions, pbc=True)
               for sc in ph.supercells_with_displacements]
        ref = Atoms(symbols=ph.supercell.symbols, cell=ph.supercell.cell,
                    scaled_positions=ph.supercell.scaled_positions, pbc=True)
        f_all = _forces_batched(eng, [ref] + scs, q["max_pairs_per_call"], q["edge_cutoff_A"])
        forces.append(np.array(f_all[1:]) - f_all[0][None])  # reference forces subtracted, as in the benchmark
        d_atoms.append([d["number"] for d in ph.dataset["first_atoms"]])
        d_vecs.append([d["displacement"] for d in ph.dataset["first_atoms"]])
    # the displacement count can differ between volumes (spglib may find a lower symmetry in a
    # slightly distorted relaxed cell), so each volume is stored under its own keys
    for i, (f, n, v) in enumerate(zip(forces, d_atoms, d_vecs)):
        out[f"forces_{i}"], out[f"disp_atoms_{i}"], out[f"disp_vecs_{i}"] = f, np.array(n), np.array(v)
    out["n_disp"] = np.array([len(n) for n in d_atoms])
    return out


def cmd_phonons(a):
    q = cfg_qha()
    v = VARIANTS[a.variant]
    eng = make_engine(a.backend)
    d = OUT / "phonons" / a.backend
    d.mkdir(parents=True, exist_ok=True)
    for mid in a.materials or CASES:
        f = d / f"{mid}_{a.variant}.npz"
        if f.exists() and not a.force:
            continue
        t = time.time()
        data = run_phonons(eng, relaxed_cell(family(a.backend), mid), v["scales"], v["width"], v["disp"], q)
        np.savez_compressed(f, width=v["width"], disp=v["disp"], wall_s=time.time() - t,
                            versions=json.dumps(backend_versions(a.backend)), **data)
        log.info("%s %s %s: %d volumes x %s displacements, supercell %s, %.0f s", a.backend, mid, a.variant,
                 len(v["scales"]), sorted(set(data["n_disp"].tolist())), data["reps"].tolist(), time.time() - t)


def cmd_determinism(a):
    """Is the backend deterministic? Repeated single points in one process (and, called again with
    another --tag, in a fresh process), plus one repeat of the benchmark's 9-volume phonon run for
    each --materials entry, saved for the analysis step."""
    import torch

    eng = make_engine(a.backend)
    fam = family(a.backend)
    d = OUT / "determinism" / a.backend
    d.mkdir(parents=True, exist_ok=True)
    rec = {"torch_threads": torch.get_num_threads(), "versions": backend_versions(a.backend), "points": {}}
    for mid in a.materials:
        at = read(OUT / "structures" / fam / f"{mid}.extxyz", index=4)  # sc_disp
        at = Atoms(numbers=at.numbers, positions=at.positions, cell=at.cell, pbc=True)
        reps = []
        for _ in range(5):
            E, F = eng.forces([at])
            reps.append((float(E[0]), np.asarray(F[0])))
        rec["points"][mid] = {"energies_eV": [e for e, _ in reps], "forces": [f.tolist() for _, f in reps]}
        t = time.time()
        data = run_phonons(eng, relaxed_cell(fam, mid), BASE_SCALES, 10.0, 0.01, cfg_qha())
        np.savez_compressed(d / f"{mid}_run{a.tag}.npz", width=10.0, disp=0.01, wall_s=time.time() - t, **data)
    (d / f"points_run{a.tag}.json").write_text(json.dumps(rec))


def determinism_report():
    """Spread of single points and of alpha_V(300 K) across repeated runs, with and without the
    Gamma-acoustic fix."""
    from chipff.runner import select, thermal_plan

    rows = []
    q = cfg_qha()
    for bdir in sorted((OUT / "determinism").glob("*")):
        runs = sorted(bdir.glob("points_run*.json"))
        pts = [json.loads(f.read_text()) for f in runs]
        if not pts:
            continue
        for mid in pts[0]["points"]:
            F = [np.array(f) for p in pts for f in p["points"][mid]["forces"]]
            E = [e for p in pts for e in p["points"][mid]["energies_eV"]]
            n_in = len(pts[0]["points"][mid]["forces"])
            in_proc = max(np.abs(F[i] - F[0]).max() for i in range(n_in))
            across = max(np.abs(F[i] - F[0]).max() for i in range(len(F)))
            al = {"drop": [], "clean": []}
            window = thermal_plan(select([mid]))[mid].temperatures
            for f in sorted(bdir.glob(f"{mid}_run*.npz")):
                dd = dict(np.load(f, allow_pickle=False))
                T, pv = per_volume(dd, q)
                for mode in al:
                    al[mode].append(qha_alpha(dd, pv, T, BASE_SCALES, q, window, mode)["alpha300"])
            rows.append(dict(backend=bdir.name, material=mid, processes=len(pts), torch_threads=pts[0]["torch_threads"],
                             max_dF_same_process_eV_per_A=in_proc, max_dF_any_run_eV_per_A=across,
                             max_dE_any_run_eV=float(np.max(E) - np.min(E)),
                             alpha300_as_benchmark=" ".join(f"{x:.2f}" for x in al["drop"]),
                             alpha300_gamma_fixed=" ".join(f"{x:.2f}" for x in al["clean"])))
    if rows:
        with open(OUT / "determinism.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, list(rows[0]))
            w.writeheader()
            for r in rows:
                w.writerow({k: (float(f"{v:.3g}") if isinstance(v, float) else v) for k, v in r.items()})


# --------------------------------------------------------------------------------------------
# 3. analysis (offline)
# --------------------------------------------------------------------------------------------
def phonopy_at(d, i: int):
    """Phonopy object with symmetrised force constants for volume i of a saved dataset."""
    from chipff.qha import _make_phonopy

    at = Atoms(numbers=d["numbers"], cell=d["cells"][i], scaled_positions=d["frac"][i], pbc=True)
    ph = _make_phonopy(at, d["reps"].tolist())
    nsc = len(ph.supercell)
    ph.dataset = {"natom": nsc, "first_atoms": [{"number": int(n), "displacement": np.asarray(v)}
                                                 for n, v in zip(d[f"disp_atoms_{i}"], d[f"disp_vecs_{i}"])]}
    ph.forces = d[f"forces_{i}"]
    ph.produce_force_constants()
    ph.symmetrize_force_constants()
    return ph


def mode_thermo(freqs_thz, weights, T, mode: str, gamma_acoustic=None):
    """F (kJ/mol), C_V and S (J/K/mol) per primitive cell from mesh frequencies.

    mode "drop":  modes with frequency <= 0 are left out: phonopy's default, as the benchmark ran it.
                  The three acoustic modes at Gamma (ideally exactly 0) come out as ~1e-5 THz of
                  random sign, and each one that happens to be positive adds kT ln(h nu / kT) / N_q.
    mode "clean": the same, with the Gamma acoustic modes excluded (phonopy's exclude_gamma_acoustic).
    mode "abs":   as "clean", with imaginary modes entering at |frequency| (bounds what dropping hides).
    gamma_acoustic: (q index, band indices) of the acoustic modes at Gamma.
    """
    fr = np.array(freqs_thz, dtype=float)
    if mode in ("clean", "abs") and gamma_acoustic is not None:
        fr[gamma_acoustic[0], gamma_acoustic[1]] = 0.0
    f = fr.ravel()
    w = np.repeat(np.asarray(weights, float), fr.shape[1]) / np.sum(weights)
    if mode == "abs":
        f = np.abs(f)
    keep = f > 0
    e = f[keep] * THZ_TO_EV
    w = w[keep]
    Fv, Cv, Sv = [], [], []
    for t in T:
        if t < 1e-9:
            Fv.append(np.sum(w * e / 2))
            Cv.append(0.0)
            Sv.append(0.0)
            continue
        x = e / (KB_EV * t)
        ex = np.exp(-np.minimum(x, 700))
        Fv.append(np.sum(w * (e / 2 + KB_EV * t * np.log1p(-ex))))
        Cv.append(np.sum(w * KB_EV * x ** 2 * ex / (1 - ex) ** 2))
        Sv.append(np.sum(w * KB_EV * (x * ex / (1 - ex) - np.log1p(-ex))))
    conv = EV_TO_KJMOL * 1000  # eV -> J/mol
    return np.array(Fv) * EV_TO_KJMOL, np.array(Cv) * conv, np.array(Sv) * conv


def per_volume(d, q):
    """Commensurate-q stability, mesh frequencies and thermodynamics at every saved volume."""
    reps = d["reps"].tolist()
    comm = np.array([[i / reps[0], j / reps[1], k / reps[2]]
                     for i in range(reps[0]) for j in range(reps[1]) for k in range(reps[2])])
    T = np.arange(0, q["t_max_K"] + 1, q["t_step_K"], dtype=float)
    out = []
    for i in range(len(d["scales"])):
        ph = phonopy_at(d, i)
        ph.run_qpoints(comm)
        fmin = float(np.min(ph.get_qpoints_dict()["frequencies"]))
        ph.run_mesh(q["mesh_length"])
        m = ph.get_mesh_dict()
        fr, w = m["frequencies"], m["weights"]
        neg = fr < 0
        qp = np.asarray(m["qpoints"])
        gi = np.flatnonzero(np.all(np.abs(qp) < 1e-9, axis=1))
        ga = (int(gi[0]), np.argsort(np.abs(fr[gi[0]]))[:3]) if len(gi) else None
        rec = dict(gamma_acoustic_THz=fr[ga[0], ga[1]].tolist() if ga else None, fmin=fmin, freqs=fr, weights=w, mesh=ph.mesh.mesh_numbers.tolist(), ph=ph,
                   interp_imag=float(np.mean(fr < -abs(q["imaginary_tolerance_THz"]))),
                   share_neg=float(np.sum(w[:, None] * neg) / (np.sum(w) * fr.shape[1])))
        for mode in ("drop", "clean", "abs"):
            rec[mode] = mode_thermo(fr, w, T, mode, ga)
        out.append(rec)
    return T, out


def qha_alpha(d, pv, T, scan, q, window, mode="drop"):
    """alpha_V at 300 K and over the window, with the benchmark's stable-volume rule."""
    from phonopy import PhonopyQHA

    scales = list(np.round(d["scales"], 4))
    idx = [scales.index(s) for s in scan if s in scales]
    fmins = [pv[i]["fmin"] for i in idx]
    tol = -abs(q["imaginary_tolerance_THz"])
    sc = [scales[i] for i in idx]
    i0 = sc.index(1.0)
    if fmins[i0] <= tol:
        return dict(alpha300=np.nan, alpha_win=np.nan, note="unstable at V0")
    lo = hi = i0
    while lo - 1 >= 0 and fmins[lo - 1] > tol:
        lo -= 1
    while hi + 1 < len(idx) and fmins[hi + 1] > tol:
        hi += 1
    keep = idx[lo:hi + 1]
    if len(keep) < q["min_volumes"]:
        return dict(alpha300=np.nan, alpha_win=np.nan, note="too few stable volumes")
    t_max = q["t_max_K"]
    qha = PhonopyQHA(volumes=d["V"][keep], electronic_energies=d["E"][keep], temperatures=T,
                     free_energy=np.array([pv[i][mode][0] for i in keep]).T,
                     cv=np.array([pv[i][mode][1] for i in keep]).T,
                     entropy=np.array([pv[i][mode][2] for i in keep]).T,
                     eos=q["eos"], t_max=t_max - 2 * q["t_step_K"], verbose=False)
    Tq = T[: len(qha.thermal_expansion)]
    alpha = np.asarray(qha.thermal_expansion) * 1e6
    volT = np.asarray(qha.volume_temperature)[: len(Tq)]
    sel = (Tq >= min(window)) & (Tq <= max(window))
    Vk = d["V"][keep]
    inside = bool(volT[sel].max() < Vk.max() and volT[sel].min() > Vk.min())
    KT = np.asarray(qha.bulk_modulus_temperature)[: len(Tq)]
    return dict(alpha300=float(np.interp(300, Tq, alpha)), alpha_win=float(np.mean(alpha[sel])),
                inside=inside, volumes_used=[scales[i] for i in keep],
                V300=float(np.interp(300, Tq, volT)), KT300=float(np.interp(300, Tq, KT)),
                K0=float(qha.bulk_modulus) * 160.21766208,  # eV/Å^3 -> GPa
                note="" if inside else "V(T) leaves the stable scan in the window")


def gruneisen(d, pv, T_eval=300.0):
    """Mode Grueneisen parameters from 0.985 / 1.0 / 1.015 V0 and their C_V-weighted average."""
    from phonopy.api_gruneisen import PhonopyGruneisen

    scales = list(np.round(d["scales"], 4))
    i0, ip, im = scales.index(1.0), scales.index(1.015), scales.index(0.985)
    g = PhonopyGruneisen(pv[i0]["ph"], pv[ip]["ph"], pv[im]["ph"])
    g.set_mesh(pv[i0]["mesh"])
    _, w, fr, _, gam = g.get_mesh()
    f = fr.ravel()
    ww = np.repeat(np.asarray(w, float), fr.shape[1])
    gg = gam.ravel()
    ok = f > 0.1  # acoustic modes at Gamma (gamma undefined) and any imaginary modes left out
    e = f[ok] * THZ_TO_EV
    x = e / (KB_EV * T_eval)
    c = ww[ok] * x ** 2 * np.exp(-x) / (1 - np.exp(-x)) ** 2  # Einstein heat capacity per mode (k_B)
    gamma = float(np.sum(c * gg[ok]) / np.sum(c))
    neg = gg[ok] < 0
    nat = fr.shape[1] // 3
    cv_per_atom = float(np.sum(c) / np.sum(w) / nat)  # k_B per atom
    # split: which modes carry the average (acoustic third of the branches vs optical)
    br = np.tile(np.arange(fr.shape[1]), len(w))[ok]
    ac = br < 3
    return dict(gamma=gamma, gamma_neg_part=float(np.sum(c[neg] * gg[ok][neg]) / np.sum(c)),
                gamma_pos_part=float(np.sum(c[~neg] * gg[ok][~neg]) / np.sum(c)),
                gamma_acoustic=float(np.sum(c[ac] * gg[ok][ac]) / np.sum(c[ac])),
                gamma_optical=float(np.sum(c[~ac] * gg[ok][~ac]) / np.sum(c[~ac])) if (~ac).any() else None,
                cv_kB_per_atom=cv_per_atom, natoms=nat,
                lowest_gamma=float(np.min(gg[ok])), share_negative_modes=float(np.sum(ww[ok][neg]) / np.sum(ww[ok])))


FCC_LATTICE = {"Si", "GaAs", "InP", "Cu"}  # diamond / zincblende / fcc: special points in units of 2pi/a
SPECIAL_Q = {"X": [1.0, 0.0, 0.0], "L": [0.5, 0.5, 0.5]}
# experiment, Si: TA(X) -1.4, TA(L) -1.3 (as quoted by Rignanese, Michenaud & Gonze, arXiv:mtrl-th/9509002,
# their ref. [25]); Gamma TO: GaAs 1.39, InP 1.44 (Aoki, Anastassakis & Cardona 1984, as tabulated in
# arXiv:1107.0196, Table 4)


def special_point_gamma(pv, scales, mid):
    """Mode Grueneisen parameters of the transverse acoustic modes at X and L (fcc-lattice crystals)."""
    if mid not in FCC_LATTICE:
        return {}
    i0, ip, im = scales.index(1.0), scales.index(1.015), scales.index(0.985)
    out = {}
    for name, qc in SPECIAL_Q.items():
        w2, vols = [], []
        for i in (im, i0, ip):
            ph = pv[i]["ph"]
            A = np.asarray(ph.primitive.cell)
            a = (4 * abs(np.linalg.det(A))) ** (1 / 3)
            q_red = A @ (np.asarray(qc) / a)  # reduced coordinates in phonopy's primitive reciprocal basis
            ph.run_qpoints([q_red])
            w2.append(np.sort(ph.get_qpoints_dict()["frequencies"][0]) ** 2)
            vols.append(abs(np.linalg.det(A)))
        g = -(vols[1] / (2 * w2[1])) * (w2[2] - w2[0]) / (vols[2] - vols[0])
        out[f"gamma_TA_{name}"] = float(np.mean(g[:2]))  # two degenerate transverse acoustic modes
        out[f"nu_TA_{name}_THz"] = float(np.sqrt(w2[1][0]))
    if len(pv[i0]["freqs"][0]) == 6:  # two-atom cells: optical modes at Gamma (no LO-TO splitting, as in the QHA)
        w2, vols = [], []
        for i in (im, i0, ip):
            ph = pv[i]["ph"]
            ph.run_qpoints([[0, 0, 0]])
            w2.append(np.sort(ph.get_qpoints_dict()["frequencies"][0])[3:] ** 2)
            vols.append(abs(np.linalg.det(np.asarray(ph.primitive.cell))))
        out["gamma_O_Gamma"] = float(np.mean(-(vols[1] / (2 * w2[1])) * (w2[2] - w2[0]) / (vols[2] - vols[0])))
    return out


def load(backend, mid, variant):
    f = OUT / "phonons" / backend / f"{mid}_{variant}.npz"
    return dict(np.load(f, allow_pickle=False)) if f.exists() else None


def cmd_analyze(_a):
    from chipff.runner import select, thermal_plan

    q = cfg_qha()
    plan = thermal_plan(select(CASES))
    rows_conv, rows_phys, rows_imag = [], [], []
    for backend in ("mace-kups", "mattersim-native", "mace-torch"):
        for mid in CASES:
            window = plan[mid].temperatures
            for variant in VARIANTS:
                d = load(backend, mid, variant)
                if d is None:
                    continue
                T, pv = per_volume(d, q)
                scans = SCANS if variant == "grid" else {"bench": BASE_SCALES}
                for scan_name, scan in scans.items():
                    for mode in ("drop", "clean", "abs"):
                        if mode == "abs" and scan_name != "bench":
                            continue
                        r = qha_alpha(d, pv, T, scan, q, window, mode)
                        rows_conv.append(dict(backend=backend, material=mid, variant=variant, scan=scan_name,
                                              imaginary=mode, supercell="x".join(map(str, d["reps"])),
                                              n_disp=int(d["n_disp"][list(np.round(d["scales"], 4)).index(1.0)]), wall_s=float(d["wall_s"]),
                                              **{k: v for k, v in r.items() if k != "volumes_used"},
                                              volumes_used=" ".join(map(str, r.get("volumes_used", [])))))
                if variant == "grid":
                    i0 = list(np.round(d["scales"], 4)).index(1.0)
                    for i, s in enumerate(np.round(d["scales"], 4)):
                        Fd, Fc, Fa = pv[i]["drop"][0], pv[i]["clean"][0], pv[i]["abs"][0]
                        j = int(np.argmin(np.abs(T - 300)))
                        rows_imag.append(dict(backend=backend, material=mid, scale=float(s), fmin_comm_THz=pv[i]["fmin"],
                                              mesh_min_THz=float(pv[i]["freqs"].min()),
                                              share_modes_below_0=pv[i]["share_neg"],
                                              share_modes_below_tol=pv[i]["interp_imag"],
                                              gamma_acoustic_THz=" ".join(f"{x:.1e}" for x in pv[i]["gamma_acoustic_THz"] or []),
                                              dF300_gamma_acoustic_meV_per_atom=float((Fd[j] - Fc[j]) / EV_TO_KJMOL * 1000 / len(d["numbers"])),
                                              dF300_imaginary_meV_per_atom=float((Fa[j] - Fc[j]) / EV_TO_KJMOL * 1000 / len(d["numbers"])),
                                              Fvib300_meV_per_atom=float(Fc[j] / EV_TO_KJMOL * 1000 / len(d["numbers"]))))
                    rb = qha_alpha(d, pv, T, BASE_SCALES, q, window, "clean")
                    gr = gruneisen(d, pv)
                    gr.update(special_point_gamma(pv, list(np.round(d["scales"], 4)), mid))
                    # alpha_V ~ gamma C_V / (K_T V): all per atom, at 300 K
                    v_atom = rb["V300"] / len(d["numbers"]) if np.isfinite(rb["alpha300"]) else d["V"][i0] / len(d["numbers"])
                    kt = rb.get("KT300", np.nan)
                    a_est = gr["gamma"] * gr["cv_kB_per_atom"] * KB_EV / (kt / 160.21766208 * v_atom) * 1e6
                    ex = exp_gamma(mid)
                    rows_phys.append(dict(backend=backend, material=mid, alpha300_qha=rb["alpha300"],
                                          alpha300_from_gamma=a_est, KT300_GPa=kt, K0_static_GPa=rb.get("K0"),
                                          V300_A3_per_atom=v_atom, **gr,
                                          exp_alpha_V=ex["alpha_V"], exp_gamma=ex["gamma"], exp_KT_GPa=ex["KT"],
                                          exp_Cv_kB=ex["Cv_kB"], exp_V_atom=ex["V_atom"],
                                          # alpha ratio model/exp = gamma ratio x C_V ratio x (K ratio)^-1 x (V ratio)^-1
                                          r_alpha=a_est / ex["alpha_V"], r_gamma=gr["gamma"] / ex["gamma"],
                                          r_Cv=gr["cv_kB_per_atom"] / ex["Cv_kB"], r_K=kt / ex["KT"],
                                          r_V=v_atom / ex["V_atom"]))
    for name, rows in (("convergence", rows_conv), ("physics", rows_phys), ("imaginary_modes", rows_imag)):
        if rows:
            keys = list(dict.fromkeys(k for r in rows for k in r))
            with open(OUT / f"{name}.csv", "w", newline="") as fh:
                w = csv.DictWriter(fh, keys)
                w.writeheader()
                for r in rows:
                    w.writerow({k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()})
    agreement()
    determinism_report()
    tables()


def agreement():
    """Native-vs-export differences on identical structures."""
    pts = {f.stem: json.loads(f.read_text()) for f in (OUT / "points").glob("*.json")}
    pairs = [("mace-kups", "mace-torch"), ("mace-kups", "mace-torch32"), ("mace-torch", "mace-torch32"),
             ("mattersim-native", "mattersim-kups")]
    rows = []
    for a, b in pairs:
        if a not in pts or b not in pts:
            continue
        for mid in CASES:
            A, B = pts[a]["materials"][mid], pts[b]["materials"][mid]
            r = dict(reference=a, other=b, material=mid)
            frames = [k for k in A if "energy_eV" in A[k]]
            r["frames_nan"] = sum(not np.isfinite(B[k]["energy_eV"]) for k in frames)
            dE = [abs(A[k]["energy_eV"] - B[k]["energy_eV"]) / A[k]["natoms"] * 1000 for k in A if "energy_eV" in A[k]]
            r["max_dE_meV_per_atom"] = float(np.nanmax(dE))
            # energy differences between frames (what an E(V) curve sees)
            ev = lambda X, k: X[k]["energy_eV"] / X[k]["natoms"]
            r["d(E_1.06-E_0.96)_meV_per_atom"] = abs((ev(A, "prim_1.06") - ev(A, "prim_0.96"))
                                                     - (ev(B, "prim_1.06") - ev(B, "prim_0.96"))) * 1000
            dF = np.concatenate([np.abs(np.array(A[k]["forces"]) - np.array(B[k]["forces"])).ravel() for k in A if "energy_eV" in A[k]])
            r["max_dF_meV_per_A"] = float(np.nanmax(dF) * 1000)
            dS = [np.abs(np.array(A[k]["stress_GPa"]) - np.array(B[k]["stress_GPa"])).max() for k in A if "energy_eV" in A[k]]
            r["max_dStress_GPa"] = float(np.nanmax(dS))
            r["dP_prim_GPa"] = float(np.trace(np.array(A["prim"]["stress_GPa"]) - np.array(B["prim"]["stress_GPa"])) / -3)
            # what the force constants see: response to the 0.01 A displacement
            fa = np.array(A["sc_disp"]["forces"]) - np.array(A["sc_ref"]["forces"])
            fb = np.array(B["sc_disp"]["forces"]) - np.array(B["sc_ref"]["forces"])
            r["rel_diff_displacement_response"] = float(np.linalg.norm(fa - fb) / np.linalg.norm(fa))
            if "sc_disp_repeat" in A:
                r["ref_repeat_max_dF_meV_per_A"] = float(np.abs(np.array(A["sc_disp_repeat"]["forces"]) - np.array(A["sc_disp"]["forces"])).max() * 1000)
            rows.append(r)
    if rows:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(OUT / "agreement.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, keys)
            w.writeheader()
            for r in rows:
                w.writerow({k: (float(f"{v:.4g}") if isinstance(v, float) else v) for k, v in r.items()})


def _csv(name):
    f = OUT / f"{name}.csv"
    return list(csv.DictReader(open(f))) if f.exists() else []


def _f(x, nd=1):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "–"
    return "–" if not np.isfinite(v) else f"{v:.{nd}f}"


def tables():
    """Markdown tables for docs/thermal_failure_study.md -> results/thermal_failure/tables.md."""
    from chipff.runner import load_raw

    L = []
    ag = _csv("agreement")
    if ag:
        L += ["### Native vs export (identical structures)", "",
              "| model | reference → other | material | max ΔE (meV/atom) | Δ[E(1.06 V0) − E(0.96 V0)] (meV/atom) | max ΔF (meV/Å) | max Δσ (GPa) | Δ displacement response | NaN frames |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in ag:
            L.append(f"| {family(r['reference'])} | {r['reference']} → {r['other']} | {r['material']} | {_f(r['max_dE_meV_per_atom'], 3)} | "
                     f"{_f(r['d(E_1.06-E_0.96)_meV_per_atom'], 3)} | {_f(r['max_dF_meV_per_A'], 3)} | {_f(r['max_dStress_GPa'], 4)} | "
                     f"{float(r['rel_diff_displacement_response']) * 100:.3g} % | {r['frames_nan']} |")
        L.append("")
    conv = _csv("convergence")
    if conv:
        L += ["### QHA convergence, α_V(300 K) in 10⁻⁶ K⁻¹", "",
              "*published*: results/raw (benchmark run). *rerun*: same settings, this study's data. *Γ fixed*: Γ-point acoustic modes "
              "excluded from F_vib; every column right of it also has them excluded. Percentages are relative to *Γ fixed*.", "",
              "| model | material | published | rerun (as benchmark) | Γ fixed | disp 0.03 Å | supercell 14 Å | scan 0.975–1.045 | scan 0.94–1.12 | imaginary modes kept as abs(ν) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        idx = {(r["backend"], r["material"], r["variant"], r["scan"], r["imaginary"]): r for r in conv}
        pub_model = {"mace-kups": "mace-mpa-0", "mattersim-native": "mattersim-5m-native", "mace-torch": None}
        for backend in ("mace-kups", "mace-torch", "mattersim-native"):
            pub = load_raw(pub_model[backend], "thermal_qha") if pub_model[backend] else {}
            for mid in CASES:
                ref = idx.get((backend, mid, "grid", "bench", "clean"))
                if ref is None:
                    continue
                a0 = float(ref["alpha300"])

                def cell(key):
                    r = idx.get(key)
                    if r is None:
                        return "not run"
                    v = float(r["alpha300"])
                    if not np.isfinite(v):
                        return r["note"] or "–"
                    flag = "" if r["inside"] == "True" else "†"
                    return f"{v:.2f} ({(v / a0 - 1) * 100:+.0f} %){flag}"
                p = pub.get(mid, {}).get("alpha_V_300K_1e6")
                L.append(f"| {backend} | {mid} | {_f(p, 2)} | {cell((backend, mid, 'grid', 'bench', 'drop'))} | **{a0:.2f}** | "
                         f"{cell((backend, mid, 'disp03', 'bench', 'clean'))} | {cell((backend, mid, 'sc14', 'bench', 'clean'))} | "
                         f"{cell((backend, mid, 'grid', 'narrow', 'clean'))} | {cell((backend, mid, 'grid', 'wide', 'clean'))} | "
                         f"{cell((backend, mid, 'grid', 'bench', 'abs'))} |")
        L += ["", "† V(T) leaves the stable scanned range inside the material's window (the benchmark's check fails).", ""]
        L += ["### Same, averaged over each material's pre-registered window", "",
              "| model | material | window (K) | Γ fixed | disp 0.03 Å | supercell 14 Å | scan 0.975–1.045 | scan 0.94–1.12 | imaginary modes kept |",
              "|---|---|---|---|---|---|---|---|---|"]
        from chipff.runner import select, thermal_plan
        plan = thermal_plan(select(CASES))
        for backend in ("mace-kups", "mace-torch", "mattersim-native"):
            for mid in CASES:
                ref = idx.get((backend, mid, "grid", "bench", "clean"))
                if ref is None:
                    continue

                def cw(key):
                    r = idx.get(key)
                    if r is None:
                        return "not run"
                    return _f(r["alpha_win"], 2) + ("" if r["inside"] == "True" else "†")
                w = plan[mid].temperatures
                L.append(f"| {backend} | {mid} | {min(w):.0f}–{max(w):.0f} | {cw((backend, mid, 'grid', 'bench', 'clean'))} | "
                         f"{cw((backend, mid, 'disp03', 'bench', 'clean'))} | {cw((backend, mid, 'sc14', 'bench', 'clean'))} | "
                         f"{cw((backend, mid, 'grid', 'narrow', 'clean'))} | {cw((backend, mid, 'grid', 'wide', 'clean'))} | "
                         f"{cw((backend, mid, 'grid', 'bench', 'abs'))} |")
        L.append("")
    im = _csv("imaginary_modes")
    if im:
        L += ["### What the free energy leaves out at V0 and at the largest benchmark volume (1.08 V0), 300 K", "",
              "| model | material | V/V0 | mesh modes with ν < 0 | lowest mesh ν (THz) | F_vib (meV/atom) | Γ acoustic modes: F they add (meV/atom) | imaginary modes kept as abs(ν): ΔF (meV/atom) |",
              "|---|---|---|---|---|---|---|---|"]
        for r in im:
            if float(r["scale"]) in (1.0, 1.08):
                L.append(f"| {r['backend']} | {r['material']} | {float(r['scale']):.2f} | {float(r['share_modes_below_0']) * 100:.2f} % | "
                         f"{_f(r['mesh_min_THz'], 2)} | {_f(r['Fvib300_meV_per_atom'], 2)} | {_f(r['dF300_gamma_acoustic_meV_per_atom'], 3)} | "
                         f"{_f(r['dF300_imaginary_meV_per_atom'], 3)} |")
        L.append("")
    ph = _csv("physics")
    if ph:
        L += ["### Ingredients of α_V ≈ γ C_V / (K_T V) at 300 K (model / experiment)", "",
              "| model | material | α_V QHA | α_V from γC_V/K_TV | α_V exp | γ model | γ exp | K_T model (GPa) | K_T exp | C_V model (k_B/atom) | C_V exp | V model (Å³/atom) | V exp | **α ratio** | γ ratio | C_V ratio | 1/K ratio | 1/V ratio |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in ph:
            L.append(f"| {r['backend']} | {r['material']} | {_f(r['alpha300_qha'])} | {_f(r['alpha300_from_gamma'])} | {_f(r['exp_alpha_V'])} | "
                     f"{_f(r['gamma'], 2)} | {_f(r['exp_gamma'], 2)} | {_f(r['KT300_GPa'], 0)} | {_f(r['exp_KT_GPa'], 0)} | "
                     f"{_f(r['cv_kB_per_atom'], 2)} | {_f(r['exp_Cv_kB'], 2)} | {_f(r['V300_A3_per_atom'], 2)} | {_f(r['exp_V_atom'], 2)} | "
                     f"**{_f(r['r_alpha'], 2)}** | {_f(r['r_gamma'], 2)} | {_f(r['r_Cv'], 2)} | {_f(1 / float(r['r_K']), 2)} | {_f(1 / float(r['r_V']), 2)} |")
        L += ["", "### Where γ comes from (C_V-weighted mode Grüneisen parameters at 300 K, 0.985/1.0/1.015 V0)", "",
              "| model | material | γ | acoustic branches | optical branches | contribution of modes with γ < 0 | share of modes with γ < 0 | lowest mode γ | γ TA(X) | γ TA(L) | γ optical at Γ |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in ph:
            L.append(f"| {r['backend']} | {r['material']} | {_f(r['gamma'], 2)} | {_f(r['gamma_acoustic'], 2)} | {_f(r['gamma_optical'], 2)} | "
                     f"{_f(r['gamma_neg_part'], 2)} | {float(r['share_negative_modes']) * 100:.0f} % | {_f(r['lowest_gamma'], 2)} | "
                     f"{_f(r.get('gamma_TA_X'), 2)} | {_f(r.get('gamma_TA_L'), 2)} | {_f(r.get('gamma_O_Gamma'), 2)} |")
        L += ["", "Experiment: Si γ TA(X) = −1.4, γ TA(L) = −1.3 (as quoted by Rignanese, Michenaud & Gonze, arXiv:mtrl-th/9509002); "
              "γ TO(Γ) = 1.39 (GaAs), 1.44 (InP) (Aoki, Anastassakis & Cardona 1984, as tabulated in arXiv:1107.0196, Table 4)."]
        L.append("")
    (OUT / "tables.md").write_text("\n".join(L))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["structures", "points", "phonons", "determinism", "analyze"])
    ap.add_argument("--backend")
    ap.add_argument("--variant", choices=list(VARIANTS), default="grid")
    ap.add_argument("--materials", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--tag", default="0", help="determinism: label of this process's run")
    a = ap.parse_args()
    {"structures": cmd_structures, "points": cmd_points, "phonons": cmd_phonons, "determinism": cmd_determinism,
     "analyze": cmd_analyze}[a.step](a)


if __name__ == "__main__":
    main()
