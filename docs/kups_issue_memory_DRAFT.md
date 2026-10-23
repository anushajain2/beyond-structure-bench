<!-- DRAFT for review. Not posted. Target: https://github.com/cusp-ai-oss/kups/issues
     Before posting: check that no existing issue covers this, that kups 1.0.8 is still the latest release, and
     rerun the reproducer. Part of the cause may be how ChipFF Bench uses kUPS (a new propagator per call), so
     the issue is phrased as a question about the recommended pattern. -->

**Title:** Memory grows ~100 MB per call when single-point forces are evaluated through a fresh MD propagator

Hi, and thanks again for kUPS. We use it to compute phonons for a thermal-expansion benchmark
([BeyondStructure Bench](https://github.com/anushajain2/beyond-structure-bench)). Each phonon calculation needs
a few hundred single-point force evaluations on slightly different supercells.

**What we do.** Each force evaluation builds an `MdState` from ASE atoms, makes a propagator with
`make_md_propagator(lens, "verlet", potential)` and `make_cycle_function`, and advances it one negligible step
with `propagate_and_fix`; forces are read from `position_gradients`. The code is
[`Engine.forces`](https://github.com/anushajain2/beyond-structure-bench/blob/main/src/chipff/engine.py) and
`_md_state` / `_md_step_fn` / `_advance` next to it.

**What happens.** The process footprint grows by about 100 MB per call and is never released. Over one phonon
calculation (≈ 500 calls on 160–270-atom supercells, Orb v3 export) a single process reached 28 GB on a 24 GB
laptop. Calling `jax.clear_caches()` after each call keeps it flat, at about 10 % extra run time.

**Reproducer** (≈ 2 min per variant, CPU):
[`scripts/repro_kups_forces_memory.py`](https://github.com/anushajain2/beyond-structure-bench/blob/main/scripts/repro_kups_forces_memory.py)

| calls | footprint, no clearing | footprint, `jax.clear_caches()` after each call |
|---|---|---|
| 5 | 4.2 GB | 1.1 GB |
| 10 | 4.8 GB | 1.2 GB |
| 20 | 5.7 GB | 1.4 GB |
| 30 | 6.6 GB | 0.9 GB |

Orb v3 export `orb_v3_conservative_inf_omat.zip`, kups 1.0.8, jax/jaxlib 0.11.2, macOS arm64, CPU.

**Questions.**

1. Is a new propagator per call expected to keep a new compiled program alive? We assume each call's closures
   are new objects, so the jit cache never hits, and the old executables stay referenced.
2. What is the recommended way to evaluate forces on many structures of the same size: build the propagator
   once and swap positions and cell in the state, or call the potential directly?

Happy to test a suggested pattern.
