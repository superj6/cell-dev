"""Supplied arrays and mocked evaluator only: no builds, native lives or genetic draws."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
import torch
from omegaconf import OmegaConf

from scripts import confirm_multitask as confirm
from src.life import build, spec
from src.life.evaluate import LifeDraw, life_seed


@pytest.fixture(autouse=True)
def forbid_engine(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("multitask unit tests must not build or run the native engine")

    monkeypatch.setattr(build, "build", forbidden)
    monkeypatch.setattr(build, "run", forbidden)


def test_minimax_selects_one_generalist_instead_of_a_portfolio():
    scores = np.array([[10., 0.], [0., 10.], [4., 4.]])
    ranks = confirm.percentile_ranks(scores)
    rows = [{"id": 5 + i, "cohort_index": i} for i in range(3)]
    assert confirm.choose(scores, ranks, rows) == rows[2]
    assert np.array_equal(ranks, [[1, 0], [0, 1], [.5, .5]])


def test_pooled_cohort_keeps_absolute_stage_rank_differences_and_average_ties():
    scores = np.array([[0, 9], [1, 9], [1, 9], [3, 9]], dtype=float)
    ranks = confirm.percentile_ranks(scores)
    assert np.array_equal(ranks[:, 0], [0, .5, .5, 1])
    assert np.array_equal(ranks[:, 1], [.5] * 4)
    # Ranking each two-row stage separately would incorrectly assign both stage champions rank1.
    assert ranks[1, 0] < ranks[3, 0]
    assert np.array_equal(confirm.percentile_ranks([[1, 1]]), [[.5, .5]])


def test_rank_selection_secondary_order_mean_rank_then_F_then_ID():
    rows = [{"id": 20, "cohort_index": 0}, {"id": 10, "cohort_index": 1}]
    scores = np.array([[100., 100.], [1., 1.]])
    assert confirm.choose(scores, np.array([[.2, .3], [.2, .8]]), rows) == rows[1]
    ranks = np.ones((2, 2)) * .5
    assert confirm.choose(scores, ranks, rows) == rows[0]
    assert confirm.choose(np.ones((2, 2)), ranks, rows) == rows[1]


def test_task_rank_scaling_and_input_immutability():
    values = np.array([[3., 8.], [7., 8.], [7., 4.], [9., 0.]])
    original = values.copy()
    assert np.array_equal(confirm.percentile_ranks(values), confirm.percentile_ranks(values * [2, .5] + [1, -10]))
    assert np.array_equal(values, original)


@pytest.mark.parametrize("values", [[], [[np.nan]], [[np.inf]], [1., 2.]])
def test_invalid_score_arrays(values):
    with pytest.raises(ValueError):
        confirm.percentile_ranks(values)


@dataclass
class Dims:
    size: int = 1


class Layout:
    dims = Dims()

    def from_dict(self, value):
        return torch.tensor(value, dtype=torch.float32)

    def to_dict(self, value):
        return value.tolist()


def snapshot(generation, current, archive):
    def group(rows):
        return {"dims": {"size": 1}, "ids": [identity for identity, _ in rows],
                "genomes": [[float(value)] for _, value in rows]}

    return dict(group(current), generation=generation, archive=group(archive))


def snapshots():
    return {0: snapshot(0, [(1, 0), (2, 1)], [(10, 2)]),
            2: snapshot(2, [(1, 0), (11, 3)], [(10, 2)]),
            4: snapshot(4, [(2, 1), (12, 4)], [(11, 3)])}


def test_cohort_deduplicates_across_stages_and_preserves_initial_archive():
    genes, rows, stages = confirm.cohort(snapshots(), Layout(), 2, 3)
    assert genes[:, 0].tolist() == [0, 1, 2, 3, 4]
    assert len(rows[0]["memberships"]) == 2
    assert stages[0][-1] == {"generation": 0, "id": 10, "source": "archive", "cohort_index": 2}
    data = snapshots()
    data[0]["archive"]["genomes"].append([1.])
    data[0]["archive"]["ids"].append(20)
    _, rows, stages = confirm.cohort(data, Layout(), 2, 3)
    assert len(stages[0]) == 3 and len(rows[1]["memberships"]) == 3
    assert [r["id"] for r in stages[0] if r["cohort_index"] == 1] == [2]


def test_cohort_rejects_changed_native_id_or_archive_capacity():
    data = snapshots()
    data[2]["genomes"][0] = [99.]
    with pytest.raises(ValueError, match="ID changed genotype"):
        confirm.cohort(data, Layout(), 2, 3)
    with pytest.raises(ValueError, match="capacity"):
        confirm.cohort(snapshots(), Layout(), 2, 0)


def configuration(out):
    def task(name):
        return {"name": name, "world": "catch_speck_l4"}
    return OmegaConf.create({"logging": {"output_dir": str(out)},
        "evolve": {"mu": 2, "archive_size": 3, "generations": 4},
        "life": {"training_tasks": [task("a"), task("b")]},
        "confirmation": {"stages": [0, 2, 4], "seed": 61018900, "development_lives": 2,
                         "lives": 3, "reserved_tasks": [task("reserved")]}})


class MockEvaluator:
    abi = spec.V7

    def __init__(self, out):
        self.out, self.calls = out, []

    def draw_tasks(self, purpose, index, tasks, lives, seed=None):
        names = tuple(task["name"] for task in tasks for _ in range(lives))
        worlds = tuple(spec.world(task["world"]) for task in tasks for _ in range(lives))
        # Like LifeEvaluator.draw_tasks: a study seed keys the panel's lives.
        seeds = (tuple(range(len(names))) if seed is None
                 else tuple(life_seed(seed, purpose, index, i) for i in range(len(names))))
        return LifeDraw(seeds, worlds, names)

    def run(self, genes, draw):
        if "reserved" in draw.tasks:
            frozen = json.loads((self.out / "confirmation" / "selection.json").read_text())
            assert set(frozen["choices"]) == {"0", "2", "4"}
            assert all(len(choice["F_means"]) == 2 for choice in frozen["choices"].values())
        self.calls.append((genes[:, 0].tolist(), draw.tasks, draw.seeds))
        ledger = np.zeros((len(genes) * draw.n, self.abi.LEDGER_SIZE))
        scores = [[6, 0], [0, 6], [3, 3], [4, 4], [5, 5]]
        for i, gene in enumerate(genes[:, 0].tolist()):
            for j, task in enumerate(draw.tasks):
                row = ledger[i * draw.n + j]
                row[self.abi.L["F"]] = scores[int(gene)][task == "b"] if task != "reserved" else 1000 - gene * 1000
                for key in ("captures", "low_light_captures", "n_end", "live_time"):
                    row[self.abi.L[key]] = gene + 1
                row[self.abi.L["income"]] = (gene + 1) * 500
        return build.Lives(ledger, np.zeros((len(ledger), self.abi.HASH_SIZE), dtype=np.uint64), abi=self.abi)

    def columns(self, result, batch, draw):
        ledger = result.ledger.reshape(batch, draw.n, -1)
        col = {k: ledger[:, :, i] for k, i in self.abi.L.items()}
        col.update(window=np.ones((batch, draw.n)), extinct_charge=np.zeros((batch, draw.n)),
                   guard=np.zeros((batch, draw.n), dtype=bool), extinct=np.zeros((batch, draw.n), dtype=bool),
                   invalid=np.zeros((batch, draw.n), dtype=bool), F_kernel=col["F"])
        return col


def test_mocked_end_to_end_union_reserved_isolation_freeze_resume_and_source_change(tmp_path):
    directory = tmp_path / "populations"
    directory.mkdir()
    for stage, payload in snapshots().items():
        (directory / f"g{stage:06d}.json").write_text(json.dumps(payload))
    cfg = configuration(tmp_path)
    ev = MockEvaluator(tmp_path)
    result = confirm.confirm(cfg, Layout(), ev, {"checkpoint": "fixed"})
    assert result["development_genotypes"] == 5 and result["lives"] == 47
    assert len(ev.calls) == 4 and set(ev.calls[0][1]) == {"a", "b"}
    assert [call[0] for call in ev.calls[1:]] == [[2.], [3.], [4.]]
    assert all(call[2] == ev.calls[1][2] for call in ev.calls[1:])
    assert set(ev.calls[0][2]).isdisjoint(ev.calls[1][2])
    frozen = json.loads((tmp_path / "confirmation" / "selection.json").read_text())
    assert frozen["choices"]["0"]["source"] == "archive"
    table = json.loads((tmp_path / "confirmation" / "development.json").read_text())
    assert np.asarray(table["F_means"]).shape == (5, 2)
    assert np.asarray(table["percentile_ranks"]).shape == (5, 2)
    assert result["paired"]["g4_minus_g2"]["a"]["captures"]["mean"] == 1
    assert result["results"]["4"]["reserved"]["F"]["mean"] == -3000  # held-out failure is preserved
    assert result["matching_ratios"]["4"]["reserved"]["narrow"]["completed_accuracy"]["value"] is None
    assert confirm.confirm(cfg, Layout(), ev, {"checkpoint": "fixed"}) == result
    assert len(ev.calls) == 4
    cfg.confirmation.reserved_tasks[0].world = "catch_speck_flash5_dim25_l4"
    with pytest.raises(ValueError, match="cached input metadata differs"):
        confirm.confirm(cfg, Layout(), ev, {"checkpoint": "fixed"})
    assert len(ev.calls) == 4


def test_source_food_cost_components_and_boolean_rates():
    ev = MockEvaluator(Path("unused"))
    tasks = [{"name": "resource", "world": "catch_contact_resources_l4"}]
    draw = ev.draw_tasks("confirm", 200, tasks, 2)
    col = {k: np.zeros((1, 2)) for k in spec.V7.L}
    col.update(window=np.full((1, 2), 100.), extinct_charge=np.full((1, 2), .5),
               guard=np.ones((1, 2), dtype=bool), extinct=np.ones((1, 2), dtype=bool), F_kernel=np.zeros((1, 2)))
    col["patch_initial_harvest_0"][:] = 2
    col["patch_refill_harvest_0"][:] = 5
    col["patch_contact_harvest_0"][:] = 3
    col["live_time"][:] = 50
    col["misses"][:] = 4
    col["income"][:] = 3500
    col["cost"][:] = 42
    col["guard_charge"][:] = 20
    col["F"][:] = 35 - .42 - .2 - .5
    result = confirm.metrics(col, draw)
    assert result["guard"].dtype == result["extinct"].dtype == np.float64
    assert np.array_equal(result["passive_refill_harvest"], [2., 2.])
    assert np.array_equal(result["patch_contact_food_F"], [15., 15.])
    assert np.array_equal(result["patch_passive_food_F"], [10., 10.])
    assert np.array_equal(result["patch_initial_food_F"], [10., 10.])
    assert np.allclose(result["F"], sum(result[k] for k in ("income_F", "physical_cost_F", "guard_F", "extinction_F")))
    assert np.array_equal(result["cost_misses_F"], [-.4, -.4])


def test_sample_classes_and_paired_life_uncertainty_are_separate():
    tasks = [{"name": "matching", "world": "catch_delayed_match_l4"}]
    draw = MockEvaluator(Path("unused")).draw_tasks("confirm", 200, tasks, 2)
    base = {f"{metric}_{label}": np.zeros(2) for metric in (
        "choice_opportunities", "choice_carry_in", "correct_choices", "wrong_choices") for label in ("narrow", "broad")}
    for label in ("narrow", "broad"):
        base[f"choice_opportunities_{label}"] = np.array([1., 3.])
    base["correct_choices_narrow"] = np.array([1., 3.])
    base["wrong_choices_broad"] = np.array([1., 3.])
    base["F"] = np.array([-100., 100.])
    final = {key: values.copy() for key, values in base.items()}
    final["F"] += 2
    report = confirm.summarize({0: base, 4: final}, draw, [0, 4], ["matching"])
    assert report["paired"]["g4_minus_g0"]["matching"]["F"] == {"mean": 2., "se": 0., "n": 2}
    rates = report["matching_ratios"]["4"]["matching"]
    assert rates["narrow"]["correct_per_opportunity"]["value"] == 1
    assert rates["broad"]["correct_per_opportunity"]["value"] == 0
    assert rates["broad"]["completed_accuracy"]["value"] == 0


def test_configuration_requires_final_stage_unique_tasks_and_sufficient_lives(tmp_path):
    cfg = configuration(tmp_path)
    confirm.settings(cfg)
    cfg.confirmation.stages = [0, 2]
    with pytest.raises(ValueError, match="configured final"):
        confirm.settings(cfg)
    cfg.confirmation.stages = [0, 2, 4]
    cfg.confirmation.reserved_tasks[0].name = "a"
    with pytest.raises(ValueError, match="unique"):
        confirm.settings(cfg)
    cfg.confirmation.reserved_tasks[0].name = "reserved"
    cfg.confirmation.lives = 1
    with pytest.raises(ValueError, match="at least two"):
        confirm.settings(cfg)


def test_selected_binary_must_match_checkpoint_without_new_build(tmp_path, monkeypatch):
    path = tmp_path / "library.so"
    path.write_bytes(b"supplied library bytes")
    monkeypatch.setattr(build, "library_path", lambda fast: path)
    identity = {"kernels": {"True": confirm.cache.digest(path.read_bytes())}}
    confirm.verify_kernel(identity, True)
    path.write_bytes(b"changed library")
    with pytest.raises(ValueError, match="native library differs"):
        confirm.verify_kernel(identity, True)
