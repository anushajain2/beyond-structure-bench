# BeyondStructure Bench

[![tests](https://github.com/anushajain2/beyond-structure-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/anushajain2/beyond-structure-bench/actions/workflows/ci.yml)

**When a machine-learned force field gets a chip material's crystal structure right, does it also get
its stiffness and thermal expansion right? And when it doesn't, why?**

BeyondStructure Bench is a benchmark of four machine-learned (ML) force fields: models that predict how
the atoms in a material push and pull on each other, used as fast stand-ins for quantum-mechanical
calculations. It tests MACE-MPA-0, Orb v3, MatterSim v1 and Meta's UMA on 33 materials used in chips, from silicon
and copper to hafnium oxide, and compares every prediction with published lab measurements (and with
[DFT](#terms-used-here) calculations where they exist). A follow-up study of six cases looks at why the
worst predictions go wrong.

**Key findings:**

1. **Getting the structure right doesn't mean getting the rest right.** Accuracy falls as the property
   gets harder: on average the models are off by under 1 % on crystal size, 11–13 % on stiffness and
   19–36 % on thermal expansion at room temperature. MACE-MPA-0, for example, gets tantalum's crystal size within 0.4 % but
   overestimates its thermal expansion by 179 %.
2. **No model is best everywhere.** Each fails on different materials: MACE-MPA-0 on metals such as
   tantalum, MatterSim on semiconductors such as silicon and gallium arsenide, Orb v3 and UMA on germanium
   and tantalum. Orb v3 and UMA have the lowest average thermal-expansion errors, but neither is clearly
   ahead of MatterSim at 300 K. On structure and stiffness, the data can barely tell the four models apart.
3. **The thermal-expansion errors come from how the models handle vibrations.** In six cases studied in
   depth, the models misjudge how strongly the atoms' vibrations change as the crystal expands. These
   cases were picked after the failures were seen, so this explains them rather than proving a general
   rule.
4. **Chip-stack thermal mismatch is hard to get right.** What strains a chip is the difference in
   expansion between stacked layers. Across 15 real stacks (metals, silicides, barriers, oxides and GaN on
   their substrates), three of the four models get the mismatch within 25 % for at most 4 of them and
   typically miss by about half; UMA, whose silicon is accurate, gets 7. MatterSim gets the direction
   wrong for 5 of 15, because its silicon expands too much.

Averages leave out layered materials such as graphite, which every model gets wrong.

**[Project site](https://anushajain2.github.io/beyond-structure-bench/)** ·
[Explore the evidence](https://anushajain2.github.io/beyond-structure-bench/explore.html) ·
[Read the study](https://anushajain2.github.io/beyond-structure-bench/study.html) ·
[Evaluation design](https://anushajain2.github.io/beyond-structure-bench/design.html) ·
[Reproduce](https://anushajain2.github.io/beyond-structure-bench/reproduce.html)

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
  report thermal expansion against experiment. This one does, for 22 materials at 300 K with two of the models.
* **Evidence that accuracy doesn't carry over between properties.** A model can get a crystal's size
  and stiffness right and its thermal expansion badly wrong: MACE-MPA-0 puts tantalum's lattice within
  0.4 % and its bulk modulus within about 6 %, yet overestimates its thermal expansion by 179 %.
* **An explanation for six of the largest failures**, separating model error from software and
  numerical artefacts.
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

**4. Chip-stack thermal mismatch is hard to get right.** A chip is a stack of layers, and what
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
