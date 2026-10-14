"""Report-only E6 readouts (TASK_VARIATION_PLAN 0.6); nothing here enters selection or a living cell.

Ratios are ratios of paired means, never means of per-life ratios. Their delta-method SE retains the covariance
between numerator and denominator. A nonpositive denominator is undefined; an uncertain positive denominator is
reported with a warning and cannot establish a success criterion.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from src.life import analysis, probe, spec


def _paired_arrays(*values):
    arrays = [np.asarray(v, dtype=np.float64) for v in values]
    if not arrays or any(a.ndim != 1 or not len(a) or not np.isfinite(a).all() for a in arrays):
        raise ValueError("scores must be nonempty finite one-dimensional arrays")
    if any(a.shape != arrays[0].shape for a in arrays):
        raise ValueError("paired lives must have equal lengths")
    return arrays


def ratio_of_means(numerator, denominator) -> dict:
    """Paired ratio and delta-method SE; the denominator must exceed zero and 3 SE to be reliable."""
    a, b = _paired_arrays(numerator, denominator)
    num, den = analysis.summary(a), analysis.summary(b)
    value = float(a.mean() / b.mean()) if den["mean"] > 0 else None
    se = None
    if value is not None and len(a) > 1:
        se = float((a - value * b).std(ddof=1) / (math.sqrt(len(a)) * den["mean"]))
    reliable = bool(len(a) > 1 and den["mean"] > 3 * den["se"])
    reason = None if reliable else "denominator is nonpositive, within 3 SE of zero, or has fewer than two lives"
    return dict(value=value, se=se, numerator=num, denominator=den, reliable=reliable, reason=reason)


def lateral_share(base, lateral_off, reflex=None) -> dict:
    """Lateral loss as shares of base F and, when supplied, of the lead over the best reflex.

All arms must use identical seeds and accounting windows. Negative or >100% results are kept. Run the fork after
development to isolate adult circuitry. The plan's R1 criterion uses share_of_reflex_lead, not share_of_base_F.
"""
    base, off = _paired_arrays(base, lateral_off)
    out = dict(base=analysis.summary(base), lateral_off=analysis.summary(off),
               loss=analysis.paired(base, off), share_of_base_F=ratio_of_means(base - off, base))
    if reflex is not None:
        base, ref = _paired_arrays(base, reflex)
        out["lead_over_reflex"] = analysis.paired(base, ref)
        out["share_of_reflex_lead"] = ratio_of_means(base - off, base - ref)
    return out


def validate_ledger(ledger) -> dict:
    """Reject guards, failed accounting, capacity failures and truncated logs; retain ordinary wall/extinction flags."""
    led = np.atleast_2d(np.asarray(ledger, dtype=float))
    if led.ndim != 2 or led.shape[1] != spec.V3.LEDGER_SIZE or not len(led) or not np.isfinite(led).all():
        raise ValueError("need finite, complete ABI-3 ledger rows")
    statuses = led[:, spec.V3.L["status"]].astype(np.int64)
    names = ("guard_cells", "guard_events", "raster_overflow", "fate_overflow", "ledger_mismatch", "capacity")
    invalid = sum(spec.STATUS[k] for k in names)
    if np.any(statuses & invalid):
        bad = {k: np.flatnonzero(statuses & spec.STATUS[k]).tolist()
               for k in names if np.any(statuses & spec.STATUS[k])}
        raise ValueError(f"invalid or incomplete measurement lives: {bad}")
    return {k: int(np.count_nonzero(statuses & v)) for k, v in spec.STATUS.items() if np.any(statuses & v)}


@dataclass(frozen=True)
class Scores:
    """Scores with enough provenance to reject unpaired or unmatched BH3 comparisons.

``footprints`` contains one identifier per life, identifying the full geometry/protocol including hidden cells,
not merely the number of cells. Dynamic bodies require a genuinely matched development protocol; substituting
their final shape is not an exact match. ``world`` includes duration, accounting window and every override.
"""
    F: list[float]
    seeds: list[int]
    footprints: list[str]
    world: dict
    tuning_seeds: list[int]

    def validate(self):
        _paired_arrays(self.F)
        if len(self.seeds) != len(self.F) or len(self.footprints) != len(self.F):
            raise ValueError("every score needs its life seed and footprint identifier")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("scoring lives must be distinct")
        if set(self.seeds) & set(self.tuning_seeds):
            raise ValueError("tuning and scoring lives must be disjoint")
        if not self.world or any(not fp for fp in self.footprints):
            raise ValueError("world and footprint metadata are required")


def information_share(best: Scores, reflex: Scores, c4: Scores) -> dict:
    """BH3: (F_best - F_reflex)/(F_C4 - F_reflex), on the same footprint and paired fresh lives.

Reflex selection/tuning and C4 tuning happen outside this readout; keep those records with the input scores.
The published hollow3 C4 number is not a valid substitute for C4 on an evolved best's footprint.
"""
    for scores in (best, reflex, c4):
        scores.validate()
        if scores.seeds != best.seeds:
            raise ValueError("BH3 requires identical ordered life seeds")
        if scores.footprints != best.footprints:
            raise ValueError("BH3 requires the same footprint in all three arms")
        if scores.world != best.world:
            raise ValueError("BH3 requires identical world and accounting windows")
    a, b, c = _paired_arrays(best.F, reflex.F, c4.F)
    out = ratio_of_means(a - b, c - b)
    out.update(best=analysis.summary(a), reflex=analysis.summary(b), c4=analysis.summary(c),
               gain=analysis.paired(a, b), information_gap=analysis.paired(c, b),
               above_quarter=bool(out["value"] > 0.25) if out["reliable"] else None,
               seeds=best.seeds, footprints=best.footprints, world=best.world)
    return out


def member_comparisons(best: Scores, reflex: Scores, s5: Scores, lateral_off: Scores | None = None) -> dict:
    """Per-world paired leads over the best reflex and pilot s5; optional R1 share removed by lateral_off.

Call once per family member with that member's complete world metadata. Footprints can differ between tissue
bodies; only BH3 requires geometry matching. All runs here must have the same accounting window.
"""
    for scores in (best, reflex, s5) + (() if lateral_off is None else (lateral_off,)):
        scores.validate()
        if scores.seeds != best.seeds or scores.world != best.world:
            raise ValueError("member comparisons require identical ordered seeds, worlds and accounting windows")
    out = dict(world=best.world, seeds=best.seeds, vs_reflex=analysis.paired(best.F, reflex.F),
               vs_s5=analysis.paired(best.F, s5.F))
    if lateral_off is not None:
        out["lateral"] = lateral_share(best.F, lateral_off.F, reflex.F)
    return out


def relay_chains(traces, *, start: float | None = None, max_depth: int = 12) -> dict:
    """Reuse probe's largest-input chains, retaining per-life counts and latency by hop count.

This follows the largest input at each firing step; it does not prove that input alone caused the spike, and
cannot reconstruct subthreshold integration. Lesions supply the complementary causal evidence.
"""
    if max_depth < 1:
        raise ValueError("max_depth must be positive")
    rows = []
    for tr in traces:
        validate_ledger([tr.ledger[k] for k in spec.V3.LEDGER])
        if not len(tr.spikes):
            rows.append(dict(seed=tr.meta["seed"], groups=[]))
            continue
        probe.relabel(tr)
        ch = probe.chains(tr, max_depth=max_depth)
        if len(ch) and start is not None:
            ch = ch[ch.t >= start]
        groups = [] if not len(ch) else probe.chain_summary(ch).to_dict("records")
        for group in groups:
            subset = ch if group["cls"] == "all" else ch[ch.cls == group["cls"]]
            receptors = subset[subset.origin == "rec"]
            group["relayed_2plus"] = float((receptors.lat_hops >= 2).mean()) if len(receptors) else None
        rows.append(dict(seed=tr.meta["seed"], groups=groups))
    return dict(lives=rows, start=start, max_depth=max_depth,
                method="largest positive input; relayed and relayed_2plus shares are among receptor-origin chains",
                limitation="subthreshold integration is omitted; unknown/deep chains are reported separately")


def silent_intervals(pings, start: float, end: float, window: float, *, life_start: float) -> list[tuple]:
    """Intervals with no delivered ping during the preceding ``window`` units, including initial silence."""
    if not math.isfinite(window) or window <= 0 or end < start or start < life_start:
        raise ValueError("need a positive finite silence window and life_start <= start <= end")
    times = np.unique(np.asarray(pings, dtype=float))
    if not np.isfinite(times).all():
        raise ValueError("ping times must be finite")
    times = times[(times >= life_start) & (times < end)]
    out, last = [], life_start
    for t in list(times) + [end]:
        lo, hi = max(start, last + window), min(end, float(t))
        if hi > lo:
            out.append((lo, hi))
        last = float(t)
    return out


def motion_distance(motion, intervals) -> float:
    """Analytic distance in intervals from observed, unmodified dot integration segments."""
    distance = 0.0
    j = 0
    for row in motion.itertuples(index=False):
        while j < len(intervals) and intervals[j][1] <= row.start:
            j += 1
        k = j
        while k < len(intervals) and intervals[k][0] < row.end:
            lo, hi = max(row.start, intervals[k][0]), min(row.end, intervals[k][1])
            if hi > lo:
                e0 = math.exp(-(lo - row.start) / row.tau)
                distance += row.speed * row.tau * e0 * (-math.expm1(-(hi - lo) / row.tau))
            k += 1
    return distance


def search_signature(tr: probe.Trace, *, silence_window: float, start: float | None = None) -> dict:
    """BH4 on one trace. Capture-zone occupancy uses the ABI's integer-time samples, not exact dwell time.

``silence_window`` is explicit because point pings themselves occupy no duration. It changes only this report.
The observation-only motion log supports exact integration through gaps, even while force direction changes.
"""
    w = tr.meta["world"]
    validate_ledger([tr.ledger[k] for k in spec.V3.LEDGER])
    start = w.t0 + w.t_open if start is None else float(start)
    end = float(tr.ledger["t_end"])
    gaps = silent_intervals(tr.receptors.t, start, end, silence_window, life_start=w.t0)
    if tr.motion is None:
        raise ValueError("this trace lacks analytic motion observations; retrace with the current probe")
    clicks = tr.clicks[(tr.clicks.t >= start) & (tr.clicks.t < end)]
    captures = int((clicks.outcome == "capture").sum())
    # The ABI samples at t0 + 1, t0 + 2, ...; probe.traj also includes an initial placement, which is not a sample.
    samples = tr.traj[(tr.traj.t > w.t0) & (tr.traj.t >= start) & (tr.traj.t < end)]
    inside = (samples.X - samples.tx) ** 2 + (samples.Y - samples.ty) ** 2 <= w.rho_c ** 2
    return dict(seed=tr.meta["seed"], start=start, end=end, silence_window=silence_window,
                silent_time=sum(hi - lo for lo, hi in gaps), silent_distance=motion_distance(tr.motion, gaps),
                total_distance=motion_distance(tr.motion, [(start, end)]), zone_samples=int(inside.sum()),
                samples=len(samples), capture_zone_sample_share=float(inside.mean()) if len(samples) else None,
                clicks=len(clicks), captures=captures, clicks_per_capture=len(clicks) / captures if captures else None,
                flip_recovery=None, dim_captures=None,
                unavailable="ABI 3 has no flip or dim state; flip recovery also needs a registered definition",
                occupancy_method="integer-time left-limit samples; excludes the initial placement")


def json_safe(value):
    """Convert missing measurements to JSON null, including non-finite probe values."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    return None if isinstance(value, float) and not math.isfinite(value) else value
