"""Fixed recovered C4 and reference-body duration measurements; no tuning or organism changes."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists())
STUDY = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "results/open_headroom/harness"))

import harness as H  # noqa: E402
import numpy as np  # noqa: E402

from scripts.taskvar_gates import paired  # noqa: E402
from scripts.taskvar_measure import compile_measurement, harness_identity  # noqa: E402
from src.life import build, spec  # noqa: E402

WORLD_NAMES = ("base", "pool")
DURATION_BLOCKS = {768: 40, 1536: 41}
LIVES, CAP, THREADS, VALIDATION_LIVES = 512, 3600, 2, 40
DEPENDENCY = "outputs/autonomous_s7_20261014"
ACTION = dict(latency="d0", charge="relay", t_ref_min=.5, privileged=False, quant=False, fast=True)
F_SOURCE_SHA = "453356a4ca121862d521eb0eec5507c9a3118893748ace169c5c81d02439e077"
C4_BASE = [.6, 2., .05, .1, 5., 2., 6., 50., 1., 0., 0., .5, .2, 7., 2., 1., 1., .5, .15, .3, 0.]
LIMITATIONS = [
    "Fixed recovered controller and references are transferred without retuning at new durations.",
    "This measures base/POOL duration payoff, not full G5 across capability worlds or a new admission decision.",
    "The central controller is an external measuring tool; computation is free and never enters an organism.",
    "Only three fixed do-less references are measured; this is not an exhaustive reference search.",
    "Best-whole-reference summaries reuse these lives and their paired SE is descriptive, not selection-adjusted.",
    "T768 and T1536 use distinct registered blocks; duration effects are not paired across durations.",
    "Scratch ledger columns21/22 retain historical dark/late-capture diagnostics rather than production meanings.",
    "Guards, capacity failures, mismatches or incomplete lives fail the entire candidate/study; no life is censored.",
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def freeze(path, value):
    path = Path(path)
    if path.exists():
        if read(path) != value:
            raise ValueError("frozen record differs: " + str(path))
    else:
        save(path, value)


def row_tools():
    path = STUDY / "sources/F_measure.py"
    if sha(path) != F_SOURCE_SHA:
        raise ValueError("reviewed F atomic row source differs")
    module_spec = importlib.util.spec_from_file_location("N_frozen_F_rows", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def candidates():
    historical = read(STUDY / "inputs/headline.json")
    result = {}
    for world in WORLD_NAMES:
        knobs = historical["reflex_knobs_verify"][world]["knobs"]
        params = list(C4_BASE)
        if world == "pool":
            params[:2] = [.4, 4.]
        if H.C4 != 5 or H.bayes_params(world).tolist() != params:
            raise ValueError("recovered default C4 changed")
        rows = [{"name": "full", "kind": "information", "footprint": "hollow3", "controller_id": 5,
                 "params": params, "action": ACTION}]
        for name, kind, shape, settings in (
            ("frozen", "frozen_reflex", "hollow3", None),
            ("retuned", "retuned_reflex", "hollow3", knobs),
            ("smaller_frozen", "do_less", "hollow2", None),
            ("smaller_transferred", "do_less", "hollow2", knobs),
            ("quieter", "do_less", "hollow3", dict(knobs, **{"K.t_ref": 8.})),
        ):
            body = H.reflex(shape, settings)
            rows.append({"name": name, "kind": kind, "footprint": shape, "knobs": settings,
                         "program_sha256": hashlib.sha256(np.asarray(body.program).tobytes()).hexdigest(),
                         "cells": [list(cell) for cell in body.cells]})
        result[world] = rows
    return result


def expected_protocol():
    source_pins = harness_identity()
    for path in sorted((ROOT / "src").rglob("*.py")):
        source_pins[str(path.relative_to(ROOT))] = sha(path)
    for name in ("taskvar_gates.py", "taskvar_gradient.py"):
        source_pins["scripts/" + name] = sha(ROOT / "scripts" / name)
    inputs = {str(p.relative_to(STUDY)): sha(p) for folder in ("inputs", "sources")
              for p in sorted((STUDY / folder).rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    worlds = {}
    for name in WORLD_NAMES:
        ws = H.world_spec(name)
        expected = {"d0": .5, "d_min": .25}
        if name == "pool":
            expected.update(sigma=.4, lam_s=4.)
        if ws.over != expected or ws.x or ws.draws or ws.preset != "catch_speck_l4":
            raise ValueError("headline base/POOL world differs")
        worlds[name] = {str(t): asdict(spec.world(ws.preset, **dict(ws.over, T=t))) for t in DURATION_BLOCKS}
    namespace = read(STUDY / "inputs/namespace_audit.json")
    if namespace["status"] != "passed":
        raise ValueError("seed namespace audit did not pass")
    seed_lists = {str(t): list(range(51_000_000 + block * 10_000, 51_000_000 + block * 10_000 + LIVES))
                  for t, block in DURATION_BLOCKS.items()}
    return {"format": 1, "question": "Does unchanged default C4 retain its information payoff at T768/T1536?",
            "candidate_lives": 12288, "validation_lives": VALIDATION_LIVES, "lives_per_candidate": LIVES,
            "simulation_workers": THREADS, "max_cpu_seconds": CAP, "durations": list(DURATION_BLOCKS),
            "duration_seed_blocks": {str(t): block for t, block in DURATION_BLOCKS.items()},
            "seeds": seed_lists, "worlds": worlds, "candidates": candidates(),
            "validation": {"T": 64, "seeds": list(range(51_099_000, 51_099_004)),
                           "closed_loop_indices": [0, 1], "control_indices": [2, 3],
                           "threads": 1, "candidate_lives": 40},
            "source_pins": source_pins, "input_sha256": inputs, "harness_identity": harness_identity(),
            "numerical_identity": row_tools().numerical_pins(),
            "wait_for_studies": [DEPENDENCY],
            "dependencies": {DEPENDENCY: {name: sha(ROOT / DEPENDENCY / name)
                                            for name in ("protocol.json", "run_budgeted.py")}},
            "primary": "C4 minus each fixed frozen/retuned reflex, separately in all four world-duration cells.",
            "do_less": "Report all three do-less contrasts and their whole-candidate maximum; never pick per life.",
            "descriptive_checks": "C4 gap versus best whole frozen/retuned reflex >3SE and >=1F; "
                                  "best do-less gain <one quarter of that gap. No admission action.",
            "limitations": LIMITATIONS}


def check_protocol():
    protocol = read(STUDY / "protocol.json")
    if protocol != expected_protocol():
        raise ValueError("prepared source, fixed candidate, world, dependency or numerical pin differs")
    return protocol


def check_ready():
    from run_budgeted import check_ready as check

    return check()


def condition_report(rows, world, tools):
    values = {name: build.Lives(row["ledger"], row["hashes"], abi=spec.V3) for name, row in rows.items()}
    reference = max(("frozen", "retuned"), key=lambda name: float(values[name]["F"].mean()))
    do_less = max(("smaller_frozen", "smaller_transferred", "quieter"),
                  key=lambda name: float(values[name]["F"].mean()))
    comparisons = {"full_minus_" + name: tools.comparison(rows["full"], rows[name], world)
                   for name in rows if name != "full"}
    smaller = {name: tools.comparison(rows[name], rows[reference], world)
               for name in ("smaller_frozen", "smaller_transferred", "quieter")}
    gap, cheap = comparisons["full_minus_" + reference]["F"], smaller[do_less]["F"]
    return {"fixed_comparisons": comparisons, "do_less_comparisons": smaller,
            "best_whole_reflex": reference, "best_whole_do_less": do_less,
            "candidate_means": {name: paired(row["F"], np.zeros(LIVES)) for name, row in values.items()},
            "descriptive_checks": {"gap_above_3se": gap["mean"] > 3 * gap["se"],
                                   "gap_at_least_1": gap["mean"] >= 1.,
                                   "do_less_below_quarter_gap": cheap["mean"] < .25 * gap["mean"]}}


def run_validation(protocol, folder):
    loader = importlib.util.spec_from_file_location("N_validation", STUDY / "validate.py")
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module.run_validation(protocol, folder)


def worker():
    protocol, ready = check_protocol(), check_ready()
    if os.environ.get("CELLDEV_INFO_DURATION_MONITOR_PID") != str(os.getppid()):
        raise ValueError("worker requires the registered parent CPU monitor")
    out = STUDY / "measurement"
    if out.exists():
        raise ValueError("measurement already exists; no automatic repeat")
    out.mkdir()
    tools = row_tools()
    validation = run_validation(protocol, out / "validation")
    if not validation["passed"] or validation["candidate_lives"] != VALIDATION_LIVES:
        raise ValueError("bounded controller/world validation failed")
    library = out / "research.so"
    compile_measurement(library, STUDY / "sources/vctl.c", fast=True)
    libraries = {str(p.relative_to(out)): sha(p) for p in out.rglob("*")
                 if p.is_file() and p.suffix in (".c", ".so")}
    manifest = {"protocol_sha256": sha(STUDY / "protocol.json"), "ready": ready, "libraries": libraries,
                "validation_sha256": sha(out / "validation/report.json"),
                "candidates": protocol["candidates"], "worlds": protocol["worlds"], "seeds": protocol["seeds"]}
    freeze(out / "manifest.json", manifest)
    report = {"status": "incomplete", "candidate_lives": 12288, "validation_lives": VALIDATION_LIVES,
              "conditions": {}, "limitations": LIMITATIONS}
    completed = []
    for duration in DURATION_BLOCKS:
        seeds = protocol["seeds"][str(duration)]
        for name in WORLD_NAMES:
            ws = H.world_spec(name).with_(T=duration)
            world = spec.world(ws.preset, **ws.over)
            rows = {}
            for candidate in protocol["candidates"][name]:
                if check_protocol() != protocol or check_ready() != ready:
                    raise ValueError("source/readiness changed during measurement")
                identity = {"manifest": manifest, "condition": [name, duration],
                            "candidate": candidate, "seeds": seeds}

                def evaluate(candidate=candidate, ws=ws, seeds=seeds):
                    if candidate["kind"] == "information":
                        return H.ctl_run(5, candidate["params"], H.footprint("hollow3"), ws, seeds,
                                         threads=THREADS, lib=str(library), **ACTION)
                    return H.tissue_run(H.reflex(candidate["footprint"], candidate["knobs"]), ws, seeds,
                                        threads=THREADS, fast=True, lib=str(library))

                label = f"{name}_T{duration}/{candidate['name']}"
                rows[candidate["name"]] = tools.checkpoint_row(out / "rows" / label, identity, world, evaluate)
                completed.append(label)
                save(out / "progress.json", {"status": "incomplete", "completed_rows": completed,
                                              "completed_candidate_lives": len(completed) * LIVES})
                print("Completed " + label + ": 512 lives", flush=True)
            report["conditions"][f"{name}_T{duration}"] = condition_report(rows, world, tools)
            save(out / "report.json", report)
    if check_protocol() != protocol or check_ready() != ready:
        raise ValueError("source/readiness changed before completion")
    report.update(status="complete", completed_candidate_lives=len(completed) * LIVES)
    save(out / "report.json", report)
    save(out / "progress.json", {"status": "complete", "completed_rows": completed,
                                  "completed_candidate_lives": len(completed) * LIVES})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.run:
        worker()
    else:
        protocol = check_protocol()
        print(json.dumps({"status": "dry_run", "candidate_lives": protocol["candidate_lives"],
                          "validation_lives": VALIDATION_LIVES, "simulated_lives": 0}))


if __name__ == "__main__":
    main()
