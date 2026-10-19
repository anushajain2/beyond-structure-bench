# Thermal expansion: why the quasi-harmonic approximation, not NPT MD

The benchmark was designed to compute thermal expansion with constant-pressure molecular
dynamics (NPT MD) through kUPS. We switched to the quasi-harmonic approximation (QHA) on
2026-10-19, before any QHA result existed, for two measured reasons.

## 1. Cost

On a free Kaggle T4 GPU, NPT MD through kUPS ran at **0.34–0.37 s per step for MACE** and
**1.2 s per step for Orb**, for batches of 2–3 cells of 100–130 atoms. kUPS's isotropic NPT
step evaluates forces twice per step, and the CuspAI model exports require 64-bit inputs,
which a T4 executes slowly. In 11 hours, MACE finished 4 of its 57 batches and Orb none.
The full set would have needed roughly 130 GPU-hours for MACE and several times that for
Orb, against a free quota of 30 GPU-hours per week.

## 2. A bias in kUPS's isotropic barostat

The three materials that did finish (Cu, Mo, W) all sat at **−0.3 to −0.9 GPa** instead of
the target 0 GPa, increasingly negative with temperature. A direct test on a 32-atom Cu cell
at 650 K (MACE):

| run | volume | mean pressure |
|---|---|---|
| `csvr_npt` (isotropic barostat), target 0 GPa | 402.9 Å³ | −0.83 GPa |
| **fixed volume (NVT) at that same 402.9 Å³** | 402.9 Å³ | **−0.88 ± 0.11 GPa** |
| `baoab_npt_langevin` (flexible cell) | 401.9 Å³ | −0.41 ± 0.40 GPa (inconclusive) |

The fixed-volume run shows that the crystal really is under tension at the volume the
barostat settles on. The offset is close to −N k_B T / V. It grows linearly with
temperature, so it adds a spurious expansion of about k_B / (v·K) per atom (≈ 9 × 10⁻⁶ K⁻¹ for
Cu), which accounts for MACE's MD value for Cu (61 vs ≈ 52 × 10⁻⁶ K⁻¹ from experiment). The
MD results are therefore not used. A reproducer is `scripts/repro_kups_barostat_bias.py`.

## What QHA does instead

For each model and material: scale the relaxed cell to 9 volumes (shape fixed), relax
the atoms, compute harmonic phonons at each volume with phonopy (finite displacements,
supercell ≥ 10 Å, forces from the model through kUPS), and minimise
E(V) + F_vib(V, T) at each temperature to get V(T) and α_V(T). α_V is averaged over the
same pre-registered temperature window per material that was fixed for MD, and compared
with experiment averaged over that window.

**Advantages.** It needs only static force evaluations (minutes per material on a laptop),
does not use a barostat, and includes zero-point motion and quantum statistics. It is
therefore valid from room temperature, with no Debye-temperature cutoff.

**Refinements after the first QHA pass** (2026-10-19, recorded in the config; made before any
QHA result was compared with experiment):

* **Stable volumes only.** At the largest scanned volumes some crystals soften into spurious
  instabilities (imaginary phonons) that they never reach within their temperature window, and
  those volumes corrupt the free-energy fit. The fit now uses only the contiguous run of
  dynamically stable volumes around V0, at least 5 of them. A crystal unstable *at V0 itself*
  is genuinely unstable in that model and is excluded.
* **Symmetrised cells.** Models that are not exactly equivariant leave ~10⁻⁴ noise in relaxed cells
  (e.g. 89.997° instead of 90°), which breaks phonopy's Brillouin-zone setup. Each relaxed cell is
  symmetrised to its own space group at 10⁻³ Å before the phonon step. That removes only noise of
  that size; genuine changes of crystal form are excluded upstream.
* **Room-temperature comparison added.** The pre-registered windows were chosen for classical MD,
  which needs high temperatures. QHA is the opposite, most reliable at low temperature, and at the
  top of some windows (1500–1600 K) the predicted volume runs past the stable range: QHA breaks down
  there. Such cases fail the "volume inside scan" check and are excluded from the window comparison.
  We also report α_V at 300 K against experiment, a standard reference point where QHA is reliable.
  It is labelled as a secondary comparison added with the method change.

**Limitations.**
- It treats vibrations as harmonic at each volume, so it misses higher-order anharmonicity,
  which grows near melting. The temperature windows stay below half the melting point.
- The volume scan keeps the cell shape fixed, which is exact for cubic crystals and an
  approximation for others.
- Layered materials, whose expansion is almost entirely along one axis, are computed but
  not graded.
- Crystals with imaginary phonon frequencies (dynamically unstable in the model) cannot be
  treated and are excluded.

**Convergence** (MACE, Si and Cu):

| change | Si | Cu |
|---|---|---|
| supercell 10 → 14 Å | +2% | 0% |
| q-mesh density ×2 | +2% | −0.2% |
| volume scan widened from −4…+8% to −6…+12% | −7% | −1.4% |

The methodological uncertainty is therefore about 5–8%, well below the 20% "good" threshold.
Si is the most delicate case, because positive and negative mode contributions nearly cancel
in its expansion.

**Sanity check against experiment** (MACE, linear α at 300 K): Si 2.52 vs 2.6, Cu 17.2 vs
16.5–16.7 × 10⁻⁶ K⁻¹.

## What remains of the MD route

`chipff thermal` and the Kaggle notebook still work and are kept for cross-checks once the
barostat is fixed upstream; the flexible-cell integrator and fixed-volume (NVT) pressure
scans are the alternatives.
