"""Fixed discrimination measurement with atomic full-ledger candidate checkpoints; no controller edits."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import torch

from scripts.taskvar_gates import admission, paired, validate_lives
from scripts.taskvar_measure import INPUTS, compile_measurement, harness_identity
from src.checkpoint import libm_identity
from src.life import analysis, build, spec

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
CONFIG = INPUTS / "discrimination.json"
AUDIT = ROOT / "results/taskvar/validation/discrimination_audit.json"
LIVES, BLOCK, DURATION, THREADS, CPU_CAP = 512, 30, 1024, 2, 1800
ACTION = dict(latency="d0", charge="relay", t_ref_min=0.5, privileged=False, quant=False, fast=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def freeze(path, value):
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError(f"frozen record changed: {path}")
    else:
        save(path, value)


def numerical_pins():
    """Read numerical dependencies without compiling a kernel or running golden lives."""
    compiler = Path(shutil.which("gcc")).resolve()
    return {"python": platform.python_version(), "numpy": np.__version__, "torch": str(torch.__version__),
            "machine": platform.machine(), "aten_cpu_capability": os.environ.get("ATEN_CPU_CAPABILITY"),
            "torch_cpu_capability": torch.backends.cpu.get_cpu_capability(), "libm": libm_identity(),
            "compiler": str(compiler), "compiler_sha256": sha(compiler),
            "compiler_flags": list(build.flags(True)),
            "note": "No simulation during pinning; exact generated scratch source/library pinned before scoring."}


def candidates(config):
    fp, knobs = config["reflex_footprint"], config["reflex_knobs"]
    result = [{"name": name, "kind": kind, "footprint": shape, "knobs": params}
              for name, kind, shape, params in (
                  ("frozen", "frozen_reflex", fp, None), ("retuned", "retuned_reflex", fp, knobs),
                  ("smaller_frozen", "do_less", "hollow2", None),
                  ("smaller_transferred", "do_less", "hollow2", knobs),
                  ("quieter", "do_less", fp, dict(knobs, **{"K.t_ref": 8.0})))]
    ablated = list(config["params"])
    for index, value in config["ablate"].items():
        ablated[int(index)] = value
    for name, kind, params in (("full", "information", config["params"]), ("ablated", "ablation", ablated)):
        result.append({"name": name, "kind": kind, "footprint": fp, "params": params,
                       "controller_id": config["controller_id"], "action": ACTION})
    return result


def expected_protocol():
    config, audit = json.loads(CONFIG.read_text()), json.loads(AUDIT.read_text())
    identity = harness_identity()
    if (sha(CONFIG) != audit["config_sha256"] or audit["harness_identity"] != identity
            or not audit["passed"] or not audit["world_parity_audit"]["passed"]
            or sha(INPUTS / config["controller_source"]) != config["source_sha256"]
            or audit["source_sha256"] != config["source_sha256"]):
        raise ValueError("existing controller replay/parity audit does not match current inputs")
    pins = {str(path.relative_to(ROOT)): sha(path) for path in
            (CONFIG, AUDIT, INPUTS / config["controller_source"], ROOT / "scripts/taskvar_gates.py",
             ROOT / "scripts/taskvar_gradient.py")}
    for path in sorted((ROOT / "src").rglob("*.py")):
        pins[str(path.relative_to(ROOT))] = sha(path)
    # Preserve the actual callback/action evidence, not only the passing JSON assertion.
    for variant in ("full", "ablated"):
        for i in range(2):
            path = ROOT / Path(audit["artifact"]).parent / f"{variant}_{i}_replay.npz"
            pins[str(path.relative_to(ROOT))] = sha(path)
            with np.load(path, allow_pickle=False) as logs:
                if any(logs[key].shape != logs["actions"].shape
                       or logs[key].tobytes() != logs["actions"].tobytes()
                       for key in ("same_life", "other_life", "other_world")):
                    raise ValueError("saved controller replay actions differ")
                if logs["control"].tobytes() == logs["actions"].tobytes():
                    raise ValueError("closed-loop replay control does not differ")
    seeds = analysis.fresh_seeds(LIVES, seed0=51_000_000 + 10_000 * BLOCK)
    tuning = sorted({s for item in config["tuning_seed_ranges"]
                     for s in analysis.fresh_seeds(item["n"], seed0=item["seed0"])})
    if set(seeds) & set(tuning):
        raise ValueError("measurement and tuning seeds overlap")
    world = spec.world("catch_speck_l4", **dict(config["overrides"], T=DURATION))
    if (world.d0, world.d_min, world.t_open, world.t_fork, world.fork_flags) != (1, 0.5, 0, 0, 0):
        raise ValueError("registered world constants changed")
    return {"format": 1, "question": "Does the existing decoy model pay at the reflex footprint?",
            "candidate_lives": 7 * LIVES, "candidates": candidates(config), "seeds": seeds, "seed_block": BLOCK,
            "tuning_seeds": tuning, "world": asdict(world), "threads": THREADS, "max_cpu_seconds": CPU_CAP,
            "source_pins": pins, "harness_identity": identity, "numerical_identity": numerical_pins(),
            "config_sha256": sha(CONFIG), "controller_sha256": config["source_sha256"],
            "audit_sha256": sha(AUDIT), "primary": ["full minus best whole reflex", "full minus ablated"],
            "fixed_reference_reports": ["full minus frozen", "full minus retuned"],
            "reference_uncertainty": "Best-reflex paired SE is conditional/descriptive, not selection-adjusted.",
            "failure_policy": "Reject guarded, capacity-failed, mismatched or incomplete candidate batches; "
                              "retain failed evidence and report the study incomplete, never censor individual lives.",
            "ablation": "Only parameter25 changes1 to0: broad decoy inference, steering avoidance and tap veto.",
            "hash_note": "Fast simulation hashes are zero; checkpoint byte hashes protect stored evidence."}


def check_protocol():
    expected = expected_protocol()
    if json.loads((STUDY / "protocol.json").read_text()) != expected:
        raise ValueError("prepared protocol/source/numerical identity changed")
    return expected


def check_ready():
    path = STUDY / "ready.json"
    if not path.exists():
        raise ValueError("not released: root must register F and create ready.json")
    ready = json.loads(path.read_text())
    for name in ("protocol.json", "measure.py", "run_budgeted.py"):
        if ready[name] != sha(STUDY / name):
            raise ValueError("readiness source or protocol pin changed")
    return ready


def library_harness():
    library, receipt = STUDY / "measurement.so", STUDY / "library.json"
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if any(sha(STUDY / name) != digest for name, digest in saved.items()):
            raise ValueError("compiled library/source differs from its receipt")
        sys.path.insert(0, str(ROOT / "results/open_headroom/harness"))
        harness = importlib.import_module("harness")
    else:
        if library.exists() or any((STUDY / "rows").glob("*/checkpoint.json")):
            raise ValueError("library or cached rows exist without a library receipt")
        config = json.loads(CONFIG.read_text())
        harness = compile_measurement(library, INPUTS / config["controller_source"], fast=True)
        freeze(receipt, {name: sha(STUDY / name) for name in ("measurement.so", "measurement.c")})
    return harness, library


def validate_arrays(arrays, row_identity, world):
    if str(arrays["identity"].item()) != canonical(row_identity):
        raise ValueError("candidate checkpoint identity differs")
    n = len(row_identity["seeds"])
    if (arrays["ledger"].dtype != np.float64 or arrays["ledger"].shape != (n, spec.V3.LEDGER_SIZE)
            or arrays["hashes"].dtype != np.uint64 or arrays["hashes"].shape != (n, spec.V3.HASH_SIZE)):
        raise ValueError("invalid candidate ledger/hash dimensions or dtype")
    controller = row_identity["candidate"]["kind"] in ("information", "ablation")
    if arrays["diag"].shape != (n, 16 if controller else 0) or not np.isfinite(arrays["diag"]).all():
        raise ValueError("invalid controller diagnostics")
    if controller and (arrays["latency"].shape != (n,) or not np.all(arrays["latency"] == world.d0)):
        raise ValueError("controller latency differs from registered one-hop action delay")
    if any(not np.isfinite(float(arrays[key])) or float(arrays[key]) < 0 for key in ("cpu_seconds", "wall_seconds")):
        raise ValueError("invalid candidate timing")
    result = build.Lives(arrays["ledger"], arrays["hashes"], abi=spec.V3)
    validate_lives(result, world)
    cost = spec.V3.column_cost(result.ledger, world)
    if not np.allclose(result["cost"], cost, rtol=1e-9, atol=1e-9):
        raise ValueError("saved cost differs from full-ledger accounting")
    if not np.array_equal(result["F"], spec.V3.fitness(result.ledger, world)):
        raise ValueError("saved fitness differs from full-ledger accounting")
    return result


def load_row(directory, row_identity, world):
    receipt = json.loads((directory / "checkpoint.json").read_text())
    path = directory / "row.npz"
    if receipt != {"identity": row_identity, "row_sha256": sha(path)}:
        raise ValueError("candidate checkpoint bytes or identity differ")
    with np.load(path, allow_pickle=False) as values:
        arrays = {key: values[key].copy() for key in values.files}
    validate_arrays(arrays, row_identity, world)
    return arrays


def checkpoint_row(directory, identity, world, evaluate):
    if directory.exists():
        return load_row(directory, identity, world)
    pending = directory.with_name(directory.name + ".pending")
    if pending.exists():
        if (pending / "failure.json").exists():
            raise ValueError("candidate previously failed validation; study remains incomplete")
        # An interrupted candidate is uncommitted and may be repeated within the original cumulative CPU cap.
        shutil.rmtree(pending)
    pending.mkdir(parents=True)
    cpu, wall = time.process_time(), time.monotonic()
    result = evaluate()
    arrays = {"identity": np.asarray(canonical(identity)), "ledger": result.ledger, "hashes": result.hashes,
              "diag": getattr(result, "diag", np.empty((len(identity["seeds"]), 0))),
              "latency": getattr(result, "latency", np.empty(0)),
              "cpu_seconds": np.asarray(time.process_time() - cpu),
              "wall_seconds": np.asarray(time.monotonic() - wall)}
    path = pending / "row.npz"
    with path.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        validate_arrays(arrays, identity, world)
    except ValueError as error:
        save(pending / "failure.json", {"status": "invalid_candidate", "reason": str(error),
                                      "identity": identity, "row_sha256": sha(path),
                                      "policy": "Entire study remains incomplete; no life is censored or replaced."})
        raise
    save(pending / "checkpoint.json", {"identity": identity, "row_sha256": sha(path)})
    pending.rename(directory)
    descriptor = os.open(directory.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return load_row(directory, identity, world)


def comparison(a, b, world):
    left, right = (build.Lives(row["ledger"], row["hashes"], abi=spec.V3) for row in (a, b))
    report = {key: paired(left[key], right[key]) for key in
              ("F", "captures", "clicks", "b2_clicks", "misses", "spikes", "path", "zone_samples", "samples")}
    window = world.T - world.t_open
    pieces = {"capture_income": world.R_cap * (left["captures"] - right["captures"]) / window,
              "poison_cost_saving": spec.b2_cost(world) * (right["b2_clicks"] - left["b2_clicks"]) / window,
              "miss_cost_saving": world.c_miss * (right["misses"] - left["misses"]) / window}
    total_saving = (spec.V3.column_cost(right.ledger, world) - spec.V3.column_cost(left.ledger, world)) / window
    pieces["other_cost_saving"] = total_saving - pieces["poison_cost_saving"] - pieces["miss_cost_saving"]
    residual = left["F"] - right["F"] - sum(pieces.values())
    if not np.allclose(residual, 0, rtol=0, atol=1e-10):
        raise ValueError("fitness decomposition residual exceeds tolerance")
    report["fitness_pieces"] = {key: paired(value, np.zeros_like(value)) for key, value in pieces.items()}
    return report


def final_report(record, rows, world):
    """Best-reflex admission plus both fixed references, without changing any selection rule."""
    gate = admission(record)
    return {"status": "complete", "admission": gate, "candidate_lives": 7 * LIVES,
            "full_vs_reflex": comparison(rows["full"], rows[gate["best_reflex"]], world),
            "full_vs_frozen_reflex": comparison(rows["full"], rows["frozen"], world),
            "full_vs_retuned_reflex": comparison(rows["full"], rows["retuned"], world),
            "full_vs_ablated": comparison(rows["full"], rows["ablated"], world),
            "limitations": ["Broad decoy-model ablation; no particular local algorithm is established.",
                            "Best reflex is selected on these same fresh lives; its SE is conditional/descriptive, "
                            "not selection-adjusted. Both fixed-reflex comparisons are also reported.",
                            "Parameters transferred from ring5; only three do-less candidates were tested.",
                            "Controller computation is free; footprint, sensing, virtual relay and actions pay.",
                            "This evidence never admits a world to selection automatically.",
                            "Replay/parity evidence is bounded to the registered T64 validation lives."]}


def worker():
    protocol, ready = check_protocol(), check_ready()
    if os.environ.get("CELLDEV_DISCRIM_MONITOR_PID") != str(os.getppid()):
        raise ValueError("scientific worker requires the registered external CPU monitor")
    config, audit = json.loads(CONFIG.read_text()), json.loads(AUDIT.read_text())
    harness, library = library_harness()
    world = spec.world("catch_speck_l4", **dict(config["overrides"], T=DURATION))
    ws = harness.WorldSpec("discrimination", over=dict(config["overrides"], T=DURATION))
    manifest = {"protocol_sha256": sha(STUDY / "protocol.json"), "ready": ready,
                "library": json.loads((STUDY / "library.json").read_text())}
    freeze(STUDY / "manifest.json", manifest)
    record = {"world": "discrimination", "T": DURATION, "capability": "discrimination",
              "seeds": protocol["seeds"], "tuning_seeds": protocol["tuning_seeds"],
              "reflex_footprint": config["reflex_footprint"], "world_overrides": config["overrides"],
              "scratch_slots": {}, "engine": "scratch controller harness", "runs": {},
              "config_sha256": sha(CONFIG), "library_sha256": sha(library),
              "harness_identity": protocol["harness_identity"], "world_parity_audit": audit["world_parity_audit"]}
    rows = {}
    for candidate in protocol["candidates"]:
        # Recheck source/input pins between candidates, and validate every completed row before reuse.
        if check_protocol() != protocol or check_ready() != ready:
            raise ValueError("study changed while running")
        identity = {"manifest": manifest, "candidate": candidate, "seeds": protocol["seeds"]}

        def evaluate(candidate=candidate):
            if "params" in candidate:
                return harness.ctl_run(candidate["controller_id"], candidate["params"],
                                       harness.footprint(candidate["footprint"]), ws, protocol["seeds"],
                                       threads=THREADS, lib=str(library), **ACTION)
            body = harness.reflex(candidate["footprint"], candidate["knobs"])
            return harness.tissue_run(body, ws, protocol["seeds"], threads=THREADS, lib=str(library), fast=True)

        name = candidate["name"]
        rows[name] = checkpoint_row(STUDY / "rows" / name, identity, world, evaluate)
        result = build.Lives(rows[name]["ledger"], rows[name]["hashes"], abi=spec.V3)
        metadata = {key: value for key, value in candidate.items() if key != "name"}
        if "params" in candidate:
            metadata.update(privileged=False, source_sha256=config["source_sha256"], replay_audit=audit,
                            ablation_of="full" if name == "ablated" else None, mechanism="discrimination",
                            disabled_parameters=[25], isolates_capability=config["ablation_isolates_capability"])
        record["runs"][name] = dict(metadata, **{key: result[key].tolist() for key in
                                                 ("F", "captures", "clicks", "status", "t_end")})
        save(STUDY / "scores.json", record)
        save(STUDY / "progress.json", {"status": "incomplete", "completed_candidates": list(rows),
                                      "candidate_cpu_seconds": sum(float(row["cpu_seconds"]) for row in rows.values())})
        print(f"Completed candidate {name}: {LIVES} lives", flush=True)
    report = final_report(record, rows, world)
    save(STUDY / "admission.json", report["admission"])
    save(STUDY / "report.json", report)
    save(STUDY / "progress.json", {"status": "complete", "completed_candidates": list(rows)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.prepare:
        freeze(STUDY / "protocol.json", expected_protocol())
        print("Prepared protocol without simulation or compilation.")
    elif args.worker:
        try:
            worker()
        except ValueError as error:
            progress = STUDY / "progress.json"
            done = json.loads(progress.read_text()).get("completed_candidates", []) if progress.exists() else []
            save(STUDY / "report.json", {"status": "incomplete", "reason": str(error),
                                       "completed_candidates": done, "planned_candidate_lives": 7 * LIVES,
                                       "policy": "No selective censoring, replacement or positive-only reporting."})
            raise
    else:
        protocol = check_protocol()
        print(json.dumps({"status": "dry_run", "candidate_lives": protocol["candidate_lives"],
                          "threads": THREADS, "max_cpu_seconds": CPU_CAP,
                          "run": "Use run_budgeted.py --run after root creates ready.json."}))


if __name__ == "__main__":
    main()
