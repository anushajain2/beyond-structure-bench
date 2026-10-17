"""Self-check: the stress kUPS reports (rotated back to the input frame) must equal the
finite-difference strain derivative of the model's own energy, sigma = (1/V) dE/d(eps).

Run:  python scripts/check_stress.py <model-key>     (e.g. mace-mpa-0)
"""
import sys, numpy as np
from ase.build import bulk
from chipff.engine import Engine, EV_PER_A3_TO_GPA
from chipff.models import get_model
eng = Engine(get_model(sys.argv[1]))
a0 = bulk("Cu", "fcc", a=3.62)  # primitive, rotated frame like the benchmark
eps = np.array([[0.004, 0.003, -0.002], [0.003, -0.003, 0.0025], [-0.002, 0.0025, 0.002]])
def strained(e):
    a = a0.copy(); a.set_cell(np.asarray(a0.cell) @ (np.eye(3) + e).T, scale_atoms=True); return a
base = strained(eps)
h = 1e-4
structs = [base]
for i in range(3):
    for j in range(i, 3):
        for s in (+1, -1):
            d = np.zeros((3, 3)); d[i, j] = d[j, i] = s * h / (1 if i == j else 2)
            structs.append(strained(eps + d))
E, S = eng.stress(structs)
V = base.get_volume()
k = 1
fd = np.zeros((3, 3))
for i in range(3):
    for j in range(i, 3):
        dE = (E[k] - E[k + 1]) / (2 * h); k += 2
        fd[i, j] = fd[j, i] = dE / V * EV_PER_A3_TO_GPA
print("kUPS stress (GPa):\n", np.round(S[0], 3))
print("FD dE/de / V (GPa):\n", np.round(fd, 3))
err = np.abs(S[0] - fd).max()
print(f"max difference {err:.3f} GPa ->", "PASS" if err < 0.05 else "FAIL")
