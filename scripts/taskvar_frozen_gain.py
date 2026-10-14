"""Separate lateral dependence with ongoing development from dependence after freezing; dry-run by default."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, replace
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")

import numpy as np

from scripts.taskvar_confirm import COLS, atomic_json, atomic_npz, compare_rows, sha
from scripts.taskvar_factorial import ARCHIVE, load_factorial
from scripts.taskvar_gates import paired
from scripts.taskvar_second_step import RowStore, freeze
from src.checkpoint import numerical_identity
from src.life import analysis, spec

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = ("normal", "freeze", "lateral_off", "freeze+lateral_off")
BLOCK, LIVES = 92, 512


def contrasts(fitness: dict) -> dict:
    """Eight arms share life seeds; subtract first, then estimate uncertainty."""
    arrays = {key: np.asarray(fitness[key], dtype=float) for key in CONDITIONS}
    shape = arrays["normal"].shape
    if len(shape) != 2 or shape[0] != 2 or shape[1] < 2:
        raise ValueError("need parent/winner rows on at least two paired lives")
    if any(value.shape != shape or not np.isfinite(value).all() for value in arrays.values()):
        raise ValueError("all eight arms need finite scores on the same lives")
    gain = {key: value[1] - value[0] for key, value in arrays.items()}
    raw = {"unfrozen_gain": gain["normal"], "frozen_gain": gain["freeze"],
           "unfrozen_lateral_off_gain": gain["lateral_off"],
           "frozen_lateral_off_gain": gain["freeze+lateral_off"],
           "unfrozen_lateral_interaction": gain["normal"] - gain["lateral_off"],
           "frozen_lateral_interaction": gain["freeze"] - gain["freeze+lateral_off"],
           "gain_lost_under_freeze": gain["normal"] - gain["freeze"]}
    raw["interaction_change_under_freeze"] = (
        raw["unfrozen_lateral_interaction"] - raw["frozen_lateral_interaction"])
    for i, label in enumerate(("parent", "winner")):
        raw[f"{label}_frozen_lateral_loss"] = arrays["freeze"][i] - arrays["freeze+lateral_off"][i]
        raw[f"{label}_unfrozen_lateral_loss"] = arrays["normal"][i] - arrays["lateral_off"][i]
    return {key: paired(values, np.zeros_like(values)) for key, values in raw.items()}


def worlds(base):
    # Pending claims sent before the fork finish by 768.25; opening at 800 excludes this transition.
    return {key: replace(base, T=1536, t_fork=768, t_open=800,
                         fork_flags=0 if key == "normal" else spec.V3.flags(*key.split("+"))) for key in CONDITIONS}


def validate_frozen_pair(rows: dict) -> dict:
    """Check that neither frozen arm changes population during the measured interval."""
    counts = []
    for i in range(2):
        left, right = rows["freeze"][i], rows["freeze+lateral_off"][i]
        for row in (left, right):
            if (np.any(row["births"] != 0) or np.any(row["deaths"] != 0)
                    or np.any(row["last_birth"] >= 800)):
                raise ValueError("frozen tissue changed population during the measured interval")
        terminal = spec.STATUS["extinct"] | spec.STATUS["guard_cells"] | spec.STATUS["guard_events"]
        complete = ((left["status"].astype(np.int64) & terminal) == 0) & (
            (right["status"].astype(np.int64) & terminal) == 0)
        counts.append(int(complete.sum()))
        if not np.array_equal(left["n_end"][complete], right["n_end"][complete]):
            raise ValueError("frozen arms have different tissue sizes")
        for row in (left, right):
            if not np.allclose(row["live_time"][complete], 736 * row["n_end"][complete], rtol=1e-10, atol=1e-8):
                raise ValueError("frozen live-time differs from constant population during the measured interval")
    return {"paired_complete_lives_by_genotype": counts, "post_open_births_and_deaths": 0,
            "constant_population_window": [800, 1536],
            "guard_note": "Constant-population integration checked on complete guard-free pairs; all F retained."}


def run(out: Path, *, threads=2, max_cpu_seconds=3600):
    if threads < 1 or not np.isfinite(max_cpu_seconds) or max_cpu_seconds <= 0:
        raise ValueError("threads and CPU budget must be positive")
    all_genomes, original_worlds, evaluator, prior_identity, artifacts, used = load_factorial(ARCHIVE)
    genomes = all_genomes[[0, 3]]
    seeds = analysis.fresh_seeds(LIVES, seed0=51_000_000 + 10_000 * BLOCK)
    if set(seeds).intersection(used):
        raise ValueError("measurement seeds overlap discovery or earlier confirmation")
    identity = numerical_identity()
    if identity != prior_identity:
        raise ValueError("source/numerical identity differs from original discovery")
    settings = worlds(original_worlds["pool"])
    manifest = {"format": 1, "seeds": seeds, "seed_block": BLOCK, "labels": ["parent", "winner"],
                "genome_sha256": [hashlib.sha256(value.tobytes()).hexdigest() for value in genomes],
                "worlds": {key: asdict(world) for key, world in settings.items()},
                "numerical_identity": identity, "prior_artifacts": artifacts,
                "runner_sha256": sha(Path(__file__)), "helpers": {
                    name: sha(ROOT / "scripts" / name) for name in
                    ("taskvar_confirm.py", "taskvar_factorial.py", "taskvar_second_step.py",
                     "taskvar_gradient.py", "taskvar_gates.py")},
                "max_cpu_seconds": max_cpu_seconds, "planned_genome_lives": 8 * LIVES,
                "primary": "frozen_lateral_interaction: (winner-parent)freeze - (winner-parent)freeze+lateral_off",
                "budget_enforcement": "row-boundary checks plus required external CPU monitor"}
    manifest = json.loads(json.dumps(manifest))
    if not (out / "manifest.json").exists() and out.exists() and any(out.rglob("*.npz")):
        raise ValueError("cached rows exist without a manifest")
    out.mkdir(parents=True, exist_ok=True)
    freeze(out / "manifest.json", manifest, "frozen-gain study inputs")
    atomic_npz(out / "genotypes.npz", genomes=genomes)
    stores = {key: RowStore(out / key, genomes, world, evaluator, threads, max_cpu_seconds)
              for key, world in settings.items()}
    report = {"report_only": True, "status": "incomplete", "conditions": {}, "planned_genome_lives": 8 * LIVES}
    all_rows = {}
    for key, world in settings.items():
        rows = {}
        for i in range(2):
            consumed = sum(store.cpu_seconds for store in stores.values())
            if not (out / key / "rows" / f"row_{i:04d}.npz").exists() and consumed >= max_cpu_seconds:
                report.update(status="budget_stop", cpu_seconds=consumed)
                atomic_json(out / "report.json", report)
                return report
            rows[i] = stores[key].row("rows", i, seeds)
        if "freeze" in key and any(np.any(row["births"] != 0) or np.any(row["deaths"] != 0)
                                   for row in rows.values()):
            raise ValueError("frozen tissue changed population during the post-transition accounting window")
        all_rows[key] = rows
        atomic_npz(out / key / "scores.npz", seeds=np.asarray(seeds, dtype=np.uint64), genome_indices=np.arange(2),
                   **{column: np.stack([rows[i][column] for i in range(2)]) for column in COLS})
        report["conditions"][key] = {
            "winner_minus_parent": compare_rows(rows[1], rows[0], world),
            "post_open_births": [analysis.summary(rows[i]["births"]) for i in range(2)],
            "post_open_deaths": [analysis.summary(rows[i]["deaths"]) for i in range(2)],
            "mean_F": [analysis.summary(rows[i]["F"]) for i in range(2)]}
        report["cpu_seconds"] = sum(store.cpu_seconds for store in stores.values())
        atomic_json(out / "report.json", report)
    report["contrasts"] = contrasts({key: np.stack([rows[i]["F"] for i in range(2)])
                                      for key, rows in all_rows.items()})
    report["frozen_tissue_validation"] = validate_frozen_pair(all_rows)
    report.update(status="complete", limitations=[
        "The two genotypes have different frozen tissue states/footprints; this is not a matched-footprint test.",
        "Freeze suppresses further GRN/phenotype updates and new division/death decisions; it changes computation.",
        "Chemical transport and membrane dynamics continue. New lateral transmissions are suppressed by lateral_off.",
        "Pending pre-fork claims/spikes may resolve after768; accounting opens at800 and checks frozen births/deaths.",
        "A positive conditional interaction supports lateral dependence in frozen tissue, not a new algorithm.",
        "Loss of gain under freeze does not by itself distinguish developmental benefits from GRN computation."])
    atomic_json(out / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/autonomous_frozen_20261013")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--max-cpu-seconds", type=float, default=3600)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.out.resolve().is_relative_to(ROOT / "outputs"):
        parser.error("study output must be inside repository outputs/")
    if args.run:
        report = run(args.out, threads=args.threads, max_cpu_seconds=args.max_cpu_seconds)
        print(json.dumps({key: report[key] for key in ("status", "cpu_seconds")}))
    else:
        print(json.dumps({"status": "dry_run", "conditions": CONDITIONS, "genome_lives": 8 * LIVES,
                          "seed_block": BLOCK, "T": 1536, "fork": 768, "accounting_open": 800,
                          "max_cpu_seconds": args.max_cpu_seconds}))


if __name__ == "__main__":
    main()
