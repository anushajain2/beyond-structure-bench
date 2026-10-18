# Result provenance

Every record in `results/raw/<model>/<step>.json` carries a `provenance` fingerprint
(`src/chipff/provenance.py`):

| hash | covers |
|---|---|
| `code` | the source of the functions that compute that step for that model's backend |
| `settings` | the config sections the step reads, the model file and its options |
| `inputs` | the material's Materials Project structure; for elastic/EOS also the model's relaxed structure; for thermal also the model's K_Reuss and the temperature plan |

plus the git commit, package versions and time (information only). `chipff analyze` recomputes the
three hashes and excludes any result whose fingerprint does not match, listing it as stale in
`results/checks.csv`, so results produced by different code or settings are never mixed.

## Backfilled fingerprints (static results, 2026-10-18)

Stamping was added after the static results were computed. Those records carry
`"stamped": "backfilled ..."` instead of `"at run time"`. They were backfilled only after checking that
the code for each step behaves identically to the code that produced them:

* **Lattice (all models)** and **EOS (MACE, Orb)** were computed before one change to `Engine.relax`:
  fixed-cell relaxations now return atoms in the caller's frame. That change touches only the fixed-cell
  branch and only the orientation of returned coordinates; lattice uses the variable-cell branch, and EOS
  uses only energies, which do not depend on orientation.
* **Elastic (MACE, Orb)** were recomputed after both frame fixes (commit 9a7aa8d); **all MatterSim
  (official package) results** were computed after them.
* The `relax`, `elastic` and `eos` sections of `configs/benchmark.yaml` are unchanged since these runs.

To remove any reliance on this, rerun the static steps (`chipff static --force`, about 1.5 h on a laptop
CPU for the three models); the new records are stamped at run time.
