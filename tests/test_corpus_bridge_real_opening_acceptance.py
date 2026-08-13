"""The real-opening acceptance round is complete, bounded, and text-safe."""

from __future__ import annotations

import hashlib
import inspect
import json
import pathlib
import sys
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from scripts.corpus_bridge.real_opening_acceptance import (
    FROZEN_SETS,
    GENERATION_RETRY_DELAYS_SECONDS,
    GENERATOR_MODEL,
    PINNED_PARAMETER_REQUIREMENTS,
    REPAIR_JUDGE_MODEL,
    ROOT_JUDGE,
    SECOND_READER_MODEL,
    _actual_cost_by_model,
    _generate_with_backoff,
    _journaled_repair_runner,
    _load_frozen_scenarios,
    _parse_args,
    _qrels_sha256_for_set,
    _reader_disagreement,
    apply_shipped_output_guards,
    build_generation_messages,
    build_public_summary,
    critical_failure_codes,
    ensure_protected_output,
    estimate_cost_usd,
    expected_language,
    find_ungrounded_numbers,
    paid_models,
    preflight,
    run_paid_round,
    validate_complete_results,
)
from scripts.corpus_bridge.semantic_catalog_evidence import (
    PINNED_CATALOG_SHA256,
    PINNED_EMBEDDING_REVISION,
    PINNED_PGVECTOR_EXTENSION,
    PINNED_QRELS_SHA256,
    CatalogSnapshot,
    _sha256_json,
    retrieval_contract_sha,
)

from src.llm.message_processor import _finalize_turn_response
from src.llm.repair_judge import (
    RepairJudgeDecision,
    RepairJudgeProviderResult,
    RepairJudgeRequest,
)
from src.llm.response_policy import (
    ReplyPolicyState,
    format_permitted_asks_prompt,
    permitted_asks_for_turn,
    render_reply,
)
from src.llm.response_runtime import LLMResponse


def _result(
    dialog_id: int, *, score: float = 20.0, attainable: float = 30.0
) -> dict[str, object]:
    return {
        "dialog_id": dialog_id,
        "length_stratum": (dialog_id - 1) // 5 + 1,
        "opening": f"private opener {dialog_id}",
        "response": f"private response {dialog_id}",
        "generator_model": "openai/gpt-5.6-luna",
        "judge_model": "z-ai/glm-5.2",
        "latency_ms": 1000 + dialog_id,
        "luna_latency_ms": 700 + dialog_id,
        "glm_latency_ms": 300,
        "prompt_tokens": 100 + dialog_id,
        "completion_tokens": 20 + dialog_id,
        "cost_micro_usd": 10 + dialog_id,
        "weighted_score": score,
        "attainable_score": attainable,
        "raw_total": 8,
        "language_ok": True,
        "critical_failures": [],
    }


def test_protected_output_refuses_the_working_tree(tmp_path: pathlib.Path) -> None:
    """Catch a future caller placing transcript-bearing output below Git."""
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(ValueError, match="outside the repository"):
        ensure_protected_output(repo / "evidence", repo_root=repo)

    protected = ensure_protected_output(
        repo / ".git" / "codex-orchestration" / "evidence",
        repo_root=repo,
    )
    assert protected.is_dir()
    assert protected.stat().st_mode & 0o777 == 0o700


def test_frozen_scenarios_require_the_recorded_seed_and_balanced_strata(
    tmp_path: pathlib.Path,
) -> None:
    """Catch a different convenience sample being substituted at run time."""
    path = tmp_path / "scenarios.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-real-openings/v1",
                "selection_seed": 9,
                "scenarios": [
                    {
                        "dialog_id": dialog_id,
                        "length_stratum": (dialog_id - 1) // 5 + 1,
                        "opening": f"opening {dialog_id}",
                    }
                    for dialog_id in range(1, 21)
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="selection seed"):
        _load_frozen_scenarios(path, FROZEN_SETS["openings-20"])


def test_a_second_set_is_only_measurable_when_it_is_registered() -> None:
    """`tj-jfmv`. The seed and stratum layout used to be module constants.

    One set needed no registry, and the constants were the guard: a round
    could not quietly measure a different twenty and report it against the
    same baseline. A second set is now needed, so the guard is kept and made
    explicit -- every registered shape must still pin its own seed, size and
    strata, and an unnamed set has no shape to be measured against.
    """

    assert set(FROZEN_SETS) == {"openings-20", "arabic-12"}
    for name, shape in FROZEN_SETS.items():
        assert shape.name == name
        assert shape.openings == sum(shape.strata.values())
        assert shape.selection_seed > 0
    seeds = {shape.selection_seed for shape in FROZEN_SETS.values()}
    assert len(seeds) == len(FROZEN_SETS), "two sets sharing a seed can be swapped"


def test_the_arabic_set_is_rejected_against_the_twenty_opening_shape(
    tmp_path: pathlib.Path,
) -> None:
    """A set is measured against the shape the round named, never another."""

    path = tmp_path / "scenarios.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-real-openings/v1",
                "selection_seed": FROZEN_SETS["arabic-12"].selection_seed,
                "scenarios": [
                    {
                        "dialog_id": dialog_id,
                        "length_stratum": (dialog_id - 1) // 4 + 1,
                        "opening": f"opening {dialog_id}",
                    }
                    for dialog_id in range(1, 13)
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="selection seed"):
        _load_frozen_scenarios(path, FROZEN_SETS["openings-20"])

    rows = _load_frozen_scenarios(path, FROZEN_SETS["arabic-12"])
    assert len(rows) == 12


def _criteria(scores: dict[int, int], applicable: set[int]) -> list[dict[str, object]]:
    return [
        {
            "rule_number": rule,
            "score": scores.get(rule, 0),
            "applicable": rule in applicable,
        }
        for rule in range(1, 16)
    ]


# Two chairs and a bench, priced and orderable, so the opening anchor has
# something real to name. `tj-rdqc`: a round that sends `anchor_line=None`
# measures an opening production would have priced.
CATALOG_SNAPSHOT_ROWS: tuple[dict[str, object], ...] = (
    {
        "id": "00000000-0000-0000-0000-000000000101",
        "sku": "CH-616",
        "name_en": "CH 616 NEW black mesh chair",
        "name_ar": None,
        "description_en": None,
        "description_ar": None,
        "category": "Seating",
        "subcategory": None,
        "price": 295.0,
        "currency": "AED",
        "stock": 36,
        "is_active": True,
    },
    {
        "id": "00000000-0000-0000-0000-000000000102",
        "sku": "CH-140",
        "name_en": "Task chair, mesh back",
        "name_ar": None,
        "description_en": None,
        "description_ar": None,
        "category": "Seating",
        "subcategory": None,
        "price": 140.0,
        "currency": "AED",
        "stock": 12,
        "is_active": True,
    },
    {
        "id": "00000000-0000-0000-0000-000000000103",
        "sku": "WS-1813",
        "name_en": "Bench workstation, four seats",
        "name_ar": None,
        "description_en": None,
        "description_ar": None,
        "category": "Workspace",
        "subcategory": None,
        "price": 1813.0,
        "currency": "AED",
        "stock": 8,
        "is_active": True,
    },
)


def _write_test_catalog_snapshot(path: pathlib.Path) -> tuple[pathlib.Path, str]:
    """The pinned snapshot, and the digest the evidence must claim."""

    document = {
        "schema_version": "treejar-semantic-catalog-snapshot/v1",
        "source": "test",
        "captured_at": None,
        "products": list(CATALOG_SNAPSHOT_ROWS),
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)
    digest = _sha256_json(
        CatalogSnapshot.model_validate(document).model_dump(mode="json")
    )
    return path, digest


def _write_test_semantic_evidence(
    path: pathlib.Path,
    scenarios: list[dict[str, object]],
    *,
    catalog_sha256: str = "a" * 64,
) -> pathlib.Path:
    query_digest = hashlib.sha256(
        json.dumps(
            scenarios,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-semantic-catalog-evidence/v1",
                "catalog": {"sha256": catalog_sha256, "rows": 1},
                "embedding": {
                    "model": "BAAI/bge-m3",
                    "revision": "b" * 40,
                    "dimensions": 1024,
                    "normalized": True,
                },
                "retrieval": {
                    "entrypoint": "src.rag.pipeline.search_products",
                    "code_sha": retrieval_contract_sha(),
                    "pgvector_python": "0.4.2",
                    "pgvector_extension": "0.8.1",
                    "distance": "cosine",
                    "search_mode": "exact",
                    "ann_indexes": [],
                    "limit": 3,
                    "query_source": "frozen_opening",
                },
                "qrels": {"sha256": "d" * 64},
                "query_set": {"sha256": query_digest, "count": len(scenarios)},
                "results": [
                    {
                        "dialog_id": int(scenario["dialog_id"]),
                        "query_sha256": hashlib.sha256(
                            str(scenario["opening"]).encode("utf-8")
                        ).hexdigest(),
                        "rows_present": False,
                        "catalog_relevant": False,
                        "relevant_skus": [],
                        "products": [],
                    }
                    for scenario in scenarios
                ],
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def test_two_readers_are_compared_only_where_both_charged_the_rule() -> None:
    """`tj-4q79`. A paired delta under the reader gap is not evidence.

    Nothing measured that gap until a round could carry both readings. Rules
    only one reader marked applicable are excluded: that is a disagreement
    about the rubric, not about the reply, and averaging them together would
    hide both.
    """

    records = {
        "1": {
            "judge": {
                "model": ROOT_JUDGE,
                "evaluation": {"criteria": _criteria({1: 2, 4: 2, 9: 2}, {1, 4, 9})},
            },
            "second_reader": {
                "model": SECOND_READER_MODEL,
                "cost_micro_usd": 5000,
                # Rule 9 is stood down here, so it is not compared at all.
                "evaluation": {"criteria": _criteria({1: 2, 4: 1}, {1, 4})},
            },
        },
        "2": {
            "judge": {
                "model": ROOT_JUDGE,
                "evaluation": {"criteria": _criteria({1: 2, 4: 2}, {1, 4})},
            },
            "second_reader": {
                "model": SECOND_READER_MODEL,
                "cost_micro_usd": 5000,
                "evaluation": {"criteria": _criteria({1: 2, 4: 0}, {1, 4})},
            },
        },
    }
    cases = [{"dialog_id": 1}, {"dialog_id": 2}]

    gap = _reader_disagreement(records, cases)

    assert gap is not None
    assert gap["second_reader"] == SECOND_READER_MODEL
    assert gap["openings_compared"] == 2
    # Rule 1 agrees; rule 4 is one step apart then two. Rule 9 never counts.
    assert gap["mean_signed_delta_by_rule_tenths"] == {"1": 0, "4": -15}
    assert "9" not in gap["mean_signed_delta_by_rule_tenths"]
    assert gap["mean_absolute_gap_per_opening_tenths"] == 15
    assert gap["worst_opening_gap_tenths"] == 20

    # And the money it cost is accounted against its own model, not the root's.
    costs = _actual_cost_by_model(
        {"records": records}, ROOT_JUDGE, second_reader_model=SECOND_READER_MODEL
    )
    assert costs[SECOND_READER_MODEL] == pytest.approx(0.01)
    assert costs[ROOT_JUDGE] == 0.0


def test_a_round_without_a_second_reader_reports_no_disagreement() -> None:
    records = {"1": {"judge": {"model": ROOT_JUDGE, "evaluation": {"criteria": []}}}}

    assert _reader_disagreement(records, [{"dialog_id": 1}]) is None


def test_complete_results_require_each_frozen_dialog_once() -> None:
    """Catch a missing or duplicated paid arm being reported as 20/20."""
    results = [_result(dialog_id) for dialog_id in range(1, 20)]

    with pytest.raises(ValueError, match="exactly the frozen dialog ids"):
        validate_complete_results(results, expected_dialog_ids=set(range(1, 21)))


def test_public_summary_contains_no_opening_or_response_text() -> None:
    """Catch private corpus text leaking through the tracked summary."""
    results = [_result(dialog_id) for dialog_id in range(1, 21)]

    public = build_public_summary(
        results, bootstrap_samples=200, seed=17, expected_openings=20
    )

    assert public["coverage"] == {
        "frozen_openings": 20,
        "luna_responses": 20,
        "judge_readings": 20,
        "critical_failures": 0,
    }
    assert public["weighted_score_tenths"] == {
        "mean": 200,
        "ci95_low": 200,
        "ci95_high": 200,
    }
    assert public["raw_total_tenths"] == {
        "openings": 20,
        "mean": 80,
        "ci95_low": 80,
        "ci95_high": 80,
    }
    assert public["acceptance"]["accepted"] is True
    assert public["acceptance"]["score_verdict"] == "paired_comparison_required"
    assert public["luna_time_to_first_reply_ms"] == {
        "responses": 20,
        "median": 710,
        "ci95_low": 710,
        "ci95_high": 712,
    }
    assert all(
        set(row)
        == {
            "dialog_id",
            "length_stratum",
            "weighted_score_tenths",
            "raw_total",
            "critical_failure_count",
            "critical_failure_codes",
            "language_ok",
            "latency_ms",
            "luna_latency_ms",
            "glm_latency_ms",
            "prompt_tokens",
            "completion_tokens",
            "cost_micro_usd",
        }
        for row in public["scenarios"]
    )
    rendered = str(public)
    assert "private opener" not in rendered
    assert "private response" not in rendered


def test_critical_failure_blocks_completion() -> None:
    """Catch an unsafe response being averaged away by a good mean score."""
    results = [_result(dialog_id) for dialog_id in range(1, 21)]
    results[4]["critical_failures"] = ["unsafe_commitment"]

    with pytest.raises(ValueError, match="critical failures"):
        validate_complete_results(results, expected_dialog_ids=set(range(1, 21)))


def test_failed_quality_round_still_produces_a_text_safe_summary() -> None:
    """Catch a failed measured round disappearing instead of being reported."""
    results = [_result(dialog_id) for dialog_id in range(1, 21)]
    results[4]["critical_failures"] = ["unsafe_commitment"]

    public = build_public_summary(
        results, bootstrap_samples=200, seed=17, expected_openings=20
    )

    assert public["coverage"]["critical_failures"] == 1
    assert public["acceptance"]["accepted"] is False


def test_no_absolute_score_threshold_can_come_back() -> None:
    """`tj-vz7o.10.2`. The retired gate and why it may not return.

    The round of 2026-08-10 pre-registered "the lower bound reaches 20.0/30",
    then the applicability maps showed eleven of the twenty openings with a
    deterministic ceiling of 9.6/30. Those eleven could not have passed with
    every applicable rule perfect: the gate was unreachable by arithmetic, not
    by quality. Restoring any absolute level over this set restores that.
    """

    results = [_result(dialog_id, score=19.9) for dialog_id in range(1, 21)]

    public = build_public_summary(
        results, bootstrap_samples=200, seed=17, expected_openings=20
    )

    assert public["weighted_score_tenths"]["mean"] == 199
    assert "minimum_ci95_low_tenths" not in public["acceptance"]
    assert public["acceptance"]["score_verdict"] == "paired_comparison_required"
    assert public["acceptance"]["accepted"] is True


def test_the_score_is_reported_against_the_ceiling_it_could_reach() -> None:
    """Averaging a 9.6 ceiling with a 30.0 one produces a number no opening
    could have scored. The bands keep them apart."""

    results = [
        _result(dialog_id, score=7.2, attainable=9.6) for dialog_id in range(1, 12)
    ] + [_result(dialog_id, score=21.0, attainable=30.0) for dialog_id in range(12, 21)]

    public = build_public_summary(
        results, bootstrap_samples=200, seed=17, expected_openings=20
    )

    assert public["ceiling_bands"] == [
        {
            "attainable_tenths": 96,
            "openings": 11,
            "mean_tenths": 72,
            "share_of_ceiling_percent": 75,
        },
        {
            "attainable_tenths": 300,
            "openings": 9,
            "mean_tenths": 210,
            "share_of_ceiling_percent": 70,
        },
    ]


def test_a_critical_failure_still_blocks_acceptance_at_any_score() -> None:
    """The one absolute left in the contract. A fabricated figure is a defect
    whatever the mean says, so it is not a threshold that can be tuned."""

    results = [_result(dialog_id, score=29.0) for dialog_id in range(1, 21)]
    results[3]["critical_failures"] = ["hallucination"]

    public = build_public_summary(
        results, bootstrap_samples=200, seed=17, expected_openings=20
    )

    assert public["acceptance"]["accepted"] is False
    assert public["acceptance"]["critical_failure_count"] == 1


def test_cost_estimate_prices_every_authorized_call() -> None:
    """Catch a preflight that reserves only one call instead of the full arm."""
    assert estimate_cost_usd(
        calls=2,
        max_input_tokens=100,
        max_output_tokens=10,
        prompt_price=0.001,
        completion_price=0.002,
    ) == pytest.approx(0.24)


@pytest.mark.parametrize(
    ("text", "language"),
    [("hello", "en"), ("مرحبا", "ar"), ("كرسي office", "ar")],
)
def test_expected_language_follows_the_customer_opening(
    text: str, language: str
) -> None:
    """Catch the English default overriding an Arabic customer opening."""
    assert expected_language(text) == language


def test_generation_messages_bind_current_prompt_and_catalog_evidence() -> None:
    """Catch a cheap prompt shortcut that stops exercising product behavior."""
    messages = build_generation_messages(
        opening="I need an ergonomic chair",
        language="en",
        catalog_evidence=[
            {"name": "Axis Chair", "sku": "AX-1", "price": 1000, "stock": 9}
        ],
    )

    assert messages[-1] == {
        "role": "user",
        "content": "I need an ergonomic chair",
    }
    system = str(messages[0]["content"])
    assert "You are Noor" in system
    assert "STAGE: GREETING" in system
    assert "[READ-ONLY CATALOG EVIDENCE]" in system
    assert "Axis Chair" in system
    assert "Do not call tools in this isolated acceptance run" in system


def test_the_round_sends_the_directives_the_opening_earns() -> None:
    """A round without them scores a prompt no customer ever receives."""
    from src.llm.engine import _turn_runtime_directives

    opening = "We are fitting out a new office for 12 people"
    earned = _turn_runtime_directives(
        opening,
        sales_stage="greeting",
        # The frozen set is one first-turn opening, and the canonical opening
        # is prepended to every reply in it, and the round quotes it in the
        # language it will be prepended in.
        opening_states_the_offer=True,
        language="en",
    )
    assert earned, "this opening is supposed to earn the consultative directives"

    system = str(
        build_generation_messages(
            opening=opening,
            language="en",
            catalog_evidence=[],
        )[0]["content"]
    )

    assert "[RUNTIME DIRECTIVES]" in system
    for directive in earned:
        assert directive in system


def test_the_round_sends_the_ask_permissions_production_derives() -> None:
    """The frozen set may ask for a name and for discovery, and nothing else."""
    system = str(
        build_generation_messages(
            opening="I need an ergonomic chair",
            language="en",
            catalog_evidence=[],
        )[0]["content"]
    )

    assert (
        format_permitted_asks_prompt(
            permitted_asks_for_turn(
                is_first_turn=True,
                customer_name=None,
                customer_name_asked=False,
                owes_company_question=False,
                quote_consent_granted=False,
            )
        )
        in system
    )


def test_a_customer_who_signs_the_opening_is_not_asked_their_name() -> None:
    """`tj-l0e3`. The round asked people it had just addressed by name.

    Production reads the name off this very message, so the ask is forbidden
    before generation. The harness derived the permission from a hardcoded
    `None` and told the model the opposite.
    """

    signed = build_generation_messages(
        opening="this is binu from bikram interiors sharjah.",
        language="en",
        catalog_evidence=[],
    )[0]["content"]
    anonymous = build_generation_messages(
        opening="I need an ergonomic chair",
        language="en",
        catalog_evidence=[],
    )[0]["content"]

    assert "- customer_name: forbidden" in str(signed)
    assert "- customer_name: allowed" in str(anonymous)


@pytest.mark.asyncio
async def test_the_guards_do_not_re_ask_a_name_the_opening_supplied() -> None:
    """The same parity gap, on the shipped-output side rather than the prompt."""

    result = await apply_shipped_output_guards(
        "Nice to meet you, Binu. What are you furnishing?",
        language="en",
        anchor_line=None,
        catalog_evidence=[],
        customer_message="this is binu from bikram interiors sharjah.",
    )

    assert "how should I address you" not in result.content


@pytest.mark.parametrize("second_reader", [False, True])
def test_every_model_the_round_pays_can_be_pinned(second_reader: bool) -> None:
    """The repair judge changed vendor and preflight died on a missing key."""
    for model in paid_models(second_reader=second_reader):
        assert model in PINNED_PARAMETER_REQUIREMENTS


async def test_a_slot_survives_an_upstream_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 200 with no completion produced nothing, so retrying re-rolls nothing."""
    bodies = [
        {
            "error": {
                "code": 429,
                "message": "temporarily rate-limited upstream",
            }
        },
        {
            "choices": [
                {"message": {"content": "A reply."}, "finish_reason": "stop"},
            ]
        },
    ]
    slept: list[float] = []

    async def request_once(
        _client: object, _payload: dict[str, object]
    ) -> tuple[dict[str, object], int]:
        return bodies.pop(0), 5

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._request_once",
        request_once,
    )

    async def sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance.asyncio.sleep",
        sleep,
    )

    _body, _latency, content, _finish, errors = await _generate_with_backoff(
        SimpleNamespace(),  # type: ignore[arg-type]
        {},
    )

    assert content == "A reply."
    assert slept == [GENERATION_RETRY_DELAYS_SECONDS[0]]
    assert errors == (
        "provider response has no choice: 429: temporarily rate-limited upstream",
    )


async def test_a_busy_provider_status_is_retried_and_a_bad_request_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 503 never reached a model; a 400 is a fault in what we sent."""
    calls: list[int] = []

    def _raise(status: int) -> None:
        request = httpx.Request("POST", "https://example.invalid/chat/completions")
        raise httpx.HTTPStatusError(
            f"status {status}",
            request=request,
            response=httpx.Response(status, request=request),
        )

    async def sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance.asyncio.sleep", sleep
    )

    async def busy_then_answer(
        _client: object, _payload: dict[str, object]
    ) -> tuple[dict[str, object], int]:
        calls.append(1)
        if len(calls) == 1:
            _raise(503)
        return (
            {
                "choices": [
                    {"message": {"content": "A reply."}, "finish_reason": "stop"}
                ]
            },
            5,
        )

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._request_once",
        busy_then_answer,
    )
    _body, _latency, content, _finish, errors = await _generate_with_backoff(
        SimpleNamespace(),  # type: ignore[arg-type]
        {},
    )
    assert content == "A reply."
    assert errors == ("provider returned 503",)

    async def bad_request(
        _client: object, _payload: dict[str, object]
    ) -> tuple[dict[str, object], int]:
        calls.append(1)
        _raise(400)
        raise AssertionError("unreachable")

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._request_once",
        bad_request,
    )
    before = len(calls)
    with pytest.raises(httpx.HTTPStatusError):
        await _generate_with_backoff(SimpleNamespace(), {})  # type: ignore[arg-type]
    assert len(calls) - before == 1


async def test_an_empty_completion_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A choice that came back blank is an answer we must not re-roll."""

    async def request_once(
        _client: object, _payload: dict[str, object]
    ) -> tuple[dict[str, object], int]:
        return {"choices": [{"message": {"content": "  "}}]}, 5

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._request_once",
        request_once,
    )

    with pytest.raises(ValueError, match="empty response"):
        await _generate_with_backoff(SimpleNamespace(), {})  # type: ignore[arg-type]


def test_the_summary_names_the_judge_that_actually_read_the_round() -> None:
    """A root-judged round used to report GLM as its judge."""
    results = [_result(dialog_id) for dialog_id in range(1, 21)]
    for row in results:
        row["judge_model"] = ROOT_JUDGE

    public = build_public_summary(
        results, bootstrap_samples=200, seed=17, expected_openings=20
    )

    assert public["judge_model"] == ROOT_JUDGE


def test_a_copied_sku_is_not_a_hallucinated_number() -> None:
    """One quoted identifier failed a whole round for hallucination."""
    case = {
        "opening": "can you share details of full height storage",
        "anchor_line": None,
        "catalog_evidence": [
            {
                "name": "Height Cabinet glass Skyland NOVO",
                "price_aed": 1274.0,
                "sku": "OF-YED-NOVO-Cabinet-63LW-1.2T-16-white",
            }
        ],
    }

    quoted = "Height Cabinet glass Skyland NOVO — AED 1,274\nSKU: `OF-YED-NOVO-Cabinet-63LW-1.2T-16-white`"
    assert find_ungrounded_numbers(quoted, case) == []

    invented = "SKU: `ZZ-9999-4.7T-11-black`"
    assert find_ungrounded_numbers(invented, case) == ["7"]


def test_the_round_never_pages_a_manager_about_its_own_repair_calls() -> None:
    """An offline measurement must not wake somebody when a vendor goes dark."""
    source = inspect.getsource(_journaled_repair_runner)
    assert "notify_on_failure=False" in source


def test_the_second_reader_is_pinned_only_when_it_was_authorized() -> None:
    """The scoring arm reads its provider route out of the pinned catalog."""
    assert SECOND_READER_MODEL not in paid_models(second_reader=False)
    assert SECOND_READER_MODEL in paid_models(second_reader=True)


@pytest.mark.asyncio
async def test_preflight_refuses_missing_semantic_evidence_before_provider_lookup(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch a keyword/fetch fallback or late validation re-entering the round."""
    scenarios_path = tmp_path / "scenarios.json"
    scenarios_path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-real-openings/v1",
                "selection_seed": 20260810,
                "scenarios": [
                    {
                        "dialog_id": dialog_id,
                        "length_stratum": (dialog_id - 1) // 5 + 1,
                        "opening": f"Opening {dialog_id}",
                    }
                    for dialog_id in range(1, 21)
                ],
            }
        ),
        encoding="utf-8",
    )

    async def provider_lookup_must_not_run(
        _models: tuple[str, ...],
    ) -> dict[str, dict[str, object]]:
        pytest.fail("provider lookup ran before semantic evidence validation")

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._pinned_model_catalog",
        provider_lookup_must_not_run,
    )

    with pytest.raises(ValueError, match="semantic retrieval evidence"):
        await preflight(
            scenarios_path=scenarios_path,
            retrieval_evidence_path=tmp_path / "missing-evidence.json",
            catalog_snapshot_path=tmp_path / "missing-snapshot.json",
            expected_catalog_sha256="a" * 64,
            expected_embedding_revision="b" * 40,
            expected_qrels_sha256="d" * 64,
            expected_pgvector_extension="0.8.1",
            output_dir=tmp_path / "protected",
            per_model_cap_usd=1.0,
        )


@pytest.mark.asyncio
async def test_preflight_withholds_rows_that_qrels_mark_irrelevant(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch nearest-but-irrelevant rows being handed to the reply generator."""
    scenarios = [
        {
            "dialog_id": dialog_id,
            "length_stratum": (dialog_id - 1) // 5 + 1,
            "opening": f"Opening {dialog_id}",
        }
        for dialog_id in range(1, 21)
    ]
    scenarios_path = tmp_path / "scenarios.json"
    scenarios_path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-real-openings/v1",
                "selection_seed": 20260810,
                "scenarios": scenarios,
            }
        ),
        encoding="utf-8",
    )
    snapshot_path, catalog_sha256 = _write_test_catalog_snapshot(
        tmp_path / "catalog-snapshot.json"
    )
    evidence_path = tmp_path / "retrieval-evidence.json"
    results: list[dict[str, object]] = []
    for scenario in scenarios:
        dialog_id = int(scenario["dialog_id"])
        products = (
            [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "sku": "ROW-1",
                    "name": "Nearest but unjudged row",
                    "category": "synthetic",
                    "price_aed": 500.0,
                    "stock": 3,
                }
            ]
            if dialog_id == 1
            else []
        )
        results.append(
            {
                "dialog_id": dialog_id,
                "query_sha256": hashlib.sha256(
                    str(scenario["opening"]).encode("utf-8")
                ).hexdigest(),
                "rows_present": bool(products),
                "catalog_relevant": False,
                "relevant_skus": [],
                "products": products,
            }
        )
    query_digest = hashlib.sha256(
        json.dumps(
            scenarios,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-semantic-catalog-evidence/v1",
                "catalog": {"sha256": catalog_sha256, "rows": 332},
                "embedding": {
                    "model": "BAAI/bge-m3",
                    "revision": "b" * 40,
                    "dimensions": 1024,
                    "normalized": True,
                },
                "retrieval": {
                    "entrypoint": "src.rag.pipeline.search_products",
                    "code_sha": retrieval_contract_sha(),
                    "pgvector_python": "0.4.2",
                    "pgvector_extension": "0.8.1",
                    "distance": "cosine",
                    "search_mode": "exact",
                    "ann_indexes": [],
                    "limit": 3,
                    "query_source": "frozen_opening",
                },
                "qrels": {"sha256": "d" * 64},
                "query_set": {"sha256": query_digest, "count": 20},
                "results": results,
            }
        ),
        encoding="utf-8",
    )
    evidence_path.chmod(0o600)

    async def model_catalog(models: tuple[str, ...]) -> dict[str, dict[str, object]]:
        return {
            model: {
                "id": model,
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                "provider_order": ["test"],
                "provider_quantizations": ["fp8"],
            }
            for model in models
        }

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._pinned_model_catalog",
        model_catalog,
    )

    document = await preflight(
        scenarios_path=scenarios_path,
        retrieval_evidence_path=evidence_path,
        catalog_snapshot_path=snapshot_path,
        expected_catalog_sha256=catalog_sha256,
        expected_embedding_revision="b" * 40,
        expected_qrels_sha256="d" * 64,
        expected_pgvector_extension="0.8.1",
        output_dir=tmp_path / "protected",
        per_model_cap_usd=1.0,
    )

    prepared = json.loads(
        (tmp_path / "protected" / "prepared-cases.json").read_text(encoding="utf-8")
    )
    assert prepared[0]["catalog_rows_present"] is True
    assert prepared[0]["catalog_relevant"] is False
    assert prepared[0]["catalog_evidence"] == []
    assert "Nearest but unjudged row" not in str(prepared[0]["generation_messages"])
    assert document["catalog_products"] == 332
    # `tj-rdqc`. Every opening carries the price production would prepend, and
    # the round records which catalog it was priced from.
    assert prepared[0]["anchor_line"] == (
        "Chairs from AED 140, desks and workstations from AED 1,813."
    )
    assert document["opening_anchor"] == {
        "source": "pinned_catalog_snapshot",
        "catalog_sha256": catalog_sha256,
        "lines": {
            "en": "Chairs from AED 140, desks and workstations from AED 1,813.",
            "ar": "الكراسي من 140 درهم, المكاتب ومحطات العمل من 1,813 درهم.",
        },
    }
    assert document["semantic_retrieval"] == {
        "catalog_sha256": catalog_sha256,
        "embedding_model": "BAAI/bge-m3",
        "embedding_revision": "b" * 40,
        "retrieval_code_sha": retrieval_contract_sha(),
        "qrels_sha256": "d" * 64,
        "query_set_sha256": query_digest,
        "pgvector_python": "0.4.2",
        "pgvector_extension": "0.8.1",
        "search_mode": "exact",
        "query_source": "frozen_opening",
    }


@pytest.mark.asyncio
async def test_preflight_refuses_a_snapshot_that_is_not_the_pinned_catalog(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`tj-rdqc`. The anchor is only faithful if it prices the pinned catalog.

    A snapshot that is not the one the retrieval artifact was built on would
    price one catalog and retrieve from another, which is the exact class of
    silent drift the evidence pin exists to stop. It fails closed, and before
    any provider is paid.
    """

    scenarios = [
        {
            "dialog_id": dialog_id,
            "length_stratum": (dialog_id - 1) // 5 + 1,
            "opening": f"Opening {dialog_id}",
        }
        for dialog_id in range(1, 21)
    ]
    scenarios_path = tmp_path / "scenarios.json"
    scenarios_path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-real-openings/v1",
                "selection_seed": 20260810,
                "scenarios": scenarios,
            }
        ),
        encoding="utf-8",
    )
    snapshot_path, catalog_sha256 = _write_test_catalog_snapshot(
        tmp_path / "catalog-snapshot.json"
    )
    evidence_path = _write_test_semantic_evidence(
        tmp_path / "retrieval-evidence.json",
        scenarios,
        catalog_sha256="a" * 64,
    )

    async def provider_lookup_must_not_run(
        _models: tuple[str, ...],
    ) -> dict[str, dict[str, object]]:
        pytest.fail("provider lookup ran before the catalog snapshot was checked")

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._pinned_model_catalog",
        provider_lookup_must_not_run,
    )

    assert catalog_sha256 != "a" * 64
    with pytest.raises(ValueError, match="does not match the pinned catalog"):
        await preflight(
            scenarios_path=scenarios_path,
            retrieval_evidence_path=evidence_path,
            catalog_snapshot_path=snapshot_path,
            expected_catalog_sha256="a" * 64,
            expected_embedding_revision="b" * 40,
            expected_qrels_sha256="d" * 64,
            expected_pgvector_extension="0.8.1",
            output_dir=tmp_path / "protected",
            per_model_cap_usd=1.0,
        )


def test_critical_failure_codes_combine_judge_and_deterministic_gates() -> None:
    """Catch a bad language or invented number being hidden by a clean judge."""
    assert critical_failure_codes(
        red_flag_codes=["ignored_question", "unverified_commitment"],
        ungrounded_numbers=["9000"],
        language_ok=False,
    ) == [
        "hallucination",
        "ignored_request",
        "unsafe_commitment",
        "wrong_language",
    ]


def test_numeric_grounding_normalizes_catalog_names_and_opening_ranges() -> None:
    """Catch catalog dimensions and formatting changes being called hallucinations."""
    case = {
        "opening": "Please deliver within 2-3 days",
        "catalog_evidence": [{"name": "Desk W1800xD800xH750", "price_aed": 1200.0}],
        "anchor_line": None,
    }

    assert (
        find_ungrounded_numbers(
            "The desk is 1,800 x 800 x 750 and costs AED 1,200; timeline 2–3 days.",
            case,
        )
        == []
    )
    assert find_ungrounded_numbers("Options start at AED 901.", case) == ["901"]


@pytest.mark.asyncio
async def test_the_harness_applies_the_guards_that_ship() -> None:
    """`tj-vz7o.10.1`. The round measured the model plus one guard.

    Production runs `apply_opening_guard`, then the deferral guard, then
    `enforce_grounding_output`, and only then does a customer see the text. A
    harness that stops after the first measures a reply that would never be
    sent. Neither failure found on 2026-08-10 was caused by this gap -- both
    survive the full pipeline -- but a defect production would have filtered
    cannot be told from a real one after the fact.
    """

    calls: list[RepairJudgeRequest] = []

    async def correct(request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        calls.append(request)
        return RepairJudgeProviderResult(
            decision=RepairJudgeDecision(
                answer="correct",
                corrected_text=(
                    "I can help you explore verified catalog options. "
                    "What are you furnishing?"
                ),
                rationale="Remove the unsupported service and keep useful help.",
            ),
            model=REPAIR_JUDGE_MODEL,
        )

    invented = await apply_shipped_output_guards(
        "We can assess and buy your used desks. What are you furnishing?",
        language="en",
        anchor_line=None,
        catalog_evidence=[],
        customer_message="I need an ergonomic chair.",
        runner=correct,
    )

    assert "buy your used desks" not in invented.content
    assert "What are you furnishing?" in invented.content
    assert invented.repair_trace is not None
    assert invented.repair_trace.counts.calls == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_a_price_on_a_retrieved_row_survives_without_a_repair_call() -> None:
    calls = 0

    async def fail_if_called(
        _request: RepairJudgeRequest,
    ) -> RepairJudgeProviderResult:
        nonlocal calls
        calls += 1
        raise AssertionError("a no-trigger reply must not call the repair judge")

    kept = await apply_shipped_output_guards(
        "The XTEN-S workstation is AED 566.87.",
        language="en",
        anchor_line=None,
        catalog_evidence=[{"name": "XTEN-S", "price_aed": 566.87, "stock": 4}],
        customer_message="What does XTEN-S cost?",
        runner=fail_if_called,
    )

    assert "566.87" in kept.content
    assert kept.repair_trace is None
    assert calls == 0


@pytest.mark.asyncio
async def test_triggered_harness_reply_matches_the_production_finalizer() -> None:
    raw = "We can assess and buy your used desks."
    state = ReplyPolicyState(language="en", is_first_turn=True)

    async def correct(_request: RepairJudgeRequest) -> RepairJudgeProviderResult:
        return RepairJudgeProviderResult(
            decision=RepairJudgeDecision(
                answer="correct",
                corrected_text="I can help you choose furniture from our catalog.",
                rationale="Use the supported catalog path.",
            ),
            model=REPAIR_JUDGE_MODEL,
        )

    harness = await apply_shipped_output_guards(
        raw,
        language="en",
        anchor_line=None,
        catalog_evidence=[],
        customer_message="Can you buy my desks?",
        runner=correct,
    )
    rendered = render_reply(raw, state=state, provenance="model")
    production = await _finalize_turn_response(
        SimpleNamespace(
            masked_text="Can you buy my desks?",
            pii_map={},
            deps=SimpleNamespace(
                executed_tool_names=(),
                conversation=SimpleNamespace(metadata_={}),
            ),
            _record_reply_on_conversation=lambda _model, _text: None,
        ),
        LLMResponse(
            text=rendered.text,
            tokens_in=10,
            tokens_out=10,
            cost=0.001,
            model=GENERATOR_MODEL,
            repair_flags=rendered.flags,
            repair_policy_state=state,
        ),
        runner=correct,
    )

    assert harness.content == production.text
    assert harness.repair_trace is not None
    assert production.repair_trace is not None
    assert harness.repair_trace.answer == production.repair_trace.answer == "correct"
    assert harness.repair_trace.counts == production.repair_trace.counts


@pytest.mark.asyncio
async def test_the_harness_commits_to_what_it_defers() -> None:
    committed = await apply_shipped_output_guards(
        "Whether assembly can be included still needs confirmation.",
        language="en",
        anchor_line=None,
        catalog_evidence=[],
        customer_message="Can assembly be included?",
    )

    assert (
        "I'll confirm assembly with our team and come back to you." in committed.content
    )


@pytest.mark.asyncio
async def test_a_second_reader_is_authorized_beside_the_root_never_instead(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`tj-4q79.1`. The flag replaced the judge the standing decision names.

    AGENTS.md: a paid model may be added beside the root reading, never in
    place of it, and the flag's own help text says the same. preflight set
    judge_model to the paid model, the round then skipped writing the pack the
    root reads, and ingest-judgment refused the root reading outright -- so no
    round could carry both, which is what tj-4q79 needs. The estimate also
    raised KeyError from the day the repair judge and the second reader became
    different vendors, so the flag had been dead since 2026-08-12.
    """

    scenarios_path = tmp_path / "scenarios.json"
    scenarios_path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-real-openings/v1",
                "selection_seed": 20260810,
                "scenarios": [
                    {
                        "dialog_id": dialog_id,
                        "length_stratum": (dialog_id - 1) // 5 + 1,
                        "opening": f"Opening {dialog_id}",
                    }
                    for dialog_id in range(1, 21)
                ],
            }
        ),
        encoding="utf-8",
    )
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))["scenarios"]
    snapshot_path, catalog_sha256 = _write_test_catalog_snapshot(
        tmp_path / "catalog-snapshot.json"
    )
    evidence_path = _write_test_semantic_evidence(
        tmp_path / "retrieval-evidence.json",
        scenarios,
        catalog_sha256=catalog_sha256,
    )

    async def model_catalog(models: tuple[str, ...]) -> dict[str, dict[str, object]]:
        return {
            model: {
                "id": model,
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                "provider_order": ["test"],
                "provider_quantizations": ["fp8"],
            }
            for model in models
        }

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._pinned_model_catalog",
        model_catalog,
    )

    document = await preflight(
        scenarios_path=scenarios_path,
        retrieval_evidence_path=evidence_path,
        catalog_snapshot_path=snapshot_path,
        expected_catalog_sha256=catalog_sha256,
        expected_embedding_revision="b" * 40,
        expected_qrels_sha256="d" * 64,
        expected_pgvector_extension="0.8.1",
        output_dir=tmp_path / "protected",
        per_model_cap_usd=1.0,
        second_reader=True,
    )

    assert document["judge_model"] == ROOT_JUDGE
    assert document["second_reader"] == SECOND_READER_MODEL
    # Its own budget. It shared the repair judge's until they split vendors.
    assert document["calls_per_model"][SECOND_READER_MODEL] == 20
    assert document["calls_per_model"][REPAIR_JUDGE_MODEL] == 20
    assert SECOND_READER_MODEL in document["estimated_cost_usd"]


@pytest.mark.asyncio
async def test_preflight_authorizes_the_repair_model_and_round_call_cap(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenarios_path = tmp_path / "scenarios.json"
    scenarios_path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-real-openings/v1",
                "selection_seed": 20260810,
                "scenarios": [
                    {
                        "dialog_id": dialog_id,
                        "length_stratum": (dialog_id - 1) // 5 + 1,
                        "opening": f"Opening {dialog_id}",
                    }
                    for dialog_id in range(1, 21)
                ],
            }
        ),
        encoding="utf-8",
    )
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))["scenarios"]
    snapshot_path, catalog_sha256 = _write_test_catalog_snapshot(
        tmp_path / "catalog-snapshot.json"
    )
    evidence_path = _write_test_semantic_evidence(
        tmp_path / "retrieval-evidence.json",
        scenarios,
        catalog_sha256=catalog_sha256,
    )
    requested_models: list[tuple[str, ...]] = []

    async def model_catalog(models: tuple[str, ...]) -> dict[str, dict[str, object]]:
        requested_models.append(models)
        return {
            model: {
                "id": model,
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                "provider_order": ["test"],
                "provider_quantizations": ["fp8"],
            }
            for model in models
        }

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._pinned_model_catalog",
        model_catalog,
    )

    document = await preflight(
        scenarios_path=scenarios_path,
        retrieval_evidence_path=evidence_path,
        catalog_snapshot_path=snapshot_path,
        expected_catalog_sha256=catalog_sha256,
        expected_embedding_revision="b" * 40,
        expected_qrels_sha256="d" * 64,
        expected_pgvector_extension="0.8.1",
        output_dir=tmp_path / "protected",
        per_model_cap_usd=1.0,
    )

    assert requested_models == [(GENERATOR_MODEL, REPAIR_JUDGE_MODEL)]
    assert document["calls_per_model"] == {
        GENERATOR_MODEL: 20,
        REPAIR_JUDGE_MODEL: 20,
        ROOT_JUDGE: 0,
    }
    assert document["repair_judge_authority"] == {
        "model": REPAIR_JUDGE_MODEL,
        "call_cap": 20,
    }


def _prepared_round_files(output_dir: pathlib.Path) -> None:
    output_dir.mkdir(mode=0o700)
    preflight_doc = {
        "schema_version": "treejar-real-opening-preflight/v1",
        "paid_calls_made": 0,
        "judge_model": ROOT_JUDGE,
        "scenario_digest": "a" * 64,
        "model_catalog": {
            GENERATOR_MODEL: {
                "provider_order": ["test"],
                "provider_quantizations": ["fp8"],
            },
            REPAIR_JUDGE_MODEL: {
                "provider_order": ["test"],
                "provider_quantizations": ["fp8"],
            },
        },
        "per_model_cap_usd": {
            GENERATOR_MODEL: 1.0,
            REPAIR_JUDGE_MODEL: 1.0,
            ROOT_JUDGE: 0.0,
        },
    }
    cases = [
        {
            "dialog_id": dialog_id,
            "length_stratum": (dialog_id - 1) // 5 + 1,
            "opening": f"Opening {dialog_id}",
            "language": "en",
            "catalog_evidence": [],
            "catalog_rows_present": False,
            "catalog_relevant": False,
            "anchor_line": None,
            "generation_messages": [
                {"role": "user", "content": f"Opening {dialog_id}"}
            ],
            "generation_prompt_digest": str(dialog_id).zfill(64),
        }
        for dialog_id in range(1, 21)
    ]
    for name, value in (
        ("preflight.json", preflight_doc),
        ("prepared-cases.json", cases),
    ):
        path = output_dir / name
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(0o600)


@pytest.mark.asyncio
@pytest.mark.parametrize("triggered", [False, True])
async def test_round_journals_only_triggered_repair_calls(
    triggered: bool,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / ("triggered" if triggered else "clean")
    _prepared_round_files(output_dir)
    generation_calls = 0
    repair_calls = 0

    async def request_once(
        _client: object,
        _payload: dict[str, object],
    ) -> tuple[dict[str, object], int]:
        nonlocal generation_calls
        generation_calls += 1
        content = (
            "We can assess and buy your used desks."
            if triggered and generation_calls == 1
            else "I can help you explore our office furniture catalog."
        )
        return (
            {
                "model": GENERATOR_MODEL,
                "choices": [
                    {
                        "message": {"content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 10,
                    "cost": 0.0001,
                },
            },
            5,
        )

    async def repair(
        request: RepairJudgeRequest,
        *,
        notify_on_failure: bool = True,
    ) -> RepairJudgeProviderResult:
        nonlocal repair_calls
        repair_calls += 1
        assert notify_on_failure is False
        return RepairJudgeProviderResult(
            decision=RepairJudgeDecision(
                answer="correct",
                corrected_text="I can help you choose furniture from our catalog.",
                rationale="Use the supported catalog path.",
            ),
            model=REPAIR_JUDGE_MODEL,
            prompt_tokens=20,
            completion_tokens=10,
            cost_usd=0.0002,
        )

    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._request_once",
        request_once,
    )
    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance.run_repair_judge",
        repair,
    )
    monkeypatch.setattr(
        "scripts.corpus_bridge.real_opening_acceptance._provider_headers",
        lambda _title: {},
    )

    result = await run_paid_round(output_dir)
    state = json.loads((output_dir / "run-state.json").read_text(encoding="utf-8"))
    repair_pack = json.loads(
        (output_dir / "repair-reading-pack.json").read_text(encoding="utf-8")
    )

    assert result["generation_complete"] is True
    assert generation_calls == 20
    assert repair_calls == int(triggered)
    assert state["calls_started_by_arm"] == {
        "generation": 20,
        "repair_judge": int(triggered),
        "scoring_judge": 0,
    }
    assert state["calls_started"][REPAIR_JUDGE_MODEL] == int(triggered)
    assert len(repair_pack) == int(triggered)
    if triggered:
        first = state["records"]["1"]
        assert first["repair_judge"]["answer"] == "correct"
        assert "buy your used desks" not in first["generation"]["content"]


def test_the_round_judges_itself_unless_a_second_reader_is_asked_for() -> None:
    """The owner's standing decision, as a default rather than a directive.

    The judge is the orchestrator reading blind. A paid model may be added
    beside that reading; it may not replace it. `preflight` therefore has to be
    told `--second-reader` before any judging call can be paid for, and the run
    that is not told stops after the generation arm.
    """

    signature = inspect.signature(preflight)
    assert signature.parameters["second_reader"].default is False

    argv = [
        "preflight",
        "--scenarios",
        "s.json",
        "--retrieval-evidence",
        "evidence.json",
        "--catalog-snapshot",
        "snapshot.json",
        "--catalog-sha256",
        "a" * 64,
        "--embedding-revision",
        "b" * 40,
        "--qrels-sha256",
        "d" * 64,
        "--pgvector-extension",
        "0.8.1",
        "--output-dir",
        "out",
    ]
    with patch.object(sys, "argv", ["prog", *argv]):
        parsed = _parse_args()
        assert parsed.second_reader is False
        assert parsed.retrieval_evidence == pathlib.Path("evidence.json")
        assert parsed.catalog_sha256 == "a" * 64
        assert parsed.embedding_revision == "b" * 40
        assert parsed.qrels_sha256 == "d" * 64
        assert parsed.pgvector_extension == "0.8.1"
    with patch.object(sys, "argv", ["prog", *argv, "--second-reader"]):
        assert _parse_args().second_reader is True


def test_a_root_judged_result_is_a_complete_result() -> None:
    """The scoring path is the same one either judge feeds."""

    results = [_result(index) for index in range(1, 21)]
    for item in results:
        item["judge_model"] = ROOT_JUDGE
        item["glm_latency_ms"] = 0

    validate_complete_results(results, expected_dialog_ids=set(range(1, 21)))

    results[0]["judge_model"] = "anthropic/claude-haiku-4.5"
    with pytest.raises(ValueError, match="root judge"):
        validate_complete_results(results, expected_dialog_ids=set(range(1, 21)))


# --- the pin lives in the repository, not on the command line --------------


def test_a_measured_round_pins_its_evidence_identity_without_the_operator() -> None:
    """Required flags made the pin only as strong as what was typed."""

    argv = [
        "preflight",
        "--scenarios",
        "scenarios.json",
        "--retrieval-evidence",
        "evidence.json",
        "--catalog-snapshot",
        "snapshot.json",
        "--output-dir",
        "out",
    ]
    with patch.object(sys, "argv", ["prog", *argv]):
        args = _parse_args()

    assert args.catalog_sha256 == PINNED_CATALOG_SHA256
    assert args.embedding_revision == PINNED_EMBEDDING_REVISION
    assert args.pgvector_extension == PINNED_PGVECTOR_EXTENSION
    assert (
        _qrels_sha256_for_set(args.frozen_set, args.qrels_sha256)
        == (PINNED_QRELS_SHA256[args.frozen_set])
    )


def test_a_set_with_no_pinned_qrels_stops_the_round() -> None:
    """`arabic-12` is registered and measurable, and has no semantic qrels."""

    assert "arabic-12" in FROZEN_SETS
    assert "arabic-12" not in PINNED_QRELS_SHA256

    with pytest.raises(ValueError, match="no pinned qrels digest"):
        _qrels_sha256_for_set("arabic-12", None)

    explicit = "f" * 64
    assert _qrels_sha256_for_set("arabic-12", explicit) == explicit
