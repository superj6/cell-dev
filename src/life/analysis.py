"""Measurements on finished lives: summaries, paired comparisons, size curves under the oracle cap, and an Euler
re-integration of the BELL-1 lumen (docs/ONE_LIFE_DESIGN.md: EVALUATION PROTOCOL and gates G1-G10)."""
from __future__ import annotations

import math

import numpy as np

from src.life import spec


def summary(F) -> dict:
    """mean, standard error, median and fraction of lives with F > 0."""
    F = np.asarray(F, dtype=np.float64)
    se = float(F.std(ddof=1) / math.sqrt(len(F))) if len(F) > 1 else 0.0
    return dict(mean=float(F.mean()), se=se, median=float(np.median(F)), frac_pos=float(np.mean(F > 0)), n=len(F))


def z_diff(a: dict, b: dict) -> float:
    """(a - b) in units of their combined standard error (``summary`` dicts); 0 when both are exact and equal."""
    se = math.hypot(a["se"], b["se"])
    d = a["mean"] - b["mean"]
    return d / se if se > 0 else (0.0 if d == 0 else math.copysign(math.inf, d))


def paired(a, b) -> dict:
    """Mean, standard error and z of the per-life differences a - b (lives matched by seed)."""
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    se = float(d.std(ddof=1) / math.sqrt(len(d))) if len(d) > 1 else 0.0
    m = float(d.mean())
    return dict(mean=m, se=se, z=m / se if se > 0 else (0.0 if m == 0 else math.copysign(math.inf, m)), n=len(d))


def curve_seeds(N: int, lives: int, seed0: int = 0) -> list[int]:
    """Life seeds of one size-curve point (the prototype's ``seed0 + 91 N + s``)."""
    return [seed0 + 91 * N + s for s in range(lives)]


# Re-registration (migration step 3, 2026-10-07): every gate measures on fresh lives seeded FRESH_SEED0 + s, shared by
# every size, organism and condition (common random numbers), disjoint from all registration seeds (G1 0..63; G3/G4
# 91 N + s, s < 36; the port check 400000 + 91 N + s; the test ladder 10^6 + 91 N + s). Screens that choose a
# candidate use SCREEN_SEED0 + s, so a chosen candidate is then measured on lives it was not chosen on.
FRESH_SEED0 = 5_000_000
SCREEN_SEED0 = 6_000_000


def fresh_seeds(lives: int, seed0: int = FRESH_SEED0, first: int = 0) -> list[int]:
    return [seed0 + s for s in range(first, lives)]


def income_rate(res) -> np.ndarray:
    """Income per cell-time unit of each life (0 for a life with no counted cell-time)."""
    live = np.asarray(res["live_time"], dtype=np.float64)
    return np.divide(np.asarray(res["income"], dtype=np.float64), live, out=np.zeros_like(live), where=live > 0)


def point(res) -> dict:
    """Summary of one batch of lives: F (mean, SE, median, fraction positive), final size, last birth, income per
    cell (x 1e3, mean and largest life), claims, spikes and extinctions."""
    rec = summary(res["F"])
    ipc = 1e3 * income_rate(res)
    rec.update(n_end=float(np.mean(res["n_end"])), last_birth=float(np.mean(res["last_birth"])),
               income_per_cell_e3=float(ipc.mean()), income_per_cell_max_e3=float(ipc.max()),
               claims=float(np.mean(res["claims"])), spikes=float(np.mean(res["spikes"])),
               extinct=int(np.sum((np.asarray(res["status"]).astype(np.int64) & spec.STATUS["extinct"]) != 0)))
    return rec


def best_size(F_by_size: dict, z_flat: float = 2.0) -> dict:
    """n* = the size with the largest mean F, F* its mean, and the flat top: every size whose paired difference from
    n* (lives matched by seed) is within ``z_flat`` SE. ``edge`` is set when n* is the largest size measured."""
    sizes = sorted(F_by_size)
    means = {N: float(np.mean(F_by_size[N])) for N in sizes}
    n = max(sizes, key=lambda N: means[N])
    flat = [N for N in sizes if N == n or paired(F_by_size[n], F_by_size[N])["z"] <= z_flat]
    return dict(n_star=int(n), F_star=means[n], se=summary(F_by_size[n])["se"], flat_top=[int(N) for N in flat],
                edge=bool(n == sizes[-1] and len(sizes) > 1))


def size_curve(org, sizes, lives: int = 36, seed0: int = 0, threads: int = 1, seeds=None, **world) -> dict[int, dict]:
    """Whole-life F of an organism (``handbuilt.Organism`` or ``GrnOrganism``) grown under oracle caps ``sizes``.

    The cap is a measurement tool, never part of a task (LIFE_ABI.md 11.3). Per size: the F summary, the mean final
    size, the mean time of the last birth, income per cell-time unit (x 1e3), and every life's F. Seeds are the
    prototype's ``curve_seeds(N, lives, seed0)`` unless ``seeds`` gives one list for every size.
    """
    out = {}
    for N in sizes:
        res = org.run(curve_seeds(N, lives, seed0) if seeds is None else seeds, cap=N, threads=threads, **world)
        rec = summary(res["F"])
        rec.update(n_end=float(res["n_end"].mean()), last_birth=float(res["last_birth"].mean()),
                   income_per_cell_e3=float(1e3 * np.mean(income_rate(res))), F=[float(x) for x in res["F"]])
        out[int(N)] = rec
    return out


def lifespans(fate_i, fate_f) -> dict[int, tuple[float, float]]:
    """uid -> (birth time, death time or inf) from a fate log (LIFE_ABI.md 4.11)."""
    out = {}
    for row, frow in zip(fate_i, fate_f):
        uid = int(row[1]) & spec.MASK64
        if row[0] == spec.FATE_KINDS["birth"]:
            out[uid] = (float(frow[0]), math.inf)
        elif row[0] == spec.FATE_KINDS["death"]:
            out[uid] = (out[uid][0], float(frow[0]))
    return out


def euler_income(raster_t, raster_uid, spans: dict[int, tuple[float, float]], w: spec.World,
                 dt: float = 1e-3) -> float:
    """Explicit-Euler income of the BELL-1 lumen, rebuilt from the spike raster and the cells' life spans.

    Assumes kappa = 1 in every phenotype, so a spike sets z to 1. On the grid t_j = t0 + j dt: P = (sum of z over
    live cells) / n, then dR = -R (P - th) / ((1 - th) tau_e) dt in systole, (1 - R) / tau_R dt in diastole, and the
    income h n (-dR) is summed in systole. The kernel integrates the same law in closed form (LIFE_ABI.md 9.2).
    """
    steps = int(round(w.T / dt))
    ts = w.t0 + np.arange(steps) * dt
    zsum = np.zeros(steps)
    n = np.zeros(steps)
    raster_t = np.asarray(raster_t)
    raster_uid = np.asarray(raster_uid).astype(np.uint64)
    for uid, (tb, td) in spans.items():
        alive = (ts >= tb) & (ts < td)
        n += alive
        ti = np.sort(raster_t[raster_uid == np.uint64(uid)])
        if len(ti) == 0:
            continue
        k = np.searchsorted(ti, ts, side="right")
        z = np.where(k > 0, np.exp(-(ts - ti[np.maximum(k - 1, 0)]) / w.tau_z), 0.0)
        zsum += np.where(alive, z, 0.0)
    P = np.divide(zsum, n, out=np.zeros(steps), where=n > 0)
    k_sys = dt / ((1.0 - w.th) * w.tau_e)
    k_dia = dt / w.tau_R
    R, income = 1.0, 0.0
    for Pj, nj in zip(P.tolist(), (w.h_inc * n).tolist()):
        if nj == 0.0:
            continue
        if Pj > w.th:
            dR = R * (Pj - w.th) * k_sys
            income += nj * dR
            R -= dR
        elif Pj < w.th_lo:
            R += (1.0 - R) * k_dia
    return income


def bootstrap_ci(x, level: float = 0.95, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap confidence interval of the mean of ``x`` (fixed resampling seed, so it is reproducible)."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    a = (1.0 - level) / 2.0
    return float(np.quantile(means, a)), float(np.quantile(means, 1.0 - a))


def phase_order(raster_t, raster_uid, fate_i, fate_f, kind: str, t0: float, t1: float) -> dict:
    """Beat synchrony of the cells alive at ``t1`` over the window [t0, t1) (the prototype's diag.phase_stats).

    The body's period is the median over cells (with more than 2 spikes in the window) of their median inter-spike
    interval. A cell's phase is the angle of the mean of exp(2 pi i t / period) over its window spikes; a silent cell
    has no phase and counts as 0 in R. Returns R (global Kuramoto order of the unit phasors, 1 = one beat), local (mean
    over pairs of live contacts that both spiked of cos(phase difference)), period, rate (spikes per cell per unit)
    and the number of cells. NaN values when the window holds fewer than 2 spiking cells.
    """
    from src.lattice import offsets

    spans = lifespans(fate_i, fate_f)
    site = {int(r[1]) & spec.MASK64: (int(r[3]), int(r[4])) for r in fate_i if r[0] == spec.FATE_KINDS["birth"]}
    alive = [u for u, (tb, td) in spans.items() if tb < t1 and td >= t1]
    t = np.asarray(raster_t, dtype=np.float64)
    uid = np.asarray(raster_uid).astype(np.uint64)
    sel = (t >= t0) & (t < t1)
    t, uid = t[sel], uid[sel]
    by = {u: np.sort(t[uid == np.uint64(u)]) for u in alive}
    nan = dict(R=float("nan"), local=float("nan"), period=float("nan"), rate=float("nan"), cells=len(alive))
    isis = [float(np.median(np.diff(ts))) for ts in by.values() if len(ts) > 2]
    spiking = [u for u in alive if len(by[u])]
    if len(spiking) < 2 or not isis:
        return nan
    per = float(np.median(isis))
    z = {u: np.exp(2j * math.pi * by[u] / per).mean() for u in spiking}
    zu = {u: v / max(abs(v), 1e-9) for u, v in z.items()}
    R = abs(sum(zu.values()) / len(alive))
    at = {site[u]: u for u in alive}
    pairs = []
    for u in spiking:
        a, b = site[u]
        for da, db in offsets(kind):
            v = at.get((a + da, b + db))
            if v is not None and v in zu:
                pairs.append(math.cos(np.angle(zu[u]) - np.angle(zu[v])))
    return dict(R=float(R), local=float(np.mean(pairs)) if pairs else float("nan"), period=per,
                rate=float(sum(len(by[u]) for u in alive) / len(alive) / (t1 - t0)), cells=len(alive))


TRAP_IPC, TRAP_LOCAL = 10e-3, 0.8  # design: trap flag = income per cell < 10e-3 with local order > 0.8


def is_trap(income_per_cell: float, local: float) -> bool:
    """Phase-wave trap: locally synchronous (local order above 0.8) but earning almost nothing per cell."""
    return bool(income_per_cell < TRAP_IPC and local > TRAP_LOCAL)
