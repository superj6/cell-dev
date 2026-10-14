"""Synthetic R covariance, fixed-structure and fixed-input checks; no simulation."""
import importlib.util
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
LOADER = importlib.util.spec_from_file_location("weight_measure_test", HERE / "measure.py")
m = importlib.util.module_from_spec(LOADER)
LOADER.loader.exec_module(m)


def test_covariance_primary_keeps_both_endpoints_and_negative_effects():
    background = np.array([100., -200., 300., -400.])
    data = {key: np.stack([background] * 3) for key in m.CONDITIONS}
    data["C"][1] += [3, 4, 5, 6]
    data["F"][1] += [1, 2, 3, 4]
    data["F"][2] += 5
    result = m.contrasts(data)
    np.testing.assert_array_equal(result[m.LABELS[1] + "__added_C_minus_F"], [2] * 4)
    np.testing.assert_array_equal(result[m.LABELS[2] + "__added_C_minus_F"], [-5] * 4)
    assert len(result) == 16


@pytest.mark.parametrize("bad", [np.zeros((2, 4)), np.zeros((3, 1)), np.full((3, 4), np.nan)])
def test_bad_paired_arrays_rejected(bad):
    data = {key: np.zeros((3, 4)) for key in m.CONDITIONS}
    data["S"] = bad
    with pytest.raises(ValueError):
        m.contrasts(data)


def test_exact_existing_flags_and_world_window():
    settings = m.worlds()
    assert [world.fork_flags for world in settings.values()] == [12, 204, 16]
    for world in settings.values():
        assert (world.T, world.t_fork, world.t_open) == (1536, 768, 800)
        assert (world.d0, world.d_min, world.sigma, world.lam_s) == (.5, .25, .4, 4)


def rows():
    row = {"births": np.zeros(2), "deaths": np.zeros(2), "last_birth": np.array([768.2, 400]),
           "n_end": np.array([100, 120]), "n_S_end": np.array([30, 40]), "n_M_end": np.array([40, 40]),
           "n_H_end": np.array([30, 40]), "live_time": np.array([73600, 88320]),
           "status": np.zeros(2), "t_end": np.full(2, 1536)}
    return {key: {i: deepcopy(row) for i in range(3)} for key in m.CONDITIONS}


def test_constant_tissue_three_genotypes_three_structure_conditions():
    data = rows()
    assert m.validate_structure(data)["complete_three_arm_lives_by_genotype"] == [2, 2, 2]
    for condition in m.CONDITIONS:
        data[condition][2]["n_end"] = np.array([200, 240])
        data[condition][2]["live_time"] *= 2
    assert m.validate_structure(data)["complete_three_arm_lives_by_genotype"] == [2, 2, 2]


@pytest.mark.parametrize("field", ["births", "deaths", "last_birth", "n_end", "n_S_end", "n_M_end",
                                    "n_H_end", "live_time", "t_end"])
def test_each_structural_difference_rejected(field):
    data = rows()
    data["F"][2][field][0] += 100
    with pytest.raises(ValueError):
        m.validate_structure(data)


def test_guard_triplets_excluded_from_structure_but_not_deleted():
    from src.life import spec

    data = rows()
    data["F"][0]["status"][0] = spec.STATUS["guard_events"]
    data["F"][0]["live_time"][0] = 1
    report = m.validate_structure(data)
    assert report["complete_three_arm_lives_by_genotype"] == [1, 2, 2]
    assert report["all_fitness_rows_retained"] and len(data["F"][0]["status"]) == 2


def test_protocol_source_input_seed_pins_without_simulation(monkeypatch):
    from src.life import build

    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("simulated a life"))
    protocol = m.check_protocol()
    assert protocol["seeds"] == list(range(52_040_000, 52_040_512))
    assert protocol["labels"] == list(m.LABELS)
    assert protocol["genome_lives"] == 4608 and protocol["threads"] == 2
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
    data["F"][0]["status"][0] = spec.STATUS[flag]
    with pytest.raises(ValueError, match="invalid implementation"):
        m.validate_structure(data)


@pytest.mark.parametrize("fail_after", [None, 5])
def test_complete_runner_has_nine_fixed_rows_and_no_endpoint_selection(monkeypatch, tmp_path, fail_after):
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
    monkeypatch.setenv("CELLDEV_WEIGHT_UPDATES_MONITOR_PID", str(m.os.getppid()))
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
            assert seeds == list(range(52_040_000, 52_040_512))
            if len(calls) == fail_after:
                raise ValueError("synthetic invalid life")
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
    if fail_after is not None:
        with pytest.raises(ValueError, match="synthetic invalid life"):
            m.run()
        report = json.loads((tmp_path / "measurement/report.json").read_text())
        assert report["status"] == "incomplete" and report["completed_genome_lives"] < 4608
        assert not (tmp_path / "measurement/contrasts.npz").exists()
        return
    result = m.run()
    assert result["status"] == "complete" and result["genome_lives"] == 4608
    assert result["completed_genome_lives"] == result["planned_genome_lives"] == 4608
    assert calls == [(flag, i) for flag in (12, 204, 16) for i in range(3)]
    assert result["structure_validation"]["complete_three_arm_lives_by_genotype"] == [512, 512, 512]
    assert len(result["contrasts"]) == 16
    for value in result["contrasts"].values():
        assert value["mean"] == value["se"] == 0 and value["n"] == 512
        assert not value["positive_above_3se"] and not value["negative_below_minus_3se"]
    saved = json.loads((tmp_path / "measurement/manifest.json").read_text())
    assert saved["labels"] == list(m.LABELS) and saved["seed_block"] == 104
    for key in m.CONDITIONS:
        with np.load(tmp_path / "measurement" / key / "scores.npz") as values:
            assert set(COLS).issubset(values.files) and values["F"].shape == (3, 512)
    saved_report = (tmp_path / "measurement/report.json").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        m.run()
    assert (tmp_path / "measurement/report.json").read_bytes() == saved_report


def test_direct_worker_without_monitor_is_rejected_before_numerical_goldens(monkeypatch):
    import sys
    from types import SimpleNamespace

    from src import checkpoint

    monkeypatch.delenv("CELLDEV_WEIGHT_UPDATES_MONITOR_PID", raising=False)
    monkeypatch.setitem(sys.modules, "run_budgeted", SimpleNamespace(check_ready=lambda: {"test": "ready"}))
    monkeypatch.setattr(checkpoint, "numerical_identity", lambda: pytest.fail("started golden lives"))
    with pytest.raises(RuntimeError, match="monitor parent"):
        m.run()


def test_added_contrasts_telescope_per_seed_with_covariance():
    rng = np.random.default_rng(42)
    data = {key: rng.normal(size=(3, 9)) for key in m.CONDITIONS}
    result = m.contrasts(data)
    for label in m.LABELS[1:]:
        np.testing.assert_allclose(result[label + "__added_S_minus_C"] + result[label + "__added_C_minus_F"],
                                   result[label + "__gain__S"] - result[label + "__gain__F"], atol=1e-14)


def test_each_own_contrast_and_endpoint_gain_orientation():
    seed = np.arange(4.)
    data = {key: np.stack([seed + offset + 10 * i for i in range(3)])
            for key, offset in (("S", 8), ("C", 3), ("F", -1))}
    result = m.contrasts(data)
    for i, label in enumerate(m.LABELS):
        np.testing.assert_array_equal(result[label + "__C_minus_F"], np.full(4, 4.))
        np.testing.assert_array_equal(result[label + "__S_minus_C"], np.full(4, 5.))
        if i:
            for key in m.CONDITIONS:
                np.testing.assert_array_equal(result[label + "__gain__" + key], np.full(4, 10. * i))
            np.testing.assert_array_equal(result[label + "__added_C_minus_F"], np.zeros(4))
            np.testing.assert_array_equal(result[label + "__added_S_minus_C"], np.zeros(4))


def test_S_is_also_checked_for_structural_change():
    data = rows()
    data["S"][1]["births"][0] = 1
    with pytest.raises(ValueError, match="changed during"):
        m.validate_structure(data)


def test_source_proof_and_independent_review_are_pinned():
    import json

    protocol = m.check_protocol()
    names = ("COMBINED_CLAMP_SOURCE_AUDIT.md", "source_proof.json", "independent_review.json")
    for name in names:
        relative = "semantic_proof/" + name
        assert m.sha(HERE / relative) == protocol["preparation_pins"][relative]
    proof = json.loads((HERE / "semantic_proof/source_proof.json").read_text())
    review = json.loads((HERE / "semantic_proof/independent_review.json").read_text())
    assert proof["proof_sha256"] == m.sha(HERE / "semantic_proof/COMBINED_CLAMP_SOURCE_AUDIT.md")
    assert review["status"] == "passed" and review["simulated_lives"] == 0
    assert review["source_proof_sha256"] == m.sha(HERE / "semantic_proof/source_proof.json")
