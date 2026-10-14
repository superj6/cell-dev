"""E7 prediction/discrimination measurements on the separate controller harness.

Uses the recovered controllers without adding organism behaviour. Default is
a dry run; --smoke runs two T=32 lives. A full measurement requires --run.
Replay leakage and harness parity audits must be completed separately before
any admission can pass. Never imports or executes interrupted study scripts.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path

from scripts.taskvar_gates import admission, validate_lives
from scripts.taskvar_gradient import atomic_json
from src.life import analysis

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "results/taskvar/measurement"


def harness_identity() -> dict:
    sources = list((ROOT / "results/open_headroom/harness").glob("*.c"))
    sources += list((ROOT / "results/open_headroom/harness").glob("*.h"))
    sources += [ROOT / "results/open_headroom/harness" / name for name in ("harness.py", "make_ckernel.py")]
    sources += [ROOT / "src/life" / name for name in ("kernel.c", "spec.py", "build.py")]
    sources += [Path(__file__), ROOT / "scripts/taskvar_replay.py", INPUTS / "replay_wrapper.c.in"]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}


def compile_measurement(library: Path, source: Path, fast: bool):
    """Disable the scratch-only blob epoch extension, preserving real ABI 3 keys."""
    sys.path.insert(0, str(ROOT / "results/open_headroom/harness"))
    harness = importlib.import_module("harness")
    compiler = importlib.import_module("make_ckernel")
    compiler.SRC = str(ROOT / "src/life/kernel.c")
    original = compiler.patched_source

    def patched(ctl_files=()):
        code = original(ctl_files)
        old = "  c->e_on = w[W_TAUR]; c->e_off = w[W_TAUE];"
        if code.count(old) != 1:
            raise ValueError("scratch epoch initialization changed; review the adapter")
        return code.replace(old, "  c->e_on = 0.0; c->e_off = 0.0; // E7 uses ABI 3 blob physics")

    compiler.patched_source = patched
    try:
        compiler.build(str(library), [str(source)], fast=fast)
    finally:
        compiler.patched_source = original
    return harness


def measurement(config_path: Path, out: Path, lives: int, duration: float, block: int, threads: int,
                audit_path: Path | None = None) -> dict:
    config = json.loads(config_path.read_text())
    if audit_path is not None:
        audit = json.loads(audit_path.read_text())
        if audit["config_sha256"] != hashlib.sha256(config_path.read_bytes()).hexdigest():
            raise ValueError("replay audit does not match this measurement config")
        if audit.get("harness_identity") != harness_identity():
            raise ValueError("harness, kernel or adapter changed since the replay/parity audit")
        config["replay_audit"] = audit
        config["world_parity_audit"] = audit["world_parity_audit"]
    source = config_path.parent / config["controller_source"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != config["source_sha256"]:
        raise ValueError("controller source changed; record its provenance in a new config")
    out.mkdir(parents=True, exist_ok=True)
    library = out / "measurement.so"
    harness = compile_measurement(library, source, fast=True)
    seeds = analysis.fresh_seeds(lives, seed0=51_000_000 + 10_000 * block)
    tune = sorted({seed for item in config["tuning_seed_ranges"]
                   for seed in analysis.fresh_seeds(item["n"], seed0=item["seed0"])})
    world = harness.WorldSpec(config["world"], over=dict(config["overrides"], T=duration))
    record = {"world": config["world"], "T": duration, "capability": config["capability"],
              "seeds": seeds, "tuning_seeds": tune, "reflex_footprint": config["reflex_footprint"],
              "world_overrides": config["overrides"], "scratch_slots": world.x,
              "engine": "scratch controller harness", "runs": {},
              "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
              "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
              "harness_identity": harness_identity(),
              "world_parity_audit": config.get("world_parity_audit")}
    fp = config["reflex_footprint"]
    knobs = config["reflex_knobs"]

    def save(name, result, **meta):
        validate_lives(result, harness.spec.world(world.preset, **world.over))
        record["runs"][name] = dict(meta, F=result["F"].tolist(),
                                     captures=result["captures"].tolist(), clicks=result["clicks"].tolist(),
                                     status=result["status"].tolist(), t_end=result["t_end"].tolist())
        atomic_json(out / "scores.json", record)

    for name, kind, shape, params in (
        ("frozen", "frozen_reflex", fp, None), ("retuned", "retuned_reflex", fp, knobs),
        ("smaller_frozen", "do_less", "hollow2", None),
        ("smaller_tuned" if config.get("smaller_reflex_knobs") else "smaller_transferred", "do_less", "hollow2",
         config.get("smaller_reflex_knobs") or knobs),
        ("quieter", "do_less", fp, dict(knobs, **{"K.t_ref": 8.0})),
    ):
        result = harness.tissue_run(harness.reflex(shape, params), world, seeds, threads=threads, lib=str(library))
        save(name, result, kind=kind, footprint=shape, knobs=params)
    params = config["params"]
    ablated = list(params)
    for index, value in config["ablate"].items():
        ablated[int(index)] = value
    for name, kind, values in (("full", "information", params), ("ablated", "ablation", ablated)):
        result = harness.ctl_run(config["controller_id"], values, harness.footprint(fp), world, seeds,
                                 threads=threads, lib=str(library), privileged=False)
        save(name, result, kind=kind, footprint=fp, params=values, privileged=False,
             source_sha256=config["source_sha256"], replay_audit=config.get("replay_audit"),
             ablation_of="full" if kind == "ablation" else None, mechanism=config["capability"],
             disabled_parameters=[int(index) for index in config["ablate"]],
             isolates_capability=config["ablation_isolates_capability"])
    report = admission(record)
    atomic_json(out / "admission.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capability", choices=("prediction", "discrimination"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--audit", type=Path, help="matching taskvar_replay audit.json")
    parser.add_argument("--lives", type=int, default=512)
    parser.add_argument("--duration", type=float, default=1024)
    parser.add_argument("--seed-block", type=int)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/taskvar_e7/measurement")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.seed_block is None:
        args.seed_block = 20 if args.capability == "prediction" else 30
    if args.smoke:
        args.lives, args.duration, args.seed_block = 2, 32, 1 if args.capability == "prediction" else 2
    if not 0 <= args.seed_block < 100 or not 2 <= args.lives <= 10_000:
        parser.error("need seed block 0..99 and lives 2..10000")
    if args.duration <= 0 or args.threads < 1:
        parser.error("duration and threads must be positive")
    if not args.out.resolve().is_relative_to(ROOT / "outputs"):
        parser.error("study output must be inside the repository outputs/ directory")
    out = args.out / f"{args.capability}_T{args.duration:g}_b{args.seed_block}"
    if not (args.smoke or args.run):
        print(json.dumps({"status": "dry_run", "lives": 7 * args.lives, "out": str(out),
                          "note": "Recheck leakage/world parity; report before full measurement."}, indent=2))
        return
    if (out / "scores.json").exists():
        parser.error("scores already exist; use a new output directory to preserve the measurement")
    result = measurement(args.config or INPUTS / f"{args.capability}.json", out, args.lives,
                         args.duration, args.seed_block, args.threads, args.audit)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
