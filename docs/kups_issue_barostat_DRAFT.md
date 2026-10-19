<!-- DRAFT for review. Not posted. Target: https://github.com/cusp-ai-oss/kups/issues -->

**Title:** `csvr_npt` equilibrates at a volume where the mean pressure is ~ −NkT/V, not the target

While computing thermal expansion with `csvr_npt` (kups 1.0.8), the mean pressure stayed at
−0.3 to −0.9 GPa for target 0 GPa, increasingly negative with temperature, even after 45 ps.

To check whether this is a measurement artefact or a real offset, I ran NVT (`csvr`) at the mean
volume `csvr_npt` settled on. The crystal is genuinely under tension there:

| 32-atom fcc Cu, MACE-MPA-0, 650 K | ⟨V⟩ | ⟨P⟩ |
|---|---|---|
| `csvr_npt`, P0 = 0 | 402.9 Å³ | −0.83 GPa |
| `csvr` (NVT) at 402.9 Å³ | — | −0.88 ± 0.11 GPa |
| N k T / V | | 0.71 GPa |

The pressure uses the same expression as `StochasticCellRescalingStep`
(`instantaneous_pressure`: 2K/(dV) + Tr σ / d with `stress_via_virial_theorem`).

Reproducer (~30 min on a laptop CPU):
[`repro_kups_barostat_bias.py`](https://github.com/anushajain2/chipff-bench/blob/main/scripts/repro_kups_barostat_bias.py)

Possibly related, from reading `StochasticCellRescalingStep`:
- positions are rescaled by μ but momenta are not (Bernetti & Bussi rescale velocities by 1/μ);
- the random term is drawn as one scalar per step, `jax.random.normal(key, dtype=volume.dtype)`, so all
  systems in a batch receive the same noise (their volumes stay correlated).

Because the offset is ∝ T, it adds a spurious thermal expansion of about k_B/(v·K) per atom
(~9 × 10⁻⁶ K⁻¹ for Cu). Happy to test a fix.
