# Pre-registration: Orb v3 benchmark-wide thermal expansion as a prospective test

**Status: registered 2026-10-23, before the run.** Everything above the line "Results (added after the run)" was
written and committed before Orb v3's Γ-fixed QHA was run on the benchmark's 33 materials. That part is not edited
after the run. Deviations, results and their evaluation go in the sections below that line. The commit that adds this
file is the registration; `git log -- docs/preregistration_orb_thermal.md` shows it predates
`results/raw/orb-v3/thermal_qha.json` with current fingerprints.

## Why

The thermal-failure study (`docs/thermal_failure_study.md`) explains the large QHA thermal-expansion errors through
Grüneisen parameters and soft bulk moduli. Its six cases (Si, GaAs, Cu, Ta, InP, monoclinic HfO₂) were chosen after
MACE's and MatterSim's failures had been seen, and the explanations came from inspecting them. An outside review
asked for a test whose cases and protocol are fixed in advance. Orb v3's benchmark-wide thermal expansion with the
current code has never been computed, so its results are still unseen. Running it is the one cheap prospective test
available.

## What has already been seen (honest accounting)

Not all of Orb's thermal results are unseen:

* **Study cases (6):** Si, GaAs, Cu, Ta, InP, HfO₂. Orb's Γ-fixed QHA for these is in the study.
* **Stale benchmark values (7):** Si, Ge, SiC, GaAs, GaN, InP, AlN. Computed before the Γ fix (2026-10-19), published
  as "stale" rows in `results/thermal_expansion.csv`, and seen by the author of this pre-registration while drafting.
  The Γ fix moved the study's values by up to ±8 %, so these are effectively seen.
* **Inputs, seen on purpose:** Orb's static results (`results/bulk_modulus.csv`: K, K′, their errors) and MACE's and
  MatterSim's thermal results (`results/thermal_expansion.csv`, including their α(T) curves and window errors). The
  hypotheses below use these as predictors. MACE's and MatterSim's window and 300 K errors were visible while drafting,
  so any test that uses them as outcomes (H4) is only partly prospective. No hypothesis statistic was computed on real
  data before registration: the evaluation script was tested on synthetic, randomised tables only.

**Blind set** = the 33 materials minus the 10 above = SiO₂ (quartz), β-Si₃N₄, Al₂O₃, ZrO₂, Y₂O₃, TiO₂ (rutile), MgO,
SrTiO₃, Al, W, Co, Ru, Mo, Ti, TiN, TaN, CoSi₂, NiSi, TiSi₂, WSi₂, MoS₂, hBN, graphite (23). After the benchmark's
exclusion rules, at most 15 of these can be graded at 300 K and at most 13 over the window. Primary tests use the blind
set; tests on seen materials are labelled as such and never decide a hypothesis.

## The run (fixed)

* **Model:** Orb v3 (conservative, OMat), `orb-v3` in `configs/benchmark.yaml`, through the kUPS export, as in the
  benchmark's static steps.
* **Materials:** all 33 in `data/materials.yaml`, rerunning the 7 stale ones.
  `chipff qha -m orb-v3 --force` (one process per material), with `configs/benchmark.yaml` `thermal_qha` unchanged:
  9 volumes 0.96–1.08 V0, Vinet EOS, supercell ≥ 10 Å, 0.01 Å displacements, reference forces subtracted, force constants
  symmetrised, stability at commensurate q-points, mesh length 50, **`exclude_gamma_acoustic: true`**. Temperature windows
  from `chipff plan` (the same as MACE's and MatterSim's).
* **Exclusions:** exactly those of `chipff.analysis.thermal_table`: stale fingerprint; layered (MoS₂, hBN, graphite:
  computed, not graded); dynamically unstable; any failed QHA check (window comparison only; 300 K is still graded
  unless the reason is one of the others); relaxed to a different crystal form (Orb's static results already flag
  TiO₂ rutile, SrTiO₃ and MoS₂). A material without an experimental value at 300 K (or covering its window) is not
  graded on that metric.
* **References:** `data/experimental/` as committed at the registration commit. A separate session may correct some
  references (the HfO₂/ZrO₂ monoclinic angle term, InP's 300 K value). The primary evaluation uses the references as
  registered. If corrected references exist when the evaluation is written, it is repeated with them as a secondary
  analysis, and any change in a verdict is reported. (None of these three materials is in the blind 300 K set.)
* **Allowed operational changes** (reported as deviations, not tuning): if a material's process dies (memory, crash),
  it is rerun once with a smaller `max_pairs_per_call` (a memory setting, excluded from the fingerprint); if it fails
  again, it is reported as not computed and drops out of every test. No other setting is changed.

## Metrics (fixed)

Primary metric: the volumetric expansion coefficient α_V against experiment, as `chipff analyze` writes it in
`results/thermal_expansion.csv`:

* **at 300 K:** `err_300K_pct` = 100 (α_V,model(300 K) / α_V,exp(300 K) − 1);
* **over the window:** `err_exp_pct`, the same for the window average.

The hypotheses are decided at 300 K, because it grades more materials and the experimental bulk moduli are
room-temperature values; the window result is reported alongside. The exception is H4, which is about the window by
construction. In the rules below, `e = ln(1 + err/100)` is the log error. Static bulk-modulus error `K_err` is
`err_exp_pct` of `results/bulk_modulus.csv` (Orb's K, Reuss or VRH as the reference defines, against experiment).
`p = ln(K_exp / K_model)` is what the bulk modulus alone predicts for α's log error with γ, C_V and V right.

The decisions are computed by `scripts/prereg_orb_thermal_eval.py`, committed with this file. If the script and this
text disagree, this text rules, and the disagreement is reported as a deviation.

## Hypotheses and decision rules (fixed)

Each verdict is one of **supported**, **refuted** or **inconclusive**; inconclusive is a legitimate outcome, not a
failure to report. Rules are checked in the order written.

### H1: Orb's errors are mostly explained by its bulk-modulus error

The study found Orb's GaAs and InP overshoots come mostly from a bulk modulus 22–25 % too soft. If that is the
general explanation, the K-only prediction `p` should match the sign and rough size of Orb's α error.

* Material *i* has an error to explain if |err_300K| > 20 %. It is **explained** if `e` and `p` have the same sign and
  0.5 ≤ p/e ≤ 2.
* **Primary set:** blind materials graded at 300 K with an experimental K (n with |err| > 20 % is not known in advance).
* **Supported** if at least 4 materials have an error to explain and ≥ 2/3 of them are explained. **Refuted** if at
  least 4 and ≤ 1/3 are explained. Otherwise **inconclusive**.
* **Secondary, not blind:** the same rule on the seven semiconductors (Si, Ge, SiC, GaAs, GaN, InP, AlN), the class the
  study's claim was about. All seven were seen (study or stale), so this is a consistency check that cannot decide H1.
  Also reported: the same rule with window errors, and the Spearman correlation of `p` with `e` over all graded
  blind materials (descriptive).

### H2: static K′ does not flag Orb's large errors better than chance

The study proposed static K′ as a candidate screening diagnostic and found one counterexample (Orb's Ta: normal K′,
+70 % error).

* Score: Orb's static K′ (`B_eos_prime`, Birch–Murnaghan fit of `results/raw/orb-v3/eos.json`), materials with
  `eos_fit_ok` true. Outcome: |err_300K| > 40 % ("large"; the benchmark's poor-grade threshold).
* Statistic: the AUC of K′ for separating large from not-large errors (ties count ½), with a one-sided permutation
  p-value for AUC > 0.5 (exact when there are at most 200 000 label placements, else 100 000 random permutations,
  seed 0).
* **Primary set:** blind materials graded at 300 K.
* **Inconclusive** if fewer than 2 large or fewer than 2 not-large errors. **Supported** (K′ no better than chance) if
  AUC ≤ 0.65. **Refuted** (K′ does flag them) if AUC ≥ 0.75 and p < 0.05. Otherwise **inconclusive**.
* Secondary, descriptive: the same on all graded materials; the hits, misses and false alarms of a fixed flag
  K′ > 5.0; the AUC for overshoots only (err > +40 %), the direction a high K′ predicts.

### H3: Orb's disagreement with the other two models tracks the ensemble's error

If the models' errors are partly independent, disagreement should signal error.

* For each material graded at 300 K for all three models: `D = |e_Orb − ½(e_MACE + e_MatterSim)|` (Orb's disagreement)
  and `E = |⅓(e_Orb + e_MACE + e_MatterSim)|` (log error of the three-model geometric mean).
* Statistic: Spearman ρ(D, E), with a one-sided permutation p for ρ > 0 (exact for n ≤ 8, else 100 000 random
  permutations, seed 0).
* **Primary set:** blind materials.
* **Inconclusive** if n < 8. **Supported** if ρ ≥ 0.30 and p < 0.05. **Refuted** if ρ ≤ 0. Otherwise **inconclusive**.
* Caveat, stated in advance: D and E share e_Orb, so a large Orb error raises both, and a positive ρ is partly built
  in. Reported alongside, not deciding: ρ(D, E′) with E′ the error of the MACE–MatterSim mean alone (no shared term),
  the same test over the window, and over all materials.

### H4: a right answer through compensating errors degrades over the window

The study found MACE's Si right at 300 K through a γ that is too low and a K that is too soft. The hypothesis: such
cancellations hold at one temperature and come apart over the window.

* Cases: every (model, material) pair, for all three models, graded both at 300 K and over the window, with an
  experimental K. A case is **right at 300 K** if |err_300K| < 20 %.
* Without phonon γ for every case, compensation is identified from K: the residual `r = e − p` is what γ, C_V and V
  together contribute. A right-at-300 K case is a **compensation case** if |r| ≥ ln 1.15 and `r` has the opposite sign
  to `p` (the other ingredients offset at least a 15 % bulk-modulus effect). Other right-at-300 K cases are
  **controls**.
* Growth: `Δ = |err_window| − |err_300K|`, in percentage points.
* **Primary set:** all three models pooled. MACE's and MatterSim's curves were seen while drafting (see above), so
  only Orb's part of this test is blind; the pooled test is reported as partly prospective.
* **Inconclusive** if fewer than 3 compensation cases. **Supported** if ≥ 2/3 of compensation cases have Δ ≥ +5 pp and
  (when there are at least 3 controls) the median Δ of compensation cases exceeds that of controls by ≥ 5 pp.
  **Refuted** if ≤ 1/3 have Δ ≥ +5 pp, or (with at least 3 controls) the median Δ of compensation cases does not
  exceed that of controls. Otherwise **inconclusive**.
* Secondary: Orb only.

### Descriptive, no decision

Orb's mean absolute error at 300 K and over the window on the blind materials graded for all three models, next to
MACE's and MatterSim's on the same materials.

## What the outcomes would mean

* **H1 supported:** the soft-bulk-modulus explanation for Orb generalises beyond the cases it was found on, and Orb's
  static K is a usable predictor of its α error. **Refuted:** it was specific to GaAs and InP; Orb's errors elsewhere
  come from γ (or from numerics).
* **H2 supported:** confirms, on materials chosen in advance, the study's warning that K′ is not a screening shortcut
  for Orb. **Refuted:** K′ is more useful than the Ta counterexample suggested.
* **H3 supported:** model disagreement is a cheap error signal worth reporting in the benchmark. **Refuted:** errors are
  shared across models (e.g. inherited from training data or PBE), so agreement does not imply accuracy.
* **H4 supported:** "right at 300 K" is not evidence of right physics; window grades matter. **Refuted:** compensation
  at 300 K tends to persist across the window.

None of these outcomes changes the benchmark's grading rules or thresholds, which stay as registered on 2026-10-17.

---

## Results (added after the run)

*Not yet run.*
