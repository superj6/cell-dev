"""Labelled training tasks and explicit fixed panels; one tiny native batch, no search."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from src.common import load_config
from src.evolve import recheck_draw
from src.genome import LIFE_DIMS_ABI3, LifeLayout
from src.life import build, spec
from src.life.evaluate import LifeDraw, LifeEvaluator, life_seed, task_objectives

LAYOUT = LifeLayout(LIFE_DIMS_ABI3)
TASKS = [dict(name="dim", world="catch_speck_flash5_dim25_l4", weight=2,
              overrides=dict(visibility_low=.375)),
         dict(name="dark", world="catch_speck_flash5_dim25_l4", overrides=dict(visibility_low=0.0))]


def config(tasks=TASKS, **changes):
    cfg = load_config("configs/life_speck.yaml", ["threads=1", "life.abi=4", "life.T=8", "life.T_choices=null",
        "life.lives=6", "life.founder_lives=3", "life.founder_T=8", "evolve.recheck_lives=3", "evolve.batch=16"])
    if tasks is not None:
        cfg.life.training_tasks = tasks
    for key, value in changes.items():
        cfg.life[key] = value
    return cfg


def test_weighted_cycle_preserves_fractional_overrides_and_recheck_order():
    ev = LifeEvaluator(config(), LAYOUT)
    assert ev.training_task_names == ("dim", "dark")
    draw = ev.draw("gen", 4)
    assert draw.tasks == ("dim", "dim", "dark") * 2
    assert [w.visibility_low for w in draw.worlds] == [.375, .375, 0] * 2
    assert draw.seeds == tuple(life_seed(ev.seed, "gen", 4, i) for i in range(6))
    extra = recheck_draw(ev, 4, 6, 3)
    assert extra.tasks == ("dim", "dim", "dark")
    assert extra.seeds == tuple(life_seed(ev.seed, "gen", 4, i) for i in range(6, 9))
    assert not set(draw.seeds) & set(extra.seeds)
    assert ev.draw("founders", 0, lives=3).tasks == ev.task_pattern
    for purpose in ("valid", "heldout", "final", "clones", "sizecurve"):
        assert ev.draw(purpose, 0, lives=1).tasks == ()


def test_legacy_draw_seed_world_bytes_and_overrides_unchanged():
    ev = LifeEvaluator(config(None), LAYOUT)
    draw = ev.draw("gen", 4)
    expected = LifeDraw(tuple(life_seed(ev.seed, "gen", 4, i) for i in range(6)), (ev.world(),) * 6)
    assert draw == expected and draw.tasks == ()
    assert ev.abi.pack_world(draw.worlds).tobytes() == ev.abi.pack_world(expected.worlds).tobytes()
    labelled = LifeEvaluator(config(), LAYOUT)
    for purpose in ("gen", "heldout"):
        overrides = [{"rho_c": .75}, {"rho_c": 1.25}]
        assert labelled.draw(purpose, 4, lives=2, overrides=overrides) == ev.draw(
            purpose, 4, lives=2, overrides=overrides)


def test_panel_is_explicit_equal_task_major_and_separate_from_training_envelope():
    cfg = config()
    cfg.envelope.enabled = True
    cfg.life.T_choices = [4, 8, 12]
    ev = LifeEvaluator(cfg, LAYOUT)
    panel = ev.draw_tasks("panel", 7, TASKS, 2, T=10)
    assert panel.tasks == ("dim", "dim", "dark", "dark")
    assert [w.T for w in panel.worlds] == [10] * 4
    assert panel.seeds == tuple(life_seed(ev.seed, "panel", 7, i) for i in range(4))
    assert [w.delay_sd for w in panel.worlds] == [ev.world().delay_sd] * 4
    assert not set(panel.seeds) & set(ev.draw_tasks("confirm", 7, TASKS, 2).seeds)
    assert not set(panel.seeds) & set(ev.draw("gen", 7).seeds)
    cfg.envelope.enabled = False
    assert panel == LifeEvaluator(cfg, LAYOUT).draw_tasks("panel", 7, TASKS, 2, T=10)


def test_every_genome_gets_the_same_world_seed_and_task_order(monkeypatch):
    ev = LifeEvaluator(config(), LAYOUT)
    draw = ev.draw("gen", 1)
    captured = {}

    def record(worlds, seeds, **kwargs):
        captured.update(worlds=worlds, seeds=seeds, **kwargs)
        return "supplied native stub"

    monkeypatch.setattr(build, "run", record)
    assert ev.run(torch.zeros(2, LAYOUT.size), draw) == "supplied native stub"
    assert captured["worlds"] == list(draw.worlds) * 2
    assert captured["seeds"] == list(draw.seeds) * 2
    np.testing.assert_array_equal(captured["genome_of"], [0] * 6 + [1] * 6)


def test_task_objectives_average_labels_not_seeds_and_keep_penalized_scores():
    ev = LifeEvaluator(config(), LAYOUT)
    draw = ev.draw("gen", 0)
    scores = torch.tensor([[1., 3., 10., 5., 7., 20.], [-8., -4., -20., 0., 4., -40.]], dtype=torch.float64)
    result = SimpleNamespace(trial_scores=scores)
    assert torch.equal(task_objectives(result, draw), torch.tensor([[4., 15.], [-2., -30.]], dtype=torch.float64))
    assert torch.equal(task_objectives(result, replace(draw, seeds=tuple(reversed(draw.seeds)))),
                       task_objectives(result, draw))
    with pytest.raises(ValueError, match="one task label"):
        task_objectives(result, replace(draw, tasks=()))
    with pytest.raises(ValueError, match="shape"):
        task_objectives(SimpleNamespace(trial_scores=scores[:, :3]), draw)


@pytest.mark.parametrize("tasks", [
    "dim", [dict(name="dim", world="catch_speck_l4", unknown=1)],
    [dict(name="dim", world="unknown")], [dict(name="", world="catch_speck_l4")],
    [dict(name="same", world="catch_speck_l4"), dict(name="same", world="catch_speck_l4")],
    [dict(name="dim", world="catch_speck_l4", overrides=dict(visibility_lwo=.25))],
    [dict(name="dim", world="catch_speck_l4", overrides=dict(lattice="square"))],
    *[[dict(name="dim", world="catch_speck_l4", weight=w)] for w in (0, -1, 1.5, True)],
])
def test_invalid_task_schema_rejected(tasks):
    with pytest.raises(ValueError):
        LifeEvaluator(config(tasks), LAYOUT)


@pytest.mark.parametrize("field,value", [("lives", 2), ("lives", 7), ("founder_lives", 1)])
def test_unbalanced_config_rejected(field, value):
    with pytest.raises(ValueError, match="divisible"):
        LifeEvaluator(config(**{field: value}), LAYOUT)


def test_invalid_recheck_draw_and_panel_lengths_rejected():
    cfg = config()
    cfg.evolve.recheck_lives = 2
    with pytest.raises(ValueError, match="divisible"):
        LifeEvaluator(cfg, LAYOUT)
    ev = LifeEvaluator(config(), LAYOUT)
    for lives in (0, 2, 4, 6.5, True):
        with pytest.raises(ValueError, match="divisible"):
            ev.draw("gen", 0, lives=lives)
    for lives in (0, -1, .5, True):
        with pytest.raises(ValueError, match="positive integer"):
            ev.draw_tasks("panel", 0, TASKS, lives)


def test_abi_invalid_mixed_kind_and_invalid_task_world_rejected():
    with pytest.raises(NotImplementedError):
        LifeEvaluator(config(abi=3), LAYOUT)
    with pytest.raises(ValueError, match="world_kind"):
        LifeEvaluator(config([dict(name="bell", world="bell_v1")]), LAYOUT)
    with pytest.raises(ValueError):
        LifeEvaluator(config([dict(name="bad", world="catch_speck_flash5_dim25_l4",
                                  overrides=dict(visibility_low=.375, visibility_mode=1.5))]), LAYOUT)


def test_native_tiny_batch_uses_production_extinction_scores(monkeypatch):
    """Exactly one native batch: two fixed zero genomes times four T8 lives. No genetic RNG or search."""
    tasks = [dict(name="dim", world="catch_speck_flash5_dim25_l4", overrides=dict(c_live=.02)),
             dict(name="dark", world="catch_speck_flash5_dim25_l4", overrides=dict(visibility_low=0., c_live=.04))]
    cfg = config(tasks, lives=4, founder_lives=2)
    cfg.evolve.recheck_lives = 2
    ev = LifeEvaluator(cfg, LAYOUT)
    genomes = torch.zeros(2, LAYOUT.size)
    LAYOUT.view(genomes, "a0")[0, spec.V4.K["p_die"]] = 2.0
    draw = ev.draw("gen", 0)
    original, saved = build.run, []

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        saved.append(result)
        return result

    monkeypatch.setattr(build, "run", capture)
    result = ev(genomes, draw)
    assert len(saved) == 1 and saved[0].ledger.shape == (8, spec.V4.LEDGER_SIZE)
    columns = ev.columns(saved[0], 2, draw)
    assert columns["extinct"][0].all() and (columns["extinct_charge"][0] > 0).all()
    assert not columns["invalid"].any()
    assert np.array_equal(result.trial_scores.numpy(), columns["F"])
    expected = np.column_stack((columns["F"][:, [0, 2]].mean(1), columns["F"][:, [1, 3]].mean(1)))
    assert np.array_equal(task_objectives(result, draw).numpy(), expected)
    assert torch.equal(result.fitness, result.trial_scores.mean(1))
