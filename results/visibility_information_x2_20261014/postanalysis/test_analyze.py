"""Complete synthetic 26-row archives and focused evidence-corruption tests. Zero simulations."""

import copy
import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("visibility_offline", HERE / "analyze.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SOURCE = HERE.parents[1] / "autonomous_visibility_information_x2_20261014"


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
            for i, seed in enumerate(M.VALIDATION_SEEDS):
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
                emit(case + "_" + key, full, 2, 128, M.VALIDATION_SEEDS, key)
            checks.append(dict(check="full_fast", case=case, passed=True))
            one = {k: v[:1] if v.ndim else v for k, v in full.items()}
            for tag, seed in [
                ("record", M.VALIDATION_SEEDS[0]),
                ("same_life", M.VALIDATION_SEEDS[0]),
                ("other_life", M.VALIDATION_SEEDS[1]),
                ("other_world", M.VALIDATION_SEEDS[1]),
                ("control", M.VALIDATION_SEEDS[1]),
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
            emit(case + "_calibration", raw(dict(w, T=1024), 2, True), 2, 1024, M.VALIDATION_SEEDS, "fast")
    save(
        base / "validation/report.json",
        dict(
            status="complete",
            simulation_calls=82,
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
            ident = dict(protocol_sha256=M.sha(base / "protocol.json"), world=world, candidate=candidate, seeds=M.SEEDS)
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
    p = copy.deepcopy(M.read(SOURCE / "protocol.json"))
    for name in (
        "original/src/life/handbuilt.py",
        "original/src/life/spec.py",
        "original/controllers/mem_ctl.c",
        "inputs/recovered_inputs.json",
    ):
        target = base / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, target)
    for name in ("monitor.py", "measure.py", "validate.py"):
        (base / name).write_text("# synthetic receipt, never execute\n")
    prod = base / "production/src/life/kernel.c"
    prod.parent.mkdir(parents=True)
    prod.write_text("/* synthetic */")
    p["production_pins"] = {"src/life/kernel.c": M.sha(prod)}
    p["production_module_pins"] = {}
    for name in (
        "src/__init__.py",
        "src/life/__init__.py",
        "src/life/spec.py",
        "src/life/build.py",
        "src/lattice.py",
    ):
        path = base / "production" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic pinned source, never executed\n")
        p["production_pins"][name] = p["production_module_pins"][name] = M.sha(path)
    reviews = base / "inputs/reviews"
    save(reviews / "namespace_inventory.json", {"synthetic_only": True, "numeric_matches": []})
    save(
        reviews / "root_text_namespace_review.json",
        {
            "synthetic_only": True,
            "proposed_primary": [52_130_000, 52_130_512],
            "proposed_validation_whole_block": [52_160_000, 52_170_000],
        },
    )
    save(
        reviews / "namespace_audit.json",
        dict(
            synthetic_only=True,
            blocks=[113, 114, 115, 116],
            whole_blocks_half_open=[
                [51_000_000 + 10_000 * k, 51_000_000 + 10_000 * (k + 1)] for k in (113, 114, 115, 116)
            ],
            numeric_matches=[],
            malformed_real=[],
            npz_errors=[],
            inventory_sha256=M.sha(reviews / "namespace_inventory.json"),
            text_review_sha256=M.sha(reviews / "root_text_namespace_review.json"),
        ),
    )
    p["file_pins"] = {
        str(x.relative_to(base)): M.sha(x) for x in base.rglob("*") if x.is_file() and "production" not in x.parts
    }
    save(base / "protocol.json", p)
    prior = base / "original/outputs/previous/budget.json"
    save(prior, dict(status="complete", running={}, queued=[], cleanup_error=None))
    save(
        base / "resource_clearance.json",
        dict(
            status="cleared",
            all_processes_exited=True,
            budget_pins={"outputs/previous/budget.json": M.sha(prior)},
            processes=[dict(pid=100, start_ticks=100)],
            process_groups=[100],
        ),
    )
    ready = dict(status="released", production_pins=p["production_pins"], source_pins=dict(p["file_pins"]))
    ready["source_pins"].update({name: M.sha(base / name) for name in ("protocol.json", "resource_clearance.json")})
    save(base / "ready.json", ready)
    monitor = dict(pid=200, ppid=1, pgid=200, start_ticks=200)
    save(base / "attempt.json", dict(monitor=monitor, ready_sha256=M.sha(base / "ready.json")))
    identities = [dict(monitor, name="monitor")] + [
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
            cap_cpu_seconds=179,
            report_sha256=M.sha(base / "validation/report.json"),
            protocol_sha256=M.sha(base / "protocol.json"),
        ),
    )
    save(
        base / "budget.json",
        dict(
            status="complete",
            cpu_seconds=100.0,
            cap_cpu_seconds=3599,
            validation_cap_cpu_seconds=179,
            validation_cpu_seconds=10.0,
            wall_seconds=90.0,
            phase="research",
            running={},
            queued=[],
            completed=[dict(name=name, exit_code=0) for name in ["validation", *M.WORLDS]],
            ready=ready,
            process_identities=identities,
            owned_process_groups=[201, 202, 203],
            exit_code=0,
            reason=None,
        ),
    )
    return base


@pytest.fixture(scope="module")
def complete(tmp_path_factory):
    return fixture(tmp_path_factory.mktemp("complete_visibility"))


@pytest.fixture
def study(complete, tmp_path, monkeypatch):
    dest = tmp_path / "study"
    shutil.copytree(complete, dest)
    monkeypatch.setattr(M, "REVIEWED_PROTOCOL_SHA256", M.sha(dest / "protocol.json"))
    return dest


def update_row(base, mutate, world="flash5_dim25", role="I"):
    d = base / "rows" / world / role
    data = M.npz(d / "row.npz")
    mutate(data)
    np.savez_compressed(d / "row.npz", **data)
    check = M.read(d / "checkpoint.json")
    check["row_sha256"] = M.sha(d / "row.npz")
    save(d / "checkpoint.json", check)
    marker = M.read(d.parent / "complete.json")
    marker["checkpoint_pins"][role + "/checkpoint.json"] = M.sha(d / "checkpoint.json")
    save(d.parent / "complete.json", marker)


def update_validation(base, label, mutate):
    path = base / "validation" / (label + ".npz")
    data = M.npz(path)
    mutate(data)
    np.savez_compressed(path, **data)
    report = M.read(base / "validation/report.json")
    report["artifacts"][label]["sha256"] = M.sha(path)
    save(base / "validation/report.json", report)
    vb = M.read(base / "validation_budget.json")
    vb["report_sha256"] = M.sha(base / "validation/report.json")
    save(base / "validation_budget.json", vb)


def incomplete(base):
    out, vectors = M.analyze(base)
    assert out["status"] == "incomplete", out
    assert out["scientific_outcomes_emitted"] is False
    assert "worlds" not in out and not vectors
    return out["error"]


def test_full_synthetic_complete_archive(study):
    out, vectors = M.analyze(study)
    assert out["status"] == "complete", out
    assert out["research_lives"] == 13312 and out["validation"]["simulation_calls"] == 82
    assert out["validation"]["independently_rechecked_cases"] == 20
    assert out["resources"]["raw_research_row_cpu_seconds"] == pytest.approx(0.26)
    assert out["ledger_aliases"]["production_abi4_ledger"] is False
    for w in out["worlds"].values():
        assert w["reference_role"] == "R1" and w["do_less_role"] == "D3"
        assert w["information_payoff_criterion"] and not w["do_less_quarter_criterion"]
        assert w["capability_specific_admission"] == "incomplete"
        assert len(w["rows"]) == 13 and len(w["contrasts"]) == 12 and len(w["do_less_quarter_margins"]) == 8
    assert len(vectors) > 1000


def test_actual_candidates_are_rebuilt_without_engine_imports():
    p = M.read(SOURCE / "protocol.json")
    result = M.C.verify(SOURCE, p, M.read(SOURCE / "inputs/recovered_inputs.json"))
    assert result["candidate_count"] == 26
    M.world_packing(SOURCE, p)


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x["ledger"].__setitem__((0, 15), 123.0),
        lambda x: x["ledger"].__setitem__((0, 21), 1000.0),
        lambda x: x["ledger"].__setitem__((0, 19), 1.0),
        lambda x: x["ledger"].__setitem__((0, 19), 2.0),
        lambda x: x["ledger"].__setitem__((0, 49), np.nan),
        lambda x: x.update(ledger=x["ledger"][:511]),
        lambda x: x.update(ledger=x["ledger"].astype(np.float32)),
        lambda x: x.update(hashes=x["hashes"].astype(np.int64)),
        lambda x: x.update(diag=np.zeros((512, 15))),
        lambda x: x["diag"].__setitem__((0, 4), np.inf),
        lambda x: x["latency"].__setitem__(0, 0.5),
        lambda x: x.update(cpu_seconds=np.asarray(-1.0)),
        lambda x: x.update(cpu_seconds=np.asarray(1000.0)),
        lambda x: x.update(wall_seconds=np.asarray(np.nan)),
        lambda x: x.update(identity=np.asarray("{}")),
    ],
)
def test_resealed_raw_corruption_is_rejected(study, change):
    update_row(study, change)
    incomplete(study)


@pytest.mark.parametrize(
    "key,value",
    [
        ("status", "running"),
        ("exit_code", 1),
        ("reason", "job_failed"),
        ("running", {"123": "worker"}),
        ("queued", ["blink20"]),
        ("cpu_seconds", 3589.0),
        ("cpu_seconds", 9.0),
        ("validation_cpu_seconds", 169.0),
        ("validation_cpu_seconds", None),
        ("cap_cpu_seconds", 7200),
        ("cleanup_error", "group remains"),
        ("process_identities", []),
        ("owned_process_groups", [201, 202]),
        ("completed", [dict(name="validation", exit_code=0)]),
    ],
)
def test_monitor_corruption_never_emits_outcomes(study, key, value):
    p = study / "budget.json"
    v = M.read(p)
    v[key] = value
    save(p, v)
    incomplete(study)


@pytest.mark.parametrize(
    "path",
    [
        "rows/flash5_dim25/complete.json",
        "rows/blink20/D7/row.npz",
        "rows/blink20/D1/checkpoint.json",
        "attempt.json",
        "ready.json",
        "validation_budget.json",
        "validation/report.json",
        "validation/build/fast.so",
    ],
)
def test_missing_required_artifact_rejects_entire_study(study, path):
    (study / path).unlink()
    incomplete(study)


def test_corrupt_source_and_protocol_anchor(study):
    (study / "original/controllers/mem_ctl.c").write_text("changed")
    assert "pinned" in incomplete(study)


def test_unreviewed_protocol_is_rejected_even_if_all_shapes_match(study, monkeypatch):
    monkeypatch.setattr(M, "REVIEWED_PROTOCOL_SHA256", "0" * 64)
    assert "reviewed" in incomplete(study)


def test_candidate_modification_rejected_independently_of_protocol_digest(study, monkeypatch):
    p = M.read(study / "protocol.json")
    p["worlds"]["flash5_dim25"]["candidates"][2]["params"][9] = 6.0
    save(study / "protocol.json", p)
    monkeypatch.setattr(M, "REVIEWED_PROTOCOL_SHA256", M.sha(study / "protocol.json"))
    assert "reconstructed candidates" in incomplete(study)


@pytest.mark.parametrize(
    "label,change",
    [
        ("flash5_dim25_R0_0_production", lambda x: x["ledger"].__setitem__((0, 57), 99.0)),
        ("flash5_dim25_I_fast", lambda x: x["ledger"].__setitem__((0, 35), 99.0)),
        ("blink20_A_record", lambda x: x["hashes"].__setitem__((0, 0), 1)),
        ("blink20_B_replay_logs", lambda x: x["other_world"].__setitem__((0, 0), 9.0)),
        ("blink20_I_replay_logs", lambda x: x.update(control=x["actions"].copy())),
        ("flash5_dim25_I_calibration", lambda x: x["ledger"].__setitem__((0, 12), 999.0)),
        ("flash5_dim25_I_other_life", lambda x: x["diag"].__setitem__((0, 0), 1.0)),
    ],
)
def test_resealed_validation_corruption_is_independently_detected(study, label, change):
    update_validation(study, label, change)
    incomplete(study)


def test_duplicate_json_key_is_not_silently_accepted(study):
    (study / "budget.json").write_text('{"status":"complete","status":"complete"}')
    assert "duplicate" in incomplete(study)


def test_no_per_seed_best_reference():
    p = M.read(SOURCE / "protocol.json")
    rows = {}
    for world in M.WORLDS:
        w = p["worlds"][world]["base_world"]
        rows[world] = {r: led(w, captures=22) for r in M.ROLES}
        rows[world]["R0"] = led(w, captures=20)
        rows[world]["R1"] = led(w, captures=21)
        rows[world]["I"] = led(w, captures=30)
        # Two reference bodies alternate, while the whole R1 mean remains higher.
        x = rows[world]["R0"]
        x[:256] = led(w, 256, captures=30)
        x[256:] = led(w, 256, captures=10)
    out, _ = M.scientific_summary(rows, p)
    assert all(x["reference_role"] == "R1" for x in out.values())
    for world in M.WORLDS:
        expected = float((rows[world]["I"][:, 15] - rows[world]["R1"][:, 15]).mean())
        assert out[world]["information_gap"]["mean"] == expected


def test_negative_quarter_margin_preserved():
    p = M.read(SOURCE / "protocol.json")
    rows = {}
    for world in M.WORLDS:
        w = p["worlds"][world]["base_world"]
        rows[world] = {r: led(w, captures=20) for r in M.ROLES}
        rows[world]["I"] = led(w, captures=24)
        rows[world]["D7"] = led(w, captures=23)
    out, _ = M.scientific_summary(rows, p)
    for v in out.values():
        assert not v["do_less_quarter_criterion"]
        assert v["do_less_quarter_margins"]["D7"]["quarter_gap_minus_gain"]["mean"] < 0


def test_unreleased_study_emits_no_outcomes(study):
    (study / "ready.json").unlink()
    incomplete(study)


@pytest.mark.parametrize(
    "key,value",
    [
        ("cpu_seconds", -1.0),
        ("cpu_seconds", np.nan),
        ("cpu_seconds", 100.0),
        ("wall_seconds", np.inf),
        ("wall_seconds", -1.0),
    ],
)
def test_production_validation_timing_is_checked(study, key, value):
    update_validation(study, "flash5_dim25_R0_0_production", lambda x: x.update({key: np.asarray(value)}))
    incomplete(study)


def test_replayed_callbacks_are_checked_independently(study):
    update_validation(study, "blink20_I_replay_logs", lambda x: x["other_world_callbacks"].__setitem__((0, 1), 99.0))
    assert "replay" in incomplete(study)


def test_static_census_cannot_change_even_if_ledger_still_reconciles(study):
    w = M.read(study / "protocol.json")["worlds"]["flash5_dim25"]["base_world"]
    update_row(study, lambda x: x.update(ledger=led(w, cells=55, sense=19)))
    assert "fixed body cell count" in incomplete(study)


def test_archived_dependency_wins_over_mutable_live_shadow(study):
    name = "outputs/previous/budget.json"
    shadow = study.resolve().parents[1] / name
    save(shadow, dict(status="running"))
    assert M.external(study, name) == (study / "original" / name).resolve()
    out, _ = M.analyze(study)
    assert out["status"] == "complete", out


def test_production_source_never_uses_frozen_abi3_original(study):
    production = study / "production/src/life/spec.py"
    assert M.external(study, "src/life/spec.py") == production.resolve()
    production.unlink()
    with pytest.raises(FileNotFoundError):
        M.external(study, "src/life/spec.py")
