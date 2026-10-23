# ChipFF Bench: findings, methods and limits in detail

The [README](../README.md) is the short guide; this page keeps the full detail it links to. Paths in
backticks are relative to the repository root unless they name a file in this folder.

## Findings in detail

Status: lattice constants and bulk moduli are complete for MACE-MPA-0, Orb v3 and MatterSim v1.
Thermal expansion is complete for MACE-MPA-0 and MatterSim v1. **Orb v3's benchmark-wide thermal expansion is not
computed in this release.** A partial run (7 of 33 materials) predates the Γ-mode fix described under Robustness and is
left out of every thermal average and comparison. Orb does appear in the six-case thermal-failure study
([`thermal_failure_study.md`](thermal_failure_study.md)). UMA is awaiting license access.

1. **Lattice constants of non-layered chip materials are accurate to under 1 % on average.** The
   effective linear error of all three models is 0.73–0.80 % against experiment across the 30
   non-layered materials (worst case: α-quartz, +2.1 to +2.5 %). Against Materials Project DFT they
   agree to 0.07–0.25 %. The systematic +0.6 % offset from experiment is consistent with PBE's known
   overestimate, plus 0.1–0.3 % from comparing 0 K cells with room-temperature measurements.
2. **Layered 2D materials are where every model fails.** Interlayer spacing is overestimated by
   10–30 % (c axis of graphite: MACE +18 %, MatterSim +25 %, Orb +30 %), because PBE training data
   lacks van der Waals binding. Their bulk moduli are off by 60–130 %. Orb relaxes MoS₂ into a
   different, sheared stacking.
3. **Stiffness is the harder property, and the models err in different directions.** Excluding layered
   materials, mean absolute bulk-modulus error vs experiment is 10.8 % (MACE), 11.9 % (Orb) and
   12.6 % (MatterSim). Orb and MatterSim run systematically soft (mean −10.5 % and −11 %) while
   staying close to DFT (5–6 %); MACE is unbiased on average but scatters more and over-stiffens some
   refractory metals (W +18 %, Mo +17 %, Ti +35 %). **Against experiment this benchmark does
   not resolve a difference between the three models** for lattice constants or bulk moduli: every
   pairwise difference's 95 % bootstrap interval includes zero (`results/robustness/pairwise.csv`), and the same holds within every
   material class (`pairwise_by_class.csv`, Holm-corrected). That is not a test of equivalence: with
   ~30 materials, differences below about 3–5 points of bulk-modulus error would go undetected.
   Against DFT the differences are resolved:
   MatterSim reproduces PBE most closely, especially for metals and semiconductors, yet is no closer to
   experiment. Closer agreement with DFT not translating into closer agreement with experiment is
   also reported elsewhere ([UniFFBench](https://arxiv.org/abs/2508.05762)); what this data adds is
   how it differs by property. For lattice constants the models' errors are strongly correlated
   (0.83–0.95), a shared bias consistent with the limits of the PBE reference and training data;
   correlation alone cannot separate the functional from shared data or reference choices. For bulk
   moduli the sample correlation between MACE and MatterSim is low (0.11, 95 % interval −0.21 to
   0.42), while Orb and MatterSim, which both track PBE closely, share more of theirs (0.61, 0.23 to
   0.88). So a closer fit to PBE is not a reliable sign of a better bulk modulus
   (`results/robustness/model_agreement.csv`).
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
   by 36 % and 24 % on average at 300 K (35 % and 34.5 % over each material's pre-registered
   temperature window), both too large on average, with no difference resolved between them. But MACE overshoots
   refractory and hcp metals (Ta +179 %, Mo +97 %, Ru +52 %, W +48 % at 300 K) where MatterSim is
   mostly within 14 %, while MatterSim overshoots semiconductors (Si +85 %, GaAs +68 % at 300 K; InP +129 %
   over its window, against a range-average reference) where MACE gets Si within 1 %. The sample correlation of
   their errors is small (−0.02 at 300 K, 95 % interval −0.40 to +0.50). Averaging the two models gives 24 % at
   300 K, no better than MatterSim alone, but 30.9 % over the windows against 35.5 % and 34.9 %. Their
   disagreement correlates with the error of that average (0.37 at 300 K, interval −0.11 to +0.77): an
   exploratory warning signal, not a calibrated uncertainty estimate. In a controlled study of
   six cases ([`thermal_failure_study.md`](thermal_failure_study.md)), backend comparisons and
   the numerical checks performed do not explain the large errors. By elimination, the study places
   them in the models' Grüneisen parameters (for MatterSim's semiconductors, also a too-soft bulk modulus).
   Orb v3, run on the same cases as a third model, shares some of these failures and avoids one. It shares the
   soft semiconductor bulk moduli and a too-high Ta Grüneisen parameter (Ta +70 %). It avoids the wrong-signed
   semiconductor acoustic modes. The cases were
   chosen after the failures were seen, so this explains those cases rather than establishing a general rule. Rutile TiO₂ and cubic SrTiO₃ are
   dynamically unstable in both models and are excluded, as are a few results where QHA itself breaks
   down at high temperature (`results/thermal_expansion.csv` gives the reason for each).

| Thermal expansion vs experiment (non-layered) | MACE-MPA-0 | MatterSim v1* | Orb v3 |
|---|---|---|---|
| mean abs. error at 300 K (95 % CI) | 36.1 % (22–58), n = 22 | 24.2 % (17–37), n = 22 | not computed† |
| mean abs. error over the window (95 % CI) | 35.5 % (23–54), n = 17 | 34.5 % (23–54), n = 18 | not computed† |
| within 20 % / 40 % at 300 K | 10 / 17 | 13 / 17 | not computed† |
| core-tier references only, 300 K | 37.6 % (21–64), n = 18 | 23.4 % (15–38), n = 18 | not computed† |
| mean absolute error at 300 K, 10⁻⁶ K⁻¹ | 7.8 | 5.2 | not computed† |

† Orb's benchmark-wide thermal expansion was not recomputed after the Γ-mode fix (status note above); its results on
the six study cases are in [`thermal_failure_study.md`](thermal_failure_study.md).

**Beyond percentage error** (`results/thermal_metrics.csv`, `thermal_mismatch.csv`). Of the 14 results
within 20 % at 300 K, 5 are off by more than 20 % at the top of their window (Y₂O₃ for both models,
MatterSim's Ru and Mo, MACE's quartz near its α–β transition); at high temperature the quasi-harmonic
method's own limits add to the model's error, so this cannot be pinned on the models alone. The models get the
direction of α's change across the window right in 20 of 29 cases. As an application example, the free
expansion mismatch between a metal and silicon compounds both materials' errors: for W, Mo or Ta on Si
between 300 and 900 K, the two models miss the measured mismatch (600–1900 microstrain) by 140–360 %, and
MatterSim gets its sign wrong, because its silicon expands too much.

7. **Accuracy averages cover only the cases that worked.** Coverage is reported next to them
   (`results/coverage.csv`): Orb changes the crystal form of 3 of 33 materials; MatterSim predicts a
   mechanically unstable elastic tensor for Ti and MoS₂, MACE for h-BN; for thermal expansion, 3
   (MACE) and 2 (MatterSim) materials are dynamically unstable, and QHA itself breaks down within
   the temperature window for 2 (MACE) and 1 (MatterSim) of the non-layered materials.

\* MatterSim runs through its official package (finding 5). Class-by-class results are in the
trust map above and `results/trust_map.csv`.

## How this relates to other benchmarks

Two published benchmarks overlap closely, and this one should be read alongside them:

* **[CHIPS-FF](https://arxiv.org/abs/2412.10516)** (Wines and Choudhary, NIST) evaluates 16 universal
  force fields on 104 semiconductor-relevant materials: structure, elastic constants, phonons,
  defects, surfaces, interfaces and amorphous Si. Its comparisons are almost entirely against
  JARVIS-DFT (vdW-DF-optB88). Its software can compute QHA thermal expansion, but no
  thermal-expansion results were reported.
* **[UniFFBench](https://arxiv.org/abs/2508.05762)** (Mannan et al.) evaluates six universal force
  fields against experiment on about 1,300 mineral structures, including measured elastic
  constants, and reports a gap between computational-benchmark and experimental accuracy. It does
  not evaluate thermal expansion.

What ChipFF Bench adds is narrower: sourced experimental references (with quotes) for a set of
device materials, thermal expansion against experiment, side-by-side DFT and experiment for every
result, and investigations of simulation failures (a model export whose energies depend on
neighbour-list order, a barostat bias, and where each model's thermal expansion breaks down).

## What's measured

| Property | Method (all through kUPS) | DFT reference | Experimental reference |
|---|---|---|---|
| Lattice constant / volume | L-BFGS cell + atom relaxation from the MP structure, fmax 0.001 eV/Å | MP PBE relaxed structure | room-temperature diffraction values |
| Bulk modulus | full elastic tensor: 24 strains (6 Voigt × ±0.5 %, ±1 %), ions relaxed, stress from kUPS → K_VRH, K_Reuss; plus a Birch–Murnaghan E(V) cross-check | MP PBE elastic tensor (K_VRH) | ultrasonic / Brillouin elastic constants or EOS fits to compression data |
| Thermal expansion | quasi-harmonic approximation: phonons (phonopy, forces via kUPS) at 9 volumes, minimise E(V) + F_vib(V,T) → α_V(T), averaged over a pre-registered temperature window ([why not MD](thermal_method.md)) | — (not available from static DFT) | high-temperature dilatometry / diffraction, averaged over the same temperature window |

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
  (`provenance.md`); `chipff analyze` refuses to mix results from different code or settings.
* **Written rules for every judgement call** (`configs/benchmark.yaml`): thermal-expansion windows run
  from 0.75 × the Debye temperature (min 300 K) to half the melting point, 50 K below any phase change;
  phonon supercells are ≥ 10 Å across. Materials where a rule can't be applied get fixed temperatures
  with the reason written down. Changes of method or rule are recorded in the config with their date
  and reason (e.g. the switch from MD to QHA, `thermal_method.md`).

## Robustness and statistics

Averages over ~30 materials can rank models by chance, and simulation results can hinge on
arbitrary settings. So every headline comparison is backed by three kinds of check, explained in
[`robustness.md`](robustness.md):

* **Confidence intervals.** A bootstrap over materials, also perturbing each experimental reference
  by its typical uncertainty, gives 95 % intervals on every error. A paired bootstrap says whether
  one model is *significantly* more accurate than another, or whether the data cannot tell them
  apart (`results/robustness/bootstrap_ci.csv`, `pairwise.csv`).
* **Sensitivity to settings.** On eight representative materials, one setting is changed at a time:
  strain size for the elastic tensor, a 10x tighter force tolerance, and starting cells 3 % smaller
  or larger. The results must not move (`static_sensitivity.json`, `chipff robustness --what static`).
* **Do models make the same mistakes?** The correlation of two models' errors against experiment,
  the error of their average, and whether their disagreement predicts that error
  (`model_agreement.csv`), each with a bootstrap interval. Strongly shared errors suggest a common
  cause such as the training reference; weakly correlated ones mean a second model adds information.
  In this data disagreement tracks error only for thermal expansion, and even there the interval
  reaches zero; for lattice constants and bulk moduli it does not track error.
* **Convergence of thermal expansion.** QHA settings were checked on six cases (Si, GaAs, Cu, Ta, InP and
  monoclinic HfO₂; [`thermal_failure_study.md`](thermal_failure_study.md)). A 3x larger
  displacement and a 14 Å supercell change α(300 K) by ≤ 2 % (MACE InP: +7 %; the 14 Å check was not run
  for MACE on HfO₂, Cu and Ta). The volume-scan range changes it by up to 9 % (Si) and 12 % (HfO₂). For HfO₂,
  the 400–1500 K average also moves by 16–25 % with how interpolation-imaginary modes are treated. These
  figures are not established for other materials. The same checks found that the acoustic modes at Γ
  entered the free energy at random; the size of that effect depends on q-mesh density and force noise.
  At the benchmark's settings it made repeated runs scatter by up to ±8 %. Those modes are now excluded,
  and the published QHA numbers come from the corrected rerun (median change 0.7 %;
  [`thermal_method.md`](thermal_method.md)). The MD seed and time-step reruns
  (`chipff robustness --what md`) belong to the MD cross-check route.

Static properties are deterministic, so "pass@k"-style repeated sampling doesn't apply to them; the
questions above are its counterparts here.

## Reproduce

```bash
uv venv --python 3.12 && uv pip install -e ".[uma,mcp,dev]"
uv pip install -r env/requirements-lock.txt   # optional: the exact versions the results used
python scripts/verify_checkpoints.py  # model files match the ones the results used (configs/checkpoints.json)
cp .env.example .env                  # add your free Materials Project API key
chipff fetch                          # MP structures + DFT references -> data/mp/
chipff static                         # lattice, elastic tensor, EOS for the kUPS models (CPU, ~1 h)
# MatterSim through its official package, in its own environment:
uv venv .venv-mattersim --python 3.12 && uv pip install --python .venv-mattersim/bin/python -r env/requirements-mattersim-lock.txt
PYTHONPATH=src .venv-mattersim/bin/python -m chipff.cli static -m mattersim-5m-native
chipff qha                            # thermal expansion, quasi-harmonic (CPU, ~1-2 h per model)
chipff analyze && chipff report       # results/*.csv, report/index.html
pytest -q
```

UMA is gated: accept Meta's license at <https://huggingface.co/facebook/UMA> and run
`hf auth login`. The original NPT-MD route (`chipff thermal`, `notebooks/thermal_expansion_gpu.ipynb`)
is kept for cross-checks; it is not used for the published numbers because of its cost and a bias in
kUPS's isotropic barostat (`thermal_method.md`, reproducer `scripts/repro_kups_barostat_bias.py`).

Validation scripts any model must pass: `scripts/check_stress.py <model>` (reported stress equals the
strain derivative of the model's own energy) and `scripts/check_batch_consistency.py <model>` (a
structure's energy doesn't depend on what else is in the batch).

Raw per-model results are committed under `results/raw/`, so `chipff analyze && chipff report`
rebuilds every table and figure without rerunning a simulation.

## Agent tool (MCP)

```bash
chipff-mcp     # stdio MCP server
```

* `recommend_model(material, property, temperature_K)` — models ranked by their measured errors for a
  material or class, with the per-material evidence and whether the benchmark resolves the
  difference; near 300 K it uses the 300 K comparison. It retrieves benchmark evidence: it is not a
  calibrated error estimate for other materials or temperatures.
* `get_benchmark(query)` — stored results for a material or class, with references and sources
* `check_material(cif)` — relaxes a new structure with every available model (MatterSim needs its own
  package installed) and reports where they disagree. Treat disagreement as an exploratory signal:
  in this benchmark it did not track error for lattice constants or bulk moduli.

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
  the volume dependence of the phonons, which matters most near melting (windows stop at T_m/2), and it
  fails near phase transitions and for crystals stabilised by anharmonicity (cubic SrTiO₃). The volume
  scan keeps the cell shape fixed: exact for cubic crystals, approximate otherwise; layered materials are
  computed but not graded. Crystals unstable in a model (imaginary phonons) are excluded. Phonopy leaves
  imaginary modes out of the free energy; they are capped at 2 % of the mesh, and in the six-case study
  putting them back moved α(300 K) by ≤ 1 % except for HfO₂.
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
* **Independent project.** Built on kUPS and CuspAI's published model exports; not affiliated with
  or endorsed by CuspAI, Meta, Microsoft, Orbital Materials or the MACE developers.

