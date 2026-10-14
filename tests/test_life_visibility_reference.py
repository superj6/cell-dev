"""ABI 4 reference boundaries; execution fixtures test physics, without fitness requirements."""
import math
from dataclasses import replace

import numpy as np
import pytest

from src.life import reference as ref
from src.life import spec

V4 = spec.V4


def _world(mode=1, **overrides):
    params = dict(T=16.0, t_resp=0.0, tau_turn=0.0, visibility_mode=mode,
                  visibility_on=2.0 if mode else 0.0,
                  visibility_off=3.0 if mode == 2 else 0.0,
                  visibility_low=0.25 if mode else 1.0)
    return spec.world("catch_speck_l4", **(params | overrides))


def _life(w, seed=11):
    """Initialize the accountant without running any cell events."""
    w = replace(w, flags=w.flags | V4.flags("program_mode"))
    lat, unit = V4.lattice_tables(w.lattice)
    latd = ref._lattice(lat, unit, V4)
    args = ref._prepare(V4.pack_world(w), latd, None, V4.pack_program(V4.theta()), None, V4)
    wv, gt, program, cells = args
    return ref._Life(wv, latd, gt, program, cells, (seed, 0, 0, 0), 0, 0, True, out_abi=V4)


def _vis(a):
    return [x for x in a.wlog if x[0] == ref.W_VISIBILITY]


def test_flash_initial_state_and_strict_before_boundary():
    a = _life(_world(t0=1024.0)).acct
    assert a.bright and a.visibility_next == 1026.0 and not _vis(a)
    a.world_to(1026.0)
    assert a.bright and not _vis(a)
    a.world_to(math.nextafter(1026.0, math.inf))
    assert not a.bright and a.visibility_next == math.inf
    assert _vis(a) == [(14, ref.bits(1026.0), 0, 0)]
    a.world_to(1100.0)
    assert len(_vis(a)) == 1


@pytest.mark.parametrize("placement_time", [1.0, 2.0, 3.0])
def test_flash_placement_resets_the_deadline_without_an_extra_hash(placement_time):
    a = _life(_world()).acct
    a.world_to(placement_time)
    before = len(_vis(a))
    a.place(0, 1, placement_time)
    assert a.bright and a.visibility_next == placement_time + 2.0
    assert len(_vis(a)) == before
    a.world_to(placement_time + 2.0)
    assert a.bright
    a.world_to(math.nextafter(placement_time + 2.0, math.inf))
    assert not a.bright and len(_vis(a)) == before + 1


@pytest.mark.parametrize("mode", [1, 2])
def test_equal_time_timers_then_turns_then_visibility(monkeypatch, mode):
    a = _life(_world(mode, t_resp=100.0, tau_turn=100.0)).acct
    a.blobs[0].r = a.blobs[0].tau = a.visibility_next = 2.0
    monkeypatch.setattr(spec, "poisson_next", lambda seed, stream, blob, k, t, mean: t + 100.0)
    a.wlog.clear()
    a.world_to(2.0)
    assert not a.wlog
    a.world_to(math.nextafter(2.0, math.inf))
    assert [x[0] for x in a.wlog] == ([12, 13] if mode == 1 else [12, 13, 14])
    assert a.bright is (mode == 1)
    assert a.visibility_next == (4.0 if mode == 1 else 102.0)


def test_renewal_stream_counters_and_schedule_persist_across_placements(monkeypatch):
    original = spec.poisson_next
    calls = []

    def traced(seed, stream, blob, k, t, mean):
        calls.append((seed, stream, blob, k, t, mean))
        return original(seed, stream, blob, k, t, mean)

    monkeypatch.setattr(spec, "poisson_next", traced)
    a = _life(_world(2, t0=1024.0), seed=17).acct
    assert calls == [(17, 26, 0, 0, 1024.0, 2.0)]
    deadline = a.visibility_next
    assert deadline == original(17, 26, 0, 0, 1024.0, 2.0)
    for cause in (1, 2):
        a.place(0, cause, (1024.0 + deadline) / 2)
        assert a.bright and a.visibility_next == deadline and a.visibility_k == 1
    a.world_to(deadline)
    assert a.bright
    a.world_to(math.nextafter(deadline, math.inf))
    assert not a.bright and calls[-1] == (17, 26, 0, 1, deadline, 3.0)
    dark_end = a.visibility_next
    a.place(0, 1, (deadline + dark_end) / 2)
    assert not a.bright and a.visibility_next == dark_end and a.visibility_k == 2
    a.world_to(math.nextafter(dark_end, math.inf))
    assert a.bright and calls[-1] == (17, 26, 0, 2, dark_end, 2.0)
    assert _vis(a) == [(14, ref.bits(deadline), 0, 0), (14, ref.bits(dark_end), 0, 1)]


@pytest.mark.parametrize("mode", [0, 1])
def test_steady_and_flash_use_no_visibility_random_draws(monkeypatch, mode):
    def unexpected(*args):
        raise AssertionError(f"unexpected Poisson draw: {args}")

    monkeypatch.setattr(spec, "poisson_next", unexpected)
    a = _life(_world(mode)).acct
    a.world_to(100.0)
    assert a.visibility_k == 0
    assert len(_vis(a)) == mode


@pytest.mark.parametrize("counted", [False, True])
def test_low_light_capture_uses_preplacement_state_and_accounting_window(counted):
    a = _life(_world()).acct
    a.world_to(3.0)
    a.blobs[0].x = a.blobs[0].y = a.blobs[0].vx = a.blobs[0].vy = 0.0
    a._click(3.0, counted)
    assert a.led[V4.L["captures"]] == int(counted)
    assert a.led[V4.L["low_light_captures"]] == int(counted)
    assert not a.bright and a.defer_place == [(0, 1)]
    a._end_group(3.0)
    assert a.bright and a.visibility_next == 5.0
    assert a.led[V4.L["low_light_captures"]] == int(counted)


@pytest.mark.parametrize("low", [0.0, 0.25, 1.0])
def test_visibility_scales_only_target_rate_and_preserves_bound(monkeypatch, low):
    life = _life(_world(visibility_low=low, lam_bg=0.5, lam_s=2.0))
    a = life.acct
    a.blobs[0].x = a.blobs[0].y = a.blobs[0].vx = a.blobs[0].vy = 0.0
    site = ref._Site(0, 0, 0)
    assert life.lam_max == 2.5
    for bright, rate in ((True, 2.5), (False, 0.5 + low * 2.0)):
        a.bright = bright
        assert 0 <= rate <= life.lam_max
        for threshold in (rate - 1e-12, rate, rate + 1e-12):
            monkeypatch.setattr(spec, "draw", lambda *args, value=threshold / life.lam_max: value)
            a._rcand(1.0, site, 17, 0, False)
            assert a.wlog[-1][4] == int(threshold < rate)


@pytest.mark.parametrize("T, expected_events", [(2.0, 0), (3.0, 1)])
def test_life_end_excludes_exact_visibility_boundary(T, expected_events):
    r = ref.run(_world(T=T), program=V4.pack_program(V4.theta()), seed=11, records=True, abi=V4)
    events = [x for x in r.world if x[0] == 14]
    assert len(events) == expected_events
    assert r.ledger.shape == (58,) and r["low_light_captures"] == 0.0


@pytest.mark.parametrize("abi", [spec.V2, spec.V3])
def test_legacy_projection_keeps_old_ledger_folds_and_logs(abi):
    w = spec.world(T=8.0) if abi.version == 2 else _world(0, T=8.0)
    program = abi.pack_program(abi.theta(b=1.875, tau_m=8.0, t_ref=2.0, kappa=1.0))
    old = ref.run(w, program=program, seed=11, records=True, abi=abi)
    padded = V4.pad_program(program, abi) if abi.version == 2 else program
    new = ref.run(w, program=padded, seed=11, records=True, abi=V4)
    assert old.ledger.tobytes() == new.ledger[:abi.LEDGER_SIZE].tobytes()
    for key in ("raster_t", "raster_uid", "fate_f"):
        assert getattr(old, key).tobytes() == getattr(new, key).tobytes()
    assert old.fate_i.tobytes() == new.fate_i[:, :abi.FATE_I_SIZE].tobytes()
    assert old.records == new.records and old.world == new.world
    h = int(old.hashes[0])
    for x in new.ledger[abi.LEDGER_SIZE:]:
        h = spec.splitmix64(h ^ ref.bits(float(x)))
    assert h == int(new.hashes[0])
    assert np.array_equal(old.hashes[1:], new.hashes[1:abi.HASH_SIZE])
    assert new["low_light_captures"] == 0.0


@pytest.mark.parametrize("abi", [spec.V2, spec.V3])
def test_legacy_callers_reject_enabled_visibility(abi):
    with pytest.raises((NotImplementedError, ValueError)):
        ref.run(_world(), program=abi.pack_program(abi.theta()), abi=abi)


@pytest.mark.parametrize("name", ["catch_speck_flash5_dim25_l4", "catch_speck_blink20_20_l4"])
def test_new_worlds_keep_reference_scheduler_and_relabel_invariance(name):
    w = spec.world(name, T=12.0, t_resp=3.0, tau_turn=3.0)
    program = V4.pack_program(V4.theta(b=0.5, w0=1.0, emit0=1.0, g_r=1.0))
    base = ref.run(w, program=program, seed=11, records=True, abi=V4)
    for other, options in ((w, dict(tie_seed=5, salt=7)),
                           (replace(w, window_h=0.25), dict(order_seed=5))):
        got = ref.run(other, program=program, seed=11, records=True, abi=V4, **options)
        for key in ("ledger", "hashes", "raster_t", "raster_uid", "fate_i", "fate_f"):
            assert getattr(got, key).tobytes() == getattr(base, key).tobytes()
