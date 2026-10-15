"""Complete-study AB audit: native recorded genetics plus unchanged Y58 accounting.
No simulation, compilation, numerical goldens or random genetic generation.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


A = module("AB_offline_accounting", HERE / "offline_accounting.py")
PROTOCOL_SHA = "1d53d07a7aa682f81f04d641c655a6018da0f278f74cfefdd4bcbcc6ab5a7ad7"
LABELS = ["Z_D90", "Z_L92", "depth_D90", "precision_D90", "depth_L92", "precision_L92"]
RUNS = ["D90_depth", "D90_precision", "L92_depth", "L92_precision"]
REFERENCES = [
    "29c41913d98602b8022cb5c636714fe7a87b8fc0b4c54888b37af33598626e29",
    "f5b436347d191b63ede427c7eab609d6319428bafd240335491d0c0623f5ce90",
]
FIELDS = ("W", "b", "lam", "s0", "Q", "act", "A", "a0", "Dm", "km")
PAIRS = {"primary": [[3, 2], [5, 4]], "gain": [[2, 0], [3, 0], [4, 1], [5, 1]]}
LIMITATIONS = [
    "Two fixed founder/run pairs do not estimate general evolutionary policy reliability.",
    "The policies match selection calls, not CPU or evolutionary depth; precision and number of generations trade off.",
    "Paired512-life SE describes these fixed genotypes over world seeds, not uncertainty across searches.",
    "Within each policy pair the native RNG seed and first candidate cohort are shared; overlapping life IDs are intentional.",
    "Low-light captures and improved fitness do not isolate memory, prediction or a new algorithm.",
    "Recorded genetic operations and shortlist ranking are replayed; RNG draws and unsaved per-life search ledgers are not.",
    "Native validation/final diagnostics retain summaries; full58-column reconciliation covers the six confirmation rows.",
    "Initial search guard counts are retained; recheck guard counts are not separately enumerated.",
    "Ten startup goldens are established by five pinned native identity calls/receipts, not executed by this audit.",
    "Natural extinction and paid guards remain in fitness; incomplete data or implementation failure blocks all outcomes.",
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
        path = (
            external(base, name) if external_paths else (operation(base, name) if operational else inside(base, name))
        )
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


def identity(value):
    keys = ("pid", "ppid", "pgid", "start_ticks")
    if any(type(value.get(key)) is not int or value[key] < (0 if key == "ppid" else 1) for key in keys):
        raise ValueError("incomplete process identity")
    return {key: value[key] for key in keys}


def check_stats(record, values, label):
    expected = A.stats(values)
    if record.get("n") != expected["n"] or any(
        not np.isclose(record.get(key, np.nan), expected[key], rtol=1e-11, atol=1e-11) for key in ("mean", "se")
    ):
        raise ValueError("worker and independent estimate differ: " + label)


def genome(path):
    data = read(path)
    assert_equal(set(data["params"]), set(FIELDS), "genome parameter fields")
    result = np.concatenate([np.asarray(data["params"][k], dtype=np.float32).reshape(-1) for k in FIELDS])
    if result.shape != (875,) or not np.isfinite(result).all():
        raise ValueError("invalid genotype")
    return result


def native_seed(seed, purpose, index, life):
    """Independent integer-only copy of the frozen SplitMix64/life tuple contract."""
    mask = (1 << 64) - 1

    def mix(value):
        value = (value + 0x9E3779B97F4A7C15) & mask
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
        return value ^ (value >> 31)

    value = mix((seed & mask) ^ mix(0x4C494645 + purpose))
    for key in (index, life):
        value = mix(value ^ (key & mask))
    return value


def planned_ids(setting):
    seed, count = setting["seed"], setting["generations"]
    result = []
    for g in range(count):
        result.extend(native_seed(seed, 1, g, j) for j in range(setting["initial_lives"] + setting["recheck_lives"]))
        if g % 4 == 0 or g == count - 1:
            result.extend(native_seed(seed, 3, g, j) for j in range(16))
    for index in (0, 1):
        result.extend(native_seed(seed, 5, index, j) for j in range(2))
    return result


def verify_seeds(p, reg, audit):
    assert_equal(p["runs"], RUNS, "four ordered run identifiers")
    paired = p["paired_native_seeds"]
    if (
        set(paired) != {"D90", "L92"}
        or len(set(paired.values())) != 2
        or any(type(x) is not int or x < 0 for x in paired.values())
    ):
        raise ValueError("two distinct background seeds required")
    expected, intersections, unions = {}, {}, {}
    for run in RUNS:
        background, policy = run.split("_")
        setting = dict(
            background=background,
            policy=policy,
            seed=paired[background],
            generations=4 if policy == "depth" else 1,
            initial_lives=3 if policy == "depth" else 12,
            recheck_lives=4 if policy == "depth" else 16,
        )
        assert_equal(p["run_settings"][run], setting, "fixed policy setting")
        expected[run] = planned_ids(setting)
        assert_equal(len(set(expected[run])), 64 if policy == "depth" else 48, "per-run unique IDs")
    for background in ("D90", "L92"):
        depth, precise = (set(expected[background + "_" + policy]) for policy in ("depth", "precision"))
        intersections[background] = sorted(depth & precise)
        unions[background] = depth | precise
        assert_equal(len(intersections[background]), 27, "exact within-pair overlap")
        assert_equal(len(unions[background]), 85, "exact background union")
    confirm = p["confirmation"]["seeds"]
    if len(confirm) != 512 or len(set(confirm)) != 512 or any(type(x) is not int or x < 0 for x in confirm):
        raise ValueError("512 ordered fresh confirmation IDs required")
    allnative = unions["D90"] | unions["L92"]
    if unions["D90"] & unions["L92"] or allnative & set(confirm) or 11 in allnative | set(confirm):
        raise ValueError("unregistered namespace overlap")
    assert_equal(reg["runs"], RUNS, "registered named runs")
    for value, label in ((reg, "registration"), (audit, "seed audit")):
        assert_equal(value["paired_native_seeds"], paired, label + " native seeds")
        assert_equal(value["confirmation_seeds"], confirm, label + " confirmation")
    assert_equal(audit["run_life_seeds"], expected, "all independently reconstructed native IDs")
    assert_equal(audit["intentional_overlap"], intersections, "all exact intentional overlaps")


def verify_Z_cost_inputs(base, p):
    source = base / "inputs/Z"
    old = read(source / "protocol.json")
    assert_equal(
        sha(source / "protocol.json"),
        "2e3e2a2f7bd19f8a10620f8bf4c23a5eb31d4c033a48c0939bf421d234be2935",
        "completed Z protocol",
    )
    assert_equal(p["world"], old["world"], "unchanged full blink world")
    assert_equal(p["expected_numerical_identity"], old["expected_numerical_identity"], "unchanged numerical identity")
    assert_equal(p["production_pins"], old["production_pins"], "unchanged production closure")
    zlabels = ["D90", "L92", "Y_D90", "Y_L92", "Z_D90", "Z_L92"]
    endpoint = read(source / "confirmation/endpoints.json")
    data = npz(source / "confirmation/genotypes.npz")
    g = data["genomes"]
    if g.shape != (6, 875) or g.dtype != np.float32 or not np.isfinite(g).all():
        raise ValueError("six complete prior genotypes required")
    assert_equal(data["labels"].tolist(), zlabels, "prior genotype roles")
    assert_equal(endpoint["labels"], zlabels, "prior endpoint roles")
    assert_equal(endpoint["genotype_sha256"], dict(zip(zlabels, map(raw_sha, g))), "prior genotype identity")
    assert_equal([raw_sha(row) for row in g[4:]], REFERENCES, "both fixed Z endpoints")
    index = read(source / "confirmation/row_index.json")
    rates, sourcepins = {}, {}
    seeds = np.asarray(old["confirmation"]["seeds"], dtype=np.uint64)
    for i, label in enumerate(zlabels):
        name = f"blink/row_{i:04d}.npz"
        path = source / "confirmation" / name
        assert_equal(sha(path), index[name]["sha256"], "prior timing row")
        row = npz(path)
        identity_ = dict(
            protocol_sha256=sha(source / "protocol.json"),
            stage="confirmation",
            endpoints_sha256=sha(source / "confirmation/endpoints.json"),
            role=label,
            genome_index=i,
            genome_sha256=raw_sha(g[i]),
            seeds=seeds.tolist(),
        )
        if row["identity"].shape != () or str(row["identity"]) != canonical(identity_):
            raise ValueError("prior timing row identity differs")
        if (
            row["ledger"].shape != (512, 58)
            or row["ledger"].dtype != np.float64
            or not np.isfinite(row["ledger"]).all()
        ):
            raise ValueError("prior timing ledger incomplete")
        if not A.identical(row["seeds"], seeds) or row["genome_index"].shape != () or int(row["genome_index"]) != i:
            raise ValueError("prior timing ordering differs")
        for timing in ("cpu_seconds", "wall_seconds"):
            if row[timing].shape != ():
                raise ValueError("prior timing must be scalar")
            number(float(row[timing]), "prior " + timing)
        assert_equal(float(row["cpu_seconds"]), index[name]["cpu_seconds"], "indexed prior CPU")
        rates[label] = float(row["cpu_seconds"]) / 512
        sourcepins["confirmation/" + name] = sha(path)
    saved = read(base / "inputs/Z_cost_rows.json")
    assert_equal(saved["rates"], rates, "six actual historical rates")
    assert_equal(saved["source_pins"], sourcepins, "six historical timing pins")
    maxima = {x: max(rates[x], rates["Y_" + x], rates["Z_" + x]) for x in ("D90", "L92")}
    projection = p["cost_projection"]
    for key, value in dict(
        rates_cpu_per_life=rates,
        lineage_maxima=maxima,
        startup_search_projection=180 + 1.5 * 8252 * sum(maxima.values()),
        confirmation_projection=180 + 1.5 * 512 * sum(rates["Z_" + x] + 2 * maxima[x] for x in ("D90", "L92")),
        search_release_threshold=7190,
        confirmation_release_threshold=1790,
        feasible=True,
    ).items():
        assert_equal(projection[key], value, "fixed cost projection " + key)
    assert_equal(saved["projection"], projection, "retained projection")
    if projection["startup_search_projection"] > 7190 or projection["confirmation_projection"] > 1790:
        raise ValueError("fixed cost estimate exceeds included allocation")
    budget = read(source / "budget.json")
    if (
        budget["status"] != "complete"
        or budget["exit_code"] != 0
        or budget.get("running")
        or budget.get("queued")
        or budget.get("cleanup_error")
    ):
        raise ValueError("Z dependency is not complete")
    summary = read(base / "inputs/Z_summary.json")
    assert_equal(summary["status"], "complete", "prior independent analysis")
    assert_equal(summary["protocol_sha256"], sha(source / "protocol.json"), "prior analyzed protocol")
    return endpoint


def verify_protocol(base):
    assert_equal(sha(base / "protocol.json"), PROTOCOL_SHA, "reviewed protocol")
    p = read(base / "protocol.json")
    for name, value in dict(
        study="AB blink precision versus depth",
        max_cpu_seconds=9000,
        search_cpu_seconds=7200,
        max_simulation_threads=4,
        search_genome_lives=16504,
        confirmation_genome_lives=3072,
        planned_genome_lives=19576,
        startup_validation_genome_lives=10,
    ).items():
        assert_equal(p[name], value, "registered " + name)
    pins(base, p["file_pins"])
    pins(base, p["production_pins"], external_paths=True)
    assert_equal(
        p["expected_numerical_identity"]["sources"],
        {k: v for k, v in p["production_pins"].items() if k.startswith("src/")},
        "complete numerical source closure",
    )
    assert_equal(p["confirmation"]["labels"], LABELS, "six ordered confirmation roles")
    assert_equal(p["confirmation"]["threads"], 2, "confirmation threads")
    for name, pairs_ in PAIRS.items():
        assert_equal(p["confirmation"][name + "_pairs"], pairs_, "fixed " + name + " contrasts")
    reg, audit = read(base / "registration.json"), read(base / "seed_audit.json")
    assert_equal(reg["status"], "registered", "root registration")
    assert_equal(reg["founder_policy"], "both_Z_final_rank0_regardless_of_AA_or_confirmation", "fixed founder policy")
    assert_equal(audit["status"], "passed", "reviewed seed audit")
    assert_equal(sha(base / "seed_audit.json"), reg["seed_audit_sha256"], "registered audit pin")
    verify_seeds(p, reg, audit)
    assert_equal(
        read(base / "generation_claim.json"),
        dict(
            registration_sha256=sha(base / "registration.json"),
            paired_native_seeds=p["paired_native_seeds"],
            populations_to_generate=2,
        ),
        "one preparation of two populations",
    )
    prior_endpoint = verify_Z_cost_inputs(base, p)
    assert_equal([raw_sha(genome(base / name)) for name in p["reference_files"]], REFERENCES, "two fixed founders")
    for i, background in enumerate(("D90", "L92")):
        meta = p["founder_mapping"][background]
        assert_equal(meta["raw_sha256"], REFERENCES[i], "fixed founder raw bytes")
        assert_equal(meta["Z_role_index"], i + 4, "prior endpoint role")
        assert_equal(meta["Z_endpoint"], prior_endpoint["endpoints"][str(53220 + i)], "prior endpoint checkpoint")
        assert_equal(raw_sha(genome(base / meta["start_file"])), REFERENCES[i], "native start file")
    tree = ast.parse(external(base, "src/life/spec.py").read_text())
    values = {
        n.targets[0].id: n.value for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
    }
    names = (
        ast.literal_eval(values["LEDGER_V2"])
        + ast.literal_eval(values["LEDGER_V3"].right)
        + ast.literal_eval(values["LEDGER_V4"].right)
    )
    assert_equal(names, A.LEDGER, "58 native ledger indices")
    return p


def owned_processes(attempt, budget, workers):
    monitor = identity(attempt["monitor"])
    process = budget["process_identities"]
    assert_equal([x["name"] for x in process], ["monitor"] + workers, "exact first-attempt process identities")
    assert_equal(identity(process[0]), monitor, "attempt/terminal monitor")
    groups = []
    for item in process[1:]:
        child = identity(item)
        if child["ppid"] != monitor["pid"] or child["pid"] != child["pgid"]:
            raise ValueError("worker was not an owned process group")
        groups.append(child["pid"])
    if len(set(groups + [monitor["pid"]])) != len(groups) + 1:
        raise ValueError("duplicate process identity")
    assert_equal(budget["owned_process_groups"], groups, "all owned groups")


def resources(base, p):
    ready = read(operation(base, "ready.json"))
    assert_equal(ready["status"], "released", "release status")
    assert_equal(ready["production_pins"], p["production_pins"], "released source closure")
    required = dict(p["file_pins"])
    for name in (
        "protocol.json",
        "resource_clearance.json",
        "analysis/analyze.py",
        "analysis/native_audit.py",
        "analysis/offline_accounting.py",
        "analysis/helpers/selection.py",
        "analysis/helpers/genetics.py",
    ):
        required[name] = sha(operation(base, name))
    if any(ready["source_pins"].get(k) != v for k, v in required.items()):
        raise ValueError("release does not bind prepared inputs/analysis")
    pins(base, ready["source_pins"], operational=True)
    assert_equal(sha(__file__), ready["source_pins"]["analysis/analyze.py"], "executing analyzer")
    assert_equal(sha(A.__file__), ready["source_pins"]["analysis/offline_accounting.py"], "executing accountant")
    assert_equal(
        sha(HERE / "native_audit.py"), ready["source_pins"]["analysis/native_audit.py"], "executing native audit"
    )
    clearance = read(operation(base, "resource_clearance.json"))
    if clearance["status"] != "cleared" or clearance["all_processes_exited"] is not True:
        raise ValueError("prior work not cleared")
    pins(base, clearance["budget_pins"], external_paths=True)
    for name in clearance["budget_pins"]:
        old = read(external(base, name))
        if (
            old.get("status") in (None, "running")
            or old.get("running")
            or old.get("queued")
            or old.get("cleanup_error")
        ):
            raise ValueError("prior budget not terminal")
    if not clearance.get("processes") or not clearance.get("process_groups"):
        raise ValueError("prior identities missing")
    for item in clearance["processes"]:
        if any(type(item.get(k)) is not int or item[k] <= 0 for k in ("pid", "start_ticks")):
            raise ValueError("prior identity incomplete")
    attempt, budget = read(operation(base, "attempt.json")), read(operation(base, "budget.json"))
    assert_equal(attempt["ready_sha256"], sha(operation(base, "ready.json")), "one attempt release")
    workers = [f"evolve_{run}" for run in p["runs"]] + ["confirmation"]
    owned_processes(attempt, budget, workers)
    for name, value in {
        "status": "complete",
        "exit_code": 0,
        "phase": "confirmation",
        "cap_cpu_seconds": 9000,
        "search_cpu_seconds": 7200,
        "confirmation_reserved_cpu_seconds": 1800,
        "running": {},
        "queued": [],
        "ready": ready,
    }.items():
        assert_equal(budget[name], value, "terminal budget " + name)
    completed = budget["completed"]
    if (
        len(completed) != 5
        or completed[-1] != {"name": "confirmation", "exit_code": 0}
        or {x["name"] for x in completed[:4]} != set(workers[:4])
        or any(x["exit_code"] != 0 for x in completed)
    ):
        raise ValueError("all four searches must finish before the one confirmation")
    if budget.get("reason") is not None or budget.get("error") or budget.get("cleanup_error"):
        raise ValueError("terminal failure")
    total = number(budget["cpu_seconds"], "total CPU", 8990)
    search = number(budget["search_stage_cpu_seconds"], "search CPU", 7190)
    number(budget["wall_seconds"], "wall time")
    if total < search:
        raise ValueError("CPU accounting went backwards")
    if not budget["affinity"] or any(type(x) is not int or not 0 <= x < 12 for x in budget["affinity"]):
        raise ValueError("registered affinity differs")
    return (
        ready,
        budget,
        {
            "total_cpu_seconds": total,
            "search_cpu_seconds": search,
            "confirmation_cpu_seconds": total - search,
            "first_attempt_only": True,
        },
    )


def endpoints(base, p, ready):
    record = read(base / "confirmation/endpoints.json")
    for name, value in {
        "format": 1,
        "labels": LABELS,
        "seeds": p["confirmation"]["seeds"],
        "protocol_sha256": PROTOCOL_SHA,
        "numerical_identity": p["expected_numerical_identity"],
        "ready": ready,
        "world": p["world"],
        "selection": "All four complete final population rank0 endpoints fixed together before confirmation.",
    }.items():
        assert_equal(record[name], value, "frozen endpoints " + name)
    data = npz(base / "confirmation/genotypes.npz")
    assert_equal(set(data), {"genomes", "labels"}, "genotype archive schema")
    assert_equal(data["labels"].tolist(), LABELS, "genotype role order")
    g = data["genomes"]
    if g.shape != (6, 875) or g.dtype != np.float32 or not np.isfinite(g).all():
        raise ValueError("six complete finite genomes required")
    assert_equal([raw_sha(x) for x in g[:2]], REFERENCES, "confirmation references")
    assert_equal(record["genotype_sha256"], dict(zip(LABELS, map(raw_sha, g))), "all frozen genotype hashes")
    identity_ = p["expected_numerical_identity"]
    assert_equal(
        identity_["golden"],
        {
            "all": "ebb3ad6fcad2d938",
            "ledger_sha256": "b622f9afad48d6ec5b39b003efba82f25e7e6a764a015fe40398b3a6bbd81251",
        },
        "existing ABI3 golden",
    )
    assert_equal(set(identity_["kernels"]), {"False", "True"}, "both full/fast builds")
    binaries = {sha(path) for path in (base / "build-cache").rglob("*.so")}
    if not set(identity_["kernels"].values()).issubset(binaries):
        raise ValueError("retained full/fast kernel binaries missing")
    return record, g


def load_rows(base, p, ep, budget):
    folder = base / "confirmation"
    index = read(folder / "row_index.json")
    names = [f"blink/row_{i:04d}.npz" for i in range(6)]
    assert_equal(set(index), set(names), "all six confirmation rows")
    actual = {str(x.relative_to(folder)) for x in folder.rglob("row_*.npz")}
    assert_equal(actual, set(names), "no extra or stale raw rows")
    rows, pinmap, cpu = {}, {}, 0.0
    seeds = np.asarray(p["confirmation"]["seeds"], dtype=np.uint64)
    for i, name in enumerate(names):
        path = folder / name
        assert_equal(sha(path), index[name]["sha256"], "raw row hash")
        row = npz(path)
        assert_equal(
            set(row),
            set(A.COLS) | {"identity", "seeds", "genome_index", "ledger", "cpu_seconds", "wall_seconds"},
            "raw row schema",
        )
        expected = {
            "protocol_sha256": PROTOCOL_SHA,
            "stage": "confirmation",
            "endpoints_sha256": sha(folder / "endpoints.json"),
            "role": LABELS[i],
            "genome_index": i,
            "genome_sha256": ep["genotype_sha256"][LABELS[i]],
            "seeds": seeds.tolist(),
        }
        if (
            row["identity"].shape != ()
            or row["identity"].dtype.kind != "U"
            or str(row["identity"]) != canonical(expected)
        ):
            raise ValueError("raw row identity differs")
        if (
            row["genome_index"].shape != ()
            or row["genome_index"].dtype.kind not in "iu"
            or int(row["genome_index"]) != i
            or not A.identical(row["seeds"], seeds)
        ):
            raise ValueError("raw row seed/genome index differs")
        A.validate_row(row, p["world"], 512)
        assert_equal(number(index[name]["cpu_seconds"], "indexed CPU"), float(row["cpu_seconds"]), "raw/index CPU")
        cpu += float(row["cpu_seconds"])
        rows[i] = row
        pinmap[str(path.relative_to(base))] = sha(path)
    score = npz(folder / "blink/scores.npz")
    assert_equal(set(score), set(A.COLS) | {"seeds", "genome_indices"}, "aggregate schema")
    if not A.identical(score["seeds"], seeds) or not A.identical(score["genome_indices"], np.arange(6)):
        raise ValueError("aggregate identities differ")
    for key in A.COLS:
        if not A.identical(score[key], np.stack([rows[i][key] for i in range(6)])):
            raise ValueError("raw/aggregate mismatch " + key)
    report = read(folder / "report.json")
    for name, value in {
        "status": "complete",
        "report_only": True,
        "genome_lives": 3072,
        "paired_seeds": 512,
        "confirmation_startup_validation_lives": 2,
        "protocol_sha256": PROTOCOL_SHA,
        "endpoints_sha256": sha(folder / "endpoints.json"),
        "genotypes_sha256": sha(folder / "genotypes.npz"),
    }.items():
        assert_equal(report[name], value, "complete confirmation " + name)
    if (
        abs(number(report["row_cpu_seconds"], "reported CPU") - cpu) > 1e-6
        or cpu > budget["cpu_seconds"] - budget["search_stage_cpu_seconds"] + 1e-6
    ):
        raise ValueError("raw CPU exceeds monitored confirmation portion")
    return rows, report, cpu, pinmap


def comparison(a, b, saved, world):
    paired, terms = A.paired_terms(a, b, world)
    cols = (
        "F",
        "F_kernel",
        "n_end",
        "n_H_end",
        "live_time",
        "spikes",
        "packets",
        "misses",
        "clicks",
        "captures",
        "path",
        "zone_samples",
        "samples",
        "low_light_captures",
        "bright_captures",
    )
    for key in cols:
        check_stats(saved[key], terms[key], key)
    check_stats(saved["capture_income"], terms["F__capture_income"], "capture income")
    assert_equal(saved["above_3se"], paired["columns"]["F"]["positive_above_3se"], "descriptive3SE direction")
    for name, row in (("parent", b), ("winner", a)):
        assert_equal(
            saved["guard_fraction"][name], float(np.mean((row["status"].astype(np.int64) & 6) != 0)), "guard fraction"
        )
    for name, _, _ in A.prices(world):
        check_stats(saved["cost_saving_components"][name], terms["F__" + name + "_cost_saving"], name)
    costs0, _ = A.physical_costs(b, world)
    costs1, _ = A.physical_costs(a, world)
    pieces = {
        "income": terms["F__capture_income"],
        "cost_saving": (costs0 - costs1) / world["T"],
        "guard_charge_saving": terms["F__guard_charge_saving"],
        "extinction_charge_saving": terms["F__extinction_charge_saving"],
    }
    pieces["accounting_residual"] = terms["F"] - sum(pieces.values())
    for name, values in pieces.items():
        check_stats(saved["fitness_contributions"][name], values, name)
    return paired, terms


def analyze(base):
    base = Path(base).resolve()
    try:
        p = verify_protocol(base)
        ready, budget, resource = resources(base, p)
        ep, g = endpoints(base, p, ready)
        native = module("AB_native_audit", HERE / "native_audit.py").audit(base, p, ep, g, external)
        native.pop("audit_process_cpu_seconds", None)
        rows, report, cpu, pinmap = load_rows(base, p, ep, budget)
        assert_equal(set(report["absolute"]), set(LABELS), "all six absolute role reports")
        absolute_metrics = {
            "F",
            "F_kernel",
            "captures",
            "low_light_captures",
            "clicks",
            "misses",
            "n_end",
            "n_H_end",
            "live_time",
            "path",
            "spikes",
            "packets",
            "income",
            "cost",
            "guard_charge",
            "extinct_charge",
        }
        absolute, health = {}, {}
        for i, label in enumerate(LABELS):
            assert_equal(set(report["absolute"][label]), absolute_metrics, "complete absolute metrics")
            for key, saved in report["absolute"][label].items():
                check_stats(saved, rows[i][key], "absolute " + label + " " + key)
            absolute[label] = {k: A.stats(rows[i][k]) for k in A.COLS}
            status = rows[i]["status"].astype(np.int64)
            health[label] = {
                name: int(np.count_nonzero(status & mask))
                for name, mask in {
                    "extinct": 1,
                    "guard_cells": 2,
                    "guard_events": 4,
                    "mismatch": 64,
                    "capacity": 128,
                }.items()
            }
        result, vectors = {}, {}
        for name, pairs_ in PAIRS.items():
            assert_equal(set(report[name]), {LABELS[a] for a, _ in pairs_}, "all " + name + " contrasts")
            result[name] = {}
            for a, b in pairs_:
                paired, terms = comparison(rows[a], rows[b], report[name][LABELS[a]], p["world"])
                result[name][LABELS[a]] = {"baseline": LABELS[b], **paired}
                vectors.update({name + "__" + LABELS[a] + "__" + k: v for k, v in terms.items()})
        for name in (
            "protocol.json",
            "ready.json",
            "attempt.json",
            "budget.json",
            "resource_clearance.json",
            "confirmation/endpoints.json",
            "confirmation/genotypes.npz",
            "confirmation/report.json",
            "confirmation/row_index.json",
            "confirmation/blink/scores.npz",
        ):
            pinmap[name] = sha(operation(base, name))
        return {
            "status": "complete",
            "study": p["study"],
            "protocol_sha256": PROTOCOL_SHA,
            "research_lives": 19576,
            "startup_validation_lives": 10,
            "total_lives": 19586,
            "resources": dict(resource, raw_confirmation_cpu_seconds=cpu),
            "world": p["world"],
            "seeds": p["confirmation"]["seeds"],
            "native_audit": native,
            "contrasts": result,
            "absolute_means": absolute,
            "confirmation_health": health,
            "input_pins": pinmap,
            "ledger_columns": list(A.LEDGER),
            "limitations": LIMITATIONS,
        }, vectors
    except (OSError, ValueError, KeyError, TypeError, IndexError, OverflowError, AttributeError, RuntimeError) as error:
        return {
            "status": "incomplete",
            "scientific_outcomes_emitted": False,
            "error": type(error).__name__ + ": " + str(error),
        }, {}


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
            raise SystemExit("output cannot replace study input")
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "summary.json").write_bytes(json_bytes(summary))
        np.savez_compressed(args.out / "paired_vectors.npz", **vectors)
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
