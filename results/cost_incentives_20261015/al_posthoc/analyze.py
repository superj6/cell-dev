"""Post hoc AL score sensitivity on fixed completed lives; no engine or evolution calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").is_file())
STUDY = ROOT / "outputs/autonomous_retention_selection_20261015"
HELPER = ROOT / "outputs/audit_retention_selection_20261015/terminal_review/verify_terminal_raw.py"
HELPER_SHA = "d0ba8b184e336e673e0f43cd0850d32af7a71eb4bb628edaf06962f0716d97a7"
PROTOCOL_SHA = "25575f9ef690d00741fea0c62570d15aeb526d66a13a42025a91c5cd2fad19bf"
ROLES = ("AI_control_start", "persistent_control_final", "mixture_final")
WORLDS = ("pool", "persistent", "blink80_5", "turn100_blink80_5")
SCALES = {"ordinary_uniform": (.25, .5, 1., 2.), "living_only": (.25, .5, 1.),
          "spike_and_message_only": (.25, .5, 1.)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def stats(values):
    mean, se = float(values.mean()), float(values.std(ddof=1) / math.sqrt(len(values)))
    return {"n": len(values), "mean": mean, "se": se, "lower_3se": mean - 3 * se,
            "upper_3se": mean + 3 * se, "positive_above_3se": mean > 3 * se,
            "negative_below_minus_3se": mean < -3 * se}


def selected_charge(row, family):
    if family == "ordinary_uniform":
        return -row["ordinary_cost"]
    if family == "living_only":
        return -row["cost__living"]
    if family == "spike_and_message_only":
        return -(row["cost__spiking"] + row["cost__messages"])
    raise ValueError("unexpected scenario")


def csv_write(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=STUDY)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    study = args.study.resolve()
    if sha(HELPER) != HELPER_SHA or sha(study / "protocol.json") != PROTOCOL_SHA:
        raise ValueError("frozen source/protocol differs")
    prior = read(study / "terminal_review/independent/independent_raw_review.json")
    if (prior["status"] != "passed" or prior["max_literal_absolute_error"] != 0
            or prior["literal_vectors_checked"] != 2254
            or prior["budget_sha256"] != sha(study / "budget.json")
            or prior["canonical_summary_sha256"] != sha(study / "analysis_result/summary.json")):
        raise ValueError("completed independent raw validation required")
    spec = importlib.util.spec_from_file_location("AL_literal_source", HELPER)
    literal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(literal)
    protocol = read(study / "protocol.json")
    if any(w["world"]["R_cap"] != 500 for w in protocol["worlds"].values()):
        raise ValueError("capture reward must remain500")
    rows, statuses, _ = literal.recount(study, protocol)
    if any(counts != {"0": 256} for world in statuses.values() for counts in world.values()):
        raise ValueError("this completed AL sensitivity expects all observed penalties zero")
    args.out.mkdir(parents=True, exist_ok=False)
    categories = ("living", "spiking", "twitching", "messages", "division", "secretion",
                  "missed_clicks", "receptors", "decoy_clicks")
    contributions, paired_contributions, counterfactual, arrays, break_even = [], [], [], {}, []
    absolute, contrasts = {}, {}
    pairs = ((1, 0), (2, 0), (2, 1))  # Last is a secondary policy comparison, already in AL.
    for world in WORLDS:
        absolute[world], contrasts[world] = {}, {}
        for role in ROLES:
            row = rows[world][role]
            cost = -row["ordinary_cost"]
            living, communication = selected_charge(row, "living_only"), selected_charge(row, "spike_and_message_only")
            contribution = {"world": world, "role": role,
                "captures_mean": float(row["captures"].mean()), "captures_se": stats(row["captures"])["se"],
                "original_F_mean": float(row["F"].mean()), "capture_income_per_time": float(row["capture_income"].mean()),
                "ordinary_charge_per_time": float(cost.mean()),
                "living_fraction_of_mean_ordinary_cost": float(living.mean() / cost.mean()),
                "spike_message_fraction_of_mean_ordinary_cost": float(communication.mean() / cost.mean()),
                "guard_charge_per_time": float((-row["guard_cost"]).mean()),
                "extinction_charge_per_time": float((-row["extinction_cost"]).mean()),
                "n_end_mean": float(row["n_end"].mean()), "live_time_mean": float(row["live_time"].mean()),
                "spikes_mean": float(row["spikes"].mean()), "message_events_mean": float(row["contact_events"].mean())}
            contribution.update({"charge_" + c: float((-row["cost__" + c]).mean()) for c in categories})
            contributions.append(contribution)
            absolute[world][role] = {"original_F": stats(row["F"]), "captures": stats(row["captures"]), "scenarios": {}}
            for family, scales in SCALES.items():
                charge = selected_charge(row, family)
                for scale in scales:
                    values = row["F"] + (1 - scale) * charge
                    key = f"{family}__{scale:g}"
                    absolute[world][role]["scenarios"][key] = stats(values)
                    arrays[f"absolute__{world}__{role}__{key}"] = values
                    if scale == 1 and not np.array_equal(values, row["F"]):
                        raise ValueError("original-price score changed")
        for a, b in pairs:
            new, old = ROLES[a], ROLES[b]
            left, right = rows[world][new], rows[world][old]
            delta = left["F"] - right["F"]
            name = f"{new}_minus_{old}"
            contrast = {"original_F": stats(delta), "captures": stats(left["captures"] - right["captures"]),
                        "scenarios": {}, "mean_break_even_scales": {}}
            paired = {"world": world, "contrast": name,
                      "captures_mean": contrast["captures"]["mean"], "captures_se": contrast["captures"]["se"],
                      "original_F_mean": float(delta.mean()), "original_F_se": stats(delta)["se"]}
            for component in ("capture_income", "ordinary_cost", "guard_cost", "extinction_cost", *["cost__" + c for c in categories]):
                values = left[component] - right[component]
                paired[component + "_mean"] = float(values.mean())
                paired[component + "_se"] = stats(values)["se"]
            paired_contributions.append(paired)
            for family, scales in SCALES.items():
                difference_in_charge = selected_charge(left, family) - selected_charge(right, family)
                slope = float(difference_in_charge.mean())
                crossing = 1 + float(delta.mean()) / slope if slope != 0 else None
                contrast["mean_break_even_scales"][family] = crossing
                break_even.append({"world": world, "contrast": name, "family": family,
                                   "mean_score_crossing_scale": crossing,
                                   "score_difference_slope": -slope,
                                   "interpretation": "Point-estimate crossing of these fixed recorded endpoints, not an optimum."})
                for scale in scales:
                    values = delta + (1 - scale) * difference_in_charge
                    key = f"{family}__{scale:g}"
                    summary = stats(values)
                    contrast["scenarios"][key] = summary
                    arrays[f"paired__{world}__{name}__{key}"] = values
                    counterfactual.append({"world": world, "contrast": name, "family": family, "scale": scale, **summary})
            contrasts[world][name] = contrast
    # Reconstruct original mean F from the independently priced components for every role/seed.
    for world in WORLDS:
        for role in ROLES:
            row = rows[world][role]
            if not np.allclose(row["F"], sum(row[k] for k in ("capture_income", "ordinary_cost", "guard_cost", "extinction_cost")), rtol=0, atol=1e-9):
                raise ValueError("original-price decomposition differs")
    metadata = {
        "status": "complete_posthoc_fixed_trajectory_sensitivity", "protocol_sha256": PROTOCOL_SHA,
        "script_sha256": sha(Path(__file__)), "literal_source_sha256": HELPER_SHA,
        "validated_raw_review_sha256": sha(study / "terminal_review/independent/independent_raw_review.json"),
        "raw_inputs": {name: {"path": str((study / name).relative_to(ROOT)), "sha256": rec["sha256"]}
                       for name, rec in read(study / "row_index.json").items()},
        "roles": list(ROLES), "worlds": list(WORLDS), "paired_seeds": 256, "raw_lives": 3072,
        "scenarios": {k: list(v) for k, v in SCALES.items()}, "capture_value_fixed": 500,
        "formula": "F_counter = F_original + (1-scale) * selected_original_charge_per_time",
        "guard_and_extinction_policy": "Held at original values; all3072 observed AL lives have zero guard/extinction charges. A true c_live change also reprices those penalties, but here the numerical answer is identical.",
        "cost_fraction_definition": "Ratio of mean category charge to mean ordinary charge, not mean per-life ratios.",
        "paired_uncertainty": "Compute each per-seed counterfactual difference before its SE; covariance is retained.",
        "absolute": absolute, "contrasts": contrasts, "paired_and_absolute_vectors": len(arrays),
        "limitations": ["Chosen post hoc after AL; these are descriptive sensitivities, not preregistered outcomes.",
            "The original physical ledgers and production fitness remain unchanged.",
            "Repricing recorded lives does not predict which genotypes would evolve or their trajectories under another selection incentive.",
            "No optimal universal cost value is estimated; a mean endpoint crossing is not a biological or statistical optimum.",
            "Cheaper maintenance may favor larger bodies; more cells/spikes/messages do not themselves establish sophisticated algorithms.",
            "One paired search, not256 evolutionary replications; three-SE bounds are descriptive and not multiplicity adjusted."],
        "new_simulations": 0, "compiler_calls": 0, "genetic_draws": 0, "production_prices_changed": False}
    (args.out / "summary.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    np.savez_compressed(args.out / "paired_arrays.npz", **arrays)
    csv_write(args.out / "absolute_cost_contributions.csv", contributions)
    csv_write(args.out / "paired_cost_contributions.csv", paired_contributions)
    csv_write(args.out / "counterfactual_scores.csv", counterfactual)
    csv_write(args.out / "mean_score_crossings.csv", break_even)
    print(json.dumps({"status": metadata["status"], "raw_lives": 3072, "vectors": len(arrays), "new_simulations": 0}))


if __name__ == "__main__":
    main()
