"""Independent fixed-budget validation orchestration checks; all scientific calls are fake."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

SOURCE = Path(__file__).resolve().parents[1] / "autonomous_visibility_information_20261014/validate.py"


class Function:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    common = ModuleType("common")
    common.ROOT = tmp_path
    common.STUDY = tmp_path / "study"
    common.STUDY.mkdir()
    common.sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def save(path, value):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(value) + "\n")

    common.save = save
    common.parent_check = lambda parent, **kwargs: None if parent == 123 else pytest.fail("wrong parent")
    value = {"validation_seeds": [52_160_000, 52_160_001], "file_pins": {"frozen": "pin"},
             "production_pins": {"production": "pin"}, "worlds": {}}
    for world in ("flash5_dim25", "blink20"):
        value["worlds"][world] = {"name": world, "base_world": {"flags": 0},
                                  "candidates": [{"role": role} for role in ("R0", "R1", "I", "A", "B")]}
    common.protocol = lambda: value
    common.require_release = lambda: value
    save(common.STUDY / "protocol.json", value)
    monkeypatch.setitem(sys.modules, "common", common)
    spec = importlib.util.spec_from_file_location("independent_validation_orchestration", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = {"scratch": [], "production": [], "compile": [], "log": np.empty((0, 6)),
             "wrong_callbacks": False, "wrong_actions": False, "wrong_bridge": False, "truth_calls": 0}

    def compile_fake(protocol):
        assert protocol is value
        result = {}
        for key in ("full", "fast", "replay", "production"):
            target = common.STUDY / "validation/build" / (key + ".so")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"FAKE: never loaded or compiled")
            state["compile"].append(key)
            result[key] = {"path": str(target.relative_to(common.STUDY)), "sha256": common.sha(target)}
        return result

    monkeypatch.setattr(module, "compile_libraries", compile_fake)

    def arrays(seeds, production=False):
        n = len(seeds)
        ledger = np.zeros((n, 58 if production else 57))
        ledger[:, 0] = [seed % 37 for seed in seeds]
        hashes = np.zeros((n, 5), dtype=np.uint64)
        return {"ledger": ledger, "hashes": hashes, "diag": np.zeros((n, 16)), "latency": np.ones(n)}

    def run(candidate, world, seeds, library, library_sha, *, duration=None, override=None, cid=None, extra=None):
        state["scratch"].append({"role": candidate["role"], "world": world["name"], "seeds": list(seeds),
            "library": Path(library).stem, "T": duration, "cid": cid, "override": override})
        if cid in (1901, 1902):
            if cid == 1901:
                time = 1.0 + seeds[0] % 10
                callbacks = np.array([[0, time, 2], [4, time + 0.5, 0]], dtype=np.float64)
            else:
                callbacks = np.asarray(extra[1:], dtype=np.float64).reshape(-1, 3).copy()
            actions = np.array([[1, callbacks[0, 1], 3, 1, callbacks[0, 1], 0]], dtype=np.float64)
            if cid == 1902 and state["wrong_callbacks"]:
                callbacks[0, 2] += 1
            if cid == 1902 and state["wrong_actions"]:
                actions[0, 2] += 1
            callback_rows = np.zeros((len(callbacks), 6))
            callback_rows[:, :3] = callbacks
            state["log"] = np.ascontiguousarray(np.concatenate([callback_rows, actions]))
        return arrays(seeds)

    raw = ModuleType("raw")
    raw.run = run
    monkeypatch.setitem(sys.modules, "raw", raw)
    frozen = ModuleType("frozen")
    frozen.load_harness = lambda: SimpleNamespace(V3=SimpleNamespace(flags=lambda name: 32))

    def copy_log(pointer):
        destination = np.ctypeslib.as_array(pointer, shape=(state["log"].size,))
        destination[:] = state["log"].reshape(-1)

    library = SimpleNamespace(e7_log_size=Function(lambda: state["log"].size),
                              e7_log_copy=Function(copy_log), x_truth_count=Function(lambda: state["truth_calls"]))
    frozen.checked_library = lambda path, digest: library
    monkeypatch.setitem(sys.modules, "frozen", frozen)

    def subprocess_fake(command, **kwargs):
        assert "production_run.py" in command[1]

        def get(key):
            return command[command.index("--" + key) + 1]

        world, role, seed = get("world"), get("role"), int(get("seed"))
        state["production"].append({"world": world, "role": role, "seed": seed, "T": 128})
        output = arrays([seed], production=True)
        if state["wrong_bridge"]:
            output["ledger"][0, 0] += 1
        np.savez_compressed(get("out"), **output)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", subprocess_fake)
    return module, common, state


def test_exact_82_calls_and_fixed_replay_package(prepared):
    module, common, state = prepared
    module.validate(123)
    report = json.loads((common.STUDY / "validation/report.json").read_text())
    assert report["status"] == "complete" and report["simulation_calls"] == 82
    assert state["compile"] == ["full", "fast", "replay", "production"]
    assert len(state["production"]) == 8
    assert sum(len(row["seeds"]) for row in state["scratch"]) == 74
    assert sum(len(row["seeds"]) for row in state["scratch"] if row["T"] == 1024) == 12
    assert len([row for row in state["scratch"] if row["cid"] == 1901]) == 12
    assert len([row for row in state["scratch"] if row["cid"] == 1902]) == 18
    assert len(report["checks"]) == 8 + 6 + 6
    assert {row["check"] for row in report["checks"]} == {"production_bridge", "full_fast", "C5_replay"}
    assert sum(row["simulation_calls"] for row in report["artifacts"].values()) == 82
    assert report["no_retuning"] is True and report["no_research_outcomes"] is True


@pytest.mark.parametrize("fault", ["wrong_callbacks", "wrong_actions", "wrong_bridge"])
def test_validation_mismatch_leaves_no_complete_report(prepared, fault):
    module, common, state = prepared
    state[fault] = True
    with pytest.raises(ValueError, match="mismatch|bridge|callback"):
        module.validate(123)
    assert not (common.STUDY / "validation/report.json").exists()
    assert sum(len(row["seeds"]) for row in state["scratch"]) + len(state["production"]) < 82


def test_truth_access_is_fatal_without_more_scoring(prepared):
    module, common, state = prepared
    state["truth_calls"] = 1
    with pytest.raises(ValueError, match="privileged"):
        module.validate(123)
    assert not (common.STUDY / "validation/report.json").exists()
    assert sum(len(row["seeds"]) for row in state["scratch"]) + len(state["production"]) == 41


def test_attempt_is_never_repeated(prepared):
    module, common, state = prepared
    (common.STUDY / "validation").mkdir()
    with pytest.raises(ValueError, match="first attempt"):
        module.validate(123)
    assert not state["compile"] and not state["scratch"] and not state["production"]
