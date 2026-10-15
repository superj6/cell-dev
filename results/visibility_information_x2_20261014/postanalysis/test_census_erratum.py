"""Actual pre-research validation regression and source-semantic counter checks."""

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("corrected_visibility_analysis", HERE / "analyze.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def fixture():
    meta = json.loads((HERE / "fixtures/metadata.json").read_text())
    path = HERE / "fixtures/blink20_R0_0_scratch.npz"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == meta["raw_sha256"]
    with np.load(path, allow_pickle=False) as data:
        return meta, data["ledger"].copy()


def test_actual_initial_cells_are_excluded_from_birth_counter():
    meta, led = fixture()
    assert led.shape == (1, 57)
    assert led[0, M.A.L["births"]] == 0
    assert led[0, M.A.L["deaths"]] == 0
    assert led[0, M.A.L["n_end"]] == len(meta["candidate"]["cells"]) == 56
    M.A.reconcile(led, meta["world"], 1)
    M.static_body(led, meta["candidate"], meta["world"])


@pytest.mark.parametrize("key", ["births", "deaths", "kills", "claims", "rejects", "rejects_wall"])
def test_fixed_candidates_still_reject_every_structural_event(key):
    meta, led = fixture()
    led[:, M.A.L[key]] = 1
    with pytest.raises(ValueError, match="growth or death"):
        M.A.reconcile(led, meta["world"], 1)
    with pytest.raises(ValueError, match="growth or death"):
        M.static_body(led, meta["candidate"], meta["world"])


def test_old_initial_birth_interpretation_is_rejected():
    meta, led = fixture()
    led[:, M.A.L["births"]] = len(meta["candidate"]["cells"])
    with pytest.raises(ValueError, match="growth or death"):
        M.A.reconcile(led, meta["world"], 1)


def test_delivered_and_dropped_arrivals_are_disjoint_counters():
    meta, led = fixture()
    led[:, M.A.L["arrivals"]] = 0
    led[:, M.A.L["arrivals_dropped"]] = 12
    M.A.reconcile(led, meta["world"], 1)
    M.static_body(led, meta["candidate"], meta["world"])


def test_candidate_census_cannot_be_replaced():
    meta, led = fixture()
    changed = dict(meta["candidate"], cells=meta["candidate"]["cells"][:-1])
    with pytest.raises(ValueError, match="cell count"):
        M.static_body(led, changed, meta["world"])
