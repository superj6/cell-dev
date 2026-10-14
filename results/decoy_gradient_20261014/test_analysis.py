"""Pure synthetic tests for all-panel selection and independent decoy accounting; no organism lives."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


def module():
    spec = importlib.util.spec_from_file_location("decoy_independent", Path(__file__).with_name("analyze.py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def world():
    return json.loads((Path(__file__).parent / "inputs/F_protocol.json").read_text())["world"]


def synthetic(run, w, status=(0, 0, 0, 0), captures=(5, 6, 7, 8), poison=(1, 2, 3, 4),
              misses=(4, 3, 2, 1)):
    a = run.A
    n = len(status)
    window = w["T"] - w["t_open"]
    row = {key: np.zeros(n, dtype=np.float64) for key in a.COLS}
    row.update(cpu_seconds=np.asarray(1.25), wall_seconds=np.asarray(1.0))
    for name, value in dict(status=status, t_end=w["T"], captures=captures, b2_clicks=poison, n_end=100,
                            n_S_end=30, n_M_end=40, n_H_end=30, live_time=100 * window,
                            window=window, misses=misses, spikes=500).items():
        row[name][:] = value
    flags = np.asarray(status, dtype=np.int64)
    row["t_end"][flags & 7 != 0] = w["T"] - 100
    row["t_ext"][flags & 1 != 0] = w["T"] - 100
    row["cost"] = sum(price * row[column] for _, column, price in a.prices(w))
    row["income"] = w["R_cap"] * row["captures"]
    row["guard_charge"] = np.where(flags & 6 != 0, w["c_live"] * w["n_max"] * (w["T"] - row["t_end"]), 0)
    row["net"] = row["income"] - row["cost"] - row["guard_charge"]
    row["F_kernel"] = row["net"] / window
    row["extinct_charge"] = w["c_live"] * np.where(flags & 1 != 0,
        w["T"] - np.maximum(row["t_ext"], w["t_open"]), 0) / window
    row["F"] = row["F_kernel"] - row["extinct_charge"]
    row["ledger"] = np.stack([row["F_kernel" if name == "F" else name] for name in a.LEDGER], axis=1)
    return row


def test_all_negative_screen_keeps_four_original_mutants_and_excludes_parent():
    run = module()
    panel = -np.arange(65, dtype=float)[:, None] * np.ones((1, 32))
    assert run.shortlist(panel) == [1, 2, 3, 4]
    panel[0] = 10000
    panel[64] = 20000
    assert run.shortlist(panel) == [64, 1, 2, 3]


def test_screen_ties_break_by_original_index_and_keep_all_rows():
    run = module()
    panel = np.zeros((65, 32))
    panel[[51, 4, 30, 8, 22]] = 1
    assert run.shortlist(panel) == [4, 8, 22, 30]


@pytest.mark.parametrize("value", [np.zeros((64, 32)), np.zeros((65, 31)), np.full((65, 32), np.nan)])
def test_partial_or_nonfinite_screen_is_rejected(value):
    with pytest.raises(ValueError, match="all 65 fixed rows"):
        module().shortlist(value)


def test_winner_ties_use_original_rows_and_all_negative_winner_is_retained():
    run = module()
    values = np.full((5, 512), -1.0)
    values[0] = 1000
    indices = [0, 51, 30, 8, 22]
    assert run.winner(values, indices) == 8
    values[1] = -.5
    assert run.winner(values, indices) == 51


@pytest.mark.parametrize("indices", [[0, 1, 2, 2, 3], [1, 2, 3, 4, 5], [0, 1, 2, 3]])
def test_invalid_rescore_row_identity_is_rejected(indices):
    with pytest.raises(ValueError, match="four distinct mutants"):
        module().winner(np.zeros((5, 512)), indices)


@pytest.mark.parametrize("values", [np.zeros((5, 32)), np.full((5, 512), np.inf)])
def test_incomplete_or_nonfinite_rescore_is_rejected(values):
    with pytest.raises(ValueError, match="five finite rows"):
        module().winner(values, [0, 1, 2, 3, 4])


def test_both_signed_three_se_directions_and_boundary_are_descriptive():
    run = module()
    assert run.primary({"mean": -1., "se": .1, "n": 512})["direction_above_3se"] == "negative"
    assert run.primary({"mean": .5, "se": 0., "n": 512})["at_least_0p5"]
    zero = run.primary({"mean": 0., "se": 0., "n": 512})
    assert zero["direction_above_3se"] == "unresolved" and not zero["above_3se"]


def test_complete_capture_poison_miss_guard_and_extinction_decomposition_keeps_covariance():
    run = module()
    w = world()
    parent = synthetic(run, w, status=(0, 4, 1, 0))
    selected = synthetic(run, w, captures=(6, 7, 8, 9), poison=(0, 1, 2, 3), misses=(2, 1, 0, 0))
    assert run.A.validate_row(parent, w, n=4) == {"guarded": 1, "extinct": 1, "valid_other_status": 0}
    run.A.validate_row(selected, w, n=4)
    data = {key: np.stack([parent[key], selected[key]]) for key in run.A.COLS}
    report, pieces = run.compare(data, 1, w)
    assert report["guard_fraction"] == {"parent": .25, "winner": 0}
    assert np.allclose(sum(value for name, value in pieces.items() if name != "residual"),
                       selected["F"] - parent["F"], atol=1e-12)
    assert pieces["guard_charge_saving"][1] > 0 and pieces["extinction_charge_saving"][2] > 0
    assert np.all(pieces["capture_income"] > 0) and np.all(pieces["poison_cost_saving"] > 0)
    assert report["F"] == run.A.stats(selected["F"] - parent["F"])
    run.check_comparison(report, report, "synthetic")
    # Shared large nuisance cancels in a paired SE, instead of inflating an independent-samples estimate.
    common = np.asarray([1e6, -1e6, 2e6, -2e6])
    assert run.A.stats((common + 2) - common) == {"mean": 2., "se": 0., "n": 4}


@pytest.mark.parametrize("field", ["F", "ledger", "cost", "net", "window"])
def test_corrupted_raw_scoring_cannot_become_fitness_evidence(field):
    run = module()
    w = world()
    row = synthetic(run, w)
    if field == "ledger":
        row[field][0, run.A.L["path"]] += 1
    else:
        row[field][0] += 1
    with pytest.raises(ValueError):
        run.A.validate_row(row, w, n=4)


def test_incomplete_study_cannot_report_selected_winner(tmp_path):
    run = module()
    assert run.analyze(tmp_path) == ({"status": "incomplete", "budget_status": "not_started"}, {})
    (tmp_path / "budget.json").write_text('{"status":"resource_limit"}')
    assert run.analyze(tmp_path) == ({"status": "incomplete", "budget_status": "resource_limit"}, {})


def test_saved_input_binding_checks_frozen_preparation_without_running_measurement(monkeypatch):
    run = module()
    base = Path(__file__).resolve().parent
    read = run.A.read
    protocol = read(base / "protocol.json")
    manifest = {"protocol_sha256": run.A.sha(base / "protocol.json"),
                "runner_sha256": run.A.sha(run.operation(base, "measure.py")),
                "world": protocol["world"], "seeds": protocol["seeds"], "seed_blocks": run.BLOCKS,
                "numerical_identity": protocol["expected_numerical_identity"],
                "helpers": protocol["helpers"], "input_sha256": protocol["input_sha256"],
                "genomes_sha256": {parent: run.raw_sha(np.load(base / "inputs" / parent / "genomes.npy"))
                                   for parent in run.PARENTS}}
    monkeypatch.setattr(run.A, "read", lambda path: manifest if Path(path) == base / "measurement/manifest.json"
                        else read(path))
    checked, panels = run.audit_inputs(base)
    assert checked == protocol
    assert set(panels) == {"s5", "s7"} and all(len(panel) == 65 for panel in panels.values())


@pytest.mark.parametrize("cpu", [3600, float("nan"), float("inf")])
def test_claimed_completion_outside_finite_budget_is_rejected(tmp_path, cpu):
    run = module()
    (tmp_path / "budget.json").write_text(json.dumps({"status": "complete", "exit_code": 0,
        "cpu_seconds": cpu, "running": [], "queued": []}))
    with pytest.raises(ValueError, match="fixed CPU budget"):
        run.analyze(tmp_path)


def test_stopped_partial_audit_keeps_every_saved_life_without_inference(tmp_path, monkeypatch):
    run = module()
    protocol = run.A.read(Path(__file__).parent / "protocol.json")
    monkeypatch.setattr(run, "audit_inputs", lambda base: (protocol, {}))
    budget = {"status": "incomplete", "cpu_seconds": 3590., "cap_cpu_seconds": 3600,
              "running": {}, "queued": [], "exit_code": -15}
    run.A.save(tmp_path / "budget.json", budget)
    row = synthetic(run, protocol["world"])
    row = {key: np.tile(value, (8, 1)) if key == "ledger" else
           (np.tile(value, 8) if value.shape == (4,) else value) for key, value in row.items()}
    row.update(genome_index=np.asarray(0), seeds=np.asarray(protocol["seeds"]["screen"], dtype=np.uint64))
    folder = tmp_path / "measurement/s5"
    (folder / "screen").mkdir(parents=True)
    path = folder / "screen/row_0000.npz"
    np.savez_compressed(path, **row)
    run.A.save(folder / "row_index.json", {"screen/row_0000.npz": {
        "sha256": run.A.sha(path), "cpu_seconds": float(row["cpu_seconds"])}})
    summary = run.audit_stopped(tmp_path)
    assert summary["status"] == "incomplete" and summary["saved_research_lives"] == 32
    assert summary["saved_rows"]["s5"] == {"screen": 1, "rescore": 0, "confirm": 0}
    assert not summary["primary_confirmation_inference_allowed"]
    assert "no completed confirmation inference" in run.stopped_markdown(summary)
    # A stop after atomic row writing but before receipt writing must retain that row explicitly.
    row["genome_index"] = np.asarray(1)
    np.savez_compressed(folder / "screen/row_0001.npz", **row)
    summary = run.audit_stopped(tmp_path)
    assert summary["saved_research_lives"] == 64
    assert summary["unindexed_saved_rows"]["s5"] == ["screen/row_0001.npz"]
    run.A.save(folder / "row_index.json", {"screen/row_0000.npz": {
        "sha256": "changed", "cpu_seconds": float(row["cpu_seconds"])}})
    with pytest.raises(ValueError, match="stopped raw row receipt"):
        run.audit_stopped(tmp_path)


@pytest.mark.parametrize("status,running", [("running", {}), ("waiting_for_workers", {}),
                                           ("incomplete", {"123": "still running"})])
def test_running_or_queued_study_cannot_use_partial_export(tmp_path, status, running):
    run = module()
    run.A.save(tmp_path / "budget.json", {"status": status, "running": running, "queued": []})
    with pytest.raises(ValueError, match="terminal stopped monitor"):
        run.audit_stopped(tmp_path)
