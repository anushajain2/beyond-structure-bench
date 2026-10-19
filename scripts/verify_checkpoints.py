"""Check that the model files on this machine are the ones the published results used.

The model paths in src/chipff/models.py point at mutable downloads (a Hugging Face repo's
latest revision, a package's default checkpoint). configs/checkpoints.json records the
revision and SHA-256 of each file the results were computed with; this script recomputes
the hashes of the local copies and reports any mismatch.

  python scripts/verify_checkpoints.py            # verify
  python scripts/verify_checkpoints.py --record   # rewrite configs/checkpoints.json from local files
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "configs" / "checkpoints.json"
HF = Path.home() / ".cache" / "huggingface" / "hub"

# model key -> where the file lives locally
SOURCES = {
    "mace-mpa-0": {"hf_repo": "CuspAI/kUPS-mace-jax", "file": "mace-mpa-0-medium_32.zip"},
    "orb-v3": {"hf_repo": "CuspAI/kUPS-orb-jax", "file": "orb_v3_conservative_inf_omat.zip"},
    "mattersim-5m": {"hf_repo": "CuspAI/kUPS-mattersim-jax", "file": "mattersim-v1.0.0-5m.zip"},
    "mattersim-5m-native": {"path": "~/.local/mattersim/pretrained_models/mattersim-v1.0.0-5M.pth",
                            "package": "mattersim"},
    "uma-s-1p2": {"hf_repo": "facebook/UMA", "file": "checkpoints/uma-s-1p2.pt"},
}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def locate(src: dict) -> tuple[Path | None, str | None]:
    if "path" in src:
        p = Path(src["path"]).expanduser()
        return (p if p.exists() else None), None
    d = HF / ("models--" + src["hf_repo"].replace("/", "--"))
    ref = d / "refs" / "main"
    if not ref.exists():
        return None, None
    rev = ref.read_text().strip()
    p = d / "snapshots" / rev / src["file"]
    return (p if p.exists() else None), rev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args()
    old = json.loads(RECORD.read_text()) if RECORD.exists() else {}
    new, bad = {}, 0
    for key, src in SOURCES.items():
        p, rev = locate(src)
        if p is None:
            print(f"{key:22s} not downloaded here")
            if key in old:
                new[key] = old[key]
            continue
        entry = {**src, "revision": rev, "sha256": _sha256(p), "bytes": p.stat().st_size}
        new[key] = entry
        ref = old.get(key)
        status = ("recorded" if a.record else "no record" if not ref else
                  "ok" if ref["sha256"] == entry["sha256"] else "MISMATCH")
        bad += status == "MISMATCH"
        print(f"{key:22s} {status:9s} rev {str(rev)[:12]:12s} sha256 {entry['sha256'][:16]}")
    if a.record:
        RECORD.write_text(json.dumps(new, indent=1) + "\n")
        print(f"wrote {RECORD.relative_to(ROOT)}")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
