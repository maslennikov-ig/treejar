"""Read-only production observation producer for the Noor E2E harness."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.message import Message
from src.models.outbound_message import OutboundMessageAudit
from src.services.outbound_audit import deterministic_crm_message_id
from src.services.runtime_execution_evidence import (
    RUNTIME_EXECUTION_EVIDENCE_KEY,
    RuntimeTurnEvidence,
)

_SUCCESS_STATUSES = frozenset({"delivered", "read", "edited"})
_FAILED_STATUSES = frozenset({"error"})
_TERMINAL_STATUSES = _SUCCESS_STATUSES | _FAILED_STATUSES


class ProductionObservationError(RuntimeError):
    """Production rows are inconsistent or cannot be bound to the request."""


class ProductionObservationNotReady(ProductionObservationError):
    """A production effect is missing, unknown, or not terminal yet."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ServerToolTraceFact(_StrictModel):
    call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    arguments_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: Literal["returned"]


class ServerTranscriptFact(_StrictModel):
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
    tool_traces: tuple[ServerToolTraceFact, ...]
    tools: tuple[str, ...]
    tool_outcomes: tuple[str, ...]
    audit_ids: tuple[str, ...]
    media_refs: tuple[str, ...]
    token_count: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    deviation: str | None
    evaluator_reasoning: str = Field(min_length=1)


class ServerSideEffectFact(_StrictModel):
    artifact_id: str = Field(min_length=1)
    subsystem: Literal["conversation", "crm", "escalation", "quotation"]
    artifact_type: Literal[
        "audit",
        "crm_contact",
        "crm_deal",
        "escalation",
        "sale_order",
    ]
    baseline_readback: dict[str, Any]
    expected_effect: dict[str, Any]
    final_readback: dict[str, Any]
    disposition: Literal[
        "voided",
        "closed",
        "resolved",
        "retained_as_test_evidence",
        "cleanup_pending",
    ]
    follow_up_suppressed: bool
    checksum_refs: tuple[str, ...] = Field(min_length=1)


class ServerExecutionObservation(_StrictModel):
    schema_version: Literal["noor-e2e-server-execution-observation/v1"]
    execution_id: str = Field(min_length=1)
    observed_at: datetime
    transcript_facts: tuple[ServerTranscriptFact, ...] = Field(min_length=1)
    side_effect_facts: tuple[ServerSideEffectFact, ...]
    baseline_inventory: dict[str, dict[str, Any]]
    final_inventory: dict[str, dict[str, Any]]

    @model_validator(mode="after")
    def _side_effects_cover_inventory_delta(self) -> ServerExecutionObservation:
        changed = {
            identity
            for identity in set(self.baseline_inventory) | set(self.final_inventory)
            if self.baseline_inventory.get(identity)
            != self.final_inventory.get(identity)
        }
        listed = [item.artifact_id for item in self.side_effect_facts]
        if changed != set(listed) or len(listed) != len(set(listed)):
            raise ValueError("server side effects do not exactly cover inventory delta")
        if any(
            item.baseline_readback
            != self.baseline_inventory.get(item.artifact_id, {"state": "absent"})
            or item.final_readback != self.final_inventory[item.artifact_id]
            for item in self.side_effect_facts
        ):
            raise ValueError("server side-effect readback differs from inventory")
        identity_sets = (
            [item.turn_id for item in self.transcript_facts],
            [item.message_id for item in self.transcript_facts],
            [item.provider_message_id for item in self.transcript_facts],
        )
        if any(len(values) != len(set(values)) for values in identity_sets):
            raise ValueError("server transcript contains duplicate identities")
        return self


class ServerWazzupActionReconciliation(_StrictModel):
    schema_version: Literal["noor-e2e-wazzup-action-reconciliation/v2"]
    adapter_id: Literal["wazzup-webhook-adapter"]
    capability: Literal["webhook.inbound"]
    observed_at: datetime
    resolved_state: Literal["succeeded", "failed"]
    source_message_ids: tuple[str, ...] = Field(min_length=1)
    audit_ids: tuple[str, ...] = Field(min_length=1)
    outbound_provider_message_ids: tuple[str, ...]
    outbound_statuses: tuple[str, ...] = Field(min_length=1)
    inventory: dict[str, dict[str, Any]] = Field(min_length=1)
    actual_cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def _provider_receipt(self) -> ServerWazzupActionReconciliation:
        identity_sets = (
            self.source_message_ids,
            self.audit_ids,
            self.outbound_provider_message_ids,
        )
        if (
            not math.isfinite(self.actual_cost_usd)
            or any(len(values) != len(set(values)) for values in identity_sets)
            or (
                self.resolved_state == "succeeded"
                and (
                    not self.outbound_provider_message_ids
                    or not all(
                        status in _SUCCESS_STATUSES for status in self.outbound_statuses
                    )
                )
            )
            or (
                self.resolved_state == "failed"
                and not any(
                    status in _FAILED_STATUSES for status in self.outbound_statuses
                )
            )
        ):
            raise ValueError("server Wazzup reconciliation receipt is invalid")
        return self


@dataclass
class ObservedTurnRows:
    conversation: Conversation
    inbound: Message
    assistant: Message
    outbound: tuple[OutboundMessageAudit, ...]
    runtime_evidence: dict[str, Any]
    final_readback_inventory: dict[str, dict[str, Any]] = field(default_factory=dict)


def _aware_utc(value: datetime | None, *, label: str) -> datetime:
    if value is None:
        raise ProductionObservationNotReady(f"{label} timestamp is unavailable")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _message_usage(
    message: Message,
    *,
    required: bool,
    label: str,
) -> tuple[int, float]:
    tokens_in = message.tokens_in
    tokens_out = message.tokens_out
    cost = message.cost
    values = (tokens_in, tokens_out, cost)
    if not required and all(value is None for value in values) and not message.model:
        return 0, 0.0
    if (
        not message.model
        or any(value is None for value in values)
        or not all(
            math.isfinite(float(value)) and float(value) >= 0
            for value in values
            if value is not None
        )
    ):
        raise ProductionObservationNotReady(f"{label} usage is unavailable")
    assert tokens_in is not None and tokens_out is not None and cost is not None
    return int(tokens_in) + int(tokens_out), float(cost)


def _turn_usage(
    rows: ObservedTurnRows,
    evidence: RuntimeTurnEvidence,
) -> tuple[int, float]:
    if evidence.usage_provenance == "provider_reported":
        assistant_tokens, assistant_cost = _message_usage(
            rows.assistant,
            required=True,
            label="assistant provider",
        )
    elif evidence.usage_provenance == "deterministic_static":
        if (
            not rows.assistant.model
            or rows.assistant.tokens_in != 0
            or rows.assistant.tokens_out != 0
            or (rows.assistant.cost is not None and float(rows.assistant.cost) != 0)
        ):
            raise ProductionObservationNotReady(
                "deterministic static usage provenance is invalid"
            )
        assistant_tokens, assistant_cost = 0, 0.0
    else:
        raise ProductionObservationNotReady("runtime usage provenance is unavailable")
    inbound_tokens, inbound_cost = _message_usage(
        rows.inbound,
        required=bool(rows.inbound.audio_url),
        label="inbound media provider",
    )
    return inbound_tokens + assistant_tokens, inbound_cost + assistant_cost


def _runtime_evidence(rows: ObservedTurnRows) -> RuntimeTurnEvidence:
    try:
        evidence = RuntimeTurnEvidence.model_validate(rows.runtime_evidence)
    except ValidationError as exc:
        raise ProductionObservationError("runtime turn evidence is invalid") from exc
    if (
        evidence.source_message_id != rows.inbound.wazzup_message_id
        or evidence.assistant_message_id != str(rows.assistant.id)
    ):
        raise ProductionObservationError("runtime turn evidence binding drift")
    if any(trace.state != "returned" for trace in evidence.tool_traces):
        raise ProductionObservationNotReady("tool trace is incomplete or nonterminal")
    return evidence


def _terminal_audits(
    audits: tuple[OutboundMessageAudit, ...],
) -> tuple[OutboundMessageAudit, ...]:
    if not audits:
        raise ProductionObservationNotReady("outbound side effect is missing")
    for audit in audits:
        if audit.status not in _TERMINAL_STATUSES:
            raise ProductionObservationNotReady(
                f"outbound side effect is nonterminal: {audit.status}"
            )
        if audit.status in _SUCCESS_STATUSES and not audit.provider_message_id:
            raise ProductionObservationNotReady(
                "terminal outbound side effect lacks provider identity"
            )
    return audits


def build_turn_fact(turn_id: str, rows: ObservedTurnRows) -> ServerTranscriptFact:
    """Build one transcript fact only from durable server-owned rows."""

    evidence = _runtime_evidence(rows)
    audits = _terminal_audits(rows.outbound)
    sent_at = _aware_utc(rows.inbound.created_at, label="inbound")
    received_at = _aware_utc(evidence.received_at, label="received")
    first_visible_at = _aware_utc(rows.assistant.created_at, label="assistant")
    final_visible_at = max(
        _aware_utc(item.status_updated_at, label="outbound") for item in audits
    )
    if not sent_at <= received_at <= first_visible_at <= final_visible_at:
        raise ProductionObservationError("production transcript timeline is invalid")
    delivered_at = (
        final_visible_at
        if all(item.status in _SUCCESS_STATUSES for item in audits)
        else None
    )
    provider_ids = [
        str(item.provider_message_id) for item in audits if item.provider_message_id
    ]
    if not provider_ids:
        provider_ids = [f"failed:{audits[0].id}"]
    media_refs = (f"message-audio:{rows.inbound.id}",) if rows.inbound.audio_url else ()
    token_count, cost_usd = _turn_usage(rows, evidence)
    return ServerTranscriptFact(
        turn_id=turn_id,
        question=rows.inbound.content,
        answer=rows.assistant.content,
        sent_at=sent_at,
        received_at=received_at,
        first_visible_at=first_visible_at,
        final_visible_at=final_visible_at,
        delivered_at=delivered_at,
        duration_ms=int((final_visible_at - sent_at).total_seconds() * 1000),
        conversation_id=str(rows.conversation.id),
        message_id=str(rows.inbound.id),
        provider_message_id=provider_ids[0],
        model=str(rows.assistant.model),
        tool_traces=tuple(
            ServerToolTraceFact(
                call_id=item.call_id,
                tool_name=item.tool_name,
                arguments_digest=item.arguments_digest,
                outcome_digest=str(item.outcome_digest),
                state="returned",
            )
            for item in evidence.tool_traces
        ),
        tools=tuple(item.tool_name for item in evidence.tool_traces),
        tool_outcomes=tuple(item.state for item in evidence.tool_traces),
        audit_ids=tuple(str(item.id) for item in audits),
        media_refs=media_refs,
        token_count=token_count,
        cost_usd=round(cost_usd, 6),
        deviation=None,
        evaluator_reasoning="Observed from durable production records.",
    )


def _audit_inventory(rows: ObservedTurnRows) -> dict[str, dict[str, Any]]:
    audits = _terminal_audits(rows.outbound)
    return {
        f"conversation:audit:{audit.id}": {
            "state": "resolved",
            "provider": audit.provider,
            "status": audit.status,
            "source": audit.source,
        }
        for audit in audits
    }


def _inventory(rows: ObservedTurnRows) -> dict[str, dict[str, Any]]:
    evidence = _runtime_evidence(rows)
    return {
        **evidence.final_inventory,
        **rows.final_readback_inventory,
        **_audit_inventory(rows),
    }


def _artifact_kind(artifact_id: str) -> tuple[str, str]:
    parts = artifact_id.split(":", 2)
    if len(parts) < 2:
        raise ProductionObservationError(
            f"unsupported business effect identity: {artifact_id}"
        )
    prefix = (parts[0], parts[1])
    kinds = {
        ("crm", "contact"): ("crm", "crm_contact"),
        ("crm", "deal"): ("crm", "crm_deal"),
        ("escalation", "conversation"): ("escalation", "escalation"),
        ("quotation", "sale_order"): ("quotation", "sale_order"),
    }
    try:
        return kinds[prefix]
    except KeyError as exc:
        raise ProductionObservationError(
            f"unsupported business effect identity: {artifact_id}"
        ) from exc


def _terminal_disposition(artifact_id: str, final_readback: dict[str, Any]) -> str:
    state = final_readback.get("state")
    dispositions = {
        "voided": "voided",
        "closed": "closed",
        "resolved": "resolved",
        "retained": "retained_as_test_evidence",
        "active": "cleanup_pending",
    }
    if state not in dispositions:
        raise ProductionObservationNotReady(
            f"business side effect lacks terminal readback: {artifact_id}/{state}"
        )
    return dispositions[str(state)]


def _readback_checksum(artifact_id: str, value: dict[str, Any]) -> str:
    payload = json.dumps(
        {"artifact_id": artifact_id, "readback": value},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _side_effect_facts(rows: ObservedTurnRows) -> tuple[ServerSideEffectFact, ...]:
    evidence = _runtime_evidence(rows)
    follow_up_suppressed = (
        isinstance(rows.conversation.metadata_, dict)
        and rows.conversation.metadata_.get("runtime_e2e_follow_up_suppressed") is True
    )
    facts: list[ServerSideEffectFact] = []
    for audit in _terminal_audits(rows.outbound):
        details = audit.details if isinstance(audit.details, dict) else {}
        final_readback = _audit_inventory(rows)[f"conversation:audit:{audit.id}"]
        facts.append(
            ServerSideEffectFact(
                artifact_id=f"conversation:audit:{audit.id}",
                subsystem="conversation",
                artifact_type="audit",
                baseline_readback={"state": "absent"},
                expected_effect=final_readback,
                final_readback=final_readback,
                disposition="resolved",
                follow_up_suppressed=details.get("follow_up_suppressed") is True,
                checksum_refs=(f"outbound-audit:{audit.id}",),
            )
        )

    business_ids = {
        identity
        for identity in set(evidence.baseline_inventory) | set(evidence.final_inventory)
        if evidence.baseline_inventory.get(identity)
        != evidence.final_inventory.get(identity)
    }
    for artifact_id in sorted(business_ids):
        expected = evidence.final_inventory.get(artifact_id, {"state": "absent"})
        if expected.get("state") in {"unknown", "absent"}:
            raise ProductionObservationNotReady(
                f"business side effect is incomplete: {artifact_id}"
            )
        business_readback = rows.final_readback_inventory.get(artifact_id)
        if business_readback is None:
            raise ProductionObservationNotReady(
                f"business side-effect disposition is missing: {artifact_id}"
            )
        subsystem, artifact_type = _artifact_kind(artifact_id)
        facts.append(
            ServerSideEffectFact(
                artifact_id=artifact_id,
                subsystem=subsystem,
                artifact_type=artifact_type,
                baseline_readback=evidence.baseline_inventory.get(
                    artifact_id, {"state": "absent"}
                ),
                expected_effect=expected,
                final_readback=business_readback,
                disposition=_terminal_disposition(artifact_id, business_readback),
                follow_up_suppressed=follow_up_suppressed,
                checksum_refs=(
                    f"server-readback-sha256:{_readback_checksum(artifact_id, business_readback)}",
                ),
            )
        )
    return tuple(facts)


def _merge_inventory(
    items: tuple[dict[str, dict[str, Any]], ...],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for inventory in items:
        for artifact_id, state in inventory.items():
            existing = merged.get(artifact_id)
            if existing is not None and existing != state:
                raise ProductionObservationError(
                    f"server inventory conflicts for {artifact_id}"
                )
            merged[artifact_id] = state
    return merged


def build_execution_observation(
    *,
    execution_id: str,
    turns: tuple[tuple[str, ObservedTurnRows], ...],
    observed_at: datetime,
) -> ServerExecutionObservation:
    facts_by_id: dict[str, ServerSideEffectFact] = {}
    for _, rows in turns:
        for fact in _side_effect_facts(rows):
            existing = facts_by_id.get(fact.artifact_id)
            if existing is not None and existing != fact:
                raise ProductionObservationError(
                    f"server side-effect facts conflict for {fact.artifact_id}"
                )
            facts_by_id[fact.artifact_id] = fact
    baseline_inventory = _merge_inventory(
        tuple(_runtime_evidence(rows).baseline_inventory for _, rows in turns)
    )
    final_inventory = _merge_inventory(tuple(_inventory(rows) for _, rows in turns))
    try:
        return ServerExecutionObservation(
            schema_version="noor-e2e-server-execution-observation/v1",
            execution_id=execution_id,
            observed_at=observed_at,
            transcript_facts=tuple(
                build_turn_fact(turn_id, rows) for turn_id, rows in turns
            ),
            side_effect_facts=tuple(facts_by_id.values()),
            baseline_inventory=baseline_inventory,
            final_inventory=final_inventory,
        )
    except ValidationError as exc:
        raise ProductionObservationError(
            "server execution observation contains duplicate or invalid identities"
        ) from exc


def build_reconciliation_observation(
    *,
    rows: tuple[ObservedTurnRows, ...],
    observed_at: datetime,
) -> ServerWazzupActionReconciliation:
    inventory = {
        artifact_id: state
        for item in rows
        for artifact_id, state in _inventory(item).items()
    }
    audits = tuple(audit for item in rows for audit in _terminal_audits(item.outbound))
    statuses = tuple(audit.status for audit in audits)
    source_message_ids = tuple(
        str(item.inbound.wazzup_message_id or "") for item in rows
    )
    if any(not identity for identity in source_message_ids):
        raise ProductionObservationNotReady(
            "Wazzup reconciliation source identity is unavailable"
        )
    try:
        return ServerWazzupActionReconciliation(
            schema_version="noor-e2e-wazzup-action-reconciliation/v2",
            adapter_id="wazzup-webhook-adapter",
            capability="webhook.inbound",
            observed_at=observed_at,
            resolved_state=(
                "succeeded"
                if statuses and all(status in _SUCCESS_STATUSES for status in statuses)
                else "failed"
            ),
            source_message_ids=source_message_ids,
            audit_ids=tuple(str(audit.id) for audit in audits),
            outbound_provider_message_ids=tuple(
                str(audit.provider_message_id)
                for audit in audits
                if audit.provider_message_id
            ),
            outbound_statuses=statuses,
            inventory=inventory,
            actual_cost_usd=round(
                sum(_turn_usage(item, _runtime_evidence(item))[1] for item in rows),
                6,
            ),
        )
    except ValidationError as exc:
        raise ProductionObservationError(
            "server Wazzup reconciliation contains duplicate or invalid identities"
        ) from exc


def _turn_evidence(
    conversation: Conversation, source_message_id: str
) -> dict[str, Any]:
    metadata = (
        conversation.metadata_ if isinstance(conversation.metadata_, dict) else {}
    )
    container = metadata.get(RUNTIME_EXECUTION_EVIDENCE_KEY)
    if (
        not isinstance(container, dict)
        or container.get("schema_version")
        not in {
            "noor-runtime-execution-evidence/v1",
            "noor-runtime-execution-evidence/v2",
            "noor-runtime-execution-evidence/v3",
        }
        or not isinstance(container.get("turns"), list)
    ):
        raise ProductionObservationNotReady("runtime execution evidence is missing")
    matches = [
        item
        for item in container["turns"]
        if isinstance(item, dict) and item.get("source_message_id") == source_message_id
    ]
    if len(matches) != 1:
        raise ProductionObservationError("runtime turn evidence is not unique")
    return dict(matches[0])


async def collect_turn_rows(
    db: AsyncSession, *, source_message_id: str
) -> ObservedTurnRows:
    inbound_result = await db.execute(
        select(Message).where(Message.wazzup_message_id == source_message_id)
    )
    inbound = inbound_result.scalar_one_or_none()
    if not isinstance(inbound, Message) or inbound.role != "user":
        raise ProductionObservationNotReady("inbound production message is missing")

    conversation_result = await db.execute(
        select(Conversation).where(Conversation.id == inbound.conversation_id)
    )
    conversation = conversation_result.scalar_one_or_none()
    if not isinstance(conversation, Conversation):
        raise ProductionObservationError("production conversation is missing")
    evidence = _turn_evidence(conversation, source_message_id)
    try:
        assistant_id = uuid.UUID(str(evidence["assistant_message_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ProductionObservationError(
            "runtime assistant identity is invalid"
        ) from exc

    assistant_result = await db.execute(
        select(Message).where(
            Message.id == assistant_id,
            Message.conversation_id == conversation.id,
            Message.role == "assistant",
        )
    )
    assistant = assistant_result.scalar_one_or_none()
    if not isinstance(assistant, Message):
        raise ProductionObservationNotReady("assistant production message is missing")
    bot_crm_message_id = deterministic_crm_message_id(
        "bot", conversation.id, source_message_id
    )
    outbound_result = await db.execute(
        select(OutboundMessageAudit).where(
            OutboundMessageAudit.provider == "wazzup",
            OutboundMessageAudit.conversation_id == conversation.id,
        )
    )
    outbound = tuple(
        audit
        for audit in outbound_result.scalars().all()
        if isinstance(audit, OutboundMessageAudit)
        and (
            (
                isinstance(audit.details, dict)
                and audit.details.get("source_message_id") == source_message_id
                and audit.details.get("customer_visible") is not False
            )
            or audit.crm_message_id == bot_crm_message_id
        )
    )
    return ObservedTurnRows(
        conversation=conversation,
        inbound=inbound,
        assistant=assistant,
        outbound=outbound,
        runtime_evidence=evidence,
    )


def _business_delta(rows: ObservedTurnRows) -> set[str]:
    evidence = _runtime_evidence(rows)
    return {
        identity
        for identity in set(evidence.baseline_inventory) | set(evidence.final_inventory)
        if evidence.baseline_inventory.get(identity)
        != evidence.final_inventory.get(identity)
    }


def _closed_readback() -> dict[str, Any]:
    return {"state": "closed"}


async def collect_business_readbacks(
    rows: ObservedTurnRows,
    *,
    crm_client: Any,
    inventory_client: Any,
) -> dict[str, dict[str, Any]]:
    """Read current CRM/quotation/escalation facts by exact durable identity."""

    from src.integrations.inventory.zoho_inventory import extract_sale_order_data

    readbacks: dict[str, dict[str, Any]] = {}
    for artifact_id in sorted(_business_delta(rows)):
        parts = artifact_id.split(":", 2)
        if len(parts) != 3:
            raise ProductionObservationError(
                f"unsupported business effect identity: {artifact_id}"
            )
        subsystem, artifact_type, durable_id = parts
        if (subsystem, artifact_type) == ("crm", "contact"):
            contact = await crm_client.get_contact(durable_id)
            if contact is None:
                readbacks[artifact_id] = _closed_readback()
                continue
            returned_id = str(contact.get("id") or "")
            if returned_id and returned_id != durable_id:
                raise ProductionObservationError("CRM contact readback identity drift")
            readbacks[artifact_id] = {
                "state": "active",
                "status": str(contact.get("status") or "active"),
            }
        elif (subsystem, artifact_type) == ("crm", "deal"):
            deal = await crm_client.get_deal_status(durable_id)
            if deal is None:
                readbacks[artifact_id] = _closed_readback()
                continue
            returned_id = str(deal.get("id") or "")
            if returned_id and returned_id != durable_id:
                raise ProductionObservationError("CRM deal readback identity drift")
            readbacks[artifact_id] = {
                "state": "active",
                "status": str(deal.get("Stage") or deal.get("stage") or "unknown"),
            }
        elif (subsystem, artifact_type) == ("quotation", "sale_order"):
            raw_order = await inventory_client.get_sale_order(durable_id)
            if raw_order is None:
                readbacks[artifact_id] = _closed_readback()
                continue
            order = extract_sale_order_data(raw_order)
            returned_id = str(order.get("salesorder_id") or "")
            if returned_id != durable_id:
                raise ProductionObservationError(
                    "Zoho sale order readback identity drift"
                )
            line_items = order.get("line_items")
            normalized_lines = [
                {
                    key: item.get(key)
                    for key in ("item_id", "sku", "quantity", "rate", "item_total")
                    if item.get(key) is not None
                }
                for item in line_items or ()
                if isinstance(item, dict)
            ]
            readbacks[artifact_id] = {
                "state": "active",
                "status": str(order.get("status") or "unknown"),
                "customer_id": str(order.get("customer_id") or ""),
                "line_items": normalized_lines,
                "total": order.get("total"),
            }
        elif (subsystem, artifact_type) == ("escalation", "conversation"):
            if durable_id != str(rows.conversation.id):
                raise ProductionObservationError("escalation readback identity drift")
            status = str(rows.conversation.escalation_status or "none")
            readbacks[artifact_id] = (
                {"state": "resolved", "status": status}
                if status == "resolved"
                else _closed_readback()
                if status == "none"
                else {"state": "unknown", "status": status}
            )
        else:
            readbacks[artifact_id] = {"state": "unknown"}
    rows.final_readback_inventory = readbacks
    return readbacks


def _parse_turn(value: str) -> tuple[str, str]:
    turn_id, separator, source_message_id = value.partition("=")
    if (
        separator != "="
        or not turn_id
        or not source_message_id
        or any(character.isspace() for character in value)
    ):
        raise argparse.ArgumentTypeError("turn must be TURN_ID=SOURCE_MESSAGE_ID")
    return turn_id, source_message_id


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="noor-e2e-observe")
    subparsers = parser.add_subparsers(dest="command", required=True)
    execution = subparsers.add_parser("execution")
    execution.add_argument("--execution-id", required=True)
    execution.add_argument("--turn", action="append", type=_parse_turn, required=True)
    reconciliation = subparsers.add_parser("reconciliation")
    reconciliation.add_argument(
        "--turn", action="append", type=_parse_turn, required=True
    )
    return parser


async def _run(args: argparse.Namespace) -> BaseModel:
    from src.core.database import async_session_factory
    from src.core.redis import redis_client
    from src.integrations.crm.zoho_crm import ZohoCRMClient
    from src.integrations.inventory.zoho_inventory import ZohoInventoryClient

    async with async_session_factory() as db:
        observed_rows: list[tuple[str, ObservedTurnRows]] = []
        for turn_id, source_message_id in args.turn:
            observed_rows.append(
                (
                    turn_id,
                    await collect_turn_rows(db, source_message_id=source_message_id),
                )
            )
        rows = tuple(observed_rows)
        async with (
            ZohoCRMClient(redis_client=redis_client) as crm_client,
            ZohoInventoryClient(redis_client=redis_client) as inventory_client,
        ):
            for _, item in rows:
                await collect_business_readbacks(
                    item,
                    crm_client=crm_client,
                    inventory_client=inventory_client,
                )
    now = datetime.now(UTC)
    if args.command == "execution":
        return build_execution_observation(
            execution_id=str(args.execution_id),
            turns=rows,
            observed_at=now,
        )
    return build_reconciliation_observation(
        rows=tuple(item for _, item in rows),
        observed_at=now,
    )


def main() -> None:
    result = asyncio.run(_run(_parser().parse_args()))
    print(
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
