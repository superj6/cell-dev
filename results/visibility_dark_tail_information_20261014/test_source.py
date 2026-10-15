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

SOURCE = Path(__file__).resolve().parent / "validate.py"
sys.path.insert(0, str(SOURCE.parent))
from contracts import ROLES, SCOPE, VALIDATION_MATRIX, calibration_projection, transfer_candidates  # noqa: E402


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
    common.read = lambda path: json.loads(Path(path).read_text())
    common.parent_check = lambda parent, **kwargs: None if parent == 123 else pytest.fail("wrong parent")
    value = {"validation_seeds": [101, 102, 103], "file_pins": {"frozen": "pin"},
             "production_pins": {"production": "pin"}, "worlds": {},
             "expected_numerical_identity": {"test": "synthetic"},
             "historical_cpu_per_life": {r: .01 for r in ROLES}}
    for world in ("flash5_dark",):
        value["worlds"][world] = {"name": world, "base_world": {"flags": 0},
                                  "candidates": [{"role": role} for role in ROLES]}
    common.protocol = lambda: value
    common.require_release = lambda: value
    save(common.STUDY / "protocol.json", value)
    monkeypatch.setitem(sys.modules, "common", common)
    spec = importlib.util.spec_from_file_location("independent_validation_orchestration", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = {"scratch": [], "production": [], "compile": [], "log": np.empty((0, 6)),
             "wrong_callbacks": False, "wrong_actions": False, "wrong_bridge": False, "truth_calls": 0, "identity_calls": 0, "wrong_identity": False, "calibration_too_slow": False}

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
        assert kwargs == {"check": True}  # No new session/group: descendants remain monitor-owned.
        if "production_identity.py" in command[1]:
            state["identity_calls"] += 1
            common.save(common.STUDY / "validation/startup_identity.json", {
                "status": "complete", "simulation_calls": 2,
                "numerical_identity_invocations": 1,
                "identity": {} if state["wrong_identity"] else value["expected_numerical_identity"]})
            return SimpleNamespace(returncode=0)
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
    original_projection = module.calibration_projection
    def projection(cpus, historical):
        if state["calibration_too_slow"]:
            cpus = {role: 100. for role in ROLES}
        return original_projection(cpus, historical)
    monkeypatch.setattr(module, "calibration_projection", projection)
    return module, common, state


def test_exact_76_calls_and_fixed_replay_package(prepared):
    module, common, state = prepared
    module.validate(123)
    report = json.loads((common.STUDY / "validation/report.json").read_text())
    assert report["status"] == "complete" and report["simulation_calls"] == 76
    assert state["compile"] == ["full", "fast", "replay", "production"]
    assert len(state["production"]) == 4
    assert sum(len(row["seeds"]) for row in state["scratch"]) == 70
    assert sum(len(row["seeds"]) for row in state["scratch"] if row["T"] == 1024) == 39
    assert len([row for row in state["scratch"] if row["cid"] == 1901]) == 6
    assert len([row for row in state["scratch"] if row["cid"] == 1902]) == 9
    assert len(report["checks"]) == 4 + 3 + 3
    assert {row["check"] for row in report["checks"]} == {"production_bridge", "full_fast", "C5_replay"}
    assert sum(row["simulation_calls"] for row in report["artifacts"].values()) == 76
    assert state["identity_calls"] == 1
    assert report["validation_matrix"] == VALIDATION_MATRIX
    assert set(report["calibration_cpu_seconds"]) == set(ROLES)
    assert report["calibration_projection"]["feasible"]
    assert all(row["seeds"] == [101,102,103] for row in state["scratch"] if row["T"] == 1024)
    assert report["no_retuning"] is True and report["no_research_outcomes"] is True


@pytest.mark.parametrize("fault", ["wrong_callbacks", "wrong_actions", "wrong_bridge"])
def test_validation_mismatch_leaves_no_complete_report(prepared, fault):
    module, common, state = prepared
    state[fault] = True
    with pytest.raises(ValueError, match="mismatch|bridge|callback"):
        module.validate(123)
    assert not (common.STUDY / "validation/report.json").exists()
    assert sum(len(row["seeds"]) for row in state["scratch"]) + len(state["production"]) < 76


def test_truth_access_is_fatal_without_more_scoring(prepared):
    module, common, state = prepared
    state["truth_calls"] = 1
    with pytest.raises(ValueError, match="privileged"):
        module.validate(123)
    assert not (common.STUDY / "validation/report.json").exists()
    assert sum(len(row["seeds"]) for row in state["scratch"]) + len(state["production"]) == 21


def test_attempt_is_never_repeated(prepared):
    module, common, state = prepared
    (common.STUDY / "validation").mkdir()
    with pytest.raises(ValueError, match="first attempt"):
        module.validate(123)
    assert not state["compile"] and not state["scratch"] and not state["production"]


def test_identity_failure_prevents_compile_or_science(prepared):
    module, common, state = prepared
    state["wrong_identity"] = True
    with pytest.raises(ValueError, match="identity"):
        module.validate(123)
    assert state["identity_calls"] == 1
    assert not state["compile"] and not state["scratch"] and not state["production"]
    assert not (common.STUDY / "validation/report.json").exists()


def test_failed_fixed_calibration_gate_never_releases_research(prepared):
    module, common, state = prepared
    state["calibration_too_slow"] = True
    with pytest.raises(ValueError, match="feasibility"):
        module.validate(123)
    assert not (common.STUDY / "validation/report.json").exists()
    assert not json.loads((common.STUDY / "validation/calibration_projection.json").read_text())["feasible"]


def test_exact_retained_parameter_mapping_only():
    old = json.loads((SOURCE.parents[2] / "results/visibility_information_x2_20261014/protocol.json").read_text())
    candidates = old["worlds"]["flash5_dim25"]["candidates"]
    new, proof = transfer_candidates(candidates)
    assert set(proof) == {"I", "B"}
    for a, b in zip(candidates, new):
        expected = json.loads(json.dumps(a))
        if a["role"] in ("I", "B"):
            expected["params"][21] = 0.
            assert [i for i,(x,y) in enumerate(zip(a["params"], b["params"])) if x != y] == [21]
        if a["role"] == "A":
            expected["changed_parameter_indices"] = [9,10]
        assert b == expected
    assert candidates[2]["params"][21] == .25


def test_calibration_keeps_historical_floor_and_all_roles():
    old = {role:.1 for role in ROLES}
    result = calibration_projection({role:.03 for role in ROLES},old)
    assert result["cpu_per_life"] == old
    assert result["projected_total_cpu_seconds"] == 180 + 1.5*512*sum(old.values())
    with pytest.raises(ValueError, match="all thirteen"):
        calibration_projection({role:.03 for role in ROLES[:-1]},old)
    assert not calibration_projection({role:100. for role in ROLES},old)["feasible"]


def test_source_caps_and_identity_count():
    import ast
    assert SCOPE["validation_lives"] == sum(VALIDATION_MATRIX.values()) == 76
    assert SCOPE["research_lives"] == 13*512 == 6656
    identity = ast.parse((SOURCE.parent / "production_identity.py").read_text())
    calls = [n for n in ast.walk(identity) if isinstance(n,ast.Call)
             and isinstance(n.func,ast.Name) and n.func.id=="numerical_identity"]
    assert len(calls)==1
    assert "numerical_identity()" not in (SOURCE.parent / "validate.py").read_text()
