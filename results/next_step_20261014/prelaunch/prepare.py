"""Freeze two ordinary continuations from both fixed D endpoints and fresh seeds; no simulation or readiness marker."""
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
BASELINE = ROOT / "results/continuation_20261013"
RUNS = (52091, 52092)
LABELS = ["pilot_s5", "founder_row38", "D51089", "D51090", "s52091_final_rank0", "s52092_final_rank0"]
CONFIRM_SEEDS = list(range(52_020_000, 52_020_256))
DEPENDENCIES = ["outputs/autonomous_regulation_20261014"]
ALLOWED = {"seed", "evolve.seed_genome", "life.control", "logging.output_dir"}
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
    expected = json.loads((BASELINE / "provenance.json").read_text())["artifacts"]["operations/prepare.py"]["sha256"]
    equal(sha(source), expected, "frozen pure D seed helper")
    spec = importlib.util.spec_from_file_location("P_frozen_D_seed_helper", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if (STUDY / "ready.json").exists() or (STUDY / "budget.json").exists():
        raise ValueError("released preparation cannot be regenerated")
    prior = json.loads((ARCHIVE / "provenance.json").read_text())
    baseline = json.loads((BASELINE / "protocol.json").read_text())
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
    for seed, old_seed in FOUNDER_MAPPING.items():
        founder = founders[seed]
        source = BASELINE / f"configs/s{old_seed}.yaml"
        equal(sha(source), baseline["configs"][str(old_seed)]["sha256"], "D config template")
        old = OmegaConf.load(source)
        cfg = OmegaConf.create(OmegaConf.to_container(old, resolve=True))
        cfg.seed = seed
        cfg.evolve.seed_genome = str(founder_files[seed].relative_to(ROOT))
        cfg.life.control = "pool_D_final_continuation"
        cfg.logging.output_dir = str(STUDY / f"runs/s{seed}")
        equal(differences(OmegaConf.to_container(old), OmegaConf.to_container(cfg)), ALLOWED,
              "allowed D configuration changes")
        evaluator = LifeEvaluator(cfg, layout)
        if not evaluator.fast or evaluator.has_envelope or evaluator.T_choices != (768, 1024, 1536):
            raise ValueError("fixed fast POOL duration mixture differs")
        if cfg.evolve.dup_rate != 0 or cfg.evolve.del_rate != 0 or cfg.threads != 2:
            raise ValueError("ordinary point-only/two-thread policy differs")
        path = STUDY / f"configs/s{seed}.yaml"
        freeze(path, OmegaConf.to_yaml(cfg, resolve=True).encode())
        configs[str(seed)] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
        template_pins[str(source.relative_to(ROOT))] = sha(source)
        seed_lists[str(seed)] = helpers.run_life_seeds(seed)
        lengths[str(seed)] = [evaluator.draw("gen", generation).worlds[0].T for generation in range(16)]
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
    freeze_json(STUDY / "initialization.json", {"status": "pure_genetic_preparation", "simulated_lives": 0,
        "selection_use": "Receipt only; production constructs its ordinary initial population from the founder.",
        "runs": initializations})
    combined = [value for values in seed_lists.values() for value in values]
    receipt = json.loads((STUDY / "sources/source_seed_review.json").read_text())
    equal(receipt["status"], "passed", "independent namespace review")
    equal(receipt["run_life_seeds"], seed_lists, "independent search/diagnostic life IDs")
    equal(receipt["confirm_seeds"], CONFIRM_SEEDS, "independent block102 life IDs")
    equal(len(combined), 392, "training/diagnostic seed count")
    if len(set(combined)) != 392 or set(combined) & set(CONFIRM_SEEDS):
        raise ValueError("prospective own seed namespaces overlap")
    pilot_seeds = helpers.pilot_life_seeds()
    prior_hashed = {value for old_seed in (51089, 51090, 51891, 51892)
                    for value in helpers.run_life_seeds(old_seed)}
    if (set(combined) | set(CONFIRM_SEEDS)) & (pilot_seeds | prior_hashed):
        raise ValueError("prospective namespace overlaps pilot/D/G/L life IDs")
    audit = {"run_life_seeds": seed_lists, "confirm_seeds": CONFIRM_SEEDS, "confirm_block": 102,
             "old_pilot_unique_seeds_checked": len(pilot_seeds), "D_G_L_unique_seeds_checked": len(prior_hashed),
             "independent_F_through_O_review_sha256": sha(STUDY / "sources/source_seed_review.json"),
             "run_seeds_unique_and_cross_run_disjoint": True, "old_pilot_overlap": 0, "D_G_L_overlap": 0,
             "confirm_cross_duration_and_genotype_seeds_intentionally_shared": True,
             "half_final_seeds_intentionally_reuse_final0": True}
    freeze_json(STUDY / "seed_audit.json", audit)
    selection, valid, final, confirmation = 2 * 16 * (256 * 3 + 64 * 4), 2 * 5 * 16, 2 * 3 * 2, 6 * 3 * 256
    equal(selection + valid + final + confirmation, 37548, "planned genome-lives")
    protocol = {"status": "prepared_not_started", "runs": list(RUNS), "generations": 16, "configs": configs,
        "founder_mapping": founder_audits,
        "reference_files": [str(copied["pilot"].relative_to(ROOT)), str(copied["row38"].relative_to(ROOT)),
                            *[str(founder_files[seed].relative_to(ROOT)) for seed in RUNS]],
        "archive_provenance_sha256": sha(ARCHIVE / "provenance.json"),
        "inputs": {str(path.relative_to(STUDY)): sha(path) for path in sorted((STUDY / "inputs").rglob("*"))
                   if path.is_file()},
        "source_identity": sources, "expected_numerical_identity": prior["numerical_identity"],
        "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS},
        "template_pins": template_pins, "reference_sources": {"PREREG.md": sha(STUDY / "PREREG.md"), **{
            str(path.relative_to(STUDY)): sha(path) for path in sorted((STUDY / "sources").iterdir())
            if path.is_file()}},
        "selection_durations": lengths, "selection_genome_lives": selection,
        "selection_T1024_equivalent_lives": sum(map(sum, lengths.values())),
        "periodic_valid_genome_lives": valid, "tiny_final_genome_lives": final,
        "tiny_final_half_duration_lives": 4, "confirmation_genome_lives": confirmation,
        "planned_genome_lives": 37548, "max_cpu_seconds": 14400, "max_simulation_threads": 4,
        "seed_audit_sha256": sha(STUDY / "seed_audit.json"), "prepare_sha256": sha(Path(__file__)),
        "initialization_audit_sha256": sha(STUDY / "initialization.json"),
        "wait_for_studies": DEPENDENCIES,
        "initialization": "One exact assigned D generation16 rank0 founder plus31 ordinary point-mutated copies, "
                          "followed by ordinary32+224 sexual evolution; no protected founder or best-ever archive.",
        "population_loading": "Exact resume uses checkpoint.pt; no automatic restart or budget reset is authorized.",
        "confirmation": {"labels": LABELS, "seeds": CONFIRM_SEEDS, "seed_block": 102,
            "durations": [768, 1024, 1536], "threads": 2, "primary_pairs": [[4, 2], [5, 3]],
            "secondary_pairs": [[4, 1], [5, 1], [4, 0], [5, 0]],
            "primary": "Each final endpoint minus its assigned D founder, equal duration average within each of256 "
                       "paired seeds; "
                       "SE across seeds. Both endpoints and both signs are retained.",
            "endpoint_rule": "Final population rank0 from each complete16-generation checkpoint; "
                             "frozen before independent confirmation, no validation-best reselection."},
        "limitations": ["Two fixed D lineages receive another seeded search step; "
                        "this does not estimate general reliability.",
            "Both D founders were fixed before H/L/M/N/O outcomes; no mechanistic or result-based founder selection.",
            "These are new seeded populations, not resumed D populations or RNG streams.",
            "Periodic validation at g0,4,8,12,15 and tiny final diagnostics never select confirmation endpoints.",
            "Fresh life SE describes fixed genotypes, not variation across evolutionary searches.",
            "Guards/extinction retain production penalties; invalid capacity/accounting failures stop inference.",
            "A missing search endpoint or confirmation role makes the entire study incomplete; "
            "no replacement or extension.",
            "More developed founders may cost more per life; completion within the fixed CPU ceiling is not promised.",
            "No world admission, organism behavior, price, channel, clock, ABI or mutation-policy change is made."]}
    freeze_json(STUDY / "protocol.json", protocol)
    print(json.dumps({key: protocol[key] for key in ("status", "planned_genome_lives", "selection_durations",
        "selection_T1024_equivalent_lives", "max_cpu_seconds")}, indent=2))


if __name__ == "__main__":
    main()
