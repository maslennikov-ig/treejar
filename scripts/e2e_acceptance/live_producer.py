"""Conservative production gate producer for unavailable live proof.

This module never executes a customer or provider action. It can only derive a
``BLOCKED`` result for the next canonical execution from the immutable scenario
kind and the trusted registry. The caller cannot select an execution, outcome,
producer, criterion set, or reason.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.production import (
    DecisiveProducerHandle,
    ProductionAdapterError,
    _producer_handle_record,
    _ProducerHandleRecord,
    _write_or_validate_exact,
    _write_producer_observation,
)

BlockReason = Literal[
    "disjoint_identity_unavailable",
    "provider_origin_unavailable",
    "independent_evidence_unavailable",
]


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


__all__ = ["materialize_next_conservative_gate"]
