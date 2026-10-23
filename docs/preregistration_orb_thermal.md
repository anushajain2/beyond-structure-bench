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

## Amendment 1 (2026-10-23, before the run): run scope

Written after a timing probe and before any blind result existed. The probe was InP, an already-seen study case: 12
displacements × 9 volumes, 81 s, ≈ 2.7 k neighbour pairs/s. It showed the full run would take 12–14 h on the laptop
CPU, not the 4–5 h assumed earlier. Orb's slightly broken symmetry multiplies the displacements; Y₂O₃ alone needs
about 240, roughly 4 h. The scope is therefore split by cost, without reference to any result:

* **Core run (now), 22 materials:** the 14 blind materials gradable at 300 K except Y₂O₃ (SiO₂ quartz, Al₂O₃, MgO, Al,
  W, Co, Ru, Mo, Ti, TiN, CoSi₂, NiSi, TiSi₂, WSi₂); the six seen semiconductors still stale (Si, Ge, SiC, GaAs, GaN,
  AlN); and Cu and Ta. InP is the probe, run with the registered settings and code. Settings, exclusions and
  references are unchanged.
* **Deferred, 10 materials,** run later for benchmark coverage: Y₂O₃, β-Si₃N₄, TaN, ZrO₂, HfO₂, TiO₂ (rutile), SrTiO₃,
  MoS₂, hBN, graphite. Y₂O₃ is the only blind material gradable at 300 K among them. Si₃N₄ and TaN are blind but
  gradable over the window only, so they enter only window secondaries. The rest are seen or cannot be graded for Orb.
* **Verdicts come from the core run only.** The primary blind set becomes the 22 blind materials minus Y₂O₃, of which
  at most 14 are gradable at 300 K. When the deferred materials are run, their results are reported as an addendum,
  with the tests recomputed for information; the verdicts are not revised.
* **Operational:** the core run uses two worker processes at once, each running one material per process as
  `chipff qha` does. A driver outside `src/` serialises writes to `results/raw/orb-v3/thermal_qha.json` with a file
  lock. `save_raw` is not part of the code fingerprint, so this changes neither numbers nor fingerprints.
* `scripts/prereg_orb_thermal_eval.py` restricts Orb to the core materials by default (`--all` lifts it for the
  addendum); MACE and MatterSim rows are used for all materials, as registered.

---

## Results (added after the run)

Written 2026-10-23, after the core run. Nothing above the line was changed. Numbers are from
`results/thermal_expansion.csv` and `results/bulk_modulus.csv` after `chipff analyze`, evaluated by
`scripts/prereg_orb_thermal_eval.py`; the full output, per material, is `results/preregistration_orb_thermal.json`.

### Verdicts

| | primary set | statistic | verdict |
|---|---|---|---|
| **H1** K error explains Orb's α error | blind, 12 graded, 6 with \|err\| > 20 % | 4 of 6 explained (exactly 2/3) | **supported** (at the threshold) |
| **H2** K′ does not flag large errors | blind, 13 graded | only 1 large error (Al) | **inconclusive** (< 2 large errors) |
| **H3** disagreement tracks ensemble error | blind, 14 | ρ = 0.24, p = 0.21 | **inconclusive** |
| **H4** compensation degrades over the window | pooled, 6 compensation / 14 control | 2 of 6 grow by ≥ 5 pp; median Δ 3.6 vs 15.8 pp | **refuted** |

### What happened in the run

* **Coverage:** all 22 core materials and the InP probe finished. Their fingerprints match the current code
  (`54a9adeb998ccd45`), so `results/checks.csv` passes the fingerprint check for all 23. Orb is now at 23/33 for
  thermal expansion and stays "pending" in the benchmark-wide tables until the 10 deferred materials are run.
* **Failed checks:** MgO and Al failed `volume_inside_scan`, so their window values are excluded. Under the
  benchmark's rule, which this test registered unchanged, they are still graded at 300 K.
* **Al is a QHA breakdown, not a thermal expansion.** Orb's Al is dynamically unstable from 1.03 V0 upward (lowest
  mode −0.6 to −2.2 THz), so only the five volumes 0.96–1.015 V0 enter the fit. The 300 K volume then lies outside
  them and α(300 K) comes out as 9088 × 10⁻⁶ K⁻¹ (+12 950 %). MACE and MatterSim keep all nine volumes for Al. The
  rules grade this value, so it stays in every test. Where it matters, the result without Al is given below, for
  information only.

### H1: supported, at the threshold

Primary, blind materials with |err_300K| > 20 % (`p` = what the bulk-modulus error alone predicts):

| material | err_300K | K error | K-only prediction p | share p/e | explained |
|---|---|---|---|---|---|
| W | +20.5 % | −19.9 % | +24.8 % | 1.19 | yes |
| Ru | +28.6 % | −17.0 % | +20.5 % | 0.74 | yes |
| Mo | +38.0 % | −17.2 % | +20.8 % | 0.59 | yes |
| Ti | +22.0 % | −11.3 % | +12.8 % | 0.60 | yes |
| MgO | +21.9 % | −7.0 % | +7.5 % | 0.37 | no |
| Al | +12 950 % | +6.8 % | −6.4 % | — | no (breakdown) |

Four of six are explained, which is exactly the 2/3 the rule requires. The support is narrow and specific:

* All four explained cases are transition metals whose static K is 11–20 % soft. In those, Orb's overshoot follows
  the K error in sign and rough size, as the study found for GaAs and InP.
* Excluding Al gives 4 of 5. Reading MgO's +22 % as just above the threshold, rather than as an error to explain,
  would not change the verdict either.
* The rule does not test the reverse direction, and that direction fails: a soft K does not reliably produce an
  overshoot. Quartz has K 25 % soft but α 15 % low; Al₂O₃ and Co have K 9 % and 4 % soft with α −2 % and −20 %.
  Over all 12 graded blind materials, the Spearman correlation of `p` with `e` is 0.06.
* Window secondary: 2 of 5 explained.

So the bulk-modulus explanation carries over to Orb's overshoots in the transition metals. It is not a general
predictor of Orb's α error.

**Semiconductors (seen, cannot decide):** 4 have |err| > 20 %. Ge and GaAs are explained (shares 0.62, 1.15). InP
(0.47) and AlN (0.43) fall just short of the 0.5 share, so the check gives 2 of 4, inconclusive. The study attributed
about two-thirds of InP's error to K using the QHA's K_T at 300 K. With the static K this test registered, K's share is
a little under half. That is consistent with the study, not a contradiction of it.

### H2: inconclusive (too few large errors)

* **Primary:** only one blind material has |err| > 40 %, and it is Al, the breakdown. Al also has by far the highest
  K′ (7.91; next highest TiSi₂ 5.42, Ru 4.79). So K′ does single out the one material where Orb's equation of state is
  abnormal, but one case cannot be scored.
* **All graded (secondary):** AUC = 0.69, p = 0.13, inconclusive. The fixed flag K′ > 5 gives 1 hit (Al), 2 false
  alarms (Cu, TiSi₂) and 3 misses (Ge +52 %, InP +48 %, Ta +70 %).
* **Without Al (information):** AUC = 0.59, p = 0.33, which meets "no better than chance". With the v1.1.0 references
  it is AUC = 0.63, p = 0.27, the same.

The direction is the one H2 predicted: K′ misses Orb's large semiconductor and Ta errors. The registered test is not
decisive.

### H3: inconclusive

* **Primary:** ρ(D, E) = 0.24, p = 0.21, n = 14. Without Al ρ = 0.05. Against E′, the MACE–MatterSim mean's own error
  with no shared term, ρ = 0.06.
* **Secondaries:** all materials ρ = 0.23, p = 0.14 (n = 23). Window, blind: ρ = −0.19, n = 8, which the rule would call
  refuted, but it is a secondary.
* **Pattern:** on several blind materials Orb agrees closely with the other two models (D < 0.05), and the shared
  answer is wrong by 17–36 %: Mo, Ru, Co, W, MgO. Al₂O₃ is the one blind case where the three agree and are right.

So there is no evidence that Orb's disagreement signals error, and agreement between the three models does not imply
accuracy.

### H4: refuted (partly prospective)

**Compensation cases**, right at 300 K with the non-K ingredients offsetting ≥ 15 % of the K effect:

| model, material | err_300K | err_window | Δ |
|---|---|---|---|
| Orb, Si | −3.2 % | −3.8 % | +0.6 pp |
| Orb, SiO₂ quartz | −15.4 % | −63.9 % | +48.5 pp |
| Orb, TiSi₂ | −12.4 % | +16.6 % | +4.2 pp |
| MACE, InP | −12.1 % | +5.3 % | −6.8 pp |
| MatterSim, Mo | −8.1 % | −34.9 % | +26.8 pp |
| MatterSim, TiSi₂ | −5.6 % | +8.6 % | +3.1 pp |

* Two of six grow by ≥ 5 pp, and the median Δ of compensation cases (3.6 pp) is below the controls' (15.8 pp, n = 14),
  so H4 is refuted on both counts. Orb only (secondary) gives the same: 1 of 3.
* The controls grow more than the compensation cases. That growth is mostly the oxides: Al₂O₃ for all three models,
  and Y₂O₃ for MACE and MatterSim. Errors growing with temperature look like a property of the oxides' windows, not
  of cancellation.
* **Limits:** compensation is identified from the static K alone, without γ. MACE's Si, the case that motivated H4,
  counts as a control here: its K residual is just under the 15 % cut-off. MACE's and MatterSim's curves were seen
  before registration.

### Descriptive (no decision)

On the 13 blind materials graded at 300 K for all three models, excluding Al:

| | Orb v3 | MACE-MPA-0 | MatterSim v1 |
|---|---|---|---|
| mean abs error, 300 K | 17.0 % | 31.1 % | 21.1 % |
| mean abs error, window (8 materials) | 25.0 % | 38.0 % | 26.7 % |

With Al included, Orb's 300 K mean is 941 %; its 300 K median absolute error on the 14 blind materials is 17.5 %.

### Deviations from the plan

1. **Scope** (Amendment 1, registered before the run): 22 core materials. The 10 deferred ones are not yet run.
2. **Memory, operational.** The first launch of the two workers leaked memory. `Engine.forces` builds a fresh jitted
   propagator per call and JAX kept every compiled program; quartz reached 28 GB. Both workers were stopped before
   any result was saved. The relaunch clears JAX's in-memory caches after each force call. That change sits in the
   driver (`scripts/qha_worker_lowmem.py`), outside `src/`. The code fingerprint was computed from the unpatched sources and checked equal to the
   InP probe's. A watchdog killed any process above 8 GB.
3. **Al₂O₃ contingency.** The watchdog killed Al₂O₃ once at 8.9 GB: a transient peak during force calls, not a
   leak. The registered contingency was a rerun with a smaller `max_pairs_per_call`. That would have done nothing,
   since Al₂O₃ already runs one supercell per call. It was instead rerun once with the same settings and a 12 GB
   limit, plus a floor of 15 % free system memory, alongside one other worker; it finished at a 9.1 GB peak. The
   driver also counted relaxations, volumes and force calls for diagnostics, without effect on the computation.
4. **Script and text agree;** no disagreement was found.
5. **References changed on `main` during the run.** `main` v1.1.0 (ae2f1ea) audits the references. InP's and NiSi's
   expansion references become range averages and lose their 300 K value, and HfO₂/ZrO₂ expansion moves to an
   extended tier. Re-evaluated with those references, with the same Orb raw results (not stale there), every primary
   verdict is unchanged: H1 supported (4 of 6), H2 inconclusive, H3 inconclusive (ρ = 0.23, n = 13), H4 refuted (2 of
   5). The only secondary that changes is H2 on all graded materials, from inconclusive to "no better than chance"
   (AUC 0.63). The Orb-only H4 now has too few controls for the median comparison and is refuted on the growth
   fraction alone.

### What this does and does not establish

**Established, on materials chosen before their results existed:**

* Orb's transition-metal overshoots follow its soft static bulk modulus (H1, at the threshold).
* Static K′ caught the one blind case where Orb's equation of state is abnormal, but missed Orb's largest seen
  errors.
* Model agreement is not evidence of accuracy (H3 gave no signal, and the five shared misses).
* "Right at 300 K through compensation" did not predict degradation over the window (H4).

**Not established:**

* None of this tests γ directly.
* The blind set is small: 12–14 materials, mostly metals and silicides, with two oxides at 300 K.
* H2 and H3 could not reach a decision.

**Follow-ups this raises:**

* The deferred 10 materials, for coverage.
* The benchmark's rule grading 300 K values from runs that failed `volume_inside_scan`. The rule is unchanged here,
  but Al shows it can grade a meaningless number.
