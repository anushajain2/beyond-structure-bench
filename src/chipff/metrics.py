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


def _exp_axis_curve(mid: str, axis: str):
    """Measured linear alpha along one crystal axis (1e-6/K), or None."""
    from chipff.analysis import _expand_ranges

    te = experimental().get(mid, {}).get("thermal_expansion") or {}
    d = {float(v["T_K"]): float(v["alpha_1e-6_per_K"]) for v in _expand_ranges(te.get("values") or [])
         if v.get("axis") == axis and v.get("T_K") is not None and v.get("alpha_1e-6_per_K") is not None}
    if len(d) < 2:
        return None
    T = sorted(d)
    return np.asarray(T, float), np.asarray([d[t] for t in T], float)


def _model_axial_curve(model: str, mid: str, axis: str = "a"):
    """A model's linear alpha along a or c from the axial run (chipff.axial), if it passed every check."""
    from chipff.provenance import check

    r = load_raw(model, "axial_qha").get(mid)
    if not r or not all(r.get("checks", {}).values()) or check("axial_qha", model, mid, r):
        return None
    return np.asarray(r["curve_T"], float), np.asarray(r[f"curve_alpha_{axis}_1e6"], float)


def _biaxial_modulus(K, G):
    """Polycrystalline biaxial modulus E/(1 - nu) in GPa from bulk and shear moduli."""
    if K is None or G is None or not (K > 0 and G > 0):
        return None
    E = 9 * K * G / (3 * K + G)
    nu = (3 * K - 2 * G) / (2 * (3 * K + G))
    return E / (1 - nu)


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
    """Free expansion mismatch for MISMATCH_PAIRS, from each graded model's alpha(T) and from experiment, and the
    thermal stress it implies in the film.

    The film's linear expansion is its in-plane alpha_a where the film is uniaxial and both the model's axial run and
    an axis-resolved measurement exist (GaN, AlN, Ru, Al2O3: chipff.axial); otherwise alpha_V/3. The stress is
    sigma = -M_f x mismatch (tensile positive), with M_f = E/(1 - nu) the film's polycrystalline biaxial modulus:
    the model's own (VRH K and G) for the model, Materials Project DFT for the reference (measured shear moduli are
    not curated here), so the reference stress mixes measured mismatch with DFT stiffness."""
    from chipff.axial import AXIAL_MATERIALS
    from chipff.materials import mp_record

    rows = []
    usable = therm[~therm["pending"].astype(bool)] if "pending" in therm else therm
    bad = {(r.model, r.material) for _, r in usable.iterrows() if isinstance(r.get("excluded"), str) and r.excluded}
    models = sorted(usable["model"].unique())
    grid_step = 10.0

    def lin(c):
        return None if c is None else (c[0], c[1] / 3)

    def moduli(mk, mid):
        el = load_raw(mk, "elastic").get(mid) or {}
        return _biaxial_modulus(el.get("K_vrh_GPa"), el.get("G_vrh_GPa"))

    for m1, m2 in MISMATCH_PAIRS:
        e2 = lin(_exp_curve(m2))
        ea1 = _exp_axis_curve(m1, "a") if m1 in AXIAL_MATERIALS else None
        dft = (mp_record(m1) or {}).get("dft_elastic") or {}
        m_ref = _biaxial_modulus(dft.get("K_vrh_GPa"), dft.get("G_vrh_GPa"))
        for T in MISMATCH_T:
            grid = np.arange(300.0, T + grid_step / 2, grid_step)

            def eps(c1, c2):
                if c1 is None or c2 is None:
                    return None
                if grid[-1] > min(c1[0].max(), c2[0].max()) or grid[0] < max(c1[0].min(), c2[0].min()) - 10:
                    return None
                return float(np.trapezoid(np.interp(grid, *c1) - np.interp(grid, *c2), grid))  # microstrain

            for mk in models:
                if (mk, m1) in bad or (mk, m2) in bad:
                    continue
                ma1 = _model_axial_curve(mk, m1, "a") if ea1 is not None else None
                inplane = ma1 is not None and eps(ea1, e2) is not None
                c_exp = ea1 if inplane else lin(_exp_curve(m1))
                c_mod = ma1 if inplane else lin(_model_curve(mk, m1))
                ref = eps(c_exp, e2)
                mod = eps(c_mod, lin(_model_curve(mk, m2)))
                if mod is None:
                    continue
                m_mod = moduli(mk, m1)
                s_mod = None if m_mod is None else -m_mod * mod * 1e-3      # GPa x microstrain -> MPa
                s_ref = None if (m_ref is None or ref is None) else -m_ref * ref * 1e-3
                rows.append({"pair": f"{m1} on {m2}", "T_K": T, "model": mk,
                             "film_expansion": "in-plane (a axis)" if inplane else "alpha_V / 3",
                             "mismatch_model_ue": mod, "mismatch_exp_ue": ref,
                             "err_ue": None if ref is None else mod - ref,
                             "err_pct": None if not ref else 100 * (mod / ref - 1),
                             "biaxial_modulus_model_GPa": m_mod, "biaxial_modulus_ref_GPa": m_ref,
                             "stress_model_MPa": s_mod, "stress_ref_MPa": s_ref,
                             "stress_err_MPa": None if (s_mod is None or s_ref is None) else s_mod - s_ref})
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
                     "median_abs_err_pct": float(g["err_pct"].abs().median()),
                     "median_abs_stress_err_MPa": float(g["stress_err_MPa"].abs().median())
                     if "stress_err_MPa" in g and g["stress_err_MPa"].notna().any() else None})
    return pd.DataFrame(rows)


def axial_table(therm: pd.DataFrame) -> pd.DataFrame:
    """Axial (a, c) expansion of the uniaxial materials against axis-resolved experiment, at 300 K and over the
    material's window, with the check that 2 alpha_a + alpha_c reproduces the full QHA's alpha_V."""
    from chipff.axial import AXIAL_MATERIALS
    from chipff.provenance import check

    rows = []
    for mk in sorted(therm["model"].unique()):
        raw = load_raw(mk, "axial_qha")
        for mid in AXIAL_MATERIALS:
            r = raw.get(mid)
            if not r:
                continue
            tr = therm[(therm["model"] == mk) & (therm["material"] == mid)]
            lo, hi = (float(tr["T_low"].iloc[0]), float(tr["T_high"].iloc[0])) if len(tr) else (300.0, 300.0)
            prov = check("axial_qha", mk, mid, r)
            failed = [k for k, v in r.get("checks", {}).items() if not v]
            excluded = ("stale: " + prov) if prov else ("failed: " + ", ".join(failed)) if failed else None
            row = {"model": mk, "material": mid, "T_low": lo, "T_high": hi, "excluded": excluded,
                   "alpha_V_axial_300K": r["alpha_V_300K_1e6"],
                   "alpha_V_qha_300K": float(tr["alpha_V_300K"].iloc[0]) if len(tr) else None}
            row["axial_vs_qha_pct"] = (100 * (row["alpha_V_axial_300K"] / row["alpha_V_qha_300K"] - 1)
                                       if row["alpha_V_qha_300K"] else None)
            for ax in ("a", "c"):
                mc = (np.asarray(r["curve_T"], float), np.asarray(r[f"curve_alpha_{ax}_1e6"], float))
                ec = _exp_axis_curve(mid, ax)
                m300, e300 = _at(mc, 300.0), (_at(ec, 300.0) if ec is not None else None)
                win = np.linspace(lo, hi, 20)
                mw = float(np.mean(np.interp(win, *mc)))
                ew = (float(np.mean(np.interp(win, *ec))) if ec is not None and ec[0].min() <= lo + 50
                      and ec[0].max() >= hi - 50 else None)
                row.update({f"alpha_{ax}_300K": m300, f"alpha_{ax}_300K_exp": e300,
                            f"err_{ax}_300K_pct": None if (excluded or not e300) else 100 * (m300 / e300 - 1),
                            f"alpha_{ax}_window": mw, f"alpha_{ax}_window_exp": ew,
                            f"err_{ax}_window_pct": None if (excluded or not ew) else 100 * (mw / ew - 1)})
            rows.append(row)
    return pd.DataFrame(rows)
