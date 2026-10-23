"""Build the static project site (GitHub Pages) from the committed results.

  python scripts/build_site.py            # writes _site/
  python -m http.server -d _site 8000     # preview

Pages live in site/pages/*.html (body only, first line `<!-- title: ... | description -->`);
site/layout.html wraps them. The evidence explorer reads _site/data/evidence.json, which this
script builds from results/summary.json, data/experimental/*.json and results/thermal_failure/.
Only the standard library is used, so the Pages workflow needs no scientific packages.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "site"
OUT = ROOT / "_site"
REPO = "https://github.com/anushajain2/chipff-bench"
RELEASE_DATE = "2026-10-20"

MODELS = ["mace-mpa-0", "orb-v3", "mattersim-5m-native"]
SHORT = {"mace-mpa-0": "MACE-MPA-0", "orb-v3": "Orb v3", "mattersim-5m-native": "MatterSim v1"}
STUDY_BACKEND = {"mace-kups": "mace-mpa-0", "orb-kups": "orb-v3", "mattersim-native": "mattersim-5m-native"}
NAV = [("index.html", "Overview"), ("explore.html", "Explore evidence"), ("study.html", "The study"),
       ("design.html", "Evaluation design"), ("building.html", "How it was built"), ("reproduce.html", "Reproduce")]
FIGURES = ["study_errors", "study_ingredients", "study_kprime", "trust_map_experiment", "trust_map_dft",
           "parity_cte_exp", "signed_cte_exp", "parity_bulk_exp", "parity_lattice_exp"]

# which self-checks belong to which property (upstream relaxation checks apply to all three)
CHECKS = {
    "lattice": ("lattice: fingerprint", "relaxation converged", "space group unchanged"),
    "bulk_modulus": ("bulk modulus: fingerprint", "relaxation converged", "space group unchanged",
                     "elastic tensor positive definite", "elastic fit symmetric", "Birch-Murnaghan fit clean",
                     "cubic: EOS B"),
    "thermal_expansion": ("thermal expansion: fingerprint", "relaxation converged", "space group unchanged",
                          "thermal:"),
}
KEEP = {
    "lattice": ["a", "b", "c", "a_exp", "b_exp", "c_exp", "a_dft", "c_dft", "V_atom", "V_atom_exp", "V_atom_dft",
                "err_lin_exp_pct", "err_lin_dft_pct", "err_a_exp_pct", "err_c_exp_pct", "spg_end", "excluded"],
    "bulk_modulus": ["K_for_exp", "B_exp", "exp_definition", "K_vrh", "K_reuss", "K_vrh_dft", "B_eos",
                     "err_exp_pct", "err_dft_pct", "excluded"],
    "thermal_expansion": ["T_low", "T_high", "alpha_V", "alpha_V_exp", "exp_note", "err_exp_pct", "alpha_V_300K",
                          "alpha_V_300K_exp", "err_300K_pct", "excluded", "excluded_300K"],
}


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return x if x not in ("", None) else None
    return None if v != v else round(v, 5)


def _csv(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def evidence() -> dict:
    s = json.loads((ROOT / "results" / "summary.json").read_text())
    exp = {}
    for p in sorted((ROOT / "data" / "experimental").glob("*.json")):
        for m in json.loads(p.read_text())["materials"]:
            exp[m["id"]] = m
    mats = []
    for m in s["materials"]:
        e = exp.get(m["id"], {})
        ref = {}
        for prop in ("lattice", "bulk_modulus", "thermal_expansion"):
            r = e.get(prop) or {}
            if r:
                ref[prop] = {k: r.get(k) for k in ("source", "citation", "quote", "method", "T_K", "value_GPa")
                             if r.get(k) is not None}
        mats.append({**{k: m[k] for k in ("id", "formula", "class", "class_label", "phase", "role", "mp_id")},
                     "ref": ref, "notes": e.get("notes")})
    pending = set(s.get("pending", {}).get("thermal_expansion", []))
    results: dict = {}
    for prop in ("lattice", "bulk_modulus", "thermal_expansion"):
        out = results.setdefault(prop, {})
        for r in s[prop]:
            if r["model"] not in MODELS:
                continue
            stale = bool(r.get("provenance")) or bool(r.get("pending")) or r["model"] in (pending if prop.startswith(
                "thermal") else ())
            rec = {"stale": True} if stale else {k: _num(r.get(k)) for k in KEEP[prop]}
            out.setdefault(r["material"], {})[r["model"]] = rec
    checks: dict = {}
    for c in s["checks"]:
        if c["model"] in MODELS:
            checks.setdefault(f"{c['model']}|{c['material']}", []).append([c["check"], bool(c["pass"])])
    classes = {}
    for t in s["trust_map"]:
        if t["model"] in MODELS and t["class"] != "all":
            classes[f"{t['property']}|{t['reference']}|{t['class']}|{t['model']}"] = {
                "MAPE": round(t["MAPE"], 2), "n": t["n"], "signed": round(t["mean_signed"], 2)}
    # six-case study: the benchmark's settings (grid, bench scan, Gamma modes excluded)
    study = {}
    phys = [r for r in _csv(ROOT / "results" / "thermal_failure" / "physics.csv") if r["variant"] == "grid"]
    conv = _csv(ROOT / "results" / "thermal_failure" / "convergence.csv")
    for r in phys:
        mk = STUDY_BACKEND.get(r["backend"])
        if not mk:
            continue
        spread = [float(c["alpha300"]) for c in conv if c["backend"] == r["backend"] and c["material"] == r["material"]
                  and c["variant"] == "grid" and c["imaginary"] == "clean" and c["alpha300"]]
        study[f"{mk}|{r['material']}"] = {
            **{k: _num(r[k]) for k in ("alpha300_qha", "exp_alpha_V", "gamma", "exp_gamma", "KT300_GPa", "exp_KT_GPa",
                                        "r_alpha", "r_gamma", "r_K", "r_Cv", "r_V", "gamma_TA_X", "gamma_TA_L",
                                        "gamma_O_Gamma")},
            "alpha300_scan_min": round(min(spread), 3) if spread else None,
            "alpha300_scan_max": round(max(spread), 3) if spread else None,
        }
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    return {
        "version": version, "date": RELEASE_DATE, "repo": REPO,
        "models": [{"key": k, "label": s["models"][k]["label"], "short": SHORT[k],
                    "via_kups": s["models"][k]["via_kups"]} for k in MODELS],
        "materials": mats, "results": results, "checks": checks, "classes": classes,
        "thresholds": s["thresholds"], "study": study,
        "study_materials": sorted({k.split("|")[1] for k in study}),
    }


def render(page: Path, layout: str, version: str) -> str:
    body = page.read_text()
    m = re.match(r"<!--\s*title:\s*(.*?)\s*\|\s*(.*?)\s*-->\n", body)
    title, desc = (m.group(1), m.group(2)) if m else ("BeyondStructure Bench", "")
    body = body[m.end():] if m else body
    current = ' aria-current="page"'
    nav = "".join(f'<a href="{href}"{current if href == page.name else ""}>{label}</a>' for href, label in NAV)
    return (layout.replace("{{title}}", title).replace("{{description}}", desc).replace("{{nav}}", nav)
            .replace("{{content}}", body).replace("{{version}}", version).replace("{{date}}", RELEASE_DATE)
            .replace("{{repo}}", REPO))


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    ev = evidence()
    (OUT / "data" / "evidence.json").write_text(json.dumps(ev, separators=(",", ":")))
    shutil.copytree(SRC / "assets", OUT / "assets")
    (OUT / "figures").mkdir()
    for f in FIGURES:
        shutil.copy(ROOT / "report" / "figures" / f"{f}.png", OUT / "figures" / f"{f}.png")
    layout = (SRC / "layout.html").read_text()
    for page in sorted((SRC / "pages").glob("*.html")):
        (OUT / page.name).write_text(render(page, layout, "v" + ev["version"]))
    (OUT / ".nojekyll").write_text("")
    n = sum(len(v) for v in ev["results"].values())
    print(f"wrote {OUT.relative_to(ROOT)}/: {len(list((SRC / 'pages').glob('*.html')))} pages, "
          f"evidence for {len(ev['materials'])} materials ({n} material-property groups)")


if __name__ == "__main__":
    main()
