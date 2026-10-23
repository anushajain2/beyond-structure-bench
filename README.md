# ChipFF Bench

[![tests](https://github.com/anushajain2/chipff-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/anushajain2/chipff-bench/actions/workflows/ci.yml)

**How far can you trust an AI force field's prediction for a material used in chips, and when it is wrong, why?**

ChipFF Bench tests three open, general-purpose machine-learned force fields (MACE-MPA-0, Orb v3 and
MatterSim v1) on 33 materials used in semiconductor devices, for three bulk properties: lattice
constant, bulk modulus and thermal expansion. Each result is compared with sourced experimental values
and, where Materials Project has one, with its DFT value. A separate study of six cases then works out
what causes the largest thermal-expansion errors. Calculations run through CuspAI's open-source
[kUPS](https://github.com/cusp-ai-oss/kups) toolkit, except MatterSim, which runs through its official
package because its kUPS export is broken (finding 3).

**[Project site](https://anushajain2.github.io/chipff-bench/)** ·
[Explore the evidence](https://anushajain2.github.io/chipff-bench/explore.html) ·
[Read the study](https://anushajain2.github.io/chipff-bench/study.html) ·
[Evaluation design](https://anushajain2.github.io/chipff-bench/design.html) ·
[Reproduce](https://anushajain2.github.io/chipff-bench/reproduce.html)

## Three findings

1. **Structure is accurate, stiffness less so, and the data can't rank the models.** Across the 30
   non-layered materials, all three models put the crystal size within 0.73–0.80 % of experiment on
   average, and the bulk modulus within 11–13 %. Against experiment the benchmark resolves no
   difference between the models for either property (paired bootstrap, 95 % intervals). Layered
   materials fail for every model.
2. **Thermal expansion is where the models fail, and each fails in different places.** At 300 K,
   MACE-MPA-0 is off by 36 % on average and MatterSim by 24 % (22 materials each; the benchmark cannot
   separate the two). MACE overshoots refractory metals (tantalum +179 %), MatterSim overshoots
   semiconductors (Si +85 %, GaAs +68 %). A model can get a crystal's size and stiffness right and still
   badly mispredict how it expands: MACE puts tantalum's lattice within 0.4 % and its bulk modulus
   within 6 %. Being right at 300 K is no guarantee at higher temperature either: 5 of the 14 results
   within 20 % at 300 K are off by more than 20 % at the top of their temperature window, where the
   quasi-harmonic method's own limits also grow.
3. **The six-case study traces the large errors to the models' Grüneisen parameters**, which describe how
   vibration frequencies change as a crystal expands; for several semiconductors a too-soft bulk modulus
   adds to it. Checks of the workflow itself found a model export whose energy depends on the order of its
   input (MatterSim through kUPS), a bias in kUPS's isotropic barostat, and a numerical defect in this
   project's own phonon step, now fixed. The six cases were chosen after the failures were seen, so the
   study explains them; it does not establish a general rule.

![Thermal-expansion error at 300 K by material and model](report/figures/study_errors.png)

*Thermal-expansion error at 300 K against experiment in the six-case study. Each bar is the spread
across three volume-scan settings: a sensitivity range, not a confidence interval. \*MatterSim runs
through its official package, not kUPS.*

## What this release covers

| Scope | Coverage in v1.1.0 |
|---|---|
| Lattice constant and bulk modulus | MACE-MPA-0, Orb v3 and MatterSim v1 on all 33 materials, with exclusions and their reasons |
| Thermal expansion, benchmark-wide | MACE-MPA-0 and MatterSim v1; 22 graded comparisons per model at 300 K, 17–18 over the temperature windows. Orb v3 is not computed in this release. |
| Thermal-failure study | MACE-MPA-0, MatterSim v1 and Orb v3 on six selected materials (Si, GaAs, InP, Cu, Ta, HfO₂) |
| UMA | Not evaluated in this release (gated licence) |

**Reference quality.** Every experimental value is audited in
[`data/reference_quality.yaml`](data/reference_quality.yaml): a *core* tier (primary measurements and
evaluated compilations with stated conditions) and an *extended* tier (provisional compilations, thin films,
range averages, unresolved conflicts), each with an uncertainty taken from its source where it gives one.
Results are reported for both tiers, and the references are released as a standalone dataset
([`data/release/`](data/release/README.md)).

Coverage is reported next to accuracy, because not every result can be graded: for example, Orb changes
the crystal form of 3 of the 33 materials (`results/coverage.csv`). These are bulk-crystal properties
relevant to device materials, not predictions of how a real thin-film stack behaves.

## Who can use it

* **Choosing a force field for these materials:** the explorer shows each model's value next to the
  reference, with its source, error and any exclusion reason.
* **Building or evaluating force fields:** the study's per-ingredient comparisons and workflow checks
  show where to look when a property comes out wrong.
* **Reusing the references:** [`data/release/chipff_references.csv`](data/release/README.md) has 495
  sourced values with their conditions, tier and uncertainty, independent of the rest of the code.
* **Running kUPS:** two of the findings concern the toolkit itself; write-ups with reproducers are in
  `docs/kups_issue_*_DRAFT.md`.

## Quick start

**Read.** No install needed: the [site](https://anushajain2.github.io/chipff-bench/), or the committed
tables in `results/` (`summary.json` and the CSVs) and `report/index.html`.

**Reanalyse.** Rebuild every table and figure from the committed raw results, with no new calculations:

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
chipff analyze && chipff report
```

**Run.** One model on one material, in about two minutes on a laptop CPU (measured on an Apple-silicon
MacBook). This recomputes the stored silicon results for MACE-MPA-0; they should agree with the
committed ones to about 0.2 %. kUPS logs "Fixing failed assertions" while it enlarges its neighbour-list
buffers; that is expected, not an error.

```bash
chipff static -m mace-mpa-0 --materials Si --force
chipff qha -m mace-mpa-0 --materials Si --force
chipff analyze
```

The full pipeline, the exact environments and the model checksums are on the
[Reproduce page](https://anushajain2.github.io/chipff-bench/reproduce.html).

## More

* **Full detail:** findings, methods and limits in [`docs/details.md`](docs/details.md); statistics in
  [`docs/robustness.md`](docs/robustness.md); the six-case study in
  [`docs/thermal_failure_study.md`](docs/thermal_failure_study.md).
* **Related benchmarks:** [CHIPS-FF](https://arxiv.org/abs/2412.10516) compares 16 force fields with DFT
  on 104 semiconductor-relevant materials, and [UniFFBench](https://arxiv.org/abs/2508.05762) compares
  six with experiment on minerals. Neither reports thermal expansion against experiment.
* **Agent interface:** `chipff-mcp` is a Model Context Protocol server that lets an AI assistant
  retrieve the same evidence. Its answers are benchmark evidence, not calibrated error estimates.

## What changed in v1.1.0

After an outside review, the experimental references were audited and tiered; InP's and NiSi's expansion
references, which are averages over wide temperature ranges, are no longer used as 300 K values; each
reference's own uncertainty now feeds the statistics; and the thermal results gain absolute and
accumulated-strain errors, a temperature-trend check and a thermal-mismatch example. The 300 K averages
changed as a result (MACE 34.5 % → 36 %, MatterSim 28.7 % → 24 %). No calculation was rerun.

## Citation

> A. Jain, *ChipFF Bench: how reliably universal machine-learned force fields predict the structure,
> stiffness and thermal expansion of semiconductor-device materials*, v1.1.0 (2026).
> https://github.com/anushajain2/chipff-bench

## Licence

Code: MIT. Model weights keep their own licences (MIT, Apache-2.0, FAIR Chemistry License). Experimental
values are cited from the sources listed with each one. This is an independent project built on kUPS and
published model exports; it is not affiliated with or endorsed by CuspAI, Meta, Microsoft, Orbital
Materials or the MACE developers.
