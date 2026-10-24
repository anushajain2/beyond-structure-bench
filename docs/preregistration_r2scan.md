# Pre-registration: does better training physics fix the errors? (UMA, PBE vs r2SCAN)

**Status: registered 2026-10-24, before either model was run.** Everything above the line "Results (added after the
run)" was written and committed before UMA s-1.2.1 or its r2SCAN fine-tune computed any benchmark result, and is not
edited afterwards.

## The question

The benchmark's models all learn from PBE, the standard DFT method. The matched-PBE comparison found that some errors
are inherited from PBE, chiefly semiconductors that come out too soft, while most of the large thermal-expansion
errors are the models' own. Meta publishes the same UMA release twice: trained on PBE labels (`uma-s-1p2p1`), and with
its omat head fine-tuned to r2SCAN labels (`uma-s-1p2p1-ft-r2scan`). r2SCAN is a more accurate method for solids.
Comparing the two isolates the effect of the training physics, with architecture, code and settings held fixed.

## What has been seen

* **Nothing from either model:** no structure, energy or property, beyond checking that the r2SCAN checkpoint
  loads and has a single `omat` task.
* **Results of the other models:** UMA s-1.2 (the previous release) and the matched-PBE comparison
  (`docs/thermal_failure_study.md` section 7) were seen; they motivate the hypotheses below.

## The run (fixed)

* **Models:** `uma-s-1p2p1` and `uma-s-1p2p1-r2scan` in `src/chipff/models.py`, through fairchem's calculator on CPU,
  omat task. Checkpoints are pinned in `configs/checkpoints.json`. The PBE model is loaded by name, which adds
  fairchem's per-element reference energies; the r2SCAN file is loaded directly. That is a constant per element, which
  changes no property measured here.
* **Steps:** `chipff static` (lattice, elastic, EOS) and the QHA for all 33 materials, settings unchanged. One process
  per material through `scripts/qha_worker_lowmem.py`, at most two at a time, each with a 12 GB memory limit and a 15 %
  free-memory floor.
* **Grading, exclusions and references:** exactly as in `chipff.analysis` and `data/` at the registration commit.

## Hypotheses and decision rules (fixed)

Computed by `scripts/prereg_r2scan_eval.py`, committed with this file. If they disagree, this text rules.
Semiconductors are Si, Ge, SiC, GaAs, GaN, InP and AlN; only materials graded for both models count.

* **R1: r2SCAN fixes the too-soft semiconductors.** The mean signed bulk-modulus error (vs experiment) of the
  semiconductors rises by at least 5 percentage points and its magnitude falls. **Refuted** if it falls (softer).
  Otherwise inconclusive; also inconclusive if fewer than 4 semiconductors are graded for both.
* **R2: r2SCAN improves semiconductor thermal expansion.** The mean absolute log error at 300 K over the
  semiconductors falls by at least 20 % (relative). **Refuted** if it rises. Otherwise inconclusive; also inconclusive
  if fewer than 4 are graded for both.
* **R3: r2SCAN does not fix tantalum.** Ta's overshoot was attributed to the models themselves, not PBE. Supported if
  the r2SCAN model's Ta error at 300 K stays above +25 %; **refuted** if below +15 %; inconclusive between, or if Ta
  is not graded.
* **R4: r2SCAN reduces PBE's oversized lattices.** The mean signed lattice error over the non-layered materials graded
  for both falls by at least 0.3 percentage points. **Refuted** if it rises. Otherwise inconclusive; also inconclusive
  if fewer than 10 are graded.

Descriptive, no decision: each model's mean absolute error per property on the materials both are graded on, and the
change from UMA s-1.2 to s-1.2.1 (PBE).

## What the outcomes would mean

* **R1 and R2 supported:** the inherited part of the error is fixed by better training physics, as the matched-PBE
  comparison predicts.
* **R3 supported:** the models' own errors survive it, so those need better models, not better labels.
* **R1 supported but R2 not:** stiffer semiconductors alone do not cure their expansion; the remaining error sits in
  the vibrations (the Grüneisen part), which the labels do not fix.

---

## Results (added after the run)

Written 2026-10-25; the registered part above is unchanged. Output of `scripts/prereg_r2scan_eval.py` is in
`results/preregistration_r2scan.json`.

**The run.** Both models finished static, QHA and axial runs for all 33 materials. Every record is current, and no
memory watchdog fired. The QHA took about 6 h instead of 1 h because the matched-DFT session's calculations were
sharing the CPU.

### Verdicts

| | prediction | PBE model | r2SCAN model | verdict |
|---|---|---|---|---|
| **R1** | semiconductors stiffen | mean signed bulk-modulus error −15.1 % | −5.2 % (+9.9 pp) | **supported** |
| **R2** | semiconductor expansion improves | mean abs. log error 0.225 | 0.155 (−31 %) | **supported** |
| **R3** | tantalum's overshoot survives | +61 % at 300 K | **+6.8 %** | **refuted** |
| **R4** | lattices shrink toward experiment | mean signed +0.61 % | −0.31 % (−0.92 pp) | **supported** |

R2 is computed over AlN, GaAs, GaN, Ge, Si and SiC; InP has no 300 K reference.

### What it means

* **The inherited errors are fixed by better training physics, as predicted.** The too-soft semiconductors, PBE's
  oversized lattices, and with them the semiconductors' expansion, all move toward experiment.
* **Tantalum's overshoot was fixed too, against the prediction.** The matched-PBE comparison had attributed it to the
  models rather than PBE, so R3 predicted it would survive. Two explanations remain, and this test cannot tell them
  apart:
  * the fine-tune changed more than the labels: its training structures may sample stretched and vibrating crystals
    more densely, which is the fix the study's diagnosis points to;
  * or some of Ta's error does trace to the PBE labels after all.
* **Caveat on Ta:** the r2SCAN model's Ta run fails the interpolation check. 2.1–2.4 % of interpolated modes are
  imaginary at the expanded volumes, against the 2 % limit; every mode at the commensurate q-points is stable. So its
  window value is excluded, and the 300 K value is graded under the benchmark's rules. Elsewhere in this benchmark, this
  kind of artefact moves α by up to about 6 %, far less than the change from +61 % to +7 %. Mode softening on expansion
  could still contribute to the improvement.

### Descriptive

Mean absolute error on the materials both models are graded on:

| | PBE (s-1.2.1) | r2SCAN fine-tune |
|---|---|---|
| lattice constant (30) | 0.72 % | 0.44 % |
| bulk modulus (28) | 11.7 % | 9.2 % |
| thermal expansion, 300 K (23) | 17.5 % | 13.5 % |
| thermal expansion, window (19) | 22.4 % | 14.3 % |

* **Benchmark-wide:** the r2SCAN model has the lowest mean error on every property of all six models. Its thermal
  expansion is significantly better than MACE-MPA-0's and MatterSim's (paired bootstrap), but not separable from the
  other UMA versions or Orb.
* **Model guidance:** it is "reliable" for 18 of 33 materials, against 9–11 for the others.
* **UMA s-1.2 against s-1.2.1 (both PBE):** similar on average (300 K: 18.8 % vs 17.5 %), but they differ on single
  materials. On ruthenium on silicon, the newer release even reverses the sign of the in-plane mismatch. A model's
  release version matters at the level of individual materials.

### Deviations

None from the registered analysis. The Ta caveat above follows from the benchmark's existing rules, applied unchanged.
