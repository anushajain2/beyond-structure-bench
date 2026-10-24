"""Evaluate the pre-registered UMA hypotheses (docs/preregistration_uma.md).

Written and committed with the pre-registration, before any UMA result existed. It reads the tables that
`chipff analyze` writes, plus the predictors frozen in results/preregistration_uma_predictors.json, and applies
the decision rules exactly as registered.

    python scripts/prereg_uma_eval.py
    python scripts/prereg_uma_eval.py --thermal T.csv --bulk B.csv --mismatch M.csv --out out.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prereg_orb_thermal_eval import lg, spearman, spearman_perm_p  # noqa: E402  (same statistics, same seed)

UMA = "uma-s-1p2"
OTHERS = {"mace-mpa-0": "MACE", "mattersim-5m-native": "MatterSim", "orb-v3": "Orb"}
# stacks on Si whose measured mismatch at 900 K is below 2000 microstrain: the ones a too-large silicon alpha
# can flip (fixed from the measured curves, before UMA ran)
SI_SENSITIVE = ["W on Si", "Mo on Si", "Ta on Si", "GaN on Si", "AlN on Si"]


def u1(th, predictors):
    """The three existing models' spread at 300 K predicts UMA's own error there."""
    u = th[(th["model"] == UMA) & th["err_300K_pct"].notna()].set_index("material")["err_300K_pct"]
    rows = [{"material": m, "spread_3": v["spread_3model_log"], "uma_abs_log_err": abs(lg(u[m]))}
            for m, v in predictors.items() if m in u.index]
    out = {"n": len(rows), "per_material": rows}
    if len(rows) < 8:
        return {**out, "rho": None, "p": None, "verdict": "inconclusive (fewer than 8 materials)"}
    x, y = [r["spread_3"] for r in rows], [r["uma_abs_log_err"] for r in rows]
    rho = spearman(x, y)
    p, how = spearman_perm_p(x, y)
    verdict = "supported" if rho >= 0.30 and p < 0.05 else "refuted" if rho <= 0 else "inconclusive"
    return {**out, "rho": rho, "p": p, "p_method": how, "verdict": verdict}


def u2(th, bk):
    """UMA's large 300 K errors are mostly explained by its static bulk-modulus error (H1's rule)."""
    d = th[(th["model"] == UMA) & th["err_300K_pct"].notna()].merge(
        bk[bk["model"] == UMA][["material", "err_exp_pct"]].rename(columns={"err_exp_pct": "K_err_pct"}), on="material")
    d = d[d["K_err_pct"].notna()]
    per, n, ok = [], 0, 0
    for _, r in d.iterrows():
        e, p = lg(r["err_300K_pct"]), -lg(r["K_err_pct"])
        big = abs(r["err_300K_pct"]) > 20.0
        expl = big and e * p > 0 and 0.5 <= p / e <= 2.0
        n += big
        ok += expl
        per.append({"material": r["material"], "err_300K_pct": r["err_300K_pct"], "K_err_pct": r["K_err_pct"],
                    "error_over_20pct": bool(big), "share_p_over_e": p / e if e else None, "explained": bool(expl)})
    frac = ok / n if n else None
    verdict = ("inconclusive (fewer than 4 materials with |error| > 20 %)" if n < 4 else
               "supported" if frac >= 2 / 3 else "refuted" if frac <= 1 / 3 else "inconclusive")
    return {"n_graded": len(per), "n_error_over_20pct": n, "n_explained": ok, "fraction_explained": frac,
            "verdict": verdict, "per_material": per}


def u3(th, mism):
    """Whether UMA flips the sign of the Si-sensitive stacks follows its silicon error over Si's window."""
    si = th[(th["model"] == UMA) & (th["material"] == "Si")]["err_exp_pct"]
    m = mism[(mism["model"] == UMA) & (mism["T_K"] == 900) & mism["pair"].isin(SI_SENSITIVE)
             & mism["mismatch_exp_ue"].notna()]
    wrong = int((np.sign(m["mismatch_model_ue"]) != np.sign(m["mismatch_exp_ue"])).sum())
    out = {"si_window_err_pct": None if si.empty or pd.isna(si.iloc[0]) else float(si.iloc[0]),
           "n_stacks": len(m), "n_wrong_sign": wrong,
           "per_stack": m[["pair", "mismatch_model_ue", "mismatch_exp_ue"]].to_dict("records")}
    if out["si_window_err_pct"] is None or len(m) < 4:
        return {**out, "verdict": "inconclusive (Si not graded or fewer than 4 stacks)"}
    if out["si_window_err_pct"] > 30.0:
        verdict = "supported" if wrong >= 3 else "refuted"
        out["prediction"] = "Si > +30 %: wrong sign on at least 3"
    elif abs(out["si_window_err_pct"]) <= 30.0:
        verdict = "supported" if wrong <= 1 else "refuted"
        out["prediction"] = "Si within 30 %: wrong sign on at most 1"
    else:
        verdict = "inconclusive (Si below -30 %: no prediction registered)"
    return {**out, "verdict": verdict}


def u4(th):
    """UMA's errors correlate more with Orb's (same OMat24 training data) than with MACE's or MatterSim's."""
    piv = th[th["model"].isin([UMA, *OTHERS])].pivot(index="material", columns="model", values="err_300K_pct")
    r = {}
    for mk in OTHERS:
        d = piv[[UMA, mk]].dropna() if UMA in piv and mk in piv else pd.DataFrame()
        r[mk] = (float(np.corrcoef(np.log1p(d[UMA] / 100), np.log1p(d[mk] / 100))[0, 1]) if len(d) >= 10 else None,
                 len(d))
    rs = {k: v[0] for k, v in r.items()}
    out = {"pearson_log_err": {OTHERS[k]: {"r": v[0], "n": v[1]} for k, v in r.items()}}
    if any(v is None for v in rs.values()):
        return {**out, "verdict": "inconclusive (fewer than 10 common materials)"}
    ro, rm, rsim = rs["orb-v3"], rs["mace-mpa-0"], rs["mattersim-5m-native"]
    verdict = ("supported" if ro >= 0.5 and ro > rm and ro > rsim else
               "refuted" if ro < rm and ro < rsim else "inconclusive")
    return {**out, "verdict": verdict}


def descriptive(th, bk):
    out = {}
    for prop, df, col in [("thermal_300K", th, "err_300K_pct"), ("thermal_window", th, "err_exp_pct"),
                          ("bulk_modulus", bk, "err_exp_pct")]:
        piv = df[df["model"].isin([UMA, *OTHERS])].pivot_table(index="material", columns="model", values=col)
        common = piv.dropna()
        out[prop] = {"n_common": len(common), **{k: float(common[k].abs().mean()) for k in common.columns}}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thermal", default=str(ROOT / "results" / "thermal_expansion.csv"))
    ap.add_argument("--bulk", default=str(ROOT / "results" / "bulk_modulus.csv"))
    ap.add_argument("--mismatch", default=str(ROOT / "results" / "thermal_mismatch.csv"))
    ap.add_argument("--predictors", default=str(ROOT / "results" / "preregistration_uma_predictors.json"))
    ap.add_argument("--out", default=str(ROOT / "results" / "preregistration_uma.json"))
    a = ap.parse_args()
    th = pd.read_csv(a.thermal)
    th = th[th["class"] != "layered"]
    bk = pd.read_csv(a.bulk).drop_duplicates(["model", "material"])
    mism = pd.read_csv(a.mismatch)
    pred = json.loads(Path(a.predictors).read_text())["materials"]
    res = {"U1": u1(th, pred), "U2": u2(th, bk), "U3": u3(th, mism), "U4": u4(th), "descriptive": descriptive(th, bk)}
    Path(a.out).write_text(json.dumps(res, indent=1, default=float))
    for k in ("U1", "U2", "U3", "U4"):
        v = res[k]
        print(f"{k}  {v['verdict']:45s}", {x: v.get(x) for x in ("rho", "p", "n", "n_error_over_20pct", "n_explained",
                                                                 "si_window_err_pct", "n_wrong_sign") if x in v})
    print("U4", res["U4"]["pearson_log_err"])
    print("wrote", a.out)


if __name__ == "__main__":
    main()
