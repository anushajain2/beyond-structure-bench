"""Fast checks that need no models, GPU or API key."""

import json
import math

import numpy as np
import pytest
from ase.build import bulk

from chipff.analysis import exp_alpha_V, exp_bulk, exp_volume_per_atom, window_average
from chipff.materials import DATA, experimental, get_material, load_materials
from chipff.thermal import _wfit, block_sem, supercell, temperature_window, time_step_fs


def test_material_set():
    mats = load_materials()
    assert len(mats) == 33
    assert len({m.id for m in mats}) == 33
    assert {m.cls for m in mats} == {"semiconductors", "dielectrics", "metals", "barriers_silicides", "layered"}


def test_every_experimental_value_has_a_source():
    for p in sorted((DATA / "experimental").glob("*.json")):
        for rec in json.loads(p.read_text())["materials"]:
            for key in ("lattice", "bulk_modulus", "debye_temperature_K", "melting_point_K"):
                v = rec.get(key) or {}
                has_value = v.get("a") is not None or v.get("value_GPa") is not None or v.get("value") is not None
                if has_value:
                    assert v.get("source"), f"{rec['id']}.{key} has a value but no source"
            te = rec.get("thermal_expansion") or {}
            if te.get("values"):
                assert te.get("source"), f"{rec['id']} thermal expansion has values but no source"


def test_temperature_rule():
    w = temperature_window(645, 1687, [])  # Si-like
    assert w.ok and w.temperatures[0] >= 0.75 * 645 and w.temperatures[-1] <= 1687 / 2
    w = temperature_window(445, 1768, [695])  # Co: hcp -> fcc at 695 K caps the window
    assert not w.ok or w.temperatures[-1] <= 645
    assert not temperature_window(None, 1000, []).ok
    assert temperature_window(560, 900, []).ok is False  # 420-450 K is too narrow


def test_supercell_width_and_timestep():
    sc, reps = supercell(bulk("Si", "diamond", a=5.43, cubic=True))
    assert reps == (2, 2, 2) and len(sc) == 64
    assert time_step_fs(bulk("MgO", "rocksalt", a=4.21)) == 1.0
    assert time_step_fs(bulk("Cu", "fcc", a=3.61)) == 2.0


def test_block_sem_white_noise():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 100_000)
    assert abs(block_sem(x) - 1 / math.sqrt(len(x))) < 0.002


def test_weighted_fit_recovers_slope():
    T = np.array([500.0, 700.0, 900.0])
    V = 20 * (1 + 1.5e-5 * (T - 700))
    slope, err, vmid = _wfit(T, V, [1e-4] * 3)
    assert slope / vmid == pytest.approx(1.5e-5, rel=1e-6)


def test_experimental_helpers():
    mat = get_material("GaN")
    vol = exp_volume_per_atom(mat, {"a": 3.189, "c": 5.186}, 4)
    assert vol == pytest.approx(math.sqrt(3) / 2 * 3.189**2 * 5.186 / 4)
    assert exp_bulk({"bulk_modulus": {"value_GPa": 33.8, "method": "Birch-Murnaghan EOS fit to X-ray data"}})[1] == "reuss"
    assert exp_bulk({"bulk_modulus": {"value_GPa": 98, "method": "from elastic constants (C11+2C12)/3"}})[1] == "vrh"
    rec = {"thermal_expansion": {"values": [{"T_K": 300, "axis": "a", "alpha_1e-6_per_K": 4.0},
                                             {"T_K": 300, "axis": "c", "alpha_1e-6_per_K": 3.0}]}}
    T, a = exp_alpha_V(rec, mat)
    assert T == [300.0] and a == [11.0]
    assert window_average([300, 1000], [10, 17], 400, 600)[0] == pytest.approx(12, rel=0.01)
    assert window_average([300], [10], 400, 600)[0] is None


def test_experimental_files_load():
    exp = experimental()
    assert {"Si", "Cu", "GaN", "MgO", "graphite"} <= set(exp)


def test_experimental_ids_match_material_set():
    ids = {m.id for m in load_materials()}
    extra = {"TaN_cubic"}  # documented alternative phase, not benchmarked
    assert set(experimental()) - ids <= extra
    assert ids - set(experimental()) == set()
