"""Download structures and DFT reference values from Materials Project.

For each material in data/materials.yaml this writes data/mp/<id>.json with:
  - the Materials Project ID used, and why (hint matched, or lowest-energy match)
  - the PBE (GGA/GGA+U) relaxed structure, which is also the starting structure
  - PBE lattice parameters and volume per atom (the DFT lattice reference)
  - the PBE elastic tensor and Voigt-Reuss-Hill bulk modulus, when MP has one

Needs MP_API_KEY in the environment or in a .env file at the repo root.
Run:  python scripts/fetch_mp.py            (skips materials already fetched)
      python scripts/fetch_mp.py --force    (re-download everything)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chipff.materials import load_materials  # noqa: E402

OUT = ROOT / "data" / "mp"
# alpha-quartz is enantiomorphic: either hand (P3_121 = 152, P3_221 = 154) is the same material
SPG_EQUIV = {154: {152, 154}, 152: {152, 154}}


def _api_key() -> str:
    key = os.environ.get("MP_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("MP_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("MP_API_KEY not set. Copy .env.example to .env and add your Materials Project key.")
    return key


def pick(mpr, mat):
    from pymatgen.core import Composition

    allowed = SPG_EQUIV.get(mat.spg, {mat.spg})
    docs = mpr.materials.summary.search(
        formula=Composition(mat.formula).reduced_formula,
        fields=["material_id", "symmetry", "energy_above_hull", "nsites", "deprecated", "theoretical"],
    )
    docs = [d for d in docs if d.symmetry.number in allowed and not d.deprecated]
    if not docs:
        raise RuntimeError(f"{mat.id}: no Materials Project entry with space group {mat.spg}")
    by_id = {str(d.material_id): d for d in docs}
    if mat.mp_hint and mat.mp_hint in by_id:
        return by_id[mat.mp_hint], "hint matched formula and space group"
    best = min(docs, key=lambda d: (d.energy_above_hull if d.energy_above_hull is not None else 9e9, d.nsites))
    why = "lowest energy above hull with this formula and space group"
    if mat.mp_hint:
        why += f" (hint {mat.mp_hint} did not match)"
    return best, why


def fetch_one(mpr, mat) -> dict:
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    doc, why = pick(mpr, mat)
    mid = str(doc.material_id)
    entry = mpr.get_entry_by_material_id(
        mid, compatible_only=False, conventional_unit_cell=False,
        additional_criteria={"thermo_types": ["GGA_GGA+U"]},
    )
    entry = entry[0] if isinstance(entry, list) else entry
    s = entry.structure
    conv = SpacegroupAnalyzer(s, symprec=0.01).get_conventional_standard_structure()
    lat = conv.lattice
    rec = {
        "id": mat.id,
        "formula": mat.formula,
        "material_id": mid,
        "selection": why,
        "functional": "PBE (GGA/GGA+U), Materials Project",
        "space_group": SpacegroupAnalyzer(s, symprec=0.01).get_space_group_symbol(),
        "space_group_number": SpacegroupAnalyzer(s, symprec=0.01).get_space_group_number(),
        "energy_above_hull_eV": doc.energy_above_hull,
        "structure": s.as_dict(),
        "dft_lattice": {
            "a": lat.a, "b": lat.b, "c": lat.c,
            "alpha": lat.alpha, "beta": lat.beta, "gamma": lat.gamma,
            "volume_per_atom": s.volume / len(s),
        },
        "dft_elastic": None,
        "fetched": date.today().isoformat(),
        "url": f"https://next-gen.materialsproject.org/materials/{mid}",
    }
    el = mpr.materials.elasticity.search(material_ids=[mid])
    if el:
        e = el[0]
        bm = getattr(e, "bulk_modulus", None)
        sm = getattr(e, "shear_modulus", None)
        tensor = getattr(e, "elastic_tensor", None)
        rec["dft_elastic"] = {
            "K_vrh_GPa": getattr(bm, "vrh", None) if bm else None,
            "K_voigt_GPa": getattr(bm, "voigt", None) if bm else None,
            "K_reuss_GPa": getattr(bm, "reuss", None) if bm else None,
            "G_vrh_GPa": getattr(sm, "vrh", None) if sm else None,
            "C_ieee_GPa": (getattr(tensor, "ieee_format", None) if tensor else None),
            "state": str(getattr(e, "state", "")),
        }
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    from mp_api.client import MPRester

    OUT.mkdir(parents=True, exist_ok=True)
    mats = load_materials()
    with MPRester(_api_key(), mute_progress_bars=True) as mpr:
        for mat in mats:
            if args.only and mat.id not in args.only:
                continue
            path = OUT / f"{mat.id}.json"
            if path.exists() and not args.force:
                continue
            rec = fetch_one(mpr, mat)
            path.write_text(json.dumps(rec, indent=1, default=str))
            el = rec["dft_elastic"] or {}
            print(f"{mat.id:12s} {rec['material_id']:10s} {rec['space_group']:10s} "
                  f"V/atom={rec['dft_lattice']['volume_per_atom']:.3f}  K_vrh={el.get('K_vrh_GPa')}  ({rec['selection']})")


if __name__ == "__main__":
    main()
