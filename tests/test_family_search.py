"""Small native searches verify family selection, reproducing archives and exact resume.

All populations and life seeds are fixed engineering fixtures, not scientific results.
CLI subprocesses explicitly select the checkpoint golden life's AVX2 numerical environment.
"""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import torch
from omegaconf import OmegaConf

from src import checkpoint
from src.common import load_config
from src.evolve import evolve, setup
from src.life import build
from src.search import SELECT_SEED

ROOT = Path(__file__).resolve().parents[1]
TIMES = {"t_gen", "t_eval", "t_recheck", "wall_s", "final_s", "elapsed"}
TASKS = [dict(name="dim", world="catch_speck_flash5_dim25_l4", overrides=dict(visibility_low=.375)),
         dict(name="dark", world="catch_speck_flash5_dim25_l4", overrides=dict(visibility_low=0.0))]


def clean(value, omit=TIMES):
    if isinstance(value, dict):
        return {k: clean(v, omit) for k, v in value.items() if k not in omit}
    if isinstance(value, list):
        return [clean(v, omit) for v in value]
    return value


def same_state(a, b, omit=TIMES):
    assert a.keys() == b.keys()
    for key in a.keys() - omit:
        if isinstance(a[key], torch.Tensor):
            assert a[key].dtype == b[key].dtype and a[key].shape == b[key].shape, key
            assert a[key].numpy().tobytes() == b[key].numpy().tobytes(), key
        else:
            assert clean(a[key], omit) == clean(b[key], omit), key


def read_log(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def config(mode="mean"):
    cfg = load_config("configs/life_speck.yaml", [
        "threads=1", "seed=45000123", "life.abi=4", "life.T=16", "life.T_choices=[16,32]",
        "life.lives=2", "life.founder_lives=2", "life.founder_T=16", "clones.every=0",
        "evolve.generations=6", "evolve.mu=4", "evolve.lam=6", "evolve.archive_size=2",
        "evolve.recheck_k=6", "evolve.recheck_lives=2", "evolve.recheck_key=all", "evolve.batch=16",
        "evolve.breeding=sex", "evolve.dup_rate=0.4", "evolve.del_rate=0.2",
        "logging.checkpoint_every=1", "logging.lineage=all", "world.n_max=48"])
    cfg.evolve.selection = mode
    cfg.life.training_tasks = TASKS
    return cfg


@pytest.fixture
def imported(tmp_path):
    # A single declared engineering draw supplies all four rows; no viability filtering.
    _, layout, _, _ = setup(config())
    pop = layout.random(4, torch.Generator().manual_seed(45_000_001))
    payload = dict(dims=layout.dims.__dict__, genomes=[layout.to_dict(row) for row in pop], ids=[73, 10, 84, 6])
    path = tmp_path / "input_population.json"
    path.write_text(json.dumps(payload))
    return path, pop, layout


@pytest.fixture
def native_calls(tmp_path, monkeypatch):
    original, calls = build.run, []

    def record(worlds, seeds, **kwargs):
        calls.append(dict(lives=len(seeds), fast=bool(kwargs.get("fast", False))))
        return original(worlds, seeds, **kwargs)

    monkeypatch.setattr(build, "run", record)
    yield calls
    (tmp_path / "native_inventory.json").write_text(json.dumps(dict(
        kind="engineering test fixtures", batches=len(calls), lives=sum(c["lives"] for c in calls), calls=calls)))


def search(cfg, out, **kwargs):
    out.mkdir(parents=True, exist_ok=True)
    states = []
    result = evolve(cfg, log=lambda row: None, out=out,
                    checkpoint=lambda state: states.append(copy.deepcopy(state)), **kwargs)
    return result, states


@pytest.mark.parametrize("mode", ["mean", "pareto", "epsilon_lexicase"])
def test_three_plus_resume_three_is_six_with_reproducing_archive(tmp_path, imported, native_calls, mode):
    path, initial, layout = imported
    cfg = config(mode)
    cfg.evolve.seed_population = str(path)
    full, full_states = search(cfg, tmp_path / "full")
    part, split_states = search(cfg, tmp_path / "split", stop_after=3)
    assert not part["complete"] and split_states[-1]["generation"] == 3
    resumed, final_states = search(cfg, tmp_path / "split", resume=split_states[-1])
    assert full["complete"] and resumed["complete"]
    same_state(full_states[-1], final_states[-1])
    assert clean(read_log(tmp_path / "full/lineage.jsonl")) == clean(read_log(tmp_path / "split/lineage.jsonl"))

    first = full_states[0]
    assert first["population"].numpy().tobytes() == initial.numpy().tobytes()
    assert first["ids"].tolist() == [0, 1, 2, 3]
    assert first["founders"]["source_ids"] == [73, 10, 84, 6]
    saved = json.loads((tmp_path / "full/populations/g000000.json").read_text())
    restored = torch.stack([layout.from_dict(row) for row in saved["genomes"]])
    assert restored.numpy().tobytes() == initial.numpy().tobytes()
    assert saved["ids"] == [0, 1, 2, 3] and saved["archive"]["genomes"] == []
    # Selection has its own persisted RNG; restoring only the genetic RNG cannot pass exact resume.
    for key, seed in (("generator", cfg.seed), ("selection_generator", cfg.seed + SELECT_SEED)):
        assert torch.equal(first[key], torch.Generator().manual_seed(seed).get_state())
        assert not torch.equal(first[key], full_states[-1][key])
    assert not torch.equal(full_states[-1]["generator"], full_states[-1]["selection_generator"])

    rows = [row for row in read_log(tmp_path / "full/lineage.jsonl") if "gen" in row]
    archive_draws = 0
    previous_archive = set()
    for row, curve in zip(rows, full["curves"]):
        assert row["tasks"] == ["dim", "dark"] and len(row["recheck"]["seeds"]) == 2
        assert not set(row["seeds"]) & set(row["recheck"]["seeds"])
        assert len(row["recheck"]["ids"]) == 6
        assert len(row["archive_ids"]) == 2
        assert not set(row["survivors"]) & set(row["archive_ids"])
        used = sum(child[parent] in previous_archive for child in row["children"] for parent in ("pa", "pb"))
        assert used == curve["archive_parent_draws"]
        archive_draws += used
        previous_archive = set(row["archive_ids"])
    assert archive_draws > 0, "archive rows must actually contribute parent IDs to later offspring"
    assert sum(c["lives"] for c in native_calls) == 2 * full["search_lives"]


def test_capability_panel_cannot_change_genetic_trajectory(tmp_path, imported, native_calls):
    path, _, _ = imported
    cfg = config("epsilon_lexicase")
    cfg.evolve.seed_population = str(path)
    cfg.evolve.generations = 4
    _, baseline = search(cfg, tmp_path / "no_panel")
    cfg.life.capability_panel = dict(tasks=TASKS, every=2, top=2, lives=1, seed=61_017_000)
    result, reported = search(cfg, tmp_path / "with_panel")
    assert reported[-1]["panel_lives"] == 12 and baseline[-1]["panel_lives"] == 0
    same_state(baseline[-1], reported[-1], TIMES | {"panel_lives"})
    before = read_log(tmp_path / "no_panel/lineage.jsonl")
    after = read_log(tmp_path / "with_panel/lineage.jsonl")
    observations = [row for row in after if row.get("event") == "capability_panel"]
    assert [row["generation"] for row in observations] == [0, 2, 4]
    assert all(set(entry["tasks"]) == {"dim", "dark"} for row in observations for entry in row["genomes"])
    assert before == [row for row in after if row.get("event") != "capability_panel"]
    assert sum(c["lives"] for c in native_calls) == 2 * result["search_lives"] + result["panel_lives"]


@pytest.mark.parametrize("changes,error", [
    ({"clones.every": 1}, "capability_panel"),
    ({"evolve.seed_genome": "unused.json"}, "seed_population or seed_genome"),
    ({"evolve.recheck_k": 4}, "breeding archive"),
    ({"evolve.recheck_lives": 0}, "breeding archive"),
])
def test_invalid_founder_or_clone_settings_fail_before_native_calls(imported, monkeypatch, changes, error):
    cfg = config()
    cfg.evolve.seed_population = str(imported[0])
    for key, value in changes.items():
        OmegaConf.update(cfg, key, value)
    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("invalid config reached native evaluation"))
    with pytest.raises(ValueError, match=error):
        evolve(cfg, log=lambda row: None)


def test_imported_population_cannot_be_silently_truncated(imported, monkeypatch):
    path, _, _ = imported
    cfg = config()
    cfg.evolve.seed_population = str(path)
    payload = json.loads(path.read_text())
    payload["genomes"].append(payload["genomes"][0])
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("invalid population reached native evaluation"))
    with pytest.raises(ValueError, match="exactly"):
        evolve(cfg, log=lambda row: None)


def test_epsilon_cli_checkpoint_restores_logs_and_final_artifacts(tmp_path, imported):
    cfg = config("epsilon_lexicase")
    cfg.evolve.seed_population = str(imported[0])
    # Save a resolved config so its original relative `extends` path cannot be reinterpreted.
    obj = OmegaConf.to_container(cfg, resolve=True)
    obj.pop("extends", None)
    config_path = tmp_path / "config.yaml"
    OmegaConf.save(OmegaConf.create(obj), config_path)
    full, split = tmp_path / "full/run", tmp_path / "split/run"

    def run(out, label, *flags):
        env = dict(os.environ, ATEN_CPU_CAPABILITY="avx2", OMP_WAIT_POLICY="PASSIVE",
                   OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        cmd = [sys.executable, "-m", "src.run", "--config", str(config_path), *flags,
               f"logging.output_dir={out}"]
        done = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
        (tmp_path / f"{label}.stdout").write_text(done.stdout)
        (tmp_path / f"{label}.stderr").write_text(done.stderr)
        assert done.returncode == 0, done.stdout + done.stderr

    run(full, "full")
    run(split, "first_three", "--stop-after", "3")
    middle = checkpoint.load(split / "checkpoint.pt")
    assert middle["state"]["generation"] == 3 and middle["state"]["family_search_version"] == 1
    assert "selection_generator" in middle["state"] and not (split / "results.jsonl").exists()
    for name in checkpoint.LOGS:
        with (split / name).open("a") as fh:
            fh.write('{"interrupted":')
    run(split, "resumed", "--resume")
    for name in (*checkpoint.LOGS, "results.jsonl"):
        assert clean(read_log(full / name)) == clean(read_log(split / name)), name
    for name in ("population.json", "best_genome.json", "determinism.json"):
        assert (full / name).read_bytes() == (split / name).read_bytes(), name
    a, b = (checkpoint.load(p / "checkpoint.pt")["state"] for p in (full, split))
    same_state(a, b)
    result = read_log(full / "results.jsonl")[0]
    assert result["selection"] == "epsilon_lexicase" and result["archive_count"] == 2
    assert result["task_names"] == ["dim", "dark"]
    assert result["confirmation"] == "separate fresh panel required"
    assert result["search_lives"] > 0 and result["panel_lives"] == 0
