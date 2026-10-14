"""Independent completed-data M audit/export; NumPy only, never compile or simulate."""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genome_audit as genes
from analysis_common import (
    COLS,
    LEDGER,
    arrays,
    check_stats,
    equal,
    identical,
    prices,
    read,
    save,
    sha,
    stats,
    validate_row,
)

ROOT = next((p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists()), None)
ROLES = ("intact", "copy_KO", "source_KO", "double_KO")
FIELDS = ("F", "F_kernel", "n_end", "n_H_end", "live_time", "spikes", "packets", "misses", "clicks",
          "captures", "path", "zone_samples", "samples")
L_DEPENDENCY = "outputs/autonomous_s7_20261014"
ANALYZERS = ("analyze.py", "analysis_common.py", "genome_audit.py", "test_analysis.py")


def operation(base, name):
    archived = base / "operations" / name
    return archived if archived.exists() else base / name


def complete_budget(path, label, cap=None):
    value = read(path)
    if value["status"] != "complete" or value.get("running") or value.get("queued"):
        raise ValueError(label + " must be complete without active or queued work")
    if cap is not None:
        equal(value["cap_cpu_seconds"], cap, label + " fixed CPU cap")
        if (value["exit_code"] != 0 or not np.isfinite(value["cpu_seconds"])
                or not 0 < value["cpu_seconds"] < cap):
            raise ValueError(label + " exceeded its worker budget or failed")
    return value


def expected_world(path):
    """Read literal world defaults/preset from the hashed source AST without importing source code."""
    tree = ast.parse(Path(path).read_text())
    assigned = {node.targets[0].id: node.value for node in tree.body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    equal(ast.literal_eval(assigned["LEDGER_V2"]) + ast.literal_eval(assigned["LEDGER_V3"].right), LEDGER,
          "ABI3 ledger order")
    costs = {item.arg: ast.literal_eval(item.value) for item in assigned["COSTS"].keywords}
    world = {}
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "World")
    for field in node.body:
        if isinstance(field, ast.AnnAssign):
            value = field.value
            world[field.target.id] = (costs[ast.literal_eval(value.slice)] if isinstance(value, ast.Subscript)
                                      else ast.literal_eval(value))
    presets = assigned["PRESETS"]
    preset = next(value for key, value in zip(presets.keys, presets.values)
                  if ast.literal_eval(key) == "catch_speck_l4")
    world.update({item.arg: ast.literal_eval(item.value) for item in preset.keywords})
    world.update(T=1024, d0=.5, d_min=.25, sigma=.4, lam_s=4)
    return world


def comparison(data, intact, knockout, world):
    result = {key: stats(data[key][intact] - data[key][knockout]) for key in FIELDS}
    window = world["T"] - world["t_open"]
    pieces = {"income": (data["income"][intact] - data["income"][knockout]) / window,
              "cost_saving": (data["cost"][knockout] - data["cost"][intact]) / window,
              "guard_charge_saving": (data["guard_charge"][knockout] - data["guard_charge"][intact]) / window,
              "extinction_charge_saving": data["extinct_charge"][knockout] - data["extinct_charge"][intact]}
    pieces["accounting_residual"] = data["F"][intact] - data["F"][knockout] - sum(pieces.values())
    if not np.allclose(pieces["accounting_residual"], 0, rtol=0, atol=1e-9):
        raise ValueError("paired fitness decomposition does not reconcile")
    result["fitness_contributions"] = {key: stats(value) for key, value in pieces.items()}
    result["cost_saving_components"] = {
        name: stats(price * data[column][knockout] / window - price * data[column][intact] / window)
        for name, column, price in prices(world)}
    result["guard_fraction"] = {name: float(np.mean(data["status"][row].astype(np.int64) & 6 != 0))
                                for name, row in (("parent", knockout), ("winner", intact))}
    return result


def check_comparison(actual, saved, label):
    for key in FIELDS:
        check_stats(actual[key], saved[key], label + " " + key)
    for group in ("fitness_contributions", "cost_saving_components"):
        equal(set(actual[group]), set(saved[group]), label + " component names")
        for key, value in actual[group].items():
            check_stats(value, saved[group][key], label + " " + key)
    equal(actual["guard_fraction"], saved["guard_fraction"], label + " guard fractions")


def source(base, name):
    archived = base / "sources" / name
    if archived.exists():
        return archived
    if ROOT is None:
        raise ValueError("missing archived source " + name)
    return ROOT / name


def dependency(base):
    archived = base / "dependency/L"
    if archived.exists():
        return archived
    if ROOT is None:
        raise ValueError("missing L resource dependency")
    return ROOT / L_DEPENDENCY


def audit_inputs(base):
    protocol, ready = read(base / "protocol.json"), read(operation(base, "ready.json"))
    expected = {"runs": [51090], "lives": 512, "seed_block": 100, "genome_lives": 2048,
                "max_cpu_seconds": 1800, "threads": 2, "T": 1024, "roles": list(ROLES),
                "endpoint_rule": "exact final population rank0 at generation16",
                "wait_for_studies": [L_DEPENDENCY], "seeds": list(range(52_000_000, 52_000_512))}
    for name, value in expected.items():
        equal(protocol[name], value, "protocol " + name)
    equal(set(ready["files"]), {"protocol.json", "measure.py", "run_budgeted.py"}, "release pin names")
    for name, digest in ready["files"].items():
        equal(sha(operation(base, name)), digest, "release " + name)
    equal(set(protocol["helpers"]), {"taskvar_confirm.py", "taskvar_second_step.py", "taskvar_gradient.py",
                                     "taskvar_gates.py"}, "helper pin names")
    for name, digest in protocol["source_identity"].items():
        equal(sha(source(base, name)), digest, "source " + name)
    for name, digest in protocol["helpers"].items():
        equal(sha(source(base, "scripts/" + name)), digest, "helper " + name)
    for name, digest in protocol["inputs"].items():
        equal(sha(base / name), digest, "input " + name)
    for name, digest in protocol["preparation_pins"].items():
        equal(sha(base / name), digest, "preparation " + name)
    equal(protocol["numerical_identity"]["sources"], protocol["source_identity"], "nested source identity")
    equal(set(ready["dependencies"]), {L_DEPENDENCY}, "L dependency set")
    files = ready["dependencies"][L_DEPENDENCY]
    equal(set(files), {"protocol.json", "run_budgeted.py"}, "L dependency pins")
    folder = dependency(base)
    complete_budget(operation(folder, "budget.json"), "L", 14400)
    for name, digest in files.items():
        equal(sha(operation(folder, name)), digest, "L pin " + name)
    g = base / "inputs/G"
    gb = complete_budget(g / "operations/budget.json", "G")
    equal(gb["cap_cpu_seconds"], 14400, "G CPU cap")
    if not np.isfinite(gb["cpu_seconds"]) or not 0 < gb["cpu_seconds"] < 14400:
        raise ValueError("G completed CPU differs")
    gp, provenance = read(g / "protocol.json"), read(g / "provenance.json")
    equal(gp["expected_numerical_identity"], protocol["numerical_identity"], "G/M numerical identity")
    for name in protocol["inputs"]:
        if name.startswith("inputs/G/") and name != "inputs/G/provenance.json":
            relative = name.removeprefix("inputs/G/")
            record = provenance["artifacts"][relative]
            equal(sha(g / relative), record["sha256"], "G archive " + relative)
            equal((g / relative).stat().st_size, record["bytes"], "G archive size " + relative)
    cfg = (base / "inputs/evaluator.yaml").read_text()
    equal(re.findall(r"^\s*extinct_charge:\s*(\S+)\s*$", cfg, re.MULTILINE), ["true"], "extinction policy")
    manifest = read(base / "measurement/manifest.json")
    equal(manifest["protocol_sha256"], sha(base / "protocol.json"), "measurement protocol")
    equal(manifest["ready"], ready, "measurement readiness")
    equal(manifest["numerical_identity"], protocol["numerical_identity"], "measurement numerical identity")
    expected = expected_world(source(base, "src/life/spec.py"))
    equal(protocol["world"], expected, "registered world/prices")
    equal(manifest["world"], expected, "measured world/prices")
    equal(manifest["seeds"], protocol["seeds"], "fresh paired seeds")
    equal(manifest["seed_block"], 100, "fresh seed block")
    equal(manifest["genome_lives"], 2048, "measurement count")
    equal(manifest["frozen_genomes"], read(base / "genomes.json"), "prospectively frozen mapping")
    return protocol, manifest


def audit_candidates(base, manifest):
    """Independently replay recorded FP32 genetics and resolve the exact source innovation."""
    frozen, g = manifest["frozen_genomes"], base / "inputs/G"
    recorded = frozen["endpoint_audits"]["51090"]
    equal(set(frozen["endpoint_audits"]), {"51090"}, "endpoint audit coverage")
    folder = g / "runs/s51090"
    gp = read(g / "protocol.json")
    equal(sha(g / "configs/s51090.yaml"), gp["configs"]["51090"]["sha256"], "G configuration")
    for name, field in (("checkpoint.pt", "checkpoint_sha256"), ("lineage.jsonl", "lineage_sha256")):
        equal(sha(folder / name), recorded[field], "recorded G " + name)
    equal(recorded["health"], {"pop_invalid": 0, "pop_mismatch": 0, "recheck_invalid": 0}, "G health")
    founder = genes.from_json(read(base / "inputs/founder_row38.json"))
    lines = [json.loads(line) for line in (folder / "lineage.jsonl").read_text().splitlines() if line.strip()]
    population, origins, replay = genes.replay(lines, founder)
    genome = genes.from_json(read(folder / "best_genome.json"))
    if not identical(population[0], genome):
        raise ValueError("G final rank0 differs from independent genetic replay")
    equal(genes.raw_sha(genome), recorded["genome_raw_sha256"], "endpoint raw hash")
    ancestry = origins[0]
    active = genes.view(genome, "act") > .5
    if not np.array_equal(active, ancestry >= 0):
        raise ValueError("active mask and origin registry differ")
    slots = np.flatnonzero(active & (ancestry >= 16)).tolist()
    equal(slots, [9], "fixed unique copied slot")
    equal(int(ancestry[9]), 21, "fixed copied origin")
    events = [value for value in replay["duplication_origins"] if value["origin_id"] == 21]
    equal(len(events), 1, "copy-origin event count")
    event = events[0]
    equal(event["source_origin_id"], 0, "fixed source origin")
    equal(np.flatnonzero(active & (ancestry == event["source_origin_id"])).tolist(), [0], "exact extant source")
    previous = recorded["genetic_replay"]
    equal(previous["raw_population_replay_bitwise"], True, "production population replay receipt")
    for name in ("duplication_events", "deletion_events", "duplication_origins"):
        equal(replay[name], previous[name], "independent genetic replay " + name)
    equal(replay["point_mutations"], previous["point_mutations_including_initial_copies"], "point mutation count")
    equal(previous["final_rank_zero_duplicate_slots"], [9], "recorded copied slots")
    equal(previous["final_rank_zero_duplicate_origin_ids"], [21], "recorded copied origins")
    equal(previous["final_rank_zero_active_genes"], int(active.sum()), "recorded active count")
    branch = {"copy_slot": 9, "copy_origin_id": 21, "source_slot": 0, "source_origin_id": 0,
              "duplication_event": event, "origins": ancestry.tolist(), "rows": {}}
    genomes, labels = [], []
    for i, (role, deleted) in enumerate(zip(ROLES, ((), (9,), (0,), (9, 0)))):
        edited, canonical = genome.copy(), genome.copy()
        for slot in deleted:
            edited = genes.delete(edited, slot)
            genes.view(canonical, "act")[slot] = 0
        packed = genes.pack(edited)
        if not identical(packed, genes.pack(canonical)):
            raise ValueError("deletion runtime table differs from canonical inactive masks")
        if role == "double_KO" and not identical(edited, genes.delete(genes.delete(genome, 0), 9)):
            raise ValueError("double deletion does not commute")
        branch["rows"][role] = {"row": i, "deleted_slots": list(deleted), "raw_sha256": genes.raw_sha(edited),
                               "runtime_table_sha256": genes.raw_sha(packed),
                               "active_slots": np.flatnonzero(genes.view(edited, "act") > .5).tolist()}
        genomes.append(edited)
        labels.append("s51090_" + role)
    genomes = np.stack(genomes)
    equal(frozen["branches"], {"51090": branch}, "all fixed source/copy roles")
    equal(frozen["labels"], labels, "prospective labels")
    equal(frozen["simulated_lives"], 0, "genome preparation life count")
    equal(frozen["genotypes_raw_sha256"], genes.raw_sha(genomes), "prospective raw genotype hash")
    if not identical(np.load(base / "genotypes.npy", allow_pickle=False), genomes):
        raise ValueError("prospective raw genomes differ from independent canonical deletions")
    measured = arrays(base / "measurement/genotypes.npz")
    if not identical(measured["genomes"], genomes) or measured["labels"].tolist() != labels:
        raise ValueError("scored raw genomes differ from prospective interventions")
    return branch, replay


def interaction(data, world):
    if any(np.asarray(data[key]).shape != (4, 512) for key in COLS):
        raise ValueError("four complete paired rows required")
    vectors = {key: data[key][0] - data[key][1] - data[key][2] + data[key][3]
               for key in COLS if key != "status"}
    result = {key: stats(value) for key, value in vectors.items()}
    pieces = {"income": vectors["income"] / world["T"], "cost_saving": -vectors["cost"] / world["T"],
              "guard_charge_saving": -vectors["guard_charge"] / world["T"],
              "extinction_charge_saving": -vectors["extinct_charge"]}
    pieces["accounting_residual"] = vectors["F"] - sum(pieces.values())
    if not np.allclose(pieces["accounting_residual"], 0, rtol=0, atol=1e-9):
        raise ValueError("interaction accounting does not reconcile")
    result["fitness_contributions"] = {key: stats(value) for key, value in pieces.items()}
    f = result["F"]
    result.update(abs_above_3se=abs(f["mean"]) > 3 * f["se"], abs_at_least_0p5=abs(f["mean"]) >= .5)
    return result, vectors["F"]


def audit_rows(base, manifest):
    folder = base / "measurement"
    aggregate, index = arrays(folder / "scores.npz"), read(folder / "row_index.json")
    equal(aggregate["seeds"].tolist(), manifest["seeds"], "aggregate seeds")
    equal(aggregate["genome_indices"].tolist(), list(range(4)), "aggregate row mapping")
    equal(set(index), {f"rows/row_{i:04d}.npz" for i in range(4)}, "raw row coverage")
    if any(aggregate[key].shape != (4, 512) for key in COLS):
        raise ValueError("aggregate dimensions differ")
    health, cpu = {}, 0.
    for i, role in enumerate(ROLES):
        name = f"rows/row_{i:04d}.npz"
        equal(sha(folder / name), index[name]["sha256"], "raw hash " + role)
        row = arrays(folder / name)
        equal(row["seeds"].tolist(), manifest["seeds"], "raw seeds " + role)
        equal(int(row["genome_index"]), i, "raw index " + role)
        health[role] = validate_row(row, manifest["world"])
        for key in COLS:
            if not identical(row[key], aggregate[key][i]):
                raise ValueError("raw/aggregate bytes differ: " + role + " " + key)
        equal(float(row["cpu_seconds"]), index[name]["cpu_seconds"], "row CPU receipt " + role)
        cpu += float(row["cpu_seconds"])
    return aggregate, health, cpu


def analyze(base):
    base = Path(base).resolve()
    budget_path = operation(base, "budget.json")
    if not budget_path.exists() or read(budget_path)["status"] != "complete":
        return {"status": "incomplete", "budget_status": read(budget_path)["status"]
                if budget_path.exists() else "not_started"}, {}
    budget = complete_budget(budget_path, "M", 1800)
    protocol, manifest = audit_inputs(base)
    equal(budget["ready"], manifest["ready"], "resource release")
    branch, replay = audit_candidates(base, manifest)
    report = read(base / "measurement/report.json")
    equal(report["status"], "complete", "scientific report")
    equal(set(report["endpoints"]), {"51090"}, "scientific endpoint coverage")
    equal(report["research_genome_lives"], 2048, "research count")
    equal(report["limitations"], protocol["limitations"], "reported limitations")
    data, health, cpu = audit_rows(base, manifest)
    primary, vector = interaction(data, manifest["world"])
    saved = report["endpoints"]["51090"]
    equal(set(saved["interaction"]), set(primary), "interaction report fields")
    for key in COLS:
        if key != "status":
            check_stats(primary[key], saved["interaction"][key], "interaction " + key)
    for key, value in primary["fitness_contributions"].items():
        check_stats(value, saved["interaction"]["fitness_contributions"][key], "interaction " + key)
    for key in ("abs_above_3se", "abs_at_least_0p5"):
        equal(primary[key], saved["interaction"][key], "interaction flag " + key)
    losses = {role: comparison(data, 0, i, manifest["world"]) for i, role in enumerate(ROLES) if i}
    equal(set(losses), set(saved["losses"]), "single/double loss coverage")
    for role, value in losses.items():
        check_comparison(value, saved["losses"][role], role)
    vectors = {"seeds": np.asarray(manifest["seeds"], dtype=np.uint64), "s51090_interaction": vector,
               **{"s51090_" + role + "_loss": data["F"][0] - data["F"][i]
                  for i, role in enumerate(ROLES) if i}}
    recorded_vectors = arrays(base / "measurement/contrasts.npz")
    equal(set(recorded_vectors), set(vectors), "paired contrast names")
    if any(not identical(recorded_vectors[key], value) for key, value in vectors.items()):
        raise ValueError("paired contrast bytes differ")
    if not np.isclose(cpu, report["row_cpu_seconds"], rtol=0, atol=1e-6) or cpu > budget["cpu_seconds"] + 1e-6:
        raise ValueError("row and monitored CPU accounting differ")
    summary = {"status": "complete", "endpoint": "51090", "research_genome_lives": 2048,
               "paired_seeds": 512, "seed_block": 100, "branch": branch, "interaction": primary,
               "losses": losses, "means": {role: {key: stats(data[key][i]) for key in COLS if key != "status"}
                                            for i, role in enumerate(ROLES)},
               "life_health": health, "genetic_replay": replay,
               "budget": {"monitored_cpu_seconds": budget["cpu_seconds"], "row_cpu_seconds": cpu,
                          "cap_cpu_seconds": 1800, "simulation_threads": 2},
               "startup_validation": {"golden_lives": 2, "T": 200, "seed": 11,
                   "scope": "Existing numerical-identity full/fast goldens; separate from research, included in CPU."},
               "audit": {"raw_rows": 4, "raw_ledger_columns": 57, "scored_columns": 60,
                   "raw_and_aggregate_bitwise": True, "production_fitness_bitwise": True,
                   "contrast_bytes_exact": True, "independent_genetic_replay": True,
                   "independent_canonical_runtime_tables": True, "analysis_simulated_lives": 0},
               "analytical_G51089": "Disconnected copy; physical and fitness effects analytically zero. "
                                     "No M G51089 life was simulated. See analytical_proof/PROOF.md.",
               "limitations": protocol["limitations"] + [
                   "Independent replay reconstructs recorded genetics, not RNG draws or evolutionary selection.",
                   "Checkpoint hashes and the original checkpoint-validation receipt are retained; this NumPy "
                   "analyzer does not deserialize checkpoint objects."]}
    return summary, vectors


def markdown(summary):
    f = summary["interaction"]["F"]
    lines = ["# Whole-life interaction between a copied gene and its source", "",
             "M measured all four fixed G51090 arms on 512 shared fresh block100 lives at T1024 in fast POOL.",
             "The primary contrast is intact − copy knockout − source knockout + double knockout.",
             f"Its paired fitness interaction is **{f['mean']:+.6f} ± {f['se']:.6f} SE**.", "",
             "| Contrast | Paired fitness difference ± SE |", "|---|---:|"]
    for role in ROLES[1:]:
        value = summary["losses"][role]["F"]
        lines.append(f"| Intact − {role} | {value['mean']:+.6f} ± {value['se']:.6f} |")
    lines += ["", "Both signs and all three losses remain. The absolute 0.5 F and three-SE flags are descriptive;",
              "an unresolved measurement is not an equivalence proof. Either interaction sign can arise through",
              "development or nonlinear task fitness, so its sign does not categorically establish redundancy.", "",
              "**G51089:** " + summary["analytical_G51089"], "The pre-release rationale is in AMENDMENT.md. The original eight-role",
              "preparation remains under superseded_4096/; it was replaced before M release or measurement.", "",
              f"Completed 2,048 research lives in {summary['budget']['monitored_cpu_seconds']:.6f} cumulative",
              "CPU-seconds (cap 1,800; two workers). Two startup golden lives are separate from research and inside CPU.",
              "Guarded and extinct lives retain their ordinary penalties.", "",
              "measurement/ preserves all raw rows and contrasts; operations/ retains release/resource receipts.",
              "prelaunch/ preserves the complete amended public preparation. summary.json contains independent",
              "genetic replay, exact source/copy mappings, every ledger contrast, costs and morphology.", "",
              "Recompute without simulation or compilation (Python + NumPy):", "", "```sh",
              "python analyze.py --study . --check", "```", "", "Interpretation limits:", ""]
    lines.extend("- " + item for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def export(base, destination, summary, vectors):
    if summary["status"] != "complete":
        raise ValueError("cannot publish incomplete conclusions")
    if Path(base).resolve() == Path(destination).resolve():
        raise ValueError("export requires a separate public archive")
    destination.mkdir(parents=True, exist_ok=True)
    prior_path, historical = destination / "provenance.json", destination / "prelaunch"
    if not historical.exists():
        previous = read(prior_path)
        equal(previous["status"], "prospective_preparation_not_released", "prelaunch provenance")
        for name, record in previous["artifacts"].items():
            equal(sha(destination / name), record["sha256"], "prelaunch artifact " + name)
            equal((destination / name).stat().st_size, record["bytes"], "prelaunch size " + name)
        for name in (*previous["artifacts"], "provenance.json"):
            target = historical / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(destination / name, target)
    protocol = read(base / "protocol.json")
    for folder in ("measurement", "inputs", "analytical_proof"):
        shutil.copytree(base / folder, destination / folder, dirs_exist_ok=True)
    for name in ("protocol.json", "genomes.json", "genotypes.npy", *protocol["preparation_pins"]):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base / name, target)
    (destination / "operations").mkdir(exist_ok=True)
    for name in ("measure.py", "run_budgeted.py", "ready.json", "budget.json", "run.log"):
        shutil.copyfile(operation(base, name), destination / "operations" / name)
    for name in [*protocol["source_identity"], *("scripts/" + name for name in protocol["helpers"])]:
        target = destination / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source(base, name), target)
    dep = destination / "dependency/L"
    dep.mkdir(parents=True, exist_ok=True)
    for name in ("protocol.json", "run_budgeted.py", "budget.json"):
        shutil.copyfile(operation(dependency(base), name), dep / name)
    for name in ANALYZERS:
        shutil.copyfile(Path(__file__).with_name(name), destination / name)
    save(destination / "summary.json", summary)
    np.savez_compressed(destination / "independent_contrasts.npz", **vectors)
    (destination / "README.md").write_text(markdown(summary))
    # The old manifest still hashes the old README; its byte-exact copy is now safely under prelaunch/.
    if prior_path.exists():
        prior_path.unlink()
    rebuilt, rebuilt_vectors = analyze(destination)
    equal(rebuilt, summary, "copied archive independent summary")
    if (set(rebuilt_vectors) != set(vectors)
            or any(not identical(rebuilt_vectors[k], v) for k, v in vectors.items())):
        raise ValueError("copied archive independent vectors differ")
    artifacts = {str(path.relative_to(destination)): {"sha256": sha(path), "bytes": path.stat().st_size}
                 for path in sorted(destination.rglob("*")) if path.is_file() and path != prior_path
                 and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts}
    save(prior_path, {"status": "complete", "artifacts": artifacts, "research_genome_lives": 2048,
                      "analysis_simulated_lives": 0})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    summary, vectors = analyze(args.study)
    if summary["status"] != "complete":
        print(json.dumps(summary))
        return
    if args.check:
        provenance = read(args.study / "provenance.json")
        equal(provenance["status"], "complete", "archive status")
        for name, record in provenance["artifacts"].items():
            equal(sha(args.study / name), record["sha256"], "archive artifact " + name)
            equal((args.study / name).stat().st_size, record["bytes"], "archive size " + name)
        equal(read(args.study / "summary.json"), summary, "saved independent summary")
        equal((args.study / "README.md").read_text(), markdown(summary), "readable summary")
        saved = arrays(args.study / "independent_contrasts.npz")
        equal(set(saved), set(vectors), "independent vector names")
        if any(not identical(saved[key], value) for key, value in vectors.items()):
            raise ValueError("independent vector bytes differ")
    if args.export:
        export(args.study.resolve(), args.export.resolve(), summary, vectors)
    print(json.dumps({"status": "complete", "research_genome_lives": 2048,
                      "interaction": summary["interaction"]["F"], "audit": summary["audit"]}, indent=2))


if __name__ == "__main__":
    main()
