"""Pilot tools for life mode: the random-genome census (scripts/life_census.py), the throughput benchmark
(scripts/life_bench.py), the sweep's lattice and breeding axes, and the seeded control (evolve.seed_genome)."""
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from scripts import life_bench, life_census, life_reference, sweep
from src.common import load_config
from src.evolve import evolve_life, seed_genome, setup
from src.genome import Dims, Layout
from src.life import analysis, spec
from src.life import handbuilt as hb

ROOT = Path(__file__).resolve().parents[1]
SMOKE = str(ROOT / "configs/life_smoke.yaml")


def _cfg(*overrides):
    return load_config(SMOKE, list(overrides))


def test_census_draws_the_founder_batches_and_partitions_the_lives():
    cfg = _cfg("evolve.init_samples=48", "threads=2")
    c = life_census.census(cfg, 96, [64, 128], top=3, top_lives=4, log=lambda *_: None)
    assert set(c["horizons"]) == {"64", "128"} and c["config"]["samples"] == 96
    for h in c["horizons"].values():
        assert h["lives"] == 96 and h["invalid"] == 0
        # every life is exactly one of: lone, a bounded body, a guard trip or an extinct body (p_die starts at 0)
        assert abs(h["lone"] + h["body"] + h["guard"] + h["extinct"] - 1.0) < 1e-12
        assert abs(h["lone_pump"] + h["lone_silent"] - h["lone"]) < 1e-12
        assert abs(sum(h["n_end_bins"].values()) - 1.0) < 1e-12
        assert h["clear_min_F"] >= h["clear_min_F_lone"] and h["best"]["F"] >= h["F_q"][-1]
    assert len(c["top"]["rows"]) == 3 and c["top"]["lives"] == 4 and "clear_short_and_long" in c["paired"]
    assert "lone pumps" in life_census.markdown(c)
    # the census genomes are the run's founder batches: same generator, same batch size
    _, layout, _, _ = setup(cfg)
    gen = torch.Generator().manual_seed(int(cfg.seed))
    first = layout.random(48, gen, float(cfg.genome.init_scale))
    zyg = life_census.zygote_census(layout, first, "hex")
    assert 0 <= zyg["pump_capable"] <= min(zyg["tonic"], zyg["contracting"]) and zyg["dying"] == 0.0


def test_census_horizon_counts_a_synthetic_ledger():
    st = spec.STATUS
    col = {k: np.zeros(4) for k in life_census.COLUMNS}
    col.update(F=np.array([0.03, -0.02, -20.0, 0.01]), income=np.array([1.0, 0.0, 0.0, 5.0]),
               births=np.array([0, 0, 900, 3]), n_end=np.array([1, 1, 1024, 4]), n_peak=np.array([1, 1, 1024, 4]),
               status=np.array([0, 0, st["guard_cells"], 0], dtype=float), arrivals=np.array([0, 0, 9, 7]),
               events=np.array([10, 10, 980, 0]), live_time=np.array([1.0, 1.0, 10.0, 4.0]))
    h = life_census.horizon(col, 0.02)
    assert (h["lone"], h["lone_pump"], h["body"], h["guard"], h["body_messaging"]) == (0.5, 0.25, 0.25, 0.25, 0.25)
    assert h["clear_min_F"] == 0.25 and h["clear_min_F_body"] == 0.0 and h["best"]["index"] == 0
    assert h["best_body"]["index"] == 3 and h["events_share_guard"] == 0.98


def test_bench_reports_generation_and_kernel_times():
    k = life_bench.kernel_bench(SMOKE, 2, 4, [])
    assert k["lives"] == 4 and k["ms_per_life"] > 0 and k["n_end"] >= 1
    b = life_bench.loop_bench(SMOKE, 2, 3, life_bench.POPULATIONS["r25"], ["clones.every=2", "evolve.heldout_every=2"])
    assert b["generations"] == 3 and b["founders_sampled"] == 0 and b["t_gen_plain"] > 0
    assert len(b["body_mean"]) == 3 and b["genomes"] == 16


def test_sweep_axes_follow_the_life_config():
    sq = load_config(str(ROOT / "configs/life_ctl_square8.yaml"))
    asex = load_config(str(ROOT / "configs/life_ctl_asex.yaml"))
    assert sweep.axes(None, None, sq, "life") == (["square8"], ["sex"])
    assert sweep.axes(None, None, asex, "life") == (["hex"], ["asex"])
    assert sweep.axes("hex,square8", "sex", sq, "life") == (["hex", "square8"], ["sex"])
    legacy = load_config(str(ROOT / "configs/local_smoke.yaml"))
    assert sweep.axes(None, None, legacy, "trials") == (["hex"], ["sex"])


def test_seeded_run_descends_from_the_r25_genome(tmp_path):
    cfg = _cfg("evolve.seed_genome=r25_v1", "evolve.generations=2", "clones.every=0")
    r = evolve_life(cfg, log=lambda row: None, out=tmp_path)
    head = json.loads((tmp_path / "lineage.jsonl").read_text().splitlines()[0])
    assert head["seeded"] == "r25_v1" and head["sampled"] == 0 and head["ids"] == [0]
    assert r["evals"] == 2 * (4 + 12) and set(r["breeds"].tolist()) == {0}
    assert all(k in row for row in r["curves"] for k in ("t_gen", "t_eval", "pop_guard", "pop_lone", "pop_body"))
    _, layout, _, _ = setup(cfg)
    g = seed_genome(cfg, layout)
    assert torch.equal(g[0], torch.from_numpy(hb.r25_genome()))
    timer = seed_genome(_cfg("evolve.seed_genome=r25_v1_timer", "evolve.seed_timer=1.5"), layout)
    assert torch.equal(timer[0], torch.from_numpy(hb.r25_genome(timer=1.5)))
    default = seed_genome(_cfg("evolve.seed_genome=r25_v1_timer"), layout)  # life.yaml: the screened best weight
    assert torch.equal(default[0], torch.from_numpy(hb.r25_genome(timer=1.125)))
    sq = seed_genome(_cfg("evolve.seed_genome=r25_v1", "lattice.kind=square8"), layout)
    assert torch.equal(sq[0], torch.from_numpy(hb.r25_genome(D=8)))
    layout.save(g[0], tmp_path / "g.json")
    assert torch.equal(seed_genome(_cfg(f"evolve.seed_genome={tmp_path / 'g.json'}"), layout), g)
    legacy = Layout(Dims())
    legacy.save(legacy.random(1, torch.Generator().manual_seed(0))[0], tmp_path / "legacy.json")
    with pytest.raises(ValueError):
        seed_genome(_cfg(f"evolve.seed_genome={tmp_path / 'legacy.json'}"), layout)


def _fates(cells):
    """A fate log of initial births at the given sites (uid, a, b)."""
    fi = np.array([[spec.FATE_KINDS["birth"], u, 0, a, b, 0] for u, a, b in cells], dtype=np.int64)
    return fi, np.zeros((len(cells), spec.FATE_F_SIZE))


def test_phase_order_reads_synchrony_from_the_raster():
    fi, ff = _fates([(1, 0, 0), (3, 1, 0), (5, 5, 5)])  # cells 1 and 3 are hex contacts, 5 is far away
    beat = np.arange(0.0, 100.0, 6.5)
    t = np.concatenate([beat, beat + 0.1, beat + 3.25])  # 1 and 3 together, 5 in anti-phase
    u = np.concatenate([np.full(len(beat), 1), np.full(len(beat), 3), np.full(len(beat), 5)]).astype(np.uint64)
    o = np.argsort(t, kind="stable")
    st = analysis.phase_order(t[o], u[o], fi, ff, "hex", 0.0, 100.0)
    assert abs(st["period"] - 6.5) < 1e-9 and st["cells"] == 3
    assert st["local"] > 0.99 and abs(st["R"] - abs(2 * np.exp(0.2j * np.pi / 6.5) - 1) / 3) < 0.05
    quiet = analysis.phase_order(t[:0], u[:0], fi, ff, "hex", 0.0, 100.0)
    assert np.isnan(quiet["R"]) and quiet["cells"] == 3
    assert analysis.is_trap(5e-3, 0.9) and not analysis.is_trap(5e-3, 0.5) and not analysis.is_trap(0.03, 0.95)


def test_bootstrap_ci_is_reproducible_and_brackets_the_mean():
    x = np.random.default_rng(1).normal(0.3, 0.1, 64)
    lo, hi = analysis.bootstrap_ci(x)
    assert lo < x.mean() < hi and (lo, hi) == analysis.bootstrap_ci(x)
    assert all(np.isnan(v) for v in analysis.bootstrap_ci([1.0]))


def test_reference_screens_the_timer_and_measures_the_pick_on_fresh_lives():
    r = life_reference.reference(threads=2, screen_lives=2, lives=2, timers=(1.0, 1.5))
    assert set(r["screen"]) == {"1.0", "1.5"} and r["best_timer"] in (1.0, 1.5)
    up = r["fresh"]["uncapped"]
    assert up["guard"] == 1.0 and up["mean"] < -10  # R25-v1 has no stop rule: it grows into the N_max guard
    assert r["fresh"][f"timer {r['best_timer']:g}"]["guard"] == 0.0
