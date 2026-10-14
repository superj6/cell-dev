"""Measurement contracts: paired ratios, matching footprints and observation-only search traces."""
import copy
import math
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.life import probe, readouts, spec


def test_relay_two_plus_uses_in_plane_hops_and_only_receptor_origins(monkeypatch):
    rows = []
    for cls, origin, lat_hops in (("M", "rec", 0), ("M", "rec", 1), ("M", "rec", 2),
                                  ("M", "tonic", 2), ("K", "tonic", 0)):
        rows.append(dict(cls=cls, origin=origin, lat_hops=lat_hops, origin_dist=lat_hops,
                         hops=lat_hops + 2, latency=1.0, p_signal=0.5, via_own_sense=False, path="synthetic"))
    chains = pd.DataFrame(rows)
    tr = SimpleNamespace(ledger={k: 0.0 for k in spec.V3.LEDGER}, spikes=pd.DataFrame([{}]), meta=dict(seed=46_000_012))
    monkeypatch.setattr(probe, "relabel", lambda trace: trace)
    monkeypatch.setattr(probe, "chains", lambda trace, max_depth: chains)
    groups = {g["cls"]: g for g in readouts.relay_chains([tr])["lives"][0]["groups"]}
    assert groups["M"]["relayed"] == pytest.approx(2 / 3)
    assert groups["M"]["relayed_2plus"] == pytest.approx(1 / 3)
    assert groups["all"]["relayed_2plus"] == pytest.approx(1 / 3)
    assert groups["K"]["relayed_2plus"] is None


def scores(F, **changes):
    data = dict(F=F, seeds=[46_000_000, 46_000_001], footprints=["full-cell-geometry"] * 2,
                world=dict(preset="catch_speck_l4", T=128, t_open=0), tuning_seeds=[46_010_000])
    data.update(changes)
    return readouts.Scores(**data)


def test_paired_ratio_keeps_covariance_and_never_clips():
    ratio = readouts.ratio_of_means([2, 4, 6], [1, 2, 3])
    assert ratio["value"] == 2 and ratio["se"] == 0
    assert readouts.ratio_of_means([-1, -1], [2, 2])["value"] == -0.5
    assert readouts.ratio_of_means([2, 4], [-1, -1])["value"] is None
    assert not readouts.ratio_of_means([1], [1])["reliable"]
    assert not readouts.ratio_of_means([1, 1], [-100, 101])["reliable"]
    with pytest.raises(ValueError):
        readouts.ratio_of_means([1, 2], [1])


def test_lateral_loss_and_bh3_use_paired_means():
    lat = readouts.lateral_share([4, 8], [2, 4], [3, 6])
    assert lat["loss"]["mean"] == 3 and lat["share_of_base_F"]["value"] == 0.5
    assert lat["share_of_reflex_lead"]["value"] == 2 and lat["share_of_reflex_lead"]["se"] == 0
    bh3 = readouts.information_share(scores([2, 4]), scores([1, 3]), scores([5, 7]))
    assert bh3["value"] == 0.25 and bh3["se"] == 0
    assert bh3["above_quarter"] is False


@pytest.mark.parametrize("change", [dict(seeds=[46_000_001, 46_000_000]), dict(footprints=["different"] * 2),
                                  dict(world=dict(T=1536)), dict(tuning_seeds=[46_000_001])])
def test_bh3_rejects_unmatched_or_reused_lives(change):
    with pytest.raises(ValueError):
        readouts.information_share(scores([2, 4]), scores([1, 3]), scores([5, 7], **change))


def test_member_comparisons_pair_both_baselines_and_keep_different_tissue_footprints():
    row = readouts.member_comparisons(scores([4, 8]), scores([3, 6], footprints=["reflex"] * 2),
                                     scores([2, 2]), scores([2, 4]))
    assert row["vs_reflex"]["mean"] == 1.5 and row["vs_s5"]["mean"] == 4
    assert row["lateral"]["share_of_reflex_lead"]["value"] == 2
    with pytest.raises(ValueError):
        readouts.member_comparisons(scores([4, 8]), scores([3, 6]), scores([2, 2], world=dict(T=10)))


def test_ledger_validation_rejects_guards_failures_and_missing_logs():
    ledger = np.zeros((1, spec.V3.LEDGER_SIZE))
    for flag in ("guard_cells", "guard_events", "raster_overflow", "fate_overflow", "ledger_mismatch", "capacity"):
        ledger[0, spec.V3.L["status"]] = spec.STATUS[flag]
        with pytest.raises(ValueError, match=flag):
            readouts.validate_ledger(ledger)
    ledger[0, spec.V3.L["status"]] = spec.STATUS["wall"] | spec.STATUS["extinct"]
    assert readouts.validate_ledger(ledger) == dict(extinct=1, wall=1)
    ledger[0, spec.V3.L["F"]] = np.nan
    with pytest.raises(ValueError):
        readouts.validate_ledger(ledger)


def test_silence_includes_initial_gap_and_pings_before_accounting_window():
    assert readouts.silent_intervals([2, 7], 0, 10, 1, life_start=0) == [(1, 2), (3, 7), (8, 10)]
    assert readouts.silent_intervals([2, 7], 2.5, 10, 1, life_start=0) == [(3, 7), (8, 10)]
    assert readouts.silent_intervals([], 0, 10, 1, life_start=0) == [(1, 10)]


def test_motion_integrates_piecewise_drag_without_chord_approximation():
    motion = pd.DataFrame([(0, 2, 3, 1), (2, 4, 5, 1)], columns=["start", "end", "speed", "tau"])
    expected = 3 * (math.exp(-1) - math.exp(-2)) + 5 * (1 - math.exp(-1))
    assert readouts.motion_distance(motion, [(1, 3)]) == pytest.approx(expected)


def test_search_trace_matches_kernel_accounting_and_preserves_life():
    org, preset = probe.hand("reflex@hollow3")
    tr = probe.trace(org, 46_000_010, preset, T=32, t_open=8)
    result = readouts.search_signature(tr, silence_window=0.5)
    assert tr.meta["kernel_F"] == tr.F
    kernel = org.run([46_000_010], preset=preset, T=32, t_open=8)
    assert np.array_equal(list(tr.ledger.values()), kernel.ledger[0])
    assert result["samples"] == tr.ledger["samples"]
    assert result["zone_samples"] == tr.ledger["zone_samples"]
    assert result["clicks"] == tr.ledger["clicks"]
    assert result["captures"] == tr.ledger["captures"]
    total = readouts.motion_distance(tr.motion, [(0, tr.ledger["t_end"])])
    assert total == pytest.approx(tr.ledger["path"], abs=1e-12)
    assert 0 <= result["silent_distance"] <= result["total_distance"]
    assert result["flip_recovery"] is None and result["dim_captures"] is None
    blank = copy.copy(tr)
    blank.motion = None
    with pytest.raises(ValueError):
        readouts.search_signature(blank, silence_window=0.5)


def test_no_spikes_or_captures_stays_explicitly_missing():
    org, preset = probe.hand("reflex@hollow3")
    tr = probe.trace(org, 46_000_011, preset, T=8, lam_s=0, lam_bg=0)
    result = readouts.search_signature(tr, silence_window=0.5)
    assert result["clicks_per_capture"] is None
    assert readouts.relay_chains([tr])["lives"][0]["groups"] == []
    assert readouts.json_safe(dict(missing=np.float64("nan"))) == dict(missing=None)
    tr.ledger["status"] = spec.STATUS["guard_cells"]
    with pytest.raises(ValueError, match="guard_cells"):
        readouts.relay_chains([tr])
