"""Scientific admission cannot pass on small, leaked, unmatched or invalid samples."""
import copy

import numpy as np
import pytest

from scripts.taskvar_gates import admission, duration_gate, gradient_report, paired, validate_lives
from scripts.taskvar_replay import bitwise_equal
from src.life import build, spec


def record():
    n = 512
    source = "0123456789abcdef" * 4

    def row(kind, score, **kw):
        return dict(kind=kind, footprint="hollow3", F=[score] * n, **kw)

    return {"world": "example", "T": 1024, "seeds": list(range(n)), "tuning_seeds": [999],
            "reflex_footprint": "hollow3", "capability": "discrimination",
            "runs": {"frozen": row("frozen_reflex", 9), "retuned": row("retuned_reflex", 10),
                     "full": row("information", 14, privileged=False, source_sha256=source, params=[0, 1],
                                 replay_audit={"passed": True, "source_sha256": source, "artifact": "audit.json"}),
                     "ablated": row("ablation", 12, privileged=False, ablation_of="full",
                                    source_sha256=source, params=[0, 0], disabled_parameters=[1],
                                    mechanism="discrimination", isolates_capability=True),
                     "quiet": row("do_less", 10.5)}}


def test_admission_uses_information_without_hand_body():
    result = admission(record())
    assert result["verdict"] == "pass"
    assert result["information_gap"]["mean"] == 4
    assert result["specific_part"]["mean"] == 2


def test_do_less_is_strictly_less_than_quarter_not_third():
    data = record()
    data["runs"]["quiet"]["F"] = [11] * 512
    assert admission(data)["verdict"] == "fail"


def test_capability_can_use_a_larger_matched_footprint_after_own_footprint_gap():
    data = record()
    data["runs"]["large"] = copy.deepcopy(data["runs"]["full"])
    data["runs"]["large"]["footprint"] = "ring5"
    data["runs"]["ablated"]["footprint"] = "ring5"
    data["runs"]["ablated"]["ablation_of"] = "large"
    data["capability_controller"] = "large"
    result = admission(data)
    assert result["verdict"] == "pass"
    assert result["information_controller"] == "full"
    assert result["capability_controller"] == "large"


@pytest.mark.parametrize("change", ["small", "bigger", "privileged", "no_tune", "no_leak", "wrong_hash",
                                    "no_ablation", "different_footprint", "not_isolated", "no_world_parity"])
def test_missing_evidence_never_passes(change):
    data = record()
    if change == "small":
        data["seeds"] = data["seeds"][:16]
        for row in data["runs"].values():
            row["F"] = row["F"][:16]
    elif change == "bigger":
        data["runs"]["full"]["footprint"] = "ring5"
    elif change == "privileged":
        data["runs"]["full"]["privileged"] = True
    elif change == "no_tune":
        data["tuning_seeds"] = []
    elif change == "no_leak":
        data["runs"]["full"]["replay_audit"] = None
    elif change == "wrong_hash":
        data["runs"]["full"]["source_sha256"] = "a different controller"
    elif change == "no_ablation":
        del data["runs"]["ablated"]
    elif change == "different_footprint":
        data["runs"]["ablated"]["footprint"] = "ring5"
    elif change == "not_isolated":
        data["runs"]["ablated"]["isolates_capability"] = False
    else:
        data["engine"] = "scratch controller harness"
    assert admission(data)["verdict"] == "incomplete"


def test_bad_seed_provenance_rejected():
    data = record()
    data["tuning_seeds"] = [data["seeds"][0]]
    with pytest.raises(ValueError, match="overlap"):
        admission(data)
    data = record()
    data["seeds"][1] = data["seeds"][0]
    with pytest.raises(ValueError, match="duplicates"):
        admission(data)


def test_reflex_selection_uses_one_whole_candidate():
    data = record()
    data["runs"]["frozen"]["F"] = [0, 18] * 256
    data["runs"]["retuned"]["F"] = [20, 0] * 256
    result = admission(data)
    assert result["best_reflex"] == "retuned"
    assert result["information_gap"]["mean"] == 4


def test_paired_uncertainty_rejects_large_noisy_gain():
    data = record()
    data["runs"]["full"]["F"] = [14 - 100, 14 + 100] * 256
    result = admission(data)
    assert not result["checks"]["information_gap"]
    assert result["verdict"] == "fail"


def test_duration_gate_requires_both_lengths_for_every_world():
    reports = [dict(world=w, T=t, verdict="pass") for w in ("base", "pool") for t in (768, 1536)]
    assert duration_gate(reports, ["base", "pool"])["verdict"] == "pass"
    assert duration_gate(reports[:-1], ["base", "pool"])["verdict"] == "incomplete"
    with pytest.raises(ValueError, match="duplicate"):
        duration_gate(reports + [reports[0]], ["base", "pool"])


def test_gradient_fraction_and_size_click_associations():
    data = {"F": [[10, 12], [11, 13], [9, 11]], "n_end": [[20, 20], [10, 10], [20, 20]],
            "clicks": [[10, 12], [5, 7], [15, 17]], "captures": [[5, 7], [5, 7], [3, 5]]}
    result = gradient_report(data)
    assert result["beneficial_fraction"] == 0.5
    assert result["rows"][0]["shrinks"] and result["rows"][0]["clicks_less"]
    assert result["report_only"]
    bad = copy.deepcopy(data)
    bad["F"][1][0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        gradient_report(bad)


def test_bitwise_comparison_distinguishes_signed_zero():
    assert not bitwise_equal(np.array([0.0]), np.array([-0.0]))
    assert bitwise_equal(np.array([1.0]), np.array([1.0]))
    with pytest.raises(ValueError, match="matching"):
        paired([1, 2], [1, 2, 3])


@pytest.mark.parametrize("status", ["guard_cells", "guard_events", "ledger_mismatch", "capacity"])
def test_invalid_lives_cannot_be_scientific_samples(status):
    world = spec.world("catch_speck_l4", T=32)
    ledger = np.zeros((1, spec.V3.LEDGER_SIZE))
    ledger[0, spec.V3.L["t_end"]] = 32
    ledger[0, spec.V3.L["status"]] = spec.STATUS[status]
    result = build.Lives(ledger, np.zeros((1, 5), dtype=np.uint64), abi=spec.V3)
    with pytest.raises(ValueError, match="guard|capacity|mismatch"):
        validate_lives(result, world)


def test_genome_extinction_is_valid_but_unexplained_early_stop_is_not():
    world = spec.world("catch_speck_l4", T=32)
    ledger = np.zeros((1, spec.V3.LEDGER_SIZE))
    ledger[0, spec.V3.L["t_end"]] = 10
    result = build.Lives(ledger, np.zeros((1, 5), dtype=np.uint64), abi=spec.V3)
    with pytest.raises(ValueError, match="incomplete"):
        validate_lives(result, world)
    ledger[0, spec.V3.L["status"]] = spec.STATUS["extinct"]
    validate_lives(result, world)


def test_guarded_mutants_are_retained_with_their_penalty_and_counted():
    world = spec.world("catch_speck_l4", T=32)
    ledger = np.zeros((1, spec.V3.LEDGER_SIZE))
    ledger[0, spec.V3.L["status"]] = spec.STATUS["guard_events"]
    result = build.Lives(ledger, np.zeros((1, 5), dtype=np.uint64), abi=spec.V3)
    validate_lives(result, world, allow_guards=True)
    data = {key: np.array([[1, 1], [0, 0]]) for key in ("F", "n_end", "clicks", "captures")}
    data["status"] = np.array([[0, 0], [spec.STATUS["guard_events"], spec.STATUS["guard_events"]]])
    report = gradient_report(data)
    assert report["guard_life_fraction"] == 1
    assert report["beneficial_fraction"] == 0
    data["status"][1, 0] = spec.STATUS["capacity"]
    with pytest.raises(ValueError, match="capacity"):
        gradient_report(data)


def test_offline_admission_rejects_known_bad_status():
    data = record()
    data["runs"]["full"]["status"] = [spec.STATUS["guard_events"]] * 512
    with pytest.raises(ValueError, match="guarded"):
        admission(data)
