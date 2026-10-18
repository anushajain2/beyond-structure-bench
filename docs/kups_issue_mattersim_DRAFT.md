<!-- DRAFT for review. Not posted. Target: https://github.com/cusp-ai-oss/kups/issues -->

**Title:** MatterSim JAX export: energy depends on edge order and supercell size

Hi, and thanks for kUPS and the model exports. They made it easy to run a benchmark of
universal force fields on semiconductor materials ([ChipFF Bench](https://github.com/anushajain2/chipff-bench)).

While validating results I found that the MatterSim export on the Hub
(`CuspAI/kUPS-mattersim-jax`, `mattersim-v1.0.0-5m.zip`) returns energies that change when
the edges of the input graph are reordered, and per-atom energies that change with
supercell size. The MACE export run through the same code path does not.

**Reproducer.** This calls `TojaxedMliap.call` directly on a clean `AtomGraphInput` built with
ASE's neighbour list, so kUPS's neighbour-list padding is not involved: [`repro_mattersim_export.py`](https://github.com/anushajain2/chipff-bench/blob/main/scripts/repro_mattersim_export.py)

Output for diamond Si (a = 5.47 Å):

| | MatterSim 5M export | MACE-MPA-0 export (control) |
|---|---|---|
| primitive cell, ASE edge order | −4.41769 eV/atom | −5.41474 eV/atom |
| primitive cell, shuffled edges | −4.70677 eV/atom | −5.41474 eV/atom |
| 2×2×2 supercell | −4.56640 eV/atom | −5.41474 eV/atom |

For reference, Microsoft's `mattersim` package (`MatterSimCalculator`, MatterSim-v1.0.0-5M)
gives −5.4014 eV/atom for this structure in both cells.

**Effects seen through kUPS.**
- Inside `kups_relax` / `kups_md` batches, the same structure gets different energies depending on what else is in the batch.
- A single 2-atom Si cell returns `NaN` when it is the only system in the batch.
- Cell relaxations stop at volumes where the model's own E(V) curve is not at its minimum (~2 GPa residual pressure for Si).

**Guess at the cause** (unverified): the result is permutation-dependent even on an unpadded
graph, so the three-body (angle) part of the exported graph may assume a particular edge
layout, or a fixed triplet count captured at export time. MACE and Orb exports are unaffected.

**Environment:** kups 1.0.8, jax 0.11.2, Python 3.12, macOS arm64 (CPU), float64 as set by the kUPS apps.

Happy to test a re-export or share more cases.
