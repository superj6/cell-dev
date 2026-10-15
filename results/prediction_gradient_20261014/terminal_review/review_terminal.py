"""Independent AE raw recount; requires explicit root terminal-clearance digest.

Standard library and NumPy only. Does not import the released reader, accountant,
worker, engine or genetic helper. Never creates a partial scientific receipt. Dry-run default opens no study artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

PROTOCOL = "0f5a591fbfb66fd29b5f9cd11d42b482eb8cb09e74613b17cc384ed2c3daa849"
LABELS = ("P_D90", "P_L92", "H_D90", "H_L92")
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
    # This is checked before any measurement/summary/outcome read.
    clearance_path = operation(base, "terminal_process_clearance.json")
    check(sha(clearance_path) == clearance_sha, "root's exact terminal-clearance digest is required")
    clearance = read(clearance_path)
    budget_path = operation(base, "budget.json")
    check(
        clearance["status"] == "cleared" and clearance["all_processes_exited"] is True, "current study is not cleared"
    )
    check(clearance["budget_sha256"] == sha(budget_path), "terminal clearance does not bind the budget")
    budget = read(budget_path)
    check(
        budget["status"] == "complete" and budget["exit_code"] == 0 and not budget["running"] and not budget["queued"],
        "study did not complete",
    )
    check(
        not budget.get("cleanup_error") and not budget.get("error") and not budget.get("reason"),
        "terminal monitor failure",
    )
    check(
        clearance["processes"] == budget["process_identities"]
        and clearance["process_groups"] == budget["owned_process_groups"],
        "cleared process identities differ",
    )
    check(
        budget["cap_cpu_seconds"] == 5400
        and budget["startup_screen_cap_cpu_seconds"] == 3400
        and budget["startup_calibration_cap_cpu_seconds"] == 180
        and budget["confirmation_reserve_cpu_seconds"] == 2000
        and budget["phase"] == "confirmation",
        "registered CPU scope differs",
    )
    total, screen_cpu = budget["cpu_seconds"], budget["startup_screen_cpu_seconds"]
    startup_cpu = budget["phase_receipts"]["calibration_complete"]["cpu_seconds"]
    check(
        all(np.isfinite(x) for x in (total, screen_cpu, startup_cpu))
        and 0 <= startup_cpu < 170
        and startup_cpu <= screen_cpu < 3390
        and screen_cpu <= total < 5390,
        "monitored phase CPU is invalid",
    )
    check(budget["completed"] == [{"name": "gradient", "exit_code": 0}], "exact first attempt completion required")
    leaders = budget["process_identities"]
    check([x["name"] for x in leaders] == ["monitor", "gradient"], "exact leader coverage differs")
    monitor, worker = leaders
    check(
        worker["ppid"] == monitor["pid"]
        and worker["pgid"] == worker["pid"]
        and worker["pid"] != monitor["pid"]
        and budget["owned_process_groups"] == [worker["pgid"]],
        "worker process ownership differs",
    )
    attempt = read(operation(base, "attempt.json"))
    check(
        attempt["monitor"] == {k: monitor[k] for k in ("pid", "ppid", "pgid", "start_ticks")},
        "attempt identity differs",
    )
    check(
        all(type(x[k]) is int and x[k] > 0 for x in leaders for k in ("pid", "pgid", "start_ticks")),
        "invalid process identity",
    )
    check(sha(base / "protocol.json") == PROTOCOL, "registered protocol changed")
    p, ready = read(base / "protocol.json"), read(operation(base, "ready.json"))
    check(ready["status"] == "released" and budget["ready"] == ready, "release differs")
    check(attempt["ready_sha256"] == sha(operation(base, "ready.json")), "attempt release differs")
    check(ready["production_pins"] == p["production_pins"], "released production closure differs")
    check(all(ready["source_pins"].get(k) == v for k, v in p["file_pins"].items()), "missing released protocol input")
    for name, digest in ready["source_pins"].items():
        check(sha(operation(base, name)) == digest, "released local bytes changed: " + name)
    for name, digest in ready["production_pins"].items():
        check(sha(external(base, name)) == digest, "released production bytes changed: " + name)
    summary = read(base / "analysis_result/summary.json")
    check(
        summary["status"] == "complete" and summary["protocol_sha256"] == PROTOCOL,
        "frozen complete reader output required",
    )
    check(summary["ledger_columns"] == list(LEDGER), "literal ledger order differs")
    check(
        summary["research_lives"] == 6208 and summary["validation_lives"] == 10 and summary["total_lives"] == 6218,
        "fixed life coverage differs",
    )
    startup = read(base / "startup_identity.json")
    check(
        startup["identity"] == p["expected_numerical_identity"] and startup["numerical_identity_invocations"] == 1,
        "startup identity differs",
    )
    check(
        startup["golden_lives"] == {"abi": 3, "seed": 11, "T": 200, "full": 1, "fast": 1},
        "two numerical goldens missing",
    )
    check(
        startup["preexpected_fields"] == sorted(p["expected_numerical_identity"])
        and startup["newly_captured_fields"] == [],
        "startup preexpected identity differs",
    )
    check(
        startup["identity"]["golden"]
        == {
            "all": "ebb3ad6fcad2d938",
            "ledger_sha256": "b622f9afad48d6ec5b39b003efba82f25e7e6a764a015fe40398b3a6bbd81251",
        },
        "standard golden differs",
    )
    check(set(startup["identity"]["kernels"]) == {"False", "True"}, "full/fast identity coverage differs")
    binaries = {sha(x) for x in (base / "build-cache").rglob("*.so")}
    check(set(startup["identity"]["kernels"].values()).issubset(binaries), "startup libraries missing")
    selection, roles = read(base / "selection.json"), read(base / "confirmation_roles.json")
    check(summary["roles"] == roles and roles["roles"] == list(LABELS), "four explicit roles differ")
    check(set(selection) == set(BACKGROUNDS), "both selected backgrounds required")
    check(
        roles["protocol_sha256"] == PROTOCOL and roles["selection_sha256"] == sha(base / "selection.json"),
        "role selection binding differs",
    )
    check(roles["genotypes_sha256"] == sha(base / "confirmation_genotypes.npz"), "role table file binding differs")
    panels = {b: np.load(base / "inputs/Y/inputs" / b / "genomes.npy", allow_pickle=False) for b in BACKGROUNDS}
    for b, table in panels.items():
        check(table.shape == (65, 875) and table.dtype == np.float32, "original65-row panel shape differs")
        check([raw(x) for x in table] == p["panel_genotype_sha256"][b], "original panel row bytes differ")
    table = npz(base / "confirmation_genotypes.npz")
    check(same(table["roles"], np.asarray(LABELS)), "ordered four-role table differs")
    expected_table = np.stack([panels[label.split("_")[1]][roles["panel_rows"][label]] for label in LABELS])
    check(same(table["genomes"], expected_table), "role table is outside retained panel")
    check(
        roles["genotype_sha256"] == {label: raw(table["genomes"][i]) for i, label in enumerate(LABELS)},
        "role genotype hashes differ",
    )
    data, parts, totals, health, rawpins = {}, {}, {}, {}, {}
    stage_cpu = dict.fromkeys(("calibration", "screen", "confirm"), 0.0)
    raw_rows = raw_lives = 0
    for group in ("screen/D90", "screen/L92", "confirm/persistent"):
        folder = base / "measurement" / group
        index = read(folder / "row_index.json")
        is_screen = group.startswith("screen/")
        stages = (
            {"calibration": (2, [0, 1]), "screen": (32, list(range(65)))}
            if is_screen
            else {"confirm": (512, list(range(4)))}
        )
        expected_files = {f"{stage}/row_{i:04d}.npz" for stage, (_, indices) in stages.items() for i in indices}
        check(set(index) == expected_files, "complete raw row index differs")
        check(
            {str(path.relative_to(folder)) for path in folder.rglob("row_*.npz")} == expected_files,
            "unexpected or missing raw row",
        )
        world = "persistent"
        for stage, (n, indices) in stages.items():
            rows = {}
            for i in indices:
                name = f"{stage}/row_{i:04d}.npz"
                path = folder / name
                check(sha(path) == index[name]["sha256"], "raw row hash differs")
                row = npz(path)
                check(
                    set(row)
                    == set(COLS) | {"identity", "seeds", "genome_index", "ledger", "cpu_seconds", "wall_seconds"},
                    "raw row fields differ",
                )
                expected = {
                    "protocol_sha256": PROTOCOL,
                    "world": world,
                    "stage": stage,
                    "genome_index": i,
                    "seeds": p["seeds"][stage],
                }
                if is_screen:
                    background = group.split("/")[1]
                    expected.update(background=background, genome_sha256=p["panel_genotype_sha256"][background][i])
                else:
                    expected.update(
                        roles=list(LABELS),
                        confirmation_roles_sha256=sha(base / "confirmation_roles.json"),
                        genome_sha256=roles["genotype_sha256"][LABELS[i]],
                    )
                check(
                    str(row["identity"]) == json.dumps(expected, sort_keys=True, separators=(",", ":")),
                    "raw identity differs",
                )
                check(
                    int(row["genome_index"]) == i
                    and same(row["seeds"], np.asarray(p["seeds"][stage], dtype=np.uint64)),
                    "ordered seed or genotype index differs",
                )
                key = group, stage, i
                parts[key], totals[key], health[str(key)] = physical(row, p["world"], n)
                check(float(row["cpu_seconds"]) == index[name]["cpu_seconds"], "indexed CPU differs")
                stage_cpu[stage] += float(row["cpu_seconds"])
                data[key], rows[i] = row, row
                rawpins[str(path.relative_to(base))] = sha(path)
                raw_rows += 1
                raw_lives += n
                if is_screen and stage == "screen":
                    check_stats(summary["screen_F"][background][str(i)], row["F"])
                if not is_screen:
                    check(
                        summary["confirmation_health"][world][LABELS[i]] == health[str(key)],
                        "confirmation health differs",
                    )
                    for metric in COLS:
                        check_stats(summary["absolute_means"][world][LABELS[i]][metric], row[metric])
            scores = npz(folder / stage / "scores.npz")
            check(set(scores) == set(COLS) | {"seeds", "genome_indices"}, "aggregate fields differ")
            check(
                same(scores["seeds"], np.asarray(p["seeds"][stage], dtype=np.uint64))
                and same(scores["genome_indices"], np.asarray(indices)),
                "aggregate identities differ",
            )
            for metric in COLS:
                check(same(scores[metric], np.stack([rows[i][metric] for i in indices])), "raw/aggregate discrepancy")
    check(raw_rows == 138 and raw_lives == 6216, "raw138-row coverage differs")
    stage_lives = {
        stage: sum(len(row["F"]) for (_, s, _), row in data.items() if s == stage)
        for stage in ("calibration", "screen", "confirm")
    }
    check(stage_lives == {"calibration": 8, "screen": 4160, "confirm": 2048}, "exact stage call counts differ")
    status_histograms = {}
    for label, stages in [
        ("calibration", ("calibration",)),
        ("screen", ("screen",)),
        ("confirm", ("confirm",)),
        ("research", ("screen", "confirm")),
    ]:
        statuses = np.concatenate(
            [row["status"].astype(np.int64) for (_, stage, _), row in data.items() if stage in stages]
        )
        values, counts = np.unique(statuses, return_counts=True)
        status_histograms[label] = {str(value): int(count) for value, count in zip(values, counts)}
    for b in BACKGROUNDS:
        chosen = min(range(1, 65), key=lambda i: (-float(data["screen/" + b, "screen", i]["F"].mean()), i))
        check(
            selection[b] == {"genome_row": chosen, "raw_sha256": raw(panels[b][chosen])},
            "whole32-life mutant-only selection differs",
        )
        check(
            roles["panel_rows"]["P_" + b] == 0 and roles["panel_rows"]["H_" + b] == chosen,
            "P/H role mapping differs",
        )
    duplicate_pairs = []
    for a in range(4):
        for b in range(a):
            if same(table["genomes"][a], table["genomes"][b]):
                duplicate_pairs.append([LABELS[a], LABELS[b]])
                for world in WORLDS:
                    check(
                        same(
                            data["confirm/" + world, "confirm", a]["ledger"],
                            data["confirm/" + world, "confirm", b]["ledger"],
                        ),
                        "identical-role deterministic ledger differs",
                    )
    expected_pairs = {LABELS[a] + "_minus_" + LABELS[b] for a, b in ((2, 0), (3, 1))}
    check(set(summary["contrasts"]) == expected_pairs, "exact two own-parent summaries required")
    vectors, compact = {}, {}
    worker_report = read(base / "report.json")
    check(set(worker_report["contrasts"]) == expected_pairs, "exact two worker contrasts required")
    for a, b in ((2, 0), (3, 1)):
        label = LABELS[a] + "_minus_" + LABELS[b]
        ka, kb = ("confirm/persistent", "confirm", a), ("confirm/persistent", "confirm", b)
        pa, pb = data[ka], data[kb]
        check(same(pa["seeds"], pb["seeds"]), "paired ordered seeds differ")
        delta = {metric: pa[metric] - pb[metric] for metric in COLS}
        delta.update(
            capture_income=(pa["income"] - pb["income"]) / 1024,
            ordinary_cost=(totals[kb] - totals[ka]) / 1024,
            guard_cost=(pb["guard_charge"] - pa["guard_charge"]) / 1024,
            extinction_cost=pb["extinct_charge"] - pa["extinct_charge"],
        )
        check(
            np.max(
                np.abs(
                    delta["F"]
                    - sum(delta[k] for k in ("capture_income", "ordinary_cost", "guard_cost", "extinction_cost"))
                )
            )
            < 1e-9,
            "fitness decomposition residual",
        )
        check(set(summary["contrasts"][label]) == set(delta) and len(delta) == 64, "all64 metric summaries required")
        check(set(worker_report["contrasts"][label]) == set(delta), "all64 worker metrics required")
        for metric, value in delta.items():
            check_stats(summary["contrasts"][label][metric], value)
            check_stats(worker_report["contrasts"][label][metric], value)
        vectors.update({label + "__" + key: value for key, value in delta.items()})
        compact[label] = {
            key: stats(delta[key])
            for key in ("F", "captures", "capture_income", "ordinary_cost", "guard_cost", "extinction_cost")
        }
    stored = npz(base / "analysis_result/paired_vectors.npz")
    check(
        set(stored) == set(vectors) and len(vectors) == 128 and len(compact) == 2,
        "complete128 paired-vector coverage differs",
    )
    check(all(same(stored[k], v) for k, v in vectors.items()), "saved paired vector bytes differ")
    for stage, charged in stage_cpu.items():
        check(
            np.isclose(charged, summary["resources"]["raw_stage_cpu_seconds"][stage], rtol=0, atol=1e-6),
            "raw stage CPU differs",
        )
    check(
        stage_cpu["calibration"] <= startup_cpu + 1e-6
        and stage_cpu["screen"] <= screen_cpu - startup_cpu + 1e-6
        and stage_cpu["confirm"] <= total - screen_cpu + 1e-6,
        "raw CPU exceeds owned phase accounting",
    )
    check(abs(sum(stage_cpu.values()) - worker_report["row_cpu_seconds"]) < 1e-6, "raw CPU differs from worker report")
    check(
        worker_report["research_genome_lives"] == 6208
        and worker_report["validation_lives"] == 10
        and worker_report["total_genome_lives"] == 6218
        and worker_report["status"] == "complete",
        "worker call coverage differs",
    )
    for name, cap in (("calibration_complete", 170), ("screens_complete", 3390)):
        receipt = read(base / "monitor_receipts" / (name + ".json"))
        check(
            receipt == budget["phase_receipts"][name]
            and receipt["status"] == "allowed"
            and receipt["protocol_sha256"] == PROTOCOL
            and receipt["attempt_sha256"] == sha(operation(base, "attempt.json"))
            and receipt["request_sha256"] == sha(base / "requests" / (name + ".json"))
            and receipt["cpu_seconds"] < cap,
            "phase acknowledgment differs",
        )
        for path, digest in receipt["artifact_pins"].items():
            check(sha(base / path) == digest, "acknowledged phase artifact changed")
        for group, snapshot in receipt["row_snapshot"].items():
            terminal = read(base / "measurement" / group / "row_index.json")
            check(all(terminal.get(k) == v for k, v in snapshot.items()), "acknowledged raw row changed")
    resource = summary["resources"]
    check(
        resource["total_cpu_seconds"] == total
        and resource["startup_screen_cpu_seconds"] == screen_cpu
        and resource["confirmation_cpu_seconds"] == total - screen_cpu
        and resource["first_attempt_only"] is True,
        "reader resource summary differs",
    )
    return {
        "status": "complete_independently_reconciled",
        "protocol_sha256": PROTOCOL,
        "review_script_sha256": sha(__file__),
        "terminal_process_clearance_sha256": clearance_sha,
        "budget_sha256": sha(budget_path),
        "source_pins_verified": len(ready["source_pins"]),
        "production_pins_verified": len(ready["production_pins"]),
        "raw_rows": raw_rows,
        "raw_lives": raw_lives,
        "raw_ledger_columns": 57,
        "numerical_goldens": 2,
        "all_fitness_lives_retained": True,
        "paired_vectors_bitwise_checked": 128,
        "contrast_summaries_independently_checked": 2,
        "selection": selection,
        "explicit_duplicate_role_pairs": duplicate_pairs,
        "raw_health": health,
        "raw_stage_lives": stage_lives,
        "status_histograms": status_histograms,
        "contrasts": compact,
        "raw_stage_cpu_seconds": stage_cpu,
        "monitored_cpu_seconds": total,
        "startup_calibration_cpu_seconds": startup_cpu,
        "startup_screen_cpu_seconds": screen_cpu,
        "research_lives": 6208,
        "validation_lives": 10,
        "total_calls": 6218,
        "raw_row_pins": rawpins,
        "output_pins": {name: sha(base / "analysis_result" / name) for name in ("summary.json", "paired_vectors.npz")},
        "limits": [
            "Independent raw arithmetic only; no fresh dynamics or genetic replay.",
            "Two startup goldens are verified through identity/library hashes; complete golden raw ledgers are not retained.",
            "Paired capture effects do not isolate tracking, prediction or memory.",
            "Two fixed local panels do not establish general evolutionary reliability.",
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
                    "raw_rows": 138,
                    "research_lives": 6208,
                    "validation_lives": 10,
                    "total_calls": 6218,
                    "paired_vectors": 128,
                    "simulation_calls": 0,
                    "requires": "root terminal process clearance and explicit execution",
                }
            )
        )
        return
    check(
        isinstance(args.terminal_clearance_sha256, str) and len(args.terminal_clearance_sha256) == 64,
        "exact root terminal-clearance digest required",
    )
    check(args.out is not None and not args.out.exists(), "fresh output receipt required")
    review = recount(args.study.resolve(), args.terminal_clearance_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(review, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "status": review["status"],
                "receipt_sha256": sha(args.out),
                "raw_rows": review["raw_rows"],
                "raw_lives": review["raw_lives"],
                "paired_vectors": review["paired_vectors_bitwise_checked"],
            }
        )
    )


if __name__ == "__main__":
    main()
