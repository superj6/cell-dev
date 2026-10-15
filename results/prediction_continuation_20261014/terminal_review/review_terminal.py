"""Independent AF terminal raw recount; requires explicit root terminal-clearance digest.

Standard library and NumPy only. Does not import the released reader, accountant,
worker, engine or genetic helper. Never creates a partial scientific receipt. Dry-run default opens no study artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

PROTOCOL = "ebdc3f37dc5d9a882b2b7d68ed3913a08540be4f476bdd6cf4b6c446e315b5e0"
LABELS = ("AE_D90", "AE_L92", "AF_D90", "AF_L92")
BACKGROUNDS = ("D90", "L92")
WORLDS = ("persistent",)
LEDGER = (
    "income",
    "live_time",
    "sec_int",
    "spikes",
    "kappa_sum",
    "contact_events",
    "claims",
    "births",
    "rejects",
    "rejects_wall",
    "deaths",
    "kills",
    "cost",
    "guard_charge",
    "net",
    "F",
    "n_end",
    "n_peak",
    "t_end",
    "status",
    "events",
    "beats",
    "P_int",
    "arrivals",
    "arrivals_dropped",
    "packets",
    "morph_secreted",
    "morph_decayed",
    "morph_lost",
    "morph_content_end",
    "morph_inflight_end",
    "chem_clamps",
    "last_birth",
    "ticks",
    "t_ext",
    "captures",
    "misses",
    "clicks",
    "b2_clicks",
    "respawns",
    "nudges",
    "rec_cand",
    "rec_accept",
    "rec_events",
    "rec_gain",
    "samples",
    "dist_sum",
    "zone_samples",
    "path",
    "X_end",
    "Y_end",
    "n_S_end",
    "n_M_end",
    "n_H_end",
    "live_S",
    "live_M",
    "live_H",
)
COLS = LEDGER + ("F_kernel", "extinct_charge", "window")
PRICES = (
    ("living", "live_time", "c_live"),
    ("spiking", "spikes", "c_spike"),
    ("twitching", "kappa_sum", "c_tw"),
    ("messages", "contact_events", "c_msg"),
    ("division", "claims", "c_div"),
    ("secretion", "sec_int", "c_sec"),
    ("missed_clicks", "misses", "c_miss"),
    ("receptors", "rec_gain", "c_rec"),
)
COUNTS = (
    "spikes",
    "contact_events",
    "claims",
    "births",
    "rejects",
    "rejects_wall",
    "deaths",
    "kills",
    "n_end",
    "n_peak",
    "status",
    "events",
    "beats",
    "arrivals",
    "arrivals_dropped",
    "packets",
    "chem_clamps",
    "ticks",
    "captures",
    "misses",
    "clicks",
    "b2_clicks",
    "respawns",
    "nudges",
    "rec_cand",
    "rec_accept",
    "rec_events",
    "samples",
    "zone_samples",
    "n_S_end",
    "n_M_end",
    "n_H_end",
)


def check(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw(value):
    return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def npz(path):
    with np.load(path, allow_pickle=False) as saved:
        check(len(saved.files) == len(set(saved.files)), "duplicate NPZ field")
        return {key: saved[key].copy() for key in saved.files}


def same(a, b):
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def stats(v):
    check(v.ndim == 1 and len(v) > 1 and np.isfinite(v).all(), "invalid paired vector")
    return {"mean": float(v.mean()), "se": float(v.std(ddof=1) / np.sqrt(len(v))), "n": len(v)}


def check_stats(saved, value):
    actual = stats(value)
    check(saved["n"] == actual["n"], "summary sample count differs")
    check(
        all(np.isclose(saved[key], actual[key], rtol=1e-12, atol=1e-12) for key in ("mean", "se")),
        "summary mean or SE differs from raw paired vector",
    )
    for flag, expected in (
        ("positive_above_3se", actual["mean"] > 3 * actual["se"]),
        ("negative_below_minus_3se", actual["mean"] < -3 * actual["se"]),
    ):
        if flag in saved:
            check(saved[flag] == expected, "summary directional flag differs")


def operation(base, name):
    path = base / name
    return path if path.is_file() else base / "operations" / name


def external(base, name):
    check(not Path(name).is_absolute() and ".." not in Path(name).parts, "unsafe external pin")
    for root in (base / "production", base / "original", base.parents[1]):
        path = root / name
        if path.is_file():
            return path
    raise FileNotFoundError(name)


def physical(row, world, n):
    """Reconstruct actual charges directly from the literal raw ledger columns."""
    led = row["ledger"]
    check(led.dtype == np.float64 and led.shape == (n, 57) and np.isfinite(led).all(), "raw57 ledger differs")
    check(world["t0"] == world["t_open"] == 0 and world["T"] == 1024, "full-life1024 scope differs")
    for j, key in enumerate(LEDGER):
        value = row["F_kernel" if key == "F" else key]
        check(same(value, led[:, j]), "raw/named ledger mismatch: " + key)
    for key in COLS:
        check(row[key].shape == (n,) and np.isfinite(row[key]).all(), "invalid scored column: " + key)
    for key in COUNTS:
        check(np.all(row[key] == np.floor(row[key])) and np.all(row[key] >= 0), "invalid count: " + key)
    for key in LEDGER:
        if key not in {"F", "net", "t_end", "last_birth", "t_ext", "X_end", "Y_end"}:
            check(np.all(row[key] >= 0), "negative physical quantity: " + key)
    status = row["status"].astype(np.int64)
    check(np.all(status <= 511) and not np.any(status & (64 | 128)), "invalid implementation status")
    guard, extinct = (status & 6) != 0, (status & 1) != 0
    check(np.all((row["t_end"] >= 0) & (row["t_end"] <= 1024)), "end time outside life")
    check(np.all(row["t_end"][~(guard | extinct)] == 1024), "unexplained partial life")
    check(np.all((row["last_birth"] >= 0) & (row["last_birth"] <= row["t_end"])), "last birth outside life")
    check(np.all(row["t_ext"][~extinct] == -1), "unexplained extinction time")
    check(
        np.all((row["t_ext"][extinct] >= 0) & (row["t_ext"][extinct] <= row["t_end"][extinct])),
        "invalid extinction time",
    )
    check(np.all(row["n_end"][extinct] == 0), "extinct life retains cells")
    check(np.all(row["window"] == 1024) and np.all(row["b2_clicks"] == 0), "window or single-target scope differs")
    check(np.array_equal(1 + row["births"] - row["deaths"] - row["kills"], row["n_end"]), "full-life census mismatch")
    check(np.array_equal(row["captures"] + row["misses"], row["clicks"]), "click reconciliation failed")
    check(np.array_equal(row["n_S_end"] + row["n_M_end"] + row["n_H_end"], row["n_end"]), "plane census mismatch")
    check(
        np.allclose(row["live_S"] + row["live_M"] + row["live_H"], row["live_time"], rtol=1e-9, atol=1e-9),
        "plane cell-time mismatch",
    )
    morph = row["morph_decayed"] + row["morph_lost"] + row["morph_content_end"] + row["morph_inflight_end"]
    check(np.allclose(morph, row["morph_secreted"], rtol=1e-9, atol=1e-9), "morphogen conservation failed")
    for lower, upper in (
        ("rec_events", "rec_accept"),
        ("rec_accept", "rec_cand"),
        ("zone_samples", "samples"),
        ("n_end", "n_peak"),
    ):
        check(np.all(row[lower] <= row[upper]), "physical count inequality failed: " + lower)
    parts = {name: row[column] * world[price] for name, column, price in PRICES}
    parts["decoy_clicks"] = max(0.0, -world["b2_value"]) * row["b2_clicks"]
    total = parts["living"].copy()
    for name in list(parts)[1:]:
        total = total + parts[name]
    check(np.all(np.abs(row["cost"] - total) <= 1e-9 * np.maximum(1, np.abs(total))), "ordinary physical cost mismatch")
    income = world["R_cap"] * row["captures"]
    guard_charge = np.where(guard, world["c_live"] * world["n_max"] * (1024 - row["t_end"]), 0.0)
    extinction_charge = world["c_live"] * np.where(extinct, 1024 - np.maximum(row["t_ext"], 0), 0.0) / 1024
    net = income - total - guard_charge
    for name, value in (
        ("income", income),
        ("guard_charge", guard_charge),
        ("net", net),
        ("F_kernel", net / 1024),
        ("extinct_charge", extinction_charge),
    ):
        check(np.allclose(row[name], value, rtol=1e-10, atol=1e-9), "independent charge mismatch: " + name)
    check(same(row["F"], row["F_kernel"] - row["extinct_charge"]), "production extinction charge mismatch")
    for key in ("cpu_seconds", "wall_seconds"):
        check(row[key].shape == () and np.isfinite(row[key]) and row[key] >= 0, "invalid scalar timing")
    values, counts = np.unique(status, return_counts=True)
    health = {"status_histogram": {str(k): int(v) for k, v in zip(values, counts)}, "all_fitness_rows_retained": n}
    return parts, total, health


def recount(base, clearance_sha):
    # Do not open runtime artifacts before the root's exact terminal clearance.
    clearance_path = operation(base, "terminal_process_clearance.json")
    check(sha(clearance_path) == clearance_sha, "root terminal-clearance digest required")
    clearance = read(clearance_path)
    budget_path = operation(base, "budget.json")
    check(clearance["status"] == "cleared" and clearance["all_processes_exited"] is True, "not cleared")
    check(clearance["budget_sha256"] == sha(budget_path), "clearance/budget binding differs")
    budget = read(budget_path)
    check(
        budget["status"] == "complete" and budget["exit_code"] == 0 and not budget["running"] and not budget["queued"],
        "not complete",
    )
    check(not any(budget.get(k) for k in ("reason", "error", "cleanup_error")), "terminal failure")
    check(
        clearance["processes"] == budget["process_identities"]
        and clearance["process_groups"] == budget["owned_process_groups"],
        "cleared identity/group set differs",
    )
    check(
        budget["cap_cpu_seconds"] == 5400
        and budget["search_cpu_seconds"] == 3400
        and budget["confirmation_reserved_cpu_seconds"] == 2000
        and budget["phase"] == "confirmation",
        "CPU contract differs",
    )
    total, search = budget["cpu_seconds"], budget["search_stage_cpu_seconds"]
    check(
        np.isfinite(total) and np.isfinite(search) and 0 <= search < 3390 and search <= total < 5390,
        "phase CPU differs",
    )
    check(sha(base / "protocol.json") == PROTOCOL, "protocol differs")
    p, ready = read(base / "protocol.json"), read(operation(base, "ready.json"))
    workers = ["evolve_s" + str(seed) for seed in p["runs"]] + ["confirmation"]
    leaders = budget["process_identities"]
    check([x["name"] for x in leaders] == ["monitor"] + workers, "four leader identities differ")
    completed = budget["completed"]
    check(
        len(completed) == 3
        and completed[-1] == {"name": "confirmation", "exit_code": 0}
        and {x["name"] for x in completed[:2]} == set(workers[:2])
        and all(x["exit_code"] == 0 for x in completed),
        "both searches must finish before confirmation",
    )
    for child in leaders[1:]:
        check(child["ppid"] == leaders[0]["pid"] and child["pid"] == child["pgid"], "owned child differs")
    check(
        len({x["pid"] for x in leaders}) == 4 and budget["owned_process_groups"] == [x["pgid"] for x in leaders[1:]],
        "owned groups differ",
    )
    check(
        all(type(x[k]) is int and x[k] > 0 for x in leaders for k in ("pid", "pgid", "start_ticks")), "identity invalid"
    )
    attempt = read(operation(base, "attempt.json"))
    check(
        attempt["monitor"] == {k: leaders[0][k] for k in ("pid", "ppid", "pgid", "start_ticks")},
        "attempt owner differs",
    )
    check(
        ready["status"] == "released"
        and budget["ready"] == ready
        and attempt["ready_sha256"] == sha(operation(base, "ready.json")),
        "release differs",
    )
    check(
        ready["production_pins"] == p["production_pins"]
        and all(ready["source_pins"].get(k) == v for k, v in p["file_pins"].items()),
        "release closure differs",
    )
    for name, digest in ready["source_pins"].items():
        check(sha(operation(base, name)) == digest, "local release bytes changed: " + name)
    for name, digest in ready["production_pins"].items():
        check(sha(external(base, name)) == digest, "production bytes changed: " + name)
    summary = read(base / "analysis_result/summary.json")
    check(
        summary["status"] == "complete"
        and summary["protocol_sha256"] == PROTOCOL
        and summary["ledger_columns"] == list(LEDGER),
        "complete ABI3 reader summary required",
    )
    check(
        summary["research_lives"] == 10316
        and summary["startup_validation_lives"] == 6
        and summary["total_lives"] == 10322,
        "scope count differs",
    )
    endpoint = read(base / "confirmation/endpoints.json")
    check(
        endpoint["protocol_sha256"] == PROTOCOL
        and endpoint["labels"] == list(LABELS)
        and endpoint["seeds"] == p["confirmation"]["seeds"]
        and endpoint["world"] == p["world"]
        and endpoint["ready"] == ready,
        "endpoint identity differs",
    )
    numeric = p["expected_numerical_identity"]
    check(
        endpoint["numerical_identity"] == numeric
        and numeric["golden"]
        == {
            "all": "ebb3ad6fcad2d938",
            "ledger_sha256": "b622f9afad48d6ec5b39b003efba82f25e7e6a764a015fe40398b3a6bbd81251",
        },
        "confirmation numerical receipt differs",
    )
    check(set(numeric["kernels"]) == {"False", "True"}, "full/fast library coverage differs")
    check(
        set(numeric["kernels"].values()).issubset({sha(x) for x in (base / "build-cache").rglob("*.so")}),
        "retained numerical libraries missing",
    )
    table = npz(base / "confirmation/genotypes.npz")
    check(set(table) == {"genomes", "labels"} and same(table["labels"], np.asarray(LABELS)), "genotype roles differ")
    genomes = table["genomes"]
    check(
        genomes.shape == (4, 875) and genomes.dtype == np.float32 and np.isfinite(genomes).all(),
        "genotype matrix differs",
    )
    check(endpoint["genotype_sha256"] == dict(zip(LABELS, map(raw, genomes))), "genotype raw binding differs")
    fields = ("W", "b", "lam", "s0", "Q", "act", "A", "a0", "Dm", "km")
    native = {}
    for i, seed in enumerate(p["runs"]):
        key = str(seed)
        folder = base / f"runs/s{seed}"
        founder = read(base / p["reference_files"][i])["params"]
        original = np.concatenate([np.asarray(founder[k], dtype=np.float32).reshape(-1) for k in fields])
        check(
            same(original, genomes[i]) and raw(original) == p["founder_mapping"][key]["raw_sha256"],
            "fixed AE start differs",
        )
        check(read(folder / "determinism.json") == numeric, "native numerical receipt differs")
        binding = endpoint["endpoints"][key]
        check(
            binding["generation"] == 4
            and binding["rank"] == 0
            and binding["checkpoint_sha256"] == sha(folder / "checkpoint.pt")
            and binding["genome_file_sha256"] == sha(folder / "best_genome.json")
            and binding["genome_raw_sha256"] == raw(genomes[i + 2]),
            "final rank-zero metadata differs",
        )
        for name, digest in binding["log_pins"].items():
            check(sha(folder / name) == digest, "native log binding differs")
        best = read(folder / "best_genome.json")["params"]
        final = np.concatenate([np.asarray(best[k], dtype=np.float32).reshape(-1) for k in fields])
        check(same(final, genomes[i + 2]), "confirmation final genome differs")
        curves = [json.loads(line) for line in (folder / "curves.jsonl").read_text().splitlines() if line.strip()]
        check(
            [x["gen"] for x in curves] == [0, 1, 2, 3] and [x["gen"] for x in curves if "valid" in x] == [0, 3],
            "native generation/validation coverage differs",
        )
        for x in curves:
            check(
                all(np.isfinite(x[k]) and x[k] == 0 for k in ("pop_invalid", "pop_mismatch", "recheck_invalid")),
                "native invalid/mismatch health",
            )
        initial_guards = [round(x["pop_guard"] * 768) for x in curves]
        check(
            all(np.isclose(x["pop_guard"] * 768, n, rtol=0, atol=1e-8) for x, n in zip(curves, initial_guards)),
            "native guard frequency differs",
        )
        checked = summary["native_audit"]["runs"][key]
        check(
            checked["status"] == "passed"
            and checked["checkpoint_sha256"] == sha(folder / "checkpoint.pt")
            and checked["genome_raw_sha256"] == raw(final)
            and checked["final_rank_zero_binding"] is True
            and checked["all_final_population_rows_bound"] is True
            and checked["initial_evaluation_guard_lives_by_generation"] == initial_guards,
            "full reader native replay binding differs",
        )
        native[key] = {
            "initial_search_lives": 3072,
            "recheck_lives": 1024,
            "validation_lives": 32,
            "tiny_final_lives": 6,
            "initial_guard_lives_by_generation": initial_guards,
            "final_rank_zero_sha256": raw(final),
            "full_reader_genetic_replay": checked["genetic_replay"],
        }
    folder = base / "confirmation"
    index = read(folder / "row_index.json")
    names = {f"persistent/row_{i:04d}.npz" for i in range(4)}
    check(
        set(index) == names and {str(x.relative_to(folder)) for x in folder.rglob("row_*.npz")} == names,
        "four complete rows required",
    )
    rows, parts, totals, health, rawpins = {}, {}, {}, {}, {}
    cpu = 0.0
    for i, label in enumerate(LABELS):
        relative = f"persistent/row_{i:04d}.npz"
        path = folder / relative
        check(sha(path) == index[relative]["sha256"], "indexed row hash differs")
        r = npz(path)
        check(
            set(r) == set(COLS) | {"identity", "seeds", "genome_index", "ledger", "cpu_seconds", "wall_seconds"},
            "row fields differ",
        )
        expected = {
            "protocol_sha256": PROTOCOL,
            "stage": "confirmation",
            "endpoints_sha256": sha(folder / "endpoints.json"),
            "role": label,
            "genome_index": i,
            "genome_sha256": raw(genomes[i]),
            "seeds": p["confirmation"]["seeds"],
        }
        check(
            r["identity"].shape == ()
            and str(r["identity"]) == json.dumps(expected, sort_keys=True, separators=(",", ":")),
            "raw identity differs",
        )
        check(
            r["genome_index"].shape == ()
            and int(r["genome_index"]) == i
            and same(r["seeds"], np.asarray(p["confirmation"]["seeds"], dtype=np.uint64)),
            "row seed/index differs",
        )
        parts[i], totals[i], health[label] = physical(r, p["world"], 512)
        check(float(r["cpu_seconds"]) == index[relative]["cpu_seconds"], "row CPU differs")
        rows[i] = r
        cpu += float(r["cpu_seconds"])
        rawpins[str(path.relative_to(base))] = sha(path)
        statuses = r["status"].astype(np.int64)
        expected_health = {
            name: int(np.count_nonzero(statuses & mask))
            for name, mask in {
                "extinct": 1,
                "guard_cells": 2,
                "guard_events": 4,
                "mismatch": 64,
                "capacity": 128,
            }.items()
        }
        check(summary["confirmation_health"][label] == expected_health, "summary health differs")
        for k in COLS:
            check_stats(summary["absolute_means"][label][k], r[k])
    score = npz(folder / "persistent/scores.npz")
    check(
        set(score) == set(COLS) | {"seeds", "genome_indices"}
        and same(score["seeds"], rows[0]["seeds"])
        and same(score["genome_indices"], np.arange(4)),
        "aggregate identity differs",
    )
    for k in COLS:
        check(same(score[k], np.stack([rows[i][k] for i in range(4)])), "aggregate/raw mismatch: " + k)
    report = read(folder / "report.json")
    for k, v in {
        "status": "complete",
        "genome_lives": 2048,
        "paired_seeds": 512,
        "confirmation_startup_validation_lives": 2,
        "protocol_sha256": PROTOCOL,
        "endpoints_sha256": sha(folder / "endpoints.json"),
        "genotypes_sha256": sha(folder / "genotypes.npz"),
    }.items():
        check(report[k] == v, "worker coverage differs: " + k)
    check(
        np.isclose(report["row_cpu_seconds"], cpu, rtol=0, atol=1e-6) and cpu <= total - search + 1e-6,
        "row CPU outside owned confirmation phase",
    )
    check(
        set(summary["contrasts"]) == {"primary"}
        and set(summary["contrasts"]["primary"]) == set(LABELS[2:])
        and set(report["primary"]) == set(LABELS[2:]),
        "exact primary contrasts differ",
    )
    vectors, compact = {}, {}
    for a, b in ((2, 0), (3, 1)):
        delta = {k: rows[a][k] - rows[b][k] for k in COLS}
        pieces = {
            "capture_income": (rows[a]["income"] - rows[b]["income"]) / 1024,
            "guard_charge_saving": (rows[b]["guard_charge"] - rows[a]["guard_charge"]) / 1024,
            "extinction_charge_saving": rows[b]["extinct_charge"] - rows[a]["extinct_charge"],
        }
        for name in parts[a]:
            pieces[name + "_cost_saving"] = (parts[b][name] - parts[a][name]) / 1024
        pieces["accounting_residual"] = delta["F"] - sum(pieces.values())
        check(np.allclose(pieces["accounting_residual"], 0, rtol=0, atol=1e-9), "accounting residual")
        result = summary["contrasts"]["primary"][LABELS[a]]
        check(
            result["baseline"] == LABELS[b]
            and set(result["columns"]) == set(delta)
            and set(result["fitness_pieces"]) == set(pieces),
            "contrast metadata differs",
        )
        for k, v in delta.items():
            check_stats(result["columns"][k], v)
        for k, v in pieces.items():
            check_stats(result["fitness_pieces"][k], v)
        ordinary = (totals[b] - totals[a]) / 1024
        check_stats(result["total_cost_saving"], ordinary)
        terms = dict(delta, **{"F__" + k: v for k, v in pieces.items()})
        vectors.update({"primary__" + LABELS[a] + "__" + k: v for k, v in terms.items()})
        compact[LABELS[a]] = {
            "baseline": LABELS[b],
            **{
                k: stats(v)
                for k, v in {
                    "F": delta["F"],
                    "captures": delta["captures"],
                    "capture_income": pieces["capture_income"],
                    "ordinary_cost_saving": ordinary,
                    "guard_charge_saving": pieces["guard_charge_saving"],
                    "extinction_charge_saving": pieces["extinction_charge_saving"],
                }.items()
            },
        }
        for k in (
            "F",
            "F_kernel",
            "captures",
            "n_end",
            "n_H_end",
            "live_time",
            "spikes",
            "packets",
            "misses",
            "clicks",
            "path",
            "zone_samples",
            "samples",
        ):
            check_stats(report["primary"][LABELS[a]][k], delta[k])
        check_stats(report["primary"][LABELS[a]]["capture_income"], pieces["capture_income"])
    stored = npz(base / "analysis_result/paired_vectors.npz")
    check(
        set(stored) == set(vectors) and len(vectors) == 146 and all(same(stored[k], v) for k, v in vectors.items()),
        "all146 paired vectors must agree bitwise",
    )
    resource = summary["resources"]
    check(
        resource["total_cpu_seconds"] == total
        and resource["search_cpu_seconds"] == search
        and resource["confirmation_cpu_seconds"] == total - search
        and np.isclose(resource["raw_confirmation_cpu_seconds"], cpu, rtol=0, atol=1e-6),
        "reader resource summary differs",
    )
    allstatus = np.concatenate([rows[i]["status"].astype(np.int64) for i in range(4)])
    values, counts = np.unique(allstatus, return_counts=True)
    return {
        "status": "complete_independently_reconciled",
        "protocol_sha256": PROTOCOL,
        "review_script_sha256": sha(__file__),
        "terminal_process_clearance_sha256": clearance_sha,
        "budget_sha256": sha(budget_path),
        "source_pins_verified": len(ready["source_pins"]),
        "production_pins_verified": len(ready["production_pins"]),
        "raw_rows": 4,
        "raw_lives": 2048,
        "raw_ledger_columns": 57,
        "research_lives": 10316,
        "native_search_lives": 8268,
        "numerical_goldens": 6,
        "total_calls": 10322,
        "native_receipt_coverage": native,
        "raw_health": health,
        "status_histogram": {str(v): int(n) for v, n in zip(values, counts)},
        "paired_vectors_bitwise_checked": 146,
        "primary_contrasts": compact,
        "monitored_cpu_seconds": total,
        "search_cpu_seconds": search,
        "confirmation_cpu_seconds": total - search,
        "raw_confirmation_cpu_seconds": cpu,
        "raw_row_pins": rawpins,
        "output_pins": {name: sha(base / "analysis_result" / name) for name in ("summary.json", "paired_vectors.npz")},
        "limits": [
            "Literal raw accounting is independently reconstructed without importing the reader, worker or accountant.",
            "Native full checkpoint/genetic replay is supplied by the frozen reader and its separately repeated terminal audit; this helper rechecks source/count/log/endpoint and health receipts.",
            "Native search lacks retained per-life raw ledgers; search status coverage is limited to its recorded summaries and initial guard frequencies.",
            "Six standard startup lives are bound by three numerical identity receipts and retained full/fast binaries; complete golden raw ledgers are not retained.",
            "Paired life uncertainty is conditional on these fixed endpoints and does not identify prediction, memory or evolutionary reliability.",
        ],
        "simulation_calls": 0,
        "compilation_calls": 0,
        "frozen_files_modified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--terminal-clearance-sha256")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not args.run:
        print(
            json.dumps(
                {
                    "status": "source_only_dry_run",
                    "study_artifacts_opened": 0,
                    "raw_rows": 4,
                    "raw_lives": 2048,
                    "research_lives": 10316,
                    "startup_goldens": 6,
                    "total_calls": 10322,
                    "paired_vectors": 146,
                    "simulation_calls": 0,
                    "requires": "root terminal process clearance and explicit execution",
                }
            )
        )
        return
    check(
        isinstance(args.terminal_clearance_sha256, str) and len(args.terminal_clearance_sha256) == 64,
        "exact root clearance digest required",
    )
    check(args.out is not None and not args.out.exists(), "fresh receipt required")
    result = recount(args.study.resolve(), args.terminal_clearance_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "receipt_sha256": sha(args.out),
                "raw_rows": 4,
                "raw_lives": 2048,
                "paired_vectors": 146,
            }
        )
    )


if __name__ == "__main__":
    main()
