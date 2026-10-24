"""A reference engine that runs a model through its own ASE calculator instead of kUPS.

Used for MatterSim, whose kUPS JAX export currently returns energies that depend on
the order of the neighbour list and on the supercell size (see
scripts/repro_mattersim_export.py). Same interface as ``chipff.engine.Engine``
(``relax`` and ``stress``), same optimiser family (L-BFGS) and the same force
tolerance, so ``chipff.static`` runs unchanged. Results from this engine are
labelled "not via kUPS" everywhere they appear.
"""

from __future__ import annotations

import numpy as np
from ase import Atoms

from chipff.engine import EV_PER_A3_TO_GPA, RelaxResult
from chipff.models import ModelSpec


def _calculator(model: ModelSpec, device: str):
    if model.backend == "ase-mattersim":
        from mattersim.forcefield import MatterSimCalculator

        return MatterSimCalculator(load_path=model.model_path, device=device)
    raise ValueError(f"no ASE calculator for backend {model.backend!r}")


def _uma_calculator(model: ModelSpec, device: str):
    """UMA through Meta's fairchem package. kUPS's PyTorch bridge needs a GPU (XLA FFI GPU context), so on CPU
    UMA runs like MatterSim, through its own calculator. Kept apart from _calculator so that adding it leaves
    MatterSim's code fingerprint unchanged."""
    from fairchem.core import FAIRChemCalculator, pretrained_mlip

    unit = pretrained_mlip.get_predict_unit(model.extra["name"], inference_settings=model.extra["inference_settings"],
                                            device=device)
    return FAIRChemCalculator(unit, task_name=model.extra["task_name"])


class AseEngine:
    def __init__(self, model: ModelSpec, device: str | None = None):
        import torch

        self.model = model
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.calc = _uma_calculator(model, self.device) if model.backend == "ase-uma" else _calculator(model, self.device)

    def relax(self, structures: list[Atoms], *, optimize_cell: bool, fmax: float = 1e-3, max_steps: int = 1000,
              seed: int = 0) -> list[RelaxResult]:
        from ase.filters import FrechetCellFilter
        from ase.optimize import LBFGS

        out = []
        for s in structures:
            a = s.copy()
            a.calc = self.calc
            target = FrechetCellFilter(a) if optimize_cell else a
            opt = LBFGS(target, logfile=None, maxstep=0.2)
            converged = bool(opt.run(fmax=fmax, steps=max_steps))
            f = float(np.max(np.linalg.norm(a.get_forces(), axis=1)))
            cg = 0.0
            if optimize_cell:
                g = target.get_forces()[len(a):]
                cg = float(np.max(np.linalg.norm(g, axis=1)))
            res = Atoms(numbers=a.numbers, positions=a.positions, cell=a.cell, pbc=True)
            out.append(RelaxResult(atoms=res, energy=float(a.get_potential_energy()), fmax=f, max_cell_grad=cg,
                                   converged=converged, steps=int(opt.nsteps)))
        return out

    def stress(self, structures: list[Atoms]) -> tuple[np.ndarray, np.ndarray]:
        """Energies (eV) and stress tensors (GPa, ASE sign: tensile positive)."""
        E, S = [], []
        for s in structures:
            a = s.copy()
            a.calc = self.calc
            E.append(a.get_potential_energy())
            S.append(a.get_stress(voigt=False) * EV_PER_A3_TO_GPA)
        return np.array(E), np.array(S)

    def forces(self, structures: list[Atoms]) -> tuple[np.ndarray, list[np.ndarray]]:
        """Energies (eV) and forces (eV/Å), for phonon calculations."""
        E, F = [], []
        for s in structures:
            a = s.copy()
            a.calc = self.calc
            E.append(a.get_potential_energy())
            F.append(a.get_forces())
        return np.array(E), F
