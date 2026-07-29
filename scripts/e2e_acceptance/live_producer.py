"""Conservative production gate producer for unavailable live proof.

This module never executes a customer or provider action. It can only derive a
``BLOCKED`` result for the next canonical execution from the immutable scenario
kind and the trusted registry. The caller cannot select an execution, outcome,
producer, criterion set, or reason.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.production import (
    DecisiveProducerHandle,
    ProductionAdapterError,
    _producer_handle_record,
    _ProducerHandleRecord,
    _write_or_validate_bytes,
    _write_or_validate_exact,
    _write_producer_observation,
)

BlockReason = Literal[
    "disjoint_identity_unavailable",
    "provider_origin_unavailable",
    "independent_evidence_unavailable",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _ServerToolTraceFact(_StrictModel):
    call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    arguments_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: Literal["returned"]


class _TranscriptFact(_StrictModel):
    turn_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    sent_at: datetime
    received_at: datetime
    first_visible_at: datetime
    final_visible_at: datetime
    delivered_at: datetime | None
    duration_ms: int = Field(ge=0)
    conversation_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    provider_message_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tool_traces: tuple[_ServerToolTraceFact, ...]
    tools: tuple[str, ...]
    tool_outcomes: tuple[str, ...]
    audit_ids: tuple[str, ...]
    media_refs: tuple[str, ...]
    token_count: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    deviation: str | None
    evaluator_reasoning: str = Field(min_length=1)

    @model_validator(mode="after")
    def _timeline_and_duration(self) -> _TranscriptFact:
        required = (
            self.sent_at,
            self.received_at,
            self.first_visible_at,
            self.final_visible_at,
        )
        if any(value.tzinfo is None or value.utcoffset() is None for value in required):
            raise ValueError("live transcript timestamps must be timezone-aware")
        if not (
            self.sent_at
            <= self.received_at
            <= self.first_visible_at
            <= self.final_visible_at
        ):
            raise ValueError("live transcript timeline is invalid")
        if self.delivered_at is not None and (
            self.delivered_at.tzinfo is None
            or self.delivered_at.utcoffset() is None
            or self.delivered_at < self.final_visible_at
        ):
            raise ValueError("live transcript delivery time is invalid")
        derived = int((self.final_visible_at - self.sent_at).total_seconds() * 1000)
        if self.duration_ms != derived:
            raise ValueError("live transcript duration differs from timestamps")
        if len(self.tools) != len(self.tool_outcomes):
            raise ValueError("live transcript tool outcomes are incomplete")
        if self.tools != tuple(item.tool_name for item in self.tool_traces):
            raise ValueError("live transcript tool trace names drift")
        return self


class _ServerSideEffectFact(_StrictModel):
    artifact_id: str = Field(min_length=1)
    subsystem: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    baseline_readback: dict[str, Any]
    expected_effect: dict[str, Any]
    final_readback: dict[str, Any]
    disposition: Literal["voided", "closed", "resolved", "retained_as_test_evidence"]
    follow_up_suppressed: bool
    checksum_refs: tuple[str, ...] = Field(min_length=1)


class _LiveExecutionObservation(_StrictModel):
    schema_version: Literal["noor-e2e-server-execution-observation/v1"]
    execution_id: str = Field(min_length=1)
    observed_at: datetime
    transcript_facts: tuple[_TranscriptFact, ...]
    side_effect_facts: tuple[_ServerSideEffectFact, ...]
    baseline_inventory: dict[str, dict[str, Any]]
    final_inventory: dict[str, dict[str, Any]]

    @model_validator(mode="after")
    def _aware_observation(self) -> _LiveExecutionObservation:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("live execution observation time must be aware")
        changed = {
            identity
            for identity in set(self.baseline_inventory) | set(self.final_inventory)
            if self.baseline_inventory.get(identity)
            != self.final_inventory.get(identity)
        }
        listed = [item.artifact_id for item in self.side_effect_facts]
        if changed != set(listed) or len(listed) != len(set(listed)):
            raise ValueError("live side effects do not cover inventory delta")
        return self


class _LiveActionReconciliation(_StrictModel):
    schema_version: Literal["noor-e2e-server-action-reconciliation/v1"]
    action_id: str = Field(min_length=1)
    observed_at: datetime
    resolved_state: Literal["succeeded", "failed"]
    inventory: dict[str, Any]
    actual_cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def _aware_and_finite(self) -> _LiveActionReconciliation:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("live reconciliation time must be aware")
        return self


class _ReadOnlyTransport(Protocol):
    def read(self, source: str) -> bytes: ...


@dataclass(frozen=True)
class IndependentExecutionProducer:
    """Materialize the next attempt only from an allowlisted read-only source."""

    collector_id: str
    transport: _ReadOnlyTransport

    def collect_next(
        self,
        *,
        producer_handle: DecisiveProducerHandle,
        observed_at: datetime | None = None,
    ) -> str:
        record = _producer_handle_record(producer_handle)
        if self.collector_id not in record.journal.authorization.collector_ids:
            raise ProductionAdapterError("live execution collector is not authorized")
        source = f"execution:{record.execution_id}"
        raw = self.transport.read(source)
        try:
            observation = _LiveExecutionObservation.model_validate(json.loads(raw))
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProductionAdapterError(
                "live execution observation is invalid"
            ) from exc
        now = observed_at or datetime.now(UTC)
        if (
            observation.execution_id != record.execution_id
            or now.tzinfo is None
            or now.utcoffset() is None
            or observation.observed_at > now
        ):
            raise ProductionAdapterError("live execution observation time is invalid")
        raw_ref = f"collector-raw/executions/{record.execution_id}.json"
        raw_sha256 = _write_or_validate_bytes(
            record.journal.run_root,
            raw_ref,
            raw,
        )
        _write_or_validate_exact(
            record.journal.run_root,
            f"producer-receipts/live-executions/{record.execution_id}.json",
            {
                "schema_version": "noor-e2e-live-execution-collector-receipt/v2",
                "registry_id": record.registry.registry_id,
                "run_id": record.journal.run_id,
                "authorization_digest": record.journal.authorization_digest,
                "execution_id": record.execution_id,
                "collector_id": self.collector_id,
                "source": source,
                "raw_ref": raw_ref,
                "raw_sha256": raw_sha256,
                "observed_at": observation.observed_at.isoformat(),
            },
        )
        return raw_ref

    def materialize_next(
        self,
        *,
        producer_handle: DecisiveProducerHandle,
        observed_at: datetime | None = None,
    ) -> str:
        self.collect_next(
            producer_handle=producer_handle,
            observed_at=observed_at,
        )
        raise ProductionAdapterError(
            "trusted semantic compiler is unavailable; caller evaluation is forbidden"
        )


@dataclass(frozen=True)
class IndependentActionReconciler:
    """Derive an uncertain action receipt from one allowlisted SSH readback."""

    collector_id: str
    transport: _ReadOnlyTransport

    def materialize(
        self,
        journal: execution.ProtectedExecutionJournal,
        *,
        action_id: str,
        current_time: datetime | None = None,
    ) -> str:
        if self.collector_id not in journal.authorization.collector_ids:
            raise ProductionAdapterError("action reconciler is not authorized")
        reservation = journal._reservations.get(action_id)
        if reservation is None or journal._actions.get(action_id) != "unknown":
            raise ProductionAdapterError(
                "action reconciliation requires an unknown reservation"
            )
        try:
            lower_bound, causal_event_digest = journal.action_reconciliation_boundary(
                action_id
            )
        except execution.ExecutionValidationError as exc:
            raise ProductionAdapterError(
                "live action reconciliation lower bound is unavailable"
            ) from exc
        source = f"reconciliation:{action_id}"
        raw = self.transport.read(source)
        try:
            observation = _LiveActionReconciliation.model_validate(json.loads(raw))
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProductionAdapterError(
                "live action reconciliation is invalid"
            ) from exc
        now = current_time or datetime.now(UTC)
        if (
            observation.action_id != action_id
            or now.tzinfo is None
            or now.utcoffset() is None
            or observation.observed_at > now
            or observation.observed_at < lower_bound
            or observation.actual_cost_usd > reservation.cost_usd
        ):
            raise ProductionAdapterError("live action reconciliation binding drift")
        raw_ref = f"collector-raw/reconciliations/{action_id}.json"
        _write_or_validate_bytes(journal.run_root, raw_ref, raw)
        receipt = execution.UnknownActionReconciliationReceipt(
            schema_version="noor-e2e-unknown-action-reconciliation/v2",
            registry_id=journal.authorization.registry_id,
            run_id=journal.run_id,
            authorization_digest=journal.authorization_digest,
            action_id=action_id,
            reservation_digest=reservation.reservation_digest,
            collector_id=self.collector_id,
            producer="independent-readback-collector",
            causal_event_digest=causal_event_digest,
            observed_at=observation.observed_at,
            expires_at=min(
                observation.observed_at + timedelta(minutes=5),
                journal.authorization.expires_at,
            ),
            resolved_state=observation.resolved_state,
            inventory_digest=execution._digest(observation.inventory),
            actual_cost_usd=observation.actual_cost_usd,
        )
        return _write_or_validate_exact(
            journal.run_root,
            f"independent-reconciliation/{action_id}.json",
            receipt.model_dump(mode="json"),
        )


def _reason_for_next_execution(record: _ProducerHandleRecord) -> BlockReason:
    execution_id = record.execution_id
    scenario = record.registry.compiled_policy.scenarios.get(execution_id)
    if scenario is None:
        return "independent_evidence_unavailable"
    if "provider_originated_canary" in scenario.required_permissions:
        return "provider_origin_unavailable"
    return "disjoint_identity_unavailable"


def materialize_next_conservative_gate(
    *,
    producer_handle: DecisiveProducerHandle,
    current_time: datetime | None = None,
) -> str:
    """Write a protected zero-turn ``BLOCKED`` source for the next execution."""

    record = _producer_handle_record(producer_handle)
    now = current_time or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ProductionAdapterError("live gate time must be timezone-aware")
    if (
        record.journal._execution_started_at is None
        or record.journal._execution_started_event_digest is None
        or now < record.journal._execution_started_at
    ):
        raise ProductionAdapterError("live gate requires started execution")
    expires_at = min(
        now + timedelta(minutes=5), record.journal.authorization.expires_at
    )
    if expires_at <= now:
        raise ProductionAdapterError("live gate authority is expired")

    criterion_ids = tuple(
        criterion.criterion_id
        for criterion in record.registry.compiled_plan.criteria.values()
        if record.execution_id in criterion.obligation_ids
    )
    if not criterion_ids:
        raise ProductionAdapterError("live gate criterion scope is empty")
    reason = _reason_for_next_execution(record)
    context = {
        "schema_version": "noor-e2e-live-block-context/v1",
        "registry_id": record.registry.registry_id,
        "run_id": record.journal.run_id,
        "authorization_digest": record.journal.authorization_digest,
        "execution_id": record.execution_id,
        "criterion_ids": criterion_ids,
        "execution_started_event_digest": (
            record.journal._execution_started_event_digest
        ),
        "producer": "trusted-evidence-registry",
        "reason_code": reason,
        "observed_at": now.isoformat(),
    }
    context_digest = _write_or_validate_exact(
        record.journal.run_root,
        f"gate-evidence-context/{record.execution_id}.json",
        context,
    )
    artifact = execution.GateEvidenceArtifact(
        schema_version="noor-e2e-gate-evidence/v2",
        registry_id=record.registry.registry_id,
        run_id=record.journal.run_id,
        authorization_digest=record.journal.authorization_digest,
        execution_id=record.execution_id,
        criterion_ids=criterion_ids,
        execution_owner=record.journal.authorization.authorization_id,
        execution_started_event_digest=record.journal._execution_started_event_digest,
        outcome="BLOCKED",
        producer="trusted-evidence-registry",
        observed_at=now,
        evidence_digest=context_digest,
    )
    artifact_sha256 = _write_or_validate_exact(
        record.journal.run_root,
        f"gate-evidence/{record.execution_id}.json",
        artifact.model_dump(mode="json"),
    )
    receipt = execution.GateEvidenceReceipt(
        schema_version="noor-e2e-gate-evidence-receipt/v2",
        registry_id=record.registry.registry_id,
        run_id=record.journal.run_id,
        authorization_digest=record.journal.authorization_digest,
        execution_id=record.execution_id,
        criterion_ids=criterion_ids,
        execution_owner=record.journal.authorization.authorization_id,
        execution_started_event_digest=record.journal._execution_started_event_digest,
        artifact_sha256=artifact_sha256,
        outcome="BLOCKED",
        producer="trusted-evidence-registry",
        issued_at=now,
        expires_at=expires_at,
    )
    receipt_digest = _write_or_validate_exact(
        record.journal.run_root,
        f"producer-receipts/gates/{record.execution_id}.json",
        receipt.model_dump(mode="json"),
    )
    attempted = execution.GateAttemptV2(
        schema_version="noor-e2e-gate-attempt/v2",
        execution_id=record.execution_id,
        outcome="BLOCKED",
        run_started_at=record.journal._execution_started_at,
        execution_started_event_digest=record.journal._execution_started_event_digest,
        receipt_digest=receipt_digest,
    )
    return _write_producer_observation(
        producer_handle=producer_handle,
        attempted=attempted,
        transcript_facts=[],
    )


__all__ = [
    "IndependentActionReconciler",
    "IndependentExecutionProducer",
    "materialize_next_conservative_gate",
]
