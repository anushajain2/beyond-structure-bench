"""ChipFF Bench as an agent tool (MCP server).

Tools
  recommend_model(material, property, temperature_K=None)
      best model for a benchmarked material (or the nearest material class)
      and its expected error, from the stored benchmark.
  get_benchmark(query)
      stored results for one material or a whole class, with references and sources.
  check_material(cif)
      run the lattice + bulk-modulus checks on a NEW structure with every
      model and report where they disagree (a warning sign that predictions
      for it are unreliable).

Run:  chipff-mcp            (stdio transport; add it to any MCP client)
"""

from __future__ import annotations

import json
import math
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
               "nitride": "barriers_silicides", "silicide": "barriers_silicides", "barrier": "barriers_silicides",
               "semiconductor": "semiconductors", "2d": "layered", "van der waals": "layered", "layered": "layered"}
    for a, k in aliases.items():
        if a in q:
            return k
    return None


def _rows(prop: str):
    return summary()[prop]


def recommend_model(material: str, property: str, temperature_K: float | None = None) -> dict:
    """Recommend the most accurate ML force field for a chip material and property.

    material: a benchmarked material (e.g. "TaN", "HfO2", "GaN") or a class
      ("nitrides", "metals", "dielectrics", "silicides", "layered").
    property: "lattice", "bulk_modulus" or "thermal_expansion".
    temperature_K: optional; for thermal expansion, whether it falls inside the
      benchmarked window is reported.
    """
    prop = PROPS.get(property.strip().lower().replace(" ", "_"))
    if prop is None:
        return {"error": f"property must be one of lattice, bulk_modulus, thermal_expansion (got {property!r})"}
    col = ERR_COL[prop]
    mat = _find_material(material)
    cls = mat.cls if mat else _find_class(material)
    if mat is None and cls is None:
        return {"error": f"{material!r} is not a benchmarked material or class",
                "benchmarked": [m.id for m in load_materials()]}
    rows = [r for r in _rows(prop) if r.get(col) is not None and (r["material"] == mat.id if mat else r["class"] == cls)]
    basis = f"material {mat.id}" if mat else f"class {CLASS_LABELS[cls]}"
    if mat and not rows:  # no experimental comparison for this material: fall back to its class
        rows = [r for r in _rows(prop) if r.get(col) is not None and r["class"] == mat.cls]
        basis = f"class {CLASS_LABELS[mat.cls]} (no experimental reference for {mat.id})"
    if not rows:
        return {"error": f"no benchmark results for {property} in {basis}"}
    by_model: dict[str, list[float]] = {}
    for r in rows:
        by_model.setdefault(r["model"], []).append(r[col])
    ranking = sorted(
        ({"model": k, "label": summary()["models"][k]["label"], "mean_abs_error_pct": sum(map(abs, v)) / len(v),
          "mean_signed_error_pct": sum(v) / len(v), "n_materials": len(v)} for k, v in by_model.items()),
        key=lambda x: x["mean_abs_error_pct"],
    )
    out = {"basis": basis, "property": prop, "reference": "experiment", "recommended": ranking[0], "ranking": ranking,
           "thresholds_pct": summary()["thresholds"][prop]}
    if prop == "thermal_expansion" and temperature_K is not None and mat:
        win = [r for r in rows if r["material"] == mat.id]
        if win:
            lo, hi = win[0]["T_low"], win[0]["T_high"]
            out["temperature_note"] = (
                f"{temperature_K:.0f} K is inside the benchmarked window {lo:.0f}-{hi:.0f} K"
                if lo <= temperature_K <= hi else
                f"{temperature_K:.0f} K is outside the benchmarked window {lo:.0f}-{hi:.0f} K; treat errors as a lower bound"
            )
    if not mat:
        out["caution"] = "class-level average; for a new material, run check_material to see whether models agree"
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

    from chipff.engine import Engine
    from chipff.models import MODELS, get_model
    from chipff.static import symmetry

    atoms = read(io.StringIO(cif), format="cif")
    keys = models or [k for k, m in MODELS.items() if not m.gated]
    res = {}
    for k in keys:
        eng = Engine(get_model(k))
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
    return {"models": res, "lattice_spread_pct": spread_lat, "bulk_modulus_spread_pct": spread_b,
            "warnings": warn or ["models agree within the benchmark's 'okay' thresholds"],
            "note": "B here is a fixed-shape EOS fit (exact for cubic crystals)."}


def main():
    from mcp.server.fastmcp import FastMCP

    app = FastMCP("chipff-bench")
    app.tool()(recommend_model)
    app.tool()(get_benchmark)
    app.tool()(check_material)
    app.run()


if __name__ == "__main__":
    main()
