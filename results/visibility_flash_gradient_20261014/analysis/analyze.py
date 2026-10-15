"""Independent complete AC analysis; full-life accounting and paired world contrasts.

Accepts only the independently reviewed registered protocol digest.
No engine, worker, compiler, random generator or simulation imports.
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

HERE = Path(__file__).resolve().parent
PROTOCOL_SHA = "672ac123ca9283cd004e699cb6be1b0ac4203b468f75f03546140560cd58fda2"
LABELS = ("P_D90", "P_L92", "B_D90", "B_L92", "H_D90", "H_L92")
PARENTS = ("D90", "L92")
WORLDS = ("flash", "blink")
WITHIN_PAIRS = ((4, 0), (5, 1), (2, 0), (3, 1), (4, 2), (5, 3))
INTERACTION_PAIRS = ((4, 0), (5, 1), (4, 2), (5, 3))
B_ROWS = {"D90": 58, "L92": 24}
Y_PROTOCOL = "1880ff6e21b4689031e892d9dc6765a8d9673a35efeefb213acf268f5370adf4"
Y_PANEL_FILES = {
    "D90": "97ff2d0ee7ef3af4964b1a0fd357a618cb4d0193baa320cd86c2d06f7a8b9cb9",
    "L92": "6ad24101c26541bbc67ff505be2e846e49df30cc253e72d5932d6b0e64d97c01",
}
N = {"calibration": 2, "screen": 32, "confirm": 512}
SCOPE = {
    "total_cpu_seconds": 7200,
    "startup_screen_cpu_seconds": 3400,
    "confirmation_reserve_cpu_seconds": 3800,
    "startup_calibration_cpu_seconds": 180,
    "max_workers": 1,
    "threads_per_worker": 2,
    "research_lives": 10304,
    "validation_lives": 10,
}
GOLDEN_SCOPE = {"abi": 3, "seed": 11, "T": 200, "full": 1, "fast": 1}
GOLDEN = {
    "all": "ebb3ad6fcad2d938",
    "ledger_sha256": "b622f9afad48d6ec5b39b003efba82f25e7e6a764a015fe40398b3a6bbd81251",
}
LIMITATIONS = [
    "Two fixed retained mutation neighborhoods; not a new evolutionary search or an estimate of general search reliability.",
    "All64 mutants are screened in flash; the top whole32-life production-F mutant is retained even when its gain is negative, with exact ties choosing the lower row.",
    "Six genotype roles remain explicit, including duplicates. Paired confirmation uncertainty concerns these fixed genomes over512 seeds, not evolutionary replication.",
    "Flash-minus-blink interactions are computed per seed before their SE. They identify regime-specific payoff, not isolated information use, memory or prediction.",
    "The worlds differ in visibility timing, residual cue strength and placement reset; action-contingent trajectories, development, sensing and economy can all change.",
    "A positive H-versus-B world interaction alone does not imply H beats B in flash or reciprocal specialization.",
    "Dim captures are timing readouts. Capture-income support and ordinary-cost savings are reported separately; neither is a new selection or world-admission gate.",
    "All natural extinction and valid paid guard lives remain in the fixed production-fitness contrasts.",
    "Recorded genetic-operation replay verifies retained raw rows but does not rerun random draws or life dynamics.",
    "Fixed calibration and selected-row timing projections assess feasibility; they cannot bound every unseen expensive lifetime.",
]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


A = module("AC_whole_life_accountant", HERE / "offline_accounting.py")


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


def selected_mutant(rows):
    """All64 original mutants compete; the parent never replaces a losing winner."""
    if set(rows) != set(range(65)):
        raise ValueError("complete65-row screen required")
    means = {i: float(np.asarray(rows[i]["F"]).mean()) for i in range(65)}
    if any(np.asarray(rows[i]["F"]).shape != (32,) or not math.isfinite(means[i]) for i in rows):
        raise ValueError("complete finite32-life screening means required")
    return min(range(1, 65), key=lambda i: (-means[i], i))


def contrast_key(winner, parent):
    return LABELS[winner] + "_minus_" + LABELS[parent]


def contrasts(rows, worlds):
    """Construct each entire paired interaction before estimating sampling error."""
    result, vectors, within = {"within": {}, "interactions": {}}, {}, {}
    for world in WORLDS:
        if set(rows[world]) != set(range(6)):
            raise ValueError("all six explicit roles required in each world")
        result["within"][world] = {}
        for winner, parent in WITHIN_PAIRS:
            key = contrast_key(winner, parent)
            report, terms = A.paired_terms(rows[world][winner], rows[world][parent], worlds[world])
            result["within"][world][key] = report
            within[world, winner, parent] = terms
            vectors.update({"within__" + world + "__" + key + "__" + metric: value for metric, value in terms.items()})
    for winner, parent in INTERACTION_PAIRS:
        key = contrast_key(winner, parent)
        for role in (winner, parent):
            if not A.identical(rows["flash"][role]["seeds"], rows["blink"][role]["seeds"]):
                raise ValueError("cross-world interaction requires the same ordered seeds")
        flash, blink = within["flash", winner, parent], within["blink", winner, parent]
        terms = {metric: flash[metric] - blink[metric] for metric in flash}
        result["interactions"][key] = {metric: A.stats(value) for metric, value in terms.items()}
        vectors.update({"interaction__" + key + "__" + metric: value for metric, value in terms.items()})
    return result, vectors


def check_worlds(worlds):
    assert_equal(set(worlds), set(WORLDS), "both fixed worlds")
    expected = {
        "flash": ("catch_speck_flash5_dim25_l4", 1, 5, 0, 0.25),
        "blink": ("catch_speck_blink20_20_l4", 2, 20, 20, 0),
    }
    differing = {"name", "visibility_mode", "visibility_on", "visibility_off", "visibility_low"}
    for name, w in worlds.items():
        values = tuple(w[k] for k in ("name", "visibility_mode", "visibility_on", "visibility_off", "visibility_low"))
        assert_equal(values, expected[name], "fixed visibility schedule " + name)
        if (w["T"], w["t0"], w["t_open"], w["world_kind"], w["b2_amp"], w["flags"], w["fork_flags"]) != (
            1024,
            0,
            0,
            1,
            0,
            0,
            0,
        ):
            raise ValueError("whole-life single-target ABI4 physics differs")
        if (w["d0"], w["d_min"], w["sigma"], w["lam_s"]) != (1, 0.5, 0.6, 2):
            raise ValueError("base physical dynamics differ")
    assert_equal(
        {k: v for k, v in worlds["flash"].items() if k not in differing},
        {k: v for k, v in worlds["blink"].items() if k not in differing},
        "common non-visibility physics and prices",
    )


def load_store(folder, stages, identities, world, pinmap, base):
    """Reconcile every explicitly indexed raw row and the complete saved aggregates."""
    index = read(folder / "row_index.json")
    expected = {f"{stage}/row_{i:04d}.npz" for stage, indices in stages.items() for i in indices}
    assert_equal(set(index), expected, "exact complete raw-row coverage")
    if {str(path.relative_to(folder)) for path in folder.rglob("row_*.npz")} != expected:
        raise ValueError("missing or unexpected raw row files")
    result, cpu = {}, 0.0
    pinmap[str((folder / "row_index.json").relative_to(base))] = sha(folder / "row_index.json")
    for stage, indices in stages.items():
        result[stage] = {}
        for i in indices:
            path = folder / f"{stage}/row_{i:04d}.npz"
            entry = index[str(path.relative_to(folder))]
            assert_equal(set(entry), {"sha256", "cpu_seconds"}, "row-index entry schema")
            assert_equal(sha(path), entry["sha256"], "raw row bytes")
            row = npz(path)
            assert_equal(
                set(row),
                set(A.COLS) | {"identity", "seeds", "genome_index", "ledger", "cpu_seconds", "wall_seconds"},
                "complete58-ledger and61-column raw schema",
            )
            expected_identity = identities[stage, i]
            if (
                row["identity"].shape != ()
                or row["identity"].dtype.kind != "U"
                or str(row["identity"]) != canonical(expected_identity)
            ):
                raise ValueError("raw row identity differs")
            if (
                row["genome_index"].shape != ()
                or row["genome_index"].dtype.kind not in "iu"
                or int(row["genome_index"]) != i
                or not A.identical(row["seeds"], np.asarray(expected_identity["seeds"], dtype=np.uint64))
            ):
                raise ValueError("raw row ordered seeds or genome index differs")
            A.validate_row(row, world, N[stage])
            charged = number(entry["cpu_seconds"], "indexed row CPU")
            assert_equal(charged, float(row["cpu_seconds"]), "indexed versus raw CPU")
            cpu += charged
            result[stage][i] = row
            pinmap[str(path.relative_to(base))] = sha(path)
        score_path = folder / stage / "scores.npz"
        score = npz(score_path)
        assert_equal(set(score), set(A.COLS) | {"seeds", "genome_indices"}, "aggregate schema")
        ordered = list(indices)
        if not A.identical(score["genome_indices"], np.asarray(ordered)) or not A.identical(
            score["seeds"], result[stage][ordered[0]]["seeds"]
        ):
            raise ValueError("aggregate ordered identities differ")
        for key in A.COLS:
            if not A.identical(score[key], np.stack([result[stage][i][key] for i in ordered])):
                raise ValueError("aggregate/raw physical or scored column differs: " + key)
        pinmap[str(score_path.relative_to(base))] = sha(score_path)
    return result, index, cpu


def historical_costs(base, p, yp):
    """Bind every old blink scalar to its exact retained row, not repeated rates."""
    rates, rowpins = {}, {}
    for background in PARENTS:
        folder = base / "inputs/Y/measurement" / background
        index = read(folder / "row_index.json")
        rates[background] = []
        for i in range(65):
            relative = f"screen/row_{i:04d}.npz"
            path = folder / relative
            entry = index[relative]
            assert_equal(sha(path), entry["sha256"], "historical raw timing row")
            row = npz(path)
            expected = {
                "protocol_sha256": Y_PROTOCOL,
                "background": background,
                "stage": "screen",
                "genome_index": i,
                "genome_sha256": p["panel_genotype_sha256"][background][i],
                "seeds": yp["seeds"]["screen"],
            }
            if (
                row["identity"].shape != ()
                or row["identity"].dtype.kind != "U"
                or str(row["identity"]) != canonical(expected)
                or row["genome_index"].shape != ()
                or row["genome_index"].dtype.kind not in "iu"
                or int(row["genome_index"]) != i
                or row["ledger"].dtype != np.float64
                or row["ledger"].shape != (32, 58)
                or not A.identical(row["seeds"], np.asarray(yp["seeds"]["screen"], dtype=np.uint64))
            ):
                raise ValueError("historical32-life timing row identity differs")
            for name in ("cpu_seconds", "wall_seconds"):
                if row[name].shape != () or row[name].dtype.kind not in "fiu":
                    raise ValueError("historical timing must be a numeric scalar")
                number(float(row[name]), "historical " + name)
            cpu = float(row["cpu_seconds"])
            if cpu <= 0 or cpu != number(entry["cpu_seconds"], "historical indexed CPU"):
                raise ValueError("historical indexed timing differs")
            rates[background].append(cpu / 32)
            rowpins[f"measurement/{background}/{relative}"] = sha(path)
    saved = read(base / "inputs/historical_blink_costs.json")
    assert_equal(
        saved,
        {"source_protocol_sha256": Y_PROTOCOL, "source_pins": rowpins, "cpu_per_life": rates, "lives_per_row": 32},
        "historical cost receipt",
    )
    assert_equal(p["historical_blink_cpu_per_life"], rates, "all130 independent historical rates")
    return rates


def verify_protocol(base):
    if PROTOCOL_SHA is None:
        raise ValueError("source-only reader has no reviewed registered protocol")
    assert_equal(sha(base / "protocol.json"), PROTOCOL_SHA, "exact reviewed protocol")
    p = read(base / "protocol.json")
    for key, expected in (
        ("study", "AC retained-panel flash gradient"),
        ("world_decision", "complete"),
        ("monitor_scope", SCOPE),
        ("roles", list(LABELS)),
        ("blink_selected_rows", B_ROWS),
        ("panel_policy", "entire_Y_panels_unchanged_regardless_of_AB_outcomes"),
        ("Y_protocol_sha256", Y_PROTOCOL),
        ("interaction_orientation", "flash_minus_blink"),
        ("selection", {"rows": list(range(1, 65)), "statistic": "mean_production_F", "tie": "lowest_row_index"}),
        ("primary_contrasts", ["within__flash__H_D90_minus_P_D90", "within__flash__H_L92_minus_P_L92"]),
    ):
        assert_equal(p[key], expected, "protocol " + key)
    pins(base, p["file_pins"])
    pins(base, p["production_pins"], external_paths=True)
    check_worlds(p["worlds"])
    tree = ast.parse(external(base, "src/life/spec.py").read_text())
    assignments = {
        n.targets[0].id: n.value for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
    }
    ledger = (
        ast.literal_eval(assignments["LEDGER_V2"])
        + ast.literal_eval(assignments["LEDGER_V3"].right)
        + ast.literal_eval(assignments["LEDGER_V4"].right)
    )
    assert_equal(ledger, A.LEDGER, "independent58-column order")
    reg, audit = read(base / "registration.json"), read(base / "seed_audit.json")
    assert_equal(reg["status"], "registered", "root registration")
    assert_equal(reg["roles"], list(LABELS), "registered roles")
    assert_equal(reg["panel_policy"], p["panel_policy"], "registered panel policy")
    assert_equal(reg["seed_audit_sha256"], sha(base / "seed_audit.json"), "registered namespace audit")
    assert_equal(audit["status"], "passed", "namespace audit status")
    assert_equal(audit["seeds"], p["seeds"], "audited ordered stage seeds")
    assert_equal(reg["seeds"], p["seeds"], "registered ordered stage seeds")
    assert_equal(set(p["seeds"]), set(N), "all stage seeds")
    allseeds = []
    for stage, count in N.items():
        values = p["seeds"][stage]
        if len(values) != count or any(type(x) is not int or not 0 <= x < 2**64 for x in values):
            raise ValueError("registered seed count or type differs")
        allseeds.extend(values)
    if len(allseeds) != len(set(allseeds)) or 11 in allseeds:
        raise ValueError("stage namespaces or numerical golden overlap")
    ab = reg["AB_terminal"]
    pins(base, ab["file_pins"], external_paths=True)
    name = "outputs/autonomous_visibility_precision_20261014/budget.json"
    if name not in ab["file_pins"]:
        raise ValueError("AB resource dependency lacks terminal budget")
    old = read(external(base, name))
    if (
        old.get("status")
        not in {"complete", "incomplete", "cpu_budget_exhausted", "job_failed", "monitor_failed", "interrupted"}
        or old.get("running")
        or old.get("queued")
        or old.get("cleanup_error")
    ):
        raise ValueError("AB resource dependency is not cleanly terminal")
    # Scientific provenance is Y; AB success is deliberately not a requirement.
    yp_path = base / "inputs/Y/protocol.json"
    assert_equal(sha(yp_path), Y_PROTOCOL, "retained Y protocol")
    yp = read(yp_path)
    assert_equal(p["worlds"]["blink"], yp["world"], "unchanged old blink world")
    assert_equal(p["production_pins"], yp["production_pins"], "unchanged production source closure")
    assert_equal(p["panel_genotype_sha256"], yp["panel_genotype_sha256"], "all original panel row identities")
    for name in ("budget.json", "analysis_result/summary.json"):
        assert_equal(read(base / "inputs/Y" / name)["status"], "complete", "completed original Y evidence")
    selection = read(base / "inputs/Y/selection.json")
    panels = {}
    for background in PARENTS:
        prefix = base / "inputs/Y/inputs" / background
        assert_equal(sha(prefix / "genomes.npy"), Y_PANEL_FILES[background], "exact retained65-row panel file")
        table = np.load(prefix / "genomes.npy", allow_pickle=False)
        if table.dtype != np.float32 or table.shape != (65, 875) or not np.isfinite(table).all():
            raise ValueError("complete original panel required")
        assert_equal(
            [raw_sha(row) for row in table], p["panel_genotype_sha256"][background], "panel genotype identities"
        )
        manifest = read(prefix / "panel_manifest.json")
        assert_equal(manifest["genomes_sha256"], raw_sha(table), "original panel manifest")
        assert_equal(manifest["mutants"], 64, "original mutant count")
        for key, name in (
            ("parent_sha256", "parent.json"),
            ("config_sha256", "config.yaml"),
            ("mutation_ops_sha256", "mutation_ops.json"),
        ):
            assert_equal(manifest[key], sha(prefix / name), "retained manifest input " + key)
        assert_equal(
            selection[background],
            {"genome_row": B_ROWS[background], "raw_sha256": raw_sha(table[B_ROWS[background]])},
            "fixed old blink winner",
        )
        panels[background] = table
    startup = read(base / "inputs/Y/startup_identity.json")["identity"]
    assert_equal(p["expected_numerical_identity"], startup, "retained startup identity")
    assert_equal(
        p["expected_startup_metadata"],
        {k: v for k, v in startup.items() if k not in {"kernels", "golden"}},
        "retained startup metadata",
    )
    assert_equal(
        p["expected_startup_metadata"]["sources"],
        {k: v for k, v in p["production_pins"].items() if k.startswith("src/")},
        "complete production closure",
    )
    assert_equal(p["numerical_identity"], yp["numerical_identity"], "retained numerical metadata")
    claim = read(base / "preparation_claim.json")
    assert_equal(
        claim,
        {
            "registration_sha256": sha(base / "registration.json"),
            "genetic_draws": 0,
            "retained_panel_rows": 130,
            "simulation_calls": 0,
            "compiled_libraries": 0,
        },
        "one copy-only preparation",
    )
    historical_costs(base, p, yp)
    return p, panels


def resources(base, p):
    ready = read(operation(base, "ready.json"))
    assert_equal(ready["status"], "released", "root release")
    assert_equal(ready["production_pins"], p["production_pins"], "released production closure")
    required = dict(p["file_pins"])
    for name in (
        "protocol.json",
        "monitor.py",
        "resource_clearance.json",
        "analysis/analyze.py",
        "analysis/offline_accounting.py",
        "analysis/panel_replay.py",
        "analysis/helpers/genetics.py",
    ):
        required[name] = sha(operation(base, name))
    if any(ready["source_pins"].get(name) != digest for name, digest in required.items()):
        raise ValueError("release fails to bind all inputs and executing helpers")
    pins(base, ready["source_pins"], operational=True)
    for local in ("analyze.py", "offline_accounting.py", "panel_replay.py", "helpers/genetics.py"):
        assert_equal(sha(HERE / local), ready["source_pins"]["analysis/" + local], "executing analysis source " + local)
    clearance = read(operation(base, "resource_clearance.json"))
    if clearance["status"] != "cleared" or clearance["all_processes_exited"] is not True:
        raise ValueError("prior resource work was not cleared")
    pins(base, clearance["budget_pins"], external_paths=True)
    for name in clearance["budget_pins"]:
        old = read(external(base, name))
        if (
            old.get("status")
            not in {"complete", "incomplete", "cpu_budget_exhausted", "job_failed", "monitor_failed", "interrupted"}
            or old.get("running")
            or old.get("queued")
            or old.get("cleanup_error")
        ):
            raise ValueError("resource dependency is not cleanly terminal")
    if not clearance.get("processes") or not clearance.get("process_groups"):
        raise ValueError("resource dependency process identities missing")
    for process in clearance["processes"]:
        if any(type(process.get(key)) is not int or process[key] <= 0 for key in ("pid", "start_ticks")):
            raise ValueError("invalid resource dependency process identity")
    attempt, budget = read(operation(base, "attempt.json")), read(operation(base, "budget.json"))
    assert_equal(attempt["ready_sha256"], sha(operation(base, "ready.json")), "single attempt release")
    for key, expected in (
        ("status", "complete"),
        ("exit_code", 0),
        ("phase", "confirmation"),
        ("cap_cpu_seconds", 7200),
        ("startup_screen_cap_cpu_seconds", 3400),
        ("startup_calibration_cap_cpu_seconds", 180),
        ("confirmation_reserve_cpu_seconds", 3800),
        ("running", {}),
        ("queued", []),
        ("completed", [{"name": "gradient", "exit_code": 0}]),
        ("ready", ready),
    ):
        assert_equal(budget[key], expected, "complete first-attempt monitor " + key)
    if budget.get("reason") is not None or budget.get("cleanup_error") or budget.get("error"):
        raise ValueError("monitor recorded a failure")
    total = number(budget["cpu_seconds"], "total CPU", 7190)
    screen = number(budget["startup_screen_cpu_seconds"], "startup/screen CPU", 3390)
    if total < screen:
        raise ValueError("CPU accounting went backwards")
    number(budget["wall_seconds"], "total wall time")
    owned_processes(attempt, budget, ["gradient"])
    if not budget["affinity"] or any(type(x) is not int or not 0 <= x < 12 for x in budget["affinity"]):
        raise ValueError("registered CPU affinity differs")
    return (
        ready,
        budget,
        {
            "total_cpu_seconds": total,
            "startup_screen_cpu_seconds": screen,
            "confirmation_cpu_seconds": total - screen,
            "first_attempt_only": True,
        },
    )


def check_startup(base, p):
    startup = read(base / "startup_identity.json")
    expected = {
        "identity": p["expected_numerical_identity"],
        "preexpected_fields": sorted(p["expected_numerical_identity"]),
        "newly_captured_fields": [],
        "numerical_identity_invocations": 1,
        "golden_lives": GOLDEN_SCOPE,
    }
    assert_equal(startup, expected, "one exact two-golden startup identity")
    assert_equal(startup["identity"]["golden"], GOLDEN, "ABI3 seed11 T200 engineering golden")
    assert_equal(set(startup["identity"]["kernels"]), {"False", "True"}, "full and fast compiled identities")
    binaries = {sha(path) for path in (base / "build-cache").rglob("*.so")}
    if not set(startup["identity"]["kernels"].values()).issubset(binaries):
        raise ValueError("full/fast compiled library bytes are missing")


def load_rows(base, p, panels):
    selection = read(base / "selection.json")
    assert_equal(set(selection), set(PARENTS), "both frozen selections")
    screens, indexes, pinmap, cpu = {}, {}, {}, dict.fromkeys(N, 0.0)
    role_rows = {}
    for background in PARENTS:
        chosen = selection[background]["genome_row"]
        if type(chosen) is not int or not 1 <= chosen <= 64:
            raise ValueError("selected row must be one of the64 original mutants")
        assert_equal(
            selection[background],
            {"genome_row": chosen, "raw_sha256": p["panel_genotype_sha256"][background][chosen]},
            "selected original row identity",
        )
        folder = base / "measurement/screen" / background
        stages = {"calibration": [0, 1], "screen": list(range(65))}
        identities = {
            (stage, i): {
                "protocol_sha256": PROTOCOL_SHA,
                "background": background,
                "world": "flash",
                "stage": stage,
                "genome_index": i,
                "genome_sha256": p["panel_genotype_sha256"][background][i],
                "seeds": p["seeds"][stage],
            }
            for stage, indices in stages.items()
            for i in indices
        }
        records, index, _ = load_store(folder, stages, identities, p["worlds"]["flash"], pinmap, base)
        screens[background] = records
        indexes["screen/" + background] = index
        for stage in stages:
            cpu[stage] += sum(float(row["cpu_seconds"]) for row in records[stage].values())
        assert_equal(chosen, selected_mutant(records["screen"]), "whole32-life selected mutant")
        role_rows.update({f"P_{background}": 0, f"B_{background}": B_ROWS[background], f"H_{background}": chosen})
    roles = read(base / "confirmation_roles.json")
    expected_roles = {
        "roles": list(LABELS),
        "panel_rows": role_rows,
        "genotype_sha256": {
            label: p["panel_genotype_sha256"][label.split("_")[1]][role_rows[label]] for label in LABELS
        },
        "selection_sha256": sha(base / "selection.json"),
        "protocol_sha256": PROTOCOL_SHA,
        "genotypes_sha256": sha(base / "confirmation_genotypes.npz"),
    }
    assert_equal(roles, expected_roles, "all six explicit frozen genotype roles")
    table = npz(base / "confirmation_genotypes.npz")
    assert_equal(set(table), {"genomes", "roles"}, "six-genotype archive schema")
    expected_table = np.stack([panels[label.split("_")[1]][role_rows[label]] for label in LABELS])
    if not A.identical(table["genomes"], expected_table) or not A.identical(table["roles"], np.asarray(LABELS)):
        raise ValueError("confirmation roles differ from the selected and fixed panel rows")
    confirmation = {}
    for world in WORLDS:
        identities = {
            ("confirm", i): {
                "protocol_sha256": PROTOCOL_SHA,
                "world": world,
                "roles": list(LABELS),
                "confirmation_roles_sha256": sha(base / "confirmation_roles.json"),
                "stage": "confirm",
                "genome_index": i,
                "genome_sha256": roles["genotype_sha256"][label],
                "seeds": p["seeds"]["confirm"],
            }
            for i, label in enumerate(LABELS)
        }
        records, index, charged = load_store(
            base / "measurement/confirm" / world,
            {"confirm": list(range(6))},
            identities,
            p["worlds"][world],
            pinmap,
            base,
        )
        confirmation[world] = records["confirm"]
        indexes["confirm/" + world] = index
        cpu["confirm"] += charged
    expected_folders = {"screen/D90", "screen/L92", "confirm/flash", "confirm/blink"}
    actual_folders = {
        str(path.parent.relative_to(base / "measurement")) for path in (base / "measurement").rglob("row_index.json")
    }
    assert_equal(actual_folders, expected_folders, "exact measurement store coverage")
    return selection, roles, screens, confirmation, indexes, cpu, pinmap


def phases(base, p, budget, indexes, selection, roles, cpu):
    assert_equal(
        set(budget["phase_receipts"]), {"calibration_complete", "screens_complete"}, "both phase acknowledgments"
    )
    receipts = {}
    previous = 0.0
    for name in ("calibration_complete", "screens_complete"):
        request_path = base / "requests" / (name + ".json")
        request = read(request_path)
        receipt = read(base / "monitor_receipts" / (name + ".json"))
        assert_equal(receipt, budget["phase_receipts"][name], "monitor phase receipt binding")
        for key, expected in (
            ("status", "allowed"),
            ("protocol_sha256", PROTOCOL_SHA),
            ("attempt_sha256", sha(operation(base, "attempt.json"))),
            ("request_sha256", sha(request_path)),
        ):
            assert_equal(receipt[key], expected, "phase receipt " + key)
        cumulative = number(receipt["cpu_seconds"], "phase CPU", 170 if name == "calibration_complete" else 3390)
        if cumulative < previous:
            raise ValueError("phase CPU went backwards")
        previous = cumulative
        snapshot, indexpins = {}, {}
        for background in PARENTS:
            names = [f"calibration/row_{i:04d}.npz" for i in (0, 1)]
            if name == "screens_complete":
                names += [f"screen/row_{i:04d}.npz" for i in range(65)]
            key = "screen/" + background
            snapshot[key] = {item: indexes[key][item] for item in names}
            indexpins[key] = hashlib.sha256(json_bytes(snapshot[key])).hexdigest()
        assert_equal(receipt["row_snapshot"], snapshot, "all acknowledged raw row snapshots")
        common = {"protocol_sha256": PROTOCOL_SHA, "row_index_sha256": indexpins}
        if name == "calibration_complete":
            artifacts = {"startup_identity.json": sha(base / "startup_identity.json")}
            expected = dict(common, validation_lives=10, startup_identity_sha256=artifacts["startup_identity.json"])
        else:
            artifacts = {
                item: sha(base / item)
                for item in (
                    "selection.json",
                    "calibration_projection.json",
                    "confirmation_projection.json",
                    "confirmation_roles.json",
                    "confirmation_genotypes.npz",
                )
            }
            expected = dict(
                common,
                scientific_genome_lives=4160,
                selection_sha256=artifacts["selection.json"],
                confirmation_roles_sha256=artifacts["confirmation_roles.json"],
                confirmation_genotypes_sha256=artifacts["confirmation_genotypes.npz"],
            )
        assert_equal(request, expected, "exact phase request")
        assert_equal(receipt["artifact_pins"], artifacts, "immutable acknowledged startup/selection artifacts")
        receipts[name] = receipt
    startup, screen = (receipts[name]["cpu_seconds"] for name in ("calibration_complete", "screens_complete"))
    assert_equal(screen, budget["startup_screen_cpu_seconds"], "monitor confirmation transition")
    if (
        cpu["calibration"] > startup + 1e-6
        or cpu["screen"] > screen - startup + 1e-6
        or cpu["confirm"] > budget["cpu_seconds"] - screen + 1e-6
    ):
        raise ValueError("raw measured CPU exceeds its monitored phase")
    historical = p["historical_blink_cpu_per_life"]
    rates = {
        b: max(indexes["screen/" + b][f"calibration/row_{i:04d}.npz"]["cpu_seconds"] for i in (0, 1)) / 2
        for b in PARENTS
    }
    initial_roles = {"flash": {label: rates[label.split("_")[1]] for label in LABELS}, "blink": {}}
    for b in PARENTS:
        initial_roles["blink"].update(
            {f"P_{b}": historical[b][0], f"B_{b}": historical[b][B_ROWS[b]], f"H_{b}": max(historical[b])}
        )
    screen_estimate = startup + 1.5 * 2080 * sum(rates.values())
    initial_confirm = 180 + 1.5 * 512 * sum(value for group in initial_roles.values() for value in group.values())
    initial = read(base / "calibration_projection.json")
    for key, expected in {
        "flash_batch_max_cpu_per_life": rates,
        "startup_cpu_seconds": startup,
        "confirmation_role_rates": initial_roles,
        "screen_projection_cpu_seconds": screen_estimate,
        "confirmation_projection_cpu_seconds": initial_confirm,
        "screen_threshold": 3390,
        "confirmation_threshold": 3790,
        "feasible": True,
    }.items():
        assert_equal(initial[key], expected, "initial fixed-scope feasibility " + key)
    if screen_estimate > 3390 or initial_confirm > 3790:
        raise ValueError("initial fixed-scope estimate did not fit")
    selected_rates = {"flash": {}, "blink": {}}
    for b in PARENTS:
        for prefix, i in (("P", 0), ("B", B_ROWS[b]), ("H", selection[b]["genome_row"])):
            label = prefix + "_" + b
            selected_rates["flash"][label] = indexes["screen/" + b][f"screen/row_{i:04d}.npz"]["cpu_seconds"] / 32
            selected_rates["blink"][label] = historical[b][i]
    selected_estimate = 180 + 1.5 * 512 * sum(value for group in selected_rates.values() for value in group.values())
    selected_projection = read(base / "confirmation_projection.json")
    for key, expected in {
        "confirmation_role_rates": selected_rates,
        "confirmation_projection_cpu_seconds": selected_estimate,
        "confirmation_threshold": 3790,
        "feasible": True,
    }.items():
        assert_equal(selected_projection[key], expected, "all-six-role frozen-selection feasibility " + key)
    if selected_estimate > 3790:
        raise ValueError("selected-role fixed-scope estimate did not fit")
    report = read(base / "report.json")
    for key, expected in (
        ("status", "complete"),
        ("scope", SCOPE),
        ("research_genome_lives", 10304),
        ("validation_lives", 10),
        ("total_genome_lives", 10314),
    ):
        assert_equal(report[key], expected, "complete worker report " + key)
    assert_equal(
        report["row_index_sha256"],
        {key: sha(base / "measurement" / key / "row_index.json") for key in indexes},
        "all four terminal row indices",
    )
    if abs(number(report["row_cpu_seconds"], "reported measured CPU") - sum(cpu.values())) > 1e-6:
        raise ValueError("raw and reported measured CPU disagree")
    assert_equal(set(report["screen"]), set(PARENTS), "both complete screens")
    assert_equal(set(report["confirmation"]), set(WORLDS), "both complete confirmations")
    for b in PARENTS:
        assert_equal(
            report["screen"][b],
            {
                "selected": selection[b],
                "complete_rows": 65,
                "row_index_sha256": report["row_index_sha256"]["screen/" + b],
            },
            "retained screen report",
        )
    for world in WORLDS:
        assert_equal(
            report["confirmation"][world],
            {"complete_roles": list(LABELS), "row_index_sha256": report["row_index_sha256"]["confirm/" + world]},
            "retained confirmation report",
        )
    return report, {"initial": initial, "selected_roles": selected_projection}


def compare_report(report, vectors, worlds):
    prefixes = {name.rsplit("__", 1)[0] for name in vectors if "__F__" not in name}
    assert_equal(set(report["contrasts"]), prefixes, "all16 fixed worker contrasts")
    for prefix in prefixes:
        metrics = {key: vectors[prefix + "__" + key] for key in A.COLS + ("bright_captures",)}
        metrics.update(
            capture_income=vectors[prefix + "__F__capture_income"],
            ordinary_cost=sum(
                vectors[prefix + "__F__" + name + "_cost_saving"] for name, _, _ in A.prices(worlds["flash"])
            ),
            guard_cost=vectors[prefix + "__F__guard_charge_saving"],
            extinction_cost=vectors[prefix + "__F__extinction_charge_saving"],
        )
        saved = report["contrasts"][prefix]
        assert_equal(set(saved), set(metrics), "all66 producer contrast metrics")
        for metric, values in metrics.items():
            check_stats(saved[metric], values, prefix + " " + metric)


def analyze(base):
    base = Path(base).resolve()
    try:
        p, panels = verify_protocol(base)
        ready, budget, resource = resources(base, p)
        check_startup(base, p)
        replay = module("AC_panel_replay", HERE / "panel_replay.py").audit(base, p, external)
        selection, roles, screens, rows, indexes, cpu, pinmap = load_rows(base, p, panels)
        report, projections = phases(base, p, budget, indexes, selection, roles, cpu)
        result, vectors = contrasts(rows, p["worlds"])
        compare_report(report, vectors, p["worlds"])
        absolute, health = {}, {}
        for world in WORLDS:
            absolute[world], health[world] = {}, {}
            for i, label in enumerate(LABELS):
                row = rows[world][i]
                absolute[world][label] = {key: A.stats(row[key]) for key in A.COLS}
                status = row["status"].astype(np.int64)
                values, counts = np.unique(status, return_counts=True)
                health[world][label] = {
                    "status_histogram": {str(k): int(v) for k, v in zip(values, counts)},
                    "all_fitness_rows_retained": 512,
                }
        for name in (
            "protocol.json",
            "ready.json",
            "attempt.json",
            "budget.json",
            "resource_clearance.json",
            "startup_identity.json",
            "selection.json",
            "confirmation_roles.json",
            "confirmation_genotypes.npz",
            "calibration_projection.json",
            "confirmation_projection.json",
            "report.json",
            "requests/calibration_complete.json",
            "requests/screens_complete.json",
            "monitor_receipts/calibration_complete.json",
            "monitor_receipts/screens_complete.json",
        ):
            pinmap[name] = sha(operation(base, name))
        return {
            "status": "complete",
            "study": p["study"],
            "protocol_sha256": PROTOCOL_SHA,
            "research_lives": 10304,
            "validation_lives": 10,
            "total_lives": 10314,
            "resources": dict(resource, raw_stage_cpu_seconds=cpu),
            "feasibility_projections": projections,
            "worlds": p["worlds"],
            "seeds": p["seeds"],
            "roles": roles,
            "panel_replay": replay,
            "primary_contrasts": p["primary_contrasts"],
            "contrasts": result,
            "absolute_means": absolute,
            "screen_F": {
                b: {str(i): A.stats(row["F"]) for i, row in records["screen"].items()} for b, records in screens.items()
            },
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
            raise SystemExit("analysis output cannot replace input study")
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "summary.json").write_bytes(json_bytes(summary))
        np.savez_compressed(args.out / "paired_vectors.npz", **vectors)
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
