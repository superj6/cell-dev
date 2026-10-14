"""Freeze U's two ordinary decoy searches and confirmation; pure genetics, zero simulated lives."""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True
STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402

from src.evolve import fill, setup  # noqa: E402
from src.genome import Layout  # noqa: E402
from src.life import spec  # noqa: E402
from src.life.evaluate import life_seed  # noqa: E402

ARCHIVE = ROOT / "results/decoy_gradient_20261014"
TEMPLATE = ROOT / "results/s7_continuation_20261014/configs/s51891.yaml"
RUNS = (53091, 53092)
MAPPING = {53091: ("s5", 32), 53092: ("s7", 1)}
LABELS = ["I_s5_row32", "I_s7_row1", "s53091_final_rank0", "s53092_final_rank0"]
SEEDS = list(range(52_060_000, 52_060_512))
CONDITIONS = ["trained", "width_swapped", "frozen", "frozen_lateral_off"]
HELPERS = ("taskvar_confirm.py", "taskvar_gradient.py", "taskvar_gates.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def freeze(path, data):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("frozen preparation differs: " + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def freeze_json(path, value):
    freeze(path, (json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def planned_search_seeds(run_seed):
    values = []
    for generation in range(4):
        values.extend(life_seed(run_seed, "gen", generation, j) for j in range(7))
        if generation in (0, 3):
            values.extend(life_seed(run_seed, "valid", generation, j) for j in range(16))
    for index in (0, 1):
        values.extend(life_seed(run_seed, "final", index, j) for j in range(2))
    return values


def checked_archive_file(relative, provenance):
    path = ARCHIVE / relative
    record = provenance["artifacts"][relative]
    if sha(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
        raise ValueError("completed I archive differs: " + relative)
    return path


def main():
    if (STUDY / "ready.json").exists() or (STUDY / "budget.json").exists():
        raise ValueError("released preparation cannot be regenerated")
    prior = json.loads((ARCHIVE / "provenance.json").read_text())
    summary = json.loads(checked_archive_file("summary.json", prior).read_text())
    original = json.loads(checked_archive_file("protocol.json", prior).read_text())
    budget = json.loads(checked_archive_file("operations/budget.json", prior).read_text())
    if summary["status"] != "complete" or budget["status"] != "complete" or budget.get("running") or budget.get("queued"):
        raise ValueError("I must be complete and inactive")
    expected_identity = original["expected_numerical_identity"]
    sources = {str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT / "src").rglob("*.py"))}
    sources["src/life/kernel.c"] = sha(ROOT / "src/life/kernel.c")
    if sources != expected_identity["sources"]:
        raise ValueError("numerical or search source differs from completed I")
    for relative in ("protocol.json", "summary.json", "measurement/selection.json", "operations/budget.json"):
        freeze(STUDY / "inputs/I" / relative, checked_archive_file(relative, prior).read_bytes())
    freeze(STUDY / "inputs/I/provenance.json", (ARCHIVE / "provenance.json").read_bytes())
    f_protocol = ROOT / "results/discrimination_20261013/protocol.json"
    if original["world"] != json.loads(f_protocol.read_text())["world"]:
        raise ValueError("F and I world differ")
    freeze(STUDY / "inputs/F_protocol.json", f_protocol.read_bytes())
    world = spec.World(**original["world"])
    expected_world = spec.world("catch_speck_l4", T=1024, d0=1.0, d_min=0.5, b2_amp=1.0,
                                b2_sigma=1.2, b2_value=-50.0, b2_p=1.0, b2_mode=1)
    if world != expected_world:
        raise ValueError("registered old-conduction decoy world differs")
    founders, founder_files, founder_audits = {}, {}, {}
    for seed, (parent, row) in MAPPING.items():
        for name in ("genomes.npy", "parent.json", "config.yaml", "mutation_ops.json", "original_screen_manifest.json"):
            relative = f"inputs/{parent}/{name}"
            freeze(STUDY / "inputs/I" / relative, checked_archive_file(relative, prior).read_bytes())
        layout, ancestor = Layout.load(STUDY / f"inputs/I/inputs/{parent}/parent.json")
        table = np.load(STUDY / f"inputs/I/inputs/{parent}/genomes.npy", allow_pickle=False)
        selected = summary["selection"][parent]
        if table.dtype != np.float32 or table.shape != (65, layout.size) or not np.isfinite(table).all():
            raise ValueError("I genome table differs")
        if table[0].tobytes() != ancestor.numpy().tobytes() or selected["genome_row"] != row:
            raise ValueError("fixed I founder mapping differs")
        founder = torch.from_numpy(table[row].copy())
        if raw_sha(founder.numpy()) != selected["raw_sha256"]:
            raise ValueError("fixed I founder raw hash differs")
        path = STUDY / f"inputs/founder_{parent}_row{row}.json"
        freeze_json(path, {"dims": layout.dims.__dict__, "params": layout.to_dict(founder)})
        if Layout.load(path)[1].numpy().tobytes() != table[row].tobytes():
            raise ValueError("founder JSON roundtrip differs")
        founders[seed], founder_files[seed] = founder, path
        founder_audits[str(seed)] = {"parent": parent, "I_row": row,
            "founder_file": str(path.relative_to(ROOT)), "file_sha256": sha(path),
            "raw_sha256": raw_sha(table[row]), "I_selection": selected}
    freeze_json(STUDY / "inputs/founder_audit.json", {"status": "passed", "simulated_lives": 0,
                                                     "fixed_mapping": founder_audits})
    template_prov = json.loads((TEMPLATE.parents[1] / "provenance.json").read_text())
    if sha(TEMPLATE) != template_prov["artifacts"][str(TEMPLATE.relative_to(TEMPLATE.parents[1]))]["sha256"]:
        raise ValueError("ordinary search template differs")
    freeze(STUDY / "sources/L_config.yaml", TEMPLATE.read_bytes())
    for name in HELPERS:
        freeze(STUDY / "sources/scripts" / name, (ROOT / "scripts" / name).read_bytes())
    configs, initializations, seed_lists = {}, {}, {}
    for seed in RUNS:
        cfg = OmegaConf.load(TEMPLATE)
        cfg.seed, cfg.threads = seed, 2
        cfg.evolve.generations = 4
        cfg.evolve.seed_genome = str(founder_files[seed].relative_to(ROOT))
        cfg.evolve.dup_rate, cfg.evolve.del_rate, cfg.evolve.dup_split = 0.0, 0.0, False
        cfg.logging.output_dir = str(STUDY / f"runs/s{seed}")
        cfg.logging.checkpoint_every = 1
        cfg.life.control = "ordinary_decoy_I_winner"
        cfg.life.T, cfg.life.T_choices = 1024, None
        cfg.world = {"d0": 1.0, "d_min": 0.5, "b2_amp": 1.0, "b2_sigma": 1.2,
                     "b2_value": -50.0, "b2_p": 1.0, "b2_mode": 1}
        _, layout, _, evaluator = setup(cfg)
        if asdict(evaluator.world()) != original["world"] or not evaluator.fast or evaluator.has_envelope:
            raise ValueError("production search world differs from completed F/I")
        if (cfg.evolve.mu, cfg.evolve.lam, cfg.life.lives, cfg.evolve.recheck_k,
                cfg.evolve.recheck_lives) != (32, 224, 3, 64, 4):
            raise ValueError("ordinary search selection scope differs")
        path = STUDY / f"configs/s{seed}.yaml"
        freeze(path, OmegaConf.to_yaml(cfg, resolve=True).encode())
        configs[str(seed)] = {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}
        seed_lists[str(seed)] = planned_search_seeds(seed)
        generator = torch.Generator().manual_seed(seed)
        before = raw_sha(generator.get_state().numpy())
        operations = []
        population = fill(founders[seed][None], 32, layout, generator, cfg.evolve, ops=operations).numpy()
        if population[0].tobytes() != founders[seed].numpy().tobytes() or len(operations) != 31:
            raise ValueError("ordinary initialization differs")
        if any(set(item) != {"mut"} or len(item["mut"]) != 2 for item in operations):
            raise ValueError("initialization must contain only two-point mutations")
        data = io.BytesIO()
        np.save(data, population, allow_pickle=False)
        initial = STUDY / f"initialization/s{seed}.npy"
        freeze(initial, data.getvalue())
        initializations[str(seed)] = {"shape": list(population.shape), "dtype": str(population.dtype),
            "population_file": str(initial.relative_to(STUDY)), "file_sha256": sha(initial),
            "population_raw_sha256": raw_sha(population),
            "row_raw_sha256": [raw_sha(row) for row in population],
            "generator_before_sha256": before, "generator_after_sha256": raw_sha(generator.get_state().numpy()),
            "founder_ids": [0], "copies": [{"id": i + 1, "parent": 0, "ops": item}
                                            for i, item in enumerate(operations)]}
    freeze_json(STUDY / "initialization.json", {"status": "pure_genetic_preparation", "simulated_lives": 0,
        "selection_use": "Receipt only; production regenerates initialization from the fixed founder.",
        "runs": initializations})
    independent = ROOT / "outputs/audit_decoy_evolution_20261014/seed_audit.json"
    audit = json.loads(independent.read_text())
    if audit["status"] != "passed" or audit["run_life_seeds"] != seed_lists or audit["confirm_seeds"] != SEEDS:
        raise ValueError("independent seed audit disagrees")
    freeze(STUDY / "seed_audit.json", independent.read_bytes())
    for name in ("namespace_lists.json", "check_seed_world.py"):
        freeze(STUDY / "sources/seed_review" / name, (independent.parent / name).read_bytes())
    protocol = {"status": "prepared_not_released", "study": "decoy_ordinary_evolution", "runs": list(RUNS),
        "generations": 4, "configs": configs, "founder_mapping": founder_audits,
        "reference_files": [str(founder_files[seed].relative_to(ROOT)) for seed in RUNS],
        "world": original["world"], "source_identity": sources, "expected_numerical_identity": expected_identity,
        "archive_provenance_sha256": sha(ARCHIVE / "provenance.json"),
        "inputs": {str(path.relative_to(STUDY)): sha(path) for path in sorted((STUDY / "inputs").rglob("*"))
                   if path.is_file()},
        "helpers": {name: sha(ROOT / "scripts" / name) for name in HELPERS},
        "reference_sources": {"PREREG.md": sha(STUDY / "PREREG.md"), **{
            str(path.relative_to(STUDY)): sha(path) for path in sorted((STUDY / "sources").rglob("*")) if path.is_file()}},
        "template_pins": {str(TEMPLATE.relative_to(ROOT)): sha(TEMPLATE)},
        "initialization_audit_sha256": sha(STUDY / "initialization.json"),
        "seed_audit_sha256": sha(STUDY / "seed_audit.json"), "prepare_sha256": sha(Path(__file__)),
        "selection_genome_lives": 8192, "periodic_valid_genome_lives": 64, "tiny_final_genome_lives": 12,
        "tiny_final_half_duration_lives": 4, "search_genome_lives": 8268,
        "confirmation_genome_lives": 8192, "planned_genome_lives": 16460,
        "startup_validation_genome_lives": 6,
        "startup_validation": "Each of two search processes and confirmation runs one T200 full/fast golden pair; "
                              "six validation lives separate from research, inside CPU cap. Preparation runs none.",
        "max_cpu_seconds": 7200, "search_cpu_seconds": 3600, "max_simulation_threads": 4,
        "confirmation": {"labels": LABELS, "seeds": SEEDS, "seed_block": 106, "conditions": CONDITIONS,
            "threads": 2, "primary_pairs": [[2, 0], [3, 1]], "fork_time": 512, "accounting_open": 544,
            "primary": "Each final rank0 minus its own fixed I founder in the trained world; paired SE over512seeds.",
            "endpoint_rule": "Both complete generation4 rank0 endpoints frozen together before confirmation.",
            "width_interaction": "(endpoint-founder) trained minus width_swapped, formed within each seed.",
            "lateral_interaction": "(endpoint-founder) frozen minus frozen_lateral_off, within each seed."},
        "initialization": "One exact I founder and31 ordinary point-mutated copies per lineage, then32+224 sexual "
                          "evolution; no protected founder, best-ever choice, duplication or deletion.",
        "failure_policy": "Any incomplete search, changed pin, invalid/mismatched life or missing confirmation arm "
                          "blocks complete-study inference. No replacement, partial inference, rescue or extension.",
        "limits": ["Two conditional founder continuations cannot estimate independent search reliability.",
            "Width reversal changes sensory geometry; an interaction is not pure discrimination or learning proof.",
            "Freeze stops growth and regulatory/phenotypic updates; fixed tissue is not proof of maturity.",
            "Lateral-off tests dependence under the registered freeze; it does not identify a circuit.",
            "Lower costs, less movement or fewer clicks can improve F without richer computation; report all ledgers.",
            "Life-level paired SEs describe fixed genotypes, not evolutionary replicate uncertainty.",
            "No organism rules, central channel/clock, ABI, prices, population-responsive world or injected behavior."]}
    freeze_json(STUDY / "protocol.json", protocol)
    print(json.dumps({"status": "prepared_not_released", "simulated_lives": 0,
                      "planned_genome_lives": 16460, "validation_lives_planned": 6,
                      "max_cpu_seconds": 7200, "search_cpu_seconds": 3600}))


if __name__ == "__main__":
    main()
