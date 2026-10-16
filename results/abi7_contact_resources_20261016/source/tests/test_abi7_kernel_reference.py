"""Exactly 22 short ABI7 engineering lives: five C full/fast/window/Python cases plus two observers.

Bodies are execution fixtures, never performance or world-admission controls. Boundary fixtures elsewhere
exercise harvest contention directly, so these cases need not achieve a particular behavior.
"""
from dataclasses import replace

import numpy as np
import pytest

from src.life import build, handbuilt, probe, reference, spec
from tests.life_helpers import mismatch

CASES = (
    ("single", dict(patch_count=1)),
    ("three", dict(patch_count=3)),
    ("four_shifted", dict(patch_count=4, t0=7, t_open=2.25)),
    ("guard", dict(patch_count=3, n_max=3, t_open=1.5)),
    ("extinct", dict(patch_count=3, kill_t=2.25, kill_frac=1)),
)


@pytest.mark.parametrize("name,changes", CASES, ids=[c[0] for c in CASES])
def test_short_patch_lives_preserve_full_reference_fast_and_window_bits(name, changes, monkeypatch):
    v = spec.V7
    options = dict(T=24, patch_refill_fast=2, patch_refill_slow=3, patch_contact_delay=2,
                   flags=v.flags("program_mode"), **changes)
    world = spec.world("catch_contact_resources_l4", **options)
    program = v.pack_program(v.theta(b=.5, w0=1, emit0=1, g_r=1, kappa=1))
    cells = [(0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 0, 1)]
    seed = 11
    kwargs = dict(programs=program, init=cells, threads=1, abi=v, raster_cap=256, fate_cap=32)
    full = build.run(world, [seed], **kwargs)
    py = reference.run(world, program=program, cells=cells, seed=seed,
                       raster_cap=256, fate_cap=32, records=True, abi=v)
    assert mismatch(full, 0, py) == []
    window = build.run(replace(world, window_h=.25), [seed], **kwargs)
    fast = build.run(world, [seed], fast=True, **kwargs)
    for other in (window, fast):
        for field in ("ledger", "raster_t", "raster_uid", "raster_n", "fate_i", "fate_f", "fate_n"):
            assert getattr(full, field).tobytes() == getattr(other, field).tobytes(), field
    assert full.hashes.tobytes() == window.hashes.tobytes()
    assert np.all(fast.hashes == spec.HASH_INIT)
    expected = spec.STATUS["guard_cells"] if name == "guard" else spec.STATUS["extinct"] if name == "extinct" else 0
    assert int(full["status"][0]) == expected
    assert len(full.ledger[0]) == 143
    for slot in range(world.patch_count, 4):
        for stem in ("stock_open", "source", "supply", "spill", "harvest", "empty", "stock_end",
                     "initial_harvest", "refill_harvest"):
            assert full[f"patch_{stem}_{slot}"][0] == 0
    events = py.world
    assert sum(row[0] == reference.W_PATCH_START for row in events) == world.patch_count
    assert sum(row[0] == reference.W_PATCH_END for row in events) == world.patch_count
    assert all(row[0] not in (reference.W_PLACE, reference.W_TURN, reference.W_TASK_PHASE) for row in events)
    if name in ("single", "three"):
        # Keep the actual observing result for full ledger/hash/raster/fate comparison. Reading result()
        # after trace() does not advance or repeat the life; the observer adds exactly one life per case.
        observed = []
        def observing_life(org, seed, w, log, lesion, abi):
            wv, lattice, genome, program, initial = probe._inputs(org, w, abi)
            life = probe._TLife(wv, lattice, genome, program, initial, (int(seed), 0, 0, 0),
                                256, 32, True, out_abi=abi, log=log, lesion=lesion)
            observed.append(life)
            return life

        monkeypatch.setattr(probe, "_life", observing_life)
        org = handbuilt.Body("ABI7 execution fixture", program, tuple((*site, -1) for site in cells))
        trace = probe.trace(org, seed, "catch_contact_resources_l4", abi=v, check=False, **options)
        assert len(observed) == 1
        result = observed[0].result()
        assert mismatch(full, 0, result) == []
        assert result.ledger.tobytes() == py.ledger.tobytes()
        assert result.hashes.tobytes() == py.hashes.tobytes()
        assert result.world == py.world
        assert np.asarray(list(trace.ledger.values())).tobytes() == full.ledger[0].tobytes()
        assert trace.spikes.t.to_numpy().tobytes() == full.spikes(0)[0].tobytes()
        assert trace.placements.empty
        assert set(trace.patch_events.kind) >= {reference.W_PATCH_START, reference.W_PATCH_SOURCE,
                                               reference.W_PATCH_END}
        assert len(trace.patch_events[trace.patch_events.kind == reference.W_PATCH_END]) == world.patch_count
        assert {"patch", "resource_outcome", "stock_before", "stock_after", "origin"} <= set(trace.clicks.columns)
    if name == "guard":
        assert full["t_end"][0] <= world.t_open
        assert np.all(full.ledger[:, 70:] == 0)
    if name == "extinct":
        end = world.t0 + world.T
        assert full["t_end"][0] == end and full["t_ext"][0] < end
        assert any(row[0] == reference.W_PATCH_SOURCE and row[1] > reference.bits(float(full["t_ext"][0]))
                   for row in events)
