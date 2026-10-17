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
MARKERS = {"mace-mpa-0": "o", "orb-v3": "s", "mattersim-5m": "^", "uma-s-1p2": "D"}
STATUS = {"good": "#0ca30c", "okay": "#fab219", "poor": "#d03b3b"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
PROP_LABEL = {"lattice": "Lattice constant", "bulk_modulus": "Bulk modulus", "thermal_expansion": "Thermal expansion"}

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
    fig, axes = plt.subplots(1, len(props), figsize=(3.3 * len(props), 0.42 * len(classes) + 1.2), squeeze=False)
    for ax, p in zip(axes[0], props):
        ax.grid(False)
        for i, c in enumerate(classes):
            for j, m in enumerate(models):
                r = next((x for x in tm if x["model"] == m and x["class"] == c and x["property"] == p), None)
                if r is None:
                    ax.add_patch(plt.Rectangle((j, i), 0.96, 0.92, color="#f0efec"))
                    ax.text(j + 0.48, i + 0.46, "n/a", ha="center", va="center", color=INK2, fontsize=7)
                    continue
                ax.add_patch(plt.Rectangle((j, i), 0.96, 0.92, color=STATUS[r["grade"]], alpha=0.9))
                ax.text(j + 0.48, i + 0.46, f"{r['MAPE']:.1f}%", ha="center", va="center", fontsize=7.5,
                        color="white" if r["grade"] != "okay" else INK)
        ax.set_xlim(0, len(models))
        ax.set_ylim(len(classes), 0)
        ax.set_xticks([j + 0.48 for j in range(len(models))], [MODELS[m].label.split(" (")[0] for m in models],
                      rotation=30, ha="right")
        ax.set_yticks([i + 0.46 for i in range(len(classes))], [CLASS_LABELS[c] for c in classes] if p == props[0] else [])
        ax.set_title(PROP_LABEL[p], color=INK, fontsize=10, loc="left")
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
    th = s["thresholds"]
    note = "  ·  ".join(f"{PROP_LABEL[p]}: good ≤{th[p]['good']:g}%, okay ≤{th[p]['okay']:g}%" for p in props)
    fig.text(0.0, -0.04, f"Mean absolute % error vs {reference}. Green good, amber okay, red poor (pre-registered: {note}).",
             fontsize=7.5, color=INK2)
    _save(fig, f"trust_map_{reference}")
    return f"figures/trust_map_{reference}.svg"


def parity_figure(s: dict, prop: str, model_col: str, ref_col: str, label: str, unit: str, log=False, name=None):
    rows = [r for r in s[prop] if r.get(model_col) is not None and r.get(ref_col) is not None]
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
                       label=MODELS[m].label.split(" (")[0], zorder=3)
    if log:
        ax.set_xscale("log")
        ax.set_yscale("log")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel(f"Reference {label} ({unit})")
    ax.set_ylabel(f"Model {label} ({unit})")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _save(fig, name or f"parity_{prop}")
    return f"figures/{name or 'parity_' + prop}.svg"


def signed_error_figure(s: dict, prop: str, col: str, title: str, name: str):
    rows = [r for r in s[prop] if r.get(col) is not None]
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
                       linewidth=0.8, label=MODELS[m].label.split(" (")[0] if i == 0 else None, zorder=3)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(range(len(classes)), [CLASS_LABELS[c] for c in classes])
    ax.set_ylim(len(classes) - 0.5, -0.5)
    ax.set_xlabel(f"{title}: signed error (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, fontsize=8, ncol=len(models), loc="lower center", bbox_to_anchor=(0.5, 1.0))
    _save(fig, name)
    return f"figures/{name}.svg"


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
        "lat": parity_figure(s, "lattice", "V_atom", "V_atom_exp", "volume per atom", "Å³", name="parity_lattice_exp"),
        "lat_dft": parity_figure(s, "lattice", "V_atom", "V_atom_dft", "volume per atom", "Å³", name="parity_lattice_dft"),
        "bulk": parity_figure(s, "bulk_modulus", "K_vrh", "B_exp", "bulk modulus", "GPa", log=True, name="parity_bulk_exp"),
        "bulk_dft": parity_figure(s, "bulk_modulus", "K_vrh", "K_vrh_dft", "bulk modulus", "GPa", log=True,
                                  name="parity_bulk_dft"),
        "cte": parity_figure(s, "thermal_expansion", "alpha_V", "alpha_V_exp", "α_V", "10⁻⁶/K", name="parity_cte_exp"),
        "lat_err": signed_error_figure(s, "lattice", "err_lin_exp_pct", "Lattice vs experiment", "signed_lattice_exp"),
        "bulk_err": signed_error_figure(s, "bulk_modulus", "err_exp_pct", "Bulk modulus vs experiment", "signed_bulk_exp"),
        "cte_err": signed_error_figure(s, "thermal_expansion", "err_exp_pct", "Thermal expansion vs experiment",
                                       "signed_cte_exp"),
    }
    sections = []
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
    print(f"wrote report/index.html and {sum(1 for v in figs.values() if v)} figures")
