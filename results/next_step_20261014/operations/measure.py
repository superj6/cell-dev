"""Fixed second D continuation endpoint confirmation, adapted from the reviewed D runner; dry-run default."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from run_budgeted import check_protocol, check_ready, save, sha  # noqa: E402


def duration_mixture(rows, candidate: int, reference: int):
    """Average durations within each shared seed, retaining their covariance."""
    import numpy as np

    if set(rows) != {"768", "1024", "1536"}:
        raise ValueError("need exactly the three registered durations")
    effects = [np.asarray(value[candidate]["F"]) - np.asarray(value[reference]["F"]) for value in rows.values()]
    values = np.stack(effects)
    if values.ndim != 2 or values.shape[1] < 2 or not np.isfinite(values).all():
        raise ValueError("duration effects must be finite and share paired life arrays")
    return values.mean(axis=0)


def confirm_endpoints():
    """Only called after both complete; freeze final population rank zero before looking at any confirmation."""
    import numpy as np
    from omegaconf import OmegaConf

    from scripts.taskvar_confirm import COLS, atomic_npz, compare_rows, score_row
    from scripts.taskvar_gates import paired
    from src import checkpoint
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    protocol, ready = check_protocol(), check_ready()
    identity = checkpoint.numerical_identity()
    if identity != protocol["expected_numerical_identity"]:
        raise ValueError("confirmation numerical identity differs from the original measurement")
    expected = {"labels": ["pilot_s5", "founder_row38", "D51089", "D51090",
                           "s52091_final_rank0", "s52092_final_rank0"],
                "primary_pairs": [[4, 2], [5, 3]], "secondary_pairs": [[4, 1], [5, 1], [4, 0], [5, 0]],
                "seed_block": 102, "seeds": list(range(52_020_000, 52_020_256)),
                "durations": [768, 1024, 1536], "threads": 2}
    if any(protocol["confirmation"][key] != value for key, value in expected.items()):
        raise ValueError("fixed six-role confirmation scope differs")
    paths = [ROOT / name for name in protocol["reference_files"]]
    if len(paths) != 4 or protocol["runs"] != [52091, 52092]:
        raise ValueError("fixed founders and run mapping differ")
    checkpoint_hashes = {}
    search_health = {}
    for seed in protocol["runs"]:
        folder = STUDY / f"runs/s{seed}"
        cfg = OmegaConf.load(ROOT / protocol["configs"][str(seed)]["path"])
        path = folder / "checkpoint.pt"
        saved = checkpoint.load(path)
        checkpoint.validate(saved, cfg, identity)
        if saved["state"]["generation"] != protocol["generations"]:
            raise ValueError("refuse endpoint measurement of an incomplete continuation")
        curves = saved["state"]["curves"]
        if [row["gen"] for row in curves] != list(range(protocol["generations"])):
            raise ValueError("checkpoint lacks the complete ordered search history")
        search_health[str(seed)] = {
            key: max(float(row[key]) for row in curves)
            for key in ("pop_invalid", "pop_mismatch", "recheck_invalid")}
        save(STUDY / "search_health.json", search_health)
        if any(value != 0 for value in search_health[str(seed)].values()):
            raise ValueError("invalid or mismatched search lives require investigation before endpoint inference")
        selected = folder / "best_genome.json"
        _, genome = Layout.load(selected)
        if genome.numpy().tobytes() != saved["state"]["population"][0].numpy().tobytes():
            raise ValueError("saved best differs from final production population rank zero")
        paths.append(selected)
        checkpoint_hashes[str(seed)] = sha(path)
    layout, _ = Layout.load(paths[0])
    genomes = np.stack([Layout.load(path)[1].numpy() for path in paths])
    labels = protocol["confirmation"]["labels"]
    seeds = json.loads((STUDY / "seed_audit.json").read_text())["confirm_seeds"]
    cfg = OmegaConf.load(ROOT / protocol["configs"][str(protocol["runs"][0])]["path"])
    evaluator = LifeEvaluator(cfg, layout)
    worlds = {str(duration): spec.world("catch_speck_l4", T=duration, d0=0.5, d_min=0.25, sigma=0.4, lam_s=4.0)
              for duration in (768, 1024, 1536)}
    manifest = {"format": 1, "labels": labels, "seeds": seeds, "seed_block": 102,
                "genotype_sha256": {label: hashlib.sha256(genome.tobytes()).hexdigest()
                                    for label, genome in zip(labels, genomes)},
                "checkpoint_sha256": checkpoint_hashes, "search_health": search_health,
                "protocol_sha256": sha(STUDY / "protocol.json"),
                "numerical_identity": identity, "ready": ready,
                "worlds": {name: asdict(world) for name, world in worlds.items()},
                "selection": "Exactly final population rank0 from each completed16-generation run; no reselection"}
    out = STUDY / "confirmation"
    previous = out / "manifest.json"
    if previous.exists() and json.loads(previous.read_text()) != manifest:
        raise ValueError("confirmation inputs changed")
    if not previous.exists() and out.exists() and any(out.rglob("*.npz")):
        raise ValueError("cached confirmation rows have no manifest")
    save(previous, manifest)
    atomic_npz(out / "genotypes.npz", genomes=genomes, labels=np.asarray(labels))
    index_path = out / "row_index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    for relative, digest in index.items():
        if sha(out / relative) != digest:
            raise ValueError("cached confirmation row differs from checkpoint hash")
    all_rows, report = {}, {"report_only": True, "status": "incomplete", "worlds": {}, "primary": {}}
    for name, world in worlds.items():
        rows = {}
        for i in range(6):
            rows[i] = score_row(out / name, i, genomes, world, seeds, evaluator, 2)
            path = out / name / f"row_{i:04d}.npz"
            index[str(path.relative_to(out))] = sha(path)
            save(index_path, index)
        atomic_npz(out / name / "scores.npz", seeds=np.asarray(seeds, dtype=np.uint64),
                   genome_indices=np.arange(6), **{key: np.stack([rows[i][key] for i in range(6)]) for key in COLS})
        all_rows[name] = rows
        report["worlds"][name] = {
            labels[i]: {"vs_own_founder": compare_rows(rows[i], rows[i - 2], world),
                        "vs_row38": compare_rows(rows[i], rows[1], world),
                        "vs_pilot": compare_rows(rows[i], rows[0], world)} for i in (4, 5)}
        save(out / "report.json", report)
    for i in (4, 5):
        by_seed = duration_mixture(all_rows, i, i - 2)
        estimate = paired(by_seed, np.zeros_like(by_seed))
        report["primary"][labels[i]] = {**estimate, "above_3se": estimate["mean"] > 3 * estimate["se"],
                                       "at_least_0p5": estimate["mean"] >= 0.5}
    report["secondary"] = {
        labels[i]: {name: paired(duration_mixture(all_rows, i, reference), np.zeros(len(seeds)))
                    for name, reference in (("vs_row38", 1), ("vs_pilot", 0))} for i in (4, 5)}
    report.update(status="complete", genome_lives=4608, independent_search_replicates=2,
                  interpretation="Each primary averages three duration effects within seed before computing SE; "
                                 "the256 seed clusters are shared across runs. These are two fixed-founder "
                                 "exploratory continuations, "
                                 "not an estimate of general search reliability or evidence of a new algorithm.")
    save(out / "report.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-child", action="store_true")
    args = parser.parse_args()
    if args.confirm_child:
        confirm_endpoints()
    else:
        print(json.dumps({"status": "dry_run", "genome_lives": 4608, "seed_block": 102, "simulated_lives": 0}))


if __name__ == "__main__":
    main()
