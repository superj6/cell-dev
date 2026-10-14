"""Synthetic validation-harness failures and the complete bounded 40-life workflow."""
import ctypes
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent


def load(name, path):
    loader = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module


P = load("N_validation_mock_helpers", HERE / "test_prepared.py")
M = P.M
previous = sys.modules.get("measure")
sys.modules["measure"] = M
try:
    V = load("N_validation_review", HERE / "validate.py")
finally:
    if previous is None:
        del sys.modules["measure"]
    else:
        sys.modules["measure"] = previous


class Callable:
    def __init__(self, action):
        self.action = action

    def __call__(self, *args):
        return self.action(*args)


@pytest.fixture
def harness(monkeypatch):
    state = {"log": np.empty(0), "calls": [], "fault": None}

    def retrieve(pointer, capacity):
        if state["fault"] == "empty_log":
            return 0
        if state["fault"] == "oversized_log":
            return capacity + 6
        if state["fault"] == "partial_log":
            return 1
        data = np.ctypeslib.as_array(ctypes.cast(pointer, ctypes.POINTER(ctypes.c_double)), shape=(capacity,))
        data[:len(state["log"])] = state["log"]
        return len(state["log"])

    class Library:
        v4h_log_enable = Callable(lambda enabled: None)
        v4h_log_get = Callable(retrieve)

    def compile_library(path, source, fast):
        assert not fast and source.name == "vctl.c"
        path.write_bytes(b"mock library")
        path.with_suffix(".c").write_text("mock source")
        return M.H

    def controller(cid, params, footprint, world, seeds, extra=None, **kwargs):
        assert kwargs["threads"] == 1 and kwargs["fast"] is False
        state["calls"].append(("controller", cid, len(seeds), world.over["T"]))
        result = P.fake_lives(M.spec.world(world.preset, **world.over), seeds, controller=True)
        if cid == M.H.NULL:
            if state["fault"] == "null_world":
                result.hashes[0, 4] = 1
            return result
        assert cid in (5, 1005, 1006)
        marker = seeds[0] % 100
        if cid == 1006:
            assert extra is not None
            marker = extra[2]
        elif state["fault"] == "insensitive_control":
            marker = 0
        action = [1., 2., marker, .5, 3., 3.5]
        if cid == 1006 and state["fault"] == "replay_action":
            action[3] += .1
        log = [action]
        if cid != 1006:
            result.diag[0, 0] = 1
            log.insert(0, [0., 1., marker, 0., 0., 0.])
        if cid == 1006 and state["fault"] == "real_ping":
            result.diag[0, 0] = 1
        if cid == 1005 and state["fault"] == "builtin_copy":
            result.hashes[0, 1] = 1
        state["log"] = np.asarray(log, dtype=np.float64).reshape(-1)
        return result

    def tissue(body, world, seeds, **kwargs):
        assert kwargs["threads"] == 1 and kwargs["fast"] is False
        state["calls"].append(("tissue", None, len(seeds), world.over["T"]))
        return P.fake_lives(M.spec.world(world.preset, **world.over), seeds)

    def production(world, seeds, **kwargs):
        assert kwargs["threads"] == 1 and kwargs["abi"] is M.spec.V3
        state["calls"].append(("production", None, len(seeds), world.T))
        result = P.fake_lives(world, seeds)
        if state["fault"] == "production_world":
            result.hashes[0, 1] = 1
        return result

    monkeypatch.setattr(V, "compile_measurement", compile_library)
    monkeypatch.setattr(M.H, "load", lambda *args, **kwargs: Library())
    monkeypatch.setattr(M.H, "ctl_run", controller)
    monkeypatch.setattr(M.H, "tissue_run", tissue)
    monkeypatch.setattr(V.build, "run", production)
    return state


def test_bounded_validation_full_mock(tmp_path, harness):
    out = tmp_path / "validation"
    result = V.run_validation(M.read(HERE / "protocol.json"), out)
    assert result["passed"] and result["candidate_lives"] == 40
    assert sum(item[2] for item in harness["calls"]) == 40
    assert all(item[3] == 64 for item in harness["calls"])
    assert len(result["records"]) == len(list(out.glob("*.npz"))) == 32
    for check in result["checks"].values():
        assert check["reflex_production_parity"] and check["null_inert_world_parity"]
        assert all(row["copy_bitwise"] and all(row["replay"].values()) for row in check["controller_replay"])
    with pytest.raises(ValueError, match="already exists"):
        V.run_validation(M.read(HERE / "protocol.json"), out)


@pytest.mark.parametrize("fault,message", [
    ("builtin_copy", "builtin C4"),
    ("replay_action", "retained ping stream"),
    ("real_ping", "retained ping stream"),
    ("insensitive_control", "replay sensitivity"),
    ("production_world", "production ABI3"),
    ("null_world", "world stream"),
    ("empty_log", "log is empty"),
    ("oversized_log", "log is empty"),
    ("partial_log", "log is empty"),
])
def test_validation_failures_are_retained_and_never_pass(tmp_path, harness, fault, message):
    harness["fault"] = fault
    out = tmp_path / "validation"
    with pytest.raises(ValueError, match=message):
        V.run_validation(M.read(HERE / "protocol.json"), out)
    assert not (out / "report.json").exists()
    assert out.is_dir()


def test_modified_validation_plan_is_rejected(tmp_path, harness):
    protocol = M.read(HERE / "protocol.json")
    protocol["validation"]["seeds"][0] += 1
    with pytest.raises(ValueError, match="fixed bounded validation"):
        V.run_validation(protocol, tmp_path / "validation")
    assert not harness["calls"]
