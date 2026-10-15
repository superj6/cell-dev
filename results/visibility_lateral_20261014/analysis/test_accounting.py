"""Focused late-window ABI4 regressions; all rows are synthetic, no engine imports."""

import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("AA_accounting", HERE / "offline_accounting.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)
LABELS = ["D90", "L92", "Y_D90", "Y_L92", "Z_D90", "Z_L92"]
PAIRS = {"primary": [[4, 2], [5, 3]], "start": [[2, 0], [3, 1]], "cumulative": [[4, 0], [5, 1]]}


def world():
    return dict(
        T=1024.0,
        t0=0.0,
        t_open=544.0,
        t_fork=512.0,
        fork_flags=16,
        world_kind=1,
        b2_amp=0,
        b2_value=0,
        R_cap=500.0,
        c_live=0.02,
        c_spike=0.004,
        c_tw=0.004,
        c_msg=0.001,
        c_div=0.5,
        c_sec=0.004,
        c_miss=10.0,
        c_rec=0.001,
        n_max=1024,
    )


def rebuild(r, w):
    for i in range(len(r["F"])):
        cost = w["c_live"] * r["live_time"][i]
        for price, key in (
            ("c_spike", "spikes"),
            ("c_tw", "kappa_sum"),
            ("c_msg", "contact_events"),
            ("c_div", "claims"),
            ("c_sec", "sec_int"),
            ("c_miss", "misses"),
            ("c_rec", "rec_gain"),
        ):
            cost = cost + w[price] * r[key][i]
        cost = cost + max(0.0, -w["b2_value"]) * r["b2_clicks"][i]
        r["cost"][i] = cost
        r["income"][i] = w["R_cap"] * r["captures"][i]
        r["guard_charge"][i] = (
            w["c_live"] * w["n_max"] * (w["t0"] + w["T"] - r["t_end"][i]) if int(r["status"][i]) & 6 else 0.0
        )
        r["net"][i] = r["income"][i] - cost - r["guard_charge"][i]
        r["F_kernel"][i] = r["net"][i] / (w["T"] - w["t_open"])
        r["extinct_charge"][i] = (
            w["c_live"] * (w["t0"] + w["T"] - max(r["t_ext"][i], w["t0"] + w["t_open"])) / (w["T"] - w["t_open"])
            if int(r["status"][i]) & 1
            else 0.0
        )
    r["F"] = r["F_kernel"] - r["extinct_charge"]
    r["ledger"] = np.stack([r["F_kernel" if k == "F" else k] for k in A.LEDGER], axis=1)
    return r


def row():
    n = 4
    r = {k: np.zeros(n, dtype=np.float64) for k in A.COLS}
    for key, value in dict(
        captures=[2, 1, 0, 0],
        low_light_captures=[1, 0, 0, 0],
        misses=[1, 1, 0, 0],
        clicks=[3, 2, 0, 0],
        n_end=[2, 3, 0, 2],
        n_peak=[3, 4, 3, 3],
        n_S_end=[1, 1, 0, 1],
        n_M_end=[1, 2, 0, 1],
        live_time=[960, 1440, 0, 0],
        live_S=[480, 480, 0, 0],
        live_M=[480, 960, 0, 0],
        last_birth=200,
        t_end=[1024, 1024, 400, 500],
        status=[0, 256, 1, 2],
        t_ext=[-1, -1, 400, -1],
        window=480,
        rec_cand=[1, 1, 0, 0],
        rec_accept=[1, 0, 0, 0],
        rec_events=[2, 1, 0, 0],
        rec_gain=[2, 1, 0, 0],
        spikes=[5, 4, 0, 0],
        contact_events=[2, 1, 0, 0],
        kappa_sum=[1, 1, 0, 0],
        morph_secreted=10,
        morph_decayed=2,
        morph_lost=3,
        morph_content_end=4,
        morph_inflight_end=1,
        arrivals=[0, 1, 0, 0],
        arrivals_dropped=[3, 4, 0, 0],
        path=[5, 6, 2, 3],
    ).items():
        r[key][:] = value
    r.update(seeds=np.arange(4, dtype=np.uint64), cpu_seconds=np.asarray(0.01), wall_seconds=np.asarray(0.02))
    return rebuild(r, world())


def change(r, key, value, index=0):
    r[key][index] = value
    r["ledger"][index, A.L[key]] = value


def test_boundary_crossing_and_preopening_endings_are_valid():
    r = row()
    health = A.validate_row(r, world(), 4)
    assert health == {"guarded": 1, "extinct": 1, "valid_other_status": 1, "all_fitness_rows_retained": 4}
    assert r["rec_events"][0] > r["rec_accept"][0] and r["births"][0] == 0 and r["n_end"][0] == 2
    assert r["extinct_charge"][2] == world()["c_live"]
    assert r["guard_charge"][3] == world()["c_live"] * 1024 * (1024 - 500)
    assert r["morph_secreted"][2] > 0 and r["live_time"][2] == 0


def test_late_natural_growth_does_not_impose_zygote_census():
    r = row()
    r["births"][0] = 3
    r["claims"][0] = 3
    r["deaths"][0] = 1
    r["last_birth"][0] = 600
    r = rebuild(r, world())
    A.validate_row(r, world(), 4)
    assert 1 + r["births"][0] - r["deaths"][0] != r["n_end"][0]


@pytest.mark.parametrize("kind", ["accept", "morph", "extinction", "raw", "low", "timing"])
def test_actual_accounting_corruption_rejected(kind):
    r = row()
    if kind == "accept":
        change(r, "rec_accept", 2)
    if kind == "morph":
        change(r, "morph_lost", 4)
    if kind == "extinction":
        r["extinct_charge"][2] = 0.03
    if kind == "raw":
        r["ledger"][0, 0] += 1
    if kind == "low":
        change(r, "low_light_captures", 3)
    if kind == "timing":
        r["cpu_seconds"] = np.asarray(np.nan)
    with pytest.raises(ValueError):
        A.validate_row(r, world(), 4)


def test_frozen_checks_retain_all_penalized_rows():
    a, b = row(), row()
    b["n_end"][3] = 7
    b["n_S_end"][3] = 6
    b["n_M_end"][3] = 1
    result = A.frozen_structure(a, b, world())
    assert result["complete_guard_free_pairs"] == 2 and result["guard_or_extinct_pairs"] == 2
    assert result["all_fitness_rows_retained"] == 4


@pytest.mark.parametrize(
    "key", ["births", "deaths", "kills", "claims", "rejects", "rejects_wall", "last_birth", "n_end", "live_time"]
)
def test_frozen_changes_rejected(key):
    a, b = row(), row()
    b[key][0] = 544 if key == "last_birth" else b[key][0] + 1
    with pytest.raises(ValueError):
        A.frozen_structure(a, b, world())


def test_all36_contrasts_use_seedwise_interactions_and_preserve_penalties():
    worlds = {
        c: dict(world(), fork_flags={"normal": 0, "freeze": 16, "freeze+lateral_off": 2064}[c]) for c in A.CONDITIONS
    }
    rows = {c: {i: row() for i in range(6)} for c in A.CONDITIONS}
    for condition, arms in rows.items():
        for i, r in arms.items():
            extra = i * ({"normal": 3, "freeze": 2, "freeze+lateral_off": 1}[condition])
            r["captures"][:2] += extra
            r["clicks"][:2] += extra
            rebuild(r, worlds[condition])
    report, vectors = A.contrasts(rows, worlds, PAIRS, LABELS)
    assert len(report["contrasts"]) == 36
    key = "primary__Z_D90__added_lateral"
    expected = np.array([2, 2, 0, 0]) * 500 / 480
    assert np.allclose(vectors[key + "__capture_income"], expected, rtol=0, atol=1e-14)
    assert report["contrasts"][key]["capture_income"]["n"] == 4
    assert np.allclose(vectors[key + "__F"], expected)
    assert all(x["all_fitness_rows_retained"] == 4 for x in report["frozen_structure"].values())
    missing = copy.deepcopy(rows)
    del missing["freeze"][5]
    with pytest.raises(ValueError, match="six"):
        A.contrasts(missing, worlds, PAIRS, LABELS)
