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
ROLES = ("AI_control_start", "AL_mixture_start", "current_value_final", "high_value_final")
ARMS = ("current_value", "high_value")
WORLDS = ("pool", "persistent", "blink80_5", "turn100_blink80_5")
PAIRS = ((1, 0), (2, 0), (3, 0), (2, 1), (3, 1), (3, 2))
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
        raise ValueError("fixed 4-genome by 4-world matrix required")
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
    for world in ("pool", "blink80_5", "turn100_blink80_5"):
        for role in ROLES:
            record(f"environment__{world}_minus_persistent__{role}", {
                name: rows[world][role][name] - rows["persistent"][role][name] for name in names})
        for a, b in PAIRS:
            record(f"interaction__{world}_minus_persistent__{ROLES[a]}_minus_{ROLES[b]}", {
                name: ((rows[world][ROLES[a]][name] - rows[world][ROLES[b]][name])
                       - (rows["persistent"][ROLES[a]][name] - rows["persistent"][ROLES[b]][name]))
                for name in names})
    return reports, arrays


RETENTION = ((1, 0, "persistent"), (2, 0, "persistent"), (3, 0, "persistent"),
             (2, 1, "pool"), (2, 1, "persistent"), (3, 1, "pool"), (3, 1, "persistent"))


def retention_diagnostics(rows):
    reports, arrays = {}, {}
    for candidate, reference, world in RETENTION:
        role, ancestor = ROLES[candidate], ROLES[reference]
        new, old = rows[world][role]["captures"], rows[world][ancestor]["captures"]
        key = f"{role}_vs_{ancestor}__{world}"
        difference, conventional = new - old, new - .9 * old
        reports[key] = {
            "capture_difference": describe(difference),
            "retained_90_percent_vector": describe(conventional),
            "passes_conventional_10_percent_diagnostic": describe(conventional)["lower_3se"] > 0,
            "reference_mean_captures": float(old.mean()), "candidate_mean_captures": float(new.mean()),
            "mean_capture_ratio": float(new.mean() / old.mean()) if old.mean() > 0 else None,
            "interpretation": "Conventional 10% diagnostic; a null difference is not established retention.",
        }
        arrays["retention__" + key + "__capture_difference"] = difference
        arrays["retention__" + key + "__ninety_percent_reference"] = conventional
    return reports, arrays


def verdicts(rows):
    def gain(world, new, old):
        return describe(rows[world][new]["captures"] - rows[world][old]["captures"])
    primary = {world: gain(world, ROLES[3], ROLES[2]) for world in ("pool", "persistent")}
    own_start = {role: {world: gain(world, role, ROLES[1]) for world in ("pool", "persistent")}
                 for role in ROLES[2:]}
    return {"primary_high_minus_current_captures": primary,
            "joint_primary_capture_advantage": all(v["lower_3se"] > 0 for v in primary.values()),
            "endpoint_minus_AL_start_captures": own_start,
            "strict_simultaneous_capture_gain_over_AL_start": {
                role: all(v["lower_3se"] > 0 for v in worlds.values()) for role, worlds in own_start.items()},
            "confirmation_capture_value": 500,
            "ancestral_L92_restoration_tested": False,
            "evolutionary_replicate_pairs": 1,
            "interpretation": "One paired selection comparison, not evolutionary replication or a proof of richer computation."}


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
    value = path if isinstance(path, dict) else read(path)
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
            or protocol["research_lives"] != 28748 or protocol["startup_lives"] != 8
            or protocol["total_calls"] != 28756 or protocol["confirmation_lives"] != 8192
            or protocol["confirmation_startup_lives"] != 4
            or protocol["extinct_charge"] is not True or protocol["retention_margin_fraction"] != .1):
        raise ValueError("fixed matrix, accounting, margin or life counts changed")
    if protocol["budget"] != {"cpu_seconds": 10800, "wall_seconds": 5400, "threads": 2,
            "workers": 1, "cleanup_margin_seconds": 10,
            "search_cpu_seconds": 7200, "confirmation_cpu_seconds": 3600,
            "rss_bytes": 4 * 1024**3, "minimum_available_bytes": 4 * 1024**3, "address_space_bytes": 8 * 1024**3}:
        raise ValueError("fixed sequential worker resource scope differs")
    if protocol["search"] != {"arms": list(ARMS), "generations": 4,
            "research_lives_per_arm": 10278, "startup_lives_per_arm": 2,
            "initial_lives": 8, "recheck_lives": 8, "parents": 32, "offspring": 224}:
        raise ValueError("native paired search scope differs")
    seeds = protocol["seeds"]
    if (len(seeds) != 512 or len(set(seeds)) != 512
            or any(type(s) is not int or not 0 <= s < 2**64 for s in seeds)
            or {11, 55040000}.intersection(seeds)):
        raise ValueError("expected 512 unique research seeds disjoint from retained truth seeds")
    status_bits = {"extinct": 1, "guard_cells": 2, "guard_events": 4, "raster_overflow": 8,
                   "fate_overflow": 16, "chem_clamp": 32, "ledger_mismatch": 64, "capacity": 128, "wall": 256}
    if protocol["status_bits"] != status_bits:
        raise ValueError("ledger status mapping differs")
    if protocol["hash_names"] != ["all", "spikes", "fate", "chem", "world"]:
        raise ValueError("recorded hash names differ")
    expected_primary = [{"world": world, "new": ROLES[3], "old": ROLES[2], "metric": "captures"}
                        for world in ("pool", "persistent")]
    if protocol["primary"] != expected_primary:
        raise ValueError("primary contrast differs")
    for key in ("input_pins", "source_pins", "production_pins"):
        if not protocol[key]:
            raise ValueError("empty input/source closure")
        for name, digest in protocol[key].items():
            path = external(base, name) if key == "production_pins" else local(base, name)
            if sha(path) != digest:
                raise ValueError("changed pinned file: " + name)
    if protocol["source_pins"].get("analyze.py") != sha(Path(__file__)):
        raise ValueError("executing analyzer differs from reviewed source")
    expected = read(base / "inputs/startup_identity.json")["identity"]
    if (protocol["expected_numerical_identity"] != expected
            or any(protocol["production_pins"].get(name) != digest for name, digest in expected["sources"].items())):
        raise ValueError("retained numerical identity/source pins differ")
    seed_audit = read(base / "inputs/seed_audit.json")
    if (seed_audit["status"] != "passed" or seed_audit["confirmation_seeds"] != seeds
            or seed_audit["native_seed"] != protocol["native_seed"]):
        raise ValueError("seed inventory differs")
    for role, reference in zip(ROLES[:2], (protocol["ancestral_reference"], protocol["reference"])):
        path = local(base, reference["path"])
        if (reference["role"] != role or sha(path) != reference["file_sha256"]
                or protocol["original_input_pins"][reference["source"]] != sha(path)
                or hashlib.sha256(json_genome(path).tobytes()).hexdigest() != reference["raw_sha256"]):
            raise ValueError("retained reference bytes or origin differs")
    record = protocol["population_start"]
    population = read(local(base, record["population_file"]))
    table = np.stack([json_genome({"dims": population["dims"], "params": v}) for v in population["genomes"]])
    row_hashes = [hashlib.sha256(v.tobytes()).hexdigest() for v in table]
    if (sha(local(base, record["population_file"])) != record["file_sha256"]
            or table.shape != (32, 875) or record["shape"] != [32, 875]
            or population["ids"] != record["old_ids"] or len(set(population["ids"])) != 32
            or record["new_ids"] != list(range(32)) or record["row_sha256"] != row_hashes
            or record["population_raw_sha256"] != hashlib.sha256(table.tobytes()).hexdigest()
            or not identical(table[0], json_genome(path))):
        raise ValueError("full original population/order or rank-zero reference differs")
    crosswalk = [{"old_id": old, "new_id": i, "row": i, "raw_sha256": row_hashes[i]}
                 for i, old in enumerate(population["ids"])]
    if record["old_to_new"] != crosswalk:
        raise ValueError("population old-to-new ID crosswalk differs")
    if set(protocol["configs"]) != set(ARMS) or type(protocol["native_seed"]) is not int:
        raise ValueError("two native configs/shared seed required")
    spec_path = external(base, "src/life/spec.py")
    cls = next(node for node in ast.parse(spec_path.read_text()).body
               if isinstance(node, ast.ClassDef) and node.name == "World")
    keys = [node.target.id for node in cls.body if isinstance(node, ast.AnnAssign)
            and node.target.id not in ("name", "stage", "implemented", "lattice", "lives")]
    if len(keys) != 70 or keys[-4:] != ["visibility_mode", "visibility_on", "visibility_off", "visibility_low"]:
        raise ValueError("pinned World dataclass layout differs")
    persistent = dict(read(base / "inputs/persistent_protocol.json")["world"],
                      visibility_mode=0, visibility_on=0., visibility_off=0., visibility_low=1.)
    blink = dict(persistent, visibility_mode=2, visibility_on=80., visibility_off=5., visibility_low=0.)
    expected = {"persistent": persistent,
                "pool": dict(persistent, d0=.5, d_min=.25, sigma=.4, lam_s=4., v_t=.1, tau_turn=20.),
                "blink80_5": blink, "turn100_blink80_5": dict(blink, tau_turn=100.)}
    if (persistent["v_t"], persistent["tau_turn"], persistent["d0"], persistent["d_min"], persistent["R_cap"]) != (.3, 200, 1, .5, 500):
        raise ValueError("retained persistent-target physics differs")
    if protocol["selection_worlds"] != {k: expected[k] for k in ("pool", "persistent")}:
        raise ValueError("fixed two-context selection physics differs")
    for name in WORLDS:
        rec = protocol["worlds"][name]
        abi = 4 if name in ("blink80_5", "turn100_blink80_5") else 3
        names = ABI4_LEDGER if abi == 4 else LEDGER
        if rec["abi"] != abi or rec["world"] != expected[name] or rec["ledger_columns"] != list(names):
            raise ValueError("planned world or ABI differs: " + name)
        vector = np.asarray([float(rec["world"][k]) for k in keys[:70 if abi == 4 else 66]], dtype=np.float64)
        if not identical(np.asarray(rec["world_vector"], dtype=np.float64), vector):
            raise ValueError("independent world packing differs: " + name)
    return protocol


def json_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_endpoints(base, protocol, identity):
    manifest = read(base / "endpoints.json")
    if (manifest["protocol_sha256"] != sha(base / "protocol.json") or manifest["roles"] != list(ROLES)
            or set(manifest["searches"]) != set(ARMS) or len(manifest["genomes"]) != 4
            or manifest["selection"] != "Both complete generation4 final population rank0 endpoints fixed before confirmation."):
        raise ValueError("frozen endpoint matrix differs")
    expected_paths = [protocol["ancestral_reference"]["path"], protocol["reference"]["path"], *[f"runs/{arm}/best_genome.json" for arm in ARMS]]
    for role, rec, path in zip(ROLES, manifest["genomes"], expected_paths):
        if (rec["role"] != role or rec["path"] != path or sha(local(base, path)) != rec["file_sha256"]
                or hashlib.sha256(json_genome(local(base, path)).tobytes()).hexdigest() != rec["raw_sha256"]):
            raise ValueError("frozen endpoint genome bytes differ")
    if any(manifest["genomes"][i]["raw_sha256"] != protocol[key]["raw_sha256"]
           for i, key in enumerate(("ancestral_reference", "reference"))):
        raise ValueError("starting reference changed")
    cohorts, reviews = [], {}
    for index, arm in enumerate(ARMS, 2):
        folder, record = base / "runs" / arm, manifest["searches"][arm]
        paths = {"checkpoint_sha256": "checkpoint.pt", "genome_file_sha256": "best_genome.json",
                 "population_file_sha256": "population.json", "determinism_sha256": "determinism.json",
                 "results_sha256": "results.jsonl"}
        if any(sha(folder / path) != record[key] for key, path in paths.items()):
            raise ValueError("search artifact changed after endpoint freeze")
        if set(record["log_pins"]) != {"curves.jsonl", "lineage.jsonl", "clones.jsonl"}:
            raise ValueError("native checkpoint log coverage differs")
        if any(sha(folder / path) != digest for path, digest in record["log_pins"].items()):
            raise ValueError("native log changed after endpoint freeze")
        curves, lineage = json_lines(folder / "curves.jsonl"), json_lines(folder / "lineage.jsonl")
        if ([r["gen"] for r in curves] != list(range(4))
                or [r["gen"] for r in curves if "valid" in r] != [0, 3]
                or len(lineage) != 5 or lineage[0]["ids"] != list(range(32)) or lineage[0]["copies"]):
            raise ValueError("four-generation native history/import differs")
        keys = ("pop_invalid", "pop_mismatch", "recheck_invalid")
        if any(not math.isfinite(float(r[k])) or float(r[k]) != 0 for r in curves for k in keys):
            raise ValueError("nonzero native invalid/mismatch summaries")
        health = {key: max(float(row[key]) for row in curves) for key in keys}
        if record["search_health"] != health or record["generation"] != 4 or record["rank"] != 0:
            raise ValueError("search health or endpoint selection differs")
        population = read(folder / "population.json")
        table = np.stack([json_genome({"dims": population["dims"], "params": p}) for p in population["genomes"]])
        fitness = np.asarray(population["fitness"], dtype=np.float64)
        if (table.shape != (32, 875) or fitness.shape != (32,) or not np.isfinite(fitness).all()
                or np.any(fitness[:-1] < fitness[1:]) or len(set(population["ids"])) != 32
                or hashlib.sha256(table.tobytes()).hexdigest() != record["population_raw_sha256"]
                or hashlib.sha256(table[0].tobytes()).hexdigest() != record["genome_raw_sha256"]
                or record["genome_raw_sha256"] != manifest["genomes"][index]["raw_sha256"]):
            raise ValueError("full final population or ordinary rank-zero endpoint differs")
        extended = record["numerical_identity"]
        configured_population = {"version": 1, **protocol["population_start"], "source_pins": {
            name: sha(base / name) for name in ("population_loader.py", "search.py")}}
        if (extended.get("population_start") != configured_population
                or {k: v for k, v in extended.items() if k not in ("population_start", "retention_selection")} != identity
                or read(folder / "determinism.json") != extended):
            raise ValueError("search base/loader startup identity differs")
        # The selection identity is also bound to the pinned config and independently reviewed adapter.
        expected_selection = {"version": 1, "arm": arm, "worlds": protocol["selection_worlds"],
            "rule": "gen indices even=pool odd=persistent; gen R_cap by arm; diagnostics=persistent R_cap500",
            "selection_capture_value": 500. if arm == "current_value" else 2000.,
            "source_pins": {"selection.py": sha(base / "selection.py")}}
        if extended["retention_selection"] != expected_selection:
            raise ValueError("selection-arm/source/world identity differs")
        marker = read(folder / "search_complete.json")
        if (marker["status"] != "complete" or marker["arm"] != arm
                or marker["research_lives"] != 10278 or marker["startup_lives"] != 2
                or marker["protocol_sha256"] != sha(base / "protocol.json")
                or marker["release_sha256"] != sha(base / "release.json")
                or marker["count_proof"] != {"selection": 10240, "valid": 32, "final": 6,
                    "half_duration": 2, "native_evals": 1280, "generations": 4, "children_per_generation": 224}
                or set(marker["output_pins"]) != {"checkpoint.pt", "config.yaml", "determinism.json",
                    "curves.jsonl", "lineage.jsonl", "population.json", "best_genome.json", "results.jsonl"}
                or any(sha(folder / name) != digest for name, digest in marker["output_pins"].items())):
            raise ValueError("native search completion provenance/counts differ")
        if any(sha(folder / name) != meta["sha256"] or (folder / name).stat().st_size != meta["bytes"]
               for name, meta in marker["checkpoint_log_pins"].items()):
            raise ValueError("native checkpoint log size/hash differs")
        for g, (curve, line) in enumerate(zip(curves, lineage[1:])):
            if (curve["evals"] != 320 * (g + 1) or curve["recheck_k"] != 64 or line["gen"] != g
                    or len(line["children"]) != 224 or len(line["seeds"]) != 8
                    or len(line["recheck"]["seeds"]) != 8 or len(line["recheck"]["ids"]) != 64
                    or not all(math.isfinite(float(curve[k])) for k in ("fitness", "mean_fitness", "pop_guard"))):
                raise ValueError("native generation evaluation counts/finiteness differ")
        for key in (*keys, "pop_guard"):
            if marker["health"][key] != [r[key] for r in curves]:
                raise ValueError("recorded native health differs")
        diagnostic = json_lines(folder / "results.jsonl")
        if len(diagnostic) != 1 or any(diagnostic[0][k] != v for k, v in {
                "seed": protocol["native_seed"], "abi": 3, "generations": 4,
                "lives": 2, "founders_sampled": 0, "top_best_rank": 0,
                "invalid_lives": 0, "mismatch_lives": 0, "forks": {}, "heldout_score": None}.items()):
            raise ValueError("native final diagnostic scope or health differs")
        first = lineage[1]
        children = [{k: child[k] for k in ("id", "pa", "pb", "mask", "ops")} for child in first["children"]]
        if len(children) != 224:
            raise ValueError("first offspring count differs")
        cohorts.append({"founder_ids": lineage[0]["ids"], "copies": lineage[0]["copies"], "children": children})
        reviews[arm] = {"generation": 4, "rank": 0, "health": health,
                        "final_population_rows": 32, "search_research_lives": 10278,
                        "startup_lives": 2, "full_recorded_genetics_replay_performed_here": False}
    if cohorts[0] != cohorts[1]:
        raise ValueError("first recorded genetic cohorts differ")
    proof = read(base / "first_cohort_replay.json")
    if (manifest["first_cohort_replay_sha256"] != sha(base / "first_cohort_replay.json")
            or proof["status"] != "passed" or proof["protocol_sha256"] != sha(base / "protocol.json")
            or proof["initial_rows"] != 32 or proof["offspring_per_arm"] != 224
            or proof["initial_population_raw_sha256"] != protocol["population_start"]["population_raw_sha256"]
            or proof["initial_row_sha256"] != protocol["population_start"]["row_sha256"]
            or proof["all_256_candidate_bytes_equal"] is not True
            or proof["recorded_genetic_signatures_equal"] is not True
            or proof["simulated_lives"] != 0 or proof["random_draws"] != 0
            or set(proof["runs"]) != set(ARMS)):
        raise ValueError("first-cohort replay proof differs")
    for arm, cohort in zip(ARMS, cohorts):
        item = proof["runs"][arm]
        signature = hashlib.sha256(json.dumps(cohort["children"], sort_keys=True,
                                              separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if (item["genetic_signature_sha256"] != signature
                or item["lineage_sha256"] != sha(base / "runs" / arm / "lineage.jsonl")
                or len(item["candidate_row_sha256"]) != 256
                or item["candidate_row_sha256"][:32] != proof["initial_row_sha256"]):
            raise ValueError("first-cohort signature/raw-row proof differs")
    for key in ("candidate_raw_sha256", "candidate_row_sha256", "genetic_signature_sha256"):
        if proof["runs"][ARMS[0]][key] != proof["runs"][ARMS[1]][key]:
            raise ValueError("first-cohort paired byte proof differs")
    return manifest, {"searches": reviews, "first_recorded_genetic_cohort_exact": True,
                      "first_256_raw_rows_replayed_before_confirmation": True,
                      "limitation": "NumPy reader binds public populations/checkpoint hashes and summaries. Full recorded genetic/ranking replay is a separate independent review; raw search ledgers are not complete."}


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


def load_rows(base, protocol, endpoints):
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
            if entry["sha256"] != sha(path) or entry["lives"] != 512:
                raise ValueError("row index hash or count differs")
            with np.load(path, allow_pickle=False) as raw:
                row = {key: raw[key].copy() for key in raw.files}
            for key, value in (("role", role), ("world_name", world),
                               ("protocol_sha256", sha(base / "protocol.json")),
                               ("genome_raw_sha256", endpoints["genomes"][i]["raw_sha256"]),
                               ("endpoints_sha256", sha(base / "endpoints.json"))):
                if scalar(row, key) != value:
                    raise ValueError("row identity differs: " + key)
            if (entry["abi"] != protocol["worlds"][world]["abi"]
                    or any(float(scalar(row, key)) != entry[key] for key in ("cpu_seconds", "wall_seconds"))):
                raise ValueError("row scalar identity differs")
            rows[world][role], health[world][role] = reconstruct(row, protocol["worlds"][world], protocol["seeds"])
            cpu += float(scalar(row, "cpu_seconds"))
    complete = read(base / "measurement_complete.json")
    if complete != {"status": "complete", "research_lives": 8192, "startup_lives": 4, "rows": 16,
                    "protocol_sha256": sha(base / "protocol.json"), "row_index_sha256": sha(base / "row_index.json"),
                    "endpoints_sha256": sha(base / "endpoints.json")}:
        raise ValueError("measurement completion receipt differs")
    return rows, health, cpu


def verify_terminal(base, protocol):
    release, attempt, budget = (read(base / name) for name in ("release.json", "attempt.json", "budget.json"))
    digest, release_digest = sha(base / "protocol.json"), sha(base / "release.json")
    if (release.get("status") != "released" or release.get("protocol_sha256") != digest
            or attempt.get("protocol_sha256") != digest or attempt.get("release_sha256") != release_digest
            or budget.get("protocol_sha256") != digest or budget.get("release_sha256") != release_digest
            or budget.get("attempt_sha256") != sha(base / "attempt.json") or attempt["budget"] != protocol["budget"]):
        raise ValueError("explicit release, attempt or terminal binding differs")
    phases = (*ARMS, "confirmation")
    namespace = budget["pid_namespace"]
    if (not isinstance(namespace, str) or not namespace.startswith("pid:[")
            or attempt["pid_namespace"] != namespace or release["pid_namespace"] != namespace
            or set(attempt["commands"]) != set(phases) or list(budget["phase_records"]) != list(phases)):
        raise ValueError("sequential execution/namespace differs")

    def terminal(record):
        if (record.get("status") != "complete" or record.get("exit_code") != 0
                or record.get("worker_exit_code") != 0 or record.get("running") or record.get("queued")
                or record.get("cleanup_error") or record.get("reason") or record.get("error")
                or record["pid_namespace"] != namespace or record["protocol_sha256"] != digest
                or record["release_sha256"] != release_digest):
            raise ValueError("complete first attempt and clean teardown required")
        for key, cap in (("cpu_seconds", "cap_cpu_seconds"), ("wall_seconds", "cap_wall_seconds")):
            value = record[key]
            if (not isinstance(value, (int, float)) or not math.isfinite(value)
                    or value < 0 or value >= record[cap]):
                raise ValueError("invalid/over-cap resource accounting")
        cleanup = record["terminal_cleanup"]
        if (cleanup["pid_namespace"] != namespace or cleanup["checked_in_monitor"] is not True
                or cleanup["same_pid_namespace"] is not True or cleanup["all_owned_groups_exited"] is not True
                or cleanup["all_worker_identities_exited"] is not True or cleanup["remaining_group_members"]
                or cleanup["remaining_worker_identities"] or cleanup["remaining_descendants"]):
            raise ValueError("same-namespace teardown is not established")
        for item in record["process_identities"]:
            if any(type(item[k]) is not int or item[k] <= 0 for k in ("pid", "ppid", "pgid", "start_ticks")):
                raise ValueError("invalid four-field persisted process identity")
        reaped_cpu = 0.
        receipts = record["wait4_receipts"]
        if len({r["pid"] for r in receipts}) != len(receipts):
            raise ValueError("duplicate reaping receipt")
        for receipt in receipts:
            for key in ("user_cpu_seconds", "system_cpu_seconds"):
                value = receipt[key]
                if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError("invalid reaped CPU")
                reaped_cpu += value
        if reaped_cpu > record["cpu_seconds"] + 1e-6:
            raise ValueError("reaped CPU exceeds monitored total")
        return reaped_cpu

    terminal(budget)
    if (budget["cap_cpu_seconds"] != 10800 or budget["cap_wall_seconds"] != 5400
            or budget["search_cpu_cap"] != 7200 or budget["confirmation_cpu_cap"] != 3600
            or budget["phase"] != "confirmation"):
        raise ValueError("global resource caps or final phase differ")
    search_cpu, confirmation_cpu = budget["search_cpu_seconds"], budget["confirmation_cpu_seconds"]
    if (not all(isinstance(x, (int, float)) and math.isfinite(x) and x >= 0 for x in (search_cpu, confirmation_cpu))
            or search_cpu >= 7200 or confirmation_cpu >= 3600
            or abs(search_cpu + confirmation_cpu - budget["cpu_seconds"]) > 1e-6):
        raise ValueError("search/confirmation reserve accounting differs")
    identities = budget["process_identities"]
    if len(identities) != 4 or [r["name"] for r in identities] != ["monitor", *phases]:
        raise ValueError("one monitor and three sequential leaders required")
    monitor, *workers = identities
    fields = ("pid", "ppid", "pgid", "start_ticks")
    if ({k: monitor[k] for k in fields} != attempt["monitor"]
            or budget["owned_process_groups"] != [r["pid"] for r in workers]
            or len({r["pid"] for r in workers}) != 3):
        raise ValueError("global monitor/owned groups differ")
    cumulative, receipts = [], []
    for phase, worker in zip(phases, workers):
        entry = budget["phase_records"][phase]
        expected_path = f"execution/{phase}/budget.json"
        phase_base = base / "execution" / phase
        if entry != {"path": expected_path, "sha256": sha(base / expected_path)}:
            raise ValueError("phase budget pin differs")
        record, phase_attempt = read(base / expected_path), read(phase_base / "attempt.json")
        terminal(record)
        actual_workers = record["process_identities"]
        if (len(actual_workers) != 2 or actual_workers[0] != monitor
                or actual_workers[1] != {**worker, "name": "worker"}
                or worker["ppid"] != monitor["pid"] or worker["pgid"] != worker["pid"]
                or record["owned_process_groups"] != [worker["pid"]]
                or record["attempt_sha256"] != sha(phase_base / "attempt.json")
                or phase_attempt["monitor"] != attempt["monitor"]
                or phase_attempt["pid_namespace"] != namespace
                or phase_attempt["protocol_sha256"] != digest or phase_attempt["release_sha256"] != release_digest
                or phase_attempt["command"] != attempt["commands"][phase]):
            raise ValueError("phase worker/attempt ownership differs")
        expected_cap = 7200 if phase in ARMS else min(10800, search_cpu + 3600)
        if (record["cap_cpu_seconds"] != expected_cap
                or phase_attempt["budget"] != {"cpu_seconds": expected_cap,
                    "wall_seconds": record["cap_wall_seconds"], "threads": 2, "workers": 1,
                    "cleanup_margin_seconds": 10, "rss_bytes": 4 * 1024**3,
                    "minimum_available_bytes": 4 * 1024**3, "address_space_bytes": 8 * 1024**3}
                or not 0 < record["cap_wall_seconds"] <= 5400):
            raise ValueError("phase fixed/cumulative budget differs")
        if (record["cap_rss_bytes"] != 4 * 1024**3
                or record["minimum_available_bytes"] != 4 * 1024**3
                or record["worker_address_space_bytes"] != 8 * 1024**3
                or type(record["peak_owned_rss_bytes"]) is not int
                or not 0 <= record["peak_owned_rss_bytes"] < record["cap_rss_bytes"]):
            raise ValueError("phase memory cap/accounting differs")
        own = [r for r in record["wait4_receipts"] if r["pid"] == worker["pid"]]
        if len(own) != 1 or own[0]["exit_code"] != 0 or own[0]["wait_status"] != 0:
            raise ValueError("phase worker was not reaped successfully")
        cumulative.append(record["cpu_seconds"])
        receipts.extend(record["wait4_receipts"])
    if (not cumulative[0] <= cumulative[1] <= search_cpu <= cumulative[2] <= budget["cpu_seconds"]
            or budget["wait4_receipts"] != receipts):
        raise ValueError("sequential cumulative CPU/reaping differs")
    complete = read(base / "study_complete.json")
    if complete != {"status": "complete", "research_lives": 28748, "startup_lives": 8,
            "total_calls": 28756, "protocol_sha256": digest,
            "measurement_complete_sha256": sha(base / "measurement_complete.json"),
            "search_complete_pins": {arm: sha(base / "runs" / arm / "search_complete.json") for arm in ARMS}}:
        raise ValueError("whole study completion coverage differs")
    return budget


def analyze(base):
    protocol = verify_protocol(base)
    budget = verify_terminal(base, protocol)
    startup = verify_startup(base, protocol)
    endpoints, searches = verify_endpoints(base, protocol, startup["identity"])
    rows, health, row_cpu = load_rows(base, protocol, endpoints)
    if row_cpu > budget["confirmation_cpu_seconds"] + 1e-6:
        raise ValueError("raw row CPU exceeds monitored total")
    differences, arrays = contrasts(rows)
    retention, extra = retention_diagnostics(rows)
    arrays.update(extra)
    if len(arrays) != 4064:
        raise ValueError("complete 4064-vector output required")
    summary = {
        "status": "complete", "protocol_sha256": sha(base / "protocol.json"),
        "research_lives": 28748, "startup_lives": 8, "total_calls": 28756, "raw_rows": 16,
        "raw_confirmation_lives": 8192, "native_search_lives": 20556, "searches": searches,
        "paired_arrays": len(arrays), "row_cpu_seconds": row_cpu,
        "cpu_seconds": budget["cpu_seconds"], "wall_seconds": budget["wall_seconds"],
        "absolute": {w: {r: {k: describe(v) for k, v in rows[w][r].items()} for r in ROLES} for w in WORLDS},
        "contrasts": differences, "retention": retention, "verdicts": verdicts(rows), "health": health,
        "primary": {f"{c['world']}__{c['new']}_minus_{c['old']}":
                    differences[f"within__{c['world']}__{c['new']}_minus_{c['old']}"][c["metric"]]
                    for c in protocol["primary"]},
        "startup": startup, "limitations": protocol["limitations"],
        "input_pins": {name: sha(base / name) for name in (
            "protocol.json", "release.json", "attempt.json", "budget.json", "startup.json",
            "row_index.json", "measurement_complete.json", "endpoints.json", "study_complete.json", "first_cohort_replay.json")},
    }
    summary["input_pins"].update({name: entry["sha256"] for name, entry in read(base / "row_index.json").items()})
    for arm in ARMS:
        folder = base / "runs" / arm
        marker = read(folder / "search_complete.json")
        summary["input_pins"][f"runs/{arm}/search_complete.json"] = sha(folder / "search_complete.json")
        summary["input_pins"].update({f"runs/{arm}/{name}": digest for name, digest in marker["output_pins"].items()})
    for phase in (*ARMS, "confirmation"):
        for name in ("attempt.json", "budget.json"):
            path = f"execution/{phase}/{name}"
            summary["input_pins"][path] = sha(base / path)
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

