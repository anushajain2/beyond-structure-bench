# ChipFF Bench

[![tests](https://github.com/anushajain2/chipff-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/anushajain2/chipff-bench/actions/workflows/ci.yml)

**How reliable are today's open ML force fields for the materials chips are made of?**

ChipFF Bench measures four universal ML force fields (MACE-MPA-0, Orb v3, MatterSim v1, UMA) on
33 chip materials — semiconductors, gate and capacitor dielectrics, interconnect metals, barriers
and silicides, and layered 2D materials — for three properties that decide whether a film stack
survives processing: **lattice constant, bulk modulus and thermal expansion**. Every number is
compared against Materials Project DFT (PBE) and against sourced experimental values. Simulations
run through CuspAI's open-source [kUPS](https://github.com/cusp-ai-oss/kups) toolkit, except MatterSim,
whose kUPS export is currently broken (see Findings) and which runs through its official package.

![Trust map vs experiment](report/figures/trust_map_experiment.png)

## Findings so far

Status: lattice constants and bulk moduli are complete for MACE-MPA-0, Orb v3 and MatterSim v1.
Thermal expansion is complete for MACE-MPA-0 and MatterSim v1; **Orb v3's thermal run is in progress
(7 of 33 materials, computed before the Γ-mode fix described below and to be recomputed) and is left out
of every thermal average and comparison until it finishes.** UMA is awaiting license access. These
findings will be updated when the rest lands.

1. **Lattice constants of non-layered chip materials are effectively solved.** All three models are
   within 0.73–0.80 % of experiment on average across the 30 non-layered materials (worst case:
   α-quartz, +2.1 to +2.5 %). Against Materials Project DFT they agree to 0.07–0.25 %, and the
   systematic +0.6 % offset from experiment is the known PBE overestimation, inherited rather than
   introduced by the models.
2. **Layered 2D materials are where every model fails.** Interlayer spacing is overestimated by
   10–30 % (c axis of graphite: MACE +18 %, MatterSim +25 %, Orb +30 %), because PBE training data
   lacks van der Waals binding. Their bulk moduli are off by 60–130 %. Orb relaxes MoS₂ into a
   different, sheared stacking.
3. **Stiffness is the harder property, and the models err in different directions.** Excluding layered
   materials, mean absolute bulk-modulus error vs experiment is 10.8 % (MACE), 11.9 % (Orb) and
   12.6 % (MatterSim). Orb and MatterSim run systematically soft (mean −10.5 % and −11 %) while
   staying close to DFT (5–6 %); MACE is unbiased on average but scatters more and over-stiffens some
   refractory metals (W +18 %, Mo +17 %, Ti +35 %). **Against experiment the three models are
   statistically tied** for both lattice constants and bulk moduli: every pairwise difference's 95 %
   bootstrap interval includes zero (`results/robustness/pairwise.csv`), and the same holds within every
   material class (`pairwise_by_class.csv`, Holm-corrected). Against DFT the differences are real:
   MatterSim reproduces PBE most closely, especially for metals and semiconductors, yet is no closer to
   experiment. **Fidelity to the PBE training data doesn't buy accuracy against reality, but for
   different reasons for the two properties.** For lattice constants the models make the same error
   (correlation of their errors 0.83–0.95): it is PBE's, and the training functional is the ceiling.
   For bulk moduli their errors are largely their own (MACE vs MatterSim: 0.11, 95 % interval −0.21
   to 0.42), because PBE's error is about as large as each model's departure from PBE; only Orb and
   MatterSim, which both track PBE closely, share theirs (0.61). So a closer fit to PBE is no sign of
   a better bulk modulus (`results/robustness/model_agreement.csv`).
4. **Symmetry is not guaranteed.** Orb, which is not built to be exactly equivariant, relaxes rutile
   TiO₂ and cubic SrTiO₃ into lower-symmetry polar structures; MACE and MatterSim keep them. Those
   cases are excluded from the averages and reported as findings.
5. **Running the models through a toolkit adds its own failure modes.** The MatterSim JAX export used
   by kUPS returns energies that depend on neighbour-list order and supercell size (reproducer:
   `scripts/repro_mattersim_export.py`), so MatterSim is benchmarked through its official package and
   starred in every figure. Self-checks also caught two frame-convention bugs in this project's own
   stress handling before any number was published.
6. **Thermal expansion is the hardest property, and the two finished models fail in different
   places.** Computed in the quasi-harmonic approximation, MACE and MatterSim are off from experiment
   by 34.5 % and 28.7 % on average at 300 K (35 % for both over each material's pre-registered
   temperature window), both too large on average, and statistically tied. But MACE overshoots
   refractory and hcp metals (Ta +179 %, Mo +97 %, Ru +52 %, W +48 % at 300 K) where MatterSim is
   mostly within 14 %, while MatterSim overshoots semiconductors (InP +119 %, Si +85 %, GaAs +68 %)
   where MACE gets Si within 1 %. Their errors are uncorrelated (−0.10 at 300 K), so **averaging the
   two models cuts the error to 25.7 %**, and the size of their disagreement tracks the error of that
   average (0.41): when two models disagree, distrust both. A controlled study of six hard cases
   ([`docs/thermal_failure_study.md`](docs/thermal_failure_study.md)) traces the large errors to the
   models' Grüneisen parameters (and, for MatterSim's semiconductors, a too-soft bulk modulus), not to
   the software route or the QHA settings. Rutile TiO₂ and cubic SrTiO₃ are
   dynamically unstable in both models and are excluded, as are a few results where QHA itself breaks
   down at high temperature (`results/thermal_expansion.csv` gives the reason for each).

| Thermal expansion vs experiment (non-layered) | MACE-MPA-0 | MatterSim v1* | Orb v3 |
|---|---|---|---|
| mean abs. error at 300 K (95 % CI) | 34.5 % (22–56), n = 24 | 28.7 % (20–44), n = 24 | in progress |
| mean abs. error over the window (95 % CI) | 35.5 % (23–53), n = 17 | 34.5 % (23–54), n = 18 | in progress |
| within 20 % / 40 % at 300 K | 11 / 19 | 13 / 18 | in progress |

\* MatterSim runs through its official package (finding 5). Class-by-class results are in the
trust map above and `results/trust_map.csv`.

## What's measured

| Property | Method (all through kUPS) | DFT reference | Experimental reference |
|---|---|---|---|
| Lattice constant / volume | L-BFGS cell + atom relaxation from the MP structure, fmax 0.001 eV/Å | MP PBE relaxed structure | room-temperature diffraction values |
| Bulk modulus | full elastic tensor: 24 strains (6 Voigt × ±0.5 %, ±1 %), ions relaxed, stress from kUPS → K_VRH, K_Reuss; plus a Birch–Murnaghan E(V) cross-check | MP PBE elastic tensor (K_VRH) | ultrasonic / Brillouin elastic constants or EOS fits to compression data |
| Thermal expansion | quasi-harmonic approximation: phonons (phonopy, forces via kUPS) at 9 volumes, minimise E(V) + F_vib(V,T) → α_V(T), averaged over a pre-registered temperature window ([why not MD](docs/thermal_method.md)) | — (not available from static DFT) | high-temperature dilatometry / diffraction, averaged over the same temperature window |

**Errors.** Lattice error is the effective linear error (V/V_ref)^(1/3) − 1, so one number covers
any crystal system; per-axis errors are in `results/lattice.csv`. Bulk modulus is compared like for
like: model K_VRH vs MP K_VRH; vs experiment, model K_Reuss when the experiment is hydrostatic
(EOS/compression) and model K_VRH when it is from single-crystal elastic constants. Thermal expansion
compares the volumetric coefficient α_V.

**Trust map.** Mean absolute % error per model × material class × property, graded with thresholds
fixed before any comparison was made (`configs/benchmark.yaml`): lattice good ≤ 1 %, okay ≤ 3 %;
bulk modulus good ≤ 10 %, okay ≤ 25 %; thermal expansion good ≤ 20 %, okay ≤ 40 %.

## How to trust it without being an expert

* **Every reference has a source.** Each experimental value in `data/experimental/*.json` carries the
  URL it was read from, a citation and a verbatim quote, plus notes on conversions and conflicts.
  Values computed from sources (e.g. a VRH average from published elastic constants) are labelled.
* **Known patterns are reproduced.** PBE-trained models should land close to MP and ~1 % larger than
  experiment; layered solids should show large c-axis errors because PBE lacks van der Waals
  binding. Both appear in the results; if they didn't, the pipeline would be suspect.
* **Automatic self-checks** (`results/checks.csv`): relaxation converged; space group unchanged;
  elastic tensor positive definite; Birch–Murnaghan fit clean; for cubic crystals, EOS bulk modulus
  within 5 % of the elastic-tensor value; elastic fit symmetric; for thermal expansion, dynamically
  stable at the relaxed volume, enough stable volumes for the fit, few phonon-interpolation
  artefacts, and the predicted volume inside the scanned range. Two invariance checks every model must pass ship as scripts:
  stress equals the strain derivative of the model's own energy, and a structure's energy does not
  depend on what else is in its batch.
* **Every result is fingerprinted** with the code, settings and inputs that produced it
  (`docs/provenance.md`); `chipff analyze` refuses to mix results from different code or settings.
* **Written rules for every judgement call** (`configs/benchmark.yaml`): thermal-expansion windows run
  from 0.75 × the Debye temperature (min 300 K) to half the melting point, 50 K below any phase change;
  phonon supercells are ≥ 10 Å across. Materials where a rule can't be applied get fixed temperatures
  with the reason written down. Changes of method or rule are recorded in the config with their date
  and reason (e.g. the switch from MD to QHA, `docs/thermal_method.md`).

## Robustness and statistics

Averages over ~30 materials can rank models by chance, and simulation results can hinge on
arbitrary settings. So every headline comparison is backed by three kinds of check, explained in
[`docs/robustness.md`](docs/robustness.md):

* **Confidence intervals.** A bootstrap over materials, also perturbing each experimental reference
  by its typical uncertainty, gives 95 % intervals on every error. A paired bootstrap says whether
  one model is *significantly* more accurate than another or the two are tied
  (`results/robustness/bootstrap_ci.csv`, `pairwise.csv`).
* **Sensitivity to settings.** On eight representative materials, one setting is changed at a time:
  strain size for the elastic tensor, a 10x tighter force tolerance, and starting cells 3 % smaller
  or larger. The results must not move (`static_sensitivity.json`, `chipff robustness --what static`).
* **Do models make the same mistakes?** The correlation of two models' errors against experiment,
  the error of their average, and whether their disagreement predicts that error
  (`model_agreement.csv`). Shared errors point at the training data; independent ones mean a second
  model is worth running.
* **Convergence of thermal expansion.** QHA's settings were checked on six hard cases (Si, GaAs, Cu,
  Ta, InP, HfO₂; [`docs/thermal_failure_study.md`](docs/thermal_failure_study.md)). A 3x larger
  displacement and a 14 Å supercell change α(300 K) by ≤ 2 % (MACE InP: +7 %); the volume-scan range
  by up to 9 % (Si) and 12 % (HfO₂). That study also found the acoustic modes at Γ entering the free
  energy at random, which made repeated runs scatter by up to ±8 %. They are now excluded, and all
  published QHA numbers come from the corrected rerun (median change 0.7 %;
  [`docs/thermal_method.md`](docs/thermal_method.md)). The MD seed and time-step reruns
  (`chipff robustness --what md`) belong to the MD cross-check route.

Static properties are deterministic, so "pass@k"-style repeated sampling doesn't apply to them; the
questions above are its counterparts here.

## Reproduce

```bash
uv venv --python 3.12 && uv pip install -e ".[uma,mcp,dev]"
cp .env.example .env                  # add your free Materials Project API key
chipff fetch                          # MP structures + DFT references -> data/mp/
chipff static                         # lattice, elastic tensor, EOS for the kUPS models (CPU, ~1 h)
# MatterSim through its official package, in its own environment:
uv venv .venv-mattersim --python 3.12 && uv pip install --python .venv-mattersim/bin/python mattersim pymatgen pyyaml pandas
PYTHONPATH=src .venv-mattersim/bin/python -m chipff.cli static -m mattersim-5m-native
chipff qha                            # thermal expansion, quasi-harmonic (CPU, ~1-2 h per model)
chipff analyze && chipff report       # results/*.csv, report/index.html
pytest -q
```

UMA is gated: accept Meta's license at <https://huggingface.co/facebook/UMA> and run
`hf auth login`. The original NPT-MD route (`chipff thermal`, `notebooks/thermal_expansion_gpu.ipynb`)
is kept for cross-checks; it is not used for the published numbers because of its cost and a bias in
kUPS's isotropic barostat (`docs/thermal_method.md`, reproducer `scripts/repro_kups_barostat_bias.py`).

Validation scripts any model must pass: `scripts/check_stress.py <model>` (reported stress equals the
strain derivative of the model's own energy) and `scripts/check_batch_consistency.py <model>` (a
structure's energy doesn't depend on what else is in the batch).

Raw per-model results are committed under `results/raw/`, so `chipff analyze && chipff report`
rebuilds every table and figure without rerunning a simulation.

## Agent tool (MCP)

```bash
chipff-mcp     # stdio MCP server
```

* `recommend_model(material, property, temperature_K)` — best model and expected error, from the benchmark
* `get_benchmark(query)` — stored results for a material or class, with references and sources
* `check_material(cif)` — relaxes a new structure with every model and flags where they disagree

Example: *"I'm screening barrier materials similar to TaN at 700 K. Which force field should I use,
and how far can I trust it?"*

## Repository map

```
configs/benchmark.yaml        every setting, the pre-registered thresholds, the temperature rule
data/materials.yaml           the 33 materials, their phases and roles in a chip
data/mp/                      Materials Project structures and DFT references (with IDs)
data/experimental/            sourced experimental values, one file per class
src/chipff/                   engine (kUPS wrapper), static, thermal, analysis, report, MCP server
results/raw/<model>/          raw results per model and step
results/*.csv, summary.json   merged tables, trust map, checks
report/                       figures and the HTML report
notebooks/                    GPU notebook for thermal expansion
```

## Limits

* **Perfect bulk crystals.** Real chip layers are thin, often amorphous films with interfaces and
  defects. TaN is benchmarked in its bulk-stable hexagonal ε phase; barrier films are usually cubic
  δ-TaN, which lacks bulk experimental data.
* **Static lattice vs room-temperature experiment.** Relaxed lattices are 0 K without zero-point
  motion; experiment is at ~300 K. This adds roughly +0.1–0.3 % to the experimental value and is
  part of the measured error, as in most benchmarks.
* **Quasi-harmonic thermal expansion.** QHA includes quantum effects but omits anharmonicity beyond
  the volume dependence of the phonons, which matters most near melting (windows stop at T_m/2). The
  volume scan keeps the cell shape fixed: exact for cubic crystals, approximate otherwise; layered
  materials are computed but not graded. Crystals unstable in a model (imaginary phonons) are excluded.
* **Experimental values vary.** Sources disagree by several percent (e.g. Ge bulk modulus 71–75 GPa,
  hBN 18–37 GPa), and some values are weaker than others (InP expansion given as a constant average;
  NiSi per-axis expansion from a conference poster). The notes in `data/experimental/` say which.
  MoS₂ has no accessible experimental thermal expansion and is compared model-to-model only; CoSi₂ has
  only a room-temperature value.
* **Materials Project's own data has gaps.** MP's elastic tensor for hcp Co is unphysical (negative
  K) and is excluded. For layered solids, PBE itself misses the interlayer binding, so "vs DFT" there
  measures agreement with a flawed reference.
* **Model versions.** Results apply to the exact model files listed in `src/chipff/models.py`
  (CuspAI's JAX exports of MACE and Orb; Meta's UMA checkpoint via kUPS's PyTorch bridge; MatterSim
  v1 5M through Microsoft's `mattersim` package with ASE's L-BFGS, not kUPS).
* **No MatterSim thermal expansion.** Its official package runs one structure at a time; at benchmark
  settings that is ~50 GPU-hours, beyond a free GPU quota, and the batched kUPS export is unusable.
* **Independent project.** Built on kUPS and CuspAI's published model exports; not affiliated with
  or endorsed by CuspAI, Meta, Microsoft, Orbital Materials or the MACE developers.

## License

Code: MIT. Model weights keep their own licenses (MIT, Apache-2.0, FAIR Chemistry License).
Experimental values are facts cited from the listed sources.
