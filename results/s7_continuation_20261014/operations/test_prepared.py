"""L's new role/seed/initialization mapping and confirmation lifecycle; pure or mocked, no lives."""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch
from omegaconf import OmegaConf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def runner():
    module("run_budgeted", HERE / "run_budgeted.py")
    return module("L_confirmation_test", HERE / "measure.py")


def test_exact_initial_population_and_unchanged_D_configuration():
    from src.evolve import fill, setup
    from src.genome import Layout

    torch.set_num_threads(2)
    prep = module("L_prepare_test", HERE / "prepare.py")
    protocol = json.loads((HERE / "protocol.json").read_text())
    receipt = json.loads((HERE / "initialization.json").read_text())
    assert protocol["planned_genome_lives"] == 36012 and receipt["simulated_lives"] == 0
    assert protocol["selection_T1024_equivalent_lives"] == 36608
    _, founder = Layout.load(HERE / "inputs/founder_row29.json")
    for seed, old in zip((51891, 51892), (51089, 51090)):
        cfg = OmegaConf.load(HERE / f"configs/s{seed}.yaml")
        previous = OmegaConf.load(ROOT / f"results/continuation_20261013/configs/s{old}.yaml")
        assert prep.differences(OmegaConf.to_container(previous), OmegaConf.to_container(cfg)) == prep.ALLOWED
        _, layout, _, _ = setup(cfg)
        generator, operations = torch.Generator().manual_seed(seed), []
        population = fill(founder[None], 32, layout, generator, cfg.evolve, ops=operations).numpy()
        saved = np.load(HERE / receipt["runs"][str(seed)]["population_file"], allow_pickle=False)
        assert population.shape == (32, 875) and population.tobytes() == saved.tobytes()
        assert saved[0].tobytes() == founder.numpy().tobytes()
        assert [item["ops"] for item in receipt["runs"][str(seed)]["copies"]] == operations
        assert len(operations) == 31 and all(set(item) == {"mut"} for item in operations)
        assert cfg.life.valid_lives == 16 and cfg.evolve.heldout_every == 4
        assert cfg.life.final_top == 1 and cfg.life.final_lives == 2


def test_all_prospective_hash_seeds_avoid_fresh_block_and_prior_namespaces():
    prep = module("L_seed_test", HERE / "prepare.py")
    helper = prep.seed_helpers()
    audit = json.loads((HERE / "seed_audit.json").read_text())
    expected = {str(seed): helper.run_life_seeds(seed) for seed in (51891, 51892)}
    assert expected == audit["run_life_seeds"]
    flattened = [value for values in expected.values() for value in values]
    assert len(flattened) == len(set(flattened)) == 392
    old = helper.pilot_life_seeds()
    old.update(value for seed in (51089, 51090) for value in helper.run_life_seeds(seed))
    assert not set(flattened) & old
    assert not any(51_000_000 <= value < 52_000_000 for value in flattened)
    assert audit["confirm_seeds"] == list(range(51_900_000, 51_900_256))
    assert not set(audit["confirm_seeds"]) & (old | set(flattened))


def test_duration_average_retains_seed_covariance_and_negative_effects():
    m = runner()
    common = np.array([1., 50., 100.])
    values = {name: {1: {"F": common}, 2: {"F": common + delta}, 3: {"F": common - 1}}
              for name, delta in (("768", [1, 2, 3]), ("1024", [3, 2, 1]), ("1536", [2, 2, 2]))}
    assert m.duration_mixture(values, 2, 1).tolist() == [2, 2, 2]
    assert m.duration_mixture(values, 3, 1).tolist() == [-1, -1, -1]
    with pytest.raises(ValueError, match="three registered"):
        m.duration_mixture({"1024": values["1024"]}, 2, 1)


def confirmation_fixture(monkeypatch, tmp_path, *, generation=16, invalid=0):
    from src import checkpoint
    from src.genome import Layout
    from src.life import build

    m = runner()
    protocol = json.loads((HERE / "protocol.json").read_text())
    _, founder = Layout.load(HERE / "inputs/founder_row29.json")
    layout, _ = Layout.load(HERE / "inputs/pilot_s7.json")
    states = {}
    for i, seed in enumerate(protocol["runs"]):
        folder = tmp_path / f"runs/s{seed}"
        folder.mkdir(parents=True)
        endpoint = founder.clone()
        endpoint[0] += (i + 1) * .125
        layout.save(endpoint, folder / "best_genome.json")
        (folder / "checkpoint.pt").write_bytes(b"synthetic checkpoint")
        states[str(seed)] = {"state": {"generation": generation, "population": endpoint[None], "curves": [
            {"gen": g, "pop_invalid": invalid, "pop_mismatch": 0, "recheck_invalid": 0} for g in range(generation)]}}
    monkeypatch.setattr(m, "STUDY", tmp_path)
    (tmp_path / "protocol.json").write_text((HERE / "protocol.json").read_text())
    (tmp_path / "seed_audit.json").write_text((HERE / "seed_audit.json").read_text())
    monkeypatch.setattr(m, "check_protocol", lambda: protocol)
    monkeypatch.setattr(m, "check_ready", lambda: {"synthetic": True})
    monkeypatch.setattr(checkpoint, "numerical_identity", lambda: protocol["expected_numerical_identity"])
    monkeypatch.setattr(checkpoint, "load", lambda path: states[path.parent.name.removeprefix("s")])
    monkeypatch.setattr(checkpoint, "validate", lambda *args: None)
    monkeypatch.setattr(build, "run", lambda *args, **kwargs: pytest.fail("simulated a life"))
    return m, protocol


def test_confirmation_freezes_four_roles_before_scoring_and_retains_negative_endpoint(monkeypatch, tmp_path):
    from scripts import taskvar_confirm

    m, protocol = confirmation_fixture(monkeypatch, tmp_path)
    calls = []

    def score(out, index, genomes, world, seeds, evaluator, threads):
        manifest = json.loads((tmp_path / "confirmation/manifest.json").read_text())
        assert manifest["labels"] == protocol["confirmation"]["labels"]
        assert manifest["seed_block"] == 90 and manifest["seeds"] == list(range(51_900_000, 51_900_256))
        assert set(manifest["checkpoint_sha256"]) == {"51891", "51892"}
        assert (tmp_path / "confirmation/genotypes.npz").exists()
        assert genomes.shape == (4, 875) and threads == 2
        assert len(seeds) == 256 and world.t_open == 0 and world.t_fork == 0 and world.fork_flags == 0
        calls.append((int(world.T), index))
        row = {key: np.zeros(256) for key in taskvar_confirm.COLS}
        row["F"][:] = (0, 1, 3, -1)[index]
        row["F_kernel"][:] = row["F"]
        row["income"][:] = 10000 + row["F"] * world.T
        row["cost"][:] = 10000
        row["window"][:], row["t_end"][:] = world.T, world.T
        out.mkdir(parents=True, exist_ok=True)
        taskvar_confirm.atomic_npz(out / f"row_{index:04d}.npz", **row)
        return row

    monkeypatch.setattr(taskvar_confirm, "score_row", score)
    m.confirm_endpoints()
    assert calls == [(t, row) for t in (768, 1024, 1536) for row in range(4)]
    report = json.loads((tmp_path / "confirmation/report.json").read_text())
    assert report["status"] == "complete" and report["genome_lives"] == 3072
    assert report["primary"]["s51891_final_rank0"]["mean"] == 2
    assert report["primary"]["s51892_final_rank0"]["mean"] == -2
    assert report["primary"]["s51891_final_rank0"]["n"] == 256


@pytest.mark.parametrize("generation,invalid", [(15, 0), (16, 1)])
def test_confirmation_rejects_incomplete_or_invalid_endpoint_before_any_scoring(
        monkeypatch, tmp_path, generation, invalid):
    from scripts import taskvar_confirm

    m, _ = confirmation_fixture(monkeypatch, tmp_path, generation=generation, invalid=invalid)
    monkeypatch.setattr(taskvar_confirm, "score_row", lambda *a, **k: pytest.fail("scored an invalid endpoint"))
    with pytest.raises(ValueError, match="incomplete|invalid"):
        m.confirm_endpoints()
    assert not (tmp_path / "confirmation/manifest.json").exists()
