"""Independent production ABI3 accounting, narrowly adapted from study I.

NumPy and standard library only: no engine, worker, mutation or simulation imports.
Raw ledger F is kernel fitness; saved named F includes the production extinction
charge. Guards and natural extinction remain in every paired fitness estimate.
This module validates row accounting, not study completeness or source identity.
"""

from __future__ import annotations

import math

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


def paired_terms(winner, parent, world):
    n = len(winner["F"])
    status = {"winner": validate_row(winner, world, n), "parent": validate_row(parent, world, n)}
    if not np.array_equal(winner["seeds"], parent["seeds"]):
        raise ValueError("paired rows have different ordered seeds")
    window = world["T"] - world["t_open"]
    vectors = {name: winner[name] - parent[name] for name in COLS}
    pieces = {
        "capture_income": (winner["income"] - parent["income"]) / window,
        "guard_charge_saving": (parent["guard_charge"] - winner["guard_charge"]) / window,
        "extinction_charge_saving": parent["extinct_charge"] - winner["extinct_charge"],
    }
    winner_total, winner_cost = physical_costs(winner, world)
    parent_total, parent_cost = physical_costs(parent, world)
    for name in winner_cost:
        pieces[name + "_cost_saving"] = (parent_cost[name] - winner_cost[name]) / window
    pieces["accounting_residual"] = vectors["F"] - sum(pieces.values())
    if not np.allclose(pieces["accounting_residual"], 0, rtol=0, atol=1e-9):
        raise ValueError("paired income/cost/penalty decomposition does not reconcile")
    total_cost_saving = (parent_total - winner_total) / window
    report = {
        "columns": {name: stats(value) for name, value in vectors.items()},
        "fitness_pieces": {name: stats(value) for name, value in pieces.items()},
        "total_cost_saving": stats(total_cost_saving),
        "status": status,
        "interpretation": "Local production-fitness and capture effects; no isolated tracking, prediction or memory claim.",
    }
    return report, dict(vectors, **{"F__" + name: value for name, value in pieces.items()})
