"""Freeze two ordinary s7-row29 continuations and fresh seeds; no simulation or readiness marker."""
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

ARCHIVE = ROOT / "results/pool_mutants_20261013"
BASELINE = ROOT / "results/continuation_20261013"
RUNS = (51891, 51892)
LABELS = ["pilot_s7", "founder_row29", "s51891_final_rank0", "s51892_final_rank0"]
CONFIRM_SEEDS = list(range(51_900_000, 51_900_256))
DEPENDENCIES = ["outputs/autonomous_duplicate_use_20261014", "outputs/autonomous_traces_20261014"]
ALLOWED = {"seed", "evolve.seed_genome", "life.control", "logging.output_dir"}
HELPERS = ("taskvar_confirm.py", "taskvar_gradient.py", "taskvar_gates.py")
FOUNDER_RAW = "c34e8ec8dff4682b99d9ca0e090d226fa1733366fa8f4c84e5a1ce000bdeb358"


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
    spec = importlib.util.spec_from_file_location("L_frozen_D_seed_helper", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    prior = json.loads((ARCHIVE / "provenance.json").read_text())
    baseline = json.loads((BASELINE / "protocol.json").read_text())
    equal(prior["numerical_identity"], baseline["expected_numerical_identity"], "D/prior numerical pins")
    input_sources = {"founder": "genomes/s7_pool_winner.json", "pilot": "parents/s7/best_genome.json"}
    copied = {}
    for name, relative in input_sources.items():
        source = ARCHIVE / relative
        equal(sha(source), prior["artifacts"][relative]["sha256"], "archived " + name)
        target = STUDY / "inputs" / ("founder_row29.json" if name == "founder" else "pilot_s7.json")
        freeze(target, source.read_bytes())
        copied[name] = target
    for original, target in (("provenance.json", "prior_provenance.json"),
                             ("screens/s7_pool_T1024_b80/followup/selection.json", "original_selection.json"),
                             ("genomes/s7_pool.npy", "original_mutants.npy"),
                             ("genomes/s7_mutation_ops.json", "original_mutation_ops.json")):
        if original != "provenance.json":
            equal(sha(ARCHIVE / original), prior["artifacts"][original]["sha256"], "original evidence")
        freeze(STUDY / "inputs" / target, (ARCHIVE / original).read_bytes())
    original_selection = json.loads((STUDY / "inputs/original_selection.json").read_text())
    equal(original_selection["winner_genome_row"], 29, "original s7 POOL winner row")
    layout, founder = Layout.load(copied["founder"])
    _, pilot = Layout.load(copied["pilot"])
    raw_sha = hashlib.sha256(founder.numpy().tobytes()).hexdigest()
    equal(raw_sha, FOUNDER_RAW, "fixed row29 raw bytes")
    mutants = np.load(STUDY / "inputs/original_mutants.npy", allow_pickle=False)
    equal(mutants[29].tobytes(), founder.numpy().tobytes(), "whole original panel row29")
    equal(mutants[0].tobytes(), pilot.numpy().tobytes(), "whole original panel parent")
    sources = {str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT / "src").rglob("*.py"))}
    sources["src/life/kernel.c"] = sha(ROOT / "src/life/kernel.c")
    equal(sources, prior["numerical_identity"]["sources"], "unchanged numerical/search source")
    helpers = seed_helpers()
    configs, seed_lists, lengths, template_pins, initializations = {}, {}, {}, {}, {}
    for seed, old_seed in zip(RUNS, (51089, 51090)):
        source = BASELINE / f"configs/s{old_seed}.yaml"
        equal(sha(source), baseline["configs"][str(old_seed)]["sha256"], "D config template")
        old = OmegaConf.load(source)
        cfg = OmegaConf.create(OmegaConf.to_container(old, resolve=True))
        cfg.seed = seed
        cfg.evolve.seed_genome = str(copied["founder"].relative_to(ROOT))
        cfg.life.control = "pool_s7_row29_continuation"
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
    pilot_seeds = helpers.pilot_life_seeds()
    d_seeds = {value for old_seed in (51089, 51090) for value in helpers.run_life_seeds(old_seed)}
    equal(len(combined), 392, "training/diagnostic seed count")
    if (len(set(combined)) != 392 or set(combined) & (pilot_seeds | d_seeds)
            or any(51_000_000 <= value < 52_000_000 for value in combined)
            or set(CONFIRM_SEEDS) & (set(combined) | pilot_seeds | d_seeds)):
        raise ValueError("prospective seed namespaces overlap")
    audit = {"run_life_seeds": seed_lists, "confirm_seeds": CONFIRM_SEEDS, "confirm_block": 90,
             "old_pilot_unique_seeds_checked": len(pilot_seeds), "D_G_unique_seeds_checked": len(d_seeds),
             "run_seeds_unique_and_cross_run_disjoint": True, "old_pilot_overlap": 0, "D_G_overlap": 0,
             "run_seed_overlap_reserved_decimal_51M_blocks_0_to_99": 0,
             "run_seed_overlap_fresh_confirmation_block90": 0,
             "confirm_cross_duration_and_genotype_seeds_intentionally_shared": True,
             "half_final_seeds_intentionally_reuse_final0": True,
             "prior_namespace_search_receipt_sha256": sha(STUDY / "sources/source_seed_review.json")}
    freeze_json(STUDY / "seed_audit.json", audit)
    selection, valid, final, confirmation = 2 * 16 * (256 * 3 + 64 * 4), 2 * 5 * 16, 2 * 3 * 2, 4 * 3 * 256
    equal(selection + valid + final + confirmation, 36012, "planned genome-lives")
    protocol = {"status": "prepared_not_started", "runs": list(RUNS), "generations": 16, "configs": configs,
        "founder_file": str(copied["founder"].relative_to(ROOT)), "founder_sha256": sha(copied["founder"]),
        "founder_raw_sha256": raw_sha, "pilot_file": str(copied["pilot"].relative_to(ROOT)),
        "pilot_sha256": sha(copied["pilot"]), "archive_provenance_sha256": sha(ARCHIVE / "provenance.json"),
        "input_sources": {key: str((ARCHIVE / relative).relative_to(ROOT)) for key, relative in input_sources.items()},
        "inputs": {str(path.relative_to(STUDY)): sha(path) for path in sorted((STUDY / "inputs").iterdir())},
        "source_identity": sources, "expected_numerical_identity": prior["numerical_identity"],
        "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS},
        "template_pins": template_pins, "reference_sources": {
            str(path.relative_to(STUDY)): sha(path) for path in sorted((STUDY / "sources").iterdir())
            if path.is_file()},
        "selection_durations": lengths, "selection_genome_lives": selection,
        "selection_T1024_equivalent_lives": sum(map(sum, lengths.values())),
        "periodic_valid_genome_lives": valid, "tiny_final_genome_lives": final,
        "tiny_final_half_duration_lives": 4, "confirmation_genome_lives": confirmation,
        "planned_genome_lives": 36012, "max_cpu_seconds": 14400, "max_simulation_threads": 4,
        "seed_audit_sha256": sha(STUDY / "seed_audit.json"), "prepare_sha256": sha(Path(__file__)),
        "initialization_audit_sha256": sha(STUDY / "initialization.json"),
        "wait_for_studies": DEPENDENCIES,
        "initialization": "One exact original s7 row29 founder plus31 ordinary point-mutated copies, "
                          "followed by ordinary32+224 sexual evolution; no protected founder or best-ever archive.",
        "population_loading": "Exact resume uses checkpoint.pt; no automatic restart or budget reset is authorized.",
        "confirmation": {"labels": LABELS, "seeds": CONFIRM_SEEDS, "seed_block": 90,
            "durations": [768, 1024, 1536], "threads": 2, "primary_pairs": [[2, 1], [3, 1]],
            "secondary_pairs": [[2, 0], [3, 0]],
            "primary": "Each final endpoint minus row29, equal duration average within each of256 paired seeds; "
                       "SE across seeds. Both endpoints and both signs are retained.",
            "endpoint_rule": "Final population rank0 from each complete16-generation checkpoint; "
                             "frozen before independent confirmation, no validation-best reselection."},
        "limitations": ["Two fixed searches extend the s7 lineage; they do not estimate general reliability.",
            "The row29 founder was selected in the original nearby-mutant study, regardless of its weak confirmation.",
            "L does not compare s7 and s5 mutation-policy efficacy or condition on G/H/I/J/K outcomes.",
            "Periodic validation and tiny final diagnostics do not select confirmation endpoints.",
            "Fresh seed uncertainty describes fixed genomes, not variation across independent evolutionary searches.",
            "Guards/extinction retain production penalties; invalid capacity/accounting failures stop inference.",
            "The bounded study changes no world admission, in-life behavior, prices, channel, clock or ABI."]}
    freeze_json(STUDY / "protocol.json", protocol)
    print(json.dumps({key: protocol[key] for key in ("status", "planned_genome_lives", "selection_durations",
        "selection_T1024_equivalent_lives", "max_cpu_seconds")}, indent=2))


if __name__ == "__main__":
    main()
