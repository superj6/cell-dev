"""The LIFE_FAST kernel build (build.run(..., fast=True)) lives the same lives as the full build: every ledger column,
the raster and the fate log bitwise, for random genomes, hand-built GRN genomes and program bodies, in CATCH and BELL
worlds, with flags and forks. It folds no hashes, so every hash family stays HASH_INIT."""
import numpy as np
import pytest
import torch

from src.genome import LIFE_DIMS_ABI3, LifeLayout
from src.life import analysis, build, spec
from src.life import handbuilt as hb

V3 = spec.V3


def _same(full: build.Lives, fast: build.Lives) -> None:
    assert np.array_equal(full.ledger.view(np.uint64), fast.ledger.view(np.uint64))  # bitwise, NaN-safe
    for name in ("raster_t", "raster_uid", "raster_n", "fate_i", "fate_f", "fate_n"):
        a, b = getattr(full, name), getattr(fast, name)
        assert (a is None) == (b is None), name
        if a is not None:
            assert np.array_equal(a, b), name
    assert (fast.hashes == spec.HASH_INIT).all()


def _both(w, seeds, **kw) -> None:
    kw = dict(kw, threads=2, raster_cap=4000, fate_cap=2000, abi=V3)
    _same(build.run(w, seeds, **kw), build.run(w, seeds, fast=True, **kw))


def _random_genomes(n: int, seed: int) -> np.ndarray:
    g = LifeLayout(LIFE_DIMS_ABI3).random(n, torch.Generator().manual_seed(seed))
    return np.asarray(g, dtype=np.float32).reshape(n, -1)


@pytest.mark.parametrize("preset", ["catch_speck_l4", "catch_v1_l4"])
def test_random_genomes_live_the_same_lives(preset):
    genomes = _random_genomes(24, 7)
    w = spec.world(preset, T=256.0)
    seeds = analysis.fresh_seeds(24, seed0=42_000_000)
    _both([w] * 24, seeds, genomes=V3.pack_genomes(genomes, w.lattice))


def test_hand_built_grn_genomes_and_forks():
    knobs = dict(hb.full_knobs(hb.PROTOTYPE_STARTS["router"], hb.ROUTER_GRID), **hb.ROUTER_FIXED, **{"J.emit0": 1.0})
    seeds = analysis.fresh_seeds(6, seed0=42_100_000)
    for g in (hb.column_genome(), hb.router_genome(knobs, 0.12)):
        table = V3.pack_genomes(np.asarray(g, dtype=np.float32)[None], "hexprism")
        for extra in ({}, {"t_fork": 40.0, "fork_flags": V3.flags("lateral_off")}):
            _both(spec.world("catch_speck", T=160.0, **extra), seeds, genomes=table)


def test_program_bodies():
    seeds = analysis.fresh_seeds(4, seed0=42_200_000)
    for name in ("reflex@hollow3", "router@ring4"):
        org = hb.speck_body(name)
        w = org.world("catch_speck_l4", T=128.0)
        _both(w, seeds, programs=org.program, init=list(org.cells))
