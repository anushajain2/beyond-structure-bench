# Why MACE-MPA-0 and MatterSim v1 mispredict thermal expansion: a controlled study

The benchmark's QHA results (`results/thermal_expansion.csv`) show large, model-specific errors at 300 K:
MACE-MPA-0 overshoots Ta (+177 %) and GaAs (+110 %), and MatterSim v1 overshoots InP (+123 %), Si (+85 %)
and GaAs (+69 %). Yet MACE gets Si within 1 %, and MatterSim gets Ta within 16 %. This study takes six cases (Si, GaAs, Cu,
Ta, InP and monoclinic HfO₂) and asks three questions:

1. **Is it the software route?** Do the backends the benchmark used give the same energies, forces and
   stresses as the official packages?
2. **Is it numerics?** How much do the QHA settings move α, including how phonopy treats imaginary modes?
3. **If it is the model, which ingredient?** α_V ≈ γ C_V / (K_T V) is split into the Grüneisen parameter,
   heat capacity, bulk modulus and volume, and each is compared with experiment.

Everything is reproduced by `scripts/thermal_failure_study.py`, and the raw data are in `results/thermal_failure/`
(see [Reproduce](#reproduce)). The tables below are generated from the CSVs by `analyze` and are copied from
`results/thermal_failure/tables.md`.

## Summary

* **The software route is not the cause for MACE.** On identical structures the kUPS export and the official
  `mace-torch` package agree to ≤ 0.01 meV/atom in energy and ≤ 0.04 meV/Å in force. The force response to a phonon
  displacement agrees to 0.04 %. **MatterSim's kUPS export is unusable**: it returns NaN on primitive cells, is off by up
  to 0.7 eV/atom elsewhere, and gets the displacement response wrong by 5–54 %. That confirms the benchmark's
  decision to run MatterSim through its official package.
* **The published QHA contains a numerical defect, but it is small next to the model errors.** `chipff.qha` lets the
  three acoustic modes at Γ into the vibrational free energy whenever their computed frequency (≈ 10⁻⁷ THz, sign random)
  happens to be positive. That adds random 0.05–0.2 meV/atom jumps between volumes, so repeated runs scatter by up to
  ±8 % in α(300 K) (MatterSim Si; MACE InP +6 %). It also makes MatterSim results irreproducible: GaAs gave 28.5 / 29.9 /
  28.7 in three fresh processes. With the modes excluded, the runs agree to 0.1 %. For these six cases the published
  values happen to lie within ±2 % of the corrected ones.
* **Once that is fixed, the other numerical settings are converged at the level that matters.** A 3× larger
  displacement and a 14 Å supercell move α(300 K) by ≤ 2 %, except MACE InP at 14 Å (+7 %). The volume-scan range moves it
  by up to 9 % (MACE Si) and 12 % (MACE HfO₂). Keeping the imaginary modes that phonopy drops moves it by ≤ 1 %, except
  HfO₂ (+6 % MACE). None of these comes near the 70–180 % errors.
* **The large errors are the models' Grüneisen parameters, sometimes compounded by a soft bulk modulus.**
  Heat capacity and volume are right to within 6 % everywhere.
  * **MACE on Ta:** γ = 4.1 against 1.56 from experiment, and every phonon mode has γ ≥ 2.1. The whole 2.6× error is γ.
    An independent check agrees: MACE's static equation of state for Ta has K′ = 7.7, against a measured 3.1.
  * **The semiconductors (MACE GaAs; MatterSim Si, GaAs, InP):** the optical modes are right (γ_TO at Γ within 5 % of
    experiment). The error is in the zone-edge transverse acoustic (TA) modes, whose negative γ normally cancels
    much of the expansion. MatterSim's TA modes are barely negative (Si TA(X) −0.64 vs −1.4 measured) or positive
    (InP). MACE's GaAs TA(L) is +1.8. On top of this, MatterSim's K_T is 17–29 % too soft for these three.
  * **MACE gets Si right partly by cancellation:** its γ is 21 % too *low* (TA(X) −2.84, too negative) while its K_T
    is 11 % too soft.
* **HfO₂ is the case where numerics and reference data matter as much as the model.** Both models give γ = 1.46
  against 1.14 (+28 %), partly offset by a 9 % stiff K. But at 400–1500 K, α depends on how imaginary
  interpolation modes are treated (+16 to +25 %) and on the volume-scan range (±13 %). The experimental reference is
  a provisional TPRC compilation. The window comparison for HfO₂ is therefore uncertain by ±20 % for reasons unrelated
  to the models.

## Scope, settings, and what was not run

* QHA settings follow `configs/benchmark.yaml` `thermal_qha` (Vinet EOS, 9 volumes 0.96–1.08 V0, supercell ≥ 10 Å,
  0.01 Å displacements, reference forces subtracted, force constants symmetrised, stability judged at commensurate
  q-points, mesh length 50). Each relaxed cell is the benchmark's own (`results/raw/<model>/lattice.json`), symmetrised
  as in `chipff.qha`. The phonon steps are those of `chipff.qha.run_qha`, which is reused for symmetrisation,
  supercells and batched forces. The raw forces are kept so that every variant can be re-analysed without new force calls.
  Rerunning the benchmark's own settings reproduces the published α(300 K) to within the Γ-acoustic noise described
  below: MACE Cu, Ta and HfO₂ to 0–1 %, the rest to ≤ 8 %.
* Backends: MACE-MPA-0 through the CuspAI tojax export in kUPS 1.0.8 (what the benchmark used) and through
  `mace-torch` 0.3.16 (`medium-mpa-0`, float64 and float32). MatterSim v1 5M through `mattersim` 1.2.5 (what the
  benchmark used) and through its kUPS tojax export (excluded from the benchmark; contrast only).
* **Skipped by the user's decision on compute time:** the 14 Å supercell check for MACE on HfO₂, Cu and Ta (the user
  approved a reduced ~45 min run instead of the full ~2 h one). The 14 Å check was run for every other case (MACE Si,
  GaAs, InP; MatterSim all six). For MACE Cu and Ta, the 0.03 Å displacement and volume-scan checks were run and moved
  α by ≤ 1 % at 300 K. A full QHA through `mace-torch` was not run either: the single-point agreement
  (0.04 % in the displacement response) makes it redundant. The MatterSim export was compared on single points only,
  because a QHA built on a broken potential would be meaningless.
* Orb v3 is not part of this study (its QHA run is paused).

## 1. Native vs export on identical structures

Each case has six structures, built from the model's benchmark-relaxed cell: the primitive cell at 1.0, 0.96 and 1.06 V0;
the benchmark's 10 Å phonon supercell undisplaced; the same with its first 0.01 Å displacement; and the supercell rattled
by 0.03 Å. *Displacement response* is the relative difference of F(displaced) − F(undisplaced) between the two routes.
That difference is what the force constants are built from.

| model | reference → other | material | max ΔE (meV/atom) | Δ[E(1.06 V0) − E(0.96 V0)] (meV/atom) | max ΔF (meV/Å) | max Δσ (GPa) | Δ displacement response | NaN frames |
|---|---|---|---|---|---|---|---|---|
| mace | mace-kups → mace-torch | Si | 0.003 | 0.002 | 0.015 | 0.0001 | 0.0285 % | 0 |
| mace | mace-kups → mace-torch | GaAs | 0.002 | 0.000 | 0.011 | 0.0001 | 0.0152 % | 0 |
| mace | mace-kups → mace-torch | Cu | 0.005 | 0.002 | 0.004 | 0.0001 | 0.00795 % | 0 |
| mace | mace-kups → mace-torch | Ta | 0.006 | 0.001 | 0.012 | 0.0003 | 0.0233 % | 0 |
| mace | mace-kups → mace-torch | InP | 0.001 | 0.001 | 0.010 | 0.0000 | 0.0195 % | 0 |
| mace | mace-kups → mace-torch | HfO2 | 0.009 | 0.000 | 0.019 | 0.0001 | 0.0124 % | 0 |
| mace | mace-kups → mace-torch32 | Si | 0.002 | 0.002 | 0.033 | 0.0002 | 0.0251 % | 0 |
| mace | mace-kups → mace-torch32 | GaAs | 0.001 | 0.000 | 0.022 | 0.0001 | 0.0196 % | 0 |
| mace | mace-kups → mace-torch32 | Cu | 0.002 | 0.002 | 0.010 | 0.0001 | 0.0134 % | 0 |
| mace | mace-kups → mace-torch32 | Ta | 0.005 | 0.001 | 0.022 | 0.0009 | 0.0413 % | 0 |
| mace | mace-kups → mace-torch32 | InP | 0.001 | 0.000 | 0.018 | 0.0000 | 0.0238 % | 0 |
| mace | mace-kups → mace-torch32 | HfO2 | 0.002 | 0.001 | 0.039 | 0.0002 | 0.0193 % | 0 |
| mattersim | mattersim-native → mattersim-kups | Si | 554.700 | – | 650.700 | 1.4210 | 14.1 % | 3 |
| mattersim | mattersim-native → mattersim-kups | GaAs | 716.200 | – | 1036.000 | 6.5480 | 54.2 % | 3 |
| mattersim | mattersim-native → mattersim-kups | Cu | 34.470 | – | 226.600 | 1.9070 | 4.82 % | 2 |
| mattersim | mattersim-native → mattersim-kups | Ta | 2.369 | – | 340.500 | 2.2180 | 17.3 % | 3 |
| mattersim | mattersim-native → mattersim-kups | InP | 628.800 | – | 717.900 | 3.6230 | 17.5 % | 3 |
| mattersim | mattersim-native → mattersim-kups | HfO2 | 24.140 | – | 1218.000 | 13.7700 | 23.6 % | 2 |

The MatterSim export returns NaN for most primitive-cell frames (2–3 of the 3 per material, 1–12 atoms), so its E(V)
differences cannot be formed. The maxima are over the frames that are finite. The MACE export is effectively exact, including
in float32. Its "_32" suffix does not cost precision at the level phonons need. The mace-torch float64 vs float32
comparison (not shown, in `agreement.csv`) is of the same size. **Conclusion: neither model's thermal-expansion error comes
from the software route the benchmark used.**

## 2. A numerical defect: Γ-point acoustic modes in the free energy

`chipff.qha.run_qha` calls `Phonopy.run_thermal_properties` with phonopy's defaults: modes with frequency ≤ 0 are left
out, and `exclude_gamma_acoustic` is off. The three acoustic modes at Γ should be exactly zero. After symmetrisation
they come out at about 10⁻⁷ THz, of random sign. Each one that happens to be positive adds kT ln(hν/kT)/N_q to F_vib.
At 300 K that is about 0.05–0.2 meV/atom (table below), and it changes from one volume to the next. The relevant
energy scale is the thermal free-energy difference across the scan, a few meV, so this is not negligible. phonopy 4.8.3
describes exactly this effect in `phonopy/phonon/thermal_properties.py` (`_treat_gamma_acoustic`) and offers
`exclude_gamma_acoustic=True` as the fix.

**This explains the irreproducible MatterSim results.** The committed GaAs α(300 K) is 29.03 and a rerun gave 30.19,
with identical package versions: mattersim 1.2.5, torch 2.14.1, ase 3.29.0 and phonopy 4.8.3, in the committed
record's provenance, in `env/requirements-mattersim-lock.txt` and in `.venv-mattersim` alike. `MatterSimCalculator` is
bit-identical on repeated single points in one process. In fresh processes its forces differ by up to 8 × 10⁻⁷ (GaAs)
to 4 × 10⁻⁶ eV/Å (Si), which is multithreaded CPU summation order; energies are identical. Force noise that small
changes the force constants by ~10⁻⁵, which flips the signs of the Γ-acoustic frequencies:

| backend | material | fresh processes | max ΔF, same process | max ΔF, across processes | α_V(300 K) as the benchmark computes it | α_V(300 K), Γ acoustic modes excluded |
|---|---|---|---|---|---|---|
| mattersim-native | GaAs | 3 | 0 | 7.9 × 10⁻⁷ eV/Å | 28.48 / 29.94 / 28.69 | 28.91 / 28.92 / 28.92 |
| mattersim-native | Si | 3 | 0 | 3.7 × 10⁻⁶ eV/Å | 14.32 / 14.38 / 14.34 | 14.50 / 14.51 / 14.50 |

Adding Gaussian noise of 3 × 10⁻⁶ eV/Å to the saved Si forces moves α(300 K) between 14.0 and 15.6 as the benchmark
computes it, and between 14.47 and 14.53 with the Γ modes excluded. MACE through kUPS is affected too. Our rerun of the
benchmark's settings differs from the published run by −1 % to +6 % (convergence table, *rerun* vs *Γ fixed*), presumably
because the batches differ and the resulting tiny force differences flip the Γ-mode signs. The batch cause was not
isolated.

**Effect on the published numbers:** the published α(300 K) of these six cases lies within ±2 % of the Γ-fixed values
(largest: MatterSim InP 28.06 vs 27.49, Ta 15.96 vs 16.26). A rerun can land anywhere within about ±8 %. The defect is real
and should be fixed; passing `exclude_gamma_acoustic=True` changes nothing else. It does not explain any of the large
errors. In the rest of this study, "Γ fixed" values are the reference.

## 3. Convergence on the hard cases

α_V(300 K) in 10⁻⁶ K⁻¹. *published*: `results/raw` (benchmark run). *rerun*: same settings, this study's data. *Γ fixed*:
Γ-point acoustic modes excluded from F_vib. Every column to its right also has them excluded, and percentages are relative to it.
"Imaginary modes kept as abs(ν)" puts every mesh mode with ν < 0 (which phonopy drops) back into F_vib at |ν|. That bounds
what dropping them hides.

| model | material | published | rerun (as benchmark) | Γ fixed | disp 0.03 Å | supercell 14 Å | scan 0.975–1.045 | scan 0.94–1.12 | imaginary modes kept as abs(ν) |
|---|---|---|---|---|---|---|---|---|---|
| mace-kups | Si | 7.83 | 7.66 (-1 %) | **7.77** | 7.77 (-0 %) | 7.81 (+0 %) | 7.59 (-2 %) | 7.09 (-9 %) | 7.77 (+0 %) |
| mace-kups | GaAs | 36.03 | 36.85 (+1 %) | **36.30** | 36.19 (-0 %) | 36.29 (-0 %) | 36.52 (+1 %) | 35.41 (-2 %) | 36.30 (+0 %) |
| mace-kups | Cu | 51.79 | 51.79 (+0 %) | **51.65** | 51.64 (-0 %) | skipped | 51.76 (+0 %) | 51.70 (+0 %) | 51.65 (+0 %) |
| mace-kups | Ta | 52.53 | 52.53 (-1 %)† | **52.82** | 52.56 (-0 %) | skipped | 53.44 (+1 %)† | 52.84 (+0 %) | 53.04 (+0 %)† |
| mace-kups | InP | 10.98 | 11.67 (+6 %) | **11.06** | 11.09 (+0 %) | 11.87 (+7 %) | 10.67 (-4 %) | 11.07 (+0 %) | 11.06 (+0 %) |
| mace-kups | HfO2 | 18.48 | 18.46 (+1 %) | **18.37** | 18.43 (+0 %) | skipped | 16.13 (-12 %) | 19.17 (+4 %) | 19.41 (+6 %) |
| mattersim-native | Si | 14.56 | 13.34 (-8 %) | **14.49** | 14.36 (-1 %) | 14.47 (-0 %) | 14.48 (-0 %) | 14.42 (-0 %) | 14.49 (+0 %) |
| mattersim-native | GaAs | 29.03 | 29.50 (+2 %) | **28.92** | 28.91 (-0 %) | 29.01 (+0 %) | 28.90 (-0 %) | 29.06 (+0 %) | 28.92 (+0 %) |
| mattersim-native | Cu | 48.79 | 48.92 (-0 %) | **49.09** | 49.15 (+0 %) | 49.08 (-0 %) | 49.32 (+0 %) | 48.51 (-1 %) | 49.09 (+0 %) |
| mattersim-native | Ta | 15.96 | 16.19 (-0 %) | **16.26** | 16.41 (+1 %) | 16.32 (+0 %) | 16.66 (+2 %) | 15.71 (-3 %) | 16.26 (+0 %) |
| mattersim-native | InP | 28.06 | 26.72 (-3 %) | **27.49** | 27.37 (-0 %) | 27.56 (+0 %) | 28.20 (+3 %) | 26.55 (-3 %) | 27.49 (+0 %) |
| mattersim-native | HfO2 | 20.33 | 20.03 (-1 %) | **20.23** | 20.24 (+0 %) | 19.88 (-2 %) | 19.37 (-4 %) | 21.46 (+6 %) | 20.04 (-1 %) |

† V(T) leaves the stable scanned range inside the material's window (the benchmark's "volume inside scan" check fails).
The 300 K value is unaffected, but the window average is not usable. "skipped": not run, by the user's decision on
compute time (see Scope).

The same checks, averaged over each material's pre-registered window:

| model | material | window (K) | Γ fixed | disp 0.03 Å | supercell 14 Å | scan 0.975–1.045 | scan 0.94–1.12 | imaginary modes kept |
|---|---|---|---|---|---|---|---|---|
| mace-kups | Si | 500–800 | 11.05 | 11.07 | 11.07 | 11.02 | 10.30 | 11.05 |
| mace-kups | GaAs | 300–750 | 37.79 | 37.74 | 37.82 | 37.61 | 37.42 | 37.79 |
| mace-kups | Cu | 300–650 | 57.49 | 57.43 | skipped | 58.80 | 56.64 | 57.49 |
| mace-kups | Ta | 300–1600 | 46.70 | 46.25 | skipped | 69.57† | 41.41 | 49.04† |
| mace-kups | InP | 350–650 | 13.24 | 13.28 | 14.09 | 12.94 | 13.18 | 13.24 |
| mace-kups | HfO2 | 400–1500 | 19.47 | 19.52 | skipped | 22.04 | 19.57 | 24.29 |
| mattersim-native | Si | 500–800 | 19.91 | 19.76 | 19.88 | 19.96 | 19.75 | 19.91 |
| mattersim-native | GaAs | 300–750 | 31.82 | 31.80 | 31.93 | 32.00 | 31.78 | 31.82 |
| mattersim-native | Cu | 300–650 | 49.71 | 49.81 | 49.71 | 49.58 | 49.74 | 49.71 |
| mattersim-native | Ta | 300–1600 | 13.84 | 14.01 | 13.89 | 13.54 | 14.22 | 13.84 |
| mattersim-native | InP | 350–650 | 28.75 | 28.68 | 28.89 | 29.10 | 28.14 | 28.75 |
| mattersim-native | HfO2 | 400–1500 | 24.38 | 24.40 | 24.71 | 26.70 | 23.55 | 28.37 |

**What the free energy leaves out.** At V0 and at 1.08 V0, 300 K:

| model | material | V/V0 | mesh modes with ν < 0 | lowest mesh ν (THz) | F_vib (meV/atom) | Γ acoustic modes: F they add (meV/atom) | imaginary modes kept as abs(ν): ΔF (meV/atom) |
|---|---|---|---|---|---|---|---|
| mace-kups | Ta | 1.00 | 0.00 % | 0.00 | -57.95 | -0.157 | 0.000 |
| mace-kups | Ta | 1.08 | 0.09 % | -0.19 | -83.03 | -0.157 | -0.242 |
| mace-kups | HfO2 | 1.00 | 0.29 % | -1.69 | 33.73 | -0.082 | -0.413 |
| mace-kups | HfO2 | 1.08 | 1.11 % | -2.34 | 25.61 | -0.092 | -1.515 |
| mattersim-native | HfO2 | 1.00 | 0.10 % | -1.24 | 38.16 | -0.084 | -0.160 |
| mattersim-native | HfO2 | 1.08 | 0.52 % | -1.66 | 28.00 | -0.094 | -0.800 |

In the other cubic cases, ≤ 0.02 % of mesh modes fall below zero, and keeping them changes F by < 0.001 meV/atom (full
table: `results/thermal_failure/imaginary_modes.csv`). For HfO₂, the imaginary modes appear only between the
commensurate q-points (interpolation artefacts of a 2×2×2 supercell in a polar crystal, as `docs/thermal_method.md`
explains). They grow with volume, so dropping them biases the volume dependence of F. That matters little at 300 K
(+6 % for MACE, −1 % for MatterSim) but adds +16 % (MatterSim) to +25 % (MACE) to the 400–1500 K window average. The
14 Å (3×3×3) supercell, run for MatterSim, leaves α(300 K) within 2 % and the window within 1.4 %. So most of the
window sensitivity comes from how the leftover artefacts are treated, not from truncating the force constants.

**Reading.** Displacement amplitude and supercell size are converged everywhere they were tested. Of the 14 Å checks,
only MACE InP moved (+7 %; 5×5×5 vs 3×3×3, which is only just over 10 Å). The volume-scan range matters by up to 9 % at 300 K for
MACE Si, where positive and negative mode contributions nearly cancel, and by 12 % for HfO₂. With the Γ fix, the
methodological uncertainty at 300 K is about ±5 % for the cubic cases and ±10 % for HfO₂. At the top of the HfO₂ and Ta
windows it is larger.

## 4. Which ingredient is wrong

In the quasi-harmonic approximation α_V = γ C_V / (K_T V). Here γ is the C_V-weighted average of the mode Grüneisen
parameters, C_V the harmonic heat capacity and K_T the isothermal bulk modulus, all at the same temperature. Per
material and model:

* γ: mode Grüneisen parameters from phonopy (`PhonopyGruneisen`) at 0.985 / 1.0 / 1.015 V0 on the benchmark's q-mesh,
  weighted with each mode's heat capacity at 300 K. The acoustic modes at Γ (< 0.1 THz) are left out.
* C_V: from the same modes at V0. K_T and V: from the QHA free-energy fit at 300 K (Γ-fixed, benchmark scan).
* Experiment: γ_exp = α_V K_T V / C_V from sourced values. α_V, K and the lattice come from the benchmark's own references
  (`data/experimental/*.json`). C_p comes from NIST-JANAF (Si, Cu, Ta; Chase 1998, Shomate fits on the NIST WebBook), the Ioffe NSM
  archive (GaAs 0.33 and InP 0.31 J g⁻¹ K⁻¹) and Zhou, Shi, Woodfield & Navrotsky, *J. Chem. Thermodyn.* 43, 970 (2011)
  for HfO₂ (57.73 J K⁻¹ mol⁻¹ at 298.15 K, NIST ThermoML). Adiabatic moduli are converted to K_T, and C_p to C_V; both
  corrections are 0.3–3 %.

The γ C_V/(K_T V) estimate reproduces the full QHA α to within 10 % (15 % for MatterSim Ta), so the split is meaningful.
The ratios multiply: **α ratio ≈ γ ratio × C_V ratio × (1/K ratio) × (1/V ratio)**.

| model | material | α_V QHA | α_V from γC_V/K_TV | α_V exp | γ model | γ exp | K_T model (GPa) | K_T exp | C_V model (k_B/atom) | C_V exp | V model (Å³/atom) | V exp | **α ratio** | γ ratio | C_V ratio | 1/K ratio | 1/V ratio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mace-kups | Si | 7.8 | 7.2 | 7.9 | 0.37 | 0.46 | 87 | 98 | 2.52 | 2.40 | 20.54 | 20.02 | **0.91** | 0.79 | 1.05 | 1.13 | 0.97 |
| mace-kups | GaAs | 36.3 | 35.3 | 17.2 | 1.30 | 0.74 | 60 | 75 | 2.81 | 2.86 | 23.92 | 22.58 | **2.06** | 1.77 | 0.98 | 1.25 | 0.94 |
| mace-kups | Cu | 51.7 | 49.8 | 49.7 | 1.85 | 1.99 | 120 | 134 | 2.85 | 2.86 | 12.25 | 11.81 | **1.00** | 0.93 | 1.00 | 1.12 | 0.96 |
| mace-kups | Ta | 52.8 | 49.5 | 19.0 | 4.09 | 1.56 | 181 | 190 | 2.94 | 3.02 | 18.56 | 18.06 | **2.61** | 2.62 | 0.97 | 1.05 | 0.97 |
| mace-kups | InP | 11.1 | 10.0 | 12.6 | 0.46 | 0.60 | 65 | 71 | 2.74 | 2.71 | 26.84 | 25.27 | **0.79** | 0.77 | 1.01 | 1.08 | 0.94 |
| mace-kups | HfO2 | 18.4 | 19.9 | 16.9 | 1.46 | 1.14 | 201 | 185 | 2.35 | 2.30 | 11.85 | 11.53 | **1.18** | 1.29 | 1.02 | 0.92 | 0.97 |
| mattersim-native | Si | 14.5 | 13.5 | 7.9 | 0.67 | 0.46 | 81 | 98 | 2.44 | 2.40 | 20.60 | 20.02 | **1.71** | 1.44 | 1.02 | 1.20 | 0.97 |
| mattersim-native | GaAs | 28.9 | 28.3 | 17.2 | 0.92 | 0.74 | 53 | 75 | 2.83 | 2.86 | 23.91 | 22.58 | **1.65** | 1.25 | 0.99 | 1.41 | 0.94 |
| mattersim-native | Cu | 49.1 | 50.7 | 49.7 | 2.16 | 1.99 | 139 | 134 | 2.85 | 2.86 | 12.04 | 11.81 | **1.02** | 1.09 | 1.00 | 0.96 | 0.98 |
| mattersim-native | Ta | 16.3 | 18.7 | 19.0 | 1.68 | 1.56 | 199 | 190 | 2.95 | 3.02 | 18.43 | 18.06 | **0.99** | 1.07 | 0.98 | 0.96 | 0.98 |
| mattersim-native | InP | 27.5 | 28.0 | 12.6 | 1.08 | 0.60 | 55 | 71 | 2.75 | 2.71 | 26.76 | 25.27 | **2.23** | 1.79 | 1.02 | 1.30 | 0.94 |
| mattersim-native | HfO2 | 20.2 | 19.4 | 16.9 | 1.46 | 1.14 | 202 | 185 | 2.31 | 2.30 | 11.82 | 11.53 | **1.15** | 1.28 | 1.00 | 0.92 | 0.97 |

Where γ comes from (C_V-weighted mode Grüneisen parameters at 300 K):

| model | material | γ | acoustic branches | optical branches | contribution of modes with γ < 0 | share of modes with γ < 0 | lowest mode γ | γ TA(X) | γ TA(L) | γ optical at Γ |
|---|---|---|---|---|---|---|---|---|---|---|
| mace-kups | Si | 0.37 | -0.69 | 1.67 | -0.48 | 33 % | -2.81 | -2.84 | -1.68 | 1.15 |
| mace-kups | GaAs | 1.30 | 0.98 | 1.66 | -0.01 | 3 % | -0.82 | -0.86 | 1.80 | 1.38 |
| mace-kups | Cu | 1.85 | 1.85 | – | -0.00 | 0 % | -1.16 | 1.87 | 1.23 | – |
| mace-kups | Ta | 4.09 | 4.09 | – | 0.00 | 0 % | 2.11 | – | – | – |
| mace-kups | InP | 0.46 | -0.31 | 1.36 | -0.33 | 33 % | -1.54 | -1.03 | -1.46 | 1.46 |
| mace-kups | HfO2 | 1.46 | 3.33 | 1.25 | -0.04 | 5 % | -5.01 | – | – | – |
| mattersim-native | Si | 0.67 | 0.07 | 1.44 | -0.15 | 32 % | -0.64 | -0.64 | -0.58 | 1.21 |
| mattersim-native | GaAs | 0.92 | 0.30 | 1.60 | -0.05 | 20 % | -1.20 | -0.22 | -0.42 | 1.33 |
| mattersim-native | Cu | 2.16 | 2.16 | – | 0.00 | 0 % | 0.91 | 2.10 | 1.59 | – |
| mattersim-native | Ta | 1.68 | 1.68 | – | -0.00 | 1 % | -1.30 | – | – | – |
| mattersim-native | InP | 1.08 | 0.77 | 1.44 | 0.00 | 0 % | 0.25 | 0.75 | 0.27 | 1.38 |
| mattersim-native | HfO2 | 1.46 | 2.19 | 1.37 | -0.03 | 4 % | -4.71 | – | – | – |

Experimental mode Grüneisen parameters: Si TA(X) = −1.4 and TA(L) = −1.3 (as quoted by Rignanese, Michenaud & Gonze,
arXiv:mtrl-th/9509002, their ref. 25); TO(Γ) = 1.39 for GaAs and 1.44 for InP (Aoki, Anastassakis & Cardona 1984, as
tabulated in arXiv:1107.0196, Table 4). The same table lists negative experimental TA(L) values for the III–V compounds,
but its column alignment is garbled in the text, so only the sign is used here. The model "optical at Γ" values have no
LO–TO splitting, as in the QHA, so they compare with TO. TA(X) and TA(L) are computed for the fcc-lattice crystals
only (for Cu they are the two lowest branches at those points), not for bcc Ta or monoclinic HfO₂.

A second, independent check on γ for the metals comes from the benchmark's static equation-of-state fits
(`results/bulk_modulus.csv`, Birch–Murnaghan over 0.94–1.06 V0). The Slater estimate γ ≈ K′/2 − 1/6 holds roughly for
simple metals:

| | K′ (static EOS) | Slater γ | phonon γ (this study) |
|---|---|---|---|
| MACE, Ta | 7.68 | 3.67 | 4.09 |
| MatterSim, Ta | 3.63 | 1.65 | 1.68 |
| MACE, Cu | 4.38 | 2.03 | 1.85 |
| MatterSim, Cu | 5.48 | 2.57 | 2.16 |

The measured K₀′ of Ta is 3.07 ± 0.14 (Vinet fit to diamond-anvil-cell data; Dewaele, Loubeyre & Mezouar,
arXiv:cond-mat/0403080). Their fit gives K₀ = 198 GPa, in line with the 194 GPa ultrasonic value.

## 5. Per-material conclusions

Errors at 300 K, Γ-fixed QHA, against the benchmark's experimental α_V.

**Si.** *MACE −1 %: right, partly by cancellation.* MACE's TA modes are too strongly negative (TA(X) −2.84 vs −1.4), so
its γ is 21 % low. Its K_T is 11 % soft and its C_V 5 % high, and these offset the low γ. *MatterSim +84 %: model (γ and K).*
Its TA modes are barely negative (TA(X) −0.64), so γ is 44 % high, and K_T is 17 % soft. About two-thirds of the log-error
is γ and one-third is K. The numerical part is small: the Γ-acoustic defect made one MatterSim rerun 8 % low (the published value is
within 1 %), and the wider volume scan gives −9 % for MACE.

**GaAs.** *MACE +111 %: model, mostly γ.* γ is 1.77× too large, and about 80 % of the log-error is γ. The optical γ
is right (1.38 vs 1.39); the acoustic branches are wrong. Only 3 % of modes have negative γ (Si and InP have 33 %), and
TA(L) is +1.8 where experiment is negative. A 20 % soft K_T adds the rest. *MatterSim +68 %: model, γ and K about
equally.* γ is +25 % (weak negative TA modes: TA(X) −0.22, TA(L) −0.42). K_T is 29 % too soft (53 vs 75 GPa), which
accounts for more of the log-error than γ does. All convergence checks move α by ≤ 2 %.

**Cu.** *Both models within 4 %.* All ingredients are within 12 %. MACE's γ is 7 % low and its K_T 11 % soft, so these
cancel. Cu is the control case and behaves as one.

**Ta.** *MACE +179 %: model, entirely γ.* γ = 4.09 against 1.56. Every mode has γ ≥ 2.1, so the whole phonon spectrum
stiffens too fast under compression. K_T, C_V and V are each within 5 %. The static EOS confirms this independently:
MACE's K′ = 7.7 against 3.1 measured, while MatterSim (K′ = 3.6) reproduces Ta's γ. The 0.03 Å and volume-scan checks
move α(300 K) by ≤ 1 %, and the exported model matches `mace-torch` exactly. So this is a property of the MACE-MPA-0
potential, not of the pipeline (the 14 Å supercell check was skipped; see Scope). The window average (300–1600 K) is
not usable: the predicted volume runs out of the stable scan. *MatterSim −14 %:* all ingredients within 7 %. The
residual sits mostly between the γ formula and the full QHA (18.7 vs 16.3), i.e. in the volume dependence of γ.

**InP.** *MACE −12 %: γ too low.* MACE has strong negative TA modes (TA(X) −1.03, TA(L) −1.46), so γ is 23 % low.
The experimental reference is the 300–910 K average recommended by Glazov et al. (4.19 × 10⁻⁶ K⁻¹ linear). The Ioffe
room-temperature value (4.60) would make MACE −20 %. *MatterSim +119 %: model, mostly γ.* MatterSim has no negative-γ
modes at all (TA(X) +0.75, TA(L) +0.27), so γ is 79 % too large. K_T 23 % soft adds the rest; about three-quarters of
the log-error is γ. The optical γ is right (1.38 vs 1.44). Numerical part: for MACE, a rerun differed by +6 % through the Γ-acoustic defect (the published value is within
1 % of the corrected one), the 14 Å supercell adds +7 %, and the narrow scan −4 %. That is about ±7 % in total, small next
to MatterSim's error but a large share of MACE's.

**HfO₂.** *MACE +9 %, MatterSim +20 % at 300 K, both against a weak reference.* Both models give γ = 1.46 against
1.14 (acoustic branches 2.2–3.3, optical 1.25–1.37). In both models a 9 % stiff K partly offsets the high γ. The reference
α_V (16.9 × 10⁻⁶ K⁻¹) is a sum of TPRC axial interval means over 293–400 K (centred at 346 K; TPRC marks it provisional,
±10 %). The experimental K (185 ± 23 GPa) is uncertain by 12 %. So γ_exp is uncertain by roughly ±20 %, and only the
direction (γ too high) is suggestive. The numerical part is large for HfO₂. The volume-scan range moves α(300 K) by −12 %
to +4 % (MACE). Treatment of the interpolation-imaginary modes moves the 400–1500 K window average by +16 to +25 %.
Isotropic volume scaling also ignores HfO₂'s strongly anisotropic expansion: the measured b axis barely expands.
**The HfO₂ window comparison in the benchmark should carry an uncertainty of about ±20 % for numerical and reference
reasons alone.**

**Pattern.** Heat capacity and volume are not the problem (within 6 % everywhere). The bulk modulus matters for
MatterSim's semiconductors, where it is 17–29 % soft (consistent with the benchmark's static K errors of −22 to −26 % for
GaAs and InP). The dominant error is the volume dependence of the phonons, γ. For tetrahedral semiconductors, the
models get the optical-mode γ right but not the delicate negative γ of the zone-edge TA (bond-bending) modes, which
partly cancel the positive contributions in real Si, GaAs and InP. MatterSim makes those modes too weakly negative and
gets α too large. MACE makes them too strongly negative in Si and InP and too weakly negative in GaAs. It gets α about
right for Si (helped by a soft K), too small for InP and too large for GaAs. For Ta, MACE's whole phonon spectrum has γ ≈ 4.

## 6. Recommendations

1. Pass `exclude_gamma_acoustic=True` to `run_thermal_properties` in `src/chipff/qha.py` and rerun the QHA. That makes
   MatterSim results reproducible and removes a ±8 % noise term from all models. This study did not change the
   benchmark code or any committed result.
2. Report HfO₂ (and other low-symmetry polar oxides) with the larger methodological uncertainty above, or compare at
   300 K only.
3. For a paper built around explaining the failures, the γ split above is the controlled explanation. The zone-edge
   TA γ of tetrahedral semiconductors, and K′ for metals, are cheap diagnostics that predict the thermal-expansion error
   without a full QHA.

## Reproduce

From the repository root (MatterSim in `.venv-mattersim` as in the README; `mace-torch` in its own environment:
`uv venv .venv-mace --python 3.12 && uv pip install --python .venv-mace/bin/python mace-torch phonopy pymatgen pyyaml ase`):

```bash
S=scripts/thermal_failure_study.py
PYTHONPATH=src .venv/bin/python $S structures
for b in mace-kups mattersim-kups; do PYTHONPATH=src .venv/bin/python $S points --backend $b; done
for b in mace-torch mace-torch32; do PYTHONPATH=src .venv-mace/bin/python $S points --backend $b; done
PYTHONPATH=src .venv-mattersim/bin/python $S points --backend mattersim-native
for v in grid disp03 sc14; do
  PYTHONPATH=src .venv/bin/python $S phonons --backend mace-kups --variant $v           # sc14: --materials Si GaAs InP
  PYTHONPATH=src .venv-mattersim/bin/python $S phonons --backend mattersim-native --variant $v
done
for t in 1 2 3; do PYTHONPATH=src .venv-mattersim/bin/python $S determinism --backend mattersim-native --materials GaAs Si --tag $t; done
PYTHONPATH=src .venv/bin/python $S analyze            # -> results/thermal_failure/*.csv, tables.md
```

Raw data are committed: `structures/`, `points/<backend>.json`, `phonons/<backend>/<material>_<variant>.npz` (relaxed
cells, energies, displacement datasets and reference-subtracted forces per volume) and `determinism/`. So `analyze`
rebuilds every table without a force call. Measured wall times on an M-series laptop CPU, per material: MatterSim 10–300 s,
MACE through kUPS 30–700 s (HfO₂ is the slowest, 12 min for 13 volumes).
