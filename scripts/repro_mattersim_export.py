"""Minimal reproducer: the kUPS MatterSim JAX export depends on edge order and supercell size.

Calls the exported model directly on a clean AtomGraphInput built with ASE's neighbour
list (no kUPS neighbour-list padding involved), for crystalline Si:

  1. the same graph with its edges shuffled,
  2. the primitive cell vs a 2x2x2 supercell (per-atom energy must be identical),

and runs the MACE export through the identical path as a control.
For reference, Microsoft's official `mattersim` package (MatterSimCalculator,
MatterSim-v1.0.0-5M) gives -5.4014 eV/atom for this structure in both cells.

Requires: pip install "kups[hf]" ase
"""

import numpy as np

import kups.application.simulations.relax  # noqa: F401  (float64, as kUPS's own apps)
import jax.numpy as jnp
from ase.build import bulk
from ase.neighborlist import neighbor_list
from kups.application.utils.path import get_model_path
from kups.potential.mliap.tojax import TojaxedMliap

MODELS = {
    "MatterSim 5M (export)": "hf://CuspAI/kUPS-mattersim-jax/mattersim-v1.0.0-5m.zip",
    "MACE-MPA-0 (control)": "hf://CuspAI/kUPS-mace-jax/mace-mpa-0-medium_32.zip",
}


def graph(atoms, cutoff, order=None):
    i, j, S = neighbor_list("ijS", atoms, cutoff)
    ei, off = np.stack([i, j]), S.astype(float)
    if order is not None:
        o = order(len(i))
        ei, off = ei[:, o], off[o]
    n = len(atoms)
    return {
        "pos": jnp.asarray(atoms.positions), "atomic_numbers": jnp.asarray(atoms.numbers),
        "cell": jnp.asarray(np.asarray(atoms.cell))[None], "pbc": jnp.ones((1, 3), bool),
        "edge_index": jnp.asarray(ei), "cell_offsets": jnp.asarray(off), "batch": jnp.zeros(n, int),
        "charge": jnp.zeros(1), "spin": jnp.zeros(1),
    }


si = bulk("Si", "diamond", a=5.47)
shuffle = lambda n: np.random.default_rng(0).permutation(n)  # noqa: E731
for name, path in MODELS.items():
    m = TojaxedMliap.from_zip_file(get_model_path(path))
    rc = float(m.cutoff.data[0])
    e = lambda a, order=None: float(np.asarray(m.call(graph(a, rc, order)))[0]) / len(a)  # noqa: E731
    print(f"{name}")
    print(f"  primitive, ASE edge order   {e(si): .5f} eV/atom")
    print(f"  primitive, shuffled edges   {e(si, shuffle): .5f} eV/atom")
    print(f"  2x2x2 supercell             {e(si.repeat(2)): .5f} eV/atom")
