import json

import torch

from src.common import load_config
from src.genome import Dims, Layout
from src.run import main


def test_crossover_of_identical_parents_returns_the_parent():
    lay = Layout(Dims())
    p = lay.random(8, torch.Generator().manual_seed(0))
    assert torch.equal(lay.crossover(p, p, torch.Generator().manual_seed(1)), p)


def test_crossover_inherits_whole_units():
    lay = Layout(Dims())
    g = torch.Generator().manual_seed(0)
    a, b = lay.random(16, g), lay.random(16, g)
    child = lay.crossover(a, b, g)
    for u in range(lay.n_units):
        sel = lay.unit_of == u
        from_a = (child[:, sel] == a[:, sel]).all(1)
        from_b = (child[:, sel] == b[:, sel]).all(1)
        assert (from_a | from_b).all()
    assert lay.n_units == Dims().genes + Dims().types + 1


def test_mutation_touches_one_block_only():
    lay = Layout(Dims())
    g = torch.Generator().manual_seed(0)
    p = lay.random(64, g)
    m = lay.mutate(p, g, n_mut=3)
    changed = m != p
    assert (changed.sum(1) <= 3).all() and (changed.sum(1) >= 1).all()
    blocks = [lay.block_of[row].unique().numel() for row in changed]
    assert all(n == 1 for n in blocks)


def test_smoke_run_writes_outputs(tmp_path):
    cfg = load_config("configs/local_smoke.yaml", [f"logging.output_dir={tmp_path}"])
    results = main(cfg)
    row = json.loads(results.read_text().splitlines()[-1])
    assert {"heldout_score", "heldout_no_messages", "evals", "n_cells", "energy"} <= set(row)
    assert (tmp_path / "best_genome.json").exists() and len((tmp_path / "curves.jsonl").read_text().splitlines()) == 3
    layout, params = Layout.load(tmp_path / "best_genome.json")
    assert params.shape == (layout.size,)


def test_fixed_tissue_baseline_and_random_search_modes(tmp_path):
    cfg = load_config("configs/local_smoke.yaml", [f"logging.output_dir={tmp_path / 'fixed'}", "develop.mode=fixed",
                                                   "develop.fixed_radius=2"])
    row = json.loads(main(cfg).read_text().splitlines()[-1])
    assert row["n_cells"] == 19 and row["types_used"] == 1  # hex disk of radius 2
    cfg = load_config("configs/local_smoke.yaml", [f"logging.output_dir={tmp_path / 'rs'}", "evolve.generations=0",
                                                   "evolve.init_samples=64"])
    row = json.loads(main(cfg).read_text().splitlines()[-1])
    assert row["evals"] == 64


def test_founder_sampling_continues_until_something_scores(tmp_path):
    """An unreachable founder score forces sampling up to the cap: a dead start must not be accepted silently."""
    cfg = load_config("configs/local_smoke.yaml", [f"logging.output_dir={tmp_path}", "evolve.generations=0",
                                                   "evolve.init_samples=32", "evolve.min_founder_score=2.0",
                                                   "evolve.max_init_samples=96"])
    row = json.loads(main(cfg).read_text().splitlines()[-1])
    assert row["evals"] == 96


def test_ladder_advance_brings_in_immigrant_founders(tmp_path):
    cfg = load_config("configs/local_smoke.yaml", [f"logging.output_dir={tmp_path}", "task.name=ladder",
                                                   "task.rungs=[light,memory]", "evolve.advance_at=-1.0",
                                                   "evolve.immigrants=0.5", "evolve.generations=3"])
    main(cfg)
    rows = [json.loads(line) for line in (tmp_path / "curves.jsonl").read_text().splitlines()]
    advanced = [r for r in rows if "advanced_to" in r]
    assert len(advanced) == 1 and advanced[0]["immigrants"]["replaced"] == 2  # mu = 4 in the smoke config
    assert rows[-1]["evals"] > rows[0]["evals"] + 2 * 16  # immigrant sampling is counted
