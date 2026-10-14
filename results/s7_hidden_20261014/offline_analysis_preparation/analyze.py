"""Independent Q ledger, paired-interaction and archive audit; NumPy only, never simulate or compile."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genome_audit as genes  # noqa: E402

ROOT = next((p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists()), None)
LABELS = ("founder_row29", "l_s51891_final_rank0", "l_s51892_final_rank0")
CONDITIONS = ("normal", "freeze", "freeze+lateral_off", "freeze+hidden_off")
FLAGS = (0, 16, 2064, 4112)
PROTOCOL_SHA = "9645eb61c343905bd870b5f7ef5329ef77c54fd2205fa739511e1798466b6545"
DEPENDENCY = "outputs/autonomous_next_step_20261014"
READY_FILES = {"protocol.json", "prepare.py", "measure.py", "run_budgeted.py", "test_measure.py", "PREREG.md"}
ANALYSIS_FILES = ("analyze.py", "genome_audit.py", "test_analysis.py", "test_analysis_workflow.py")
FIELDS = ("W", "b", "lam", "s0", "Q", "act", "A", "a0", "Dm", "km")
LEDGER = (
    "income", "live_time", "sec_int", "spikes", "kappa_sum", "contact_events", "claims", "births", "rejects",
    "rejects_wall", "deaths", "kills", "cost", "guard_charge", "net", "F", "n_end", "n_peak", "t_end", "status",
    "events", "beats", "P_int", "arrivals", "arrivals_dropped", "packets", "morph_secreted", "morph_decayed",
    "morph_lost", "morph_content_end", "morph_inflight_end", "chem_clamps", "last_birth", "ticks", "t_ext",
    "captures", "misses", "clicks", "b2_clicks", "respawns", "nudges", "rec_cand", "rec_accept", "rec_events",
    "rec_gain", "samples", "dist_sum", "zone_samples", "path", "X_end", "Y_end", "n_S_end", "n_M_end", "n_H_end",
    "live_S", "live_M", "live_H")
L = {name: i for i, name in enumerate(LEDGER)}
COLS = LEDGER + ("F_kernel", "extinct_charge", "window")
COSTS = (("living", "c_live", "live_time"), ("spiking", "c_spike", "spikes"),
         ("twitching", "c_tw", "kappa_sum"), ("messages", "c_msg", "contact_events"),
         ("division", "c_div", "claims"), ("secretion", "c_sec", "sec_int"),
         ("missed_clicks", "c_miss", "misses"), ("receptors", "c_rec", "rec_gain"))
LIMITATIONS = [
    "These are conditional spike-message effects in two fixed evolved descendants, not proof of a new algorithm.",
    "Hidden-off prevents new sends from z>=2; incoming and already emitted spikes, firing and chemistry continue. "
    "The suppressed messages retain their ordinary charge and can affect other cells indirectly.",
    "The three genotypes may have different frozen bodies and internal states; footprints are not matched.",
    "Freeze also stops gene-regulatory and phenotype/effective-weight updates. Normal-minus-freeze does not "
    "isolate development, and no adult-maturity claim follows.",
    "The settling interval removes bounded pending structural deliveries, not prior membrane, chemical or world "
    "history.",
    "Structural checks compare terminal population counts and cell-time, not equality of complete internal states.",
    "Both descendants and both signs are retained. Three-SE flags are descriptive; unresolved effects are not zero.",
    "Life-level SE describes these fixed genotypes on 512 shared seeds, not uncertainty across evolution replicates.",
    "Guards and extinction retain production penalties. Only complete guard-free triplets enter structural checks.",
    "Fitness, captures and additive costs use 800..1536; path, last birth and terminal counts describe whole lives.",
    "Independent recorded-genetics replay reconstructs the fixed endpoints, not RNG draws or search reliability.",
    "Checkpoint bytes and prospective validation receipts are bound; this NumPy analyzer does not deserialize them.",
]


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(label + " differs")


def identical(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def arrays(path):
    with np.load(path, allow_pickle=False) as value:
        return {key: value[key].copy() for key in value.files}


def source(base, relative, helper=False):
    archived = base / "sources" / relative
    if archived.exists():
        return archived
    if ROOT is None:
        raise ValueError("missing archived source: " + relative)
    return ROOT / relative


def operation(base, name):
    archived = base / "operations" / name
    return archived if archived.exists() else base / name


def stats(values, flags=False):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("paired statistics require finite one-dimensional values")
    mean, se = float(values.mean()), float(values.std(ddof=1) / np.sqrt(len(values)))
    result = {"mean": mean, "se": se, "n": len(values)}
    if flags:
        result.update(positive_above_3se=mean > 3 * se, negative_below_minus_3se=mean < -3 * se)
    return result


def check_stats(actual, saved, label):
    equal(actual["n"], saved["n"], label + " sample size")
    if any(not np.isclose(actual[key], saved[key], rtol=1e-11, atol=1e-12) for key in ("mean", "se")):
        raise ValueError(label + " paired estimate differs")
    for key in ("positive_above_3se", "negative_below_minus_3se"):
        if key in actual:
            equal(actual[key], saved[key], label + " descriptive flag")


def prices(world):
    return [(name, column, world[price]) for name, price, column in COSTS] + [
        ("decoy_clicks", "b2_clicks", max(0.0, -world["b2_value"]))]


def validate_row(row, world, n=512):
    """Rebuild every raw/production column, including guarded and extinct lives, without evaluator imports."""
    led = row["ledger"]
    if led.dtype != np.float64 or led.shape != (n, len(LEDGER)) or not np.isfinite(led).all():
        raise ValueError("invalid complete raw ledger")
    if any(row[key].shape != (n,) or not np.isfinite(row[key]).all() for key in COLS):
        raise ValueError("invalid production-scored column")
    for name in LEDGER:
        saved = row["F_kernel" if name == "F" else name]
        if not identical(saved, led[:, L[name]]):
            raise ValueError("raw ledger and saved production column differ: " + name)
    status = row["status"].astype(np.int64)
    if np.any(row["status"] != status) or np.any(status < 0) or np.any(status & (64 | 128)):
        raise ValueError("invalid implementation status cannot become evidence")
    ended = (status & (1 | 2 | 4)) != 0
    if np.any(~ended & (row["t_end"] != world["t0"] + world["T"])):
        raise ValueError("unexplained incomplete life")
    window = world["T"] - world["t_open"]
    if not np.all(row["window"] == window):
        raise ValueError("accounting window differs")
    cost = prices(world)[0][2] * row[prices(world)[0][1]]
    for _, column, price in prices(world)[1:]:
        cost = cost + price * row[column]
    guard = np.where((status & 6) != 0,
                     world["c_live"] * world["n_max"] * (world["t0"] + world["T"] - row["t_end"]), 0)
    extinction = world["c_live"] * np.where((status & 1) != 0,
        world["t0"] + world["T"] - np.maximum(row["t_ext"], world["t0"] + world["t_open"]), 0) / window
    income = world["R_cap"] * row["captures"] + max(0.0, world["b2_value"]) * row["b2_clicks"]
    reconstructed = {"income": income, "cost": cost, "guard_charge": guard, "net": income - cost - guard,
                     "extinct_charge": extinction,
                     "F_kernel": (income - cost - guard) / window}
    for key, value in reconstructed.items():
        if not np.allclose(row[key], value, rtol=1e-10, atol=1e-9):
            raise ValueError("independent accounting differs: " + key)
    if not identical(row["F"], row["F_kernel"] - row["extinct_charge"]):
        raise ValueError("production fitness differs from kernel minus extinction charge")
    for key in ("cpu_seconds", "wall_seconds"):
        if not np.isfinite(float(row[key])) or float(row[key]) < 0:
            raise ValueError("invalid saved row timing")
    return {"guarded": int(np.count_nonzero(status & 6)), "extinct": int(np.count_nonzero(status & 1)),
            "valid_other_status": int(np.count_nonzero(status & ~(1 | 2 | 4)))}


def frozen_structure(data):
    output = []
    for index, label in enumerate(LABELS):
        arms = [{key: data[condition][key][index] for key in COLS} for condition in CONDITIONS[1:]]
        for row in arms:
            if np.any(row["status"].astype(np.int64) & (64 | 128)):
                raise ValueError("invalid life cannot be excluded only from structure")
            if np.any(row["births"] != 0) or np.any(row["deaths"] != 0) or np.any(row["last_birth"] >= 800):
                raise ValueError("frozen tissue changed during accounting")
        complete = np.logical_and.reduce([(row["status"].astype(np.int64) & 7) == 0 for row in arms])
        for row in arms:
            if np.any(row["t_end"][complete] != 1536):
                raise ValueError("complete frozen life ended early")
            for key in ("n_end", "n_S_end", "n_M_end", "n_H_end"):
                if not identical(arms[0][key][complete], row[key][complete]):
                    raise ValueError("frozen triplet terminal population differs: " + key)
            if not np.allclose(row["live_time"][complete], 736 * row["n_end"][complete], rtol=1e-10, atol=1e-8):
                raise ValueError("frozen cell-time differs from constant population")
        output.append({"label": label, "complete_triplets": int(complete.sum()),
                       "excluded_guard_or_extinct_triplets": int((~complete).sum()),
                       "all_fitness_rows_retained": True})
    return output


def effects(fitness):
    values = {condition: np.asarray(fitness[condition], dtype=np.float64) for condition in CONDITIONS}
    shape = values["normal"].shape
    if len(shape) != 2 or shape[0] != 3 or shape[1] < 2:
        raise ValueError("need three genotype rows and paired life columns")
    if any(value.shape != shape or not np.isfinite(value).all() for value in values.values()):
        raise ValueError("all four conditions must have finite paired arrays")
    result = {}
    for index, label in enumerate(LABELS[1:], 1):
        gains = {key: value[index] - value[0] for key, value in values.items()}
        result.update({label + "__gain__" + key: value for key, value in gains.items()})
        for lesion in ("hidden", "lateral"):
            result[label + "__added_" + lesion + "_dependence"] = gains["freeze"] - gains["freeze+" + lesion + "_off"]
        result[label + "__gain_lost_under_freeze"] = gains["normal"] - gains["freeze"]
    for index, label in enumerate(LABELS):
        for lesion in ("hidden", "lateral"):
            result[label + "__frozen_" + lesion + "_loss"] = (
                values["freeze"][index] - values["freeze+" + lesion + "_off"][index])
    return result


def pair_terms(data, index, world):
    window = world["T"] - world["t_open"]
    pieces = {"income": (data["income"][index] - data["income"][0]) / window,
              "cost_saving": (data["cost"][0] - data["cost"][index]) / window,
              "guard_charge_saving": (data["guard_charge"][0] - data["guard_charge"][index]) / window,
              "extinction_charge_saving": data["extinct_charge"][0] - data["extinct_charge"][index]}
    pieces["accounting_residual"] = data["F"][index] - data["F"][0] - sum(pieces.values())
    if not np.allclose(pieces["accounting_residual"], 0, rtol=0, atol=1e-9):
        raise ValueError("paired income/cost/penalty decomposition does not reconcile")
    return pieces


def audit_inputs(base):
    equal(sha(base / "protocol.json"), PROTOCOL_SHA, "exact prospective Q protocol")
    equal(sha(Path(__file__).with_name("genome_audit.py")),
          "4a2d38965d87ec5bdabb7ab39947e99da35a49a7d827a025291def659b5c91ab", "genetic replay helper")
    protocol, ready = read(base / "protocol.json"), read(operation(base, "ready.json"))
    equal(protocol["labels"], list(LABELS), "fixed genotype labels")
    equal(protocol["conditions"], list(CONDITIONS), "fixed interventions")
    equal(protocol["seeds"], list(range(52_030_000, 52_030_512)), "ordered block103 seeds")
    for key, value in dict(seed_block=103, genome_lives=6144, threads=2, max_cpu_seconds=3600,
                           T=1536, t_fork=768, t_open=800).items():
        equal(protocol[key], value, "protocol " + key)
    for name, digest in ready["files"].items():
        path = base / name if name == "protocol.json" else operation(base, name)
        equal(sha(path), digest, "released file " + name)
    equal(set(ready["files"]), READY_FILES, "release file names")
    for relative, digest in protocol["source_identity"].items():
        equal(sha(source(base, relative)), digest, "source " + relative)
    for name, digest in protocol["helpers"].items():
        equal(sha(source(base, "scripts/" + name, helper=True)), digest, "helper " + name)
    for relative, record in protocol["inputs"].items():
        equal(sha(base / relative), record["sha256"], "fixed input " + relative)
    for relative, digest in protocol["preparation_pins"].items():
        equal(sha(base / relative), digest, "preparation " + relative)
    equal(protocol["wait_for_studies"], [DEPENDENCY], "resource dependency")
    equal(set(protocol["dependencies"]), {DEPENDENCY}, "dependency pin set")
    equal(ready["dependencies"], protocol["dependencies"], "released dependency pins")
    dependency = base / "dependency/P"
    if not (dependency / "budget.json").exists():
        dependency = ROOT / DEPENDENCY
    dep_budget = read(dependency / "budget.json")
    if dep_budget["status"] != "complete" or dep_budget.get("running") or dep_budget.get("queued"):
        raise ValueError("P dependency is not complete and empty")
    if (dep_budget["cap_cpu_seconds"] != 14400 or dep_budget["exit_code"] != 0
            or not np.isfinite(dep_budget["cpu_seconds"]) or not 0 < dep_budget["cpu_seconds"] < 14400):
        raise ValueError("P dependency resource completion is invalid")
    for name, digest in protocol["dependencies"][DEPENDENCY].items():
        equal(sha(dependency / name), digest, "P dependency " + name)
    tree = ast.parse(source(base, "src/life/spec.py").read_text())
    assigned = {node.targets[0].id: node.value for node in tree.body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    equal(ast.literal_eval(assigned["LEDGER_V2"]) + ast.literal_eval(assigned["LEDGER_V3"].right), LEDGER,
          "documented ledger order")
    cfg = (base / "inputs/evaluator.yaml").read_text()
    equal(re.findall(r"^\s*extinct_charge:\s*(\S+)\s*$", cfg, re.MULTILINE), ["true"], "production extinction policy")
    l_manifest = read(base / "inputs/L/confirmation/manifest.json")
    l_protocol = read(base / "inputs/L/protocol.json")
    equal(sha(base / "inputs/L/protocol.json"), l_manifest["protocol_sha256"], "L protocol binding")
    equal(l_manifest["numerical_identity"], protocol["numerical_identity"], "L numerical identity")
    equal(l_protocol["expected_numerical_identity"], protocol["numerical_identity"], "L protocol numerical identity")
    equal(protocol["numerical_identity"]["sources"], protocol["source_identity"], "source identity nesting")
    genomes = []
    for index, label in enumerate(LABELS):
        record = read(base / "inputs" / (label + ".json"))
        equal(set(record["params"]), set(FIELDS), "genome parameter fields")
        genome = np.concatenate([np.asarray(record["params"][field], dtype=np.float32).reshape(-1) for field in FIELDS])
        digest = hashlib.sha256(genome.tobytes()).hexdigest()
        equal(digest, protocol["genome_raw_sha256"][index], "fixed raw genome " + label)
        equal(digest, l_manifest["genotype_sha256"][label.removeprefix("l_")], "L endpoint identity " + label)
        genomes.append(genome)
    for index, seed in enumerate(("51891", "51892"), 1):
        item = protocol["fixed_endpoint_audits"][seed]
        folder = base / "inputs/L/runs" / ("s" + seed)
        equal(item["generation"], 16, "fixed L endpoint generation")
        equal(item["checkpoint_sha256"], l_manifest["checkpoint_sha256"][seed], "L checkpoint identity")
        equal(sha(folder / "checkpoint.pt"), item["checkpoint_sha256"], "L checkpoint bytes")
        equal(item["health"], {"pop_invalid": 0, "pop_mismatch": 0, "recheck_invalid": 0}, "L health")
        lines = [json.loads(line) for line in (folder / "lineage.jsonl").read_text().splitlines() if line.strip()]
        if any(set(child["ops"]) != {"mut"} for row in lines[1:] for child in row["children"]):
            raise ValueError("structural operation appeared in point-only L continuation")
        population, origins, replay = genes.replay(lines, genomes[0])
        if not identical(population[0], genomes[index]):
            raise ValueError("independent L genetic replay differs from final rank0")
        equal(replay["point_mutations"], item["genetic_replay"]["point_mutations_including_initial_copies"],
              "L point mutation count")
        equal(replay["duplication_events"], 0, "L duplication count")
        equal(replay["deletion_events"], 0, "L deletion count")
        equal(int((origins[0] >= 0).sum()), 8, "L active genes")
    manifest = read(base / "measurement/manifest.json")
    for key in ("labels", "conditions", "seeds", "seed_block", "genome_raw_sha256", "numerical_identity"):
        equal(manifest[key], protocol[key], "measurement manifest " + key)
    equal(manifest["protocol_sha256"], sha(base / "protocol.json"), "measurement protocol")
    equal(manifest["ready"], ready, "measurement release")
    equal(manifest["planned_genome_lives"], 6144, "measurement life count")
    saved = arrays(base / "measurement/genotypes.npz")
    if not identical(saved["genomes"], np.stack(genomes)):
        raise ValueError("saved raw genotypes differ from fixed JSON float32 bytes")
    equal(saved["labels"].tolist(), list(LABELS), "saved genotype labels")
    for condition, flags in zip(CONDITIONS, FLAGS):
        world = dict(l_manifest["worlds"]["1536"], t_fork=768, t_open=800, fork_flags=flags)
        equal(manifest["worlds"][condition], world, "world/price identity " + condition)
        equal(protocol["worlds"][condition], world, "prospective world " + condition)
    return protocol, manifest


def analyze(base):
    base = Path(base).resolve()
    budget_path = operation(base, "budget.json")
    if not budget_path.exists() or read(budget_path)["status"] != "complete":
        return {"status": "incomplete", "budget_status": read(budget_path)["status"]
                if budget_path.exists() else "not_started"}, {}
    budget = read(budget_path)
    if (budget["exit_code"] != 0 or not np.isfinite(budget["cpu_seconds"]) or not 0 < budget["cpu_seconds"] < 3600
            or budget["running"] or budget["queued"]):
        raise ValueError("Q did not finish within its fixed worker budget")
    equal(budget["cap_cpu_seconds"], 3600, "worker CPU cap")
    protocol, manifest = audit_inputs(base)
    equal(budget["ready"], manifest["ready"], "resource release binding")
    report = read(base / "measurement/report.json")
    equal(report["status"], "complete", "scientific report")
    equal(report["genome_lives"], 6144, "scientific report count")
    equal(report["planned_genome_lives"], 6144, "planned life count")
    equal(report["completed_genome_lives"], 6144, "actual completed life count")
    equal(report["limitations"], protocol["limitations"], "reported limitations")
    data, health, pairs, terms = {}, {}, {}, {}
    raw_cpu = 0.0
    for condition in CONDITIONS:
        folder = base / "measurement" / condition
        world = manifest["worlds"][condition]
        data[condition] = arrays(folder / "scores.npz")
        aggregate = data[condition]
        equal(aggregate["seeds"].tolist(), protocol["seeds"], "aggregate seed order")
        equal(aggregate["genome_indices"].tolist(), [0, 1, 2], "aggregate genotype order")
        if any(aggregate[key].shape != (3, 512) for key in COLS):
            raise ValueError("aggregate dimensions differ")
        row_index = read(folder / "row_index.json")
        equal(set(row_index), {f"rows/row_{index:04d}.npz" for index in range(3)}, "checkpoint row index")
        health[condition] = {}
        for index, label in enumerate(LABELS):
            name = f"rows/row_{index:04d}.npz"
            equal(sha(folder / name), row_index[name]["sha256"], "raw checkpoint " + condition + " " + label)
            row = arrays(folder / name)
            equal(row["seeds"].tolist(), protocol["seeds"], "raw seed order")
            equal(int(row["genome_index"]), index, "raw genotype index")
            health[condition][label] = validate_row(row, world)
            for column in COLS:
                if not identical(aggregate[column][index], row[column]):
                    raise ValueError("raw/aggregate bytes differ: " + condition + " " + column)
            equal(float(row["cpu_seconds"]), row_index[name]["cpu_seconds"], "raw CPU receipt")
            raw_cpu += float(row["cpu_seconds"])
        pairs[condition], terms[condition] = {}, {}
        for index, label in enumerate(LABELS[1:], 1):
            recorded = report["conditions"][condition][label]
            counts = {key: stats(aggregate[key][index] - aggregate[key][0]) for key in
                      ("F", "F_kernel", "n_end", "n_H_end", "live_time", "spikes", "packets", "misses", "clicks",
                       "captures", "path", "zone_samples", "samples")}
            for key, value in counts.items():
                check_stats(value, recorded[key], condition + " " + label + " " + key)
            pieces = pair_terms(aggregate, index, world)
            terms[condition][label] = pieces
            contributions = {key: stats(value) for key, value in pieces.items()}
            for key, value in contributions.items():
                check_stats(value, recorded["fitness_contributions"][key], "paired fitness piece " + key)
            components = {}
            for name, column, price in prices(world):
                value = stats(price * aggregate[column][0] / 736 - price * aggregate[column][index] / 736)
                check_stats(value, recorded["cost_saving_components"][name], "paired cost component " + name)
                components[name] = value
            pairs[condition][label] = dict(counts, fitness_contributions=contributions, cost_savings=components)
    if not np.isclose(raw_cpu, report["row_cpu_seconds"], rtol=0, atol=1e-7):
        raise ValueError("raw row CPU sum differs")
    if raw_cpu > budget["cpu_seconds"] + 1e-6:
        raise ValueError("raw CPU exceeds cumulative monitor accounting")
    vectors = effects({key: value["F"] for key, value in data.items()})
    recorded_vectors = arrays(base / "measurement/contrasts.npz")
    equal(recorded_vectors["seeds"].tolist(), protocol["seeds"], "paired contrast seed order")
    equal(set(recorded_vectors) - {"seeds"}, set(vectors), "paired contrast names")
    estimates = {}
    for key, value in vectors.items():
        if not identical(recorded_vectors[key], value):
            raise ValueError("independent paired contrast bytes differ: " + key)
        estimates[key] = stats(value, flags=True)
        check_stats(estimates[key], report["contrasts"][key], key)
    structure = frozen_structure(data)
    equal([item["complete_triplets"] for item in structure],
          report["frozen_tissue_validation"]["complete_three_arm_lives_by_genotype"], "frozen triplet counts")
    primary_pieces = {label: {name: stats(value - terms["freeze+hidden_off"][label][name])
                              for name, value in terms["freeze"][label].items()} for label in LABELS[1:]}
    means = {condition: {label: {key: stats(value[key][index]) for key in
                                ("F", "captures", "clicks", "n_end", "n_H_end", "live_time", "path")}
                         for index, label in enumerate(LABELS)} for condition, value in data.items()}
    summary = {"status": "complete", "scientific_genome_lives": 6144, "paired_seeds": 512, "seed_block": 103,
               "accounting_window": [800, 1536], "startup_validation": {"golden_lives": 2, "T": 200, "seed": 11,
                   "scope": "One full plus one fast E1 numerical-identity golden; excluded from research lives."},
               "primary": {label: estimates[label + "__added_hidden_dependence"] for label in LABELS[1:]},
               "primary_fitness_contributions": primary_pieces, "contrasts": estimates, "conditions": pairs,
               "candidate_means": means, "frozen_tissue": structure, "life_health": health,
               "budget": {"monitored_worker_cpu_seconds": budget["cpu_seconds"], "row_cpu_seconds": raw_cpu,
                          "cap_cpu_seconds": 3600, "simulation_threads": 2},
               "audit": {"raw_checkpoints": 12, "raw_ledger_columns": 57, "saved_scored_columns": 60,
                         "exact_raw_aggregate_bytes": True, "exact_production_extinction_bytes": True,
                         "exact_contrast_bytes": True, "numerical_pins_match_L": True,
                         "independent_recorded_genetics_replay": True, "analysis_simulated_lives": 0},
               "limitations": LIMITATIONS}
    return summary, {"seeds": np.asarray(protocol["seeds"], dtype=np.uint64), **vectors}


def markdown(summary):
    lines = ["# Hidden and lateral messages in fixed continuation tissues", "",
             "Three fixed genotypes share 512 fresh seeds across four interventions. Both final L descendants are",
             "retained regardless of sign. Tissue is frozen at 768; common accounting covers 800..1536.", "",
             "| Fixed endpoint | Added hidden dependence, ΔF ± SE | Descriptive 3-SE flag |", "|---|---:|---|"]
    for label, value in summary["primary"].items():
        flag = "positive" if value["positive_above_3se"] else (
            "negative" if value["negative_below_minus_3se"] else "unresolved")
        lines.append(f"| {label} | {value['mean']:+.6f} ± {value['se']:.6f} | {flag} |")
    lines += ["", "The primary difference is `(endpoint−row29)freeze − (endpoint−row29)freeze+hidden_off`.",
              "Subtraction happens within each life before uncertainty is calculated over 512 paired seeds.", "",
              "| Contrast | ΔF ± SE |", "|---|---:|"]
    for key, value in summary["contrasts"].items():
        lines.append(f"| {key.replace('__', ': ').replace('_', ' ')} | "
                     f"{value['mean']:+.6f} ± {value['se']:.6f} |")
    counts = [item["complete_triplets"] for item in summary["frozen_tissue"]]
    cpu = summary["budget"]["monitored_worker_cpu_seconds"]
    lines += ["", f"All 6,144 research genome-lives completed within {cpu:.6f} cumulative CPU-seconds (cap 3,600).",
              "The worker also ran two existing T200 numerical-identity golden lives, counted separately from",
              "research.",
              f"Complete guard-free frozen triplets: {counts}, in row29 / L51891 / L51892 order.",
              "Guard/extinct exclusions apply only to structural validation; every valid fitness row is retained.", "",
              "`measurement/` preserves all twelve full raw row checkpoints, aggregates, paired vectors and reports.",
              "`inputs/`, `sources/` and `operations/` preserve exact genomes, protocols, source and resource",
              "receipts.",
              "`prelaunch/` retains the complete original preparation archive without altering its pinned bytes.", "",
              "Recompute without simulation or compilation (Python + NumPy; Matplotlib only for `--plot`):", "",
              "```bash", "python analyze.py --study . --check", "```", "", "Interpretation limits:", ""]
    lines.extend("- " + item for item in LIMITATIONS)
    return "\n".join(lines) + "\n"


def plot(summary, output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), layout="constrained")
    colors = ("#205493", "#b45309")
    for index, (label, color) in enumerate(zip(LABELS[1:], colors)):
        primary = summary["primary"][label]
        axes[0].errorbar(primary["mean"], index, xerr=3 * primary["se"], fmt="o", capsize=5, color=color)
        values = [summary["contrasts"][label + "__gain__" + condition] for condition in CONDITIONS]
        axes[1].errorbar([v["mean"] for v in values], np.arange(4) + (index - 0.5) * 0.16,
                         xerr=[3 * v["se"] for v in values], fmt="o", capsize=4, color=color,
                         label=label.replace("l_s", "L ").replace("_final_rank0", ""))
    axes[0].set_yticks([0, 1], ["L 51891", "L 51892"])
    axes[0].set_title("Added dependence on hidden-cell spike sends")
    axes[1].set_yticks(np.arange(4), ["Normal", "Frozen", "Frozen + lateral off", "Frozen + hidden off"])
    axes[1].set_title("Each descendant's gain over row29")
    axes[1].legend(loc="best")
    for axis in axes:
        axis.axvline(0, color="#6b7280", linewidth=1)
        axis.invert_yaxis()
        axis.set_xlabel("Paired ΔF, mean ± 3 SE")
        axis.grid(axis="x", color="#e5e7eb")
    fig.suptitle("Fixed evolved endpoints; 512 shared seeds; accounting interval 800–1536", fontsize=14)
    for suffix in ("png", "svg"):
        fig.savefig(output / ("hidden_dependence." + suffix), dpi=170)
    plt.close(fig)


def export(base, destination, summary, vectors):
    base, destination = Path(base).resolve(), Path(destination).resolve()
    if base == destination or summary["status"] != "complete":
        raise ValueError("completed export needs a separate public preparation archive")
    destination.mkdir(parents=True, exist_ok=True)
    historical = destination / "prelaunch"
    if historical.exists():
        raise ValueError("prelaunch already exists; inspect rather than reset the archive")
    previous = read(destination / "provenance.json")
    equal(previous["status"], "prospective_preparation_not_released", "original preparation status")
    for name, record in previous["artifacts"].items():
        equal(sha(destination / name), record["sha256"], "prelaunch artifact " + name)
        equal((destination / name).stat().st_size, record["bytes"], "prelaunch size " + name)
    for name in (*previous["artifacts"], "provenance.json"):
        target = historical / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(destination / name, target)
    shutil.copytree(base / "measurement", destination / "measurement", dirs_exist_ok=True)
    shutil.copytree(base / "inputs", destination / "inputs", dirs_exist_ok=True)
    shutil.copyfile(base / "protocol.json", destination / "protocol.json")
    operations = destination / "operations"
    operations.mkdir(exist_ok=True)
    for name in (*READY_FILES, "ready.json", "budget.json", "run.log"):
        shutil.copyfile(operation(base, name), operations / name)
    protocol = read(base / "protocol.json")
    for relative in protocol["source_identity"]:
        target = destination / "sources" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source(base, relative), target)
    for name in protocol["helpers"]:
        target = destination / "sources/scripts" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source(base, "scripts/" + name, helper=True), target)
    dependency = base / "dependency/P"
    if not (dependency / "budget.json").exists():
        dependency = ROOT / DEPENDENCY
    (destination / "dependency/P").mkdir(parents=True, exist_ok=True)
    for name in ("protocol.json", "run_budgeted.py", "budget.json"):
        shutil.copyfile(dependency / name, destination / "dependency/P" / name)
    for name in ANALYSIS_FILES:
        shutil.copyfile(Path(__file__).with_name(name), destination / name)
    save(destination / "summary.json", summary)
    np.savez_compressed(destination / "independent_contrasts.npz", **vectors)
    (destination / "README.md").write_text(markdown(summary))
    plot(summary, destination)
    checked, recomputed = analyze(destination)
    equal(checked, summary, "public independent summary")
    equal(set(recomputed), set(vectors), "public vector set")
    for key, values in vectors.items():
        if not identical(values, recomputed[key]):
            raise ValueError("exported paired vector bytes differ")
    for condition in CONDITIONS:
        for index in range(3):
            relative = f"measurement/{condition}/rows/row_{index:04d}.npz"
            equal(sha(base / relative), sha(destination / relative), "exported raw checkpoint bytes")
    artifacts = {str(path.relative_to(destination)): {"sha256": sha(path), "bytes": path.stat().st_size}
                 for path in sorted(destination.rglob("*")) if path.is_file()
                 and path != destination / "provenance.json" and "__pycache__" not in path.parts
                 and ".pytest_cache" not in path.parts}
    save(destination / "provenance.json", {"status": "complete", "scientific_genome_lives": 6144,
                                           "artifacts": artifacts, "analysis_simulated_lives": 0})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args()
    summary, vectors = analyze(args.study)
    if summary["status"] != "complete":
        print(json.dumps(summary))
        return
    if args.check:
        record = read(args.study / "provenance.json")
        equal(record["status"], "complete", "public archive status")
        for name, item in record["artifacts"].items():
            equal(sha(args.study / name), item["sha256"], "public artifact " + name)
            equal((args.study / name).stat().st_size, item["bytes"], "public artifact size " + name)
        equal(read(args.study / "summary.json"), summary, "public independent summary")
        equal((args.study / "README.md").read_text(), markdown(summary), "public readable summary")
        saved = arrays(args.study / "independent_contrasts.npz")
        equal(set(saved), set(vectors), "public contrast names")
        if any(not identical(saved[key], value) for key, value in vectors.items()):
            raise ValueError("public independent contrast bytes differ")
    if args.export:
        export(args.study.resolve(), args.export.resolve(), summary, vectors)
    if args.plot:
        plot(summary, args.study)
    print(json.dumps({"status": summary["status"], "primary": summary["primary"],
                      "audit": summary["audit"]}, indent=2))


if __name__ == "__main__":
    main()
