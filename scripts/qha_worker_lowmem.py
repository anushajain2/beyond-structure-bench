"""Run one material's QHA as `chipff qha --no-isolate` does, with low, flat memory (used for Orb v3, 2026-10-23).

    PYTHONPATH=src python scripts/qha_worker_lowmem.py orb-v3 Al2O3 /tmp/qha.lock           # chipff qha
    PYTHONPATH=src python scripts/qha_worker_lowmem.py orb-v3 GaN /tmp/qha.lock axial      # chipff axial

See docs/preregistration_orb_thermal.md, Deviations 2-3.
"""
# One material's QHA, as `chipff qha --no-isolate` does, with two operational changes that do not touch the numbers:
# * writes to the results file are serialised by a lock, so two workers can run side by side;
# * JAX's in-memory caches are cleared after every force call. Engine.forces builds a fresh jitted propagator
#   per call and JAX keeps each compiled program (~100 MB per call, ~50 GB over one oxide's QHA).
# The code fingerprint is computed (and cached) from the unpatched sources before anything is wrapped.
import fcntl, gc, logging, sys
import chipff.runner as R
from chipff import engine, provenance
from chipff.models import get_model

model, mat, LOCK = sys.argv[1:4]
STEP = sys.argv[4] if len(sys.argv) > 4 else "qha"
CODE = provenance.code_hash(provenance._code_step("axial_qha" if STEP == "axial" else "thermal_qha"),
                            get_model(model).backend)
print("code fingerprint", CODE, flush=True)

_save = R.save_raw
def locked(*a, **k):
    with open(LOCK, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            return _save(*a, **k)
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
R.save_raw = locked

_forces = engine.Engine.forces
def forces(self, structures):
    out = _forces(self, structures)
    self.jax.clear_caches()
    gc.collect()
    return out
engine.Engine.forces = forces

# diagnostics: memory footprint every 15 s, with how far the run has got
import os, subprocess, threading, time
from chipff import qha
STAGE = {"relax": 0, "volume": 0, "forces": 0}
_relax = engine.Engine.relax
def relax(self, *a, **k):
    STAGE["relax"] += 1
    return _relax(self, *a, **k)
engine.Engine.relax = relax
_mk = qha._make_phonopy
def make_phonopy(*a, **k):
    STAGE["volume"] += 1
    return _mk(*a, **k)
qha._make_phonopy = make_phonopy
_fc = forces
def counted(self, structures):
    STAGE["forces"] += 1
    return _fc(self, structures)
engine.Engine.forces = counted
def watch():
    while True:
        mem = subprocess.run(["top", "-l", "1", "-pid", str(os.getpid()), "-stats", "mem"], capture_output=True,
                             text=True).stdout.split()[-1]
        print(f"MEM {time.strftime('%H:%M:%S')} {mem} {STAGE}", flush=True)
        time.sleep(15)
threading.Thread(target=watch, daemon=True).start()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
for noisy in ("httpx", "huggingface_hub", "absl", "jax"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
if STEP == "axial":
    R.run_axial_qha(model, [mat], force=True)
else:
    R.run_thermal_qha(model, [mat], force=True)
