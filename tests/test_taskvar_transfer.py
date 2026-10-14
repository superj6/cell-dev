"""Transfer preserves fixed genomes, paired covariance, accounting, and strict cached artifacts."""
import hashlib
import json
import shutil

import numpy as np
import pytest

from scripts import taskvar_transfer as transfer


def row(score, duration=1024):
    fitness = np.asarray(score, dtype=float)
    result = {key: np.zeros(len(fitness)) for key in transfer.COLS}
    result.update(F=fitness, F_kernel=fitness.copy(), income=fitness * duration,
                  window=np.full(len(fitness), duration), t_end=np.full(len(fitness), duration),
                  cpu_seconds=np.asarray(0.1), wall_seconds=np.asarray(0.2))
    return result


def test_duration_average_keeps_cross_duration_covariance():
    parent = np.array([10, 11, 12, 13])
    gains = {"fast_T768": [1, 3, 5, 7], "fast_T1024": [7, 5, 3, 1],
             "fast_T1536": [4, 4, 4, 4], "old_T1024": [2, 2, 2, 2]}
    rows = {name: {0: row(parent), 1: row(parent + gain)} for name, gain in gains.items()}
    report, contrasts = transfer.case_report(rows, transfer.condition_worlds("base"), {})
    assert np.array_equal(contrasts["duration_average"], [4, 4, 4, 4])
    assert report["gains"]["duration_average"] == {"mean": 4, "se": 0, "n": 4}
    assert np.array_equal(contrasts["fast_minus_old_gain"], [5, 3, 1, -1])
    interaction = report["gains"]["fast_minus_old_gain"]
    assert interaction["mean"] == 2
    assert interaction["se"] == pytest.approx(np.std([5, 3, 1, -1], ddof=1) / 2)
    rows["old_T1024"][0] = row([10])
    with pytest.raises(ValueError, match="matching"):
        transfer.transfer_contrasts(rows)


def test_transfer_seed_block_and_worlds_are_fixed():
    seeds = transfer.transfer_seeds()
    assert seeds == list(range(51_850_000, 51_850_256))
    with pytest.raises(ValueError, match="overlap"):
        transfer.transfer_seeds([seeds[0]])
    worlds = transfer.condition_worlds("pool")
    assert list(worlds) == ["fast_T768", "fast_T1024", "fast_T1536", "old_T1024"]
    assert all(w.t_open == 0 and w.t_fork == 0 and w.fork_flags == 0 for w in worlds.values())
    assert all(w.sigma == 0.4 and w.lam_s == 4 for w in worlds.values())
    assert all((w.d0, w.d_min) == (0.5, 0.25) for name, w in worlds.items() if name.startswith("fast"))
    assert (worlds["old_T1024"].d0, worlds["old_T1024"].d_min) == (1, 0.5)


def mocked_study(monkeypatch):
    cases = []
    for position, (name, _, world, source_row) in enumerate(transfer.CASES):
        genomes = np.array([[position, 0], [position, 1]], dtype=np.float32)
        cases.append({"name": name, "world": world, "source_row": source_row, "genomes": genomes,
                      "evaluator": None, "winner_sha256": hashlib.sha256(genomes[1].tobytes()).hexdigest(),
                      "parent_sha256": hashlib.sha256(genomes[0].tobytes()).hexdigest()})
    monkeypatch.setattr(transfer, "load_cases", lambda archive: (cases, {"test": 1}, {}, {1, 2}))
    monkeypatch.setattr(transfer, "numerical_identity", lambda: {"test": 1})
    calls = []

    def score(out, index, genomes, world, seeds, evaluator, threads):
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"row_{index:04d}.npz"
        if path.exists():
            with np.load(path) as saved:
                return {key: saved[key].copy() for key in saved.files}
        calls.append((out.parent.name, out.name, index, genomes.copy(), world, seeds.copy()))
        values = row(np.arange(len(seeds)) + 10 + index, world.T)
        transfer.atomic_npz(path, **values)
        return values

    monkeypatch.setattr(transfer, "score_row", score)
    return cases, calls


def test_every_condition_keeps_same_fixed_winner_and_ordered_shared_seeds(tmp_path, monkeypatch):
    cases, calls = mocked_study(monkeypatch)
    out = tmp_path / "transfer"
    report = transfer.run_transfer(tmp_path / "archive", out)
    assert report["status"] == "complete"
    assert report["completed_genome_lives"] == report["planned_genome_lives"] == 8192
    assert len(calls) == 32
    assert len({tuple(call[-1]) for call in calls}) == 1
    for case in cases:
        case_calls = [call for call in calls if call[0] == case["name"]]
        assert len(case_calls) == 8
        assert all(np.array_equal(call[3], case["genomes"]) for call in case_calls)
        assert report["cases"][case["name"]]["source_row"] == case["source_row"]
        assert report["cases"][case["name"]]["gains"]["duration_average"]["mean"] == 1
    original = {p: transfer.sha(p) for p in out.glob("*/*/row_*.npz")}
    resumed = transfer.run_transfer(tmp_path / "archive", out, threads=1)
    assert len(calls) == 32  # Thread changes do not force repeat simulations.
    assert resumed["cpu_seconds"] == pytest.approx(3.2)
    assert original == {p: transfer.sha(p) for p in original}


def test_cache_change_and_source_change_stop_before_new_rows(tmp_path, monkeypatch):
    _, calls = mocked_study(monkeypatch)
    out = tmp_path / "transfer"
    transfer.run_transfer(tmp_path / "archive", out)
    saved = next(out.glob("*/*/row_*.npz"))
    saved.write_bytes(saved.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="cached transfer row differs"):
        transfer.run_transfer(tmp_path / "archive", out)
    assert len(calls) == 32
    monkeypatch.setattr(transfer, "numerical_identity", lambda: {"test": 2})
    with pytest.raises(ValueError, match="numerical/source identity differs"):
        transfer.run_transfer(tmp_path / "archive", tmp_path / "uncreated")
    assert not (tmp_path / "uncreated").exists()


def test_budget_counts_previous_rows_and_stops_before_starting_more(tmp_path, monkeypatch):
    _, calls = mocked_study(monkeypatch)
    out = tmp_path / "transfer"
    first = transfer.run_transfer(tmp_path / "archive", out, max_cpu_seconds=0.15)
    assert first["status"] == "budget_stop" and len(calls) == 2
    assert first["cpu_seconds"] == pytest.approx(0.2)
    second = transfer.run_transfer(tmp_path / "archive", out, max_cpu_seconds=0.15)
    assert second["status"] == "budget_stop" and len(calls) == 2
    with pytest.raises(ValueError, match="inputs or source identity changed"):
        transfer.run_transfer(tmp_path / "archive", out, max_cpu_seconds=1)


def test_cached_rows_require_matching_manifest(tmp_path):
    out = tmp_path / "transfer"
    out.mkdir()
    transfer.atomic_npz(out / "row_0000.npz", F=np.array([1, 2]))
    with pytest.raises(ValueError, match="without a manifest"):
        transfer.ensure_manifest(out, {"runner": "a"})
    transfer.atomic_json(out / "manifest.json", {"runner": "a"})
    with pytest.raises(ValueError, match="source identity changed"):
        transfer.ensure_manifest(out, {"runner": "b"})


def test_public_archive_verifies_fixed_genomes_and_rejects_tampering(tmp_path):
    original = transfer.ROOT / "results/pool_mutants_20261013"
    cases, _, artifacts, used = transfer.load_cases(original)
    assert [case["source_row"] for case in cases] == [38, 38, 15, 29]
    assert cases[0]["genomes"].tobytes() == cases[1]["genomes"].tobytes()
    assert not set(transfer.transfer_seeds()).intersection(used)
    archive = tmp_path / "archive"
    for relative in artifacts:
        destination = archive / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original / relative, destination)
    winner = archive / "genomes/s7_pool_winner.json"
    content = json.loads(winner.read_text())
    content["params"]["b"][0] += 1
    winner.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="archive hash differs"):
        transfer.load_cases(archive)


def test_negative_transfer_effects_are_reported_without_filtering():
    worlds = transfer.condition_worlds("pool")
    rows = {name: {0: row([10, 12], w.T), 1: row([9, 11], w.T)} for name, w in worlds.items()}
    report, _ = transfer.case_report(rows, worlds, {"source_row": 29})
    assert report["gains"]["duration_average"]["mean"] == -1
    assert len(report["conditions"]) == 4


def test_resume_recovers_completed_row_written_before_index_checkpoint(tmp_path, monkeypatch):
    _, calls = mocked_study(monkeypatch)
    out = tmp_path / "transfer"
    transfer.run_transfer(tmp_path / "archive", out)
    index_path = out / "row_index.json"
    index = json.loads(index_path.read_text())
    orphan, expected = index.popitem()
    transfer.atomic_json(index_path, index)
    report = transfer.run_transfer(tmp_path / "archive", out)
    assert len(calls) == 32
    assert report["cpu_seconds"] == pytest.approx(3.2)
    assert json.loads(index_path.read_text())[orphan] == expected
