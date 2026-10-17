"""Recompute moduli in results/raw/*/elastic.json from the stored stiffness matrices
(no simulation): used when the moduli definition changes."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from chipff.static import elastic_moduli  # noqa: E402

for p in sorted((ROOT / "results" / "raw").glob("*/elastic.json")):
    d = json.loads(p.read_text())
    for r in d["results"]:
        r.update(elastic_moduli(r["C_voigt_GPa"]))
    p.write_text(json.dumps(d, indent=1))
    print("updated", p.relative_to(ROOT))
