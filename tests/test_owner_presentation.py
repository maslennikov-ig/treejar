"""The owner-facing presentation layer, after the Russian translation was removed.

What is left is the part that was never translation: one label per escalation
reason however it was spelled, a name for a criterion the judge left blank, and
the placeholders shown when a value is missing.
"""

from __future__ import annotations

from unittest.mock import patch


def test_canonical_rating_is_shown_not_translated() -> None:
    from src.services.owner_presentation import format_quality_rating

    assert format_quality_rating("poor") == "Poor"
    assert format_quality_rating("satisfactory") == "Satisfactory"
    assert format_quality_rating("good") == "Good"
    assert format_quality_rating("excellent") == "Excellent"


def test_sales_stage_enum_is_shown_readably() -> None:
    from src.services.owner_presentation import format_sales_stage

    assert format_sales_stage("greeting") == "Greeting"
    assert format_sales_stage("qualifying") == "Qualifying"
    assert format_sales_stage("needs_analysis") == "Needs analysis"
    assert format_sales_stage("company_details") == "Company details"


def test_one_label_per_escalation_reason_however_it_is_spelled() -> None:
    """The normalisation is the reason this module still exists.

    A weekly report counts reasons. Four spellings of "the customer asked for a
    human" must not appear as four separate causes.
    """
    from src.services.owner_presentation import format_report_trigger

    spellings = (
        "human_requested",
        "human requested",
        "customer asked for manager",
        "customer asked for a manager",
        "customer requested human",
        "customer wants human",
        "manager requested",
        "manager_requested",
    )

    assert {format_report_trigger(value) for value in spellings} == {
        "manager requested"
    }
    assert format_report_trigger("idle 3h") == "no reply for 3 hours"
    assert format_report_trigger("low_score") == "score below threshold"
    assert format_report_trigger("threshold_breach") == "score below threshold"


def test_verified_policy_handoff_collapses_to_one_reason() -> None:
    from src.services.owner_presentation import format_report_trigger

    result = format_report_trigger(
        (
            "Verified-answer policy requires manager confirmation because no "
            "verified FAQ support was found for 'Do you have a showroom?'."
        ),
        surface="escalation_alert",
        module="notifications",
    )

    assert result == "manager confirmation required"


def test_an_unmapped_trigger_does_not_leak_into_an_owner_alert() -> None:
    """It is an internal string -- a policy sentence, a raw enum -- not a reason."""
    from src.services.owner_presentation import format_report_trigger

    with patch("src.services.owner_presentation.logfire.info") as mock_logfire:
        result = format_report_trigger(
            "mystery english trigger",
            surface="weekly_report",
            module="reports",
        )

    assert result == "other reason"
    mock_logfire.assert_called_once()
    assert mock_logfire.call_args.args[0] == "owner_presentation.miss"
    assert mock_logfire.call_args.kwargs["surface"] == "weekly_report"
    assert mock_logfire.call_args.kwargs["module"] == "reports"
    assert mock_logfire.call_args.kwargs["value"] == "mystery english trigger"


def test_missing_values_get_placeholders_not_a_blank() -> None:
    from src.services.owner_presentation import (
        format_quality_rating,
        format_report_trigger,
        format_sales_stage,
        owner_na,
        owner_unknown,
    )

    assert owner_na() == "n/a"
    assert owner_unknown() == "unknown"
    assert owner_unknown(kind="person") == "not specified"
    for missing in (None, "", "  ", "n/a", "unknown", "none"):
        assert format_quality_rating(missing) == "unknown"
        assert format_sales_stage(missing) == "unknown stage"
        assert format_report_trigger(missing) == "other reason"


def test_criterion_score_renders_as_words() -> None:
    from src.services.owner_presentation import format_criterion_status

    assert format_criterion_status(0) == "not met"
    assert format_criterion_status(1) == "partially met"
    assert format_criterion_status(2) == "met"
    assert format_criterion_status(None) == "n/a"


def test_the_rule_number_names_the_criterion_not_the_stored_wording() -> None:
    """So a report rendered today reads the same as one rendered a year ago."""
    from src.quality.manager_schemas import MANAGER_RULE_NAMES
    from src.quality.schemas import RULE_NAMES
    from src.services.owner_presentation import manager_rule_name, quality_rule_name

    assert quality_rule_name(1, "whatever the judge wrote") == RULE_NAMES[1]
    assert quality_rule_name(1) == RULE_NAMES[1]
    assert quality_rule_name(99, "Unmapped rule") == "Unmapped rule"
    assert quality_rule_name(None) == "Evaluation criterion"

    assert manager_rule_name(4, "whatever the judge wrote") == MANAGER_RULE_NAMES[4]
    assert manager_rule_name(4) == MANAGER_RULE_NAMES[4]
    assert manager_rule_name(None) == "Manager evaluation criterion"


def test_red_flags_are_titled_deterministically_by_code() -> None:
    from src.services.owner_presentation import red_flag_explanation, red_flag_title

    assert red_flag_title("missing_identity") == "No identification"
    assert red_flag_explanation("missing_identity") == (
        "The assistant did not introduce itself as Noor from Treejar in its "
        "first reply."
    )
    assert red_flag_title("unheard_of_code", "Judge wording") == "Judge wording"
    assert red_flag_title(None) == "Critical signal"
    assert red_flag_explanation(None) == "The conversation needs a manual review."


def test_nothing_in_the_presentation_layer_is_cyrillic() -> None:
    import pathlib
    import re

    source = pathlib.Path("src/services/owner_presentation.py").read_text(
        encoding="utf-8"
    )

    assert not re.search(r"[Ѐ-ӿ]", source)
