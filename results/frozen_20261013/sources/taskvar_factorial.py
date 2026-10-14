"""Measure the two already-discovered s5 alleles separately and together; dry-run by default.

Four fixed genotypes, 512 shared fresh lives in base-fast and POOL, and no
selection. These measurement reversions never introduce a designed circuit.
The primary contrast in each world is AB - A - B + parent (epistasis).
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
from omegaconf import OmegaConf

from scripts.taskvar_confirm import COLS, atomic_json, atomic_npz, compare_rows, score_row, sha
from scripts.taskvar_gates import paired
from src.checkpoint import numerical_identity
from src.genome import Layout
from src.life import analysis, spec
from src.life.evaluate import LifeEvaluator

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "results/pool_mutants_20261013"
LABELS = ("parent", "A", "B", "AB")
SLOTS = (41, 124)  # W[1,16] reads m0; W[4,24] reads is_M. Zero-based ABI-3 flat indices.
N_LIVES, SEED_BLOCK, SOURCE_ROW = 512, 88, 38


def construct_genotypes(parent, winner) -> np.ndarray:
    """Copy the two discovered float32 alleles exactly; introduce no new allele value."""
    parent, winner = np.asarray(parent, dtype=np.float32), np.asarray(winner, dtype=np.float32)
    if parent.shape != (spec.V3.GENOME_SIZE,) or winner.shape != parent.shape:
        raise ValueError("need flat ABI-3 parent and winner genomes")
    if not np.isfinite(parent).all() or not np.isfinite(winner).all():
        raise ValueError("genomes must be finite")
    if tuple(np.flatnonzero(parent != winner)) != SLOTS:
        raise ValueError("archived winner must differ at exactly the two registered slots 41 and 124")
    genomes = np.repeat(parent[None], 4, axis=0)
    genomes[1, SLOTS[0]], genomes[2, SLOTS[1]] = winner[list(SLOTS)]
    genomes[3, list(SLOTS)] = winner[list(SLOTS)]
    if genomes[3].tobytes() != winner.tobytes():
        raise ValueError("combined genotype does not reconstruct the archived winner bitwise")
    return genomes


def factorial_seeds(used=()) -> list[int]:
    seeds = analysis.fresh_seeds(N_LIVES, seed0=51_000_000 + 10_000 * SEED_BLOCK)
    if set(seeds).intersection(used):
        raise ValueError("factorial seeds overlap the original screen or follow-up lives")
    return seeds


def load_factorial(archive: Path) -> tuple:
    """Bind both archived s5 selections to row 38 before constructing the two reversions."""
    provenance = json.loads((archive / "provenance.json").read_text())
    artifacts = {"provenance.json": sha(archive / "provenance.json")}

    def checked(relative):
        path = archive / relative
        digest = sha(path)
        if provenance["artifacts"][relative]["sha256"] != digest:
            raise ValueError(f"archive hash differs: {relative}")
        artifacts[relative] = digest
        return path

    parent_path = checked("parents/s5/best_genome.json")
    cfg_path = checked("parents/s5/config.yaml")
    layout, parent = Layout.load(str(parent_path))
    parent = parent.reshape(-1).float().numpy()
    if [layout.locate(slot) for slot in SLOTS] != [("W", [1, 16]), ("W", [4, 24])]:
        raise ValueError("genome layout does not match registered allele meanings")
    pool = np.load(checked("genomes/s5_pool.npy"), allow_pickle=False)
    if pool.ndim != 2 or pool.shape[0] <= SOURCE_ROW or pool.shape[1] != layout.size:
        raise ValueError("invalid archived mutation pool shape")
    identity, used, worlds, chosen = provenance["numerical_identity"], set(), {}, []
    for name in ("base", "pool"):
        prefix = f"screens/s5_{name}_T1024_b80"
        screen = json.loads(checked(f"{prefix}/manifest.json").read_text())
        followup = json.loads(checked(f"{prefix}/followup/manifest.json").read_text())
        selection = json.loads(checked(f"{prefix}/followup/selection.json").read_text())
        winner_layout, winner = Layout.load(str(checked(f"genomes/s5_{name}_winner.json")))
        winner = winner.reshape(-1).float().numpy()
        if layout.dims != winner_layout.dims or screen["world"] != name:
            raise ValueError("archived layout or world differs")
        if screen["numerical_identity"] != identity or followup["numerical_identity"] != identity:
            raise ValueError("archived numerical identities disagree")
        if followup["runner_sha256"] != sha(ROOT / "scripts/taskvar_confirm.py"):
            raise ValueError("confirmation helper differs from the measured archive")
        if followup["gates_sha256"] != sha(ROOT / "scripts/taskvar_gates.py"):
            raise ValueError("validation helper differs from the measured archive")
        if screen["runner_sha256"] != sha(ROOT / "scripts/taskvar_gradient.py"):
            raise ValueError("screen helper differs from the measured archive")
        if screen["parent_sha256"] != sha(parent_path) or screen["config_sha256"] != sha(cfg_path):
            raise ValueError("archived parent or configuration differs from original screen")
        if hashlib.sha256(pool.tobytes()).hexdigest() != screen["genomes_sha256"]:
            raise ValueError("mutation pool differs from original screen")
        if parent.tobytes() != pool[0].tobytes() or winner.tobytes() != pool[SOURCE_ROW].tobytes():
            raise ValueError("exported parent or winner differs from original genome rows")
        if selection["winner_genome_row"] != SOURCE_ROW or selection["winner_mutant_index"] != SOURCE_ROW - 1:
            raise ValueError("selected winner differs from registered row 38")
        if selection["winner_sha256"] != hashlib.sha256(winner.tobytes()).hexdigest():
            raise ValueError("winner differs from frozen selection digest")
        world = spec.world("catch_speck_l4", **screen["overrides"])
        expected = dict(T=1024, d0=0.5, d_min=0.25, t_open=0, t_fork=0, fork_flags=0)
        if name == "pool":
            expected.update(sigma=0.4, lam_s=4.0)
        if any(getattr(world, key) != value for key, value in expected.items()):
            raise ValueError("factorial requires original full-life base-fast and POOL worlds")
        worlds[name] = world
        used.update(screen["seeds"])
        for seeds in followup["seeds"].values():
            used.update(seeds)
        chosen.append(winner)
    if chosen[0].tobytes() != chosen[1].tobytes():
        raise ValueError("base and POOL selected different s5 genotypes")
    genomes = construct_genotypes(parent, chosen[0])
    return genomes, worlds, LifeEvaluator(OmegaConf.load(cfg_path), layout), identity, artifacts, used


def factorial_contrasts(values) -> dict[str, np.ndarray]:
    """Per-life contrasts retain covariance among all four genotypes before computing SE."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[0] != 4 or values.shape[1] < 2 or not np.isfinite(values).all():
        raise ValueError("need four finite paired genotype rows with at least two lives")
    parent, a, b, ab = values
    return {"A_minus_parent": a - parent, "B_minus_parent": b - parent,
            "AB_minus_A": ab - a, "AB_minus_B": ab - b, "AB_minus_parent": ab - parent,
            "epistasis": ab - a - b + parent}


def direction(estimate: dict) -> str:
    mean, se = estimate["mean"], estimate["se"]
    return "positive" if mean > 3 * se else "negative" if mean < -3 * se else "unresolved"


def world_report(rows: dict, world: spec.World) -> dict:
    window = world.T - world.t_open
    measures = {key: np.stack([rows[i][key] for i in range(4)])
                for key in ("F", "captures", "cost", "income", "live_time", "n_end", "n_H_end", "path")}
    measures.update(cost_rate=measures["cost"] / window, income_rate=measures["income"] / window)
    contrasts = {metric: {name: paired(values, np.zeros_like(values))
                          for name, values in factorial_contrasts(scores).items()}
                 for metric, scores in measures.items()}
    signs = {name: direction(value) for name, value in contrasts["F"].items()}
    return {"primary": {"name": "epistasis", **contrasts["F"]["epistasis"],
                        "direction_above_3se": signs["epistasis"]},
            "contrasts": contrasts,
            "genotype_means": {LABELS[i]: {key: analysis.summary(row[key]) for key in COLS}
                               for i, row in rows.items()},
            "vs_parent": {LABELS[i]: compare_rows(rows[i], rows[0], world) for i in (1, 2, 3)},
            "fitness_signs_above_3se": signs,
            "two_step_paths": {
                "A_then_B": {"first": signs["A_minus_parent"], "second": signs["AB_minus_A"]},
                "B_then_A": {"first": signs["B_minus_parent"], "second": signs["AB_minus_B"]}},
            "interpretation": "Signs describe the fitness effects of these two already-discovered alleles in "
                              "these backgrounds. Epistasis means nonadditive fitness, not a new algorithm. "
                              "Unresolved is not zero. Neither genotype is admitted to search by this measurement."}


def row_index(out: Path) -> dict:
    """Verify persistent byte hashes, including timing metadata, before using cached rows."""
    path = out / "row_index.json"
    index = json.loads(path.read_text()) if path.exists() else {}
    allowed = {f"{world}/row_{i:04d}.npz" for world in ("base", "pool") for i in range(4)}
    if not isinstance(index, dict) or set(index) - allowed:
        raise ValueError("invalid factorial row checkpoint index")
    for relative, digest in index.items():
        row = out / relative
        if not row.exists() or sha(row) != digest:
            raise ValueError(f"cached factorial row differs from its byte-hash checkpoint: {relative}")
    return index


def cached_cpu(out: Path, seeds) -> float:
    """Include every saved row, even one written just before an interrupted progress update."""
    row_index(out)
    total = 0.0
    for world in ("base", "pool"):
        for i in range(4):
            path = out / world / f"row_{i:04d}.npz"
            if path.exists():
                with np.load(path, allow_pickle=False) as saved:
                    seconds = float(saved["cpu_seconds"])
                    if int(saved["genome_index"]) != i or not np.array_equal(saved["seeds"], seeds):
                        raise ValueError("cached factorial row identity or seeds differ")
                    if not np.isfinite(seconds) or seconds < 0:
                        raise ValueError("invalid cached CPU accounting")
                    total += seconds
    return total


def run_factorial(archive: Path, out: Path, *, threads: int = 2, max_cpu_seconds: float = 1800) -> dict:
    if threads < 1 or not np.isfinite(max_cpu_seconds) or max_cpu_seconds <= 0:
        raise ValueError("threads and CPU budget must be positive")
    genomes, worlds, evaluator, old_identity, artifacts, used = load_factorial(archive)
    seeds = factorial_seeds(used)
    identity = numerical_identity()
    if identity != old_identity:
        raise ValueError("factorial numerical/source identity differs from measured archive")
    manifest = {
        "format": 1, "archive": str(archive.resolve()), "artifacts": artifacts,
        "numerical_identity": identity, "runner_sha256": sha(Path(__file__)),
        "helpers": {name: sha(ROOT / "scripts" / name) for name in
                    ("taskvar_confirm.py", "taskvar_gradient.py", "taskvar_gates.py")},
        "genotype_order": LABELS, "source_genome_row": SOURCE_ROW, "allele_slots": SLOTS,
        "genotype_sha256": {label: hashlib.sha256(genome.tobytes()).hexdigest()
                            for label, genome in zip(LABELS, genomes)},
        "worlds": {name: asdict(world) for name, world in worlds.items()},
        "seeds": seeds, "seed_block": SEED_BLOCK, "max_cpu_seconds": max_cpu_seconds,
        "primary": "AB - A - B + parent fitness interaction, separately in both worlds; descriptive 3-SE signs",
        "budget_enforcement": "Check before each new row; a row can cross the budget. "
                              "An external CPU monitor is required for a strict mid-row study cap.",
    }
    # JSON normalization makes tuple metadata compare identically on resume.
    manifest = json.loads(json.dumps(manifest))
    path = out / "manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("factorial inputs or sources changed; use a new output directory")
    if not path.exists() and out.exists() and any(out.rglob("*.npz")):
        raise ValueError("cached rows exist without a factorial manifest")
    out.mkdir(parents=True, exist_ok=True)
    atomic_json(path, manifest)
    atomic_npz(out / "genotypes.npz", genomes=genomes, labels=np.asarray(LABELS))
    report = {"report_only": True, "status": "incomplete", "seed_block": SEED_BLOCK, "seeds": seeds,
              "planned_genome_lives": 8 * len(seeds), "worlds": {}, "cpu_seconds": cached_cpu(out, seeds),
              "max_cpu_seconds": max_cpu_seconds}
    for name, world in worlds.items():
        rows = {}
        for i in range(4):
            row_path = out / name / f"row_{i:04d}.npz"
            if not row_path.exists() and report["cpu_seconds"] >= max_cpu_seconds:
                report["status"] = "budget_exhausted"
                atomic_json(out / "report.json", report)
                return report
            rows[i] = score_row(out / name, i, genomes, world, seeds, evaluator, threads)
            index = row_index(out)
            index[str(row_path.relative_to(out))] = sha(row_path)
            atomic_json(out / "row_index.json", index)
            report["cpu_seconds"] = cached_cpu(out, seeds)
            atomic_json(out / "progress.json", {"world": name, "completed_rows": list(rows),
                                                "cpu_seconds": report["cpu_seconds"]})
        atomic_npz(out / name / "scores.npz", seeds=np.asarray(seeds, dtype=np.uint64),
                   genome_indices=np.arange(4), **{key: np.stack([rows[i][key] for i in range(4)]) for key in COLS})
        report["worlds"][name] = world_report(rows, world)
        atomic_json(out / "report.json", report)
    report["status"] = "complete"
    atomic_json(out / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/autonomous_followthrough_20261013/factorial")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--max-cpu-seconds", type=float, default=1800)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.out.resolve().is_relative_to(ROOT / "outputs"):
        parser.error("study output must be inside repository outputs/")
    if args.threads < 1 or not np.isfinite(args.max_cpu_seconds) or args.max_cpu_seconds <= 0:
        parser.error("threads and CPU budget must be positive")
    if not args.run:
        genomes, _, _, _, _, used = load_factorial(args.archive)
        seeds = factorial_seeds(used)
        print(json.dumps({"status": "dry_run", "genotype_order": LABELS, "allele_slots": SLOTS,
                          "genome_lives": 8 * len(seeds), "seed_block": SEED_BLOCK,
                          "genotypes_sha256": hashlib.sha256(genomes.tobytes()).hexdigest(),
                          "max_cpu_seconds": args.max_cpu_seconds, "out": str(args.out)}, indent=2))
        return
    report = run_factorial(args.archive, args.out, threads=args.threads, max_cpu_seconds=args.max_cpu_seconds)
    print(json.dumps({key: report[key] for key in ("status", "planned_genome_lives", "cpu_seconds")}, indent=2))


if __name__ == "__main__":
    main()
