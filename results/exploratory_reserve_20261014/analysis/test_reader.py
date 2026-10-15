"""Focused AH three-role/source-contract checks; no engine calls or genetic draws."""

import __future__

import ast
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
s = importlib.util.spec_from_file_location("AH_reader_tests", HERE / "analyze.py")
M = importlib.util.module_from_spec(s)
s.loader.exec_module(M)
ROOT = next((p for p in HERE.parents if (p / "src/life/spec.py").is_file()), None)
SOURCE = (
    HERE.parent if (HERE.parent / "measure.py").is_file() else ROOT / "outputs/autonomous_exploratory_reserve_20261014"
)


def world():
    return dict(
        t0=0,
        T=1024,
        t_open=0,
        world_kind=1,
        b2_amp=0,
        b2_value=0,
        c_live=0.001,
        c_spike=0.02,
        c_tw=0.03,
        c_msg=0.04,
        c_div=0.05,
        c_sec=0.06,
        c_miss=0.07,
        c_rec=0.08,
        R_cap=500,
        n_max=128,
    )


def row(captures, seeds=None):
    captures = np.broadcast_to(captures, (512,)).astype(np.float64).copy()
    w = world()
    r = {key: np.zeros(512, dtype=np.float64) for key in M.A.COLS}
    for key, value in {
        "captures": captures,
        "clicks": captures,
        "n_end": 1,
        "n_peak": 1,
        "n_S_end": 1,
        "live_time": 1024,
        "live_S": 1024,
        "t_end": 1024,
        "t_ext": -1,
        "window": 1024,
        "spikes": 2,
    }.items():
        r[key][:] = value
    r["income"] = w["R_cap"] * r["captures"]
    r["cost"], _ = M.A.physical_costs(r, w)
    r["net"] = r["income"] - r["cost"] - r["guard_charge"]
    r["F_kernel"] = r["net"] / w["T"]
    r["F"] = r["F_kernel"] - r["extinct_charge"]
    r["ledger"] = np.stack([r["F_kernel" if name == "F" else name] for name in M.A.LEDGER], axis=1)
    r.update(
        seeds=np.arange(512, dtype=np.uint64) if seeds is None else seeds,
        cpu_seconds=np.asarray(0.01),
        wall_seconds=np.asarray(0.02),
    )
    return r


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(M.json_bytes(value))


def pure_functions(path, names, extra=None):
    source = ast.parse(path.read_text())
    functions = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in functions} == set(names)
    env = {
        "np": np,
        "spec": SimpleNamespace(b2_cost=lambda w: max(0.0, -w.b2_value), STATUS={"guard_cells": 2, "guard_events": 4}),
    }
    if extra:
        env.update(extra)
    exec(
        compile(
            ast.Module(body=functions, type_ignores=[]), str(path), "exec", flags=__future__.annotations.compiler_flag
        ),
        env,
    )
    return env


def actual_comparison(a, b, w):
    # Execute only these reviewed pure report functions, not their import blocks.
    gates = pure_functions(M.external(SOURCE, "scripts/taskvar_gates.py"), ["paired"])
    confirm = pure_functions(
        M.external(SOURCE, "scripts/taskvar_confirm.py"), ["compare_rows"], {"paired": gates["paired"]}
    )
    adapter = SimpleNamespace(
        LEDGER=M.A.LEDGER,
        column_cost=lambda led, w: M.A.physical_costs({k: led[:, j] for j, k in enumerate(M.A.LEDGER)}, vars(w))[0],
    )
    scoring = pure_functions(
        SOURCE / "scoring.py",
        ["comparison"],
        {"ABI": adapter, "paired": gates["paired"], "compare_rows": confirm["compare_rows"]},
    )
    return scoring["comparison"](a, b, SimpleNamespace(**w))


@pytest.fixture
def complete(monkeypatch):
    # All arrays stay in memory: no synthetic NPZ tree or candidate namespace.
    base = Path("/synthetic_AH_unregistered")
    folder = base / "confirmation"
    p = {"world": world(), "confirmation": {"seeds": list(range(512))}}
    ep = {"genotype_sha256": {label: "synthetic-" + label for label in M.LABELS}}
    rows, arrays, index = {}, {}, {}
    for i, label in enumerate(M.LABELS):
        r = row(2 + i + np.arange(512) % 3)
        r["genome_index"] = np.asarray(i)
        r["identity"] = np.asarray(
            M.canonical(
                {
                    "protocol_sha256": M.PROTOCOL_SHA,
                    "stage": "confirmation",
                    "endpoints_sha256": "synthetic_sha",
                    "role": label,
                    "genome_index": i,
                    "genome_sha256": ep["genotype_sha256"][label],
                    "seeds": p["confirmation"]["seeds"],
                }
            )
        )
        name = f"persistent/row_{i:04d}.npz"
        rows[i] = r
        arrays[str(folder / name)] = r
        index[name] = {"sha256": "synthetic_sha", "cpu_seconds": 0.01}
    arrays[str(folder / "persistent/scores.npz")] = dict(
        seeds=np.arange(512, dtype=np.uint64),
        genome_indices=np.arange(3),
        **{k: np.stack([rows[i][k] for i in range(3)]) for k in M.A.COLS},
    )
    report = {
        "status": "complete",
        "report_only": True,
        "genome_lives": 1536,
        "paired_seeds": 512,
        "confirmation_startup_validation_lives": 2,
        "protocol_sha256": M.PROTOCOL_SHA,
        "endpoints_sha256": "synthetic_sha",
        "genotypes_sha256": "synthetic_sha",
        "row_cpu_seconds": 0.03,
    }
    documents = {str(folder / "row_index.json"): index, str(folder / "report.json"): report}
    monkeypatch.setattr(M, "npz", lambda path: copy.deepcopy(arrays[str(path)]))
    monkeypatch.setattr(M, "read", lambda path: copy.deepcopy(documents[str(path)]))
    monkeypatch.setattr(M, "sha", lambda path: "synthetic_sha")
    monkeypatch.setattr(Path, "rglob", lambda self, pattern: iter(folder / name for name in index))
    return base, p, ep, {"cpu_seconds": 100.0, "search_stage_cpu_seconds": 50.0}, rows


def test_three_rows_three_contrasts_actual_producer_reports(complete):
    base, p, ep, budget, expected = complete
    rows, _, cpu, _ = M.load_rows(base, p, ep, budget)
    assert len(rows) == 3 and cpu == pytest.approx(0.03)
    vectors = {}
    for category, pairs in M.PAIRS.items():
        for a, b in pairs:
            saved = actual_comparison(rows[a], rows[b], p["world"])
            result, terms = M.comparison(rows[a], rows[b], saved, p["world"])
            assert result["columns"]["F"]["mean"] == pytest.approx((rows[a]["F"] - rows[b]["F"]).mean())
            assert len(terms) == 73
            vectors.update({category + "__" + M.LABELS[a] + "__" + k: v for k, v in terms.items()})
    assert len(vectors) == 219 and all(v.shape == (512,) for v in vectors.values())


@pytest.mark.parametrize(
    "kind",
    [
        "raw58",
        "named_F",
        "identity_role",
        "seed_order",
        "genome_index",
        "negative_timing",
        "aggregate_order",
        "wrong_budget",
        "wrong_call_count",
    ],
)
def test_specific_corruptions(complete, monkeypatch, kind):
    base, p, ep, budget, rows = complete
    budget = copy.deepcopy(budget)
    old_npz, old_read = M.npz, M.read

    def changed(path):
        r = old_npz(path)
        if Path(path).name == "row_0000.npz":
            if kind == "raw58":
                r["ledger"] = np.column_stack([r["ledger"], np.zeros(512)])
            elif kind == "named_F":
                r["F"][0] += 1
            elif kind == "identity_role":
                r["identity"] = np.asarray(str(r["identity"]).replace("AE_L92", "AH_control"))
            elif kind == "seed_order":
                r["seeds"] = r["seeds"][::-1]
            elif kind == "genome_index":
                r["genome_index"] = np.asarray(2)
            elif kind == "negative_timing":
                r["cpu_seconds"] = np.asarray(-1.0)
        if Path(path).name == "scores.npz" and kind == "aggregate_order":
            r["genome_indices"] = np.arange(3)[::-1]
        return r

    def changed_read(path):
        r = old_read(path)
        if Path(path).name == "report.json" and kind == "wrong_call_count":
            r["genome_lives"] = 2048
        return r

    monkeypatch.setattr(M, "npz", changed)
    monkeypatch.setattr(M, "read", changed_read)
    if kind == "wrong_budget":
        budget["cpu_seconds"] = 50.01
    with pytest.raises(ValueError):
        M.load_rows(base, p, ep, budget)


def test_real_Z_four_field_identity_and_current_monitor_ast():
    path = (
        (ROOT / "results/visibility_continuation_20261014/operations/budget.json")
        if ROOT
        else SOURCE / "inputs/AE/budget.json"
    )
    budget = M.read(path)
    attempt = {"monitor": M.identity(budget["process_identities"][0])}
    M.owned_processes(attempt, budget, [x["name"] for x in budget["process_identities"][1:]])
    tree = ast.parse((SOURCE / "run_budgeted.py").read_text())
    f = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_identity")
    r = next(n.value for n in ast.walk(f) if isinstance(n, ast.Return))
    assert [ast.literal_eval(k) for k in r.keys] == ["pid", "ppid", "pgid", "start_ticks"]


def test_exact_one_confirmation_golden_call_and_fixed_three_roles():
    tree = ast.parse((SOURCE / "measure.py").read_text())
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "numerical_identity"
    ]
    assert len(calls) == 1
    labels = next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "LABELS" for t in n.targets)
    )
    assert labels == M.LABELS
    source = (SOURCE / "scoring.py").read_text()
    assert "ABI = spec.V3" in source and "THREADS = 2" in source
    assert "low_light_captures" not in source


def test_exact_unchanged_accountant_and_genetic_helpers():
    assert M.sha(HERE / "offline_accounting.py") == "5a20bb4966660ff5d44b74b67c6e124b9bbe1ef6ff03ea7c9cf280eba03dac0b"
    assert M.sha(HERE / "helpers/genetics.py") == "8fd717bdecb5f0e073e04838bbf286a4a968924bc9848b55c5a8d2b2055f4139"
    assert len(M.A.LEDGER) == 57 and len(M.A.COLS) == 60


def test_native_schedule_counts_without_draws_or_reserved_seeds():
    ids = []
    # Artificial seed for pure arithmetic, never proposed or registered for research.
    seed = 1
    for g in range(4):
        ids.extend(M.native_seed(seed, 1, g, j) for j in range(7))
        if g in (0, 3):
            ids.extend(M.native_seed(seed, 3, g, j) for j in range(16))
    ids.extend(M.native_seed(seed, 5, index, j) for index in (0, 1) for j in range(2))
    assert len(ids) == len(set(ids)) == 64
    assert 2 * (4 * (256 * 3 + 64 * 4) + 32 + 6) == 8268
    assert 8268 + 3 * 512 + 3 * 2 == 9810


def test_unregistered_refuses_outcomes(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "PROTOCOL_SHA", None)
    summary, vectors = M.analyze(tmp_path)
    assert summary["status"] == "incomplete" and summary["scientific_outcomes_emitted"] is False
    assert not vectors


@pytest.mark.parametrize("maximum", [0.1, 0.282159943, 0.5])
def test_all65_rate_maximum_and_exact_cost_formula(maximum):
    rates = [0.01] * 65
    rates[45] = maximum
    actual = pure_functions(SOURCE / "prepare.py", ["cost_projection"], {"math": __import__("math")})[
        "cost_projection"
    ](rates)
    independent = M.expected_cost_projection(rates)
    assert actual == independent
    assert independent["startup_search_projection"] == 180 + 1.5 * 8268 * maximum
    assert independent["confirmation_projection"] == 180 + 1.5 * 512 * 5 * maximum


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_invalid_cost_rate_rejected(bad):
    rates = [0.1] * 65
    rates[31] = bad
    with pytest.raises(ValueError):
        M.expected_cost_projection(rates)


def test_independent_policy_matches_literal_contract_and_checkpoint_identity():
    N = M.module("AH_native_source_test", HERE / "native_audit.py")
    P = M.module("AH_producer_source_test", SOURCE / "reserve_adapter.py")
    assert M.POLICY == P.POLICY
    p = {"reserve_policy": M.POLICY, "file_pins": {n: M.sha(SOURCE / n) for n in ("reserve_adapter.py", "search.py")}}
    for mode in ("control", "reserve"):
        assert N.external_identity(p, mode) == P.selection_identity(mode)
    current = ast.parse((HERE / "native_audit.py").read_text())
    old = ast.parse((HERE / "history/AB_first_cohort.py.txt").read_text())
    function = next(n for n in current.body if isinstance(n, ast.FunctionDef) and n.name == "first_cohort")
    historical = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == "first_cohort")
    assert ast.dump(function) == ast.dump(historical)
    assert N.HELPERS["L"][1] == M.sha(HERE / "selection.py")
    assert N.HELPERS["G"][1] == M.sha(HERE / "helpers/genetics.py")


def test_no_engine_modules_imported():
    import sys

    assert not any(
        n.startswith(("src.evolve", "src.run", "src.checkpoint", "src.life.build", "src.life.evaluate"))
        for n in sys.modules
    )
