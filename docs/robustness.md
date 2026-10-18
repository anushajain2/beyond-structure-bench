# How robust are ChipFF Bench's conclusions?

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
zero, we report the two models as **statistically tied**.

**Files.** `bootstrap_ci.csv` holds each model's mean error with its interval; `pairwise.csv`
holds every pair, the difference, its interval, P(A better) and a verdict. Layered materials
are left out of these tables because their errors are so large (60–130%) that they would
dominate the averages; they are reported separately.

**What it showed.** Against experiment, MACE, Orb and MatterSim are statistically tied for
both lattice constants and bulk moduli. Against DFT there are real differences: MatterSim
reproduces PBE lattice constants most closely, and Orb reproduces PBE bulk moduli more closely
than MACE.

## 2. Would a rerun give the same numbers? Determinism

Lattice constants and bulk moduli involve no randomness, so repeating a run adds no
information. We still check it: a subset is rerun from scratch in a differently composed
batch, and the result must match the stored value (`lattice_rerun_pct` in
`static_sensitivity.json`; tiny differences come only from floating-point summation order).

Thermal expansion does involve randomness: random starting velocities, and random thermostat
and barostat kicks. Each run reports a statistical error bar from block averaging. To test
whether those error bars are honest, we rerun six materials with two different random seeds
(`md_variants.csv`). Agreement within about two combined error bars means the error bars can
be trusted.

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
