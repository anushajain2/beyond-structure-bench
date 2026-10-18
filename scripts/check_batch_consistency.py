"""Self-check: a structure's energy must not depend on what else is in the kUPS batch.

Evaluates the same Si crystal alone, duplicated, as a supercell, and batched with Cu and
MgO, and reports the per-atom energies. A correct model gives identical numbers.

Run:  python scripts/check_batch_consistency.py <model-key>
"""

import sys

import numpy as np
from ase.build import bulk

from chipff.engine import Engine
from chipff.models import get_model


def main(model: str) -> bool:
    eng = Engine(get_model(model))
    si = bulk("Si", "diamond", a=5.47)
    cu, mgo = bulk("Cu", "fcc", a=3.63), bulk("MgO", "rocksalt", a=4.25)
    cases = {
        "Si alone": [si], "Si x2": [si, si], "Si conventional (8 atoms)": [bulk("Si", "diamond", a=5.47, cubic=True)],
        "Si 2x2x2 supercell": [si.repeat(2)], "Si with Cu": [si, cu], "Si with MgO": [si, mgo],
    }
    vals = []
    for name, batch in cases.items():
        e, _ = eng.stress(batch)
        v = float(e[0]) / len(batch[0])
        vals.append(v)
        print(f"  {name:28s} Si energy {v: .6f} eV/atom")
    ok = bool(np.all(np.isfinite(vals))) and (max(vals) - min(vals) < 1e-4)
    print(f"{model}: spread {np.nanmax(vals) - np.nanmin(vals):.2e} eV/atom ->", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1]) else 1)
