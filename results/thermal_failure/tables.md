### Native vs export (identical structures)

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
| mace | mace-torch → mace-torch32 | Si | 0.001 | 0.000 | 0.025 | 0.0000 | 0.019 % | 0 |
| mace | mace-torch → mace-torch32 | GaAs | 0.003 | 0.000 | 0.017 | 0.0001 | 0.0158 % | 0 |
| mace | mace-torch → mace-torch32 | Cu | 0.003 | 0.001 | 0.007 | 0.0001 | 0.0125 % | 0 |
| mace | mace-torch → mace-torch32 | Ta | 0.006 | 0.002 | 0.020 | 0.0006 | 0.0384 % | 0 |
| mace | mace-torch → mace-torch32 | InP | 0.001 | 0.001 | 0.010 | 0.0000 | 0.0141 % | 0 |
| mace | mace-torch → mace-torch32 | HfO2 | 0.010 | 0.000 | 0.028 | 0.0001 | 0.0174 % | 0 |
| mattersim | mattersim-native → mattersim-kups | Si | 554.700 | – | 650.700 | 1.4210 | 14.1 % | 3 |
| mattersim | mattersim-native → mattersim-kups | GaAs | 716.200 | – | 1036.000 | 6.5480 | 54.2 % | 3 |
| mattersim | mattersim-native → mattersim-kups | Cu | 34.470 | – | 226.600 | 1.9070 | 4.82 % | 2 |
| mattersim | mattersim-native → mattersim-kups | Ta | 2.369 | – | 340.500 | 2.2180 | 17.3 % | 3 |
| mattersim | mattersim-native → mattersim-kups | InP | 628.800 | – | 717.900 | 3.6230 | 17.5 % | 3 |
| mattersim | mattersim-native → mattersim-kups | HfO2 | 24.140 | – | 1218.000 | 13.7700 | 23.6 % | 2 |

### QHA convergence, α_V(300 K) in 10⁻⁶ K⁻¹

*published*: results/raw (benchmark run). *rerun*: same settings, this study's data. *Γ fixed*: Γ-point acoustic modes excluded from F_vib; every column right of it also has them excluded. Percentages are relative to *Γ fixed*.

| model | material | published | rerun (as benchmark) | Γ fixed | disp 0.03 Å | supercell 14 Å | scan 0.975–1.045 | scan 0.94–1.12 | imaginary modes kept as abs(ν) |
|---|---|---|---|---|---|---|---|---|---|
| mace-kups | Si | 7.83 | 7.66 (-1 %) | **7.77** | 7.77 (-0 %) | 7.81 (+0 %) | 7.59 (-2 %) | 7.09 (-9 %) | 7.77 (+0 %) |
| mace-kups | GaAs | 36.03 | 36.85 (+1 %) | **36.30** | 36.19 (-0 %) | 36.29 (-0 %) | 36.52 (+1 %) | 35.41 (-2 %) | 36.30 (+0 %) |
| mace-kups | Cu | 51.79 | 51.79 (+0 %) | **51.65** | 51.64 (-0 %) | not run | 51.76 (+0 %) | 51.70 (+0 %) | 51.65 (+0 %) |
| mace-kups | Ta | 52.53 | 52.53 (-1 %)† | **52.82** | 52.56 (-0 %) | not run | 53.44 (+1 %)† | 52.84 (+0 %) | 53.04 (+0 %)† |
| mace-kups | InP | 10.98 | 11.67 (+6 %) | **11.06** | 11.09 (+0 %) | 11.87 (+7 %) | 10.67 (-4 %) | 11.07 (+0 %) | 11.06 (+0 %) |
| mace-kups | HfO2 | 18.48 | 18.46 (+1 %) | **18.37** | 18.43 (+0 %) | not run | 16.13 (-12 %) | 19.17 (+4 %) | 19.41 (+6 %) |
| mattersim-native | Si | 14.56 | 13.34 (-8 %) | **14.49** | 14.36 (-1 %) | 14.47 (-0 %) | 14.48 (-0 %) | 14.42 (-0 %) | 14.49 (+0 %) |
| mattersim-native | GaAs | 29.03 | 29.50 (+2 %) | **28.92** | 28.91 (-0 %) | 29.01 (+0 %) | 28.90 (-0 %) | 29.06 (+0 %) | 28.92 (+0 %) |
| mattersim-native | Cu | 48.79 | 48.92 (-0 %) | **49.09** | 49.15 (+0 %) | 49.08 (-0 %) | 49.32 (+0 %) | 48.51 (-1 %) | 49.09 (+0 %) |
| mattersim-native | Ta | 15.96 | 16.19 (-0 %) | **16.26** | 16.41 (+1 %) | 16.32 (+0 %) | 16.66 (+2 %) | 15.71 (-3 %) | 16.26 (+0 %) |
| mattersim-native | InP | 28.06 | 26.72 (-3 %) | **27.49** | 27.37 (-0 %) | 27.56 (+0 %) | 28.20 (+3 %) | 26.55 (-3 %) | 27.49 (+0 %) |
| mattersim-native | HfO2 | 20.33 | 20.03 (-1 %) | **20.23** | 20.24 (+0 %) | 19.88 (-2 %) | 19.37 (-4 %) | 21.46 (+6 %) | 20.04 (-1 %) |

† V(T) leaves the stable scanned range inside the material's window (the benchmark's check fails).

### Same, averaged over each material's pre-registered window

| model | material | window (K) | Γ fixed | disp 0.03 Å | supercell 14 Å | scan 0.975–1.045 | scan 0.94–1.12 | imaginary modes kept |
|---|---|---|---|---|---|---|---|---|
| mace-kups | Si | 500–800 | 11.05 | 11.07 | 11.07 | 11.02 | 10.30 | 11.05 |
| mace-kups | GaAs | 300–750 | 37.79 | 37.74 | 37.82 | 37.61 | 37.42 | 37.79 |
| mace-kups | Cu | 300–650 | 57.49 | 57.43 | not run | 58.80 | 56.64 | 57.49 |
| mace-kups | Ta | 300–1600 | 46.70 | 46.25 | not run | 69.57† | 41.41 | 49.04† |
| mace-kups | InP | 350–650 | 13.24 | 13.28 | 14.09 | 12.94 | 13.18 | 13.24 |
| mace-kups | HfO2 | 400–1500 | 19.47 | 19.52 | not run | 22.04 | 19.57 | 24.29 |
| mattersim-native | Si | 500–800 | 19.91 | 19.76 | 19.88 | 19.96 | 19.75 | 19.91 |
| mattersim-native | GaAs | 300–750 | 31.82 | 31.80 | 31.93 | 32.00 | 31.78 | 31.82 |
| mattersim-native | Cu | 300–650 | 49.71 | 49.81 | 49.71 | 49.58 | 49.74 | 49.71 |
| mattersim-native | Ta | 300–1600 | 13.84 | 14.01 | 13.89 | 13.54 | 14.22 | 13.84 |
| mattersim-native | InP | 350–650 | 28.75 | 28.68 | 28.89 | 29.10 | 28.14 | 28.75 |
| mattersim-native | HfO2 | 400–1500 | 24.38 | 24.40 | 24.71 | 26.70 | 23.55 | 28.37 |

### What the free energy leaves out at V0 and at the largest benchmark volume (1.08 V0), 300 K

| model | material | V/V0 | mesh modes with ν < 0 | lowest mesh ν (THz) | F_vib (meV/atom) | Γ acoustic modes: F they add (meV/atom) | imaginary modes kept as abs(ν): ΔF (meV/atom) |
|---|---|---|---|---|---|---|---|
| mace-kups | Si | 1.00 | 0.00 % | 0.00 | 24.92 | -0.163 | 0.000 |
| mace-kups | Si | 1.08 | 0.01 % | -0.00 | 21.52 | -0.069 | 0.000 |
| mace-kups | GaAs | 1.00 | 0.00 % | -0.00 | -23.54 | -0.139 | 0.000 |
| mace-kups | GaAs | 1.08 | 0.00 % | 0.00 | -31.28 | -0.210 | 0.000 |
| mace-kups | Cu | 1.00 | 0.00 % | 0.00 | -24.64 | -0.097 | 0.000 |
| mace-kups | Cu | 1.08 | 0.00 % | -0.00 | -37.34 | -0.077 | 0.000 |
| mace-kups | Ta | 1.00 | 0.00 % | 0.00 | -57.95 | -0.157 | 0.000 |
| mace-kups | Ta | 1.08 | 0.09 % | -0.19 | -83.03 | -0.157 | -0.242 |
| mace-kups | InP | 1.00 | 0.02 % | -0.00 | -17.91 | 0.000 | 0.000 |
| mace-kups | InP | 1.08 | 0.01 % | -0.00 | -23.05 | 0.000 | 0.000 |
| mace-kups | HfO2 | 1.00 | 0.29 % | -1.69 | 33.73 | -0.082 | -0.413 |
| mace-kups | HfO2 | 1.08 | 1.11 % | -2.34 | 25.61 | -0.092 | -1.515 |
| mattersim-native | Si | 1.00 | 0.00 % | 0.00 | 32.99 | -0.165 | 0.000 |
| mattersim-native | Si | 1.08 | 0.00 % | 0.00 | 26.64 | -0.196 | 0.000 |
| mattersim-native | GaAs | 1.00 | 0.01 % | -0.00 | -23.92 | 0.000 | 0.000 |
| mattersim-native | GaAs | 1.08 | 0.01 % | -0.00 | -30.43 | -0.069 | 0.000 |
| mattersim-native | Cu | 1.00 | 0.01 % | -0.00 | -23.78 | 0.000 | 0.000 |
| mattersim-native | Cu | 1.08 | 0.00 % | -0.00 | -36.12 | -0.076 | 0.000 |
| mattersim-native | Ta | 1.00 | 0.01 % | -0.00 | -69.32 | -0.051 | 0.000 |
| mattersim-native | Ta | 1.08 | 0.01 % | -0.00 | -76.68 | 0.000 | 0.000 |
| mattersim-native | InP | 1.00 | 0.00 % | -0.00 | -20.08 | -0.137 | 0.000 |
| mattersim-native | InP | 1.08 | 0.01 % | -0.00 | -26.40 | -0.089 | 0.000 |
| mattersim-native | HfO2 | 1.00 | 0.10 % | -1.24 | 38.16 | -0.084 | -0.160 |
| mattersim-native | HfO2 | 1.08 | 0.52 % | -1.66 | 28.00 | -0.094 | -0.800 |

### Ingredients of α_V ≈ γ C_V / (K_T V) at 300 K (model / experiment)

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

### Where γ comes from (C_V-weighted mode Grüneisen parameters at 300 K, 0.985/1.0/1.015 V0)

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

Experiment: Si γ TA(X) = −1.4, γ TA(L) = −1.3 (as quoted by Rignanese, Michenaud & Gonze, arXiv:mtrl-th/9509002); γ TO(Γ) = 1.39 (GaAs), 1.44 (InP) (Aoki, Anastassakis & Cardona 1984, as tabulated in arXiv:1107.0196, Table 4).
