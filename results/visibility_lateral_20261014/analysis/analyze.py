"""Independent complete-study AA reader bound to the registered protocol.
NumPy-only; retains every valid guarded/extinct row in matched late-window contrasts.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("AA_independent_accounting", HERE / "offline_accounting.py")
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)
PROTOCOL_SHA = "d9028fe08597f62782759ab98384408b7522394e202bf84218f0b5e6b7ccbeab"
LABELS = ["D90", "L92", "Y_D90", "Y_L92", "Z_D90", "Z_L92"]
CONDITIONS = ["normal", "freeze", "freeze+lateral_off"]
PAIRS = {"primary": [[4, 2], [5, 3]], "start": [[2, 0], [3, 1]], "cumulative": [[4, 0], [5, 1]]}
METRICS = (
    "F",
    "F_kernel",
    "captures",
    "low_light_captures",
    "clicks",
    "misses",
    "spikes",
    "kappa_sum",
    "contact_events",
    "rec_gain",
    "income",
    "cost",
    "guard_charge",
    "extinct_charge",
    "live_time",
    "n_end",
    "n_S_end",
    "n_M_end",
    "n_H_end",
    "last_birth",
    "path",
    "bright_captures",
    "capture_income",
    "ordinary_cost_saving",
    "guard_charge_saving",
    "extinction_charge_saving",
)
METRIC_MAP = {
    "ordinary_cost_saving": "ordinary_cost",
    "guard_charge_saving": "guard_cost",
    "extinction_charge_saving": "extinction_cost",
}


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


def verify_protocol(base):
    assert_equal(sha(base / "protocol.json"), PROTOCOL_SHA, "reviewed AA protocol")
    p = read(base / "protocol.json")
    for name, value in {
        "study": "AA fixed-tissue blink lateral dependence",
        "labels": LABELS,
        "conditions": CONDITIONS,
        "T": 1024,
        "t_fork": 512,
        "t_open": 544,
        "max_cpu_seconds": 1200,
        "max_workers": 1,
        "max_simulation_threads": 2,
        "planned_genome_lives": 2304,
        "startup_validation_genome_lives": 2,
    }.items():
        assert_equal(p[name], value, "registered " + name)
    for name, pairs_ in PAIRS.items():
        assert_equal(p[name + "_pairs"], pairs_, name + " pairs")
    pins(base, p["file_pins"])
    pins(base, p["production_pins"], external_paths=True)
    reg = read(base / "registration.json")
    audit = read(base / "seed_audit.json")
    assert_equal(sha(base / "registration.json"), p["registration_sha256"], "registration pin")
    for name, value in {
        "status": "registered",
        "labels": LABELS,
        "conditions": CONDITIONS,
        "seeds": p["seeds"],
    }.items():
        assert_equal(reg[name], value, "root " + name)
    assert_equal(sha(base / "seed_audit.json"), reg["seed_audit_sha256"], "independent namespace pin")
    assert_equal(audit["status"], "passed", "namespace status")
    assert_equal(audit["seeds"], p["seeds"], "namespace seeds")
    if (
        len(p["seeds"]) != 128
        or len(set(p["seeds"])) != 128
        or 11 in p["seeds"]
        or any(type(x) is not int or x < 0 for x in p["seeds"])
    ):
        raise ValueError("128 fresh paired seeds required")
    z = read(base / "inputs/Z/protocol.json")
    zb = read(base / "inputs/Z/budget.json")
    summary = read(base / "inputs/Z_summary.json")
    if (
        summary["status"] != "complete"
        or zb["status"] != "complete"
        or zb["running"]
        or zb["queued"]
        or zb.get("cleanup_error")
        or zb["exit_code"] != 0
        or summary["protocol_sha256"] != sha(base / "inputs/Z/protocol.json")
    ):
        raise ValueError("reviewed complete Z required")
    assert_equal(p["production_pins"], z["production_pins"], "unchanged Z source closure")
    assert_equal(p["expected_numerical_identity"], z["expected_numerical_identity"], "unchanged Z numerical identity")
    assert_equal(p["unmodified_world"], z["world"], "unchanged blink physics")
    for condition, flags in zip(CONDITIONS, (0, 16, 2064)):
        expected = dict(z["world"], t_fork=512, t_open=544, fork_flags=flags)
        assert_equal(p["worlds"][condition], expected, "exact matched intervention " + condition)
    data = npz(base / p["genotypes_file"])
    assert_equal(set(data), {"genomes", "labels"}, "six-role genotype archive schema")
    assert_equal(data["labels"].tolist(), LABELS, "role order")
    g = data["genomes"]
    if g.shape != (6, 875) or g.dtype != np.float32 or not np.isfinite(g).all():
        raise ValueError("six fixed raw genomes required")
    assert_equal(dict(zip(LABELS, map(raw_sha, g))), p["genotype_sha256"], "genotype raw hashes")
    endpoint = read(base / "inputs/Z/confirmation/endpoints.json")
    assert_equal(endpoint["genotype_sha256"], p["genotype_sha256"], "terminal Z endpoint binding")
    assert_equal(endpoint["labels"], LABELS, "terminal Z roles")
    retained = read(base / "inputs/Z_cost_rows.json")
    zindex = read(base / "inputs/Z/confirmation/row_index.json")
    rates, timing_pins = {}, {}
    for i, label in enumerate(LABELS):
        relative = f"blink/row_{i:04d}.npz"
        path = base / "inputs/Z/confirmation" / relative
        timing_pins["confirmation/" + relative] = sha(path)
        assert_equal(sha(path), zindex[relative]["sha256"], "retained Z timing row pin")
        row = npz(path)
        expected = {
            "protocol_sha256": sha(base / "inputs/Z/protocol.json"),
            "stage": "confirmation",
            "endpoints_sha256": sha(base / "inputs/Z/confirmation/endpoints.json"),
            "role": label,
            "genome_index": i,
            "genome_sha256": p["genotype_sha256"][label],
            "seeds": z["confirmation"]["seeds"],
        }
        if (
            row["ledger"].shape != (512, 58)
            or row["ledger"].dtype != np.float64
            or not np.isfinite(row["ledger"]).all()
            or row["identity"].shape != ()
            or str(row["identity"]) != canonical(expected)
            or row["genome_index"].shape != ()
            or int(row["genome_index"]) != i
            or not A.identical(row["seeds"], np.asarray(z["confirmation"]["seeds"], dtype=np.uint64))
        ):
            raise ValueError("actual Z timing row identities or coverage differ")
        if row["cpu_seconds"].shape != () or row["wall_seconds"].shape != ():
            raise ValueError("Z scalar timings required")
        cpu = number(float(row["cpu_seconds"]), "retained Z CPU")
        number(float(row["wall_seconds"]), "retained Z wall time")
        assert_equal(cpu, zindex[relative]["cpu_seconds"], "retained Z raw/index CPU")
        rates[label] = cpu / 512
    assert_equal(retained["source_pins"], timing_pins, "all six retained timing input pins")
    projection = p["cost_projection"]
    assert_equal(retained["projection"], projection, "retained timing projection")
    assert_equal(projection["rates_cpu_per_life"], rates, "six actual developed-body rates")
    assert_equal(set(rates), set(LABELS), "all six measured timing rates")
    if any(number(v, "developed-body rate") <= 0 for v in rates.values()):
        raise ValueError("positive timing rates required")
    assert_equal(
        projection["projected_cpu_seconds"], 180 + 1.5 * 3 * 128 * sum(rates.values()), "fixed feasibility formula"
    )
    if projection["feasible"] is not True or projection["projected_cpu_seconds"] > 1190:
        raise ValueError("fixed feasibility failed")
    return p


def resources(base, p):
    ready = read(operation(base, "ready.json"))
    assert_equal(ready["status"], "released", "release status")
    assert_equal(ready["production_pins"], p["production_pins"], "release sources")
    required = dict(p["file_pins"])
    for name in ("protocol.json", "resource_clearance.json", "analysis/analyze.py", "analysis/offline_accounting.py"):
        required[name] = sha(operation(base, name))
    if any(ready["source_pins"].get(k) != v for k, v in required.items()):
        raise ValueError("release misses required analysis/input pins")
    pins(base, ready["source_pins"], operational=True)
    assert_equal(sha(__file__), ready["source_pins"]["analysis/analyze.py"], "executing reader")
    assert_equal(sha(A.__file__), ready["source_pins"]["analysis/offline_accounting.py"], "executing accountant")
    clear = read(operation(base, "resource_clearance.json"))
    if clear["status"] != "cleared" or clear["all_processes_exited"] is not True:
        raise ValueError("prior resources uncleared")
    pins(base, clear["budget_pins"], external_paths=True)
    if not clear["processes"] or not clear["process_groups"]:
        raise ValueError("prior exact process records absent")
    for item in clear["processes"]:
        if any(type(item.get(k)) is not int or item[k] <= 0 for k in ("pid", "start_ticks")):
            raise ValueError("prior exact identity absent")
    for name in clear["budget_pins"]:
        old = read(external(base, name))
        if (
            old.get("status") in (None, "running")
            or old.get("running")
            or old.get("queued")
            or old.get("cleanup_error")
        ):
            raise ValueError("prior budget still active")
    attempt, budget = read(operation(base, "attempt.json")), read(operation(base, "budget.json"))
    assert_equal(attempt["ready_sha256"], sha(operation(base, "ready.json")), "one attempt release")
    owned_processes(attempt, budget, ["measurement"])
    for name, value in {
        "status": "complete",
        "exit_code": 0,
        "phase": "measurement",
        "cap_cpu_seconds": 1200,
        "running": {},
        "queued": [],
        "completed": [{"name": "measurement", "exit_code": 0}],
        "ready": ready,
    }.items():
        assert_equal(budget[name], value, "terminal " + name)
    if budget.get("reason") is not None or budget.get("error") or budget.get("cleanup_error"):
        raise ValueError("monitor failure")
    total = number(budget["cpu_seconds"], "total CPU", 1190)
    number(budget["wall_seconds"], "wall time")
    if not budget["affinity"] or any(type(x) is not int or not 0 <= x < 12 for x in budget["affinity"]):
        raise ValueError("CPU affinity differs")
    startup = read(base / "startup_identity.json")
    assert_equal(startup["protocol_sha256"], PROTOCOL_SHA, "startup protocol")
    assert_equal(startup["startup_validation_genome_lives"], 2, "one golden pair")
    assert_equal(startup["identity"], p["expected_numerical_identity"], "complete startup identity")
    binaries = {sha(path) for path in (base / "build-cache").rglob("*.so")}
    if not set(startup["identity"]["kernels"].values()).issubset(binaries):
        raise ValueError("retained full/fast kernel binaries missing")
    return budget, {"total_cpu_seconds": total, "first_attempt_only": True}


def load_rows(base, p, budget):
    folder = base / "measurement"
    index = read(folder / "row_index.json")
    names = {f"{c}/row_{i:04d}.npz" for c in CONDITIONS for i in range(6)}
    assert_equal(set(index), names, "all eighteen row identities")
    assert_equal({str(x.relative_to(folder)) for x in folder.rglob("row_*.npz")}, names, "no missing or stale rows")
    rows, pinmap, cpu = {}, {}, 0.0
    for condition in CONDITIONS:
        rows[condition] = {}
        for i, label in enumerate(LABELS):
            name = f"{condition}/row_{i:04d}.npz"
            path = folder / name
            row = npz(path)
            assert_equal(sha(path), index[name]["sha256"], "raw row pin")
            assert_equal(
                set(row),
                set(A.COLS) | {"identity", "seeds", "genome_index", "ledger", "cpu_seconds", "wall_seconds"},
                "raw schema",
            )
            expected = {
                "protocol_sha256": PROTOCOL_SHA,
                "genotypes_sha256": sha(base / p["genotypes_file"]),
                "role": label,
                "condition": condition,
                "stage": condition,
                "genome_index": i,
                "genome_sha256": p["genotype_sha256"][label],
                "seeds": p["seeds"],
            }
            if (
                row["identity"].shape != ()
                or row["identity"].dtype.kind != "U"
                or str(row["identity"]) != canonical(expected)
            ):
                raise ValueError("raw identity differs")
            if (
                row["genome_index"].shape != ()
                or row["genome_index"].dtype.kind not in "iu"
                or int(row["genome_index"]) != i
                or not A.identical(row["seeds"], np.asarray(p["seeds"], dtype=np.uint64))
            ):
                raise ValueError("raw seed or genome order differs")
            A.validate_row(row, p["worlds"][condition], 128)
            assert_equal(
                number(index[name]["cpu_seconds"], "indexed CPU"), float(row["cpu_seconds"]), "raw timing binding"
            )
            cpu += float(row["cpu_seconds"])
            rows[condition][i] = row
            pinmap[str(path.relative_to(base))] = sha(path)
        score = npz(folder / condition / "scores.npz")
        assert_equal(set(score), set(A.COLS) | {"seeds", "genome_indices"}, "aggregate schema")
        if not A.identical(score["seeds"], np.asarray(p["seeds"], dtype=np.uint64)) or not A.identical(
            score["genome_indices"], np.arange(6)
        ):
            raise ValueError("aggregate identities differ")
        for key in A.COLS:
            if not A.identical(score[key], np.stack([rows[condition][i][key] for i in range(6)])):
                raise ValueError("aggregate/raw column differs " + key)
        pinmap[str((folder / condition / "scores.npz").relative_to(base))] = sha(folder / condition / "scores.npz")
    report = read(folder / "report.json")
    for name, value in {
        "status": "complete",
        "report_only": True,
        "genome_lives": 2304,
        "paired_seeds": 128,
        "startup_validation_genome_lives": 2,
        "protocol_sha256": PROTOCOL_SHA,
        "startup_identity_sha256": sha(base / "startup_identity.json"),
        "labels": LABELS,
        "conditions": CONDITIONS,
    }.items():
        assert_equal(report[name], value, "complete worker " + name)
    if abs(number(report["row_cpu_seconds"], "reported CPU") - cpu) > 1e-6 or cpu > budget["cpu_seconds"] + 1e-6:
        raise ValueError("raw CPU exceeds monitored total")
    return rows, report, cpu, pinmap


def contrast_names():
    mapping = {}
    for group, pairs_ in PAIRS.items():
        for a, b in pairs_:
            own = group + "__" + LABELS[a]
            producer = own + "_minus_" + LABELS[b]
            for condition in CONDITIONS:
                mapping[own + "__gain__" + condition] = producer + "__gain__" + condition
            mapping[own + "__added_lateral"] = producer + "__added_lateral_dependence"
            mapping[own + "__gain_lost_under_freeze"] = producer + "__gain_lost_under_freeze"
    mapping.update({"own_lateral__" + label: label + "__frozen_lateral_loss" for label in LABELS})
    return mapping


def validate_report(base, rows, p, report, result, vectors):
    saved = npz(base / "measurement/paired.npz")
    names = contrast_names()
    assert_equal(set(report["contrasts"]), set(METRICS), "all reported metrics")
    assert_equal(set(report["absolute"]), set(METRICS), "all absolute metrics")
    assert_equal(
        set(saved),
        {metric + "___" + name for metric in METRICS for name in names.values()},
        "all worker paired vectors",
    )
    for metric in METRICS:
        key = METRIC_MAP.get(metric, metric)
        assert_equal(set(report["contrasts"][metric]), set(names.values()), "all36 contrasts")
        for ours, theirs in names.items():
            values = vectors[ours + "__" + key]
            check_stats(report["contrasts"][metric][theirs], values, metric + " " + theirs)
            raw = saved[metric + "___" + theirs]
            if raw.shape != (128,) or raw.dtype != np.float64 or not np.isfinite(raw).all():
                raise ValueError("invalid saved paired vector shape/dtype")
            if not np.allclose(saved[metric + "___" + theirs], values, rtol=1e-12, atol=1e-12):
                raise ValueError("worker paired vector differs")
        assert_equal(set(report["absolute"][metric]), set(CONDITIONS), "absolute conditions")
        for condition in CONDITIONS:
            assert_equal(set(report["absolute"][metric][condition]), set(LABELS), "absolute roles")
            for i, label in enumerate(LABELS):
                values = A.metric_vectors(rows[condition][i], p["worlds"][condition])[key]
                check_stats(report["absolute"][metric][condition][label], values, "absolute " + metric)
    structural = report["frozen_checks"]
    assert_equal(structural["window"], [544, 1024], "frozen interval")
    assert_equal(structural["all_fitness_rows_retained"], True, "no scientific exclusion")
    expected = [
        {
            "label": label,
            "complete_paired_lives": result["frozen_structure"][label]["complete_guard_free_pairs"],
            "excluded_from_structural_equality_only": result["frozen_structure"][label]["guard_or_extinct_pairs"],
        }
        for label in LABELS
    ]
    assert_equal(structural["coverage"], expected, "frozen engineering coverage")


def analyze(base):
    base = Path(base).resolve()
    try:
        p = verify_protocol(base)
        budget, resource = resources(base, p)
        rows, report, cpu, pinmap = load_rows(base, p, budget)
        result, vectors = A.contrasts(rows, p["worlds"], PAIRS, LABELS)
        validate_report(base, rows, p, report, result, vectors)
        result["absolute_means"] = {
            condition: {
                LABELS[i]: {key: A.stats(value) for key, value in A.metric_vectors(row, p["worlds"][condition]).items()}
                for i, row in arms.items()
            }
            for condition, arms in rows.items()
        }
        result["health"] = {
            condition: {LABELS[i]: A.validate_row(row, p["worlds"][condition], 128) for i, row in arms.items()}
            for condition, arms in rows.items()
        }

        for name in (
            "protocol.json",
            "ready.json",
            "attempt.json",
            "budget.json",
            "resource_clearance.json",
            "startup_identity.json",
            "measurement/row_index.json",
            "measurement/report.json",
            "measurement/paired.npz",
        ):
            pinmap[name] = sha(operation(base, name))
        return {
            "status": "complete",
            "study": p["study"],
            "protocol_sha256": PROTOCOL_SHA,
            "research_lives": 2304,
            "startup_validation_lives": 2,
            "total_lives": 2306,
            "resources": dict(resource, raw_row_cpu_seconds=cpu),
            "worlds": p["worlds"],
            "seeds": p["seeds"],
            "labels": LABELS,
            "ledger_columns": list(A.LEDGER),
            "input_pins": pinmap,
            **result,
        }, vectors
    except (OSError, ValueError, KeyError, TypeError, IndexError, OverflowError, AttributeError) as error:
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
            raise SystemExit("output cannot replace input")
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "summary.json").write_bytes(json_bytes(summary))
        np.savez_compressed(args.out / "paired_vectors.npz", **vectors)
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
