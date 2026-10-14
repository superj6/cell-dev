"""Independent completed-data J audit/export. NumPy only; never compile or simulate."""
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
RUNS = ("51089", "51090")
FIELDS = ("F", "F_kernel", "n_end", "n_H_end", "live_time", "spikes", "packets", "misses", "clicks",
          "captures", "path", "zone_samples", "samples")
NA = "not_applicable_no_active_duplicate_origin"
ANALYZERS = ("analyze.py", "analysis_common.py", "genome_audit.py", "test_analysis.py")


def operation(base, name):
    archived = base / "operations" / name
    return archived if archived.exists() else base / name


def dependency(base, study):
    archived = base / "dependencies" / Path(study).name
    if archived.exists():
        return archived
    if ROOT is None:
        raise ValueError("missing archived dependency " + study)
    return ROOT / study


def source(base, name, helper=False):
    archived = base / "sources" / (Path(name).name if helper else name)
    if archived.exists():
        return archived
    if ROOT is None:
        raise ValueError("missing archived source " + name)
    return ROOT / name


def complete_budget(path, label, cap=None):
    value = read(path)
    if value["status"] != "complete" or value.get("running") or value.get("queued"):
        raise ValueError(label + " must be complete without active or queued work")
    if cap is not None:
        equal(value["cap_cpu_seconds"], cap, label + " fixed CPU cap")
        if (value["exit_code"] != 0 or not np.isfinite(value["cpu_seconds"])
                or not 0 < value["cpu_seconds"] <= cap):
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


def audit_inputs(base):
    protocol, ready = read(base / "protocol.json"), read(operation(base, "ready.json"))
    expected = {"runs": [51089, 51090], "lives_per_stage": 512, "stage_blocks": {"screen": 98, "confirm": 99},
                "max_genome_lives": 19456, "max_cpu_seconds": 7200, "threads": 2, "T": 1024,
                "endpoint_rule": "exact final population rank0 at generation16",
                "candidate_rule": "every active slot with innovation origin >=16, no fitness or weight filter",
                "selection_rule": "largest paired intact-minus-KO mean per endpoint; smallest slot tie; any sign",
                "world": {"preset": "catch_speck_l4", "d0": .5, "d_min": .25, "sigma": .4, "lam_s": 4}}
    for name, value in expected.items():
        equal(protocol[name], value, "protocol " + name)
    equal(set(ready["files"]), {"protocol.json", "measure.py", "run_budgeted.py"}, "release pin names")
    for name, digest in ready["files"].items():
        equal(sha(base / name if name == "protocol.json" else operation(base, name)), digest, "release " + name)
    for name, digest in protocol["source_identity"].items():
        equal(sha(source(base, name)), digest, "source " + name)
    for name, digest in protocol["helpers"].items():
        equal(sha(source(base, "scripts/" + name, helper=True)), digest, "helper " + name)
    for name, digest in protocol["inputs"].items():
        equal(sha(base / name), digest, "input " + name)
    equal(protocol["numerical_identity"]["sources"], protocol["source_identity"], "nested source identity")
    equal(set(ready["dependencies"]), set(protocol["wait_for_studies"]), "H/I dependency set")
    for study, files in ready["dependencies"].items():
        folder = dependency(base, study)
        complete_budget(operation(folder, "budget.json"), study)
        equal(set(files), {"protocol.json", "run_budgeted.py"}, "dependency pin set")
        for name, digest in files.items():
            equal(sha(operation(folder, name)), digest, "dependency " + study + "/" + name)
    g = dependency(base, protocol["G_study"])
    complete_budget(operation(g, "budget.json"), "G")
    for name, digest in protocol["G_pins"].items():
        equal(sha(operation(g, name)), digest, "G pin " + name)
    gp = read(g / "protocol.json")
    equal(gp, read(base / "inputs/G_protocol.json"), "G protocol input")
    equal(gp["expected_numerical_identity"], protocol["numerical_identity"], "G/J numerical identity")
    cfg = (base / "inputs/evaluator.yaml").read_text()
    equal(re.findall(r"^\s*extinct_charge:\s*(\S+)\s*$", cfg, re.MULTILINE), ["true"], "extinction policy")
    manifest = read(base / "measurement/manifest.json")
    equal(manifest["protocol_sha256"], sha(base / "protocol.json"), "measurement protocol")
    equal(manifest["ready"], ready, "measurement readiness")
    equal(manifest["numerical_identity"], protocol["numerical_identity"], "measurement numerical identity")
    equal(manifest["world"], expected_world(source(base, "src/life/spec.py")), "complete world/prices")
    equal(manifest["seeds"], {"screen": list(range(51_980_000, 51_980_512)),
                              "confirm": list(range(51_990_000, 51_990_512))}, "fresh paired seed blocks")
    equal(manifest["max_genome_lives"], 19456, "measurement count bound")
    return protocol, manifest, g


def audit_candidates(base, manifest, g):
    founder = genes.from_json(read(base / "inputs/founder_row38.json"))
    saved = arrays(base / "measurement/genotypes.npz")
    expected_genomes, labels, branches, evidence = [], [], {}, {}
    g_protocol = read(g / "protocol.json")
    for seed in RUNS:
        folder, recorded = g / ("runs/s" + seed), manifest["endpoint_audits"][seed]
        equal(sha(g / ("configs/s" + seed + ".yaml")), g_protocol["configs"][seed]["sha256"], "G config")
        equal(sha(folder / "checkpoint.pt"), recorded["checkpoint_sha256"], "G checkpoint bytes")
        equal(sha(folder / "lineage.jsonl"), recorded["lineage_sha256"], "G lineage bytes")
        if set(recorded["health"]) != {"pop_invalid", "pop_mismatch", "recheck_invalid"} or any(
                recorded["health"].values()):
            raise ValueError("invalid G endpoint health")
        lines = [json.loads(line) for line in (folder / "lineage.jsonl").read_text().splitlines() if line.strip()]
        population, origin, replay = genes.replay(lines, founder)
        genome = genes.from_json(read(folder / "best_genome.json"))
        if not identical(population[0], genome):
            raise ValueError("G rank0 raw genome differs from independent genetic replay")
        equal(genes.raw_sha(genome), recorded["genome_raw_sha256"], "G endpoint raw hash")
        ancestry = origin[0]
        slots = np.flatnonzero((genes.view(genome, "act") > .5) & (ancestry >= 16)).tolist()
        previous = recorded["genetic_replay"]
        equal(previous["raw_population_replay_bitwise"], True, "measurement population replay receipt")
        for name in ("duplication_events", "deletion_events"):
            equal(replay[name], previous[name], "independent genetic replay " + name)
        equal(replay["point_mutations"], previous["point_mutations_including_initial_copies"] , "point count")
        equal(previous["final_rank_zero_duplicate_slots"], slots, "duplicate-origin slots")
        equal(previous["final_rank_zero_duplicate_origin_ids"], ancestry[slots].tolist(), "duplicate origins")
        equal(previous["final_rank_zero_active_genes"], int((ancestry >= 0).sum()), "active genes")
        evidence[seed] = replay
        branch = {"status": "applicable" if slots else NA, "slots": slots, "origins": ancestry.tolist(),
                  "intact_row": None, "knockouts": []}
        branches[seed] = branch
        if not slots:
            continue
        branch["intact_row"] = len(expected_genomes)
        expected_genomes.append(genome)
        labels.append("s" + seed + "_intact")
        for slot in slots:
            knockout = genes.delete(genome, slot)
            canonical = genome.copy()
            genes.view(canonical, "act")[slot] = 0
            packed = genes.pack(knockout)
            if not identical(packed, genes.pack(canonical)):
                raise ValueError("knockout runtime table differs from canonical inactive-bit intervention")
            row = len(expected_genomes)
            expected_genomes.append(knockout)
            labels.append(f"s{seed}_delete_slot{slot}_origin{int(ancestry[slot])}")
            branch["knockouts"].append({"row": row, "slot": slot, "origin_id": int(ancestry[slot]),
                "operation": {"delete": slot}, "raw_sha256": genes.raw_sha(knockout),
                "runtime_table_sha256": genes.raw_sha(packed)})
    genomes = np.stack(expected_genomes) if expected_genomes else np.empty((0, genes.SIZE), dtype=np.float32)
    if not identical(genomes, saved["genomes"]):
        raise ValueError("candidate rows differ from all prescribed genetic deletions")
    equal(branches, manifest["branches"], "complete candidate manifest")
    equal(labels, manifest["labels"], "candidate labels")
    equal(labels, saved["labels"].tolist(), "saved candidate labels")
    equal([genes.raw_sha(row) for row in genomes], manifest["genome_raw_sha256"], "all raw genotype hashes")
    equal(len(genomes) * 512, manifest["screen_genome_lives"], "screen life count")
    if len(genomes) > 34:
        raise ValueError("candidate count exceeds registered bound")
    return genomes, branches, evidence


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


def selection(fitness, branches):
    if fitness.ndim != 2 or fitness.shape[1] != 512 or not np.isfinite(fitness).all():
        raise ValueError("invalid paired screen fitness")
    chosen, rows, pairs = {}, [], {}
    for seed in RUNS:
        branch = branches[seed]
        if not branch["knockouts"]:
            chosen[seed] = {"status": NA}
            continue
        intact = branch["intact_row"]
        item = min(branch["knockouts"], key=lambda item: (
            -float(np.mean(fitness[intact] - fitness[item["row"]])), item["slot"]))
        chosen[seed] = {"status": "selected", "intact_screen_row": intact, "knockout_screen_row": item["row"],
                        "slot": item["slot"], "origin_id": item["origin_id"],
                        "screen_mean_loss": float(np.mean(fitness[intact] - fitness[item["row"]]))}
        pairs[seed] = [len(rows), len(rows) + 1]
        rows.extend([intact, item["row"]])
    return chosen, rows, pairs


def stage(base, name, count, manifest):
    folder = base / "measurement" / name
    aggregate = arrays(folder / "scores.npz")
    equal(aggregate["seeds"].tolist(), manifest["seeds"][name], name + " aggregate seeds")
    equal(aggregate["genome_indices"].tolist(), list(range(count)), name + " aggregate rows")
    if any(aggregate[key].shape != (count, 512) for key in COLS):
        raise ValueError(name + " aggregate dimensions differ")
    index = read(folder / "row_index.json")
    equal(set(index), {f"rows/row_{i:04d}.npz" for i in range(count)}, name + " raw row set")
    health, cpu = {}, 0.0
    for i in range(count):
        relative = f"rows/row_{i:04d}.npz"
        equal(sha(folder / relative), index[relative]["sha256"], name + " raw hash")
        row = arrays(folder / relative)
        equal(row["seeds"].tolist(), manifest["seeds"][name], name + " raw seeds")
        equal(int(row["genome_index"]), i, name + " raw row identity")
        health[str(i)] = validate_row(row, manifest["world"])
        for key in COLS:
            if not identical(row[key], aggregate[key][i]):
                raise ValueError(name + " aggregate/raw bytes differ: " + key)
        equal(float(row["cpu_seconds"]), index[relative]["cpu_seconds"], name + " CPU receipt")
        cpu += float(row["cpu_seconds"])
    return aggregate, health, cpu


def analyze(base):
    base = Path(base).resolve()
    budget_path = operation(base, "budget.json")
    if not budget_path.exists() or read(budget_path)["status"] != "complete":
        return {"status": "incomplete", "budget_status": read(budget_path)["status"]
                if budget_path.exists() else "not_started"}, {}
    budget = complete_budget(budget_path, "J", 7200)
    protocol, manifest, g = audit_inputs(base)
    equal(budget["ready"], manifest["ready"], "resource release")
    genomes, branches, replay = audit_candidates(base, manifest, g)
    report = read(base / "measurement/report.json")
    equal(report["status"], "complete", "scientific report")
    equal(report["branches"], branches, "scientific branch coverage")
    screen, primary, health, vectors, means, row_cpu = {}, {}, {}, {}, {}, 0.0
    chosen, rows, pairs = {seed: {"status": NA} for seed in RUNS}, [], {}
    if len(genomes):
        first, health["screen"], row_cpu = stage(base, "screen", len(genomes), manifest)
        chosen, rows, pairs = selection(first["F"], branches)
        saved = read(base / "measurement/selection.json")
        for key, value in (("selection", chosen), ("screen_rows", rows), ("confirm_pairs", pairs)):
            equal(saved[key], value, "frozen " + key)
        equal(saved["screen_scores_sha256"], sha(base / "measurement/screen/scores.npz"), "selection source")
        selected = arrays(base / "measurement/confirmation_genotypes.npz")
        if not identical(selected["genomes"], genomes[rows]):
            raise ValueError("confirmation genotypes differ from frozen choices")
        equal(selected["screen_rows"].tolist(), rows, "confirmation genotype mapping")
        equal(selected["labels"].tolist(), [manifest["labels"][i] for i in rows], "confirmation labels")
        fresh, health["confirm"], extra_cpu = stage(base, "confirm", len(rows), manifest)
        row_cpu += extra_cpu
        vectors = {"seeds": np.asarray(manifest["seeds"]["confirm"], dtype=np.uint64)}
        for seed in RUNS:
            branch = branches[seed]
            screen[seed] = {str(item["slot"]): comparison(first, branch["intact_row"], item["row"], manifest["world"])
                            for item in branch["knockouts"]}
            equal(set(screen[seed]), set(report["screen"][seed]), "all screened knockout reports")
            for slot, value in screen[seed].items():
                check_comparison(value, report["screen"][seed][slot], "screen " + seed + " slot " + slot)
        for seed, (intact, knockout) in pairs.items():
            value = comparison(fresh, intact, knockout, manifest["world"])
            value.update(positive_above_3se=value["F"]["mean"] > 3 * value["F"]["se"],
                         above_0p5=value["F"]["mean"] > .5)
            check_comparison(value, report["confirmation"][seed]["loss"], "confirm " + seed)
            for flag in ("positive_above_3se", "above_0p5"):
                equal(value[flag], report["confirmation"][seed]["loss"][flag], "fresh descriptive flag")
            equal(report["confirmation"][seed]["selection"], chosen[seed], "report chosen intervention")
            primary[seed] = value
            vectors["s" + seed + "_intact_minus_KO"] = fresh["F"][intact] - fresh["F"][knockout]
            means[seed] = {name: {key: stats(fresh[key][index]) for key in FIELDS}
                           for name, index in (("intact", intact), ("knockout", knockout))}
        equal(set(report["confirmation"]), set(pairs), "confirmation endpoint coverage")
        contrasts = arrays(base / "measurement/contrasts.npz")
        equal(set(contrasts), set(vectors), "saved paired contrast names")
        if any(not identical(contrasts[key], value) for key, value in vectors.items()):
            raise ValueError("paired contrast bytes differ")
        equal(report["selection"], chosen, "scientific report choices")
        equal(report["confirmation_genome_lives"], len(rows) * 512, "confirmation life count")
    else:
        equal(report["no_applicable_branches"], True, "no-candidate report")
        equal(report["screen"], {}, "no-candidate screen")
        equal(report["confirmation"], {}, "no-candidate confirmation")
        if any((base / "measurement" / name).exists() for name in ("screen", "confirm", "selection.json")):
            raise ValueError("empty candidate policy contains unregistered scoring")
    lives = (len(genomes) + len(rows)) * 512
    equal(report["research_genome_lives"], lives, "total scientific lives")
    if lives > 19456 or not np.isclose(row_cpu, report["row_cpu_seconds"], rtol=0, atol=1e-6):
        raise ValueError("life or row CPU accounting differs")
    if row_cpu > budget["cpu_seconds"] + 1e-6:
        raise ValueError("raw row CPU exceeds complete worker CPU")
    summary = {"status": "complete", "research_genome_lives": lives, "screen_rows": len(genomes),
               "confirmation_rows": len(rows), "paired_seeds_per_stage": 512, "blocks": [98, 99],
               "branches": branches, "selection": chosen, "screen": screen, "confirmation": primary,
               "confirmation_means": means, "life_health": health, "genetic_replay": replay,
               "budget": {"monitored_worker_cpu_seconds": budget["cpu_seconds"], "row_cpu_seconds": row_cpu,
                          "cap_cpu_seconds": 7200, "simulation_threads": 2},
               "startup_validation": {"golden_lives": 2, "T": 200, "seed": 11,
                   "scope": "Numerical-identity full/fast goldens; separate from research, included in CPU."},
               "audit": {"raw_checkpoints": len(genomes) + len(rows), "raw_ledger_columns": 57,
                   "scored_columns": 60, "raw_and_aggregate_bitwise": True, "production_fitness_bitwise": True,
                   "contrast_bytes_exact": True, "independent_rank0_genetic_replay": True,
                   "independent_canonical_runtime_tables": True, "analysis_simulated_lives": 0},
               "limitations": protocol["limitations"] + [
                   "Independent replay reconstructs recorded genetics and final rank0, not RNG draws or selection.",
                   "Checkpoint byte hashes and the original pinned checkpoint-validation receipt are retained; "
                   "this NumPy analysis does not independently deserialize checkpoint objects."]}
    return summary, vectors


def markdown(summary):
    lines = ["# Contribution of duplicated-origin genes", "",
             "Every active gene with a duplication origin in both fixed G endpoints was deleted separately.",
             "The strongest paired loss per endpoint was selected on block98, even if negative, then tested",
             "on independent block99 lives. Every prescribed role uses 512 shared seeds in fast POOL, T1024.", "",
             "| G endpoint | Eligible genes | Chosen slot / origin | Fresh intact−knockout F ± SE |",
             "|---|---:|---|---:|"]
    for seed in RUNS:
        choice = summary["selection"][seed]
        if choice["status"] == NA:
            lines.append(f"| {seed} | 0 | Not applicable | Not applicable |")
        else:
            value = summary["confirmation"][seed]["F"]
            count = len(summary["branches"][seed]["slots"])
            lines.append(f"| {seed} | {count} | {choice['slot']} / {choice['origin_id']} | "
                         f"{value['mean']:+.6f} ± {value['se']:.6f} |")
    lines += ["", f"Completed {summary['research_genome_lives']:,} research genome-lives in "
              f"{summary['budget']['monitored_worker_cpu_seconds']:.6f} worker CPU-seconds (cap 7,200; two workers).",
              "Two existing numerical-identity golden lives are counted separately and included in CPU usage.",
              "Guards and extinction retain their production penalties. Negative and unresolved results remain.", "",
              "`measurement/` preserves every raw row, aggregate and decision. `dependencies/` retains the exact",
              "G lineages, endpoint files and checkpoint bytes; `operations/` retains launch/resource receipts.",
              "`prelaunch/` preserves the original public preparation. `review/` preserves the independent",
              "single-empty-branch test evidence. `summary.json` includes every screen effect and cost breakdown.", "",
              "Recompute without simulation or compilation (Python + NumPy):", "", "```bash",
              "python analyze.py --study . --check", "```", "", "Interpretation limits:", ""]
    lines.extend("- " + item for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def export(base, destination, summary, vectors):
    if summary["status"] != "complete":
        raise ValueError("cannot publish incomplete scientific conclusions")
    destination.mkdir(parents=True, exist_ok=True)
    historical = destination / "prelaunch"
    if not historical.exists():
        previous = read(destination / "provenance.json")
        equal(previous["status"], "prospective_preparation_not_released", "prelaunch provenance status")
        for name, record in previous["artifacts"].items():
            equal(sha(destination / name), record["sha256"], "original preparation " + name)
        for name in (*previous["artifacts"], "provenance.json"):
            target = historical / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(destination / name, target)
    protocol = read(base / "protocol.json")
    for folder in ("measurement", "inputs"):
        shutil.copytree(base / folder, destination / folder, dirs_exist_ok=True)
    shutil.copyfile(base / "protocol.json", destination / "protocol.json")
    (destination / "operations").mkdir(exist_ok=True)
    for name in ("measure.py", "run_budgeted.py", "ready.json", "budget.json", "run.log"):
        shutil.copyfile(operation(base, name), destination / "operations" / name)
    for name in protocol["source_identity"]:
        target = destination / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source(base, name), target)
    for name in protocol["helpers"]:
        shutil.copyfile(source(base, "scripts/" + name, helper=True), destination / "sources" / name)
    for study in [protocol["G_study"], *protocol["wait_for_studies"]]:
        src, dst = dependency(base, study), destination / "dependencies" / Path(study).name
        dst.mkdir(parents=True, exist_ok=True)
        names = ["protocol.json", "run_budgeted.py", "budget.json"]
        if study == protocol["G_study"]:
            names.append("audit_search.py")
            for seed in RUNS:
                names += [f"configs/s{seed}.yaml", *[f"runs/s{seed}/{name}" for name in
                          ("checkpoint.pt", "lineage.jsonl", "best_genome.json")]]
        for name in names:
            target = dst / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(operation(src, name), target)
    for name in ANALYZERS:
        shutil.copyfile(Path(__file__).with_name(name), destination / name)
    (destination / "review").mkdir(exist_ok=True)
    evidence = Path(__file__).parent / "independent_review.json"
    shutil.copyfile(evidence, destination / "review/independent_review.json")
    test_evidence = Path(__file__).parent / "test_single_branch_review.py"
    if not test_evidence.exists():
        test_evidence = test_evidence.with_suffix(".py.txt")
    shutil.copyfile(test_evidence, destination / "review/test_single_branch.py.txt")
    validation = Path(__file__).parent / "analysis_validation.json"
    if validation.exists():
        shutil.copyfile(validation, destination / "review/analysis_validation.json")
    save(destination / "summary.json", summary)
    np.savez_compressed(destination / "independent_contrasts.npz", **vectors)
    (destination / "README.md").write_text(markdown(summary))
    checked, rebuilt = analyze(destination)
    equal(checked, summary, "public independent summary")
    if set(rebuilt) != set(vectors) or any(not identical(rebuilt[key], value) for key, value in vectors.items()):
        raise ValueError("exported independent contrasts differ")
    artifacts = {str(path.relative_to(destination)): {"sha256": sha(path), "bytes": path.stat().st_size}
                 for path in sorted(destination.rglob("*")) if path.is_file()
                 and path != destination / "provenance.json"
                 and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts}
    save(destination / "provenance.json", {"status": "complete", "artifacts": artifacts,
         "research_genome_lives": summary["research_genome_lives"], "analysis_simulated_lives": 0})


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
    print(json.dumps({"status": "complete", "research_genome_lives": summary["research_genome_lives"],
                      "confirmation": {key: value["F"] for key, value in summary["confirmation"].items()},
                      "audit": summary["audit"]}, indent=2))


if __name__ == "__main__":
    main()
