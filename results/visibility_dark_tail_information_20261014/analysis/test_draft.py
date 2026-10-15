"""Focused synthetic checks of reused static accounting and paired statistics."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("ad_draft", HERE / "analyze.py")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)
A = D.A


def world():
    return dict(
        T=1024,
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


def ledger(captures):
    x = np.zeros((len(captures), 57), dtype=np.float64)
    values = dict(
        captures=captures,
        clicks=captures,
        live_time=2048,
        live_S=1024,
        live_M=1024,
        n_end=2,
        n_peak=2,
        n_S_end=1,
        n_M_end=1,
        t_end=1024,
        t_ext=-1,
    )
    for key, value in values.items():
        x[:, A.L[key]] = value
    # Independent scalar expression for this fixture: only cell maintenance costs.
    x[:, A.L["cost"]] = 0.02 * 2048
    x[:, A.L["income"]] = 500 * np.asarray(captures)
    x[:, A.L["net"]] = x[:, A.L["income"]] - x[:, A.L["cost"]]
    x[:, A.L["F"]] = x[:, A.L["net"]] / 1024
    return x


def test_unset_registration_prevents_outcomes(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "REVIEWED_PROTOCOL_SHA256", None)
    summary, vectors = D.analyze(tmp_path)
    assert summary["status"] == "incomplete"
    assert not summary["scientific_outcomes_emitted"] and not vectors
    assert D.REVIEWED_PROTOCOL_SHA256 is None
    assert sum(D.VALIDATION_MATRIX.values()) == D.VALIDATION_LIVES == 76
    assert D.RESEARCH_LIVES + D.VALIDATION_LIVES == 6732


def test_only_physical_description_coordinate_changes(monkeypatch):
    params = [float(i + 1) for i in range(27)]
    params[21] = 0.25
    recovered = {"full_parameters": params, "retuned_reflex_knobs": {}}
    monkeypatch.setitem(D.C.PARAM_SHA, "flash5_dim25", D.C.digest(np.asarray(params, dtype="<f8").tobytes()))
    tuned = {"reflex@" + shape: {} for shape in ("hollow3", "hollow2", "ring2")}
    descriptions = D.C.descriptions(recovered)
    for desc in descriptions:
        if desc["role"] in ("I", "B"):
            desc["params"][21] = 0.0
        elif desc["role"] == "A":
            desc["changed_parameter_indices"] = [9, 10]
    candidates = [D.C.reconstruct(desc, tuned) for desc in descriptions]
    review = D.verify_candidate_transfer(candidates, recovered, tuned)
    assert set(review["physical_description_changes"]) == {"I", "B"}
    assert all(item["changed_indices"] == [21] for item in review["physical_description_changes"].values())
    candidates[D.ROLES.index("I")]["params"][22] += 1
    with pytest.raises(ValueError, match="exceeds approved"):
        D.verify_candidate_transfer(candidates, recovered, tuned)


def test_initial_cells_are_not_births():
    x = ledger([1, 2, 3, 4])
    A.reconcile(x, world(), 4)
    D.static_body(x, {"cells": [[0, 0, 0, 0], [0, 0, 1, 1]]}, world())
    x[:, A.L["births"]] = 2
    with pytest.raises(ValueError, match="growth or death"):
        D.static_body(x, {"cells": [[0, 0, 0, 0], [0, 0, 1, 1]]}, world())


def test_zero_signal_does_not_force_zero_dark_captures():
    x = ledger([1, 2, 3, 4])
    x[:, A.L["dark_captures"]] = [1, 1, 2, 3]
    acc = A.reconcile(x, world(), 4)
    assert np.array_equal(acc["low_light_captures"], [1, 1, 2, 3])
    assert A.RAW_LEDGER[21:23] == ("dark_captures", "late_captures")


def test_fixed_roles_and_shared_pairing_survive_reference_selection():
    raw = {role: ledger([10, 12, 14, 16]) for role in D.ROLES}
    raw["R1"] = ledger([11, 13, 15, 17])
    raw["I"] = ledger([15, 17, 19, 21])
    summary, vectors = D.scientific_summary(raw, world(), n=4)
    assert summary["reference_role"] == "R1"
    assert summary["information_gap"]["mean"] == pytest.approx(2000 / 1024)
    assert summary["information_gap"]["se"] < 1e-12
    assert "I_minus_R0" in summary["contrasts"] and "I_minus_R1" in summary["contrasts"]
    expected = 0.25 * (raw["I"][:, A.L["F"]] - raw["R1"][:, A.L["F"]])
    expected -= raw["D0"][:, A.L["F"]] - raw["R1"][:, A.L["F"]]
    assert np.array_equal(vectors["quarter_margin__D0"], expected)
    assert len(vectors) == 836


def test_incomplete_or_invalid_candidate_blocks_entire_summary():
    raw = {role: ledger([10, 12, 14, 16]) for role in D.ROLES}
    del raw["D7"]
    with pytest.raises(ValueError, match="13-role"):
        D.scientific_summary(raw, world(), n=4)
    raw["D7"] = ledger([10, 12, 14, 16])
    raw["D7"][0, A.L["status"]] = 2
    with pytest.raises(ValueError, match="guard"):
        D.scientific_summary(raw, world(), n=4)


def test_nonpositive_information_gap_is_retained():
    raw = {role: ledger([10, 12, 14, 16]) for role in D.ROLES}
    raw["I"] = ledger([9, 11, 13, 15])
    summary, _ = D.scientific_summary(raw, world(), n=4)
    assert summary["reference_role"] == "R0"
    assert summary["information_gap"]["mean"] < 0
    assert not summary["information_payoff_criterion"]
    assert not summary["do_less_quarter_criterion"]
    assert summary["do_less_quarter_margins"]["D0"]["fraction_of_information_gap"]["value"] is None
