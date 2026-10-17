"""Print what thermal-expansion results exist, their checks, and timings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="thermal")
    a = ap.parse_args()
    for p in sorted((ROOT / "results" / "raw").glob(f"*/{a.tag}.json")):
        d = json.loads(p.read_text())
        print(f"\n== {d['model']}  ({d['meta'].get('device')}, last batch {d['meta'].get('wall_s', 0) / 60:.1f} min)")
        for r in sorted(d["results"], key=lambda r: r["material"]):
            c = r["checks"]
            flags = [k for k in ("temperature_on_target", "pressure_on_target", "volume_converged") if not c[k]]
            print(f"  {r['material']:12s} T={r['temperatures']}  alpha_V={r['alpha_V_1e6']:7.2f} ± {r['alpha_V_err_1e6']:5.2f} e-6/K"
                  f"  prod={max(r['prod_ps']):.0f} ps  {'OK' if not flags else 'CHECK: ' + ', '.join(flags)}")


if __name__ == "__main__":
    main()
