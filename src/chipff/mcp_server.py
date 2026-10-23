"""ChipFF Bench as an agent tool (MCP server).

Tools
  recommend_model(material, property, temperature_K=None)
      models ranked by their measured errors for a benchmarked material (or its
      class), with the evidence behind the ranking and whether it is resolved.
  get_benchmark(query)
      stored results for one material or a whole class, with references and sources.
  check_material(cif)
      run the lattice + bulk-modulus checks on a NEW structure with every
      model and report where they disagree (an exploratory warning signal that
      predictions for it may be unreliable).

Run:  chipff-mcp            (stdio transport; add it to any MCP client)
"""

from __future__ import annotations

import json
from functools import lru_cache

from chipff.materials import CLASS_LABELS, ROOT, load_materials

PROPS = {"lattice": "lattice", "lattice_constant": "lattice", "bulk_modulus": "bulk_modulus",
         "stiffness": "bulk_modulus", "thermal_expansion": "thermal_expansion", "cte": "thermal_expansion"}
ERR_COL = {"lattice": "err_lin_exp_pct", "bulk_modulus": "err_exp_pct", "thermal_expansion": "err_exp_pct"}
DFT_COL = {"lattice": "err_lin_dft_pct", "bulk_modulus": "err_dft_pct"}


@lru_cache
def summary() -> dict:
    p = ROOT / "results" / "summary.json"
    if not p.exists():
        raise FileNotFoundError("results/summary.json missing: run `chipff analyze` first")
    return json.loads(p.read_text())


def _find_material(name: str):
    q = name.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    for m in load_materials():
        keys = {m.id.lower().replace("_", ""), m.formula.lower()}
        if q in keys:
            return m
    return None


def _find_class(name: str):
    q = name.strip().lower()
    for k, v in CLASS_LABELS.items():
        if q in (k, v.lower()) or q.rstrip("s") in k:
            return k
    aliases = {"metal": "metals", "oxide": "dielectrics", "dielectric": "dielectrics", "insulator": "dielectrics",
               "silicide": "barriers_silicides", "barrier": "barriers_silicides",
               "semiconductor": "semiconductors", "2d": "layered", "van der waals": "layered", "layered": "layered"}
    for a, k in aliases.items():
        if a in q:
            return k
    return None


def _rows(prop: str):
    return summary()[prop]


def _pairwise_note(prop_key: str, a: str, b: str, cls: str | None) -> str | None:
    """What the paired bootstrap says about the top two models (results/robustness)."""
    rob = summary().get("robustness", {})
    rows = rob.get("pairwise_by_class", []) if cls else rob.get("pairwise", [])
    for r in rows:
        if (r.get("subset", "all") == "all" and r["property"] == prop_key and r["reference"] == "experiment"
                and {r["model_a"], r["model_b"]} == {a, b}
                and (cls is None or r.get("class") == cls)):
            lo, hi = r["ci_low"], r["ci_high"]
            if lo < 0 < hi:
                return (f"the benchmark does not resolve a difference between {a} and {b} "
                        f"(95% interval of {r['model_a']} minus {r['model_b']}: {lo:+.2f} to {hi:+.2f} points, "
                        f"{r['n_common']} shared materials)")
            return f"paired bootstrap: {r['verdict']} ({r['n_common']} shared materials)"
    return None


def recommend_model(material: str, property: str, temperature_K: float | None = None) -> dict:
    """Rank the ML force fields by their measured ChipFF Bench errors for a material or class.

    This retrieves benchmark evidence; it is not a calibrated prediction of the error for
    another material. Each ranking entry lists the per-material errors it averages.

    material: a benchmarked material (e.g. "TaN", "HfO2", "GaN") or a class
      ("nitrides", "metals", "dielectrics", "silicides", "layered").
    property: "lattice", "bulk_modulus" or "thermal_expansion".
    temperature_K: optional, thermal expansion only. Near 300 K (250-350 K) the 300 K
      comparison is used; otherwise the pre-registered temperature-window comparison.
      Outside both, the answer says the benchmark has no evidence at that temperature.
    """
    prop = PROPS.get(property.strip().lower().replace(" ", "_"))
    if prop is None:
        return {"error": f"property must be one of lattice, bulk_modulus, thermal_expansion (got {property!r})"}
    col, prop_key, comparison = ERR_COL[prop], prop, None
    if prop == "thermal_expansion":
        comparison = "temperature window (pre-registered)"
        if temperature_K is not None and abs(temperature_K - 300.0) <= 50:
            col, prop_key, comparison = "err_300K_pct", "thermal_expansion_300K", "300 K"
    mat = _find_material(material)
    cls = mat.cls if mat else _find_class(material)
    if mat is None and cls is None:
        return {"error": f"{material!r} is not a benchmarked material or class",
                "benchmarked": [m.id for m in load_materials()]}
    if not _rows(prop):
        return {"error": f"no {prop.replace('_', ' ')} results in this benchmark yet"}
    # models whose run is still in progress are not ranked (results/summary.json "pending")
    pending = set(summary().get("pending", {}).get(prop, []))
    rows = [r for r in _rows(prop) if r.get(col) is not None and r["model"] not in pending
            and (r["material"] == mat.id if mat else r["class"] == cls)]
    basis = f"material {mat.id}" if mat else f"class {CLASS_LABELS[cls]}"
    used_cls = None if mat else cls
    if mat and not rows:  # no experimental comparison for this material: fall back to its class
        rows = [r for r in _rows(prop) if r.get(col) is not None and r["model"] not in pending
                and r["class"] == mat.cls]
        basis = f"class {CLASS_LABELS[mat.cls]} (no usable experimental comparison for {mat.id})"
        used_cls = mat.cls
    if not rows:
        return {"error": f"no benchmark results for {property} in {basis}"}
    by_model: dict[str, list[dict]] = {}
    for r in rows:
        by_model.setdefault(r["model"], []).append(r)
    ranking = sorted(
        ({"model": k, "label": summary()["models"][k]["label"],
          "mean_abs_error_pct": sum(abs(x[col]) for x in v) / len(v),
          "mean_signed_error_pct": sum(x[col] for x in v) / len(v), "n_materials": len(v),
          "errors_pct": {x["material"]: round(x[col], 2) for x in v}} for k, v in by_model.items()),
        key=lambda x: x["mean_abs_error_pct"],
    )
    out = {"basis": basis, "property": prop, "reference": "experiment", "lowest_error": ranking[0],
           "ranking": ranking, "thresholds_pct": summary()["thresholds"][prop],
           "caution": ("benchmark evidence on the materials listed, not a calibrated error estimate for "
                       "other materials or conditions")}
    if comparison:
        out["comparison"] = comparison
    if len(ranking) > 1:
        if mat and basis.startswith("material"):
            out["statistical_note"] = (f"single material: these are its measured errors; the benchmark-wide "
                                       f"comparison: {_pairwise_note(prop_key, ranking[0]['model'], ranking[1]['model'], None) or 'n/a'}")
        else:
            note = _pairwise_note(prop_key, ranking[0]["model"], ranking[1]["model"], used_cls)
            if note:
                out["statistical_note"] = note
    if pending:
        out["pending"] = f"not yet ranked (run in progress): {', '.join(sorted(pending))}"
    if prop == "thermal_expansion" and temperature_K is not None and comparison != "300 K":
        win = [r for r in rows if mat and r["material"] == mat.id]
        if win:
            lo, hi = win[0]["T_low"], win[0]["T_high"]
            out["temperature_note"] = (
                f"{temperature_K:.0f} K is inside the benchmarked window {lo:.0f}-{hi:.0f} K"
                if lo <= temperature_K <= hi else
                f"the benchmark has no evidence at {temperature_K:.0f} K: it compares at 300 K and over "
                f"{lo:.0f}-{hi:.0f} K only; errors elsewhere may be larger or smaller")
        else:
            out["temperature_note"] = (f"the windows differ by material; check each material's window "
                                       f"(get_benchmark) before relying on this at {temperature_K:.0f} K")
    if not mat:
        out["caution"] += "; for a new material, run check_material to see whether models agree"
    return out


def get_benchmark(query: str) -> dict:
    """Stored ChipFF Bench results for one material (e.g. "Ru") or a class (e.g. "metals"),
    with model values, DFT and experimental references, errors and sources."""
    mat = _find_material(query)
    cls = None if mat else _find_class(query)
    if mat is None and cls is None:
        return {"error": f"{query!r} not found", "materials": [m.id for m in load_materials()],
                "classes": list(CLASS_LABELS)}
    keep = (lambda r: r["material"] == mat.id) if mat else (lambda r: r["class"] == cls)
    s = summary()
    out = {p: [r for r in s[p] if keep(r)] for p in ("lattice", "bulk_modulus", "thermal_expansion")}
    if cls:
        out["trust_map"] = [r for r in s["trust_map"] if r["class"] == cls]
    out["thresholds_pct"] = s["thresholds"]
    return out


def check_material(cif: str, models: list[str] | None = None) -> dict:
    """Relax a new crystal (CIF text) with every model and compare lattice and bulk modulus.

    Large disagreement between models is a warning sign. Runs on CPU in about
    a minute per model for small cells.
    """
    import io

    from ase.io import read

    from chipff.models import MODELS
    from chipff.runner import make_engine
    from chipff.static import symmetry

    atoms = read(io.StringIO(cif), format="cif")
    keys = models or [k for k, m in MODELS.items() if not m.gated and not m.excluded]
    res, skipped = {}, {}
    for k in keys:
        if k not in MODELS:
            skipped[k] = "unknown model"
            continue
        if MODELS[k].excluded:
            skipped[k] = "excluded from the benchmark: " + MODELS[k].excluded
            continue
        try:  # each model on its own backend (kUPS, or its official package for MatterSim)
            eng = make_engine(k)
        except ImportError as e:
            skipped[k] = f"backend not installed here ({e.name}); see the README's Reproduce section"
            continue
        r = eng.relax([atoms], optimize_cell=True)[0]
        scales = [0.97, 0.985, 1.0, 1.015, 1.03]
        structs = []
        for s in scales:
            a = r.atoms.copy()
            a.set_cell(a.cell * s ** (1 / 3), scale_atoms=True)
            structs.append(a)
        rel = eng.relax(structs, optimize_cell=False)
        from pymatgen.analysis.eos import EOS

        n = len(atoms)
        fit = EOS("birch_murnaghan").fit([a.get_volume() / n for a in structs], [x.energy / n for x in rel])
        sym = symmetry(r.atoms)
        res[k] = {"volume_per_atom": sym["volume_per_atom"], "lattice": sym["conventional"],
                  "space_group": sym["symbol"], "B_eos_GPa": float(fit.b0_GPa), "converged": r.converged}
    if len(res) < 2:
        return {"models": res, "skipped": skipped,
                "error": "fewer than two models ran, so there is no disagreement to measure"}
    vols = [v["volume_per_atom"] for v in res.values()]
    bs = [v["B_eos_GPa"] for v in res.values()]
    spread_lat = 100 * ((max(vols) / min(vols)) ** (1 / 3) - 1)
    spread_b = 100 * (max(bs) / min(bs) - 1)
    th = summary()["thresholds"] if (ROOT / "results" / "summary.json").exists() else {
        "lattice": {"okay": 3.0}, "bulk_modulus": {"okay": 25.0}}
    warn = []
    if spread_lat > th["lattice"]["okay"]:
        warn.append(f"models disagree on lattice size by {spread_lat:.1f}%")
    if spread_b > th["bulk_modulus"]["okay"]:
        warn.append(f"models disagree on stiffness by {spread_b:.0f}%")
    if len({v["space_group"] for v in res.values()}) > 1:
        warn.append("models relax to different space groups")
    return {"models": res, "skipped": skipped, "lattice_spread_pct": spread_lat, "bulk_modulus_spread_pct": spread_b,
            "warnings": warn or ["models agree within the benchmark's 'okay' thresholds"],
            "note": ("B here is a fixed-shape EOS fit (exact for cubic crystals). Disagreement is an exploratory "
                     "warning signal: agreement does not show that the models are right, since they share "
                     "training data and its errors.")}


def main():
    try:  # mcp >= 2
        from mcp.server.mcpserver import MCPServer as Server
    except ImportError:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP as Server

    app = Server("chipff-bench")
    app.tool()(recommend_model)
    app.tool()(get_benchmark)
    app.tool()(check_material)
    app.run()


if __name__ == "__main__":
    main()
