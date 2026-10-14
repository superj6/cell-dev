"""Second-step selection matches production and freezes choices before fresh confirmation."""
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from scripts import taskvar_second_step as step
from src import evolve
from src.life import spec


def example_scores():
    scores = np.ones((4, 28))
    scores[1, :7], scores[1, 7:] = 5, -20
    scores[2, :3], scores[2, 3:7], scores[2, 7:] = 4, 0, 10
    scores[3] = 2
    return scores


def choose(scores, *, keep=2, shortlist=4):
    return step.select_both(scores, step.cohort_rows(len(scores) - 1, 2), list(range(28)),
                            spec.world("catch_speck_l4"), keep, shortlist, step.TIE_GENERATOR_SEED)


def test_fixed_seed_partitions_cohort_and_logical_costs():
    seeds = step.stage_seeds(86, 87, 512)
    assert seeds["screen"] == list(range(51_860_000, 51_860_028))
    assert seeds["confirm"] == list(range(51_870_000, 51_870_512))
    assert not set(seeds["screen"]) & set(seeds["confirm"])
    with pytest.raises(ValueError, match="overlap"):
        step.stage_seeds(86, 86, 512)
    mapping = step.cohort_rows(224, 32)
    assert mapping.tolist() == [0] * 32 + list(range(1, 225))
    selections = step.select_both(np.zeros((225, 28)), mapping, seeds["screen"],
                                  spec.world("catch_speck_l4"), 32, 64, step.TIE_GENERATOR_SEED)
    assert selections["low"]["initial_seeds"] == seeds["screen"][:3]
    assert selections["low"]["recheck_seeds"] == seeds["screen"][3:7]
    assert selections["high"]["initial_seeds"] == seeds["screen"][:12]
    assert selections["high"]["recheck_seeds"] == seeds["screen"][12:28]
    assert selections["low"]["logical_deployment_genome_lives"] == 1024
    assert selections["high"]["logical_deployment_genome_lives"] == 4096


def test_three_production_tie_permutations_and_paired_reset(monkeypatch):
    calls = []
    real = evolve.rank_desc

    def record(fitness, generator):
        calls.append(len(fitness))
        return real(fitness, generator)

    monkeypatch.setattr(step, "rank_desc", record)
    monkeypatch.setattr(evolve, "rank_desc", record)
    chosen = choose(np.zeros((4, 28)))
    assert calls == [5, 5, 4, 5, 5, 4]
    expected = torch.Generator().manual_seed(step.TIE_GENERATOR_SEED)
    for size in (5, 5, 4):
        torch.randperm(size, generator=expected)
    assert chosen["low"]["tie_rng_end_sha256"] == step.array_sha(expected.get_state().numpy())
    assert chosen["low"]["tie_rng_end_sha256"] == chosen["high"]["tie_rng_end_sha256"]
    assert chosen["low"]["kept_cohort_entries"] == chosen["high"]["kept_cohort_entries"]


def test_different_choices_and_low_rule_does_not_read_later_lives():
    scores = example_scores()
    chosen = choose(scores)
    assert chosen["low"]["winner_candidate_row"] == 1
    assert chosen["high"]["winner_candidate_row"] == 2
    changed = scores.copy()
    changed[3, 7:] = 1000
    second = choose(changed)
    for key in ("winner_candidate_row", "kept_cohort_entries", "pooled_kept_fitness", "shortlist_cohort_entries"):
        assert second["low"][key] == chosen["low"][key]
    assert second["high"]["winner_candidate_row"] == 3


def test_initial_shortlist_excludes_later_lucky_candidate_and_parent_can_win():
    scores = np.zeros((4, 28))
    scores[0] = 5
    scores[1:3] = 4
    scores[3, :12], scores[3, 12:] = -1, 1000
    chosen = choose(scores)
    for result in chosen.values():
        assert result["winner_candidate_row"] == 0
        assert 4 not in result["shortlist_cohort_entries"]
        assert result["parent_copy_entries_retained"] == 2


def test_confirmation_dedup_preserves_all_roles_and_raw_identity():
    genomes = np.array([[1, 2], [1, 2], [3, 4]], dtype=np.float32)
    selected = {"low": {"winner_candidate_row": 0}, "high": {"winner_candidate_row": 1}}
    rows, roles = step.confirmation_mapping(genomes, selected, 2)
    assert rows == [2, 0]
    assert roles["high"]["candidate_row"] == 1 and roles["high"]["scored_row"] == 0
    assert roles["start"]["raw_sha256"] == roles["low"]["raw_sha256"] == roles["high"]["raw_sha256"]


def mocked_study(tmp_path, monkeypatch):
    files = [tmp_path / name for name in ("start.json", "original.json", "config.yaml")]
    for path in files:
        path.write_text(path.name)
    genomes = np.arange(10, dtype=np.float32).reshape(5, 2)
    layout = SimpleNamespace(save=lambda value, path: path.write_text(json.dumps(value.tolist())))
    monkeypatch.setattr(step, "load_inputs", lambda *args: (layout, genomes, [], None))
    monkeypatch.setattr(step, "numerical_identity", lambda: {"test": 1})
    calls = []

    def score(out, index, genomes, world, seeds, evaluator, threads):
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"row_{index:04d}.npz"
        if path.exists():
            with np.load(path) as saved:
                return {key: saved[key].copy() for key in saved.files}
        calls.append((out.name, index, seeds.copy()))
        if out.name == "screen":
            values = example_scores()[index]
        else:
            frozen = json.loads((out.parent / "selection.json").read_text())
            assert frozen["rules"]["low"]["winner_candidate_row"] == 1
            assert frozen["rules"]["high"]["winner_candidate_row"] == 2
            values = np.full(len(seeds), {0: 11, 1: 9, 2: 8, 4: 10}[index], dtype=float)
        row = {key: np.zeros(len(seeds)) for key in step.COLS}
        row.update(F=values, F_kernel=values.copy(), income=values * world.T,
                   window=np.full(len(seeds), world.T), t_end=np.full(len(seeds), world.T),
                   cpu_seconds=np.asarray(0.1), wall_seconds=np.asarray(0.2))
        step.atomic_npz(path, **row)
        return row

    monkeypatch.setattr(step, "score_row", score)
    kwargs = dict(offspring=3, parent_copies=2, shortlist=4, keep=2, confirm_lives=4)
    return files, genomes, calls, kwargs


def test_choices_frozen_before_negative_confirmation_and_resumed_without_simulation(tmp_path, monkeypatch):
    files, _, calls, kwargs = mocked_study(tmp_path, monkeypatch)
    out = tmp_path / "study"
    report = step.run_study(*files, out, **kwargs)
    assert report["status"] == "complete"
    assert report["confirmation"]["low"]["second_step_gain"]["F"]["mean"] == -2
    assert report["confirmation"]["high"]["second_step_gain"]["F"]["mean"] == -3
    assert report["confirmation"]["low"]["total_gain_vs_original"]["F"]["mean"] == -1
    assert report["starting_gain_vs_original"]["F"]["mean"] == 1
    assert report["high_minus_low"] == {"mean": -1, "se": 0, "n": 4}
    assert report["actual_genome_lives"] == 4 * 28 + 4 * 4
    assert [index for stage, index, _ in calls if stage == "confirm"] == [4, 0, 1, 2]
    original = {path: step.sha(path) for path in out.glob("*/row_*.npz")}
    frozen = (out / "selection.json").read_bytes()
    resumed = step.run_study(*files, out, threads=1, **kwargs)
    assert len(calls) == 8 and resumed["cpu_seconds"] == pytest.approx(0.8)
    assert original == {path: step.sha(path) for path in original}
    assert frozen == (out / "selection.json").read_bytes()
    index_path = out / "row_index.json"
    index = json.loads(index_path.read_text())
    orphan, expected = index.popitem()
    step.atomic_json(index_path, index)
    resumed = step.run_study(*files, out, **kwargs)
    assert len(calls) == 8 and resumed["cpu_seconds"] == pytest.approx(0.8)
    assert json.loads(index_path.read_text())[orphan] == expected


@pytest.mark.parametrize("damage", ["source", "input", "genome", "row", "selection"])
def test_changed_identity_or_cache_is_rejected_without_new_lives(tmp_path, monkeypatch, damage):
    files, _, calls, kwargs = mocked_study(tmp_path, monkeypatch)
    out = tmp_path / "study"
    step.run_study(*files, out, **kwargs)
    if damage == "source":
        monkeypatch.setattr(step, "numerical_identity", lambda: {"test": 2})
    elif damage == "input":
        files[0].write_text("changed input")
    elif damage == "genome":
        np.save(out / "genomes.npy", np.zeros((5, 2)))
    elif damage == "row":
        path = out / "confirm/row_0001.npz"
        path.write_bytes(path.read_bytes() + b"changed")
    else:
        path = out / "selection.json"
        content = json.loads(path.read_text())
        content["rules"]["low"]["winner_candidate_row"] = 0
        step.atomic_json(path, content)
    with pytest.raises(ValueError, match="changed|differ"):
        step.run_study(*files, out, **kwargs)
    assert len(calls) == 8


def test_budget_persists_across_resume_and_unmanifested_cache_is_rejected(tmp_path, monkeypatch):
    files, _, calls, kwargs = mocked_study(tmp_path, monkeypatch)
    out = tmp_path / "study"
    first = step.run_study(*files, out, max_cpu_seconds=0.15, **kwargs)
    second = step.run_study(*files, out, max_cpu_seconds=0.15, **kwargs)
    assert first["status"] == second["status"] == "budget_stop"
    assert first["cpu_seconds"] == second["cpu_seconds"] == 0.2 and len(calls) == 2
    fresh = tmp_path / "unmanifested"
    fresh.mkdir()
    step.atomic_npz(fresh / "row_0000.npz", F=np.array([1, 2]))
    with pytest.raises(ValueError, match="without their study manifest"):
        step.run_study(*files, fresh, **kwargs)
