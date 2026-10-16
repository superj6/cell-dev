"""Saved ABI5 rows only: independent accounting, paired fitness and observer choice readouts."""
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
LEDGER += TASK_COLUMNS
L = {name: i for i, name in enumerate(LEDGER)}
ROLES = ("AM_reference", "AO_start", "mixed8", "mixed24")
WORLDS = ("match85", "pool", "persistent", "blink80_20", "match1024", "short_blank", "transfer")
COSTS = (("maintenance", "c_live", "live_time"), ("spikes", "c_spike", "spikes"),
         ("twitch", "c_tw", "kappa_sum"), ("messages", "c_msg", "contact_events"),
         ("division", "c_div", "claims"), ("secretion", "c_sec", "sec_int"),
         ("misses", "c_miss", "misses"), ("receptors", "c_rec", "rec_gain"))
COUNTS = ("spikes", "contact_events", "claims", "births", "rejects", "rejects_wall", "deaths", "kills",
          "n_end", "n_peak", "events", "beats", "arrivals", "arrivals_dropped", "packets", "chem_clamps",
          "ticks", "captures", "misses", "clicks", "b2_clicks", "respawns", "nudges", "rec_cand",
          "rec_accept", "rec_events", "samples", "zone_samples", "n_S_end", "n_M_end", "n_H_end",
          "low_light_captures") + TASK_COLUMNS
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
    if (definition["abi"] != 5 or definition["ledger_columns"] != list(LEDGER)
            or ledger.dtype != np.float64 or ledger.shape != (n, 70) or not np.isfinite(ledger).all()):
        raise ValueError("complete finite ABI5 ledger and exact schema required")
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
            or np.any(~(guarded | extinct) & (col["t_end"] != end))):
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
    if world["task_mode"] == 1:
        for cls in ("narrow", "broad"):
            def get(metric, cls=cls):
                return col[f"{metric}_{cls}"]
            if not np.array_equal(get("choice_opportunities")+get("choice_carry_in"),
                                  sum(get(m) for m in TASK_METRICS[2:])):
                raise ValueError("class opportunity conservation differs: " + cls)
        correct = col["correct_choices_narrow"]+col["correct_choices_broad"]
        wrong = col["wrong_choices_narrow"]+col["wrong_choices_broad"]
        if (not np.array_equal(col["captures"], col["correct_choices_narrow"]+col["wrong_choices_broad"])
                or not np.array_equal(col["b2_clicks"], col["wrong_choices_narrow"]+col["correct_choices_broad"])):
            raise ValueError("physical width hits and class outcomes disagree")
        income = world["R_cap"]*correct
    elif world["task_mode"] == 0:
        if any(np.any(col[key] != 0) for key in TASK_COLUMNS) or world["b2_amp"] != 0:
            raise ValueError("legacy controls require neutral task counters and one target")
        wrong = col["b2_clicks"]
        income = world["R_cap"]*col["captures"]
    else:
        raise ValueError("unsupported task mode")
    if world["visibility_mode"] == 0 and np.any(col["low_light_captures"] != 0):
        raise ValueError("neutral visibility has low-light captures")
    parts = {name: world[price]*col[key] for name, price, key in COSTS}
    parts["wrong_choices" if world["task_mode"] else "decoy_hits"] = max(0., -world["b2_value"])*wrong
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
    health = dict(status_counts={str(int(s)): int((status == s).sum()) for s in np.unique(status)},
                  guarded=int(guarded.sum()), extinct=int(extinct.sum()), all_fitness_rows_retained=n,
                  hashes_are_fast_constants_not_trajectory_evidence=True)
    return metrics, health


def ratio_with_influence(numerator, denominator):
    denominator = np.asarray(denominator)
    total = float(denominator.sum())
    if total == 0:
        return None, None
    estimate = float(np.asarray(numerator).sum()/total)
    influence = (numerator-estimate*denominator)/denominator.mean()
    return dict(estimate=estimate, se=float(influence.std(ddof=1)/np.sqrt(len(influence))),
                numerator=float(np.asarray(numerator).sum()), denominator=total,
                uncertainty="life-cluster delta-method SE"), influence


def choice_readout(metrics, *, with_influence=False):
    classes, influences, rates = {}, {}, {}
    all_influences = {}
    for cls in ("narrow", "broad"):
        def get(metric, cls=cls):
            return metrics[f"{metric}_{cls}"]
        opportunity = get("choice_opportunities")+get("choice_carry_in")
        correct, wrong = get("correct_choices"), get("wrong_choices")
        complete = correct+wrong
        narrow_hits = correct if cls == "narrow" else wrong
        entry = {name: int(get(name).sum()) for name in TASK_METRICS}
        entry["narrow_hits"], entry["broad_hits"] = int(narrow_hits.sum()), int((complete-narrow_hits).sum())
        for name, numerator, denominator in (
                ("completion_coverage", complete, opportunity), ("correct_per_opportunity", correct, opportunity),
                ("accuracy_among_completed", correct, complete), ("narrow_given_completed", narrow_hits, complete),
                ("narrow_per_opportunity", narrow_hits, opportunity)):
            entry[name], influence = ratio_with_influence(numerator, denominator)
            all_influences[cls+"/"+name] = influence
            if name in ("narrow_given_completed", "narrow_per_opportunity"):
                rates[cls, name], influences[cls, name] = entry[name], influence
        classes[cls] = entry
    response, response_influences = {}, {}
    for name in ("narrow_given_completed", "narrow_per_opportunity"):
        narrow, broad = rates["narrow", name], rates["broad", name]
        if narrow is None or broad is None:
            response[name] = None
            response_influences[name] = None
        else:
            difference = narrow["estimate"]-broad["estimate"]
            influence = influences["narrow", name]-influences["broad", name]
            response[name] = dict(estimate=difference, se=describe(influence)["se"],
                                  uncertainty="paired life-cluster delta-method SE")
            response_influences[name] = influence
    report = dict(classes=classes, narrow_choice_response_to_narrow_cue=response,
                  scope="native class counters; observer readout, no phase/class input and no memory-mechanism claim")
    all_influences.update(response_influences)
    return (report, all_influences) if with_influence else report


def paired_ratio(new_value, old_value, new_influence, old_influence):
    if new_value is None or old_value is None:
        return None
    estimate = new_value["estimate"]-old_value["estimate"]
    se = describe(new_influence-old_influence)["se"]
    return dict(estimate=estimate, se=se, lower_3se=estimate-3*se, upper_3se=estimate+3*se,
                uncertainty="paired life-cluster delta-method SE", descriptive_only=True)


def analyze(study):
    protocol = read(study/"protocol.json")
    complete = read(study/"measurement_complete.json")
    index = read(study/"row_index.json")
    if (complete["status"] != "complete" or complete["research_lives"] != 14336
            or complete["startup_lives"] != 4 or complete["rows"] != 28
            or complete["protocol_sha256"] != sha(study/"protocol.json")
            or complete["row_index_sha256"] != sha(study/"row_index.json")
            or complete["endpoints_sha256"] != sha(study/"endpoints.json")):
        raise ValueError("complete fixed confirmation required")
    if tuple(protocol["roles"]) != ROLES or tuple(protocol["worlds"]) != WORLDS or not protocol["extinct_charge"]:
        raise ValueError("fixed four-role/seven-world matrix and extinction accounting required")
    seeds = protocol["seeds"]
    if len(seeds) != 512 or len(set(seeds)) != 512:
        raise ValueError("512 fresh paired seeds required")
    endpoints = read(study/"endpoints.json")
    rows, absolute, health, choice, choice_influence = {}, {}, {}, {}, {}
    expected_paths = {f"raw/{world}/row_{i:02d}.npz" for world in WORLDS for i in range(4)}
    if set(index) != expected_paths:
        raise ValueError("missing or extra confirmation row")
    for world in WORLDS:
        rows[world], absolute[world], health[world], choice[world] = {}, {}, {}, {}
        choice_influence[world] = {}
        for i, role in enumerate(ROLES):
            path = f"raw/{world}/row_{i:02d}.npz"
            entry = index[path]
            if (entry["status"] != "validated" or entry["lives"] != 512
                    or entry["sha256"] != sha(study/path)
                    or entry["scored_sha256"] != sha(study/entry["scored_path"])):
                raise ValueError("row index differs")
            with np.load(study/path, allow_pickle=False) as data:
                native = {key: data[key].copy() for key in data.files}
            with np.load(study/entry["scored_path"], allow_pickle=False) as data:
                scored = {key: data[key].copy() for key in data.files}
            for key, expected in (("world_name", world), ("role", role),
                                  ("protocol_sha256", sha(study/"protocol.json")),
                                  ("endpoints_sha256", sha(study/"endpoints.json")),
                                  ("genome_raw_sha256", endpoints["genomes"][i]["raw_sha256"])):
                if np.asarray(native[key]).item() != expected:
                    raise ValueError("native row identity differs: "+key)
            if str(scored["raw_sha256"]) != entry["sha256"]:
                raise ValueError("scored row is not bound to saved native output")
            native["production_F"] = scored["production_F"]
            metrics, checked = reconstruct(native, protocol["worlds"][world], seeds)
            if (not identical(scored["native_F"], metrics["native_F"])
                    or not identical(scored["extinct_charge"], metrics["extinct_charge"])):
                raise ValueError("scored native/extinction columns differ")
            rows[world][role], health[world][role] = metrics, checked
            absolute[world][role] = {key: describe(value) for key, value in metrics.items()}
            if protocol["worlds"][world]["world"]["task_mode"]:
                choice[world][role], choice_influence[world][role] = choice_readout(metrics, with_influence=True)
    paired, choice_paired, class_paired = {}, {}, {}
    for world in WORLDS:
        paired[world] = {}
        choice_paired[world] = {}
        class_paired[world] = {}
        for new, old in (("mixed24", "AO_start"), ("mixed24", "mixed8"),
                         ("mixed8", "AO_start"), ("mixed24", "AM_reference")):
            paired[world][new+"_minus_"+old] = {
                key: describe(rows[world][new][key]-rows[world][old][key]) for key in rows[world][new]}
            if choice[world]:
                contrasts = {}
                for name in ("narrow_given_completed", "narrow_per_opportunity"):
                    new_value = choice[world][new]["narrow_choice_response_to_narrow_cue"][name]
                    old_value = choice[world][old]["narrow_choice_response_to_narrow_cue"][name]
                    contrasts[name] = paired_ratio(new_value, old_value,
                        choice_influence[world][new][name], choice_influence[world][old][name])
                choice_paired[world][new+"_minus_"+old] = contrasts
                conditional = {}
                for cls in ("narrow", "broad"):
                    conditional[cls] = {}
                    for name in ("completion_coverage", "correct_per_opportunity", "accuracy_among_completed",
                                 "narrow_given_completed", "narrow_per_opportunity"):
                        conditional[cls][name] = paired_ratio(
                            choice[world][new]["classes"][cls][name], choice[world][old]["classes"][cls][name],
                            choice_influence[world][new][cls+"/"+name], choice_influence[world][old][cls+"/"+name])
                class_paired[world][new+"_minus_"+old] = conditional
    retention = {}
    for world in ("pool", "persistent", "blink80_20"):
        retention[world] = {}
        for candidate in ("mixed8", "mixed24"):
            for reference in ("AO_start", "AM_reference"):
                new, old = rows[world][candidate]["captures"], rows[world][reference]["captures"]
                margin = describe(new-.9*old)
                retention[world][candidate+"_vs_"+reference] = dict(
                    captures_difference=describe(new-old), retained_90_percent_margin=margin,
                    mean_capture_ratio=None if old.mean() == 0 else float(new.mean()/old.mean()),
                    lower_3se_positive=margin["lower_3se"] > 0, diagnostic_only_not_a_gate=True)
    return dict(status="complete", research_lives=14336, startup_lives=4, paired_life_clusters=512,
                absolute=absolute, paired=paired, health=health, choice_readouts=choice,
                paired_cue_response=choice_paired, old_world_retention=retention,
                paired_class_rates=class_paired,
                protocol_sha256=sha(study/"protocol.json"),
                row_index_sha256=sha(study/"row_index.json"),
                limitations=["Fixed genotypes and one continuation; seed SE does not estimate search reliability.",
                    "Matching captures/b2_clicks are physical narrow/broad slot hits, never reward correctness.",
                    "Class-conditioned choice response is descriptive; it does not isolate a memory mechanism.",
                    "Cue dependence may use persistent body or morphological state as well as neural dynamics.",
                    "All guards/extinction remain in fitness; physical costs and extinction surcharge are distinct.",
                    "Transfer and 90% old-world retention are diagnostics, not selection or replacement rules.",
                    "Missing rows or incomplete endpoints cannot support a complete-study inference."])


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
