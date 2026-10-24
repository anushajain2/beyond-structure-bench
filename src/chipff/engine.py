"""Batched kUPS calculations: relaxation, stress, and NPT molecular dynamics.

Everything physical in BeyondStructure Bench goes through this module, and everything in
it goes through kUPS's public building blocks (potentials, relaxation and MD
propagators). Structures enter and leave as ASE ``Atoms``; many structures are
stacked into one kUPS batch so each model is compiled once per batch shape.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

import numpy as np
from ase import Atoms

from chipff.models import ModelSpec

log = logging.getLogger(__name__)

EV_PER_A3_TO_GPA = 160.21766208

_LBFGS = [
    {"transform": "scale_by_ase_lbfgs", "memory_size": 100, "alpha": 70},
    {"transform": "max_step_size", "max_step_size": 0.2},
    {"transform": "scale", "step_size": -1},
]


def _kups():
    """Import kUPS lazily (it switches JAX to float64 on import, like its CLIs)."""
    import jax

    import kups.application.simulations.md  # noqa: F401  (sets jax x64 + cache dir)
    import kups.application.simulations.relax  # noqa: F401

    jax.config.update("jax_compilation_cache_dir", str(Path(tempfile.gettempdir()) / "chipff_jax_cache"))
    return jax


def default_device() -> str:
    jax = _kups()
    return "cuda" if any(d.platform == "gpu" for d in jax.devices()) else "cpu"


@dataclass
class RelaxResult:
    atoms: Atoms
    energy: float  # eV per cell
    fmax: float  # eV/Å, max atomic force at the end
    max_cell_grad: float  # optimizer cell-DOF gradient at the end (0 if cell fixed)
    converged: bool
    steps: int


def _split(state, n_systems: int):
    """Turn a batched kUPS state back into per-system numpy arrays."""
    pos = np.asarray(state.particles.data.positions)
    sys_idx = np.asarray(state.particles.data.system.indices)
    numbers = np.asarray(state.particles.data.atomic_numbers)
    cells = np.asarray(state.systems.data.cell.vectors)
    out = []
    for i in range(n_systems):
        m = sys_idx == i
        out.append((numbers[m], pos[m], cells[i], m))
    return out


class Engine:
    """One ML force field, ready to run batched kUPS jobs."""

    def __init__(self, model: ModelSpec, device: str | None = None, workdir: str | Path | None = None):
        self.jax = _kups()
        self.model = model
        self.device = device or default_device()
        self.workdir = Path(workdir or Path(tempfile.gettempdir()) / "chipff_work")
        self.workdir.mkdir(parents=True, exist_ok=True)
        self._potentials: dict[str, tuple] = {}

    # -- potentials ---------------------------------------------------------
    def _potential(self, kind: str, lens):
        from kups.application.potential.filter import FRECHET_FILTER, POSITIONS_AND_CELL, POSITIONS_ONLY

        flt = {"cell": FRECHET_FILTER, "positions": POSITIONS_ONLY, "md": POSITIONS_AND_CELL}[kind]
        cfg = self.model.potential_config(self.device)
        return cfg.build(lens, flt), flt

    # -- relaxation ---------------------------------------------------------
    def relax(
        self,
        structures: list[Atoms],
        *,
        optimize_cell: bool,
        fmax: float = 1e-3,
        max_steps: int = 1000,
        seed: int = 0,
    ) -> list[RelaxResult]:
        """Relax many structures in one kUPS batch (L-BFGS, as in kUPS's examples)."""
        import jax.numpy as jnp

        from kups.application.relaxation.data import RelaxRunConfig, RelaxState, relax_state_from_ase
        from kups.application.relaxation.simulation import make_relax_propagator, run_relax
        from kups.core.data import Table
        from kups.core.lens import identity_lens
        from kups.core.neighborlist import UniversalNeighborlistParameters
        from kups.relaxation.config import make_optimizer

        lens = identity_lens(RelaxState)
        (pot, cutoff), flt = self._potential("cell" if optimize_cell else "positions", lens)
        cfg = RelaxRunConfig(
            out_file=str(self.workdir / f"relax_{os.getpid()}_{time.time_ns()}.h5"),
            max_steps=max_steps,
            seed=seed,
            force_tolerance=fmax,
            optimizer=_LBFGS,
            optimize_cell=optimize_cell,
        )
        opt = make_optimizer(cfg.optimizer)
        prop, opt_init = make_relax_propagator(lens, pot, opt, flt)
        parts = [relax_state_from_ase(a.copy()) for a in structures]
        particles, systems = Table.union([p for p, _ in parts], [s for _, s in parts])
        mult = 2.0 if self.model.backend != "tojax" else 1.0
        nl = UniversalNeighborlistParameters.estimate(particles.data.system.counts, systems, cutoff, multiplier=mult)
        state = RelaxState(
            particles=particles,
            systems=systems,
            neighborlist_params=nl,
            opt_state=opt_init(particles, systems),
            step=jnp.array([0]),
        )
        final = run_relax(self.jax.random.key(seed), prop, state, cfg)
        Path(cfg.out_file).unlink(missing_ok=True)

        steps = int(np.asarray(final.step).ravel()[0])
        energies = np.asarray(final.systems.data.potential_energy)
        grads = np.asarray(final.particles.data.position_gradients)
        cell_leaves = [np.asarray(x) for x in self.jax.tree.leaves(final.systems.data.cell_gradients)]
        results = []
        for i, (numbers, pos, cell, mask) in enumerate(_split(final, len(structures))):
            f = float(np.max(np.linalg.norm(grads[mask], axis=-1))) if mask.any() else 0.0
            cg = 0.0
            if optimize_cell:
                cg = float(max(np.max(np.abs(leaf[i])) for leaf in cell_leaves if leaf.ndim >= 1 and leaf.shape[0] == len(structures)))
                atoms = Atoms(numbers=numbers, positions=pos, cell=cell, pbc=True)
            else:
                # kUPS works in its own (rotated) frame; hand the atoms back in the INPUT frame via
                # fractional coordinates, so stresses computed later refer to the caller's axes
                src = structures[i]
                assert list(numbers) == list(src.numbers), "kUPS reordered atoms"
                frac = np.linalg.solve(np.asarray(cell).T, np.asarray(pos).T).T
                atoms = Atoms(numbers=numbers, scaled_positions=frac, cell=src.cell, pbc=True)
            results.append(
                RelaxResult(
                    atoms=atoms,
                    energy=float(energies[i]),
                    fmax=f,
                    max_cell_grad=cg,
                    converged=max(f, cg) < fmax * 1.0001,
                    steps=steps,
                )
            )
        return results

    # -- single-point stress -------------------------------------------------
    def stress(self, structures: list[Atoms]) -> tuple[np.ndarray, np.ndarray]:
        """Energies (eV) and stress tensors (GPa, ASE sign: tensile positive).

        kUPS reports stress as -(1/V) dU/dε from the virial; we evaluate it by
        taking a single velocity-Verlet step of negligible length from rest, so
        the atoms do not move and the stored gradients are those of the input
        geometry.
        """
        from kups.application.md.data import MdParameters
        from kups.observables.stress import stress_via_virial_theorem

        state = self._md_state(structures, MdParameters(
            temperature=0.0, time_step=1e-9, friction_coefficient=0.0, thermostat_time_constant=1.0,
            target_pressure=0.0, pressure_coupling_time=1.0, compressibility=1e-11, minimum_scale_factor=0.0,
            integrator="verlet", initialize_momenta=False,
        ))
        step = self._md_step_fn(state, "verlet", 1)
        state = self._advance(step, state, self.jax.random.key(0))
        sigma = np.asarray(stress_via_virial_theorem(state.particles, state.systems).data)
        energies = np.asarray(state.systems.data.potential_energy)
        # kUPS rotates every cell into its own lower-triangular frame (rows L = H @ Rt).
        # Rotate each stress back into the frame of the input cell H: sigma_H = Rt sigma_L Rt^T.
        L_all = np.asarray(state.systems.data.cell.vectors)
        out = []
        for a, L, sg in zip(structures, L_all, sigma):
            Rt = np.linalg.solve(np.asarray(a.cell), L)
            out.append(Rt @ sg @ Rt.T)
        return energies, -np.array(out) * EV_PER_A3_TO_GPA

    # -- single-point forces ---------------------------------------------------
    def forces(self, structures: list[Atoms]) -> tuple[np.ndarray, list[np.ndarray]]:
        """Energies (eV) and forces (eV/Å) in each input's own frame, for phonon calculations.

        Same single negligible-length Verlet step as ``stress``; kUPS's frame rotation is
        undone per structure (forces transform like positions: f_in = f_kups @ Rt^T).
        """
        from kups.application.md.data import MdParameters

        state = self._md_state(structures, MdParameters(
            temperature=0.0, time_step=1e-9, friction_coefficient=0.0, thermostat_time_constant=1.0,
            target_pressure=0.0, pressure_coupling_time=1.0, compressibility=1e-11, minimum_scale_factor=0.0,
            integrator="verlet", initialize_momenta=False,
        ))
        step = self._md_step_fn(state, "verlet", 1)
        state = self._advance(step, state, self.jax.random.key(0))
        grads = np.asarray(state.particles.data.position_gradients)
        energies = np.asarray(state.systems.data.potential_energy)
        L_all = np.asarray(state.systems.data.cell.vectors)
        out = []
        for i, (numbers, _pos, _cell, mask) in enumerate(_split(state, len(structures))):
            assert list(numbers) == list(structures[i].numbers), "kUPS reordered atoms"
            Rt = np.linalg.solve(np.asarray(structures[i].cell), L_all[i])
            out.append(-grads[mask] @ Rt.T)
        return energies, out

    # -- molecular dynamics --------------------------------------------------
    def _md_state(self, structures, params_list, keys=None):
        import jax.numpy as jnp

        from kups.application.md.data import MdParameters, MdState, md_state_from_ase
        from kups.core.data import Table
        from kups.core.lens import identity_lens
        from kups.core.neighborlist import UniversalNeighborlistParameters

        if isinstance(params_list, MdParameters):
            params_list = [params_list] * len(structures)
        lens = identity_lens(MdState)
        if not hasattr(self, "_md_lens"):
            self._md_lens = lens
        (pot, cutoff), _ = self._potential("md", lens)
        self._md_pot = pot
        parts = [
            md_state_from_ase(a.copy(), p, key=None if keys is None else keys[i])
            for i, (a, p) in enumerate(zip(structures, params_list))
        ]
        particles, systems = Table.union([p for p, _ in parts], [s for _, s in parts])
        base = 1 if self.model.backend == "tojax" else 2
        mult = 2.0 if self.model.backend != "tojax" else 1.0
        nl = UniversalNeighborlistParameters.estimate(
            particles.data.system.counts, systems, cutoff, base=base, multiplier=mult
        )
        return MdState(particles=particles, systems=systems, neighborlist_params=nl, step=jnp.array([0]))

    def _md_step_fn(self, state, integrator: str, block: int):
        from kups.application.md.simulation import make_md_propagator
        from kups.application.utils.propagate import make_cycle_function
        from kups.core.propagator import LoopPropagator

        prop = make_md_propagator(self._md_lens, integrator, self._md_pot)
        return make_cycle_function(LoopPropagator(prop, block) if block > 1 else prop)

    def _advance(self, fn, state, key):
        from kups.core.propagator import propagate_and_fix

        return propagate_and_fix(fn, key, state)

    def npt(
        self,
        structures: list[Atoms],
        temperatures: list[float],
        *,
        integrators: list[str],
        time_step_fs: float,
        compressibility_per_pa: list[float],
        equil_ps: float,
        min_prod_ps: float,
        max_prod_ps: float,
        sample_every_fs: float = 10.0,
        check_every_ps: float = 5.0,
        stop_fn=None,
        seed: int = 0,
        thermostat_tau_fs: float = 100.0,
        barostat_tau_fs: float = 1000.0,
        friction_per_fs: float = 0.01,
    ) -> dict:
        """Run batched NPT MD at P = 0 and record cell vectors over time.

        All systems in one call must share an integrator (one compiled program),
        so callers group cubic and non-cubic materials separately.
        """
        from kups.application.md.data import MdParameters

        assert len(set(integrators)) == 1, "one integrator per batch"
        integ = integrators[0]
        params = [
            MdParameters(
                temperature=float(T),
                time_step=time_step_fs,
                friction_coefficient=friction_per_fs,
                thermostat_time_constant=thermostat_tau_fs,
                target_pressure=0.0,
                pressure_coupling_time=barostat_tau_fs,
                compressibility=float(k),
                minimum_scale_factor=0.0,
                integrator=integ,
                initialize_momenta=True,
            )
            for T, k in zip(temperatures, compressibility_per_pa)
        ]
        keys = list(self.jax.random.split(self.jax.random.key(seed), len(structures)))
        state = self._md_state(structures, params, keys)
        block = max(1, int(round(sample_every_fs / time_step_fs)))
        fn = self._md_step_fn(state, integ, block)
        key = self.jax.random.key(seed + 1)

        n_equil = int(round(equil_ps * 1000 / (block * time_step_fs)))
        n_check = max(1, int(round(check_every_ps * 1000 / (block * time_step_fs))))
        n_min = int(round(min_prod_ps * 1000 / (block * time_step_fs)))
        n_max = int(round(max_prod_ps * 1000 / (block * time_step_fs)))

        from kups.md.observables import system_kinetic_energy

        from kups.observables.stress import stress_via_virial_theorem

        import jax.numpy as jnp

        @self.jax.jit
        def _snap(s):
            cells = s.systems.data.cell.vectors
            ke = system_kinetic_energy(s.particles.data.momenta, s.particles.data.masses,
                                       s.particles.data.system, remove_com=True)
            vir = stress_via_virial_theorem(s.particles, s.systems).data  # pressure-positive
            vol = jnp.abs(jnp.linalg.det(cells))
            p = (jnp.trace(vir, axis1=-2, axis2=-1) / 3 + 2 * ke / (3 * vol)) * EV_PER_A3_TO_GPA
            return cells, ke, p

        def snapshot(s):
            return tuple(np.asarray(x) for x in _snap(s))

        t0 = time.time()
        for _ in range(n_equil):
            key, k = self.jax.random.split(key)
            state = self._advance(fn, state, k)
        t_equil = time.time() - t0
        cells, kes, press = [], [], []
        i = 0
        while i < n_max:
            key, k = self.jax.random.split(key)
            state = self._advance(fn, state, k)
            c, ke, p = snapshot(state)
            cells.append(c)
            kes.append(ke)
            press.append(p)
            i += 1
            if i >= n_min and i % n_check == 0 and stop_fn is not None and stop_fn(np.array(cells)):
                break
        natoms = np.array([len(a) for a in structures])
        return {
            "cells": np.array(cells),  # (n_samples, n_systems, 3, 3) Å
            "kinetic_energy": np.array(kes),  # eV
            "pressure_GPa": np.array(press),
            "natoms": natoms,
            "sample_dt_fs": block * time_step_fs,
            "prod_ps": i * block * time_step_fs / 1000,
            "equil_ps": equil_ps,
            "wall_s": time.time() - t0,
            "wall_equil_s": t_equil,
        }

    def nve_drift(self, structures: list[Atoms], temperature: float, time_step_fs: float, ps: float = 2.0, seed: int = 0):
        """Energy drift (meV/atom/ps) of a short no-thermostat run, the time-step check."""
        from kups.application.md.data import MdParameters

        p = MdParameters(
            temperature=temperature, time_step=time_step_fs, friction_coefficient=0.0, thermostat_time_constant=1.0,
            target_pressure=0.0, pressure_coupling_time=1.0, compressibility=1e-11, minimum_scale_factor=0.0,
            integrator="verlet", initialize_momenta=True,
        )
        keys = list(self.jax.random.split(self.jax.random.key(seed), len(structures)))
        state = self._md_state(structures, p, keys)
        block = max(1, int(round(10 / time_step_fs)))
        fn = self._md_step_fn(state, "verlet", block)
        from kups.md.observables import system_kinetic_energy

        n = int(round(ps * 1000 / (block * time_step_fs)))
        tot = []
        key = self.jax.random.key(seed)
        for _ in range(n):
            key, k = self.jax.random.split(key)
            state = self._advance(fn, state, k)
            ke = np.asarray(system_kinetic_energy(state.particles.data.momenta, state.particles.data.masses,
                                                  state.particles.data.system))
            tot.append(ke + np.asarray(state.systems.data.potential_energy))
        tot = np.array(tot)
        t = np.arange(n) * block * time_step_fs / 1000
        natoms = np.array([len(a) for a in structures])
        slopes = np.polyfit(t, tot, 1)[0]  # eV/ps per system
        return slopes / natoms * 1000  # meV/atom/ps
