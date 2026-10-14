"""U's fixed four-role/four-condition confirmation; dry-run default, no endpoint reselection."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

RUNS = [53091, 53092]
LABELS = ["I_s5_row32", "I_s7_row1", "s53091_final_rank0", "s53092_final_rank0"]
CONDITIONS = ["trained", "width_swapped", "frozen", "frozen_lateral_off"]
SEEDS = list(range(52_060_000, 52_060_512))


def condition_worlds(base):
    from src.life import spec

    expected = spec.world("catch_speck_l4", T=1024, d0=1.0, d_min=0.5, b2_amp=1.0,
                          b2_sigma=1.2, b2_value=-50.0, b2_p=1.0, b2_mode=1)
    if base != expected:
        raise ValueError("U base world must equal the completed F/I world")
    freeze = spec.V3.flags("freeze")
    worlds = {"trained": base, "width_swapped": replace(base, sigma=1.2, b2_sigma=0.6),
              "frozen": replace(base, t_fork=512.0, t_open=544.0, fork_flags=freeze),
              "frozen_lateral_off": replace(base, t_fork=512.0, t_open=544.0,
                                             fork_flags=spec.V3.flags("freeze", "lateral_off"))}
    for world in worlds.values():
        spec.V3.validate_world(world)
    return worlds


def paired_interaction(rows, first, second, candidate, reference, key="F"):
    """Difference of paired differences; do not combine separate SEs or unequal accounting windows."""
    import numpy as np

    if (first, second) not in (("trained", "width_swapped"), ("frozen", "frozen_lateral_off")):
        raise ValueError("registered interactions require matching accounting windows")
    arrays = [np.asarray(rows[condition][i][key], dtype=float)
              for condition in (first, second) for i in (candidate, reference)]
    if any(value.ndim != 1 or len(value) < 2 or not np.isfinite(value).all() for value in arrays):
        raise ValueError("interactions require finite one-dimensional paired rows")
    if len({value.shape for value in arrays}) != 1:
        raise ValueError("interaction rows must share the same seed order and length")
    return (arrays[0] - arrays[1]) - (arrays[2] - arrays[3])


def decoy_comparison(candidate, reference, world):
    import numpy as np

    from scripts.taskvar_confirm import compare_rows
    from scripts.taskvar_gates import paired
    from src.life import spec

    result = compare_rows(candidate, reference, world)
    result["b2_clicks"] = paired(candidate["b2_clicks"], reference["b2_clicks"])
    window = world.T - world.t_open
    if window <= 0:
        raise ValueError("accounting window must be positive")
    pieces = {
        "capture_income": world.R_cap * (candidate["captures"] - reference["captures"]) / window,
        "poison_cost_saving": spec.b2_cost(world) * (reference["b2_clicks"] - candidate["b2_clicks"]) / window,
        "miss_cost_saving": world.c_miss * (reference["misses"] - candidate["misses"]) / window,
        "guard_charge_saving": (reference["guard_charge"] - candidate["guard_charge"]) / window,
        "extinction_charge_saving": reference["extinct_charge"] - candidate["extinct_charge"],
    }
    costs = (reference["cost"] - candidate["cost"]) / window
    pieces["other_cost_saving"] = costs - pieces["poison_cost_saving"] - pieces["miss_cost_saving"]
    pieces["residual"] = candidate["F"] - reference["F"] - sum(pieces.values())
    if not np.allclose(pieces["residual"], 0.0, atol=1e-8, rtol=0):
        raise ValueError("decoy accounting does not reconstruct paired fitness")
    result["decoy_fitness_contributions"] = {name: paired(value, np.zeros_like(value))
                                             for name, value in pieces.items()}
    return result


def validate_search_state(state, generations=4):
    if state["generation"] != generations:
        raise ValueError("refuse incomplete search endpoint")
    curves = state["curves"]
    if [row["gen"] for row in curves] != list(range(generations)):
        raise ValueError("checkpoint lacks complete ordered search history")
    keys = ("pop_invalid", "pop_mismatch", "recheck_invalid")
    if any(not math.isfinite(float(row[key])) or float(row[key]) != 0 for row in curves for key in keys):
        raise ValueError("invalid or mismatched search lives block inference")
    health = {key: max(float(row[key]) for row in curves) for key in keys}
    return health


def confirm_endpoints():
    import numpy as np
    from omegaconf import OmegaConf
    from run_budgeted import check_protocol, check_ready, save, sha

    from scripts.taskvar_confirm import COLS, atomic_npz, score_row
    from scripts.taskvar_gates import paired
    from src import checkpoint
    from src.genome import Layout
    from src.life import spec
    from src.life.evaluate import LifeEvaluator

    protocol, ready = check_protocol(), check_ready()
    expected = {"labels": LABELS, "seeds": SEEDS, "seed_block": 106, "conditions": CONDITIONS,
                "threads": 2, "primary_pairs": [[2, 0], [3, 1]], "fork_time": 512, "accounting_open": 544}
    if protocol["runs"] != RUNS or protocol["generations"] != 4:
        raise ValueError("registered search scope differs")
    if any(protocol["confirmation"][key] != value for key, value in expected.items()):
        raise ValueError("registered confirmation scope differs")
    if json.loads((STUDY / "seed_audit.json").read_text())["confirm_seeds"] != SEEDS:
        raise ValueError("confirmation seeds differ from independent audit")
    out = STUDY / "confirmation"
    if out.exists():
        raise ValueError("confirmation artifacts already exist; no automatic retry or partial rescue")
    identity = checkpoint.numerical_identity()  # Two existing startup validation lives, inside the monitor cap.
    if identity != protocol["expected_numerical_identity"]:
        raise ValueError("confirmation numerical identity differs")
    paths = [ROOT / name for name in protocol["reference_files"]]
    if len(paths) != 2:
        raise ValueError("exactly two fixed I references required")
    endpoint_records = {}
    for seed in RUNS:
        folder = STUDY / f"runs/s{seed}"
        cfg = OmegaConf.load(ROOT / protocol["configs"][str(seed)]["path"])
        path = folder / "checkpoint.pt"
        saved = checkpoint.load(path)
        checkpoint.validate(saved, cfg, identity)
        health = validate_search_state(saved["state"])
        selected = folder / "best_genome.json"
        _, genome = Layout.load(selected)
        if genome.numpy().tobytes() != saved["state"]["population"][0].numpy().tobytes():
            raise ValueError("endpoint differs from final production population rank0")
        paths.append(selected)
        endpoint_records[str(seed)] = {"checkpoint_sha256": sha(path), "genome_file_sha256": sha(selected),
            "genome_raw_sha256": hashlib.sha256(genome.numpy().tobytes()).hexdigest(),
            "generation": 4, "rank": 0, "search_health": health}
    layout, _ = Layout.load(paths[0])
    loaded = [Layout.load(path) for path in paths]
    if any(other.dims != layout.dims for other, _ in loaded):
        raise ValueError("genotype layouts differ")
    genomes = np.stack([genome.numpy() for _, genome in loaded])
    for i, seed in enumerate(RUNS):
        if hashlib.sha256(genomes[i].tobytes()).hexdigest() != protocol["founder_mapping"][str(seed)]["raw_sha256"]:
            raise ValueError("fixed I founder genotype differs")
    worlds = condition_worlds(spec.World(**protocol["world"]))
    cfg = OmegaConf.load(ROOT / protocol["configs"][str(RUNS[0])]["path"])
    evaluator = LifeEvaluator(cfg, layout)
    manifest = {"format": 1, "labels": LABELS, "seeds": SEEDS, "seed_block": 106,
        "genotype_sha256": {label: hashlib.sha256(genome.tobytes()).hexdigest()
                            for label, genome in zip(LABELS, genomes)},
        "endpoints": endpoint_records, "protocol_sha256": sha(STUDY / "protocol.json"),
        "numerical_identity": identity, "ready": ready, "worlds": {key: asdict(value) for key, value in worlds.items()},
        "selection": "Both complete generation4 final rank0 endpoints fixed together before any confirmation."}
    # A single atomic receipt binds both endpoints before any score_row call.
    save(out / "endpoints.json", manifest)
    atomic_npz(out / "genotypes.npz", genomes=genomes, labels=np.asarray(LABELS))
    all_rows, index = {}, {}
    report = {"status": "incomplete", "report_only": True, "conditions": {}, "primary": {}, "secondary": {}}
    for name, world in worlds.items():
        rows = {}
        for i in range(4):
            rows[i] = score_row(out / name, i, genomes, world, SEEDS, evaluator, 2)
            path = out / name / f"row_{i:04d}.npz"
            index[str(path.relative_to(out))] = sha(path)
            save(out / "row_index.json", index)
        atomic_npz(out / name / "scores.npz", seeds=np.asarray(SEEDS, dtype=np.uint64),
                   genome_indices=np.arange(4), **{key: np.stack([rows[i][key] for i in range(4)]) for key in COLS})
        all_rows[name] = rows
        report["conditions"][name] = {
            "accounting_window": world.T - world.t_open,
            "absolute": {LABELS[i]: {key: paired(rows[i][key], np.zeros(len(SEEDS))) for key in
                ("F", "captures", "b2_clicks", "clicks", "misses", "n_end", "n_H_end", "live_time",
                 "path", "spikes", "packets", "income", "cost", "guard_charge", "extinct_charge")}
                for i in range(4)},
            "own_founder_contrasts": {LABELS[i]: decoy_comparison(rows[i], rows[i - 2], world) for i in (2, 3)}}
        save(out / "report.json", report)
    for i in (2, 3):
        primary = paired(all_rows["trained"][i]["F"], all_rows["trained"][i - 2]["F"])
        report["primary"][LABELS[i]] = {**primary, "above_3se": primary["mean"] > 3 * primary["se"],
                                       "at_least_0p5": primary["mean"] >= 0.5}
        report["secondary"][LABELS[i]] = {}
        for label, first, second in (("width_association_gain", "trained", "width_swapped"),
                                      ("added_lateral_dependence", "frozen", "frozen_lateral_off")):
            report["secondary"][LABELS[i]][label] = {key: paired(
                paired_interaction(all_rows, first, second, i, i - 2, key), np.zeros(len(SEEDS)))
                for key in ("F", "captures", "b2_clicks", "clicks", "misses", "n_end", "path", "spikes", "packets")}
    report.update(status="complete", genome_lives=8192, paired_seeds=512, conditional_searches=2,
        confirmation_startup_validation_lives=2,
        limitations=["Life-level paired SE describes fixed genotypes, not independent evolutionary reliability.",
            "Width reversal changes sensory geometry, detection and action-contingent trajectories; an effect is "
            "not pure discrimination or learning proof.",
            "Freeze bundles growth, regulatory and phenotypic updates; it does not establish maturity.",
            "Lateral-off suppresses new in-plane spike sends, retaining attempted-send charges, in-flight and "
            "vertical spikes and chemical packets; effects can include indirect network and motor dynamics.",
            "Whole-life trained/swap fitness is never directly subtracted from frozen-window fitness.",
            "Lower costs or fewer actions may improve F without richer computation; complete accounting is retained.",
            "No missing arm, stopped search or partial result supports a complete-study inference."])
    save(out / "report.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-child", action="store_true")
    args = parser.parse_args()
    if args.confirm_child:
        confirm_endpoints()
    else:
        print(json.dumps({"status": "dry_run", "genome_lives": 8192, "seed_block": 106,
                          "conditions": CONDITIONS, "simulated_lives": 0}))


if __name__ == "__main__":
    main()
