"""Export the experimental reference dataset as one flat, reusable table.

  python scripts/export_references.py   ->  data/release/chipff_references.csv

One row per reference value: lattice parameters, bulk moduli and linear thermal-expansion coefficients
(per axis), each with its conditions, source, citation, short quote and the quality audit from
data/reference_quality.yaml. See data/release/README.md for the column definitions.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "release" / "chipff_references.csv"
COLS = ["material", "formula", "phase", "class", "mp_id", "property", "axis", "value", "unit", "T_K",
        "tier", "quality", "kind", "rel_sigma_1", "sigma_from", "audit_note", "citation", "source", "quote"]


def main():
    q = yaml.safe_load((ROOT / "data" / "reference_quality.yaml").read_text())
    defaults = q.get("defaults", {})
    by_class = yaml.safe_load((ROOT / "data" / "materials.yaml").read_text())
    mats = {m["id"]: m for ms in by_class.values() if isinstance(ms, list) for m in ms}
    mp = {}
    for p in (ROOT / "data" / "mp").glob("*.json"):
        try:
            mp[p.stem] = json.loads(p.read_text()).get("material_id")
        except (json.JSONDecodeError, AttributeError):
            pass
    rows = []
    for f in sorted((ROOT / "data" / "experimental").glob("*.json")):
        d = json.loads(f.read_text())
        for m in d["materials"]:
            mid = m["id"]
            if mid not in mats:
                continue
            base = {"material": mid, "formula": mats[mid].get("formula"), "phase": m.get("phase"),
                    "class": d.get("class"), "mp_id": mp.get(mid)}

            def audit(prop):
                a = (q.get(mid) or {}).get(prop) or {}
                return {"tier": a.get("tier"), "quality": a.get("quality"), "kind": a.get("kind"),
                        "rel_sigma_1": a.get("sigma", defaults.get(prop)), "sigma_from": a.get("sigma_from", "default"),
                        "audit_note": a.get("why")}

            def src(r):
                return {"citation": r.get("citation"), "source": r.get("source"), "quote": r.get("quote")}

            lat = m.get("lattice") or {}
            for ax in ("a", "b", "c", "beta_deg"):
                if lat.get(ax) is not None:
                    rows.append({**base, "property": "lattice_parameter" if ax != "beta_deg" else "monoclinic_beta",
                                 "axis": ax.replace("_deg", ""), "value": lat[ax],
                                 "unit": "deg" if ax == "beta_deg" else "angstrom", "T_K": lat.get("T_K"),
                                 **audit("lattice"), **src(lat)})
            bm = m.get("bulk_modulus") or {}
            if bm.get("value_GPa") is not None:
                rows.append({**base, "property": "bulk_modulus", "axis": "", "value": bm["value_GPa"], "unit": "GPa",
                             "T_K": bm.get("T_K"), **audit("bulk_modulus"), **src(bm)})
            te = m.get("thermal_expansion") or {}
            for v in te.get("values") or []:
                if v.get("alpha_1e-6_per_K") is None:
                    continue
                t = v.get("T_K") if v.get("T_K") is not None else "-".join(map(str, v.get("T_range_K") or []))
                rows.append({**base, "property": "linear_thermal_expansion", "axis": v.get("axis", "iso"),
                             "value": v["alpha_1e-6_per_K"], "unit": "1e-6 per K", "T_K": t,
                             **audit("thermal_expansion"), **src(te)})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} values for {len({r['material'] for r in rows})} materials")


if __name__ == "__main__":
    main()
