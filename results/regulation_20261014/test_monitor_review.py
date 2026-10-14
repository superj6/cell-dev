"""Independent O completion-contract checks; fake process only, no scientific life."""
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location("o_existing_mock_fixture", HERE / "test_monitor.py")
P = importlib.util.module_from_spec(loader)
loader.loader.exec_module(P)
m = P.m


@pytest.mark.parametrize("count", [None, 4607, 4609, 2048])
def test_only_actual_complete_4608_report_can_succeed(m, monkeypatch, count):
    def spawn(*args, **kwargs):
        report = {"status": "complete"}
        if count is not None:
            report["genome_lives"] = count
        m.save(m.STUDY / "measurement/report.json", report)
        return P.Process()

    monkeypatch.setattr(m.subprocess, "Popen", spawn)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 1
    record = json.loads((m.STUDY / "budget.json").read_text())
    assert record["status"] == "incomplete" and record["cap_cpu_seconds"] == 3600
    assert not record["running"] and not record["queued"]
