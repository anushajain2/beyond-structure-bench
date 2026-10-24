# Pre-registration: UMA as a fourth model, a blind test

**Status: registered 2026-10-24, before any UMA result existed.** Everything above the line "Results (added
after the run)" was written and committed before UMA was run on any benchmark material. It is not edited
afterwards; results and deviations go below that line. The commit that adds this file is the registration, and
it predates every file in `results/raw/uma-s-1p2/`.

## Why UMA, and what is already known

UMA small 1.2 (Meta FAIR, omat task) is the benchmark's fourth model. Its training data, OMat24, overlaps with
Orb v3's (the OMat-trained conservative model) and differs from MACE-MPA-0's (MPtrj + sAlex) and MatterSim's (its
own sampled set).

* **UMA results seen:** none. A timing probe ran UMA force calls on MACE's relaxed Si, InP and Al₂O₃ supercells; it
  recorded wall time and memory only, no energy or property.
* **Seen, used as predictors:** every MACE, MatterSim and Orb result in this branch, and the exploratory finding of
  `docs/preregistration_orb_thermal.md`: the three models' spread tracks their mean's error (post hoc, ρ ≈ 0.5–0.6).

Unlike the Orb test, every material is blind for UMA.

## The run (fixed)

* **Model:** `uma-s-1p2` in `src/chipff/models.py`, through fairchem's `FAIRChemCalculator`. kUPS's PyTorch bridge
  needs a GPU, so this is the official-package route, as for MatterSim. The checkpoint is pinned in
  `configs/checkpoints.json` (revision `c5107e43`, sha256 `ba5c0d91…`).
* **Materials and steps:** all 33. `chipff static -m uma-s-1p2` (lattice, elastic, EOS), then the QHA with
  `configs/benchmark.yaml` `thermal_qha` unchanged, Γ acoustic modes excluded, one process per material. Two workers
  run at a time through `scripts/qha_worker_lowmem.py`, each with a 12 GB memory limit and a 15 % free-memory
  floor.
* **Exclusions and grading:** exactly those of `chipff.analysis` at the registration commit. That includes v1.1.0's
  reference tiers and the 300 K rule fix (f2e89c1). Layered materials are not graded.
* **References:** `data/experimental/` and `data/reference_quality.yaml` at the registration commit.
* **Allowed operational changes** (reported as deviations): if a material's process dies, it is rerun once with the
  same settings and a higher memory limit, alone. If it fails again, it is reported as not computed.

## Metrics (fixed)

Primary: α_V at 300 K against experiment (`err_300K_pct` in `results/thermal_expansion.csv`), as in the Orb test.
`e = ln(1 + err/100)`. Bulk-modulus error is `err_exp_pct` of `results/bulk_modulus.csv`, for UMA's own static K.
Decisions are computed by `scripts/prereg_uma_eval.py`, committed with this file. If the script and this text
disagree, this text rules.

## Hypotheses and decision rules (fixed)

Each verdict is supported, refuted or inconclusive.

### U1: where the existing models disagree, UMA is also wrong

The predictor is frozen in `results/preregistration_uma_predictors.json`, before UMA ran. For each of the 21
materials graded at 300 K for MACE, MatterSim and Orb, it is S₃, the spread (population SD) of their log
predictions. It ranges from Al₂O₃ 0.005 and MgO 0.012 to Co 0.41 and Ta 0.48.

* **Statistic:** Spearman ρ(S₃, |e_UMA|) over those of the 21 that UMA is graded on at 300 K. One-sided permutation
  p for ρ > 0, 100 000 permutations, seed 0.
* **Inconclusive** if n < 8. **Supported** if ρ ≥ 0.30 and p < 0.05. **Refuted** if ρ ≤ 0. Otherwise
  **inconclusive**.
* **Meaning:** this is the prospective version of the Orb test's exploratory finding. If supported, existing
  models' disagreement marks genuinely hard materials, and it is a cheap warning for a new model. The predictor
  shares no term with the outcome.

### U2: UMA's large errors follow its bulk-modulus error

The rule is the Orb test's H1, applied to UMA on all graded materials, which are all blind.

* Material *i* has an error to explain if |err_300K| > 20 %. It is **explained** if `e` and `p = ln(K_exp/K_UMA)`
  have the same sign and 0.5 ≤ p/e ≤ 2.
* **Supported** if at least 4 have an error to explain and ≥ 2/3 are explained. **Refuted** if ≤ 1/3 are
  explained. Otherwise **inconclusive**.

### U3: UMA's silicon error decides whether it flips the sign of chip-stack mismatch

MatterSim gets the mismatch sign wrong for the stacks whose measured mismatch at 900 K is below 2000 microstrain:
W, Mo, Ta, GaN and AlN on Si. This is because its silicon expands too much.

* **Prediction:** the outcome follows UMA's Si window error (`err_exp_pct`, 500–800 K).
  * If that error is above +30 %, UMA gets the sign wrong for at least 3 of those 5 stacks.
  * If it is within ±30 %, UMA gets the sign wrong for at most 1.
* **Supported** if the observation matches the branch that applies; **refuted** if not.
* **Inconclusive** if Si is not graded over its window, fewer than 4 of the 5 stacks are computed, or the Si
  error is below −30 % (no prediction registered).

### U4: shared training data, shared errors

* **Statistic:** Pearson correlation of signed log errors at 300 K between UMA and each other model, over the
  materials both are graded on, requiring at least 10 per pair.
* **Supported** if r(UMA, Orb) ≥ 0.5 and exceeds both r(UMA, MACE) and r(UMA, MatterSim). **Refuted** if r(UMA,
  Orb) is below both. Otherwise **inconclusive**.
* **Meaning:** if supported, models trained on the same data inherit each other's errors. That would be evidence
  for the training-data explanation over model architecture.

### Descriptive, no decision

UMA's mean absolute error at 300 K, over the window and for bulk modulus, on the materials all four models are
graded on.

## What the outcomes would mean

* **U1 supported:** the benchmark can flag materials where any new model is likely to fail before running it.
* **U3 supported:** mismatch sign errors are a silicon problem, and checking a model's silicon is a cheap screen
  for chip-stack use.
* **U4 supported:** the shared-error question has a data answer; refuted, it points at architecture or chance.

None changes the grading rules or thresholds.

---

## Results (added after the run)

*Not yet run.*
