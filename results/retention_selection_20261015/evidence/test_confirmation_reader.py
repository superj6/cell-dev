"""Focused AL delta checks; no compiler, life call or genotype draw."""
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").is_file())
STUDY = ROOT / "outputs/autonomous_retention_selection_20261015"
AK = ROOT / "outputs/autonomous_retention_frontier_20261015"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = load("al_reader", STUDY / "analyze.py")


def test_accounting_and_truth_functions_are_exact_AK():
    pairs = (("analyze.py", ("validate_row", "physical_costs", "prices", "stats", "identical", "reconstruct")),
             ("measure.py", ("check_visibility_truth",)))
    for filename, names in pairs:
        old, new = ast.parse((AK / filename).read_text()), ast.parse((STUDY / filename).read_text())
        for name in names:
            a = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == name)
            b = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == name)
            assert ast.dump(a) == ast.dump(b)


def rows():
    # Reuse the already tested literal ledger construction, not another fixture archive.
    fixture = load("ak_test_row", ROOT / "outputs/cumulative_capability_20261015/design/test_retention_analyze.py")
    values, _ = M.reconstruct(*fixture.row(n=256))
    return {w: {r: copy.deepcopy(values) for r in M.ROLES} for w in M.WORLDS}


def test_all_fixed_contrasts_and_combined_context_pairing():
    data = rows()
    noise = np.arange(256, dtype=float)
    data["persistent"][M.ROLES[2]]["captures"] += noise
    data["turn100_blink80_5"][M.ROLES[2]]["captures"] += noise + 2
    reports, arrays = M.contrasts(data)
    _, extra = M.retention_diagnostics(data)
    assert len(reports) == 30 and len(arrays) + len(extra) == 2254
    key = "interaction__turn100_blink80_5_minus_persistent__mixture_final_minus_AI_control_start"
    np.testing.assert_array_equal(arrays[key + "__captures"], np.full(256, 2.))
    assert reports[key]["captures"]["se"] == 0


def test_relative_advantage_cannot_masquerade_as_recovery():
    data = rows()
    for world in M.WORLDS:
        for role in M.ROLES:
            data[world][role]["captures"] = np.full(256, 10.)
    data["pool"][M.ROLES[1]]["captures"][:] = 5
    data["pool"][M.ROLES[2]]["captures"][:] = 9
    result = M.verdicts(data)
    assert result["relative_POOL_advantage"]
    assert not result["actual_POOL_recovery"]
    assert not result["partial_POOL_recovery_with_conventional_persistent_retention"]
    assert not result["strict_simultaneous_capture_gain"]


def test_ten_percent_margin_exact_boundary_is_not_pass():
    data = rows()
    original = np.arange(256, dtype=float) + 1
    data["persistent"][M.ROLES[0]]["captures"] = original
    for role in M.ROLES[1:]:
        data["persistent"][role]["captures"] = .9 * original
    reports, vectors = M.retention_diagnostics(data)
    assert len(vectors) == 4
    assert all(not r["passes_conventional_10_percent_diagnostic"] for r in reports.values())
    assert all(r["retained_90_percent_vector"]["mean"] == 0 for r in reports.values())


def test_strict_simultaneous_gain_kept_separate_from_tolerated_loss():
    data = rows()
    for world in M.WORLDS:
        data[world][M.ROLES[0]]["captures"] = np.full(256, 10.)
        data[world][M.ROLES[1]]["captures"] = np.full(256, 10.)
        data[world][M.ROLES[2]]["captures"] = np.full(256, 11.)
    data["persistent"][M.ROLES[2]]["captures"][:] = 9.5
    result = M.verdicts(data)
    assert result["actual_POOL_recovery"]
    assert result["partial_POOL_recovery_with_conventional_persistent_retention"]
    assert not result["strict_simultaneous_capture_gain"]
    assert not result["ancestral_L92_restoration_tested"]


def test_measure_has_one_standard_identity_and_freezes_before_rows(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY))
    worker = load("al_worker", STUDY / "measure.py")
    good = {"generation": 4, "curves": [{"gen": i, "pop_invalid": 0, "pop_mismatch": 0,
                                           "recheck_invalid": 0} for i in range(4)]}
    assert worker.validate_search_state(good) == {"pop_invalid": 0., "pop_mismatch": 0., "recheck_invalid": 0.}
    for mutation in ("incomplete", "nan", "invalid"):
        bad = copy.deepcopy(good)
        if mutation == "incomplete":
            bad["generation"] = 3
        else:
            bad["curves"][0]["pop_invalid"] = float("nan") if mutation == "nan" else 1
        with pytest.raises(ValueError):
            worker.validate_search_state(bad)
    source = ast.parse((STUDY / "measure.py").read_text())
    calls = [n for n in ast.walk(source) if isinstance(n, ast.Call)]
    assert sum(isinstance(n.func, ast.Attribute) and n.func.attr == "numerical_identity" for n in calls) == 1
    measure = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "measure")
    freeze = next(n.lineno for n in ast.walk(measure) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name) and n.func.id == "freeze_endpoints")
    loops = [n.lineno for n in ast.walk(measure) if isinstance(n, ast.For)]
    assert freeze < min(loops)
    assert not any(name.startswith(("src.life.build", "src.run", "src.evolve")) for name in sys.modules)


def terminal_fixture(monkeypatch):
    base = Path("/synthetic_AL")
    docs = {}
    def put(name, value):
        docs[str(base / name)] = value
    def digest(path):
        return hashlib.sha256(json.dumps(docs[str(path)], sort_keys=True).encode()).hexdigest()
    monkeypatch.setattr(M, "read", lambda path: copy.deepcopy(docs[str(path)]))
    monkeypatch.setattr(M, "sha", digest)
    namespace = "pid:[4026531836]"
    budget_spec = {"cpu_seconds": 5400, "wall_seconds": 3600, "search_cpu_seconds": 3600,
                   "confirmation_cpu_seconds": 1800, "threads": 2, "workers": 1,
                   "cleanup_margin_seconds": 10, "rss_bytes": 4 * 1024**3,
                   "minimum_available_bytes": 4 * 1024**3, "address_space_bytes": 8 * 1024**3}
    protocol = {"budget": budget_spec}
    put("protocol.json", protocol)
    pd = digest(base / "protocol.json")
    put("release.json", {"status": "released", "protocol_sha256": pd, "pid_namespace": namespace})
    rd = digest(base / "release.json")
    monitor = {"pid": 100, "ppid": 90, "pgid": 100, "start_ticks": 1000}
    phases = (*M.ARMS, "confirmation")
    commands = {p: ["python", p] for p in phases}
    put("attempt.json", {"monitor": monitor, "pid_namespace": namespace, "protocol_sha256": pd,
                         "release_sha256": rd, "commands": commands, "budget": budget_spec})
    cleanup = {"pid_namespace": namespace, "checked_in_monitor": True, "same_pid_namespace": True,
               "all_owned_groups_exited": True, "all_worker_identities_exited": True,
               "remaining_group_members": [], "remaining_worker_identities": [], "remaining_descendants": []}
    workers, all_receipts, records = [], [], {}
    for i, phase in enumerate(phases):
        worker = {"pid": 101 + i, "ppid": 100, "pgid": 101 + i, "start_ticks": 1001 + i, "name": phase}
        workers.append(worker)
        cap = 3600 if i < 2 else 2010
        pb = {"cpu_seconds": cap, "wall_seconds": 3600 - i * 100, "threads": 2, "workers": 1,
              "cleanup_margin_seconds": 10, "rss_bytes": 4 * 1024**3,
              "minimum_available_bytes": 4 * 1024**3, "address_space_bytes": 8 * 1024**3}
        put(f"execution/{phase}/attempt.json", {"monitor": monitor, "pid_namespace": namespace,
             "protocol_sha256": pd, "release_sha256": rd, "command": commands[phase], "budget": pb})
        receipts = [{"pid": worker["pid"], "wait_status": 0, "exit_code": 0,
                     "user_cpu_seconds": 45., "system_cpu_seconds": 5.}]
        all_receipts.extend(receipts)
        record = {"status": "complete", "exit_code": 0, "worker_exit_code": 0,
                  "running": {}, "queued": [], "reason": None, "error": None, "cleanup_error": None,
                  "cpu_seconds": 100 * (i + 1), "wall_seconds": 90, "cap_cpu_seconds": cap,
                  "cap_wall_seconds": pb["wall_seconds"], "pid_namespace": namespace,
                  "protocol_sha256": pd, "release_sha256": rd,
                  "attempt_sha256": digest(base / f"execution/{phase}/attempt.json"),
                  "process_identities": [{**monitor, "name": "monitor"}, {**worker, "name": "worker"}],
                  "owned_process_groups": [worker["pid"]], "terminal_cleanup": copy.deepcopy(cleanup),
                  "wait4_receipts": receipts, "cap_rss_bytes": 4 * 1024**3,
                  "minimum_available_bytes": 4 * 1024**3, "worker_address_space_bytes": 8 * 1024**3,
                  "peak_owned_rss_bytes": 100000}
        name = f"execution/{phase}/budget.json"
        put(name, record)
        records[phase] = {"path": name, "sha256": digest(base / name)}
    global_record = {**copy.deepcopy(record), "cpu_seconds": 310., "wall_seconds": 300.,
                     "cap_cpu_seconds": 5400, "cap_wall_seconds": 3600,
                     "search_cpu_cap": 3600, "confirmation_cpu_cap": 1800,
                     "search_cpu_seconds": 210., "confirmation_cpu_seconds": 100.,
                     "phase": "confirmation", "attempt_sha256": digest(base / "attempt.json"),
                     "process_identities": [{**monitor, "name": "monitor"}, *workers],
                     "owned_process_groups": [w["pid"] for w in workers],
                     "phase_records": records, "wait4_receipts": all_receipts}
    put("budget.json", global_record)
    put("measurement_complete.json", {"fixture": True})
    for arm in M.ARMS:
        put(f"runs/{arm}/search_complete.json", {"fixture": arm})
    put("study_complete.json", {"status": "complete", "research_lives": 13388, "startup_lives": 8,
        "total_calls": 13396, "protocol_sha256": pd,
        "measurement_complete_sha256": digest(base / "measurement_complete.json"),
        "search_complete_pins": {a: digest(base / f"runs/{a}/search_complete.json") for a in M.ARMS}})
    return base, protocol, docs, digest


def test_actual_three_phase_terminal_contract(monkeypatch):
    base, protocol, _, _ = terminal_fixture(monkeypatch)
    assert M.verify_terminal(base, protocol)["cpu_seconds"] == 310


@pytest.mark.parametrize("kind", ["missing_phase", "reserve", "wrong_parent", "cleanup", "rss", "address", "reaping"])
def test_concrete_terminal_corruptions(monkeypatch, kind):
    base, protocol, docs, digest = terminal_fixture(monkeypatch)
    budget = docs[str(base / "budget.json")]
    path = "execution/confirmation/budget.json"
    phase = docs[str(base / path)]
    if kind == "missing_phase":
        del budget["phase_records"]["balanced_mixture"]
    elif kind == "reserve":
        budget["confirmation_cpu_seconds"] = 1800.
    elif kind == "wrong_parent":
        phase["process_identities"][1]["ppid"] += 1
    elif kind == "cleanup":
        phase["terminal_cleanup"]["remaining_descendants"] = [999]
    elif kind == "rss":
        phase["peak_owned_rss_bytes"] = 4 * 1024**3
    elif kind == "address":
        phase["worker_address_space_bytes"] = 16 * 1024**3
    else:
        phase["wait4_receipts"][0]["wait_status"] = 1
    budget["phase_records"]["confirmation"]["sha256"] = digest(base / path)
    with pytest.raises(ValueError):
        M.verify_terminal(base, protocol)
