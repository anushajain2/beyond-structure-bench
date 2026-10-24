# BeyondStructure Bench

[![tests](https://github.com/anushajain2/beyond-structure-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/anushajain2/beyond-structure-bench/actions/workflows/ci.yml)

**Can AI models that simulate atoms be trusted to predict how chip materials behave when they heat up?**

Designing chips increasingly relies on computer simulations of materials. A new kind of AI model, called a
machine-learned force field, can run these simulations thousands of times faster than traditional physics
calculations. This project checks how good four widely used ones are: MACE-MPA-0, MatterSim, Orb v3 and Meta's UMA.
It tests them on 33 materials found in chips, from silicon and copper to the oxides used as insulators. For each
material, each model predicts three things, and every prediction is compared with real laboratory measurements:

* **how big the material's crystal is**, that is, how far apart its atoms sit;
* **how stiff it is**, or how hard it is to squeeze;
* **how much it grows when it heats up**, its thermal expansion.

## What we found, in short

1. **The models get the crystal structure almost exactly right,** usually within 1 % of the lab value.
2. **They are much less accurate about heating.** Their predictions of how much a material grows when heated are
   typically off by 20–35 %, and for some materials by a factor of two or three. Getting the structure right is no
   guarantee: one model gets tantalum's crystal size right to within 0.4 %, but predicts that it grows almost three
   times as much as it really does.
3. **This matters most where materials meet.** A chip is a stack of layers. When neighbouring layers grow by
   different amounts, they push and pull on each other, which can bend, crack or peel them.
   * For 15 real combinations of layers, the best model (UMA) predicts this mismatch to within 25 % for about half
     of them. The others manage at most 4 of the 15.
   * One model gets even the direction wrong for a third of them.
4. **Most of the big mistakes are the AI models' own.** The models learn from a standard physics method (DFT). We
   ran that method ourselves on some of the same materials and compared. For most of the large errors we could
   check, the AI model introduced the error rather than inheriting it, so better models could fix them.
5. **Newer models do better, but none is reliable everywhere.** Orb v3 and UMA are the most accurate about heating
   on average. Still, every model fails badly on some materials, and different models fail on different ones.

For two of the models we wrote down our predictions about their mistakes before running them. That way the
conclusions could not be bent to fit the results.

**[Project site](https://anushajain2.github.io/beyond-structure-bench/)** ·
[Explore the evidence](https://anushajain2.github.io/beyond-structure-bench/explore.html) ·
[Read the study](https://anushajain2.github.io/beyond-structure-bench/study.html) ·
[Evaluation design](https://anushajain2.github.io/beyond-structure-bench/design.html) ·
[Reproduce](https://anushajain2.github.io/beyond-structure-bench/reproduce.html)

## The key findings in more detail

1. **Structure is easy, stiffness is harder and thermal expansion is hardest.** Averaged over the 30 non-layered
   materials:
   * lattice constant: 0.7–0.8 % off for all four models;
   * bulk modulus: 11–13 %;
   * volumetric thermal expansion at 300 K: MACE-MPA-0 36 %, MatterSim 24 %, Orb v3 21 % and UMA 19 %.

   Accuracy on structure does not predict accuracy on expansion. MACE-MPA-0 puts tantalum's lattice within 0.4 % and
   its bulk modulus within about 6 %, yet overestimates its thermal expansion by 179 %.
2. **No model is best everywhere.**
   * Orb v3 and UMA are significantly more accurate than MACE-MPA-0 at 300 K. The data cannot separate them from
     each other or from MatterSim.
   * On structure and stiffness, the four models are nearly indistinguishable.
   * Each has its own blind spots: MACE-MPA-0 on refractory metals (Ta +179 %, Mo +97 %), MatterSim on
     semiconductors (Si +85 %, GaAs +68 %), and Orb v3 and UMA on germanium (+52 %, +54 %) and tantalum (+70 %,
     +45 %).
3. **The large expansion errors come from how the atoms' vibrations change with volume.** A material's thermal
   expansion is set mainly by its stiffness and its Grüneisen parameter, which measures how much the vibration
   frequencies shift as the crystal expands. In the worst cases, heat capacity, volume and often stiffness are right,
   and the Grüneisen parameter is wrong. Tantalum is the clearest example: three of the four models overshoot its
   expansion with a roughly correct stiffness, and MACE-MPA-0's Grüneisen parameter is 4.1 against 1.6 from
   experiment. For some semiconductors, a too-soft bulk modulus adds to the error. The six cases studied in depth
   were picked after the failures were seen, so they explain those failures rather than prove a general rule.
4. **Most of those errors are the models' own; the soft semiconductors are inherited.** Matched PBE references, our
   own for Si and GaAs and published ones for Cu, Ta, Ru, Mo and MgO, separate a model's error from the DFT method's.
   * The models' own: MACE-MPA-0's Ta and GaAs errors, MatterSim's Si and GaAs errors, and the Ru overshoots, where
     PBE itself is right.
   * Inherited: the too-soft semiconductors, since PBE makes Si and GaAs 12–18 % too soft. All of Orb v3's GaAs
     error comes from this.
   * MACE-MPA-0's accurate silicon is its own error cancelling an inherited one.
5. **Chip-stack thermal mismatch is harder than either material alone.** Across 15 device stacks (metals, silicides,
   barriers, oxides and GaN on their substrates), at 900 K:
   * MACE-MPA-0, MatterSim and Orb v3 each get the free expansion mismatch within 25 % for at most 4, and typically
     miss by about half.
   * UMA gets 7.
   * MatterSim gets the sign wrong for 5, because its silicon expands too much.
6. **Two blind tests, with the predictions and decision rules committed before the runs** (Orb v3 and UMA).
   * Supported:
     * Orb v3's overshoots in transition metals follow its too-soft bulk modulus.
     * A model with accurate silicon gets the mismatch signs right.
     * UMA's errors resemble those of Orb v3, trained on the same data, more than the others'. This one is
       suggestive, not decisive.
   * Refuted: that results right at 300 K through cancelling errors degrade at high temperature.
   * Not confirmed: that where existing models disagree, a new model will also fail.

Averages leave out layered materials such as graphite, which every model gets wrong (layer spacing 18–41 % too
large). Every number here comes from the committed tables in `results/` and is detailed below and in
[`docs/details.md`](docs/details.md#findings-in-detail).

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
  report thermal expansion against experiment. This one does, for all four models: 21–22 materials at 300 K
  and 17–18 over each material's temperature window.
* **Evidence that accuracy doesn't carry over between properties.** A model can get a crystal's size
  and stiffness right and its thermal expansion badly wrong: MACE-MPA-0 puts tantalum's lattice within
  0.4 % and its bulk modulus within about 6 %, yet overestimates its thermal expansion by 179 %.
* **An explanation for six of the largest failures**, separating model error from software and
  numerical artefacts, and, with matched PBE references, from errors inherited from the DFT the models learned
  from.
* **Blind tests.** Two of the models (Orb v3 and UMA) were run only after predictions about their errors, and the
  rules for judging them, had been committed ([Orb](docs/preregistration_orb_thermal.md),
  [UMA](docs/preregistration_uma.md)), so those conclusions were not fitted to the results.
* **Thermal mismatch of real chip stacks** (16 metal, silicide, barrier, oxide and GaN stacks), the quantity that
  actually strains a device, not just each material on its own.
* **Sourced, audited reference data.** Every experimental value comes with its citation and a verbatim
  quote, and is audited into a *core* tier (primary measurements and trusted compilations) or an
  *extended* tier, with its own uncertainty. The 495 values are released as a standalone dataset
  ([`data/release/`](data/release/README.md)) that others can reuse without the rest of the code.

## What it doesn't tell you

This is not a general verdict on whether ML force fields can be trusted for chip materials. It covers
three bulk properties, four models and perfect crystals. Real chip layers are thin films with
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

**1. Getting the structure right doesn't mean getting the rest right.** Across the 30 non-layered
materials, the four models put the crystal size within 0.72–0.80 % of experiment on average and the
bulk modulus within 11–13 %. At 300 K, thermal expansion is off by 36 % on average for MACE-MPA-0,
24 % for MatterSim, 21 % for Orb v3 and 19 % for UMA (21–22 materials each). Orb v3 and UMA are more accurate than MACE-MPA-0 (paired bootstrap); the benchmark cannot separate MatterSim, Orb v3 and UMA from one another at 300 K. Good structure is no guarantee: MACE-MPA-0 puts tantalum's
lattice within 0.4 % and its bulk modulus within about 6 %, yet overestimates its thermal expansion by 179 %. Being right at 300 K is no guarantee at higher temperature
either: of the 32 results that are within 20 % at 300 K and can also be compared at the top of their
temperature window, 13 are off there by more than 20 %, where the quasi-harmonic method's own limits also grow.

**2. No model is best everywhere.** MACE-MPA-0 overshoots the thermal expansion of refractory metals
(tantalum +179 %); MatterSim overshoots that of semiconductors (Si +85 %, GaAs +68 %), where MACE gets
silicon within about 1 %. Against experiment, the benchmark resolves no overall difference between the models
for bulk modulus, and only one for lattice constant (UMA more accurate than MatterSim, by 0.08 points)
(paired bootstrap, 95 % intervals), nor between MACE-MPA-0 and MatterSim for thermal expansion. Orb v3 and
UMA are more accurate than MACE-MPA-0 at 300 K and than MatterSim over the temperature windows (all
references; not on core-tier references alone). Some failures are shared: every model overestimates the spacing between
graphite's layers, by 18–41 %, and every model but MatterSim overshoots tantalum's thermal expansion (+45 to +179 %).

![Thermal-expansion error at 300 K by material and model](report/figures/study_errors.png)

*Thermal-expansion error at 300 K against experiment in the six-case study. Each bar is the spread
across three volume-scan settings: a sensitivity range, not a confidence interval. \*MatterSim runs
through its official package, not kUPS.*

**3. The thermal-expansion errors come from how the models handle vibrations.** How much a material
expands depends mainly on its stiffness and its Grüneisen parameter, which measures how strongly its
vibrations change as the crystal expands. In six cases (Si, GaAs, InP, Cu, Ta and HfO₂), checks of the
software and numerical settings did not explain the large errors; they trace to the models' Grüneisen
parameters, with a too-soft bulk modulus adding to it for several semiconductors. For tantalum,
MACE-MPA-0's Grüneisen parameter is 4.1, against 1.6 inferred from experiment. The six cases were chosen
after the failures were seen, so the study explains them; it does not establish a general rule. A test fixed
in advance on Orb v3's unseen materials ([pre-registration](docs/preregistration_orb_thermal.md)) supported
one of its explanations (Orb's overshoots in transition metals follow its too-soft bulk modulus), refuted
another and left two undecided. A second blind test, on UMA ([pre-registration](docs/preregistration_uma.md)),
confirmed that a model with accurate silicon gets chip-stack mismatch signs right and that UMA's errors track
those of Orb v3, trained on the same data, most closely; it did not confirm that the other models'
disagreement predicts where a new model fails.

**4. Most of those errors are the models' own; the soft semiconductors are inherited.** The models learned from
PBE calculations. Matched PBE references separate what a model gets wrong from what PBE itself gets wrong. They are
our own calculations for Si and GaAs and published ones for Cu and Ta.
* **The models' own errors:** MACE's tantalum and GaAs errors, and MatterSim's silicon and GaAs errors. For
  tantalum, PBE gives a Grüneisen parameter of about 2.0, where MACE gives 4.1.
* **Inherited from PBE:** PBE makes silicon and GaAs 12–18 % too soft. All of Orb v3's GaAs error comes from this.
* **Right answers that are not PBE's:** MACE's accurate silicon is its own error cancelling an inherited one.
Details are in [section 7 of the study](docs/thermal_failure_study.md#7-model-error-or-inherited-from-pbe).

**5. Chip-stack thermal mismatch is hard to get right.** A chip is a stack of layers, and what
strains it is the *difference* in their expansion. For 15 device stacks (copper, tungsten, molybdenum,
tantalum, ruthenium and silicides on silicon; copper on tantalum and tungsten on TiN; TiN, Al₂O₃ and Y₂O₃
on silicon; GaN on silicon and SiC; AlN on silicon), the free expansion mismatch from 300 to 900 K is
compared with the one built from the measured expansion curves
([`results/thermal_mismatch_summary.csv`](results/thermal_mismatch_summary.csv)):

| at 900 K | MACE-MPA-0 | MatterSim v1* | Orb v3 | UMA* |
|---|---|---|---|---|
| stacks with the right sign | 13 of 13 | 10 of 15 | 15 of 15 | 15 of 15 |
| within 25 % of the measured mismatch | 3 | 4 | 3 | 7 |
| median miss | 46 % (1190 microstrain) | 71 % (1200 microstrain) | 53 % (980 microstrain) | 29 % (520 microstrain) |

\*MatterSim and UMA run through their official packages. The stacks were chosen by device role before their mismatch was computed. Mismatch is an ingredient of
thermal stress, not a prediction of it: stress also depends on geometry, constraint and elastic response.
A metal on silicon compounds both materials' errors, so a model can be good on each material alone and
still miss the stack.

Every number above comes from the committed tables in `results/`; the full findings, with confidence
intervals and sample sizes, are in [`docs/details.md`](docs/details.md#findings-in-detail).

## What this release covers

| Scope | Coverage |
|---|---|
| Lattice constant and bulk modulus | MACE-MPA-0, Orb v3, MatterSim v1 and UMA on all 33 materials, with exclusions and their reasons |
| Thermal expansion, benchmark-wide | All four models on all 33 materials; 21–22 graded comparisons per model at 300 K, 17–18 over the temperature windows. Orb v3 and UMA were added after v1.1.0, each as a pre-registered test. |
| Thermal-failure study | MACE-MPA-0, MatterSim v1 and Orb v3 on six selected materials (Si, GaAs, InP, Cu, Ta, HfO₂) |
| UMA s-1.2 | Run through Meta's `fairchem` package (kUPS's UMA bridge needs a GPU), like MatterSim through its own package |

Not every result can be graded, so coverage is reported next to accuracy
([`results/coverage.csv`](results/coverage.csv)). Each model–material–property result is one of:

* **Graded:** the model gave a valid answer and it is compared with the reference.
* **Model failure:** the model gave an answer that can't be compared, for example Orb changes the crystal
  form of 3 of the 33 materials. These are findings in their own right and are left out of the averages.
* **Method limit:** the calculation method itself doesn't apply, for example thermal expansion of layered
  materials, which grow differently in different directions, or at temperatures where the method breaks down.
* **No reference:** there is no trustworthy lab measurement to compare with.
* **Not computed:** the calculation was not run (no current case among the four models).

Every reference is also tiered (`data/reference_quality.yaml`), and the statistics are reported both for
all graded references and for core-tier references only; no conclusion changes between the two.

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

Orb v3's benchmark-wide thermal expansion was computed for all 33 materials, and UMA s-1.2 was added as a
fourth model. Both were run as pre-registered tests with their predictions committed before the run
([Orb](docs/preregistration_orb_thermal.md), [UMA](docs/preregistration_uma.md)). Chip-stack thermal mismatch
became a headline result (16 stacks), and a 300 K result is no longer graded when instability cut the volume
scan short.

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
