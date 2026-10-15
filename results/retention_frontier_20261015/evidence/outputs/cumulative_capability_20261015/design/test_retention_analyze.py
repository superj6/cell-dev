"""Focused AK accounting/contrast checks; no engine imports, builds or lives."""
import ast
import copy
import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src/life/spec.py").is_file())
STUDY = ROOT / "outputs/autonomous_retention_frontier_20261015"
spec = importlib.util.spec_from_file_location("ak_analyzer", STUDY / "analyze.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def world(abi=3):
    p = json.loads((ROOT / "results/exploratory_reserve_replication_20261014/protocol.json").read_text())
    w = dict(p["world"], visibility_mode=0, visibility_on=0., visibility_off=0., visibility_low=1.)
    if abi == 4:
        w.update(visibility_mode=2, visibility_on=80., visibility_off=5., visibility_low=0.)
    return {"abi": abi, "world": w, "ledger_columns": list(M.LEDGER if abi == 3 else M.ABI4_LEDGER)}


def row(abi=3, mode="normal", n=8):
    rec = world(abi)
    w = rec["world"]
    ledger = np.zeros((n, 57 if abi == 3 else 58), dtype=np.float64)
    vals = {name: ledger[:, i] for i, name in enumerate(M.LEDGER)}
    for key, value in {"n_end": 1, "n_peak": 1, "n_S_end": 1, "t_end": 1024,
                       "t_ext": -1, "live_time": 1024, "live_S": 1024, "samples": 1024}.items():
        vals[key][:] = value
    vals["captures"][:] = np.arange(n) % 3
    vals["clicks"][:] = vals["captures"]
    if mode in ("guard", "extinct"):
        vals["t_end"][:] = 512
        vals["live_time"][:] = vals["live_S"][:] = 512
        vals["samples"][:] = 512
        vals["status"][:] = 4 if mode == "guard" else 1
        if mode == "extinct":
            vals["t_ext"][:] = 512
            vals["n_end"][:] = vals["n_S_end"][:] = 0
            vals["deaths"][:] = 1
    if mode == "growth":
        vals["births"][:] = 1
        vals["n_end"][:] = vals["n_peak"][:] = vals["n_S_end"][:] = 2
        vals["live_time"][:] = vals["live_S"][:] = 1536
        vals["last_birth"][:] = 512
    vals["cost"][:] = M.physical_costs(vals, w)[0]
    vals["income"][:] = w["R_cap"] * vals["captures"]
    if mode == "guard":
        vals["guard_charge"][:] = w["c_live"] * w["n_max"] * 512
    vals["net"][:] = vals["income"] - vals["cost"] - vals["guard_charge"]
    vals["F"][:] = vals["net"] / 1024
    prod = vals["F"] - (w["c_live"] * .5 if mode == "extinct" else 0)
    if abi == 4:
        ledger[:, -1] = vals["captures"]
    seeds = list(range(100, 100 + n))
    raw = {"ledger": ledger, "production_F": prod.copy(), "seeds": np.asarray(seeds, dtype=np.uint64),
           "hashes": np.zeros((n, 5), dtype=np.uint64),
           "cpu_seconds": np.asarray(1.), "wall_seconds": np.asarray(.6)}
    return raw, rec, seeds


@pytest.mark.parametrize("abi", [3, 4])
@pytest.mark.parametrize("mode", ["normal", "guard", "extinct", "growth"])
def test_accounting_retains_normal_guard_extinction_and_growth(abi, mode):
    raw, rec, seeds = row(abi, mode)
    values, health = M.reconstruct(raw, rec, seeds)
    assert len(values) == 75
    assert health["all_fitness_rows_retained"] == len(seeds)
    assert health["guarded"] == (len(seeds) if mode == "guard" else 0)
    assert health["extinct"] == (len(seeds) if mode == "extinct" else 0)
    np.testing.assert_allclose(values["F"], sum(values[k] for k in (
        "capture_income", "ordinary_cost", "guard_cost", "extinction_cost")), atol=1e-12)


@pytest.mark.parametrize("kind", ["production", "raw_f", "cost", "census", "clicks", "incomplete",
                                  "status", "hash_shape", "hash_dtype", "seed_order", "width", "nan",
                                  "low", "negative_cpu"])
def test_concrete_raw_corruptions_fail(kind):
    raw, rec, seeds = row(4)
    if kind == "production":
        raw["production_F"][0] += 1
    elif kind in ("raw_f", "cost", "census", "clicks"):
        column = {"raw_f": "F", "cost": "cost", "census": "births", "clicks": "clicks"}[kind]
        raw["ledger"][0, M.L[column]] += 1
    elif kind == "incomplete":
        raw["ledger"][0, M.L["t_end"]] = 512
    elif kind == "status":
        raw["ledger"][0, M.L["status"]] = 128
    elif kind == "hash_shape":
        raw["hashes"] = raw["hashes"][:, :4]
    elif kind == "hash_dtype":
        raw["hashes"] = raw["hashes"].astype(float)
    elif kind == "seed_order":
        raw["seeds"] = raw["seeds"][::-1]
    elif kind == "width":
        raw["ledger"] = raw["ledger"][:, :57]
    elif kind == "nan":
        raw["ledger"][0, 0] = np.nan
    elif kind == "low":
        raw["ledger"][0, -1] = 1
    else:
        raw["cpu_seconds"] = np.asarray(-1.)
    with pytest.raises(ValueError):
        M.reconstruct(raw, rec, seeds)


def test_initial_cell_and_disjoint_counters_not_old_static_assumptions():
    raw, rec, seeds = row()
    raw["ledger"][:, M.L["arrivals_dropped"]] = 9
    raw["ledger"][:, M.L["rejects_wall"]] = 3
    M.reconstruct(raw, rec, seeds)
    assert np.all(raw["ledger"][:, M.L["births"]] == 0)


def test_complete_paired_matrix_count_and_covariance():
    values, _ = M.reconstruct(*row(n=256))
    rows = {w: {r: {k: v.copy() for k, v in values.items()} for r in M.ROLES} for w in M.WORLDS}
    noise = np.arange(256, dtype=float)
    rows["persistent"]["AI_control"]["captures"] += noise
    rows["turn100"]["AI_control"]["captures"] += noise + 2
    reports, arrays = M.contrasts(rows)
    _, extra = M.retention_diagnostics(rows)
    assert len(reports) == 30 and len(arrays) + len(extra) == 2254
    key = "interaction__turn100_minus_persistent__AI_control_minus_AE_L92__captures"
    np.testing.assert_array_equal(arrays[key], np.full(256, 2.))
    assert reports[key.rsplit("__", 1)[0]]["captures"]["se"] == 0


def test_noninferiority_margin_uses_paired_reference_not_fixed_sample_mean():
    values, _ = M.reconstruct(*row())
    rows = {w: {r: copy.deepcopy(values) for r in M.ROLES} for w in M.WORLDS}
    reference = np.arange(8, dtype=float) + 1
    for w, r in (("pool", "L92"), ("persistent", "AE_L92")):
        rows[w][r]["captures"] = reference
        rows[w]["AI_control"]["captures"] = .9 * reference
    reports, vectors = M.retention_diagnostics(rows)
    for rec in reports.values():
        assert rec["retained_90_percent_vector"]["mean"] == 0
        assert not rec["passes_conventional_10_percent_diagnostic"]
    assert len(vectors) == 4


def test_unchanged_af_accountant_functions():
    old = ast.parse((ROOT / M.ACCOUNTANT_SOURCE).read_text())
    new = ast.parse((STUDY / "analyze.py").read_text())
    names = ("validate_row", "physical_costs", "prices", "stats", "identical")
    for name in names:
        a = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == name)
        b = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == name)
        assert ast.dump(a) == ast.dump(b)


def test_actual_genome_json_raw_hashes_and_no_engine_import():
    ep = json.loads((ROOT / "results/exploratory_reserve_replication_20261014/confirmation/endpoints.json").read_text())
    for role, path in (("AE_L92", "inputs/AE_L92.json"), ("AI_control", "runs/control/best_genome.json")):
        g = M.json_genome(ROOT / "results/exploratory_reserve_replication_20261014" / path)
        assert M.hashlib.sha256(g.tobytes()).hexdigest() == ep["genotype_sha256"][role]
    assert not any(k == "src" or k.startswith("src.") for k in sys.modules)


def test_actual_truth_integer_conversion_and_two_mocked_calls(monkeypatch):
    fixture = next(c for c in json.loads((ROOT / "results/abi4_visibility_20261014/final_truth/truth.json").read_text())[
        "cases"] if c["name"] == "body0_renewal_55040000")
    calls = []
    integer_keys = ("n_max", "e_max", "fabric_R", "oracle_cap", "stuck_a", "stuck_b", "world_kind", "L_max",
                    "stuck_z", "b2_mode", "visibility_mode")

    def world_stub(preset, **kwargs):
        assert all(type(kwargs[k]) is int for k in (*integer_keys, "flags", "fork_flags"))
        return kwargs

    def run_stub(world, seeds, **kwargs):
        calls.append((world, seeds, kwargs))
        return types.SimpleNamespace(ledger=np.asarray([fixture["ledger"]], dtype=np.float64),
                                     hashes=np.asarray([[int(x, 16) for x in fixture["hashes"]]], dtype=np.uint64))

    fake = types.ModuleType("src.life")
    fake.spec = types.SimpleNamespace(INT_WORLD_KEYS=integer_keys, world=world_stub, V4=object())
    fake.build = types.SimpleNamespace(run=run_stub)
    monkeypatch.setitem(sys.modules, "src.life", fake)
    tree = ast.parse((STUDY / "measure.py").read_text())
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "check_visibility_truth")
    namespace = {"read": lambda path: fixture, "STUDY": STUDY,
                 "raw_sha": lambda value: M.hashlib.sha256(value.tobytes()).hexdigest()}
    exec(compile(ast.Module(body=[func], type_ignores=[]), str(STUDY / "measure.py"), "exec"), namespace)
    result = namespace["check_visibility_truth"]()
    assert len(calls) == result["lives"] == 2
    assert not calls[0][2].get("fast") and calls[1][2]["fast"] is True


@pytest.mark.parametrize("corrupt", [None, "namespace", "exit", "reaped_cpu", "row_group", "remaining",
                                     "budget", "attempt", "reason"])
def test_exact_persisted_terminal_contract(monkeypatch, corrupt):
    caps = {"cpu_seconds": 2400, "wall_seconds": 1800, "threads": 2,
            "workers": 1, "cleanup_margin_seconds": 10}
    monitor = {"pid": 100, "ppid": 99, "pgid": 98, "start_ticks": 1000}
    worker = {"pid": 101, "ppid": 100, "pgid": 101, "start_ticks": 1001}
    ns = "pid:[123]"
    release = {"status": "released", "protocol_sha256": "protocol.json", "pid_namespace": ns}
    attempt = {"monitor": monitor, "budget": caps, "protocol_sha256": "protocol.json",
               "release_sha256": "release.json", "pid_namespace": ns}
    budget = {"status": "complete", "exit_code": 0, "worker_exit_code": 0,
              "protocol_sha256": "protocol.json", "release_sha256": "release.json",
              "attempt_sha256": "attempt.json", "running": {}, "queued": [], "cleanup_error": None,
              "reason": None, "error": None, "cpu_seconds": 100., "wall_seconds": 60.,
              "cap_cpu_seconds": 2400., "cap_wall_seconds": 1800., "pid_namespace": ns,
              "process_identities": [dict(monitor, name="monitor"), dict(worker, name="worker")],
              "owned_process_groups": [101], "terminal_cleanup": {
                  "pid_namespace": ns, "same_pid_namespace": True, "checked_in_monitor": True,
                  "all_owned_groups_exited": True, "all_worker_identities_exited": True,
                  "remaining_group_members": [], "remaining_worker_identities": [], "remaining_descendants": []},
              "wait4_receipts": [{"pid": 101, "exit_code": 0, "wait_status": 0,
                                  "user_cpu_seconds": 80., "system_cpu_seconds": 10.}]}
    if corrupt == "namespace":
        release["pid_namespace"] = "pid:[456]"
    elif corrupt == "exit":
        budget["wait4_receipts"][0]["exit_code"] = 1
    elif corrupt == "reaped_cpu":
        budget["wait4_receipts"][0]["user_cpu_seconds"] = 500.
    elif corrupt == "row_group":
        budget["owned_process_groups"] = [999]
    elif corrupt == "remaining":
        budget["terminal_cleanup"]["remaining_descendants"] = [999]
    elif corrupt == "budget":
        budget["cap_cpu_seconds"] = 5000
    elif corrupt == "attempt":
        budget["attempt_sha256"] = "wrong"
    elif corrupt == "reason":
        budget["reason"] = "cpu_budget_exhausted"
    files = {"release.json": release, "attempt.json": attempt, "budget.json": budget}
    monkeypatch.setattr(M, "read", lambda path: files[path.name])
    monkeypatch.setattr(M, "sha", lambda path: path.name)
    if corrupt:
        with pytest.raises(ValueError):
            M.verify_terminal(Path("/synthetic"), {"budget": caps})
    else:
        assert M.verify_terminal(Path("/synthetic"), {"budget": caps}) == budget
