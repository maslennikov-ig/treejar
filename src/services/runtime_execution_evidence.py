"""Bounded server-owned evidence for one customer turn.

The product response remains unchanged. This module records only identifiers,
digests, timestamps, and tool terminality in the existing conversation JSON
metadata so a read-only production collector can materialize factual E2E
observations without accepting transcript facts from the caller.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)

RUNTIME_EXECUTION_EVIDENCE_KEY = "runtime_execution_evidence"
_RUNTIME_TURN_LIMIT = 20


class RuntimeToolTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    arguments_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    state: Literal["returned", "unknown"]

    @model_validator(mode="after")
    def _terminal_digest(self) -> RuntimeToolTrace:
        if (self.state == "returned") != (self.outcome_digest is not None):
            raise ValueError("tool terminal state and outcome digest differ")
        return self


class RuntimeTurnEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "noor-runtime-turn-evidence/v1",
        "noor-runtime-turn-evidence/v2",
        "noor-runtime-turn-evidence/v3",
    ]
    source_message_id: str = Field(min_length=1)
    assistant_message_id: str = Field(min_length=1)
    received_at: datetime
    recorded_at: datetime
    usage_provenance: Literal["provider_reported", "deterministic_static"] | None = None
    tool_traces: tuple[RuntimeToolTrace, ...]
    baseline_inventory: dict[str, dict[str, Any]] = Field(default_factory=dict)
    final_inventory: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _versioned_usage_provenance(self) -> RuntimeTurnEvidence:
        if (self.schema_version == "noor-runtime-turn-evidence/v3") != (
            self.usage_provenance is not None
        ):
            raise ValueError("runtime usage provenance/version binding drift")
        return self


_TOOL_TRACE_ADAPTER = TypeAdapter(tuple[RuntimeToolTrace, ...])


def _canonical_digest(value: object) -> str:
    def _default(item: object) -> object:
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            return model_dump(mode="json")
        if isinstance(item, datetime):
            return item.isoformat()
        return repr(item)

    encoded = json.dumps(
        value,
        default=_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def extract_runtime_tool_traces(result: Any) -> tuple[RuntimeToolTrace, ...]:
    """Extract ordered call/return identities from the completed agent result."""

    all_messages = getattr(result, "all_messages", None)
    if not callable(all_messages):
        return ()
    calls: list[ToolCallPart] = []
    returns: dict[str, ToolReturnPart] = {}
    for message in all_messages():
        if not isinstance(message, ModelRequest | ModelResponse):
            continue
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                calls.append(part)
            elif isinstance(part, ToolReturnPart):
                returns[part.tool_call_id] = part

    traces: list[RuntimeToolTrace] = []
    seen: set[str] = set()
    for call in calls:
        if call.tool_call_id in seen:
            continue
        seen.add(call.tool_call_id)
        returned = returns.get(call.tool_call_id)
        traces.append(
            RuntimeToolTrace(
                call_id=call.tool_call_id,
                tool_name=call.tool_name,
                arguments_digest=_canonical_digest(call.args),
                outcome_digest=(
                    _canonical_digest(returned.content)
                    if returned is not None
                    else None
                ),
                state="returned" if returned is not None else "unknown",
            )
        )
    return tuple(traces)


def build_runtime_tool_trace(
    *,
    tool_name: str,
    arguments: object,
    outcome: object,
) -> RuntimeToolTrace:
    """Build a digest-only trace for a deterministic application tool route."""

    arguments_digest = _canonical_digest(arguments)
    return RuntimeToolTrace(
        call_id=f"runtime-{tool_name}-{arguments_digest[:20]}",
        tool_name=tool_name,
        arguments_digest=arguments_digest,
        outcome_digest=_canonical_digest(outcome),
        state="returned",
    )


def record_runtime_turn_evidence(
    conversation: Any,
    *,
    source_message_id: str | None,
    assistant_message_id: str,
    received_at: datetime,
    recorded_at: datetime,
    usage_provenance: Literal["provider_reported", "deterministic_static"],
    tool_traces: tuple[RuntimeToolTrace, ...],
    baseline_inventory: dict[str, dict[str, Any]] | None = None,
    final_inventory: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Upsert one bounded evidence row without disturbing unrelated metadata."""

    if not source_message_id:
        return
    evidence = RuntimeTurnEvidence(
        schema_version="noor-runtime-turn-evidence/v3",
        source_message_id=source_message_id,
        assistant_message_id=assistant_message_id,
        received_at=received_at,
        recorded_at=recorded_at,
        usage_provenance=usage_provenance,
        tool_traces=tool_traces,
        baseline_inventory=baseline_inventory or {},
        final_inventory=final_inventory or {},
    )
    metadata = dict(getattr(conversation, "metadata_", None) or {})
    current = metadata.get(RUNTIME_EXECUTION_EVIDENCE_KEY)
    turns = (
        list(current.get("turns", ()))
        if isinstance(current, dict)
        and current.get("schema_version")
        in {
            "noor-runtime-execution-evidence/v1",
            "noor-runtime-execution-evidence/v2",
            "noor-runtime-execution-evidence/v3",
        }
        and isinstance(current.get("turns"), list)
        else []
    )
    turns = [
        item
        for item in turns
        if isinstance(item, dict) and item.get("source_message_id") != source_message_id
    ]
    turns.append(evidence.model_dump(mode="json"))
    metadata[RUNTIME_EXECUTION_EVIDENCE_KEY] = {
        "schema_version": "noor-runtime-execution-evidence/v3",
        "turns": turns[-_RUNTIME_TURN_LIMIT:],
    }
    conversation.metadata_ = metadata


def parse_runtime_tool_traces(value: object) -> tuple[RuntimeToolTrace, ...]:
    """Strict shared parser used by the production observation producer."""

    return _TOOL_TRACE_ADAPTER.validate_python(value)


def snapshot_runtime_inventory(conversation: Any) -> dict[str, dict[str, Any]]:
    """Project durable business effects without customer content or secrets."""

    inventory: dict[str, dict[str, Any]] = {}
    contact_id = getattr(conversation, "zoho_contact_id", None)
    if isinstance(contact_id, str) and contact_id:
        inventory[f"crm:contact:{contact_id}"] = {"state": "active"}
    deal_id = getattr(conversation, "zoho_deal_id", None)
    if isinstance(deal_id, str) and deal_id:
        inventory[f"crm:deal:{deal_id}"] = {
            "state": "active",
            "status": str(getattr(conversation, "deal_status", "") or "unknown"),
        }

    metadata = (
        conversation.metadata_
        if isinstance(getattr(conversation, "metadata_", None), dict)
        else {}
    )
    raw_journal = metadata.get("quotation_effect_journal")
    entries = raw_journal.get("entries") if isinstance(raw_journal, dict) else None
    for effect in entries or ():
        if not isinstance(effect, dict):
            continue
        order_id = effect.get("sale_order_id")
        if not isinstance(order_id, str) or not order_id:
            continue
        status = str(effect.get("status") or "unknown")
        inventory[f"quotation:sale_order:{order_id}"] = {
            "state": "active" if status == "pdf_sent" else "unknown",
            "status": status,
            "source_message_id": effect.get("source_message_id"),
            "media_crm_message_id": effect.get("media_crm_message_id"),
            "caption_crm_message_id": effect.get("caption_crm_message_id"),
        }

    escalation_status = str(getattr(conversation, "escalation_status", "") or "none")
    if escalation_status != "none":
        inventory[f"escalation:conversation:{conversation.id}"] = {
            "state": ("resolved" if escalation_status == "resolved" else "active"),
            "status": escalation_status,
        }
    return inventory


__all__ = [
    "RUNTIME_EXECUTION_EVIDENCE_KEY",
    "RuntimeToolTrace",
    "RuntimeTurnEvidence",
    "build_runtime_tool_trace",
    "extract_runtime_tool_traces",
    "parse_runtime_tool_traces",
    "record_runtime_turn_evidence",
    "snapshot_runtime_inventory",
]
