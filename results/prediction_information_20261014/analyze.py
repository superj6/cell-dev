"""Independent, offline V audit: NumPy accounting and source-text reconstruction; never simulate."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np

ROOT = next((p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists()), None)
PROTOCOL_SHA256 = "bc2df79bfd484107ce50027ec6b734c041a00efa982654a64ddc7e065910d99f"
NAMES = ("frozen", "retuned", "smaller_frozen", "smaller_tuned", "quieter", "full", "ablated")
LEDGER = (
    "income", "live_time", "sec_int", "spikes", "kappa_sum", "contact_events", "claims", "births", "rejects",
    "rejects_wall", "deaths", "kills", "cost", "guard_charge", "net", "F", "n_end", "n_peak", "t_end", "status",
    "events", "beats", "P_int", "arrivals", "arrivals_dropped", "packets", "morph_secreted", "morph_decayed",
    "morph_lost", "morph_content_end", "morph_inflight_end", "chem_clamps", "last_birth", "ticks", "t_ext",
    "captures", "misses", "clicks", "b2_clicks", "respawns", "nudges", "rec_cand", "rec_accept", "rec_events",
    "rec_gain", "samples", "dist_sum", "zone_samples", "path", "X_end", "Y_end", "n_S_end", "n_M_end", "n_H_end",
    "live_S", "live_M", "live_H")
L = {name: i for i, name in enumerate(LEDGER)}
HASH_INIT = 0x243F6A8885A308D3
COSTS = (("c_live", "live_time"), ("c_spike", "spikes"), ("c_tw", "kappa_sum"),
         ("c_msg", "contact_events"), ("c_div", "claims"), ("c_sec", "sec_int"),
         ("c_miss", "misses"), ("c_rec", "rec_gain"))
LIMITATIONS = [
    "The unchanged recovered controller is an external measuring tool, never an organism policy.",
    "Parameters3/4 remove the broad moving-target model: tracking, observation propagation and anticipatory actions. "
    "This does not isolate action lookahead; prediction-specific admission stays incomplete.",
    "Controller parameters were transferred from ring4 to hollow3 without fresh tuning; a failure does not "
    "establish that the information is useless.",
    "The better whole reflex and best do-less candidate are chosen on these outcomes. Their paired SEs are "
    "conditional and descriptive, without selection adjustment; both fixed-reflex comparisons are reported.",
    "Only three fixed do-less candidates were measured, not an exhaustive optimum.",
    "All cells, receptor pings, virtual relay spikes and actions pay; central controller computation is free.",
    "This study uses old conduction d0=1, d_min=0.5 and T1024; it supplies no duration-transfer evidence.",
    "Existing replay/parity evidence covers bounded T64 lives, not universal long-duration parity.",
    "Fast event hashes retain HASH_INIT (0x243f6a8885a308d3) and are not replay evidence; file hashes protect "
    "stored bytes.",
    "A passing descriptive measurement never automatically admits the world into selection.",
    "This pilot permits only its first attempt; failure means incomplete, with no resume or rescue allocation. "
    "A future resume would need repaired, reviewed exception-attempt accounting.",
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


def source(base, relative):
    archived = base / "original" / relative
    if archived.is_file():
        return archived
    if ROOT is None:
        raise ValueError("missing archived source: " + relative)
    return ROOT / relative


def operation(base, name):
    archived = base / "operations" / name
    return archived if archived.is_file() else base / name


def stats(values):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("statistics require finite one-dimensional paired values")
    return {"mean": float(values.mean()), "se": float(values.std(ddof=1) / np.sqrt(len(values))), "n": len(values)}


def check_stats(actual, expected, label):
    equal(actual["n"], expected["n"], label + " sample count")
    for key in ("mean", "se"):
        if not np.isclose(actual[key], expected[key], rtol=1e-12, atol=1e-12):
            raise ValueError(label + " paired statistics differ")


def costs(ledger, world):
    # Independently mirror the documented left-to-right ABI3 accounting; no spec or runner import.
    value = world[COSTS[0][0]] * ledger[:, L[COSTS[0][1]]]
    for price, column in COSTS[1:]:
        value = value + world[price] * ledger[:, L[column]]
    return value + max(0.0, -world["b2_value"]) * ledger[:, L["b2_clicks"]]


def validate_ledger(ledger, world, n=512):
    if ledger.dtype != np.float64 or ledger.shape != (n, len(LEDGER)) or not np.isfinite(ledger).all():
        raise ValueError("invalid complete full ledger")
    status = ledger[:, L["status"]]
    if np.any(status != status.astype(np.int64)) or np.any(status < 0):
        raise ValueError("invalid status encoding")
    if np.any(status.astype(np.int64) & (2 | 4 | 64 | 128)):
        raise ValueError("guarded or invalid life leaves the entire study incomplete")
    alive = (status.astype(np.int64) & 1) == 0
    if np.any(alive & (ledger[:, L["t_end"]] != world["t0"] + world["T"])):
        raise ValueError("unexplained incomplete life")
    charge = costs(ledger, world)
    income = world["R_cap"] * ledger[:, L["captures"]]
    if not np.array_equal(income, ledger[:, L["income"]]):
        raise ValueError("capture income differs from the raw ledger")
    if not np.allclose(charge, ledger[:, L["cost"]], rtol=1e-9, atol=1e-9):
        raise ValueError("rebuilt total cost differs from the raw ledger")
    if np.any(ledger[:, L["guard_charge"]] != 0):
        raise ValueError("nonzero guard charge in a valid candidate")
    if not np.allclose(ledger[:, L["net"]], income - charge, rtol=1e-10, atol=1e-9):
        raise ValueError("raw net income/cost differs")
    fitness = (income - charge) / (world["T"] - world["t_open"])
    if not identical(fitness, ledger[:, L["F"]]):
        raise ValueError("independently rebuilt fitness differs from the raw ledger bytes")
    return charge


def generated_source_check(base):
    """Recreate C source text from the pinned patch function; never import/run a compiler or simulator."""
    path = source(base, "results/open_headroom/harness/make_ckernel.py")
    tree = ast.parse(path.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "patched_source")
    isolated = ast.Module(body=[function], type_ignores=[])
    env = {"os": os, "HERE": "/CELLDEV/results/open_headroom/harness",
           "SRC": str(source(base, "src/life/kernel.c"))}
    exec(compile(isolated, str(path), "exec"), env)
    code = env["patched_source"](["/CELLDEV/results/taskvar/measurement/prediction_ctl.c"])
    old = "  c->e_on = w[W_TAUR]; c->e_off = w[W_TAUE];"
    equal(code.count(old), 1, "epoch-alias patch target")
    code = code.replace(old, "  c->e_on = 0.0; c->e_off = 0.0; // E7 uses ABI 3 blob physics")
    actual = operation(base, "measurement.c").read_text()
    actual = re.sub(r'#include "[^"\n]*/(results/(?:open_headroom/harness|taskvar/measurement)/[^"\n]+)"',
                    r'#include "/CELLDEV/\1"', actual)
    equal(actual, code, "generated measurement source reconstructed from pinned sources")


def audit_inputs(base):
    equal(sha(base / "protocol.json"), PROTOCOL_SHA256, "independently reviewed fixed V protocol")
    protocol = read(base / "protocol.json")
    equal(protocol["seeds"], list(range(52_080_000, 52_080_512)), "shared ordered block108 seeds")
    equal([row["name"] for row in protocol["candidates"]], list(NAMES), "candidate order")
    equal((protocol["candidate_lives"], protocol["threads"], protocol["max_cpu_seconds"]),
          (3584, 2, 3600), "registered dimensions")
    if set(protocol["seeds"]) & set(protocol["tuning_seeds"]):
        raise ValueError("scoring and tuning seeds overlap")
    pins = {**protocol["source_pins"], **protocol["harness_identity"]}
    for relative, digest in pins.items():
        equal(sha(source(base, relative)), digest, "pinned source/input " + relative)
    spec_tree = ast.parse(source(base, "src/life/spec.py").read_text())
    assigned = {node.targets[0].id: node.value for node in spec_tree.body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    ledger_v2 = ast.literal_eval(assigned["LEDGER_V2"])
    equal(ledger_v2 + ast.literal_eval(assigned["LEDGER_V3"].right), LEDGER, "documented ledger column order")
    equal(ast.literal_eval(assigned["HASH_INIT"]), HASH_INIT, "documented fast hash initializer")
    config = read(source(base, "results/taskvar/measurement/prediction.json"))
    audit = read(source(base, "results/taskvar/validation/prediction_audit.json"))
    expected_candidates = [
        {"name": "frozen", "kind": "frozen_reflex", "footprint": "hollow3", "knobs": None},
        {"name": "retuned", "kind": "retuned_reflex", "footprint": "hollow3", "knobs": config["reflex_knobs"]},
        {"name": "smaller_frozen", "kind": "do_less", "footprint": "hollow2", "knobs": None},
        {"name": "smaller_tuned", "kind": "do_less", "footprint": "hollow2", "knobs": config["smaller_reflex_knobs"]},
        {"name": "quieter", "kind": "do_less", "footprint": "hollow3",
         "knobs": dict(config["reflex_knobs"], **{"K.t_ref": 8.0})}]
    equal(config["ablate"], {"3": 0, "4": 0}, "registered broad-model parameter mask")
    no_motion = list(config["params"])
    no_motion[3] = no_motion[4] = 0
    for name, kind, params in (("full", "information", config["params"]), ("ablated", "ablation", no_motion)):
        expected_candidates.append({"name": name, "kind": kind, "footprint": "hollow3", "params": params,
            "controller_id": 1201, "action": {"latency": "d0", "charge": "relay", "t_ref_min": .5,
                "privileged": False, "quant": False, "fast": True}})
    equal(protocol["candidates"], expected_candidates, "all seven unchanged candidates independently reconstructed")
    equal(audit["harness_identity"], protocol["harness_identity"], "bounded audit harness")
    equal(audit["config_sha256"], protocol["config_sha256"], "bounded audit config")
    equal(audit["source_sha256"], protocol["controller_sha256"], "bounded audit controller")
    equal(audit["passed"] and audit["world_parity_audit"]["passed"], True, "bounded audit success")
    equal((audit["T"], len(audit["rows"])), (64, 4), "bounded audit scope")
    replay_count = 0
    for variant in ("full", "ablated"):
        for i in range(2):
            relative = str(Path(audit["artifact"]).parent / f"{variant}_{i}_replay.npz")
            with np.load(source(base, relative), allow_pickle=False) as values:
                for key in ("same_life", "other_life", "other_world"):
                    if not identical(values["actions"], values[key]):
                        raise ValueError("bounded callback replay action bytes differ")
                    replay_count += 1
                if identical(values["actions"], values["control"]):
                    raise ValueError("bounded closed-loop control failed to differ")
    world = protocol["world"]
    for key, value in dict(T=1024, t0=0, t_open=0, t_fork=0, fork_flags=0, d0=1, d_min=0.5, v_t=.3, tau_turn=200,
                           b2_amp=0, kill_rate=0, wound_rate=0, drift_tau=0).items():
        equal(world[key], value, "world " + key)
    full, ablated = protocol["candidates"][-2:]
    equal(full["params"], config["params"], "recovered full controller parameters")
    expected_ablation = list(config["params"])
    expected_ablation[3] = expected_ablation[4] = 0
    equal(config["ablation_isolates_capability"], False, "broad ablation interpretation")
    equal(protocol["candidates"][3]["knobs"], config["smaller_reflex_knobs"], "independently recovered smaller knobs")
    equal(ablated["params"], expected_ablation, "recovered broad ablation")
    action = dict(latency="d0", charge="relay", t_ref_min=0.5, privileged=False, quant=False, fast=True)
    for candidate in (full, ablated):
        equal(candidate["action"], action, "controller action rule")
        equal(candidate["footprint"], "hollow3", "controller footprint")
    ready = read(operation(base, "ready.json"))
    for name, digest in ready.items():
        path = base / name if name == "protocol.json" else operation(base, name)
        equal(sha(path), digest, "released file " + name)
    equal(set(ready), {"protocol.json", "measure.py", "run_budgeted.py", "resource_clearance.json"}, "release pin names")
    clearance = read(operation(base, "resource_clearance.json"))
    equal(clearance["all_processes_exited"], True, "U resource clearance")
    equal(clearance["dependency_budget"], "outputs/autonomous_decoy_evolution_20261014/budget.json", "U resource dependency")
    equal(sha(source(base, clearance["dependency_budget"])), clearance["dependency_budget_sha256"], "U terminal budget")
    if not clearance["processes"] or not clearance["process_groups"]:
        raise ValueError("U clearance lacks exact exited identities/groups")
    calibration = read(operation(base, "calibration_budget.json"))
    equal(calibration["status"], "complete", "fixed calibration completed")
    equal(sha(operation(base, "calibration_budget.json")), protocol["calibration_budget_sha256"], "fixed calibration receipt")
    equal(calibration["cpu_seconds"], protocol["calibration_cpu_seconds"], "calibration CPU carried forward")
    if not 0 < calibration["cpu_seconds"] <= 30:
        raise ValueError("calibration exceeded its fixed allocation")
    library = read(operation(base, "library.json"))
    equal(set(library), {"measurement.so", "measurement.c"}, "library receipt names")
    for name, digest in library.items():
        equal(sha(operation(base, name)), digest, "compiled measurement artifact " + name)
    generated_source_check(base)
    manifest = read(operation(base, "manifest.json"))
    equal(manifest, {"protocol_sha256": sha(base / "protocol.json"), "ready": ready, "library": library},
          "candidate manifest")
    return protocol, manifest, {"source_input_pins": len(pins), "bounded_replay_comparisons": replay_count,
                                "generated_source_reconstruction": True, "simulation_executed": False}


def load_rows(base, protocol, manifest):
    rows = {}
    equal({p.name for p in (base / "rows").iterdir()}, set(NAMES), "exact completed candidate directories")
    for candidate in protocol["candidates"]:
        name = candidate["name"]
        directory = base / "rows" / name
        identity = {"manifest": manifest, "candidate": candidate, "seeds": protocol["seeds"]}
        equal(read(directory / "checkpoint.json"),
              {"identity": identity, "row_sha256": sha(directory / "row.npz")}, name + " checkpoint")
        with np.load(directory / "row.npz", allow_pickle=False) as saved:
            arrays = {key: saved[key].copy() for key in saved.files}
        equal(json.loads(str(arrays["identity"].item())), identity, name + " NPZ identity")
        validate_ledger(arrays["ledger"], protocol["world"])
        hashes = arrays["hashes"]
        if hashes.shape != (512, 5) or hashes.dtype != np.uint64 or np.any(hashes != HASH_INIT):
            raise ValueError("fast hashes have an unexpected shape, type or initialized value")
        controller = name in ("full", "ablated")
        if arrays["diag"].shape != (512, 16 if controller else 0) or not np.isfinite(arrays["diag"]).all():
            raise ValueError("invalid saved controller diagnostics")
        latency = arrays["latency"]
        if controller and (latency.shape != (512,) or not np.all(latency == protocol["world"]["d0"])):
            raise ValueError("saved controller latency differs")
        if not controller and latency.size:
            raise ValueError("unexpected tissue latency vector")
        for key in ("cpu_seconds", "wall_seconds"):
            if not np.isfinite(float(arrays[key])) or float(arrays[key]) < 0:
                raise ValueError("invalid saved candidate timing")
        rows[name] = arrays
    return rows


def contrast(left, right, world):
    a, b = left["ledger"], right["ledger"]
    result = {key: stats(a[:, L[key]] - b[:, L[key]]) for key in
              ("F", "captures", "clicks", "b2_clicks", "misses", "spikes", "path", "zone_samples", "samples")}
    window = world["T"] - world["t_open"]
    pieces = {"capture_income": world["R_cap"] * (a[:, L["captures"]] - b[:, L["captures"]]) / window,
              "poison_cost_saving": max(0, -world["b2_value"]) * (b[:, L["b2_clicks"]] - a[:, L["b2_clicks"]])
              / window,
              "miss_cost_saving": world["c_miss"] * (b[:, L["misses"]] - a[:, L["misses"]]) / window}
    total_saving = (costs(b, world) - costs(a, world)) / window
    pieces["other_cost_saving"] = total_saving - pieces["poison_cost_saving"] - pieces["miss_cost_saving"]
    if not np.allclose(a[:, L["F"]] - b[:, L["F"]] - sum(pieces.values()), 0, rtol=0, atol=1e-10):
        raise ValueError("paired fitness decomposition does not reconcile")
    result["fitness_pieces"] = {name: stats(value) for name, value in pieces.items()}
    return result, pieces


def analyze(base):
    base = Path(base).resolve()
    budget_path = operation(base, "budget.json")
    if not budget_path.exists() or read(budget_path)["status"] != "complete":
        status = read(budget_path)["status"] if budget_path.exists() else "not_started"
        return {"status": "incomplete", "budget_status": status}, {}
    protocol, manifest, audit = audit_inputs(base)
    budget = read(budget_path)
    equal(budget["ready"], manifest["ready"], "monitor release pins")
    equal(budget["cap_cpu_seconds"], 3600, "monitor CPU cap")
    if not 0 < budget["cpu_seconds"] <= 3600:
        raise ValueError("completed study is outside its registered CPU cap")
    if budget.get("worker_pid") is not None or budget.get("cleanup_error"):
        raise ValueError("completed monitor has an active worker or unresolved cleanup")
    total = protocol["calibration_cpu_seconds"]
    if not isinstance(budget["attempts"], list) or len(budget["attempts"]) != 1:
        raise ValueError("this pilot permits exactly one finalized attempt; no resume outcome")
    for index, item in enumerate(budget["attempts"]):
        equal(item.get("number"), index + 1, "ordered attempt number")
        if not isinstance(item.get("exit_code"), int):
            raise ValueError("attempt lacks a finalized exit receipt")
        if index + 1 < len(budget["attempts"]) and item["exit_code"] == 0:
            raise ValueError("successful study was rerun")
        if not np.isfinite(item["cpu_seconds"]) or item["cpu_seconds"] < 0:
            raise ValueError("invalid attempt CPU")
        if not np.isclose(item["prior_cpu_seconds"], total, rtol=0, atol=1e-8):
            raise ValueError("attempt resets prior calibration/research CPU")
        total += item["cpu_seconds"]
    if not np.isclose(total, budget["cpu_seconds"], rtol=0, atol=1e-8):
        raise ValueError("cumulative monitor CPU accounting differs")
    equal(budget["attempts"][-1]["exit_code"], 0, "final worker exit")
    report, scores = read(operation(base, "report.json")), read(operation(base, "scores.json"))
    equal(report["status"], "complete", "scientific worker report")
    equal(report["candidate_lives"], 3584, "scientific report life count")
    progress = read(operation(base, "progress.json"))
    equal(progress, {"status": "complete", "completed_candidates": list(NAMES)}, "all fixed candidates completed")
    equal(list(scores["runs"]), list(NAMES), "raw score candidate order")
    equal(scores["seeds"], protocol["seeds"], "score seed order")
    equal((scores["world"], scores["T"], scores["capability"]), ("prediction", 1024, "prediction"), "score world/capability")
    equal(scores["config_sha256"], protocol["config_sha256"], "score fixed config")
    equal(scores["scratch_slots"], {}, "no scratch world extension")
    for candidate in protocol["candidates"]:
        metadata = scores["runs"][candidate["name"]]
        for key, expected in candidate.items():
            if key != "name":
                equal(metadata[key], expected, "score candidate metadata " + candidate["name"] + " " + key)
        if "params" in candidate:
            equal(metadata["isolates_capability"], False, "score broad ablation interpretation")
            equal(metadata["disabled_parameters"], [3, 4], "score disabled parameter identities")
            equal(metadata["source_sha256"], protocol["controller_sha256"], "score controller source")
            equal(metadata["privileged"], False, "controller information access")
    equal(scores["harness_identity"], protocol["harness_identity"], "score source pins")
    equal(scores["library_sha256"], manifest["library"]["measurement.so"], "score library")
    rows = load_rows(base, protocol, manifest)
    candidate_cpu = sum(float(row["cpu_seconds"]) for row in rows.values())
    if candidate_cpu > budget["cpu_seconds"] - protocol["calibration_cpu_seconds"] + 1e-8:
        raise ValueError("committed candidate CPU exceeds the monitored research allocation")
    for name, row in rows.items():
        for column in ("F", "captures", "clicks", "status", "t_end"):
            if not identical(np.asarray(scores["runs"][name][column], dtype=np.float64), row["ledger"][:, L[column]]):
                raise ValueError(name + " raw score JSON roundtrip differs")
    best_ref = max(NAMES[:2], key=lambda name: rows[name]["ledger"][:, L["F"]].mean())
    best_quiet = max(NAMES[2:5], key=lambda name: rows[name]["ledger"][:, L["F"]].mean())
    contrasts, vectors = {}, {"seeds": np.asarray(protocol["seeds"], dtype=np.int64)}
    comparisons = {"full_vs_reflex": best_ref, "full_vs_frozen_reflex": "frozen",
                   "full_vs_retuned_reflex": "retuned", "full_vs_ablated": "ablated"}
    for key, reference in comparisons.items():
        contrasts[key], pieces = contrast(rows["full"], rows[reference], protocol["world"])
        for column, value in contrasts[key].items():
            if column != "fitness_pieces":
                check_stats(value, report[key][column], key + " " + column)
        for piece, value in contrasts[key]["fitness_pieces"].items():
            check_stats(value, report[key]["fitness_pieces"][piece], key + " " + piece)
        vectors[key] = rows["full"]["ledger"][:, L["F"]] - rows[reference]["ledger"][:, L["F"]]
        vectors.update({key + "__" + name: value for name, value in pieces.items()})
    do_less = {}
    for name in NAMES[2:5]:
        delta = rows[name]["ledger"][:, L["F"]] - rows[best_ref]["ledger"][:, L["F"]]
        do_less[name] = stats(delta)
        vectors["do_less__" + name] = delta
    gap, specific = contrasts["full_vs_reflex"]["F"], contrasts["full_vs_ablated"]["F"]
    checks = {"information_gap": gap["mean"] >= 1 and gap["mean"] > 3 * gap["se"],
              "do_less": do_less[best_quiet]["mean"] < gap["mean"] / 4}
    gate = read(operation(base, "admission.json"))
    equal(gate, report["admission"], "worker admission copies")
    equal(gate["missing"], ["ablation isolating the named capability"], "explicit unresolved prediction-specific evidence")
    equal((gate["world"], gate["T"], gate["n"]), ("prediction", 1024, 512), "gate world/duration/count")
    equal(gate["best_reflex"], best_ref, "whole-candidate reference selection")
    equal(gate["best_do_less"], best_quiet, "whole-candidate do-less selection")
    equal(gate["checks"], checks, "independent descriptive admission checks")
    verdict = "incomplete"
    if "specific_part" in gate or "specific_part" in gate["checks"]:
        raise ValueError("broad-model ablation cannot become prediction-specific evidence")
    equal(gate["verdict"], verdict, "independent descriptive admission verdict")
    for key, actual in (("information_gap", gap),
                        ("ablation_gap", specific), ("do_less_gap", do_less[best_quiet])):
        check_stats(actual, gate[key], key)
    summary = {"status": "complete", "candidate_lives": 3584, "paired_seeds": 512, "T": 1024,
               "best_reflex": best_ref, "best_do_less": best_quiet, "contrasts": contrasts, "do_less": do_less,
               "descriptive_checks": checks, "descriptive_verdict": verdict,
               "broad_moving_target_model_effect": specific, "prediction_specific_effect": "unmeasured",
               "candidate_means": {name: {key: stats(row["ledger"][:, L[key]]) for key in
                                           ("F", "captures", "clicks", "misses", "b2_clicks", "path", "zone_samples",
                                            "samples", "n_end", "live_time", "cost")}
                                   for name, row in rows.items()},
               "budget": {"monitored_cpu_seconds": budget["cpu_seconds"], "cap_cpu_seconds": 3600,
                          "calibration_cpu_seconds_included": protocol["calibration_cpu_seconds"],
                          "candidate_cpu_seconds": sum(float(row["cpu_seconds"]) for row in rows.values()),
                          "attempts": len(budget["attempts"]), "workers": 2},
               "audit": dict(audit, full_ledger_columns=57, candidate_checkpoints=7,
                             score_json_raw_float64_roundtrip=True, independent_fitness_bytes=True),
               "limitations": LIMITATIONS}
    return summary, vectors



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    summary, vectors = analyze(args.study)
    if args.out is not None:
        if summary["status"] != "complete":
            raise ValueError("refuse to write outcome artifacts from an incomplete study")
        args.out.mkdir(parents=True, exist_ok=True)
        save(args.out / "summary.json", summary)
        if summary["status"] == "complete":
            np.savez_compressed(args.out / "independent_contrasts.npz", **vectors)
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
