"""Pure synthetic completed-data and archive tests for N; no compiler or life simulator."""
import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location("N_analysis_test", HERE / "analyze.py")
A = importlib.util.module_from_spec(loader)
loader.loader.exec_module(A)
PUBLIC = A.ROOT / "results/information_duration_20261014"
PREPARATION = PUBLIC / "prelaunch" if (PUBLIC / "prelaunch").exists() else PUBLIC


def save_arrays(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **values)


def ledger(world, count, captures=5., cells=56):
    result = np.zeros((count, 57), dtype=np.float64)
    for name, value in {"t_end": world["T"], "n_end": cells, "n_peak": cells,
                        "live_time": cells * world["T"], "captures": captures, "clicks": captures}.items():
        result[:, A.L[name]] = value
    result[:, A.L["income"]] = world["R_cap"] * result[:, A.L["captures"]]
    result[:, A.L["cost"]] = A.F.costs(result, world)
    result[:, A.L["net"]] = result[:, A.L["income"]] - result[:, A.L["cost"]]
    result[:, A.L["F"]] = result[:, A.L["net"]] / world["T"]
    return result


def validation(base, protocol):
    folder = base / "measurement/validation"
    report = {"passed": True, "candidate_lives": 40, "T": 64, "records": [], "checks": {},
              "cpu_seconds": 1., "library_sha256": A.sha(folder / "replay.so"),
              "source_sha256": A.sha(folder / "replay.c")}

    def keep(tag, world, count, controller=False, replay=False, marker=0, logged=False):
        row = {"ledger": ledger(world, count), "hashes": np.full((count, 5), 17, dtype=np.uint64),
               "diag": np.zeros((count, 16 if controller else 0))}
        if controller and not replay:
            row["diag"][:, 0] = 1
        if controller:
            row["diag"][:, 2] = 3
        if logged:
            row.update(pings=np.array([[1., marker]]), actions=np.array([
                [1., 2., marker, .5, 3., 3.5],
                [2., 2., .2, .3, 4., 2.],
                [3., .5, 4., .03125, 2., 0.]]))
        path = folder / (tag + ".npz")
        save_arrays(path, row)
        report["records"].append({"tag": tag, "lives": count, "sha256": A.sha(path)})

    for name in A.WORLDS:
        world = dict(protocol["worlds"][name]["768"], T=64)
        controller = []
        for i in (0, 1):
            prefix = f"{name}_{i}_"
            keep(prefix + "builtin", world, 1, controller=True)
            keep(prefix + "closed", world, 1, controller=True, marker=i, logged=True)
            for role in ("same_life", "other_life", "other_world"):
                keep(prefix + role, world, 1, controller=True, replay=True, marker=i, logged=True)
            keep(prefix + "control", world, 1, controller=True, marker=i + 2, logged=True)
            controller.append({"seed": protocol["validation"]["seeds"][i], "copy_bitwise": True,
                               "replay": {role: True for role in ("same_life", "other_life", "other_world")},
                               "control_differs": True, "pings": 1, "action_records": 3})
        for role in ("scratch_reflex", "production_reflex", "null", "inert"):
            keep(name + "_" + role, world, 2)
        report["checks"][name] = {"controller_replay": controller, "reflex_production_parity": True,
                                  "null_inert_world_parity": True, "excluded_ledger_columns": [21, 22],
                                  "excluded_hash": "all"}
    A.save(folder / "report.json", report)


@pytest.fixture
def complete(tmp_path):
    base = tmp_path / "work"
    shutil.copytree(PREPARATION, base, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    protocol = A.read(base / "protocol.json")
    ready = A.read(base / "ready.template.json")
    A.save(base / "ready.json", ready)
    A.save(base / "budget.json", {"status": "complete", "cpu_seconds": 100., "cap_cpu_seconds": 3600,
                                  "exit_code": 0, "running": {}, "queued": [], "ready": ready})
    dependency = base / "dependencies/L"
    dependency.mkdir(parents=True)
    for name in ("protocol.json", "run_budgeted.py"):
        shutil.copy2(A.ROOT / A.DEPENDENCY / name, dependency / name)
    A.save(dependency / "budget.json", {"status": "complete", "running": {}, "queued": []})
    folder = base / "measurement"
    (folder / "validation").mkdir(parents=True)
    generated = A.generated_text(base)
    for name in ("research", "validation/replay"):
        (folder / (name + ".c")).write_text(generated)
        (folder / (name + ".so")).write_bytes(b"synthetic library; never executable")
    validation(base, protocol)
    manifest = {"protocol_sha256": A.sha(base / "protocol.json"), "ready": ready,
                "libraries": {str(path.relative_to(folder)): A.sha(path) for path in folder.rglob("*")
                              if path.suffix in (".c", ".so")},
                "validation_sha256": A.sha(folder / "validation/report.json"),
                **{key: protocol[key] for key in ("worlds", "candidates", "seeds")}}
    A.save(folder / "manifest.json", manifest)
    report = {"status": "complete", "candidate_lives": 12288, "completed_candidate_lives": 12288,
              "validation_lives": 40, "limitations": protocol["limitations"], "conditions": {}}
    done = []
    for duration in A.DURATIONS:
        for world in A.WORLDS:
            key, rows = f"{world}_T{duration}", {}
            settings = protocol["worlds"][world][str(duration)]
            for candidate in protocol["candidates"][world]:
                name = candidate["name"]
                counts = {"full": 8., "frozen": np.tile([0., 20.], 256), "retuned": 11.,
                          "smaller_frozen": 2., "smaller_transferred": 3., "quieter": 4.}
                identity = {"manifest": manifest, "condition": [world, duration], "candidate": candidate,
                            "seeds": protocol["seeds"][str(duration)]}
                row = {"identity": np.asarray(json.dumps(identity, sort_keys=True, separators=(",", ":"))),
                       "ledger": ledger(settings, 512, counts[name]),
                       "hashes": np.full((512, 5), A.F.HASH_INIT, dtype=np.uint64),
                       "diag": np.zeros((512, 16 if name == "full" else 0)),
                       "latency": np.full(512, settings["d0"]) if name == "full" else np.empty(0),
                       "cpu_seconds": np.asarray(1.), "wall_seconds": np.asarray(.5)}
                directory = folder / "rows" / key / name
                save_arrays(directory / "row.npz", row)
                A.save(directory / "checkpoint.json",
                       {"identity": identity, "row_sha256": A.sha(directory / "row.npz")})
                rows[name] = row
                done.append(key + "/" + name)
            report["conditions"][key], _ = A.condition(rows, settings)
    A.save(folder / "report.json", report)
    A.save(folder / "progress.json", {"status": "complete", "completed_rows": done,
                                      "completed_candidate_lives": 12288})
    return base


@pytest.mark.parametrize("status", [None, "running", "waiting_for_workers", "incomplete", "monitor_failed"])
def test_own_completion_gate_precedes_all_input_or_dependency_reads(tmp_path, monkeypatch, status):
    if status is not None:
        A.save(tmp_path / "budget.json", {"status": status})
    monkeypatch.setattr(A, "audit_inputs", lambda base: pytest.fail("read input before own completion"))
    summary, vectors = A.analyze(tmp_path)
    assert summary == {"status": "incomplete", "analysis_simulated_lives": 0} and vectors == {}


def test_complete_synthetic_study_retains_all24_rows_negative_effects_and_paired_covariance(complete):
    summary, vectors = A.analyze(complete)
    assert summary["research_candidate_lives"] == 12288 and summary["bounded_validation_lives"] == 40
    assert summary["audit"]["validation"]["raw_records"] == 32
    assert summary["budget"]["row_cpu_seconds"] == 24.
    protocol = A.read(complete / "protocol.json")
    for name, result in summary["conditions"].items():
        duration = int(name.split("T")[1])
        world = protocol["worlds"][name.split("_T")[0]][str(duration)]
        assert result["best_whole_reflex"] == "retuned"
        assert result["fixed_comparisons"]["full_minus_retuned"]["F"]["mean"] == pytest.approx(
            -3 * world["R_cap"] / duration)
        paired = (8 - np.tile([0., 20.], 256)) * world["R_cap"] / duration
        contrast = result["fixed_comparisons"]["full_minus_frozen"]["F"]
        assert contrast["mean"] == pytest.approx(paired.mean())
        assert contrast["se"] == pytest.approx(paired.std(ddof=1) / np.sqrt(512))
        assert not result["descriptive_checks"]["gap_above_3se"]
        assert len(summary["candidate_full_ledger_means"][name]["full"]) == 57
        assert np.allclose(vectors[name + "__full_minus_frozen"], paired)
    assert len(vectors) == 162


@pytest.mark.parametrize("key,value", [("cpu_seconds", 3600), ("exit_code", 1),
                                       ("running", {"123": "measurement"}), ("queued", ["measurement"])])
def test_false_complete_budget_rejected_before_scoring(complete, key, value):
    budget = A.read(complete / "budget.json")
    budget[key] = value
    A.save(complete / "budget.json", budget)
    with pytest.raises(ValueError):
        A.analyze(complete)


@pytest.mark.parametrize("fault,message", [("status", "guarded"), ("fitness", "fitness bytes"),
                                          ("net", "net accounting"),
                                          ("hash", "hash initializer"), ("latency", "latency"),
                                          ("diagnostics", "diagnostics"), ("identity", "identity")])
def test_raw_row_semantic_corruption_rejected_even_with_updated_file_hash(complete, fault, message):
    folder = complete / "measurement/rows/base_T768/full"
    row = A.arrays(folder / "row.npz")
    if fault == "status":
        row["ledger"][0, A.L["status"]] = 2
    elif fault == "fitness":
        row["ledger"][0, A.L["F"]] += 1
    elif fault == "net":
        row["ledger"][0, A.L["net"]] += 1
    elif fault == "hash":
        row["hashes"][0, 0] ^= np.uint64(1)
    elif fault == "latency":
        row["latency"][0] = 1
    elif fault == "diagnostics":
        row["diag"] = row["diag"][:, :15]
    else:
        identity = json.loads(str(row["identity"].item()))
        identity["seeds"][0] += 1
        row["identity"] = np.asarray(json.dumps(identity))
    save_arrays(folder / "row.npz", row)
    checkpoint = A.read(folder / "checkpoint.json")
    checkpoint["row_sha256"] = A.sha(folder / "row.npz")
    A.save(folder / "checkpoint.json", checkpoint)
    with pytest.raises(ValueError, match=message):
        A.analyze(complete)


@pytest.mark.parametrize("tag,fault,message", [("base_0_other_world", "actions", "replay action"),
                                              ("base_0_closed", "hashes", "builtin/copy"),
                                              ("base_production_reflex", "hashes", "production/scratch"),
                                              ("base_null", "hashes", "null/inert")])
def test_validation_is_rebuilt_from_raw_arrays(complete, tag, fault, message):
    folder = complete / "measurement/validation"
    row = A.arrays(folder / (tag + ".npz"))
    row[fault][0, -1] += 1
    save_arrays(folder / (tag + ".npz"), row)
    report = A.read(folder / "report.json")
    next(r for r in report["records"] if r["tag"] == tag)["sha256"] = A.sha(folder / (tag + ".npz"))
    A.save(folder / "report.json", report)
    with pytest.raises(ValueError, match=message):
        A.validation_audit(complete, A.read(complete / "protocol.json"))


def test_source_reconstruction_detects_generated_code_change(complete):
    path = complete / "measurement/research.c"
    path.write_text(path.read_text() + "\n/* unregistered generated change */\n")
    manifest = A.read(complete / "measurement/manifest.json")
    manifest["libraries"]["research.c"] = A.sha(path)
    A.save(complete / "measurement/manifest.json", manifest)
    with pytest.raises(ValueError, match="generated C"):
        A.audit_inputs(complete)


@pytest.mark.parametrize("fault,message", [("empty_pings", "empty or invalid"),
                                          ("oversized", "registered capacity"),
                                          ("ping_count", "ping count"),
                                          ("accepted_count", "accepted-action count"),
                                          ("steering_count", "steering returned counts"),
                                          ("steering_negative", "steering returned counts"),
                                          ("steering_fraction", "steering returned counts"),
                                          ("steering_total", "accepted-action count"),
                                          ("truncated_steering", "truncated or mismatched"),
                                          ("replay_pings", "injected ping bytes")])
def test_logged_validation_counts_and_capacity_are_independently_checked(complete, fault, message):
    folder = complete / "measurement/validation"
    tag = "base_0_same_life" if fault == "replay_pings" else "base_0_control"
    row = A.arrays(folder / (tag + ".npz"))
    if fault == "empty_pings":
        row["pings"] = np.empty((0, 2))
    elif fault == "oversized":
        row["pings"] = np.zeros(((1 << 20) // 6 + 1, 2))
    elif fault == "ping_count":
        row["diag"][0, 0] += 1
    elif fault == "accepted_count":
        row["diag"][0, 2] += 1
    elif fault == "steering_count":
        row["actions"][2, 4] += 1
    elif fault in ("steering_negative", "steering_fraction", "steering_total"):
        count = {"steering_negative": -1., "steering_fraction": .5, "steering_total": 3.}[fault]
        row["actions"][1, 5] = row["actions"][2, 4] = count
    elif fault == "truncated_steering":
        row["actions"][0, 0] = 2
    else:
        row["pings"][0, 1] += 1
    save_arrays(folder / (tag + ".npz"), row)
    report = A.read(folder / "report.json")
    next(r for r in report["records"] if r["tag"] == tag)["sha256"] = A.sha(folder / (tag + ".npz"))
    A.save(folder / "report.json", report)
    with pytest.raises(ValueError, match=message):
        A.validation_audit(complete, A.read(complete / "protocol.json"))


def test_steering_tolerance_is_not_the_logged_accepted_count(complete):
    folder = complete / "measurement/validation"
    tag = "base_0_control"
    row = A.arrays(folder / (tag + ".npz"))
    assert row["actions"][2, 3] == .03125 and row["actions"][2, 4] == 2
    assert row["diag"][0, 2] == 3
    row["actions"][2, 3] = .0625
    save_arrays(folder / (tag + ".npz"), row)
    report = A.read(folder / "report.json")
    next(r for r in report["records"] if r["tag"] == tag)["sha256"] = A.sha(folder / (tag + ".npz"))
    A.save(folder / "report.json", report)
    assert A.validation_audit(complete, A.read(complete / "protocol.json"))["lives"] == 40


def test_generated_source_absolute_includes_are_normalized_without_changing_code():
    source = ('#include "/home/test/repo/results/open_headroom/harness/ctl_core.c"\n'
              '#include "/home/test/repo/outputs/autonomous_information_duration_20261014/sources/vctl.c"\n')
    assert A.normalize_source(source) == ('#include "/CELLDEV/results/open_headroom/harness/ctl_core.c"\n'
                                          '#include "/CELLDEV/sources/vctl.c"\n')


@pytest.mark.parametrize("target", ["sources/vctl.c", "archive_sources/src/life/kernel.c", "measure.py"])
def test_input_and_released_source_pins_are_checked(complete, target):
    path = complete / target
    path.write_text(path.read_text() + "\n# changed\n")
    with pytest.raises(ValueError, match="differs"):
        A.audit_inputs(complete)


def test_dependency_must_be_complete_and_empty(complete):
    A.save(complete / "dependencies/L/budget.json", {"status": "complete", "running": {"123": "search"}, "queued": []})
    with pytest.raises(ValueError, match="L still"):
        A.audit_inputs(complete)


def test_report_sample_count_and_statistics_are_independently_checked(complete):
    report = A.read(complete / "measurement/report.json")
    report["conditions"]["base_T768"]["fixed_comparisons"]["full_minus_retuned"]["F"]["mean"] += .1
    A.save(complete / "measurement/report.json", report)
    with pytest.raises(ValueError, match="statistic differs"):
        A.analyze(complete)


def test_export_preserves_preparation_and_reanalyzes_raw_copy(complete, tmp_path):
    target = tmp_path / "public"
    shutil.copytree(PREPARATION, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    before = A.read(target / "provenance.json")
    provenance_bytes = (target / "provenance.json").read_bytes()
    summary, vectors = A.analyze(complete)
    A.export(complete, target, summary, vectors)
    assert (target / "prelaunch/provenance.json").read_bytes() == provenance_bytes
    for name, record in before["artifacts"].items():
        assert A.sha(target / "prelaunch" / name) == record["sha256"]
    repeated, saved = A.analyze(target)
    assert repeated == summary and all(A.identical(vectors[key], saved[key]) for key in vectors)
    final = A.read(target / "provenance.json")
    assert final["status"] == "complete"
    for name, record in final["artifacts"].items():
        assert A.sha(target / name) == record["sha256"]
    A.check_archive(target, summary, vectors)
    with pytest.raises(ValueError, match="preparation status"):
        A.export(complete, target, summary, vectors)


def test_export_rejects_changed_prelaunch_bytes_before_copy(complete, tmp_path):
    target = tmp_path / "public"
    shutil.copytree(PREPARATION, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (target / "README.md").write_text("changed")
    summary, vectors = A.analyze(complete)
    with pytest.raises(ValueError, match="prelaunch artifact"):
        A.export(complete, target, summary, vectors)
    assert not (target / "prelaunch").exists()


@pytest.mark.parametrize("fault,message", [("status", "provenance status"), ("hash", "artifact hashes"),
                                          ("size", "artifact hashes"), ("README", "reproduced README")])
def test_final_archive_check_verifies_every_hash_size_status_and_readme(complete, tmp_path, fault, message):
    target = tmp_path / "public"
    shutil.copytree(PREPARATION, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    summary, vectors = A.analyze(complete)
    A.export(complete, target, summary, vectors)
    provenance = A.read(target / "provenance.json")
    if fault == "status":
        provenance["status"] = "incomplete"
    elif fault == "hash":
        provenance["artifacts"]["summary.json"]["sha256"] = "0" * 64
    elif fault == "size":
        provenance["artifacts"]["summary.json"]["bytes"] += 1
    else:
        (target / "README.md").write_text("altered interpretation")
        provenance["artifacts"]["README.md"] = {"sha256": A.sha(target / "README.md"),
                                                   "bytes": (target / "README.md").stat().st_size}
    A.save(target / "provenance.json", provenance)
    with pytest.raises(ValueError, match=message):
        A.check_archive(target, summary, vectors)
