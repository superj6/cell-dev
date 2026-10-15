"""Complete-study AH audit: native recorded genetics plus unchanged AE57 accounting.
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
POLICY = {
    "version": 1,
    "domain": "cell-dev:AH:reserve:v1",
    "mu": 32,
    "offspring": 224,
    "reserved": 2,
    "active_generations": [0, 1, 2],
    "ordinary_final_generation": 3,
    "initial_lives": 3,
    "recheck_k": 64,
    "recheck_lives": 4,
    "recheck_key": "all",
    "eligibility": "all fresh offspring, independent of scores or phenotype",
    "lottery": "SHA256 ASCII domain|seed|generation|counter, first8 little-endian, rejection modulo shrinking list",
    "shortlist": "protected2 plus top62 nonprotected by initial F, ordered by full initial rank",
    "survivors": "protected2 plus top30 nonprotected by pooled F, ordered by full pooled rank",
}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


A = module("AH_offline_accounting", HERE / "offline_accounting.py")
PROTOCOL_SHA = "0a9e505969ed11cd8f240f9404bbff2adf9a91d91d5387252fd9595874c61be4"
LABELS = ["AE_L92", "AH_control", "AH_reserve"]
BACKGROUNDS = ("L92",)
REFERENCES = [
    "edc62b75a48c76cdc4214f04561d7528a77399c90837f6e07b3f90aea47755a7",
]
AE_PROTOCOL = "0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849"
AE_SELECTED = {"L92": 31}
FIELDS = ("W", "b", "lam", "s0", "Q", "act", "A", "a0", "Dm", "km")
PAIRS = {"primary": [[2, 1]], "gain": [[1, 0], [2, 0]]}
LIMITATIONS = [
    "One deliberately chosen founder and one paired search do not estimate general policy reliability.",
    "512-life paired uncertainty concerns fixed endpoints, not evolutionary replicates.",
    "The reserve changes both evaluation allocation and breeder retention, with unchanged prices and task fitness.",
    "Higher captures with lower F is a tradeoff; neither alone demonstrates a more sophisticated algorithm.",
    "Recorded genetics and external tie/lottery streams are replayed without mutation generation or life simulation.",
    "Protected ancestry does not prove a necessary stepping stone or recover unevaluated ordinary counterfactual scores.",
    "Native diagnostics retain summaries; three confirmation rows retain complete raw57 ledgers.",
    "Search guard counts cover initial evaluations; full search per-life ledgers were not retained.",
    "Six numerical goldens are bound through three recorded identities; this reader executes none.",
    "Historical maximum CPU estimates do not bound costly fresh descendants; hard caps remain authoritative.",
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


def expected_cost_projection(rates):
    if len(rates) != 65 or any(number(v, "historical rate") <= 0 for v in rates):
        raise ValueError("all65 positive historical L92 rates required")
    maximum = max(rates)
    search = 180 + 1.5 * 8268 * maximum
    confirmation = 180 + 1.5 * 512 * 5 * maximum
    return {
        "rates_cpu_per_life": rates,
        "max_cpu_per_life": maximum,
        "startup_search_projection": search,
        "confirmation_projection": confirmation,
        "confirmation_allowance": "one historical maximum for start, twice maximum for each unknown endpoint",
        "feasible": search <= 3390 and confirmation <= 1990,
        "limitation": "Historical maxima and margins do not bound new reserve offspring; hard caps are decisive.",
    }


def verify_AE_inputs(base, p):
    source = base / "inputs/AE"
    assert_equal(sha(source / "protocol.json"), AE_PROTOCOL, "original complete AE protocol")
    old = read(source / "protocol.json")
    for key in ("world", "world_packing", "expected_numerical_identity", "production_pins", "numerical_identity"):
        assert_equal(p[key], old[key], "unchanged AE " + key)
    roles, selection = read(source / "confirmation_roles.json"), read(source / "selection.json")
    prior_labels = ["P_D90", "P_L92", "H_D90", "H_L92"]
    assert_equal(roles["roles"], prior_labels, "prior complete roles")
    assert_equal(roles["protocol_sha256"], AE_PROTOCOL, "prior protocol")
    assert_equal(roles["selection_sha256"], sha(source / "selection.json"), "prior selection")
    assert_equal(roles["genotypes_sha256"], sha(source / "confirmation_genotypes.npz"), "prior table bytes")
    table = npz(source / "confirmation_genotypes.npz")
    assert_equal(set(table), {"roles", "genomes"}, "prior role archive schema")
    genotypes = table["genomes"]
    if genotypes.dtype != np.float32 or genotypes.shape != (4, 875) or not np.isfinite(genotypes).all():
        raise ValueError("complete prior role table required")
    assert_equal(table["roles"].tolist(), prior_labels, "prior table order")
    assert_equal(roles["genotype_sha256"], dict(zip(prior_labels, map(raw_sha, genotypes))), "prior raw hashes")
    assert_equal(raw_sha(genotypes[3]), REFERENCES[0], "fixed pre-AF AE L92 start")
    assert_equal(selection["L92"], {"genome_row": 31, "raw_sha256": REFERENCES[0]}, "fixed row31 selection")
    assert_equal(roles["panel_rows"]["H_L92"], 31, "fixed role panel row")
    summary = read(base / "inputs/AE_summary.json")
    assert_equal(summary["status"], "complete", "reviewed AE completion")
    assert_equal(summary["protocol_sha256"], AE_PROTOCOL, "reviewed AE protocol")
    assert_equal(summary["roles"], roles, "reviewed original roles")
    budget = read(source / "budget.json")
    if (
        budget.get("status") != "complete"
        or budget.get("exit_code") != 0
        or budget.get("running")
        or budget.get("queued")
        or budget.get("cleanup_error")
        or budget.get("reason")
    ):
        raise ValueError("complete clean original AE work required")
    assert_equal(read(source / "startup_identity.json")["identity"], p["expected_numerical_identity"], "AE identity")
    panel = np.load(source / "inputs/Y/inputs/L92/genomes.npy", allow_pickle=False)
    if panel.shape != (65, 875) or panel.dtype != np.float32 or not np.isfinite(panel).all():
        raise ValueError("complete original L92 neighborhood required")
    assert_equal(list(map(raw_sha, panel)), old["panel_genotype_sha256"]["L92"], "all original neighborhood bytes")
    if not A.identical(panel[31], genotypes[3]):
        raise ValueError("start is not original L92 row31")
    rates, sourcepins = [], {}
    folder = source / "measurement/screen/L92"
    index = read(folder / "row_index.json")
    relative_index = str((folder / "row_index.json").relative_to(source))
    assert_equal(sha(folder / "row_index.json"), summary["input_pins"][relative_index], "reviewed timing index")
    sourcepins[relative_index] = sha(folder / "row_index.json")
    for i in range(65):
        path = folder / f"screen/row_{i:04d}.npz"
        relative = str(path.relative_to(source))
        entry = index[f"screen/row_{i:04d}.npz"]
        assert_equal(sha(path), entry["sha256"], "retained timing row")
        assert_equal(sha(path), summary["input_pins"][relative], "reviewed timing row")
        row = npz(path)
        expected = {
            "protocol_sha256": AE_PROTOCOL,
            "background": "L92",
            "world": "persistent",
            "stage": "screen",
            "genome_index": i,
            "genome_sha256": old["panel_genotype_sha256"]["L92"][i],
            "seeds": old["seeds"]["screen"],
        }
        if row["identity"].shape != () or str(row["identity"]) != canonical(expected):
            raise ValueError("historical timing identity differs")
        if (
            row["ledger"].shape != (32, 57)
            or row["ledger"].dtype != np.float64
            or not np.isfinite(row["ledger"]).all()
            or row["genome_index"].shape != ()
            or int(row["genome_index"]) != i
            or not A.identical(row["seeds"], np.asarray(expected["seeds"], dtype=np.uint64))
        ):
            raise ValueError("historical raw row coverage differs")
        for name in ("cpu_seconds", "wall_seconds"):
            if row[name].shape != ():
                raise ValueError("historical timing must be scalar")
            number(float(row[name]), name)
        cpu = float(row["cpu_seconds"])
        if cpu <= 0 or cpu != entry["cpu_seconds"]:
            raise ValueError("historical CPU/index differs")
        rates.append(cpu / 32)
        sourcepins[relative] = sha(path)
    expected = expected_cost_projection(rates)
    assert_equal(p["cost_projection"], expected, "complete prospective cost formula")
    assert_equal(
        read(base / "inputs/AE_cost_rows.json"),
        {"rates": rates, "source_pins": sourcepins, "projection": expected},
        "cost evidence",
    )
    assert_equal(expected["feasible"], True, "fixed allocations fit planning estimate")
    return roles


def verify_protocol(base):
    if PROTOCOL_SHA is None:
        raise ValueError("source-only AH reader has no reviewed protocol")
    assert_equal(sha(base / "protocol.json"), PROTOCOL_SHA, "reviewed AH protocol")
    p = read(base / "protocol.json")
    for name, value in {
        "study": "AH fresh-offspring exploratory reserve",
        "abi": 3,
        "runs": ["control", "reserve"],
        "generations": 4,
        "max_cpu_seconds": 5400,
        "search_cpu_seconds": 3400,
        "max_simulation_threads": 4,
        "search_genome_lives": 8268,
        "confirmation_genome_lives": 1536,
        "planned_genome_lives": 9804,
        "startup_validation_genome_lives": 6,
    }.items():
        assert_equal(p[name], value, "registered " + name)
    pins(base, p["file_pins"])
    pins(base, p["production_pins"], external_paths=True)
    assert_equal(
        p["expected_numerical_identity"]["sources"],
        {k: v for k, v in p["production_pins"].items() if k.startswith("src/")},
        "complete source identity",
    )
    assert_equal(p["reserve_policy"], POLICY, "reviewed independent reserve definition")
    verify_AE_inputs(base, p)
    c = p["confirmation"]
    assert_equal(c["labels"], LABELS, "three fixed roles")
    assert_equal(c["threads"], 2, "confirmation thread cap")
    for name, pairs in PAIRS.items():
        assert_equal(c[name + "_pairs"], pairs, "fixed " + name + " contrasts")
    assert_equal(set(c), {"labels", "seeds", "threads", "primary_pairs", "gain_pairs"}, "no extra comparison scope")
    reg, audit = read(base / "registration.json"), read(base / "seed_audit.json")
    for name, expected in (
        ("status", "registered"),
        ("founder_policy", "fixed_AE_L92_row31"),
        ("runs", p["runs"]),
        ("paired_native_seed", p["paired_native_seed"]),
        ("confirmation_seeds", c["seeds"]),
    ):
        assert_equal(reg[name], expected, "registered " + name)
    assert_equal(reg["native_seed_audit_sha256"], sha(base / "seed_audit.json"), "namespace proof bytes")
    assert_equal(audit["status"], "passed", "namespace proof status")
    assert_equal(audit["paired_native_seed"], p["paired_native_seed"], "audited shared seed")
    assert_equal(audit["confirmation_seeds"], c["seeds"], "audited confirmation")
    seed = p["paired_native_seed"]
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("unsigned paired native seed required")
    ids = []
    for g in range(4):
        ids.extend(native_seed(seed, 1, g, j) for j in range(7))
        if g in (0, 3):
            ids.extend(native_seed(seed, 3, g, j) for j in range(16))
    for index in (0, 1):
        ids.extend(native_seed(seed, 5, index, j) for j in range(2))
    assert_equal(audit["run_life_seeds"], {run: ids for run in p["runs"]}, "independent native schedules")
    assert_equal(audit["intentional_overlap"], ids, "explicit complete native overlap")
    if (
        len(c["seeds"]) != 512
        or any(type(x) is not int or not 0 <= x < 2**64 for x in c["seeds"])
        or len(set(ids)) != 64
        or len(set(ids + c["seeds"])) != 576
        or 11 in ids + c["seeds"]
    ):
        raise ValueError("exact native/confirmation identities required")
    assert_equal(
        read(base / "generation_claim.json"),
        {
            "registration_sha256": sha(base / "registration.json"),
            "paired_native_seed": seed,
            "populations_to_generate": 1,
        },
        "one shared initialization claim",
    )
    assert_equal(p["reference_files"], [p["founder_mapping"]["L92"]["start_file"]], "one fixed start file")
    meta = p["founder_mapping"]["L92"]
    assert_equal(set(p["founder_mapping"]), {"L92"}, "one background")
    assert_equal(meta["background"], "L92", "fixed background")
    assert_equal(meta["AE_selection"], {"genome_row": 31, "raw_sha256": REFERENCES[0]}, "fixed original selection")
    assert_equal(meta["raw_sha256"], REFERENCES[0], "fixed start hash")
    assert_equal(raw_sha(genome(base / meta["start_file"])), REFERENCES[0], "fixed start bytes")
    terminal = reg["AG_terminal"]["file_pins"]
    name = "outputs/autonomous_visibility_dark_tail_gradient_20261014/budget.json"
    if name not in terminal:
        raise ValueError("AG operational terminal evidence required")
    pins(base, terminal, external_paths=True)
    old = read(external(base, name))
    if (
        old.get("status")
        not in {"complete", "incomplete", "monitor_failed", "job_failed", "cpu_budget_exhausted", "interrupted"}
        or old.get("running")
        or old.get("queued")
        or old.get("cleanup_error")
    ):
        raise ValueError("clean AG resource terminal required, independent of scientific success")
    tree = ast.parse(external(base, "src/life/spec.py").read_text())
    values = {
        n.targets[0].id: n.value for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
    }
    assert_equal(
        ast.literal_eval(values["LEDGER_V2"]) + ast.literal_eval(values["LEDGER_V3"].right), A.LEDGER, "57 ABI3 columns"
    )
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "World")
    fields = [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)]
    metadata = ast.literal_eval(values["_META"])
    keys = [k for k in fields[: fields.index("visibility_mode")] if k not in metadata]
    packed = np.asarray([p["world"][k] for k in keys], dtype=np.float64)
    assert_equal(
        p["world_packing"],
        {"abi": 3, "keys": keys, "values": packed.tolist(), "raw_sha256": raw_sha(packed)},
        "full ABI3 packing",
    )
    if len(keys) != 66:
        raise ValueError("wrong ABI3 world width")
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
        "analysis/selection.py",
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
        "cap_cpu_seconds": 5400,
        "search_cpu_seconds": 3400,
        "confirmation_reserved_cpu_seconds": 2000,
        "running": {},
        "queued": [],
        "ready": ready,
    }.items():
        assert_equal(budget[name], value, "terminal budget " + name)
    completed = budget["completed"]
    if (
        len(completed) != 3
        or completed[-1] != {"name": "confirmation", "exit_code": 0}
        or {x["name"] for x in completed[:2]} != set(workers[:2])
        or any(x["exit_code"] != 0 for x in completed)
    ):
        raise ValueError("both searches must finish before the one confirmation")
    if budget.get("reason") is not None or budget.get("error") or budget.get("cleanup_error"):
        raise ValueError("terminal failure")
    total = number(budget["cpu_seconds"], "total CPU", 5390)
    search = number(budget["search_stage_cpu_seconds"], "search CPU", 3390)
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
        "selection": "Both complete generation4 final population rank0 endpoints fixed together before confirmation.",
    }.items():
        assert_equal(record[name], value, "frozen endpoints " + name)
    data = npz(base / "confirmation/genotypes.npz")
    assert_equal(set(data), {"genomes", "labels"}, "genotype archive schema")
    assert_equal(data["labels"].tolist(), LABELS, "genotype role order")
    g = data["genomes"]
    if g.shape != (3, 875) or g.dtype != np.float32 or not np.isfinite(g).all():
        raise ValueError("three complete finite genomes required")
    assert_equal([raw_sha(g[0])], REFERENCES, "confirmation references")
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
    names = [f"persistent/row_{i:04d}.npz" for i in range(3)]
    assert_equal(set(index), set(names), "all three confirmation rows")
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
    score = npz(folder / "persistent/scores.npz")
    assert_equal(set(score), set(A.COLS) | {"seeds", "genome_indices"}, "aggregate schema")
    if not A.identical(score["seeds"], seeds) or not A.identical(score["genome_indices"], np.arange(3)):
        raise ValueError("aggregate identities differ")
    for key in A.COLS:
        if not A.identical(score[key], np.stack([rows[i][key] for i in range(3)])):
            raise ValueError("raw/aggregate mismatch " + key)
    report = read(folder / "report.json")
    for name, value in {
        "status": "complete",
        "report_only": True,
        "genome_lives": 1536,
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
        native = module("AH_native_audit", HERE / "native_audit.py").audit(base, p, ep, g, external)
        native.pop("audit_process_cpu_seconds", None)
        rows, report, cpu, pinmap = load_rows(base, p, ep, budget)
        assert_equal(set(report["absolute"]), set(LABELS), "all three absolute role reports")
        absolute_metrics = {
            "F",
            "F_kernel",
            "captures",
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
            "confirmation/persistent/scores.npz",
        ):
            pinmap[name] = sha(operation(base, name))
        return {
            "status": "complete",
            "study": p["study"],
            "protocol_sha256": PROTOCOL_SHA,
            "research_lives": 9804,
            "startup_validation_lives": 6,
            "total_lives": 9810,
            "resources": dict(resource, raw_confirmation_cpu_seconds=cpu),
            "world": p["world"],
            "seeds": p["confirmation"]["seeds"],
            "native_audit": native,
            "contrasts": result,
            "primary_behavioral_estimate": {
                "contrast": "AH_reserve_minus_AH_control",
                "metric": "captures",
                **result["primary"]["AH_reserve"]["columns"]["captures"],
                "interpretation": "Fixed-endpoint paired acquisition estimate; one paired search does not establish policy reliability.",
            },
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
