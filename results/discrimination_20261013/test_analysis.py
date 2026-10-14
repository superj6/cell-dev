"""Independent F analyzer tests use synthetic ledgers and saved source text; never run lives."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


def module():
    path = Path(__file__).with_name("analyze.py")
    spec = importlib.util.spec_from_file_location("independent_discrimination", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def world(run):
    return json.loads((Path(__file__).parent / "protocol.json").read_text())["world"]


def row(run, w, captures=5, poison=1, misses=3):
    ledger = np.zeros((512, len(run.LEDGER)), dtype=np.float64)
    for key, value in dict(captures=captures, b2_clicks=poison, misses=misses,
                           clicks=captures + poison + misses, live_time=56 * w["T"], n_end=56,
                           t_end=w["T"], income=w["R_cap"] * captures).items():
        ledger[:, run.L[key]] = value
    ledger[:, run.L["cost"]] = run.costs(ledger, w)
    ledger[:, run.L["net"]] = ledger[:, run.L["income"]] - ledger[:, run.L["cost"]]
    ledger[:, run.L["F"]] = ledger[:, run.L["net"]] / w["T"]
    return {"ledger": ledger}


def test_documented_cost_accounting_reconstructs_fitness_bytes():
    run = module()
    w = world(run)
    values = row(run, w)["ledger"]
    expected_cost = 56 * w["T"] * 0.02 + 3 * 10 + 50
    assert np.all(run.validate_ledger(values, w) == expected_cost)
    assert np.all(values[:, run.L["F"]] == (5 * 500 - expected_cost) / 1024)


@pytest.mark.parametrize("column,delta,message", [
    ("status", 4, "guarded or invalid"), ("F", 0.01, "fitness differs"),
    ("cost", 1, "total cost differs"), ("income", 1, "capture income differs"),
    ("t_end", -1, "incomplete life"), ("status", 0.1, "status encoding")])
def test_invalid_single_life_rejects_whole_batch(column, delta, message):
    run = module()
    w = world(run)
    ledger = row(run, w)["ledger"]
    ledger[7, run.L[column]] += delta
    with pytest.raises(ValueError, match=message):
        run.validate_ledger(ledger, w)


def test_poison_miss_and_capture_pieces_reconcile_separately():
    run = module()
    w = world(run)
    full, reference = row(run, w, captures=6, poison=0, misses=2), row(run, w)
    report, arrays = run.contrast(full, reference, w)
    assert report["F"] == {"mean": 560 / 1024, "se": 0, "n": 512}
    assert report["fitness_pieces"]["capture_income"]["mean"] == 500 / 1024
    assert report["fitness_pieces"]["poison_cost_saving"]["mean"] == 50 / 1024
    assert report["fitness_pieces"]["miss_cost_saving"]["mean"] == 10 / 1024
    assert report["fitness_pieces"]["other_cost_saving"]["mean"] == 0
    assert np.all(sum(arrays.values()) == 560 / 1024)


def test_paired_standard_error_retains_covariance():
    run = module()
    left = np.asarray([100.0, -100.0, 50.0, -50.0])
    right = left - np.asarray([1.0, 2.0, 3.0, 4.0])
    actual = run.stats(left - right)
    assert actual["mean"] == 2.5
    assert np.isclose(actual["se"], np.sqrt(5 / 3) / 2)


def test_incomplete_does_not_analyze_or_import_simulator(tmp_path):
    run = module()
    assert run.analyze(tmp_path) == ({"status": "incomplete", "budget_status": "not_started"}, {})
    (tmp_path / "budget.json").write_text('{"status":"cpu_budget_exhausted"}')
    assert run.analyze(tmp_path)[0]["budget_status"] == "cpu_budget_exhausted"


def test_raw_identity_detects_sign_bit_and_dtype_changes():
    run = module()
    assert not run.identical(np.asarray([0.0]), np.asarray([-0.0]))
    assert not run.identical(np.asarray([1], dtype=np.int64), np.asarray([1.0]))
