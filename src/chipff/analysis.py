"""Compare model results with DFT and experiment; build the trust map.

Outputs (results/):
  lattice.csv, bulk_modulus.csv, thermal_expansion.csv   one row per model × material
  trust_map.csv          mean absolute % error per model × class × property × reference
  checks.csv             every self-check, pass/fail, per model × material
  summary.json           everything the report and the MCP server read
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from chipff.materials import CLASS_LABELS, ROOT, experimental, load_materials, mp_record
from chipff.models import MODELS as _ALL_MODELS

MODELS = {k: m for k, m in _ALL_MODELS.items() if not m.excluded}
from chipff.provenance import check as provenance_check
from chipff.runner import config, load_raw

OUT = ROOT / "results"
HYDROSTATIC_WORDS = ("eos", "equation of state", "compression", "birch", "murnaghan", "vinet", "x-ray", "isothermal",
                     "hydrostatic", "diamond anvil", "pressure")


# -- reference helpers ---------------------------------------------------------
def _conv_natoms(mid: str) -> int | None:
    rec = mp_record(mid)
    if not rec:
        return None
    from pymatgen.core import Structure
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    s = Structure.from_dict(rec["structure"])
    return len(SpacegroupAnalyzer(s, symprec=0.1).get_conventional_standard_structure())


def exp_volume_per_atom(mat, lat: dict, nconv: int) -> float | None:
    a, b, c = lat.get("a"), lat.get("b"), lat.get("c")
    if a is None:
        return None
    sysname = mat.crystal_system
    if sysname == "cubic":
        v = a**3
    elif sysname in ("hexagonal", "trigonal"):
        if c is None:
            return None
        v = math.sqrt(3) / 2 * a * a * c
    elif sysname == "tetragonal":
        v = a * a * c if c else None
    elif sysname == "orthorhombic":
        v = a * b * c if (b and c) else None
    elif sysname == "monoclinic":
        beta = lat.get("beta_deg")
        v = a * b * c * math.sin(math.radians(beta)) if (b and c and beta) else None
    else:
        v = None
    return None if v is None else v / nconv


def exp_bulk(e: dict) -> tuple[float | None, str]:
    bm = e.get("bulk_modulus") or {}
    val = bm.get("value_GPa")
    method = (bm.get("method") or "").lower()
    kind = "reuss" if any(w in method for w in HYDROSTATIC_WORDS) else "vrh"
    return val, kind


_QUALITY_FIELDS = ("tier", "quality", "kind", "sigma", "why")


def reference_quality() -> dict:
    """data/reference_quality.yaml: tier, quality, kind and uncertainty of every experimental reference."""
    import yaml

    p = ROOT / "data" / "reference_quality.yaml"
    return yaml.safe_load(p.read_text()) if p.exists() else {"defaults": {}}


def ref_info(mid: str, prop: str, q: dict | None = None) -> dict:
    q = q or reference_quality()
    e = (q.get(mid) or {}).get(prop) or {}
    sigma = e.get("sigma", q.get("defaults", {}).get(prop))
    return {"tier": e.get("tier"), "quality": e.get("quality"), "kind": e.get("kind"), "sigma": sigma,
            "why": e.get("why")}


def attach_reference_quality(df: pd.DataFrame, prop: str) -> pd.DataFrame:
    """Add ref_tier, ref_quality, ref_kind, ref_sigma and ref_why columns."""
    if df.empty:
        return df
    q = reference_quality()
    info = df["material"].map(lambda m: ref_info(m, prop, q))
    for f in _QUALITY_FIELDS:
        df[f"ref_{f}"] = info.map(lambda d, f=f: d[f])
    return df


def _expand_ranges(vals: list[dict]) -> list[dict]:
    """A value averaged over T_range_K stands at both ends of its range."""
    out = []
    for v in vals:
        if v.get("T_K") is None and v.get("T_range_K"):
            lo, hi = v["T_range_K"]
            out += [{**v, "T_K": lo}, {**v, "T_K": hi}]
        else:
            out.append(v)
    return out


def exp_alpha_V(e: dict, mat) -> tuple[list[float], list[float]]:
    """Experimental volumetric expansion α_V(T) from linear per-axis data."""
    te = e.get("thermal_expansion") or {}
    vals = _expand_ranges(te.get("values") or [])
    by_axis: dict[str, dict[float, float]] = {}
    for v in vals:
        if v.get("alpha_1e-6_per_K") is None or v.get("T_K") is None:
            continue
        by_axis.setdefault(v.get("axis", "iso"), {})[float(v["T_K"])] = float(v["alpha_1e-6_per_K"])
    if "volume" in by_axis:
        T = sorted(by_axis["volume"])
        return T, [by_axis["volume"][t] for t in T]
    sysname = mat.crystal_system
    if sysname == "cubic" or set(by_axis) == {"iso"}:
        d = by_axis.get("iso") or by_axis.get("a") or {}
        T = sorted(d)
        return T, [3 * d[t] for t in T]
    if sysname in ("hexagonal", "trigonal", "tetragonal") and "a" in by_axis and "c" in by_axis:
        T = sorted(set(by_axis["a"]) & set(by_axis["c"]))
        return T, [2 * by_axis["a"][t] + by_axis["c"][t] for t in T]
    if {"a", "b", "c"} <= set(by_axis):
        T = sorted(set(by_axis["a"]) & set(by_axis["b"]) & set(by_axis["c"]))
        return T, [by_axis["a"][t] + by_axis["b"][t] + by_axis["c"][t] for t in T]
    if "iso" in by_axis:  # polycrystalline average for a non-cubic solid
        d = by_axis["iso"]
        T = sorted(d)
        return T, [3 * d[t] for t in T]
    return [], []


def exp_alpha_axes(e: dict) -> dict[str, tuple[list, list]]:
    te = e.get("thermal_expansion") or {}
    out: dict[str, dict] = {}
    for v in _expand_ranges(te.get("values") or []):
        if v.get("alpha_1e-6_per_K") is None or v.get("T_K") is None:
            continue
        out.setdefault(v.get("axis", "iso"), {})[float(v["T_K"])] = float(v["alpha_1e-6_per_K"])
    return {k: (sorted(d), [d[t] for t in sorted(d)]) for k, d in out.items()}


def window_average(T: list, y: list, lo: float, hi: float, tol: float = 50.0):
    """Mean of y(T) over [lo, hi] by linear interpolation; None if data doesn't cover it."""
    if not T:
        return None, "no experimental data"
    T, y = np.asarray(T, float), np.asarray(y, float)
    if len(T) == 1:
        return None, f"only one experimental temperature ({T[0]:.0f} K)"
    if T.min() > lo + tol or T.max() < hi - tol:
        return None, f"experiment covers {T.min():.0f}-{T.max():.0f} K, window is {lo:.0f}-{hi:.0f} K"
    grid = np.linspace(max(lo, T.min()), min(hi, T.max()), 50)
    return float(np.mean(np.interp(grid, T, y))), "ok"


def pct(model, ref):
    if model is None or ref is None or ref == 0 or (isinstance(ref, float) and math.isnan(ref)):
        return None
    return 100.0 * (model / ref - 1.0)


# -- tables -----------------------------------------------------------------------
def lattice_table() -> pd.DataFrame:
    exp = experimental()
    rows = []
    for mat in load_materials():
        mp = mp_record(mat.id) or {}
        dft = mp.get("dft_lattice") or {}
        e = exp.get(mat.id, {})
        lat = e.get("lattice") or {}
        nconv = _conv_natoms(mat.id)
        v_exp = exp_volume_per_atom(mat, lat, nconv) if nconv else None
        for mk in MODELS:
            r = load_raw(mk, "lattice").get(mat.id)
            if not r:
                continue
            row = {
                "model": mk, "material": mat.id, "class": mat.cls, "converged": r["converged"],
                "symmetry_kept": r["symmetry_kept"], "spg_end": r["spg_end"],
                "a": r["a"], "b": r["b"], "c": r["c"], "beta": r["beta"], "V_atom": r["volume_per_atom"],
                "a_dft": dft.get("a"), "c_dft": dft.get("c"), "V_atom_dft": dft.get("volume_per_atom"),
                "a_exp": lat.get("a"), "b_exp": lat.get("b"), "c_exp": lat.get("c"), "V_atom_exp": v_exp,
                "exp_source": lat.get("source"),
            }
            if mat.crystal_system == "orthorhombic" and all(lat.get(k) for k in "abc"):
                # axis labels differ between conventions (e.g. Pnma vs Pbnm): match each model
                # axis to the experimental axis it is closest to
                import itertools

                m3, e3 = [r["a"], r["b"], r["c"]], [lat["a"], lat["b"], lat["c"]]
                best = min(itertools.permutations(range(3)),
                           key=lambda p: sum(math.log(m3[p[i]] / e3[i]) ** 2 for i in range(3)))
                row["a"], row["b"], row["c"] = (m3[best[i]] for i in range(3))
                row["axis_matching"] = "".join("abc"[i] for i in best)
            row["excluded"] = None
            row["provenance"] = provenance_check("lattice", mk, mat.id, r)
            if row["provenance"]:
                row["excluded"] = "stale: " + row["provenance"]
            elif not r["symmetry_kept"]:
                row["excluded"] = f"relaxed to a different crystal form (space group {r['spg_start']} -> {r['spg_end']})"
            elif not r["converged"]:
                row["excluded"] = "relaxation did not converge"
            for ref in ("dft", "exp"):
                vref = row[f"V_atom_{ref}"]
                row[f"err_lin_{ref}_pct"] = None if (not vref or row["excluded"]) else (
                    100 * ((r["volume_per_atom"] / vref) ** (1 / 3) - 1))
            ok = not row["excluded"]
            row["err_a_exp_pct"] = pct(row["a"], lat.get("a")) if ok else None
            row["err_b_exp_pct"] = pct(row["b"], lat.get("b")) if (ok and lat.get("b")) else None
            row["err_c_exp_pct"] = pct(row["c"], lat.get("c")) if (ok and not mat.cubic) else None
            rows.append(row)
    return pd.DataFrame(rows)


def bulk_table() -> pd.DataFrame:
    exp = experimental()
    rows = []
    for mat in load_materials():
        mp = mp_record(mat.id) or {}
        dft = dict(mp.get("dft_elastic") or {})
        # MP occasionally carries an unphysical elastic fit (e.g. negative K for hcp Co): drop it
        if any((dft.get(k) is not None and dft[k] <= 0) for k in ("K_vrh_GPa", "K_reuss_GPa", "G_vrh_GPa")):
            dft["K_vrh_GPa"] = None
        e = exp.get(mat.id, {})
        b_exp, kind = exp_bulk(e)
        for mk in MODELS:
            el = load_raw(mk, "elastic").get(mat.id)
            eos = load_raw(mk, "eos").get(mat.id)
            if not el:
                continue
            k_for_exp = el["K_reuss_GPa"] if kind == "reuss" else el["K_vrh_GPa"]
            asym = el.get("asymmetry_rel", 0.0)
            excluded = None
            lat_row = load_raw(mk, "lattice").get(mat.id) or {}
            prov = provenance_check("elastic", mk, mat.id, el) or (provenance_check("eos", mk, mat.id, eos) if eos else None)
            if prov:
                excluded = "stale: " + prov
            elif lat_row and not lat_row.get("symmetry_kept", True):
                excluded = "relaxed to a different crystal form"
            elif not el["mechanically_stable"]:
                excluded = "elastic tensor not positive definite"
            elif asym > 0.05:
                excluded = f"elastic fit {100 * asym:.0f}% asymmetric (nonlinear response)"
            rows.append({
                "model": mk, "material": mat.id, "class": mat.cls,
                "K_vrh": el["K_vrh_GPa"], "K_reuss": el["K_reuss_GPa"], "K_voigt": el["K_voigt_GPa"],
                "G_vrh": el["G_vrh_GPa"], "B_eos": eos["B0_GPa"] if eos else None,
                "B_eos_prime": eos["B0_prime"] if eos else None,
                "K_vrh_dft": dft.get("K_vrh_GPa"), "B_exp": b_exp, "exp_definition": kind,
                "K_for_exp": k_for_exp,
                "exp_source": (e.get("bulk_modulus") or {}).get("source"),
                "err_dft_pct": None if excluded else pct(el["K_vrh_GPa"], dft.get("K_vrh_GPa")),
                "err_exp_pct": None if excluded else pct(k_for_exp, b_exp),
                "excluded": excluded, "asymmetry_rel": asym, "provenance": prov,
                "eos_vs_elastic_pct": pct(eos["B0_GPa"], el["K_vrh_GPa"]) if eos else None,
                "mechanically_stable": el["mechanically_stable"], "eos_fit_ok": eos["fit_ok"] if eos else None,
            })
    return pd.DataFrame(rows)


def thermal_table(tag: str = "thermal_qha") -> pd.DataFrame:
    """Thermal expansion vs experiment. Default source: QHA (docs/thermal_method.md)."""
    exp = experimental()
    rows = []
    mats = load_materials()
    # a model whose run has not covered every material is reported per material but kept out
    # of class averages, rankings and model comparisons until it is complete
    pending = {mk for mk in MODELS if 0 < len(load_raw(mk, tag)) < len(mats)}
    for mat in mats:
        e = exp.get(mat.id, {})
        T_exp, aV_exp = exp_alpha_V(e, mat)
        for mk in MODELS:
            r = load_raw(mk, tag).get(mat.id)
            if not r:
                continue
            lo, hi = min(r["temperatures"]), max(r["temperatures"])
            ref, why = window_average(T_exp, aV_exp, lo, hi)
            prov = provenance_check(tag, mk, mat.id, r)
            checks = r.get("checks", {})
            excluded = None
            if prov:
                excluded = "stale: " + prov
            elif mat.layered:
                excluded = "layered: isotropic volume scan cannot represent its anisotropic expansion"
            elif not checks.get("dynamically_stable", True):
                excluded = f"dynamically unstable (lowest phonon {r.get('min_frequency_THz', float('nan')):.2f} THz)"
            elif not all(checks.values()):
                excluded = "failed: " + ", ".join(k for k, v in checks.items() if not v)
            lat_row = load_raw(mk, "lattice").get(mat.id) or {}
            if not excluded and lat_row and not lat_row.get("symmetry_kept", True):
                excluded = "relaxed to a different crystal form"
            # secondary comparison at room temperature (added with the switch to QHA, which is
            # most reliable there): not affected by high-temperature breakdown of the window
            ex300 = excluded if (excluded and not excluded.startswith("failed")) else None
            # a failed volume check leaves 300 K valid only when every scanned volume was stable: then the
            # failure lies at the window's hot end. If instability cut the scan short (Orb Al: stable only up
            # to 1.015 V0), the 300 K volume itself can fall outside the fit and alpha(300 K) is meaningless.
            if (not ex300 and not checks.get("volume_inside_scan", True)
                    and len(r.get("volumes_used") or []) < len(r.get("volume_scales") or [])):
                ex300 = "failed: volume_inside_scan with the stable scan cut short by instability"
            # a range average (one constant alpha over a wide range) is not a value at 300 K
            point_ref = ref_info(mat.id, "thermal_expansion").get("kind") != "range_average"
            a300_exp = (float(np.interp(300.0, T_exp, aV_exp)) if point_ref and T_exp and min(T_exp) <= 310
                        and max(T_exp) >= 290 else None)
            rows.append({
                "model": mk, "material": mat.id, "class": mat.cls, "T_low": lo, "T_high": hi,
                "alpha_V": r["alpha_V_1e6"], "alpha_V_err": r.get("alpha_V_err_1e6"),
                "alpha_V_300K": r.get("alpha_V_300K_1e6"), "alpha_V_exp": ref, "exp_note": why,
                "exp_source": (e.get("thermal_expansion") or {}).get("source"),
                "err_exp_pct": None if excluded else pct(r["alpha_V_1e6"], ref),
                "alpha_V_300K_exp": a300_exp,
                "err_300K_pct": None if (ex300 or r.get("alpha_V_300K_1e6") is None) else pct(r["alpha_V_300K_1e6"], a300_exp),
                "excluded_300K": ex300,
                "excluded": excluded, "provenance": prov, "method": r.get("method", "MD"),
                "pending": mk in pending,
                **{f"check_{k}": v for k, v in checks.items()},
            })
    return pd.DataFrame(rows)


def grade(err: float | None, th: dict) -> str | None:
    if err is None or (isinstance(err, float) and math.isnan(err)):
        return None
    a = abs(err)
    return "good" if a <= th["good"] else "okay" if a <= th["okay"] else "poor"


def trust_map(lat: pd.DataFrame, bulk: pd.DataFrame, therm: pd.DataFrame) -> pd.DataFrame:
    th = config()["thresholds"]
    specs = [
        ("lattice", lat, "err_lin_exp_pct", "experiment"), ("lattice", lat, "err_lin_dft_pct", "dft"),
        ("bulk_modulus", bulk, "err_exp_pct", "experiment"), ("bulk_modulus", bulk, "err_dft_pct", "dft"),
        ("thermal_expansion", therm, "err_exp_pct", "experiment"),
        ("thermal_expansion_300K", therm, "err_300K_pct", "experiment"),
    ]
    rows = []
    for prop, df, col, ref in specs:
        if df.empty or col not in df:
            continue
        if "pending" in df:
            df = df[~df["pending"].astype(bool)]
        for (mk, cls), g in df.groupby(["model", "class"]):
            vals = g[col].dropna().astype(float)
            if vals.empty:
                continue
            mape = float(vals.abs().mean())
            rows.append({"model": mk, "class": cls, "property": prop, "reference": ref, "MAPE": mape,
                         "mean_signed": float(vals.mean()), "n": int(len(vals)),
                         "worst_material": g.loc[g[col].abs().idxmax(), "material"],
                         "grade": grade(mape, th[prop.replace("_300K", "")])})
        for mk, g in df.groupby("model"):
            vals = g[col].dropna().astype(float)
            if not vals.empty:
                rows.append({"model": mk, "class": "all", "property": prop, "reference": ref,
                             "MAPE": float(vals.abs().mean()), "mean_signed": float(vals.mean()), "n": int(len(vals)),
                             "worst_material": g.loc[g[col].abs().idxmax(), "material"],
                             "grade": grade(float(vals.abs().mean()), th[prop.replace("_300K", "")])})
    return pd.DataFrame(rows)


def checks_table(lat, bulk, therm) -> pd.DataFrame:
    rows = []
    for name, df in (("lattice", lat), ("bulk modulus", bulk), ("thermal expansion", therm)):
        for _, r in df.iterrows():
            rows.append({"model": r.model, "material": r.material, "check": f"{name}: fingerprint matches current code",
                         "pass": not (isinstance(r.get("provenance"), str) and r.get("provenance"))})
    for _, r in lat.iterrows():
        rows.append({"model": r.model, "material": r.material, "check": "relaxation converged", "pass": bool(r.converged)})
        rows.append({"model": r.model, "material": r.material, "check": "space group unchanged", "pass": bool(r.symmetry_kept)})
    for _, r in bulk.iterrows():
        rows.append({"model": r.model, "material": r.material, "check": "elastic tensor positive definite",
                     "pass": bool(r.mechanically_stable)})
        rows.append({"model": r.model, "material": r.material, "check": "elastic fit symmetric (<5%)",
                     "pass": bool(r.asymmetry_rel <= 0.05)})
        if r.eos_fit_ok is not None:
            rows.append({"model": r.model, "material": r.material, "check": "Birch-Murnaghan fit clean",
                         "pass": bool(r.eos_fit_ok)})
        if r.eos_vs_elastic_pct is not None and r.material in {m.id for m in load_materials() if m.cubic}:
            rows.append({"model": r.model, "material": r.material, "check": "cubic: EOS B within 5% of elastic K",
                         "pass": abs(r.eos_vs_elastic_pct) < 5})
    for _, r in therm.iterrows():
        for col in [c for c in therm.columns if c.startswith("check_")]:
            if pd.notna(r[col]):
                rows.append({"model": r.model, "material": r.material,
                             "check": f"thermal: {col[6:].replace('_', ' ')}", "pass": bool(r[col])})
    return pd.DataFrame(rows)


MODEL_FAILURES = ("relaxed to a different crystal form", "elastic tensor not positive definite", "dynamically unstable")
METHOD_LIMITS = ("layered", "failed: volume_inside_scan")


def coverage_table(lat: pd.DataFrame, bulk: pd.DataFrame, therm: pd.DataFrame) -> pd.DataFrame:
    """How often each model produced a gradable result, and why the rest were not graded.

    Accuracy averages only cover successful cases, so they are reported next to this:
    a model that changes the crystal form or is dynamically unstable has failed part of
    the workflow even when leaving its number out of the average is the right call.
    """
    specs = [("lattice", lat, "err_lin_exp_pct", "excluded"), ("bulk_modulus", bulk, "err_exp_pct", "excluded"),
             ("thermal_expansion", therm, "err_exp_pct", "excluded"),
             ("thermal_expansion_300K", therm, "err_300K_pct", "excluded_300K")]
    rows = []
    n_mat = len(load_materials())
    for prop, df, col, exc in specs:
        if df.empty or col not in df:
            continue
        for mk, g in df.groupby("model"):
            why = g[exc].fillna("").astype(str) if exc in g else pd.Series("", index=g.index)
            if prop.startswith("thermal") and "excluded" in g:  # window failures also matter at 300 K
                why = why.where(why != "", g["excluded"].fillna("").astype(str).where(
                    g["excluded"].fillna("").astype(str).str.startswith(MODEL_FAILURES), ""))
            graded = g[col].notna()
            fail = why.str.startswith(MODEL_FAILURES) & ~graded
            limit = why.str.startswith(METHOD_LIMITS) & ~graded & ~fail
            rows.append({"model": mk, "property": prop, "materials": n_mat, "computed": int(len(g)),
                         "graded": int(graded.sum()), "model_failure": int(fail.sum()),
                         "method_limit": int(limit.sum()),
                         "no_experimental_reference": int((~graded & ~fail & ~limit & (why == "")).sum()),
                         "pending": bool(g["pending"].any()) if "pending" in g else False,
                         "model_failure_cases": "; ".join(f"{m} ({w.split(' (')[0]})" for m, w in
                                                          zip(g.material[fail], why[fail]))})
    return pd.DataFrame(rows)


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records")) if not df.empty else []


def build_tables(tag: str = "thermal_qha") -> dict:
    OUT.mkdir(exist_ok=True)
    lat, bulk, therm = lattice_table(), bulk_table(), thermal_table(tag)
    lat, bulk, therm = (attach_reference_quality(lat, "lattice"), attach_reference_quality(bulk, "bulk_modulus"),
                        attach_reference_quality(therm, "thermal_expansion"))
    tm = trust_map(lat, bulk, therm)
    chk = checks_table(lat, bulk, therm)
    cov = coverage_table(lat, bulk, therm)
    from chipff.metrics import axial_table, compensation_check, mismatch_summary, thermal_metrics, thermal_mismatch

    tmet = thermal_metrics(therm) if not therm.empty else pd.DataFrame()
    comp = compensation_check(tmet)
    mism = thermal_mismatch(therm) if not therm.empty else pd.DataFrame()
    msum = mismatch_summary(mism)
    axial = axial_table(therm) if not therm.empty else pd.DataFrame()
    from chipff.guidance import guidance_markdown, model_guidance

    guide = model_guidance(lat, bulk, therm, config()["thresholds"], MODEL_FAILURES)
    (ROOT / "docs" / "model_guidance.md").write_text(guidance_markdown(
        guide, {k: m.label.split(" (")[0].split(",")[0] for k, m in MODELS.items()}, CLASS_LABELS))
    for name, df in (("lattice", lat), ("bulk_modulus", bulk), ("thermal_expansion", therm), ("trust_map", tm),
                     ("checks", chk), ("coverage", cov), ("thermal_metrics", tmet), ("thermal_mismatch", mism),
                     ("thermal_mismatch_summary", msum), ("model_guidance", guide),
                     ("thermal_axial", axial)):
        df.to_csv(OUT / f"{name}.csv", index=False, float_format="%.5g")
    summary = {
        "thresholds": config()["thresholds"],
        "models": {k: {"label": m.label, "developer": m.developer, "training_data": m.training_data,
                       "license": m.license, "model_path": m.model_path, "via_kups": m.via_kups}
                   for k, m in MODELS.items()},
        "excluded_models": {k: m.excluded for k, m in _ALL_MODELS.items() if m.excluded},
        "materials": [{"id": m.id, "formula": m.formula, "class": m.cls, "class_label": CLASS_LABELS[m.cls],
                       "phase": m.phase, "spg": m.spg, "role": m.role,
                       "mp_id": (mp_record(m.id) or {}).get("material_id")} for m in load_materials()],
        "lattice": _records(lat), "bulk_modulus": _records(bulk), "thermal_expansion": _records(therm),
        "trust_map": _records(tm), "checks": _records(chk), "coverage": _records(cov),
        "thermal_metrics": _records(tmet), "thermal_mismatch": _records(mism),
        "thermal_mismatch_summary": _records(msum),
        "reference_quality_file": "data/reference_quality.yaml",
        "pending": {"thermal_expansion": sorted(therm.loc[therm["pending"].astype(bool), "model"].unique())
                    if "pending" in therm else []},
    }
    from chipff.robustness import build as build_robustness

    summary["robustness"] = build_robustness(lat, bulk, therm)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(f"wrote results/: {len(lat)} lattice, {len(bulk)} bulk, {len(therm)} thermal rows; "
          f"{int(chk['pass'].sum()) if not chk.empty else 0}/{len(chk)} checks pass")
    return summary
