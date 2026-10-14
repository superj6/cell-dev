"""A fixed existing mutant panel in the ABI-3 decoy world; no simulation without --run."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
sys.dont_write_bytecode = True
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists())
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402

from scripts.taskvar_confirm import atomic_json, compare_rows, select_top, sha  # noqa: E402
from scripts.taskvar_gates import paired  # noqa: E402
from scripts.taskvar_second_step import RowStore, freeze  # noqa: E402
from src.checkpoint import numerical_identity  # noqa: E402
from src.genome import Layout  # noqa: E402
from src.life import spec  # noqa: E402
from src.life.evaluate import LifeEvaluator  # noqa: E402

STUDY = ROOT / "outputs/autonomous_decoy_gradient_20261014"
PARENTS = ("s5", "s7")
BLOCKS = {"screen": 95, "rescore": 96, "confirm": 97}
LIVES = {"screen": 32, "rescore": 512, "confirm": 512}
WORLD_OVERRIDES = dict(T=1024, d0=1.0, d_min=0.5, b2_amp=1.0, b2_sigma=1.2,
                       b2_value=-50.0, b2_p=1.0, b2_mode=1)
HELPERS = ("taskvar_confirm.py", "taskvar_second_step.py", "taskvar_gradient.py", "taskvar_gates.py")


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def stage_seeds():
    values = {name: list(range(51_000_000 + 10_000 * block, 51_000_000 + 10_000 * block + LIVES[name]))
              for name, block in BLOCKS.items()}
    combined = sum(values.values(), [])
    if len(set(combined)) != len(combined):
        raise ValueError("registered stages overlap")
    return values


def read_json(path):
    return json.loads(path.read_text())


def load_inputs(study):
    protocol = read_json(study / "protocol.json")
    for relative, expected in protocol["input_sha256"].items():
        if sha(study / relative) != expected:
            raise ValueError("fixed input differs: " + relative)
    prior = read_json(study / "inputs/prior_provenance.json")
    identity = prior["numerical_identity"]
    if identity != protocol["expected_numerical_identity"]:
        raise ValueError("numerical identity differs from fixed panel")
    world = spec.world("catch_speck_l4", **WORLD_OVERRIDES)
    if asdict(world) != protocol["world"] or protocol["world"] != read_json(study / "inputs/F_protocol.json")["world"]:
        raise ValueError("diagnostic world differs from F's fixed ABI-3 decoy world")
    genomes, configs = {}, {}
    for parent in PARENTS:
        prefix = study / "inputs" / parent
        table = np.load(prefix / "genomes.npy", allow_pickle=False)
        manifest = read_json(prefix / "original_screen_manifest.json")
        layout, ancestor = Layout.load(str(prefix / "parent.json"))
        if (table.dtype != np.float32 or table.shape != (65, layout.size)
                or not np.isfinite(table).all() or table[0].tobytes() != ancestor.reshape(-1).numpy().tobytes()):
            raise ValueError("panel must contain the unchanged parent plus all 64 fixed mutants")
        if raw_sha(table) != manifest["genomes_sha256"] or manifest["mutants"] != 64:
            raise ValueError("panel differs from its original generation manifest")
        if sha(prefix / "parent.json") != manifest["parent_sha256"]:
            raise ValueError("parent differs from original panel")
        if sha(prefix / "config.yaml") != manifest["config_sha256"]:
            raise ValueError("parent config differs from original panel")
        if manifest["numerical_identity"] != identity:
            raise ValueError("panel identities disagree")
        if manifest["runner_sha256"] != sha(ROOT / "scripts/taskvar_gradient.py"):
            raise ValueError("original mutation helper changed")
        genomes[parent], configs[parent] = table, (layout, prefix / "config.yaml")
    return protocol, genomes, configs, world


def select_winner(rows, selected):
    if len(selected) != 4 or len(set(selected)) != 4 or 0 in selected:
        raise ValueError("rescore needs exactly four distinct mutant rows")
    for index in selected:
        scores = np.asarray(rows[index]["F"])
        if scores.ndim != 1 or len(scores) < 2 or not np.isfinite(scores).all():
            raise ValueError("rescore requires finite paired rows")
    return min(selected, key=lambda i: (-float(rows[i]["F"].mean()), i))


def sign(value):
    return "positive" if value["mean"] > 3 * value["se"] else (
        "negative" if value["mean"] < -3 * value["se"] else "unresolved")


def screen_report(rows):
    values = np.stack([rows[i]["F"] for i in range(65)])
    differences = values[1:] - values[0]
    estimates = [paired(d, np.zeros_like(d)) for d in differences]
    return {"mutant_count": 64, "paired_estimates": estimates,
            "positive_mean_fraction": float(np.mean([x["mean"] > 0 for x in estimates])),
            "positive_above_3se_fraction": float(np.mean([x["mean"] > 3 * x["se"] for x in estimates])),
            "fraction_limit": "Fixed 64-mutant panel, reused in other worlds; descriptive, no multiplicity correction."}


def comparison(winner, parent, world):
    report = compare_rows(winner, parent, world)
    window = world.T - world.t_open
    pieces = {
        "capture_income": world.R_cap * (winner["captures"] - parent["captures"]) / window,
        "poison_cost_saving": spec.b2_cost(world) * (parent["b2_clicks"] - winner["b2_clicks"]) / window,
        "miss_cost_saving": world.c_miss * (parent["misses"] - winner["misses"]) / window,
    }
    pieces["other_cost_saving"] = (parent["cost"] - winner["cost"]) / window - (
        pieces["poison_cost_saving"] + pieces["miss_cost_saving"])
    pieces["guard_charge_saving"] = (parent["guard_charge"] - winner["guard_charge"]) / window
    pieces["extinction_charge_saving"] = parent["extinct_charge"] - winner["extinct_charge"]
    residual = winner["F"] - parent["F"] - sum(pieces.values())
    if not np.allclose(residual, 0, atol=1e-9, rtol=0):
        raise ValueError("capture/poison/miss accounting does not reconstruct paired fitness")
    report["decoy_fitness_contributions"] = {key: paired(value, np.zeros_like(value))
                                             for key, value in pieces.items()}
    report["decoy_fitness_contributions"]["residual"] = paired(residual, np.zeros_like(residual))
    report["b2_clicks"] = paired(winner["b2_clicks"], parent["b2_clicks"])
    report["primary"] = {**report["F"], "direction_above_3se": sign(report["F"]),
                         "above_3se": report["F"]["mean"] > 3 * report["F"]["se"],
                         "at_least_0p5": report["F"]["mean"] >= 0.5}
    return report


def validate_cache(store, parent, protocol):
    """Prevent an unexplained cache row from being used as a different stage or candidate."""
    allowed = {f"{stage}/row_{i:04d}.npz" for stage in BLOCKS for i in range(65)}
    if set(store.index) - allowed:
        raise ValueError("unexpected cached row path for " + parent)
    manifest = store.out.parent / "manifest.json"
    if not manifest.exists() and store.index:
        raise ValueError("cached rows lack a pinned manifest")
    if protocol["max_cpu_seconds"] != 3600 or protocol["simulation_workers"] != 2:
        raise ValueError("registered resource budget changed")


def run(study=STUDY):
    protocol, genomes, configs, world = load_inputs(study)
    for relative, expected in protocol["source_identity"].items():
        if sha(ROOT / relative) != expected:
            raise ValueError("source changed: " + relative)
    for name, expected in protocol["helpers"].items():
        if sha(ROOT / "scripts" / name) != expected:
            raise ValueError("helper changed: " + name)
    identity = numerical_identity()
    if identity != protocol["expected_numerical_identity"]:
        raise ValueError("runtime numerical identity differs from the fixed panel")
    out = study / "measurement"
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "manifest.json").exists() and any(out.rglob("*.npz")):
        raise ValueError("unexplained scientific rows without a manifest")
    seeds = stage_seeds()
    manifest = {"format": 1, "protocol_sha256": sha(study / "protocol.json"),
                "runner_sha256": sha(Path(__file__)), "numerical_identity": identity,
                "world": asdict(world), "seeds": seeds, "seed_blocks": BLOCKS,
                "genomes_sha256": {key: raw_sha(value) for key, value in genomes.items()},
                "helpers": protocol["helpers"], "input_sha256": protocol["input_sha256"]}
    freeze(out / "manifest.json", manifest, "measurement source, inputs, world, seeds or numerical identity")
    stores = {}
    for parent in PARENTS:
        layout, config_path = configs[parent]
        evaluator = LifeEvaluator(OmegaConf.load(config_path), layout)
        stores[parent] = RowStore(out / parent, genomes[parent], world, evaluator, 2, 3600)
        validate_cache(stores[parent], parent, protocol)
    report = {"status": "incomplete", "report_only": True, "planned_genome_lives": 11328,
              "screen": {}, "rescore": {}, "confirmation": {}, "selection": {}}
    selected = {}
    for parent in PARENTS:
        rows = stores[parent].stage("screen", list(range(65)), seeds["screen"])
        selected[parent] = select_top(np.stack([rows[i]["F"] for i in range(65)]))
        if len(selected[parent]) != 4:
            raise ValueError("screen did not choose exactly four mutant rows")
        report["screen"][parent] = screen_report(rows)
        atomic_json(out / "report.json", report)
    freeze(out / "shortlist.json", selected, "screen shortlists")
    winners = {}
    for parent in PARENTS:
        rows = stores[parent].stage("rescore", [0, *selected[parent]], seeds["rescore"])
        chosen = select_winner(rows, selected[parent])
        winners[parent] = {"genome_row": chosen, "raw_sha256": raw_sha(genomes[parent][chosen]),
                           "source_genome_row": chosen, "mutant_index": chosen - 1}
        report["rescore"][parent] = {str(i): comparison(rows[i], rows[0], world) for i in selected[parent]}
        atomic_json(out / "report.json", report)
    freeze(out / "selection.json", winners, "both rescore winners before fresh confirmation")
    report["selection"] = winners
    for parent in PARENTS:
        chosen = winners[parent]["genome_row"]
        rows = stores[parent].stage("confirm", [0, chosen], seeds["confirm"])
        report["confirmation"][parent] = comparison(rows[chosen], rows[0], world)
        atomic_json(out / "report.json", report)
    report.update(status="complete", scientific_genome_lives=11328,
                  row_cpu_seconds=sum(store.cpu_seconds for store in stores.values()),
                  limitations=["All 64 mutants per parent are reused without filtering on other-world outcomes.",
                               "The selected mutant is retained even if worse than its parent.",
                               "Fresh positive steps are not a discrimination circuit or a new algorithm.",
                               "Fitness gains may reflect capture, poison avoidance, misses, growth or other costs.",
                               "This is a bounded diagnostic, not full G2 or world admission/selection."])
    atomic_json(out / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({"status": "dry_run", "scientific_genome_lives": 11328, "workers": 2,
                          "max_cpu_seconds": 3600, "seed_blocks": BLOCKS, "new_mutants_generated": 0}))
        return
    result = run()
    print(json.dumps({"status": result["status"], "confirmation": result["confirmation"]}, indent=2))


if __name__ == "__main__":
    main()
