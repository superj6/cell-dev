"""Pure fixed-input checks and mocked complete research workflow; no simulation."""
import importlib.util
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location("N_prepared_review", HERE / "measure.py")
M = importlib.util.module_from_spec(loader)
loader.loader.exec_module(M)


def fake_lives(world, seeds, cells=56, captures=5, controller=False):
    ledger = np.zeros((len(seeds), M.spec.V3.LEDGER_SIZE), dtype=np.float64)
    for key, value in {"t_end": world.T, "n_end": cells, "n_peak": cells,
                       "live_time": cells * world.T, "captures": captures, "clicks": captures}.items():
        ledger[:, M.spec.V3.L[key]] = value
    ledger[:, M.spec.V3.L["income"]] = world.R_cap * ledger[:, M.spec.V3.L["captures"]]
    ledger[:, M.spec.V3.L["cost"]] = world.c_live * ledger[:, M.spec.V3.L["live_time"]]
    ledger[:, M.spec.V3.L["net"]] = ledger[:, M.spec.V3.L["income"]] - ledger[:, M.spec.V3.L["cost"]]
    ledger[:, M.spec.V3.L["F"]] = ledger[:, M.spec.V3.L["net"]] / world.T
    value = M.build.Lives(ledger, np.zeros((len(seeds), 5), dtype=np.uint64), abi=M.spec.V3)
    if controller:
        value.diag = np.zeros((len(seeds), 16))
        value.latency = np.full(len(seeds), world.d0)
    return value


def test_fixed_worlds_inputs_and_minimum_sample_scope():
    p = M.check_protocol()
    assert p["candidate_lives"] == 6 * 2 * 2 * 512 == 12288
    assert p["validation_lives"] == 40 and p["wait_for_studies"] == [M.DEPENDENCY]
    assert p["duration_seed_blocks"] == {"768": 40, "1536": 41}
    for world, rows in p["candidates"].items():
        assert [r["name"] for r in rows] == ["full", "frozen", "retuned", "smaller_frozen",
                                              "smaller_transferred", "quieter"]
        assert rows[0]["controller_id"] == 5 and len(rows[0]["params"]) == 21
        assert rows[0]["params"] == M.H.bayes_params(world).tolist()
        assert rows[4]["knobs"] == rows[2]["knobs"]
        assert rows[5]["knobs"] == dict(rows[2]["knobs"], **{"K.t_ref": 8.})
        assert len(rows[1]["cells"]) == 56 and len(rows[3]["cells"]) == 32
        for settings in p["worlds"][world].values():
            assert (settings["d0"], settings["d_min"]) == (.5, .25)
    assert not set(p["seeds"]["768"]) & set(p["seeds"]["1536"])
    assert not set(p["validation"]["seeds"]) & set(p["seeds"]["768"])


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    for folder in ("inputs", "sources"):
        shutil.copytree(HERE / folder, tmp_path / folder)
    shutil.copyfile(HERE / "protocol.json", tmp_path / "protocol.json")
    monkeypatch.setattr(M, "STUDY", tmp_path)
    return tmp_path


def test_changed_seed_or_candidate_protocol_is_rejected(prepared):
    p = M.read(prepared / "protocol.json")
    p["seeds"]["768"][0] += 1
    M.save(prepared / "protocol.json", p)
    with pytest.raises(ValueError, match="prepared source"):
        M.check_protocol()


def test_worker_requires_registered_parent_before_any_output(prepared, monkeypatch):
    monkeypatch.setattr(M, "check_ready", lambda: {"synthetic": True})
    monkeypatch.delenv("CELLDEV_INFO_DURATION_MONITOR_PID", raising=False)
    with pytest.raises(ValueError, match="registered parent"):
        M.worker()
    assert not (prepared / "measurement").exists()


@pytest.mark.parametrize("invalid", [False, True])
def test_mocked_all24_rows_preserve_identity_and_fail_without_censoring(prepared, monkeypatch, invalid):
    monkeypatch.setattr(M, "check_ready", lambda: {"synthetic": True})
    monkeypatch.setenv("CELLDEV_INFO_DURATION_MONITOR_PID", str(os.getppid()))
    calls = []

    def validate(protocol, folder):
        result = {"passed": True, "candidate_lives": 40}
        M.save(folder / "report.json", result)
        return result

    def compile_library(path, source, fast):
        assert fast and M.sha(source) == M.read(prepared / "protocol.json")["input_sha256"]["sources/vctl.c"]
        path.write_bytes(b"mock library")
        path.with_suffix(".c").write_text("mock source")

    def ctl(cid, params, fp, ws, seeds, **kwargs):
        assert cid == 5 and kwargs["privileged"] is False and kwargs["threads"] == 2
        calls.append((ws.name, ws.over["T"], list(seeds), "full"))
        return fake_lives(M.spec.world(ws.preset, **ws.over), seeds, captures=12, controller=True)

    def tissue(body, ws, seeds, **kwargs):
        assert kwargs["threads"] == 2
        calls.append((ws.name, ws.over["T"], list(seeds), "reference"))
        value = fake_lives(M.spec.world(ws.preset, **ws.over), seeds, cells=len(body.cells))
        if invalid:
            value.ledger[0, M.spec.V3.L["status"]] = 64
        return value

    monkeypatch.setattr(M, "run_validation", validate)
    monkeypatch.setattr(M, "compile_measurement", compile_library)
    monkeypatch.setattr(M.H, "ctl_run", ctl)
    monkeypatch.setattr(M.H, "tissue_run", tissue)
    if invalid:
        with pytest.raises(ValueError, match="mismatch"):
            M.worker()
        assert len(calls) == 2
        failed = prepared / "measurement/rows/base_T768/frozen.pending/failure.json"
        assert M.read(failed)["status"] == "invalid_candidate"
        assert not (prepared / "measurement/report.json").exists()
        return
    M.worker()
    assert len(calls) == 24 and sum(len(c[2]) for c in calls) == 12288
    p = M.read(prepared / "protocol.json")
    assert all(c[2] == p["seeds"][str(c[1])] for c in calls)
    report = M.read(prepared / "measurement/report.json")
    assert report["status"] == "complete" and report["completed_candidate_lives"] == 12288
    assert set(report["conditions"]) == {f"{w}_T{t}" for w in M.WORLD_NAMES for t in M.DURATION_BLOCKS}
    assert len(list((prepared / "measurement/rows").rglob("row.npz"))) == 24
    with pytest.raises(ValueError, match="already exists"):
        M.worker()


def test_whole_reference_selection_retains_negative_effect_and_covariance():
    world = M.spec.world("catch_speck_l4", T=768, d0=.5, d_min=.25)
    captures = {"full": np.full(512, 8.), "frozen": np.tile([0., 20.], 256),
                "retuned": np.full(512, 11.), "smaller_frozen": np.full(512, 2.),
                "smaller_transferred": np.full(512, 3.), "quieter": np.full(512, 4.)}
    rows = {}
    for name, values in captures.items():
        result = fake_lives(world, range(512), captures=values)
        rows[name] = {"ledger": result.ledger, "hashes": result.hashes}
    report = M.condition_report(rows, world, M.row_tools())
    assert report["best_whole_reflex"] == "retuned"
    assert report["fixed_comparisons"]["full_minus_retuned"]["F"]["mean"] < 0
    direct = M.paired((captures["full"] - captures["frozen"]) * world.R_cap / world.T, np.zeros(512))
    actual = report["fixed_comparisons"]["full_minus_frozen"]["F"]
    assert actual["n"] == direct["n"]
    assert np.isclose(actual["mean"], direct["mean"], atol=1e-14)
    assert actual["se"] == direct["se"]
    assert not report["descriptive_checks"]["gap_above_3se"]
