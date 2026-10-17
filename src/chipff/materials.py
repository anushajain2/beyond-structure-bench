"""The material set and its reference data (Materials Project DFT + experiment)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

CLASS_LABELS = {
    "semiconductors": "Semiconductors",
    "dielectrics": "Insulators & dielectrics",
    "metals": "Wiring & contact metals",
    "barriers_silicides": "Barriers & silicides",
    "layered": "Layered (2D) materials",
}


@dataclass(frozen=True)
class Material:
    id: str
    formula: str
    spg: int
    phase: str
    cls: str
    role: str = ""
    mp_hint: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def layered(self) -> bool:
        return "layered" in self.tags

    @property
    def crystal_system(self) -> str:
        n = self.spg
        if n >= 195:
            return "cubic"
        if n >= 168:
            return "hexagonal"
        if n >= 143:
            return "trigonal"
        if n >= 75:
            return "tetragonal"
        if n >= 16:
            return "orthorhombic"
        if n >= 3:
            return "monoclinic"
        return "triclinic"

    @property
    def cubic(self) -> bool:
        return self.crystal_system == "cubic"


@lru_cache
def load_materials(path: str | Path | None = None) -> tuple[Material, ...]:
    raw = yaml.safe_load(Path(path or DATA / "materials.yaml").read_text())
    out = []
    for cls, items in raw.items():
        for it in items:
            out.append(
                Material(
                    id=it["id"], formula=it["formula"], spg=int(it["spg"]), phase=it["phase"], cls=cls,
                    role=it.get("role", ""), mp_hint=it.get("mp_hint"), tags=tuple(it.get("tags", [])),
                )
            )
    return tuple(out)


def get_material(mid: str) -> Material:
    for m in load_materials():
        if m.id == mid:
            return m
    raise KeyError(mid)


def mp_record(mid: str) -> dict | None:
    p = DATA / "mp" / f"{mid}.json"
    return json.loads(p.read_text()) if p.exists() else None


def mp_structure(mid: str):
    """The Materials Project PBE structure as ASE Atoms (the starting structure)."""
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    rec = mp_record(mid)
    if rec is None:
        raise FileNotFoundError(f"data/mp/{mid}.json missing; run scripts/fetch_mp.py")
    return AseAtomsAdaptor.get_atoms(Structure.from_dict(rec["structure"]))


@lru_cache
def experimental() -> dict[str, dict]:
    """All curated experimental records, keyed by material id."""
    out: dict[str, dict] = {}
    for p in sorted((DATA / "experimental").glob("*.json")):
        for rec in json.loads(p.read_text())["materials"]:
            out[rec["id"]] = rec
    return out
