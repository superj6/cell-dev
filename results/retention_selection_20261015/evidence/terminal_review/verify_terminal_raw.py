"""AL terminal-only literal-ledger recount and separate frozen-reader replay; never simulates."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").is_file())
STUDY = ROOT / "outputs/autonomous_retention_selection_20261015"
DEST = ROOT / "outputs/audit_retention_selection_20261015/terminal_review/independent"
ANALYZER_SHA = "1152fbef215aad60f09b010fb8308f3b908aa36fc995dcbab7921a1e5dc05302"
NAMES = (
    "income live_time sec_int spikes kappa_sum contact_events claims births rejects rejects_wall deaths kills "
    "cost guard_charge net F n_end n_peak t_end status events beats P_int arrivals arrivals_dropped packets "
    "morph_secreted morph_decayed morph_lost morph_content_end morph_inflight_end chem_clamps last_birth ticks t_ext "
    "captures misses clicks b2_clicks respawns nudges rec_cand rec_accept rec_events rec_gain samples dist_sum "
    "zone_samples path X_end Y_end n_S_end n_M_end n_H_end live_S live_M live_H"
).split()
PROTOCOL_SHA = "25575f9ef690d00741fea0c62570d15aeb526d66a13a42025a91c5cd2fad19bf"
ROLES = ("AI_control_start", "persistent_control_final", "mixture_final")
ARMS = ("persistent_control", "balanced_mixture")
WORLDS = ("pool", "persistent", "blink80_5", "turn100_blink80_5")


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stat(values):
    mean = float(values.mean())
    se = float(values.std(ddof=1) / math.sqrt(len(values)))
    return {"mean": mean, "se": se, "n": len(values), "lower_3se": mean - 3 * se,
            "upper_3se": mean + 3 * se, "positive_above_3se": mean > 3 * se}


def literal_row(raw, world, abi):
    led = raw["ledger"]
    if led.dtype != np.float64 or led.shape != (256, 57 if abi == 3 else 58) or not np.isfinite(led).all():
        raise ValueError("invalid literal ledger")
    status = led[:, 19]
    if np.any(status < 0) or np.any(status > 511) or np.any(status != np.floor(status)):
        raise ValueError("invalid status encoding")
    status = status.astype(np.int64)
    if np.any(status & 192):
        raise ValueError("capacity/mismatch cannot become evidence")
    end, window = world["t0"] + world["T"], world["T"] - world["t_open"]
    terms = [
        ("living", world["c_live"] * led[:, 1]),
        ("spiking", world["c_spike"] * led[:, 3]),
        ("twitching", world["c_tw"] * led[:, 4]),
        ("messages", world["c_msg"] * led[:, 5]),
        ("division", world["c_div"] * led[:, 6]),
        ("secretion", world["c_sec"] * led[:, 2]),
        ("missed_clicks", world["c_miss"] * led[:, 36]),
        ("receptors", world["c_rec"] * led[:, 44]),
        ("decoy_clicks", max(0., -world["b2_value"]) * led[:, 38]),
    ]
    cost = terms[0][1].copy()
    for _, value in terms[1:]:
        cost = cost + value
    income = world["R_cap"] * led[:, 35]
    guard = np.where((status & 6) != 0, world["c_live"] * world["n_max"] * (end - led[:, 18]), 0.)
    extinct = world["c_live"] * np.where(
        (status & 1) != 0, end - np.maximum(led[:, 34], world["t0"]), 0.) / window
    net = income - cost - guard
    kernel_f, production_f = net / window, net / window - extinct
    if np.any(np.abs(led[:, 12] - cost) > 1e-9 * np.maximum(1., np.abs(cost))):
        raise ValueError("literal ordinary-cost reconciliation failed")
    for observed, expected in ((led[:, 0], income), (led[:, 13], guard), (led[:, 14], net),
                               (led[:, 15], kernel_f), (raw["production_F"], production_f)):
        if not np.allclose(observed, expected, rtol=0, atol=1e-9):
            raise ValueError("literal raw/scored accounting differs")
    if not np.array_equal(1 + led[:, 7] - led[:, 10] - led[:, 11], led[:, 16]):
        raise ValueError("initial-cell-aware census differs")
    if not np.array_equal(led[:, 35] + led[:, 36], led[:, 37]):
        raise ValueError("capture/miss/click census differs")
    low = led[:, 57] if abi == 4 else np.zeros(256, dtype=np.float64)
    if np.any(low < 0) or np.any(low > led[:, 35]) or np.any(low != np.floor(low)):
        raise ValueError("invalid low-light captures")
    metrics = {name: led[:, i].copy() for i, name in enumerate(NAMES)}
    metrics.update(F=production_f, F_kernel=kernel_f, extinct_charge=extinct,
                   window=np.full(256, window, dtype=np.float64), low_light_captures=low,
                   bright_captures=led[:, 35] - low, capture_income=income / window,
                   ordinary_cost=-cost / window, guard_cost=-guard / window, extinction_cost=-extinct)
    metrics.update({"cost__" + name: -value / window for name, value in terms})
    return metrics, {str(int(s)): int(np.sum(status == s)) for s in np.unique(status)}


def recount(study, protocol):
    index = read(study / "row_index.json")
    endpoints = read(study / "endpoints.json")
    endpoint_sha = sha(study / "endpoints.json")
    if endpoints["roles"] != list(ROLES) or endpoints["protocol_sha256"] != PROTOCOL_SHA:
        raise ValueError("frozen endpoint manifest differs")
    wanted = {f"raw/{w}/row_{i:02d}.npz" for w in WORLDS for i in range(3)}
    if set(index) != wanted or {str(p.relative_to(study)) for p in (study / "raw").rglob("*.npz")} != wanted:
        raise ValueError("literal raw coverage differs")
    if protocol["roles"] != list(ROLES) or list(protocol["worlds"]) != list(WORLDS):
        raise ValueError("fixed roles/worlds differ")
    rows, status_counts, cpu = {}, {}, 0.
    for world in WORLDS:
        rows[world], status_counts[world] = {}, {}
        for i, role in enumerate(ROLES):
            name = f"raw/{world}/row_{i:02d}.npz"
            path = study / name
            if sha(path) != index[name]["sha256"]:
                raise ValueError("changed raw file")
            with np.load(path, allow_pickle=False) as handle:
                raw = {k: handle[k].copy() for k in handle.files}
            if (raw["seeds"].dtype != np.uint64 or raw["seeds"].tolist() != protocol["seeds"]
                    or str(raw["role"]) != role or str(raw["world_name"]) != world
                    or str(raw["genome_raw_sha256"]) != endpoints["genomes"][i]["raw_sha256"]
                    or str(raw["endpoints_sha256"]) != endpoint_sha
                    or str(raw["protocol_sha256"]) != sha(study / "protocol.json")
                    or raw["hashes"].dtype != np.uint64 or raw["hashes"].shape != (256, 5)):
                raise ValueError("raw binding differs")
            definition = protocol["worlds"][world]
            rows[world][role], status_counts[world][role] = literal_row(raw, definition["world"], definition["abi"])
            for timing in ("cpu_seconds", "wall_seconds"):
                if raw[timing].shape != () or not np.isfinite(raw[timing]) or raw[timing] < 0:
                    raise ValueError("invalid raw scalar timing")
                if float(raw[timing]) != index[name][timing]:
                    raise ValueError("raw timing/index differs")
            cpu += float(raw["cpu_seconds"])
    return rows, status_counts, cpu


def all_vectors(rows):
    vectors = {}
    metrics = list(rows["pool"][ROLES[0]])
    pairs = ((ROLES[1], ROLES[0]), (ROLES[2], ROLES[0]), (ROLES[2], ROLES[1]))
    for w in WORLDS:
        for new, old in pairs:
            for metric in metrics:
                vectors[f"within__{w}__{new}_minus_{old}__{metric}"] = rows[w][new][metric] - rows[w][old][metric]
    for w in ("pool", "blink80_5", "turn100_blink80_5"):
        for role in ROLES:
            for metric in metrics:
                vectors[f"environment__{w}_minus_persistent__{role}__{metric}"] = (
                    rows[w][role][metric] - rows["persistent"][role][metric])
        for new, old in pairs:
            for metric in metrics:
                vectors[f"interaction__{w}_minus_persistent__{new}_minus_{old}__{metric}"] = (
                    (rows[w][new][metric] - rows[w][old][metric])
                    - (rows["persistent"][new][metric] - rows["persistent"][old][metric]))
    for role in ROLES[1:]:
        key = f"retention__{role}_vs_{ROLES[0]}__persistent"
        new, previous = rows["persistent"][role]["captures"], rows["persistent"][ROLES[0]]["captures"]
        vectors[key + "__capture_difference"] = new - previous
        vectors[key + "__ninety_percent_reference"] = new - .9 * previous
    if len(vectors) != 2254:
        raise ValueError("literal vector coverage differs")
    return vectors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=STUDY)
    parser.add_argument("--out", type=Path, default=DEST)
    parser.add_argument("--budget-sha256", required=True)
    parser.add_argument("--clearance-sha256", required=True)
    args = parser.parse_args()
    study = args.study.resolve()
    # Fail before loading any scientific row or canonical result until exact terminal evidence is present.
    if sha(study / "budget.json") != args.budget_sha256 or sha(study / "terminal_review/host_clearance.json") != args.clearance_sha256:
        raise ValueError("root terminal pins differ")
    budget, clearance = read(study / "budget.json"), read(study / "terminal_review/host_clearance.json")
    if (budget["status"] != "complete" or budget["exit_code"] != 0 or budget["worker_exit_code"] != 0
            or clearance["status"] != "cleared" or clearance["budget_sha256"] != args.budget_sha256
            or clearance["pid_namespace"] != budget["pid_namespace"]
            or clearance["remaining_identities"] or clearance["remaining_group_members"]):
        raise ValueError("root-cleared complete execution required before outcomes")
    if sha(study / "protocol.json") != PROTOCOL_SHA:
        raise ValueError("released protocol differs")
    if sha(study / "analyze.py") != ANALYZER_SHA:
        raise ValueError("frozen canonical analyzer changed")
    canonical = study / "analysis_result"
    if read(canonical / "summary.json")["status"] != "complete":
        raise ValueError("root's complete canonical analysis required")
    args.out.mkdir(parents=True, exist_ok=False)
    protocol = read(study / "protocol.json")
    marker = read(study / "study_complete.json")
    if (marker["status"] != "complete" or marker["research_lives"] != 13388
            or marker["startup_lives"] != 8 or marker["total_calls"] != 13396
            or marker["protocol_sha256"] != PROTOCOL_SHA
            or marker["measurement_complete_sha256"] != sha(study / "measurement_complete.json")):
        raise ValueError("whole completed-call coverage differs")
    search = {}
    for arm in ARMS:
        path = study / "runs" / arm / "search_complete.json"
        record = read(path)
        if (sha(path) != marker["search_complete_pins"][arm] or record["status"] != "complete"
                or record["arm"] != arm or record["protocol_sha256"] != PROTOCOL_SHA
                or record["research_lives"] != 5158 or record["startup_lives"] != 2):
            raise ValueError("completed native call count differs")
        search[arm] = {"research_lives": record["research_lives"], "startup_lives": record["startup_lives"],
                       "count_proof": record["count_proof"], "aggregate_health": record["health"],
                       "limitation": "Native summaries, not complete per-life raw search ledgers."}
    rows, statuses, cpu = recount(study, protocol)
    vectors = all_vectors(rows)
    max_error = 0.
    with np.load(canonical / "paired_arrays.npz", allow_pickle=False) as reference:
        if set(reference.files) != set(vectors):
            raise ValueError("canonical array set differs")
        for name, value in vectors.items():
            observed = reference[name]
            if observed.dtype != np.float64 or observed.shape != (256,):
                raise ValueError("canonical vector schema differs")
            error = float(np.max(np.abs(value - observed)))
            max_error = max(max_error, error)
            if not np.allclose(value, observed, rtol=0, atol=1e-9):
                raise ValueError("literal paired reconstruction differs: " + name)
    if cpu > budget["confirmation_cpu_seconds"] + 1e-6:
        raise ValueError("raw row CPU exceeds monitor total")
    command = [str(ROOT / ".venv/bin/python"), str(study / "analyze.py"), "--study", str(study),
               "--out", str(args.out.resolve() / "reanalysis")]
    result = subprocess.run(command, cwd="/", env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                            text=True, capture_output=True, check=False)
    (args.out / "reanalysis.stdout.txt").write_text(result.stdout)
    (args.out / "reanalysis.stderr.txt").write_text(result.stderr)
    if result.returncode:
        raise ValueError("frozen reader replay failed; exact output retained")
    for name in ("summary.json", "paired_arrays.npz"):
        if sha(args.out / "reanalysis" / name) != sha(canonical / name):
            raise ValueError("frozen reader reanalysis bytes differ: " + name)
    interesting = {k: stat(v) for k, v in vectors.items() if k.endswith(("__captures", "__F", "__ordinary_cost",
                    "__capture_income", "__guard_cost", "__extinction_cost", "__low_light_captures"))
                   or k.startswith("retention__")}
    report = {
        "status": "passed", "protocol_sha256": sha(study / "protocol.json"),
        "budget_sha256": args.budget_sha256, "clearance_sha256": args.clearance_sha256,
        "script_sha256": sha(Path(__file__)), "analyzer_sha256": ANALYZER_SHA,
        "canonical_summary_sha256": sha(canonical / "summary.json"),
        "canonical_arrays_sha256": sha(canonical / "paired_arrays.npz"),
        "raw_rows": 12, "raw_confirmation_lives": 3072, "native_search_research_lives": 10316,
        "research_lives": 13388, "startup_lives": 8, "total_calls": 13396, "native_counts_and_summary_health": search,
        "literal_vectors_checked": len(vectors), "max_literal_absolute_error": max_error,
        "canonical_frozen_reanalysis_exact_bytes": True, "status_counts": statuses,
        "row_cpu_seconds": cpu, "total_cpu_seconds": budget["cpu_seconds"],
        "total_wall_seconds": budget["wall_seconds"], "search_cpu_seconds": budget["search_cpu_seconds"],
        "confirmation_cpu_seconds": budget["confirmation_cpu_seconds"], "effects": interesting,
        "reanalysis_command": command, "reanalysis_cwd": "/",
        "new_simulations": 0, "builds": 0, "genetic_draws": 0,
        "limitations": ["One paired evolution from one chosen lineage; confirmation seeds are not evolutionary repetitions.",
                        "Raw status coverage is all3072 confirmation lives; native search statuses have only saved aggregate coverage.",
                        "A positive mixture-control POOL difference alone is not recovery relative to AI start or ancestral L92.",
                        "Full native genetic and selection replay is a separate independent audit.",
                        "Ten-percent retention margin is conventional; null effects do not establish retention.",
                        "A frozen genome may develop differently across worlds; no circuit or memory claim."]}
    (args.out / "independent_raw_review.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "literal_vectors_checked", "max_literal_absolute_error",
                                            "research_lives", "startup_lives", "total_cpu_seconds")}))


if __name__ == "__main__":
    main()
