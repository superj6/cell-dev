"""Fixed-genotype duration and conduction transfer; dry-run unless --run is given.

Every archived parent/winner pair is measured on the same 256 block-85 seeds.
Fast-conduction durations are 768, 1024 and 1536; old conduction is measured at
1024. This never chooses another genome from transfer results.
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
CASES = (("s5_base", 5, "base", 38), ("s5_pool", 5, "pool", 38),
         ("s7_base", 7, "base", 15), ("s7_pool", 7, "pool", 29))
DURATIONS = (768, 1024, 1536)
N_LIVES = 256
SEED_BLOCK = 85


def transfer_seeds(used=()) -> list[int]:
    seeds = analysis.fresh_seeds(N_LIVES, seed0=51_000_000 + 10_000 * SEED_BLOCK)
    if set(seeds).intersection(used):
        raise ValueError("transfer lives overlap archived screening or follow-up lives")
    return seeds


def condition_worlds(name: str) -> dict[str, spec.World]:
    if name not in ("base", "pool"):
        raise ValueError("transfer world must be base or pool")
    common = {"t_open": 0.0, "sigma": 0.4, "lam_s": 4.0} if name == "pool" else {"t_open": 0.0}
    worlds = {f"fast_T{duration}": spec.world("catch_speck_l4", T=duration, d0=0.5, d_min=0.25, **common)
              for duration in DURATIONS}
    worlds["old_T1024"] = spec.world("catch_speck_l4", T=1024, d0=1.0, d_min=0.5, **common)
    return worlds


def load_cases(archive: Path) -> tuple[list[dict], dict, dict, set]:
    """Verify the four frozen winners against the public archive before using any scores."""
    provenance = json.loads((archive / "provenance.json").read_text())
    artifact_hashes = {"provenance.json": sha(archive / "provenance.json")}

    def checked(relative):
        path = archive / relative
        digest = sha(path)
        if provenance["artifacts"][relative]["sha256"] != digest:
            raise ValueError(f"archive hash differs: {relative}")
        artifact_hashes[relative] = digest
        return path

    used, cases = set(), []
    identity = provenance["numerical_identity"]
    for name, body, world_name, source_row in CASES:
        screen = f"screens/{name}_T1024_b80"
        manifest = json.loads(checked(f"{screen}/manifest.json").read_text())
        followup = json.loads(checked(f"{screen}/followup/manifest.json").read_text())
        selected = json.loads(checked(f"{screen}/followup/selection.json").read_text())
        parent_path = checked(f"parents/s{body}/best_genome.json")
        cfg_path = checked(f"parents/s{body}/config.yaml")
        winner_path = checked(f"genomes/{name}_winner.json")
        pool_path = checked(f"genomes/s{body}_pool.npy")
        if manifest["numerical_identity"] != identity or followup["numerical_identity"] != identity:
            raise ValueError(f"{name}: inconsistent archived numerical identities")
        if manifest["parent_sha256"] != sha(parent_path) or manifest["config_sha256"] != sha(cfg_path):
            raise ValueError(f"{name}: parent or configuration differs from the original screen")
        if selected["winner_genome_row"] != source_row or selected["winner_mutant_index"] != source_row - 1:
            raise ValueError(f"{name}: winner differs from the fixed transfer cohort")
        if followup["runner_sha256"] != sha(ROOT / "scripts/taskvar_confirm.py"):
            raise ValueError("confirmation helper differs from the measured archive")
        if followup["gates_sha256"] != sha(ROOT / "scripts/taskvar_gates.py"):
            raise ValueError("validation helper differs from the measured archive")
        if manifest["runner_sha256"] != sha(ROOT / "scripts/taskvar_gradient.py"):
            raise ValueError("screen source differs from the measured archive")
        pool = np.load(pool_path, allow_pickle=False)
        if hashlib.sha256(pool.tobytes()).hexdigest() != manifest["genomes_sha256"]:
            raise ValueError(f"{name}: archived mutation pool differs from screen")
        parent_layout, parent = Layout.load(str(parent_path))
        winner_layout, winner = Layout.load(str(winner_path))
        genomes = np.stack((parent.reshape(-1).float().numpy(), winner.reshape(-1).float().numpy()))
        if parent_layout.size != winner_layout.size or not np.isfinite(genomes).all():
            raise ValueError(f"{name}: invalid parent/winner genome layout or values")
        if pool.ndim != 2 or pool.shape[0] <= source_row or pool.shape[1] != genomes.shape[1]:
            raise ValueError(f"{name}: invalid archived mutation pool shape")
        if genomes[0].tobytes() != pool[0].tobytes() or genomes[1].tobytes() != pool[source_row].tobytes():
            raise ValueError(f"{name}: exported parent/winner differs from original mutation pool")
        winner_sha = hashlib.sha256(genomes[1].tobytes()).hexdigest()
        if winner_sha != selected["winner_sha256"]:
            raise ValueError(f"{name}: winner differs from frozen genotype hash")
        used.update(manifest["seeds"])
        for seeds in followup["seeds"].values():
            used.update(seeds)
        cases.append({"name": name, "world": world_name, "source_row": source_row, "genomes": genomes,
                      "evaluator": LifeEvaluator(OmegaConf.load(cfg_path), parent_layout),
                      "winner_sha256": winner_sha,
                      "parent_sha256": hashlib.sha256(genomes[0].tobytes()).hexdigest()})
    return cases, identity, artifact_hashes, used


def transfer_contrasts(rows: dict) -> dict[str, np.ndarray]:
    """Average the paired per-seed effects first, retaining covariance across durations."""
    expected = {f"fast_T{duration}" for duration in DURATIONS} | {"old_T1024"}
    if set(rows) != expected:
        raise ValueError("transfer needs all three fast durations and old conduction")
    effects = {}
    shape = None
    for name, values in rows.items():
        winner, parent = np.asarray(values[1]["F"]), np.asarray(values[0]["F"])
        paired(winner, parent)  # Validate paired shape and finiteness before subtraction can broadcast.
        if shape is not None and winner.shape != shape:
            raise ValueError("transfer conditions must share the same ordered seed arrays")
        shape = winner.shape
        effects[name] = winner - parent
    fast = [effects[f"fast_T{duration}"] for duration in DURATIONS]
    stacked = np.stack(fast)
    if stacked.ndim != 2 or stacked.shape[1] < 2 or not np.isfinite(stacked).all():
        raise ValueError("duration effects must share finite paired seed arrays")
    if effects["old_T1024"].shape != fast[1].shape or not np.isfinite(effects["old_T1024"]).all():
        raise ValueError("old-conduction effects must share finite paired seed arrays")
    return {**effects, "duration_average": stacked.mean(axis=0),
            "fast_minus_old_gain": effects["fast_T1024"] - effects["old_T1024"]}


def case_report(rows: dict, worlds: dict, metadata: dict) -> tuple[dict, dict]:
    contrasts = transfer_contrasts(rows)
    summary = {name: paired(values, np.zeros_like(values)) for name, values in contrasts.items()}
    report = {**metadata, "conditions": {name: compare_rows(values[1], values[0], worlds[name])
                                         for name, values in rows.items()},
              "gains": summary, "averaging": "Equal mean of the three per-seed fast-duration fitness gains; "
                                                  "SE across seeds after averaging, retaining covariance.",
              "interpretation": "All four winners were fixed before transfer. This evaluates duration and "
                                "conduction transfer without selecting replacements or establishing new mechanisms."}
    return report, contrasts


def ensure_manifest(out: Path, manifest: dict) -> None:
    path = out / "manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("transfer inputs or source identity changed; use a new output directory")
    if not path.exists() and out.exists() and any(out.rglob("*.npz")):
        raise ValueError("transfer output contains cached rows without a manifest")
    out.mkdir(parents=True, exist_ok=True)
    atomic_json(path, manifest)


def run_transfer(archive: Path, out: Path, *, threads: int = 2, max_cpu_seconds: float = 3600) -> dict:
    if threads < 1 or not np.isfinite(max_cpu_seconds) or max_cpu_seconds <= 0:
        raise ValueError("threads and CPU budget must be positive")
    cases, old_identity, artifacts, used = load_cases(archive)
    seeds = transfer_seeds(used)
    identity = numerical_identity()
    if identity != old_identity:
        raise ValueError("transfer numerical/source identity differs from the measured archive")
    worlds = {case["name"]: condition_worlds(case["world"]) for case in cases}
    metadata = {case["name"]: {key: case[key] for key in ("world", "source_row", "parent_sha256", "winner_sha256")}
                for case in cases}
    manifest = {"format": 1, "archive": str(archive.resolve()), "artifacts": artifacts,
                "numerical_identity": identity, "runner_sha256": sha(Path(__file__)),
                "helpers": {name: sha(ROOT / "scripts" / name) for name in
                            ("taskvar_confirm.py", "taskvar_gradient.py", "taskvar_gates.py")},
                "seeds": seeds, "seed_block": SEED_BLOCK, "cases": metadata,
                "worlds": {case: {name: asdict(world) for name, world in values.items()}
                           for case, values in worlds.items()}, "max_cpu_seconds": max_cpu_seconds,
                "budget_enforcement": "Check before each new row; one row may cross the budget. "
                                      "Use the external CPU monitor for a strict mid-row study cap."}
    ensure_manifest(out, manifest)
    index_path = out / "row_index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    cpu_spent = 0.0
    for relative, saved in index.items():
        path = out / relative
        if not path.exists() or sha(path) != saved["sha256"]:
            raise ValueError(f"cached transfer row differs from its checkpoint: {relative}")
        if not np.isfinite(saved["cpu_seconds"]) or saved["cpu_seconds"] < 0:
            raise ValueError("cached transfer CPU accounting is invalid")
        cpu_spent += saved["cpu_seconds"]
    report = {"report_only": True, "status": "incomplete", "seed_block": SEED_BLOCK, "seeds": seeds,
              "planned_genome_lives": len(cases) * 4 * 2 * len(seeds), "cases": {}, "timings": {},
              "cpu_seconds": cpu_spent, "max_cpu_seconds": max_cpu_seconds}
    for case in cases:
        name = case["name"]
        rows = {}
        for condition, world in worlds[name].items():
            stage_out = out / name / condition
            values = {}
            for genome_index in (0, 1):
                row_path = stage_out / f"row_{genome_index:04d}.npz"
                relative = str(row_path.relative_to(out))
                if not row_path.exists() and cpu_spent >= max_cpu_seconds:
                    report.update(status="budget_stop", cpu_seconds=cpu_spent)
                    atomic_json(out / "report.json", report)
                    return report
                row = score_row(stage_out, genome_index, case["genomes"], world, seeds, case["evaluator"], threads)
                if any(not np.isfinite(float(row[key])) or float(row[key]) < 0
                       for key in ("cpu_seconds", "wall_seconds")):
                    raise ValueError("transfer row has invalid timing metadata")
                values[genome_index] = row
                if relative not in index:
                    cpu_spent += float(row["cpu_seconds"])
                    index[relative] = {"sha256": sha(row_path), "cpu_seconds": float(row["cpu_seconds"])}
                    atomic_json(index_path, index)
                report["cpu_seconds"] = cpu_spent
                progress = {"case": name, "condition": condition, "genome_index": genome_index,
                            "completed_rows": len(index), "planned_rows": len(cases) * 8,
                            "cpu_seconds": cpu_spent, "max_cpu_seconds": max_cpu_seconds}
                atomic_json(out / "progress.json", progress)
                print(json.dumps(progress), flush=True)
            rows[condition] = values
            report["timings"][f"{name}/{condition}"] = {
                key: sum(float(row[key]) for row in values.values()) for key in ("cpu_seconds", "wall_seconds")}
            atomic_npz(stage_out / "scores.npz", seeds=np.asarray(seeds, dtype=np.uint64),
                       genome_indices=np.asarray([0, 1]),
                       **{key: np.stack([values[i][key] for i in (0, 1)]) for key in COLS})
            atomic_json(out / "report.json", report)
        report["cases"][name], contrasts = case_report(rows, worlds[name], metadata[name])
        atomic_npz(out / name / "contrasts.npz", seeds=np.asarray(seeds, dtype=np.uint64), **contrasts)
        atomic_json(out / name / "report.json", report["cases"][name])
        atomic_json(out / "report.json", report)
    report["status"] = "complete"
    report["completed_genome_lives"] = len(index) * len(seeds)
    atomic_json(out / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "results/pool_mutants_20261013")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/autonomous_followthrough_20261013/transfer")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--max-cpu-seconds", type=float, default=3600)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.out.resolve().is_relative_to(ROOT / "outputs"):
        parser.error("study output must be inside the repository outputs/ directory")
    if args.threads < 1 or not np.isfinite(args.max_cpu_seconds) or args.max_cpu_seconds <= 0:
        parser.error("threads and CPU budget must be positive")
    if not args.run:
        cases, _, _, used = load_cases(args.archive)
        seeds = transfer_seeds(used)
        print(json.dumps({"status": "dry_run", "out": str(args.out), "cases": [case["name"] for case in cases],
                          "lives": len(seeds), "seed_block": SEED_BLOCK, "durations": list(DURATIONS),
                          "genome_lives": len(cases) * 4 * 2 * len(seeds), "max_cpu_seconds": args.max_cpu_seconds,
                          "note": "Fixed archived winners; transfer never selects another genotype."}, indent=2))
        return
    report = run_transfer(args.archive, args.out, threads=args.threads, max_cpu_seconds=args.max_cpu_seconds)
    print(json.dumps({key: report[key] for key in ("status", "cpu_seconds", "planned_genome_lives")}, indent=2))


if __name__ == "__main__":
    main()
