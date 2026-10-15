"""Complete-study Z audit: native recorded genetics plus unchanged Y58 accounting.
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
import numpy as np

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


A = module("Z_offline_accounting", HERE / "offline_accounting.py")
PROTOCOL_SHA = "2e3e2a2f7bd19f8a10620f8bf4c23a5eb31d4c033a48c0939bf421d234be2935"
LABELS = ["D90", "L92", "Y_D90", "Y_L92", "Z_D90", "Z_L92"]
REFERENCES = [
    "1287ee4421f88fc108c073eae282f625bd0e340a5e4b12d590cd27cbc046bfac",
    "8f14c79b8bea73c08dff7f6bc1094dc848534f9f2d45598c99c4351cf364cf27",
    "2317b26eb6c61d99e12d8a345436bcbcb16d7863048715278525148aec9b413e",
    "6935252982803614cb973b8b938e7ca927ab2d72e5ef31aaa243c2625385d86a",
]
FIELDS = ("W", "b", "lam", "s0", "Q", "act", "A", "a0", "Dm", "km")
PAIRS = {"primary": [[4, 2], [5, 3]], "cumulative": [[4, 0], [5, 1]], "start": [[2, 0], [3, 1]]}
LIMITATIONS = [
    "Two fixed four-generation continuations do not estimate general evolutionary reliability.",
    "Paired512-life SE describes these fixed genotypes over world seeds, not variation across independent searches.",
    "Low-light captures do not isolate memory, prediction or a specific algorithm; movement, growth, cues and costs can contribute.",
    "Both Y screen-selected starts are retained regardless of their previous confirmation signs.",
    "Recorded genetic operations and shortlist ranking are replayed; RNG draws and unretained search life ledgers are not reconstructed.",
    "Native validation and tiny final diagnostics retain summaries rather than raw ledgers; the six confirmation rows receive full58-column reconciliation.",
    "Initial search guard counts are available; logs do not separately enumerate every recheck guard life.",
    "Six startup lives are established by pinned call paths and three matching numerical receipts; no new golden is executed by this audit.",
    "Natural extinction and paid guards remain in production fitness; missing data, capacity or ledger mismatch blocks a complete verdict.",
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


def verify_protocol(base):
    assert_equal(sha(base / "protocol.json"), PROTOCOL_SHA, "reviewed protocol")
    p = read(base / "protocol.json")
    for name, value in {
        "study": "Z ordinary blink continuation",
        "generations": 4,
        "max_cpu_seconds": 7200,
        "search_cpu_seconds": 3600,
        "max_simulation_threads": 4,
        "search_genome_lives": 8268,
        "confirmation_genome_lives": 3072,
        "planned_genome_lives": 11340,
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
    assert_equal(
        p["expected_numerical_identity"],
        read(base / "inputs/Y/startup_identity.json")["identity"],
        "unchanged Y identity",
    )
    assert_equal(p["world"], read(base / "inputs/Y/protocol.json")["world"], "unchanged complete Y physics")
    if p["world"]["T"] != 1024 or p["world"]["name"] != "catch_speck_blink20_20_l4":
        raise ValueError("fixed blink world differs")
    c = p["confirmation"]
    assert_equal(c["labels"], LABELS, "six ordered roles")
    assert_equal(c["threads"], 2, "confirmation threads")
    for name, pairs_ in PAIRS.items():
        assert_equal(c[name + "_pairs"], pairs_, name + " pairs")
    reg, audit = read(base / "registration.json"), read(base / "seed_audit.json")
    assert_equal(reg["status"], "registered", "registration")
    assert_equal(reg["founder_policy"], "both_Y_selected_regardless_of_confirmation_sign", "fixed start policy")
    assert_equal(reg["runs"], p["runs"], "run registration")
    assert_equal(reg["confirmation_seeds"], c["seeds"], "confirmation registration")
    assert_equal(audit["status"], "passed", "seed audit status")
    assert_equal(audit["runs"], p["runs"], "seed audit runs")
    assert_equal(audit["confirmation_seeds"], c["seeds"], "seed audit confirmation")
    allseeds = [v for values in audit["run_life_seeds"].values() for v in values] + c["seeds"]
    if (
        len(p["runs"]) != 2
        or len(set(p["runs"])) != 2
        or len(c["seeds"]) != 512
        or len(allseeds) != 640
        or len(set(allseeds)) != 640
        or 11 in allseeds
    ):
        raise ValueError("exact disjoint search/confirmation namespaces required")
    assert_equal(
        read(base / "generation_claim.json"),
        {"registration_sha256": sha(base / "registration.json"), "runs": p["runs"]},
        "one initial generation claim",
    )
    refs = [genome(base / name) for name in p["reference_files"]]
    assert_equal([raw_sha(x) for x in refs], REFERENCES, "four fixed original/Y references")
    for i, seed in enumerate(p["runs"]):
        meta = p["founder_mapping"][str(seed)]
        assert_equal(meta["raw_sha256"], REFERENCES[i + 2], "registered start raw hash")
        assert_equal(meta["background"], LABELS[i], "registered background order")
    tree = ast.parse(external(base, "src/life/spec.py").read_text())
    values = {
        n.targets[0].id: n.value for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
    }
    names = (
        ast.literal_eval(values["LEDGER_V2"])
        + ast.literal_eval(values["LEDGER_V3"].right)
        + ast.literal_eval(values["LEDGER_V4"].right)
    )
    assert_equal(names, A.LEDGER, "all58 ledger column indices")
    rate = read(base / "inputs/Y_cost_rows.json")["rates"]
    maxima = {k: max(v.values()) for k, v in rate.items()}
    projection = p["cost_projection"]
    assert_equal(projection["rates_cpu_per_life"], rate, "timing projection inputs")
    assert_equal(projection["startup_search_projection"], 180 + 1.5 * 4134 * sum(maxima.values()), "search projection")
    assert_equal(
        projection["confirmation_projection"],
        180 + 1.5 * 512 * sum(sum(rate[k].values()) + 2 * maxima[k] for k in rate),
        "confirmation projection",
    )
    if not projection["feasible"] or any(
        projection[k] > 3590 for k in ("startup_search_projection", "confirmation_projection")
    ):
        raise ValueError("registered fixed feasibility test failed")
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
    workers = [f"evolve_s{seed}" for seed in p["runs"]] + ["confirmation"]
    owned_processes(attempt, budget, workers)
    for name, value in {
        "status": "complete",
        "exit_code": 0,
        "phase": "confirmation",
        "cap_cpu_seconds": 7200,
        "search_cpu_seconds": 3600,
        "confirmation_reserved_cpu_seconds": 3600,
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
    total = number(budget["cpu_seconds"], "total CPU", 7190)
    search = number(budget["search_stage_cpu_seconds"], "search CPU", 3590)
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
    if g.shape != (6, 875) or g.dtype != np.float32 or not np.isfinite(g).all():
        raise ValueError("six complete finite genomes required")
    assert_equal([raw_sha(x) for x in g[:4]], REFERENCES, "confirmation references")
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
        native = module("Z_native_audit", HERE / "native_audit.py").audit(base, p, ep, g, external)
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
            "research_lives": 11340,
            "startup_validation_lives": 6,
            "total_lives": 11346,
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
