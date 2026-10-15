"""Actual prepared AD inputs, no simulation or source-engine imports."""

import copy
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("ad_bound", HERE / "analyze.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
SOURCE = (
    HERE.parent
    if (HERE.parent / "protocol.json").is_file()
    else HERE.parent / "autonomous_visibility_dark_tail_information_20261014"
)


def test_actual_prepared_inputs_and_physical_transfer():
    p, review = M.verify_protocol(SOURCE)
    xp = M.read(SOURCE / "inputs/X2/protocol.json")
    yp = M.read(SOURCE / "inputs/Y/protocol.json")
    assert p["production_pins"] == dict(xp["production_pins"], **yp["production_pins"])
    assert len(p["file_pins"]) == 98 and len(p["production_pins"]) == 56
    assert review["candidate_count"] == 13
    assert set(review["physical_description_changes"]) == {"I", "B"}
    assert all(row["changed_indices"] == [21] for row in review["physical_description_changes"].values())
    assert p["worlds"]["flash5_dark"]["production"]["world"]["visibility_low"] == 0
    assert len(p["historical_cpu_per_life"]) == 13


def test_actual_transfer_rejects_an_extra_parameter_change():
    p = M.read(SOURCE / "protocol.json")
    recovered = M.read(SOURCE / "inputs/recovered_inputs.json")["worlds"]["flash5_dim25"]
    tuned = M.C.literals((SOURCE / "original/src/life/handbuilt.py").read_text(), "SPECK_TUNED")
    candidates = copy.deepcopy(p["worlds"]["flash5_dark"]["candidates"])
    candidates[M.ROLES.index("I")]["params"][22] += 0.125
    with pytest.raises(ValueError, match="exceeds approved"):
        M.verify_candidate_transfer(candidates, recovered, tuned)


def test_unstarted_actual_study_cannot_emit_outcomes():
    if (SOURCE / "ready.json").exists() or (SOURCE / "operations/ready.json").exists():
        pytest.skip("This retained preparation check applies before root release only")
    summary, vectors = M.analyze(SOURCE)
    assert summary["status"] == "incomplete" and not summary["scientific_outcomes_emitted"]
    assert "ready.json" in summary["error"] and not vectors
