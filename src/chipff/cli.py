"""Command line: `chipff <step>`.

  chipff fetch                      download MP structures + DFT references (needs MP_API_KEY)
  chipff static  [-m MODEL ...]     lattice constants, elastic tensor, EOS (CPU is fine)
  chipff qha     [-m MODEL ...]     thermal expansion, quasi-harmonic (CPU is fine; the published method)
  chipff thermal [-m MODEL ...]     thermal expansion from NPT MD (GPU; cross-check only, see docs/thermal_method.md)
  chipff plan                       print the thermal-expansion temperatures chosen by the rule
  chipff robustness --what static   rerun a subset with one setting changed (CPU, ~10 min per model)
  chipff robustness --what md       MD reruns: 2 extra seeds, bigger cell, half time step (GPU)
  chipff analyze                    merge raw results with references -> results/*.csv (+ bootstrap CIs)
  chipff report                     figures + report/index.html
  chipff all                        everything above, in order
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys

from chipff.materials import ROOT


def main(argv=None):
    ap = argparse.ArgumentParser(prog="chipff", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["fetch", "static", "thermal", "qha", "robustness", "plan", "analyze", "report", "all"])
    ap.add_argument("--what", choices=["static", "md"], help="robustness: which reruns")
    ap.add_argument("-m", "--models", nargs="*", help="model keys (default: all in configs/benchmark.yaml)")
    ap.add_argument("--materials", nargs="*", help="material ids (default: all)")
    ap.add_argument("--force", action="store_true", help="recompute even if cached")
    ap.add_argument("--max-prod-ps", type=float, help="cap MD production length (pilot runs)")
    ap.add_argument("--tag", default="thermal", help="name of the thermal result set (e.g. thermal_pilot)")
    ap.add_argument("--steps", nargs="*", default=["lattice", "elastic", "eos"],
                    help="static steps to run (lattice, elastic, eos)")
    ap.add_argument("--max-edges", type=int, help="memory budget per MD batch, in neighbour pairs (default from config)")
    ap.add_argument("--no-isolate", action="store_true", help="qha: run all materials in this process")
    ap.add_argument("--smoke", action="store_true", help="tiny thermal run that only tests the code path")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(name)s %(message)s")
    for noisy in ("httpx", "huggingface_hub", "absl", "jax"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from chipff.runner import config, run_static, run_thermal, select, thermal_plan

    models = a.models or config()["models"]
    if a.step in ("fetch", "all"):
        cmd = [sys.executable, str(ROOT / "scripts" / "fetch_mp.py")] + (["--force"] if a.force else [])
        if a.materials:
            cmd += ["--only", *a.materials]
        subprocess.run(cmd, check=True)
    if a.step == "plan":
        for mid, w in thermal_plan(select(a.materials)).items():
            print(f"{mid:12s} {'ok ' if w.ok else 'SKIP'} {w.temperatures}  ({w.reason})")
    if a.step in ("static", "all"):
        for m in models:
            run_static(m, a.materials, steps=tuple(a.steps), force=a.force)
    if a.step == "thermal":
        for m in models:
            run_thermal(m, a.materials, force=a.force, max_prod_ps=a.max_prod_ps, tag=a.tag, smoke=a.smoke,
                        max_edges=a.max_edges)
    if a.step in ("qha", "all"):
        from chipff.runner import run_thermal_qha, run_thermal_qha_isolated

        for m in models:
            if a.no_isolate:
                run_thermal_qha(m, a.materials, force=a.force)
            else:
                run_thermal_qha_isolated(m, a.materials, force=a.force)
    if a.step == "robustness":
        from chipff import robustness

        for m in models:
            if a.what == "static":
                robustness.save_static_sensitivity(robustness.static_sensitivity(m, a.materials))
            elif a.what == "md":
                robustness.md_variants(m, max_edges=a.max_edges)
            else:
                raise SystemExit("chipff robustness needs --what static or --what md")
    if a.step in ("analyze", "all", "report"):
        from chipff.analysis import build_tables

        build_tables()
    if a.step in ("report", "all"):
        from chipff.report import build_report

        build_report()


if __name__ == "__main__":
    main()
