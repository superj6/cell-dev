"""The approved ABI 4 visibility contract, legacy layouts and explicit evaluator opt-in."""
from dataclasses import replace

import numpy as np
import pytest

from src.common import load_config
from src.genome import LIFE_DIMS_ABI3, LifeLayout
from src.life import spec
from src.life.evaluate import LifeEvaluator

V4 = spec.V4


def test_abi4_only_appends_world_and_ledger_fields():
    assert spec.CURRENT is spec.V2
    assert (spec.V2.WORLD_SIZE, spec.V3.WORLD_SIZE, V4.WORLD_SIZE) == (41, 66, 70)
    assert (spec.V2.LEDGER_SIZE, spec.V3.LEDGER_SIZE, V4.LEDGER_SIZE) == (35, 57, 58)
    assert V4.WORLD_KEYS[:66] == spec.V3.WORLD_KEYS
    assert V4.LEDGER[:57] == spec.V3.LEDGER
    assert V4.L['low_light_captures'] == 57
    assert V4.GENOME_FIELDS == spec.V3.GENOME_FIELDS
    assert V4.INPUTS == spec.V3.INPUTS and V4.KNOBS == spec.V3.KNOBS and V4.FLAGS == spec.V3.FLAGS
    assert V4.STREAMS == dict(spec.V3.STREAMS, visibility=26)
    assert np.array_equal(V4.pack_world(spec.world('catch_speck_l4'))[-4:], [0, 0, 0, 1])


@pytest.mark.parametrize('name, tail', [
    ('catch_speck_flash5_dim25_l4', [1, 5, 0, .25]),
    ('catch_speck_blink20_20_l4', [2, 20, 20, 0]),
])
def test_visibility_presets_and_legacy_rejection(name, tail):
    world = spec.world(name)
    assert np.array_equal(V4.pack_world(world)[-4:], tail)
    assert np.array_equal(V4.pack_world(world)[:66], spec.V3.pack_world(spec.world('catch_speck_l4')))
    for older in (spec.V2, spec.V3):
        with pytest.raises(NotImplementedError):
            older.pack_world(world)


@pytest.mark.parametrize('overrides', [
    dict(visibility_mode=-1), dict(visibility_mode=3), dict(visibility_mode=.5),
    dict(visibility_mode=1, visibility_on=0), dict(visibility_mode=1, visibility_on=2**-11),
    dict(visibility_mode=1, visibility_on=2**31), dict(visibility_mode=1, visibility_on=5, visibility_off=1),
    dict(visibility_mode=2, visibility_on=20, visibility_off=0),
    dict(visibility_mode=2, visibility_on=20, visibility_off=2**31),
    dict(visibility_mode=1, visibility_on=5, visibility_low=-.1),
    dict(visibility_mode=1, visibility_on=5, visibility_low=1.1),
    dict(visibility_low=.5), dict(visibility_on=1), dict(visibility_off=1),
    dict(visibility_mode=1, visibility_on=5, b2_amp=1),
    dict(visibility_mode=1, visibility_on=5, world_kind=0),
    dict(visibility_low=float('nan')), dict(visibility_on=float('inf')),
])
def test_invalid_visibility_worlds_are_rejected(overrides):
    with pytest.raises(ValueError):
        V4.pack_world(spec.world('catch_speck_l4', **overrides))


@pytest.mark.parametrize('low', [0., 1.])
@pytest.mark.parametrize('duration', [spec.STEP_MIN, spec.TIME_MAX])
def test_visibility_boundaries_pack(low, duration):
    world = spec.world('catch_speck_l4', visibility_mode=2, visibility_on=duration,
                       visibility_off=duration, visibility_low=low)
    assert V4.pack_world(world).shape == (70,)
    assert V4.pack_world(replace(world, visibility_mode=1, visibility_off=0)).shape == (70,)


def test_evaluator_requires_explicit_abi4_opt_in():
    cfg = load_config('configs/life_speck.yaml')
    cfg.life.world = 'catch_speck_flash5_dim25_l4'
    layout = LifeLayout(LIFE_DIMS_ABI3)
    with pytest.raises(NotImplementedError):
        LifeEvaluator(cfg, layout)
    cfg.life.abi = 4
    evaluator = LifeEvaluator(cfg, layout)
    assert evaluator.abi is V4 and evaluator.world().visibility_mode == 1
    cfg.life.abi = 2
    with pytest.raises(ValueError, match='genome layout'):
        LifeEvaluator(cfg, layout)
