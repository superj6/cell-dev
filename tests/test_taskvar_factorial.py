"""The allele factorial preserves frozen genotypes, paired covariance and atomic resume accounting."""
import json
from pathlib import Path

import numpy as np
import pytest

from scripts import taskvar_factorial as factorial
from src.life import spec


def test_archived_alleles_are_exact_reversions_of_the_same_frozen_winner():
    genomes, worlds, _, _, artifacts, used = factorial.load_factorial(factorial.ARCHIVE)
    assert genomes.shape == (4, spec.V3.GENOME_SIZE)
    assert np.flatnonzero(genomes[1] != genomes[0]).tolist() == [41]
    assert np.flatnonzero(genomes[2] != genomes[0]).tolist() == [124]
    assert np.flatnonzero(genomes[3] != genomes[0]).tolist() == [41, 124]
    original = np.load(factorial.ARCHIVE / "genomes/s5_pool.npy", allow_pickle=False)[38]
    assert genomes[3].tobytes() == original.tobytes()
    assert genomes[1, 41] == genomes[3, 41] and genomes[2, 124] == genomes[3, 124]
    assert worlds["base"].d0 == worlds["pool"].d0 == 0.5
    assert worlds["pool"].sigma == 0.4
    assert "parents/s5/config.yaml" in artifacts
    seeds = factorial.factorial_seeds(used)
    assert seeds == list(range(51_880_000, 51_880_512))
    with pytest.raises(ValueError, match="overlap"):
        factorial.factorial_seeds([seeds[-1]])


def test_unregistered_changes_cannot_be_silently_folded_into_the_factorial():
    parent = np.zeros(spec.V3.GENOME_SIZE, dtype=np.float32)
    winner = parent.copy()
    winner[[41, 124]] = [0.1, -0.2]
    factorial.construct_genotypes(parent, winner)
    winner[200] = 0.01
    with pytest.raises(ValueError, match="exactly the two"):
        factorial.construct_genotypes(parent, winner)
    winner[200] = np.nan
    with pytest.raises(ValueError, match="finite"):
        factorial.construct_genotypes(parent, winner)


def test_archive_damage_is_detected_before_scoring(monkeypatch):
    original = factorial.sha
    monkeypatch.setattr(factorial, "sha", lambda path: "changed" if path.name == "config.yaml" else original(path))
    with pytest.raises(ValueError, match="archive hash differs"):
        factorial.load_factorial(factorial.ARCHIVE)


def test_epistasis_is_paired_before_summary_and_retains_four_arm_covariance():
    # Shared variation is large; subtracting within life leaves a known constant interaction.
    parent = np.array([1, 50, 100.0])
    values = np.stack((parent, parent + [1, 2, 3], parent + [5, 4, 3], parent + 8))
    contrasts = factorial.factorial_contrasts(values)
    assert np.array_equal(contrasts["epistasis"], [2, 2, 2])
    assert np.array_equal(contrasts["AB_minus_A"], [7, 6, 5])
    assert np.array_equal(contrasts["AB_minus_B"], [3, 4, 5])
    assert factorial.direction({"mean": 0.3, "se": 0.1}) == "unresolved"
    assert factorial.direction({"mean": -0.31, "se": 0.1}) == "negative"
    with pytest.raises(ValueError, match="four finite"):
        factorial.factorial_contrasts(values[:, :1])


def score_columns(score, world):
    row = {key: np.zeros(len(score), dtype=float) for key in factorial.COLS}
    row["F"] = np.asarray(score, dtype=float)
    row["F_kernel"] = row["F"].copy()
    row["income"] = row["F"] * world.T
    row["window"][:] = world.T
    row["t_end"][:] = world.T
    row.update(cpu_seconds=np.asarray(1.0), wall_seconds=np.asarray(2.0))
    return row


def fake_study(monkeypatch):
    world = spec.world("catch_speck_l4", T=32, d0=0.5, d_min=0.25)
    genomes = np.zeros((4, spec.V3.GENOME_SIZE), dtype=np.float32)
    monkeypatch.setattr(factorial, "load_factorial", lambda _: (
        genomes, {"base": world, "pool": world}, None, {"test": 1}, {"source": "unchanged"}, set()))
    monkeypatch.setattr(factorial, "numerical_identity", lambda: {"test": 1})
    monkeypatch.setattr(factorial, "factorial_seeds", lambda _: [51_880_000, 51_880_001])
    calls = []

    def row(out, index, genomes, world, seeds, evaluator, threads):
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"row_{index:04d}.npz"
        values = score_columns([10 + index] * len(seeds), world)
        if not path.exists():
            calls.append((out.name, index))
            factorial.atomic_npz(path, seeds=np.asarray(seeds), genome_index=np.asarray(index), **values)
        return values

    monkeypatch.setattr(factorial, "score_row", row)
    return calls


def test_factorial_resume_preserves_rows_counts_preexisting_cpu_and_keeps_all_contrasts(tmp_path, monkeypatch):
    calls = fake_study(monkeypatch)
    out = tmp_path / "factorial"
    report = factorial.run_factorial(tmp_path / "archive", out)
    assert calls == [(name, i) for name in ("base", "pool") for i in range(4)]
    assert report["status"] == "complete" and report["cpu_seconds"] == 8
    assert report["planned_genome_lives"] == 16
    for value in report["worlds"].values():
        assert value["primary"]["mean"] == 0 and value["primary"]["se"] == 0
        assert value["two_step_paths"]["A_then_B"] == {"first": "positive", "second": "positive"}
        assert value["contrasts"]["F"]["AB_minus_parent"]["mean"] == 3
    resumed = factorial.run_factorial(tmp_path / "archive", out)
    assert len(calls) == 8 and resumed == report
    assert not list(out.rglob("*.tmp*"))
    with pytest.raises(ValueError, match="inputs or sources changed"):
        factorial.run_factorial(tmp_path / "archive", out, max_cpu_seconds=1000)


def test_factorial_budget_retains_completed_rows_and_remains_incomplete(tmp_path, monkeypatch):
    calls = fake_study(monkeypatch)
    out = tmp_path / "factorial"
    report = factorial.run_factorial(tmp_path / "archive", out, max_cpu_seconds=2)
    assert calls == [("base", 0), ("base", 1)]
    assert report["status"] == "budget_exhausted" and report["cpu_seconds"] == 2
    assert report["worlds"] == {}
    resumed = factorial.run_factorial(tmp_path / "archive", out, max_cpu_seconds=2)
    assert len(calls) == 2 and resumed == report
    assert json.loads((out / "report.json").read_text())["status"] == "budget_exhausted"


def test_resume_rejects_tampered_finite_cpu_metadata(tmp_path, monkeypatch):
    calls = fake_study(monkeypatch)
    out = tmp_path / "factorial"
    factorial.run_factorial(tmp_path / "archive", out, max_cpu_seconds=2)
    path = out / "base/row_0000.npz"
    with np.load(path, allow_pickle=False) as saved:
        damaged = {key: saved[key].copy() for key in saved.files}
    damaged["cpu_seconds"] = np.asarray(0.125)
    factorial.atomic_npz(path, **damaged)
    with pytest.raises(ValueError, match="byte-hash checkpoint"):
        factorial.run_factorial(tmp_path / "archive", out, max_cpu_seconds=2)
    assert calls == [("base", 0), ("base", 1)]


def test_numerical_identity_or_missing_manifest_stops_before_scoring(tmp_path, monkeypatch):
    calls = fake_study(monkeypatch)
    out = tmp_path / "factorial"
    monkeypatch.setattr(factorial, "numerical_identity", lambda: {"test": 2})
    with pytest.raises(ValueError, match="identity differs"):
        factorial.run_factorial(tmp_path / "archive", out)
    assert not out.exists() and calls == []
    monkeypatch.setattr(factorial, "numerical_identity", lambda: {"test": 1})
    out.mkdir()
    np.savez(out / "unbound.npz", values=[1])
    with pytest.raises(ValueError, match="without a factorial manifest"):
        factorial.run_factorial(tmp_path / "archive", out)
    assert calls == []


def test_cli_is_dry_run_and_has_the_registered_life_count(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["taskvar_factorial"])
    monkeypatch.setattr(factorial, "run_factorial", lambda *args, **kwargs: pytest.fail("dry run simulated lives"))
    factorial.main()
    value = json.loads(capsys.readouterr().out)
    assert value["status"] == "dry_run" and value["genome_lives"] == 4096
    assert value["seed_block"] == 88 and value["max_cpu_seconds"] == 1800
    assert Path(value["out"]).parts[-2:] == ("autonomous_followthrough_20261013", "factorial")
