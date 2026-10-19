"""Reproducer: kUPS's isotropic NPT (csvr_npt) settles at a volume where <P> != target.

1. NPT (csvr_npt, P0 = 0) on a 32-atom fcc Cu cell at 650 K with MACE-MPA-0 -> mean volume V*.
2. NVT (csvr) at fixed V* -> mean pressure there.

If the barostat sampled P0 = 0, step 2 would give ~0 GPa. We find about -0.9 GPa
(~ -N kT / V). Runs ~30 min on a laptop CPU. Requires: pip install "kups[hf]" ase
and this repository (for the thin chipff wrapper around kUPS).
"""

import numpy as np
from ase.build import bulk

from chipff.engine import Engine
from chipff.models import get_model

T = 650.0
eng = Engine(get_model("mace-mpa-0"))
cu = bulk("Cu", "fcc", a=3.64 * (1 + 1e-5 * T), cubic=True).repeat(2)


def run(integ, atoms):
    o = eng.npt([atoms], [T], integrators=[integ], time_step_fs=2.0, compressibility_per_pa=[1 / 130e9],
                equil_ps=3.0, min_prod_ps=10.0, max_prod_ps=10.0, sample_every_fs=10)
    V = np.abs(np.linalg.det(o["cells"]))[:, 0]
    P = o["pressure_GPa"][:, 0]
    return V.mean(), P.mean(), P.std() / np.sqrt(len(P) / 50)


V_npt, P_npt, s1 = run("csvr_npt", cu)
print(f"csvr_npt: <V> = {V_npt:.2f} A^3, <P> = {P_npt:+.3f} +- {s1:.3f} GPa (target 0)")
a = cu.copy()
a.set_cell(cu.cell * (V_npt / cu.get_volume()) ** (1 / 3), scale_atoms=True)
_, P_nvt, s2 = run("csvr", a)
print(f"NVT at that volume: <P> = {P_nvt:+.3f} +- {s2:.3f} GPa;  N k T / V = "
      f"{len(cu) * 8.617e-5 * T / V_npt * 160.2177:.3f} GPa")
