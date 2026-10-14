"""Prepare the fixed X3 structural-operator comparison; no simulations or launch."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from omegaconf import OmegaConf  # noqa: E402

from src.genome import Layout  # noqa: E402
from src.life.evaluate import LifeEvaluator, life_seed  # noqa: E402

STUDY = Path(__file__).resolve().parent
BASELINE = ROOT / "outputs/autonomous_continuation_20261013"
ARCHIVE = ROOT / "results/pool_mutants_20261013"
RUNS = (51089, 51090)
CONFIRM_SEEDS = list(range(51_930_000, 51_930_256))
LABELS = ["pilot_s5", "founder_row38", "d_s51089_final_rank0", "d_s51090_final_rank0",
          "g_s51089_final_rank0", "g_s51090_final_rank0"]
ALLOWED_CONFIG_CHANGES = {"evolve.dup_rate", "evolve.del_rate", "evolve.seed_genome",
                          "life.control", "logging.output_dir"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(label + " differs from fixed comparison")


def freeze(path, data):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("refuse to overwrite frozen preparation: " + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def freeze_json(path, value):
    freeze(path, (json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def differences(left, right, prefix=""):
    if isinstance(left, dict) and isinstance(right, dict):
        result = set()
        for key in set(left) | set(right):
            path = prefix + "." + key if prefix else key
            if key not in left or key not in right:
                result.add(path)
            else:
                result.update(differences(left[key], right[key], path))
        return result
    return set() if left == right else {prefix}


def run_seeds(seed):
    values = []
    for generation in range(16):
        values.extend(life_seed(seed, "gen", generation, j) for j in range(7))
        if generation % 4 == 0 or generation == 15:
            values.extend(life_seed(seed, "valid", generation, j) for j in range(16))
    for index in (0, 1):
        values.extend(life_seed(seed, "final", index, j) for j in range(2))
    return values


def baseline_pins():
    protocol = json.loads((BASELINE / "protocol.json").read_text())
    ready = json.loads((BASELINE / "ready.json").read_text())
    equal(sha(BASELINE / "protocol.json"), ready["protocol_sha256"], "D protocol")
    equal(sha(BASELINE / "run_budgeted.py"), ready["runner_sha256"], "D runner")
    equal(protocol["runs"], list(RUNS), "D replicate seeds")
    equal(protocol["generations"], 16, "D generation count")
    equal(sha(BASELINE / "seed_audit.json"), protocol["seed_audit_sha256"], "D seed audit")
    for relative, expected in protocol["source_identity"].items():
        equal(sha(ROOT / relative), expected, "engine/search source")
    for name, expected in ready["helpers"].items():
        equal(sha(ROOT / "scripts" / name), expected, "measurement helper")
    for value in protocol["configs"].values():
        equal(sha(ROOT / value["path"]), value["sha256"], "D configuration")
    return protocol, ready


def main():
    baseline, ready = baseline_pins()
    provenance = json.loads((ARCHIVE / "provenance.json").read_text())
    equal(sha(ARCHIVE / "provenance.json"), baseline["archive_provenance_sha256"], "prior archive")
    equal(provenance["numerical_identity"], baseline["expected_numerical_identity"], "numerical identity")
    copied = {}
    for name in ("founder", "pilot"):
        original = ROOT / baseline[name + "_file"]
        equal(sha(original), baseline[name + "_sha256"], name + " genotype")
        path = STUDY / "inputs" / original.name
        freeze(path, original.read_bytes())
        copied[name] = path
    founder, pilot = copied["founder"], copied["pilot"]
    layout, genome = Layout.load(founder)
    equal(hashlib.sha256(genome.numpy().tobytes()).hexdigest(), baseline["founder_raw_sha256"], "raw founder")
    active = layout.active(genome).nonzero()[:, 0].tolist()
    equal(active, list(range(8)), "founder active gene slots")
    configs, seeds, lengths = {}, {}, {}
    for seed in RUNS:
        old = OmegaConf.load(ROOT / baseline["configs"][str(seed)]["path"])
        cfg = OmegaConf.create(OmegaConf.to_container(old, resolve=True))
        cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split = 0.02, 0.01, False
        cfg.evolve.seed_genome = str(founder.relative_to(ROOT))
        cfg.life.control = "pool_row38_structural_x3"
        cfg.logging.output_dir = str(STUDY / f"runs/s{seed}")
        changed = differences(OmegaConf.to_container(old), OmegaConf.to_container(cfg))
        equal(changed, ALLOWED_CONFIG_CHANGES, "allowed changes from D")
        ev = LifeEvaluator(cfg, layout)
        if not ev.fast or ev.has_envelope or ev.T_choices != (768, 1024, 1536):
            raise ValueError("G must retain D's fixed fast physics and duration choices")
        path = STUDY / f"configs/s{seed}.yaml"
        freeze(path, OmegaConf.to_yaml(cfg, resolve=True).encode())
        configs[str(seed)] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
        seeds[str(seed)] = run_seeds(seed)
        lengths[str(seed)] = [ev.draw("gen", g).worlds[0].T for g in range(16)]
    baseline_audit = json.loads((BASELINE / "seed_audit.json").read_text())
    equal(seeds, baseline_audit["run_life_seeds"], "shared D/G training and diagnostic seeds")
    equal(lengths, baseline["selection_durations"], "shared D/G selection durations")
    combined = [seed for values in seeds.values() for seed in values]
    if len(combined) != len(set(combined)) or any(51_000_000 <= seed < 52_000_000 for seed in combined):
        raise ValueError("unexpected training seed collision")
    if set(CONFIRM_SEEDS) & set(baseline_audit["confirm_seeds"]):
        raise ValueError("G/D confirmation seeds must be fresh relative to D confirmation")
    audit = {"run_life_seeds": seeds, "confirm_seeds": CONFIRM_SEEDS, "confirm_block": 93,
             "run_seeds_unique_and_cross_run_disjoint": True,
             "D_G_training_and_diagnostic_seeds_intentionally_shared": True,
             "D_G_initial_population_rng_intentionally_shared": True,
             "old_pilot_unique_seeds_checked": baseline_audit["old_pilot_unique_seeds_checked"],
             "old_pilot_overlap": baseline_audit["old_pilot_overlap"],
             "run_seed_overlap_reserved_decimal_51M_blocks_0_to_99": 0,
             "confirm_cross_duration_and_genotype_seeds_intentionally_shared": True,
             "half_final_seeds_intentionally_reuse_final0": True,
             "confirmation_block91_overlap": 0,
             "note": "Structural operator RNG draws change later crossover/mutation choices; "
                     "matching the run seed is not a pathwise isolated intervention after generation0."}
    freeze_json(STUDY / "seed_audit.json", audit)
    protocol = {"status": "prepared_not_started", "runs": list(RUNS), "generations": 16,
        "configs": configs, "founder_file": str(founder.relative_to(ROOT)), "founder_sha256": sha(founder),
        "founder_raw_sha256": baseline["founder_raw_sha256"], "pilot_file": str(pilot.relative_to(ROOT)),
        "pilot_sha256": sha(pilot), "archive_provenance_sha256": baseline["archive_provenance_sha256"],
        "input_sources": baseline["input_sources"], "source_identity": baseline["source_identity"],
        "expected_numerical_identity": baseline["expected_numerical_identity"],
        "D_study": str(BASELINE.relative_to(ROOT)),
        "D_pins": {"protocol.json": sha(BASELINE / "protocol.json"), "ready.json": sha(BASELINE / "ready.json"),
                   "run_budgeted.py": sha(BASELINE / "run_budgeted.py"),
                   "seed_audit.json": sha(BASELINE / "seed_audit.json")},
        "D_endpoint_rule": "Exactly final population rank 0 of each completed D generation 16 checkpoint; "
                           "genotype and checkpoint hashes are frozen in confirmation manifest, no reselection.",
        "selection_durations": lengths, "selection_genome_lives": 32768,
        "selection_T1024_equivalent_lives": sum(map(sum, lengths.values())),
        "periodic_valid_genome_lives": 160, "tiny_final_genome_lives": 12, "tiny_final_half_duration_lives": 4,
        "confirmation_genome_lives": 4608, "planned_genome_lives": 37548,
        "planned_genome_lives_including_neutrality_validation": 37566,
        "max_cpu_seconds": 14400, "max_simulation_threads": 4,
        "seed_audit_sha256": sha(STUDY / "seed_audit.json"), "prepare_sha256": sha(Path(__file__)),
        "structural_operators": {"dup_rate": 0.02, "del_rate": 0.01, "dup_split": False,
                                 "n_mut_scale": True, "existing_production_operators": True},
        "initialization": "One exact row38 founder plus 31 point-mutated copies, identical to D at each run seed; "
                          "production fill does not pass structural rates, so structural events start in offspring.",
        "population_loading": "No protected founder/best-ever archive; exact resume uses checkpoint.pt.",
        "confirmation": {"labels": LABELS, "seeds": CONFIRM_SEEDS, "seed_block": 93,
                         "durations": [768, 1024, 1536], "threads": 2,
                         "primary_pairs": [[4, 2], [5, 3]], "secondary_pairs": [[4, 1], [5, 1], [4, 0], [5, 0]],
                         "primary": "Paired G minus matched D endpoint, equal-duration average within each seed; "
                                    "SE over 256 shared seed clusters; both fixed replicates retained "
                                    "regardless of sign.",
                         "endpoint_rule": "Final population rank 0 from each completed 16-generation G checkpoint, "
                                          "frozen before independent confirmation; no validation-best selection."},
        "neutrality_validation": {"required_before_search": True, "genome_lives": 18,
                                  "seeds": [51_090_000, 51_090_001], "T": 1024,
                                  "active_source_slots": active, "destination_slot": 8, "split": False,
                                  "kernel": "full", "threads": 1, "max_cpu_seconds": 30,
                                  "cpu_included_in_study_cap": True, "raster_cap": 100000, "fate_cap": 8192,
                                  "reject_log_overflow": True,
                                  "world": "same fixed POOL-fast physics as G",
                                  "check": "Founder and each of 8 silent outgoing copies: all 57 ledger columns, "
                                           "5 hashes, "
                                           "spike times/UIDs and fate integer records match bitwise on both seeds. "
                                           "Fate float fields match except the new gene internal-state column, "
                                           "which must equal its copied source column bitwise.",
                                  "status": "prepared_not_executed"},
        "limitations": ["Two paired run seeds, not a general estimate of structural-search efficiency.",
                        "Matching seeds fixes initial populations and worlds; structural RNG draws diverge paths.",
                        "Same generations/evaluation counts are not matched CPU if evolved bodies cost different time.",
                        "Silent duplication is a neutral starting mutation; no behavior or ABI is hand-designed.",
                        "D endpoint outcomes are neither inspected nor used to choose this comparison at preparation."]}
    freeze_json(STUDY / "protocol.json", protocol)
    print(json.dumps({key: protocol[key] for key in ("status", "planned_genome_lives", "selection_durations",
                                                    "selection_T1024_equivalent_lives", "max_cpu_seconds")}, indent=2))


if __name__ == "__main__":
    main()
