<!-- DRAFT for review. Not posted. Target: https://github.com/cusp-ai-oss/kups/issues
     Checked before drafting (2026-10-20): no existing kUPS issue mentions MatterSim; kups 1.0.8 is the
     latest release; the export on the Hub is still revision 9bedd37 (last modified 2026-07-29), and the
     reproducer below gives the same numbers today. -->

**Title:** MatterSim JAX export: energy depends on edge order and supercell size

Hi, and thanks for kUPS and the model exports. They made it straightforward to benchmark universal force
fields on semiconductor-device materials ([ChipFF Bench](https://github.com/anushajain2/chipff-bench)).

While validating results I found that the MatterSim export on the Hub returns energies that change when the
edges of the input graph are reordered, and per-atom energies that change with supercell size. The MACE
export, run through the same code path, does not.

**Export tested:** `CuspAI/kUPS-mattersim-jax`, file `mattersim-v1.0.0-5m.zip`, revision
`9bedd37fab0b593dadb90e894a4afbf8eb9251df`, SHA-256
`8debd7072cd9220faa2a745f6739faf92d593a0c24671a6099effdbf4dd58f0a`.

**Reproducer** (about 5 s on a laptop CPU). It calls `TojaxedMliap.call` directly on a clean
`AtomGraphInput` built with ASE's neighbour list, so kUPS's neighbour-list padding is not involved:
[`scripts/repro_mattersim_export.py`](https://github.com/anushajain2/chipff-bench/blob/v1.0.0/scripts/repro_mattersim_export.py)

Output for diamond Si (a = 5.47 Å):

| | MatterSim 5M export | MACE-MPA-0 export (control) |
|---|---|---|
| primitive cell, ASE edge order | −4.41769 eV/atom | −5.41474 eV/atom |
| primitive cell, shuffled edges | −4.70677 eV/atom | −5.41474 eV/atom |
| 2×2×2 supercell | −4.56640 eV/atom | −5.41474 eV/atom |

For reference, Microsoft's `mattersim` package (1.2.5, `MatterSimCalculator`, MatterSim-v1.0.0-5M) gives
−5.4014 eV/atom for this structure in both cells.

**Comparison on more structures.** On six materials (Si, GaAs, InP, Cu, Ta, monoclinic HfO₂), with identical
structures sent to the export (through kUPS) and to the official package:

- primitive cells (1–12 atoms) return `NaN` in 2–3 of 3 frames per material;
- where the energy is finite it differs from the official package by up to 0.7 eV/atom (GaAs), and forces by
  up to 1.2 eV/Å (HfO₂);
- the force response to a 0.01 Å phonon displacement differs by 5–54 %.

The same comparison for the MACE and Orb exports agrees with `mace-torch` and `orb-models` to ≤ 0.07 meV/atom
and 0.3 % in the displacement response, so the comparison code itself looks sound. Tables and data:
[`docs/thermal_failure_study.md`, section 1](https://github.com/anushajain2/chipff-bench/blob/v1.0.0/docs/thermal_failure_study.md#1-native-vs-export-on-identical-structures).

**Effects seen through kUPS:**
- inside `kups_relax` and `kups_md` batches, the same structure gets different energies depending on what else
  is in the batch;
- a single 2-atom Si cell returns `NaN` when it is the only system in the batch;
- cell relaxations stop at volumes where the model's own E(V) curve is not at its minimum (about 2 GPa residual
  pressure for Si).

**A guess at the cause** (not verified): the result depends on edge order even on an unpadded graph, so the
three-body (angle) part of the exported graph may assume a particular edge layout, or a triplet count fixed at
export time.

**Environment:** kups 1.0.8, jax/jaxlib 0.11.2, Python 3.12, macOS arm64 (CPU), float64 as set by the kUPS
apps. Exact versions: [`env/requirements-lock.txt`](https://github.com/anushajain2/chipff-bench/blob/v1.0.0/env/requirements-lock.txt).

Happy to test a re-export or run more cases.
