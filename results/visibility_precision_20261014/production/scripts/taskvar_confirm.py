"""Fresh paired confirmation and lateral lesions for a saved taskvar_gradient screen.

Dry-run by default. Select ceil(5% of mutants) by screen mean, re-score those
on disjoint lives, and freeze one winner before independent confirmation.
Lesion parent and winner on a third shared seed set, keeping t_open=0 in both
arms. These are descriptive measurements and never change selection or worlds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, replace
from pathlib import Path

# Match the screen and production search before importing torch indirectly.
os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")

import numpy as np
from omegaconf import OmegaConf

from scripts.taskvar_gates import paired, validate_lives
from scripts.taskvar_gradient import COLS as SCREEN_COLS
from scripts.taskvar_gradient import atomic_json
from src.checkpoint import numerical_identity
from src.genome import Layout
from src.life import analysis, build, spec
from src.life.evaluate import LifeDraw, LifeEvaluator

ROOT = Path(__file__).resolve().parents[1]
COLS = spec.V3.LEDGER + ("F_kernel", "extinct_charge", "window")
STAGES = ("rescore", "confirm", "lesion")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_top(fitness, fraction: float = 0.05) -> list[int]:
    """Return genome row indices (parent is row zero); exact ties use row order."""
    scores = np.asarray(fitness, dtype=float)
    if scores.ndim != 2 or min(scores.shape) < 2 or not np.isfinite(scores).all():
        raise ValueError("screen needs finite parent/mutant rows and at least two lives")
    if not 0 < fraction <= 1:
        raise ValueError("selection fraction must lie in (0, 1]")
    count = max(1, math.ceil(fraction * (len(scores) - 1)))
    return sorted(range(1, len(scores)), key=lambda i: (-float(scores[i].mean()), i))[:count]


def stage_seeds(screen_seeds, lives: dict, blocks: dict) -> dict:
    """Reject overlap explicitly, even when a caller supplied arbitrary screen seeds."""
    seen = set(screen_seeds)
    if len(seen) != len(screen_seeds):
        raise ValueError("screen seeds contain duplicates")
    result = {}
    for stage in STAGES:
        n, block = lives[stage], blocks[stage]
        if not 2 <= n <= 10_000 or not 0 <= block < 100:
            raise ValueError("each stage needs 2..10000 lives and a seed block in 0..99")
        seeds = analysis.fresh_seeds(n, seed0=51_000_000 + 10_000 * block)
        if seen.intersection(seeds):
            raise ValueError(f"{stage} seeds overlap a previous stage or the screen")
        seen.update(seeds)
        result[stage] = seeds
    return result


def load_screen(screen: Path, parent: Path) -> tuple[dict, np.ndarray, spec.World, LifeEvaluator, list[int]]:
    """Bind the complete saved screen to its parent, configuration, genomes and sources."""
    manifest = json.loads((screen / "manifest.json").read_text())
    expected = {"parent_sha256": sha(parent), "config_sha256": sha(parent.parent / "config.yaml"),
                "runner_sha256": sha(ROOT / "scripts/taskvar_gradient.py"),
                "kernel_source_sha256": sha(ROOT / "src/life/kernel.c")}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("screen parent, config, runner or kernel sources differ")
    genomes = np.load(screen / "genomes.npy", allow_pickle=False)
    if hashlib.sha256(genomes.tobytes()).hexdigest() != manifest["genomes_sha256"]:
        raise ValueError("screen genomes differ from their manifest")
    layout, ancestor = Layout.load(str(parent))
    if genomes.ndim != 2 or genomes.shape[0] != manifest["mutants"] + 1:
        raise ValueError("screen genome count differs from its manifest")
    if not np.array_equal(genomes[0], ancestor.reshape(-1).float().numpy()):
        raise ValueError("screen parent row differs from the original parent")
    if manifest["world"] not in ("base", "pool"):
        raise ValueError("only production ABI 3 base/POOL screens are supported")
    world = spec.world("catch_speck_l4", **manifest["overrides"])
    if world.t_open != 0 or world.t_fork != 0 or world.fork_flags:
        raise ValueError("screen must use full-life, unlesioned accounting")
    seeds = manifest["seeds"]
    with np.load(screen / "scores.npz", allow_pickle=False) as saved:
        if not np.array_equal(saved["seeds"], np.asarray(seeds, dtype=np.uint64)):
            raise ValueError("screen scores have different seed order")
        for key in SCREEN_COLS:
            values = saved[key]
            if values.shape != (len(genomes), len(seeds)) or not np.isfinite(values).all():
                raise ValueError(f"screen {key} has invalid shape or non-finite values")
        status = saved["status"].astype(np.int64)
        guards = spec.STATUS["guard_cells"] | spec.STATUS["guard_events"]
        if np.any(status & (spec.STATUS["capacity"] | spec.STATUS["ledger_mismatch"])):
            raise ValueError("screen contains a capacity failure or ledger mismatch")
        ended = status & (spec.STATUS["extinct"] | guards) != 0
        if np.any(~ended & (saved["t_end"] != world.t0 + world.T)):
            raise ValueError("screen contains an unexplained incomplete life")
        expected_f = saved["F_kernel"] - saved["extinct_charge"]
        if expected_f.tobytes() != saved["F"].tobytes():
            raise ValueError("screen fitness differs from production guard/extinction accounting")
        # A completed aggregate must agree with every incremental screen checkpoint.
        for i in range(len(genomes)):
            with np.load(screen / f"row_{i:04d}.npz", allow_pickle=False) as row:
                if any(saved[key][i].tobytes() != row[key].tobytes() for key in SCREEN_COLS):
                    raise ValueError("screen scores disagree with an incremental row")
        selected = select_top(saved["F"])
    evaluator = LifeEvaluator(OmegaConf.load(parent.parent / "config.yaml"), layout)
    return manifest, genomes, world, evaluator, selected


def atomic_npz(destination: Path, **values) -> None:
    tmp = destination.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **values)
    tmp.replace(destination)


def score_row(out: Path, index: int, genomes: np.ndarray, world: spec.World, seeds: list[int],
              evaluator: LifeEvaluator, threads: int) -> dict:
    """Each completed genome is atomic; resume validates raw and production-scored columns."""
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"row_{index:04d}.npz"
    draw = LifeDraw(tuple(seeds), tuple(world for _ in seeds))
    if not path.exists():
        wall_start, cpu_start = time.perf_counter(), time.process_time()
        result = build.run(world, seeds, genomes=spec.V3.pack_genomes(genomes[index:index + 1], world.lattice),
                           abi=spec.V3, fast=True, threads=threads)
        validate_lives(result, world, allow_guards=True)
        columns = evaluator.columns(result, 1, draw)
        atomic_npz(path, seeds=np.asarray(seeds, dtype=np.uint64), genome_index=np.asarray(index),
                   ledger=result.ledger, wall_seconds=np.asarray(time.perf_counter() - wall_start),
                   cpu_seconds=np.asarray(time.process_time() - cpu_start),
                   **{key: columns[key][0] for key in COLS})
        print(json.dumps({"stage": out.name, "completed_genome_row": index, "lives": len(seeds)}), flush=True)
    with np.load(path, allow_pickle=False) as saved:
        if int(saved["genome_index"]) != index or not np.array_equal(saved["seeds"], seeds):
            raise ValueError(f"{path}: row identity or seeds differ")
        ledger = saved["ledger"].copy()
        if ledger.shape != (len(seeds), spec.V3.LEDGER_SIZE):
            raise ValueError(f"{path}: invalid ledger shape")
        result = build.Lives(ledger, np.zeros((len(seeds), spec.V3.HASH_SIZE), dtype=np.uint64), abi=spec.V3)
        validate_lives(result, world, allow_guards=True)
        recomputed = evaluator.columns(result, 1, draw)
        if any(saved[key].tobytes() != recomputed[key][0].tobytes() for key in COLS):
            raise ValueError(f"{path}: saved columns disagree with production accounting")
        return {key: saved[key].copy() for key in (*COLS, "cpu_seconds", "wall_seconds")}


def compare_rows(winner: dict, parent: dict, world: spec.World) -> dict:
    """Keep paired fitness and the additive accounting pieces; counts alone are not causal evidence."""
    report = {key: paired(winner[key], parent[key])
              for key in ("F", "F_kernel", "n_end", "n_H_end", "live_time", "spikes", "packets",
                          "misses", "clicks", "captures", "path", "zone_samples", "samples")}
    window = world.T - world.t_open
    win_f, par_f = winner["F"], parent["F"]
    pieces = {
        "income": (winner["income"] - parent["income"]) / window,
        "cost_saving": (parent["cost"] - winner["cost"]) / window,
        "guard_charge_saving": (parent["guard_charge"] - winner["guard_charge"]) / window,
        "extinction_charge_saving": parent["extinct_charge"] - winner["extinct_charge"],
    }
    # Guards already pay the kernel's remaining-life charge; invalid implementation failures are rejected.
    pieces["accounting_residual"] = win_f - par_f - sum(pieces.values())
    report["fitness_contributions"] = {key: paired(value, np.zeros_like(value)) for key, value in pieces.items()}
    prices = {"living": ("live_time", world.c_live), "spiking": ("spikes", world.c_spike),
              "twitching": ("kappa_sum", world.c_tw), "messages": ("contact_events", world.c_msg),
              "division": ("claims", world.c_div), "secretion": ("sec_int", world.c_sec),
              "missed_clicks": ("misses", world.c_miss), "receptors": ("rec_gain", world.c_rec),
              "decoy_clicks": ("b2_clicks", spec.b2_cost(world))}
    report["cost_saving_components"] = {
        name: paired(price * parent[key] / window, price * winner[key] / window)
        for name, (key, price) in prices.items()}
    guards = spec.STATUS["guard_cells"] | spec.STATUS["guard_events"]
    report["guard_fraction"] = {name: float(np.mean(row["status"].astype(np.int64) & guards != 0))
                                for name, row in (("parent", parent), ("winner", winner))}
    return report


def lesion_report(normal: dict, lesioned: dict, winner: int, world: spec.World) -> dict:
    normal_gain = normal[winner]["F"] - normal[0]["F"]
    lesion_gain = lesioned[winner]["F"] - lesioned[0]["F"]
    return {"normal": compare_rows(normal[winner], normal[0], world),
            "lateral_off": compare_rows(lesioned[winner], lesioned[0], world),
            "gain_dependence": paired(normal_gain, lesion_gain),
            "parent_loss": paired(normal[0]["F"], lesioned[0]["F"]),
            "winner_loss": paired(normal[winner]["F"], lesioned[winner]["F"]),
            "interpretation": "Positive interaction means the mutant gain depends on lateral messages after the "
                              "fork. This broad lesion does not isolate a particular algorithm or prove new routing."}


def run_followup(screen: Path, parent: Path, out: Path, *, lives: dict, blocks: dict, threads: int = 2,
                 fork_time: float = 256, stop_after: str = "lesion") -> dict:
    manifest, genomes, world, evaluator, selected = load_screen(screen, parent)
    if threads < 1 or not 0 < fork_time < world.T or stop_after not in STAGES:
        raise ValueError("need positive threads, a fork strictly inside the life, and a valid final stage")
    seeds = stage_seeds(manifest["seeds"], lives, blocks)
    identity = numerical_identity()
    if identity != manifest["numerical_identity"]:
        raise ValueError("numerical/source identity differs from the screen; cannot confirm under changed rules")
    protocol = {"format": 1, "screen": str(screen.resolve()), "screen_manifest_sha256": sha(screen / "manifest.json"),
                "screen_scores_sha256": sha(screen / "scores.npz"), "numerical_identity": identity,
                "runner_sha256": sha(Path(__file__)), "gates_sha256": sha(ROOT / "scripts/taskvar_gates.py"),
                "world": asdict(world), "seeds": seeds, "seed_blocks": blocks, "selected_genome_rows": selected,
                "selection": "ceil(0.05 * mutants), descending screen mean, ascending genome row for exact ties",
                "winner_rule": "maximum rescore mean, ascending original genome row for exact ties",
                "lesion": {"t_fork": fork_time, "t_open": 0, "flag": "lateral_off"}}
    out.mkdir(parents=True, exist_ok=True)
    saved = out / "manifest.json"
    if saved.exists() and json.loads(saved.read_text()) != protocol:
        raise ValueError("follow-up inputs changed; use a new study directory")
    atomic_json(saved, protocol)
    timings = {}

    def stage(name, indices, these_seeds, this_world):
        rows = {}
        for i in indices:
            rows[i] = score_row(out / name, i, genomes, this_world, these_seeds, evaluator, threads)
            atomic_json(out / "progress.json", {"stage": name, "completed_rows": list(rows),
                                                "planned_rows": indices, "seeds": these_seeds})
        timings[name] = {key: sum(float(row[key]) for row in rows.values())
                         for key in ("cpu_seconds", "wall_seconds")}
        atomic_npz(out / name / "scores.npz", seeds=np.asarray(these_seeds, dtype=np.uint64),
                   genome_indices=np.asarray(indices),
                   **{key: np.stack([rows[i][key] for i in indices]) for key in COLS})
        return rows

    rescored = stage("rescore", [0, *selected], seeds["rescore"], world)
    winner = min(selected, key=lambda i: (-float(rescored[i]["F"].mean()), i))
    report = {"report_only": True, "screen": str(screen.resolve()), "world": manifest["world"], "T": world.T,
              "screened_mutants": len(genomes) - 1, "rescored_mutants": len(selected),
              "selected_genome_rows": selected, "winner_genome_row": winner, "winner_mutant_index": winner - 1,
              "seed_blocks": blocks, "seeds": seeds, "rescore": {
                  str(i): compare_rows(rescored[i], rescored[0], world) for i in selected},
              "timings": timings, "last_completed_stage": "rescore",
              "interpretation": "Selected candidates are not an unbiased distribution of fitness effects. "
                                "Confirmation and lesion are descriptive, never world admission gates."}
    selection = {"winner_genome_row": winner, "winner_mutant_index": winner - 1,
                 "winner_sha256": hashlib.sha256(genomes[winner].tobytes()).hexdigest(),
                 "rescore_seed_block": blocks["rescore"], "selected_genome_rows": selected}
    frozen_selection = out / "selection.json"
    if frozen_selection.exists() and json.loads(frozen_selection.read_text()) != selection:
        raise ValueError("frozen selection differs from the saved re-score rows")
    atomic_json(frozen_selection, selection)
    atomic_json(out / "report.json", report)
    if stop_after == "rescore":
        return report
    confirmed = stage("confirm", [0, winner], seeds["confirm"], world)
    report["confirmation"] = compare_rows(confirmed[winner], confirmed[0], world)
    contrast = report["confirmation"]["F"]
    report["confirmed_positive_2se"] = contrast["mean"] > 2 * contrast["se"]
    report["confirmed_positive_3se"] = contrast["mean"] > 3 * contrast["se"]
    report["practical_gain_at_least_0p5"] = contrast["mean"] >= 0.5
    report["last_completed_stage"] = "confirm"
    atomic_json(out / "report.json", report)
    if stop_after == "confirm":
        return report
    # Match t_fork and t_open in the control too, so only the lesion flag differs.
    control_world = replace(world, t_fork=fork_time, t_open=0, fork_flags=0)
    lesion_world = replace(control_world, fork_flags=spec.V3.flags("lateral_off"))
    normal = stage("lesion_normal", [0, winner], seeds["lesion"], control_world)
    lesioned = stage("lesion_lateral_off", [0, winner], seeds["lesion"], lesion_world)
    report["lesion"] = lesion_report(normal, lesioned, winner, world)
    report["last_completed_stage"] = "lesion"
    atomic_json(out / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--rescore-lives", type=int, default=512)
    parser.add_argument("--confirm-lives", type=int, default=512)
    parser.add_argument("--lesion-lives", type=int, default=512)
    parser.add_argument("--rescore-block", type=int, default=11)
    parser.add_argument("--confirm-block", type=int, default=12)
    parser.add_argument("--lesion-block", type=int, default=50)
    parser.add_argument("--fork-time", type=float, default=256)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--stop-after", choices=STAGES, default="lesion")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    out = args.out or args.screen / "followup"
    if not out.resolve().is_relative_to(ROOT / "outputs"):
        parser.error("study output must be inside the repository outputs/ directory")
    try:
        manifest, _, world, _, selected = load_screen(args.screen, args.parent)
        lives = {name: getattr(args, name + "_lives") for name in STAGES}
        blocks = {name: getattr(args, name + "_block") for name in STAGES}
        if args.smoke:
            lives = dict.fromkeys(STAGES, 2)
            blocks = dict(zip(STAGES, (6, 7, 8)))
            args.fork_time = min(args.fork_time, world.T / 2)
        stage_seeds(manifest["seeds"], lives, blocks)
        if args.threads < 1 or not 0 < args.fork_time < world.T:
            raise ValueError("need positive threads and a fork strictly inside the life")
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    if not (args.run or args.smoke):
        budget = {"rescore": (len(selected) + 1) * lives["rescore"], "confirm": 2 * lives["confirm"],
                  "lesion": 4 * lives["lesion"]}
        budget = {key: value for key, value in budget.items() if STAGES.index(key) <= STAGES.index(args.stop_after)}
        print(json.dumps({"status": "dry_run", "selected_genome_rows": selected, "genome_lives": budget,
                          "out": str(out), "seed_blocks": blocks, "fork_time": args.fork_time}, indent=2))
        return
    report = run_followup(args.screen, args.parent, out, lives=lives, blocks=blocks, threads=args.threads,
                          fork_time=args.fork_time, stop_after=args.stop_after)
    print(json.dumps({key: report[key] for key in ("world", "winner_genome_row", "last_completed_stage", "timings")},
                     indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
