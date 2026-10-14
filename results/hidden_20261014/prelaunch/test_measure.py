"""Synthetic H covariance, frozen-tissue and fixed-input checks; no simulation."""
import importlib.util
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
LOADER = importlib.util.spec_from_file_location("hidden_measure_test", HERE / "measure.py")
m = importlib.util.module_from_spec(LOADER)
LOADER.loader.exec_module(m)


def test_covariance_primary_keeps_both_endpoints_and_negative_effects():
    background = np.array([100., -200., 300., -400.])
    data = {key: np.stack([background] * 3) for key in m.CONDITIONS}
    data["freeze"][1] += [3, 4, 5, 6]
    data["freeze+hidden_off"][1] += [1, 2, 3, 4]
    data["freeze+hidden_off"][2] += 5
    result = m.contrasts(data)
    np.testing.assert_array_equal(result[m.LABELS[1] + "__added_hidden_dependence"], [2] * 4)
    np.testing.assert_array_equal(result[m.LABELS[2] + "__added_hidden_dependence"], [-5] * 4)
    assert len(result) == 20


@pytest.mark.parametrize("bad", [np.zeros((2, 4)), np.zeros((3, 1)), np.full((3, 4), np.nan)])
def test_bad_paired_arrays_rejected(bad):
    data = {key: np.zeros((3, 4)) for key in m.CONDITIONS}
    data["normal"] = bad
    with pytest.raises(ValueError):
        m.contrasts(data)


def test_exact_existing_flags_and_world_window():
    settings = m.worlds()
    assert [world.fork_flags for world in settings.values()] == [0, 16, 2064, 4112]
    for world in settings.values():
        assert (world.T, world.t_fork, world.t_open) == (1536, 768, 800)
        assert (world.d0, world.d_min, world.sigma, world.lam_s) == (.5, .25, .4, 4)


def rows():
    row = {"births": np.zeros(2), "deaths": np.zeros(2), "last_birth": np.array([768.2, 400]),
           "n_end": np.array([100, 120]), "n_S_end": np.array([30, 40]), "n_M_end": np.array([40, 40]),
           "n_H_end": np.array([30, 40]), "live_time": np.array([73600, 88320]),
           "status": np.zeros(2), "t_end": np.full(2, 1536)}
    return {key: {i: deepcopy(row) for i in range(3)} for key in m.CONDITIONS[1:]}


def test_constant_tissue_three_genotypes_three_frozen_conditions():
    data = rows()
    assert m.validate_frozen(data)["complete_three_arm_lives_by_genotype"] == [2, 2, 2]
    for condition in m.CONDITIONS[1:]:
        data[condition][2]["n_end"] = np.array([200, 240])
        data[condition][2]["live_time"] *= 2
    assert m.validate_frozen(data)["complete_three_arm_lives_by_genotype"] == [2, 2, 2]


@pytest.mark.parametrize("field", ["births", "deaths", "last_birth", "n_end", "n_S_end", "n_M_end",
                                    "n_H_end", "live_time", "t_end"])
def test_each_structural_difference_rejected(field):
    data = rows()
    data["freeze+hidden_off"][2][field][0] += 100
    with pytest.raises(ValueError):
        m.validate_frozen(data)


def test_guard_triplets_excluded_from_structure_but_not_deleted():
    from src.life import spec

    data = rows()
    data["freeze+hidden_off"][0]["status"][0] = spec.STATUS["guard_events"]
    data["freeze+hidden_off"][0]["live_time"][0] = 1
    report = m.validate_frozen(data)
    assert report["complete_three_arm_lives_by_genotype"] == [1, 2, 2]
    assert report["all_fitness_rows_retained"] and len(data["freeze+hidden_off"][0]["status"]) == 2


def test_protocol_source_input_seed_pins_without_simulation(monkeypatch):
    from src.life import build

    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("simulated a life"))
    protocol = m.check_protocol()
    assert protocol["seeds"] == list(range(51_940_000, 51_940_512))
    assert protocol["labels"] == list(m.LABELS)
    assert protocol["genome_lives"] == 6144 and protocol["threads"] == 2
    assert [record["generation"] for record in protocol["fixed_endpoint_audits"].values()] == [16, 16]


def test_changed_input_pin_rejected(tmp_path):
    import json
    import shutil

    shutil.copytree(HERE / "inputs", tmp_path / "inputs")
    shutil.copy2(HERE / "protocol.json", tmp_path / "protocol.json")
    p = json.loads((tmp_path / "protocol.json").read_text())
    path = tmp_path / next(iter(p["inputs"]))
    path.write_text("changed")
    with pytest.raises(ValueError, match="fixed input"):
        m.check_protocol(tmp_path)


@pytest.mark.parametrize("flag", ["capacity", "ledger_mismatch"])
def test_invalid_status_cannot_be_structurally_excluded(flag):
    from src.life import spec

    data = rows()
    data["freeze+hidden_off"][0]["status"][0] = spec.STATUS[flag]
    with pytest.raises(ValueError, match="invalid implementation"):
        m.validate_frozen(data)


def test_complete_runner_has_twelve_fixed_rows_and_no_endpoint_selection(monkeypatch, tmp_path):
    import json
    import shutil
    import sys
    from types import SimpleNamespace

    from scripts import taskvar_second_step
    from scripts.taskvar_confirm import COLS
    from src import checkpoint
    from src.life import build

    protocol = m.check_protocol()
    shutil.copytree(HERE / "inputs", tmp_path / "inputs")
    shutil.copy2(HERE / "protocol.json", tmp_path / "protocol.json")
    monkeypatch.setattr(m, "STUDY", tmp_path)
    monkeypatch.setattr(m, "check_protocol", lambda: protocol)
    monkeypatch.setitem(sys.modules, "run_budgeted", SimpleNamespace(check_ready=lambda: {"test": "ready"}))
    monkeypatch.setattr(checkpoint, "numerical_identity", lambda: protocol["numerical_identity"])
    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("simulated a life"))
    calls = []

    class Store:
        def __init__(self, out, genomes, world, evaluator, threads, cap):
            self.cpu_seconds, self.world = 0, world
            out.mkdir(parents=True, exist_ok=True)
            assert len(genomes) == 3 and threads == 2 and cap == 3600

        def row(self, stage, i, seeds):
            assert seeds == list(range(51_940_000, 51_940_512))
            calls.append((self.world.fork_flags, i))
            self.cpu_seconds += 1
            row = {key: np.zeros(512) for key in COLS}
            row.update(cpu_seconds=np.asarray(1.), wall_seconds=np.asarray(1.))
            for key, value in {"F": -2, "F_kernel": -2, "cost": 1472, "live_time": 73600,
                               "n_end": 100, "n_S_end": 30, "n_M_end": 40, "n_H_end": 30,
                               "t_end": 1536, "window": 736, "last_birth": 100}.items():
                row[key][:] = value
            return row

    monkeypatch.setattr(taskvar_second_step, "RowStore", Store)
    result = m.run()
    assert result["status"] == "complete" and result["genome_lives"] == 6144
    assert calls == [(flag, i) for flag in (0, 16, 2064, 4112) for i in range(3)]
    assert result["frozen_tissue_validation"]["complete_three_arm_lives_by_genotype"] == [512, 512, 512]
    assert len(result["contrasts"]) == 20
    for value in result["contrasts"].values():
        assert value["mean"] == value["se"] == 0 and value["n"] == 512
        assert not value["positive_above_3se"] and not value["negative_below_minus_3se"]
    saved = json.loads((tmp_path / "measurement/manifest.json").read_text())
    assert saved["labels"] == list(m.LABELS) and saved["seed_block"] == 94
    for key in m.CONDITIONS:
        with np.load(tmp_path / "measurement" / key / "scores.npz") as values:
            assert set(COLS).issubset(values.files) and values["F"].shape == (3, 512)
