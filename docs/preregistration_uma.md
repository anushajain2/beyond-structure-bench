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

Written 2026-10-24, after the run. Nothing above the line was changed. Output of `scripts/prereg_uma_eval.py`, per
material, is in `results/preregistration_uma.json`.

### Verdicts

| | prediction | result | verdict |
|---|---|---|---|
| **U1** | existing models' spread predicts UMA's error | ρ = 0.21, p = 0.18, n = 21 | **inconclusive** |
| **U2** | UMA's large errors follow its bulk modulus | 2 of 5 explained | **inconclusive** |
| **U3** | Si within ±30 % → at most 1 sign flip | Si +10.1 %, 0 of 5 flipped | **supported** |
| **U4** | UMA's errors track Orb's most | r(UMA, Orb) = 0.77 against 0.59 (MACE) and 0.59 (MatterSim) | **supported** |

### The run

* **Steps:** static, then QHA, all 33 materials. All records are current and none was built from a dirty tree.
* **Time:** the QHA took 30 min with two workers, well under the 1–3 h estimate. UMA keeps crystal symmetry, so
  its displacement counts are close to MACE's: Si 1, HfO₂ 36, Y₂O₃ 22.
* **Memory:** peak 6.5 GB (Al₂O₃). No watchdog kill.
* **Exclusions:**
  * TiO₂ and SrTiO₃ are dynamically unstable, as for MACE and MatterSim.
  * MgO fails the volume check over its window, as for every model.
  * hBN fails the interpolation check. It is layered and not graded anyway.

### What each result says

* **U1, inconclusive.** The Orb test's exploratory signal, three-model spread tracking the error, does not carry
  over to a new model.
  * Materials where the old models agree can still be hard. UMA is off by 36 % on AlN, 55 % on Ge and 17 % on
    MgO, all low-spread materials.
  * Materials where they disagree can be easy for UMA: Mo, W and Ru are high-spread, and UMA is within 8 %.
  * So disagreement among existing models is not a reliable warning for a new one.
* **U2, inconclusive (0.4, between the thresholds).** UMA's bulk modulus is about as accurate as the others', and
  UMA's large errors mostly do not come from it.
  * Ta is +45 % with K exact (+0.03 %), the Grüneisen pattern seen for MACE and Orb.
  * Ge (+54 %) and AlN (+35 %) have K errors that explain only a third of their α errors.
  * GaAs and Co are explained.
* **U3, supported.** UMA's silicon is close (+10 % over its window), and it gets the sign of every Si-sensitive
  stack right, as predicted. That is consistent with mismatch sign errors being a silicon problem, but a single
  supported branch is weak evidence. The other branch, a model with a bad silicon, was MatterSim's case, which
  motivated the hypothesis.
* **U4, supported by the registered rule, but not decisively.** r(UMA, Orb) = 0.77 (n = 21) is higher than UMA's
  correlation with MACE (0.59) or MatterSim (0.59, n = 22). A bootstrap of the difference was not registered; done
  now, for information, its 95 % intervals cross zero (−0.19 to 0.60 against MACE, −0.10 to 0.62 against
  MatterSim). So the two OMat24-trained models share the most error, but this sample cannot rule out that all four
  share errors about equally.

### Descriptive

Mean absolute error with 95 % CI, and paired bootstrap from `results/robustness/`:

| | MACE-MPA-0 | MatterSim v1 | Orb v3 | UMA s-1.2 |
|---|---|---|---|---|
| thermal expansion, 300 K | 36.1 % (n 22) | 24.2 % (n 22) | 20.9 % (n 21) | **18.9 %** (14–29, n 22) |
| thermal expansion, window | 35.5 % (n 17) | 34.5 % (n 18) | 24.6 % (n 17) | 24.5 % (17–37, n 18) |
| bulk modulus vs experiment | 10.4 % | 13.4 % | 12.0 % | 11.0 % |

The bulk-modulus row is on the 25 non-layered materials graded for all four. UMA's own bootstrap figure is
11.2 % (8–16, n 27).

* **Paired comparisons, UMA against each model:**
  * More accurate than MACE at 300 K (+17 pp) and than MatterSim over the window (+10 pp).
  * Not separable from Orb on any thermal metric.
  * On bulk modulus, not separable from any model against experiment, but closer to DFT than every other model.
* **Shared failure:** Ta is overshot by every model except MatterSim (MACE +179 %, Orb +70 %, UMA +45 %). In each,
  this happens with a reasonable bulk modulus, which is the Grüneisen failure the six-case study found.

### Deviations

1. **Metadata fix before the run:** `run_meta` assumed every official-package model was MatterSim, so the first
   static launch failed before computing anything. Fixed in 2932e90; it is not part of any fingerprint.
2. **Watchdog on the static run:** the first watchdog watched `caffeinate`'s child, not Python. A second watchdog on
   the Python process covered the whole static run, which peaked at 4.8 GB. The QHA drivers watched the right
   process.
3. **No deviation from the registered analysis.** The U4 bootstrap above is additional and labelled as such.
4. **Descriptive bulk-modulus figure corrected.** The script's descriptive block, which decides nothing, averages
   bulk modulus over layered materials too, which the benchmark does not grade. The table above uses non-layered
   materials. The script is left as registered.
