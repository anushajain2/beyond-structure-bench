"""Fast checks that need no models, GPU or API key."""

import json
import math

import numpy as np
import pytest
from ase.build import bulk

from chipff.analysis import exp_alpha_V, exp_bulk, exp_volume_per_atom, window_average
from chipff.materials import DATA, experimental, get_material, load_materials
from chipff.thermal import _wfit, block_sem, pack_batches, supercell, temperature_window, time_step_fs


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


def test_pack_batches_respects_padded_budget():
    jobs = [{"id": i, "edges": e} for i, e in enumerate([8000, 8000, 8000, 3000, 3000, 3000, 30000])]
    batches = pack_batches(jobs, budget=24000)
    for b in batches:
        assert len(b) == 1 or len(b) * max(j["edges"] for j in b) <= 24000
    assert sorted(j["id"] for b in batches for j in b) == list(range(7))   # nothing lost
    assert any(len(b) == 1 and b[0]["edges"] == 30000 for b in batches)  # oversize job runs alone


def test_provenance_detects_stale_results():
    import copy

    from chipff.provenance import check
    from chipff.runner import load_raw

    rec = load_raw("mace-mpa-0", "lattice")["Si"]
    assert check("lattice", "mace-mpa-0", "Si", rec) is None          # committed results match today's code
    stale = copy.deepcopy(rec)
    stale["provenance"]["code"] = "0" * 16
    assert "code" in check("lattice", "mace-mpa-0", "Si", stale)
    assert check("lattice", "mace-mpa-0", "Si", {k: v for k, v in rec.items() if k != "provenance"})  # unstamped


def test_model_agreement_and_pending():
    import pandas as pd

    from chipff.robustness import model_agreement

    ref = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    rows = []
    for mk, scale, pending in (("a", [1.1, 1.2, 0.9, 1.0, 1.3, 0.8], False), ("b", [1.1, 1.2, 0.9, 1.0, 1.3, 0.8], False),
                               ("c", [1.5] * 6, True)):
        for i, (r, f) in enumerate(zip(ref, scale)):
            rows.append({"model": mk, "material": f"m{i}", "class": "metals", "alpha_V": r * f, "alpha_V_exp": r,
                         "alpha_V_300K": None, "alpha_V_300K_exp": None, "err_exp_pct": 100 * (f - 1),
                         "err_300K_pct": None, "pending": pending})
    out = model_agreement(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(rows), n=200)
    assert list(zip(out.model_a, out.model_b)) == [("a", "b")]  # the pending model is left out
    r = out.iloc[0]
    assert abs(r.error_correlation - 1) < 1e-9 and abs(r.MAPE_average_of_two - r.MAPE_a) < 1e-9


def test_mcp_temperature_and_exclusions():
    import io

    from ase.io import write

    from chipff.mcp_server import check_material, recommend_model

    r = recommend_model("Si", "thermal_expansion", 300)
    assert r["comparison"] == "300 K" and "calibrated" in r["caution"]
    r = recommend_model("Si", "thermal_expansion", 2000)
    assert "no evidence" in r["temperature_note"] and "lower bound" not in r["temperature_note"]
    buf = io.BytesIO()
    write(buf, bulk("Si", "diamond", 5.43), format="cif")
    out = check_material(buf.getvalue().decode(), models=["mattersim-5m"])  # the broken export is refused
    assert "excluded" in out["skipped"]["mattersim-5m"] and "error" in out


def test_coverage_counts_model_failures():
    import pandas as pd

    from chipff.analysis import coverage_table

    lat = pd.DataFrame({"model": ["a", "a"], "material": ["x", "y"], "class": ["metals"] * 2,
                        "err_lin_exp_pct": [0.5, None], "excluded": [None, "relaxed to a different crystal form (P1)"]})
    cov = coverage_table(lat, pd.DataFrame(), pd.DataFrame())
    r = cov.iloc[0]
    assert (r.graded, r.model_failure, r.method_limit) == (1, 1, 0) and "y" in r.model_failure_cases


def test_qha_free_energy_ignores_gamma_acoustic_modes():
    """The acoustic modes at Gamma come out as ~1e-7 THz of random sign. Left in the free energy, they
    make alpha depend on force noise far below any physical scale (docs/thermal_failure_study.md).
    A coarse q-mesh (larger Gamma weight) makes the effect unmistakable on a model-free EMT copper crystal."""
    from types import SimpleNamespace

    from ase.calculators.emt import EMT

    from chipff.ase_engine import AseEngine
    from chipff.qha import run_qha
    from chipff.runner import config

    class NoisyEMT(AseEngine):
        def __init__(self, seed):
            self.calc, self.device, self.rng = EMT(), "cpu", np.random.default_rng(seed)

        def forces(self, structures):
            E, F = super().forces(structures)
            return E, [f + self.rng.normal(0, 3e-6, f.shape) for f in F]

    def alphas(exclude):
        q = dict(config()["thermal_qha"], exclude_gamma_acoustic=exclude, mesh_length=10.0)
        return [run_qha(NoisyEMT(seed), SimpleNamespace(id="Cu"), "emt", bulk("Cu", "fcc", a=3.61), [300, 600], q)
                .alpha_V_300K_1e6 for seed in range(3)]

    assert config()["thermal_qha"]["exclude_gamma_acoustic"] is True
    fixed = alphas(True)
    assert max(fixed) - min(fixed) < 0.005 * np.mean(fixed)  # 3e-6 eV/Å of noise: agreement to 0.5 %
    assert 40 < np.mean(fixed) < 80  # EMT Cu expands like a metal (about 62e-6/K)
    unfixed = alphas(False)
    assert max(unfixed) - min(unfixed) > 0.05 * np.mean(fixed)  # the defect the setting removes


def test_site_evidence_builds():
    import importlib.util

    from chipff.materials import ROOT

    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ev = mod.evidence()
    assert len(ev["materials"]) == 33 and ev["study_materials"] == sorted(["Si", "GaAs", "InP", "Cu", "Ta", "HfO2"])
    # Orb's benchmark-wide thermal results are not part of this release, so no stale values are published
    th = ev["results"]["thermal_expansion"]
    assert all(set(r) == {"stale"} for m in th.values() for k, r in m.items() if k == "orb-v3")
