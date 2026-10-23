<!-- DRAFT for review. Not posted. Target: https://github.com/cusp-ai-oss/kups/issues
     Checked before drafting (2026-10-20): kups 1.0.8 is the latest release, and kups/md/integrators.py has
     not changed upstream since 2026-08-18. Closed issue #198 (batched virial stress for n_sys > 1) is a
     different problem: this reproducer runs a single system. The numbers below are from the original run
     (2026-10-18); the reproducer was not rerun for this draft. -->

**Title:** `csvr_npt` settles at a volume where the mean pressure is about −NkT/V, not the target

While computing thermal expansion with `csvr_npt` (kups 1.0.8), the mean pressure stayed at −0.3 to −0.9 GPa
for a 0 GPa target, more negative at higher temperature, in runs of up to 45 ps (Cu, Mo, W with MACE-MPA-0).

To check whether this is a measurement artefact or a real offset, I ran NVT (`csvr`) at the mean volume
`csvr_npt` settled on. The crystal is genuinely under tension there:

| 32-atom fcc Cu, MACE-MPA-0, 650 K, single system | ⟨V⟩ | ⟨P⟩ |
|---|---|---|
| `csvr_npt`, P0 = 0 | 402.9 Å³ | −0.83 GPa |
| `csvr` (NVT) at 402.9 Å³ | — | −0.88 ± 0.11 GPa |
| N k T / V, for comparison | | 0.71 GPa |

Settings: 2 fs time step, 3 ps equilibration and 10 ps production, thermostat time constant 100 fs, barostat
time constant 1000 fs, compressibility 1/(130 GPa). The pressure uses the same expression as
`StochasticCellRescalingStep` (`instantaneous_pressure`: 2K/(dV) + Tr σ / d, with `stress_via_virial_theorem`).

**Reproducer** (about 30 min on a laptop CPU; it uses a thin wrapper around kUPS from the same repository):
[`scripts/repro_kups_barostat_bias.py`](https://github.com/anushajain2/beyond-structure-bench/blob/v1.0.0/scripts/repro_kups_barostat_bias.py).
I can turn it into a kUPS-only script if that is more useful.

**Possibly related**, from reading `StochasticCellRescalingStep`:
- positions are rescaled by μ, but momenta are not (Bernetti and Bussi rescale velocities by 1/μ);
- the random term is drawn as one scalar per step, `jax.random.normal(key, dtype=volume.dtype)`, so every
  system in a batch receives the same noise and their volumes stay correlated.

**Why it matters:** because the offset grows with T, it adds a spurious thermal expansion of about
k_B/(v·K) to the volumetric coefficient (v = volume per atom, K = bulk modulus): about 8 × 10⁻⁶ K⁻¹ for Cu, a sixth of its measured value (about 50 × 10⁻⁶ K⁻¹).
More detail: [`docs/thermal_method.md`](https://github.com/anushajain2/beyond-structure-bench/blob/v1.0.0/docs/thermal_method.md).

**Environment:** kups 1.0.8, jax/jaxlib 0.11.2, Python 3.12, macOS arm64 (CPU), float64; MACE-MPA-0 export
`CuspAI/kUPS-mace-jax` revision `aa54c05`.

Happy to test a fix.
