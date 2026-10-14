"""Configuration, initialization and seed checks only; no simulation or endpoint inspection."""
import importlib.util
import json
from pathlib import Path

import pytest
import torch
from omegaconf import OmegaConf

PATH = Path(__file__).with_name("prepare.py")
SPEC = importlib.util.spec_from_file_location("structural_prepare", PATH)
prep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prep)


def protocol():
    return json.loads((prep.STUDY / "protocol.json").read_text())


def test_protocol_source_pins_and_registered_comparisons():
    value = protocol()
    baseline, _ = prep.baseline_pins()
    assert value["runs"] == [51089, 51090] and value["generations"] == 16
    assert value["source_identity"] == baseline["source_identity"]
    assert value["expected_numerical_identity"] == baseline["expected_numerical_identity"]
    assert value["prepare_sha256"] == prep.sha(PATH)
    assert value["planned_genome_lives"] == 37548
    assert value["planned_genome_lives_including_neutrality_validation"] == 37566
    assert value["max_cpu_seconds"] == 14400 and value["max_simulation_threads"] == 4
    assert value["confirmation"]["labels"] == prep.LABELS
    assert value["confirmation"]["primary_pairs"] == [[4, 2], [5, 3]]
    assert value["confirmation"]["seeds"] == list(range(51_930_000, 51_930_256))
    assert value["neutrality_validation"]["genome_lives"] == 18
    assert value["neutrality_validation"]["cpu_included_in_study_cap"] is True


@pytest.mark.parametrize("seed", prep.RUNS)
def test_only_registered_configuration_changes(seed):
    old = OmegaConf.load(prep.BASELINE / f"configs/s{seed}.yaml")
    new = OmegaConf.load(prep.STUDY / f"configs/s{seed}.yaml")
    assert prep.differences(OmegaConf.to_container(old), OmegaConf.to_container(new)) == prep.ALLOWED_CONFIG_CHANGES
    assert new.evolve.dup_rate == 0.02 and new.evolve.del_rate == 0.01 and not new.evolve.dup_split
    assert new.evolve.n_mut_scale and new.evolve.random_ties
    assert (new.evolve.mu, new.evolve.lam, new.life.lives, new.evolve.recheck_k, new.evolve.recheck_lives) == (
        32, 224, 3, 64, 4)


@pytest.mark.parametrize("seed", prep.RUNS)
def test_initial_populations_and_mutation_rng_are_identical_to_D(seed):
    from src.evolve import fill

    old = OmegaConf.load(prep.BASELINE / f"configs/s{seed}.yaml")
    new = OmegaConf.load(prep.STUDY / f"configs/s{seed}.yaml")
    layout, founder = prep.Layout.load(prep.STUDY / "inputs/founder_row38.json")
    a, b = torch.Generator().manual_seed(seed), torch.Generator().manual_seed(seed)
    old_ops, new_ops = [], []
    old_pop = fill(founder[None], 32, layout, a, old.evolve, ops=old_ops)
    new_pop = fill(founder[None], 32, layout, b, new.evolve, ops=new_ops)
    assert torch.equal(old_pop, new_pop) and torch.equal(a.get_state(), b.get_state())
    assert torch.equal(new_pop[0], founder) and len(new_ops) == 31
    assert old_ops == new_ops and all(set(op) == {"mut"} for op in new_ops)


def test_training_seed_sharing_and_confirmation_freshness():
    value = json.loads((prep.STUDY / "seed_audit.json").read_text())
    old = json.loads((prep.BASELINE / "seed_audit.json").read_text())
    assert value["run_life_seeds"] == old["run_life_seeds"]
    combined = [seed for run in value["run_life_seeds"].values() for seed in run]
    assert len(combined) == len(set(combined)) == 392
    assert not set(value["confirm_seeds"]) & set(old["confirm_seeds"])
    assert not any(51_000_000 <= seed < 52_000_000 for seed in combined)


def test_freeze_is_idempotent_and_rejects_changed_preparation(tmp_path):
    path = tmp_path / "pin.json"
    prep.freeze_json(path, {"a": 1})
    original = path.read_bytes()
    prep.freeze_json(path, {"a": 1})
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match="overwrite"):
        prep.freeze_json(path, {"a": 2})
    assert path.read_bytes() == original


def test_preparation_does_not_read_endpoints_or_run_lives(monkeypatch, capsys):
    from src.life import build

    read_text, read_bytes = Path.read_text, Path.read_bytes

    def checked_text(path, *args, **kwargs):
        assert "/runs/" not in str(path), "preparation read a D endpoint or outcome"
        return read_text(path, *args, **kwargs)

    def checked_bytes(path, *args, **kwargs):
        assert "/runs/" not in str(path), "preparation read a D endpoint or outcome"
        return read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", checked_text)
    monkeypatch.setattr(Path, "read_bytes", checked_bytes)
    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("preparation simulated a life"))
    prep.main()
    assert json.loads(capsys.readouterr().out)["status"] == "prepared_not_started"
