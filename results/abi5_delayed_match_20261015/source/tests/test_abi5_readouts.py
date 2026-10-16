"""Keep conditional-choice reporting distinct from target hits and selective abstention."""
import numpy as np
import pytest

from src.life import readouts, spec


def test_matching_confusion_table_keeps_carry_in_and_abstentions():
    led = np.zeros((1, spec.V5.LEDGER_SIZE))
    for label, values in (("narrow", (6, 1, 3, 1, 2, 1)), ("broad", (7, 0, 1, 2, 3, 1))):
        for name, value in zip(("choice_opportunities", "choice_carry_in", "correct_choices", "wrong_choices",
                                "choice_timeouts", "unfinished_choices"), values, strict=True):
            led[0, spec.V5.L[f"{name}_{label}"]] = value
    led[0, spec.V5.L["captures"]] = 5  # narrow hits: three correct, two wrong
    led[0, spec.V5.L["b2_clicks"]] = 2  # broad hits: one correct, one wrong
    led[0, spec.V5.L["clicks"]] = 7
    result = readouts.matching_summary(led)
    narrow, broad = result["classes"]["narrow"], result["classes"]["broad"]
    assert (narrow["narrow_choice"], narrow["broad_choice"], narrow["no_completed_choice"]) == (3, 1, 3)
    assert (broad["narrow_choice"], broad["broad_choice"], broad["no_completed_choice"]) == (2, 1, 4)
    assert narrow["correct_per_opportunity"] == 3 / 7
    assert narrow["accuracy_among_choices"] == 3 / 4
    assert broad["choice_coverage"] == 3 / 7
    led[0, spec.V5.L["unfinished_choices_broad"]] = 0
    with pytest.raises(ValueError, match="opportunities do not reconcile"):
        readouts.matching_summary(led)


def test_no_opportunities_does_not_become_perfect_accuracy():
    result = readouts.matching_summary(np.zeros(spec.V5.LEDGER_SIZE))
    for counts in result["classes"].values():
        assert counts["correct_per_opportunity"] is None
        assert counts["accuracy_among_choices"] is None
        assert counts["choice_coverage"] is None


def test_fractional_task_counts_are_rejected():
    led = np.zeros(spec.V5.LEDGER_SIZE)
    led[spec.V5.L["choice_opportunities_narrow"]] = .5
    led[spec.V5.L["correct_choices_narrow"]] = .5
    with pytest.raises(ValueError, match="nonnegative integers"):
        readouts.matching_summary(led)
