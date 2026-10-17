# ChipFF Bench

**How reliable are today's open ML force fields for the materials chips are made of?**

ChipFF Bench measures four universal ML force fields (MACE-MPA-0, Orb v3, MatterSim v1, UMA) on
33 chip materials — semiconductors, gate and capacitor dielectrics, interconnect metals, barriers
and silicides, and layered 2D materials — for three properties that decide whether a film stack
survives processing: **lattice constant, bulk modulus and thermal expansion**. Every number is
compared against Materials Project DFT (PBE) and against sourced experimental values. All
simulations run through CuspAI's open-source [kUPS](https://github.com/cusp-ai-oss/kups) toolkit.

<!-- FINDINGS -->

## What's measured

| Property | Method (all through kUPS) | DFT reference | Experimental reference |
|---|---|---|---|
| Lattice constant / volume | L-BFGS cell + atom relaxation from the MP structure, fmax 0.001 eV/Å | MP PBE relaxed structure | room-temperature diffraction values |
| Bulk modulus | full elastic tensor: 24 strains (6 Voigt × ±0.5 %, ±1 %), ions relaxed, stress from kUPS → K_VRH, K_Reuss; plus a Birch–Murnaghan E(V) cross-check | MP PBE elastic tensor (K_VRH) | ultrasonic / Brillouin elastic constants or EOS fits to compression data |
| Thermal expansion | NPT MD at P = 0 (isotropic `csvr_npt` for cubic, flexible-cell `baoab_npt_langevin` otherwise), 3 temperatures, slope of ⟨V⟩(T) | — (not available from static DFT) | high-temperature dilatometry / diffraction, averaged over the same temperature window |

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
  within 5 % of the elastic-tensor value; MD temperature and pressure on target; mean volume
  converged; short NVE runs conserve energy.
* **Written rules for every judgement call** (`configs/benchmark.yaml`): MD temperatures are above
  0.75 × the Debye temperature, below half the melting point and 50 K below any phase change; MD
  runs until the volume's standard error is below 0.02 %; supercells are ≥ 10 Å across.
  Materials where a rule can't be applied get fixed temperatures with the reason written down.

## Reproduce

```bash
uv venv --python 3.12 && uv pip install -e ".[uma,mcp,dev]"
cp .env.example .env                  # add your free Materials Project API key
chipff fetch                          # MP structures + DFT references -> data/mp/
chipff static                         # lattice, elastic tensor, EOS for all models (CPU, ~1 h)
chipff thermal                        # NPT MD (GPU; see notebooks/thermal_expansion_gpu.ipynb)
chipff analyze && chipff report       # results/*.csv, report/index.html
pytest -q
```

UMA is gated: accept Meta's license at <https://huggingface.co/facebook/UMA> and run
`hf auth login`. Thermal expansion needs a GPU; the notebook runs it on a free Kaggle or Colab GPU
and writes `results/raw/<model>/thermal.json`, which `chipff analyze` picks up.

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
* **Classical MD.** Thermal expansion is compared only where classical statistics hold
  (T ≥ 0.75 Θ_D). Graphite's and h-BN's negative in-plane expansion is a quantum effect classical MD
  can't reproduce; their volumetric expansion is dominated by the c axis.
* **Experimental values vary.** Sources disagree by several percent (e.g. Ge bulk modulus 71–75 GPa,
  hBN 18–37 GPa), and some values are weaker than others (InP expansion given as a constant average;
  NiSi per-axis expansion from a conference poster). The notes in `data/experimental/` say which.
  MoS₂ has no accessible experimental thermal expansion and is compared model-to-model only; CoSi₂ has
  only a room-temperature value.
* **Materials Project's own data has gaps.** MP's elastic tensor for hcp Co is unphysical (negative
  K) and is excluded. For layered solids, PBE itself misses the interlayer binding, so "vs DFT" there
  measures agreement with a flawed reference.
* **Model versions.** Results apply to the exact model files listed in `src/chipff/models.py`
  (CuspAI's JAX exports of MACE, Orb and MatterSim; Meta's UMA checkpoint via kUPS's PyTorch bridge).
* **Independent project.** Built on kUPS and CuspAI's published model exports; not affiliated with
  or endorsed by CuspAI, Meta, Microsoft, Orbital Materials or the MACE developers.

## License

Code: MIT. Model weights keep their own licenses (MIT, Apache-2.0, FAIR Chemistry License).
Experimental values are facts cited from the listed sources.
