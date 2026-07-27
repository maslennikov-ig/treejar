"""Local fixture runner for the Noor E2E acceptance evidence contract."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from scripts.e2e_acceptance.evaluators import evaluate_scenario
from scripts.e2e_acceptance.evidence import (
    EvidenceError,
    EvidenceStore,
    redact_payload,
    validate_side_effect_closeout,
)
from scripts.e2e_acceptance.manifest import (
    ManifestValidationError,
    build_scenario_binding,
    validate_preflight,
)
from scripts.e2e_acceptance.schemas import (
    AuthorizationManifest,
    AuthorizationQuotas,
    PreflightObservation,
    PreflightRequest,
    RuntimeIdentity,
    ScenarioSet,
)


class RunnerError(ValueError):
    """A dry-run fixture or execution boundary is invalid."""


class UsageTotals(TypedDict):
    scenarios: int
    messages: int
    model_calls: int
    token_count: int
    cost_usd: float
    subsystem_usage: dict[str, int]
    cumulative: NotRequired[UsageTotals]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class PlannedTurn(_StrictModel):
    turn_id: str = Field(min_length=1)
    customer_text: str = Field(min_length=1)
    expected_behavior: str = Field(min_length=1)
    criterion_ids: list[str] = Field(min_length=1)
    deterministic_check_ids: list[str] = Field(min_length=1)


class TurnTimestamps(_StrictModel):
    sent_at: datetime
    received_at: datetime
    first_visible_at: datetime
    final_visible_at: datetime
    delivered_at: datetime | None = None

    @model_validator(mode="after")
    def _ordered_timezone_aware(self) -> TurnTimestamps:
        values = [
            self.sent_at,
            self.received_at,
            self.first_visible_at,
            self.final_visible_at,
        ]
        if any(item.tzinfo is None or item.utcoffset() is None for item in values):
            raise ValueError("turn timestamps must be timezone-aware")
        if values != sorted(values):
            raise ValueError("turn timestamp order is invalid")
        if self.delivered_at is not None and (
            self.delivered_at.tzinfo is None
            or self.delivered_at.utcoffset() is None
            or self.delivered_at < self.final_visible_at
        ):
            raise ValueError("delivery timestamp is invalid")
        return self


class ActualTurn(_StrictModel):
    turn_id: str = Field(min_length=1)
    planned_turn_id: str | None = None
    conversation_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    provider_message_id: str | None
    customer_text: str = Field(min_length=1)
    assistant_text: str = Field(min_length=1)
    original_language: Literal["en", "ar", "mixed"]
    translation: str | None
    translation_provenance: dict[str, Any] | None
    timestamps: TurnTimestamps
    model: str = Field(min_length=1)
    routing_suffix: str | None = None
    media_refs: list[str] = Field(default_factory=list)
    tools: list[str]
    tool_outcomes: list[str] = Field(default_factory=list)
    audit_ids: list[str]
    expected_behavior: str = Field(min_length=1)
    actual_observation: str = Field(min_length=1)
    criterion_ids: list[str] = Field(min_length=1)
    beads_ids: list[str] = Field(min_length=1)
    deterministic_check_ids: list[str] = Field(min_length=1)
    token_count: int = Field(ge=0)
    cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def _translation_required_for_arabic(self) -> ActualTurn:
        if self.original_language == "ar" and (
            not self.translation or not self.translation_provenance
        ):
            raise ValueError(
                "Arabic turn requires Russian translation and translation provenance"
            )
        return self


class AdaptiveDeviation(_StrictModel):
    planned_turn_id: str = Field(min_length=1)
    actual_turn_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class OracleDefinition(_StrictModel):
    type: Literal["required_substring_present", "forbidden_substring_absent"]
    field: Literal["assistant_text"]
    value: str = Field(min_length=1)


class DeterministicCheck(_StrictModel):
    check_id: str = Field(min_length=1)
    hard_safety: bool
    turn_ids: list[str] = Field(min_length=1)
    oracle: OracleDefinition


class JudgeConfig(_StrictModel):
    model: str = Field(min_length=1)
    reasoning_effort: str = Field(min_length=1)
    max_calls: int = Field(ge=1)
    temperature: float
    rubric: str = Field(min_length=1)
    rubric_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    passed: bool
    reasoning: str = Field(min_length=1)
    calls_used: int = Field(ge=0)
    token_count: int = Field(ge=0)
    cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def _rubric_digest_matches(self) -> JudgeConfig:
        if self.rubric_digest != _canonical_digest(self.rubric):
            raise ValueError("judge rubric digest mismatch")
        if self.calls_used > self.max_calls:
            raise ValueError("judge call usage exceeds configured maximum")
        return self


class TesterConfig(_StrictModel):
    model: str = Field(min_length=1)
    reasoning_effort: str = Field(min_length=1)
    seed: int = Field(ge=0)
    prompt: str = Field(min_length=1)
    prompt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    max_calls: int = Field(ge=0)
    calls_used: int = Field(ge=0)
    token_count: int = Field(ge=0)
    cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def _prompt_digest_matches(self) -> TesterConfig:
        if self.prompt_digest != _canonical_digest(self.prompt):
            raise ValueError("tester prompt digest mismatch")
        if self.calls_used > self.max_calls:
            raise ValueError("tester call usage exceeds configured maximum")
        return self


class RetestMetadata(_StrictModel):
    retest_of: str = Field(pattern=r"^attempt-\d{3}$")
    defect_id: str = Field(min_length=1)
    fix_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    deployment_identity: str = Field(min_length=1)


class SideEffectReadback(_StrictModel):
    schema_version: Literal["noor-e2e-side-effect-readback/v1"]
    source_id: str = Field(min_length=1)
    observed_at: datetime
    authorization_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    inventory: dict[str, dict[str, Any]]

    @model_validator(mode="after")
    def _explicit_provenance(self) -> SideEffectReadback:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("readback observation time must be timezone-aware")
        if not self.inventory:
            raise ValueError("independent readback inventory is required")
        return self


class RunContext(_StrictModel):
    started_at_utc: datetime
    started_at_moscow: datetime
    retention_expires_at: datetime
    expected_identity: RuntimeIdentity
    actual_identity: RuntimeIdentity
    authorization_id: str = Field(min_length=1)
    authorization_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_target_refs: list[str] = Field(min_length=1)
    quotas: AuthorizationQuotas
    harness_version: str = Field(min_length=1)
    available_tools: list[str]

    @model_validator(mode="after")
    def _timestamps_and_identity_are_explicit(self) -> RunContext:
        if (
            self.started_at_utc.tzinfo is None
            or self.started_at_moscow.tzinfo is None
            or self.retention_expires_at.tzinfo is None
            or self.started_at_utc.utcoffset() is None
            or self.started_at_moscow.utcoffset() is None
            or self.retention_expires_at.utcoffset() is None
        ):
            raise ValueError("run timestamps must be timezone-aware")
        if not self.expected_identity or not self.actual_identity:
            raise ValueError("expected and actual runtime identities are required")
        if self.expected_identity != self.actual_identity:
            raise ValueError("runtime identity drift")
        if self.retention_expires_at <= self.started_at_utc:
            raise ValueError("retention expiry must follow run creation")
        return self


class DryRunFixture(_StrictModel):
    schema_version: Literal["noor-e2e-dry-run-fixture/v1"]
    scenario_id: str = Field(min_length=1)
    attempt_number: int = Field(ge=1)
    previous_attempt_sha256: str | None
    retest: RetestMetadata | None
    run_context: RunContext
    planned_turns: list[PlannedTurn] = Field(min_length=1)
    actual_turns: list[ActualTurn] = Field(min_length=1)
    adaptive_deviations: list[AdaptiveDeviation]
    deterministic_checks: list[DeterministicCheck] = Field(min_length=1)
    judge: JudgeConfig
    tester: TesterConfig
    side_effects: list[dict[str, Any]]

    @model_validator(mode="after")
    def _turn_correlations_are_complete(self) -> DryRunFixture:
        planned_ids = {turn.turn_id for turn in self.planned_turns}
        actual_ids = {turn.turn_id for turn in self.actual_turns}
        check_ids = {check.check_id for check in self.deterministic_checks}
        if len(planned_ids) != len(self.planned_turns):
            raise ValueError("planned turn IDs must be unique")
        if len(actual_ids) != len(self.actual_turns):
            raise ValueError("actual turn IDs must be unique")
        if len(check_ids) != len(self.deterministic_checks):
            raise ValueError("deterministic check IDs must be unique")
        deviations = {
            (item.planned_turn_id, item.actual_turn_id)
            for item in self.adaptive_deviations
        }
        for turn in self.actual_turns:
            planned_id = turn.planned_turn_id or turn.turn_id
            if planned_id not in planned_ids:
                raise ValueError(f"actual turn has unknown plan: {turn.turn_id}")
            if (
                turn.turn_id != planned_id
                and (planned_id, turn.turn_id) not in deviations
            ):
                raise ValueError(
                    f"adaptive turn lacks explained deviation: {turn.turn_id}"
                )
            unknown_checks = set(turn.deterministic_check_ids) - check_ids
            if unknown_checks:
                raise ValueError(
                    f"actual turn references unknown deterministic checks: "
                    f"{sorted(unknown_checks)}"
                )
        referenced_checks = {
            check_id
            for turn in self.actual_turns
            for check_id in turn.deterministic_check_ids
        }
        if referenced_checks != check_ids:
            raise ValueError("deterministic checks must be referenced by actual turns")
        for check in self.deterministic_checks:
            if not set(check.turn_ids) <= actual_ids:
                raise ValueError(
                    f"deterministic oracle references unknown turns: {check.check_id}"
                )
        if self.attempt_number == 1:
            if self.previous_attempt_sha256 is not None or self.retest is not None:
                raise ValueError("first attempt cannot carry retest linkage")
        elif (
            self.previous_attempt_sha256 is None
            or len(self.previous_attempt_sha256) != 64
            or self.retest is None
            or self.retest.retest_of != f"attempt-{self.attempt_number - 1:03d}"
        ):
            raise ValueError("retest attempt requires previous hash and exact linkage")
        if (
            self.retest is not None
            and self.retest.deployment_identity
            != self.run_context.actual_identity.deployed_release_sha
        ):
            raise ValueError("retest deployment identity differs from actual release")
        return self


_OPEN_EN_CHECKPOINTS = (
    "English Noor and Treejar opener",
    "Name requested without product or quote side effect",
    "Bare name accepted",
    "Original chair request resumed",
)
_OPEN_EN_PROHIBITED = (
    "Siyyad identity",
    "Repeated name question",
    "Premature CRM quotation or manager handoff",
)
_OPEN_EN_ORACLE_POLICY: tuple[dict[str, object], ...] = (
    {
        "check_id": "cp-english-opener",
        "source_kind": "checkpoint",
        "source_text": _OPEN_EN_CHECKPOINTS[0],
        "hard_safety": False,
        "planned_turn_ids": ["turn-001"],
        "oracle": {
            "type": "required_substring_present",
            "field": "assistant_text",
            "value": "Noor from Treejar",
        },
    },
    {
        "check_id": "cp-name-requested",
        "source_kind": "checkpoint",
        "source_text": _OPEN_EN_CHECKPOINTS[1],
        "hard_safety": False,
        "planned_turn_ids": ["turn-001"],
        "oracle": {
            "type": "required_substring_present",
            "field": "assistant_text",
            "value": "What should I call you",
        },
    },
    {
        "check_id": "cp-bare-name-accepted",
        "source_kind": "checkpoint",
        "source_text": _OPEN_EN_CHECKPOINTS[2],
        "hard_safety": False,
        "planned_turn_ids": ["turn-002"],
        "oracle": {
            "type": "required_substring_present",
            "field": "assistant_text",
            "value": "Nice to meet you, Lina",
        },
    },
    {
        "check_id": "cp-original-request-resumed",
        "source_kind": "checkpoint",
        "source_text": _OPEN_EN_CHECKPOINTS[3],
        "hard_safety": False,
        "planned_turn_ids": ["turn-002"],
        "oracle": {
            "type": "required_substring_present",
            "field": "assistant_text",
            "value": "continue with chairs",
        },
    },
    {
        "check_id": "po-siyyad-identity",
        "source_kind": "prohibited_outcome",
        "source_text": _OPEN_EN_PROHIBITED[0],
        "hard_safety": True,
        "planned_turn_ids": ["turn-001", "turn-002"],
        "oracle": {
            "type": "forbidden_substring_absent",
            "field": "assistant_text",
            "value": "Siyyad",
        },
    },
    {
        "check_id": "po-repeated-name-question",
        "source_kind": "prohibited_outcome",
        "source_text": _OPEN_EN_PROHIBITED[1],
        "hard_safety": True,
        "planned_turn_ids": ["turn-002"],
        "oracle": {
            "type": "forbidden_substring_absent",
            "field": "assistant_text",
            "value": "What should I call you",
        },
    },
    {
        "check_id": "po-premature-commercial-side-effect",
        "source_kind": "prohibited_outcome",
        "source_text": _OPEN_EN_PROHIBITED[2],
        "hard_safety": True,
        "planned_turn_ids": ["turn-001", "turn-002"],
        "oracle": {
            "type": "forbidden_substring_absent",
            "field": "assistant_text",
            "value": "quotation",
        },
    },
)


def _canonical_oracle_policy(
    fixture: DryRunFixture,
    *,
    checkpoints: list[str],
    prohibited_outcomes: list[str],
) -> list[dict[str, object]]:
    if fixture.scenario_id != "SC-OPEN-EN":
        raise RunnerError(
            f"no code-owned canonical oracle policy for {fixture.scenario_id}"
        )
    if (
        tuple(checkpoints) != _OPEN_EN_CHECKPOINTS
        or tuple(prohibited_outcomes) != _OPEN_EN_PROHIBITED
    ):
        raise RunnerError("canonical scenario checkpoint/prohibited outcome drift")
    actual_by_plan = {
        turn.planned_turn_id or turn.turn_id: turn.turn_id
        for turn in fixture.actual_turns
    }
    materialized: list[dict[str, object]] = []
    for policy in _OPEN_EN_ORACLE_POLICY:
        planned_turn_ids = policy["planned_turn_ids"]
        if not isinstance(planned_turn_ids, list) or not all(
            isinstance(item, str) and item in actual_by_plan
            for item in planned_turn_ids
        ):
            raise RunnerError("canonical oracle policy lacks exact plan coverage")
        materialized.append(
            {
                "check_id": policy["check_id"],
                "hard_safety": policy["hard_safety"],
                "turn_ids": [actual_by_plan[item] for item in planned_turn_ids],
                "oracle": policy["oracle"],
            }
        )
    return materialized


def load_dry_run_fixture(path: Path) -> DryRunFixture:
    if path.is_symlink() or not path.is_file():
        raise RunnerError(f"dry-run fixture is not a regular file: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return DryRunFixture.model_validate(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise RunnerError(f"invalid dry-run fixture: {exc}") from exc


def load_side_effect_readback(path: Path) -> SideEffectReadback:
    if path.is_symlink() or not path.is_file():
        raise RunnerError(f"readback is not a regular file: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return SideEffectReadback.model_validate(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise RunnerError(f"invalid independent readback: {exc}") from exc


class AcceptanceRunner:
    """Execute deterministic fixtures only; live adapters belong to Task 3."""

    def __init__(
        self,
        *,
        repo_root: Path,
        protected_root: Path,
        dry_run: bool,
        scenario_set: ScenarioSet,
        scenario_set_path: Path,
        authorization: AuthorizationManifest,
        observation: PreflightObservation,
        request: PreflightRequest,
        readback: SideEffectReadback,
        preflight_now: datetime,
    ) -> None:
        if not dry_run:
            raise RunnerError(
                "Task 2 runner is dry-run only; live execution requires Task 3"
            )
        self.store = EvidenceStore(
            repo_root=repo_root,
            protected_root=protected_root,
        )
        try:
            validate_preflight(
                authorization,
                observation,
                request,
                now=preflight_now,
            )
            canonical_binding = build_scenario_binding(
                scenario_set,
                scenario_set_path,
                executable_input_digests=(
                    authorization.scenario_binding.executable_input_digests
                ),
            )
        except ManifestValidationError as exc:
            raise RunnerError(f"authorization preflight failed: {exc}") from exc
        if canonical_binding != authorization.scenario_binding:
            raise RunnerError("authorization canonical scenario binding drift")
        self.scenario_set = scenario_set
        self.authorization = authorization
        readback_identity = observation.readback_identity
        readback_digest = _canonical_digest(readback.model_dump(mode="json"))
        if (
            readback_identity is None
            or readback_identity.source_id != readback.source_id
            or readback_identity.observed_at != readback.observed_at
            or readback_identity.content_digest != readback_digest
            or readback.authorization_id != authorization.authorization_id
            or readback.observed_at > preflight_now
            or readback.observed_at < authorization.issued_at
        ):
            raise RunnerError("independent readback provenance drift")
        self.readback = readback
        self.readback_digest = readback_digest
        self.authorization_digest = _canonical_digest(
            authorization.model_dump(mode="json")
        )

    def _fixture_input_digests(self, fixture: DryRunFixture) -> dict[str, str]:
        scenario_id = fixture.scenario_id
        return {
            f"{scenario_id}:planned_turns": _canonical_digest(
                [item.model_dump(mode="json") for item in fixture.planned_turns]
            ),
            f"{scenario_id}:tester_prompt": _canonical_digest(fixture.tester.prompt),
            f"{scenario_id}:judge_rubric": _canonical_digest(fixture.judge.rubric),
            f"{scenario_id}:deterministic_oracles": _canonical_digest(
                [item.model_dump(mode="json") for item in fixture.deterministic_checks]
            ),
            f"{scenario_id}:side_effect_readback": self.readback_digest,
        }

    @staticmethod
    def _evaluate_oracles(
        fixture: DryRunFixture,
    ) -> list[dict[str, object]]:
        turns = {turn.turn_id: turn for turn in fixture.actual_turns}
        results: list[dict[str, object]] = []
        for check in fixture.deterministic_checks:
            values = [
                str(getattr(turns[turn_id], check.oracle.field))
                for turn_id in check.turn_ids
            ]
            if check.oracle.type == "required_substring_present":
                passed = all(check.oracle.value in value for value in values)
            else:
                passed = all(check.oracle.value not in value for value in values)
            results.append(
                {
                    "check_id": check.check_id,
                    "passed": passed,
                    "hard_safety": check.hard_safety,
                    "reasoning": (
                        f"Bound oracle {check.oracle.type} evaluated "
                        f"{len(values)} authorized turn(s)."
                    ),
                    "oracle_digest": _canonical_digest(check.model_dump(mode="json")),
                }
            )
        return results

    @staticmethod
    def _validate_actual_bindings(
        fixture: DryRunFixture,
        *,
        canonical_criterion_ids: list[str],
        canonical_checks: list[dict[str, object]],
    ) -> None:
        planned_by_id = {turn.turn_id: turn for turn in fixture.planned_turns}
        actual_by_plan: dict[str, ActualTurn] = {}
        for turn in fixture.actual_turns:
            planned_id = turn.planned_turn_id or turn.turn_id
            if planned_id in actual_by_plan:
                raise RunnerError("actual turn binding duplicates a planned turn")
            actual_by_plan[planned_id] = turn
        if set(actual_by_plan) != set(planned_by_id):
            raise RunnerError("actual turn binding lacks exact plan coverage")

        expected_deviations: set[tuple[str, str]] = set()
        for planned_id, planned in planned_by_id.items():
            actual = actual_by_plan[planned_id]
            if (
                actual.turn_id != planned_id
                or actual.customer_text != planned.customer_text
            ):
                expected_deviations.add((planned_id, actual.turn_id))
            if (
                actual.expected_behavior != planned.expected_behavior
                or actual.criterion_ids != planned.criterion_ids
                or actual.deterministic_check_ids != planned.deterministic_check_ids
            ):
                raise RunnerError(f"actual turn binding drift for {actual.turn_id}")
            if actual.customer_text != planned.customer_text and (
                planned_id,
                actual.turn_id,
            ) not in {
                (item.planned_turn_id, item.actual_turn_id)
                for item in fixture.adaptive_deviations
            }:
                raise RunnerError(
                    f"actual turn binding customer drift for {actual.turn_id}"
                )
        actual_deviations = {
            (item.planned_turn_id, item.actual_turn_id)
            for item in fixture.adaptive_deviations
        }
        if actual_deviations != expected_deviations:
            raise RunnerError("adaptive deviations do not match actual plan drift")

        planned_criteria = {
            criterion_id
            for turn in fixture.planned_turns
            for criterion_id in turn.criterion_ids
        }
        if planned_criteria != set(canonical_criterion_ids):
            raise RunnerError("actual turn binding lacks canonical criterion coverage")
        planned_checks = {
            check_id
            for turn in fixture.planned_turns
            for check_id in turn.deterministic_check_ids
        }
        canonical_check_ids = {str(check["check_id"]) for check in canonical_checks}
        if planned_checks != canonical_check_ids:
            raise RunnerError(
                "actual turn binding lacks checkpoint/prohibited outcome coverage"
            )

    @staticmethod
    def _attempt_usage(fixture: DryRunFixture) -> UsageTotals:
        model_calls = (
            len(fixture.actual_turns)
            + fixture.tester.calls_used
            + fixture.judge.calls_used
        )
        cost_usd = (
            sum(turn.cost_usd for turn in fixture.actual_turns)
            + fixture.tester.cost_usd
            + fixture.judge.cost_usd
        )
        token_count = (
            sum(turn.token_count for turn in fixture.actual_turns)
            + fixture.tester.token_count
            + fixture.judge.token_count
        )
        messages = len(fixture.actual_turns)
        subsystem_usage: dict[str, int] = {
            "application_native_webhook": messages,
            "outbound_text": messages,
        }
        artifact_quota_keys = {
            "crm_contact": "crm_contact_create",
            "crm_deal": "crm_deal_create",
            "crm_stage_transition": "crm_stage_transition",
            "quotation": "quotation_create",
            "sale_order": "sale_order_create",
            "telegram_alert": "telegram_alert",
            "callback": "telegram_callback",
            "followup": "followup_synthetic",
            "feedback": "feedback_synthetic",
            "referral": "referral_synthetic",
            "reward": "referral_synthetic",
        }
        for entry in fixture.side_effects:
            quota_key = artifact_quota_keys.get(str(entry.get("artifact_type", "")))
            if quota_key is not None:
                subsystem_usage[quota_key] = subsystem_usage.get(quota_key, 0) + 1
        return {
            "scenarios": 1,
            "messages": messages,
            "model_calls": model_calls,
            "token_count": token_count,
            "cost_usd": cost_usd,
            "subsystem_usage": subsystem_usage,
        }

    def _validate_quotas(
        self,
        fixture: DryRunFixture,
        *,
        prior_attempts: list[dict[str, Any]],
    ) -> UsageTotals:
        usage = self._attempt_usage(fixture)
        prior_scenario_ids: set[str] = set()
        cumulative_messages = usage["messages"]
        cumulative_model_calls = usage["model_calls"]
        cumulative_tokens = usage["token_count"]
        cumulative_cost = usage["cost_usd"]
        cumulative_subsystems = dict(usage["subsystem_usage"])
        for attempt in prior_attempts:
            prior_scenario_id = attempt.get("scenario_id")
            prior_usage = attempt.get("usage")
            if not isinstance(prior_scenario_id, str) or not isinstance(
                prior_usage, dict
            ):
                raise RunnerError("cumulative quota evidence is incomplete")
            prior_messages = prior_usage.get("messages")
            prior_model_calls = prior_usage.get("model_calls")
            prior_tokens = prior_usage.get("token_count")
            prior_cost = prior_usage.get("cost_usd")
            if (
                not isinstance(prior_messages, int)
                or not isinstance(prior_model_calls, int)
                or not isinstance(prior_tokens, int)
                or not isinstance(prior_cost, (int, float))
            ):
                raise RunnerError("cumulative quota evidence has invalid totals")
            prior_scenario_ids.add(prior_scenario_id)
            cumulative_messages += prior_messages
            cumulative_model_calls += prior_model_calls
            cumulative_tokens += prior_tokens
            cumulative_cost += float(prior_cost)
            prior_subsystems = prior_usage.get("subsystem_usage")
            if not isinstance(prior_subsystems, dict):
                raise RunnerError("cumulative subsystem quota evidence is incomplete")
            for key, value in prior_subsystems.items():
                if not isinstance(value, int):
                    raise RunnerError(
                        "cumulative subsystem quota evidence has invalid totals"
                    )
                cumulative_subsystems[str(key)] = (
                    cumulative_subsystems.get(str(key), 0) + value
                )
        cumulative_scenarios = len(prior_scenario_ids | {fixture.scenario_id})
        cumulative_usage: UsageTotals = {
            "scenarios": cumulative_scenarios,
            "messages": cumulative_messages,
            "model_calls": cumulative_model_calls,
            "token_count": cumulative_tokens,
            "cost_usd": cumulative_cost,
            "subsystem_usage": cumulative_subsystems,
        }
        quotas = self.authorization.quotas
        qualifier = "cumulative " if prior_attempts else "authorization "
        if cumulative_scenarios > quotas.max_scenarios:
            raise RunnerError(f"{qualifier}scenario quota is insufficient")
        if cumulative_messages > quotas.max_messages:
            raise RunnerError(f"{qualifier}message quota is insufficient")
        if cumulative_model_calls > quotas.max_model_calls:
            raise RunnerError(f"{qualifier}model-call quota is insufficient")
        if cumulative_cost > quotas.max_cost_usd:
            raise RunnerError(f"{qualifier}cost quota is insufficient")
        subsystem_usage = cumulative_subsystems
        if not isinstance(subsystem_usage, dict):
            raise RunnerError("subsystem quota accounting is invalid")
        for key, used in subsystem_usage.items():
            allowed = quotas.subsystem_quotas.get(key, 0)
            if int(used) > allowed:
                raise RunnerError(f"{qualifier}subsystem quota is insufficient: {key}")
        usage["cumulative"] = cumulative_usage
        return usage

    def run_fixture(
        self,
        *,
        run_id: str,
        fixture: DryRunFixture,
    ) -> dict[str, Any]:
        selected = next(
            (
                item
                for item in self.scenario_set.scenarios
                if item.scenario_id == fixture.scenario_id
            ),
            None,
        )
        if selected is None:
            raise RunnerError(
                f"fixture scenario is absent from scenario set: {fixture.scenario_id}"
            )
        if self.readback.scenario_id != fixture.scenario_id:
            raise RunnerError("independent readback scenario drift")
        expected_seed = self.scenario_set.deterministic_seed
        if fixture.tester.seed != expected_seed:
            raise RunnerError("tester seed drift from scenario set")
        actual_digests = self._fixture_input_digests(fixture)
        authorized_digests = (
            self.authorization.scenario_binding.executable_input_digests
        )
        if any(
            authorized_digests.get(key) != value
            for key, value in actual_digests.items()
        ):
            raise RunnerError("authorization executable input drift")
        canonical_checks = _canonical_oracle_policy(
            fixture,
            checkpoints=selected.checkpoints,
            prohibited_outcomes=selected.prohibited_outcomes,
        )
        if [
            item.model_dump(mode="json") for item in fixture.deterministic_checks
        ] != canonical_checks:
            raise RunnerError("canonical oracle policy drift")
        self._validate_actual_bindings(
            fixture,
            canonical_criterion_ids=selected.criterion_ids,
            canonical_checks=canonical_checks,
        )
        context = fixture.run_context
        if (
            context.authorization_id != self.authorization.authorization_id
            or context.authorization_manifest_digest != self.authorization_digest
            or context.expected_identity != self.authorization.expected_identity
            or context.actual_identity != context.expected_identity
            or context.quotas != self.authorization.quotas
            or context.approved_target_refs
            != list(self.authorization.targets.model_dump(mode="json").values())
        ):
            raise RunnerError("authorization or run identity proof drift")
        if not set(selected.required_permissions) <= set(
            self.authorization.permissions
        ):
            raise RunnerError("authorization lacks scenario permissions")
        try:
            prior_attempts = self.store.verified_attempt_payloads(run_id)
        except EvidenceError as exc:
            raise RunnerError(f"cumulative quota evidence failed: {exc}") from exc
        usage = self._validate_quotas(
            fixture,
            prior_attempts=prior_attempts,
        )

        deterministic_results = self._evaluate_oracles(fixture)
        evaluation = evaluate_scenario(
            deterministic_checks=deterministic_results,
            judge=fixture.judge.model_dump(mode="json"),
        )
        validate_side_effect_closeout(
            fixture.side_effects,
            observed_inventory=self.readback.inventory,
        )
        attempt_id = f"attempt-{fixture.attempt_number:03d}"
        result: dict[str, Any] = {
            "schema_version": "noor-e2e-scenario-attempt/v1",
            "attempt_id": attempt_id,
            "attempt_number": fixture.attempt_number,
            "previous_attempt_sha256": fixture.previous_attempt_sha256,
            "retest": (
                fixture.retest.model_dump(mode="json")
                if fixture.retest is not None
                else None
            ),
            "scenario_id": fixture.scenario_id,
            "status": evaluation.status,
            "run_context": fixture.run_context.model_dump(mode="json"),
            "scenario_set_version": self.scenario_set.scenario_set_version,
            "scenario_definition": selected.model_dump(mode="json"),
            "authorization_proof": {
                "status": "passed",
                "manifest_digest": self.authorization_digest,
                "scenario_binding_digest": self.authorization.scenario_binding.scenario_set_digest,
            },
            "run_identity_proof": {
                "status": "passed",
                "expected_equals_actual": True,
            },
            "executable_input_digests": actual_digests,
            "planned_turns": [
                item.model_dump(mode="json") for item in fixture.planned_turns
            ],
            "actual_turns": [
                item.model_dump(mode="json") for item in fixture.actual_turns
            ],
            "adaptive_deviations": [
                item.model_dump(mode="json") for item in fixture.adaptive_deviations
            ],
            "tester": fixture.tester.model_dump(mode="json"),
            "judge": fixture.judge.model_dump(mode="json"),
            "deterministic_checks": deterministic_results,
            "evaluation": {
                "hard_failure": evaluation.hard_failure,
                "failure_reasons": list(evaluation.failure_reasons),
                "judge_reasoning": evaluation.judge_reasoning,
            },
            "usage": usage,
            "side_effects": fixture.side_effects,
            "side_effect_readback_proof": {
                "source_id": self.readback.source_id,
                "observed_at": self.readback.observed_at.isoformat(),
                "content_digest": self.readback_digest,
            },
            "side_effect_closeout": "passed",
        }
        raw_record = self.store.write_raw_json(
            run_id, f"raw/{fixture.scenario_id}/{attempt_id}.json", result
        )
        tracked_record = self.store.append_attempt(run_id, result)
        retention = self.store.build_retention_manifest(
            run_id,
            raw_records=[raw_record],
            redacted_records=[tracked_record],
            owner="acceptance-owner",
            created_at=fixture.run_context.started_at_utc.isoformat(),
            expires_at=fixture.run_context.retention_expires_at.isoformat(),
        )
        self.store.write_redacted_json(
            run_id,
            f"evidence-retention/{attempt_id}.json",
            retention,
        )
        redacted_result = redact_payload(result)
        if not isinstance(redacted_result, dict):
            raise RunnerError("redacted scenario result must remain an object")
        return redacted_result
