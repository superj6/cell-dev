"""Fail-closed, NumPy-only analysis of the complete registered Y gradient pilot.

Reuses study I row accounting and reviewed archive/receipt patterns. No engine,
mutation, worker, controller, compilation or simulation imports are executed.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location("gradient_offline_accounting", Path(__file__).with_name("offline_accounting.py"))
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)
REVIEWED_PROTOCOL_SHA256 = "1880ff6e21b4689031e892d9dc6765a8d9673a35efeefb213acf268f5370adf4"
PARENTS = ("D90", "L92")
FIELDS = ("W", "b", "lam", "s0", "Q", "act", "A", "a0", "Dm", "km")
FOUNDER_SHA = {"D90": "1287ee4421f88fc108c073eae282f625bd0e340a5e4b12d590cd27cbc046bfac",
               "L92": "8f14c79b8bea73c08dff7f6bc1094dc848534f9f2d45598c99c4351cf364cf27"}
BLOCKS = {"screen": 117, "confirm": 118, "calibration": 119}
N = {"calibration": 2, "screen": 32, "confirm": 512}
MUTATION_RNG = {"D90": 53117, "L92": 53118}
MUTATION = {"n_mut": 2, "p_cell": .5, "scale_n_mut": True, "dup_rate": 0, "del_rate": 0, "split": False}
SCOPE = {"total_cpu_seconds": 5400, "startup_screen_cpu_seconds": 3400,
         "confirmation_reserve_cpu_seconds": 2000, "max_workers": 1,
         "threads_per_worker": 2, "research_lives": 6208, "validation_lives": 10}
GOLDEN = {"all": "ebb3ad6fcad2d938", "ledger_sha256": "b622f9afad48d6ec5b39b003efba82f25e7e6a764a015fe40398b3a6bbd81251"}
GOLDEN_SCOPE = {"abi": 3, "seed": 11, "T": 200, "full": 1, "fast": 1}
LIMITATIONS = [
    "This is a one-step ordinary-mutation gradient diagnostic from two fixed founders, not an evolution continuation.",
    "Each winner was selected by its whole32-life screening mean; all64 mutants and negative or null confirmation effects remain included.",
    "Confirmation SE describes these fixed selected genomes over512 paired world seeds, not uncertainty across independent evolutionary searches.",
    "Low-light capture gains do not isolate memory, prediction or a specific algorithm; growth, movement, firing and ordinary costs can contribute.",
    "The world's information payoff supports this phase0 diagnostic; capability-specific admission remains incomplete.",
    "Natural extinction and valid paid guards remain in production fitness; invalid implementation failures invalidate the complete verdict.",
    "Four two-seed calibration batches estimate feasibility but cannot bound the cost of all mutants or selected winners.",
    "Mutation replay independently reruns the same pinned operator; it is not a separate mutation implementation.",
]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_sha(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def read(path):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    def bad(value):
        raise ValueError("nonfinite JSON number: " + value)

    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=bad)


def inside(base, name):
    if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("unsafe input path")
    path = (Path(base) / name).resolve()
    if not path.is_relative_to(Path(base).resolve()):
        raise ValueError("input path leaves bundle")
    return path


def external(base, name):
    for root in (Path(base) / "production", Path(base) / "original", Path(base).resolve().parents[1]):
        path = inside(root, name)
        if path.is_file():
            return path
    raise FileNotFoundError("missing pinned external input: " + name)


def operation(base, name):
    path = inside(base, name)
    return path if path.is_file() else inside(Path(base) / "operations", name)


def pins(base, table, external_paths=False, operational=False):
    if not isinstance(table, dict) or not table:
        raise ValueError("empty required pin map")
    for name, digest in table.items():
        path = external(base, name) if external_paths else (operation(base, name) if operational else inside(base, name))
        if not isinstance(digest, str) or len(digest) != 64 or sha(path) != digest:
            raise ValueError("changed pinned input: " + name)


def number(value, label, ceiling=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid " + label)
    if ceiling is not None and value >= ceiling:
        raise ValueError(label + " reaches stop threshold")
    return float(value)


def npz(path):
    with np.load(path, allow_pickle=False) as record:
        if len(record.files) != len(set(record.files)):
            raise ValueError("duplicate archive array names")
        return {key: record[key].copy() for key in record.files}


def json_bytes(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def assert_equal(actual, expected, label):
    if actual != expected:
        raise ValueError(label + " differs")


def verify_protocol(base):
    assert_equal(sha(base / "protocol.json"), REVIEWED_PROTOCOL_SHA256, "reviewed protocol")
    p = read(base / "protocol.json")
    for key, expected in (("study", "Y ordinary visibility gradient"), ("world_decision", "complete"),
                          ("monitor_scope", SCOPE), ("founder_raw_sha256", FOUNDER_SHA),
                          ("seed_blocks", BLOCKS), ("mutation_rng", MUTATION_RNG)):
        assert_equal(p[key], expected, key)
    seeds = {stage: list(range(51_000_000 + 10_000 * BLOCKS[stage],
                              51_000_000 + 10_000 * BLOCKS[stage] + n)) for stage, n in N.items()}
    assert_equal(p["seeds"], seeds, "exact ordered stage seeds")
    pins(base, p["file_pins"])
    pins(base, p["production_pins"], external_paths=True)
    metadata = p["expected_startup_metadata"]
    assert_equal(metadata["sources"], {k: v for k, v in p["production_pins"].items() if k.startswith("src/")},
                 "complete production source closure")
    if metadata["aten_cpu_capability"] != "avx2" or metadata["torch_cpu_capability"] != "AVX2":
        raise ValueError("numerical capability differs")
    snapshot = read(base / "inputs/reviews/approved_blink_world.json")
    assert_equal(p["world"], snapshot["production"]["world"], "approved complete world")
    w = p["world"]
    if (w["name"] != "catch_speck_blink20_20_l4" or w["T"] != 1024 or w["t_open"] != 0
            or (w["visibility_mode"], w["visibility_on"], w["visibility_off"], w["visibility_low"]) != (2, 20, 20, 0)
            or (w["d0"], w["d_min"], w["sigma"], w["lam_s"], w["flags"], w["fork_flags"]) != (1, .5, .6, 2, 0, 0)):
        raise ValueError("fixed visibility physics differs")
    tree = ast.parse(external(base, "src/life/spec.py").read_text())
    assignments = {node.targets[0].id: node.value for node in tree.body
                   if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    ledger = (ast.literal_eval(assignments["LEDGER_V2"]) + ast.literal_eval(assignments["LEDGER_V3"].right)
              + ast.literal_eval(assignments["LEDGER_V4"].right))
    assert_equal(ledger, A.LEDGER, "independent ledger order")
    registration = read(base / "registration.json")
    for key, expected in (("status", "registered"), ("world", w["name"]), ("seed_blocks", BLOCKS),
                          ("mutation_rng", MUTATION_RNG), ("seeds", seeds)):
        assert_equal(registration[key], expected, "root registration " + key)
    claim = read(base / "panel_generation_claim.json")
    assert_equal(claim, {"parents": list(PARENTS), "mutation_rng": MUTATION_RNG,
                        "mutation_helper_sha256": p["production_pins"]["scripts/taskvar_gradient.py"],
                        "registration_sha256": sha(base / "registration.json")}, "one generation claim")
    replay = read(base / "analysis/genetic_replay.json")
    for key, expected in (("status", "pass"), ("protocol_sha256", REVIEWED_PROTOCOL_SHA256),
                          ("registration_sha256", sha(base / "registration.json")),
                          ("script_sha256", sha(base / "analysis/genetic_replay.py")),
                          ("production_pins", p["production_pins"]), ("simulation_calls", 0),
                          ("compilation_calls", 0), ("mutation_replay_calls", 2),
                          ("aten_cpu_capability", "avx2"), ("torch_cpu_capability", "AVX2")):
        assert_equal(replay[key], expected, "independent genetic replay " + key)
    panels = {}
    for parent in PARENTS:
        prefix = base / "inputs" / parent
        table = np.load(prefix / "genomes.npy", allow_pickle=False)
        if table.dtype != np.float32 or table.shape != (65, 875) or not np.isfinite(table).all():
            raise ValueError("complete original mutant table required")
        founder = read(prefix / "parent.json")
        assert_equal(set(founder["params"]), set(FIELDS), "founder parameter fields")
        original = np.concatenate([np.asarray(founder["params"][key], dtype=np.float32).reshape(-1) for key in FIELDS])
        if not A.identical(original, table[0]) or raw_sha(original) != FOUNDER_SHA[parent]:
            raise ValueError("fixed founder changed")
        hashes = [raw_sha(row) for row in table]
        assert_equal(hashes, p["panel_genotype_sha256"][parent], "entire fixed candidate table")
        manifest = read(prefix / "panel_manifest.json")
        assert_equal(manifest, {"genomes_sha256": raw_sha(table), "mutants": 64,
                               "parent_sha256": sha(prefix / "parent.json"), "config_sha256": sha(prefix / "config.yaml"),
                               "mutation_ops_sha256": sha(prefix / "mutation_ops.json"), "mutation_seed": MUTATION_RNG[parent],
                               "mutation_helper_sha256": p["production_pins"]["scripts/taskvar_gradient.py"],
                               "mutation": MUTATION}, "panel generation manifest")
        item = replay["backgrounds"][parent]
        for key, expected in (("mutation_rng", MUTATION_RNG[parent]), ("rows", 65), ("columns", 875),
                              ("dtype", "float32"), ("all_rows_byte_identical", True), ("recorded_operations_equal", True),
                              ("config_world_equal", True), ("abi", 4), ("extinct_charge", True), ("threads", 2),
                              ("raw_row_sha256", hashes), ("duplicate_rows_retained", 65 - len({row.tobytes() for row in table}))):
            assert_equal(item[key], expected, "replayed panel " + key)
        required = {str((prefix / name).relative_to(base)): sha(prefix / name) for name in
                    ("parent.json", "genomes.npy", "mutation_ops.json", "panel_manifest.json", "config.yaml")}
        assert_equal(item["file_pins"], required, "replay input binding")
        panels[parent] = table
    assert_equal(p["calibration_rule"], {"rate": "max(parent_two_seed_CPU,mutant1_two_seed_CPU)/2 per background",
                 "safety_multiplier": 1.5, "startup_screen_projection_ceiling": 3390,
                 "confirmation_projection_ceiling": 1990, "calibration_lives": 8, "numerical_goldens": GOLDEN_SCOPE},
                 "registered feasibility rule")
    return p, panels


def identity(value):
    keys = ("pid", "ppid", "pgid", "start_ticks")
    if any(type(value.get(key)) is not int or value[key] < (0 if key == "ppid" else 1) for key in keys):
        raise ValueError("incomplete process identity")
    return {key: value[key] for key in keys}


def resources(base, p):
    ready = read(operation(base, "ready.json"))
    assert_equal(ready["status"], "released", "release status")
    assert_equal(ready["production_pins"], p["production_pins"], "released production pins")
    required = dict(p["file_pins"])
    for name in ("protocol.json", "monitor.py", "resource_clearance.json", "analysis/analyze.py",
                 "analysis/offline_accounting.py", "analysis/genetic_replay.py", "analysis/genetic_replay.json"):
        required[name] = sha(operation(base, name))
    if any(ready["source_pins"].get(key) != digest for key, digest in required.items()):
        raise ValueError("release does not bind all prepared analysis and inputs")
    pins(base, ready["source_pins"], operational=True)
    # The released reader remains immutable; this separate correction is pinned by the postanalysis review.
    if (sha(base / "analysis/analyze.py") != "1f8bc838666f6ba2e58e8a64aac4506fc2a94488850d50a20de29c06120449d7"
            or sha(A.__file__) != ready["source_pins"]["analysis/offline_accounting.py"]):
        raise ValueError("original released analyzer or executing accountant changed")
    clearance = read(operation(base, "resource_clearance.json"))
    if clearance["status"] != "cleared" or clearance["all_processes_exited"] is not True:
        raise ValueError("prior work was not cleared")
    pins(base, clearance["budget_pins"], external_paths=True)
    for name in clearance["budget_pins"]:
        old = read(external(base, name))
        if (old.get("status") not in ("complete", "incomplete", "cpu_budget_exhausted", "job_failed", "monitor_failed")
                or old.get("cleanup_error") or old.get("running") or old.get("queued")):
            raise ValueError("dependency budget is not cleanly terminal")
    if not clearance.get("processes") or not clearance.get("process_groups"):
        raise ValueError("dependency identities missing")
    for process in clearance["processes"]:
        if any(type(process.get(k)) is not int or process[k] <= 0 for k in ("pid", "start_ticks")):
            raise ValueError("dependency process identity missing")
    attempt = read(operation(base, "attempt.json"))
    monitor = identity(attempt["monitor"])
    assert_equal(attempt["ready_sha256"], sha(operation(base, "ready.json")), "single attempt release")
    budget = read(operation(base, "budget.json"))
    for key, expected in (("status", "complete"), ("exit_code", 0), ("phase", "confirmation"),
                          ("cap_cpu_seconds", 5400), ("startup_screen_cap_cpu_seconds", 3400),
                          ("confirmation_reserve_cpu_seconds", 2000), ("running", {}), ("queued", []),
                          ("completed", [{"name": "gradient", "exit_code": 0}]), ("ready", ready)):
        assert_equal(budget[key], expected, "terminal monitor " + key)
    if budget.get("reason") is not None or budget.get("cleanup_error") or budget.get("error"):
        raise ValueError("monitor recorded a failure")
    total = number(budget["cpu_seconds"], "total CPU", 5390)
    screen = number(budget["startup_screen_cpu_seconds"], "startup/screen CPU", 3390)
    if total < screen:
        raise ValueError("CPU accounting went backwards")
    process = budget["process_identities"]
    if len(process) != 2 or [x["name"] for x in process] != ["monitor", "gradient"]:
        raise ValueError("one monitor and one worker identity required")
    assert_equal(identity(process[0]), monitor, "attempt monitor identity")
    worker = identity(process[1])
    if worker["ppid"] != monitor["pid"] or worker["pid"] != worker["pgid"]:
        raise ValueError("worker was not an owned process group")
    assert_equal(budget["owned_process_groups"], [worker["pid"]], "owned worker group")
    if not budget["affinity"] or any(type(x) is not int or not 0 <= x < 12 for x in budget["affinity"]):
        raise ValueError("registered CPU affinity differs")
    return budget, {"total_cpu_seconds": total, "startup_screen_cpu_seconds": screen,
                    "confirmation_cpu_seconds": total - screen, "first_attempt_only": True}


def check_startup(base, p):
    item = read(base / "startup_identity.json")
    assert_equal(item["numerical_identity_invocations"], 1, "single numerical golden invocation")
    assert_equal(item["golden_lives"], GOLDEN_SCOPE, "retained two-life engineering replay")
    recorded = item["identity"]
    assert_equal({k: v for k, v in recorded.items() if k not in ("kernels", "golden")},
                 p["expected_startup_metadata"], "startup numerical/source identity")
    assert_equal(item["preexpected_fields"], sorted(p["expected_startup_metadata"]), "startup metadata scope")
    assert_equal(item["newly_captured_fields"], ["kernels", "golden"], "new startup fields")
    assert_equal(recorded["golden"], GOLDEN, "existing ABI3 full/fast golden")
    if set(recorded["kernels"]) != {"False", "True"}:
        raise ValueError("both kernel builds required")
    binaries = {sha(path) for path in (base / "build-cache").rglob("*.so")}
    if not set(recorded["kernels"].values()).issubset(binaries):
        raise ValueError("startup compiled kernel bytes are missing or changed")
    return item


def expected_paths(selection):
    return {stage + f"/row_{index:04d}.npz" for stage, indices in
            (("calibration", [0, 1]), ("screen", range(65)), ("confirm", [0, selection])) for index in indices}


def load_rows(base, p):
    selected = read(base / "selection.json")
    assert_equal(set(selected), set(PARENTS), "both frozen selections")
    records, indexes, rawpins, stage_cpu = {}, {}, {}, dict.fromkeys(N, 0.0)
    for parent in PARENTS:
        chosen = selected[parent]["genome_row"]
        if type(chosen) is not int or not 1 <= chosen <= 64:
            raise ValueError("selection must be an original mutant row")
        assert_equal(selected[parent], {"genome_row": chosen, "raw_sha256": p["panel_genotype_sha256"][parent][chosen]},
                     "selected original genome")
        folder = base / "measurement" / parent
        index = read(folder / "row_index.json")
        assert_equal(set(index), expected_paths(chosen), "complete69-row index")
        indexes[parent], records[parent] = index, {}
        rawpins[str((folder / "row_index.json").relative_to(base))] = sha(folder / "row_index.json")
        for stage, indices in (("calibration", [0, 1]), ("screen", list(range(65))), ("confirm", [0, chosen])):
            rows = {}
            for number_ in indices:
                name = stage + f"/row_{number_:04d}.npz"
                path = folder / name
                assert_equal(sha(path), index[name]["sha256"], "raw row pin")
                row = npz(path)
                assert_equal(set(row), set(A.COLS) | {"identity", "seeds", "genome_index", "ledger", "cpu_seconds", "wall_seconds"},
                             "raw row schema")
                expected = {"protocol_sha256": REVIEWED_PROTOCOL_SHA256, "background": parent, "stage": stage,
                            "genome_index": number_, "genome_sha256": p["panel_genotype_sha256"][parent][number_],
                            "seeds": p["seeds"][stage]}
                if row["identity"].shape != () or row["identity"].dtype.kind != "U" or str(row["identity"]) != canonical(expected):
                    raise ValueError("row identity disagrees with fixed protocol")
                if (row["genome_index"].shape != () or row["genome_index"].dtype.kind not in "iu"
                        or int(row["genome_index"]) != number_
                        or not A.identical(row["seeds"], np.asarray(p["seeds"][stage], dtype=np.uint64))):
                    raise ValueError("row genome index or ordered seeds differ")
                A.validate_row(row, p["world"], N[stage])
                cpu = number(index[name]["cpu_seconds"], "indexed row CPU")
                assert_equal(cpu, float(row["cpu_seconds"]), "raw/indexed row CPU")
                stage_cpu[stage] += cpu
                rows[number_] = row
                rawpins[str(path.relative_to(base))] = sha(path)
            score_path = folder / stage / "scores.npz"
            score = npz(score_path)
            assert_equal(set(score), set(A.COLS) | {"seeds", "genome_indices"}, "aggregate schema")
            if (not A.identical(score["seeds"], np.asarray(p["seeds"][stage], dtype=np.uint64))
                    or not A.identical(score["genome_indices"], np.asarray(indices))):
                raise ValueError("aggregate stage identities differ")
            for key in A.COLS:
                if not A.identical(score[key], np.stack([rows[i][key] for i in indices])):
                    raise ValueError("aggregate and raw stage columns differ: " + key)
            rawpins[str(score_path.relative_to(base))] = sha(score_path)
            records[parent][stage] = rows
        actual = min(range(1, 65), key=lambda i: (-float(records[parent]["screen"][i]["F"].mean()), i))
        assert_equal(chosen, actual, "whole32-life selection with row-order ties")
    return selected, records, indexes, stage_cpu, rawpins


def phases(base, p, budget, index, selected, stage_cpu):
    assert_equal(set(budget["phase_receipts"]), {"calibration_complete", "screens_complete"}, "both phase acknowledgments")
    receipts = {}
    previous_cpu = 0.0
    for name in ("calibration_complete", "screens_complete"):
        request_path = base / "requests" / (name + ".json")
        receipt = read(base / "monitor_receipts" / (name + ".json"))
        request = read(request_path)
        assert_equal(receipt, budget["phase_receipts"][name], "terminal phase receipt binding")
        for key, expected in (("status", "allowed"), ("protocol_sha256", REVIEWED_PROTOCOL_SHA256),
                              ("attempt_sha256", sha(operation(base, "attempt.json"))), ("request_sha256", sha(request_path))):
            assert_equal(receipt[key], expected, "phase receipt " + key)
        assert_equal(request["protocol_sha256"], REVIEWED_PROTOCOL_SHA256, "phase request protocol")
        cpu = number(receipt["cpu_seconds"], "phase CPU", 3390)
        if cpu < previous_cpu:
            raise ValueError("phase CPU went backwards")
        previous_cpu = cpu
        expected_snapshot = {}
        for parent in PARENTS:
            names = [f"calibration/row_{i:04d}.npz" for i in (0, 1)]
            if name == "screens_complete":
                names += [f"screen/row_{i:04d}.npz" for i in range(65)]
            expected_snapshot[parent] = {key: index[parent][key] for key in names}
            partial_sha = hashlib.sha256(json_bytes(expected_snapshot[parent])).hexdigest()
            assert_equal(request["row_index_sha256"][parent], partial_sha, "phase row-index snapshot bytes")
        assert_equal(receipt["row_snapshot"], expected_snapshot, "all previously acknowledged raw rows")
        if name == "calibration_complete":
            assert_equal(request["validation_lives"], 10, "all validation lives")
            artifacts = {"startup_identity.json": sha(base / "startup_identity.json")}
            assert_equal(request["startup_identity_sha256"], artifacts["startup_identity.json"], "startup request pin")
        else:
            assert_equal(request["scientific_genome_lives"], 4160, "complete screens")
            artifacts = {"selection.json": sha(base / "selection.json"),
                         "calibration_projection.json": sha(base / "calibration_projection.json")}
            assert_equal(request["selection_sha256"], artifacts["selection.json"], "both selections frozen before confirmation")
        assert_equal(receipt["artifact_pins"], artifacts, "phase scientific artifact pins")
        receipts[name] = receipt
    startup = receipts["calibration_complete"]["cpu_seconds"]
    screen = receipts["screens_complete"]["cpu_seconds"]
    assert_equal(screen, budget["startup_screen_cpu_seconds"], "monitor phase transition")
    if (stage_cpu["calibration"] > startup + 1e-6 or stage_cpu["screen"] > screen - startup + 1e-6
            or stage_cpu["confirm"] > budget["cpu_seconds"] - screen + 1e-6):
        raise ValueError("raw row CPU exceeds its monitored phase")
    rates = {parent: max(index[parent][f"calibration/row_{i:04d}.npz"]["cpu_seconds"] for i in (0, 1)) / 2
             for parent in PARENTS}
    projection = read(base / "calibration_projection.json")
    screen_prediction, confirm_prediction = startup + 1.5 * 2080 * sum(rates.values()), 1.5 * 1024 * sum(rates.values())
    for key, expected in (("batch_max_cpu_per_life", rates), ("startup_cpu_seconds", startup),
                          ("screen_projection_cpu_seconds", screen_prediction),
                          ("confirmation_projection_cpu_seconds", confirm_prediction), ("feasible", True)):
        assert_equal(projection[key], expected, "fixed feasibility estimate")
    if screen_prediction > 3390 or confirm_prediction > 1990:
        raise ValueError("registered feasibility estimate did not fit")
    report = read(base / "report.json")
    for key, expected in (("status", "complete"), ("scope", SCOPE), ("research_genome_lives", 6208),
                          ("validation_lives", 10), ("total_genome_lives", 6218)):
        assert_equal(report[key], expected, "complete worker report")
    if abs(number(report["row_cpu_seconds"], "reported row CPU") - sum(stage_cpu.values())) > 1e-6:
        raise ValueError("reported and raw row CPU differ")
    assert_equal(set(report["screen"]), set(PARENTS), "both screens")
    assert_equal(set(report["confirmation"]), set(PARENTS), "both confirmations")
    for parent in PARENTS:
        assert_equal(report["row_index_sha256"][parent], sha(base / "measurement" / parent / "row_index.json"), "terminal row index")
        assert_equal(report["screen"][parent], {"selected": selected[parent], "complete_rows": 65,
                     "row_index_sha256": hashlib.sha256(json_bytes(receipts["screens_complete"]["row_snapshot"][parent])).hexdigest()},
                     "saved screen selection")
    return report, projection


def check_stats(record, values, label):
    expected = A.stats(values)
    if record.get("n") != expected["n"] or any(not np.isclose(record.get(key, np.nan), expected[key], rtol=1e-11, atol=1e-11)
                                               for key in ("mean", "se")):
        raise ValueError("worker and independent estimate differ: " + label)


def summaries(records, selected, report, world):
    result, vectors = {}, {}
    for parent in PARENTS:
        baseline = records[parent]["confirm"][0]
        winner = records[parent]["confirm"][selected[parent]["genome_row"]]
        paired, terms = A.paired_terms(winner, baseline, world)
        saved = report["confirmation"][parent]
        columns = ("F", "F_kernel", "n_end", "n_H_end", "live_time", "spikes", "packets", "misses", "clicks",
                   "captures", "path", "zone_samples", "samples", "low_light_captures", "bright_captures")
        for key in columns:
            check_stats(saved[key], terms[key], key)
        check_stats(saved["capture_income"], terms["F__capture_income"], "capture income")
        assert_equal(saved["above_3se"], paired["columns"]["F"]["positive_above_3se"], "descriptive3SE direction")
        for name, row in (("parent", baseline), ("winner", winner)):
            assert_equal(saved["guard_fraction"][name], float(np.mean((row["status"].astype(np.int64) & 6) != 0)),
                         "retained guard fraction")
        for name, _, _ in A.prices(world):
            check_stats(saved["cost_saving_components"][name], terms["F__" + name + "_cost_saving"], name)
        costs0, _ = A.physical_costs(baseline, world)
        costs1, _ = A.physical_costs(winner, world)
        pieces = {"income": terms["F__capture_income"], "cost_saving": (costs0 - costs1) / world["T"],
                  "guard_charge_saving": terms["F__guard_charge_saving"],
                  "extinction_charge_saving": terms["F__extinction_charge_saving"]}
        pieces["accounting_residual"] = terms["F"] - sum(pieces.values())
        for key, values in pieces.items():
            check_stats(saved["fitness_contributions"][key], values, key)
        result[parent] = {"selection": selected[parent], "screen_F": {str(i): A.stats(row["F"]) for i, row in records[parent]["screen"].items()},
                          "confirmation": paired, "absolute_means": {label: {key: A.stats(row[key]) for key in A.COLS}
                               for label, row in (("parent", baseline), ("winner", winner))}}
        vectors.update({parent + "__" + key: value for key, value in terms.items()})
    return result, vectors


def analyze(base):
    base = Path(base).resolve()
    try:
        p, _ = verify_protocol(base)
        budget, resource = resources(base, p)
        check_startup(base, p)
        selected, records, indexes, cpu, rawpins = load_rows(base, p)
        report, projection = phases(base, p, budget, indexes, selected, cpu)
        result, vectors = summaries(records, selected, report, p["world"])
        for name in ("protocol.json", "ready.json", "attempt.json", "budget.json", "resource_clearance.json",
                     "startup_identity.json", "selection.json", "calibration_projection.json", "report.json",
                     "requests/calibration_complete.json", "requests/screens_complete.json",
                     "monitor_receipts/calibration_complete.json", "monitor_receipts/screens_complete.json"):
            rawpins[name] = sha(operation(base, name))
        summary = {"status": "complete", "study": "Y ordinary visibility gradient", "protocol_sha256": REVIEWED_PROTOCOL_SHA256,
                   "research_lives": 6208, "validation_lives": 10, "total_lives": 6218, "resources": dict(resource, raw_stage_cpu_seconds=cpu),
                   "calibration_projection": projection, "world": p["world"], "seeds": p["seeds"], "backgrounds": result,
                   "limitations": LIMITATIONS, "input_pins": rawpins, "ledger_columns": list(A.LEDGER)}
        return summary, vectors
    except (OSError, ValueError, KeyError, TypeError, IndexError, OverflowError, AttributeError) as error:
        return {"status": "incomplete", "scientific_outcomes_emitted": False,
                "error": type(error).__name__ + ": " + str(error)}, {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    summary, vectors = analyze(args.study)
    if args.out is not None:
        if summary["status"] != "complete":
            raise SystemExit(json.dumps(summary))
        if args.out.resolve() == args.study.resolve() or args.study.resolve().is_relative_to(args.out.resolve()):
            raise SystemExit("analysis output cannot replace study inputs")
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
        np.savez_compressed(args.out / "paired_vectors.npz", **vectors)
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
