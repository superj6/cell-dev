"""Fixed activity-input lesions with cell composition held constant; dry-run by default."""
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
sys.path.insert(0, str(ROOT))
STUDY = ROOT / "outputs/autonomous_regulation_20261014"
CONDITIONS = ("structure", "structure+genes_blind", "freeze")
FLAGS = {"structure": ("division_off", "apoptosis_off"),
         "structure+genes_blind": ("division_off", "apoptosis_off", "genes_blind"),
         "freeze": ("freeze",)}
LABELS = ("founder_row38", "d_s51089_final_rank0", "d_s51090_final_rank0")
LIVES, BLOCK, CAP = 512, 101, 3600
HELPERS = ("taskvar_confirm.py", "taskvar_second_step.py", "taskvar_gradient.py", "taskvar_gates.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_protocol(study=STUDY):
    protocol = json.loads((study / "protocol.json").read_text())
    expected = {"labels": list(LABELS), "conditions": list(CONDITIONS), "seed_block": BLOCK,
                "seeds": list(range(52_010_000, 52_010_512)), "genome_lives": 4608,
                "max_cpu_seconds": CAP, "threads": 2, "T": 1536, "t_fork": 768, "t_open": 800}
    if any(protocol[key] != value for key, value in expected.items()):
        raise ValueError("registered scope differs")
    for name, key in (("prepare.py", "prepare_sha256"), ("seed_review.json", "seed_review_sha256"),
                      ("PREREG.md", "prereg_sha256")):
        if sha(study / name) != protocol[key]:
            raise ValueError("preparation receipt differs: " + name)
    for relative, expected_sha in protocol["source_identity"].items():
        if sha(ROOT / relative) != expected_sha:
            raise ValueError("source differs: " + relative)
    if set(protocol["helpers"]) != set(HELPERS):
        raise ValueError("helper pin set differs")
    for name, expected_sha in protocol["helpers"].items():
        if sha(ROOT / "scripts" / name) != expected_sha:
            raise ValueError("helper differs: " + name)
    for relative, item in protocol["inputs"].items():
        if sha(study / relative) != item["sha256"]:
            raise ValueError("fixed input differs: " + relative)
    return protocol


def worlds():
    from src.life import spec

    return {key: spec.world("catch_speck_l4", T=1536, t_fork=768, t_open=800,
                           d0=.5, d_min=.25, sigma=.4, lam_s=4,
                           fork_flags=spec.V3.flags(*FLAGS[key]))
            for key in CONDITIONS}


def contrasts(fitness):
    """Compute all genotype and intervention differences within each life before estimating SE."""
    import numpy as np

    arrays = {key: np.asarray(fitness[key], dtype=np.float64) for key in CONDITIONS}
    shape = arrays["structure"].shape
    if len(shape) != 2 or shape[0] != 3 or shape[1] < 2:
        raise ValueError("need three genotype rows and at least two paired lives")
    if any(value.shape != shape or not np.isfinite(value).all() for value in arrays.values()):
        raise ValueError("all nine arms must be finite and paired")
    raw = {}
    for i, label in enumerate(LABELS[1:], 1):
        gains = {key: value[i] - value[0] for key, value in arrays.items()}
        for key, gain in gains.items():
            raw[label + "__gain__" + key] = gain
        raw[label + "__added_input_dependence"] = gains["structure"] - gains["structure+genes_blind"]
        raw[label + "__added_regulation_effect"] = gains["structure"] - gains["freeze"]
    for i, label in enumerate(LABELS):
        raw[label + "__input_loss"] = arrays["structure"][i] - arrays["structure+genes_blind"][i]
        raw[label + "__regulation_effect"] = arrays["structure"][i] - arrays["freeze"][i]
    return raw


def validate_structure(rows):
    """Check constant tissue in all arms within genotype, retaining guarded rows in fitness."""
    import numpy as np

    from src.life import spec

    terminal = spec.STATUS["extinct"] | spec.STATUS["guard_cells"] | spec.STATUS["guard_events"]
    counts = []
    for i in range(3):
        arms = [rows[key][i] for key in CONDITIONS]
        for row in arms:
            invalid = spec.STATUS["capacity"] | spec.STATUS["ledger_mismatch"]
            if np.any(row["status"].astype(np.int64) & invalid):
                raise ValueError("invalid implementation status in structure-clamped tissue")
            if (np.any(row["births"] != 0) or np.any(row["deaths"] != 0)
                    or np.any(row["last_birth"] >= 800)):
                raise ValueError("structure-clamped tissue changed during the measured interval")
        complete = np.logical_and.reduce([(row["status"].astype(np.int64) & terminal) == 0 for row in arms])
        counts.append(int(complete.sum()))
        for row in arms:
            if np.any(row["t_end"][complete] != 1536):
                raise ValueError("complete life ended early")
            for key in ("n_end", "n_S_end", "n_M_end", "n_H_end"):
                if not np.array_equal(arms[0][key][complete], row[key][complete]):
                    raise ValueError("structure-clamped arms have different tissue counts")
            if not np.allclose(row["live_time"][complete], 736 * row["n_end"][complete], rtol=1e-10, atol=1e-8):
                raise ValueError("structure-clamped live-time differs from constant population")
    return {"complete_three_arm_lives_by_genotype": counts, "post_open_births_and_deaths": 0,
            "window": [800, 1536], "all_fitness_rows_retained": True,
            "limitation": "Guard/extinct rows remain in fitness; constant-population checks use complete triplets."}


def run():
    import numpy as np
    from omegaconf import OmegaConf
    from run_budgeted import check_ready

    from scripts.taskvar_confirm import COLS, atomic_json, atomic_npz, compare_rows
    from scripts.taskvar_gates import paired
    from scripts.taskvar_second_step import RowStore, freeze
    from src.checkpoint import numerical_identity
    from src.genome import Layout
    from src.life.evaluate import LifeEvaluator

    protocol, ready = check_protocol(), check_ready()
    identity = numerical_identity()
    if identity != protocol["numerical_identity"]:
        raise ValueError("numerical identity differs from D")
    genome_rows, layout = [], None
    for label in LABELS:
        row_layout, row = Layout.load(STUDY / "inputs" / (label + ".json"))
        if layout is not None and layout.dims != row_layout.dims:
            raise ValueError("genome layouts differ")
        layout = row_layout
        genome_rows.append(row.numpy())
    genomes = np.stack(genome_rows)
    if [hashlib.sha256(g.tobytes()).hexdigest() for g in genomes] != protocol["genome_raw_sha256"]:
        raise ValueError("raw fixed genotype differs")
    evaluator = LifeEvaluator(OmegaConf.load(STUDY / "inputs/evaluator.yaml"), layout)
    settings, seeds, out = worlds(), protocol["seeds"], STUDY / "measurement"
    manifest = {"labels": list(LABELS), "conditions": list(CONDITIONS), "seeds": seeds, "seed_block": BLOCK,
                "worlds": {key: asdict(world) for key, world in settings.items()},
                "genome_raw_sha256": protocol["genome_raw_sha256"], "numerical_identity": identity,
                "protocol_sha256": sha(STUDY / "protocol.json"), "ready": ready, "planned_genome_lives": 4608}
    manifest = json.loads(json.dumps(manifest))
    if not (out / "manifest.json").exists() and out.exists() and any(out.rglob("*.npz")):
        raise ValueError("cached rows without frozen manifest")
    out.mkdir(parents=True, exist_ok=True)
    freeze(out / "manifest.json", manifest, "structure-clamped regulation inputs")
    atomic_npz(out / "genotypes.npz", genomes=genomes, labels=np.asarray(LABELS))
    stores = {key: RowStore(out / key, genomes, world, evaluator, 2, CAP) for key, world in settings.items()}
    rows, report = {}, {"status": "incomplete", "conditions": {}, "planned_genome_lives": 4608}
    for key, world in settings.items():
        rows[key] = {}
        for i in range(3):
            if sum(store.cpu_seconds for store in stores.values()) >= CAP:
                report.update(status="budget_stop")
                atomic_json(out / "report.json", report)
                return report
            rows[key][i] = stores[key].row("rows", i, seeds)
        atomic_npz(out / key / "scores.npz", seeds=np.asarray(seeds, dtype=np.uint64), genome_indices=np.arange(3),
                   **{column: np.stack([rows[key][i][column] for i in range(3)]) for column in COLS})
        report["conditions"][key] = {label: compare_rows(rows[key][i], rows[key][0], world)
                                     for i, label in enumerate(LABELS[1:], 1)}
        report["row_cpu_seconds"] = sum(store.cpu_seconds for store in stores.values())
        atomic_json(out / "report.json", report)
    raw = contrasts({key: np.stack([row["F"] for row in value.values()]) for key, value in rows.items()})
    report["contrasts"] = {}
    for name, values in raw.items():
        estimate = paired(values, np.zeros_like(values))
        report["contrasts"][name] = {**estimate, "positive_above_3se": estimate["mean"] > 3 * estimate["se"],
                                     "negative_below_minus_3se": estimate["mean"] < -3 * estimate["se"]}
    atomic_npz(out / "contrasts.npz", seeds=np.asarray(seeds, dtype=np.uint64), **raw)
    report["constant_tissue_validation"] = validate_structure(rows)
    report.update(status="complete", genome_lives=4608, limitations=protocol["limitations"])
    atomic_json(out / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.run:
        result = run()
        print(json.dumps({key: result[key] for key in ("status", "row_cpu_seconds")}))
    else:
        print(json.dumps({"status": "dry_run", "genome_lives": 4608, "seed_block": BLOCK,
                          "labels": LABELS, "conditions": CONDITIONS, "simulated_lives": 0}))


if __name__ == "__main__":
    main()
