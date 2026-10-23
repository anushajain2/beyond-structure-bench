"""Evaluate the pre-registered Orb v3 thermal-expansion hypotheses (docs/preregistration_orb_thermal.md).

Written and committed with the pre-registration, before any Orb result existed. It reads the tables that
`chipff analyze` writes and applies the decision rules exactly as registered; nothing here is tuned to data.

    python scripts/prereg_orb_thermal_eval.py                      # results/*.csv -> stdout + JSON
    python scripts/prereg_orb_thermal_eval.py --thermal T.csv --bulk B.csv --out out.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ORB = "orb-v3"
OTHERS = ["mace-mpa-0", "mattersim-5m-native"]
MODELS = [ORB, *OTHERS]
# Orb thermal results already seen before the pre-registration: the six study cases (Gamma-fixed QHA,
# docs/thermal_failure_study.md) and the seven pre-fix benchmark values published in results/thermal_expansion.csv
STUDY = {"Si", "GaAs", "Cu", "Ta", "InP", "HfO2"}
STALE = {"Si", "Ge", "SiC", "GaAs", "GaN", "InP", "AlN"}
SEEN = STUDY | STALE
SEMICONDUCTORS = ["Si", "Ge", "SiC", "GaAs", "GaN", "InP", "AlN"]
# Amendment 1 (before the run): verdicts use Orb's core run only; the deferred materials enter an addendum (--all)
DEFERRED = {"Y2O3", "Si3N4_beta", "TaN", "ZrO2", "HfO2", "TiO2_rutile", "SrTiO3", "MoS2", "hBN", "graphite"}
SEED = 0
N_RANDOM = 100_000
MAX_EXACT = 200_000


def lg(err_pct):
    """Percentage error -> log ratio ln(model / reference)."""
    return math.log1p(err_pct / 100.0)


# -- statistics ----------------------------------------------------------------------------------------
def auc(score, label):
    """Probability that a random positive scores above a random negative (ties count one half)."""
    s, y = np.asarray(score, float), np.asarray(label, bool)
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return None
    return float(np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg]))


def auc_perm_p(score, label):
    """One-sided permutation p for AUC > 0.5: exact over label placements when feasible, else random."""
    s, y = np.asarray(score, float), np.asarray(label, bool)
    n, k = len(s), int(y.sum())
    obs = auc(s, y)
    if math.comb(n, k) <= MAX_EXACT:
        vals = []
        for idx in itertools.combinations(range(n), k):
            lab = np.zeros(n, bool)
            lab[list(idx)] = True
            vals.append(auc(s, lab))
        return float(np.mean(np.asarray(vals) >= obs - 1e-12)), "exact"
    rng = np.random.default_rng(SEED)
    hits = sum(auc(s, rng.permutation(y)) >= obs - 1e-12 for _ in range(N_RANDOM))
    return (hits + 1) / (N_RANDOM + 1), f"{N_RANDOM} random permutations, seed {SEED}"


def spearman(x, y):
    rx, ry = pd.Series(x).rank().to_numpy(), pd.Series(y).rank().to_numpy()
    if np.std(rx) == 0 or np.std(ry) == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def spearman_perm_p(x, y):
    """One-sided permutation p for rho > 0."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    obs = spearman(x, y)
    if math.factorial(len(x)) <= MAX_EXACT:
        vals = [spearman(x, y[list(p)]) for p in itertools.permutations(range(len(y)))]
        return float(np.mean(np.asarray(vals) >= obs - 1e-12)), "exact"
    rng = np.random.default_rng(SEED)
    hits = sum(spearman(x, rng.permutation(y)) >= obs - 1e-12 for _ in range(N_RANDOM))
    return (hits + 1) / (N_RANDOM + 1), f"{N_RANDOM} random permutations, seed {SEED}"


# -- inputs --------------------------------------------------------------------------------------------
def load(thermal_csv, bulk_csv, core_only=True):
    th = pd.read_csv(thermal_csv)
    bk = pd.read_csv(bulk_csv).drop_duplicates(["model", "material"])
    th = th[th["model"].isin(MODELS)]
    if core_only:
        th = th[~((th["model"] == ORB) & th["material"].isin(DEFERRED))]
    bk = bk[bk["model"].isin(MODELS)][["model", "material", "err_exp_pct", "B_exp", "K_for_exp", "B_eos_prime",
                                        "eos_fit_ok", "excluded"]]
    bk = bk.rename(columns={"err_exp_pct": "K_err_pct", "excluded": "K_excluded"})
    return th.merge(bk, on=["model", "material"], how="left")


def rows(df, model, materials=None, need=("err_300K_pct",)):
    d = df[df["model"] == model]
    if materials is not None:
        d = d[d["material"].isin(materials)]
    for c in need:
        d = d[d[c].notna()]
    return d


# -- hypotheses ----------------------------------------------------------------------------------------
def h1(df, materials, label):
    """Orb's alpha error (300 K) is mostly explained by its static bulk-modulus error."""
    d = rows(df, ORB, materials, need=("err_300K_pct", "K_err_pct"))
    per, explained = [], 0
    for _, r in d.iterrows():
        e, p = lg(r["err_300K_pct"]), -lg(r["K_err_pct"])  # p = ln(K_exp / K_model): the K-only prediction
        big = abs(r["err_300K_pct"]) > 20.0
        ok = big and e * p > 0 and 0.5 <= p / e <= 2.0
        explained += ok
        per.append({"material": r["material"], "err_300K_pct": r["err_300K_pct"], "K_err_pct": r["K_err_pct"],
                    "K_only_prediction_pct": 100 * math.expm1(p), "error_over_20pct": big,
                    "share_p_over_e": p / e if e else None, "explained": bool(ok)})
    n = sum(x["error_over_20pct"] for x in per)
    frac = explained / n if n else None
    if n < 4:
        verdict = "inconclusive (fewer than 4 materials with |error| > 20 %)"
    elif frac >= 2 / 3:
        verdict = "supported"
    elif frac <= 1 / 3:
        verdict = "refuted"
    else:
        verdict = "inconclusive"
    rho = spearman([-lg(x["K_err_pct"]) for x in per], [lg(x["err_300K_pct"]) for x in per]) if len(per) >= 3 else None
    # secondary: the same rule with the window-average error
    dw = rows(df, ORB, materials, need=("err_exp_pct", "K_err_pct"))
    wn = wx = 0
    for _, r in dw.iterrows():
        if abs(r["err_exp_pct"]) > 20.0:
            e, p = lg(r["err_exp_pct"]), -lg(r["K_err_pct"])
            wn += 1
            wx += e * p > 0 and 0.5 <= p / e <= 2.0
    return {"set": label, "n_graded": len(per), "n_error_over_20pct": n, "n_explained": explained,
            "fraction_explained": frac, "verdict": verdict, "spearman_prediction_vs_error_all_graded": rho,
            "window_secondary": {"n_error_over_20pct": wn, "n_explained": wx}, "per_material": per}


def h2(df, materials, label):
    """Static K' does not flag Orb's large (|error| > 40 %) errors better than chance."""
    d = rows(df, ORB, materials, need=("err_300K_pct", "B_eos_prime"))
    d = d[d["eos_fit_ok"].astype(str) == "True"]
    score = d["B_eos_prime"].to_numpy(float)
    big = (d["err_300K_pct"].abs() > 40.0).to_numpy()
    npos, nneg = int(big.sum()), int((~big).sum())
    out = {"set": label, "n": len(d), "n_large": npos, "n_not_large": nneg,
           "per_material": [{"material": m, "K_prime": k, "err_300K_pct": e, "large": bool(b)}
                            for m, k, e, b in zip(d["material"], score, d["err_300K_pct"], big)]}
    if npos < 2 or nneg < 2:
        out.update(auc=auc(score, big) if npos and nneg else None, p=None,
                   verdict="inconclusive (fewer than 2 large or 2 not-large errors)")
    else:
        a = auc(score, big)
        p, how = auc_perm_p(score, big)
        verdict = ("supported (no better than chance)" if a <= 0.65 else
                   "refuted (K' flags large errors)" if a >= 0.75 and p < 0.05 else "inconclusive")
        out.update(auc=a, p=p, p_method=how, verdict=verdict)
    flag = score > 5.0  # secondary, descriptive: fixed flag K' > 5
    out["flag_Kprime_gt_5"] = {"hits": int((flag & big).sum()), "false_alarms": int((flag & ~big).sum()),
                               "misses": int((~flag & big).sum()), "correct_quiet": int((~flag & ~big).sum())}
    over = (d["err_300K_pct"] > 40.0).to_numpy()  # secondary: overshoots only (the direction K' predicts)
    out["overshoot_only_auc"] = auc(score, over) if over.any() and (~over).any() else None
    return out


def h3(df, materials, label, col="err_300K_pct"):
    """Orb's disagreement with MACE/MatterSim correlates positively with the three-model mean's error."""
    per = []
    mats = sorted(set(df["material"])) if materials is None else materials
    for m in mats:
        e = {}
        for mk in MODELS:
            r = df[(df["model"] == mk) & (df["material"] == m)]
            if len(r) and pd.notna(r[col].iloc[0]):
                e[mk] = lg(r[col].iloc[0])
        if len(e) < 3:
            continue
        D = abs(e[ORB] - (e[OTHERS[0]] + e[OTHERS[1]]) / 2)
        E = abs(sum(e.values()) / 3)  # log error of the geometric-mean prediction
        E2 = abs((e[OTHERS[0]] + e[OTHERS[1]]) / 2)  # secondary: error of the other two models only
        per.append({"material": m, "D": D, "E": E, "E_other_two": E2})
    out = {"set": label, "metric": col, "n": len(per), "per_material": per}
    if len(per) < 8:
        out.update(rho=None, p=None, verdict="inconclusive (fewer than 8 materials)")
        return out
    D, E = [x["D"] for x in per], [x["E"] for x in per]
    rho = spearman(D, E)
    p, how = spearman_perm_p(D, E)
    verdict = "supported" if rho >= 0.30 and p < 0.05 else "refuted" if rho <= 0 else "inconclusive"
    out.update(rho=rho, p=p, p_method=how, verdict=verdict,
               rho_other_two=spearman(D, [x["E_other_two"] for x in per]))
    return out


def h4(df, models, label):
    """Right at 300 K through compensating errors -> error grows over the window."""
    comp, ctrl = [], []
    for mk in models:
        d = rows(df, mk, None, need=("err_300K_pct", "err_exp_pct", "K_err_pct"))
        for _, r in d.iterrows():
            if abs(r["err_300K_pct"]) >= 20.0:
                continue
            e, p = lg(r["err_300K_pct"]), -lg(r["K_err_pct"])
            res = e - p  # what the non-K ingredients (gamma, C_V, V) contribute
            is_comp = abs(res) >= math.log(1.15) and res * p < 0
            delta = abs(r["err_exp_pct"]) - abs(r["err_300K_pct"])
            (comp if is_comp else ctrl).append({"model": mk, "material": r["material"],
                                                "err_300K_pct": r["err_300K_pct"], "err_window_pct": r["err_exp_pct"],
                                                "K_err_pct": r["K_err_pct"], "delta_pp": delta})
    n = len(comp)
    grow = sum(x["delta_pp"] >= 5.0 for x in comp)
    frac = grow / n if n else None
    mc = float(np.median([x["delta_pp"] for x in comp])) if comp else None
    mk_ = float(np.median([x["delta_pp"] for x in ctrl])) if ctrl else None
    diff = mc - mk_ if (comp and len(ctrl) >= 3) else None
    if n < 3:
        verdict = "inconclusive (fewer than 3 compensation cases)"
    elif frac >= 2 / 3 and (diff is None or diff >= 5.0):
        verdict = "supported"
    elif frac <= 1 / 3 or (diff is not None and diff <= 0):
        verdict = "refuted"
    else:
        verdict = "inconclusive"
    return {"set": label, "n_compensation": n, "n_control": len(ctrl), "n_growing": grow, "fraction_growing": frac,
            "median_delta_comp_pp": mc, "median_delta_control_pp": mk_, "median_difference_pp": diff,
            "control_comparison_skipped": len(ctrl) < 3, "verdict": verdict, "compensation": comp, "control": ctrl}


def descriptive(df, materials):
    """Mean absolute error per model on the given materials, where all three are graded (no decision)."""
    out = {}
    for col in ("err_300K_pct", "err_exp_pct"):
        common = [m for m in materials if all(len(rows(df, mk, [m], need=(col,))) for mk in MODELS)]
        out[col] = {"materials": common,
                    **{mk: float(rows(df, mk, common, need=(col,))[col].abs().mean()) if common else None
                       for mk in MODELS}}
    return out


def evaluate(df):
    allm = sorted(set(df["material"]))
    blind = [m for m in allm if m not in SEEN]
    orb = df[df["model"] == ORB]
    return {
        "blind_set": blind,
        "orb_graded_300K": sorted(orb[orb["err_300K_pct"].notna()]["material"]),
        "orb_graded_window": sorted(orb[orb["err_exp_pct"].notna()]["material"]),
        "orb_missing": sorted(set(allm) - set(orb["material"])),
        "H1_primary_blind": h1(df, blind, "blind"),
        "H1_semiconductors_not_blind": h1(df, SEMICONDUCTORS, "semiconductors (all seen)"),
        "H2_primary_blind": h2(df, blind, "blind"),
        "H2_secondary_all": h2(df, None, "all graded"),
        "H3_primary_blind": h3(df, blind, "blind"),
        "H3_secondary_all": h3(df, None, "all graded"),
        "H3_secondary_window_blind": h3(df, blind, "blind", col="err_exp_pct"),
        "H4_primary_pooled": h4(df, MODELS, "all three models (MACE, MatterSim seen; Orb blind)"),
        "H4_secondary_orb_only": h4(df, [ORB], "Orb only"),
        "descriptive_blind": descriptive(df, blind),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thermal", default=str(ROOT / "results" / "thermal_expansion.csv"))
    ap.add_argument("--bulk", default=str(ROOT / "results" / "bulk_modulus.csv"))
    ap.add_argument("--out", default=str(ROOT / "results" / "preregistration_orb_thermal.json"))
    ap.add_argument("--all", action="store_true", help="include Orb's deferred materials (addendum, not verdicts)")
    a = ap.parse_args()
    res = evaluate(load(a.thermal, a.bulk, core_only=not a.all))
    Path(a.out).write_text(json.dumps(res, indent=1, default=float))
    for k, v in res.items():
        if isinstance(v, dict) and "verdict" in v:
            stat = {x: v.get(x) for x in ("n_error_over_20pct", "n_explained", "auc", "p", "rho", "n",
                                          "n_compensation", "fraction_growing", "median_difference_pp") if x in v}
            print(f"{k:32s} {v['verdict']:40s} {stat}")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
