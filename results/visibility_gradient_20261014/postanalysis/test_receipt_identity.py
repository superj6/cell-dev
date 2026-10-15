"""Regression against the actual terminal monitor receipt schema; no outcomes or simulations."""
import copy
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent if (HERE.parent / "protocol.json").is_file() else HERE.parents[1] / "autonomous_visibility_gradient_20261014"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = load(HERE / "analyze.py", "corrected_gradient_analysis")
OLD = load(STUDY / "analysis/analyze.py", "original_gradient_analysis")


def actual():
    failure = M.read(HERE / "original_failure.json")
    for name, digest in failure["fixture_pins"].items():
        assert M.sha(HERE / "fixtures" / name) == digest
    return M.read(HERE / "fixtures/attempt.json"), M.read(HERE / "fixtures/budget.json")


def test_actual_monitor_has_exactly_four_identity_fields():
    attempt, budget = actual()
    assert set(attempt["monitor"]) == {"pid", "ppid", "pgid", "start_ticks"}
    assert M.identity(attempt["monitor"]) == attempt["monitor"]
    with pytest.raises(ValueError, match="incomplete process identity"):
        OLD.identity(attempt["monitor"])
    assert M.identity(budget["process_identities"][0]) == attempt["monitor"]


def test_actual_complete_resources_keep_all_other_release_and_budget_checks():
    protocol, _ = M.verify_protocol(STUDY)
    budget, resource = M.resources(STUDY, protocol)
    assert budget == actual()[1]
    assert resource["total_cpu_seconds"] == 1768.464936
    assert resource["startup_screen_cpu_seconds"] == 1240.066735


@pytest.mark.parametrize("key,value", [("ppid", 1), ("pgid", 1), ("start_ticks", 0)])
def test_worker_ownership_and_start_identity_remain_required(monkeypatch, key, value):
    protocol, _ = M.verify_protocol(STUDY)
    read = M.read
    changed = copy.deepcopy(actual()[1])
    changed["process_identities"][1][key] = value

    def replacement(path):
        return changed if Path(path) == M.operation(STUDY, "budget.json") else read(path)

    monkeypatch.setattr(M, "read", replacement)
    with pytest.raises(ValueError, match="process identity|owned process group"):
        M.resources(STUDY, protocol)
