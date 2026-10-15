"""Fail-closed independent NumPy analysis of complete visibility-information pilot records.

No engine imports, compilation, subprocesses, controller execution or simulation.
Local imports are independent audit helpers. No scientific outcomes are returned for partial records.
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


def helper(name):
    spec = importlib.util.spec_from_file_location("visibility_audit_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A, C = helper("accounting"), helper("candidates")
REVIEWED_PROTOCOL_SHA256 = "a2e3699ca131b0091473097607be054d6908c4470aadd1996ad5f2acc0a75d99"
ROLES, WORLDS = C.ROLES, C.WORLDS
SEEDS = list(range(52_130_000, 52_130_512))
VALIDATION_SEEDS = [52_160_000, 52_160_001]
SCOPE = dict(
    total_cpu_seconds=3599,
    validation_cpu_seconds=179,
    max_workers=2,
    threads_per_worker=1,
    research_lives=13312,
    validation_lives=82,
    worlds=WORLDS,
    roles=ROLES,
)
LIMITATIONS = [
    "This is fixed external-controller information-payoff measurement, not evolved behavior.",
    "A removes the broad visibility model; B suppresses actions while believed dark. Neither isolates memory or a specific capability.",
    "The information/reference contrast combines sensing, state estimation, model assumptions and action policy.",
    "Reference and do-less winners are selected by whole-sample mean. Paired SEs are descriptive, conditional on selection; fixed contrasts are also retained.",
    "Matching seed IDs pairs exogenous random streams, but actions change subsequent trajectories and capture-triggered replacements.",
    "Scratch 57-column ledgers are labelled as scratch; dark captures map to production low-light captures only through the accepted physical bridge.",
    "G5 duration extension and capability-specific admission remain incomplete; no automatic admission or memory claim follows.",
    "CPU is the monitor total including validation and compilation. Row process CPU omits wrapper/compression/monitor overhead.",
]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    # Duplicate keys and NaN are malformed evidence, even where JSON's default reader tolerates them.
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out

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
    """Prefer archival copies; working-layout repo fallback is used only when no copy exists."""
    roots = [Path(base) / "production"]
    # original/src is the intentionally different frozen ABI3 controller package.
    # Other original/<repo-path> files are portable dependency receipts and win over mutable live outputs.
    if Path(name).parts[:1] != ("src",):
        roots.append(Path(base) / "original")
    roots.append(Path(base).resolve().parents[1])
    for root in roots:
        path = inside(root, name)
        if path.is_file():
            return path
    raise FileNotFoundError("missing pinned external input: " + name)


def operation(base, name):
    path = inside(base, name)
    return path if path.is_file() else inside(Path(base) / "operations", name)


def pins(base, table, external_paths=False):
    if not isinstance(table, dict) or not table:
        raise ValueError("empty required pin map")
    for name, expected in table.items():
        path = external(base, name) if external_paths else inside(base, name)
        if not isinstance(expected, str) or len(expected) != 64 or sha(path) != expected:
            raise ValueError("changed pinned input: " + name)


def number(value, name, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid " + name)
    if maximum is not None and value >= maximum:
        raise ValueError(name + " reaches stop threshold")
    return float(value)


def array(values, name, shape, dtype=np.float64):
    x = values[name]
    if x.shape != shape or x.dtype != np.dtype(dtype):
        raise ValueError("invalid raw array " + name)
    if x.dtype.kind == "f" and not np.isfinite(x).all():
        raise ValueError("nonfinite raw array " + name)
    return x


def npz(path):
    with np.load(path, allow_pickle=False) as data:
        if len(data.files) != len(set(data.files)):
            raise ValueError("duplicate NPZ field")
        return {key: data[key].copy() for key in data.files}


def world_packing(base, protocol):
    tree = ast.parse((base / "original/src/life/spec.py").read_text())
    world = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "World")
    keys = [node.target.id for node in world.body if isinstance(node, ast.AnnAssign)]
    keys = [key for key in keys if key not in ("name", "stage", "implemented", "lattice", "lives")]
    if len(keys) != 66:
        raise ValueError("unexpected frozen world packing")
    slots = {"blink_on": 38, "blink_off": 39, "dim_flag": 19, "dark_amp": 16}
    for name in WORLDS:
        entry = protocol["worlds"][name]
        w = entry["base_world"]
        if (w["T"], w["t0"], w["t_open"], w["flags"], w["b2_amp"], w["d0"], w["d_min"], w["lattice"]) != (
            1024,
            0,
            0,
            512,
            0,
            1,
            0.5,
            "hexprism",
        ):
            raise ValueError("fixed physical world changed")
        expected_slots = (
            {"blink_on": 5.0, "blink_off": -1.0, "dim_flag": 777.0, "dark_amp": 0.25}
            if name == WORLDS[0]
            else {"blink_on": 20.0, "blink_off": 20.0}
        )
        if entry["scratch_slots"] != expected_slots:
            raise ValueError("scratch visibility rules changed")
        packed = [float(w[key]) for key in keys]
        for key, value in expected_slots.items():
            packed[slots[key]] = value
        if not A.identical(np.asarray(packed), np.asarray(entry["packed_world"], dtype=np.float64)):
            raise ValueError("world vector differs from independent packing")
        prod = entry["production"]
        if prod["sizes"] != [4, 875, 129, 70, 58, 5, 23, 1024, 7, 18]:
            raise ValueError("production ABI4 sizes differ")
        # Production snapshots have no program-mode flag; production_run adds it when executing each body.
        expected = [float(w[key]) if key != "flags" else float(w["flags"] & ~512) for key in keys]
        expected += [1.0, 5.0, 0.0, 0.25] if name == WORLDS[0] else [2.0, 20.0, 20.0, 0.0]
        if not A.identical(np.asarray(expected), np.asarray(prod["packed_world"], dtype=np.float64)):
            raise ValueError("production world does not bridge scratch physics")


def verify_protocol(base):
    path = base / "protocol.json"
    if sha(path) != REVIEWED_PROTOCOL_SHA256:
        raise ValueError("protocol is not the independently reviewed fixed registration")
    p = read(path)
    if p["format"] != 1 or p["study"] != "X2 visibility information" or p["T"] != 1024 or p["n"] != 512:
        raise ValueError("study scope changed")
    if (
        p["seeds"] != SEEDS
        or p["validation_seeds"] != VALIDATION_SEEDS
        or p["seed_block"] != 113
        or p["validation_seed_block"] != 116
    ):
        raise ValueError("fixed fresh paired seed IDs differ")
    if p["monitor_scope"] != SCOPE or set(p["worlds"]) != set(WORLDS):
        raise ValueError("resource or world scope differs")
    if p["abi3_sizes"] != [3, 875, 129, 66, 57, 5, 23, 1024, 7, 18] or p["raw_ledger_aliases"] != {
        "21": "dark_captures",
        "22": "late_captures",
    }:
        raise ValueError("scratch ABI changed")
    if p["production_binding"]["status"] != "complete":
        raise ValueError("production binding missing")
    for field, want in [
        ("information_min_F", 1.0),
        ("information_SE_multiple", 3.0),
        ("do_less_max_fraction", 0.25),
        ("capability_specific_admission", "incomplete"),
        ("G5", "held_unreserved"),
    ]:
        if p["analysis"][field] != want:
            raise ValueError("analysis rule changed")
    pins(base, p["file_pins"])
    pins(base, p["production_pins"], True)
    modules = p["production_module_pins"]
    required_modules = {
        "src/__init__.py",
        "src/life/__init__.py",
        "src/life/spec.py",
        "src/life/build.py",
        "src/lattice.py",
    }
    if not required_modules.issubset(modules) or any(p["production_pins"].get(k) != v for k, v in modules.items()):
        raise ValueError("production Python module closure is not bound")
    review = base / "inputs/reviews"
    namespace = read(review / "namespace_audit.json")
    if (
        namespace["blocks"] != [113, 114, 115, 116]
        or namespace["whole_blocks_half_open"]
        != [[51_000_000 + 10_000 * k, 51_000_000 + 10_000 * (k + 1)] for k in (113, 114, 115, 116)]
        or namespace["numeric_matches"]
        or namespace["malformed_real"]
        or namespace["npz_errors"]
        or namespace["inventory_sha256"] != sha(review / "namespace_inventory.json")
        or namespace["text_review_sha256"] != sha(review / "root_text_namespace_review.json")
    ):
        raise ValueError("prior seed namespace evidence differs")
    text_review = read(review / "root_text_namespace_review.json")
    if text_review["proposed_primary"] != [52_130_000, 52_130_512] or text_review[
        "proposed_validation_whole_block"
    ] != [52_160_000, 52_170_000]:
        raise ValueError("text seed-namespace review differs")
    recovered = read(base / "inputs/recovered_inputs.json")
    candidates = C.verify(base, p, recovered)
    world_packing(base, p)
    return p, candidates


def static_body(ledger, candidate, world):
    cells = np.asarray(candidate["cells"], dtype=np.int32)
    counts = {
        "S": int(np.sum(cells[:, 2] == 0)),
        "M": int(np.sum(cells[:, 2] == 1)),
        "H": int(np.sum(cells[:, 2] >= 2)),
    }
    for key in ("n_end", "n_peak"):
        if np.any(ledger[:, A.L[key]] != len(cells)):
            raise ValueError("fixed body cell count changed")
    for key in ("births", "deaths", "kills", "claims", "rejects", "rejects_wall"):
        if np.any(ledger[:, A.L[key]] != 0):
            raise ValueError("unexpected fixed-body growth or death event")
    census = len(cells) + ledger[:, A.L["births"]] - ledger[:, A.L["deaths"]] - ledger[:, A.L["kills"]]
    if not np.array_equal(census, ledger[:, A.L["n_end"]]):
        raise ValueError("initial-cell plus birth/death/kill census differs")
    for plane, count in counts.items():
        if np.any(ledger[:, A.L["n_" + plane + "_end"]] != count) or not np.allclose(
            ledger[:, A.L["live_" + plane]], count * world["T"], rtol=1e-9, atol=1e-9
        ):
            raise ValueError("fixed physical footprint or lifetime differs")


def resources(base, p):
    ready_path = operation(base, "ready.json")
    ready = read(ready_path)
    if ready.get("status") != "released" or ready["production_pins"] != p["production_pins"]:
        raise ValueError("release missing or changed")
    required = dict(p["file_pins"])
    for name in ("protocol.json", "monitor.py", "measure.py", "validate.py", "resource_clearance.json"):
        required[name] = sha(operation(base, name))
    if any(ready["source_pins"].get(k) != v for k, v in required.items()):
        raise ValueError("release does not bind all fixed inputs")
    for name, digest in ready["source_pins"].items():
        if sha(operation(base, name)) != digest:
            raise ValueError("released input changed")
    clearance = read(operation(base, "resource_clearance.json"))
    if (
        clearance.get("status") != "cleared"
        or clearance.get("all_processes_exited") is not True
        or not clearance["processes"]
        or not clearance["process_groups"]
    ):
        raise ValueError("prior resource clearance absent")
    pins(base, clearance["budget_pins"], True)
    for name in clearance["budget_pins"]:
        prior = read(external(base, name))
        if (
            prior.get("status")
            not in ("complete", "incomplete", "cpu_budget_exhausted", "job_failed", "interrupted", "monitor_failed")
            or prior.get("cleanup_error")
            or prior.get("running")
            or prior.get("queued")
        ):
            raise ValueError("prior dependency is not fully terminal")
    attempt = read(operation(base, "attempt.json"))
    budget = read(operation(base, "budget.json"))
    if attempt.get("ready_sha256") != sha(ready_path):
        raise ValueError("first attempt is not release-bound")
    for key, want in [
        ("status", "complete"),
        ("exit_code", 0),
        ("reason", None),
        ("phase", "research"),
        ("running", {}),
        ("queued", []),
        ("cap_cpu_seconds", 3599),
        ("validation_cap_cpu_seconds", 179),
        ("ready", ready),
    ]:
        if key not in budget or budget[key] != want:
            raise ValueError("monitor is not successfully complete: " + key)
    if budget.get("cleanup_error") or budget.get("error"):
        raise ValueError("monitor cleanup or execution failed")
    names = [item["name"] for item in budget["completed"]]
    if (
        len(names) != 3
        or names[0] != "validation"
        or set(names) != set(["validation", *WORLDS])
        or any(x["exit_code"] != 0 for x in budget["completed"])
    ):
        raise ValueError("missing, failed or repeated monitored worker")
    identities = budget["process_identities"]
    if len(identities) != 4 or {x["name"] for x in identities} != {"monitor", "validation", *WORLDS}:
        raise ValueError("incomplete first-attempt process receipt")
    if len({x["pid"] for x in identities}) != 4:
        raise ValueError("repeated process identity")
    for item in identities:
        if any(type(item[k]) is not int or item[k] <= 0 for k in ("pid", "ppid", "pgid", "start_ticks")):
            raise ValueError("invalid recorded process identity")
    mon = next(x for x in identities if x["name"] == "monitor")
    if attempt["monitor"] != {k: v for k, v in mon.items() if k != "name"}:
        raise ValueError("attempt monitor identity differs")
    children = [x for x in identities if x["name"] != "monitor"]
    if any(x["ppid"] != mon["pid"] or x["pgid"] != x["pid"] for x in children) or budget["owned_process_groups"] != [
        x["pgid"] for x in children
    ]:
        raise ValueError("owned process groups do not match workers")
    total = number(budget["cpu_seconds"], "total CPU", 3589)
    vcpu = number(budget["validation_cpu_seconds"], "validation CPU", 169)
    if total < vcpu:
        raise ValueError("total CPU smaller than validation CPU")
    number(budget["wall_seconds"], "monitor wall time")
    vb = read(operation(base, "validation_budget.json"))
    if vb != {
        "status": "complete",
        "cpu_seconds": budget["validation_cpu_seconds"],
        "cap_cpu_seconds": 179,
        "report_sha256": sha(base / "validation/report.json"),
        "protocol_sha256": sha(base / "protocol.json"),
    }:
        raise ValueError("validation budget receipt differs")
    return dict(
        total_cpu_seconds=total,
        validation_cpu_seconds=vcpu,
        research_cpu_seconds=total - vcpu,
        first_attempt_only=True,
        monitor_accounting_includes_compilation=True,
    )


def verify_validation(base, p):
    report = read(base / "validation/report.json")
    if (
        report.get("status") != "complete"
        or report.get("simulation_calls") != 82
        or report["protocol_sha256"] != sha(base / "protocol.json")
        or report["source_pins"] != p["file_pins"]
        or report["production_pins"] != p["production_pins"]
        or report.get("no_retuning") is not True
        or report.get("no_research_outcomes") is not True
    ):
        raise ValueError("validation report is incomplete or unbound")
    libs = report["libraries"]
    if set(libs) != {"full", "fast", "replay", "production"}:
        raise ValueError("validation library set differs")
    for name, item in libs.items():
        if sha(inside(base, item["path"])) != item["sha256"]:
            raise ValueError("validation library bytes changed")
        if name != "production":
            if (
                sha(inside(base, item["generated_source"])) != item["generated_source_sha256"]
                or item["compiler_sha256"] != p["numerical_identity"]["compiler_sha256"]
            ):
                raise ValueError("compiled source/compiler differs")
            if item["flags"] != p["numerical_identity"]["compiler_flags"] + (["-DLIFE_FAST"] if name == "fast" else []):
                raise ValueError("compiler flags differ")
        elif item["source_sha256"] != p["production_pins"]["src/life/kernel.c"]:
            raise ValueError("production library source differs")
    artifacts = report["artifacts"]
    loaded = {}
    for label, item in artifacts.items():
        path = inside(base, item["path"])
        if sha(path) != item["sha256"]:
            raise ValueError("validation raw artifact changed")
        loaded[label] = npz(path)
    expected = {}
    checks = []
    for world in WORLDS:
        for role in ("R0", "R1"):
            for i, seed in enumerate(VALIDATION_SEEDS):
                case = f"{world}_{role}_{i}"
                for kind, lib in [("scratch", "full"), ("production", "production")]:
                    expected[case + "_" + kind] = (1, 128, [seed], lib)
                old, new = loaded[case + "_scratch"], loaded[case + "_production"]
                cols = [i for i in range(57) if i not in (21, 22)]
                if (
                    not A.identical(old["ledger"][:, cols], new["ledger"][:, cols])
                    or not A.identical(old["ledger"][:, 21], new["ledger"][:, 57])
                    or not A.identical(old["hashes"][:, 1:4], new["hashes"][:, 1:4])
                ):
                    raise ValueError("raw production physical bridge differs")
                checks.append(("production_bridge", case))
        for role in ("I", "A", "B"):
            case = f"{world}_{role}"
            for kind in ("full", "fast"):
                expected[case + "_" + kind] = (2, 128, VALIDATION_SEEDS, kind)
            full, fast = loaded[case + "_full"], loaded[case + "_fast"]
            if any(not A.identical(full[k], fast[k]) for k in ("ledger", "diag", "latency")):
                raise ValueError("raw full/fast parity differs")
            checks.append(("full_fast", case))
            expected[case + "_calibration"] = (2, 1024, VALIDATION_SEEDS, "fast")
            for tag, seed in [
                ("record", VALIDATION_SEEDS[0]),
                ("same_life", VALIDATION_SEEDS[0]),
                ("other_life", VALIDATION_SEEDS[1]),
                ("other_world", VALIDATION_SEEDS[1]),
                ("control", VALIDATION_SEEDS[1]),
            ]:
                expected[case + "_" + tag] = (1, 128, [seed], "replay")
            record = loaded[case + "_record"]
            if any(not A.identical(record[k], full[k][:1]) for k in ("ledger", "hashes", "diag", "latency")):
                raise ValueError("recording instrumentation changes raw outcome")
            log = loaded[case + "_replay_logs"]
            if set(log) != {
                "callbacks",
                "actions",
                "same_life",
                "other_life",
                "other_world",
                "control",
                "same_life_callbacks",
                "other_life_callbacks",
                "other_world_callbacks",
            }:
                raise ValueError("callback replay log schema differs")
            for key, x in log.items():
                if (
                    x.dtype != np.float64
                    or x.ndim != 2
                    or x.shape[1] != (3 if key == "callbacks" or key.endswith("_callbacks") else 6)
                    or len(x) == 0
                    or not np.isfinite(x).all()
                ):
                    raise ValueError("invalid callback/action replay log")
            for tag in ("same_life", "other_life", "other_world"):
                if (
                    not A.identical(log["actions"], log[tag])
                    or not A.identical(log["callbacks"], log[tag + "_callbacks"])
                    or loaded[case + "_" + tag]["diag"][0, 0] != 0
                ):
                    raise ValueError("action replay or no-receptor control differs")
            if A.identical(log["actions"], log["control"]):
                raise ValueError("closed-loop replay control did not differ")
            if (
                artifacts[case + "_replay_logs"].get("truth_calls") != 0
                or artifacts[case + "_replay_logs"]["simulation_calls"] != 0
            ):
                raise ValueError("privileged truth access or extra simulated replay logs")
            checks.append(("C5_replay", case))
    extra_logs = {f"{world}_{role}_replay_logs" for world in WORLDS for role in ("I", "A", "B")}
    if set(artifacts) != set(expected) | extra_logs or sum(x["simulation_calls"] for x in artifacts.values()) != 82:
        raise ValueError("validation life count or artifact set differs")
    raw_cpu = 0.0
    for label, (n, duration, seeds, lib) in expected.items():
        item = artifacts[label]
        if tuple(item[k] for k in ("simulation_calls", "T", "seeds", "library")) != (n, duration, seeds, lib):
            raise ValueError("validation life identity differs")
        x = loaded[label]
        array(x, "hashes", (n, 5), np.uint64)
        raw_cpu += number(float(array(x, "cpu_seconds", ())), "validation row CPU")
        number(float(array(x, "wall_seconds", ())), "validation row wall")
        if lib == "production":
            array(x, "ledger", (n, 58))
            continue
        world = next(w for w in WORLDS if label.startswith(w + "_"))
        w = dict(p["worlds"][world]["base_world"], T=duration)
        A.reconcile(array(x, "ledger", (n, 57)), w, n)
        role = label[len(world) + 1 :].split("_")[0]
        candidate = next(c for c in p["worlds"][world]["candidates"] if c["role"] == role)
        static_body(x["ledger"], candidate, w)
        controller = any(label.startswith(world + "_" + r + "_") for r in ("I", "A", "B"))
        array(x, "diag", (n, 16 if controller else 0))
        lat = array(x, "latency", (n,) if controller else (0,))
        if controller and np.any(lat != w["d0"]):
            raise ValueError("validation action latency changed")
    got = [(x["check"], x["case"]) for x in report["checks"]]
    if len(got) != 20 or set(got) != set(checks) or any(x.get("passed") is not True for x in report["checks"]):
        raise ValueError("validation checks incomplete")
    return dict(
        simulation_calls=82,
        independently_rechecked_cases=20,
        raw_row_cpu_seconds=raw_cpu,
        scratch_raw_ledger_columns=57,
        production_raw_ledger_columns=58,
    )


def load_rows(base, p):
    rows = {}
    cpu = 0.0
    rawpins = {}
    for world in WORLDS:
        directory = base / "rows" / world
        marker = read(directory / "complete.json")
        if any(
            marker.get(k) != v
            for k, v in dict(
                status="complete",
                protocol_sha256=sha(base / "protocol.json"),
                world=world,
                roles=ROLES,
                simulation_calls=6656,
            ).items()
        ):
            raise ValueError("world completion is missing or mismatched")
        if set(marker["checkpoint_pins"]) != {role + "/checkpoint.json" for role in ROLES}:
            raise ValueError("world completion must cover exactly 13 roles")
        pins(directory, marker["checkpoint_pins"])
        rawpins[str((directory / "complete.json").relative_to(base))] = sha(directory / "complete.json")
        rows[world] = {}
        for candidate in p["worlds"][world]["candidates"]:
            role = candidate["role"]
            d = directory / role
            expected = dict(protocol_sha256=sha(base / "protocol.json"), world=world, candidate=candidate, seeds=SEEDS)
            checkpoint = read(d / "checkpoint.json")
            if checkpoint != {"identity": expected, "row_sha256": sha(d / "row.npz")}:
                raise ValueError("row checkpoint identity or raw bytes changed")
            data = npz(d / "row.npz")
            if set(data) != {"identity", "ledger", "hashes", "diag", "latency", "cpu_seconds", "wall_seconds"}:
                raise ValueError("raw research row schema differs")
            if (
                data["identity"].shape != ()
                or data["identity"].dtype.kind != "U"
                or str(data["identity"]) != canonical(expected)
            ):
                raise ValueError("NPZ identity differs from checkpoint")
            x = array(data, "ledger", (512, 57))
            A.reconcile(x, p["worlds"][world]["base_world"])
            static_body(x, candidate, p["worlds"][world]["base_world"])
            array(data, "hashes", (512, 5), np.uint64)
            ctl = "params" in candidate
            array(data, "diag", (512, 16 if ctl else 0))
            latency = array(data, "latency", (512,) if ctl else (0,))
            if ctl and np.any(latency != p["worlds"][world]["base_world"]["d0"]):
                raise ValueError("research action latency changed")
            cpu += number(float(array(data, "cpu_seconds", ())), "research row CPU")
            number(float(array(data, "wall_seconds", ())), "research row wall")
            rows[world][role] = x
            for name in ("checkpoint.json", "row.npz"):
                rawpins[str((d / name).relative_to(base))] = sha(d / name)
    return rows, cpu, rawpins


def scientific_summary(rows, p):
    worlds = {}
    vectors = {}
    for world in WORLDS:
        raw = rows[world]
        w = p["worlds"][world]["base_world"]
        f = {role: x[:, A.L["F"]] for role, x in raw.items()}
        reference = max(("R0", "R1"), key=lambda r: float(f[r].mean()))
        do_less = max(ROLES[5:], key=lambda r: float(f[r].mean()))
        contrasts = {}
        for left, right in [("I", "R0"), ("I", "R1"), ("I", "A"), ("I", "B"), *[(r, reference) for r in ROLES[5:]]]:
            label = left + "_minus_" + right
            summary, v = A.paired_contrast(raw[left], raw[right], w)
            contrasts[label] = summary
            vectors.update({world + "__" + label + "__" + key: value for key, value in v.items()})
        gap = f["I"] - f[reference]
        gapstats = A.mean_se(gap)
        margins = {}
        for role in ROLES[5:]:
            gain = f[role] - f[reference]
            margin = 0.25 * gap - gain
            margins[role] = dict(
                quarter_gap_minus_gain=A.mean_se(margin), fraction_of_information_gap=A.ratio_of_paired_means(gain, gap)
            )
            vectors[world + "__quarter_margin__" + role] = margin
        means = {}
        for role, x in raw.items():
            acc = A.reconcile(x, w)
            means[role] = {
                "raw_columns": {name: A.mean_se(x[:, i]) for i, name in enumerate(A.RAW_LEDGER)},
                "low_light_captures": A.mean_se(acc["low_light_captures"]),
                "bright_captures": A.mean_se(acc["bright_captures"]),
                "costs": {key: A.mean_se(value) for key, value in acc["parts"].items()},
                "low_light_share_of_captures": A.ratio_of_paired_means(
                    acc["low_light_captures"], x[:, A.L["captures"]]
                ),
            }
        best_gain = float((f[do_less] - f[reference]).mean())
        worlds[world] = dict(
            rows=means,
            reference_role=reference,
            do_less_role=do_less,
            reference_selection="largest whole mean; ties retain first registered role",
            contrasts=contrasts,
            information_gap=gapstats,
            do_less_quarter_margins=margins,
            information_payoff_criterion=gapstats["mean"] >= 1.0 and gapstats["mean"] > 3 * gapstats["se"],
            do_less_quarter_criterion=gapstats["mean"] > 0 and best_gain < 0.25 * gapstats["mean"],
            capability_specific_admission="incomplete",
            gradient="not measured by this study",
            G5="held_unreserved",
        )
    return worlds, vectors


def analyze(base):
    base = Path(base).resolve()
    try:
        p, candidates = verify_protocol(base)
        resource = resources(base, p)
        validation = verify_validation(base, p)
        rows, cpu, rawpins = load_rows(base, p)
        if (
            cpu > resource["research_cpu_seconds"] + 1e-6
            or validation["raw_row_cpu_seconds"] > resource["validation_cpu_seconds"] + 1e-6
        ):
            raise ValueError("raw row CPU exceeds monitored phase accounting")
        worlds, vectors = scientific_summary(rows, p)
        summary = dict(
            status="complete",
            protocol_sha256=sha(base / "protocol.json"),
            study="X2 visibility information",
            simulation_calls=13394,
            research_lives=13312,
            validation=validation,
            resources=dict(resource, raw_research_row_cpu_seconds=cpu),
            candidates=candidates,
            ledger_aliases=A.ALIASES,
            seed_ids=SEEDS,
            worlds=worlds,
            limitations=LIMITATIONS,
            input_pins=rawpins,
        )
        for name in ("ready.json", "attempt.json", "budget.json", "validation_budget.json", "resource_clearance.json"):
            summary["input_pins"][name] = sha(operation(base, name))
        summary["input_pins"]["validation/report.json"] = sha(base / "validation/report.json")
        return summary, vectors
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration, OverflowError) as error:
        return dict(
            status="incomplete", scientific_outcomes_emitted=False, error=type(error).__name__ + ": " + str(error)
        ), {}


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
            raise SystemExit("analysis output must not replace study inputs")
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
        np.savez_compressed(args.out / "paired_vectors.npz", **vectors)
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
