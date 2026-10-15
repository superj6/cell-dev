"""Independent production ABI3 accounting, narrowly adapted from study I.

NumPy and standard library only: no engine, worker, mutation or simulation imports.
Raw ledger F is kernel fitness; saved named F includes the production extinction
charge. Guards and natural extinction remain in every paired fitness estimate.
The ledger accountant below is retained from AF; this file adds the fixed retention matrix reader.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

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
L = {name: i for i, name in enumerate(LEDGER)}
COLS = LEDGER + ("F_kernel", "extinct_charge", "window")
COSTS = (
    ("living", "c_live", "live_time"),
    ("spiking", "c_spike", "spikes"),
    ("twitching", "c_tw", "kappa_sum"),
    ("messages", "c_msg", "contact_events"),
    ("division", "c_div", "claims"),
    ("secretion", "c_sec", "sec_int"),
    ("missed_clicks", "c_miss", "misses"),
    ("receptors", "c_rec", "rec_gain"),
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
NONNEGATIVE = tuple(
    name for name in LEDGER if name not in ("net", "F", "t_end", "last_birth", "t_ext", "X_end", "Y_end")
)


def identical(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def stats(values):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("paired statistics require at least two finite one-dimensional values")
    mean = float(values.mean())
    se = float(values.std(ddof=1) / math.sqrt(len(values)))
    return {
        "mean": mean,
        "se": se,
        "n": len(values),
        "positive_above_3se": mean > 3 * se,
        "negative_below_minus_3se": mean < -3 * se,
    }


def prices(world):
    return [(name, column, world[price]) for name, price, column in COSTS] + [
        ("decoy_clicks", "b2_clicks", max(0.0, -world["b2_value"]))
    ]


def physical_costs(row, world):
    parts = {name: price * row[column] for name, column, price in prices(world)}
    names = list(parts)
    total = parts[names[0]].copy()
    for name in names[1:]:
        total = total + parts[name]
    return total, parts


def validate_row(row, world, n=512, initial_cells=1):
    """Reconcile all 57 raw/named columns and retain legitimate paid early endings.

    The AE world uses full-life accounting and a single target. Unlike X/X2's fixed
    static yardsticks, births, deaths, growth, natural extinction and paid guards are
    valid here. Production columns 21/22 retain beats/P_int; no scratch aliases.
    """
    if type(initial_cells) is not int or initial_cells < 1:
        raise ValueError("positive supplied initial-cell count required")
    if world["t_open"] != 0 or world["world_kind"] != 1 or world["b2_amp"] != 0:
        raise ValueError("this gradient accountant requires full-life single-target CATCH")
    led = row["ledger"]
    if led.dtype != np.float64 or led.shape != (n, len(LEDGER)) or not np.isfinite(led).all():
        raise ValueError("invalid complete ABI3 raw ledger")
    for key in COLS:
        value = np.asarray(row[key])
        if value.shape != (n,) or not np.issubdtype(value.dtype, np.number) or not np.isfinite(value).all():
            raise ValueError("invalid production-scored column: " + key)
    for name in LEDGER:
        saved = row["F_kernel" if name == "F" else name]
        if not identical(saved, led[:, L[name]]):
            raise ValueError("raw ledger and saved production column differ: " + name)
    for key in NONNEGATIVE:
        if np.any(row[key] < 0):
            raise ValueError("negative physical quantity: " + key)
    for key in COUNTS:
        if np.any(row[key] != np.floor(row[key])):
            raise ValueError("nonintegral physical count: " + key)
    if np.any(row["status"] != np.floor(row["status"])) or np.any(row["status"] > 511):
        raise ValueError("invalid status encoding")
    status = row["status"].astype(np.int64)
    if np.any(status & (64 | 128)):
        raise ValueError("implementation failure cannot become evidence")
    guarded, extinct = (status & 6) != 0, (status & 1) != 0
    start, end = world["t0"], world["t0"] + world["T"]
    if (
        np.any(row["t_end"] < start)
        or np.any(row["t_end"] > end)
        or np.any(~(guarded | extinct) & (row["t_end"] != end))
    ):
        raise ValueError("unexplained incomplete life")
    if np.any(extinct & ((row["t_ext"] < start) | (row["t_ext"] > row["t_end"]))) or np.any(
        ~extinct & (row["t_ext"] != -1)
    ):
        raise ValueError("extinction time disagrees with status")
    if np.any(extinct & (row["n_end"] != 0)):
        raise ValueError("extinct life retains cells")
    if np.any((row["last_birth"] < start) | (row["last_birth"] > row["t_end"])):
        raise ValueError("birth time lies outside life")
    window = world["T"] - world["t_open"]
    if window <= 0 or not np.all(row["window"] == window):
        raise ValueError("accounting window differs")
    if np.any(row["b2_clicks"] != 0):
        raise ValueError("single-target world has second-blob clicks")
    for small, large in (
        ("zone_samples", "samples"),
        ("rec_accept", "rec_cand"),
        ("rec_events", "rec_accept"),
        ("n_end", "n_peak"),
    ):
        if np.any(row[small] > row[large]):
            raise ValueError(small + " exceeds " + large)
    if not np.array_equal(row["captures"] + row["misses"], row["clicks"]):
        raise ValueError("captures and misses do not sum to clicks")
    if not np.array_equal(row["n_S_end"] + row["n_M_end"] + row["n_H_end"], row["n_end"]):
        raise ValueError("plane census does not sum to final cells")
    if not np.allclose(row["live_S"] + row["live_M"] + row["live_H"], row["live_time"], rtol=1e-9, atol=1e-9):
        raise ValueError("plane cell-times do not sum to total cell-time")
    # Initial cells enter the census but R_BIRTH excludes them from the births counter.
    if not np.array_equal(initial_cells + row["births"] - row["deaths"] - row["kills"], row["n_end"]):
        raise ValueError("birth/death/kill census does not reconcile")
    morph = row["morph_decayed"] + row["morph_lost"] + row["morph_content_end"] + row["morph_inflight_end"]
    if not np.allclose(morph, row["morph_secreted"], rtol=1e-9, atol=1e-9):
        raise ValueError("morphogen conservation does not reconcile")
    cost, _ = physical_costs(row, world)
    # Match the kernel's accumulated-event versus reconstructed-column tolerance.
    if np.any(np.abs(row["cost"] - cost) > 1e-9 * np.maximum(1.0, np.abs(cost))):
        raise ValueError("independent accounting differs: cost")
    guard = np.where(guarded, world["c_live"] * world["n_max"] * (end - row["t_end"]), 0.0)
    extinction = world["c_live"] * np.where(extinct, end - np.maximum(row["t_ext"], start), 0.0) / window
    income = world["R_cap"] * row["captures"]
    net = income - cost - guard
    for key, value in (
        ("income", income),
        ("guard_charge", guard),
        ("net", net),
        ("extinct_charge", extinction),
        ("F_kernel", net / window),
    ):
        if not np.allclose(row[key], value, rtol=1e-10, atol=1e-9):
            raise ValueError("independent accounting differs: " + key)
    if not identical(row["F"], row["F_kernel"] - row["extinct_charge"]):
        raise ValueError("production fitness differs from kernel minus extinction charge")
    for key in ("cpu_seconds", "wall_seconds"):
        timing = np.asarray(row[key])
        if timing.shape != () or not np.issubdtype(timing.dtype, np.number) or not np.isfinite(timing) or timing < 0:
            raise ValueError("invalid scalar saved row timing: " + key)
    return {
        "guarded": int(guarded.sum()),
        "extinct": int(extinct.sum()),
        "valid_other_status": int(np.count_nonzero(status & ~7)),
        "all_fitness_rows_retained": n,
    }


# The root release binds the exact protocol; its source_pins bind this executing reader.
ROLES = ("L92", "AE_L92", "AI_control")
WORLDS = ("pool", "persistent", "turn100", "blink80_5")
PAIRS = ((1, 0), (2, 0), (2, 1))
ABI4_LEDGER = LEDGER + ("low_light_captures",)
ACCOUNTANT_SOURCE = "results/prediction_continuation_20261014/analysis/offline_accounting.py"
ACCOUNTANT_SOURCE_SHA256 = "5a20bb4966660ff5d44b74b67c6e124b9bbe1ef6ff03ea7c9cf280eba03dac0b"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def describe(values):
    result = stats(values)
    result["lower_3se"] = result["mean"] - 3 * result["se"]
    result["upper_3se"] = result["mean"] + 3 * result["se"]
    result["bounds_are_descriptive"] = True
    return result


def scalar(row, key):
    value = np.asarray(row[key])
    if value.shape != ():
        raise ValueError("expected scalar: " + key)
    return value.item()


def reconstruct(row, world_record, seeds):
    """Read actual ABI3/4 bytes; independently derive the production accountant."""
    abi, world = world_record["abi"], world_record["world"]
    names = LEDGER if abi == 3 else ABI4_LEDGER if abi == 4 else ()
    n = len(seeds)
    ledger = np.asarray(row["ledger"])
    if (world_record["ledger_columns"] != list(names) or ledger.dtype != np.float64
            or ledger.shape != (n, len(names)) or not np.isfinite(ledger).all()):
        raise ValueError("raw ledger width, columns, dtype or finiteness differs")
    observed_seeds, hashes = np.asarray(row["seeds"]), np.asarray(row["hashes"])
    if (observed_seeds.dtype != np.uint64 or observed_seeds.shape != (n,)
            or observed_seeds.tolist() != seeds or hashes.dtype != np.uint64 or hashes.shape != (n, 5)):
        raise ValueError("raw seeds or hash schema differs")
    if (world["T"] != 1024 or world["t_open"] != 0 or world["t0"] != 0
            or world["world_kind"] != 1 or world["b2_amp"] != 0):
        raise ValueError("expected full-life T1024 single-target world")
    if abi == 3 and (world["visibility_mode"], world["visibility_on"],
                     world["visibility_off"], world["visibility_low"]) != (0, 0, 0, 1):
        raise ValueError("ABI3 cannot have enabled visibility")
    columns = {name: ledger[:, i] for i, name in enumerate(LEDGER)}
    columns["ledger"] = ledger[:, :len(LEDGER)]
    columns["F_kernel"] = columns["F"]
    columns["F"] = np.asarray(row["production_F"])
    if columns["F"].dtype != np.float64 or columns["F"].shape != (n,):
        raise ValueError("invalid production F vector")
    status = columns["status"]
    # Validate encoding before converting; otherwise a NaN or overflow could hide an error.
    if np.any(status < 0) or np.any(status > 511) or np.any(status != np.floor(status)):
        raise ValueError("invalid status encoding")
    extinct = (status.astype(np.int64) & 1) != 0
    window = world["T"] - world["t_open"]
    end = world["t0"] + world["T"]
    columns["extinct_charge"] = world["c_live"] * np.where(
        extinct, end - np.maximum(columns["t_ext"], world["t0"]), 0.0) / window
    columns["window"] = np.full(n, window, dtype=np.float64)
    for key in ("cpu_seconds", "wall_seconds"):
        columns[key] = np.asarray(row[key])
    health = validate_row(columns, world, n)
    if abi == 4:
        low = ledger[:, -1]
        if np.any(low < 0) or np.any(low > columns["captures"]) or np.any(low != np.floor(low)):
            raise ValueError("invalid low-light capture count")
        if world["visibility_mode"] == 0 and np.any(low != 0):
            raise ValueError("neutral visibility has low-light captures")
    else:
        low = np.zeros(n, dtype=np.float64)
    costs, pieces = physical_costs(columns, world)
    metrics = {name: columns[name] for name in COLS}
    metrics.update(low_light_captures=low, bright_captures=columns["captures"] - low,
                   capture_income=columns["income"] / window,
                   ordinary_cost=-costs / window,
                   guard_cost=-columns["guard_charge"] / window,
                   extinction_cost=-columns["extinct_charge"])
    metrics.update({"cost__" + name: -value / window for name, value in pieces.items()})
    if not np.allclose(sum(metrics[k] for k in (
            "capture_income", "ordinary_cost", "guard_cost", "extinction_cost")),
            metrics["F"], rtol=0, atol=1e-9):
        raise ValueError("production fitness decomposition differs")
    health["status_counts"] = {str(int(s)): int(np.sum(status == s)) for s in np.unique(status)}
    health["hashes_are_fast_mode_diagnostics_not_trajectory_proof"] = True
    return metrics, health


def contrasts(rows):
    """All fixed lineage, environmental and interaction vectors, always paired by seed."""
    if tuple(rows) != WORLDS or any(tuple(rows[w]) != ROLES for w in WORLDS):
        raise ValueError("fixed 3-genome by 4-world matrix required")
    names = tuple(rows[WORLDS[0]][ROLES[0]])
    arrays, reports = {}, {}

    def record(key, values):
        reports[key] = {name: describe(value) for name, value in values.items()}
        arrays.update({key + "__" + name: value for name, value in values.items()})

    for world in WORLDS:
        for a, b in PAIRS:
            key = f"within__{world}__{ROLES[a]}_minus_{ROLES[b]}"
            record(key, {name: rows[world][ROLES[a]][name] - rows[world][ROLES[b]][name] for name in names})
    # Include POOL as an ancestral environment contrast, without calling its physics a single-factor edge.
    for world in ("pool", "turn100", "blink80_5"):
        for role in ROLES:
            record(f"environment__{world}_minus_persistent__{role}", {
                name: rows[world][role][name] - rows["persistent"][role][name] for name in names})
        for a, b in PAIRS:
            record(f"interaction__{world}_minus_persistent__{ROLES[a]}_minus_{ROLES[b]}", {
                name: ((rows[world][ROLES[a]][name] - rows[world][ROLES[b]][name])
                       - (rows["persistent"][ROLES[a]][name] - rows["persistent"][ROLES[b]][name]))
                for name in names})
    return reports, arrays


def retention_diagnostics(rows):
    reports, arrays = {}, {}
    for world, reference in (("pool", "L92"), ("persistent", "AE_L92")):
        new, old = rows[world]["AI_control"]["captures"], rows[world][reference]["captures"]
        key = f"AI_control_vs_{reference}__{world}"
        difference = new - old
        conventional = new - .9 * old
        reports[key] = {
            "capture_difference": describe(difference),
            "retained_90_percent_vector": describe(conventional),
            "passes_conventional_10_percent_diagnostic": describe(conventional)["lower_3se"] > 0,
            "reference_mean_captures": float(old.mean()),
            "candidate_mean_captures": float(new.mean()),
            "mean_capture_ratio": float(new.mean() / old.mean()) if old.mean() > 0 else None,
            "interpretation": "Conventional diagnostic only; a null difference is not established retention.",
        }
        arrays["retention__" + key + "__capture_difference"] = difference
        arrays["retention__" + key + "__ninety_percent_reference"] = conventional
    return reports, arrays


def local(base, name):
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("path escapes study: " + name)
    return path


def external(base, name):
    # Portable archives take precedence over a mutable live checkout.
    prefixes = ("production",) if name.startswith(("src/", "scripts/")) else ("original",)
    for prefix in prefixes:
        path = local(base / prefix, name)
        if path.is_file():
            return path
    for root in base.parents:
        if (root / "src/life/spec.py").is_file():
            return local(root, name)
    raise ValueError("missing archived dependency: " + name)


def json_genome(path):
    value = read(path)
    dims = {"genes_max": 16, "genes_init": 8, "morph": 2, "channels": 2,
            "stim": 1, "pheno": 22, "kind": "life", "cues": 2}
    shapes = {"W": (16, 25), "b": (16,), "lam": (16,), "s0": (16,), "Q": (16,),
              "act": (16,), "A": (23, 16), "a0": (23,), "Dm": (2,), "km": (2,)}
    if value["dims"] != dims or set(value["params"]) != set(shapes):
        raise ValueError("BODY-1 genome schema differs")
    fields = []
    for name, shape in shapes.items():
        array = np.asarray(value["params"][name], dtype=np.float32)
        if array.shape != shape or not np.isfinite(array).all():
            raise ValueError("genotype shape or finiteness differs: " + name)
        fields.append(array.ravel())
    result = np.concatenate(fields)
    if result.shape != (875,):
        raise ValueError("genotype width differs")
    return result


def verify_protocol(base):
    protocol = read(base / "protocol.json")
    if (protocol["roles"] != list(ROLES) or list(protocol["worlds"]) != list(WORLDS)
            or protocol["research_lives"] != 3072 or protocol["startup_lives"] != 4
            or protocol["extinct_charge"] is not True or protocol["retention_margin_fraction"] != .1):
        raise ValueError("fixed matrix, accounting, margin or life counts changed")
    if protocol["budget"] != {"cpu_seconds": 2400, "wall_seconds": 1800, "threads": 2,
                              "workers": 1, "cleanup_margin_seconds": 10}:
        raise ValueError("fixed one-worker resource scope differs")
    seeds = protocol["seeds"]
    if (len(seeds) != 256 or len(set(seeds)) != 256
            or any(type(s) is not int or not 0 <= s < 2**64 for s in seeds)
            or {11, 55040000}.intersection(seeds)):
        raise ValueError("expected 256 unique research seeds disjoint from retained truth seeds")
    status_bits = {"extinct": 1, "guard_cells": 2, "guard_events": 4, "raster_overflow": 8,
                   "fate_overflow": 16, "chem_clamp": 32, "ledger_mismatch": 64, "capacity": 128, "wall": 256}
    if protocol["status_bits"] != status_bits:
        raise ValueError("ledger status mapping differs")
    expected_primary = [{"world": "pool", "new": "AI_control", "old": "L92", "metric": "captures"},
                        {"world": "persistent", "new": "AI_control", "old": "AE_L92", "metric": "captures"}]
    if protocol["primary"] != expected_primary:
        raise ValueError("primary contrasts differ")
    for key in ("input_pins", "source_pins", "production_pins"):
        if not protocol[key]:
            raise ValueError("empty input/source closure")
        for name, digest in protocol[key].items():
            path = external(base, name) if key == "production_pins" else local(base, name)
            if sha(path) != digest:
                raise ValueError("changed pinned file: " + name)
    if protocol["source_pins"].get("analyze.py") != sha(Path(__file__)):
        raise ValueError("executing analyzer differs from reviewed source")
    seed_audit = read(base / "inputs/seed_audit.json")
    if seed_audit["status"] != "passed" or seed_audit["candidate_seeds"] != seeds:
        raise ValueError("seed inventory differs")
    if len(protocol["genomes"]) != 3:
        raise ValueError("exactly three frozen roles required")
    for role, record in zip(ROLES, protocol["genomes"]):
        path = local(base, record["path"])
        if (record["role"] != role or record["path"] != f"inputs/{role}.json"
                or sha(path) != record["file_sha256"]
                or protocol["original_input_pins"][record["source"]] != sha(path)
                or hashlib.sha256(json_genome(path).tobytes()).hexdigest() != record["raw_sha256"]):
            raise ValueError("retained genome bytes or origin differs")
    spec_path = external(base, "src/life/spec.py")
    cls = next(node for node in ast.parse(spec_path.read_text()).body
               if isinstance(node, ast.ClassDef) and node.name == "World")
    keys = [node.target.id for node in cls.body if isinstance(node, ast.AnnAssign)
            and node.target.id not in ("name", "stage", "implemented", "lattice", "lives")]
    if len(keys) != 70 or keys[-4:] != ["visibility_mode", "visibility_on", "visibility_off", "visibility_low"]:
        raise ValueError("pinned World dataclass layout differs")
    persistent = dict(read(base / "inputs/persistent_protocol.json")["world"],
                      visibility_mode=0, visibility_on=0., visibility_off=0., visibility_low=1.)
    expected = {"persistent": persistent,
                "pool": dict(persistent, d0=.5, d_min=.25, sigma=.4, lam_s=4., v_t=.1, tau_turn=20.),
                "turn100": dict(persistent, tau_turn=100.),
                "blink80_5": dict(persistent, visibility_mode=2, visibility_on=80.,
                                  visibility_off=5., visibility_low=0.)}
    if (persistent["v_t"], persistent["tau_turn"], persistent["d0"], persistent["d_min"]) != (.3, 200, 1, .5):
        raise ValueError("retained persistent-target physics differs")
    for name in WORLDS:
        rec = protocol["worlds"][name]
        abi = 4 if name == "blink80_5" else 3
        names = ABI4_LEDGER if abi == 4 else LEDGER
        if rec["abi"] != abi or rec["world"] != expected[name] or rec["ledger_columns"] != list(names):
            raise ValueError("planned world or ABI differs: " + name)
        vector = np.asarray([float(rec["world"][k]) for k in keys[:70 if abi == 4 else 66]], dtype=np.float64)
        if not identical(np.asarray(rec["world_vector"], dtype=np.float64), vector):
            raise ValueError("independent world packing differs: " + name)
    return protocol


def verify_startup(base, protocol):
    startup = read(base / "startup.json")
    if (startup["protocol_sha256"] != sha(base / "protocol.json") or startup["startup_lives"] != 4
            or startup["identity"] != read(base / "inputs/startup_identity.json")["identity"]):
        raise ValueError("four-call startup identity differs")
    fixture = read(base / "inputs/visibility_truth.json")
    ledger = np.asarray([fixture["ledger"]], dtype=np.float64)
    hashes = np.asarray([[int(v, 16) for v in fixture["hashes"]]], dtype=np.uint64)
    expected = {"name": fixture["name"], "seed": fixture["seed"], "lives": 2,
                "ledger_sha256": hashlib.sha256(ledger.tobytes()).hexdigest(),
                "hashes_sha256": hashlib.sha256(hashes.tobytes()).hexdigest()}
    if startup["visibility"] != expected or expected["name"] != "body0_renewal_55040000":
        raise ValueError("retained ABI4 full/fast truth receipt differs")
    if startup["identity"]["golden"]["all"] != "ebb3ad6fcad2d938":
        raise ValueError("standard ABI3 golden receipt differs")
    library_hashes = {sha(p) for p in (base / "build-cache").rglob("*.so")}
    if not set(startup["identity"]["kernels"].values()).issubset(library_hashes):
        raise ValueError("retained compiled library bytes do not bind startup identity")
    return startup


def load_rows(base, protocol):
    index = read(base / "row_index.json")
    expected = {f"raw/{world}/row_{i:02d}.npz" for world in WORLDS for i in range(3)}
    actual = {str(p.relative_to(base)) for p in (base / "raw").rglob("*.npz")}
    if set(index) != expected or actual != expected:
        raise ValueError("complete exact 12-row matrix required")
    rows, health, cpu = {}, {}, 0.0
    for world in WORLDS:
        rows[world], health[world] = {}, {}
        for i, role in enumerate(ROLES):
            name = f"raw/{world}/row_{i:02d}.npz"
            path = base / name
            entry = index[name]
            if entry["sha256"] != sha(path) or entry["lives"] != 256:
                raise ValueError("row index hash or count differs")
            with np.load(path, allow_pickle=False) as raw:
                row = {key: raw[key].copy() for key in raw.files}
            for key, value in (("role", role), ("world_name", world),
                               ("protocol_sha256", sha(base / "protocol.json")),
                               ("genome_raw_sha256", protocol["genomes"][i]["raw_sha256"])):
                if scalar(row, key) != value:
                    raise ValueError("row identity differs: " + key)
            if (entry["abi"] != protocol["worlds"][world]["abi"]
                    or any(float(scalar(row, key)) != entry[key] for key in ("cpu_seconds", "wall_seconds"))):
                raise ValueError("row scalar identity differs")
            rows[world][role], health[world][role] = reconstruct(row, protocol["worlds"][world], protocol["seeds"])
            cpu += float(scalar(row, "cpu_seconds"))
    complete = read(base / "measurement_complete.json")
    if complete != {"status": "complete", "research_lives": 3072, "startup_lives": 4, "rows": 12,
                    "protocol_sha256": sha(base / "protocol.json"), "row_index_sha256": sha(base / "row_index.json")}:
        raise ValueError("measurement completion receipt differs")
    return rows, health, cpu


def verify_terminal(base, protocol):
    release, attempt, budget = (read(base / name) for name in ("release.json", "attempt.json", "budget.json"))
    digest = sha(base / "protocol.json")
    if (release.get("status") != "released" or release.get("protocol_sha256") != digest
            or attempt.get("protocol_sha256") != digest or attempt.get("release_sha256") != sha(base / "release.json")
            or budget.get("protocol_sha256") != digest or budget.get("release_sha256") != sha(base / "release.json")
            or budget.get("attempt_sha256") != sha(base / "attempt.json")):
        raise ValueError("explicit release, attempt or terminal binding differs")
    if (budget.get("status") != "complete" or budget.get("exit_code") != 0 or budget.get("worker_exit_code") != 0
            or budget.get("running") or budget.get("queued") or budget.get("cleanup_error")
            or budget.get("reason") or budget.get("error") or attempt["budget"] != protocol["budget"]):
        raise ValueError("complete first attempt and clean teardown required")
    for key, cap_key, protocol_key in (("cpu_seconds", "cap_cpu_seconds", "cpu_seconds"),
                                       ("wall_seconds", "cap_wall_seconds", "wall_seconds")):
        value = budget[key]
        if (not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0
                or budget[cap_key] != protocol["budget"][protocol_key] or value > budget[cap_key]):
            raise ValueError("resource accounting is invalid or over cap")
    namespace = budget["pid_namespace"]
    if (not isinstance(namespace, str) or not namespace.startswith("pid:[")
            or attempt["pid_namespace"] != namespace or release["pid_namespace"] != namespace):
        raise ValueError("monitor execution namespace differs")
    identities = budget["process_identities"]
    if len(identities) != 2 or {r["name"] for r in identities} != {"monitor", "worker"}:
        raise ValueError("two exact process leaders required")
    by_name = {item["name"]: item for item in identities}
    for item in identities:
        if any(type(item[k]) is not int or item[k] <= 0 for k in ("pid", "ppid", "pgid", "start_ticks")):
            raise ValueError("invalid persisted process identity")
    monitor, worker = by_name["monitor"], by_name["worker"]
    if ({k: monitor[k] for k in ("pid", "ppid", "pgid", "start_ticks")} != attempt["monitor"]
            or worker["ppid"] != monitor["pid"] or worker["pgid"] != worker["pid"]
            or budget["owned_process_groups"] != [worker["pid"]]):
        raise ValueError("owned worker lineage differs")
    cleanup = budget["terminal_cleanup"]
    if (cleanup["pid_namespace"] != namespace or cleanup["checked_in_monitor"] is not True
            or cleanup["same_pid_namespace"] is not True
            or cleanup["all_owned_groups_exited"] is not True or cleanup["all_worker_identities_exited"] is not True
            or cleanup["remaining_group_members"] or cleanup["remaining_worker_identities"]
            or cleanup["remaining_descendants"]):
        raise ValueError("same-namespace cleanup was not established")
    receipts = budget["wait4_receipts"]
    worker_receipts = [r for r in receipts if r["pid"] == worker["pid"]]
    if (len(worker_receipts) != 1 or worker_receipts[0]["exit_code"] != 0
            or worker_receipts[0]["wait_status"] != 0
            or len({r["pid"] for r in receipts}) != len(receipts)):
        raise ValueError("worker was not reaped")
    reaped_cpu = 0.
    for receipt in receipts:
        for key in ("user_cpu_seconds", "system_cpu_seconds"):
            value = receipt[key]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("invalid reaped process CPU")
            reaped_cpu += value
    if reaped_cpu > budget["cpu_seconds"] + 1e-6:
        raise ValueError("reaped process CPU exceeds monitored total")
    return budget


def analyze(base):
    protocol = verify_protocol(base)
    budget = verify_terminal(base, protocol)
    startup = verify_startup(base, protocol)
    rows, health, row_cpu = load_rows(base, protocol)
    if row_cpu > budget["cpu_seconds"] + 1e-6:
        raise ValueError("raw row CPU exceeds monitored total")
    differences, arrays = contrasts(rows)
    retention, extra = retention_diagnostics(rows)
    arrays.update(extra)
    if len(arrays) != 2254:
        raise ValueError("complete 2254-vector output required")
    summary = {
        "status": "complete", "protocol_sha256": sha(base / "protocol.json"),
        "research_lives": 3072, "startup_lives": 4, "total_calls": 3076, "raw_rows": 12,
        "paired_arrays": len(arrays), "row_cpu_seconds": row_cpu,
        "cpu_seconds": budget["cpu_seconds"], "wall_seconds": budget["wall_seconds"],
        "absolute": {w: {r: {k: describe(v) for k, v in rows[w][r].items()} for r in ROLES} for w in WORLDS},
        "contrasts": differences, "retention": retention, "health": health,
        "primary": {f"{c['world']}__{c['new']}_minus_{c['old']}":
                    differences[f"within__{c['world']}__{c['new']}_minus_{c['old']}"][c["metric"]]
                    for c in protocol["primary"]},
        "startup": startup, "limitations": protocol["limitations"],
        "input_pins": {name: sha(base / name) for name in (
            "protocol.json", "release.json", "attempt.json", "budget.json", "startup.json",
            "row_index.json", "measurement_complete.json")},
    }
    summary["input_pins"].update({name: entry["sha256"] for name, entry in read(base / "row_index.json").items()})
    # Detect changes across the read, rather than trusting a receipt read before all rows.
    verify_protocol(base)
    verify_terminal(base, protocol)
    if any(sha(base / name) != digest for name, digest in summary["input_pins"].items()):
        raise ValueError("input changed during analysis")
    return summary, arrays


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    try:
        summary, arrays = analyze(args.study.resolve())
    except (ValueError, KeyError, OSError, TypeError, StopIteration) as error:
        result = {"status": "incomplete", "error": str(error), "outcomes_emitted": False}
        (args.out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
        return 1
    np.savez_compressed(args.out / "paired_arrays.npz", **arrays)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: summary[k] for k in ("status", "total_calls", "paired_arrays", "primary")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

