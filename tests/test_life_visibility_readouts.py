"""Explicit ABI4 measurement support; existing tissues are execution fixtures only."""
import copy
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.life import build, probe, readouts, spec
from src.life import handbuilt as hb
from tests.life_helpers import COLUMN3, R3, columns, hexdisk
from tests.test_life_world_catch import TONIC

V4 = spec.V4


def _ledger(captures=3.0, low=2.0):
    led = np.zeros((1, V4.LEDGER_SIZE))
    led[0, V4.L["captures"]] = captures
    led[0, V4.L["low_light_captures"]] = low
    return led


def _tonic():
    quiet = V4.theta()
    program = V4.pack_program(TONIC, alone=quiet, rim=quiet, zygote=quiet)
    return hb.Body("existing tonic execution fixture", program,
                   ((0, 0, 0, R3["zygote"]), (0, 0, 1, R3["contact"])))


@pytest.mark.parametrize("low", [0.0, 1.0, 3.0])
def test_complete_abi4_ledger_requires_explicit_contract_and_validates_subset(low):
    ledger = _ledger(low=low)
    assert readouts.validate_ledger(ledger, abi=V4) == {}
    with pytest.raises(ValueError, match="ABI-3"):
        readouts.validate_ledger(ledger)
    assert readouts.validate_ledger(ledger[:, :57]) == {}


@pytest.mark.parametrize("captures, low", [(3, -1), (3, 4), (-1, 0), (3, np.nan), (3, np.inf)])
def test_abi4_rejects_invalid_low_light_counts(captures, low):
    with pytest.raises(ValueError):
        readouts.validate_ledger(_ledger(captures, low), abi=V4)


def test_trace_readouts_do_not_discard_invalid_appended_column():
    tr = SimpleNamespace(ledger=dict(zip(V4.LEDGER, _ledger(low=4)[0])),
                         meta=dict(seed=11, abi=4), spikes=pd.DataFrame())
    with pytest.raises(ValueError, match="low_light_captures"):
        readouts.relay_chains([tr])


@pytest.mark.parametrize("preset", ["catch_speck_flash5_dim25_l4", "catch_speck_blink20_20_l4"])
def test_explicit_abi4_trace_and_kernel_trace_preserve_complete_ledgers(preset):
    org = _tonic()
    options = dict(T=24, t_open=8, v_t=0, R_min=0, R_max=.5, t_resp=0)
    tr = probe.trace(org, 11, preset, abi=V4, **options)
    assert tr.meta["abi"] == 4 and len(tr.ledger) == 58
    kr = probe.trace_kernel(org, [11], preset, abi=V4, threads=1, raster_cap=64, fate_cap=8, **options)[0]
    assert kr.meta["abi"] == 4 and kr.ledger == tr.ledger
    pd.testing.assert_series_equal(tr.spikes.t, kr.spikes.t)
    signature = readouts.search_signature(tr, silence_window=.5)
    assert signature["low_light_captures"] == tr.ledger["low_light_captures"]
    assert signature["dim_captures"] == signature["low_light_captures"]
    if "flash" in preset:
        assert signature["low_light_captures"] > 0
    later = readouts.search_signature(tr, silence_window=.5, start=20)
    expected = tr.clicks[(tr.clicks.t >= 20) & (tr.clicks.outcome == "capture") & tr.clicks.low_light]
    assert later["low_light_captures"] == len(expected)
    changed = copy.deepcopy(tr)
    changed.ledger["low_light_captures"] = tr.ledger["captures"] + 1
    with pytest.raises(ValueError, match="low_light_captures"):
        readouts.search_signature(changed, silence_window=.5)
    changed = copy.deepcopy(tr)
    changed.clicks["low_light"] = ~changed.clicks.low_light
    with pytest.raises(ValueError, match="accounting-window ledger"):
        readouts.search_signature(changed, silence_window=.5)


def test_observer_signal_attribution_scales_target_without_changing_life():
    org = hb.Body("existing column execution fixture", COLUMN3, tuple(columns(hexdisk(1))))
    options = dict(T=8, visibility_on=2.0, visibility_low=0.0, t_resp=0, lam_bg=4.0)
    tr = probe.trace(org, 11, "catch_speck_flash5_dim25_l4", abi=V4, **options)
    dark = tr.receptors[tr.receptors.t > 2.0 + .5]
    assert len(dark) > 0 and (dark.p_signal == 0.0).all()
    result = build.run(org.world("catch_speck_flash5_dim25_l4", **options), [11], programs=org.program,
                       init=list(org.cells), abi=V4, threads=1)
    assert np.asarray(list(tr.ledger.values()), dtype=np.float64).tobytes() == result.ledger[0].tobytes()


def test_neutral_v4_trace_keeps_abi3_observations_and_default_shape():
    org = _tonic()
    old = probe.trace(org, 11, "catch_speck_l4", T=8)
    new = probe.trace(org, 11, "catch_speck_l4", T=8, abi=V4)
    assert len(old.ledger) == 57 and "low_light" not in old.clicks and "abi" not in old.meta
    assert {k: new.ledger[k] for k in old.ledger} == old.ledger
    assert new.ledger["low_light_captures"] == 0
    for field in ("cells", "spikes", "receptors", "motion"):
        pd.testing.assert_frame_equal(getattr(old, field), getattr(new, field))
    pd.testing.assert_frame_equal(old.clicks, new.clicks.drop(columns="low_light"))
    with pytest.raises(NotImplementedError):
        probe.trace(org, 11, "catch_speck_flash5_dim25_l4", T=8)


def test_reference_lateral_lesion_matches_abi4_kernel_fork():
    org = hb.Body("existing column execution fixture", COLUMN3, tuple(columns(hexdisk(1))))
    pairs = probe.check_lesion_equivalence(org, "catch_speck_flash5_dim25_l4", 4, [11], T=8, abi=V4)
    assert len(pairs) == 1 and pairs[0][0] == pairs[0][1]


def test_paired_helpers_forward_explicit_abi4_without_running_lives(monkeypatch):
    calls = []

    def kernel(org, seeds, preset, **kw):
        calls.append(kw)
        return {k: np.ones(len(seeds)) for k in ("F", "captures", "misses", "n_end", "last_birth")}

    monkeypatch.setattr(probe, "_kernel_run", kernel)
    org = _tonic()
    probe.development_end(org, "catch_speck_flash5_dim25_l4", n_lives=2, threads=1, abi=V4)
    probe.lesion(org, "catch_speck_flash5_dim25_l4", "lateral_off", 4, n_lives=2, threads=1, abi=V4, T=8)
    monkeypatch.setattr(probe, "_ref_job", lambda seed: (1.0, 1.0, 1.0, 0))
    probe.lesion_ref(org, "catch_speck_flash5_dim25_l4", probe.Lesion(4), n_lives=2, threads=1,
                     procs=1, abi=V4, T=8)
    assert len(calls) == 4 and all(c["abi"] is V4 for c in calls)
