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


def validate_ledger(ledger, *, abi=spec.V3) -> dict:
    """Check complete caller-ledger rows; ABI 4 is explicit and low-light captures must be a subset of captures.

Reject guards, failed accounting, capacity failures and truncated logs; retain ordinary wall/extinction flags.
"""
    if not isinstance(abi, spec.Abi) or abi.version not in (3, 4, 5, 6, 7):
        raise ValueError("ledger readouts require spec.V3, spec.V4, spec.V5 spec.V6 or spec.V7")
    led = np.atleast_2d(np.asarray(ledger, dtype=float))
    if led.ndim != 2 or led.shape[1] != abi.LEDGER_SIZE or not len(led) or not np.isfinite(led).all():
        raise ValueError(f"need finite, complete ABI-{abi.version} ledger rows")
    if abi.version >= 4:
        low, captures = led[:, abi.L["low_light_captures"]], led[:, abi.L["captures"]]
        if np.any(low < 0) or np.any(low > captures):
            raise ValueError("low_light_captures must lie between zero and captures")
    if abi.version >= 5:
        for label in ("narrow", "broad"):
            names = ("choice_opportunities", "choice_carry_in", "correct_choices", "wrong_choices",
                     "choice_timeouts", "unfinished_choices")
            columns = [led[:, abi.L[f"{name}_{label}"]] for name in names]
            if any(np.any(c < 0) or np.any(c != np.floor(c)) for c in columns):
                raise ValueError("delayed-match counts must be nonnegative integers")
            opened, carried, correct, wrong, timeout, unfinished = columns
            if not np.array_equal(opened + carried, correct + wrong + timeout + unfinished):
                raise ValueError("delayed-match opportunities do not reconcile")
    if abi.version >= 6:
        patch = led[:, [abi.L[name] for name in spec.PATCH_LEDGER]]
        if np.any(patch < 0) or np.any(patch != np.floor(patch)):
            raise ValueError("resource-patch counts must be nonnegative integers")
        for i in range(spec.PATCH_SLOTS):
            def at(metric, slot=i):
                return led[:, abi.L[f"patch_{metric}_{slot}"]]
            if not np.array_equal(at("source"), at("supply") + at("spill")):
                raise ValueError("resource-patch sources do not reconcile")
            if not np.array_equal(at("stock_open") + at("supply"), at("harvest") + at("stock_end")):
                raise ValueError("resource-patch stocks do not reconcile")
            if not np.array_equal(at("harvest"), at("initial_harvest") + at("refill_harvest")):
                raise ValueError("resource-patch harvest origins do not reconcile")
            if np.any(at("initial_harvest") > at("stock_open")):
                raise ValueError("initial resource harvest exceeds the stock present at window opening")
    if abi.version >= 7:
        contact = led[:, [abi.L[name] for name in spec.CONTACT_LEDGER]]
        if np.any(contact < 0) or np.any(contact != np.floor(contact)):
            raise ValueError("contact-resource counts must be nonnegative integers")
        for i in range(spec.PATCH_SLOTS):
            def cc(metric, slot=i):
                return led[:, abi.L[f"patch_contact_{metric}_{slot}"]]

            def pp(metric, slot=i):
                return led[:, abi.L[f"patch_{metric}_{slot}"]]

            if (not np.array_equal(cc("pending_open") + cc("starts"), cc("maturities") + cc("pending_end"))
                    or not np.array_equal(cc("maturities"), cc("supply") + cc("spill"))
                    or not np.array_equal(cc("stock_open") + cc("supply"), cc("harvest") + cc("stock_end"))):
                raise ValueError("contact-resource accounting does not reconcile")
            if (np.any(cc("pending_open") > 1) or np.any(cc("pending_end") > 1)
                    or any(np.any(cc(a) > pp(b)) for a, b in (
                        ("starts", "empty"), ("maturities", "source"), ("supply", "supply"), ("spill", "spill"),
                        ("harvest", "refill_harvest"), ("stock_open", "stock_open"), ("stock_end", "stock_end")))):
                raise ValueError("contact-resource subset or pending bound failed")
    statuses = led[:, abi.L["status"]].astype(np.int64)
    names = ("guard_cells", "guard_events", "raster_overflow", "fate_overflow", "ledger_mismatch", "capacity")
    invalid = sum(spec.STATUS[k] for k in names)
    if np.any(statuses & invalid):
        bad = {k: np.flatnonzero(statuses & spec.STATUS[k]).tolist()
               for k in names if np.any(statuses & spec.STATUS[k])}
        raise ValueError(f"invalid or incomplete measurement lives: {bad}")
    return {k: int(np.count_nonzero(statuses & v)) for k, v in spec.STATUS.items() if np.any(statuses & v)}


def _validate_trace_ledger(tr):
    version = tr.meta.get("abi", 3)
    if version not in (3, 4, 5, 6, 7):
        raise ValueError("trace metadata must name ABI 3, 4, 5, 6 or 7")
    abi = {3: spec.V3, 4: spec.V4, 5: spec.V5, 6: spec.V6, 7: spec.V7}[version]
    validate_ledger([tr.ledger[k] for k in abi.LEDGER], abi=abi)
    return abi


def matching_summary(ledger, *, abi=spec.V5) -> dict:
    """Class-conditioned choices, retaining abstentions and unfinished opportunities in denominators.

Totals aggregate complete lives before division. Physical slot hits and positive fitness alone do not establish
matching. Use this only for delayed-match worlds; a neutral V5 world has no opportunities and undefined ratios.
"""
    if abi.version not in (5, 6, 7):
        raise ValueError("delayed matching requires ABI 5 or later")
    statuses = validate_ledger(ledger, abi=abi)
    led = np.atleast_2d(np.asarray(ledger, dtype=float))
    classes = {}
    for label in ("narrow", "broad"):
        counts = {name: int(led[:, abi.L[f"{name}_{label}"]].sum()) for name in
                  ("choice_opportunities", "choice_carry_in", "correct_choices", "wrong_choices",
                   "choice_timeouts", "unfinished_choices")}
        opportunities = counts["choice_opportunities"] + counts["choice_carry_in"]
        correct, wrong = counts["correct_choices"], counts["wrong_choices"]
        completed = correct + wrong
        classes[label] = dict(counts, total_opportunities=opportunities,
                              narrow_choice=correct if label == "narrow" else wrong,
                              broad_choice=correct if label == "broad" else wrong,
                              no_completed_choice=counts["choice_timeouts"] + counts["unfinished_choices"],
                              correct_per_opportunity=correct / opportunities if opportunities else None,
                              choice_coverage=completed / opportunities if opportunities else None,
                              accuracy_among_choices=correct / completed if completed else None)
    return dict(lives=len(led), classes=classes, status_counts=statuses,
                interpretation="Report both sample classes and coverage; positive reward is not evidence of matching.")


def resource_summary(ledger, world: spec.World, *, abi=spec.V6) -> dict:
    """Conserved resources and click outcomes, without inferring a strategy from aggregate counts."""
    if abi.version not in (6, 7) or not world.patch_count:
        raise ValueError("resource_summary requires an enabled ABI-6 or later patch world")
    abi.validate_world(world)
    statuses = validate_ledger(ledger, abi=abi)
    led = np.atleast_2d(np.asarray(ledger, dtype=float))
    metrics = (*spec.PATCH_METRICS, "initial_harvest", "refill_harvest")
    per_patch, totals = [], dict.fromkeys(metrics, 0)
    harvested = np.zeros(len(led))
    empty = np.zeros(len(led))
    for i in range(spec.PATCH_SLOTS):
        columns = {name: led[:, abi.L[f"patch_{name}_{i}"]] for name in metrics}
        if i >= world.patch_count and any(np.any(x) for x in columns.values()):
            raise ValueError("inactive resource slots must remain zero")
        if any(np.any(columns[name] > world.patch_capacity) for name in ("stock_open", "stock_end")):
            raise ValueError("resource stock exceeds capacity")
        counts = {name: int(value.sum()) for name, value in columns.items()}
        if i < world.patch_count:
            per_patch.append(dict(slot=i, **counts))
        for name, value in counts.items():
            totals[name] += value
        harvested += columns["harvest"]
        empty += columns["empty"]
    contact_totals = None
    if abi.version >= 7:
        contact_totals = dict.fromkeys(spec.CONTACT_METRICS, 0)
        for i in range(spec.PATCH_SLOTS):
            cc = {name: led[:, abi.L[f"patch_contact_{name}_{i}"]] for name in spec.CONTACT_METRICS}
            if (i >= world.patch_count or not world.patch_contact_delay) and any(np.any(x) for x in cc.values()):
                raise ValueError("disabled contact-resource slots must remain zero")
            if i < world.patch_count:
                per_patch[i]["contact"] = {name: int(value.sum()) for name, value in cc.items()}
            for name, value in cc.items():
                contact_totals[name] += int(value.sum())
    geometric = led[:, abi.L["patch_geometric_misses"]]
    if (not np.array_equal(harvested, led[:, abi.L["captures"]]) or
            not np.array_equal(empty + geometric, led[:, abi.L["misses"]]) or
            not np.array_equal(harvested + empty + geometric, led[:, abi.L["clicks"]])):
        raise ValueError("resource click outcomes do not reconcile with the native ledger")
    absent = ("b2_clicks", "respawns", "low_light_captures", *spec.TASK_LEDGER)
    if any(np.any(led[:, abi.L[name]]) for name in absent):
        raise ValueError("resource worlds cannot record legacy target or matching outcomes")
    offered = totals["stock_open"] + totals["source"]
    return dict(lives=len(led), patches=per_patch, totals=totals,
                **({"contact_totals": contact_totals,
                    "passive_harvest_per_life": (totals["refill_harvest"] - contact_totals["harvest"]) / len(led),
                    "contact_harvest_per_life": contact_totals["harvest"] / len(led)}
                   if contact_totals is not None else {}),
                geometric_misses=int(geometric.sum()), status_counts=statuses,
                harvest_per_life=totals["harvest"] / len(led),
                initial_harvest_per_life=totals["initial_harvest"] / len(led),
                refill_harvest_per_life=totals["refill_harvest"] / len(led),
                offered_utilization=totals["harvest"] / offered if offered else None,
                spill_share=totals["spill"] / totals["source"] if totals["source"] else None,
                interpretation="Food provenance and conservation; these totals do not establish switching or memory.")


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
        _validate_trace_ledger(tr)
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
    if w.task_mode or w.patch_count:
        raise ValueError("single-target search signature requires an ordinary CATCH world")
    abi = _validate_trace_ledger(tr)
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
    out = dict(seed=tr.meta["seed"], start=start, end=end, silence_window=silence_window,
                silent_time=sum(hi - lo for lo, hi in gaps), silent_distance=motion_distance(tr.motion, gaps),
                total_distance=motion_distance(tr.motion, [(start, end)]), zone_samples=int(inside.sum()),
                samples=len(samples), capture_zone_sample_share=float(inside.mean()) if len(samples) else None,
                clicks=len(clicks), captures=captures, clicks_per_capture=len(clicks) / captures if captures else None,
                flip_recovery=None, dim_captures=None,
                unavailable="ABI 3 has no flip or dim state; flip recovery also needs a registered definition",
                occupancy_method="integer-time left-limit samples; excludes the initial placement")
    if abi.version >= 4:
        if "low_light" not in tr.clicks or not tr.clicks.low_light.isin([True, False]).all():
            raise ValueError("ABI-4 search readouts need pre-replacement low_light observations on every click")
        counted = tr.clicks[(tr.clicks.t >= w.t0 + w.t_open) & (tr.clicks.t < end)]
        counted_low = int(((counted.outcome == "capture") & counted.low_light.astype(bool)).sum())
        if counted_low != tr.ledger["low_light_captures"]:
            raise ValueError("observed low-light captures disagree with the accounting-window ledger")
        low = int(((clicks.outcome == "capture") & clicks.low_light.astype(bool)).sum())
        out.update(dim_captures=low, low_light_captures=low,
                   low_light_capture_share=low / captures if captures else None,
                   unavailable="flip recovery is unmeasured and needs a registered definition",
                   low_light_method="pre-replacement visibility at each capture within the requested window")
    return out


def json_safe(value):
    """Convert missing measurements to JSON null, including non-finite probe values."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    return None if isinstance(value, float) and not math.isfinite(value) else value
