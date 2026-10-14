"""Independent synthetic J workflow check; no G outcomes or life simulation."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
J = ROOT / "outputs/autonomous_duplicate_use_20261014"
spec = importlib.util.spec_from_file_location("j_review_fixtures", J / "test_measure.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
m = fixture.m


@pytest.mark.parametrize("empty_first", [True, False])
def test_single_branch_keeps_negative_choice_and_correct_confirmation_mapping(monkeypatch, tmp_path, empty_first):
    from scripts import taskvar_second_step
    from scripts.taskvar_confirm import COLS
    from src import checkpoint
    from src.life import build

    protocol = m.check_protocol()
    layout, records = fixture.endpoints((0, 2) if empty_first else (2, 0))
    selected_seed, empty_seed = ("51090", "51089") if empty_first else ("51089", "51090")
    shutil.copytree(J / "inputs", tmp_path / "inputs")
    shutil.copy2(J / "protocol.json", tmp_path / "protocol.json")
    monkeypatch.setattr(m, "STUDY", tmp_path)
    monkeypatch.setattr(m, "check_protocol", lambda: protocol)
    monkeypatch.setattr(m, "load_endpoints", lambda p: (layout, records))
    monkeypatch.setitem(sys.modules, "run_budgeted", SimpleNamespace(check_ready=lambda: {"test": "ready"}))
    monkeypatch.setattr(checkpoint, "numerical_identity", lambda: protocol["numerical_identity"])
    monkeypatch.setattr(build, "run", lambda *a, **kw: pytest.fail("simulated a life"))
    calls = []

    class Store:
        def __init__(self, out, genomes, world, evaluator, threads, cap):
            self.cpu_seconds, self.stage = 0, out.name
            out.mkdir(parents=True, exist_ok=True)
            assert len(genomes) == (3 if self.stage == "screen" else 2)
            assert threads == 2 and cap == 7200

        def row(self, stage, i, seeds):
            assert seeds == m.seeds(self.stage)
            if self.stage == "screen":
                assert (tmp_path / "measurement/genotypes.npz").exists()
            else:
                assert (tmp_path / "measurement/selection.json").exists()
            calls.append((self.stage, i))
            self.cpu_seconds += 1
            fitness = [0, 1, 2][i] if self.stage == "screen" else [0, 3][i]
            row = {key: np.zeros(512) for key in COLS}
            row.update(cpu_seconds=np.asarray(1.), wall_seconds=np.asarray(1.))
            for key, value in {"F": fitness, "F_kernel": fitness, "cost": 10000,
                               "income": fitness * 1024 + 10000, "live_time": 102400, "n_end": 100,
                               "n_S_end": 30, "n_M_end": 40, "n_H_end": 30, "t_end": 1024,
                               "window": 1024, "last_birth": 100}.items():
                row[key][:] = value
            return row

    monkeypatch.setattr(taskvar_second_step, "RowStore", Store)
    result = m.run()
    assert result["status"] == "complete"
    assert result["research_genome_lives"] == 2560
    assert calls == [("screen", 0), ("screen", 1), ("screen", 2), ("confirm", 0), ("confirm", 1)]
    assert result["confirmation"][selected_seed]["loss"]["F"]["mean"] == -3
    assert empty_seed not in result["confirmation"]
    selected = json.loads((tmp_path / "measurement/selection.json").read_text())
    assert selected["screen_rows"] == [0, 1]
    assert selected["confirm_pairs"] == {selected_seed: [0, 1]}
    assert selected["selection"][selected_seed]["slot"] == 8
    assert selected["selection"][selected_seed]["screen_mean_loss"] == -1
    assert selected["selection"][empty_seed]["status"] == "not_applicable_no_active_duplicate_origin"
