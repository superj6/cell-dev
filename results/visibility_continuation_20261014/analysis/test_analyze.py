"""Actual producer-schema regressions and synthetic six-row failures; no simulated lives."""

import ast
import importlib.util
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("Z_test_analysis", HERE / "analyze.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SOURCE = (
    HERE.parent
    if (HERE.parent / "protocol.json").is_file()
    else HERE.parents[1] / "autonomous_visibility_continuation_20261014"
)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(M.json_bytes(value))


def stats(values):
    return {"mean": float(values.mean()), "se": float(values.std(ddof=1) / np.sqrt(len(values))), "n": len(values)}


@pytest.mark.parametrize("name", ["U", "Y"])
def test_real_recorded_four_field_receipts(name):
    budget = M.read(HERE / "fixtures" / f"{name}_budget.json")
    attempt = (
        M.read(HERE / "fixtures/Y_attempt.json")
        if name == "Y"
        else {"monitor": M.identity(budget["process_identities"][0])}
    )
    assert set(attempt["monitor"]) == {"pid", "ppid", "pgid", "start_ticks"}
    M.owned_processes(attempt, budget, [x["name"] for x in budget["process_identities"][1:]])


def test_actual_Z_monitor_function_matches_recorded_schema():
    source = M.read(SOURCE / "protocol.json")
    assert M.sha(SOURCE / "run_budgeted.py") == source["file_pins"]["run_budgeted.py"]
    tree = ast.parse((SOURCE / "run_budgeted.py").read_text())
    function = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "process_identity")
    result = next(x for x in ast.walk(function) if isinstance(x, ast.Return)).value
    assert [ast.literal_eval(k) for k in result.keys] == ["pid", "ppid", "pgid", "start_ticks"]
    assert "start_new_session=True" in (SOURCE / "run_budgeted.py").read_text()


@pytest.mark.parametrize("field,value", [("ppid", 1), ("pgid", 1), ("start_ticks", 0)])
def test_real_receipt_ownership_corruption(field, value):
    budget = M.read(HERE / "fixtures/U_budget.json")
    attempt = {"monitor": M.identity(budget["process_identities"][0])}
    budget["process_identities"][1][field] = value
    with pytest.raises(ValueError, match="identity|owned"):
        M.owned_processes(attempt, budget, [x["name"] for x in budget["process_identities"][1:]])


def test_final_protocol_and_recorded_initialization():
    p = M.verify_protocol(SOURCE)
    N = M.module("Z_test_native", HERE / "native_audit.py")
    result = N.initialization_audit(SOURCE, p, M.external)
    assert all(x["all_rows_bitwise_equal"] for x in result["runs"].values())
    assert result["random_draws"] == result["simulation_calls"] == result["compilation_calls"] == 0


def row(p, i, endpoint_sha):
    n, w = 512, p["world"]
    r = {key: np.zeros(n, dtype=np.float64) for key in M.A.COLS}
    for key, val in dict(
        captures=1 + i + np.arange(n) % 2,
        low_light_captures=1,
        misses=1,
        births=2,
        claims=2,
        n_end=3,
        n_peak=3,
        n_S_end=1,
        n_M_end=2,
        live_time=2 * w["T"],
        live_S=w["T"],
        live_M=w["T"],
        last_birth=w["T"] / 2,
        t_end=w["T"],
        t_ext=-1,
        window=w["T"],
        rec_cand=4,
        rec_accept=2,
        rec_events=2,
        spikes=4 + i,
        contact_events=2,
        kappa_sum=2,
        rec_gain=2,
    ).items():
        r[key][:] = val
    r["clicks"] = r["captures"] + r["misses"]
    for j in range(n):
        cost = w["c_live"] * r["live_time"][j]
        for price, column in (
            ("c_spike", "spikes"),
            ("c_tw", "kappa_sum"),
            ("c_msg", "contact_events"),
            ("c_div", "claims"),
            ("c_sec", "sec_int"),
            ("c_miss", "misses"),
            ("c_rec", "rec_gain"),
        ):
            cost = cost + w[price] * r[column][j]
        cost = cost + 0.0
        r["cost"][j], r["income"][j] = cost, w["R_cap"] * r["captures"][j]
        r["net"][j] = r["income"][j] - cost - 0.0
        r["F_kernel"][j] = r["net"][j] / w["T"]
    r["F"] = r["F_kernel"] - r["extinct_charge"]
    r["ledger"] = np.stack([r["F_kernel" if key == "F" else key] for key in M.A.LEDGER], axis=1)
    identity = {
        "protocol_sha256": M.PROTOCOL_SHA,
        "stage": "confirmation",
        "endpoints_sha256": endpoint_sha,
        "role": M.LABELS[i],
        "genome_index": i,
        "genome_sha256": "synthetic" + str(i),
        "seeds": p["confirmation"]["seeds"],
    }
    r.update(
        identity=np.asarray(M.canonical(identity)),
        seeds=np.asarray(p["confirmation"]["seeds"], dtype=np.uint64),
        genome_index=np.asarray(i),
        cpu_seconds=np.asarray(0.01),
        wall_seconds=np.asarray(0.02),
    )
    return r


def saved_comparison(a, b, w):
    cols = (
        "F",
        "F_kernel",
        "n_end",
        "n_H_end",
        "live_time",
        "spikes",
        "packets",
        "misses",
        "clicks",
        "captures",
        "path",
        "zone_samples",
        "samples",
        "low_light_captures",
    )
    result = {key: stats(a[key] - b[key]) for key in cols}
    result["bright_captures"] = stats(a["captures"] - a["low_light_captures"] - b["captures"] + b["low_light_captures"])
    pieces = dict(
        income=(a["income"] - b["income"]) / w["T"],
        cost_saving=(b["cost"] - a["cost"]) / w["T"],
        guard_charge_saving=(b["guard_charge"] - a["guard_charge"]) / w["T"],
        extinction_charge_saving=b["extinct_charge"] - a["extinct_charge"],
    )
    pieces["accounting_residual"] = a["F"] - b["F"] - sum(pieces.values())
    result["fitness_contributions"] = {k: stats(v) for k, v in pieces.items()}
    result["capture_income"] = stats(pieces["income"])
    result["cost_saving_components"] = {
        name: stats(price * b[col] / w["T"] - price * a[col] / w["T"]) for name, col, price in M.A.prices(w)
    }
    result["above_3se"] = result["F"]["mean"] > 3 * result["F"]["se"]
    result["guard_fraction"] = {"parent": 0.0, "winner": 0.0}
    return result


def fixture(base):
    p = M.read(SOURCE / "protocol.json")
    folder = base / "confirmation"
    endpoint = {"genotype_sha256": dict(zip(M.LABELS, ["synthetic" + str(i) for i in range(6)]))}
    save(folder / "endpoints.json", endpoint)
    np.savez(folder / "genotypes.npz", genomes=np.zeros((6, 875), dtype=np.float32), labels=np.asarray(M.LABELS))
    endpoint_sha = M.sha(folder / "endpoints.json")
    rows = {i: row(p, i, endpoint_sha) for i in range(6)}
    (folder / "blink").mkdir()
    index = {}
    for i, r in rows.items():
        path = folder / f"blink/row_{i:04d}.npz"
        np.savez_compressed(path, **r)
        index[str(path.relative_to(folder))] = {"sha256": M.sha(path), "cpu_seconds": 0.01}
    save(folder / "row_index.json", index)
    np.savez_compressed(
        folder / "blink/scores.npz",
        seeds=np.asarray(p["confirmation"]["seeds"], dtype=np.uint64),
        genome_indices=np.arange(6),
        **{k: np.stack([rows[i][k] for i in range(6)]) for k in M.A.COLS},
    )
    report = {
        "status": "complete",
        "report_only": True,
        "genome_lives": 3072,
        "paired_seeds": 512,
        "confirmation_startup_validation_lives": 2,
        "protocol_sha256": M.PROTOCOL_SHA,
        "endpoints_sha256": endpoint_sha,
        "genotypes_sha256": M.sha(folder / "genotypes.npz"),
        "row_cpu_seconds": 0.06,
    }
    save(folder / "report.json", report)
    return p, endpoint, {"cpu_seconds": 100.0, "search_stage_cpu_seconds": 50.0}, rows


def test_complete_six_rows_all_contrasts(tmp_path):
    p, ep, budget, expected = fixture(tmp_path)
    rows, _, cpu, _ = M.load_rows(tmp_path, p, ep, budget)
    assert len(rows) == 6 and cpu == pytest.approx(0.06)
    for pairs_ in M.PAIRS.values():
        for a, b in pairs_:
            result, terms = M.comparison(
                rows[a], rows[b], saved_comparison(expected[a], expected[b], p["world"]), p["world"]
            )
            assert result["columns"]["F"]["mean"] == pytest.approx((rows[a]["F"] - rows[b]["F"]).mean())
            assert len(terms["F"]) == 512


@pytest.mark.parametrize(
    "kind",
    [
        "missing_row",
        "raw_hash",
        "identity",
        "seeds",
        "production_F",
        "raw58",
        "aggregate",
        "timing",
        "budget",
        "report",
        "extra_row",
    ],
)
def test_six_row_corruptions_fail_before_summaries(tmp_path, kind):
    p, ep, budget, rows = fixture(tmp_path)
    folder = tmp_path / "confirmation"
    path = folder / "blink/row_0000.npz"
    if kind == "missing_row":
        path.unlink()
    elif kind == "raw_hash":
        path.write_bytes(b"corrupt")
    elif kind == "aggregate":
        score = M.npz(folder / "blink/scores.npz")
        score["F"][0, 0] += 1
        np.savez_compressed(folder / "blink/scores.npz", **score)
    elif kind == "budget":
        budget["cpu_seconds"] = 50.01
    elif kind == "report":
        report = M.read(folder / "report.json")
        report["genome_lives"] = 2560
        save(folder / "report.json", report)
    elif kind == "extra_row":
        np.savez(folder / "blink/row_0006.npz", **rows[0])
    else:
        r = rows[0]
        if kind == "identity":
            r["identity"] = np.asarray("{}")
        if kind == "seeds":
            r["seeds"] = r["seeds"][::-1].copy()
        if kind == "production_F":
            r["F"] = r["F"] + 1
        if kind == "raw58":
            r["ledger"][0, 57] += 10
        if kind == "timing":
            r["wall_seconds"] = np.asarray(np.nan)
        np.savez_compressed(path, **r)
        index = M.read(folder / "row_index.json")
        index["blink/row_0000.npz"]["sha256"] = M.sha(path)
        save(folder / "row_index.json", index)
    with pytest.raises((OSError, ValueError)):
        M.load_rows(tmp_path, p, ep, budget)


def test_missing_study_emits_no_outcomes(tmp_path):
    result, vectors = M.analyze(tmp_path)
    assert result["status"] == "incomplete" and result["scientific_outcomes_emitted"] is False and vectors == {}
