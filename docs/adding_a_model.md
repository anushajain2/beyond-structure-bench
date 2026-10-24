# Adding a model to the benchmark

How to run a new machine-learned force field through BeyondStructure Bench. This is the procedure used for Orb v3's
thermal expansion and the three UMA releases. Each step points at the code it uses.

## 1. Describe the model (`src/chipff/models.py`)

Add a `ModelSpec` with:
* a key;
* a label, developer, training data and licence;
* a backend, one of:
  * `tojax`, a CuspAI JAX export run through kUPS;
  * `ase-<package>`, an official ASE calculator, as for MatterSim (`ase-mattersim`) and UMA (`ase-uma`,
    `ase-uma-file`).

A new ASE calculator gets its own function in `src/chipff/ase_engine.py`, dispatched from `AseEngine.__init__`. Keeping
it separate leaves every existing model's code fingerprint unchanged. Then add that function to the backend's code
objects in `src/chipff/provenance.py`, so the new model's results are fingerprinted against it.

## 2. Pin the checkpoint (`configs/checkpoints.json`)

Add the model file's location to `scripts/verify_checkpoints.py` and record its revision and SHA-256. Results then
apply to that exact file, and CI checks it.

## 3. Pre-register (`docs/preregistration_<model>.md`)

Before running anything, commit:
* what has already been seen;
* the run settings (unchanged from `configs/benchmark.yaml`);
* a few hypotheses with numeric decision rules, and an evaluation script;
* for templates, see the three existing pre-registrations.

A new model's results are a chance for a blind test, and they lose that value the moment they are seen.

## 4. Run

```bash
PYTHONPATH=src python -m chipff.cli static -m <key>                                  # ~10-30 min on a laptop CPU
PYTHONPATH=src python scripts/qha_worker_lowmem.py <key> <material> <lock-file>        # QHA, one material per process
PYTHONPATH=src python scripts/qha_worker_lowmem.py <key> <material> <lock-file> axial  # GaN, AlN, Ru, Al2O3
```

`chipff qha -m <key>` does the same in one command; the low-memory worker is safer on a laptop.
* It clears JAX caches after each force call, so kUPS backends don't leak memory.
* It serialises writes, so two workers can run side by side.
* Expect a few GB per process, and up to about 9 GB for the largest cells.

## 5. Analyse and check

```bash
PYTHONPATH=src python -m chipff.cli analyze && PYTHONPATH=src python -m chipff.cli report
PYTHONPATH=src python scripts/prereg_<model>_eval.py
PYTHONPATH=src python -m pytest -q tests
```

`analyze` includes every model in `src/chipff/models.py` automatically: tables, trust map, pairwise bootstrap,
chip-stack mismatch and stress, and the per-material guidance. Then add the model's key to `MODELS` in
`scripts/build_site.py` and `MARKERS` in `src/chipff/report.py` so it appears on the site and in the figures.

## 6. Report

Write the results below the line in the pre-registration, without editing the registered part. Report deviations
separately.
