"""One-off: stamp static results computed before fingerprinting existed (see docs/provenance.md)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from chipff.provenance import fingerprint  # noqa: E402

NOTE = "backfilled 2026-10-18: computed before stamping; step code verified behaviour-identical (docs/provenance.md)"
EXCLUDED = {"mattersim-5m"}  # broken export: results kept only as bug evidence, never stamped
for step in ("lattice", "elastic", "eos"):     # lattice first: elastic/EOS input hashes read it
    for p in sorted((ROOT / "results" / "raw").glob(f"*/{step}.json")):
        d = json.loads(p.read_text())
        if d["model"] in EXCLUDED:
            continue
        n = 0
        for r in d["results"]:
            if "provenance" not in r:
                r["provenance"] = fingerprint(step, d["model"], r["material"], stamped=NOTE)
                n += 1
        p.write_text(json.dumps(d, indent=1))
        print(f"{p.relative_to(ROOT)}: stamped {n}")
