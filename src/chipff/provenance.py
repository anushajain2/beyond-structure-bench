"""Fingerprints that tie every saved result to the code, settings and inputs that made it.

A fingerprint has three hashes that must match for a result to be used:

* ``code``: the source of exactly the functions that compute this step, for this
  model's backend (editing unrelated code, e.g. the MD integrator, does not
  invalidate lattice results);
* ``settings``: the config sections the step reads, plus the model file and options;
* ``inputs``: the material's starting data and, for later steps, the upstream results
  they build on (elastic uses the relaxed structure; thermal also uses the bulk
  modulus and the temperature plan).

It also records, for information only, the git commit and package versions.
``chipff analyze`` recomputes the three hashes and sets aside any result whose
fingerprint no longer matches, so results from different code or settings are
never mixed.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version

from chipff.materials import ROOT, mp_record

STEPS = ("lattice", "elastic", "eos", "thermal")


def _h(obj) -> str:
    data = obj if isinstance(obj, (bytes, str)) else json.dumps(obj, sort_keys=True, default=str)
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()[:16]


def _code_objects(step: str, backend: str) -> list:
    from chipff import engine, static, thermal

    ase_backend = backend.startswith("ase-")
    if ase_backend:
        from chipff import ase_engine

        relax = [ase_engine.AseEngine.relax, ase_engine._calculator]
        stress = [ase_engine.AseEngine.stress]
    else:
        E = engine.Engine
        relax = [E._potential, E.relax, engine._split]
        stress = [E._potential, E.stress, E._md_state, E._md_step_fn, E._advance]
    if step == "lattice":
        return relax + [static.symmetry, static.run_lattice]
    if step == "elastic":
        return relax + stress + [static._batched, static.run_elastic, static.elastic_moduli, "STRAINS",
                                 repr(static.STRAINS)]
    if step == "eos":
        return relax + [static.run_eos, "EOS_VOLUME_SCALES", repr(static.EOS_VOLUME_SCALES)]
    if step == "thermal_qha":
        from chipff import qha, runner

        fcall = [ase_engine.AseEngine.forces] if ase_backend else [engine.Engine.forces, engine.Engine._md_state,
                                                                    engine.Engine._md_step_fn, engine.Engine._advance]
        return relax + fcall + [qha.run_qha, qha._forces_batched, qha._supercell_reps, qha._phonopy_atoms,
                                runner.run_thermal_qha, runner.thermal_plan]
    if step.startswith("thermal"):
        from chipff import runner

        E = engine.Engine
        return [E._potential, E._md_state, E._md_step_fn, E._advance, E.npt, runner.run_thermal, runner.thermal_plan,
                thermal.temperature_window, thermal.supercell, thermal.time_step_fs, thermal.pack_batches,
                thermal.block_sem, thermal.make_stop_fn, thermal.cell_lengths, thermal._wfit, thermal.analyze]
    raise ValueError(step)


def _code_step(step: str) -> str:
    if step == "thermal_qha":
        return step
    return "thermal" if step.startswith("thermal") else step


@lru_cache
def code_hash(step: str, backend: str) -> str:
    parts = [o if isinstance(o, str) else inspect.getsource(o) for o in _code_objects(step, backend)]
    return _h("\n".join(parts))


def settings_hash(step: str, model_key: str) -> str:
    from chipff.models import get_model
    from chipff.runner import config

    cfg = config()
    sections = {"lattice": ["relax"], "elastic": ["relax", "elastic"], "eos": ["relax", "eos"],
                "thermal_qha": ["thermal_qha"]}
    keys = sections.get(step, ["thermal"])
    m = get_model(model_key)
    return _h({"config": {k: cfg.get(k) for k in keys},
               "model": {"path": m.model_path, "backend": m.backend, "extra": m.extra}})


def inputs_hash(step: str, model_key: str, material: str) -> str:
    from chipff.runner import load_raw, thermal_plan, select

    mp = mp_record(material) or {}
    parts = {"mp_structure": _h(mp.get("structure"))}
    if step in ("elastic", "eos") or step.startswith("thermal"):
        lat = load_raw(model_key, "lattice").get(material) or {}
        parts["relaxed_structure"] = _h(lat.get("structure"))
    if step == "thermal_qha":
        w = thermal_plan(select([material]))[material]
        parts["temperatures"] = list(w.temperatures)
    elif step.startswith("thermal"):
        el = load_raw(model_key, "elastic").get(material) or {}
        parts["K_reuss"] = round(float(el["K_reuss_GPa"]), 6) if el.get("K_reuss_GPa") is not None else None
        w = thermal_plan(select([material]))[material]
        parts["temperatures"] = list(w.temperatures)
    return _h(parts)


@lru_cache
def _git() -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                                check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "src", "configs", "data"], cwd=ROOT,
                                    capture_output=True, text=True).stdout.strip())
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


@lru_cache
def _versions() -> dict:
    out = {}
    for pkg in ("kups", "jax", "mattersim", "torch", "ase", "pymatgen"):
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            pass
    return out


def fingerprint(step: str, model_key: str, material: str, stamped: str = "at run time") -> dict:
    from chipff.models import get_model

    return {
        "code": code_hash(_code_step(step), get_model(model_key).backend),
        "settings": settings_hash(step, model_key),
        "inputs": inputs_hash(step, model_key, material),
        "git": _git(),
        "versions": _versions(),
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stamped": stamped,
    }


def check(step: str, model_key: str, material: str, rec: dict) -> str | None:
    """None if the record's fingerprint matches today's code, settings and inputs; else the reason."""
    fp = rec.get("provenance")
    if not fp:
        return "no fingerprint (computed before provenance stamping)"
    from chipff.models import get_model

    now = {"code": code_hash(_code_step(step), get_model(model_key).backend),
           "settings": settings_hash(step, model_key), "inputs": inputs_hash(step, model_key, material)}
    stale = [k for k in ("code", "settings", "inputs") if fp.get(k) != now[k]]
    return None if not stale else "computed with different " + ", ".join(stale)
