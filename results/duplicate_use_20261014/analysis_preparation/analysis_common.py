"""Independent ledger/accounting audit shared by J; NumPy only, no simulation.

Ledger checks copied from the separately reviewed H analysis, not the production scorer.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

LEDGER = (
    "income", "live_time", "sec_int", "spikes", "kappa_sum", "contact_events", "claims", "births", "rejects",
    "rejects_wall", "deaths", "kills", "cost", "guard_charge", "net", "F", "n_end", "n_peak", "t_end", "status",
    "events", "beats", "P_int", "arrivals", "arrivals_dropped", "packets", "morph_secreted", "morph_decayed",
    "morph_lost", "morph_content_end", "morph_inflight_end", "chem_clamps", "last_birth", "ticks", "t_ext",
    "captures", "misses", "clicks", "b2_clicks", "respawns", "nudges", "rec_cand", "rec_accept", "rec_events",
    "rec_gain", "samples", "dist_sum", "zone_samples", "path", "X_end", "Y_end", "n_S_end", "n_M_end", "n_H_end",
    "live_S", "live_M", "live_H")


L = {name: i for i, name in enumerate(LEDGER)}


COLS = LEDGER + ("F_kernel", "extinct_charge", "window")


COSTS = (("living", "c_live", "live_time"), ("spiking", "c_spike", "spikes"),
         ("twitching", "c_tw", "kappa_sum"), ("messages", "c_msg", "contact_events"),
         ("division", "c_div", "claims"), ("secretion", "c_sec", "sec_int"),
         ("missed_clicks", "c_miss", "misses"), ("receptors", "c_rec", "rec_gain"))


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(label + " differs")


def identical(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def arrays(path):
    with np.load(path, allow_pickle=False) as value:
        return {key: value[key].copy() for key in value.files}


def stats(values, flags=False):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("paired statistics require finite one-dimensional values")
    mean, se = float(values.mean()), float(values.std(ddof=1) / np.sqrt(len(values)))
    result = {"mean": mean, "se": se, "n": len(values)}
    if flags:
        result.update(positive_above_3se=mean > 3 * se, negative_below_minus_3se=mean < -3 * se)
    return result


def check_stats(actual, saved, label):
    equal(actual["n"], saved["n"], label + " sample size")
    if any(not np.isclose(actual[key], saved[key], rtol=1e-11, atol=1e-12) for key in ("mean", "se")):
        raise ValueError(label + " paired estimate differs")
    for key in ("positive_above_3se", "negative_below_minus_3se"):
        if key in actual:
            equal(actual[key], saved[key], label + " descriptive flag")


def prices(world):
    return [(name, column, world[price]) for name, price, column in COSTS] + [
        ("decoy_clicks", "b2_clicks", max(0.0, -world["b2_value"]))]


def validate_row(row, world, n=512):
    """Rebuild every raw/production column, including guarded and extinct lives, without evaluator imports."""
    led = row["ledger"]
    if led.dtype != np.float64 or led.shape != (n, len(LEDGER)) or not np.isfinite(led).all():
        raise ValueError("invalid complete raw ledger")
    if any(row[key].shape != (n,) or not np.isfinite(row[key]).all() for key in COLS):
        raise ValueError("invalid production-scored column")
    for name in LEDGER:
        saved = row["F_kernel" if name == "F" else name]
        if not identical(saved, led[:, L[name]]):
            raise ValueError("raw ledger and saved production column differ: " + name)
    status = row["status"].astype(np.int64)
    if np.any(row["status"] != status) or np.any(status < 0) or np.any(status & (64 | 128)):
        raise ValueError("invalid implementation status cannot become evidence")
    ended = (status & (1 | 2 | 4)) != 0
    if np.any(~ended & (row["t_end"] != world["t0"] + world["T"])):
        raise ValueError("unexplained incomplete life")
    window = world["T"] - world["t_open"]
    if not np.all(row["window"] == window):
        raise ValueError("accounting window differs")
    cost = prices(world)[0][2] * row[prices(world)[0][1]]
    for _, column, price in prices(world)[1:]:
        cost = cost + price * row[column]
    guard = np.where((status & 6) != 0,
                     world["c_live"] * world["n_max"] * (world["t0"] + world["T"] - row["t_end"]), 0)
    extinction = world["c_live"] * np.where((status & 1) != 0,
        world["t0"] + world["T"] - np.maximum(row["t_ext"], world["t0"] + world["t_open"]), 0) / window
    income = world["R_cap"] * row["captures"] + max(0.0, world["b2_value"]) * row["b2_clicks"]
    reconstructed = {"income": income, "cost": cost, "guard_charge": guard, "net": income - cost - guard,
                     "extinct_charge": extinction,
                     "F_kernel": (income - cost - guard) / window}
    for key, value in reconstructed.items():
        if not np.allclose(row[key], value, rtol=1e-10, atol=1e-9):
            raise ValueError("independent accounting differs: " + key)
    if not identical(row["F"], row["F_kernel"] - row["extinct_charge"]):
        raise ValueError("production fitness differs from kernel minus extinction charge")
    for key in ("cpu_seconds", "wall_seconds"):
        if not np.isfinite(float(row[key])) or float(row[key]) < 0:
            raise ValueError("invalid saved row timing")
    return {"guarded": int(np.count_nonzero(status & 6)), "extinct": int(np.count_nonzero(status & 1)),
            "valid_other_status": int(np.count_nonzero(status & ~(1 | 2 | 4)))}
