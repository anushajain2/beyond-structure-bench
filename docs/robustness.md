# How robust are BeyondStructure Bench's conclusions?

A benchmark makes two kinds of claim: *how accurate* each model is, and *which model is
more accurate*. Both can be wrong for reasons that have nothing to do with the models: too
few materials to tell models apart, a result that depends on an arbitrary setting, or
noise in the simulation or in the reference values. This page explains what we check, why,
and where the results live. Everything here is recomputed by `chipff analyze`, or produced
by `chipff robustness`, and written to `results/robustness/`.

## 1. Are the differences between models real? Bootstrap confidence intervals

**The problem.** Each mean error is an average over roughly 25–30 materials. With so few,
a different but equally reasonable choice of materials could reorder the models. A ranking
by raw averages can therefore claim a winner where there is none.

**What we do.** We resample the materials with replacement 5,000 times and recompute every
mean absolute error. The middle 95% of those values is the confidence interval. In each draw
we also perturb every experimental reference by its typical uncertainty (1σ):

| Property | Reference uncertainty assumed |
|---|---|
| lattice constant | 0.1% |
| bulk modulus | 5% |
| thermal expansion | 10% |

These are typical scatters between independent measurements. To compare two models we use a
**paired** bootstrap: only materials both models have, resampled together, with the same
perturbed references for both. That gives a 95% interval on the *difference* of their errors
and the probability that model A is more accurate than model B. If the interval includes
zero, we report that the benchmark **does not resolve a difference** between the two models.
That is not evidence that they are equally accurate: it is a failure to reject "no difference",
not an equivalence test. The statistical-power paragraph below says how large a difference the
data could have detected.

**Files.** `bootstrap_ci.csv` holds each model's mean error with its interval; `pairwise.csv`
holds every pair, the difference, its interval, P(A better) and a verdict. Layered materials
are left out of these tables because their errors are so large (60–130%) that they would
dominate the averages; they are reported separately.

**Within each material class** (`pairwise_by_class.csv`) the same paired bootstrap is run per
class. With 5 classes x 3 model pairs there are 15 comparisons per property and reference, so about
one would look significant at 95% by chance alone. We therefore apply the Holm-Bonferroni correction
and only claim a difference whose adjusted p-value is below 0.05. Uncorrected "suggestive" results
are listed but not claimed.

**What it showed.** Against experiment, no difference between MACE, Orb and MatterSim is
resolved for lattice constants or bulk moduli, overall or within any class. Against DFT there are
real differences: MatterSim reproduces PBE most closely (lattices for semiconductors, dielectrics,
barriers; bulk moduli for semiconductors, metals, barriers), and Orb is closer than MACE for barrier
bulk moduli. Being closer to the training data does not make a model closer to experiment.

**Do the models make the same mistakes?** (`model_agreement.csv`) For each pair of models we
correlate their signed errors against experiment over the materials both have, with a bootstrap
95% interval. This separates two reasons why "closer to PBE" fails to mean "closer to experiment":

| property | MACE vs MatterSim | MACE vs Orb | Orb vs MatterSim |
|---|---|---|---|
| lattice constant | 0.88 (0.72 to 0.96) | 0.83 (0.65 to 0.93) | 0.95 (0.90 to 0.98) |
| bulk modulus | 0.11 (−0.21 to 0.42) | 0.19 (−0.17 to 0.53) | 0.61 (0.23 to 0.88) |
| thermal expansion, 300 K | −0.10 (−0.42 to 0.37) | Orb not computed | Orb not computed |
| thermal expansion, window | 0.23 (−0.29 to 0.73) | Orb not computed | Orb not computed |

- Lattice constants: strongly shared errors. This is consistent with the limits of the PBE
  reference and training data (plus the 0 K vs room-temperature mismatch), but correlation alone
  cannot separate the functional from shared training data, numerical choices or reference
  mismatches.
- Bulk moduli: the two models that track PBE closely (Orb, MatterSim) share their errors; MACE's
  correlate only weakly with theirs (sample correlation 0.11 and 0.19, intervals spanning zero).
  PBE's error is about as large as MACE's departure from PBE, so tracking PBE more closely does not
  make a model more accurate here.
- Thermal expansion: the sample correlation is small, with wide uncertainty (table above). The average of MACE and MatterSim has a 25.7%
  error at 300 K (against 34.5% and 28.7% alone). The models' relative disagreement correlates
  with that average's error (0.41 at 300 K, interval −0.06 to 0.78; 0.25 over the window, −0.13
  to 0.64). That is an exploratory warning signal, not a calibrated uncertainty estimate.

**Does disagreement predict error for the static properties?** Not in this data. For lattice
constants and bulk moduli the same correlation is −0.31 to +0.51 across model pairs, with every
interval spanning zero (`model_agreement.csv`). The MCP `check_material` tool compares lattice
constants and bulk moduli, so its disagreement flag is a heuristic that this benchmark does not
validate: agreement between models that share training data does not show they are right.

**Incomplete runs are not compared.** A model whose thermal run has not covered every material
(currently Orb v3: 7 of 33, computed before the Γ-mode fix and so also stale by provenance) is marked `pending` in
`results/thermal_expansion.csv` and left out of
the trust map, the bootstrap, the pairwise tests and the MCP rankings, so a partial sample cannot
look better or worse than a complete one.

**Statistical power.** With ~26-30 materials, differences of about 3-5 percentage points in
bulk-modulus error and about 0.1 points in lattice error can be resolved; within a class
(4-9 materials) only much larger ones. Smaller real differences appear as ties.

## 2. Would a rerun give the same numbers? Determinism

Lattice constants and bulk moduli involve no randomness, so repeating a run adds no
information. We still check it: a subset is rerun from scratch in a differently composed
batch, and the result must match the stored value (`lattice_rerun_pct` in
`static_sensitivity.json`; tiny differences come only from floating-point summation order).

Thermal expansion, as published, has no random element by design ([`thermal_method.md`](thermal_method.md)),
but it was not reproducible in practice until the Γ-mode fix. MatterSim's CPU forces differ by ~10⁻⁶ eV/Å
between processes, and before the fix that was enough to move α(300 K) by several percent. With the
acoustic modes at Γ excluded, repeated runs agree to 0.1 % ([`thermal_failure_study.md`](thermal_failure_study.md)).
Its sensitivity to settings was tested on six cases: ≤ 2 % for displacement size and supercell size (MACE
InP +7 %), and up to 9–12 % for the volume range. The MD route, kept
as a cross-check, does involve randomness (starting velocities, thermostat and barostat kicks);
for it, six materials are rerun with two other random seeds (`md_variants.csv`), and agreement
within about two combined error bars means its error bars can be trusted.

## 3. Do the results depend on arbitrary settings? Sensitivity tests

Every simulation involves choices that should not matter. If they do, the result reflects
the setting rather than the model. On a representative subset of eight materials (Si, GaN,
Cu, W, HfO2, TiN, Al2O3, NiSi; one or more per class, layered materials excluded) we change
one setting at a time:

| Test | Changed | Should be |
|---|---|---|
| strain size | elastic tensor from only ±0.5% or only ±1% strains (normally both) | K within ~2% |
| force tolerance | 10x tighter (10⁻⁴ eV/Å) for lattice and elastic relaxations | lattice within ~0.01%, K within ~1% |
| starting cell | start 3% compressed or 3% expanded in volume | same relaxed lattice |
| supercell size (MD) | 14 Å instead of 10 Å, for Si, Cu and MgO | α_V within error bars |
| time step (MD) | halved, for Si, Cu and MgO | α_V within error bars |

**Files.** `static_sensitivity.json` holds the first three, as percentage changes from the
main result; `md_variants.csv` holds the MD ones, as differences in units of the combined
error bar.

**What it showed (static).** Over 8 materials and 3 models the largest changes were 0.002% in
lattice constant (rerun, tighter tolerance, compressed or expanded start) and 0.49% in bulk
modulus (strain size; 0.05% for the tighter tolerance), far inside the bands above and two to
three orders of magnitude below the errors being measured. A rerun reproduced every lattice
constant exactly.

## 4. What these checks do not cover

* **Which materials are in the benchmark.** The bootstrap asks how much the conclusions
  depend on *this* sample of materials; it cannot make 33 materials represent every possible
  chip material.
* **Systematic errors in the references.** The reference perturbation covers random scatter,
  not a bias shared by all measurements of a material.
* **Training-data overlap.** The models have likely seen these materials' DFT data, so the
  comparison against DFT is optimistic; see the paper's "Threats to validity".

## Why not pass@k?

pass@k measures how often a *stochastic* system (such as a language model writing code)
succeeds in k attempts. Force-field predictions of static properties are deterministic, so
repeated attempts are identical. The analogous questions are the ones above: would a rerun
agree (determinism and seeds), would different reasonable settings agree (sensitivity), and
would a different sample of materials agree (bootstrap).
