"""Saved ABI6 rows only: physical accounting, paired food/fitness and resource conservation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

LEDGER = (
    "income", "live_time", "sec_int", "spikes", "kappa_sum", "contact_events", "claims", "births",
    "rejects", "rejects_wall", "deaths", "kills", "cost", "guard_charge", "net", "F", "n_end", "n_peak",
    "t_end", "status", "events", "beats", "P_int", "arrivals", "arrivals_dropped", "packets",
    "morph_secreted", "morph_decayed", "morph_lost", "morph_content_end", "morph_inflight_end",
    "chem_clamps", "last_birth", "ticks", "t_ext", "captures", "misses", "clicks", "b2_clicks", "respawns",
    "nudges", "rec_cand", "rec_accept", "rec_events", "rec_gain", "samples", "dist_sum", "zone_samples", "path",
    "X_end", "Y_end", "n_S_end", "n_M_end", "n_H_end", "live_S", "live_M", "live_H", "low_light_captures",
)
TASK_METRICS = ("choice_opportunities", "choice_carry_in", "correct_choices", "wrong_choices",
                "choice_timeouts", "unfinished_choices")
TASK_COLUMNS = tuple(f"{metric}_{cls}" for metric in TASK_METRICS for cls in ("narrow", "broad"))
PATCH_METRICS = ("stock_open", "source", "supply", "spill", "harvest", "empty", "stock_end",
                 "initial_harvest", "refill_harvest")
PATCH_COLUMNS = tuple(f"patch_{metric}_{i}" for metric in PATCH_METRICS[:7] for i in range(4))
PATCH_COLUMNS += ("patch_geometric_misses",) + tuple(
    f"patch_{metric}_{i}" for metric in PATCH_METRICS[7:] for i in range(4))
LEDGER += TASK_COLUMNS + PATCH_COLUMNS
L = {name: i for i, name in enumerate(LEDGER)}
ROLES = ("AO_start", "patch8_start", "mean4", "pareto4")
WORLDS = ("patch", "pool", "persistent", "blink80_20", "transfer")
PAIRS = (("pareto4", "mean4"), ("mean4", "patch8_start"), ("pareto4", "patch8_start"),
         ("mean4", "AO_start"), ("pareto4", "AO_start"), ("patch8_start", "AO_start"))
COSTS = (("maintenance", "c_live", "live_time"), ("spikes", "c_spike", "spikes"),
         ("twitch", "c_tw", "kappa_sum"), ("messages", "c_msg", "contact_events"),
         ("division", "c_div", "claims"), ("secretion", "c_sec", "sec_int"),
         ("misses", "c_miss", "misses"), ("receptors", "c_rec", "rec_gain"))
COUNTS = ("spikes", "contact_events", "claims", "births", "rejects", "rejects_wall", "deaths", "kills",
          "n_end", "n_peak", "events", "beats", "arrivals", "arrivals_dropped", "packets", "chem_clamps",
          "ticks", "captures", "misses", "clicks", "b2_clicks", "respawns", "nudges", "rec_cand",
          "rec_accept", "rec_events", "samples", "zone_samples", "n_S_end", "n_M_end", "n_H_end",
          "low_light_captures") + TASK_COLUMNS + PATCH_COLUMNS
SIGNED = ("net", "F", "t_end", "last_birth", "t_ext", "X_end", "Y_end")
STUDY = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def identical(left, right):
    left, right = np.asarray(left), np.asarray(right)
    return left.dtype == right.dtype and left.shape == right.shape and left.tobytes() == right.tobytes()


def describe(values):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.isfinite(values).all():
        raise ValueError("finite one-dimensional life-cluster sample required")
    mean, se = float(values.mean()), float(values.std(ddof=1) / np.sqrt(len(values)))
    return dict(n=len(values), mean=mean, se=se, lower_3se=mean-3*se, upper_3se=mean+3*se,
                positive_above_3se=mean > 3*se, bounds_are_descriptive=True)


def reconcile(actual, expected, label):
    if np.any(np.abs(actual-expected) > 1e-9 * np.maximum(1.0, np.abs(expected))):
        raise ValueError("independent accounting differs: " + label)


def reconstruct(row, definition, seeds):
    """Retain guards/extinction; reject invalid outputs after their original bytes are saved."""
    world = definition["world"]
    n, ledger = len(seeds), np.asarray(row["ledger"])
    if (definition["abi"] != 6 or definition["ledger_columns"] != list(LEDGER)
            or ledger.dtype != np.float64 or ledger.shape != (n, 107) or not np.isfinite(ledger).all()):
        raise ValueError("complete finite ABI6 ledger and exact schema required")
    observed_seeds, hashes = np.asarray(row["seeds"]), np.asarray(row["hashes"])
    if (observed_seeds.dtype != np.uint64 or observed_seeds.shape != (n,)
            or observed_seeds.tolist() != list(seeds) or hashes.dtype != np.uint64 or hashes.shape != (n, 5)):
        raise ValueError("raw seed or hash schema differs")
    if not np.all(hashes == np.uint64(0x243F6A8885A308D3)):
        raise ValueError("confirmation uses fast constant hashes, never trajectory proof")
    col = {name: ledger[:, i] for i, name in enumerate(LEDGER)}
    for name in set(LEDGER)-set(SIGNED):
        if np.any(col[name] < 0):
            raise ValueError("negative physical quantity: " + name)
    for name in COUNTS + ("status",):
        if np.any(col[name] != np.floor(col[name])):
            raise ValueError("nonintegral count: " + name)
    if np.any(col["status"] > 511):
        raise ValueError("unknown status bits")
    status = col["status"].astype(np.int64)
    if np.any(status & (8 | 16 | 64 | 128)):
        raise ValueError("overflow, capacity or ledger mismatch cannot support inference")
    guarded, extinct = (status & 6) != 0, (status & 1) != 0
    start, end = world["t0"], world["t0"]+world["T"]
    window, opened = world["T"]-world["t_open"], start+world["t_open"]
    if window <= 0 or world["world_kind"] != 1 or world["t_open"] != 0:
        raise ValueError("registered full-life CATCH worlds required")
    if (np.any(col["t_end"] < start) or np.any(col["t_end"] > end)
            or np.any(~guarded & (col["t_end"] != end))):
        raise ValueError("unexplained incomplete life")
    if (np.any(extinct & ((col["t_ext"] < start) | (col["t_ext"] > col["t_end"])))
            or np.any(~extinct & (col["t_ext"] != -1)) or np.any(extinct & (col["n_end"] != 0))):
        raise ValueError("extinction status/time/census disagree")
    if np.any((col["last_birth"] < start) | (col["last_birth"] > col["t_end"])):
        raise ValueError("birth time outside life")
    for small, large in (("zone_samples", "samples"), ("rec_accept", "rec_cand"),
                         ("rec_events", "rec_accept"), ("n_end", "n_peak"),
                         ("low_light_captures", "captures")):
        if np.any(col[small] > col[large]):
            raise ValueError(small + " exceeds " + large)
    if not np.array_equal(col["captures"] + col["b2_clicks"] + col["misses"], col["clicks"]):
        raise ValueError("physical slot hits plus misses do not sum to clicks")
    if not np.array_equal(col["n_S_end"] + col["n_M_end"] + col["n_H_end"], col["n_end"]):
        raise ValueError("plane census differs")
    reconcile(col["live_S"]+col["live_M"]+col["live_H"], col["live_time"], "plane live time")
    if not np.array_equal(1+col["births"]-col["deaths"]-col["kills"], col["n_end"]):
        raise ValueError("one-cell initial census does not reconcile")
    morph = sum(col[k] for k in ("morph_decayed", "morph_lost", "morph_content_end", "morph_inflight_end"))
    reconcile(morph, col["morph_secreted"], "morphogen conservation")
    if (world["task_mode"] != 0 or world["b2_amp"] != 0 or world["b2_value"] != 0
            or any(np.any(col[key] != 0) for key in TASK_COLUMNS) or np.any(col["b2_clicks"] != 0)):
        raise ValueError("registered worlds require neutral matching/second-blob inputs and counters")
    income = world["R_cap"] * col["captures"]
    patch = {name: sum(col[f"patch_{name}_{i}"] for i in range(4)) for name in PATCH_METRICS}
    if world["patch_count"]:
        capacity, active = world["patch_capacity"], col["t_end"] > opened
        for i in range(4):
            values = {name: col[f"patch_{name}_{i}"] for name in PATCH_METRICS}
            if i >= world["patch_count"]:
                if any(np.any(value != 0) for value in values.values()):
                    raise ValueError("inactive patch counters are nonzero")
                continue
            if (np.any(values["stock_open"] != np.where(active, capacity, 0))
                    or np.any(values["stock_end"] > capacity)
                    or any(np.any(value[~active] != 0) for value in values.values())):
                raise ValueError("patch stock bounds/full-life opening/empty-window differ")
            if (not np.array_equal(values["source"], values["supply"] + values["spill"])
                    or not np.array_equal(values["stock_open"] + values["supply"],
                                          values["harvest"] + values["stock_end"])
                    or not np.array_equal(values["harvest"], values["initial_harvest"] + values["refill_harvest"])
                    or not np.array_equal(values["initial_harvest"], np.minimum(capacity, values["harvest"]))
                    or np.any(values["refill_harvest"] > values["supply"])):
                raise ValueError("patch source/stock/FIFO conservation differs")
        if (not np.array_equal(patch["harvest"], col["captures"])
                or not np.array_equal(patch["empty"] + col["patch_geometric_misses"], col["misses"])
                or np.any(col["respawns"] != 0)):
            raise ValueError("patch counters disagree with native outcomes")
    elif any(np.any(col[key] != 0) for key in PATCH_COLUMNS):
        raise ValueError("older worlds must have neutral patch counters")
    if world["visibility_mode"] == 0 and np.any(col["low_light_captures"] != 0):
        raise ValueError("neutral visibility has low-light captures")
    parts = {name: world[price]*col[key] for name, price, key in COSTS}
    cost = sum(parts.values())
    guard = np.where(guarded, world["c_live"]*world["n_max"]*(end-col["t_end"]), 0.)
    extinction = world["c_live"]*np.where(extinct, end-np.maximum(col["t_ext"], opened), 0.)/window
    net = income-cost-guard
    for name, expected in (("income", income), ("cost", cost), ("guard_charge", guard),
                           ("net", net), ("F", net/window)):
        reconcile(col[name], expected, name)
    production = col["F"]-extinction
    if "production_F" in row and not identical(row["production_F"], production):
        raise ValueError("production fitness is not native F minus extinction surcharge")
    for name in ("cpu_seconds", "wall_seconds"):
        value = np.asarray(row[name])
        if value.shape != () or not np.isfinite(value) or value < 0:
            raise ValueError("invalid scalar row timing")
    metrics = dict(col, F=production, native_F=col["F"], extinct_charge=extinction,
                   income_contribution=income/window, ordinary_cost_contribution=-cost/window,
                   guard_contribution=-guard/window, extinction_contribution=-extinction)
    metrics.update({"cost__"+name: value for name, value in parts.items()})
    metrics.update({"total_patch_"+name: value for name, value in patch.items()})
    metrics.update(initial_income=world["R_cap"] * patch["initial_harvest"],
                   refill_income=world["R_cap"] * patch["refill_harvest"],
                   initial_income_contribution=world["R_cap"] * patch["initial_harvest"] / window,
                   refill_income_contribution=world["R_cap"] * patch["refill_harvest"] / window,
                   physical_cost=cost, guard_energy=guard, extinction_energy=extinction * window,
                   guarded=guarded.astype(np.float64), extinct=extinct.astype(np.float64))
    health = dict(status_counts={str(int(s)): int((status == s).sum()) for s in np.unique(status)},
                  guarded=int(guarded.sum()), extinct=int(extinct.sum()), all_fitness_rows_retained=n,
                  hashes_are_fast_constants_not_trajectory_evidence=True)
    return metrics, health


def analyze(study):
    protocol = read(study / "protocol.json")
    complete = read(study / "measurement_complete.json")
    index = read(study / "row_index.json")
    if (complete["status"] != "complete" or complete["research_lives"] != 10240
            or complete["startup_lives"] != 4 or complete["rows"] != 20
            or complete["protocol_sha256"] != sha(study / "protocol.json")
            or complete["row_index_sha256"] != sha(study / "row_index.json")
            or complete["endpoints_sha256"] != sha(study / "endpoints.json")):
        raise ValueError("complete fixed confirmation required")
    if tuple(protocol["roles"]) != ROLES or tuple(protocol["worlds"]) != WORLDS or not protocol["extinct_charge"]:
        raise ValueError("fixed four-role/five-world matrix and extinction accounting required")
    seeds = protocol["seeds"]
    if seeds != list(range(52500000, 52500512)):
        raise ValueError("512 fresh paired confirmation seeds required")
    endpoints = read(study / "endpoints.json")
    if endpoints["roles"] != list(ROLES) or endpoints["protocol_sha256"] != sha(study / "protocol.json"):
        raise ValueError("fixed endpoint manifest differs")
    rows, absolute, health = {}, {}, {}
    expected_paths = {f"raw/{world}/row_{i:02d}.npz" for world in WORLDS for i in range(4)}
    if set(index) != expected_paths:
        raise ValueError("missing or extra confirmation row")
    for world in WORLDS:
        rows[world], absolute[world], health[world] = {}, {}, {}
        for i, role in enumerate(ROLES):
            raw_path = f"raw/{world}/row_{i:02d}.npz"
            entry = index[raw_path]
            if (entry["status"] != "validated" or entry["lives"] != 512 or entry["abi"] != 6
                    or entry["role"] != role or entry["world"] != world
                    or entry["sha256"] != sha(study / raw_path)
                    or entry["scored_path"] != f"scored/{world}/row_{i:02d}.npz"
                    or entry["scored_sha256"] != sha(study / entry["scored_path"])):
                raise ValueError("row index differs")
            with np.load(study / raw_path, allow_pickle=False) as data:
                native = {key: data[key].copy() for key in data.files}
            with np.load(study / entry["scored_path"], allow_pickle=False) as data:
                scored = {key: data[key].copy() for key in data.files}
            for key, expected in (("world_name", world), ("role", role), ("raw_path", raw_path),
                                  ("protocol_sha256", sha(study / "protocol.json")),
                                  ("endpoints_sha256", sha(study / "endpoints.json")),
                                  ("genome_raw_sha256", endpoints["genomes"][i]["raw_sha256"])):
                if np.asarray(native[key]).shape != () or np.asarray(native[key]).item() != expected:
                    raise ValueError("native row identity differs: " + key)
            if str(scored["raw_sha256"]) != entry["sha256"]:
                raise ValueError("scored row is not bound to saved native output")
            native["production_F"] = scored["production_F"]
            metrics, checked = reconstruct(native, protocol["worlds"][world], seeds)
            if (not identical(scored["native_F"], metrics["native_F"])
                    or not identical(scored["extinct_charge"], metrics["extinct_charge"])):
                raise ValueError("scored native/extinction columns differ")
            if checked != entry["health"]:
                raise ValueError("retained row health differs")
            rows[world][role], health[world][role] = metrics, checked
            absolute[world][role] = {key: describe(value) for key, value in metrics.items()}
    paired = {}
    for world in WORLDS:
        paired[world] = {}
        for new, old in PAIRS:
            paired[world][new + "_minus_" + old] = {
                key: describe(rows[world][new][key] - rows[world][old][key]) for key in rows[world][new]}
    retention = {}
    for world in ("pool", "persistent", "blink80_20"):
        retention[world] = {}
        for candidate in ("mean4", "pareto4"):
            new, old = rows[world][candidate]["captures"], rows[world]["AO_start"]["captures"]
            margin = describe(new - .9 * old)
            retention[world][candidate + "_vs_AO_start"] = dict(
                captures_difference=describe(new - old), retained_90_percent_margin=margin,
                mean_capture_ratio=None if old.mean() == 0 else float(new.mean() / old.mean()),
                lower_3se_positive=margin["lower_3se"] > 0, diagnostic_only_not_a_gate=True)
    return dict(status="complete", research_lives=10240, startup_lives=4, paired_life_clusters=512,
                absolute=absolute, paired=paired, health=health, old_world_retention=retention,
                primary_contrast="pareto4_minus_mean4",
                protocol_sha256=sha(study / "protocol.json"), row_index_sha256=sha(study / "row_index.json"),
                endpoints_sha256=sha(study / "endpoints.json"),
                limitations=[
                    "One matched pair of continuations; life SE does not estimate reliability across searches.",
                    "Patch captures are food harvests; initial/refill FIFO labels describe origin, not revisit order.",
                    "Aggregate food and costs do not establish switching, memory or learned recovery rates.",
                    "All guards/extinction remain; physical energy costs and production extinction F are separate.",
                    "Both four-generation endpoints use the same frozen joint selection rule before confirmation.",
                    "The joint endpoint may differ from native rank zero; neither is replaced after confirmation.",
                    "New count2/radius3.5-5.5/refill60-180 transfer and 90% old-task retention are diagnostics.",
                    "The previously observed count4/radius3-5/refill100-200 combination is not this transfer.",
                    "The same unchanged endpoints face every world; no new endpoint is selected from transfer.",
                    "This bounded exploratory continuation makes no formal section0.4 admission claim."])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=STUDY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        print("source only: saved-row analysis requires --output; no simulator or random calls")
    else:
        with args.output.open("x") as stream:
            json.dump(analyze(args.study), stream, indent=2, allow_nan=False)
            stream.write("\n")

