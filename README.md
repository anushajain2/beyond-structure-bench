# BeyondStructure Bench

[![tests](https://github.com/anushajain2/beyond-structure-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/anushajain2/beyond-structure-bench/actions/workflows/ci.yml)

**Can AI models that simulate atoms be trusted to predict how chip materials behave when they heat up?**

Designing chips increasingly relies on computer simulations of materials. A new kind of AI model, called a
machine-learned force field, can run these simulations thousands of times faster than traditional physics
calculations. This project checks how good the most widely used ones are: MACE-MPA-0, MatterSim, Orb v3 and Meta's UMA, including
two versions of UMA that differ only in the physics calculations they learned from.
It tests them on 33 materials found in chips, from silicon and copper to the oxides used as insulators. For each
material, each model predicts three things, and every prediction is compared with real laboratory measurements:

* **how big the material's crystal is**, that is, how far apart its atoms sit;
* **how stiff it is**, or how hard it is to squeeze;
* **how much it grows when it heats up**, its thermal expansion.

## What we found

**1. A model that gets a material's structure right can still get its behaviour wrong.**
Every model predicts the size of the crystals almost perfectly, usually within 1 %. But for the same materials,
their predictions of how much the material grows when it heats up are typically off by 15–40 %, and sometimes by a
factor of two or three. "Does the model get the structure right?" is the check these models are usually judged on.
Passing it is no evidence that a model can be trusted on heat. Heat matters for chips, which warm up and cool
down every time they run.

**2. The newer models are better, but every model has blind spots, and in different places.**
Orb v3 and UMA are the most accurate on average. Yet every model, including the best, gets some materials badly
wrong, and which materials depends on the model. One model is far off for tantalum, a metal used in chip wiring;
another for silicon itself. Even two releases of the same model can disagree on a particular material. So no model
can be trusted across the board: it has to be checked on the specific materials it will be used for (our
[guide](docs/model_guidance.md) does this for the 33 materials here).

**3. The models go wrong in one specific, identifiable way.**
The atoms in a solid are always vibrating, and the warmer it gets, the harder they vibrate. That pushes them apart,
which is why materials expand when heated. How much a material expands depends on how its vibrations change once
the atoms are a little further apart. The models get the vibrations themselves mostly right, but they misjudge how
those vibrations change as the material expands, so they predict too much or too little growth. Knowing where the
error sits tells model developers what to fix. The models need to learn from, and be tested on, crystals that are
slightly stretched or squeezed, not only crystals at rest.

**4. Better models and better training data can both fix these errors.**
These AI models learn by imitating a standard physics calculation (called DFT), so an error can come from the AI
model or from the calculation it copied. We checked both ways.
* We ran the calculation ourselves on the same materials. For most of the big errors, it is much closer to the
  right answer than the AI model is, so those errors are the model's own.
* We tested one model trained twice: once on the usual calculation, and once on a more accurate version (r2SCAN).
  The second version is the most accurate model in the benchmark on every property; its heating errors drop by about
  a third.
* It also fixed errors we had blamed on the model itself, such as tantalum's, so how a model is trained matters, not
  only which calculation it imitates.

Either way, the problems are fixable: with better models, and with better and broader training data.

**5. Small errors in single materials become big errors in a real chip.**
A chip is a stack of different materials bonded together. When it heats up, each layer tries to grow by a different
amount. That difference is what builds up the stress that can warp, crack or peel a chip. Predicting the
difference means getting two materials right at once, so errors add up.
* For 15 real layer combinations, the best models get the difference close (within 25 %) for about half to
  two-thirds of them. The weakest manage only a fifth to a third.
* Translated into stress, the typical miss ranges from about 100 to 550 MPa, depending on the model. That is
  a large error next to the stresses chip designers try to control.
* One model even gets the direction wrong for more than a third of them, predicting that the layers pull the
  opposite way to what really happens.
* A model can get a material's overall growth right and still get the direction wrong. Many crystals grow by
  different amounts sideways and upwards, and a layer on a chip only feels the sideways part. One model predicts
  ruthenium's overall growth within 6 %, but says it barely grows sideways at all.

**The bottom line:** today's AI models for atoms are excellent at predicting the structure of chip materials. They
should not be trusted, without checking, to predict how those materials respond to heat, and least of all when
several materials are stacked together.

**Which model should I use for my material?** See [`docs/model_guidance.md`](docs/model_guidance.md): for each of
the 33 materials, whether each model is reliable, usable or best avoided, and why. To add your own model, see
[`docs/adding_a_model.md`](docs/adding_a_model.md).

To make sure these conclusions were not shaped by hindsight, we ran three blind tests. We wrote down our
predictions about their mistakes before running them; some held and some did not, and we report both.

**[Project site](https://anushajain2.github.io/beyond-structure-bench/)** ·
[Explore the evidence](https://anushajain2.github.io/beyond-structure-bench/explore.html) ·
[Read the study](https://anushajain2.github.io/beyond-structure-bench/study.html) ·
[Evaluation design](https://anushajain2.github.io/beyond-structure-bench/design.html) ·
[Reproduce](https://anushajain2.github.io/beyond-structure-bench/reproduce.html)

## The same findings, in numbers

For readers who want the specifics. Each point matches the one above; technical terms are explained under
[Terms used here](#terms-used-here). The models are MACE-MPA-0, MatterSim v1, Orb v3 and three UMA releases: s-1.2,
and s-1.2.1 trained on PBE or fine-tuned to r2SCAN.

1. **Structure is easy, stiffness is harder and thermal expansion is hardest.** Mean absolute error against
   experiment, non-layered materials:

   | | MACE-MPA-0 | MatterSim | Orb v3 | UMA s-1.2 | UMA s-1.2.1 (PBE) | UMA s-1.2.1 (r2SCAN) |
   |---|---|---|---|---|---|---|
   | lattice constant | 0.74 % | 0.80 % | 0.73 % | 0.72 % | 0.72 % | 0.44 % |
   | bulk modulus | 10.8 % | 12.6 % | 12.0 % | 11.2 % | 9.9 % | 8.3 % |
   | thermal expansion, 300 K | 39.8 % | 24.3 % | 20.6 % | 18.8 % | 17.5 % | 13.5 % |
   | thermal expansion, window | 34.4 % | 32.6 % | 23.5 % | 23.2 % | 22.4 % | 14.4 % |

   Accuracy on structure does not predict accuracy on expansion. MACE-MPA-0 puts tantalum's lattice within 0.4 % and
   its bulk modulus within about 6 %, yet overestimates its thermal expansion by 179 %.
2. **No model is best everywhere.**
   * Orb v3 and the UMA models are significantly more accurate than MACE-MPA-0 at 300 K (paired bootstrap); the
     r2SCAN UMA is also more accurate than MatterSim. The data cannot separate Orb and the three UMAs from each other.
   * Blind spots differ by model:
     * MACE-MPA-0: refractory metals (Ta +179 %, Mo +97 %);
     * MatterSim: semiconductors (Si +85 %, GaAs +68 %);
     * Orb v3 and UMA s-1.2: germanium (+52 %, +54 %) and tantalum (+70 %, +45 %).
   * Two PBE releases of UMA (s-1.2 and s-1.2.1) are similar on average but differ on single materials.
   * Per material: [`docs/model_guidance.md`](docs/model_guidance.md).
3. **The large expansion errors come from how the atoms' vibrations change with volume.** A material's thermal
   expansion is set mainly by its stiffness and its Grüneisen parameter, which measures how much the vibration
   frequencies shift as the crystal expands. In the worst cases, heat capacity, volume and often stiffness are right,
   and the Grüneisen parameter is wrong. Tantalum is the clearest example: MACE-MPA-0's Grüneisen parameter is 4.1
   against 1.6 from experiment, with a roughly correct stiffness. For some semiconductors, a too-soft bulk modulus adds
   to the error. The six cases studied in depth were picked after the failures were seen, so they explain those
   failures rather than prove a general rule.
4. **Model error and training physics both matter.**
   * Matched PBE references (our own for Si and GaAs; published ones for Cu, Ta, Ru, Mo and MgO) separate a model's
     error from the DFT method's:
     * the models' own: MACE-MPA-0's Ta and GaAs, MatterSim's Si and GaAs, and the Ru overshoots, where PBE itself is
       right;
     * inherited from PBE: the too-soft semiconductors (PBE makes Si and GaAs 12–18 % too soft), including all of Orb
       v3's GaAs error.
   * A pre-registered test on UMA s-1.2.1, PBE-trained against r2SCAN-fine-tuned
     ([details](docs/preregistration_r2scan.md)), went as predicted for the inherited errors:
     * semiconductor bulk-modulus error went from −15 % to −5 %;
     * their expansion error fell by 31 %;
     * lattices went from +0.61 % to −0.31 %;
     * MgO, the one miss all the earlier models shared, went from +20 % to +3 %.
   * Against the prediction, it also cut tantalum's overshoot from +61 % to +7 %. So the fine-tune changes more than
     the labels, or some of tantalum's error was PBE's after all.
5. **Chip-stack thermal mismatch is harder than either material alone.** Across 15 device stacks (metals, silicides,
   barriers, oxides, and GaN and AlN on their substrates), the free expansion mismatch from 300 to 900 K is compared
   with the one built from measured expansion. It uses in-plane expansion for GaN, AlN, Ru and Al₂O₃ films. The
   implied thermal stress uses each film's biaxial modulus.

   | at 900 K | MACE-MPA-0 | MatterSim | Orb v3 | UMA s-1.2 | UMA s-1.2.1 (PBE) | UMA s-1.2.1 (r2SCAN) |
   |---|---|---|---|---|---|---|
   | right sign | 13 of 13 | 9 of 15 | 15 of 15 | 15 of 15 | 14 of 15 | 13 of 13 |
   | within 25 % | 3 | 5 | 5 | 10 | 6 | 7 |
   | median stress miss | 440 MPa | 570 MPa | 240 MPa | 150 MPa | 160 MPa | 100 MPa |

   The volume can hide the direction. MatterSim gets ruthenium's volume expansion within 6 %, but its in-plane
   expansion is 0.1 against 5.8 × 10⁻⁶ K⁻¹ measured, which flips the sign of Ru on Si. The axial expansion
   (`results/thermal_axial.csv`) reproduces each model's volume expansion within −8 to +12 %.
6. **Three blind tests, with predictions and decision rules committed before the runs** (Orb v3, UMA s-1.2, and the
   UMA PBE/r2SCAN pair).
   * Supported:
     * Orb v3's overshoots in transition metals follow its too-soft bulk modulus;
     * a model with accurate silicon gets the mismatch signs right;
     * UMA's errors resemble those of Orb v3, trained on the same data (suggestive, not decisive);
     * r2SCAN fixes the inherited errors.
   * Refuted:
     * that results right at 300 K through cancelling errors degrade at high temperature;
     * that r2SCAN would leave tantalum's overshoot in place.
   * Not confirmed: that where existing models disagree, a new model will also fail.

Averages leave out layered materials such as graphite. Every model whose relaxation converges overestimates graphite's
layer spacing, by 18–41 %. Every number here comes from the committed tables in `results/` and is detailed below and
in [`docs/details.md`](docs/details.md#findings-in-detail).

## What it measures

| Property | In everyday terms | Why it matters for chips |
|---|---|---|
| **Lattice constant** | The size of the crystal's repeating unit: how far apart the atoms sit | Layers grown on top of each other need to fit; a model that gets the size wrong gets everything built on it wrong |
| **Bulk modulus** | How hard the material is to squeeze; a higher value means stiffer | Sets how much a layer pushes back when its neighbours strain it |
| **Thermal expansion** | How much the material grows when it heats up | Chips heat and cool constantly; layers that expand by different amounts build up stress, which can bend, crack or peel them |

The three properties get harder to predict in turn. Crystal size
depends only on where the atoms sit at rest. Stiffness depends on how the energy changes when the
crystal is squeezed. Thermal expansion depends on how the atoms' vibrations change as the crystal grows,
a subtler feature of the model that structure and stiffness don't test. So the benchmark asks whether
accuracy on the easier properties carries over to the harder one.

The 33 materials fall into five groups: semiconductors, insulators and dielectrics, wiring and contact
metals, barriers and silicides, and layered (2D) materials such as graphite. Exact definitions, units and
methods are in [`docs/details.md`](docs/details.md#whats-measured).

## What it adds

* **Thermal expansion against experiment.** Force-field benchmarks mostly test structure and stiffness,
  often against DFT alone. The two closest benchmarks for these kinds of materials,
  [CHIPS-FF](https://arxiv.org/abs/2412.10516) and [UniFFBench](https://arxiv.org/abs/2508.05762), don't
  report thermal expansion against experiment. This one does, for six models: 22–23 materials at 300 K
  and 18–20 over each material's temperature window.
* **Evidence that accuracy doesn't carry over between properties.** A model can get a crystal's size
  and stiffness right and its thermal expansion badly wrong: MACE-MPA-0 puts tantalum's lattice within
  0.4 % and its bulk modulus within about 6 %, yet overestimates its thermal expansion by 179 %.
* **An explanation for six of the largest failures**, separating model error from software and
  numerical artefacts, and, with matched PBE references, from errors inherited from the DFT the models learned
  from.
* **A controlled test of the training physics.** The same UMA release trained on PBE and fine-tuned to r2SCAN,
  compared property by property ([details](docs/preregistration_r2scan.md)).
* **Blind tests.** Orb v3, UMA and the PBE/r2SCAN pair were run only after predictions about their errors, and the
  rules for judging them, had been committed ([Orb](docs/preregistration_orb_thermal.md),
  [UMA](docs/preregistration_uma.md), [r2SCAN](docs/preregistration_r2scan.md)), so those conclusions were not fitted
  to the results.
* **Thermal mismatch and stress of real chip stacks** (16 metal, silicide, barrier, oxide and GaN stacks), using
  in-plane expansion where it differs from the average. This is the quantity that actually strains a device, not
  just each material on its own.
* **Sourced, audited reference data.** Every experimental value comes with its citation and a verbatim
  quote, and is audited into a *core* tier (primary measurements and trusted compilations) or an
  *extended* tier, with its own uncertainty. The 462 values are released as a standalone dataset
  ([`data/release/`](data/release/README.md)) that others can reuse without the rest of the code.

## What it doesn't tell you

This is not a general verdict on whether ML force fields can be trusted for chip materials. It covers
three bulk properties, six models (four families) and perfect crystals. Real chip layers are thin films with
interfaces, defects and often disordered structure, and many properties that matter for devices, such as
heat conduction, diffusion and adhesion, are not tested. The results say how these models do on these
properties; for anything else they are at most a warning sign.

## How it works

1. **Pick the materials:** 33 materials with a role in semiconductor devices (`data/materials.yaml`).
2. **Run the models:** each force field finds every crystal's preferred shape, then simulates squeezing it
   and how its atoms vibrate.
   Most calculations run through CuspAI's open-source [kUPS](https://github.com/cusp-ai-oss/kups)
   toolkit; MatterSim runs through its official package, because its kUPS version gives inconsistent
   energies ([details](docs/details.md#findings-in-detail)), and UMA through Meta's `fairchem`, because kUPS's
   UMA bridge needs a GPU.
3. **Compute the three properties** from those simulations.
4. **Compare with references:** sourced lab measurements for every material, each with a citation and a
   quote, and DFT values from [Materials Project](https://materialsproject.org) where they exist.
5. **Analyse the errors:** statistics with uncertainty, documented exclusions, checks that the
   results don't depend on arbitrary settings, and a detailed study of the worst failures.

## The evidence

![Average error of each model by material group and property](report/figures/trust_map_experiment.png)

*Average error against lab measurements, by material group (rows), property and model (columns).
Green, amber and red use thresholds fixed before any result was seen (lattice constant good ≤ 1 %,
okay ≤ 3 %; bulk modulus good ≤ 10 %, okay ≤ 25 %; thermal expansion good ≤ 20 %, okay ≤ 40 %).
"n/a" means the value was computed but not graded, because the method does not apply to layered
materials. It is not a score.
Numbers: [`results/trust_map.csv`](results/trust_map.csv). \*MatterSim and UMA run through their
official packages, not kUPS.*

The numbers behind each finding are summarised under
[The same findings, in numbers](#the-same-findings-in-numbers), and in full, with confidence intervals and sample
sizes, in [`docs/details.md`](docs/details.md#findings-in-detail).

![Thermal-expansion error at 300 K by material and model](report/figures/study_errors.png)

*Thermal-expansion error at 300 K against experiment in the six-case study. Each bar is the spread
across three volume-scan settings: a sensitivity range, not a confidence interval. \*MatterSim runs
through its official package, not kUPS.*

**Why the expansion errors happen.** How much a material expands depends mainly on its stiffness and its Grüneisen
parameter, which measures how strongly its vibrations change as the crystal expands.
* In six cases (Si, GaAs, InP, Cu, Ta and HfO₂), checks of the software and numerical settings did not explain the
  large errors. They trace to the models' Grüneisen parameters, with a too-soft bulk modulus adding to it for several
  semiconductors. For tantalum, MACE-MPA-0's Grüneisen parameter is 4.1, against 1.6 inferred from experiment.
* The six cases were chosen after the failures were seen, so the study explains them; it does not establish a general
  rule.
* Three later tests were fixed in advance:
  * [Orb v3](docs/preregistration_orb_thermal.md): Orb's overshoots in transition metals follow its too-soft bulk
    modulus;
  * [UMA](docs/preregistration_uma.md): a model with accurate silicon gets chip-stack mismatch signs right;
  * [PBE vs r2SCAN](docs/preregistration_r2scan.md): training on more accurate physics fixes the inherited errors,
    and tantalum's too.

**Model error or training physics.** The models learned from PBE calculations.
* Matched PBE references separate what a model gets wrong from what PBE itself gets wrong
  ([section 7 of the study](docs/thermal_failure_study.md#7-model-error-or-inherited-from-pbe)).
* The UMA r2SCAN test changes the training physics while holding the model fixed.

**Chip stacks.** Mismatch is an ingredient of thermal stress, not a prediction of it: stress also depends on
geometry, constraint and elastic response. The stacks were chosen by device role before their mismatch was computed
([`results/thermal_mismatch.csv`](results/thermal_mismatch.csv),
[`results/thermal_mismatch_summary.csv`](results/thermal_mismatch_summary.csv),
[`results/thermal_axial.csv`](results/thermal_axial.csv)).

Every number comes from the committed tables in `results/`.

## What this release covers

| Scope | Coverage |
|---|---|
| Lattice constant and bulk modulus | All six models (MACE-MPA-0, Orb v3, MatterSim v1, UMA s-1.2, UMA s-1.2.1 PBE and r2SCAN) on all 33 materials, with exclusions and their reasons |
| Thermal expansion, benchmark-wide | All six models on all 33 materials; 22–23 graded comparisons per model at 300 K, 18–20 over the temperature windows. Orb v3 and the UMA models were added after v1.1.0, as pre-registered tests. |
| Axial (in-plane and vertical) expansion | All six models on GaN, AlN, Ru and Al₂O₃, against axis-resolved measurements |
| Chip-stack mismatch and stress | 16 device stacks, 15 with references covering 300–900 K |
| Thermal-failure study | MACE-MPA-0, MatterSim v1 and Orb v3 on six selected materials (Si, GaAs, InP, Cu, Ta, HfO₂) |
| UMA | Run through Meta's `fairchem` package (kUPS's UMA bridge needs a GPU), like MatterSim through its own package |

Not every result can be graded, so coverage is reported next to accuracy
([`results/coverage.csv`](results/coverage.csv)). Each model–material–property result is one of:

* **Graded:** the model gave a valid answer and it is compared with the reference.
* **Model failure:** the model gave an answer that can't be compared, for example Orb changes the crystal
  form of 3 of the 33 materials. These are findings in their own right and are left out of the averages.
* **Method limit:** the calculation method itself doesn't apply, for example thermal expansion of layered
  materials, which grow differently in different directions, or at temperatures where the method breaks down.
* **No reference:** there is no trustworthy lab measurement to compare with.
* **Not computed:** the calculation was not run (no current case among the six models).

Every reference is also tiered (`data/reference_quality.yaml`), and the statistics are reported both for
all graded references and for core-tier references only; the main conclusions hold for both, and the few
paired differences that depend on the subset are flagged where they are stated.

## Terms used here

<details>
<summary>Short explanations of the scientific terms (click to expand)</summary>

* **Force field:** a model of how atoms push and pull on each other, used to simulate how a material
  behaves. A **machine-learned (ML)** force field learns this from many quantum-mechanical calculations;
  a **universal** one is meant to work across most of the periodic table rather than for one material.
* **DFT (density functional theory):** the standard quantum-mechanical way to calculate material
  properties. Accurate but slow; it is what ML force fields are trained to imitate.
* **PBE:** the specific DFT approximation behind most training data. It is known to make crystals about
  1 % too large and to miss the weak forces that hold layered materials together.
* **Materials Project:** a public database of DFT calculations, used here as the DFT reference.
* **kUPS:** CuspAI's open-source toolkit for running simulations with these models.
* **Layered (2D) materials:** materials such as graphite, made of sheets held together by weak van der
  Waals forces. PBE misses those forces, so models trained on it get the spacing between sheets wrong.
* **Phonons:** the collective vibrations of atoms in a crystal. Heat is stored in them, and how they
  change with volume decides how much a material expands.
* **Quasi-harmonic approximation (QHA):** the method used here to compute thermal expansion: calculate
  the vibrations at several crystal sizes and find which size is preferred at each temperature
  ([why this method](docs/thermal_method.md)).
* **Grüneisen parameter:** how strongly a material's vibration frequencies change when it expands or is
  squeezed. Too large a value means too much thermal expansion.
* **Barostat:** the part of a simulation that holds pressure constant by letting the crystal change size.
* **Mean absolute % error:** the average size of the error, ignoring whether it is too high or too low.
* **Bootstrap confidence interval:** an uncertainty range obtained by recomputing a result many times on
  random resamples of the materials. A **paired bootstrap** compares two models on the same resamples to
  see whether the difference between them is real or could be chance ([details](docs/robustness.md)).
* **Thermal mismatch:** the difference in how much two stacked layers grow between two temperatures, in
  microstrain (millionths of a length). Mismatch is what builds stress in a chip; this benchmark reports the
  free mismatch, before geometry and bonding turn it into stress.
* **Pre-registration (blind test):** writing down predictions and the exact rules for judging them, and
  committing them, before running the experiment, so the conclusions cannot be adjusted to fit the results.

</details>

## Who can use it

* **Choosing a force field for these materials:** the explorer shows each model's value next to the
  reference, with its source, error and any exclusion reason.
* **Building or evaluating force fields:** the study's per-ingredient comparisons and workflow checks
  show where to look when a property comes out wrong.
* **Reusing the references:** [`data/release/chipff_references.csv`](data/release/README.md) has 495
  sourced values with their conditions, tier and uncertainty.
* **Running kUPS:** two problems found in the toolkit are written up with reproducers in
  `docs/kups_issue_*_DRAFT.md`.

## Quick start

There are three ways in, from no setup at all to rerunning the simulations.

**1. Explore (no install).** The [site](https://anushajain2.github.io/beyond-structure-bench/), or the committed
tables in `results/` (`summary.json` and the CSVs) and `report/index.html`.

**2. Reanalyse (Python only, no simulations).** Rebuild every table and figure from the committed raw
results:

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
chipff analyze && chipff report
```

**3. Run simulations.** One model on one material, in about two minutes on a laptop CPU (measured on an
Apple-silicon MacBook). This recomputes the stored silicon results for MACE-MPA-0; they should agree
with the committed ones to about 0.2 %. kUPS logs "Fixing failed assertions" while it enlarges its
neighbour-list buffers; that is expected, not an error.

```bash
chipff static -m mace-mpa-0 --materials Si --force
chipff qha -m mace-mpa-0 --materials Si --force
chipff analyze
```

The full pipeline (roughly an hour on CPU for the static properties and one to two hours per model for
thermal expansion), the MatterSim environment and UMA access are on the
[Reproduce page](https://anushajain2.github.io/beyond-structure-bench/reproduce.html) and in
[`docs/details.md`](docs/details.md#reproduce).

## Scientific details and reproducibility

| What | Where |
|---|---|
| Full findings, methods and limits | [`docs/details.md`](docs/details.md) |
| Statistics and robustness checks | [`docs/robustness.md`](docs/robustness.md) |
| The six-case thermal-failure study | [`docs/thermal_failure_study.md`](docs/thermal_failure_study.md) |
| Why thermal expansion uses QHA, not molecular dynamics | [`docs/thermal_method.md`](docs/thermal_method.md) |
| Every setting, the pre-registered thresholds and rules, and dated changes | [`configs/benchmark.yaml`](configs/benchmark.yaml) |
| Experimental references, each with a source, citation and quote | [`data/experimental/`](data/experimental) |
| The audit of every reference: tier, kind of measurement, uncertainty | [`data/reference_quality.yaml`](data/reference_quality.yaml) |
| The references as one reusable table | [`data/release/`](data/release/README.md) |
| Absolute, strain and temperature-trend errors; thermal mismatch of 16 device stacks | [`results/thermal_metrics.csv`](results/thermal_metrics.csv), [`results/thermal_mismatch.csv`](results/thermal_mismatch.csv), [`results/thermal_mismatch_summary.csv`](results/thermal_mismatch_summary.csv) |
| Exact package versions | [`env/requirements-lock.txt`](env/requirements-lock.txt), [`env/requirements-mattersim-lock.txt`](env/requirements-mattersim-lock.txt) |
| Model files and checksums | [`configs/checkpoints.json`](configs/checkpoints.json), checked by `scripts/verify_checkpoints.py` |
| How each result is tied to the code and settings that made it | [`docs/provenance.md`](docs/provenance.md) |
| Automatic self-checks on every result | [`results/checks.csv`](results/checks.csv) |

**Related benchmarks.** [CHIPS-FF](https://arxiv.org/abs/2412.10516) compares 16 force fields with DFT
on 104 semiconductor-relevant materials, and [UniFFBench](https://arxiv.org/abs/2508.05762) compares
six with experiment on minerals. Neither reports thermal expansion against experiment.

**Agent interface.** `chipff-mcp` is a Model Context Protocol server that lets an AI assistant
retrieve the same evidence. Its answers are benchmark evidence, not calibrated error estimates.

## What changed in v1.1.0

After an outside review, the experimental references were audited and tiered. InP's and NiSi's expansion
references, which are averages over wide temperature ranges, are no longer used as 300 K values; HfO₂'s
and ZrO₂'s moved to the extended tier, because their volumes miss the change of the monoclinic angle.
Each reference's own uncertainty now feeds the statistics, and the thermal results gain absolute and
accumulated-strain errors, a temperature-trend check and a thermal-mismatch example. The 300 K averages
changed as a result (MACE 34.5 % → 36 %, MatterSim 28.7 % → 24 %). No calculation was rerun. The project
was also renamed from ChipFF Bench to BeyondStructure Bench; the Python package and command are still
`chipff`.

## Since v1.1.0

* **More models, each a pre-registered test.**
  * Orb v3's benchmark-wide thermal expansion, for all 33 materials.
  * UMA s-1.2, as a fourth model family.
  * The UMA s-1.2.1 PBE/r2SCAN pair, a controlled test of the training physics.
  * Write-ups: [Orb](docs/preregistration_orb_thermal.md), [UMA](docs/preregistration_uma.md),
    [r2SCAN](docs/preregistration_r2scan.md).
* **Chip stacks:**
  * thermal mismatch became a headline result (16 stacks), with the implied thermal stress;
  * in-plane expansion is used for GaN, AlN, Ru and Al₂O₃ films, from a new axial calculation (`chipff axial`).
* **References:**
  * HfO₂ and ZrO₂ now use the full measured expansion tensor (Haggerty et al. 2014), which includes the
    monoclinic-angle term the old axial data missed. With it, every model is within about 20 % for both over their
    windows; the earlier large HfO₂ discrepancy was mostly the reference.
  * β-Si₃N₄ gained a table covering 300 K.
* **Guidance:** [`docs/model_guidance.md`](docs/model_guidance.md) says which model to rely on for each material.
* **Rules and checks:**
  * a 300 K result is no longer graded when instability cut the volume scan short;
  * CI now checks that the published tables, and one recomputed result, reproduce.

## Citation

> A. Jain, *BeyondStructure Bench: how reliably universal machine-learned force fields predict the structure,
> stiffness and thermal expansion of semiconductor-device materials*, v1.1.0 (2026).
> https://github.com/anushajain2/beyond-structure-bench

## Licence

Code: MIT. Model weights keep their own licences (MIT, Apache-2.0, FAIR Chemistry License). This work uses
Meta's UMA under the FAIR Chemistry License; if you use its UMA results, please also cite Wood et al.,
*UMA: A Family of Universal Models for Atoms*, arXiv:2506.23971 (2025). Experimental
values are cited from the sources listed with each one. This is an independent project built on kUPS and
published model exports; it is not affiliated with or endorsed by CuspAI, Meta, Microsoft, Orbital
Materials or the MACE developers.
