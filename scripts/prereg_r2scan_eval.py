"""Evaluate the pre-registered PBE-vs-r2SCAN test on UMA (docs/preregistration_r2scan.md).

Written and committed with the pre-registration, before either model was run. The two models are UMA s-1.2.1
(PBE-trained) and its r2SCAN fine-tune; everything else (code, settings, references) is shared.

    python scripts/prereg_r2scan_eval.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PBE, R2 = "uma-s-1p2p1", "uma-s-1p2p1-r2scan"
SEMIS = ["Si", "Ge", "SiC", "GaAs", "GaN", "InP", "AlN"]


def _col(df, model, col, mats=None):
    d = df[(df["model"] == model) & df[col].notna()]
    if mats is not None:
        d = d[d["material"].isin(mats)]
    return d.set_index("material")[col]


def paired(df, col, mats=None):
    a, b = _col(df, PBE, col, mats), _col(df, R2, col, mats)
    common = sorted(set(a.index) & set(b.index))
    return a[common], b[common]


def lg(x):
    return np.log1p(np.asarray(x, float) / 100)


def r1(bulk):
    """Semiconductor bulk moduli: mean signed error rises (stiffer) by >= 5 pp and its magnitude falls."""
    a, b = paired(bulk, "err_exp_pct", SEMIS)
    out = {"n": len(a), "mean_signed_pbe": float(a.mean()) if len(a) else None,
           "mean_signed_r2scan": float(b.mean()) if len(b) else None}
    if len(a) < 4:
        return {**out, "verdict": "inconclusive (fewer than 4 semiconductors)"}
    shift = b.mean() - a.mean()
    out["shift_pp"] = float(shift)
    verdict = ("supported" if shift >= 5 and abs(b.mean()) < abs(a.mean()) else
               "refuted" if shift < 0 else "inconclusive")
    return {**out, "verdict": verdict}


def r2(therm):
    """Semiconductor thermal expansion at 300 K: mean |log error| falls by >= 20 % (relative)."""
    a, b = paired(therm, "err_300K_pct", SEMIS)
    out = {"n": len(a), "materials": list(a.index)}
    if len(a) < 4:
        return {**out, "verdict": "inconclusive (fewer than 4 semiconductors)"}
    ma, mb = float(np.mean(np.abs(lg(a)))), float(np.mean(np.abs(lg(b))))
    change = mb / ma - 1
    verdict = "supported" if change <= -0.20 else "refuted" if change > 0 else "inconclusive"
    return {**out, "mean_abs_log_err_pbe": ma, "mean_abs_log_err_r2scan": mb, "relative_change": change,
            "verdict": verdict}


def r3(therm):
    """Ta's overshoot (a model error, not PBE's) survives r2SCAN: err_300K > +25 %."""
    b = _col(therm, R2, "err_300K_pct", ["Ta"])
    if b.empty:
        return {"verdict": "inconclusive (Ta not graded)"}
    e = float(b.iloc[0])
    verdict = "supported" if e > 25 else "refuted" if e < 15 else "inconclusive"
    return {"err_300K_pct_r2scan": e, "err_300K_pct_pbe": float(_col(therm, PBE, "err_300K_pct", ["Ta"]).iloc[0])
            if not _col(therm, PBE, "err_300K_pct", ["Ta"]).empty else None, "verdict": verdict}


def r4(lat):
    """Lattice constants: mean signed error (non-layered) falls by >= 0.3 pp."""
    lat = lat[lat["class"] != "layered"]
    a, b = paired(lat, "err_lin_exp_pct")
    if len(a) < 10:
        return {"n": len(a), "verdict": "inconclusive (fewer than 10 materials)"}
    shift = float(b.mean() - a.mean())
    verdict = "supported" if shift <= -0.3 else "refuted" if shift > 0 else "inconclusive"
    return {"n": len(a), "mean_signed_pbe": float(a.mean()), "mean_signed_r2scan": float(b.mean()),
            "shift_pp": shift, "verdict": verdict}


def descriptive(lat, bulk, therm):
    out = {}
    for name, df, col in (("lattice", lat[lat["class"] != "layered"], "err_lin_exp_pct"),
                          ("bulk_modulus", bulk, "err_exp_pct"), ("thermal_300K", therm, "err_300K_pct"),
                          ("thermal_window", therm, "err_exp_pct")):
        a, b = paired(df, col)
        out[name] = {"n": len(a), "mae_pbe": float(a.abs().mean()) if len(a) else None,
                     "mae_r2scan": float(b.abs().mean()) if len(b) else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results" / "preregistration_r2scan.json"))
    a = ap.parse_args()
    lat = pd.read_csv(ROOT / "results" / "lattice.csv")
    bulk = pd.read_csv(ROOT / "results" / "bulk_modulus.csv").drop_duplicates(["model", "material"])
    therm = pd.read_csv(ROOT / "results" / "thermal_expansion.csv")
    therm = therm[therm["class"] != "layered"]
    res = {"R1": r1(bulk), "R2": r2(therm), "R3": r3(therm), "R4": r4(lat), "descriptive": descriptive(lat, bulk, therm)}
    Path(a.out).write_text(json.dumps(res, indent=1, default=float))
    for k in ("R1", "R2", "R3", "R4"):
        print(k, res[k]["verdict"], {x: v for x, v in res[k].items() if x != "verdict" and not isinstance(v, list)})
    print("wrote", a.out)


if __name__ == "__main__":
    main()
