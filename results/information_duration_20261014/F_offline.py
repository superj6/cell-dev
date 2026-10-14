"""Independent, offline F audit/export: NumPy accounting and source-text reconstruction; never simulate."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import numpy as np

ROOT = next((p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").exists()), None)
NAMES = ("frozen", "retuned", "smaller_frozen", "smaller_transferred", "quieter", "full", "ablated")
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
    "Model 1 versus 0 removes broad decoy belief, ping attribution, steering avoidance and tap veto; "
    "the effect does not isolate one classifier or tap mechanism.",
    "Controller parameters were transferred from ring5 to hollow3 without fresh tuning; a failure does not "
    "establish that the information is useless.",
    "The better whole reflex and best do-less candidate are chosen on these outcomes. Their paired SEs are "
    "conditional and descriptive, without selection adjustment; both fixed-reflex comparisons are reported.",
    "Only three fixed do-less candidates were measured, not an exhaustive optimum.",
    "All cells, receptor pings, virtual relay spikes and actions pay; central controller computation is free.",
    "This study uses old conduction d0=1, d_min=0.5 and T1024; it supplies no duration-transfer evidence.",
    "Existing replay/parity evidence covers bounded T64 lives, not universal long-duration parity.",
    "Fast event hashes retain HASH_INIT (0x243f6a8885a308d3) and are not replay evidence; file hashes protect "
    "stored bytes. The preparation's claim of zero hashes is corrected in ERRATA.md without changing its pins.",
    "A passing descriptive measurement never automatically admits the world into selection.",
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


def validate_ledger(ledger, world):
    if ledger.dtype != np.float64 or ledger.shape != (512, len(LEDGER)) or not np.isfinite(ledger).all():
        raise ValueError("invalid 512-life full ledger")
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
    code = env["patched_source"](["/CELLDEV/results/taskvar/measurement/discrimination_ctl.c"])
    old = "  c->e_on = w[W_TAUR]; c->e_off = w[W_TAUE];"
    equal(code.count(old), 1, "epoch-alias patch target")
    code = code.replace(old, "  c->e_on = 0.0; c->e_off = 0.0; // E7 uses ABI 3 blob physics")
    actual = operation(base, "measurement.c").read_text()
    actual = re.sub(r'#include "[^"\n]*/(results/(?:open_headroom/harness|taskvar/measurement)/[^"\n]+)"',
                    r'#include "/CELLDEV/\1"', actual)
    equal(actual, code, "generated measurement source reconstructed from pinned sources")


def audit_inputs(base):
    protocol = read(base / "protocol.json")
    equal(protocol["seeds"], list(range(51_300_000, 51_300_512)), "shared ordered block30 seeds")
    equal([row["name"] for row in protocol["candidates"]], list(NAMES), "candidate order")
    equal((protocol["candidate_lives"], protocol["threads"], protocol["max_cpu_seconds"]),
          (3584, 2, 1800), "registered dimensions")
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
    config = read(source(base, "results/taskvar/measurement/discrimination.json"))
    audit = read(source(base, "results/taskvar/validation/discrimination_audit.json"))
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
    for key, value in dict(T=1024, t0=0, t_open=0, d0=1, d_min=0.5, b2_value=-50, b2_sigma=1.2,
                           b2_amp=1, b2_p=1, b2_mode=1, kill_rate=0, wound_rate=0, drift_tau=0).items():
        equal(world[key], value, "world " + key)
    full, ablated = protocol["candidates"][-2:]
    equal(full["params"], config["params"], "recovered full controller parameters")
    expected_ablation = list(config["params"])
    expected_ablation[25] = 0
    equal(ablated["params"], expected_ablation, "recovered broad ablation")
    action = dict(latency="d0", charge="relay", t_ref_min=0.5, privileged=False, quant=False, fast=True)
    for candidate in (full, ablated):
        equal(candidate["action"], action, "controller action rule")
        equal(candidate["footprint"], "hollow3", "controller footprint")
    ready = read(operation(base, "ready.json"))
    for name, digest in ready.items():
        path = base / name if name == "protocol.json" else operation(base, name)
        equal(sha(path), digest, "released file " + name)
    equal(set(ready), {"protocol.json", "measure.py", "run_budgeted.py"}, "release pin names")
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
    equal(budget["cap_cpu_seconds"], 1800, "monitor CPU cap")
    if not 0 < budget["cpu_seconds"] <= 1800:
        raise ValueError("completed study is outside its registered CPU cap")
    total = sum(item["cpu_seconds"] for item in budget["attempts"])
    if not np.isclose(total, budget["cpu_seconds"], rtol=0, atol=1e-8):
        raise ValueError("cumulative monitor CPU accounting differs")
    equal(budget["attempts"][-1]["exit_code"], 0, "final worker exit")
    report, scores = read(operation(base, "report.json")), read(operation(base, "scores.json"))
    equal(report["status"], "complete", "scientific worker report")
    equal(scores["seeds"], protocol["seeds"], "score seed order")
    equal(scores["harness_identity"], protocol["harness_identity"], "score source pins")
    equal(scores["library_sha256"], manifest["library"]["measurement.so"], "score library")
    rows = load_rows(base, protocol, manifest)
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
              "specific_part": specific["mean"] >= 1 and specific["mean"] > 3 * specific["se"],
              "do_less": do_less[best_quiet]["mean"] < gap["mean"] / 4}
    gate = read(operation(base, "admission.json"))
    equal(gate, report["admission"], "worker admission copies")
    equal(gate["missing"], [], "admission evidence completeness")
    equal(gate["best_reflex"], best_ref, "whole-candidate reference selection")
    equal(gate["best_do_less"], best_quiet, "whole-candidate do-less selection")
    equal(gate["checks"], checks, "independent descriptive admission checks")
    verdict = "pass" if all(checks.values()) else "fail"
    equal(gate["verdict"], verdict, "independent descriptive admission verdict")
    for key, actual in (("information_gap", gap), ("specific_part", specific),
                        ("ablation_gap", specific), ("do_less_gap", do_less[best_quiet])):
        check_stats(actual, gate[key], key)
    summary = {"status": "complete", "candidate_lives": 3584, "paired_seeds": 512, "T": 1024,
               "best_reflex": best_ref, "best_do_less": best_quiet, "contrasts": contrasts, "do_less": do_less,
               "descriptive_checks": checks, "descriptive_verdict": verdict,
               "candidate_means": {name: {key: stats(row["ledger"][:, L[key]]) for key in
                                           ("F", "captures", "clicks", "misses", "b2_clicks", "path", "zone_samples",
                                            "samples", "n_end", "live_time", "cost")}
                                   for name, row in rows.items()},
               "budget": {"monitored_cpu_seconds": budget["cpu_seconds"], "cap_cpu_seconds": 1800,
                          "candidate_cpu_seconds": sum(float(row["cpu_seconds"]) for row in rows.values()),
                          "attempts": len(budget["attempts"]), "workers": 2},
               "audit": dict(audit, full_ledger_columns=57, candidate_checkpoints=7,
                             score_json_raw_float64_roundtrip=True, independent_fitness_bytes=True),
               "limitations": LIMITATIONS}
    return summary, vectors


def markdown(summary):
    lines = ["# Discrimination: the fixed recovered controller measurement", "",
             "Seven fixed candidates share 512 fresh T1024 lives in the existing harmful-decoy world,",
             "using old conduction d0=1 and d_min=0.5. All seven candidates and negative results are retained.", "",
             "| Comparison | Paired ΔF ± SE |", "|---|---:|"]
    labels = {"full_vs_reflex": "Full − selected whole reflex (" + summary["best_reflex"] + ")",
              "full_vs_frozen_reflex": "Full − frozen reflex", "full_vs_retuned_reflex": "Full − retuned reflex",
              "full_vs_ablated": "Full − matched ablation"}
    for key, label in labels.items():
        value = summary["contrasts"][key]["F"]
        lines.append(f"| {label} | {value['mean']:+.6f} ± {value['se']:.6f} |")
    lines += ["", "The unchanged descriptive plan-0.4 checks give **" + summary["descriptive_verdict"] + "**:", ""]
    for name, passed in summary["descriptive_checks"].items():
        lines.append(f"- {name.replace('_', ' ')}: {'passes' if passed else 'fails'}.")
    quiet = summary["do_less"][summary["best_do_less"]]
    lines += ["", f"The best of three fixed do-less variants is `{summary['best_do_less']}`: "
              f"{quiet['mean']:+.6f} ± {quiet['se']:.6f} F versus the selected reflex.", "",
              "All differences are formed within a shared seed before SE is estimated over 512 pairs.",
              "Reference selection uses each candidate's whole mean; it never picks a different reflex per life.", "",
              "| Candidate | Mean F ± SE | Captures | Poison clicks |", "|---|---:|---:|---:|"]
    for name in NAMES:
        row = summary["candidate_means"][name]
        lines.append(f"| {name} | {row['F']['mean']:.6f} ± {row['F']['se']:.6f} | "
                     f"{row['captures']['mean']:.3f} | {row['b2_clicks']['mean']:.3f} |")
    budget = summary["budget"]
    lines += ["", "All 3,584 candidate-lives completed in "
              f"{budget['monitored_cpu_seconds']:.6f} monitored CPU-seconds,",
              "within the fixed 1,800-second cap with two workers. No candidate or sample-size extension followed",
              "results.",
              "", "The independent audit reconstructs every F from all 57 ledger columns, checks byte-exact raw-score",
              "JSON roundtrips, candidate/library/source receipts, all 12 saved callback replays and generated C",
              "source. `rows/` preserves full ledgers, diagnostics, latency and timing. `operations/` preserves the",
              "actual compiled library, generated C, runner, release, manifest and budget. `original/` preserves",
              "the pinned source inputs.",
              "`prelaunch/` preserves the complete original preparation archive and its offline validator. The",
              "preparation's zero-hash wording is corrected in [ERRATA.md](ERRATA.md); frozen bytes are unchanged.", "",
              "Recompute without simulation or compilation (Python + NumPy; Matplotlib only for `--plot`):", "",
              "```bash",
              "python analyze.py --study . --check", "```", "", "Interpretation limits:", ""]
    lines.extend("- " + text for text in LIMITATIONS)
    return "\n".join(lines) + "\n"


def plot(summary, directory):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5), layout="constrained")
    names = ("full_vs_frozen_reflex", "full_vs_retuned_reflex", "full_vs_ablated")
    labels = ("Full − frozen reflex", "Full − retuned reflex", "Full − ablation")
    values = [summary["contrasts"][key]["F"] for key in names]
    axes[0].errorbar([v["mean"] for v in values], np.arange(3), xerr=[3 * v["se"] for v in values],
                     fmt="o", capsize=5, color="#205493")
    axes[0].set_yticks(np.arange(3), labels)
    axes[0].invert_yaxis()
    axes[0].axvline(0, color="#6b7280", linewidth=1)
    axes[0].axvline(1, color="#9ca3af", linestyle="--", linewidth=1)
    axes[0].set(title="Fixed paired comparisons", xlabel="ΔF, mean ± 3 SE (512 shared lives)")
    axes[0].text(0.02, 0.97, "Dashed line: +1 F threshold", transform=axes[0].transAxes,
                 ha="left", va="top", fontsize=9, color="#4b5563")
    parts = ("capture_income", "poison_cost_saving", "miss_cost_saving", "other_cost_saving")
    colors = ("#2d6a4f", "#bc4749", "#e9a23b", "#6366a1")
    positive, negative = np.zeros(2), np.zeros(2)
    for part, color in zip(parts, colors):
        heights = np.array([summary["contrasts"][key]["fitness_pieces"][part]["mean"]
                            for key in ("full_vs_reflex", "full_vs_ablated")])
        bottoms = np.where(heights >= 0, positive, negative)
        axes[1].bar(np.arange(2), heights, bottom=bottoms, label=part.replace("_", " "), color=color, width=0.55)
        positive += np.maximum(heights, 0)
        negative += np.minimum(heights, 0)
    axes[1].axhline(0, color="#6b7280", linewidth=1)
    axes[1].set_xticks([0, 1], ["Full − selected reflex", "Full − ablation"])
    axes[1].set(title="Mean fitness accounting", ylabel="Contribution to paired ΔF")
    axes[1].set_ylim(top=max(positive) * 1.28)
    axes[1].legend(fontsize=9, loc="best")
    fig.suptitle("Existing decoy controller at the same 56-cell footprint", fontsize=14)
    fig.savefig(directory / "discrimination_summary.png", dpi=170)
    fig.savefig(directory / "discrimination_summary.svg")
    plt.close(fig)


def provenance(base):
    artifacts = {str(path.relative_to(base)): {"sha256": sha(path), "bytes": path.stat().st_size}
                 for path in sorted(base.rglob("*")) if path.is_file() and path != base / "provenance.json"
                 and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts}
    save(base / "provenance.json", {"format": 2, "status": "complete", "candidate_lives": 3584,
                                    "artifacts": artifacts})


def export(base, destination, summary, vectors):
    destination.mkdir(parents=True, exist_ok=True)
    historical = destination / "prelaunch"
    if not historical.exists():
        previous = read(destination / "provenance.json")
        equal(previous["status"], "prepared_not_launched", "original preparation archive status")
        for name in (*previous["artifacts"], "provenance.json"):
            target = historical / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(destination / name, target)
        # These entrypoints expect a preparation archive; retain their exact runnable copies in prelaunch/.
        for name in ("validate.py", "test_archive.py"):
            (destination / name).unlink()
    for old, new in (("README.md", "PREPARATION.md"), ("provenance.json", "preparation_provenance.json")):
        if (destination / old).is_file() and not (destination / new).exists():
            shutil.copyfile(destination / old, destination / new)
    shutil.copyfile(base / "protocol.json", destination / "protocol.json")
    shutil.copytree(base / "rows", destination / "rows", dirs_exist_ok=True)
    operations = destination / "operations"
    operations.mkdir(exist_ok=True)
    for name in ("measure.py", "run_budgeted.py", "ready.json", "library.json", "measurement.c", "measurement.so",
                 "manifest.json", "budget.json", "measurement.log", "progress.json", "scores.json", "report.json",
                 "admission.json"):
        shutil.copyfile(base / name, operations / name)
    protocol = read(base / "protocol.json")
    for relative in {**protocol["source_pins"], **protocol["harness_identity"]}:
        path = destination / "original" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source(base, relative), path)
    shutil.copyfile(Path(__file__), destination / "analyze.py")
    test_path = Path(__file__).with_name("test_analysis.py")
    if test_path.exists():
        shutil.copyfile(test_path, destination / "test_analysis.py")
    save(destination / "summary.json", summary)
    np.savez_compressed(destination / "independent_contrasts.npz", **vectors)
    (destination / "README.md").write_text(markdown(summary))
    (destination / "ERRATA.md").write_text(
        "# Preparation wording correction\n\n"
        "The preregistration, protocol and preparation describe fast event hashes as zero. The existing LIFE_FAST\n"
        "kernel instead skips hash folds and leaves all five hash families at HASH_INIT, 0x243f6a8885a308d3.\n"
        "Every recorded candidate-life hash has that constant value. Neither a constant initializer nor zero\n"
        "contains event replay evidence. File SHA256 receipts continue to protect saved evidence.\n\n"
        "This corrects a documentation error, with no change to a simulation, result, source pin or protocol choice.\n"
        "The frozen preparation bytes and their validator remain intact under prelaunch/.\n")
    plot(summary, destination)
    checked, reloaded = analyze(destination)
    equal(checked, summary, "exported independent summary")
    for key in vectors:
        if not identical(vectors[key], reloaded[key]):
            raise ValueError("exported paired vector bytes differ")
    for name in NAMES:
        equal(sha(base / "rows" / name / "row.npz"), sha(destination / "rows" / name / "row.npz"),
              "exported raw candidate bytes")
    provenance(destination)


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
        for name, meta in record["artifacts"].items():
            equal(sha(args.study / name), meta["sha256"], "public artifact " + name)
            equal((args.study / name).stat().st_size, meta["bytes"], "public artifact size " + name)
        equal(read(args.study / "summary.json"), summary, "public independent summary")
        equal((args.study / "README.md").read_text(), markdown(summary), "public readable summary")
        with np.load(args.study / "independent_contrasts.npz", allow_pickle=False) as saved:
            equal(set(saved.files), set(vectors), "public paired vector keys")
            for key, value in vectors.items():
                if not identical(saved[key], value):
                    raise ValueError("public paired vector bytes differ")
    if args.export:
        export(args.study.resolve(), args.export.resolve(), summary, vectors)
    if args.plot:
        plot(summary, args.study)
    print(json.dumps({"status": summary["status"], "candidate_lives": 3584,
                      "descriptive_verdict": summary["descriptive_verdict"], "audit": summary["audit"]}, indent=2))


if __name__ == "__main__":
    main()
