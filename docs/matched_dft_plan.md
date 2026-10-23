# Model error or PBE error? Matched PBE references for thermal expansion

*Written 2026-10-23. A plan, not a result: only two short timing calibrations have been run (section 5), and nothing in the benchmark code or results was changed.*

The thermal-failure study ([thermal_failure_study.md](thermal_failure_study.md)) compares each model's
quasi-harmonic (QHA) thermal expansion with experiment, and traces the large errors to the Grüneisen parameter γ,
sometimes made worse by a soft bulk modulus K. It cannot say whether an error belongs to the model or comes from PBE,
the functional the training data were computed with (section 7 of the study). An outside review asked for matched PBE
thermal calculations on a small subset to separate the two:

* **model minus PBE** is the model's own error: what it gets wrong relative to the data it was trained to reproduce;
* **PBE minus experiment** is the error it inherits: a perfect fit to the training data would still have it.

This page does three things, for Si, Cu, Ta and GaAs. It collects published PBE QHA values and records each source's
settings (section 2). It puts them next to experiment and the three models (section 3), and says what that changes in
the study's conclusions (section 4). It then costs running our own PBE QHA on this laptop and recommends what, if
anything, to run (sections 5 and 6).

## Summary

* **The literature already separates the two errors for Ta, Si and Cu.** For GaAs the only published 300 K PBE-type
  QHA value probably used PBE+U, so GaAs remains provisional.
* **MACE's Ta failure is MACE's own.** PBE QHA overshoots experiment by about 21 % in α_V(300 K)
  ([Gong & Dal Corso 2025](https://doi.org/10.1063/5.0258989)). MACE overshoots PBE by 130 %, and its γ (4.09) is about
  twice PBE's (≈ 1.98). Its K′ (7.7) is about twice PBE's as well (3.5–3.7).
* **Part of the "shared" Ta γ error is inherited from PBE.** PBE's γ is already about 27 % above the value inferred from
  experiment. Orb's γ is only 10 % above PBE, and most of its excess over PBE in α (+40 %) comes from its soft bulk
  modulus. MatterSim's apparent Ta accuracy (−14 % vs experiment) is a 29 % *undershoot* of PBE.
* **MatterSim's Si error (+85 %) is its own.** PBE gives α_V(300 K) of 8.0–9.0 ×10⁻⁶ K⁻¹ (experiment 7.85) and γ of
  0.39–0.42. MatterSim's γ of 0.67 is 60–70 % above PBE.
* **The soft semiconductor bulk moduli are mostly inherited.** PBE's static K is 10 % below experiment for Si and
  about 19 % below for GaAs (17 % for InP). For Si and GaAs the models are within −8 % to +6 % of PBE. The study's "K_T 17–29 % too soft"
  for MatterSim and Orb is therefore mostly PBE's error, with a model share of 1–8 %.
* **Cu "works" partly by departing from PBE.** PBE overshoots Cu by 11–15 %. All three models fall 2–14 % *below* PBE,
  which puts them closer to experiment than their training functional.
* **Running our own:** the supercell route that matches `configs/benchmark.yaml` exactly is affordable only for Si
  (about 4–5 h, calibrated). For Cu and Ta it would take hundreds of hours of laptop CPU each, and published PBE QHA is
  already better converged than what we could afford. The recommendation (section 6) is a GaAs PBE calculation with
  density-functional perturbation theory (DFPT): about 3–7 h for γ at 3 volumes, calibrated, or 9–20 h for the full
  QHA. A Si control adds about 4–5 h. Quantum ESPRESSO is now installed and calibrated (section 5); the production
  runs have not been started.

## 1. What the models were trained on

| | Materials Project / MPtrj (MACE-MPA-0) | Alexandria PBE (MACE-MPA-0, via sAlex) | OMat24 (Orb v3 conservative, OMat) |
|---|---|---|---|
| Code, functional | VASP, PBE; PBE+U only for oxides/fluorides of Co, Cr, Fe, Mn, Mo, Ni, V, W | VASP, PBE, MP-compatible | VASP, PBE(+U), same U rule |
| PAW potentials for these four | Si, **Cu_pv**, **Ta_pv**, **Ga_d**, As | MP-compatible | Same labels from PBE_54 |
| Cutoff, k-points, smearing | 520 eV; 1000 k-points per reciprocal atom (`reciprocal_density` 64); tetrahedron | 520 eV; Γ-centred, 1000 k-points per reciprocal atom | 520 eV; `reciprocal_density` 64; tetrahedron, σ 0.05 |
| Sources | [MPRelaxSet.yaml](https://github.com/materialsproject/pymatgen/blob/v2025.1.24/src/pymatgen/io/vasp/MPRelaxSet.yaml), [MP parameters](https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/parameters-and-convergence), [MP pseudopotentials](https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/pseudopotentials), [MP U values](https://docs.materialsproject.org/methodology/materials-methodology/calculation-details/gga+u-calculations/hubbard-u-values), [CHGNet/MPtrj](https://arxiv.org/abs/2302.14231) | [Alexandria](https://arxiv.org/abs/2512.09169) | [OMat24](https://arxiv.org/abs/2410.12771) §2.2.2, [OMat24StaticSet.yaml](https://github.com/facebookresearch/fairchem/blob/main/src/fairchem/data/omat/vasp/OMat24StaticSet.yaml) |

No +U applies to Si, Cu, Ta or GaAs in any of these datasets. MatterSim v1 was trained on its developers' own PBE(+U)
data, whose settings were not checked here. The Materials Project has **no PBE phonon or thermal data** for these four:
its phonon database is PBEsol (ABINIT DFPT, PseudoDojo; [Petretto et al. 2018](https://doi.org/10.1038/sdata.2018.65),
[MP docs](https://docs.materialsproject.org/methodology/materials-methodology/phonon-dispersion)). MP does give static PBE
values, which the benchmark already stores in `data/mp/` (fetched 2026-10-17):

| | MP id | a (Å) | K_VRH, elastic (GPa) |
|---|---|---|---|
| Si | [mp-149](https://next-gen.materialsproject.org/materials/mp-149) | 5.4687 | 88.9 |
| Cu | [mp-30](https://next-gen.materialsproject.org/materials/mp-30) | 3.6213 | 151.4 |
| Ta | [mp-50](https://next-gen.materialsproject.org/materials/mp-50) | 3.3223 | 194.5 |
| GaAs | [mp-2534](https://next-gen.materialsproject.org/materials/mp-2534) | 5.7502 | 60.7 |

MP's current Cu modulus (151) is above every other PBE value found (136–141, below). Older MP snapshots
(matminer, 2015 and 2018) give 136 and 139, so the static Cu reference below uses the equation-of-state values instead.

## 2. Published PBE references

All values below were read in the source itself, except where marked *(fig.)*, meaning digitised from a figure, or
*(derived)*. Linear α was multiplied by 3 to give α_V. "MP match" says how close the setup is to the training data.

### Si

| Source | Values (PBE) | Settings | MP match |
|---|---|---|---|
| Nath et al., Comput. Mater. Sci. 125, 82 (2016), AFLOW-QHA, [doi](https://doi.org/10.1016/j.commatsci.2016.07.043), [arXiv:1603.06924](https://arxiv.org/abs/1603.06924) | α_V = **8.0** ×10⁻⁶ K⁻¹, γ = **0.42**, B = 84.9 GPa (QHA at 300 K), Table 1. That α is at 300 K is inferred from the text. | VASP PAW-PBE (POTCAR not named), cutoff 1.4 × ENMAX, 8000 k-points per reciprocal atom. 3×3×3 supercell (54 atoms), 0.015 Å displacements, 21³ mesh. 13 volumes, 98–113 % V0, Birch–Murnaghan. | Close: VASP PAW PBE, denser k than MP. Supercell smaller than ours (128 atoms). |
| Nath et al., Phys. Rev. Materials 3, 073801 (2019), AFLOW-QHA3P, [doi](https://doi.org/10.1103/PhysRevMaterials.3.073801), [arXiv:1807.04669](https://arxiv.org/abs/1807.04669) | α_V(300 K) ≈ **9.0** (fig., ±0.5); 12.3 at 500 K, 13.8 at 800 K. B ≈ 86.6 GPa (0 K). Includes zero-point energy. | Same AFLOW setup; 5×5×5 supercell (250 atoms), 31³ mesh, 10 volumes from −3 % to +6 %. | Close, as above. Shows the setup sensitivity: 8.0 vs 9.0 between two AFLOW setups. |
| Parks, Kim, Viswanathan & McGaughey, Phys. Rev. Materials 4, 083805 (2020), [doi](https://doi.org/10.1103/PhysRevMaterials.4.083805), [arXiv:2005.08835](https://arxiv.org/abs/2005.08835) | γ̄(300 K) = **0.39** (signed, C_V-weighted; Table S1). Mode γ: TA(X) ≈ **−1.5**, TA(L) ≈ −1.35, TO(Γ) ≈ 0.93 (fig.). B = 86.9 GPa (static), a = 5.478 Å. Its α (7.2, as α_V) is from the Grüneisen formula, not a free-energy QHA. | GPAW (real-space PAW, 0.18 Å grid). Harmonic force constants from a 216-atom supercell, cubic from a 64-atom one; mode γ from cubic force constants. | Different code and route; same functional. LDA in the same paper: γ̄ 0.20. |
| Delta test: Lejaeghere et al., Science 351, aad3000 (2016), WIEN2k reference, [data file](https://github.com/molmod/DeltaCodesDFT/blob/master/WIEN2k.txt) | Static V0 = 20.453 Å³/atom (a = 5.469 Å), **B0 = 88.5 GPa, B′ = 4.31** | All-electron WIEN2k 13.1, PBE, Birch–Murnaghan over ±6 % V | All-electron reference; MP's VASP setup matches it to about 1 %. |

Not PBE (checked and excluded): Kim et al., PNAS 2018 (AM05); Ritz, Li & Benedek, J. Appl. Phys. 2019 (PBEsol).

### Cu

| Source | Values (PBE) | Settings | MP match |
|---|---|---|---|
| Grabowski, Hickel & Neugebauer, Phys. Rev. B 76, 024309 (2007), [doi](https://doi.org/10.1103/PhysRevB.76.024309) (paywalled); numbers read from Grabowski's open [PhD thesis](https://digital.ub.uni-paderborn.de/hsmig/download/pdf/1376) (Paderborn 2009), same study | α_V(300 K) ≈ **55** (fig., linear 18.3 ± 0.3); linear 19.4 / 20.4 / 21.7 at 400 / 500 / 650 K (fig.). Static a = 3.637 Å, **B = 136 GPa**, B′ = 5.1 (PAW); LAPW B = 141. | VASP PAW (Cu valence not stated; the 290 eV cutoff suggests no 3p semicore), 4×4×4 supercell (256 atoms), 0.01 bohr displacements, 16³ mesh. Includes the electronic free energy (small for Cu at 300 K). | VASP PAW PBE; potential probably "Cu", not MP's Cu_pv. |
| Narasimhan & de Gironcoli, Phys. Rev. B 65, 064302 (2002), [arXiv:cond-mat/0109020](https://arxiv.org/abs/cond-mat/0109020) | α_V(300 K) ≈ **57** (fig., linear 19.1 ± 0.3; the text says +14 % vs experiment). **γ(300 K) ≈ 2.12** (fig.). Mode γ at static a: X LA 2.35, TA 1.93; L LA 2.39, TA 1.67 (fig.). a = 3.672 Å, B = 128 GPa, B′ = 5.11. | PWscf DFPT, ultrasoft, 30/300 Ry, 60 k-points, 4³ q-mesh interpolated to 24³. | Less converged: a is 1 % above, and B 10 % below, the all-electron value. |
| Delta test (as above) | Static V0 = 11.951 Å³/atom (a = 3.630 Å), **B0 = 141.3 GPa, B′ = 4.86** | WIEN2k | Reference. |

AFLOW-QHA has no elemental Cu entry.

### Ta

| Source | Values (PBE) | Settings | MP match |
|---|---|---|---|
| Gong & Dal Corso, J. Chem. Phys. 162, 124709 (2025), [doi](https://doi.org/10.1063/5.0258989) (open access), [supplement](https://doi.org/10.60893/figshare.jcp.c.7709672) | α_V(300 K) **≈ 23.0 phonon-only**, 23.6 with electronic excitations (SI Fig. 4, fig. ±0.3). Phonon-only 24.4 at 500 K, 27.2 at 1000 K, 30.8 at 1500 K (fig.). Table I: a = 3.315 Å (0 K), 3.322 Å (295 K); **B_T = 194.8 GPa (0 K), 190.2 GPa (295 K); B′ = 3.53**. γ(300 K) ≈ **1.98** *(derived* by us from their β, B_T, V and C_P, the same way the study infers the experimental γ*)*. | Quantum ESPRESSO + thermo_pw, PAW `Ta.pbe-spn-kjpaw_psl.1.0.0` (5s5p in valence), 90/360 Ry, 40³ k, smearing 0.02 Ry, DFPT on a 10³ q-grid interpolated to 200³, 17 volumes. No spin-orbit coupling. | Good: semicore 5p like MP's Ta_pv. Better converged than any calculation we could afford. |
| Delta test (as above) | Static V0 = 18.286 Å³/atom (a = 3.319 Å), **B0 = 195.1 GPa, B′ = 3.71**. Accurate PBE codes in the Delta set span B0 = 193–196 and B′ = 3.5–4.0. | WIEN2k | Reference. |
| Cohen & Gülseren, Phys. Rev. B 63, 224101 (2001), [arXiv:cond-mat/0006213](https://arxiv.org/abs/cond-mat/0006213) | Static PBE-LAPW: K0 = 190.9 GPa, K′ = 3.99. Its thermal part (α_V 26.4, γ 2.09 at 300 K) uses **LDA** vibrations in a particle-in-a-cell model, so it is **not** a PBE QHA. | LAPW, 5p in the bands, 16³ k | Static only. |

The machine-learned potentials ignore thermal electronic excitations, so the **phonon-only** PBE value (23.0) is the
matched one. AFLOW-QHA has no Ta entry.

### GaAs

| Source | Values | Settings | MP match |
|---|---|---|---|
| Nath et al. 2016, AFLOW-QHA (as above) | α_V(300 K) = **21.6**, **γ = 0.76**, B(300 K) = 57.2 GPa (Table 1; their experimental value is 16.2) | AFLOW's GaAs entry (ICSD 53964) uses Ga_h (3d in valence) and **Dudarev U = 3.9 eV on Ga d** ([AFLOW entry](http://aflowlib.duke.edu/AFLOWDATA/ICSD_WEB/FCC/As1Ga1_ICSD_53964/?ldau_TLUJ)). The paper does not mention U; that its QHA used +U is our inference from "AFLOW standard". | **Not matched**: MP uses no U on Ga. Use as provisional. |
| Yang et al., New J. Phys. 21, 123015 (2019), [open access](https://iopscience.iop.org/article/10.1088/1367-2630/ab5cb3) | a = 5.76 Å. Mode γ along Γ–X–K–Γ (fig.): **TA(X) ≈ −1.0**, optical 1.3–1.6 (TO(Γ) ≈ 1.3–1.4). No 300 K α (its figure stops at 150 K); no TA(L). | QE + thermo_pw, PBE, 120 Ry, 24³ k, 6³ q with Wannier interpolation; Ga 3d not stated. | Same functional; mode values only. |
| MP mp-2534 (above) | Static K_VRH = **60.7 GPa**, a = 5.750 Å | MP elastic workflow, PBE, 700 eV | The training setup itself. |

Not usable: Herriman & Fultz, Phys. Rev. B 101, 214108 (2020), chose LDA. Shao et al., Phys. Rev. B 108, 024306 (2023),
[doi](https://doi.org/10.1103/PhysRevB.108.024306), reports QHA for 60 cubic binaries with LDA, PBE, PBEsol and SCAN and
may contain GaAs with PBE. It is paywalled and was not opened.

## 3. PBE vs experiment vs each model

Model values are from the study (`results/thermal_failure/physics.csv`, variant `grid`, Γ-acoustic modes excluded) and
from `results/bulk_modulus.csv` (static Birch–Murnaghan B and B′). The experimental γ is the one *inferred* in the study
from α_exp (section 4 there). PBE values are those of section 2. A range is shown where two PBE sources disagree. The
model columns give the model value and, in brackets, **model minus PBE** as a percentage of PBE.

**α_V(300 K), 10⁻⁶ K⁻¹**

| | exp | PBE (lit.) | **PBE − exp** | MACE-MPA-0 | MatterSim v1 | Orb v3 |
|---|---|---|---|---|---|---|
| Si | 7.85 | 8.0–9.0 | **+2 to +15 %** | 7.8 (−3 to −14 %) | 14.5 (**+61 to +81 %**) | 7.6 (−5 to −15 %) |
| Cu | 49.7 | ≈ 55–57 | **+11 to +15 %** | 51.7 (−6 to −9 %) | 49.1 (−11 to −14 %) | 53.9 (−2 to −6 %) |
| Ta | 19.0 | ≈ 23.0 | **+21 %** | 52.8 (**+130 %**) | 16.3 (−29 %) | 32.2 (**+40 %**) |
| GaAs | 17.2 | 21.6 (+U, provisional) | +26 % | 36.3 (+68 %) | 28.9 (+34 %) | 21.5 (0 %) |

**γ at 300 K (C_V-weighted)**

| | exp (inferred) | PBE (lit.) | **PBE − exp** | MACE-MPA-0 | MatterSim v1 | Orb v3 |
|---|---|---|---|---|---|---|
| Si | 0.46 | 0.39–0.42 | −10 to −16 % | 0.37 (−6 to −13 %) | 0.67 (**+59 to +71 %**) | 0.32 (−19 to −25 %) |
| Cu | 1.99 | ≈ 2.12 | +7 % | 1.85 (−13 %) | 2.16 (+2 %) | 2.14 (+1 %) |
| Ta | 1.56 | ≈ 1.98 (derived) | **+27 %** | 4.09 (**+107 %**) | 1.68 (−15 %) | 2.19 (+10 %) |
| GaAs | 0.74 | 0.76 (+U, provisional) | +3 % | 1.30 (+72 %) | 0.92 (+22 %) | 0.79 (+4 %) |

**Zone-edge mode γ (semiconductors)**

| | exp | PBE (lit.) | MACE-MPA-0 | MatterSim v1 | Orb v3 |
|---|---|---|---|---|---|
| Si TA(X) | −1.4 | ≈ −1.5 (Parks, fig.) | −2.84 | −0.64 | −2.23 |
| Si TA(L) | −1.3 | ≈ −1.35 (Parks, fig.) | −1.68 | −0.58 | −1.68 |
| GaAs TA(X) | (negative) | ≈ −1.0 (Yang, fig.) | −0.86 | −0.22 | −1.06 |
| GaAs TA(L) | (negative) | not found | +1.80 | −0.42 | −1.03 |

**Static bulk modulus B0 (GPa) and B′**

| | exp K | PBE B0 (lit.) | **PBE − exp** | MACE-MPA-0 | MatterSim v1 | Orb v3 | PBE B′ | B′ MACE / MatterSim / Orb |
|---|---|---|---|---|---|---|---|---|
| Si | 98 | 88.5 (Delta); 86.9–88.9 | **−10 %** | 86.4 (−2 %) | 85.9 (−3 %) | 83.3 (−6 %) | 4.31 | 4.00 / 4.98 / 4.30 |
| Cu | 137.6 | 141.3 (Delta); 136 (PAW) | +3 % | 130.4 (−8 %) | 143.6 (+2 %) | 135.3 (−4 %) | 4.86–5.1 | 4.38 / 5.48 / 5.12 |
| Ta | 191.9 | 195.1 (Delta); 194.8 | +2 % | 203.0 (+4 %) | 186.9 (−4 %) | 171.3 (**−12 %**) | 3.53–3.71 (exp 3.07) | **7.68** / 3.63 / 3.16 |
| GaAs | 75.3 | 60.7 (MP elastic) | **−19 %** | 64.4 (+6 %) | 55.9 (−8 %) | 58.1 (−4 %) | – | 6.21 / 5.00 / 4.71 |
| InP (for reference) | 71.1 | 59.4 (MP elastic) | **−17 %** | 68.5 (+15 %) | 55.7 (−6 %) | 58.7 (−1 %) | – | – |

Model minus PBE is computed against the Delta-test B0 for Si, Cu and Ta and against MP for GaAs and InP. The QHA
moduli at 300 K behave the same way: PBE's K_T(295 K) for Ta is 190.2 GPa (Gong & Dal Corso), against Orb's 163 (−14 %).

## 4. What this says about the study's conclusions

The study's conclusions about *where* the errors sit (γ, sometimes K) are unaffected; they were all made against
experiment. What changes is *whose* error each one is.

1. **MACE on Ta: the model's own.** PBE's γ is about 1.98 and its B′ 3.5–3.7. MACE's 4.09 and 7.68 are about double,
   and its α is 2.3 × PBE's. The study's diagnosis (an energy-volume curve that stiffens too fast) is a failure to
   reproduce PBE, not something PBE does. Of the +179 % error against experiment, PBE accounts for about +21 %.
2. **The "shared" Ta γ error is mostly PBE's for Orb, and not shared by MatterSim.** PBE's γ is already about 27 %
   above the experimental inference. Orb's 2.19 is only 10 % above PBE. Its α excess over PBE (+40 %) is roughly
   γ (×1.10) times a soft K_T (190/163 ≈ ×1.17), plus the reconstruction residual. MatterSim lands *below* PBE (γ −15 %,
   α −29 %), so its 14 % undershoot of experiment is not inherited either: it partly cancels PBE's overshoot. The
   statement "Orb's phonon γ is 40 % too high, while its K′ is normal" still holds against experiment. Against its
   training functional, though, Orb's γ error is about 10 %, and its K′ (3.16) is 10–15 % *below* PBE's. So K′ is still
   no warning sign, but the size of Orb's own Ta error is about 40 %, not 70 %.
3. **MatterSim's semiconductor failure is its own.** For Si, PBE's α is within 2–15 % of experiment and its zone-edge
   TA γ (≈ −1.5, −1.35) matches the measured −1.4 and −1.3. MatterSim's TA modes (−0.64, −0.58) and γ (+60–70 % over
   PBE) depart from PBE. The study's attribution of MatterSim's Si, GaAs and InP errors to wrong-signed or too-weak TA
   modes is therefore a model error. For GaAs, the PBE TA(X) ≈ −1.0 (Yang) supports the same reading, but TA(L) and the
   integrated γ still lack a matched PBE value.
4. **The soft semiconductor bulk moduli are inherited.** The study reads Orb's and MatterSim's K_T, 17–29 % below
   experiment, as a shared model failure. PBE itself is 10 % soft for Si, 19 % for GaAs and 17 % for InP. The models'
   own share is 1–8 % (MACE's GaAs and InP are even stiffer than PBE). Against PBE, Orb's GaAs α (21.5) matches the
   provisional PBE value (21.6) almost exactly. Its +25 % against experiment would then be essentially PBE's error,
   pending a U-free check (section 6).
5. **MACE's Si "right by cancellation" is partly PBE's own cancellation.** PBE already has a γ 10–16 % low and a K 10 %
   soft, and gets α within 2–15 %. MACE's average γ is close to PBE's (−6 to −13 %), but its TA(X) (−2.84) is twice as
   negative as PBE's (−1.5). So the integrated γ is right for partly the wrong mode-level reason. Orb's Si γ (0.32) is
   19–25 % below PBE, which confirms that the study's caution about Orb's Si is a model-level issue.
6. **Cu's agreement with experiment is not PBE agreement.** PBE QHA overshoots Cu by 11–15 % at 300 K, and by more at
   higher T. All three models sit 2–14 % below PBE. MatterSim and Orb reproduce PBE's γ to within 2 %, so their lower α must
   come from the other ingredients (K_T, V), which have no published PBE values at 300 K to compare with. MACE's γ is 13 % below PBE. The study's "Cu works" should be read as "Cu matches
   experiment", not "the models reproduce PBE for Cu".

**How firm this is.** PBE QHA values for the same material differ by 4 % (Cu, two codes) to 12 % (Si, two AFLOW
setups). Those sources also differ from the training setup in pseudopotentials and supercells (section 2), and the study
itself found ±9 % sensitivity to the volume-scan range. Model-minus-PBE gaps above about 30 % are therefore robust:
MACE Ta, MatterSim Si, MACE GaAs, Orb Ta and MatterSim Ta. Gaps below about 15 % are not resolved: all of Cu, MACE and
Orb Si, Orb GaAs. Volumes differ too: the literature evaluates PBE at PBE's own volume, the models at theirs. Their
lattice constants are within 0.2 % of MP's, except MACE Cu (+0.5 %), which changes γ negligibly.

## 5. Cost of running our own PBE QHA on this laptop

**Machine:** Apple M4 Pro, 12 cores (8 performance + 4 efficiency), 24 GB RAM. **Software** (installed 2026-10-23,
outside the repository):
* Miniforge 26.7.2 in `~/miniforge3`, checksum verified against the GitHub release. The shell profile was not changed.
* Quantum ESPRESSO 7.6 (conda-forge, openmpi build) in the conda env `qe`. Miniforge and the env take 1.3 GB on disk.
* SSSP 1.3.0 PBE efficiency in `~/chipff-dft/sssp_1.3.0_pbe_eff`, md5 verified against the
  [Materials Cloud record](https://archive.materialscloud.org/records/rcyfm-68h65).

**Matched settings** (`configs/benchmark.yaml` `thermal_qha`, as the benchmark actually ran them):

| | supercell | atoms | displacements per volume | SCF runs (9 volumes) | SSSP efficiency PBE (valence, cutoff) | electrons |
|---|---|---|---|---|---|---|
| Si | 4×4×4 primitive | 128 | 1 (+1 reference) | 9 (+9) | Si pslibrary US (4 e), 30 Ry | 512 |
| GaAs | 4×4×4 primitive | 128 | 2 (+1) | 18 (+9) | Ga pslibrary PAW (13 e, 3d), As US (5 e); 70 Ry | 1152 |
| Cu | 5×5×5 primitive | 125 | 1 (+1) | 9 (+9) | Cu pslibrary PAW (11 e, no 3s3p); 90 Ry | 1375 |
| Ta | 5×5×5 primitive | 125 | 1 (+1) | 9 (+9) | Ta GBRV US (13 e, 5s5p); 45 Ry | 1625 |

The reference (undisplaced) supercell can be skipped in DFT: for these four high-symmetry crystals its forces vanish by
symmetry, so subtracting them only removes the models' numerical noise.

**Estimated time per SCF.** These estimates scale the cost as (bands² × plane waves × k-points) from the AUSURF112 QE
benchmark: 112 Au atoms, about 800 bands. It takes 917 s for two SCF iterations on a Ryzen 9 5900HX laptop
([OpenBenchmarking pts/qe](https://mail.openbenchmarking.org/test/pts/qe)), and the M4 Pro is assumed to be 1–1.5× as
fast. The estimate also assumes 12–20 iterations per SCF and 4 k-points (semiconductors) or 8 (metals) after symmetry
reduction of the displaced cell. Before the calibration below, this was an order-of-magnitude estimate. The Si run
landed at its upper end per k-point, so the **upper ends of the ranges are the realistic figures**.

| | plane waves | bands | per SCF | **supercell QHA, 9 volumes** | wavefunction memory |
|---|---|---|---|---|---|
| Si | 49 k | 256 | **≈ 0.45 h measured** (estimate 0.2–0.4 h) | **≈ 4–4.5 h** | 13 GB total measured (8 ranks) |
| GaAs | 203 k | 576 | 4–9 h | **70–170 h** | ~8 GB (wavefunctions only) |
| Cu | 144 k | ~825 | 11–28 h | **100–250 h** | ~15 GB (wavefunctions only; will not fit with 8 ranks) |
| Ta | 79 k | ~975 | 8–21 h | **75–190 h** | ~10 GB (wavefunctions only) |

**Calibration runs (2026-10-23, QE 7.6, 8 MPI ranks, 1 thread each).** Inputs and outputs are in
`~/chipff-dft/calib/`. During both runs, another session's Python jobs were using about 3–4 cores and ~5 GB, so these
timings are somewhat pessimistic.

* **Si, 128-atom supercell, one 0.01 Å displacement** (phonopy's own displacement; 30/240 Ry; 2×2×2 k, i.e. 6 k-points
  after symmetry):
  * The first attempt, with QE's default parallel subspace diagonalisation and 2 k-pools, gave NaN energies at
    iteration 1 and stopped at 6 min. A 2-atom Si test on 1 and 4 ranks gave identical, normal energies, so the build
    is fine. With serial subspace diagonalisation (`-nd 1`) and no pools, the 128-atom SCF behaves normally.
  * Setup takes 70 s and the first iteration 220 s; later iterations take ≈ 110 s each. The run reached 3 × 10⁻⁵ Ry
    accuracy after 6 iterations, at the 14-minute cap.
  * A converged SCF (about 13 iterations to 10⁻⁹ Ry) is therefore ≈ 25–30 min. Nine volumes come to ≈ 4–4.5 h, or
    about twice that if the undisplaced reference supercells are also computed.
* **GaAs, primitive cell, DFPT** (70/560 Ry, 8×8×8 k):
  * The SCF takes 19 s.
  * The calibration q-point is the 4×4×4 grid's lowest-symmetry one, (0.75, −0.25, 0.75) 2π/a: 6 irreducible
    representations of 1 mode each. Three of them took 13.5 min, so the whole q-point takes ≈ 27 min.
  * The other 7 irreducible q-points of the grid have higher symmetry and need fewer k-points and representations.
    Weighting them by the order of their point groups gives ≈ **1.7 h per volume** (range 1–2.5 h). That is about
    twice the earlier guess.
  * A 6×6×6 k-mesh, if a ≤ 15-min convergence test on this q-point allows it, would cut this by up to about 2×.

Both calibrations confirm the scale of the cost: the GaAs supercell route would take ≈ 18 h per volume (two displaced
128-atom SCFs), against ≈ 1.7 h with DFPT.

**The cheaper matched alternative: DFPT on the primitive cell.** DFPT on a q-grid equal to the supercell (4×4×4 for
Si and GaAs, 5×5×5 for Cu and Ta) gives the same harmonic force constants at the q-points the supercell samples, which
are the only ones the finite-displacement method computes exactly. The two routes then share phonopy's interpolation.
phonopy can read QE `q2r.x` force constants. Per volume, the GaAs cost is calibrated at ≈ 1.7 h (above). Si should
be roughly 5–10× cheaper (30 Ry, 4 instead of 9 occupied bands), so 10–20 min per volume. The Cu and Ta figures are
uncalibrated guesses, which would probably need doubling as GaAs did: about 1–2 h per volume. That gives roughly
**9–20 h (GaAs), 1.5–3 h (Si) and 9–18 h each (Cu, Ta) for 9 volumes, and a third of that for a γ-only run at 3
volumes**.
For GaAs, the matched comparison drops the LO–TO non-analytic term, as the MLIP pipeline does; the corrected value would
be reported alongside.

## 6. Recommendation

1. **Do not compute Ta or Cu.** For Ta, Gong & Dal Corso's PBE DFPT QHA (semicore PAW, 10³ q-grid, 17 volumes) is
   better converged than anything this laptop can do in the supercell route. The conclusion it supports (MACE +130 % over
   PBE) is ten times the plausible spread between setups. For Cu, two independent PBE QHA results agree within 4 %, and
   all model-minus-PBE gaps are below the level a new calculation could resolve.
2. **Before any computation, try to get Shao et al., Phys. Rev. B 108, 024306 (2023) through library access.** If it
   contains a U-free PBE QHA for GaAs, the GaAs gap may close at no cost.
3. **If GaAs remains open, compute it with DFPT, γ first.** Use QE with SSSP-efficiency PBE (Ga with 3d, no U), a 4×4×4
   q-grid, and the model-relaxed and PBE-relaxed volumes. Step one is 3 volumes (0.985 / 1.0 / 1.015 V0) for γ, TA(X),
   TA(L) and TO(Γ): **≈ 3–7 h (calibrated)**, or less if a 6×6×6 k-mesh passes a short convergence test. Step two,
   9 volumes for α(T) through `PhonopyQHA`, is worth adding only if step one leaves the GaAs attribution unclear:
   **≈ 9–20 h** in total. This is the one material where the PBE
   reference is missing, and it tests the study's semiconductor TA-mode mechanism (MACE's TA(L) +1.8) at the mode
   level.
4. **Add Si as a matched-pipeline control: the exact supercell route, ≈ 4–4.5 h (calibrated), with `-nd 1`.** It is
   the only material for which the benchmark's own settings (128-atom supercell, 0.01 Å, 9 volumes, Γ fix) are affordable with DFT. It checks the
   literature spread (8.0 vs 9.0) and our pipeline against published PBE, and it gives PBE TA(X) and TA(L) computed
   exactly as the models' are.
5. **Approvals.** (a) The install and (b) the calibration were approved and done on 2026-10-23 (section 5). (c) The
   production runs still need approval: ≈ 7–12 h of background CPU for steps 3 (γ only) and 4, or ≈ 13–25 h with the
   full GaAs QHA. Running them while other sessions' jobs share the CPU would slow both.

Outputs, if run, would go to a new `results/matched_dft/` with their own provenance. The benchmark's results and the
study's tables would stay unchanged; the comparison would be added as a new section of the study.
