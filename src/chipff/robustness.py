"""Robustness of the benchmark's conclusions (docs/robustness.md).

Three questions, three parts:

1. **Statistics** (`bootstrap_tables`): with ~30 materials per model, are the
   differences between models real? Bootstrap over materials, with each experimental
   reference also perturbed by its typical uncertainty, gives 95% confidence intervals
   on every mean absolute error and a paired "probability model A is more accurate
   than model B".
2. **Static sensitivity** (`static_sensitivity`): do lattice constants and bulk
   moduli depend on arbitrary settings? Rerun a representative subset with
   (a) the identical protocol in a fresh batch (determinism), (b) only the ±0.5% or
   only the ±1% strains, (c) a 10x tighter force tolerance, (d) starting cells
   compressed or expanded by 3% in volume.
3. **MD sensitivity** (`md_variants`): do thermal-expansion coefficients depend on
   the random seed, the supercell size or the time step? Rerun a subset with two
   extra seeds, a 14 Å supercell and half the time step.

Nothing here changes how the benchmark's own results are computed; it only reruns
subsets with one setting changed and compares.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from chipff.materials import ROOT, get_material

OUT = ROOT / "results" / "robustness"
log = logging.getLogger("chipff")

# typical 1-sigma relative uncertainty of an experimental reference, used to perturb
# references inside the bootstrap (documented in docs/robustness.md)
REF_SIGMA = {"lattice": 0.001, "bulk_modulus": 0.05, "thermal_expansion": 0.10}
STATIC_SUBSET = ["Si", "GaN", "Cu", "W", "HfO2", "TiN", "Al2O3", "NiSi"]
MD_SEED_SUBSET = ["Si", "Cu", "MgO", "GaN", "W", "TiN"]
MD_SIZE_SUBSET = ["Si", "Cu", "MgO"]


# -- 1. statistics -----------------------------------------------------------------
def _errors(df: pd.DataFrame, prop: str, ref: str, rng, perturb: bool) -> pd.Series:
    """Percentage errors, optionally with each experimental reference resampled."""
    if prop == "lattice":
        v, r = df["V_atom"], df["V_atom_exp" if ref == "experiment" else "V_atom_dft"]
        if perturb and ref == "experiment":  # sigma is on the linear lattice constant: volume x (1 + 3 eps)
            r = r * (1 + 3 * REF_SIGMA["lattice"] * rng.standard_normal(len(r)))
        return 100 * ((v / r) ** (1 / 3) - 1)
    if prop == "bulk_modulus":
        v, r = (df["K_for_exp"], df["B_exp"]) if ref == "experiment" else (df["K_vrh"], df["K_vrh_dft"])
    else:
        v, r = df["alpha_V"], df["alpha_V_exp"]
    if perturb and ref == "experiment":
        r = r * (1 + REF_SIGMA[prop] * rng.standard_normal(len(r)))
    return 100 * (v / r - 1)


def _usable(df: pd.DataFrame, prop: str, ref: str) -> pd.DataFrame:
    col = {"lattice": {"experiment": "err_lin_exp_pct", "dft": "err_lin_dft_pct"},
           "bulk_modulus": {"experiment": "err_exp_pct", "dft": "err_dft_pct"},
           "thermal_expansion": {"experiment": "err_exp_pct"}}[prop][ref]
    return df[df[col].notna()]


def bootstrap_tables(lat: pd.DataFrame, bulk: pd.DataFrame, therm: pd.DataFrame, n: int = 5000, seed: int = 0,
                     exclude_layered: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """95% CIs of MAPE per model, and paired win probabilities between models."""
    rng = np.random.default_rng(seed)
    specs = [("lattice", lat, "experiment"), ("lattice", lat, "dft"), ("bulk_modulus", bulk, "experiment"),
             ("bulk_modulus", bulk, "dft"), ("thermal_expansion", therm, "experiment")]
    ci_rows, pair_rows = [], []
    for prop, df, ref in specs:
        if df is None or df.empty or (prop == "thermal_expansion" and "alpha_V_exp" not in df):
            continue
        d = _usable(df, prop, ref)
        if exclude_layered:
            d = d[d["class"] != "layered"]
        if d.empty:
            continue
        models = sorted(d.model.unique())
        perturb = ref == "experiment"
        # per-model CI (each model over its own materials)
        for m in models:
            g = d[d.model == m].reset_index(drop=True)
            k = len(g)
            stats = []
            for _ in range(n):
                idx = rng.integers(0, k, k)
                stats.append(np.abs(_errors(g.iloc[idx], prop, ref, rng, perturb)).mean())
            point = float(np.abs(_errors(g, prop, ref, rng, False)).mean())
            lo, hi = np.percentile(stats, [2.5, 97.5])
            ci_rows.append({"property": prop, "reference": ref, "model": m, "n": k, "MAPE": point,
                            "ci_low": float(lo), "ci_high": float(hi)})
        # paired comparison on materials both models have
        for i, a in enumerate(models):
            for b in models[i + 1:]:
                common = sorted(set(d[d.model == a].material) & set(d[d.model == b].material))
                if len(common) < 5:
                    continue
                A = d[d.model == a].set_index("material").loc[common].reset_index()
                B = d[d.model == b].set_index("material").loc[common].reset_index()
                k = len(common)
                diffs = []
                for _ in range(n):
                    idx = rng.integers(0, k, k)
                    # the same perturbed reference for both models in a draw
                    noise = rng.standard_normal(k)
                    ea = np.abs(_perturbed(A.iloc[idx], prop, ref, noise[idx] if perturb else None)).mean()
                    eb = np.abs(_perturbed(B.iloc[idx], prop, ref, noise[idx] if perturb else None)).mean()
                    diffs.append(ea - eb)
                diffs = np.array(diffs)
                lo, hi = np.percentile(diffs, [2.5, 97.5])
                pair_rows.append({
                    "property": prop, "reference": ref, "model_a": a, "model_b": b, "n_common": k,
                    "mean_diff_pct_points": float(np.abs(_errors(A, prop, ref, rng, False)).mean()
                                                  - np.abs(_errors(B, prop, ref, rng, False)).mean()),
                    "ci_low": float(lo), "ci_high": float(hi), "p_a_better": float((diffs < 0).mean()),
                    "verdict": (f"{a} more accurate" if hi < 0 else f"{b} more accurate" if lo > 0
                                else "no significant difference"),
                })
    return pd.DataFrame(ci_rows), pd.DataFrame(pair_rows)


def _perturbed(g: pd.DataFrame, prop: str, ref: str, noise) -> pd.Series:
    if noise is None:
        return _errors(g, prop, ref, None, False)
    if prop == "lattice":
        r = g["V_atom_exp"].to_numpy() * (1 + 3 * REF_SIGMA["lattice"] * noise)
        return 100 * ((g["V_atom"].to_numpy() / r) ** (1 / 3) - 1)
    v, r = (g["K_for_exp"], g["B_exp"]) if prop == "bulk_modulus" else (g["alpha_V"], g["alpha_V_exp"])
    return 100 * (v.to_numpy() / (r.to_numpy() * (1 + REF_SIGMA[prop] * noise)) - 1)


# -- 2. static sensitivity -------------------------------------------------------------
def static_sensitivity(model_key: str, materials: list[str] | None = None) -> list[dict]:
    """Rerun a subset with one setting changed at a time; compare with the stored results."""
    from chipff import static
    from chipff.materials import mp_structure
    from chipff.runner import config, load_raw, make_engine, relaxed_structures

    mats = [get_material(m) for m in (materials or STATIC_SUBSET)]
    cfg = config()
    fmax = cfg["relax"]["fmax_eV_per_A"]
    eng = make_engine(model_key)
    base_lat, base_el = load_raw(model_key, "lattice"), load_raw(model_key, "elastic")
    relaxed = relaxed_structures(model_key)
    out = []

    def lattice_volumes(structs, f):
        res = eng.relax(structs, optimize_cell=True, fmax=f, max_steps=cfg["relax"]["max_steps"])
        return [r.atoms.get_volume() / len(r.atoms) for r in res], [r.converged for r in res]

    t = time.time()
    # (a) determinism: identical protocol, fresh and differently composed batch
    v_rep, _ = lattice_volumes([mp_structure(m.id) for m in mats], fmax)
    # (c) tighter tolerance
    v_tight, conv_tight = lattice_volumes([mp_structure(m.id) for m in mats], fmax / 10)
    # (d) start from compressed / expanded cells
    starts = {}
    for s in (0.97, 1.03):
        ss = []
        for m in mats:
            a = mp_structure(m.id)
            a.set_cell(a.cell * s ** (1 / 3), scale_atoms=True)
            ss.append(a)
        starts[s], _ = lattice_volumes(ss, fmax)
    # (b) strain amplitude subsets and (c) tighter tolerance for the elastic tensor
    saved = static.STRAINS
    try:
        k_small = {r.material: r for r in _elastic(static, eng, mats, relaxed, fmax, (-0.005, 0.005))}
        k_large = {r.material: r for r in _elastic(static, eng, mats, relaxed, fmax, (-0.01, 0.01))}
        k_tight = {r.material: r for r in _elastic(static, eng, mats, relaxed, fmax / 10, saved)}
    finally:
        static.STRAINS = saved
    for i, m in enumerate(mats):
        v0 = base_lat[m.id]["volume_per_atom"]
        K0 = base_el[m.id]["K_vrh_GPa"]
        lin = lambda v: 100 * ((v / v0) ** (1 / 3) - 1)  # noqa: E731
        out.append({
            "model": model_key, "material": m.id,
            "lattice_rerun_pct": lin(v_rep[i]), "lattice_tight_fmax_pct": lin(v_tight[i]),
            "lattice_start_minus3pct_vol_pct": lin(starts[0.97][i]), "lattice_start_plus3pct_vol_pct": lin(starts[1.03][i]),
            "K_strain_0p5_only_pct": 100 * (k_small[m.id].K_vrh_GPa / K0 - 1),
            "K_strain_1p0_only_pct": 100 * (k_large[m.id].K_vrh_GPa / K0 - 1),
            "K_tight_fmax_pct": 100 * (k_tight[m.id].K_vrh_GPa / K0 - 1),
            "tight_relax_converged": bool(conv_tight[i]),
        })
    log.info("%s: static sensitivity for %d materials in %.0f s", model_key, len(mats), time.time() - t)
    return out


def _elastic(static, eng, mats, relaxed, fmax, strains):
    static.STRAINS = tuple(strains)
    return static.run_elastic(eng, mats, relaxed, fmax=fmax)


# -- 3. MD sensitivity -----------------------------------------------------------------
MD_VARIANTS = {
    "seed1": {"seed": 1, "materials": MD_SEED_SUBSET},
    "seed2": {"seed": 2, "materials": MD_SEED_SUBSET},
    "big_cell": {"min_supercell_width_A": 14.0, "materials": MD_SIZE_SUBSET},
    "half_dt": {"dt_factor": 0.5, "materials": MD_SIZE_SUBSET},
}


def md_variants(model_key: str, variants: list[str] | None = None, max_edges: int | None = None):
    """Rerun thermal expansion for a subset with one setting changed; results go to thermal_<variant>."""
    from ase.neighborlist import neighbor_list
    from pymatgen.io.ase import AseAtomsAdaptor
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    from chipff.runner import config, load_raw, make_engine, relaxed_structures, run_meta, save_raw, select, thermal_plan
    from chipff.thermal import analyze, make_stop_fn, pack_batches, supercell, time_step_fs, to_record

    base = config()["thermal"]
    eng = make_engine(model_key)
    meta = run_meta(eng)
    relaxed = relaxed_structures(model_key)
    elastic = load_raw(model_key, "elastic")
    for name in variants or list(MD_VARIANTS):
        v = MD_VARIANTS[name]
        tag = f"thermal_{name}"
        done = load_raw(model_key, tag)
        mats = [m for m in select(v["materials"]) if m.id in relaxed and m.id not in done]
        plan = thermal_plan(mats)
        width = v.get("min_supercell_width_A", base["min_supercell_width_A"])
        jobs = []
        for m in mats:
            conv = AseAtomsAdaptor.get_atoms(SpacegroupAnalyzer(AseAtomsAdaptor.get_structure(relaxed[m.id]),
                                                                symprec=0.1).get_conventional_standard_structure())
            sc, reps = supercell(conv, width, max_atoms=1200)
            dt = time_step_fs(sc) * v.get("dt_factor", 1.0)
            integ = base["integrator"]["cubic"] if m.cubic else base["integrator"]["other"]
            K = (elastic.get(m.id) or {}).get("K_reuss_GPa") or 100.0
            e = len(neighbor_list("i", sc, base.get("edge_cutoff_A", 6.0)))
            for T in plan[m.id].temperatures:
                a = sc.copy()
                a.set_cell(sc.cell * (1 + base.get("start_strain_per_K", 1e-5) * T), scale_atoms=True)
                jobs.append({"m": m, "T": T, "atoms": a, "k": 1 / (max(K, 5.0) * 1e9), "edges": e, "reps": reps,
                             "natoms": len(sc), "integ": integ, "dt": dt})
        groups: dict[tuple, list] = {}
        for j in jobs:
            groups.setdefault((j["integ"], j["dt"]), []).append(j)
        for (integ, dt), js in groups.items():
            pending: dict[str, dict] = {}
            need = {}
            for j in js:
                need[j["m"].id] = need.get(j["m"].id, 0) + 1
            for batch in pack_batches(js, int(max_edges or base.get("max_edges_per_batch", 24000))):
                log.info("%s %s: batch of %d systems (%s)", model_key, tag, len(batch),
                         ", ".join(f"{j['m'].id}@{j['T']:.0f}K" for j in batch))
                prod = base["production_ps"]
                o = eng.npt([j["atoms"] for j in batch], [j["T"] for j in batch], integrators=[integ] * len(batch),
                            time_step_fs=dt, compressibility_per_pa=[j["k"] for j in batch],
                            equil_ps=base["equilibration_ps"], min_prod_ps=prod["min"], max_prod_ps=prod["max"],
                            check_every_ps=prod["check_every"], sample_every_fs=base["sample_every_fs"],
                            stop_fn=make_stop_fn(base["stop_when_volume_sem_below"]), seed=v.get("seed", 0),
                            thermostat_tau_fs=base["thermostat_tau_fs"], barostat_tau_fs=base["barostat_tau_fs"],
                            friction_per_fs=base["langevin_friction_per_fs"])
                for i, j in enumerate(batch):
                    pending.setdefault(j["m"].id, {})[j["T"]] = (j, o["cells"][:, i], o["kinetic_energy"][:, i],
                                                               o["pressure_GPa"][:, i], o["prod_ps"])
                recs = []
                for mid, by_T in list(pending.items()):
                    if len(by_T) < need[mid]:
                        continue
                    Ts = sorted(by_T)
                    j0 = by_T[Ts[0]][0]
                    r = analyze(mid, model_key, Ts, [by_T[T][1] for T in Ts], [by_T[T][2] for T in Ts],
                                [by_T[T][3] for T in Ts], j0["natoms"], j0["reps"], integ, dt,
                                [by_T[T][4] for T in Ts])
                    rec = to_record(r)
                    rec["variant"] = {k: val for k, val in v.items() if k != "materials"}
                    recs.append(rec)
                    del pending[mid]
                if recs:
                    save_raw(model_key, tag, recs, {**meta, "variant": name})


def md_variant_table() -> pd.DataFrame:
    """Compare each MD variant's alpha_V with the main run, in units of the combined error bar."""
    from chipff.models import MODELS
    from chipff.runner import load_raw

    rows = []
    for mk in MODELS:
        main = load_raw(mk, "thermal")
        for name in MD_VARIANTS:
            for mid, r in load_raw(mk, f"thermal_{name}").items():
                b = main.get(mid)
                if not b:
                    continue
                d = r["alpha_V_1e6"] - b["alpha_V_1e6"]
                s = float(np.hypot(r["alpha_V_err_1e6"], b["alpha_V_err_1e6"]))
                rows.append({"model": mk, "material": mid, "variant": name, "alpha_V_main": b["alpha_V_1e6"],
                             "alpha_V_variant": r["alpha_V_1e6"], "diff_pct": 100 * d / b["alpha_V_1e6"],
                             "diff_in_sigma": d / s if s else None, "consistent": abs(d) <= 2 * s})
    return pd.DataFrame(rows)


def build(lat, bulk, therm) -> dict:
    """Write results/robustness/*.csv from what exists; called by chipff analyze."""
    OUT.mkdir(parents=True, exist_ok=True)
    ci, pairs = bootstrap_tables(lat, bulk, therm)
    ci.to_csv(OUT / "bootstrap_ci.csv", index=False, float_format="%.4g")
    pairs.to_csv(OUT / "pairwise.csv", index=False, float_format="%.4g")
    md = md_variant_table()
    md.to_csv(OUT / "md_variants.csv", index=False, float_format="%.4g")
    sens_p = OUT / "static_sensitivity.json"
    sens = json.loads(sens_p.read_text()) if sens_p.exists() else []
    return {"bootstrap_ci": json.loads(ci.to_json(orient="records")),
            "pairwise": json.loads(pairs.to_json(orient="records")),
            "md_variants": json.loads(md.to_json(orient="records")), "static_sensitivity": sens}


def save_static_sensitivity(rows: list[dict]):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "static_sensitivity.json"
    old = json.loads(p.read_text()) if p.exists() else []
    keep = [r for r in old if (r["model"], r["material"]) not in {(x["model"], x["material"]) for x in rows}]
    p.write_text(json.dumps(keep + rows, indent=1))
