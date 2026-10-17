"""Finite-temperature property: thermal expansion from NPT molecular dynamics.

Method (all MD through kUPS):

* Supercell of the model's own relaxed structure, at least 10 Å across in
  every direction (perpendicular widths).
* Three temperatures chosen by a fixed rule from experimental data: above the
  Debye temperature (classical MD is only valid there), below half the melting
  point, and at least 50 K below any solid-state phase change.
* Constant-pressure (P = 0) MD: cubic crystals use kUPS's isotropic stochastic
  cell-rescaling barostat (``csvr_npt``); others use the fully flexible cell
  (``baoab_npt_langevin``) so each axis expands on its own. The barostat's
  compressibility is set from the model's own bulk modulus.
* Equilibrate, then sample until the block-averaged standard error of the mean
  volume falls below a set fraction (or a time cap is hit).
* Fit mean volume (and each mean lattice length) against temperature; the
  slope over the value at the middle temperature gives the volumetric (and
  per-axis linear) expansion coefficient, with a weighted-fit uncertainty.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from ase import Atoms

KB_EV = 8.617333262e-5
LIGHT = {"H", "Li", "Be", "B", "C", "N", "O", "F"}


# -- temperature rule ---------------------------------------------------------
@dataclass
class TemperatureWindow:
    t_low: float
    t_high: float
    temperatures: list
    ok: bool
    reason: str


def temperature_window(debye_K: float | None, melt_K: float | None, transitions_K: list[float],
                       min_span: float = 150.0, floor: float = 300.0, debye_fraction: float = 0.75,
                       override: dict | None = None) -> TemperatureWindow:
    """The written rule: T ≥ 0.75 Θ_D (classical heat capacity ≥ ~93 % of its
    high-T limit), below Tm/2, and 50 K below any solid-state phase change."""
    if override:
        t = list(override["temperatures"])
        return TemperatureWindow(min(t), max(t), t, True, "override: " + override["reason"])
    if debye_K is None or melt_K is None:
        return TemperatureWindow(math.nan, math.nan, [], False, "missing Debye or melting temperature")
    lo = max(floor, debye_fraction * float(debye_K))
    hi = 0.5 * float(melt_K)
    caps = [t - 50.0 for t in transitions_K if t is not None and t > lo]
    if caps:
        hi = min(hi, min(caps))
    if hi - lo < min_span:
        return TemperatureWindow(lo, hi, [], False, f"window {lo:.0f}-{hi:.0f} K narrower than {min_span:.0f} K")
    lo_r, hi_r = 50 * math.ceil(lo / 50), 50 * math.floor(hi / 50)
    temps = [float(lo_r), float(round((lo_r + hi_r) / 2 / 10) * 10), float(hi_r)]
    return TemperatureWindow(lo_r, hi_r, temps, True, "rule")


# -- supercell + time step -----------------------------------------------------
def supercell(atoms: Atoms, min_width: float = 10.0, max_atoms: int = 400) -> tuple[Atoms, tuple[int, int, int]]:
    """Smallest diagonal repeat with every perpendicular width ≥ min_width Å."""
    cell = np.asarray(atoms.cell)
    vol = abs(np.linalg.det(cell))
    widths = [vol / np.linalg.norm(np.cross(cell[(i + 1) % 3], cell[(i + 2) % 3])) for i in range(3)]
    reps = tuple(int(math.ceil(min_width / w)) for w in widths)
    sc = atoms.repeat(reps)
    if len(sc) > max_atoms:
        raise ValueError(f"supercell {reps} has {len(sc)} atoms > {max_atoms}")
    return sc, reps


def time_step_fs(atoms: Atoms) -> float:
    return 1.0 if set(atoms.get_chemical_symbols()) & LIGHT else 2.0


# -- statistics ------------------------------------------------------------------
def block_sem(x: np.ndarray, n_blocks: int = 10) -> float:
    """Standard error of the mean from n_blocks contiguous block averages."""
    x = np.asarray(x, float)
    n = len(x) // n_blocks
    if n < 2:
        return float("inf")
    b = x[: n * n_blocks].reshape(n_blocks, n).mean(axis=1)
    return float(b.std(ddof=1) / math.sqrt(n_blocks))


def make_stop_fn(rel_sem_target: float):
    """Stop when every system's mean volume is known to rel_sem_target."""

    def stop(cells: np.ndarray) -> bool:
        vols = np.abs(np.linalg.det(cells))  # (n_samples, n_systems)
        return all(block_sem(vols[:, j]) / vols[:, j].mean() < rel_sem_target for j in range(vols.shape[1]))

    return stop


def cell_lengths(cells: np.ndarray, reps) -> np.ndarray:
    """Lattice-vector lengths per sample, divided by the supercell repeats."""
    return np.linalg.norm(cells, axis=-1) / np.asarray(reps, float)


# -- per-material analysis --------------------------------------------------------
@dataclass
class ThermalResult:
    material: str
    model: str
    temperatures: list
    natoms: int
    reps: list
    integrator: str
    time_step_fs: float
    prod_ps: list
    mean_T: list
    mean_P_GPa: list
    volume_per_atom: list
    volume_sem_rel: list
    lengths: list  # per T: [a, b, c] of the primitive/conventional input cell
    alpha_V_1e6: float
    alpha_V_err_1e6: float
    alpha_axes_1e6: list  # [αa, αb, αc]
    alpha_axes_err_1e6: list
    checks: dict


def _wfit(x, y, s):
    """Weighted linear fit y = p0 + p1 x; returns slope, slope error, value at mean x."""
    x, y, s = map(lambda v: np.asarray(v, float), (x, y, s))
    s = np.where(np.isfinite(s) & (s > 0), s, np.nanmax(s[np.isfinite(s)]) if np.isfinite(s).any() else 1.0)
    w = 1 / s**2
    W, Sx, Sy = w.sum(), (w * x).sum(), (w * y).sum()
    Sxx, Sxy = (w * x * x).sum(), (w * x * y).sum()
    d = W * Sxx - Sx**2
    slope = (W * Sxy - Sx * Sy) / d
    icpt = (Sxx * Sy - Sx * Sxy) / d
    err = math.sqrt(W / d)
    xm = float(np.mean(x))
    return float(slope), float(err), float(icpt + slope * xm)


def analyze(material: str, model: str, temps, cells_by_T, ke_by_T, P_by_T, natoms, reps, integrator, dt, prod_ps,
            target_P_tol_GPa: float = 0.2, T_tol_frac: float = 0.03) -> ThermalResult:
    vols, sems, lens, Ts, Ps = [], [], [], [], []
    len_sems = []
    for cells, ke, P in zip(cells_by_T, ke_by_T, P_by_T):
        v = np.abs(np.linalg.det(cells)) / natoms
        vols.append(v.mean())
        sems.append(block_sem(v))
        L = cell_lengths(cells, reps)
        lens.append(L.mean(axis=0))
        len_sems.append([block_sem(L[:, k]) for k in range(3)])
        Ts.append(float(np.mean(2 * ke / (3 * (natoms - 1) * KB_EV))))
        Ps.append(float(np.mean(P)))
    slope, err, vmid = _wfit(temps, vols, sems)
    aV, aV_err = slope / vmid * 1e6, err / vmid * 1e6
    ax, ax_err = [], []
    lens_a = np.array(lens)
    for k in range(3):
        s, e, lm = _wfit(temps, lens_a[:, k], [x[k] for x in len_sems])
        ax.append(s / lm * 1e6)
        ax_err.append(e / lm * 1e6)
    checks = {
        "temperature_on_target": all(abs(t - T0) / T0 < T_tol_frac for t, T0 in zip(Ts, temps)),
        "pressure_on_target": all(abs(p) < target_P_tol_GPa for p in Ps),
        "volume_converged": all(s / v < 3e-4 for s, v in zip(sems, vols)),
        "monotonic_volume": bool(np.all(np.diff(vols) > 0)) or aV < 0,
        "relative_alpha_uncertainty": float(abs(aV_err / aV)) if aV else float("inf"),
    }
    return ThermalResult(
        material=material, model=model, temperatures=list(map(float, temps)), natoms=int(natoms), reps=list(reps),
        integrator=integrator, time_step_fs=dt, prod_ps=list(prod_ps), mean_T=Ts, mean_P_GPa=Ps,
        volume_per_atom=[float(x) for x in vols], volume_sem_rel=[float(s / v) for s, v in zip(sems, vols)],
        lengths=[list(map(float, x)) for x in lens], alpha_V_1e6=float(aV), alpha_V_err_1e6=float(aV_err),
        alpha_axes_1e6=ax, alpha_axes_err_1e6=ax_err, checks=checks,
    )


def to_record(r: ThermalResult) -> dict:
    return asdict(r)
