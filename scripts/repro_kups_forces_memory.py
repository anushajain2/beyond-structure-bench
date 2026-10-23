"""Memory growth from repeated single-point force calls through kUPS (docs/kups_issue_memory_DRAFT.md).

Calls chipff's Engine.forces (one kUPS Verlet step per call, as a phonon calculation does) 30 times on Orb v3
supercells of alpha-quartz and prints the process footprint every 5 calls, without and with
jax.clear_caches() after each call. About 2 min per variant on a laptop CPU.

    PYTHONPATH=src python scripts/repro_kups_forces_memory.py keep
    PYTHONPATH=src python scripts/repro_kups_forces_memory.py clear
"""

import gc
import logging
import os
import subprocess
import sys
import time
import warnings

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

from ase import Atoms  # noqa: E402

from chipff.qha import _make_phonopy, _supercell_reps, _symmetrized  # noqa: E402
from chipff.runner import make_engine, relaxed_structures  # noqa: E402

clear = sys.argv[1] == "clear"
a = _symmetrized(relaxed_structures("orb-v3")["SiO2_quartz"])
ph = _make_phonopy(a, _supercell_reps(a, 10.0))
ph.generate_displacements(distance=0.01)
scs = [Atoms(symbols=s.symbols, cell=s.cell, scaled_positions=s.scaled_positions, pbc=True)
       for s in ph.supercells_with_displacements]
eng = make_engine("orb-v3")
import jax  # noqa: E402


def footprint():
    out = subprocess.run(["top", "-l", "1", "-pid", str(os.getpid()), "-stats", "mem"], capture_output=True, text=True)
    return out.stdout.split()[-1]


t = time.time()
for i in range(30):
    eng.forces([scs[i % len(scs)]])
    if clear:
        jax.clear_caches()
        gc.collect()
    if i % 5 == 4:
        print(f"{i + 1:3d} calls  footprint {footprint():>7s}  {time.time() - t:5.0f} s", flush=True)
