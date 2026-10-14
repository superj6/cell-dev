"""Prepare the fixed selection-life-budget comparison against P; no simulation or readiness marker."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402

from src.evolve import fill, setup  # noqa: E402
from src.genome import Layout  # noqa: E402
from src.life.evaluate import LifeEvaluator  # noqa: E402

ARCHIVE = ROOT / "results/continuation_20261013"
BASELINE = ROOT / "results/next_step_20261014"
P_WORK = ROOT / "outputs/autonomous_next_step_20261014"
RUNS = (52091, 52092)
LABELS = ["D51089", "D51090", "P52091", "P52092", "S52091_final_rank0", "S52092_final_rank0"]
CONFIRM_SEEDS = list(range(52_050_000, 52_050_256))
DEPENDENCIES = ["outputs/autonomous_weight_updates_20261014"]
ALLOWED = {"evolve.generations", "life.lives", "evolve.recheck_lives",
           "evolve.seed_genome", "life.control", "logging.output_dir"}
HELPERS = ("taskvar_confirm.py", "taskvar_gradient.py", "taskvar_gates.py")
FOUNDER_MAPPING = {52091: 51089, 52092: 51090}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(label + " differs")


def freeze(path, value):
    path = Path(path)
    if path.exists():
        equal(path.read_bytes(), value, "frozen preparation " + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(value)
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


def seed_helpers():
    source = STUDY / "sources/D_prepare.py"
    expected = json.loads((ARCHIVE / "provenance.json").read_text())["artifacts"]["operations/prepare.py"]["sha256"]
    equal(sha(source), expected, "frozen pure D seed helper")
    spec = importlib.util.spec_from_file_location("P_frozen_D_seed_helper", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_life_seeds(seed):
    from src.life import spec

    def life(purpose, index, j):
        return spec.hash64(seed, 0x4C494645 + purpose, index, j)

    values = []
    for generation in range(8):
        values.extend(life(1, generation, j) for j in range(14))
        if generation % 4 == 0 or generation == 7:
            values.extend(life(3, generation, j) for j in range(16))
    for index in (0, 1):
        values.extend(life(5, index, j) for j in range(2))
    return values


def main():
    if (STUDY / "ready.json").exists() or (STUDY / "budget.json").exists():
        raise ValueError("released preparation cannot be regenerated")
    prior = json.loads((ARCHIVE / "provenance.json").read_text())
    baseline = json.loads((ARCHIVE / "protocol.json").read_text())
    p_protocol = json.loads((P_WORK / "protocol.json").read_text())
    equal(sha(P_WORK / "protocol.json"),
          "2b4628a0ef6c2bef186641e5302eae9eaa1c41a98c1aa7218e9c95c378c70cfa", "fixed P protocol")
    equal(sha(P_WORK / "initialization.json"), p_protocol["initialization_audit_sha256"],
          "P prospective initialization receipt")
    equal(sha(STUDY / "sources/P_analyze.py"),
          "5bc3f2cf941b71b8df91a8dee69fdb73a915d83764f7b2ff9820419216510196", "reviewed P offline auditor")
    p_initial = json.loads((P_WORK / "initialization.json").read_text())
    equal(prior["numerical_identity"], baseline["expected_numerical_identity"], "D/prior numerical pins")
    from src import checkpoint

    for relative, record in prior["artifacts"].items():
        equal(sha(ARCHIVE / relative), record["sha256"], "completed D artifact " + relative)
        equal((ARCHIVE / relative).stat().st_size, record["bytes"], "completed D artifact size " + relative)
    budget = json.loads((ARCHIVE / "operations/budget.json").read_text())
    if budget["status"] != "complete" or budget.get("running") or budget.get("queued"):
        raise ValueError("both D searches must be complete")
    files = ["protocol.json", "provenance.json", "operations/budget.json"]
    for old_seed in FOUNDER_MAPPING.values():
        files += [f"configs/s{old_seed}.yaml", *[f"runs/s{old_seed}/{name}" for name in
                  ("checkpoint.pt", "best_genome.json", "lineage.jsonl")]]
    for relative in files:
        freeze(STUDY / "inputs/D" / relative, (ARCHIVE / relative).read_bytes())
    for relative in ("protocol.json", "initialization.json", "configs/s52091.yaml", "configs/s52092.yaml",
                     "initialization/s52091.npy", "initialization/s52092.npy"):
        freeze(STUDY / "inputs/P_preparation" / relative, (P_WORK / relative).read_bytes())
    copied = {}
    for name, relative in (("row38", "inputs/founder_row38.json"), ("pilot", "inputs/pilot_s5.json")):
        copied[name] = STUDY / relative
        freeze(copied[name], (ARCHIVE / relative).read_bytes())
    layout, row38 = Layout.load(copied["row38"])
    helper_path = STUDY / "sources/G_audit_search.py"
    equal(sha(helper_path), "8fd717bdecb5f0e073e04838bbf286a4a968924bc9848b55c5a8d2b2055f4139", "genetic audit")
    loader = importlib.util.spec_from_file_location("P_existing_genetic_audit", helper_path)
    auditor = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(auditor)
    founders, founder_files, founder_audits = {}, {}, {}
    for seed, old_seed in FOUNDER_MAPPING.items():
        folder = ARCHIVE / f"runs/s{old_seed}"
        saved = checkpoint.load(folder / "checkpoint.pt")
        checkpoint.validate(saved, OmegaConf.load(ARCHIVE / f"configs/s{old_seed}.yaml"),
                            baseline["expected_numerical_identity"])
        state = saved["state"]
        if state["generation"] != 16 or [r["gen"] for r in state["curves"]] != list(range(16)):
            raise ValueError("fixed D founder is not its completed generation16 rank0")
        health = {key: max(r[key] for r in state["curves"])
                  for key in ("pop_invalid", "pop_mismatch", "recheck_invalid")}
        if any(health.values()):
            raise ValueError("D founder source has invalid or mismatched search lives")
        actual_layout, founder = Layout.load(folder / "best_genome.json")
        if actual_layout.dims != layout.dims or founder.numpy().tobytes() != state["population"][0].numpy().tobytes():
            raise ValueError("fixed D founder differs from its final rank0")
        lines = [json.loads(line) for line in (folder / "lineage.jsonl").read_text().splitlines() if line.strip()]
        replay = auditor.replay_genetics(lines, state, layout, row38, structural=False)
        target = STUDY / f"inputs/founder_D{old_seed}.json"
        freeze(target, (folder / "best_genome.json").read_bytes())
        founders[seed], founder_files[seed] = founder, target
        founder_audits[str(seed)] = {"D_run": old_seed, "final_generation": 16, "final_rank": 0,
            "founder_file": str(target.relative_to(ROOT)), "file_sha256": sha(target),
            "raw_sha256": hashlib.sha256(founder.numpy().tobytes()).hexdigest(),
            "checkpoint_sha256": sha(folder / "checkpoint.pt"), "lineage_sha256": sha(folder / "lineage.jsonl"),
            "health": health, "genetic_replay": replay}
    freeze_json(STUDY / "inputs/founder_audit.json", {"status": "passed", "simulated_lives": 0,
                                                     "fixed_mapping": founder_audits})
    sources = {str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT / "src").rglob("*.py"))}
    sources["src/life/kernel.c"] = sha(ROOT / "src/life/kernel.c")
    equal(sources, prior["numerical_identity"]["sources"], "unchanged numerical/search source")
    helpers = seed_helpers()
    configs, seed_lists, lengths, template_pins, initializations = {}, {}, {}, {}, {}
    for seed in FOUNDER_MAPPING:
        founder = founders[seed]
        source = BASELINE / f"configs/s{seed}.yaml"
        equal(sha(source), p_protocol["configs"][str(seed)]["sha256"], "P config template")
        old = OmegaConf.load(source)
        cfg = OmegaConf.create(OmegaConf.to_container(old, resolve=True))
        cfg.evolve.generations = 8
        cfg.life.lives = 6
        cfg.evolve.recheck_lives = 8
        cfg.evolve.seed_genome = str(founder_files[seed].relative_to(ROOT))
        cfg.life.control = "pool_fixed_selection_life_budget"
        cfg.logging.output_dir = str(STUDY / f"runs/s{seed}")
        equal(differences(OmegaConf.to_container(old), OmegaConf.to_container(cfg)), ALLOWED,
              "allowed P scoring-budget configuration changes")
        evaluator = LifeEvaluator(cfg, layout)
        if not evaluator.fast or evaluator.has_envelope or evaluator.T_choices != (768, 1024, 1536):
            raise ValueError("fixed fast POOL duration mixture differs")
        if cfg.evolve.dup_rate != 0 or cfg.evolve.del_rate != 0 or cfg.threads != 2:
            raise ValueError("ordinary point-only/two-thread policy differs")
        path = STUDY / f"configs/s{seed}.yaml"
        freeze(path, OmegaConf.to_yaml(cfg, resolve=True).encode())
        configs[str(seed)] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
        template_pins[str(source.relative_to(ROOT))] = sha(source)
        seed_lists[str(seed)] = run_life_seeds(seed)
        lengths[str(seed)] = [evaluator.draw("gen", generation).worlds[0].T for generation in range(8)]
        # Exact production initialization is a pure genetic operation, never a life evaluation.
        _, production_layout, _, _ = setup(cfg)
        generator = torch.Generator().manual_seed(seed)
        start_rng = hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest()
        operations = []
        population = fill(founder[None], 32, production_layout, generator, cfg.evolve, ops=operations).numpy()
        equal(population[0].tobytes(), founder.numpy().tobytes(), "exact initial founder")
        if len(operations) != 31 or any(set(item) != {"mut"} or len(item["mut"]) != 2 for item in operations):
            raise ValueError("initial fill differs from31 ordinary point-mutated copies")
        data = io.BytesIO()
        np.save(data, population, allow_pickle=False)
        initial_path = STUDY / f"initialization/s{seed}.npy"
        freeze(initial_path, data.getvalue())
        initializations[str(seed)] = {"shape": list(population.shape), "dtype": str(population.dtype),
            "population_file": str(initial_path.relative_to(STUDY)), "file_sha256": sha(initial_path),
            "population_raw_sha256": hashlib.sha256(population.tobytes()).hexdigest(),
            "row_raw_sha256": [hashlib.sha256(row.tobytes()).hexdigest() for row in population],
            "generator_before_sha256": start_rng,
            "generator_after_sha256": hashlib.sha256(generator.get_state().numpy().tobytes()).hexdigest(),
            "founder_ids": [0], "copies": [
                {"id": i + 1, "parent": 0, "ops": item} for i, item in enumerate(operations)]}
        equal(initializations[str(seed)], p_initial["runs"][str(seed)], "byte-exact P initialization receipt")
        equal(sha(initial_path), sha(P_WORK / p_initial["runs"][str(seed)]["population_file"]),
              "identical P initialized population file")
    freeze_json(STUDY / "initialization.json", {"status": "pure_genetic_preparation", "simulated_lives": 0,
        "selection_use": "Receipt only; production constructs its ordinary initial population from the founder.",
        "runs": initializations})
    combined = [value for values in seed_lists.values() for value in values]
    receipt = json.loads((STUDY / "sources/source_seed_review.json").read_text())
    equal(receipt["status"], "passed", "independent namespace review")
    equal(receipt["run_life_seeds"], seed_lists, "independent search/diagnostic life IDs")
    equal(receipt["confirm_seeds"], CONFIRM_SEEDS, "independent block105 life IDs")
    equal(len(combined), 328, "training/diagnostic seed count")
    if len(set(combined)) != 328 or set(combined) & set(CONFIRM_SEEDS):
        raise ValueError("prospective own seed namespaces overlap")
    pilot_seeds = helpers.pilot_life_seeds()
    prior_hashed = {value for old_seed in (51089, 51090, 51891, 51892)
                    for value in helpers.run_life_seeds(old_seed)}
    if (set(combined) | set(CONFIRM_SEEDS)) & (pilot_seeds | prior_hashed):
        raise ValueError("prospective namespace overlaps pilot/D/G/L life IDs")
    p_ids = {value for seed in RUNS for value in helpers.run_life_seeds(seed)}
    equal(len(set(combined) & p_ids), 184, "intentional P/S shared seed IDs")
    equal(len(set(combined) - p_ids), 144, "new S seed IDs")
    for seed in RUNS:
        equal(lengths[str(seed)], receipt["duration_schedules"][str(seed)]["S"], "independent duration schedule")
        independent = receipt["initialization_audits"][str(seed)]
        for key in ("population_raw_sha256", "generator_before_sha256", "generator_after_sha256"):
            equal(initializations[str(seed)][key], independent[key], "independent exact initialization " + key)
    audit = {"run_life_seeds": seed_lists, "confirm_seeds": CONFIRM_SEEDS, "confirm_block": 105,
             "old_pilot_unique_seeds_checked": len(pilot_seeds), "D_G_L_unique_seeds_checked": len(prior_hashed),
             "independent_through_R_review_sha256": sha(STUDY / "sources/source_seed_review.json"),
             "run_seeds_unique_and_cross_run_disjoint": True, "old_pilot_overlap": 0, "D_G_L_overlap": 0,
             "confirm_cross_duration_and_genotype_seeds_intentionally_shared": True,
             "half_final_seeds_intentionally_reuse_final0": True,
             "intentional_shared_P_ids": sorted(set(combined) & p_ids), "new_S_unique_ids": 144,
             "P_overlap_role_classification": receipt["intentional_P_overlap"]}
    freeze_json(STUDY / "seed_audit.json", audit)
    selection, valid, final, confirmation = 2 * 8 * (256 * 6 + 64 * 8), 2 * 3 * 16, 2 * 3 * 2, 6 * 3 * 256
    equal(selection + valid + final + confirmation, 37484, "planned genome-lives")
    protocol = {"status": "prepared_not_started", "runs": list(RUNS), "generations": 8, "configs": configs,
        "founder_mapping": founder_audits,
        "reference_labels": LABELS[:4],
        "reference_files": ["genome_D51089.json", "genome_D51090.json",
                            "genome_P52091.json", "genome_P52092.json"],
        "P_study": str(P_WORK.relative_to(ROOT)),
        "P_pins": {name: sha(P_WORK / name) for name in ("protocol.json", "run_budgeted.py")},
        "P_analysis_sha256": sha(STUDY / "sources/P_analyze.py"),
        "archive_provenance_sha256": sha(ARCHIVE / "provenance.json"),
        "inputs": {str(path.relative_to(STUDY)): sha(path) for path in sorted((STUDY / "inputs").rglob("*"))
                   if path.is_file()},
        "source_identity": sources, "expected_numerical_identity": prior["numerical_identity"],
        "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS},
        "template_pins": template_pins, "reference_sources": {"PREREG.md": sha(STUDY / "PREREG.md"), **{
            str(path.relative_to(STUDY)): sha(path) for path in sorted((STUDY / "sources").iterdir())
            if path.is_file()}},
        "selection_durations": lengths, "selection_genome_lives": selection,
        "selection_T1024_equivalent_lives": 2 * sum(map(sum, lengths.values())),
        "periodic_valid_genome_lives": valid, "tiny_final_genome_lives": final,
        "tiny_final_half_duration_lives": 4, "confirmation_genome_lives": confirmation,
        "planned_genome_lives": 37484, "max_cpu_seconds": 14400, "max_simulation_threads": 4,
        "seed_audit_sha256": sha(STUDY / "seed_audit.json"), "prepare_sha256": sha(Path(__file__)),
        "initialization_audit_sha256": sha(STUDY / "initialization.json"),
        "wait_for_studies": DEPENDENCIES,
        "dependencies": {relative: {name: sha(ROOT / relative / name)
                         for name in ("protocol.json", "run_budgeted.py")} for relative in DEPENDENCIES},
        "initialization": "One exact assigned D generation16 rank0 founder plus31 ordinary point-mutated copies, "
                          "followed by ordinary32+224 sexual evolution; no protected founder or best-ever archive.",
        "population_loading": "Exact resume uses checkpoint.pt; no automatic restart or budget reset is authorized.",
        "confirmation": {"labels": LABELS, "seeds": CONFIRM_SEEDS, "seed_block": 105,
            "durations": [768, 1024, 1536], "threads": 2, "primary_pairs": [[4, 2], [5, 3]],
            "secondary_pairs": [[4, 0], [5, 1], [2, 0], [3, 1]],
            "primary": "Each S endpoint minus its matched P endpoint, equal duration average within each of 256 "
                       "paired seeds; SE across seeds. Both pairs and both signs are retained.",
            "endpoint_rule": "P final population rank0 at generation16 and S rank0 at generation8; "
                             "both P references frozen before either S search, all six before confirmation."},
        "policy_comparison": {"P": {"generations": 16, "initial_lives": 3, "recheck_lives": 4},
                              "S": {"generations": 8, "initial_lives": 6, "recheck_lives": 8},
                              "selection_lives_per_branch_each_policy": 16384,
                              "equal_selection_genome_lives_not_equal_CPU": True,
                              "initial_population_and_rng_receipt_identical_to_P": True,
                              "P_selection_durations": p_protocol["selection_durations"],
                              "P_selection_T1024_equivalent_lives": p_protocol["selection_T1024_equivalent_lives"],
                              "duration_exposure_by_run": receipt["duration_schedules"]},
        "limitations": ["Only two fixed D founder/run-seed pairs; not an estimate of general policy reliability.",
            "The policies spend equal selection genome-lives, not equal actual CPU time or duration-adjusted lives.",
            "S uses the first eight duration draws while P uses sixteen; the duration mixture can differ.",
            "Identical initial populations and genetics RNG states do not preserve later trajectories "
            "after selection diverges.",
            "P/S initial/recheck life IDs intentionally overlap, including changed stage roles; "
            "validation/final IDs also overlap.",
            "Fresh confirmation block105 is separate from all training, validation and prior/prepared "
            "confirmation IDs.",
            "Fresh life SE describes fixed endpoint genotypes, not uncertainty across evolutionary searches.",
            "Both P endpoints are audited and frozen before either S search; no P outcome-based founder replacement.",
            "Periodic validation at g0,4,7 and tiny final diagnostics never select confirmation endpoints.",
            "Guards/extinction retain production penalties; invalid capacity/accounting failures stop inference.",
            "Any missing P/S endpoint or confirmation role makes the whole comparison incomplete; "
            "no replacement or extension.",
            "A fixed 14400 CPU-second ceiling does not promise completion; all actual monitored CPU is reported.",
            "No world admission, organism behavior, price, channel, clock, ABI or mutation-policy change is made."]}
    freeze_json(STUDY / "protocol.json", protocol)
    print(json.dumps({key: protocol[key] for key in ("status", "planned_genome_lives", "selection_durations",
        "selection_T1024_equivalent_lives", "max_cpu_seconds")}, indent=2))


if __name__ == "__main__":
    main()
