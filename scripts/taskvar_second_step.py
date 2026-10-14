"""One fixed second mutation step and two counterfactual selectors; dry-run by default.

The default cohort is 32 copies of the already frozen s5 row-38 founder plus
224 ordinary point-mutated offspring in POOL at T=1024. Candidate rows share
28 lives, allowing production top-64/keep-32 selection with 3+4 or 12+16 lives.
Both chosen genotypes, the founder and original s5 are confirmed on fresh lives,
including negative results and parent wins. This is not a continuation run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")

import numpy as np
import torch
from omegaconf import OmegaConf

from scripts.taskvar_confirm import COLS, atomic_json, atomic_npz, compare_rows, score_row, sha
from scripts.taskvar_gates import paired
from scripts.taskvar_gradient import make_mutants
from src.checkpoint import numerical_identity
from src.evolve import TIE_SEED, Eval, rank_desc, recheck
from src.genome import Layout
from src.life import analysis, spec
from src.life.evaluate import LifeDraw, LifeEvaluator

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "results/pool_mutants_20261013"
RULES = {"low": (3, 4), "high": (12, 16)}
MUTATION_SEED = 51_086
TIE_GENERATOR_SEED = MUTATION_SEED + TIE_SEED
START_RAW_SHA256 = "6d79248a5bb82c49aa4278ccd755234b7952a09d9af4873b7a4ad303d3654f92"


def array_sha(value) -> str:
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def stage_seeds(screen_block: int, confirm_block: int, confirm_lives: int) -> dict[str, list[int]]:
    if not 0 <= screen_block < 100 or not 0 <= confirm_block < 100 or not 2 <= confirm_lives <= 10_000:
        raise ValueError("seed blocks must be 0..99 and confirmation needs 2..10000 lives")
    seeds = {"screen": analysis.fresh_seeds(28, seed0=51_000_000 + 10_000 * screen_block),
             "confirm": analysis.fresh_seeds(confirm_lives, seed0=51_000_000 + 10_000 * confirm_block)}
    if set(seeds["screen"]) & set(seeds["confirm"]):
        raise ValueError("screen and independent confirmation seeds overlap")
    return seeds


def cohort_rows(offspring: int, parent_copies: int) -> np.ndarray:
    if offspring < 1 or parent_copies < 1:
        raise ValueError("need at least one offspring and one parent copy")
    return np.concatenate((np.zeros(parent_copies, dtype=np.int64), np.arange(1, offspring + 1)))


def as_eval(scores) -> Eval:
    """Only fitness/trial_scores enter selection; other Eval fields are inert adapter values."""
    values = np.ascontiguousarray(scores, dtype=np.float64)
    zeros = torch.zeros(len(values), dtype=torch.float64)
    return Eval(torch.from_numpy(values.mean(axis=1)), zeros, zeros, zeros, zeros, zeros,
                torch.from_numpy(values))


class SavedScores:
    """Production recheck reads fixed recorded scores, never calls the life simulator."""

    def __init__(self, scores, seeds, world):
        self.scores = np.asarray(scores, dtype=np.float64)
        self.seeds = tuple(seeds)
        self.world = world
        self.seed_index = {seed: i for i, seed in enumerate(seeds)}

    def draw(self, purpose, generation, *, lives):
        if purpose != "gen" or generation != 0 or lives > len(self.seeds):
            raise ValueError("saved selection draw is outside the fixed cohort")
        return LifeDraw(self.seeds[:lives], tuple(self.world for _ in range(lives)))

    def __call__(self, entries, draw):
        indices = entries[:, 0].numpy().astype(np.int64)
        columns = [self.seed_index[seed] for seed in draw.seeds]
        return as_eval(self.scores[np.ix_(indices, columns)])


def select_rule(fitness, mapping, seeds, world, *, initial: int, extra: int, keep: int, shortlist: int,
                tie_seed: int) -> dict:
    """Match evolve_life's diagnostic ranking, then production recheck's two rankings."""
    fitness = np.asarray(fitness, dtype=np.float64)
    mapping = np.asarray(mapping, dtype=np.int64)
    if (fitness.ndim != 2 or fitness.shape[1] != len(seeds) or not np.isfinite(fitness).all()
            or mapping.ndim != 1 or np.any(mapping < 0) or np.any(mapping >= len(fitness))):
        raise ValueError("need finite candidate-by-life scores and valid cohort row indices")
    if not 1 <= keep <= shortlist <= len(mapping) or initial < 1 or extra < 1 or initial + extra > len(seeds):
        raise ValueError("invalid selector sizes or life partitions")
    expanded = fitness[mapping]
    evaluator = SavedScores(expanded, seeds, world)
    entries = torch.arange(len(mapping)).reshape(-1, 1)
    first = as_eval(expanded[:, :initial])
    generator = torch.Generator().manual_seed(tie_seed)
    before = array_sha(generator.get_state().numpy())
    # Production evolve_life consumes this permutation before calling recheck, even when recheck is enabled.
    onestage = rank_desc(first.fitness, generator)[:keep]
    selected = recheck(evaluator, entries, first, 0, keep, shortlist, extra, "all", generator)
    order = selected["order"].tolist()
    short = selected["shortlist"].tolist()
    winner_entry = order[0]
    winner = int(mapping[winner_entry])
    return {"initial_lives": initial, "recheck_lives": extra, "pooled_lives": initial + extra,
            "initial_seeds": list(seeds[:initial]), "recheck_seeds": list(seeds[initial:initial + extra]),
            "tie_seed": tie_seed, "tie_rng_start_sha256": before,
            "tie_rng_end_sha256": array_sha(generator.get_state().numpy()),
            "tie_draws": "rank_desc for one-stage diagnostic, initial shortlist, then pooled shortlist",
            "onestage_cohort_entries": onestage.tolist(), "shortlist_cohort_entries": short,
            "kept_cohort_entries": order, "kept_candidate_rows": mapping[order].tolist(),
            "winner_cohort_entry": winner_entry, "winner_candidate_row": winner,
            "winner_initial_rank_in_shortlist": short.index(winner_entry) + 1,
            "winner_all28_candidate_strict_rank": 1 + int(np.sum(fitness.mean(axis=1) > fitness[winner].mean())),
            "pooled_kept_fitness": selected["chosen"].fitness.tolist(),
            "parent_copy_entries_retained": int(np.count_nonzero(mapping[order] == 0)),
            "unique_candidate_rows_retained": len(set(mapping[order].tolist())),
            "recheck_changed_entries": selected["changed"],
            "logical_deployment_genome_lives": len(mapping) * initial + shortlist * extra}


def select_both(fitness, mapping, seeds, world, keep: int, shortlist: int, tie_seed: int) -> dict:
    return {name: select_rule(fitness, mapping, seeds, world, initial=initial, extra=extra, keep=keep,
                              shortlist=shortlist, tie_seed=tie_seed)
            for name, (initial, extra) in RULES.items()}


def confirmation_mapping(genomes, selected: dict, original_row: int) -> tuple[list[int], dict]:
    """Score identical genotype bytes once while preserving all four scheduled roles."""
    roles = {"original": original_row, "start": 0,
             **{name: result["winner_candidate_row"] for name, result in selected.items()}}
    seen, rows, mapped = {}, [], {}
    for role, candidate in roles.items():
        digest = array_sha(genomes[candidate])
        if digest not in seen:
            seen[digest] = candidate
            rows.append(candidate)
        mapped[role] = {"candidate_row": candidate, "scored_row": seen[digest], "raw_sha256": digest}
    return rows, mapped


def freeze(path: Path, value, label: str) -> None:
    if path.exists() and json.loads(path.read_text()) != value:
        raise ValueError(f"{label} changed; use a new study directory")
    atomic_json(path, value)


class RowStore:
    """Existing atomic production-scored rows plus persistent integrity and CPU accounting."""

    def __init__(self, out: Path, genomes, world, evaluator, threads, max_cpu_seconds):
        self.out, self.genomes, self.world, self.evaluator = out, genomes, world, evaluator
        self.threads, self.max_cpu_seconds = threads, max_cpu_seconds
        self.index_path = out / "row_index.json"
        self.index = json.loads(self.index_path.read_text()) if self.index_path.exists() else {}
        self.cpu_seconds = 0.0
        for relative, record in self.index.items():
            path = out / relative
            if not path.exists() or sha(path) != record["sha256"]:
                raise ValueError("cached row differs from its integrity checkpoint")
            cpu = record["cpu_seconds"]
            if not np.isfinite(cpu) or cpu < 0:
                raise ValueError("cached CPU accounting is invalid")
            self.cpu_seconds += cpu

    def row(self, stage: str, index: int, seeds):
        target = self.out / stage
        path = target / f"row_{index:04d}.npz"
        if not path.exists() and self.cpu_seconds >= self.max_cpu_seconds:
            raise RuntimeError("cpu_budget_stop")
        row = score_row(target, index, self.genomes, self.world, seeds, self.evaluator, self.threads)
        if any(not np.isfinite(float(row[key])) or float(row[key]) < 0
               for key in ("cpu_seconds", "wall_seconds")):
            raise ValueError("row contains invalid timing metadata")
        relative = str(path.relative_to(self.out))
        if relative not in self.index:
            self.cpu_seconds += float(row["cpu_seconds"])
            self.index[relative] = {"sha256": sha(path), "cpu_seconds": float(row["cpu_seconds"])}
            atomic_json(self.index_path, self.index)
        atomic_json(self.out / "progress.json", {"stage": stage, "candidate_row": index,
                                                 "completed_rows": len(self.index),
                                                 "cpu_seconds": self.cpu_seconds})
        return row

    def stage(self, name, indices, seeds):
        rows = {index: self.row(name, index, seeds) for index in indices}
        atomic_npz(self.out / name / "scores.npz", seeds=np.asarray(seeds, dtype=np.uint64),
                   genome_indices=np.asarray(indices),
                   **{key: np.stack([rows[index][key] for index in indices]) for key in COLS})
        return rows


def load_inputs(start: Path, original: Path, config: Path, offspring: int, mutation_seed: int):
    layout, founder = Layout.load(str(start))
    original_layout, ancestor = Layout.load(str(original))
    if layout.dims != original_layout.dims:
        raise ValueError("starting and original genomes use different layouts")
    founder = founder.reshape(-1).float().numpy()
    ancestor = ancestor.reshape(-1).float().numpy()
    if not np.isfinite(founder).all() or not np.isfinite(ancestor).all():
        raise ValueError("input genomes contain non-finite values")
    if start.resolve() == (ARCHIVE / "genomes/s5_pool_winner.json").resolve():
        if array_sha(founder) != START_RAW_SHA256:
            raise ValueError("default founder differs from the fixed s5 row-38 genotype")
    candidates, operations = make_mutants(start, offspring, mutation_seed)
    genomes = np.concatenate((candidates, ancestor[None]), axis=0)
    evaluator = LifeEvaluator(OmegaConf.load(config), layout)
    return layout, genomes, operations, evaluator


def run_study(start: Path, original: Path, config: Path, out: Path, *, offspring: int = 224,
              parent_copies: int = 32, shortlist: int = 64, keep: int = 32, duration: float = 1024,
              confirm_lives: int = 512, screen_block: int = 86, confirm_block: int = 87,
              mutation_seed: int = MUTATION_SEED, tie_seed: int = TIE_GENERATOR_SEED,
              threads: int = 2, max_cpu_seconds: float = 3600, stop_after: str = "confirm") -> dict:
    mapping = cohort_rows(offspring, parent_copies)
    if not 1 <= keep <= shortlist <= len(mapping) or threads < 1 or duration <= 0:
        raise ValueError("invalid selector dimensions, threads or duration")
    if not np.isfinite(max_cpu_seconds) or max_cpu_seconds <= 0 or stop_after not in ("screen", "confirm"):
        raise ValueError("need a positive CPU budget and a supported last stage")
    seeds = stage_seeds(screen_block, confirm_block, confirm_lives)
    identity = numerical_identity()
    layout, genomes, operations, evaluator = load_inputs(start, original, config, offspring, mutation_seed)
    world = spec.world("catch_speck_l4", T=duration, sigma=0.4, lam_s=4.0, d0=0.5, d_min=0.25)
    original_row = offspring + 1
    manifest = {"format": 1, "start": str(start.resolve()), "original": str(original.resolve()),
                "inputs": {"start_sha256": sha(start), "original_sha256": sha(original), "config_sha256": sha(config)},
                "start_raw_sha256": array_sha(genomes[0]), "original_raw_sha256": array_sha(genomes[original_row]),
                "genomes_sha256": array_sha(genomes), "candidate_rows": offspring + 1,
                "original_comparison_row": original_row, "cohort_mapping": mapping.tolist(),
                "mutation_seed": mutation_seed, "mutation": {"n_mut": 2, "p_cell": 0.5, "scale_n_mut": True,
                                                               "dup_rate": 0, "del_rate": 0},
                "rules": RULES, "tie_seed": tie_seed, "shortlist": shortlist, "keep": keep,
                "world": asdict(world), "seeds": seeds,
                "seed_blocks": {"screen": screen_block, "confirm": confirm_block},
                "numerical_identity": identity, "runner_sha256": sha(Path(__file__)),
                "helpers": {name: sha(ROOT / "scripts" / name) for name in
                            ("taskvar_confirm.py", "taskvar_gradient.py", "taskvar_gates.py")},
                "max_cpu_seconds": max_cpu_seconds,
                "budget_enforcement": "Check before each new row; external process monitor handles "
                                      "a strict mid-row cap."}
    # JSON normalizes tuple rules into lists before comparing a resumed manifest.
    manifest = json.loads(json.dumps(manifest))
    if not (out / "manifest.json").exists() and out.exists() and any(out.rglob("*.npz")):
        raise ValueError("cached rows exist without their study manifest")
    out.mkdir(parents=True, exist_ok=True)
    freeze(out / "manifest.json", manifest, "study inputs or numerical/source identity")
    if (out / "genomes.npy").exists():
        if array_sha(np.load(out / "genomes.npy", allow_pickle=False)) != manifest["genomes_sha256"]:
            raise ValueError("cached genomes differ from the manifest")
    else:
        np.save(out / "genomes.npy", genomes)
    freeze(out / "mutation_ops.json", operations, "recorded mutation operations")
    store = RowStore(out, genomes, world, evaluator, threads, max_cpu_seconds)
    report = {"report_only": True, "status": "incomplete", "world": "pool", "T": duration,
              "candidate_rows": offspring + 1, "cohort_entries": len(mapping), "seed_blocks": manifest["seed_blocks"],
              "planned_max_genome_lives": (offspring + 1) * 28 + 4 * confirm_lives}
    try:
        screen = store.stage("screen", list(range(offspring + 1)), seeds["screen"])
        fitness = np.stack([screen[index]["F"] for index in range(offspring + 1)])
        selected = select_both(fitness, mapping, seeds["screen"], world, keep, shortlist, tie_seed)
        confirmation_rows, roles = confirmation_mapping(genomes, selected, original_row)
        selection = {"rules": selected, "confirmation_rows": confirmation_rows, "roles": roles,
                     "screen_scores_sha256": sha(out / "screen/scores.npz"),
                     "interpretation": "Both rules use the same candidate pool. Each winner is the first kept "
                                       "genome by its rule's pooled score; parent wins and duplicate "
                                       "winners are retained."}
        freeze(out / "selection.json", selection, "frozen selector choices")
        for name in RULES:
            layout.save(torch.from_numpy(genomes[roles[name]["candidate_row"]]), out / f"{name}_selected_genome.json")
        report.update(selection=selection, last_completed_stage="screen", cpu_seconds=store.cpu_seconds)
        atomic_json(out / "report.json", report)
        if stop_after == "screen":
            return report
        confirmed = store.stage("confirm", confirmation_rows, seeds["confirm"])
        by_role = {role: confirmed[value["scored_row"]] for role, value in roles.items()}
        report["confirmation"] = {
            name: {"second_step_gain": compare_rows(by_role[name], by_role["start"], world),
                   "total_gain_vs_original": compare_rows(by_role[name], by_role["original"], world)}
            for name in RULES}
        report["starting_gain_vs_original"] = compare_rows(by_role["start"], by_role["original"], world)
        report["high_minus_low"] = paired(by_role["high"]["F"], by_role["low"]["F"])
        report["retention_overlap"] = {
            "cohort_entries": len(set(selected["low"]["kept_cohort_entries"])
                                  & set(selected["high"]["kept_cohort_entries"])),
            "candidate_rows": len(set(selected["low"]["kept_candidate_rows"])
                                  & set(selected["high"]["kept_candidate_rows"]))}
        report.update(status="complete", last_completed_stage="confirm", cpu_seconds=store.cpu_seconds,
                      actual_genome_lives=(offspring + 1) * 28 + len(confirmation_rows) * confirm_lives)
        report["limitations"] = [
            "This is one fixed mutation cohort around a previously selected founder at T=1024, not a continuation run.",
            "Transfer results do not choose this founder, change either selector, or gate the POOL world.",
            "All candidate rows were measured on 28 lives to compare both rules on the same pool. "
            "This does not establish matched-compute superiority or value per CPU-hour of either search budget.",
            "The rules reuse overlapping lives in different roles: low uses 3+4, high 12+16. "
            "Initial and recheck sets remain disjoint within each rule; final confirmation is independent.",
            "One comparison between selectors cannot establish average search efficiency or long-term accumulation.",
        ]
    except RuntimeError as error:
        if str(error) != "cpu_budget_stop":
            raise
        report.update(status="budget_stop", cpu_seconds=store.cpu_seconds)
    atomic_json(out / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=Path, default=ARCHIVE / "genomes/s5_pool_winner.json")
    parser.add_argument("--original", type=Path, default=ARCHIVE / "parents/s5/best_genome.json")
    parser.add_argument("--config", type=Path, default=ARCHIVE / "parents/s5/config.yaml")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/autonomous_followthrough_20261013/second_step")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--max-cpu-seconds", type=float, default=3600)
    parser.add_argument("--stop-after", choices=("screen", "confirm"), default="confirm")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if not args.out.resolve().is_relative_to(ROOT / "outputs"):
        parser.error("study output must be inside the repository outputs/ directory")
    if args.threads < 1 or not np.isfinite(args.max_cpu_seconds) or args.max_cpu_seconds <= 0:
        parser.error("threads and CPU budget must be positive")
    if not (args.run or args.smoke):
        _, founder = Layout.load(str(args.start))
        if array_sha(founder.reshape(-1).float().numpy()) != START_RAW_SHA256:
            parser.error("default study is fixed to s5 row38; use the Python API for a separately registered cohort")
        print(json.dumps({"status": "dry_run", "out": str(args.out), "candidate_rows": 225, "cohort_entries": 256,
                          "rules": RULES, "shortlist": 64, "keep": 32, "mutation_seed": MUTATION_SEED,
                          "tie_seed": TIE_GENERATOR_SEED, "screen_genome_lives": 6300,
                          "max_confirm_genome_lives": 2048, "max_genome_lives": 8348,
                          "note": "Fixed founder; transfer never changes this experiment."}, indent=2))
        return
    options = dict(threads=args.threads, max_cpu_seconds=args.max_cpu_seconds, stop_after=args.stop_after)
    if args.smoke:
        options.update(offspring=4, parent_copies=2, shortlist=4, keep=2, duration=32, confirm_lives=2,
                       screen_block=8, confirm_block=9)
    result = run_study(args.start, args.original, args.config, args.out, **options)
    print(json.dumps({key: result[key] for key in ("status", "candidate_rows", "cpu_seconds")}, indent=2))


if __name__ == "__main__":
    main()
