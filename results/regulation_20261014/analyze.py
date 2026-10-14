"""Independent O ledger, paired-interaction and archive audit; NumPy only, never simulate or compile."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
from pathlib import Path

import numpy as np

ROOT = next((p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists()), None)
LABELS = ("founder_row38", "d_s51089_final_rank0", "d_s51090_final_rank0")
CONDITIONS = ("structure", "structure+genes_blind", "freeze")
FLAGS = (12, 44, 16)
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
    "The intervention masks local GRN inputs 18–22: own/incoming spike traces, contact fraction and receptor trace.",
    "Current genes, morphogens and sense/act plane cues remain; ordinary neuron receptor events and spikes continue.",
    "This tests ongoing dependence on specified local GRN inputs, not memory or a new algorithm.",
    "The mask also removes static contact information; a loss alone does not establish adaptation or use of "
    "changing evidence.",
    "Structure-minus-freeze also includes phenotype and effective-weight updates; it is not a pure GRN-state test.",
    "Both fixed descendants retain their different footprints and pre-fork states; there is no matched-body claim.",
    "Pending pre-fork events settle before 800, but this does not erase earlier membrane, chemical or world history.",
    "Structural checks compare terminal counts and cell-time, not equality of complete internal states.",
    "Both descendants and signs are retained. Three-SE flags are descriptive; unresolved effects are not zero.",
    "Life-level SE describes these fixed genotypes on 512 shared seeds, not uncertainty across evolution replicates.",
    "Guards/extinction retain production penalties. Only complete guard-free triplets enter structural checks.",
    "Fitness, captures and additive costs use 800..1536; path, last birth and terminal counts describe whole lives.",
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
    archived = base / "sources" / (Path(relative).name if helper else relative)
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


def constant_structure(data):
    output = []
    for index, label in enumerate(LABELS):
        arms = [{key: data[condition][key][index] for key in COLS} for condition in CONDITIONS]
        for row in arms:
            if np.any(row["status"].astype(np.int64) & (64 | 128)):
                raise ValueError("invalid life cannot be excluded only from structure")
            if np.any(row["births"] != 0) or np.any(row["deaths"] != 0) or np.any(row["last_birth"] >= 800):
                raise ValueError("structure-clamped tissue changed during accounting")
        complete = np.logical_and.reduce([(row["status"].astype(np.int64) & 7) == 0 for row in arms])
        for row in arms:
            if np.any(row["t_end"][complete] != 1536):
                raise ValueError("complete structure-clamped life ended early")
            for key in ("n_end", "n_S_end", "n_M_end", "n_H_end"):
                if not identical(arms[0][key][complete], row[key][complete]):
                    raise ValueError("structure-clamped triplet terminal population differs: " + key)
            if not np.allclose(row["live_time"][complete], 736 * row["n_end"][complete], rtol=1e-10, atol=1e-8):
                raise ValueError("structure-clamped cell-time differs from constant population")
        output.append({"label": label, "complete_triplets": int(complete.sum()),
                       "excluded_guard_or_extinct_triplets": int((~complete).sum()),
                       "all_fitness_rows_retained": True})
    return output


def effects(fitness):
    values = {condition: np.asarray(fitness[condition], dtype=np.float64) for condition in CONDITIONS}
    shape = values["structure"].shape
    if len(shape) != 2 or shape[0] != 3 or shape[1] < 2:
        raise ValueError("need three genotype rows and paired life columns")
    if any(value.shape != shape or not np.isfinite(value).all() for value in values.values()):
        raise ValueError("all three conditions must have finite paired arrays")
    result = {}
    for index, label in enumerate(LABELS[1:], 1):
        gains = {key: value[index] - value[0] for key, value in values.items()}
        result.update({label + "__gain__" + key: value for key, value in gains.items()})
        result[label + "__added_input_dependence"] = gains["structure"] - gains["structure+genes_blind"]
        result[label + "__added_regulation_effect"] = gains["structure"] - gains["freeze"]
    for index, label in enumerate(LABELS):
        result[label + "__input_loss"] = values["structure"][index] - values["structure+genes_blind"][index]
        result[label + "__regulation_effect"] = values["structure"][index] - values["freeze"][index]
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


def h_source(base, relative):
    archived = Path(base) / "motivation_H" / relative
    if archived.exists():
        return archived
    if ROOT is None:
        raise ValueError("missing archived fixed H provenance: " + relative)
    return ROOT / "results/hidden_20261014" / relative


def contrast_accounting(data, worlds, vectors):
    """Reconstruct every paired contrast's additive pieces within each seed before computing SE."""
    terms = {
        "income": effects({key: row["income"] / 736 for key, row in data.items()}),
        "cost_saving": effects({key: -row["cost"] / 736 for key, row in data.items()}),
        "guard_charge_saving": effects({key: -row["guard_charge"] / 736 for key, row in data.items()}),
        "extinction_charge_saving": effects({key: -row["extinct_charge"] for key, row in data.items()}),
    }
    components = {}
    for name, column, price in prices(worlds[CONDITIONS[0]]):
        for world in worlds.values():
            equal(prices(world), prices(worlds[CONDITIONS[0]]), "common accounting prices")
            equal(world["T"] - world["t_open"], 736, "common accounting window")
        components[name] = effects({key: -price * row[column] / 736 for key, row in data.items()})
    result = {}
    for contrast, value in vectors.items():
        pieces = {key: terms[key][contrast] for key in terms}
        residual = value - sum(pieces.values())
        if not np.allclose(residual, 0, rtol=0, atol=1e-9):
            raise ValueError("full contrast accounting does not reconcile: " + contrast)
        if not np.allclose(pieces["cost_saving"], sum(rows[contrast] for rows in components.values()),
                           rtol=0, atol=1e-9):
            raise ValueError("full contrast ordinary cost pieces do not reconcile: " + contrast)
        result[contrast] = {
            "fitness_contributions": {key: stats(raw) for key, raw in
                                      dict(pieces, accounting_residual=residual).items()},
            "cost_savings": {key: stats(raw[contrast]) for key, raw in components.items()},
        }
    return result


def audit_inputs(base):
    if (base / "prelaunch/provenance.json").exists():
        check_prelaunch(base / "prelaunch")
    protocol, ready = read(base / "protocol.json"), read(operation(base, "ready.json"))
    equal(protocol["labels"], list(LABELS), "fixed genotype labels")
    equal(protocol["conditions"], list(CONDITIONS), "fixed interventions")
    equal(protocol["seeds"], list(range(52_010_000, 52_010_512)), "ordered block101 seeds")
    for key, value in dict(seed_block=101, genome_lives=4608, threads=2, max_cpu_seconds=3600,
                           T=1536, t_fork=768, t_open=800).items():
        equal(protocol[key], value, "protocol " + key)
    for name, digest in ready["files"].items():
        path = base / name if name == "protocol.json" else operation(base, name)
        equal(sha(path), digest, "released file " + name)
    equal(set(ready["files"]), {"measure.py", "run_budgeted.py", "protocol.json"}, "release file names")
    for relative, digest in protocol["source_identity"].items():
        equal(sha(source(base, relative)), digest, "source " + relative)
    for name, digest in protocol["helpers"].items():
        equal(sha(source(base, "scripts/" + name, helper=True)), digest, "helper " + name)
    for relative, record in protocol["inputs"].items():
        equal(sha(base / relative), record["sha256"], "fixed input " + relative)
    for name, key in (("prepare.py", "prepare_sha256"), ("seed_review.json", "seed_review_sha256"),
                      ("PREREG.md", "prereg_sha256")):
        equal(sha(operation(base, name)), protocol[key], "prepared source/receipt " + name)
    expected_dependencies = {"outputs/autonomous_gene_interaction_20261014",
                             "outputs/autonomous_information_duration_20261014"}
    equal(set(protocol["wait_for_studies"]), expected_dependencies, "registered dependencies")
    equal(len(protocol["wait_for_studies"]), 2, "dependency count")
    equal(set(ready["dependencies"]), expected_dependencies, "released dependency names")
    for folder, files in ready["dependencies"].items():
        equal(set(files), {"protocol.json", "run_budgeted.py"}, "released dependency sources")
        for name, digest in files.items():
            path = base / "dependencies" / Path(folder).name / name
            if not path.exists():
                if ROOT is None:
                    raise ValueError("missing archived dependency: " + folder + "/" + name)
                path = ROOT / folder / name
            equal(sha(path), digest, "dependency " + folder + "/" + name)
    h_protocol, h_provenance = read(h_source(base, "protocol.json")), read(h_source(base, "provenance.json"))
    equal(h_provenance["status"], "complete", "completed motivating H archive")
    for relative in ("protocol.json", "summary.json", "inputs/D_manifest.json", "inputs/D_protocol.json",
                     "inputs/D_budget.json"):
        item = h_provenance["artifacts"][relative]
        equal(sha(h_source(base, relative)), item["sha256"], "fixed H provenance " + relative)
        equal(h_source(base, relative).stat().st_size, item["bytes"], "fixed H artifact size " + relative)
    for key in ("genome_raw_sha256", "fixed_endpoint_audits", "source_identity", "numerical_identity"):
        equal(protocol[key], h_protocol[key], "same fixed H input " + key)
    for relative, item in protocol["inputs"].items():
        equal(item["sha256"], h_protocol["inputs"][relative]["sha256"], "unchanged H genome/evaluator " + relative)
    tree = ast.parse(source(base, "src/life/spec.py").read_text())
    assigned = {node.targets[0].id: node.value for node in tree.body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    equal(ast.literal_eval(assigned["LEDGER_V2"]) + ast.literal_eval(assigned["LEDGER_V3"].right), LEDGER,
          "documented ledger order")
    cfg = (base / "inputs/evaluator.yaml").read_text()
    equal(re.findall(r"^\s*extinct_charge:\s*(\S+)\s*$", cfg, re.MULTILINE), ["true"], "production extinction policy")
    d_manifest = read(h_source(base, "inputs/D_manifest.json"))
    d_protocol = read(h_source(base, "inputs/D_protocol.json"))
    equal(read(h_source(base, "inputs/D_budget.json"))["status"], "complete", "fixed D completed budget")
    equal(sha(h_source(base, "inputs/D_protocol.json")), d_manifest["protocol_sha256"], "D protocol binding")
    equal(d_manifest["numerical_identity"], protocol["numerical_identity"], "D numerical identity")
    equal(d_protocol["expected_numerical_identity"], protocol["numerical_identity"], "D protocol numerical identity")
    equal(protocol["numerical_identity"]["sources"], protocol["source_identity"], "source identity nesting")
    genomes = []
    for index, label in enumerate(LABELS):
        record = read(base / "inputs" / (label + ".json"))
        equal(set(record["params"]), set(FIELDS), "genome parameter fields")
        genome = np.concatenate([np.asarray(record["params"][field], dtype=np.float32).reshape(-1) for field in FIELDS])
        digest = hashlib.sha256(genome.tobytes()).hexdigest()
        equal(digest, protocol["genome_raw_sha256"][index], "fixed raw genome " + label)
        equal(digest, d_manifest["genotype_sha256"][label.removeprefix("d_")], "D endpoint identity " + label)
        genomes.append(genome)
    for seed in ("51089", "51090"):
        item = protocol["fixed_endpoint_audits"][seed]
        equal(item["generation"], 16, "fixed D endpoint generation")
        equal(item["checkpoint_sha256"], d_manifest["checkpoint_sha256"][seed], "D checkpoint identity")
    manifest = read(base / "measurement/manifest.json")
    for key in ("labels", "conditions", "seeds", "seed_block", "genome_raw_sha256", "numerical_identity"):
        equal(manifest[key], protocol[key], "measurement manifest " + key)
    equal(manifest["protocol_sha256"], sha(base / "protocol.json"), "measurement protocol")
    equal(manifest["ready"], ready, "measurement release")
    equal(manifest["planned_genome_lives"], 4608, "measurement life count")
    saved = arrays(base / "measurement/genotypes.npz")
    if not identical(saved["genomes"], np.stack(genomes)):
        raise ValueError("saved raw genotypes differ from fixed JSON float32 bytes")
    equal(saved["labels"].tolist(), list(LABELS), "saved genotype labels")
    for condition, flags in zip(CONDITIONS, FLAGS):
        world = dict(d_manifest["worlds"]["1536"], t_fork=768, t_open=800, fork_flags=flags)
        equal(manifest["worlds"][condition], world, "world/price identity " + condition)
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
        raise ValueError("O did not finish within its fixed worker budget")
    equal(budget["cap_cpu_seconds"], 3600, "worker CPU cap")
    protocol, manifest = audit_inputs(base)
    equal(budget["ready"], manifest["ready"], "completed resource release")
    report = read(base / "measurement/report.json")
    equal(report["status"], "complete", "scientific report")
    equal(report["genome_lives"], 4608, "scientific report count")
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
    if raw_cpu > budget["cpu_seconds"] + .05:
        raise ValueError("raw CPU exceeds total monitored CPU")
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
    structure = constant_structure(data)
    equal([item["complete_triplets"] for item in structure],
          report["constant_tissue_validation"]["complete_three_arm_lives_by_genotype"], "constant triplet counts")
    decomposition = contrast_accounting(data, manifest["worlds"], vectors)
    primary_pieces = {label: decomposition[label + "__added_input_dependence"]["fitness_contributions"]
                      for label in LABELS[1:]}
    means = {condition: {label: {key: stats(value[key][index]) for key in
                                ("F", "captures", "clicks", "n_end", "n_H_end", "live_time", "path")}
                         for index, label in enumerate(LABELS)} for condition, value in data.items()}
    summary = {"status": "complete", "scientific_genome_lives": 4608, "paired_seeds": 512, "seed_block": 101,
               "accounting_window": [800, 1536], "startup_validation": {"golden_lives": 2, "T": 200, "seed": 11,
                   "scope": "One full plus one fast E1 numerical-identity golden; excluded from research lives."},
               "primary": {label: estimates[label + "__added_input_dependence"] for label in LABELS[1:]},
               "primary_fitness_contributions": primary_pieces, "contrasts": estimates,
               "contrast_accounting": decomposition, "conditions": pairs,
               "candidate_means": means, "constant_tissue": structure, "life_health": health,
               "budget": {"monitored_worker_cpu_seconds": budget["cpu_seconds"], "row_cpu_seconds": raw_cpu,
                          "cap_cpu_seconds": 3600, "simulation_threads": 2},
               "audit": {"raw_checkpoints": 9, "raw_ledger_columns": 57, "saved_scored_columns": 60,
                         "exact_raw_aggregate_bytes": True, "exact_production_extinction_bytes": True,
                         "exact_contrast_bytes": True, "numerical_pins_match_D": True, "analysis_simulated_lives": 0},
               "limitations": LIMITATIONS}
    return summary, {"seeds": np.asarray(protocol["seeds"], dtype=np.uint64), **vectors}


def markdown(summary):
    lines = ["# Local gene-regulation inputs with cell structure held constant", "",
             "Three fixed genotypes share 512 fresh seeds across three interventions. Both final 16-generation",
             "D descendants are retained. Interventions begin at 768; common accounting covers 800..1536.", "",
             "| Fixed endpoint | Added GRN-input dependence, ΔF ± SE | Descriptive 3-SE flag |", "|---|---:|---|"]
    for label, value in summary["primary"].items():
        flag = "positive" if value["positive_above_3se"] else (
            "negative" if value["negative_below_minus_3se"] else "unresolved")
        lines.append(f"| {label} | {value['mean']:+.6f} ± {value['se']:.6f} | {flag} |")
    lines += ["", "The primary difference is `(endpoint−row38)structure − (endpoint−row38)structure+genes_blind`.",
              "Subtraction happens within each life before uncertainty is calculated over 512 paired seeds.",
              "All three arms stop new division and apoptosis decisions. The first keeps normal gene regulation;",
              "the second masks five local GRN inputs; full freeze also stops gene/phenotype/effective-weight updates.",
              "Ordinary receptor events, neuron firing, spike messages, morphogens and plane cues remain.", "",
              "| Contrast | ΔF ± SE |", "|---|---:|"]
    for key, value in summary["contrasts"].items():
        lines.append(f"| {key.replace('__', ': ').replace('_', ' ')} | "
                     f"{value['mean']:+.6f} ± {value['se']:.6f} |")
    lines += ["", "All 16 contrasts include independently reconstructed income, each ordinary cost, guard and",
              "extinction contributions with paired SEs in `summary.json`. These pieces sum within each seed.", ""]
    counts = [item["complete_triplets"] for item in summary["constant_tissue"]]
    cpu = summary["budget"]["monitored_worker_cpu_seconds"]
    lines += [f"All 4,608 research genome-lives completed in {cpu:.6f} monitored CPU-seconds (cap 3,600).",
              "Two existing T200 numerical-identity golden lives are separate validation inside that cap.",
              f"Complete guard-free constant-structure triplets: {counts}, in row38 / D51089 / D51090 order.",
              "Guard/extinct exclusions apply only to structural validation; every valid fitness row is retained.", "",
              "`measurement/` preserves all nine full raw checkpoints, aggregates, paired vectors and reports.",
              "`inputs/`, `sources/`, `dependencies/` and `operations/` preserve genomes, source and resource",
              "receipts.",
              "`motivation_H/` binds these fixed inputs to the completed H archive and original D provenance.",
              "`prelaunch/` preserves the complete original preparation without changing its pinned bytes.", "",
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
        axes[1].errorbar([v["mean"] for v in values], np.arange(3) + (index - 0.5) * 0.16,
                         xerr=[3 * v["se"] for v in values], fmt="o", capsize=4, color=color,
                         label=label.replace("d_s", "D ").replace("_final_rank0", ""))
    axes[0].set_yticks([0, 1], ["D 51089", "D 51090"])
    axes[0].set_title("Added dependence on local GRN inputs")
    axes[1].set_yticks(np.arange(3), ["Structure clamped", "Structure + GRN inputs masked", "Full freeze"])
    axes[1].set_title("Each descendant's gain over row38")
    axes[1].legend(loc="best")
    for axis in axes:
        axis.axvline(0, color="#6b7280", linewidth=1)
        axis.invert_yaxis()
        axis.set_xlabel("Paired ΔF, mean ± 3 SE")
        axis.grid(axis="x", color="#e5e7eb")
    fig.suptitle("Fixed evolved endpoints; 512 shared seeds; accounting interval 800–1536", fontsize=14)
    for suffix in ("png", "svg"):
        fig.savefig(output / ("regulation_dependence." + suffix), dpi=170)
    plt.close(fig)


def check_prelaunch(folder):
    receipt = read(folder / "provenance.json")
    equal(receipt["status"], "prospective_preparation_not_released", "original preparation status")
    for relative, item in receipt["artifacts"].items():
        path = folder / relative
        equal(sha(path), item["sha256"], "preserved preparation bytes " + relative)
        equal(path.stat().st_size, item["bytes"], "preserved preparation size " + relative)
    return receipt


def export(base, destination, summary, vectors):
    destination.mkdir(parents=True, exist_ok=True)
    historical = destination / "prelaunch"
    if not historical.exists():
        previous = check_prelaunch(destination)
        for name in (*previous["artifacts"], "provenance.json"):
            target = historical / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(destination / name, target)
    check_prelaunch(historical)
    shutil.copytree(base / "measurement", destination / "measurement", dirs_exist_ok=True)
    shutil.copytree(base / "inputs", destination / "inputs", dirs_exist_ok=True)
    shutil.copyfile(base / "protocol.json", destination / "protocol.json")
    operations = destination / "operations"
    operations.mkdir(exist_ok=True)
    for name in ("measure.py", "run_budgeted.py", "ready.json", "budget.json", "run.log",
                 "prepare.py", "seed_review.json", "PREREG.md"):
        shutil.copyfile(base / name, operations / name)
    protocol = read(base / "protocol.json")
    for relative in ("protocol.json", "summary.json", "provenance.json", "inputs/D_protocol.json",
                     "inputs/D_manifest.json", "inputs/D_budget.json"):
        target = destination / "motivation_H" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(h_source(base, relative), target)
    ready = read(operation(base, "ready.json"))
    for folder, files in ready["dependencies"].items():
        for name in files:
            archived = base / "dependencies" / Path(folder).name / name
            path = archived if archived.exists() else ROOT / folder / name
            target = destination / "dependencies" / Path(folder).name / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    for relative in protocol["source_identity"]:
        target = destination / "sources" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source(base, relative), target)
    for name in protocol["helpers"]:
        shutil.copyfile(source(base, "scripts/" + name, helper=True), destination / "sources" / name)
    for name in ("analyze.py", "test_analysis.py"):
        shutil.copyfile(Path(__file__).with_name(name), destination / name)
    save(destination / "summary.json", summary)
    np.savez_compressed(destination / "independent_contrasts.npz", **vectors)
    (destination / "README.md").write_text(markdown(summary))
    plot(summary, destination)
    checked, recomputed = analyze(destination)
    equal(checked, summary, "public independent summary")
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
    save(destination / "provenance.json", {"status": "complete", "scientific_genome_lives": 4608,
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
