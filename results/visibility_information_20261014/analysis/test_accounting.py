"""Synthetic corruption and arithmetic checks; never import a simulator."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("visibility_accounting", Path(__file__).with_name("accounting.py"))
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def world():
    return dict(
        T=16,
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
    )


def ledger(captures=(1, 2, 3, 4), dark=(0, 1, 2, 3), spikes=4):
    n = len(captures)
    x = np.zeros((n, 57), dtype=np.float64)
    for k, v in dict(
        captures=captures,
        dark_captures=dark,
        late_captures=dark,
        misses=2,
        clicks=np.asarray(captures) + 2,
        live_time=32,
        live_S=16,
        live_M=16,
        births=2,
        n_end=2,
        n_peak=2,
        n_S_end=1,
        n_M_end=1,
        t_end=16,
        t_ext=-1,
        spikes=spikes,
        kappa_sum=2,
        contact_events=2,
        rec_gain=2,
        rec_cand=4,
        rec_accept=2,
        rec_events=2,
        samples=15,
        zone_samples=1,
    ).items():
        x[:, A.L[k]] = v
    # Documented accountant expression, in scalar order, independent of the audit function.
    for row in x:
        cost = 0.02 * row[A.L["live_time"]]
        for p, c in (
            (0.004, "spikes"),
            (0.004, "kappa_sum"),
            (0.001, "contact_events"),
            (0.5, "claims"),
            (0.004, "sec_int"),
            (10, "misses"),
            (0.001, "rec_gain"),
        ):
            cost = cost + p * row[A.L[c]]
        cost = cost + 0 * row[A.L["b2_clicks"]]
        row[A.L["cost"]] = cost
        row[A.L["income"]] = 500 * row[A.L["captures"]]
        row[A.L["net"]] = row[A.L["income"]] - cost - 0.0
        row[A.L["F"]] = row[A.L["net"]] / 16
    return x


def test_complete_scratch_ledger_keeps_aliases_and_exact_fitness():
    x = ledger()
    r = A.reconcile(x, world(), 4)
    assert np.array_equal(r["low_light_captures"], [0, 1, 2, 3])
    assert np.array_equal(r["bright_captures"], np.ones(4))
    assert r["fitness"].tobytes() == x[:, A.L["F"]].tobytes()
    assert A.RAW_LEDGER[21:23] == ("dark_captures", "late_captures")
    assert not A.ALIASES["production_abi4_ledger"]


@pytest.mark.parametrize("column", range(57))
def test_every_raw_column_must_be_finite(column):
    x = ledger()
    x[0, column] = np.nan
    with pytest.raises(ValueError, match="nonfinite"):
        A.reconcile(x, world(), 4)


@pytest.mark.parametrize(
    "name,value",
    [
        ("dark_captures", -1),
        ("dark_captures", 2),
        ("late_captures", 2),
        ("status", 2),
        ("status", 4),
        ("status", 8),
        ("status", 16),
        ("status", 64),
        ("status", 128),
        ("status", 512),
        ("status", 0.5),
        ("t_end", 15),
        ("guard_charge", 1),
        ("b2_clicks", 1),
        ("clicks", 5),
        ("births", 3),
        ("n_M_end", 2),
        ("live_M", 18),
        ("zone_samples", 16),
        ("rec_accept", 5),
        ("rec_events", 3),
        ("morph_lost", 1),
        ("net", 1),
        ("F", 1),
        ("cost", 1),
        ("income", 1),
        ("captures", 0.5),
        ("spikes", -1),
        ("rec_gain", -1),
        ("live_H", -1),
    ],
)
def test_raw_corruption_fails_the_whole_batch(name, value):
    x = ledger()
    x[0, A.L[name]] = value
    with pytest.raises(ValueError):
        A.reconcile(x, world(), 4)


def test_no_truncation_shape_or_precision_substitution():
    for x in (ledger().astype(np.float32), ledger()[:3], np.pad(ledger(), ((0, 0), (0, 1)))):
        with pytest.raises(ValueError):
            A.reconcile(x, world(), 4)


def test_paired_decomposition_and_negative_effects_are_kept():
    left = ledger((2, 3, 4, 5), (1, 2, 3, 4), spikes=6)
    right = ledger()
    summary, v = A.paired_contrast(left, right, world())
    assert summary["columns"]["F"]["mean"] == pytest.approx((500 - 0.008) / 16)
    assert summary["fitness_pieces"]["capture_income"]["mean"] == 31.25
    assert summary["fitness_pieces"]["spikes_cost_saving"]["mean"] == -0.008 / 16
    assert summary["low_light_share_of_extra_captures"]["value"] == 1
    assert summary["low_light_share_of_extra_captures"]["se"] == 0
    negative, _ = A.paired_contrast(right, left, world())
    assert negative["columns"]["F"]["mean"] < 0
    assert negative["low_light_share_of_extra_captures"]["value"] is None
    assert np.array_equal(v["low_light_captures"], np.ones(4))


def test_ratio_uses_pairs_and_retains_values_outside_zero_one():
    r = A.ratio_of_paired_means([2, 4, 6], [1, 2, 3])
    assert r["value"] == 2 and r["se"] == 0
    r = A.ratio_of_paired_means([-1, -2, -3], [1, 2, 3])
    assert r["value"] == -1 and r["se"] == 0
    assert A.ratio_of_paired_means([1, 1, 1], [-1, 0, 1])["value"] is None


def test_unexpected_extinction_invalidates_fixed_static_study_without_penalty():
    x = ledger()
    x[:, A.L["status"]] = 1
    x[:, A.L["deaths"]] = 2
    x[:, A.L["n_end"]] = x[:, A.L["n_S_end"]] = x[:, A.L["n_M_end"]] = 0
    x[:, A.L["t_ext"]] = 12
    with pytest.raises(ValueError, match="unexpected extinction"):
        A.reconcile(x, world(), 4)
