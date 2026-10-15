"""NumPy-only physical accounting for explicitly labelled ABI3 SCRATCH visibility ledgers.

Columns 21/22 are scratch dark/late capture counters, not production beats/P_int.
No simulation, engine imports, controller code or worker helpers are executed.
"""

from __future__ import annotations

import math

import numpy as np

RAW_LEDGER = (
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
    "dark_captures",
    "late_captures",
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
L = {name: i for i, name in enumerate(RAW_LEDGER)}
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
    "dark_captures",
    "late_captures",
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
    name for name in RAW_LEDGER if name not in ("net", "F", "t_end", "last_birth", "t_ext", "X_end", "Y_end")
)
PRICE_COLUMNS = (
    ("living", "c_live", "live_time"),
    ("spikes", "c_spike", "spikes"),
    ("twitches", "c_tw", "kappa_sum"),
    ("messages", "c_msg", "contact_events"),
    ("division", "c_div", "claims"),
    ("secretion", "c_sec", "sec_int"),
    ("misses", "c_miss", "misses"),
    ("receptors", "c_rec", "rec_gain"),
)
ALIASES = {
    "raw_contract": "ABI3 scratch visibility, 57 columns",
    "raw_column_21": "dark_captures (replaces beats in scratch only)",
    "raw_column_22": "late_captures (replaces P_int in scratch only)",
    "derived_low_light_captures": "raw dark_captures, physically bridged to production ABI4 column57",
    "production_abi4_ledger": False,
}


def identical(a, b):
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def mean_se(values):
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("paired statistics require at least two finite one-dimensional values")
    return {"mean": float(x.mean()), "se": float(x.std(ddof=1) / math.sqrt(len(x))), "n": len(x)}


def ratio_of_paired_means(numerator, denominator):
    a, b = np.asarray(numerator, dtype=np.float64), np.asarray(denominator, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError("ratio arrays must be paired")
    num, den = mean_se(a), mean_se(b)
    result = {
        "numerator": num,
        "denominator": den,
        "value": None,
        "se": None,
        "reliable": False,
        "method": "ratio of paired means; delta-method SE; no clipping",
    }
    if den["mean"] > 0:
        value = num["mean"] / den["mean"]
        result.update(
            value=value,
            se=float((a - value * b).std(ddof=1) / (math.sqrt(len(a)) * den["mean"])),
            reliable=den["mean"] > 3 * den["se"],
        )
    return result


def physical_costs(ledger, world):
    parts = {name: world[price] * ledger[:, L[column]] for name, price, column in PRICE_COLUMNS}
    parts["second_blob"] = max(0.0, -world["b2_value"]) * ledger[:, L["b2_clicks"]]
    total = parts[PRICE_COLUMNS[0][0]].copy()
    for name, _, _ in PRICE_COLUMNS[1:]:
        total = total + parts[name]
    total = total + parts["second_blob"]
    return total, parts


def reconcile(ledger, world, n=512):
    if not isinstance(ledger, np.ndarray) or ledger.dtype != np.float64 or ledger.shape != (n, 57):
        raise ValueError("need complete float64 (n,57) ABI3 scratch ledger")
    if not np.isfinite(ledger).all():
        raise ValueError("nonfinite raw ledger column")
    if any(np.any(ledger[:, L[key]] < 0) for key in NONNEGATIVE):
        raise ValueError("negative physical count or quantity")
    for name in COUNTS:
        x = ledger[:, L[name]]
        if np.any(x != np.floor(x)):
            raise ValueError("nonintegral raw count: " + name)
    status = ledger[:, L["status"]]
    if np.any(status != np.floor(status)) or np.any(status > 511):
        raise ValueError("invalid raw status encoding")
    if np.any(status.astype(np.int64) & (2 | 4 | 8 | 16 | 64 | 128)):
        raise ValueError("guard, truncated log, capacity or ledger failure invalidates the whole study")
    if np.any(status.astype(np.int64) & 1):
        raise ValueError("unexpected extinction in fixed static candidates")
    end = ledger[:, L["t_end"]]
    extinct = (status.astype(np.int64) & 1) != 0
    if (
        np.any(end < world["t0"])
        or np.any(end > world["t0"] + world["T"])
        or np.any((~extinct) & (end != world["t0"] + world["T"]))
    ):
        raise ValueError("unexplained incomplete physical life")
    if world["t_open"] != 0 or world["b2_amp"] != 0:
        raise ValueError("this fixed visibility audit requires full-life accounting and no second blob")
    if np.any(ledger[:, L["guard_charge"]] != 0) or np.any(ledger[:, L["b2_clicks"]] != 0):
        raise ValueError("unexpected guard charge or second-blob click")
    captures = ledger[:, L["captures"]]
    if np.any(ledger[:, L["dark_captures"]] > captures) or np.any(ledger[:, L["late_captures"]] > captures):
        raise ValueError("scratch phase captures exceed total captures")
    if not np.array_equal(captures + ledger[:, L["misses"]], ledger[:, L["clicks"]]):
        raise ValueError("capture and miss accounting does not sum to clicks")
    for small, large in (
        ("zone_samples", "samples"),
        ("rec_accept", "rec_cand"),
        ("rec_events", "rec_accept"),
        ("n_end", "n_peak"),
    ):
        if np.any(ledger[:, L[small]] > ledger[:, L[large]]):
            raise ValueError(f"{small} exceeds {large}")
    if not np.array_equal(sum(ledger[:, L[k]] for k in ("n_S_end", "n_M_end", "n_H_end")), ledger[:, L["n_end"]]):
        raise ValueError("plane cell counts do not sum to final cells")
    if not np.allclose(
        sum(ledger[:, L[k]] for k in ("live_S", "live_M", "live_H")), ledger[:, L["live_time"]], rtol=1e-9, atol=1e-9
    ):
        raise ValueError("plane cell-times do not sum to total cell-time")
    # Initial cells enter the census but are excluded from the production births counter.
    # These fixed candidates cannot grow or die; candidate-bound census is checked by static_body.
    for name in ("births", "deaths", "kills", "claims", "rejects", "rejects_wall"):
        if np.any(ledger[:, L[name]] != 0):
            raise ValueError("unexpected fixed-body growth or death event: " + name)
    morph = sum(ledger[:, L[k]] for k in ("morph_decayed", "morph_lost", "morph_content_end", "morph_inflight_end"))
    if not np.allclose(morph, ledger[:, L["morph_secreted"]], rtol=1e-9, atol=1e-9):
        raise ValueError("morphogen accounting differs")
    cost, parts = physical_costs(ledger, world)
    income = world["R_cap"] * captures
    net = income - cost - ledger[:, L["guard_charge"]]
    fitness = net / (world["T"] - world["t_open"])
    for name, value in (("income", income), ("net", net), ("F", fitness)):
        if not identical(np.asarray(value, dtype=np.float64), ledger[:, L[name]]):
            raise ValueError("independent " + name + " differs from raw bytes")
    if not np.allclose(cost, ledger[:, L["cost"]], rtol=1e-9, atol=1e-9):
        raise ValueError("independent event cost does not reconcile")
    return {
        "cost": cost,
        "parts": parts,
        "income": income,
        "fitness": fitness,
        "low_light_captures": ledger[:, L["dark_captures"]].copy(),
        "bright_captures": captures - ledger[:, L["dark_captures"]],
    }


def paired_contrast(left, right, world):
    n = len(left)
    a, b = reconcile(left, world, n), reconcile(right, world, n)
    window = world["T"] - world["t_open"]
    delta = left - right
    vectors = {name: delta[:, L[name]] for name in RAW_LEDGER}
    vectors["low_light_captures"] = a["low_light_captures"] - b["low_light_captures"]
    vectors["bright_captures"] = a["bright_captures"] - b["bright_captures"]
    pieces = {"capture_income": (a["income"] - b["income"]) / window}
    pieces.update({name + "_cost_saving": (b["parts"][name] - a["parts"][name]) / window for name in a["parts"]})
    if not np.allclose(sum(pieces.values()), vectors["F"], rtol=1e-10, atol=1e-10):
        raise ValueError("paired physical fitness decomposition differs")
    summary = {
        "columns": {name: mean_se(value) for name, value in vectors.items()},
        "fitness_pieces": {name: mean_se(value) for name, value in pieces.items()},
        "low_light_share_of_extra_captures": ratio_of_paired_means(vectors["low_light_captures"], vectors["captures"]),
    }
    return summary, dict(vectors, **{"F__" + name: value for name, value in pieces.items()})
