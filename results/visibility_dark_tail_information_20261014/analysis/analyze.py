"""Independent AD reader; accepts only the reviewed registered protocol.

NumPy only. No controller execution, engine imports, compilation or simulations.
All scientific outcomes require complete pinned source, validation, resource and raw records.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np


def helper(name):
    spec = importlib.util.spec_from_file_location("dark_tail_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A, C = helper("accounting"), helper("candidates")
REVIEWED_PROTOCOL_SHA256 = "ee041636fec03ab3dc8e468b0d3427d75a2ac2736436b4dd954e3ac1c96100fe"
ROLES = C.ROLES
WORLDS = ["flash5_dark"]
SCOPE = dict(
    total_cpu_seconds=2400,
    validation_cpu_seconds=180,
    max_workers=1,
    threads_per_worker=2,
    research_lives=6656,
    validation_lives=76,
    worlds=WORLDS,
    roles=ROLES,
)
X2_PROTOCOL_SHA256 = "a2e3699ca131b0091473097607be054d6908c4470aadd1996ad5f2acc0a75d99"
RESEARCH_LIVES = 6656
CALIBRATION_LIVES = 39
GOLDEN_LIVES = 2
VALIDATION_LIVES = 76
VALIDATION_MATRIX = {"production_bridge": 8, "full_fast": 12, "callback_replay": 15, "calibration": 39, "identity": 2}
RESOURCE_SCOPE = {"total_cpu_seconds": 2400, "validation_cpu_seconds": 180, "total_stop": 2390, "validation_stop": 170}
LIMITATIONS = [
    "Fixed external-controller transfer measures the payoff of this retained candidate set, not evolved behavior.",
    "Retained R0/R1 reflex references were not optimized for fully dark tails; a gap against them is not a ceiling over all reflex strategies.",
    "The retained controller changes only physical-description parameter 21 from 0.25 to zero for I and B; its strategy and all other parameters remain fixed. A already has parameter 21 zero.",
    "The existing controller approximates flash visibility using an exponential hazard while the physical flash ends after a deterministic five units; the retained model is not an exact prediction oracle.",
    "A removes a broad visibility model; B suppresses actions while believed dark. Neither intervention isolates memory.",
    "Reference and do-less roles are selected by whole-sample mean; their paired uncertainty is conditional on that selection. Both fixed reference contrasts remain available.",
    "Shared seed IDs pair random streams, but actions alter trajectories and replacement events.",
    "Scratch columns 21 and 22 are dark and late captures, not production beats or P_int. Native low-light capture agreement requires the retained physical bridge.",
    "No automatic world admission, memory claim, or inference about search accessibility follows.",
    "The numerical identity subprocess is owned and counted through the validation worker's process group; the persisted monitor receipt records leaders, not a separate identity for every nested child.",
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


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


def verify_protocol(base):
    if REVIEWED_PROTOCOL_SHA256 is None:
        raise ValueError("AD protocol is unset; source-only draft cannot analyze outcomes")
    if sha(Path(base) / "protocol.json") != REVIEWED_PROTOCOL_SHA256:
        raise ValueError("protocol differs from the independently reviewed registration")
    p = read(base / "protocol.json")
    if (p["format"], p["study"], p["T"], p["n"]) != (1, "AD fully dark flash information", 1024, 512):
        raise ValueError("fixed scientific scope changed")
    if p["monitor_scope"] != SCOPE or p["validation_matrix"] != VALIDATION_MATRIX or list(p["worlds"]) != WORLDS:
        raise ValueError("world or resource call matrix changed")
    if p["abi3_sizes"] != [3, 875, 129, 66, 57, 5, 23, 1024, 7, 18]:
        raise ValueError("scratch ABI changed")
    if p["raw_ledger_aliases"] != {"21": "dark_captures", "22": "late_captures"}:
        raise ValueError("scratch ledger aliases changed")
    if p["candidate_policy"] != "retained_X2_flash_controllers_with_physical_amplitude_only":
        raise ValueError("candidate transfer policy differs")
    if p["simulation_calls_completed"] != 0 or p["compiled_libraries"] != 0:
        raise ValueError("protocol was not prepared before measurement")
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
        raise ValueError("production module closure is not pinned")
    reg = read(base / "registration.json")
    audit = read(base / "seed_audit.json")
    stages = {"validation": p["validation_seeds"], "research": p["seeds"]}
    if (
        reg["status"] != "registered"
        or reg["roles"] != ROLES
        or reg["candidate_policy"] != p["candidate_policy"]
        or reg["seeds"] != stages
        or reg["seed_audit_sha256"] != sha(base / "seed_audit.json")
        or audit["status"] != "passed"
        or audit["seeds"] != stages
    ):
        raise ValueError("exact reviewed seed registration differs")
    for name, count in (("validation", 3), ("research", 512)):
        values = stages[name]
        if (
            len(values) != count
            or len(set(values)) != count
            or any(type(x) is not int or not 0 <= x < 2**64 for x in values)
        ):
            raise ValueError("invalid stage seed IDs")
    if set(stages["validation"]) & set(stages["research"]) or 11 in stages["validation"] + stages["research"]:
        raise ValueError("scientific seed scopes overlap")
    pins(base, reg["AC_terminal"]["file_pins"], True)
    acname = "outputs/autonomous_visibility_flash_gradient_20261014/budget.json"
    if acname not in reg["AC_terminal"]["file_pins"]:
        raise ValueError("terminal AC resource receipt is not pinned")
    ac = read(external(base, acname))
    if (
        ac.get("status")
        not in ("complete", "incomplete", "cpu_budget_exhausted", "job_failed", "interrupted", "monitor_failed")
        or ac.get("running")
        or ac.get("queued")
        or ac.get("cleanup_error")
    ):
        raise ValueError("AC resource dependency is not clean terminal")
    oldpath = base / "inputs/X2/protocol.json"
    if sha(oldpath) != X2_PROTOCOL_SHA256 or p["X2_protocol_sha256"] != X2_PROTOCOL_SHA256:
        raise ValueError("historical X2 registration differs")
    xp = read(oldpath)
    if any(read(base / "inputs/X2" / name).get("status") != "complete" for name in ("budget.json", "summary.json")):
        raise ValueError("historical X2 measurement is incomplete")
    if p["analysis"] != xp["analysis"] or p["numerical_identity"] != xp["numerical_identity"]:
        raise ValueError("analysis policy or numerical environment changed")
    recovered = read(base / "inputs/recovered_inputs.json")
    C.verify(base, xp, recovered)
    tuned = C.literals((base / "original/src/life/handbuilt.py").read_text(), "SPECK_TUNED")
    candidate_review = verify_candidate_transfer(
        p["worlds"][WORLDS[0]]["candidates"], recovered["worlds"]["flash5_dim25"], tuned
    )
    old = xp["worlds"]["flash5_dim25"]
    expected = copy.deepcopy(old)
    expected["scratch_slots"]["dark_amp"] = 0.0
    expected["packed_world"][16] = 0.0
    expected["production"]["world"]["visibility_low"] = 0.0
    expected["production"]["packed_world"][69] = 0.0
    expected["candidates"] = p["worlds"][WORLDS[0]]["candidates"]
    if old["scratch_slots"]["dark_amp"] != 0.25 or old["packed_world"][16] != 0.25:
        raise ValueError("historical flash amplitude differs")
    if old["production"]["packed_world"][69] != 0.25 or p["worlds"][WORLDS[0]] != expected:
        raise ValueError("world change exceeds the approved residual-amplitude coordinate")
    if p["production_binding"]["status"] != "complete" or p["production_binding"]["physical_delta"] != {
        "visibility_low": [0.25, 0.0]
    }:
        raise ValueError("production world binding differs")
    snapshot = read(base / "inputs/production_snapshot.json")
    if snapshot["original_world"] != old["production"]["world"] or snapshot["module_pins"] != modules:
        raise ValueError("production snapshot source binding differs")
    if {k: snapshot[k] for k in ("preset", "world", "packed_world", "sizes")} != expected["production"]:
        raise ValueError("production snapshot physics differs")
    transfer = {}
    for role in ("I", "B"):
        before = next(c for c in old["candidates"] if c["role"] == role)["params"]
        after = next(c for c in expected["candidates"] if c["role"] == role)["params"]
        transfer[role] = dict(
            original_parameters=before,
            parameters=after,
            changed_parameter_indices=[21],
            reason="match the declared target dark-rate multiplier",
        )
    if p["candidate_transfer"] != transfer or read(base / "inputs/candidate_transfer.json") != transfer:
        raise ValueError("parameter transfer receipt differs")
    startup = read(base / "inputs/Y/startup_identity.json")["identity"]
    yp = read(base / "inputs/Y/protocol.json")
    if sha(base / "inputs/Y/protocol.json") != "1880ff6e21b4689031e892d9dc6765a8d9673a35efeefb213acf268f5370adf4":
        raise ValueError("historical Y numerical registration differs")
    if (
        startup != p["expected_numerical_identity"]
        or {k: v for k, v in startup.items() if k not in ("kernels", "golden")} != yp["expected_startup_metadata"]
    ):
        raise ValueError("expected complete numerical identity differs")
    rates = historical_rates(base, xp)
    if rates != p["historical_cpu_per_life"]:
        raise ValueError("historical role cost floor differs")
    timing = read(base / "inputs/timing.json")
    if timing != dict(
        cpu_per_life=rates,
        lives_per_role=512,
        source_protocol_sha256=X2_PROTOCOL_SHA256,
        total_cpu_seconds=sum(rates.values()) * 512,
    ):
        raise ValueError("historical timing receipt differs")
    return p, candidate_review


def historical_rates(base, xp):
    directory = base / "inputs/X2/rows/flash5_dim25"
    marker = read(directory / "complete.json")
    if (marker["status"], marker["world"], marker["roles"], marker["simulation_calls"], marker["protocol_sha256"]) != (
        "complete",
        "flash5_dim25",
        ROLES,
        6656,
        X2_PROTOCOL_SHA256,
    ):
        raise ValueError("historical complete-world receipt differs")
    if set(marker["checkpoint_pins"]) != {role + "/checkpoint.json" for role in ROLES}:
        raise ValueError("historical role coverage differs")
    pins(directory, marker["checkpoint_pins"])
    rates = {}
    for candidate in xp["worlds"]["flash5_dim25"]["candidates"]:
        role = candidate["role"]
        d = directory / role
        expected = dict(
            protocol_sha256=X2_PROTOCOL_SHA256, world="flash5_dim25", candidate=candidate, seeds=xp["seeds"]
        )
        if read(d / "checkpoint.json") != {"identity": expected, "row_sha256": sha(d / "row.npz")}:
            raise ValueError("historical row binding differs")
        row = npz(d / "row.npz")
        if row["identity"].shape != () or str(row["identity"]) != canonical(expected):
            raise ValueError("historical row identity differs")
        array(row, "ledger", (512, 57))
        cpu = number(float(array(row, "cpu_seconds", ())), "historical CPU")
        number(float(array(row, "wall_seconds", ())), "historical wall")
        if cpu <= 0:
            raise ValueError("historical CPU must be positive")
        rates[role] = cpu / 512
    return rates


def verify_candidate_transfer(candidates, recovered_flash, tuned):
    """Rebuild old candidates with only the approved I/B world-description change."""
    if C.digest(np.asarray(recovered_flash["full_parameters"], dtype="<f8").tobytes()) != C.PARAM_SHA["flash5_dim25"]:
        raise ValueError("transferred full controller parameters changed")
    descriptions = C.descriptions(recovered_flash)
    parameter_changes = {}
    for descriptor in descriptions:
        if descriptor["role"] == "A":
            # This metadata is relative to the transferred I, whose parameter21 is now zero.
            # A's actual parameter vector was already zero here and remains byte-identical.
            descriptor["changed_parameter_indices"] = [9, 10]
        if descriptor["role"] in ("I", "B"):
            original = np.asarray(descriptor["params"], dtype="<f8")
            corrected = original.copy()
            corrected[21] = 0.0
            if np.flatnonzero(original != corrected).tolist() != [21] or original[21] != 0.25:
                raise ValueError("expected single-coordinate physical-description update differs")
            descriptor["params"] = corrected.tolist()
            parameter_changes[descriptor["role"]] = {
                "original_sha256": C.digest(original.tobytes()),
                "new_sha256": C.digest(corrected.tobytes()),
                "changed_indices": [21],
                "original_value": 0.25,
                "new_value": 0.0,
            }
    expected = [C.reconstruct(d, tuned) for d in descriptions]
    if candidates != expected:
        raise ValueError("X2 candidate transfer exceeds approved physical-description change")
    return {
        "candidate_count": 13,
        "full_parameter_bytes_sha256": C.PARAM_SHA["flash5_dim25"],
        "independent_arrays_reconstructed": True,
        "physical_description_changes": parameter_changes,
        "strategy_retuned": False,
    }


def static_body(ledger, candidate, world):
    """Correct X2 census: initial cells are present but excluded from births."""
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


def scientific_summary(raw, world, n=512):
    """Retain corrected X2 information/reference, broad ablation and do-less contrasts."""
    if set(raw) != set(ROLES):
        raise ValueError("complete fixed 13-role matrix required")
    # Validate every role before returning any score or contrast.
    accounted = {role: A.reconcile(raw[role], world, n) for role in ROLES}
    f = {role: raw[role][:, A.L["F"]] for role in ROLES}
    reference = max(("R0", "R1"), key=lambda role: float(f[role].mean()))
    do_less = max(ROLES[5:], key=lambda role: float(f[role].mean()))
    contrasts, vectors = {}, {}
    pairs = [("I", "R0"), ("I", "R1"), ("I", "A"), ("I", "B"), *[(r, reference) for r in ROLES[5:]]]
    for left, right in pairs:
        label = left + "_minus_" + right
        summary, values = A.paired_contrast(raw[left], raw[right], world)
        contrasts[label] = summary
        vectors.update({label + "__" + key: value for key, value in values.items()})
    gap = f["I"] - f[reference]
    gapstats = A.mean_se(gap)
    margins = {}
    for role in ROLES[5:]:
        gain = f[role] - f[reference]
        margin = 0.25 * gap - gain
        margins[role] = {
            "quarter_gap_minus_gain": A.mean_se(margin),
            "fraction_of_information_gap": A.ratio_of_paired_means(gain, gap),
        }
        vectors["quarter_margin__" + role] = margin
    means = {}
    for role in ROLES:
        x, acc = raw[role], accounted[role]
        means[role] = {
            "raw_columns": {name: A.mean_se(x[:, i]) for i, name in enumerate(A.RAW_LEDGER)},
            "low_light_captures": A.mean_se(acc["low_light_captures"]),
            "bright_captures": A.mean_se(acc["bright_captures"]),
            "costs": {key: A.mean_se(value) for key, value in acc["parts"].items()},
            "low_light_share_of_captures": A.ratio_of_paired_means(acc["low_light_captures"], x[:, A.L["captures"]]),
        }
    best_gain = float((f[do_less] - f[reference]).mean())
    summary = {
        "rows": means,
        "reference_role": reference,
        "do_less_role": do_less,
        "reference_selection": "largest whole mean; ties retain first registered role",
        "contrasts": contrasts,
        "information_gap": gapstats,
        "do_less_quarter_margins": margins,
        "information_payoff_criterion": gapstats["mean"] >= 1.0 and gapstats["mean"] > 3 * gapstats["se"],
        "do_less_quarter_criterion": gapstats["mean"] > 0 and best_gain < 0.25 * gapstats["mean"],
        "capability_specific_admission": "incomplete",
        "gradient": "not measured by this study",
    }
    return summary, vectors


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
    for name in ("analyze.py", "accounting.py", "candidates.py"):
        if ready["source_pins"].get("analysis/" + name) != sha(Path(__file__).with_name(name)):
            raise ValueError("executing analysis helper is not the released file: " + name)
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
        ("cap_cpu_seconds", 2400),
        ("validation_cap_cpu_seconds", 180),
        ("ready", ready),
    ]:
        if key not in budget or budget[key] != want:
            raise ValueError("monitor is not successfully complete: " + key)
    if budget.get("cleanup_error") or budget.get("error"):
        raise ValueError("monitor cleanup or execution failed")
    names = [item["name"] for item in budget["completed"]]
    if (
        len(names) != 2
        or names[0] != "validation"
        or set(names) != set(["validation", *WORLDS])
        or any(x["exit_code"] != 0 for x in budget["completed"])
    ):
        raise ValueError("missing, failed or repeated monitored worker")
    identities = budget["process_identities"]
    if len(identities) != 3 or {x["name"] for x in identities} != {"monitor", "validation", *WORLDS}:
        raise ValueError("incomplete first-attempt process receipt")
    if len({x["pid"] for x in identities}) != 3:
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
    total = number(budget["cpu_seconds"], "total CPU", 2390)
    vcpu = number(budget["validation_cpu_seconds"], "validation CPU", 170)
    if total < vcpu:
        raise ValueError("total CPU smaller than validation CPU")
    number(budget["wall_seconds"], "monitor wall time")
    vb = read(operation(base, "validation_budget.json"))
    if vb != {
        "status": "complete",
        "cpu_seconds": budget["validation_cpu_seconds"],
        "cap_cpu_seconds": 180,
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


def calibration_projection(calibration, historical):
    if set(calibration) != set(ROLES) or set(historical) != set(ROLES):
        raise ValueError("cost projection requires all thirteen fixed roles")
    rates = {}
    for role in ROLES:
        batch, floor = number(calibration[role], "calibration CPU"), number(historical[role], "historical CPU per life")
        if batch <= 0 or floor <= 0:
            raise ValueError("positive role CPU required")
        rates[role] = max(batch / 3, floor)
    total = 180 + 1.5 * 512 * sum(rates.values())
    return dict(
        cpu_per_life=rates,
        validation_allowance_cpu_seconds=180,
        multiplier=1.5,
        projected_total_cpu_seconds=total,
        threshold_cpu_seconds=2390,
        feasible=total <= 2390,
        interpretation="cost feasibility estimate; the monitor enforces the hard cap",
    )


def verify_startup(base, p, report, receipt):
    path = base / "validation/startup_identity.json"
    entry = dict(
        path="validation/startup_identity.json",
        sha256=sha(path),
        simulation_calls=2,
        T=200,
        seeds=[11, 11],
        library="isolated_production_full_and_fast",
    )
    if report["identity"] != entry or report["artifacts"]["startup_identity"] != entry:
        raise ValueError("isolated production identity artifact differs")
    expected = dict(
        status="complete",
        identity=p["expected_numerical_identity"],
        protocol_sha256=sha(base / "protocol.json"),
        preexpected_fields=sorted(p["expected_numerical_identity"]),
        newly_captured_fields=[],
        numerical_identity_invocations=1,
        simulation_calls=2,
        abi=3,
        seeds=[11, 11],
        T=200,
    )
    if set(receipt) != set(expected) | {"cpu_seconds", "wall_seconds"} or any(
        receipt[k] != v for k, v in expected.items()
    ):
        raise ValueError("one complete preexpected standard identity pair required")
    cpu = number(receipt["cpu_seconds"], "identity process CPU")
    number(receipt["wall_seconds"], "identity wall time")
    kernels = receipt["identity"]["kernels"]
    if set(kernels) != {"False", "True"}:
        raise ValueError("full and fast numerical libraries required")
    found = {sha(path) for path in (base / "build-cache").rglob("*.so")}
    if not set(kernels.values()).issubset(found):
        raise ValueError("exact standard identity library bytes not retained")
    for name, digest in receipt["identity"]["sources"].items():
        if p["production_pins"].get(name) != digest:
            raise ValueError("numerical identity source closure differs")
    return cpu


def verify_validation(base, p):
    report = read(base / "validation/report.json")
    if (
        report.get("status") != "complete"
        or report.get("simulation_calls") != 76
        or report["protocol_sha256"] != sha(base / "protocol.json")
        or report["source_pins"] != p["file_pins"]
        or report["production_pins"] != p["production_pins"]
        or report.get("no_retuning") is not True
        or report.get("no_research_outcomes") is not True
        or report.get("validation_matrix") != VALIDATION_MATRIX
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
        loaded[label] = read(path) if label == "startup_identity" else npz(path)
    identity_cpu = verify_startup(base, p, report, loaded["startup_identity"])
    validation_seeds = p["validation_seeds"][:2]
    expected = {}
    checks = []
    for world in WORLDS:
        for role in ("R0", "R1"):
            for i, seed in enumerate(validation_seeds):
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
                expected[case + "_" + kind] = (2, 128, validation_seeds, kind)
            full, fast = loaded[case + "_full"], loaded[case + "_fast"]
            if any(not A.identical(full[k], fast[k]) for k in ("ledger", "diag", "latency")):
                raise ValueError("raw full/fast parity differs")
            checks.append(("full_fast", case))
            for tag, seed in [
                ("record", validation_seeds[0]),
                ("same_life", validation_seeds[0]),
                ("other_life", validation_seeds[1]),
                ("other_world", validation_seeds[1]),
                ("control", validation_seeds[1]),
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
        for role in ROLES:
            expected[world + "_" + role + "_calibration"] = (3, 1024, p["validation_seeds"], "fast")
    extra_logs = {f"{world}_{role}_replay_logs" for world in WORLDS for role in ("I", "A", "B")}
    if (
        set(artifacts) != set(expected) | extra_logs | {"startup_identity"}
        or sum(x["simulation_calls"] for x in artifacts.values()) != 76
    ):
        raise ValueError("validation life count or artifact set differs")
    raw_cpu = identity_cpu
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
    if len(got) != 10 or set(got) != set(checks) or any(x.get("passed") is not True for x in report["checks"]):
        raise ValueError("validation checks incomplete")
    calibrated = {role: float(loaded[WORLDS[0] + "_" + role + "_calibration"]["cpu_seconds"]) for role in ROLES}
    if report["calibration_cpu_seconds"] != calibrated:
        raise ValueError("calibration role CPU differs from raw rows")
    projection = calibration_projection(calibrated, p["historical_cpu_per_life"])
    if (
        report["calibration_projection"] != projection
        or not projection["feasible"]
        or read(base / "validation/calibration_projection.json") != projection
    ):
        raise ValueError("all-role fixed cost feasibility gate differs")
    return dict(
        simulation_calls=76,
        independently_rechecked_cases=10,
        raw_row_cpu_seconds=raw_cpu,
        scratch_raw_ledger_columns=57,
        production_raw_ledger_columns=58,
        calibration_projection=projection,
        numerical_identity_invocations=1,
        standard_golden_lives=2,
    )


def load_rows(base, p):
    rows = {}
    cpu = 0.0
    rawpins = {}
    for world in WORLDS:
        directory = base / "rows" / world
        if {path.name for path in directory.iterdir()} != {*ROLES, "complete.json"}:
            raise ValueError("research world has missing, partial or extra candidate artifacts")
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
            expected = dict(
                protocol_sha256=sha(base / "protocol.json"), world=world, candidate=candidate, seeds=p["seeds"]
            )
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
            raise ValueError("raw timing exceeds monitored stage CPU")
        world = WORLDS[0]
        outcome, values = scientific_summary(rows[world], p["worlds"][world]["base_world"])
        vectors = {world + "__" + key: value for key, value in values.items()}
        summary = dict(
            status="complete",
            study=p["study"],
            protocol_sha256=sha(base / "protocol.json"),
            simulation_calls=6732,
            research_lives=6656,
            validation=validation,
            resources=dict(resource, raw_research_row_cpu_seconds=cpu),
            candidates=candidates,
            ledger_aliases=A.ALIASES,
            seed_ids=p["seeds"],
            worlds={world: outcome},
            limitations=LIMITATIONS,
            input_pins=rawpins,
        )
        for name in ("ready.json", "attempt.json", "budget.json", "validation_budget.json", "resource_clearance.json"):
            summary["input_pins"][name] = sha(operation(base, name))
        summary["input_pins"]["validation/report.json"] = sha(base / "validation/report.json")
        return summary, vectors
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration, OverflowError) as error:
        return {"status": "incomplete", "scientific_outcomes_emitted": False, "error": str(error)}, {}


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
