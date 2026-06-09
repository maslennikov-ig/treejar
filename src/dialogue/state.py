from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, Field, ValidationError, field_validator

from src.dialogue.order_state import (
    QuoteFrame,
    quote_frame_from_metadata,
    quote_frame_is_active,
)

DIALOGUE_KERNEL_METADATA_KEY = "dialogue_kernel"
DIALOGUE_STATE_METADATA_KEY = "dialogue_state"


class DialogueSlots(BaseModel):
    customer_name: str | None = None
    company: str | None = None
    customer_type: str | None = None
    delivery_address: str | None = None
    selected_items: list[dict[str, Any]] = Field(default_factory=list)
    pending_product_refs: list[str] = Field(default_factory=list)
    quote_sent: bool = False
    post_quotation_status: str | None = None


class LastQuestion(BaseModel):
    flow: str
    prompt_key: str
    asked_at: str | datetime | None = None
    expected_slots: list[str] = Field(default_factory=list)


class ExpectedSlot(BaseModel):
    slot: str
    required: bool = True
    accepted_values: list[str] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)
    validator: str | None = None


class ExpectedAnswerFrame(BaseModel):
    frame_id: str
    flow: str
    question_kind: str
    prompt_key: str | None = None
    status: str = "active"
    priority: int = 50
    asked_at: str | datetime | None = None
    expires_at: str | datetime | None = None
    max_customer_turns: int | None = None
    turns_seen: int = 0
    expected_slots: list[ExpectedSlot] = Field(default_factory=list)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    filled_slots: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DialogueDecision(BaseModel):
    action: str
    flow: str
    response_text: str | None = None
    handled: bool = False
    side_effects_allowed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class DialogueTrace(BaseModel):
    mode: str
    legacy_route: str | None = None
    kernel_route: str | None = None
    decision: DialogueDecision
    slot_diff: dict[str, dict[str, Any]] = Field(default_factory=dict)
    mismatch_reason: str | None = None

    def to_bounded_dict(
        self,
        *,
        max_text_length: int = 240,
        max_slot_diff: int = 20,
    ) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        return cast(
            "dict[str, Any]", _bound_value(data, max_text_length, max_slot_diff)
        )


class DialogueState(BaseModel):
    version: int = 1
    thread_id: str | None = None
    active_flow: str | None = None
    slots: DialogueSlots = Field(default_factory=DialogueSlots)
    last_question: LastQuestion | None = None
    expected_answer_frames: list[ExpectedAnswerFrame] = Field(default_factory=list)
    trace_history: list[DialogueTrace] = Field(default_factory=list)

    @field_validator("expected_answer_frames", mode="before")
    @classmethod
    def _load_valid_expected_answer_frames(
        cls, value: Any
    ) -> list[ExpectedAnswerFrame]:
        if not isinstance(value, list):
            return []
        frames: list[ExpectedAnswerFrame] = []
        for item in value:
            if isinstance(item, ExpectedAnswerFrame):
                frames.append(item)
                continue
            if not isinstance(item, Mapping):
                continue
            try:
                frames.append(ExpectedAnswerFrame.model_validate(item))
            except ValidationError:
                continue
        return frames

    @classmethod
    def from_conversation_metadata(
        cls, metadata: dict[str, Any] | None
    ) -> DialogueState:
        return cls.load(metadata)

    @classmethod
    def load(cls, metadata: dict[str, Any] | None) -> DialogueState:
        if not isinstance(metadata, dict):
            return cls()
        kernel_payload = metadata.get(DIALOGUE_KERNEL_METADATA_KEY)
        thread_id = _mapping_text(kernel_payload, "thread_id")
        payload = (
            kernel_payload.get("state") if isinstance(kernel_payload, dict) else None
        )
        if not isinstance(payload, dict):
            payload = metadata.get(DIALOGUE_STATE_METADATA_KEY)
        if not isinstance(payload, dict):
            return cls(thread_id=thread_id)
        try:
            state = cls.model_validate(payload)
        except ValidationError:
            return cls(thread_id=thread_id)
        if thread_id and not state.thread_id:
            state = state.model_copy(update={"thread_id": thread_id})
        return state

    @classmethod
    def from_conversation(cls, conversation: Any) -> DialogueState:
        metadata = getattr(conversation, "metadata_", None)
        metadata = metadata if isinstance(metadata, dict) else {}
        state = cls.load(metadata)
        slot_updates: dict[str, Any] = {}

        customer_name = _text_value(getattr(conversation, "customer_name", None))
        customer_name = customer_name or _text_value(metadata.get("customer_name"))
        if customer_name and not state.slots.customer_name:
            slot_updates["customer_name"] = customer_name

        quote_details = metadata.get("quote_customer_details")
        if isinstance(quote_details, Mapping):
            detail_name = _mapping_text(quote_details, "name")
            company = _mapping_text(quote_details, "company")
            customer_type = _mapping_text(quote_details, "customer_type")
            address = _mapping_text(quote_details, "address")
            if detail_name and not state.slots.customer_name:
                slot_updates["customer_name"] = detail_name
            if company and not state.slots.company:
                slot_updates["company"] = company
            if customer_type and not state.slots.customer_type:
                slot_updates["customer_type"] = customer_type
            if address and not state.slots.delivery_address:
                slot_updates["delivery_address"] = address

        quote_frame = quote_frame_from_metadata(metadata)
        selection = metadata.get("pending_quote_selection")
        selected_items = _quote_frame_selection_items(quote_frame) or _selection_items(
            selection
        )
        if selected_items and not state.slots.selected_items:
            slot_updates["selected_items"] = selected_items
        quote_status = _mapping_text(metadata, "last_quote_status")
        selection_source = _mapping_text(selection, "source")
        quote_sent = state.slots.quote_sent or quote_status in {
            "sent",
            "shared",
            "delivered",
        }
        quote_sent = quote_sent or (
            quote_frame is not None and quote_frame.status == "quoted"
        )
        quote_sent = quote_sent or selection_source == "quotation_sent"
        if quote_sent:
            slot_updates["quote_sent"] = True
            slot_updates["post_quotation_status"] = quote_status or "sent"

        if slot_updates:
            state = state.model_copy(
                update={
                    "slots": state.slots.model_copy(update=slot_updates, deep=True)
                },
                deep=True,
            )

        active_flow = state.active_flow
        if not active_flow:
            if quote_sent:
                active_flow = "post_quotation_hold"
            elif selected_items:
                active_flow = "quote_details"
            elif isinstance(metadata.get("name_gate_pending_request"), Mapping):
                active_flow = "name_gate"
        thread_id = state.thread_id or _mapping_text(
            metadata.get(DIALOGUE_KERNEL_METADATA_KEY), "thread_id"
        )
        if not thread_id and getattr(conversation, "id", None):
            thread_id = f"conversation:{conversation.id}"
        state = state.model_copy(
            update={"active_flow": active_flow, "thread_id": thread_id},
            deep=True,
        )
        return state

    def to_metadata_patch(self) -> dict[str, Any]:
        return {
            DIALOGUE_KERNEL_METADATA_KEY: {
                "state": self.model_dump(mode="json"),
                "traces": [
                    trace.to_bounded_dict() for trace in self.trace_history[-20:]
                ],
            }
        }

    def to_metadata(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        updated = dict(metadata or {})
        updated.update(self.to_metadata_patch())
        return updated


def _bound_value(value: Any, max_text_length: int, max_items: int) -> Any:
    if isinstance(value, str):
        if len(value) <= max_text_length:
            return value
        if max_text_length <= 3:
            return "." * max_text_length
        return f"{value[: max_text_length - 3]}..."
    if isinstance(value, list):
        return [
            _bound_value(item, max_text_length, max_items) for item in value[:max_items]
        ]
    if isinstance(value, dict):
        bounded: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                break
            bounded[key] = _bound_value(item, max_text_length, max_items)
        return bounded
    return value


def _text_value(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _mapping_text(value: Any, key: str) -> str | None:
    if not isinstance(value, Mapping):
        return None
    raw = value.get(key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _selection_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    raw_items = value.get("items")
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            continue
        sku = _mapping_text(raw_item, "sku")
        quantity = raw_item.get("quantity")
        if not sku or not isinstance(quantity, int) or quantity <= 0:
            continue
        items.append({"sku": sku, "quantity": quantity})
    return items


def _quote_frame_selection_items(frame: QuoteFrame | None) -> list[dict[str, Any]]:
    if not quote_frame_is_active(frame):
        return []
    return [
        {"sku": line.sku, "quantity": line.quantity}
        for line in frame.lines
        if line.is_valid
    ]
