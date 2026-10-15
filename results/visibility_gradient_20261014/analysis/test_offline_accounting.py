"""Synthetic production-ABI4 accounting; no engine imports or simulated lives."""
import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("gradient_accounting", Path(__file__).with_name("offline_accounting.py"))
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def world():
    return dict(T=16, t0=0, t_open=0, world_kind=1, b2_amp=0, b2_value=0, R_cap=500,
                c_live=.02, c_spike=.004, c_tw=.004, c_msg=.001, c_div=.5, c_sec=.004,
                c_miss=10, c_rec=.001, n_max=1024)


def rebuild(row, w):
    """Scalar arithmetic independent of the accountant under test."""
    for i in range(len(row["F"])):
        cost = w["c_live"] * row["live_time"][i]
        for price, name in (("c_spike", "spikes"), ("c_tw", "kappa_sum"), ("c_msg", "contact_events"),
                            ("c_div", "claims"), ("c_sec", "sec_int"), ("c_miss", "misses"), ("c_rec", "rec_gain")):
            cost = cost + w[price] * row[name][i]
        cost = cost + max(0, -w["b2_value"]) * row["b2_clicks"][i]
        row["cost"][i] = cost
        row["income"][i] = w["R_cap"] * row["captures"][i]
        row["guard_charge"][i] = (w["c_live"] * w["n_max"] * (w["t0"] + w["T"] - row["t_end"][i])
                                     if int(row["status"][i]) & 6 else 0)
        row["net"][i] = row["income"][i] - cost - row["guard_charge"][i]
        row["F_kernel"][i] = row["net"][i] / (w["T"] - w["t_open"])
        row["extinct_charge"][i] = (w["c_live"] * (w["t0"] + w["T"] - max(row["t_ext"][i], w["t0"]))
                                       / (w["T"] - w["t_open"]) if int(row["status"][i]) & 1 else 0)
    row["F"] = row["F_kernel"] - row["extinct_charge"]
    row["ledger"] = np.stack([row["F_kernel" if key == "F" else key] for key in A.LEDGER], axis=1)
    return row


def fixture():
    n = 4
    row = {key: np.zeros(n, dtype=np.float64) for key in A.COLS}
    for key, val in dict(captures=[1, 2, 0, 3], low_light_captures=[0, 1, 0, 2], misses=1,
                         clicks=[2, 3, 1, 4], live_time=[16, 40, 8, 20], live_S=[16, 20, 8, 10],
                         live_M=[0, 20, 0, 10], births=[0, 4, 0, 3], deaths=[0, 1, 1, 0], kills=[0, 1, 0, 0],
                         claims=[0, 4, 0, 4], n_end=[1, 3, 0, 4], n_peak=[1, 5, 1, 4],
                         n_S_end=[1, 1, 0, 2], n_M_end=[0, 2, 0, 2], t_end=[16, 16, 8, 10],
                         status=[0, 256, 1, 2], t_ext=[-1, -1, 8, -1], last_birth=[0, 4, 0, 2],
                         spikes=4, kappa_sum=2, contact_events=2, rec_gain=2, rec_cand=4,
                         rec_accept=2, rec_events=2, samples=7, zone_samples=1, window=16,
                         rejects=[0, 0, 0, 0], rejects_wall=[0, 2, 0, 1],
                         arrivals=[0, 0, 0, 0], arrivals_dropped=[1, 4, 0, 3]).items():
        row[key][:] = val
    row.update(cpu_seconds=np.asarray(1.0), wall_seconds=np.asarray(1.1),
               seeds=np.asarray([101, 102, 103, 104], dtype=np.uint64))
    return rebuild(row, world())


def raw_change(row, key, value):
    row[key][0] = value
    row["ledger"][0, A.L[key]] = value


def test_production_58_columns_preserve_growth_guard_and_extinction():
    row = fixture()
    assert A.validate_row(row, world(), 4) == dict(guarded=1, extinct=1, valid_other_status=1,
                                                 all_fitness_rows_retained=4)
    assert row["F"][2] < row["F_kernel"][2]
    assert row["guard_charge"][3] > 0
    assert A.LEDGER[21:23] == ("beats", "P_int")
    assert A.LEDGER[57] == "low_light_captures"


@pytest.mark.parametrize("column", range(58))
def test_every_raw_column_must_be_finite(column):
    row = fixture()
    row["ledger"][0, column] = np.nan
    with pytest.raises(ValueError, match="raw ledger"):
        A.validate_row(row, world(), 4)


@pytest.mark.parametrize("key", A.LEDGER)
def test_every_named_raw_column_is_bound_to_raw_bytes(key):
    row = fixture()
    row["F_kernel" if key == "F" else key][0] += 1
    with pytest.raises(ValueError, match="raw ledger and saved"):
        A.validate_row(row, world(), 4)


@pytest.mark.parametrize("key,value", [("status", 64), ("status", 128), ("status", 512), ("status", .5),
                                      ("t_end", 15), ("t_end", 17), ("low_light_captures", 2),
                                      ("low_light_captures", .5), ("births", 1), ("n_M_end", 1),
                                      ("live_M", 1), ("clicks", 3), ("b2_clicks", 1), ("t_ext", 0),
                                      ("morph_lost", 1), ("last_birth", 17)])
def test_physical_corruption_rejected(key, value):
    row = fixture()
    raw_change(row, key, value)
    with pytest.raises(ValueError):
        A.validate_row(row, world(), 4)


def test_kernel_cost_rounding_tolerance_preserved():
    row = fixture()
    tolerance = 1e-9 * max(1, abs(row["cost"][0]))
    raw_change(row, "cost", row["cost"][0] + .5 * tolerance)
    A.validate_row(row, world(), 4)
    raw_change(row, "cost", row["cost"][0] + 2 * tolerance)
    with pytest.raises(ValueError, match="cost"):
        A.validate_row(row, world(), 4)


def test_extinction_charge_cannot_be_removed_from_named_fitness():
    row = fixture()
    row["F"][2] = row["F_kernel"][2]
    with pytest.raises(ValueError, match="production fitness"):
        A.validate_row(row, world(), 4)


def test_guard_charge_cannot_be_removed():
    row = fixture()
    row["guard_charge"][3] = row["ledger"][3, A.L["guard_charge"]] = 0
    with pytest.raises(ValueError, match="guard_charge"):
        A.validate_row(row, world(), 4)


def test_initial_zygote_is_not_a_recorded_birth():
    row = fixture()
    assert row["births"][0] == 0 and row["n_end"][0] == 1
    raw_change(row, "births", 1)
    with pytest.raises(ValueError, match="census"):
        A.validate_row(row, world(), 4)


def test_paired_decomposition_keeps_both_penalties_and_disjoint_counters():
    parent, winner = fixture(), fixture()
    winner["captures"] += 1
    winner["clicks"] += 1
    winner["low_light_captures"] += 1
    winner["spikes"] += 2
    # Preserve growth and the natural extinction, while removing the guarded stop.
    winner["status"][3] = 0
    winner["t_end"][3] = 16
    rebuild(winner, world())
    report, vectors = A.paired_terms(winner, parent, world())
    assert report["status"]["parent"]["all_fitness_rows_retained"] == 4
    assert report["status"]["winner"]["extinct"] == 1
    assert report["fitness_pieces"]["guard_charge_saving"]["mean"] > 0
    assert np.allclose(vectors["F__accounting_residual"], 0)
    assert report["fitness_pieces"]["capture_income"]["mean"] == 500 / 16
    assert report["fitness_pieces"]["spiking_cost_saving"]["mean"] == pytest.approx(-.008 / 16)
    assert report["columns"]["low_light_captures"]["mean"] == 1
    loser, _ = A.paired_terms(parent, winner, world())
    assert loser["columns"]["F"]["mean"] < 0


def test_paired_seed_order_cannot_change():
    parent, winner = fixture(), fixture()
    winner["seeds"] = winner["seeds"][::-1]
    with pytest.raises(ValueError, match="ordered seeds"):
        A.paired_terms(winner, parent, world())


@pytest.mark.parametrize("bad", [np.asarray(-1.0), np.asarray(np.inf), np.asarray([1.0])])
def test_row_cpu_is_finite_nonnegative_scalar(bad):
    row = fixture()
    row["cpu_seconds"] = bad
    with pytest.raises(ValueError, match="timing"):
        A.validate_row(row, world(), 4)


def test_partial_and_retyped_ledgers_rejected():
    for ledger in (fixture()["ledger"][:3], fixture()["ledger"].astype(np.float32)):
        row = copy.deepcopy(fixture())
        row["ledger"] = ledger
        with pytest.raises(ValueError, match="raw ledger"):
            A.validate_row(row, world(), 4)
