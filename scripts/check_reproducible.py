"""Check that the published numbers can be reproduced, so a code or dependency change cannot shift them silently.

    python scripts/check_reproducible.py --tables      # after `chipff analyze`: tables equal the committed ones
    python scripts/check_reproducible.py --recompute   # rerun MACE-MPA-0 on Si (lattice + EOS) and compare

--tables compares every results/*.csv (and results/robustness/*.csv) in the working tree with the version committed
at HEAD: same rows and columns, text equal, numbers within a relative 2e-4 (the tables are written with 5
significant digits, so another platform may round the last one differently).

--recompute reruns one cheap, already-published result through the real model (MACE-MPA-0 via kUPS: Si lattice
constant and equation of state, a few minutes on a CPU). It checks the recomputed record's code, settings and inputs
fingerprints equal the committed ones, its numbers agree within the tolerances below, and the downloaded model file
matches configs/checkpoints.json. The committed raw files are restored afterwards.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# relative tolerances for the recomputed Si record (CPU / XLA builds differ in the last few digits)
TOL = {"a": 2e-4, "volume_per_atom": 6e-4, "energy_per_atom": 1e-4, "B0_GPa": 5e-3, "B0_prime": 3e-2, "V0_per_atom": 6e-4}


def _committed(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def check_tables() -> list[str]:
    bad = []
    files = sorted((ROOT / "results").glob("*.csv")) + sorted((ROOT / "results" / "robustness").glob("*.csv"))
    for p in files:
        try:
            text = _committed(p)
        except subprocess.CalledProcessError:
            continue  # not committed yet
        name = p.relative_to(ROOT).as_posix()
        if not text.strip() or not p.read_text().strip():
            if text.strip() != p.read_text().strip():
                bad.append(f"{name}: one version is empty")
            continue
        ref, now = pd.read_csv(io.StringIO(text)), pd.read_csv(p)
        if ref.shape != now.shape or list(ref.columns) != list(now.columns):
            bad.append(f"{name}: shape or columns differ ({ref.shape} vs {now.shape})")
            continue
        for c in ref.columns:
            a, b = ref[c], now[c]
            if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
                if not np.allclose(a.to_numpy(float), b.to_numpy(float), rtol=2e-4, atol=1e-9, equal_nan=True):
                    i = int(np.argmax(~np.isclose(a.to_numpy(float), b.to_numpy(float), rtol=2e-4, atol=1e-9, equal_nan=True)))
                    bad.append(f"{name}: column {c!r} differs (row {i}: {a.iloc[i]} vs {b.iloc[i]})")
            elif not a.fillna("").astype(str).equals(b.fillna("").astype(str)):
                bad.append(f"{name}: column {c!r} differs")
    print(f"tables: {len(files)} files checked, {len(bad)} differ")
    return bad


def check_recompute() -> list[str]:
    from chipff.runner import load_raw, run_static

    model, mat, steps = "mace-mpa-0", "Si", ("lattice", "eos")
    raw = {s: ROOT / "results" / "raw" / model / f"{s}.json" for s in steps}
    backup = Path(tempfile.mkdtemp())
    for s, p in raw.items():
        shutil.copy2(p, backup / p.name)
    ref = {s: load_raw(model, s)[mat] for s in steps}
    bad = []
    try:
        # EOS first, from the committed relaxed cell: its inputs fingerprint includes that cell, so recomputing the
        # lattice first would change it in the last digits
        run_static(model, [mat], steps=("eos",), force=True)
        run_static(model, [mat], steps=("lattice",), force=True)
        new = {s: load_raw(model, s)[mat] for s in steps}
        for s in steps:
            for k in ("code", "settings", "inputs"):
                if ref[s]["provenance"].get(k) != new[s]["provenance"].get(k):
                    bad.append(f"{s}: {k} fingerprint changed")
            for k, rtol in TOL.items():
                if k in ref[s] and ref[s][k] is not None:
                    x, y = float(ref[s][k]), float(new[s][k])
                    ok = abs(y - x) <= rtol * abs(x)
                    print(f"  {s:8s} {k:16s} committed {x:.6g}  recomputed {y:.6g}  {'ok' if ok else 'DIFFERS'}")
                    if not ok:
                        bad.append(f"{s}: {k} {x:.6g} -> {y:.6g} (tolerance {rtol:g})")
    finally:
        for s, p in raw.items():
            shutil.copy2(backup / p.name, p)
        shutil.rmtree(backup)
    v = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_checkpoints.py")], cwd=ROOT,
                       capture_output=True, text=True)
    print(v.stdout.strip())
    if v.returncode:
        bad.append("model checkpoint differs from configs/checkpoints.json")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", action="store_true")
    ap.add_argument("--recompute", action="store_true")
    a = ap.parse_args()
    bad = (check_tables() if a.tables else []) + (check_recompute() if a.recompute else [])
    for b in bad:
        print("FAIL", b)
    print("reproducible" if not bad else f"{len(bad)} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
