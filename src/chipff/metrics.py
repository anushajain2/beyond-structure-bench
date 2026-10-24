"""Thermal-expansion measures beyond the percentage error (added in v1.1.0).

Percentage error alone can mislead: a small reference makes a modest absolute miss look large, and
the same percentage can mean very different strain in a device. So for each model x material:

  abs_err_300K, abs_err_window   model minus experiment, in 1e-6 per K (volumetric alpha)
  strain_err_ue                  error in accumulated mean linear strain over the window,
                                 (alpha_V,model - alpha_V,exp)/3 x (T_high - T_low), in microstrain
  trend                          does the model get the change of alpha across the window right?
                                 d_alpha = alpha(T_high) - alpha(T_low) for model and experiment
  err_T_high_pct                 percentage error at the top of the window, next to the 300 K one,
                                 to test whether a model that is right at 300 K stays right when hot

and, as an application example, the free thermal-expansion mismatch between two materials,

  delta_eps(T) = integral from 300 K to T of [alpha_L1(T') - alpha_L2(T')] dT',

with alpha_L = alpha_V / 3 (exact for cubic materials, a mean linear value otherwise). Mismatch is
an ingredient of thermal stress, not a prediction of it: stress also depends on geometry,
constraint and the elastic response.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from chipff.materials import experimental, get_material
from chipff.runner import load_raw

# device-relevant pairs: metal or silicide on silicon, and a liner under copper; added 2026-10-24 by device role
# alone, before their mismatch was computed: contact and barrier stacks, dielectrics on silicon, and the
# GaN power/RF stacks. A pair is skipped where a reference does not cover 300 K to T (TaN, HfO2, Si3N4).
MISMATCH_PAIRS = [("Cu", "Si"), ("W", "Si"), ("Al", "Si"), ("Mo", "Si"), ("Ta", "Si"), ("TiSi2", "Si"),
                  ("Cu", "Ta"),
                  ("W", "TiN"), ("TiN", "Si"), ("WSi2", "Si"), ("Ru", "Si"),
                  ("Al2O3", "Si"), ("Y2O3", "Si"),
                  ("GaN", "Si"), ("GaN", "SiC"), ("AlN", "Si")]
MISMATCH_T = (600.0, 900.0)


def _exp_curve(mid: str):
    from chipff.analysis import exp_alpha_V, ref_info

    if ref_info(mid, "thermal_expansion").get("kind") == "range_average":
        return None
    T, a = exp_alpha_V(experimental().get(mid, {}), get_material(mid))
    if len(T) < 2:
        return None
    return np.asarray(T, float), np.asarray(a, float)


def _model_curve(model: str, mid: str, tag: str = "thermal_qha"):
    r = load_raw(model, tag).get(mid)
    if not r or not r.get("curve_T"):
        return None
    return np.asarray(r["curve_T"], float), np.asarray(r["curve_alpha_V_1e6"], float)


def _at(curve, T):
    Tc, a = curve
    return float(np.interp(T, Tc, a)) if Tc.min() - 1e-6 <= T <= Tc.max() + 1e-6 else None


def thermal_metrics(therm: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in therm.iterrows():
        if r.get("pending") or (isinstance(r.get("provenance"), str) and r["provenance"]):
            continue
        row = {"model": r.model, "material": r.material, "class": r["class"], "ref_tier": r.get("ref_tier"),
               "T_low": r.T_low, "T_high": r.T_high}
        if pd.notna(r.get("err_300K_pct")):
            row["abs_err_300K"] = r.alpha_V_300K - r.alpha_V_300K_exp
        if pd.notna(r.get("err_exp_pct")):
            row["abs_err_window"] = r.alpha_V - r.alpha_V_exp
            row["strain_err_ue"] = (r.alpha_V - r.alpha_V_exp) / 3 * (r.T_high - r.T_low)
        exc = r.get("excluded")
        ec, mc = _exp_curve(r.material), _model_curve(r.model, r.material)
        if ec is not None and mc is not None and not (isinstance(exc, str) and exc):
            e_lo, e_hi = _at(ec, r.T_low), _at(ec, r.T_high)
            m_lo, m_hi = _at(mc, r.T_low), _at(mc, r.T_high)
            if None not in (e_lo, e_hi, m_lo, m_hi):
                de, dm = e_hi - e_lo, m_hi - m_lo
                row.update(d_alpha_exp=de, d_alpha_model=dm,
                           trend_sign_ok=bool(np.sign(round(de, 2)) == np.sign(round(dm, 2))),
                           err_T_high_pct=100 * (m_hi / e_hi - 1))
        rows.append(row)
    return pd.DataFrame(rows)


def compensation_check(metrics: pd.DataFrame, good: float = 20.0) -> pd.DataFrame:
    """Results that are good at 300 K: do they stay good at the top of the window?"""
    if metrics.empty or "err_T_high_pct" not in metrics:
        return pd.DataFrame()
    m = metrics.dropna(subset=["err_T_high_pct"])
    rows = []
    for _, r in m.iterrows():
        t300 = r.get("abs_err_300K")
        rows.append({"model": r.model, "material": r.material, "T_high": r.T_high,
                     "err_T_high_pct": r.err_T_high_pct, "trend_sign_ok": r.trend_sign_ok,
                     "d_alpha_exp": r.d_alpha_exp, "d_alpha_model": r.d_alpha_model,
                     "has_300K": pd.notna(t300)})
    return pd.DataFrame(rows)


def thermal_mismatch(therm: pd.DataFrame) -> pd.DataFrame:
    """Free expansion mismatch for MISMATCH_PAIRS, from each graded model's alpha(T) and from experiment."""
    rows = []
    usable = therm[~therm["pending"].astype(bool)] if "pending" in therm else therm
    bad = {(r.model, r.material) for _, r in usable.iterrows() if isinstance(r.get("excluded"), str) and r.excluded}
    models = sorted(usable["model"].unique())
    grid_step = 10.0
    for m1, m2 in MISMATCH_PAIRS:
        e1, e2 = _exp_curve(m1), _exp_curve(m2)
        for T in MISMATCH_T:
            grid = np.arange(300.0, T + grid_step / 2, grid_step)

            def eps(c1, c2):
                if c1 is None or c2 is None:
                    return None
                if grid[-1] > min(c1[0].max(), c2[0].max()) or grid[0] < max(c1[0].min(), c2[0].min()) - 10:
                    return None
                d = (np.interp(grid, *c1) - np.interp(grid, *c2)) / 3
                return float(np.trapezoid(d, grid))   # 1e-6 x K -> microstrain

            ref = eps(e1, e2)
            for mk in models:
                if (mk, m1) in bad or (mk, m2) in bad:
                    continue
                mod = eps(_model_curve(mk, m1), _model_curve(mk, m2))
                if mod is None:
                    continue
                rows.append({"pair": f"{m1} on {m2}", "T_K": T, "model": mk, "mismatch_model_ue": mod,
                             "mismatch_exp_ue": ref, "err_ue": None if ref is None else mod - ref,
                             "err_pct": None if not ref else 100 * (mod / ref - 1)})
    return pd.DataFrame(rows)


def mismatch_summary(mism: pd.DataFrame) -> pd.DataFrame:
    """Per model and temperature: how often the free mismatch has the measured sign, how often it is within
    25 % of the measured value, and the median miss in microstrain, over the pairs with a reference."""
    if mism.empty:
        return pd.DataFrame()
    d = mism[mism["mismatch_exp_ue"].notna()]
    rows = []
    for (mk, T), g in d.groupby(["model", "T_K"]):
        rows.append({"model": mk, "T_K": T, "n_pairs": len(g),
                     "sign_right": int((np.sign(g["mismatch_model_ue"]) == np.sign(g["mismatch_exp_ue"])).sum()),
                     "within_25pct": int((g["err_pct"].abs() <= 25).sum()),
                     "median_abs_err_ue": float(g["err_ue"].abs().median()),
                     "median_abs_err_pct": float(g["err_pct"].abs().median())})
    return pd.DataFrame(rows)
