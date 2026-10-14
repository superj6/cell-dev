"""Paired descriptive behavior from the archived confirmation ledgers; no life is simulated."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from src.life import analysis, readouts, spec  # noqa: E402

OUT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "results/pool_mutants_20261013"
CASES = ((5, "base", 38), (5, "pool", 38), (7, "base", 15), (7, "pool", 29))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean_contrast(parent, winner):
    return {"parent": analysis.summary(parent), "winner": analysis.summary(winner),
            "difference": analysis.paired(winner, parent)}


def paired_ratios(parent_num, parent_den, winner_num, winner_den):
    """Ratio of means in each genotype; paired influence functions give the contrast SE."""
    parent = readouts.ratio_of_means(parent_num, parent_den)
    winner = readouts.ratio_of_means(winner_num, winner_den)
    out = {"parent": parent, "winner": winner, "difference": None,
           "method": "Difference of ratios of means; delta-method SE retains all paired covariance."}
    if parent["value"] is None or winner["value"] is None:
        return out
    influence_parent = (parent_num - parent["value"] * parent_den) / np.mean(parent_den)
    influence_winner = (winner_num - winner["value"] * winner_den) / np.mean(winner_den)
    influence = influence_winner - influence_parent
    out["difference"] = {"mean": winner["value"] - parent["value"],
                         "se": float(np.std(influence, ddof=1) / np.sqrt(len(influence))),
                         "n": len(influence), "reliable_denominators": parent["reliable"] and winner["reliable"]}
    return out


def click_decomposition(parent_clicks, parent_caps, winner_clicks, winner_caps):
    """Symmetric arithmetic split of extra captures into volume and hit-fraction terms, not causal attribution."""
    cp, kp, cw, kw = map(np.asarray, (parent_clicks, parent_caps, winner_clicks, winner_caps))
    cpm, kpm, cwm, kwm = map(float, (cp.mean(), kp.mean(), cw.mean(), kw.mean()))
    if min(cpm, cwm) <= 0:
        return {"available": False, "reason": "a genotype has no clicks"}
    pp, pw = kpm / cpm, kwm / cwm
    dc, dp = cwm - cpm, pw - pp
    cm, pm = (cwm + cpm) / 2, (pw + pp) / 2
    icp, icw = cp - cpm, cw - cwm
    ipp, ipw = (kp - pp * cp) / cpm, (kw - pw * cw) / cwm
    volume, precision = dc * pm, cm * dp
    ivolume = (icw - icp) * pm + dc * (ipw + ipp) / 2
    iprecision = (icw + icp) * dp / 2 + cm * (ipw - ipp)

    def estimate(value, influence):
        return {"mean": float(value), "se": float(influence.std(ddof=1) / np.sqrt(len(influence))), "n": len(cp)}

    if not np.isclose(volume + precision, kwm - kpm, atol=1e-12, rtol=0):
        raise ValueError("click decomposition does not reconstruct extra captures")
    if not np.allclose(ivolume + iprecision, (kw - kp) - (kwm - kpm), atol=1e-12, rtol=0):
        raise ValueError("click decomposition influence functions do not sum correctly")
    return {"available": True, "extra_captures": analysis.paired(kw, kp),
            "click_volume_term": estimate(volume, ivolume), "hit_fraction_term": estimate(precision, iprecision),
            "formula": "Delta captures = Delta clicks * mean(hit fraction) + mean(clicks) * Delta hit fraction; "
                       "each mean here averages the two genotype-level ratios or count means.",
            "limitation": "Arithmetic description only. Changed trajectories and target replacement couple clicking, "
                          "occupancy and captures; these terms do not isolate tapping or steering mechanisms."}


def case_report(body, world, winner_row, provenance):
    prefix = f"screens/s{body}_{world}_T1024_b80/followup"
    paths = [f"{prefix}/confirm/scores.npz", f"{prefix}/manifest.json", f"{prefix}/selection.json"]
    hashes = {}
    for relative in paths:
        hashes[relative] = sha(ARCHIVE / relative)
        if hashes[relative] != provenance["artifacts"][relative]["sha256"]:
            raise ValueError(f"archive hash mismatch: {relative}")
    protocol = json.loads((ARCHIVE / paths[1]).read_text())
    selection = json.loads((ARCHIVE / paths[2]).read_text())
    if selection["winner_genome_row"] != winner_row or selection["winner_mutant_index"] != winner_row - 1:
        raise ValueError("frozen winner differs from expected row")
    with np.load(ARCHIVE / paths[0], allow_pickle=False) as stored:
        values = {key: stored[key].copy() for key in stored.files}
    seeds = values["seeds"]
    if not np.array_equal(seeds, protocol["seeds"]["confirm"]) or len(seeds) != 512:
        raise ValueError("confirmation life identities or counts differ")
    if values["genome_indices"].tolist() != [0, winner_row]:
        raise ValueError("confirmation genome order differs")
    for key in spec.V3.LEDGER:
        if values[key].shape != (2, len(seeds)) or not np.isfinite(values[key]).all():
            raise ValueError(f"invalid confirmation column: {key}")
    ledger = np.stack([values["F_kernel"] if key == "F" else values[key] for key in spec.V3.LEDGER], axis=-1)
    statuses = readouts.validate_ledger(ledger.reshape(-1, spec.V3.LEDGER_SIZE))
    duration = protocol["world"]["T"] - protocol["world"]["t_open"]
    if duration != 1024 or protocol["world"]["t_open"] != 0:
        raise ValueError("expected full-life T1024 confirmation")
    if not np.array_equal(values["window"], np.full((2, len(seeds)), duration)):
        raise ValueError("saved scoring windows differ")
    if (values["samples"] <= 0).any():
        raise ValueError("occupancy requires positive sample counts")
    means = {key: mean_contrast(values[key][0], values[key][1]) for key in
             ("F", "captures", "clicks", "misses", "path", "n_end", "n_S_end", "n_M_end", "n_H_end", "last_birth")}
    for key in ("live_time", "live_S", "live_M", "live_H"):
        means[key + "_per_unit_time"] = mean_contrast(values[key][0] / duration, values[key][1] / duration)
    ratios = {}
    for label, numerator, denominator in (
        ("capture_zone_sample_share", "zone_samples", "samples"),
        ("mean_sampled_target_distance", "dist_sum", "samples"),
        ("clicks_per_capture", "clicks", "captures"),
        ("captures_per_click", "captures", "clicks"),
        ("captures_per_cell_time", "captures", "live_time"),
    ):
        ratios[label] = paired_ratios(values[numerator][0], values[denominator][0],
                                     values[numerator][1], values[denominator][1])
    return {"body": f"s{body}", "world": world, "winner_genome_row": winner_row,
            "winner_sha256": selection["winner_sha256"], "seeds": seeds.tolist(), "n": len(seeds),
            "source_hashes": hashes, "status_counts": statuses, "means": means, "ratios": ratios,
            "click_decomposition": click_decomposition(values["clicks"][0], values["captures"][0],
                                                        values["clicks"][1], values["captures"][1]),
            "silence_distance": None, "relay_chains": None}


def main():
    # Synthetic algebra checks exercise covariance and the zero-denominator case without simulating a life.
    common = np.array([1.0, 10, 100])
    fixed = paired_ratios(common * 2, common, common * 3, common)
    assert fixed["difference"]["mean"] == 1 and fixed["difference"]["se"] == 0
    assert paired_ratios(common, common * 0, common, common)["difference"] is None
    decomposition = click_decomposition(common, common / 4, common * 2, common)
    assert decomposition["available"]
    provenance = json.loads((ARCHIVE / "provenance.json").read_text())
    cases = [case_report(*case, provenance) for case in CASES]
    report = {
        "format": 1, "analysis_only": True, "simulated_lives": 0, "runner_sha256": sha(Path(__file__)),
        "archive_provenance_sha256": sha(ARCHIVE / "provenance.json"), "cases": cases,
        "limitations": [
            "All readouts are retrospective descriptions of the same independent confirmation lives, not new evidence.",
            "Integer-time occupancy samples estimate time share; they are not exact continuous dwell time.",
            "A capture replaces the target, so occupancy and target distance also respond to success, not only steering.",
            "More travel does not by itself establish purposeful search; more cells can change sensing and movement.",
            "Cell-time and final counts do not match footprints; capture efficiency per cell-time is descriptive only.",
            "Silence distance and relay chains require full reference traces and cannot be recovered from these ledgers.",
            "No statistical threshold or new mechanism label is chosen from these secondary readouts.",
        ],
        "validation": "All source hashes, winner rows, ordered seeds, 512-life counts, ledger dimensions, statuses, "
                      "and T1024 windows checked. Paired-ratio covariance and exact click-decomposition algebra tested.",
    }
    path = OUT / "report.json"
    temp = path.with_suffix(".tmp.json")
    temp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    temp.replace(path)
    for case in cases:
        print(json.dumps({"case": f"{case['body']}_{case['world']}",
                          "zone_share_delta": case["ratios"]["capture_zone_sample_share"]["difference"],
                          "clicks_per_capture_delta": case["ratios"]["clicks_per_capture"]["difference"],
                          "capture_decomposition": case["click_decomposition"]}))


if __name__ == "__main__":
    main()
