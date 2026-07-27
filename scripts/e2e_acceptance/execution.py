"""Protected local execution state for the Noor acceptance trust center."""

from __future__ import annotations

import hashlib
import json
import math
import os
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from scripts.e2e_acceptance.evidence import (
    redact_payload,
    validate_redacted_payload,
)
from scripts.e2e_acceptance.policy import (
    CompiledPolicy,
    OracleEvidence,
    ReadbackObservation,
    TrustedAcceptanceRegistry,
)
from scripts.e2e_acceptance.schemas import EvidenceMode

COMPILER_ID = "treejar.acceptance-policy-compiler.v2"
LOCAL_ADAPTER_IDS = ("fake-local-adapter",)
_PHASES = (
    "prepared",
    "baseline_sealed",
    "executing",
    "final_turn_anchored",
    "final_readback_sealed",
    "evaluated",
    "attempt_committed",
)


class ExecutionValidationError(ValueError):
    """Protected execution state or authorization is invalid."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class CriterionPlan(_StrictModel):
    criterion_id: str
    evidence_mode: EvidenceMode
    aggregation: Literal["all_required"]
    scenario_ids: tuple[str, ...]
    evidence_block_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...] = Field(min_length=1)
    allows_client_exclusion: bool


class CompiledExecutionPlan(_StrictModel):
    schema_version: Literal["noor-e2e-compiled-plan/v2"]
    compiler_id: Literal["treejar.acceptance-policy-compiler.v2"]
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_ids: tuple[str, ...] = Field(min_length=29, max_length=29)
    criteria: dict[str, CriterionPlan]
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def build_compiled_plan(policy: CompiledPolicy) -> CompiledExecutionPlan:
    execution_ids = (*policy.scenarios.keys(), *policy.evidence_blocks.keys())
    if len(execution_ids) != 29 or len(set(execution_ids)) != 29:
        raise ExecutionValidationError("compiled execution scope must be exact 29")
    criteria: dict[str, CriterionPlan] = {}
    for criterion in policy.criteria.values():
        obligation_ids = (
            *criterion.scenario_ids,
            *criterion.evidence_block_ids,
        )
        if not obligation_ids or len(obligation_ids) != len(set(obligation_ids)):
            raise ExecutionValidationError(
                f"criterion obligations are invalid: {criterion.criterion_id}"
            )
        if not set(obligation_ids) <= set(execution_ids):
            raise ExecutionValidationError(
                f"criterion obligation is outside execution plan: "
                f"{criterion.criterion_id}"
            )
        criteria[criterion.criterion_id] = CriterionPlan(
            criterion_id=criterion.criterion_id,
            evidence_mode=criterion.evidence_mode,
            aggregation="all_required",
            scenario_ids=criterion.scenario_ids,
            evidence_block_ids=criterion.evidence_block_ids,
            obligation_ids=obligation_ids,
            allows_client_exclusion=criterion.allows_client_exclusion,
        )
    if len(criteria) != 30:
        raise ExecutionValidationError("compiled criterion scope must be exact 30")
    identity = {
        "schema_version": "noor-e2e-compiled-plan/v2",
        "compiler_id": COMPILER_ID,
        "policy_digest": policy.policy_digest,
        "execution_ids": execution_ids,
        "criteria": {
            key: value.model_dump(mode="json") for key, value in criteria.items()
        },
    }
    return CompiledExecutionPlan(
        **identity,
        plan_digest=_digest(identity),
    )


OutcomeValue = Literal["PASS", "FAIL", "BLOCKED", "EXCLUDED_BY_CLIENT"]


def aggregate_criterion_outcome(
    plan: CriterionPlan,
    outcomes: dict[str, OutcomeValue],
    *,
    valid_exclusions: frozenset[str],
) -> OutcomeValue:
    unknown = set(outcomes) - set(plan.obligation_ids)
    if unknown:
        raise ExecutionValidationError(
            f"criterion outcome contains unknown obligations: {sorted(unknown)}"
        )
    missing = set(plan.obligation_ids) - set(outcomes)
    if missing:
        return "BLOCKED"
    if any(value == "FAIL" for value in outcomes.values()):
        return "FAIL"
    excluded = {
        identity
        for identity, value in outcomes.items()
        if value == "EXCLUDED_BY_CLIENT"
    }
    if excluded:
        if (
            plan.evidence_mode is not EvidenceMode.EXTERNAL_GATE
            or not excluded <= valid_exclusions
        ):
            raise ExecutionValidationError(
                "criterion exclusion is not a valid Task 1 external gate"
            )
        if any(value == "BLOCKED" for value in outcomes.values()):
            return "BLOCKED"
        return "EXCLUDED_BY_CLIENT"
    if any(value == "BLOCKED" for value in outcomes.values()):
        return "BLOCKED"
    return "PASS"


class StoreIdentities(_StrictModel):
    raw_store_id: str = Field(min_length=1)
    tracked_store_id: str = Field(min_length=1)
    anchor_store_id: str = Field(min_length=1)
    raw_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tracked_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    anchor_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _stores_are_distinct(self) -> StoreIdentities:
        if len({self.raw_store_id, self.tracked_store_id, self.anchor_store_id}) != 3:
            raise ValueError("authorization store bindings must be distinct")
        return self


class ProtectedQuotas(_StrictModel):
    max_scenarios: int = Field(ge=0)
    max_messages: int = Field(ge=0)
    max_model_calls: int = Field(ge=0)
    max_cost_usd: float = Field(ge=0)
    subsystem_quotas: dict[str, int] = Field(min_length=1)

    @model_validator(mode="after")
    def _non_negative_subsystems(self) -> ProtectedQuotas:
        if any(value < 0 for value in self.subsystem_quotas.values()):
            raise ValueError("subsystem quota must be non-negative")
        return self


class ExecutionAuthorizationV2(_StrictModel):
    schema_version: Literal["noor-e2e-authorization/v2"]
    authorization_id: str = Field(min_length=1)
    status: Literal["approved"]
    issued_at: datetime
    expires_at: datetime
    task1_authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    task1_input_digests: dict[str, str] = Field(min_length=1)
    preflight_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    readback_collector_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    compiler_id: str = Field(min_length=1)
    compiled_plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_ids: tuple[str, ...] = Field(min_length=1)
    execution_input_digests: dict[str, str] = Field(min_length=29)
    adapter_ids: tuple[str, ...] = Field(min_length=1)
    store_ids: StoreIdentities
    registry_id: str = Field(min_length=1)
    quotas: ProtectedQuotas

    @model_validator(mode="after")
    def _valid_window(self) -> ExecutionAuthorizationV2:
        if (
            self.issued_at.tzinfo is None
            or self.issued_at.utcoffset() is None
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("authorization v2 window is invalid")
        if set(self.execution_input_digests) != set(self.execution_ids) or any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.execution_input_digests.values()
        ):
            raise ValueError("authorization v2 executable input binding drift")
        if any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.task1_input_digests.values()
        ):
            raise ValueError("authorization Task 1 input digest binding drift")
        return self


def authorization_digest(authorization: ExecutionAuthorizationV2) -> str:
    return _digest(authorization.model_dump(mode="json"))


def store_root_digest(root: Path) -> str:
    if not root.is_absolute() or any(
        part in {"", ".", ".."} for part in root.parts[1:]
    ):
        raise ExecutionValidationError("store root must be absolute and normalized")
    return _digest(
        {
            "schema_version": "noor-e2e-store-root/v2",
            "absolute_path": str(root),
        }
    )


def validate_execution_authorization(
    authorization: object,
    *,
    policy: CompiledPolicy,
    plan: CompiledExecutionPlan,
    registry_id: str,
    current_time: datetime | None = None,
) -> ExecutionAuthorizationV2:
    if not isinstance(authorization, ExecutionAuthorizationV2):
        schema = getattr(authorization, "schema_version", "")
        raise ExecutionValidationError(
            f"{schema or 'unknown'} is archival; executor requires authorization/v2"
        )
    if authorization.policy_digest != policy.policy_digest:
        raise ExecutionValidationError("authorization policy drift")
    if authorization.compiler_id != plan.compiler_id:
        raise ExecutionValidationError("authorization compiler drift")
    if authorization.compiled_plan_digest != plan.plan_digest:
        raise ExecutionValidationError("authorization compiled plan drift")
    if authorization.execution_ids != plan.execution_ids:
        raise ExecutionValidationError(
            "authorization execution drift: exact canonical 29 required"
        )
    if authorization.adapter_ids != LOCAL_ADAPTER_IDS:
        raise ExecutionValidationError("authorization adapter is not allowed")
    if authorization.registry_id != registry_id:
        raise ExecutionValidationError("authorization registry drift")
    now = current_time or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ExecutionValidationError("authorization validity time must be aware")
    if not authorization.issued_at <= now < authorization.expires_at:
        raise ExecutionValidationError(
            "authorization validity is expired or not active"
        )
    return authorization


class QuotaUsage(_StrictModel):
    messages: int = 0
    model_calls: int = 0
    cost_usd: float = 0
    subsystem_usage: dict[str, int] = Field(default_factory=dict)


ActionState = Literal["reserved", "succeeded", "failed", "unknown"]


class ActionReservation(_StrictModel):
    action_id: str
    adapter_id: str
    subsystem: str
    messages: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    reservation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _finite_cost(self) -> ActionReservation:
        if not math.isfinite(self.cost_usd):
            raise ValueError("reservation cost must be finite")
        return self


class AttemptRecovery(_StrictModel):
    transaction_id: str
    status: Literal["committed", "aborted"]
    raw_digest: str | None
    tracked_digest: str | None
    commit_digest: str


class PlannedTurnV2(_StrictModel):
    turn_id: str = Field(min_length=1)
    customer_input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_behavior_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    assertion_ids: tuple[str, ...] = Field(min_length=1)


class TurnTimelineV2(_StrictModel):
    sent_at: datetime
    first_visible_at: datetime
    final_visible_at: datetime
    delivered_at: datetime | None

    @model_validator(mode="after")
    def _ordered(self) -> TurnTimelineV2:
        values = [self.sent_at, self.first_visible_at, self.final_visible_at]
        if any(item.tzinfo is None or item.utcoffset() is None for item in values):
            raise ValueError("turn timeline must be timezone-aware")
        if values != sorted(values):
            raise ValueError("turn timeline order is invalid")
        if self.delivered_at is not None and (
            self.delivered_at.tzinfo is None
            or self.delivered_at.utcoffset() is None
            or self.delivered_at < self.final_visible_at
        ):
            raise ValueError("turn delivery timestamp is invalid")
        return self


class ActualTurnV2(_StrictModel):
    actual_turn_id: str = Field(min_length=1)
    planned_turn_id: str = Field(min_length=1)
    customer_input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_behavior_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    assertion_ids: tuple[str, ...] = Field(min_length=1)
    event_refs: tuple[str, ...] = Field(min_length=1)
    tool_refs: tuple[str, ...]
    audit_refs: tuple[str, ...] = Field(min_length=1)
    timeline: TurnTimelineV2
    model_id: str = Field(min_length=1)
    token_count: int = Field(ge=0)
    cost_usd: float = Field(ge=0)


class AdaptiveDeviationV2(_StrictModel):
    planned_turn_id: str = Field(min_length=1)
    actual_turn_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ScenarioAttemptV2(_StrictModel):
    schema_version: Literal["noor-e2e-scenario-attempt/v2"]
    execution_id: str = Field(min_length=1)
    planned_turns: tuple[PlannedTurnV2, ...] = Field(min_length=1)
    actual_turns: tuple[ActualTurnV2, ...] = Field(min_length=1)
    adaptive_deviations: tuple[AdaptiveDeviationV2, ...]
    oracle_evidence: tuple[OracleEvidence, ...] = Field(min_length=1)
    permission_evidence: tuple[str, ...]
    readback_evidence: tuple[str, ...]
    baseline: ReadbackObservation
    final: ReadbackObservation
    action_at: tuple[datetime, ...]
    tester_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    judge_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceBlockAttemptV2(_StrictModel):
    schema_version: Literal["noor-e2e-evidence-block-attempt/v2"]
    execution_id: str = Field(min_length=1)
    evidence_collection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    oracle_evidence: tuple[OracleEvidence, ...] = Field(min_length=1)
    permission_evidence: tuple[str, ...]


class ValidatedAttempt(_StrictModel):
    execution_id: str
    plan_digest: str
    attempt_digest: str
    outcome: Literal["PASS", "FAIL"]
    oracle_decisions: tuple[dict[str, Any], ...]


def scenario_input_digest(
    *,
    execution_id: str,
    planned_turns: tuple[PlannedTurnV2, ...],
    tester_config_digest: str,
    judge_config_digest: str,
) -> str:
    return _digest(
        {
            "execution_id": execution_id,
            "planned_turns": [item.model_dump(mode="json") for item in planned_turns],
            "tester_config_digest": tester_config_digest,
            "judge_config_digest": judge_config_digest,
        }
    )


def scenario_plan_digest(attempt: ScenarioAttemptV2) -> str:
    return scenario_input_digest(
        execution_id=attempt.execution_id,
        planned_turns=attempt.planned_turns,
        tester_config_digest=attempt.tester_config_digest,
        judge_config_digest=attempt.judge_config_digest,
    )


def evidence_block_input_digest(attempt: EvidenceBlockAttemptV2) -> str:
    return _digest(
        {
            "execution_id": attempt.execution_id,
            "evidence_collection_digest": attempt.evidence_collection_digest,
            "evaluator_config_digest": attempt.evaluator_config_digest,
        }
    )


class GenericAcceptanceRunner:
    """Validate locally captured attempts against the universal compiled policy."""

    def __init__(
        self,
        *,
        registry: TrustedAcceptanceRegistry,
        authorization: ExecutionAuthorizationV2,
        journal: ProtectedExecutionJournal,
    ) -> None:
        registry.validate_execution_authorization(authorization)
        if journal.authorization_digest != _digest(
            authorization.model_dump(mode="json")
        ):
            raise ExecutionValidationError("journal authorization binding drift")
        self.registry = registry
        self.authorization = authorization
        self.journal = journal

    def validate_attempt(self, attempt: ScenarioAttemptV2) -> ValidatedAttempt:
        if (
            attempt.baseline.run_id != self.journal.run_id
            or attempt.final.run_id != self.journal.run_id
        ):
            raise ExecutionValidationError("readback run identity drift")
        scenario = self.registry.compiled_policy.scenarios.get(attempt.execution_id)
        if scenario is None:
            raise ExecutionValidationError(
                "generic scenario runner requires a canonical scenario execution"
            )
        plan_digest = scenario_plan_digest(attempt)
        if (
            self.authorization.execution_input_digests.get(attempt.execution_id)
            != plan_digest
        ):
            raise ExecutionValidationError("authorized planned input digest drift")

        planned_by_id = {item.turn_id: item for item in attempt.planned_turns}
        actual_by_plan = {item.planned_turn_id: item for item in attempt.actual_turns}
        if (
            len(planned_by_id) != len(attempt.planned_turns)
            or len(actual_by_plan) != len(attempt.actual_turns)
            or set(planned_by_id) != set(actual_by_plan)
        ):
            raise ExecutionValidationError("actual turns lack exact planned coverage")

        canonical_assertions = {
            item.assertion_id
            for group in (scenario.checkpoints, scenario.prohibited_outcomes)
            for item in group.values()
        }
        for criterion_id in scenario.criterion_ids:
            canonical_assertions.update(
                item.assertion_id
                for item in self.registry.compiled_policy.criteria[
                    criterion_id
                ].oracle_checks.values()
            )
        planned_criteria = {
            criterion_id
            for item in attempt.planned_turns
            for criterion_id in item.criterion_ids
        }
        planned_assertions = {
            assertion_id
            for item in attempt.planned_turns
            for assertion_id in item.assertion_ids
        }
        if planned_criteria != set(scenario.criterion_ids):
            raise ExecutionValidationError("planned criterion coverage drift")
        if planned_assertions != canonical_assertions:
            raise ExecutionValidationError("planned canonical oracle coverage drift")

        expected_deviations: set[tuple[str, str]] = set()
        for planned_id, planned in planned_by_id.items():
            actual = actual_by_plan[planned_id]
            if (
                actual.expected_behavior_digest != planned.expected_behavior_digest
                or actual.criterion_ids != planned.criterion_ids
                or actual.assertion_ids != planned.assertion_ids
            ):
                raise ExecutionValidationError("actual turn plan binding drift")
            if (
                actual.actual_turn_id != planned_id
                or actual.customer_input_digest != planned.customer_input_digest
            ):
                expected_deviations.add((planned_id, actual.actual_turn_id))
        actual_deviations = {
            (item.planned_turn_id, item.actual_turn_id)
            for item in attempt.adaptive_deviations
        }
        if actual_deviations != expected_deviations:
            raise ExecutionValidationError("adaptive deviation coverage drift")

        evidence_by_assertion = {
            item.assertion_id: item for item in attempt.oracle_evidence
        }
        if (
            len(evidence_by_assertion) != len(attempt.oracle_evidence)
            or set(evidence_by_assertion) != canonical_assertions
        ):
            raise ExecutionValidationError("structured oracle evidence coverage drift")
        decisions = tuple(
            self.registry.evaluate_oracle(
                assertion_id,
                evidence_by_assertion[assertion_id],
            )
            for assertion_id in sorted(canonical_assertions)
        )
        if set(attempt.permission_evidence) != set(scenario.required_permissions):
            raise ExecutionValidationError("permission evidence coverage drift")
        if set(attempt.readback_evidence) != set(scenario.required_readbacks):
            raise ExecutionValidationError("readback evidence coverage drift")

        final_visible = [
            item.timeline.final_visible_at for item in attempt.actual_turns
        ]
        delivered = [
            item.timeline.delivered_at
            for item in attempt.actual_turns
            if item.timeline.delivered_at is not None
        ]
        self.registry.validate_readback_window(
            baseline=attempt.baseline,
            final=attempt.final,
            final_visible_at=final_visible,
            delivered_at=delivered,
            action_at=attempt.action_at,
        )
        if self.journal.phase != "executing":
            raise ExecutionValidationError(
                "attempt validation requires executing phase"
            )
        outcome: Literal["PASS", "FAIL"] = (
            "PASS" if all(item.passed for item in decisions) else "FAIL"
        )
        return ValidatedAttempt(
            execution_id=attempt.execution_id,
            plan_digest=plan_digest,
            attempt_digest=_digest(attempt.model_dump(mode="json")),
            outcome=outcome,
            oracle_decisions=tuple(item.model_dump(mode="json") for item in decisions),
        )

    def validate_evidence_block(
        self,
        attempt: EvidenceBlockAttemptV2,
    ) -> ValidatedAttempt:
        block = self.registry.compiled_policy.evidence_blocks.get(attempt.execution_id)
        if block is None:
            raise ExecutionValidationError(
                "generic evidence runner requires a canonical evidence block"
            )
        plan_digest = evidence_block_input_digest(attempt)
        if (
            self.authorization.execution_input_digests.get(attempt.execution_id)
            != plan_digest
        ):
            raise ExecutionValidationError(
                "authorized evidence-block input digest drift"
            )
        canonical_assertions = {
            item.assertion_id for item in block.oracle_checks.values()
        }
        for criterion_id in block.criterion_ids:
            canonical_assertions.update(
                item.assertion_id
                for item in self.registry.compiled_policy.criteria[
                    criterion_id
                ].oracle_checks.values()
            )
        evidence_by_assertion = {
            item.assertion_id: item for item in attempt.oracle_evidence
        }
        if (
            len(evidence_by_assertion) != len(attempt.oracle_evidence)
            or set(evidence_by_assertion) != canonical_assertions
        ):
            raise ExecutionValidationError(
                "evidence-block structured oracle coverage drift"
            )
        if set(attempt.permission_evidence) != set(block.required_permissions):
            raise ExecutionValidationError("evidence-block permission coverage drift")
        if self.journal.phase != "executing":
            raise ExecutionValidationError(
                "evidence-block validation requires executing phase"
            )
        decisions = tuple(
            self.registry.evaluate_oracle(
                assertion_id,
                evidence_by_assertion[assertion_id],
            )
            for assertion_id in sorted(canonical_assertions)
        )
        return ValidatedAttempt(
            execution_id=attempt.execution_id,
            plan_digest=plan_digest,
            attempt_digest=_digest(attempt.model_dump(mode="json")),
            outcome=("PASS" if all(item.passed for item in decisions) else "FAIL"),
            oracle_decisions=tuple(item.model_dump(mode="json") for item in decisions),
        )


def _directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None or os.open not in os.supports_dir_fd:
        raise ExecutionValidationError("descriptor-relative no-follow I/O unavailable")
    return cast("int", os.O_RDONLY | nofollow | directory)


def _open_absolute_chain(path: Path, *, create: bool) -> int:
    if not path.is_absolute() or any(
        part in {"", ".", ".."} for part in path.parts[1:]
    ):
        raise ExecutionValidationError("protected path must be absolute and normalized")
    flags = _directory_flags()
    current_fd = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            if create:
                with suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=current_fd)
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
    except OSError as exc:
        os.close(current_fd)
        raise ExecutionValidationError(
            f"protected path violates no-follow policy: {exc}"
        ) from exc
    return current_fd


def _validated_relative(value: str) -> tuple[str, ...]:
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ExecutionValidationError("protected relative path is unsafe")
    return path.parts


def _open_relative_parent(
    root: Path,
    relative: str,
    *,
    create: bool,
) -> tuple[int, str]:
    parts = _validated_relative(relative)
    current_fd = _open_absolute_chain(root, create=create)
    flags = _directory_flags()
    try:
        for part in parts[:-1]:
            if create:
                with suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=current_fd)
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
    except OSError as exc:
        os.close(current_fd)
        raise ExecutionValidationError(
            f"protected parent violates no-follow policy: {exc}"
        ) from exc
    return current_fd, parts[-1]


def _write_exclusive(root: Path, relative: str, value: object) -> str:
    payload = _canonical_bytes(value)
    parent_fd, name = _open_relative_parent(root, relative, create=True)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(name, flags, 0o600, dir_fd=parent_fd)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise ExecutionValidationError(
            f"protected exclusive write failed: {relative}: {exc}"
        ) from exc
    finally:
        os.close(parent_fd)
    return hashlib.sha256(payload).hexdigest()


def _read_protected(root: Path, relative: str) -> bytes:
    parent_fd, name = _open_relative_parent(root, relative, create=False)
    try:
        fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
        try:
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(fd)
    except OSError as exc:
        raise ExecutionValidationError(
            f"protected read failed: {relative}: {exc}"
        ) from exc
    finally:
        os.close(parent_fd)
    return b"".join(chunks)


class AttemptTransaction:
    def __init__(
        self,
        *,
        journal: ProtectedExecutionJournal,
        transaction_id: str,
    ) -> None:
        self._journal = journal
        self.transaction_id = transaction_id

    def write_raw(self, payload: object) -> str:
        return _write_exclusive(
            self._journal.run_root,
            f"attempts/{self.transaction_id}/raw.json",
            payload,
        )

    def write_tracked(self) -> str:
        """Derive the tracked payload only from the already sealed raw bytes."""

        raw = _read_protected(
            self._journal.run_root,
            f"attempts/{self.transaction_id}/raw.json",
        )
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExecutionValidationError(
                "sealed raw attempt JSON is invalid"
            ) from exc
        redacted = redact_payload(payload)
        validate_redacted_payload(redacted)
        return _write_exclusive(
            self._journal.run_root,
            f"attempts/{self.transaction_id}/tracked.json",
            redacted,
        )

    def commit(self) -> AttemptRecovery:
        return self._journal._finish_attempt(self.transaction_id, abort=False)


class FakeLocalAdapter:
    """No-network adapter used by Task 2 contract tests only."""

    def __init__(
        self,
        *,
        adapter_id: str,
        journal: ProtectedExecutionJournal | None,
    ) -> None:
        if adapter_id not in LOCAL_ADAPTER_IDS:
            raise ExecutionValidationError("only fake local adapter is available")
        self.adapter_id = adapter_id
        self._journal = journal

    def execute(self, reservation: ActionReservation | None) -> dict[str, str]:
        if (
            reservation is None
            or self._journal is None
            or reservation.adapter_id != self.adapter_id
        ):
            raise ExecutionValidationError(
                "adapter call requires a protected action reservation"
            )
        self._journal.consume_permit(
            reservation,
            adapter_id=self.adapter_id,
        )
        return {
            "status": "synthetic",
            "reservation_digest": reservation.reservation_digest,
        }


class ProtectedExecutionJournal:
    """Append-only phase/action journal under a protected external root."""

    def __init__(
        self,
        *,
        protected_root: Path,
        run_id: str,
        authorization: ExecutionAuthorizationV2,
    ) -> None:
        if not run_id or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-._"
            for character in run_id.lower()
        ):
            raise ExecutionValidationError("run identity is unsafe")
        self.protected_root = protected_root
        self.run_id = run_id
        self.run_root = protected_root / run_id
        self.authorization = authorization
        self.authorization_digest = _digest(authorization.model_dump(mode="json"))
        self.phase = "prepared"
        self.cursor = 0
        self.previous_event_digest: str | None = None
        self.quota_usage = QuotaUsage()
        self._actions: dict[str, ActionState] = {}
        self._reservations: dict[str, ActionReservation] = {}
        self._attempted_executions: list[str] = []
        self._authorization_scenarios = 0
        self._authorization_ledger_cursor = 0
        self._authorization_ledger_head: str | None = None
        self._final_turn_occurred_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        protected_root: Path,
        run_id: str,
        authorization: ExecutionAuthorizationV2,
    ) -> ProtectedExecutionJournal:
        journal = cls(
            protected_root=protected_root,
            run_id=run_id,
            authorization=authorization,
        )
        journal._reload_authorization_ledger()
        fd = _open_absolute_chain(journal.run_root, create=True)
        os.fchmod(fd, 0o700)
        os.close(fd)
        journal._append_event(
            phase="prepared",
            kind="prepared",
            data={
                "authorization_digest": journal.authorization_digest,
                "anchor_store_id": authorization.store_ids.anchor_store_id,
            },
        )
        return journal

    @classmethod
    def open(
        cls,
        *,
        protected_root: Path,
        run_id: str,
        authorization: ExecutionAuthorizationV2,
    ) -> ProtectedExecutionJournal:
        journal = cls(
            protected_root=protected_root,
            run_id=run_id,
            authorization=authorization,
        )
        journal._reload_authorization_ledger()
        journal_fd = _open_absolute_chain(
            journal.run_root / "journal",
            create=False,
        )
        try:
            names = sorted(os.listdir(journal_fd))
        finally:
            os.close(journal_fd)
        previous_digest: str | None = None
        for expected_cursor, name in enumerate(names, start=1):
            if name != f"{expected_cursor:06d}.json":
                raise ExecutionValidationError("journal cursor sequence drift")
            payload = _read_protected(journal.run_root, f"journal/{name}")
            try:
                event = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ExecutionValidationError("journal event JSON invalid") from exc
            if (
                event.get("cursor") != expected_cursor
                or event.get("previous_event_digest") != previous_digest
            ):
                raise ExecutionValidationError("journal digest/cursor causality drift")
            if expected_cursor == 1 and (
                event.get("kind") != "prepared"
                or event.get("data", {}).get("authorization_digest")
                != journal.authorization_digest
            ):
                raise ExecutionValidationError("journal authorization binding drift")
            journal._apply_loaded_event(event)
            previous_digest = hashlib.sha256(payload).hexdigest()
        if not names:
            raise ExecutionValidationError("protected journal is empty")
        journal.previous_event_digest = previous_digest
        return journal

    def _apply_loaded_event(self, event: dict[str, Any]) -> None:
        self.cursor = int(event["cursor"])
        self.phase = str(event["phase"])
        kind = str(event["kind"])
        data = event.get("data", {})
        if kind == "action_reserved":
            reservation = ActionReservation.model_validate(data["reservation"])
            self._reservations[reservation.action_id] = reservation
            self._actions[reservation.action_id] = "reserved"
        elif kind == "action_completed":
            self._actions[str(data["action_id"])] = str(data["state"])  # type: ignore[assignment]
        elif kind == "permit_consumed":
            self._actions[str(data["action_id"])] = "unknown"
        elif kind == "attempt_intent":
            self._attempted_executions.append(str(data["execution_id"]))
        elif kind == "final_turn_anchored":
            occurred_at = datetime.fromisoformat(str(data["occurred_at"]))
            if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
                raise ExecutionValidationError("final-turn anchor timestamp is invalid")
            self._final_turn_occurred_at = occurred_at

    def _append_event(
        self,
        *,
        phase: str,
        kind: str,
        data: dict[str, Any],
    ) -> str:
        cursor = self.cursor + 1
        event = {
            "schema_version": "noor-e2e-protected-event/v2",
            "cursor": cursor,
            "phase": phase,
            "kind": kind,
            "previous_event_digest": self.previous_event_digest,
            "data": data,
        }
        digest = _write_exclusive(
            self.run_root,
            f"journal/{cursor:06d}.json",
            event,
        )
        self.cursor = cursor
        self.previous_event_digest = digest
        self.phase = phase
        return digest

    def _transition(
        self,
        *,
        expected: str,
        target: str,
        kind: str,
        data: dict[str, Any],
    ) -> str:
        if self.phase != expected:
            raise ExecutionValidationError(
                f"phase transition requires {expected}, got {self.phase}"
            )
        expected_index = _PHASES.index(expected)
        if _PHASES[expected_index + 1] != target:
            raise ExecutionValidationError("phase transition is not canonical")
        return self._append_event(phase=target, kind=kind, data=data)

    def seal_baseline(self, observation: ReadbackObservation) -> None:
        if observation.phase != "baseline":
            raise ExecutionValidationError("baseline observation phase drift")
        if (
            observation.run_id != self.run_id
            or observation.preflight_digest != self.authorization.preflight_digest
            or observation.collector_artifact_digest
            != self.authorization.readback_collector_digest
        ):
            raise ExecutionValidationError("baseline preflight/run binding drift")
        self._transition(
            expected="prepared",
            target="baseline_sealed",
            kind="baseline_sealed",
            data={
                "source_id": observation.source_id,
                "collector_id": observation.collector_id,
                "observed_at": observation.observed_at.isoformat(),
                "content_digest": observation.content_digest,
            },
        )

    def begin_execution(self) -> None:
        self._transition(
            expected="baseline_sealed",
            target="executing",
            kind="execution_started",
            data={},
        )

    def _consume(self, reservation: ActionReservation) -> None:
        subsystems = dict(self.quota_usage.subsystem_usage)
        subsystems[reservation.subsystem] = subsystems.get(reservation.subsystem, 0) + 1
        self.quota_usage = QuotaUsage(
            messages=self.quota_usage.messages + reservation.messages,
            model_calls=self.quota_usage.model_calls + reservation.model_calls,
            cost_usd=self.quota_usage.cost_usd + reservation.cost_usd,
            subsystem_usage=subsystems,
        )

    @property
    def _authorization_ledger_root(self) -> Path:
        return (
            self.protected_root / ".authorization-ledgers" / self.authorization_digest
        )

    def _reload_authorization_ledger(self) -> None:
        self.quota_usage = QuotaUsage()
        self._authorization_scenarios = 0
        self._authorization_ledger_cursor = 0
        self._authorization_ledger_head = None
        try:
            ledger_fd = _open_absolute_chain(
                self._authorization_ledger_root,
                create=False,
            )
        except ExecutionValidationError:
            return
        try:
            names = sorted(os.listdir(ledger_fd))
        finally:
            os.close(ledger_fd)
        previous: str | None = None
        for expected, name in enumerate(names, start=1):
            if name != f"{expected:06d}.json":
                raise ExecutionValidationError(
                    "authorization quota ledger cursor sequence drift"
                )
            payload = _read_protected(
                self._authorization_ledger_root,
                name,
            )
            try:
                event = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ExecutionValidationError(
                    "authorization quota ledger JSON invalid"
                ) from exc
            if (
                event.get("cursor") != expected
                or event.get("previous_event_digest") != previous
                or event.get("authorization_digest") != self.authorization_digest
            ):
                raise ExecutionValidationError(
                    "authorization quota ledger causality drift"
                )
            if event.get("kind") == "action_reserved":
                self._consume(ActionReservation.model_validate(event["reservation"]))
            elif event.get("kind") == "scenario_reserved":
                self._authorization_scenarios += 1
            else:
                raise ExecutionValidationError(
                    "authorization quota ledger event kind drift"
                )
            previous = hashlib.sha256(payload).hexdigest()
        self._authorization_ledger_cursor = len(names)
        self._authorization_ledger_head = previous

    def _append_authorization_ledger(
        self,
        *,
        kind: Literal["action_reserved", "scenario_reserved"],
        data: dict[str, Any],
    ) -> None:
        event = {
            "schema_version": "noor-e2e-authorization-quota-event/v2",
            "cursor": self._authorization_ledger_cursor + 1,
            "previous_event_digest": self._authorization_ledger_head,
            "authorization_digest": self.authorization_digest,
            "kind": kind,
            **data,
        }
        digest = _write_exclusive(
            self._authorization_ledger_root,
            f"{self._authorization_ledger_cursor + 1:06d}.json",
            event,
        )
        self._authorization_ledger_cursor += 1
        self._authorization_ledger_head = digest

    def reserve_action(
        self,
        *,
        action_id: str,
        adapter_id: str,
        subsystem: str,
        messages: int,
        model_calls: int,
        cost_usd: float,
    ) -> ActionReservation:
        if self.phase != "executing":
            raise ExecutionValidationError(
                "action reservation requires executing phase"
            )
        if adapter_id not in self.authorization.adapter_ids:
            raise ExecutionValidationError("action adapter is not authorized")
        if action_id in self._actions:
            raise ExecutionValidationError("action identity is already reserved")
        if (
            messages < 0
            or model_calls < 0
            or cost_usd < 0
            or not math.isfinite(cost_usd)
        ):
            raise ExecutionValidationError(
                "reservation quota values must be non-negative and finite"
            )
        self._reload_authorization_ledger()
        identity = {
            "action_id": action_id,
            "adapter_id": adapter_id,
            "subsystem": subsystem,
            "messages": messages,
            "model_calls": model_calls,
            "cost_usd": cost_usd,
            "authorization_digest": self.authorization_digest,
            "next_cursor": self.cursor + 1,
        }
        reservation = ActionReservation(
            action_id=action_id,
            adapter_id=adapter_id,
            subsystem=subsystem,
            messages=messages,
            model_calls=model_calls,
            cost_usd=cost_usd,
            reservation_digest=_digest(identity),
        )
        projected_messages = self.quota_usage.messages + messages
        projected_calls = self.quota_usage.model_calls + model_calls
        projected_cost = self.quota_usage.cost_usd + cost_usd
        projected_subsystem = self.quota_usage.subsystem_usage.get(subsystem, 0) + 1
        quotas = self.authorization.quotas
        if (
            projected_messages > quotas.max_messages
            or projected_calls > quotas.max_model_calls
            or projected_cost > quotas.max_cost_usd
            or projected_subsystem > quotas.subsystem_quotas.get(subsystem, 0)
        ):
            raise ExecutionValidationError("protected action reservation exceeds quota")
        self._append_authorization_ledger(
            kind="action_reserved",
            data={"reservation": reservation.model_dump(mode="json")},
        )
        self._append_event(
            phase="executing",
            kind="action_reserved",
            data={"reservation": reservation.model_dump(mode="json")},
        )
        self._reservations[action_id] = reservation
        self._actions[action_id] = "reserved"
        self._consume(reservation)
        return reservation

    def consume_permit(
        self,
        reservation: ActionReservation,
        *,
        adapter_id: str,
    ) -> None:
        """Atomically validate and consume the one-use protected permit."""

        if (
            self.phase != "executing"
            or adapter_id != reservation.adapter_id
            or self._actions.get(reservation.action_id) != "reserved"
            or self._reservations.get(reservation.action_id) != reservation
        ):
            raise ExecutionValidationError(
                "forged, reused, or missing protected reservation"
            )
        self._append_event(
            phase="executing",
            kind="permit_consumed",
            data={
                "action_id": reservation.action_id,
                "reservation_digest": reservation.reservation_digest,
                "adapter_id": adapter_id,
            },
        )
        self._actions[reservation.action_id] = "unknown"

    def complete_action(
        self,
        reservation: ActionReservation,
        *,
        state: Literal["succeeded", "failed", "unknown"],
        outcome_digest: str,
    ) -> None:
        if self._actions.get(reservation.action_id) != "unknown":
            raise ExecutionValidationError("action completion lacks active reservation")
        if self._reservations.get(reservation.action_id) != reservation:
            raise ExecutionValidationError("action reservation identity drift")
        if len(outcome_digest) != 64:
            raise ExecutionValidationError("action outcome digest must be SHA-256")
        self._append_event(
            phase="executing",
            kind="action_completed",
            data={
                "action_id": reservation.action_id,
                "reservation_digest": reservation.reservation_digest,
                "state": state,
                "outcome_digest": outcome_digest,
            },
        )
        self._actions[reservation.action_id] = state

    def anchor_final_turn(self, *, event_digest: str, occurred_at: datetime) -> None:
        if any(state in {"reserved", "unknown"} for state in self._actions.values()):
            raise ExecutionValidationError(
                "unknown or uncompleted action blocks final-turn closeout"
            )
        if (
            len(event_digest) != 64
            or any(character not in "0123456789abcdef" for character in event_digest)
            or occurred_at.tzinfo is None
            or occurred_at.utcoffset() is None
        ):
            raise ExecutionValidationError("final-turn anchor identity is invalid")
        self._transition(
            expected="executing",
            target="final_turn_anchored",
            kind="final_turn_anchored",
            data={
                "event_digest": event_digest,
                "occurred_at": occurred_at.isoformat(),
            },
        )
        self._final_turn_occurred_at = occurred_at

    def seal_final_readback(self, observation: ReadbackObservation) -> None:
        if (
            self._final_turn_occurred_at is None
            or observation.observed_at < self._final_turn_occurred_at
        ):
            raise ExecutionValidationError(
                "final readback timestamp predates final-turn anchor"
            )
        if (
            observation.phase != "final"
            or observation.run_id != self.run_id
            or observation.preflight_digest != self.authorization.preflight_digest
            or observation.collector_artifact_digest
            != self.authorization.readback_collector_digest
            or observation.causal_event_digest != self.previous_event_digest
        ):
            raise ExecutionValidationError(
                "final readback protected causality/preflight binding drift"
            )
        self._transition(
            expected="final_turn_anchored",
            target="final_readback_sealed",
            kind="final_readback_sealed",
            data={
                "source_id": observation.source_id,
                "collector_id": observation.collector_id,
                "observed_at": observation.observed_at.isoformat(),
                "content_digest": observation.content_digest,
                "causal_event_digest": observation.causal_event_digest,
            },
        )

    def mark_evaluated(self, *, evaluation_digest: str) -> None:
        if len(evaluation_digest) != 64 or any(
            character not in "0123456789abcdef" for character in evaluation_digest
        ):
            raise ExecutionValidationError("evaluation digest must be SHA-256")
        self._transition(
            expected="final_readback_sealed",
            target="evaluated",
            kind="evaluated",
            data={"evaluation_digest": evaluation_digest},
        )

    def commit_phase(self, *, attempt_chain_digest: str) -> None:
        if len(attempt_chain_digest) != 64 or any(
            character not in "0123456789abcdef" for character in attempt_chain_digest
        ):
            raise ExecutionValidationError("attempt chain digest must be SHA-256")
        self._transition(
            expected="evaluated",
            target="attempt_committed",
            kind="attempt_committed",
            data={"attempt_chain_digest": attempt_chain_digest},
        )

    def begin_attempt(
        self,
        *,
        execution_id: str,
        attempt_number: int,
        intent_digest: str,
    ) -> AttemptTransaction:
        if self.phase != "executing":
            raise ExecutionValidationError(
                "attempt intent requires contiguous executing phase"
            )
        if execution_id not in self.authorization.execution_ids:
            raise ExecutionValidationError(
                "attempt requires a canonical execution identity"
            )
        if attempt_number < 1:
            raise ExecutionValidationError("attempt number must be positive")
        if len(intent_digest) != 64 or any(
            character not in "0123456789abcdef" for character in intent_digest
        ):
            raise ExecutionValidationError("attempt intent digest must be SHA-256")
        self._reload_authorization_ledger()
        if self._authorization_scenarios >= self.authorization.quotas.max_scenarios:
            raise ExecutionValidationError(
                "authorization-scoped scenario quota exceeded"
            )
        transaction_id = f"{execution_id.lower()}-attempt-{attempt_number:03d}"
        self._append_authorization_ledger(
            kind="scenario_reserved",
            data={
                "run_id": self.run_id,
                "transaction_id": transaction_id,
                "execution_id": execution_id,
            },
        )
        self._authorization_scenarios += 1
        _write_exclusive(
            self.run_root,
            f"attempts/{transaction_id}/intent.json",
            {
                "schema_version": "noor-e2e-attempt-intent/v2",
                "transaction_id": transaction_id,
                "execution_id": execution_id,
                "attempt_number": attempt_number,
                "intent_digest": intent_digest,
                "authorization_digest": self.authorization_digest,
            },
        )
        self._append_event(
            phase="executing",
            kind="attempt_intent",
            data={
                "transaction_id": transaction_id,
                "execution_id": execution_id,
                "attempt_number": attempt_number,
                "intent_digest": intent_digest,
            },
        )
        self._attempted_executions.append(execution_id)
        return AttemptTransaction(journal=self, transaction_id=transaction_id)

    def _optional_digest(self, relative: str) -> str | None:
        try:
            return hashlib.sha256(_read_protected(self.run_root, relative)).hexdigest()
        except ExecutionValidationError:
            return None

    def _finish_attempt(
        self,
        transaction_id: str,
        *,
        abort: bool,
    ) -> AttemptRecovery:
        raw_digest = self._optional_digest(f"attempts/{transaction_id}/raw.json")
        tracked_digest = self._optional_digest(
            f"attempts/{transaction_id}/tracked.json"
        )
        execution_id: str | None = None
        attempt_digest: str | None = None
        semantic_digest: str | None = None
        status: Literal["committed", "aborted"]
        if abort or raw_digest is None or tracked_digest is None:
            status = "aborted"
        else:
            intent_payload = _read_protected(
                self.run_root,
                f"attempts/{transaction_id}/intent.json",
            )
            raw_payload = _read_protected(
                self.run_root,
                f"attempts/{transaction_id}/raw.json",
            )
            tracked_payload = _read_protected(
                self.run_root,
                f"attempts/{transaction_id}/tracked.json",
            )
            try:
                intent = json.loads(intent_payload)
                raw = json.loads(raw_payload)
                tracked = json.loads(tracked_payload)
            except json.JSONDecodeError as exc:
                raise ExecutionValidationError(
                    "attempt raw/tracked semantic envelope is invalid"
                ) from exc
            expected_execution = intent.get("execution_id")
            semantic_fields = (
                "schema_version",
                "execution_id",
                "outcome",
                "semantic_digest",
            )
            if (
                expected_execution not in self.authorization.execution_ids
                or not isinstance(raw, dict)
                or not isinstance(tracked, dict)
                or any(
                    field not in raw or field not in tracked
                    for field in semantic_fields
                )
                or any(raw[field] != tracked[field] for field in semantic_fields)
                or raw["execution_id"] != expected_execution
                or raw["schema_version"] != "noor-e2e-attempt-result/v2"
                or raw["outcome"]
                not in {"PASS", "FAIL", "BLOCKED", "EXCLUDED_BY_CLIENT"}
                or not isinstance(raw["semantic_digest"], str)
                or len(raw["semantic_digest"]) != 64
            ):
                raise ExecutionValidationError(
                    "attempt raw/tracked semantic binding drift"
                )
            execution_id = str(expected_execution)
            attempt_digest = str(intent["intent_digest"])
            semantic_digest = str(raw["semantic_digest"])
            status = "committed"
        record = {
            "schema_version": "noor-e2e-attempt-commit/v2",
            "transaction_id": transaction_id,
            "run_id": self.run_id,
            "execution_id": execution_id,
            "attempt_digest": attempt_digest,
            "status": status,
            "authorization_digest": self.authorization_digest,
            "semantic_digest": semantic_digest,
            "raw_digest": raw_digest,
            "tracked_digest": tracked_digest,
        }
        commit_digest = _write_exclusive(
            self.run_root,
            f"attempts/{transaction_id}/commit.json",
            record,
        )
        return AttemptRecovery(
            transaction_id=transaction_id,
            status=status,
            raw_digest=raw_digest,
            tracked_digest=tracked_digest,
            commit_digest=commit_digest,
        )

    def recover_attempt(self, transaction_id: str) -> AttemptRecovery:
        return self._finish_attempt(transaction_id, abort=True)
