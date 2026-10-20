"""Figures (report/figures/*.svg|png) and a self-contained report/index.html."""

from __future__ import annotations

import html
import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from chipff.materials import CLASS_LABELS, ROOT  # noqa: E402
from chipff.models import MODELS  # noqa: E402

REPORT = ROOT / "report"
FIG = REPORT / "figures"
MARKERS = {"mace-mpa-0": "o", "orb-v3": "s", "mattersim-5m": "^", "mattersim-5m-native": "^", "uma-s-1p2": "D"}


def short(m: str) -> str:
    """Legend name; models not run through kUPS are starred."""
    return MODELS[m].label.split(" (")[0] + ("*" if not MODELS[m].via_kups else "")
STATUS = {"good": "#0ca30c", "okay": "#fab219", "poor": "#d03b3b"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
PROP_LABEL = {"lattice": "Lattice constant", "bulk_modulus": "Bulk modulus", "thermal_expansion": "Thermal expansion",
              "thermal_expansion_300K": "Thermal exp. at 300 K"}

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
    "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": SURF,
    "axes.facecolor": SURF, "savefig.facecolor": SURF, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
})


def _save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.svg", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def trust_map_figure(s: dict, reference: str = "experiment"):
    tm = [r for r in s["trust_map"] if r["reference"] == reference]
    if not tm:
        return None
    models = [m for m in MODELS if any(r["model"] == m for r in tm)]
    classes = list(CLASS_LABELS)
    props = [p for p in PROP_LABEL if any(r["property"] == p for r in tm)]
    fig, axes = plt.subplots(1, len(props), figsize=(1.15 * len(models) * len(props) + 2.4, 0.5 * len(classes) + 1.6),
                             squeeze=False, gridspec_kw={"wspace": 0.08})
    for ax, p in zip(axes[0], props):
        ax.grid(False)
        for i, c in enumerate(classes):
            for j, m in enumerate(models):
                r = next((x for x in tm if x["model"] == m and x["class"] == c and x["property"] == p), None)
                if r is None:
                    ax.add_patch(plt.Rectangle((j, i), 0.96, 0.92, color="#f0efec"))
                    pending = p.startswith("thermal") and m in s.get("pending", {}).get("thermal_expansion", [])
                    ax.text(j + 0.48, i + 0.46, "pending" if pending else "n/a", ha="center", va="center", color=INK2,
                            fontsize=7.5)
                    continue
                ax.add_patch(plt.Rectangle((j, i), 0.96, 0.92, color=STATUS[r["grade"]], alpha=0.9))
                val = f"{r['MAPE']:.2f}%" if r["MAPE"] < 10 else f"{r['MAPE']:.0f}%"
                ax.text(j + 0.48, i + 0.46, val, ha="center", va="center", fontsize=8,
                        color="white" if r["grade"] != "okay" else INK)
        ax.set_xlim(0, len(models))
        ax.set_ylim(len(classes), 0)
        ax.xaxis.tick_top()
        ax.set_xticks([j + 0.48 for j in range(len(models))], [short(m) for m in models], fontsize=8)
        ax.set_yticks([i + 0.46 for i in range(len(classes))], [CLASS_LABELS[c] for c in classes] if p == props[0] else [])
        ax.set_title(PROP_LABEL[p], color=INK, fontsize=10, loc="left", pad=22)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
    th = s["thresholds"]
    note = "; ".join(f"{PROP_LABEL[p].lower()} good ≤{th[p.replace('_300K', '')]['good']:g}%, okay ≤{th[p.replace('_300K', '')]['okay']:g}%"
                     for p in props if not p.endswith("_300K"))
    star = " *not run through kUPS (official package)." if any(not MODELS[m].via_kups for m in models) else ""
    pend = [short(m) for m in s.get("pending", {}).get("thermal_expansion", [])]
    if pend and any(p.startswith("thermal") for p in props):
        star += f" Thermal expansion for {', '.join(pend)}: run in progress, shown once complete."
    fig.text(0.0, -0.02, f"Mean absolute % error vs {reference}. Green good, amber okay, red poor; thresholds fixed in "
             f"advance ({note}).{star}", fontsize=7.5, color=INK2, wrap=True)
    _save(fig, f"trust_map_{reference}")
    return f"figures/trust_map_{reference}.svg"


def parity_figure(s: dict, prop: str, model_col: str, ref_col: str, label: str, unit: str, log=False, name=None,
                  err_col: str | None = None):
    rows = [r for r in s[prop] if r.get(model_col) is not None and r.get(ref_col) is not None
            and (err_col is None or r.get(err_col) is not None) and not r.get("pending")]
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(4.6, 4.4))
    allv = [r[model_col] for r in rows] + [r[ref_col] for r in rows]
    lo, hi = min(allv), max(allv)
    pad = (hi / lo) ** 0.08 if log and lo > 0 else None
    lim = (lo / pad, hi * pad) if pad else (lo - 0.05 * (hi - lo), hi + 0.05 * (hi - lo))
    ax.plot(lim, lim, color=INK2, lw=1, zorder=1)
    for m in MODELS:
        pts = [(r[ref_col], r[model_col]) for r in rows if r["model"] == m]
        if pts:
            x, y = zip(*pts)
            ax.scatter(x, y, s=34, marker=MARKERS[m], color=MODELS[m].color, edgecolor=SURF, linewidth=1.2,
                       label=short(m), zorder=3)
    if log:
        from matplotlib.ticker import FixedLocator, NullFormatter, ScalarFormatter

        ax.set_xscale("log")
        ax.set_yscale("log")
        ticks = [t for t in (5, 10, 20, 50, 100, 200, 500) if lim[0] <= t <= lim[1]]
        for axis in (ax.xaxis, ax.yaxis):
            axis.set_major_locator(FixedLocator(ticks))
            axis.set_major_formatter(ScalarFormatter())
            axis.set_minor_formatter(NullFormatter())
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel(f"Reference {label} ({unit})")
    ax.set_ylabel(f"Model {label} ({unit})")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _save(fig, name or f"parity_{prop}")
    return f"figures/{name or 'parity_' + prop}.svg"


def signed_error_figure(s: dict, prop: str, col: str, title: str, name: str):
    rows = [r for r in s[prop] if r.get(col) is not None and not r.get("pending")]
    if not rows:
        return None
    classes = [c for c in CLASS_LABELS if any(r["class"] == c for r in rows)]
    fig, ax = plt.subplots(figsize=(7.2, 0.55 * len(classes) + 1.0))
    models = [m for m in MODELS if any(r["model"] == m for r in rows)]
    for i, c in enumerate(classes):
        for j, m in enumerate(models):
            vals = [r[col] for r in rows if r["class"] == c and r["model"] == m]
            y = i + (j - (len(models) - 1) / 2) * 0.16
            ax.scatter(vals, [y] * len(vals), s=22, marker=MARKERS[m], color=MODELS[m].color, edgecolor=SURF,
                       linewidth=0.8, label=short(m) if i == 0 else None, zorder=3)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(range(len(classes)), [CLASS_LABELS[c] for c in classes])
    ax.set_ylim(len(classes) - 0.5, -0.5)
    ax.set_xlabel(f"{title}: signed error (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, fontsize=8, ncol=len(models), loc="lower center", bbox_to_anchor=(0.5, 1.0))
    _save(fig, name)
    return f"figures/{name}.svg"


# -- thermal-failure study (docs/thermal_failure_study.md) ---------------------------------------------
STUDY = ROOT / "results" / "thermal_failure"
STUDY_MODELS = {"mace-kups": "mace-mpa-0", "mattersim-native": "mattersim-5m-native", "orb-kups": "orb-v3"}
STUDY_CASES = ["Si", "GaAs", "InP", "Cu", "Ta", "HfO2"]
# ingredient colours: categorical slots 7, 4, 5, 6 of the validated palette, kept apart from the model colours
INGREDIENTS = [("γ", "r_gamma", +1, "#6250d6"), ("1/K", "r_K", -1, "#eda100"), ("1/V", "r_V", -1, "#e87ba4"),
               ("C_V", "r_Cv", +1, "#008300")]
TA_KPRIME_EXP = 3.07  # Dewaele, Loubeyre & Mezouar, arXiv:cond-mat/0403080 (Vinet fit to DAC data)


def _study_rows(name):
    import csv

    f = STUDY / f"{name}.csv"
    return list(csv.DictReader(open(f))) if f.exists() else []


def study_error_figure():
    """alpha_V(300 K) error per material and model, with the spread across volume-scan choices."""
    phys = [r for r in _study_rows("physics") if r["backend"] in STUDY_MODELS and r.get("variant", "grid") in ("grid", "")]
    conv = _study_rows("convergence")
    if not phys:
        return None
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    for j, (backend, mk) in enumerate(STUDY_MODELS.items()):
        for i, mid in enumerate(STUDY_CASES):
            r = next((x for x in phys if x["backend"] == backend and x["material"] == mid), None)
            if r is None:
                continue
            e = float(r["exp_alpha_V"])
            y = i + (j - 1) * 0.22
            scans = [float(c["alpha300"]) for c in conv if c["backend"] == backend and c["material"] == mid
                     and c["variant"] == "grid" and c["imaginary"] == "clean" and c["alpha300"] not in ("", "nan")]
            if scans:
                ax.plot([(min(scans) / e - 1) * 100, (max(scans) / e - 1) * 100], [y, y], color=MODELS[mk].color,
                        lw=2, alpha=0.45, solid_capstyle="round", zorder=2)
            ax.scatter([(float(r["alpha300_qha"]) / e - 1) * 100], [y], s=40, marker=MARKERS[mk], color=MODELS[mk].color,
                       edgecolor=SURF, linewidth=1, zorder=3, label=short(mk) if i == 0 else None)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(range(len(STUDY_CASES)), [m.replace("HfO2", "HfO₂") for m in STUDY_CASES])
    ax.set_ylim(len(STUDY_CASES) - 0.5, -0.5)
    ax.set_xlabel("α_V(300 K) error vs experiment (%) · bar: spread across volume-scan ranges")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    _save(fig, "study_errors")
    return "figures/study_errors.svg"


def study_ingredient_figure():
    """ln(alpha_model / alpha_exp) split into gamma, 1/K, 1/V, C_V and the reconstruction residual."""
    phys = [r for r in _study_rows("physics") if r["backend"] in STUDY_MODELS and r.get("variant", "grid") in ("grid", "")]
    if not phys:
        return None
    rows = [(mid, b) for mid in STUDY_CASES for b in STUDY_MODELS
            if any(r["backend"] == b and r["material"] == mid for r in phys)]
    fig, ax = plt.subplots(figsize=(7.4, 0.26 * len(rows) + 1.3))
    for y, (mid, b) in enumerate(rows):
        r = next(x for x in phys if x["backend"] == b and x["material"] == mid)
        e = float(r["exp_alpha_V"])
        parts = [(lab, sign * math.log(float(r[col])), c) for lab, col, sign, c in INGREDIENTS]
        recon = math.log(float(r["alpha300_from_gamma"]) / e)
        total = math.log(float(r["alpha300_qha"]) / e)
        parts.append(("residual (full QHA − reconstruction)", total - recon, None))
        pos = neg = 0.0
        for lab, v, c in parts:
            left = pos if v >= 0 else neg + v
            kw = dict(color=c, edgecolor=SURF, linewidth=1) if c else dict(color=SURF, edgecolor=INK2, hatch="////", linewidth=0.6)
            ax.barh(y, abs(v), left=left, height=0.62, label=lab if y == 0 else None, zorder=2, **kw)
            if v >= 0:
                pos += v
            else:
                neg += v
        ax.scatter([total], [y], marker="D", s=22, color=INK, zorder=4, label="full-QHA error" if y == 0 else None)
    ax.axvline(0, color=INK2, lw=1)
    ticks = [0.5, 0.75, 1, 1.5, 2, 3]
    ax.set_xticks([math.log(t) for t in ticks], [f"×{t:g}" for t in ticks])
    ax.set_yticks(range(len(rows)), [f"{m.replace('HfO2', 'HfO₂')} · {short(STUDY_MODELS[b])}" for m, b in rows], fontsize=8)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.set_xlabel("contribution to α_model / α_exp (log scale; segments multiply)")
    ax.grid(axis="y", visible=False)
    h, lab = ax.get_legend_handles_labels()
    order = [lab.index(x) for x in [i[0] for i in INGREDIENTS] + ["residual (full QHA − reconstruction)", "full-QHA error"]]
    ax.legend([h[i] for i in order], [lab[i] for i in order], frameon=False, fontsize=7.5, ncol=3, loc="lower center",
              bbox_to_anchor=(0.5, 1.0))
    _save(fig, "study_ingredients")
    return "figures/study_ingredients.svg"


def study_kprime_figure():
    """Static K' against the phonon Grueneisen parameter for the metals, with the Slater estimate."""
    import csv

    phys = [r for r in _study_rows("physics") if r["backend"] in STUDY_MODELS and r.get("variant", "grid") in ("grid", "")]
    bm = {(r["model"], r["material"]): r for r in csv.DictReader(open(ROOT / "results" / "bulk_modulus.csv"))}
    if not phys:
        return None
    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    k = np.linspace(2.8, 8.2, 50)
    ax.plot(k, k / 2 - 1 / 6, color=INK2, lw=1, ls="--", zorder=1)
    ax.text(7.9, 7.9 / 2 - 1 / 6 + 0.12, "Slater: γ ≈ K′/2 − 1/6", color=INK2, fontsize=7.5, ha="right")
    for mid in ("Ta", "Cu"):
        for b, mk in STUDY_MODELS.items():
            r = next((x for x in phys if x["backend"] == b and x["material"] == mid), None)
            kp = bm.get((mk, mid), {}).get("B_eos_prime")
            if r is None or not kp:
                continue
            x, y = float(kp), float(r["gamma"])
            ax.scatter([x], [y], s=46, marker=MARKERS[mk], color=MODELS[mk].color, edgecolor=SURF, linewidth=1, zorder=3,
                       label=short(mk) if mid == "Ta" else None)
            ax.annotate(mid, (x, y), xytext=(6, -3), textcoords="offset points", fontsize=8, color=INK)
            if mid == "Ta" and b == "orb-kups":
                ax.annotate("Orb, Ta: normal K′,\nγ 40 % above experiment", (x, y), xytext=(22, 48),
                            textcoords="offset points", fontsize=7.5, color=INK2,
                            arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ta_exp = next((float(x["exp_gamma"]) for x in phys if x["material"] == "Ta"), None)
    if ta_exp:
        ax.scatter([TA_KPRIME_EXP], [ta_exp], marker="*", s=90, color=INK, zorder=4, label="Ta, experiment (K′ measured, γ inferred)")
    cu_exp = next((float(x["exp_gamma"]) for x in phys if x["material"] == "Cu"), None)
    if cu_exp:
        ax.axhline(cu_exp, color=INK2, lw=0.8, ls=":", zorder=1)
        ax.text(8.2, cu_exp - 0.13, "Cu, γ inferred from experiment", fontsize=7, color=INK2, ha="right")
    ax.set_xlabel("K′ from the static equation of state")
    ax.set_ylabel("phonon Grüneisen parameter γ (300 K)")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _save(fig, "study_kprime")
    return "figures/study_kprime.svg"


def _table(rows, cols, fmt):
    head = "".join(f"<th>{html.escape(c)}</th>" for c, _ in cols)
    body = []
    for r in rows:
        tds = []
        for _, k in cols:
            v = r.get(k)
            if isinstance(v, float):
                v = "" if math.isnan(v) else fmt.get(k, "{:.2f}").format(v)
            tds.append(f"<td>{html.escape(str(v if v is not None else ''))}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_report():
    s = json.loads((ROOT / "results" / "summary.json").read_text())
    figs = {
        "tm_exp": trust_map_figure(s, "experiment"),
        "tm_dft": trust_map_figure(s, "dft"),
        "lat": parity_figure(s, "lattice", "V_atom", "V_atom_exp", "volume per atom", "Å³", name="parity_lattice_exp",
                            err_col="err_lin_exp_pct"),
        "lat_dft": parity_figure(s, "lattice", "V_atom", "V_atom_dft", "volume per atom", "Å³", name="parity_lattice_dft",
                                 err_col="err_lin_dft_pct"),
        "bulk": parity_figure(s, "bulk_modulus", "K_for_exp", "B_exp", "bulk modulus", "GPa", log=True,
                              name="parity_bulk_exp", err_col="err_exp_pct"),
        "bulk_dft": parity_figure(s, "bulk_modulus", "K_vrh", "K_vrh_dft", "bulk modulus", "GPa", log=True,
                                  name="parity_bulk_dft", err_col="err_dft_pct"),
        "cte": parity_figure(s, "thermal_expansion", "alpha_V", "alpha_V_exp", "α_V", "10⁻⁶/K", name="parity_cte_exp",
                            err_col="err_exp_pct"),
        "lat_err": signed_error_figure(s, "lattice", "err_lin_exp_pct", "Lattice vs experiment", "signed_lattice_exp"),
        "bulk_err": signed_error_figure(s, "bulk_modulus", "err_exp_pct", "Bulk modulus vs experiment", "signed_bulk_exp"),
        "cte_err": signed_error_figure(s, "thermal_expansion", "err_exp_pct", "Thermal expansion vs experiment",
                                       "signed_cte_exp"),
    }
    study = {"errors": study_error_figure(), "ingredients": study_ingredient_figure(), "kprime": study_kprime_figure()}
    sections = []
    if any(study.values()):
        sections.append(
            "<h2>Why thermal expansion fails: six-case study</h2><p>Si, GaAs, InP, Cu, Ta and HfO₂ for MACE-MPA-0, "
            "MatterSim v1* and Orb v3, at 300 K with the Γ-mode fix. The full analysis, its checks and its limits are in "
            "<a href='../docs/thermal_failure_study.md'>docs/thermal_failure_study.md</a>; the numbers are in "
            "<code>results/thermal_failure/</code>. Orb's benchmark-wide thermal expansion is not computed in this "
            "release, so Orb appears here only.</p>"
            + "".join(f"<img src='{v}' alt='{a}'>" for v, a in (
                (study["errors"], "Thermal-expansion error by material and model"),
                (study["ingredients"], "Ingredients of the thermal-expansion error"),
                (study["kprime"], "Static K-prime against the phonon Grüneisen parameter")) if v))
    for key, title in (("tm_exp", "Trust map vs experiment"), ("tm_dft", "Trust map vs DFT (Materials Project PBE)"),
                       ("lat", "Lattice: model vs experiment"), ("lat_err", "Lattice errors by class"),
                       ("bulk", "Bulk modulus: model vs experiment"), ("bulk_err", "Bulk modulus errors by class"),
                       ("cte", "Thermal expansion: model vs experiment"), ("cte_err", "Thermal expansion errors by class")):
        if figs.get(key):
            sections.append(f"<h2>{title}</h2><img src='{figs[key]}' alt='{title}'>")
    lat_cols = [("Model", "model"), ("Material", "material"), ("V/atom", "V_atom"), ("V/atom DFT", "V_atom_dft"),
                ("V/atom exp", "V_atom_exp"), ("err vs DFT %", "err_lin_dft_pct"), ("err vs exp %", "err_lin_exp_pct")]
    b_cols = [("Model", "model"), ("Material", "material"), ("K_VRH", "K_vrh"), ("K_Reuss", "K_reuss"),
              ("B (EOS)", "B_eos"), ("K_VRH DFT", "K_vrh_dft"), ("B exp", "B_exp"), ("err vs DFT %", "err_dft_pct"),
              ("err vs exp %", "err_exp_pct")]
    t_cols = [("Model", "model"), ("Material", "material"), ("T low", "T_low"), ("T high", "T_high"),
              ("α_V", "alpha_V"), ("±", "alpha_V_err"), ("α_V exp", "alpha_V_exp"), ("err %", "err_exp_pct")]
    fmt = {"T_low": "{:.0f}", "T_high": "{:.0f}"}
    sections += [
        "<h2>Lattice data (Å³ per atom; error is the effective linear error)</h2>" + _table(s["lattice"], lat_cols, fmt),
        "<h2>Bulk modulus data (GPa)</h2>" + _table(s["bulk_modulus"], b_cols, fmt),
        "<h2>Thermal expansion data (volumetric, 10⁻⁶/K)</h2>" + _table(s["thermal_expansion"], t_cols, fmt),
    ]
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ChipFF Bench results</title><style>
body{{font:15px/1.5 system-ui,sans-serif;max-width:1000px;margin:0 auto;padding:16px;color:#0b0b0b;background:#fcfcfb}}
img{{max-width:100%;height:auto}} table{{border-collapse:collapse;font-size:12px;width:100%;margin:8px 0 24px}}
td,th{{border-bottom:1px solid #e6e5e1;padding:3px 6px;text-align:right}} td:nth-child(-n+2),th:nth-child(-n+2){{text-align:left}}
h2{{margin-top:32px;font-size:18px}} .wrap{{overflow-x:auto}}</style></head><body>
<h1>ChipFF Bench: results</h1>
<p>Generated by <code>chipff report</code> from <code>results/summary.json</code>. See README.md for method and limits.</p>
{''.join(f"<div class='wrap'>{x}</div>" for x in sections)}
</body></html>"""
    REPORT.mkdir(exist_ok=True)
    (REPORT / "index.html").write_text(page)
    n = sum(1 for v in list(figs.values()) + list(study.values()) if v)
    print(f"wrote report/index.html and {n} figures")
