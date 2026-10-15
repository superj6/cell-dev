"""Focused AF four-role/source-contract checks; no engine calls or genetic draws."""

import __future__

import ast
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
s = importlib.util.spec_from_file_location("AF_reader_tests", HERE / "analyze.py")
M = importlib.util.module_from_spec(s)
s.loader.exec_module(M)
ROOT = next((p for p in HERE.parents if (p / "src/life/spec.py").is_file()), None)
SOURCE = (
    HERE.parent
    if (HERE.parent / "measure.py").is_file()
    else ROOT / "outputs/autonomous_prediction_continuation_20261014"
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


@pytest.fixture(scope="module")
def complete(tmp_path_factory):
    base = tmp_path_factory.mktemp("one_four_row_fixture")
    p = {"world": world(), "confirmation": {"seeds": list(range(512))}}
    folder = base / "confirmation"
    ep = {"genotype_sha256": {label: "synthetic-" + label for label in M.LABELS}}
    save(folder / "endpoints.json", ep)
    # Only a file hash is used in load_rows; no genetic table is made here.
    np.savez(folder / "genotypes.npz", marker=np.asarray("synthetic file-hash placeholder; no genotype table"))
    (folder / "persistent").mkdir()
    rows = {}
    index = {}
    for i, label in enumerate(M.LABELS):
        r = row(2 + i + np.arange(512) % 3)
        r["genome_index"] = np.asarray(i)
        r["identity"] = np.asarray(
            M.canonical(
                {
                    "protocol_sha256": M.PROTOCOL_SHA,
                    "stage": "confirmation",
                    "endpoints_sha256": M.sha(folder / "endpoints.json"),
                    "role": label,
                    "genome_index": i,
                    "genome_sha256": ep["genotype_sha256"][label],
                    "seeds": p["confirmation"]["seeds"],
                }
            )
        )
        path = folder / f"persistent/row_{i:04d}.npz"
        np.savez_compressed(path, **r)
        index[str(path.relative_to(folder))] = {"sha256": M.sha(path), "cpu_seconds": 0.01}
        rows[i] = r
    save(folder / "row_index.json", index)
    np.savez_compressed(
        folder / "persistent/scores.npz",
        seeds=np.arange(512, dtype=np.uint64),
        genome_indices=np.arange(4),
        **{k: np.stack([rows[i][k] for i in range(4)]) for k in M.A.COLS},
    )
    save(
        folder / "report.json",
        {
            "status": "complete",
            "report_only": True,
            "genome_lives": 2048,
            "paired_seeds": 512,
            "confirmation_startup_validation_lives": 2,
            "protocol_sha256": M.PROTOCOL_SHA,
            "endpoints_sha256": M.sha(folder / "endpoints.json"),
            "genotypes_sha256": M.sha(folder / "genotypes.npz"),
            "row_cpu_seconds": 0.04,
        },
    )
    return base, p, ep, {"cpu_seconds": 100.0, "search_stage_cpu_seconds": 50.0}, rows


def test_four_rows_two_primary_actual_producer_comparisons(complete):
    base, p, ep, budget, expected = complete
    rows, _, cpu, _ = M.load_rows(base, p, ep, budget)
    assert len(rows) == 4 and cpu == pytest.approx(0.04)
    vectors = {}
    for a, b in M.PAIRS["primary"]:
        report = actual_comparison(rows[a], rows[b], p["world"])
        result, terms = M.comparison(rows[a], rows[b], report, p["world"])
        assert result["columns"]["F"]["mean"] == pytest.approx((rows[a]["F"] - rows[b]["F"]).mean())
        assert len(terms) == 73
        vectors.update({M.LABELS[a] + "__" + k: v for k, v in terms.items()})
    assert len(vectors) == 146
    assert all(v.shape == (512,) for v in vectors.values())


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
    old_npz = M.npz
    old_read = M.read

    def changed(path):
        r = old_npz(path)
        if Path(path).name == "row_0000.npz":
            if kind == "raw58":
                r["ledger"] = np.column_stack([r["ledger"], np.zeros(512)])
            elif kind == "named_F":
                r["F"][0] += 1
            elif kind == "identity_role":
                r["identity"] = np.asarray(str(r["identity"]).replace("AE_D90", "AF_D90"))
            elif kind == "seed_order":
                r["seeds"] = r["seeds"][::-1]
            elif kind == "genome_index":
                r["genome_index"] = np.asarray(2)
            elif kind == "negative_timing":
                r["cpu_seconds"] = np.asarray(-1.0)
        if Path(path).name == "scores.npz" and kind == "aggregate_order":
            r["genome_indices"] = np.arange(4)[::-1]
        return r

    def changed_read(path):
        result = old_read(path)
        if Path(path).name == "report.json" and kind == "wrong_call_count":
            result["genome_lives"] = 3072
        return result

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


def test_exact_one_confirmation_golden_call_and_fixed_four_roles():
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
    assert M.sha(HERE / "helpers/selection.py") == "41b97ad3f22db01778d21fe3bb52952016423cb83f453aa1449743d36884c7bd"
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
    assert 8268 + 4 * 512 + 3 * 2 == 10322


def test_unregistered_refuses_outcomes(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "PROTOCOL_SHA", None)
    summary, vectors = M.analyze(tmp_path)
    assert summary["status"] == "incomplete" and summary["scientific_outcomes_emitted"] is False
    assert not vectors


@pytest.mark.parametrize(
    "rates",
    [
        {
            "D90": {"H_screen": 0.2, "H_confirm": 0.1, "P_confirm": 0.15},
            "L92": {"H_screen": 0.1, "H_confirm": 0.12, "P_confirm": 0.08},
        },
        {
            "D90": {"H_screen": 0.1, "H_confirm": 0.15, "P_confirm": 0.2},
            "L92": {"H_screen": 0.08, "H_confirm": 0.1, "P_confirm": 0.12},
        },
        {
            "D90": {"H_screen": 1.0, "H_confirm": 0.1, "P_confirm": 0.2},
            "L92": {"H_screen": 1.0, "H_confirm": 0.1, "P_confirm": 0.2},
        },
    ],
)
def test_all_three_cost_sources_and_hard_feasibility(rates):
    producer = pure_functions(
        SOURCE / "prepare.py", ["cost_projection"], {"PARENTS": M.BACKGROUNDS, "math": __import__("math")}
    )["cost_projection"](rates)
    independent = M.expected_cost_projection(rates)
    assert {k: producer[k] for k in independent} == independent
    assert independent["startup_search_projection"] == 180 + 1.5 * 4134 * sum(max(x.values()) for x in rates.values())
    assert independent["confirmation_projection"] == pytest.approx(
        180 + 1.5 * 512 * 3 * sum(max(x.values()) for x in rates.values()), rel=0, abs=1e-12
    )


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_invalid_cost_floor_rejected(bad):
    rates = {b: {"H_screen": 0.1, "H_confirm": 0.1, "P_confirm": 0.1} for b in M.BACKGROUNDS}
    rates["D90"]["P_confirm"] = bad
    with pytest.raises(ValueError):
        M.expected_cost_projection(rates)


@pytest.mark.parametrize("field,value", [("ppid", 1), ("pgid", 1), ("start_ticks", 0)])
def test_actual_ownership_corruptions(field, value):
    budget = M.read(
        (ROOT / "results/visibility_continuation_20261014/operations/budget.json")
        if ROOT
        else SOURCE / "inputs/AE/budget.json"
    )
    attempt = {"monitor": M.identity(budget["process_identities"][0])}
    budget["process_identities"][1][field] = value
    with pytest.raises(ValueError):
        M.owned_processes(attempt, budget, [x["name"] for x in budget["process_identities"][1:]])
