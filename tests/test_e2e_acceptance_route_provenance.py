"""The provenance split, as a number rather than a manual read-through.

Every capture in the 2026-08-07 run already carried ``text_provenance`` per
turn. It took scoring the run by hand to find that the scenarios containing a
template averaged 13.3 against 22.8 for the ones the model wrote. These tests
cover the reader that turns that into one line of output.

The fixtures are synthetic. No captured wording, identifier or customer datum
belongs in a test file.
"""

from __future__ import annotations

from typing import Any

from scripts.e2e_acceptance.route_provenance import (
    format_summary,
    is_scenario_capture,
    summarise_capture,
    summarise_run,
)


def _capture(scenario: str, turns: list[tuple[str, str, str]]) -> dict[str, Any]:
    """One capture in the shape the scenario runner writes.

    Each turn is (assistant message id, model label, provenance). The evidence
    block is cumulative in the real capture, so it is built that way here.
    """

    evidence_turns = [
        {
            "schema_version": "noor-runtime-turn-evidence/v4",
            "assistant_message_id": message_id,
            "text_provenance": provenance,
        }
        for message_id, _model, provenance in turns
    ]
    return {
        "scenario": scenario,
        "turns": [
            {
                "assistant": {"id": message_id, "model": model},
                "detail": {
                    "metadata": {
                        "runtime_execution_evidence": {
                            "turns": evidence_turns[: index + 1]
                        }
                    }
                },
            }
            for index, (message_id, model, _provenance) in enumerate(turns)
        ],
    }


def test_a_scenario_the_model_wrote_throughout_is_reported_as_one() -> None:
    summary = summarise_capture(
        _capture(
            "S01",
            [
                ("m1", "openai/some-model", "model"),
                ("m2", "openai/some-model", "model_repaired"),
            ],
        )
    )

    assert summary.turns == 2
    assert summary.model_written == 2
    assert summary.fully_model_written is True
    assert summary.deterministic_routes == {}


def test_a_template_turn_is_counted_against_the_route_that_produced_it() -> None:
    summary = summarise_capture(
        _capture(
            "S06",
            [
                ("m1", "openai/some-model", "model"),
                (
                    "m2",
                    "openai/some-model|selection-confirmation",
                    "deterministic_static",
                ),
            ],
        )
    )

    assert summary.fully_model_written is False
    assert summary.deterministic_routes == {"selection-confirmation": 1}


def test_a_turn_the_runtime_never_recorded_is_not_guessed_at() -> None:
    capture = _capture("S09", [("m1", "openai/some-model", "model")])
    capture["turns"].append(
        {"assistant": {"id": "m2", "model": "openai/some-model|sales-opportunity"}}
    )

    summary = summarise_capture(capture)

    assert summary.provenance["unrecorded"] == 1
    assert summary.deterministic_routes == {"sales-opportunity": 1}


def test_a_capture_with_no_evidence_block_still_reads() -> None:
    summary = summarise_capture({"scenario": "S02", "turns": [{"assistant": {}}]})

    assert summary.turns == 1
    assert summary.model_written == 0


def test_the_run_summary_names_the_split_the_report_had_to_derive_by_hand() -> None:
    scenarios, total = summarise_run(
        [
            _capture("S01", [("a", "m", "model"), ("b", "m", "model")]),
            _capture(
                "S06",
                [
                    ("c", "m", "model"),
                    ("d", "m|selection-confirmation", "deterministic_static"),
                ],
            ),
            _capture(
                "S05",
                [
                    (
                        "e",
                        "m|verified-catalog-functional-failure",
                        "deterministic_replacement",
                    )
                ],
            ),
        ]
    )

    assert [item.scenario for item in scenarios] == ["S01", "S05", "S06"]
    assert total.turns == 5
    assert total.model_written == 3
    assert total.deterministic_routes == {
        "selection-confirmation": 1,
        "verified-catalog-functional-failure": 1,
    }

    rendered = format_summary(scenarios, total)
    assert "1 of them model-written throughout" in rendered
    assert "2 of 5 turns came from a deterministic route" in rendered
    assert "selection-confirmation" in rendered


def test_the_summary_carries_no_message_text() -> None:
    """Reports leave the protected tree; captured wording does not."""

    capture = _capture("S03", [("a", "m|showroom-location", "deterministic_static")])
    capture["turns"][0]["assistant"]["content"] = "a customer-visible sentence"

    scenarios, total = summarise_run([capture])

    assert "customer-visible sentence" not in format_summary(scenarios, total)


def test_a_bare_route_label_is_read_as_one() -> None:
    """The oldest routes record the label with no model in front of it.

    A retired route is included: an earlier run's capture names routes the
    registry no longer describes, and reading those as "unlabelled" would hide
    exactly the history this tool exists to show.
    """

    summary = summarise_capture(
        _capture(
            "S08",
            [
                ("a", "name-gate", "deterministic_static"),
                ("b", "saved-context-summary", "deterministic_static"),
                ("c", "openai/some-model", "model"),
            ],
        )
    )

    assert summary.deterministic_routes == {
        "name-gate": 1,
        "saved-context-summary": 1,
    }


def test_the_other_files_in_a_run_directory_are_not_scenarios() -> None:
    """A run directory holds scores, readbacks and cleanup records too."""

    assert is_scenario_capture(_capture("S01", [("a", "m", "model")])) is True
    assert is_scenario_capture({"scenario": "S01", "turns": []}) is False
    assert is_scenario_capture({"comparable": 18.0, "raw": 15.8}) is False
    assert is_scenario_capture(["not", "a", "capture"]) is False
