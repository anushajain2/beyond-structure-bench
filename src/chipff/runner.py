"""Run the benchmark steps and cache raw results under results/raw/<model>/."""

from __future__ import annotations

import json
import logging
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from chipff.materials import ROOT, Material, experimental, load_materials

RAW = ROOT / "results" / "raw"
CONFIG = ROOT / "configs" / "benchmark.yaml"
log = logging.getLogger("chipff")


def config() -> dict:
    return yaml.safe_load(CONFIG.read_text())


def raw_path(model: str, step: str) -> Path:
    return RAW / model / f"{step}.json"


def load_raw(model: str, step: str) -> dict[str, dict]:
    p = raw_path(model, step)
    if not p.exists():
        return {}
    return {r["material"]: r for r in json.loads(p.read_text())["results"]}


def save_raw(model: str, step: str, records: list[dict], meta: dict):
    """Merge records into results/raw/<model>/<step>.json, stamping each with its fingerprint."""
    from chipff.provenance import fingerprint

    for r in records:
        r.setdefault("provenance", fingerprint(step, model, r["material"]))
    p = raw_path(model, step)
    p.parent.mkdir(parents=True, exist_ok=True)
    old = load_raw(model, step)
    old.update({r["material"]: r for r in records})
    body = {"model": model, "step": step, "meta": meta, "results": list(old.values())}
    p.write_text(json.dumps(body, indent=1, default=_json_default))


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def run_meta(engine) -> dict:
    meta = {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "device": engine.device,
        "platform": platform.platform(),
        "model_path": engine.model.model_path,
        "via_kups": engine.model.via_kups,
    }
    if engine.model.via_kups:
        import jax

        from importlib.metadata import version

        meta.update(kups_version=version("kups"), jax_version=jax.__version__,
                    jax_devices=[str(d) for d in jax.devices()])
    else:
        from importlib.metadata import version

        meta.update(ase_version=version("ase"), torch_version=version("torch"),
                    calculator_package_version=version("mattersim"))
    return meta


def make_engine(model_key: str):
    from chipff.models import get_model

    spec = get_model(model_key)
    if spec.backend.startswith("ase-"):
        from chipff.ase_engine import AseEngine

        return AseEngine(spec)
    from chipff.engine import Engine

    return Engine(spec)


def select(materials: list[str] | None) -> list[Material]:
    mats = list(load_materials())
    if materials:
        unknown = set(materials) - {m.id for m in mats}
        if unknown:
            raise SystemExit(f"unknown materials: {sorted(unknown)}")
        mats = [m for m in mats if m.id in materials]
    return mats


def relaxed_structures(model: str) -> dict:
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    return {k: AseAtomsAdaptor.get_atoms(Structure.from_dict(v["structure"])) for k, v in load_raw(model, "lattice").items()}


# -- static ------------------------------------------------------------------
def run_static(model_key: str, materials: list[str] | None = None, steps=("lattice", "elastic", "eos"), force=False):
    from chipff.static import run_elastic, run_eos, run_lattice, to_records

    cfg = config()
    mats = select(materials)
    eng = make_engine(model_key)
    meta = run_meta(eng)
    if "lattice" in steps:
        todo = mats if force else [m for m in mats if m.id not in load_raw(model_key, "lattice")]
        if todo:
            t = time.time()
            res = run_lattice(eng, todo, fmax=cfg["relax"]["fmax_eV_per_A"], max_steps=cfg["relax"]["max_steps"])
            save_raw(model_key, "lattice", to_records(res), {**meta, "wall_s": time.time() - t})
            log.info("lattice: %d materials in %.0f s", len(todo), time.time() - t)
    relaxed = relaxed_structures(model_key)
    for step, fn in (("elastic", run_elastic), ("eos", run_eos)):
        if step not in steps:
            continue
        done = load_raw(model_key, step)
        todo = [m for m in mats if m.id in relaxed and (force or m.id not in done)]
        if todo:
            t = time.time()
            res = fn(eng, todo, relaxed, fmax=cfg["relax"]["fmax_eV_per_A"])
            save_raw(model_key, step, to_records(res), {**meta, "wall_s": time.time() - t})
            log.info("%s: %d materials in %.0f s", step, len(todo), time.time() - t)


# -- thermal -----------------------------------------------------------------
def thermal_plan(materials: list[Material]) -> dict:
    """Temperatures per material from the written rule + experimental data."""
    from chipff.thermal import temperature_window

    overrides = config()["thermal"].get("overrides", {}) or {}
    exp = experimental()
    plan = {}
    for m in materials:
        e = exp.get(m.id, {})
        debye = (e.get("debye_temperature_K") or {}).get("value")
        melt = (e.get("melting_point_K") or {}).get("value")
        trans = [t.get("T_K") for t in e.get("phase_transitions") or []]
        plan[m.id] = temperature_window(debye, melt, trans, override=overrides.get(m.id))
    return plan


def run_thermal(model_key: str, materials: list[str] | None = None, force=False, max_prod_ps=None, tag: str = "thermal",
                smoke: bool = False, max_edges: int | None = None):
    """NPT thermal expansion. ``smoke=True`` uses tiny cells and runs of a few ps: it tests the
    code path on a CPU and its numbers are not results."""
    from pymatgen.io.ase import AseAtomsAdaptor
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    from chipff.engine import Engine
    from chipff.models import get_model
    from ase.neighborlist import neighbor_list

    from chipff.thermal import analyze, make_stop_fn, pack_batches, supercell, time_step_fs, to_record

    cfg = config()["thermal"]
    if smoke:
        cfg = {**cfg, "min_supercell_width_A": 7.0, "equilibration_ps": 0.5,
               "production_ps": {"min": 1.0, "max": 1.0, "check_every": 1.0}}
        tag = "thermal_smoke"
    mats = select(materials)
    plan = thermal_plan(mats)
    relaxed = relaxed_structures(model_key)
    elastic = load_raw(model_key, "elastic")
    done = load_raw(model_key, tag)
    eng = Engine(get_model(model_key))
    meta = run_meta(eng)

    # group runs by (integrator, time step) so each group is one compiled kUPS batch
    groups: dict[tuple, list] = {}
    for m in mats:
        w = plan[m.id]
        if not w.ok:
            log.warning("%s: skipped (%s)", m.id, w.reason)
            continue
        if m.id not in relaxed:
            log.warning("%s: no relaxed structure for %s; run static first", m.id, model_key)
            continue
        if m.id in done and not force:
            continue
        conv = SpacegroupAnalyzer(AseAtomsAdaptor.get_structure(relaxed[m.id]), symprec=0.1).get_conventional_standard_structure()
        atoms = AseAtomsAdaptor.get_atoms(conv)
        sc, reps = supercell(atoms, cfg["min_supercell_width_A"])
        dt = time_step_fs(sc)
        integ = cfg["integrator"]["cubic"] if m.cubic else cfg["integrator"]["other"]
        K = (elastic.get(m.id) or {}).get("K_reuss_GPa") or 100.0
        groups.setdefault((integ, dt), []).append((m, sc, reps, w.temperatures, 1 / (max(K, 5.0) * 1e9)))

    prod = cfg["production_ps"]
    budget = int(max_edges or cfg.get("max_edges_per_batch", 24000))
    for (integ, dt), items in groups.items():
        # one job per (material, temperature); jobs are packed into batches under a memory budget
        # (neighbour pairs within the model cutoff, which is what MLFF memory scales with)
        jobs = []
        for m, sc, reps, Ts, k in items:
            n_edges = len(neighbor_list("i", sc, cfg.get("edge_cutoff_A", 6.0)))
            for T in Ts:
                # start near the expected volume (linear strain 1e-5/K x T) so the initial thermal
                # pressure doesn't kick the cell into a long-lived breathing oscillation
                start = sc.copy()
                start.set_cell(sc.cell * (1 + cfg.get("start_strain_per_K", 1e-5) * T), scale_atoms=True)
                jobs.append({"m": m, "T": T, "atoms": start, "k": k, "edges": n_edges, "reps": reps, "natoms": len(sc)})
        batches = pack_batches(jobs, budget)

        pending: dict[str, dict] = {}
        need = {m.id: len(Ts) for m, _, _, Ts, _ in items}
        for b, batch in enumerate(batches, 1):
            log.info("%s: NPT %s dt=%.1f fs, batch %d/%d: %d systems, %d atoms, ~%d pairs (%s)", model_key, integ, dt, b,
                     len(batches), len(batch), sum(len(j["atoms"]) for j in batch), sum(j["edges"] for j in batch),
                     ", ".join(f"{j['m'].id}@{j['T']:.0f}K" for j in batch))
            out = eng.npt(
                [j["atoms"] for j in batch], [j["T"] for j in batch], integrators=[integ] * len(batch), time_step_fs=dt,
                compressibility_per_pa=[j["k"] for j in batch], equil_ps=cfg["equilibration_ps"],
                min_prod_ps=prod["min"], max_prod_ps=max_prod_ps or prod["max"], check_every_ps=prod["check_every"],
                sample_every_fs=cfg["sample_every_fs"], stop_fn=make_stop_fn(cfg["stop_when_volume_sem_below"]),
                thermostat_tau_fs=cfg["thermostat_tau_fs"], barostat_tau_fs=cfg["barostat_tau_fs"],
                friction_per_fs=cfg["langevin_friction_per_fs"],
            )
            steps = (cfg["equilibration_ps"] + out["prod_ps"]) * 1000 / dt
            log.info("%s: batch %d done in %.1f min (%.1f ms/step, %.1f ps production)", model_key, b,
                     out["wall_s"] / 60, 1000 * out["wall_s"] / max(steps, 1), out["prod_ps"])
            for i, j in enumerate(batch):
                pending.setdefault(j["m"].id, {})[j["T"]] = (
                    j, out["cells"][:, i], out["kinetic_energy"][:, i], out["pressure_GPa"][:, i], out["prod_ps"])
            recs = []
            for mid, by_T in list(pending.items()):
                if len(by_T) < need[mid]:
                    continue
                Ts = sorted(by_T)
                j0 = by_T[Ts[0]][0]
                r = analyze(mid, model_key, Ts, [by_T[T][1] for T in Ts], [by_T[T][2] for T in Ts],
                            [by_T[T][3] for T in Ts], j0["natoms"], j0["reps"], integ, dt, [by_T[T][4] for T in Ts])
                recs.append(to_record(r))
                del pending[mid]
                log.info("%s %s: alpha_V = %.2f ± %.2f e-6/K", model_key, mid, r.alpha_V_1e6, r.alpha_V_err_1e6)
            if recs:
                save_raw(model_key, tag, recs, {**meta, "wall_s": out["wall_s"], "batch": [integ, dt]})
