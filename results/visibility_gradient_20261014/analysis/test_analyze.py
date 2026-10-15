"""One complete synthetic138-row archive and focused completeness/selection failures; no simulation."""
import importlib.util
import shutil
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("gradient_complete_analysis", HERE / "analyze.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SOURCE = HERE.parent if (HERE.parent / "protocol.json").is_file() else HERE.parent / "autonomous_visibility_gradient_20261014"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(M.json_bytes(value))


def stats(values):
    return {"mean": float(values.mean()), "se": float(values.std(ddof=1) / np.sqrt(len(values))), "n": len(values)}


def row(p, parent, stage, index):
    n, w = M.N[stage], p["world"]
    r = {name: np.zeros(n, dtype=np.float64) for name in M.A.COLS}
    for key, value in dict(captures=1 + (index in (1, 2)) + np.arange(n) % 2, low_light_captures=1,
                           misses=1, births=2, claims=2, n_end=3, n_peak=3, n_S_end=1, n_M_end=2,
                           live_time=2 * w["T"], live_S=w["T"], live_M=w["T"], last_birth=w["T"] / 2,
                           t_end=w["T"], t_ext=-1, window=w["T"], rec_cand=4, rec_accept=2,
                           rec_events=2, spikes=4, contact_events=2, kappa_sum=2, rec_gain=2).items():
        r[key][:] = value
    r["clicks"] = r["captures"] + r["misses"]
    # Scalar accountant, independently of the production scorer and reader.
    for i in range(n):
        cost = w["c_live"] * r["live_time"][i]
        for price, column in (("c_spike", "spikes"), ("c_tw", "kappa_sum"), ("c_msg", "contact_events"),
                              ("c_div", "claims"), ("c_sec", "sec_int"), ("c_miss", "misses"), ("c_rec", "rec_gain")):
            cost = cost + w[price] * r[column][i]
        cost = cost + 0.0
        r["cost"][i], r["income"][i] = cost, w["R_cap"] * r["captures"][i]
        r["net"][i] = r["income"][i] - cost - 0.0
        r["F_kernel"][i] = r["net"][i] / w["T"]
    r["F"] = r["F_kernel"] - r["extinct_charge"]
    r["ledger"] = np.stack([r["F_kernel" if key == "F" else key] for key in M.A.LEDGER], axis=1)
    identity = dict(protocol_sha256=M.REVIEWED_PROTOCOL_SHA256, background=parent, stage=stage,
                    genome_index=index, genome_sha256=p["panel_genotype_sha256"][parent][index], seeds=p["seeds"][stage])
    r.update(seeds=np.asarray(p["seeds"][stage], dtype=np.uint64), genome_index=np.asarray(index),
             identity=np.asarray(M.canonical(identity)), cpu_seconds=np.asarray(.01), wall_seconds=np.asarray(.02))
    return r


def comparison(a, b, w):
    columns = ("F", "F_kernel", "n_end", "n_H_end", "live_time", "spikes", "packets", "misses", "clicks",
               "captures", "path", "zone_samples", "samples", "low_light_captures")
    r = {key: stats(a[key] - b[key]) for key in columns}
    r["bright_captures"] = stats(a["captures"] - a["low_light_captures"] - b["captures"] + b["low_light_captures"])
    parts = dict(income=(a["income"] - b["income"]) / w["T"], cost_saving=(b["cost"] - a["cost"]) / w["T"],
                 guard_charge_saving=(b["guard_charge"] - a["guard_charge"]) / w["T"],
                 extinction_charge_saving=b["extinct_charge"] - a["extinct_charge"])
    parts["accounting_residual"] = a["F"] - b["F"] - sum(parts.values())
    r["fitness_contributions"] = {key: stats(value) for key, value in parts.items()}
    r["capture_income"] = stats(parts["income"])
    r["cost_saving_components"] = {name: stats(price * b[column] / w["T"] - price * a[column] / w["T"])
                                    for name, column, price in M.A.prices(w)}
    r["guard_fraction"] = dict(parent=0.0, winner=0.0)
    r["above_3se"] = r["F"]["mean"] > 3 * r["F"]["se"]
    r["interpretation"] = "Synthetic report only."
    return r


def construct(base, chosen=1):
    p = M.read(SOURCE / "protocol.json")
    for name in (*p["file_pins"], "protocol.json"):
        dest = base / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / name, dest)
    for name in p["production_pins"]:
        dest = base / "production" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(M.external(SOURCE, name), dest)
    for name in ("analyze.py", "offline_accounting.py", "genetic_replay.py", "genetic_replay.json"):
        dest = base / "analysis" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / name, dest)
    dependency = "outputs/synthetic_prior/budget.json"
    save(base / "original" / dependency, dict(status="complete", running={}, queued=[], cpu_seconds=5))
    clearance = dict(status="cleared", all_processes_exited=True,
                     budget_pins={dependency: M.sha(base / "original" / dependency)},
                     processes=[dict(pid=999000, start_ticks=1)], process_groups=[999000])
    save(base / "resource_clearance.json", clearance)
    ready_pins = dict(p["file_pins"])
    for name in ("protocol.json", "monitor.py", "resource_clearance.json", "analysis/analyze.py",
                 "analysis/offline_accounting.py", "analysis/genetic_replay.py", "analysis/genetic_replay.json"):
        ready_pins[name] = M.sha(base / name)
    ready = dict(status="released", source_pins=ready_pins, production_pins=p["production_pins"])
    save(base / "ready.json", ready)
    monitor = dict(pid=999001, ppid=1, pgid=999001, sid=999001, start_ticks=2)
    save(base / "attempt.json", dict(monitor=monitor, ready_sha256=M.sha(base / "ready.json")))
    kernels = {}
    for name in ("False", "True"):
        path = base / "build-cache" / (name + ".so")
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"EXPLICITLY SYNTHETIC NONEXECUTABLE LIBRARY " + name.encode())
        kernels[name] = M.sha(path)
    startup = dict(identity=dict(p["expected_startup_metadata"], kernels=kernels, golden=M.GOLDEN),
                   preexpected_fields=sorted(p["expected_startup_metadata"]), newly_captured_fields=["kernels", "golden"],
                   numerical_identity_invocations=1, golden_lives=M.GOLDEN_SCOPE)
    save(base / "startup_identity.json", startup)
    selection = {parent: dict(genome_row=chosen, raw_sha256=p["panel_genotype_sha256"][parent][chosen]) for parent in M.PARENTS}
    save(base / "selection.json", selection)
    snapshots = {stage: {} for stage in ("calibration_complete", "screens_complete")}
    report = dict(status="complete", scope=M.SCOPE, research_genome_lives=6208, validation_lives=10,
                  total_genome_lives=6218, row_cpu_seconds=1.38, row_index_sha256={}, screen={}, confirmation={})
    for parent in M.PARENTS:
        index, rows = {}, {}
        for stage, indices in (("calibration", [0, 1]), ("screen", list(range(65))), ("confirm", [0, chosen])):
            rows[stage] = {}
            folder = base / "measurement" / parent / stage
            folder.mkdir(parents=True)
            for i in indices:
                r = row(p, parent, stage, i)
                path = folder / f"row_{i:04d}.npz"
                np.savez_compressed(path, **r)
                index[stage + "/" + path.name] = dict(sha256=M.sha(path), cpu_seconds=.01)
                rows[stage][i] = r
            np.savez_compressed(folder / "scores.npz", seeds=np.asarray(p["seeds"][stage], dtype=np.uint64),
                                genome_indices=np.asarray(indices),
                                **{key: np.stack([rows[stage][i][key] for i in indices]) for key in M.A.COLS})
            if stage != "confirm":
                snapshot = dict(index)
                snapshots["calibration_complete" if stage == "calibration" else "screens_complete"][parent] = snapshot
        save(base / "measurement" / parent / "row_index.json", index)
        report["row_index_sha256"][parent] = M.sha(base / "measurement" / parent / "row_index.json")
        report["screen"][parent] = dict(selected=selection[parent], complete_rows=65,
            row_index_sha256=M.hashlib.sha256(M.json_bytes(snapshots["screens_complete"][parent])).hexdigest())
        report["confirmation"][parent] = comparison(rows["confirm"][chosen], rows["confirm"][0], p["world"])
    rates = dict.fromkeys(M.PARENTS, .005)
    projection = dict(feasible=True, batch_max_cpu_per_life=rates, startup_cpu_seconds=20,
                      screen_projection_cpu_seconds=20 + 1.5 * 2080 * sum(rates.values()),
                      confirmation_projection_cpu_seconds=1.5 * 1024 * sum(rates.values()))
    save(base / "calibration_projection.json", projection)
    receipts = {}
    for phase, cpu in (("calibration_complete", 20), ("screens_complete", 50)):
        request = dict(protocol_sha256=M.REVIEWED_PROTOCOL_SHA256,
                       row_index_sha256={parent: M.hashlib.sha256(M.json_bytes(snapshots[phase][parent])).hexdigest()
                                         for parent in M.PARENTS})
        if phase == "calibration_complete":
            request.update(validation_lives=10, startup_identity_sha256=M.sha(base / "startup_identity.json"))
            artifacts = {"startup_identity.json": M.sha(base / "startup_identity.json")}
        else:
            request.update(scientific_genome_lives=4160, selection_sha256=M.sha(base / "selection.json"))
            artifacts = {name: M.sha(base / name) for name in ("selection.json", "calibration_projection.json")}
        save(base / "requests" / (phase + ".json"), request)
        receipts[phase] = dict(status="allowed", protocol_sha256=M.REVIEWED_PROTOCOL_SHA256,
                               attempt_sha256=M.sha(base / "attempt.json"),
                               request_sha256=M.sha(base / "requests" / (phase + ".json")),
                               cpu_seconds=cpu, row_snapshot=snapshots[phase], artifact_pins=artifacts)
        save(base / "monitor_receipts" / (phase + ".json"), receipts[phase])
    save(base / "report.json", report)
    budget = dict(status="complete", exit_code=0, phase="confirmation", cap_cpu_seconds=5400,
                   startup_screen_cap_cpu_seconds=3400, confirmation_reserve_cpu_seconds=2000,
                   cpu_seconds=70, startup_screen_cpu_seconds=50, running={}, queued=[],
                   completed=[dict(name="gradient", exit_code=0)], ready=ready, affinity=[0, 1],
                   process_identities=[dict(monitor, name="monitor"),
                                       dict(name="gradient", pid=999002, ppid=999001, pgid=999002, sid=999002, start_ticks=3)],
                   owned_process_groups=[999002], phase_receipts=receipts, reason=None)
    save(base / "budget.json", budget)
    return base


@pytest.fixture(scope="session")
def template(tmp_path_factory):
    return construct(tmp_path_factory.mktemp("complete_template"))


@pytest.fixture
def study(template, tmp_path):
    base = tmp_path / "study"
    shutil.copytree(template, base)
    return base


def rejected(base):
    summary, vectors = M.analyze(base)
    assert summary["status"] == "incomplete", summary
    assert summary["scientific_outcomes_emitted"] is False and vectors == {}
    assert "backgrounds" not in summary
    return summary["error"]


def modify(base, name, fn):
    record = M.read(base / name)
    fn(record)
    save(base / name, record)


def test_complete_original_panel_full_rows_and_paired_statistics(study):
    summary, vectors = M.analyze(study)
    assert summary["status"] == "complete", summary
    assert summary["total_lives"] == 6218
    for parent in M.PARENTS:
        item = summary["backgrounds"][parent]
        assert item["selection"]["genome_row"] == 1
        assert len(item["screen_F"]) == 65
        assert item["confirmation"]["columns"]["F"]["mean"] == pytest.approx(500 / 1024)
        assert len(vectors[parent + "__F"]) == 512


def test_tied_later_row_is_not_an_allowed_substitution(tmp_path):
    assert "selection" in rejected(construct(tmp_path / "wrong_selection", chosen=2))


@pytest.mark.parametrize("name", ["measurement/D90/confirm/row_0001.npz", "measurement/L92/screen/row_0064.npz",
                                  "monitor_receipts/screens_complete.json", "startup_identity.json", "build-cache/True.so"])
def test_partial_records_emit_no_scientific_outcomes(study, name):
    (study / name).unlink()
    rejected(study)


@pytest.mark.parametrize("key,value", [("status", "incomplete"), ("exit_code", 1), ("cpu_seconds", 5390),
                                      ("startup_screen_cpu_seconds", 3390), ("running", {"999002": "gradient"}),
                                      ("queued", ["gradient"]), ("cleanup_error", "survivor"),
                                      ("phase", "startup_screen")])
def test_monitor_resource_or_completion_failure_blocks_all_results(study, key, value):
    modify(study, "budget.json", lambda x: x.update({key: value}))
    rejected(study)


def test_stale_earlier_row_snapshot_is_rejected(study):
    modify(study, "budget.json", lambda x: x["phase_receipts"]["calibration_complete"]["row_snapshot"]["D90"]
           ["calibration/row_0000.npz"].update(cpu_seconds=.02))
    assert "receipt" in rejected(study)


def test_wrong_retained_golden_is_rejected(study):
    modify(study, "startup_identity.json", lambda x: x["identity"]["golden"].update(all="0" * 16))
    assert "golden" in rejected(study)


def test_stale_aggregate_cannot_replace_raw_rows(study):
    path = study / "measurement/D90/screen/scores.npz"
    rows = M.npz(path)
    rows["F"][1, 0] += 1
    np.savez_compressed(path, **rows)
    assert "aggregate" in rejected(study)


def test_worker_summary_is_independently_recomputed(study):
    modify(study, "report.json", lambda x: x["confirmation"]["D90"]["F"].update(mean=100))
    assert "estimate" in rejected(study)


def test_raw_confirmation_cpu_cannot_exceed_its_phase(study):
    modify(study, "budget.json", lambda x: x.update(cpu_seconds=50.01))
    assert "CPU exceeds" in rejected(study)


def test_frozen_parent_table_cannot_change(study):
    path = study / "inputs/D90/genomes.npy"
    a = np.load(path, allow_pickle=False)
    a[0, 0] += 1
    np.save(path, a, allow_pickle=False)
    assert "pinned input" in rejected(study)


def test_an_unstarted_preparation_has_no_outcomes(tmp_path):
    (tmp_path / "protocol.json").write_bytes((SOURCE / "protocol.json").read_bytes())
    rejected(tmp_path)
