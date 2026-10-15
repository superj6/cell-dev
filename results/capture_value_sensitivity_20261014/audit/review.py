"""Independent raw-ledger review of fixed AC post hoc capture-price sensitivity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check(ok, why):
    if not ok:
        raise ValueError(why)


def review(study, ac, root):
    study, ac, root = study.resolve(), ac.resolve(), root.resolve()
    summary = read(study / "summary.json")
    p = read(ac / "protocol.json")
    rolemap = read(ac / "confirmation_roles.json")
    labels = ["P_D90", "P_L92", "B_D90", "B_L92", "H_D90", "H_L92"]
    check(rolemap["roles"] == labels, "fixed role order changed")
    check(summary["capture_values"] == [500, 1000, 2000], "fixed price grid differs")
    check(summary["status"] == "complete_exploratory_repricing", "diagnostic is incomplete")
    check(summary["new_independent_evidence"] is False, "must label reused evidence")
    for key in ("new_simulated_lives", "new_genetic_draws", "new_compilations"):
        check(summary[key] == 0, "new work was not part of repricing")
    check(sha(study / "analyze.py") == summary["analysis_sha256"], "repricing source changed")
    check(sha(study / "PLAN.md") == summary["plan_sha256"], "declared post hoc plan changed")
    check(sha(study / "paired_vectors.npz") == summary["paired_vectors_sha256"], "saved vectors changed")
    for name, digest in {**summary["input_pins"], **summary["source_pins"]}.items():
        check(sha(root / name) == digest, "pinned input/source differs: " + name)
    rawrows, rawpins = {}, {}
    for world in ("flash", "blink"):
        w = p["worlds"][world]
        check((w["R_cap"], w["T"], w["t0"], w["t_open"], w["b2_amp"]) == (500, 1024, 0, 0, 0), "wrong raw world scope")
        prefix = ac / "measurement/confirm" / world
        index = read(prefix / "row_index.json")
        for i, label in enumerate(labels):
            name = f"confirm/row_{i:04d}.npz"
            path = prefix / name
            check(index[name]["sha256"] == sha(path), "raw row index changed")
            with np.load(path, allow_pickle=False) as f:
                x = f["ledger"].copy()
                identity = json.loads(str(f["identity"]))
                seeds = f["seeds"].copy()
                oldfitness = f["F"].copy()
            check(x.shape == (512, 58) and x.dtype == np.float64 and np.isfinite(x).all(), "raw ledger scope differs")
            check(np.all(x[:, 19] == 0), "this complete AC confirmation has no invalid/guard/extinct lives")
            check(
                identity["protocol_sha256"] == sha(ac / "protocol.json") and identity["world"] == world,
                "raw world identity differs",
            )
            check(
                identity["confirmation_roles_sha256"] == sha(ac / "confirmation_roles.json"), "raw role binding differs"
            )
            check(identity["genome_index"] == i and identity["roles"] == labels, "raw role index differs")
            check(identity["genome_sha256"] == rolemap["genotype_sha256"][label], "fixed genotype identity differs")
            check(np.array_equal(seeds, np.asarray(identity["seeds"], dtype=np.uint64)), "raw paired seeds differ")
            check(identity["seeds"] == p["seeds"]["confirm"], "registered confirmation seeds differ")
            # Independent literal native column mapping and native physical-cost order.
            cost = w["c_live"] * x[:, 1]
            for price, column in (
                ("c_spike", 3),
                ("c_tw", 4),
                ("c_msg", 5),
                ("c_div", 6),
                ("c_sec", 2),
                ("c_miss", 36),
                ("c_rec", 44),
            ):
                cost = cost + w[price] * x[:, column]
            cost = cost + max(0.0, -w["b2_value"]) * x[:, 38]
            guard = np.where((x[:, 19].astype(np.int64) & 6) != 0, w["c_live"] * w["n_max"] * (1024 - x[:, 18]), 0.0)
            extinction = (
                w["c_live"] * np.where((x[:, 19].astype(np.int64) & 1) != 0, 1024 - np.maximum(x[:, 34], 0), 0.0) / 1024
            )
            check(np.all(np.abs(cost - x[:, 12]) <= 1e-9 * np.maximum(1, np.abs(cost))), "raw physical cost differs")
            baseline = (500 * x[:, 35] - cost - guard) / 1024 - extinction
            check(baseline.tobytes() == oldfitness.tobytes(), "raw price500 production fitness differs")
            priced = {value: (value * x[:, 35] - cost - guard) / 1024 - extinction for value in (500, 1000, 2000)}
            rawrows[world, label] = dict(priced=priced, captures=x[:, 35], seeds=seeds, baseline=baseline)
            rawpins[str(path.relative_to(root))] = sha(path)
    expected, max_error, exact_linear = set(), 0.0, 0
    with np.load(study / "paired_vectors.npz", allow_pickle=False) as stored:
        for world in ("flash", "blink"):
            for background in ("D90", "L92"):
                for left, right in (("H", "P"), ("B", "P"), ("H", "B")):
                    a, b = rawrows[world, left + "_" + background], rawrows[world, right + "_" + background]
                    check(np.array_equal(a["seeds"], b["seeds"]), "contrast lost pairing")
                    comparison = f"{left}_{background}_minus_{right}_{background}"
                    for value in (500, 1000, 2000):
                        key = f"R{value}__within__{world}__{comparison}"
                        expected.add(key)
                        direct = a["priced"][value] - b["priced"][value]
                        got = stored[key]
                        check(got.dtype == np.float64 and got.shape == (512,), "repriced vector shape/type differs")
                        error = float(np.max(np.abs(direct - got)))
                        max_error = max(error, max_error)
                        check(np.allclose(direct, got, rtol=0, atol=2e-12), "direct full-fitness repricing differs")
                        # Also recover the author's arithmetic order from raw-only quantities.
                        linear = (
                            a["baseline"]
                            - b["baseline"]
                            + (value / 500 - 1) * (500 * a["captures"] - 500 * b["captures"]) / 1024
                        )
                        check(linear.tobytes() == got.tobytes(), "raw-only linear identity is not byte-exact")
                        exact_linear += 1
                        item = summary["comparisons"][key]
                        mean, se = float(direct.mean()), float(direct.std(ddof=1) / np.sqrt(512))
                        check(
                            abs(item["mean_F_change"] - mean) <= 2e-12 and abs(item["paired_se"] - se) <= 2e-12,
                            "summary statistics differ",
                        )
                        check(
                            item["above_3se"] == (mean > 3 * se) and item["below_minus_3se"] == (mean < -3 * se),
                            "strict sign threshold differs",
                        )
                        check(
                            (item["capture_value"], item["world"], item["comparison"], item["n"])
                            == (value, world, comparison, 512),
                            "contrast metadata differs",
                        )
        check(
            set(stored.files) == expected == set(summary["comparisons"]) and len(expected) == 36,
            "all12 contrasts×3 prices required",
        )
    return dict(
        status="approved_independent_raw_review",
        author_summary_sha256=sha(study / "summary.json"),
        author_script_sha256=sha(study / "analyze.py"),
        author_vectors_sha256=sha(study / "paired_vectors.npz"),
        review_source_sha256=sha(Path(__file__)),
        raw_row_pins=rawpins,
        raw_rows_checked=12,
        paired_lives=512,
        all_fixed_within_world_contrasts=12,
        price_grid=[500, 1000, 2000],
        vectors_checked=36,
        direct_repricing_max_absolute_roundoff=max_error,
        raw_only_linear_vectors_bitwise_equal=exact_linear,
        source_pins=summary["source_pins"],
        simulations=0,
        compilations=0,
        new_genomes_selected=False,
        source_review={
            "R_cap": "Native kernel field is assigned from W_RCAP and only read to add capture income. Income is read only in final net/ledger accounting; no organism or physics input reads it.",
            "extinction": "Evaluator uses c_live×uncounted remaining lifetime/window; independent of capture value. Actual AC confirmation statuses are all zero.",
            "guard": "Native guard charge depends on c_live,n_max,remaining lifetime; independent of R_cap.",
            "hashes": "Income/fitness ledger values and overall hashes could change under a repriced execution; physical trajectories are the intended invariance, not all output bytes.",
        },
        limitations_review={
            "post_hoc": True,
            "not_fresh_evidence": True,
            "same_observations_and_pairing": True,
            "no_new_selection": True,
            "no_claim_about_evolution_under_new_prices": True,
            "no_production_prices_changed": True,
        },
        limits=[
            "This reviews fixed observed outcomes, not a new native run or fresh confirmation.",
            "The diagnostic does not estimate what genomes would be selected by a different objective.",
            "Two algebraically equivalent operation orders differ only by recorded floating roundoff.",
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--ac", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = review(args.study, args.ac, args.root)
    with args.out.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({"status": result["status"], "vectors": result["vectors_checked"], "receipt_sha256": sha(args.out)})
    )
