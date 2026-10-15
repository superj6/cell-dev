"""Synthetic AD runtime coverage; no engine imports or real library execution."""

import ast
import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("ad_runtime", HERE / "analyze.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def led(w, n=512, captures=20, cells=56, sense=19):
    x = np.zeros((n, 57), dtype=np.float64)
    values = dict(
        captures=np.arange(n) % 3 + captures,
        dark_captures=np.arange(n) % 2 + 3,
        late_captures=1,
        misses=2,
        live_time=cells * w["T"],
        live_S=sense * w["T"],
        live_M=(cells - sense) * w["T"],
        births=0,
        n_end=cells,
        n_peak=cells,
        n_S_end=sense,
        n_M_end=cells - sense,
        t_end=w["T"],
        t_ext=-1,
        spikes=20,
        kappa_sum=20,
        contact_events=40,
        rec_gain=20,
        rec_cand=40,
        rec_accept=20,
        rec_events=20,
        samples=4,
        zone_samples=1,
    )
    for key, value in values.items():
        x[:, M.A.L[key]] = value
    x[:, M.A.L["clicks"]] = x[:, M.A.L["captures"]] + 2
    # Independent fixture accountant: scalar loop, with stated physical prices.
    for row in x:
        cost = w["c_live"] * row[1]
        for price, index in [
            ("c_spike", 3),
            ("c_tw", 4),
            ("c_msg", 5),
            ("c_div", 6),
            ("c_sec", 2),
            ("c_miss", 36),
            ("c_rec", 44),
        ]:
            cost = cost + w[price] * row[index]
        cost = cost + max(0, -w["b2_value"]) * row[38]
        row[12] = cost
        row[0] = w["R_cap"] * row[35]
        row[14] = row[0] - cost - 0.0
        row[15] = row[14] / w["T"]
    return x


def raw(w, n, controller, captures=20, cells=56, sense=19):
    return dict(
        ledger=led(w, n, captures, cells, sense),
        hashes=np.zeros((n, 5), dtype=np.uint64),
        diag=np.zeros((n, 16 if controller else 0)),
        latency=np.full(n, w["d0"]) if controller else np.empty(0),
        cpu_seconds=np.asarray(0.01),
        wall_seconds=np.asarray(0.02),
    )


def write_validation(base, p):
    libraries = {}
    for key in ("full", "fast", "replay", "production"):
        lib = base / "validation/build" / (key + ".so")
        lib.parent.mkdir(parents=True, exist_ok=True)
        lib.write_bytes(b"SYNTHETIC NOT A SHARED LIBRARY " + key.encode())
        item = dict(path=str(lib.relative_to(base)), sha256=M.sha(lib))
        if key == "production":
            item["source_sha256"] = p["production_pins"]["src/life/kernel.c"]
        else:
            src = lib.with_suffix(".c")
            src.write_text("/* synthetic only */\n")
            item.update(
                generated_source=str(src.relative_to(base)),
                generated_source_sha256=M.sha(src),
                compiler_sha256=p["numerical_identity"]["compiler_sha256"],
                flags=p["numerical_identity"]["compiler_flags"] + (["-DLIFE_FAST"] if key == "fast" else []),
            )
        libraries[key] = item
    artifacts = {}
    checks = []

    def emit(label, data, n, T, seeds, library, **extra):
        path = base / "validation" / (label + ".npz")
        np.savez_compressed(path, **data)
        artifacts[label] = dict(path=str(path.relative_to(base)), sha256=M.sha(path), simulation_calls=n, **extra)
        if n:
            artifacts[label].update(T=T, seeds=seeds, library=library)

    for world in M.WORLDS:
        w = dict(p["worlds"][world]["base_world"], T=128)
        for role in ("R0", "R1"):
            for i, seed in enumerate(p["validation_seeds"][:2]):
                case = f"{world}_{role}_{i}"
                old = raw(w, 1, False)
                emit(case + "_scratch", old, 1, 128, [seed], "full")
                new = dict(old, ledger=np.c_[old["ledger"], old["ledger"][:, 21]])
                new["ledger"][:, 21:23] = 0
                emit(case + "_production", new, 1, 128, [seed], "production")
                checks.append(dict(check="production_bridge", case=case, passed=True))
        for role in ("I", "A", "B"):
            case = f"{world}_{role}"
            full = raw(w, 2, True)
            for key in ("full", "fast"):
                emit(case + "_" + key, full, 2, 128, p["validation_seeds"][:2], key)
            checks.append(dict(check="full_fast", case=case, passed=True))
            one = {k: v[:1] if v.ndim else v for k, v in full.items()}
            for tag, seed in [
                ("record", p["validation_seeds"][:2][0]),
                ("same_life", p["validation_seeds"][:2][0]),
                ("other_life", p["validation_seeds"][:2][1]),
                ("other_world", p["validation_seeds"][:2][1]),
                ("control", p["validation_seeds"][:2][1]),
            ]:
                emit(case + "_" + tag, one, 1, 128, [seed], "replay")
            actions = np.array([[1.0, 1.0, 1.0, 1.0, 1.0, 1.0], [2.0, 2.0, 2.0, 2.0, 2.0, 2.0]])
            logs = dict(
                callbacks=np.array([[0.0, 0.0, 0.0], [4.0, 1.0, 1.0]]),
                actions=actions,
                same_life=actions,
                other_life=actions,
                other_world=actions,
                control=actions + 1,
            )
            logs.update({tag + "_callbacks": logs["callbacks"] for tag in ("same_life", "other_life", "other_world")})
            emit(case + "_replay_logs", logs, 0, None, None, None, truth_calls=0)
            checks.append(dict(check="C5_replay", case=case, passed=True))
        for role in M.ROLES:
            emit(
                world + "_" + role + "_calibration",
                raw(dict(w, T=1024), 3, role in ("I", "A", "B")),
                3,
                1024,
                p["validation_seeds"],
                "fast",
            )
    startup = dict(
        status="complete",
        identity=p["expected_numerical_identity"],
        protocol_sha256=M.sha(base / "protocol.json"),
        preexpected_fields=sorted(p["expected_numerical_identity"]),
        newly_captured_fields=[],
        numerical_identity_invocations=1,
        simulation_calls=2,
        abi=3,
        seeds=[11, 11],
        T=200,
        cpu_seconds=0.01,
        wall_seconds=0.02,
    )
    save(base / "validation/startup_identity.json", startup)
    identity = dict(
        path="validation/startup_identity.json",
        sha256=M.sha(base / "validation/startup_identity.json"),
        simulation_calls=2,
        T=200,
        seeds=[11, 11],
        library="isolated_production_full_and_fast",
    )
    artifacts["startup_identity"] = identity
    calibration = {role: 0.01 for role in M.ROLES}
    projection = M.calibration_projection(calibration, p["historical_cpu_per_life"])
    save(base / "validation/calibration_projection.json", projection)
    save(
        base / "validation/report.json",
        dict(
            status="complete",
            simulation_calls=76,
            identity=identity,
            validation_matrix=M.VALIDATION_MATRIX,
            calibration_cpu_seconds=calibration,
            calibration_projection=projection,
            protocol_sha256=M.sha(base / "protocol.json"),
            source_pins=p["file_pins"],
            production_pins=p["production_pins"],
            libraries=libraries,
            artifacts=artifacts,
            checks=checks,
            no_retuning=True,
            no_research_outcomes=True,
        ),
    )


def write_rows(base, p):
    for world in M.WORLDS:
        checkpoint_pins = {}
        w = p["worlds"][world]["base_world"]
        for candidate in p["worlds"][world]["candidates"]:
            role = candidate["role"]
            directory = base / "rows" / world / role
            directory.mkdir(parents=True)
            ident = dict(
                protocol_sha256=M.sha(base / "protocol.json"), world=world, candidate=candidate, seeds=p["seeds"]
            )
            captures = {"R0": 20, "R1": 21, "I": 30, "A": 23, "B": 24}.get(role, 22)
            sense = sum(c[2] == 0 for c in candidate["cells"])
            data = raw(w, 512, "params" in candidate, captures, candidate["cell_count"], sense)
            data["identity"] = np.asarray(M.canonical(ident))
            np.savez_compressed(directory / "row.npz", **data)
            save(directory / "checkpoint.json", dict(identity=ident, row_sha256=M.sha(directory / "row.npz")))
            checkpoint_pins[role + "/checkpoint.json"] = M.sha(directory / "checkpoint.json")
        save(
            base / "rows" / world / "complete.json",
            dict(
                status="complete",
                protocol_sha256=M.sha(base / "protocol.json"),
                world=world,
                roles=M.ROLES,
                simulation_calls=6656,
                checkpoint_pins=checkpoint_pins,
            ),
        )


def fixture(base):
    base.mkdir(parents=True)
    # This is fabricated evidence only: no retained world, candidate or scientific seed is used.
    world = dict(
        T=1024,
        t0=0,
        t_open=0,
        b2_amp=0,
        b2_value=0,
        R_cap=500,
        c_live=0.02,
        c_spike=0.004,
        c_tw=0.004,
        c_msg=0.001,
        c_div=0.5,
        c_sec=0.004,
        c_miss=10,
        c_rec=0.001,
        d0=1.0,
    )
    candidates = []
    for role in M.ROLES:
        item = dict(role=role, cell_count=56, cells=[[i, 0, 0 if i < 19 else 1, 0] for i in range(56)])
        if role in ("I", "A", "B"):
            item["params"] = [0.0] * 30
        candidates.append(item)
    p = dict(
        study="AD fully dark flash information",
        worlds={"flash5_dark": dict(base_world=world, candidates=candidates)},
        validation_seeds=[100001, 100002, 100003],
        seeds=list(range(200000, 200512)),
        file_pins={},
        production_pins={},
        historical_cpu_per_life={role: 0.005 for role in M.ROLES},
        numerical_identity=dict(compiler_sha256="1" * 64, compiler_flags=["SYNTHETIC_ONLY"]),
    )
    src = base / "production/src/life/kernel.c"
    src.parent.mkdir(parents=True)
    src.write_text("/* synthetic never compile */")
    p["production_pins"]["src/life/kernel.c"] = M.sha(src)
    kernels = {}
    for fast in (False, True):
        lib = base / "build-cache" / ("synthetic_" + str(fast) + ".so")
        lib.parent.mkdir(parents=True, exist_ok=True)
        lib.write_bytes(b"NOT_A_LIBRARY_" + str(fast).encode())
        kernels[str(fast)] = M.sha(lib)
    p["expected_numerical_identity"] = dict(kernels=kernels, sources=dict(p["production_pins"]), golden="synthetic")
    for name in ("monitor.py", "measure.py", "validate.py"):
        (base / name).write_text("# synthetic source receipt, never execute\n")
        p["file_pins"][name] = M.sha(base / name)
    for name in ("analyze.py", "accounting.py", "candidates.py"):
        dest = base / "analysis" / name
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(HERE / name, dest)
        p["file_pins"]["analysis/" + name] = M.sha(dest)
    save(base / "protocol.json", p)
    prior = base / "original/outputs/synthetic_prior/budget.json"
    save(prior, dict(status="incomplete", running={}, queued=[], cleanup_error=None))
    save(
        base / "resource_clearance.json",
        dict(
            status="cleared",
            all_processes_exited=True,
            budget_pins={"outputs/synthetic_prior/budget.json": M.sha(prior)},
            processes=[dict(pid=100, start_ticks=100)],
            process_groups=[100],
        ),
    )
    ready = dict(status="released", production_pins=p["production_pins"], source_pins=dict(p["file_pins"]))
    ready["source_pins"].update({name: M.sha(base / name) for name in ("protocol.json", "resource_clearance.json")})
    save(base / "ready.json", ready)
    mon = dict(pid=200, ppid=1, pgid=200, start_ticks=200)
    save(base / "attempt.json", dict(monitor=mon, ready_sha256=M.sha(base / "ready.json")))
    identities = [dict(mon, name="monitor")] + [
        dict(pid=201 + i, ppid=200, pgid=201 + i, start_ticks=201 + i, name=name)
        for i, name in enumerate(["validation", *M.WORLDS])
    ]
    write_validation(base, p)
    write_rows(base, p)
    save(
        base / "validation_budget.json",
        dict(
            status="complete",
            cpu_seconds=10.0,
            cap_cpu_seconds=180,
            report_sha256=M.sha(base / "validation/report.json"),
            protocol_sha256=M.sha(base / "protocol.json"),
        ),
    )
    save(
        base / "budget.json",
        dict(
            status="complete",
            cpu_seconds=100.0,
            cap_cpu_seconds=2400,
            validation_cap_cpu_seconds=180,
            validation_cpu_seconds=10.0,
            wall_seconds=90.0,
            phase="research",
            running={},
            queued=[],
            completed=[dict(name=name, exit_code=0) for name in ["validation", *M.WORLDS]],
            ready=ready,
            process_identities=identities,
            owned_process_groups=[201, 202],
            exit_code=0,
            reason=None,
        ),
    )
    return base


@pytest.fixture(scope="module")
def complete(tmp_path_factory):
    return fixture(tmp_path_factory.mktemp("synthetic_AD") / "complete")


@pytest.fixture
def study(complete, tmp_path, monkeypatch):
    dest = tmp_path / "study"
    shutil.copytree(complete, dest)
    # Operational coverage test intentionally substitutes preparation verification.
    # Exact real registration/source/candidate tests remain pending authorized preparation.
    monkeypatch.setattr(M, "verify_protocol", lambda base: (M.read(base / "protocol.json"), {"synthetic_only": True}))
    return dest


def update_validation(base, label, mutate):
    path = base / "validation" / (label + ".npz")
    data = M.npz(path)
    mutate(data)
    np.savez_compressed(path, **data)
    report = M.read(base / "validation/report.json")
    report["artifacts"][label]["sha256"] = M.sha(path)
    save(base / "validation/report.json", report)
    budget = M.read(base / "validation_budget.json")
    budget["report_sha256"] = M.sha(base / "validation/report.json")
    save(base / "validation_budget.json", budget)


def reject(base):
    summary, vectors = M.analyze(base)
    assert summary["status"] == "incomplete", summary
    assert not summary["scientific_outcomes_emitted"] and not vectors and "worlds" not in summary
    return summary["error"]


def test_all76_validation_and6656_research_lives_complete(study):
    summary, vectors = M.analyze(study)
    assert summary["status"] == "complete", summary
    assert summary["simulation_calls"] == 6732 and summary["validation"]["simulation_calls"] == 76
    assert summary["validation"]["numerical_identity_invocations"] == 1
    assert summary["validation"]["independently_rechecked_cases"] == 10
    assert len(vectors) == 836 and len(summary["worlds"]["flash5_dark"]["rows"]) == 13
    assert summary["validation"]["calibration_projection"]["cpu_per_life"] == {role: 0.005 for role in M.ROLES}


@pytest.mark.parametrize(
    "label,change",
    [
        ("flash5_dark_R0_0_production", lambda d: d["cpu_seconds"].__setitem__((), np.nan)),
        ("flash5_dark_D7_calibration", lambda d: d["ledger"].__setitem__((0, 15), 123.0)),
        ("flash5_dark_I_fast", lambda d: d["ledger"].__setitem__((0, 35), 123.0)),
        ("flash5_dark_A_replay_logs", lambda d: d["other_world_callbacks"].__setitem__((0, 2), 123.0)),
    ],
)
def test_resealed_validation_corruptions_reject(study, label, change):
    update_validation(study, label, change)
    reject(study)


@pytest.mark.parametrize(
    "key,value",
    [
        ("cpu_seconds", 2390.0),
        ("validation_cpu_seconds", 170.0),
        ("cleanup_error", "survivor"),
        ("owned_process_groups", [201]),
        ("completed", [dict(name="validation", exit_code=0)]),
    ],
)
def test_resource_corruptions_reject(study, key, value):
    path = study / "budget.json"
    data = M.read(path)
    data[key] = value
    save(path, data)
    reject(study)


def test_identity_must_be_once_and_original_fields_retained(study):
    path = study / "validation/startup_identity.json"
    data = M.read(path)
    data["numerical_identity_invocations"] = 2
    save(path, data)
    report = M.read(study / "validation/report.json")
    report["identity"]["sha256"] = M.sha(path)
    report["artifacts"]["startup_identity"]["sha256"] = M.sha(path)
    save(study / "validation/report.json", report)
    budget = M.read(study / "validation_budget.json")
    budget["report_sha256"] = M.sha(study / "validation/report.json")
    save(study / "validation_budget.json", budget)
    assert "one complete" in reject(study)


def test_unaccounted_startup_library_rejects(study):
    next((study / "build-cache").glob("*.so")).unlink()
    assert "library bytes" in reject(study)


def test_fixed_cost_gate_uses_every_historical_role_floor():
    cal = {role: 0.03 for role in M.ROLES}
    old = {role: 0.005 for role in M.ROLES}
    old["D7"] = 0.2
    result = M.calibration_projection(cal, old)
    assert result["cpu_per_life"]["D7"] == 0.2
    assert result["projected_total_cpu_seconds"] == pytest.approx(180 + 1.5 * 512 * (0.2 + 0.01 * 12))
    del old["D7"]
    with pytest.raises(ValueError, match="thirteen"):
        M.calibration_projection(cal, old)


def test_missing_last_research_role_cannot_emit_partial(study):
    (study / "rows/flash5_dark/D7/row.npz").unlink()
    reject(study)


def test_actual_producer_four_field_receipt_and_owned_identity_order():
    source = HERE.parent / "autonomous_visibility_dark_tail_information_20261014"
    if not source.exists():
        source = HERE.parent
    tree = ast.parse((source / "monitor.py").read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_identity")
    returned = next(n.value for n in ast.walk(function) if isinstance(n, ast.Return))
    assert {ast.literal_eval(k) for k in returned.keys} == {"pid", "ppid", "pgid", "start_ticks"}
    tree = ast.parse((source / "validate.py").read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "validate")
    isolated = [
        n
        for n in ast.walk(function)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "subprocess"
        and n.func.attr == "run"
        and any(isinstance(x, ast.Constant) and x.value == "production_identity.py" for x in ast.walk(n))
    ]
    assert len(isolated) == 1
    imports = [n.lineno for n in ast.walk(function) if isinstance(n, ast.ImportFrom) and n.module in ("raw", "frozen")]
    assert imports and isolated[0].lineno < min(imports)
    assert not any(k.arg == "start_new_session" for k in isolated[0].keywords)
    tree = ast.parse((source / "production_identity.py").read_text())
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "numerical_identity"
    ]
    assert len(calls) == 1
