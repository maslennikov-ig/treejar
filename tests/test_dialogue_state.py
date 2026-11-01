from __future__ import annotations

from types import SimpleNamespace

from src.dialogue.state import (
    DialogueSlots,
    DialogueState,
    LastQuestion,
    QuoteConsent,
    QuoteLifecycle,
)


def test_dialogue_state_loads_from_metadata_and_emits_patch() -> None:
    metadata = {
        "source": "whatsapp",
        "dialogue_state": {
            "version": 1,
            "active_flow": "quotation",
            "slots": {
                "customer_name": "Mira",
                "company": "Noor",
                "customer_type": "business",
                "delivery_address": "Dubai Marina",
                "selected_items": [{"sku": "CH-616", "quantity": 2}],
                "pending_product_refs": ["SKYLAND NOVO 2400"],
                "quote_sent": True,
                "post_quotation_status": "waiting_customer",
            },
            "last_question": {
                "flow": "quotation",
                "prompt_key": "ask_delivery_address",
                "asked_at": "2026-05-19T09:30:00+00:00",
                "expected_slots": ["delivery_address"],
            },
            "trace_history": [],
        },
    }

    state = DialogueState.from_conversation_metadata(metadata)

    assert state.active_flow == "quotation"
    assert state.slots.customer_name == "Mira"
    assert state.slots.selected_items == [{"sku": "CH-616", "quantity": 2}]
    assert state.last_question == LastQuestion(
        flow="quotation",
        prompt_key="ask_delivery_address",
        asked_at="2026-05-19T09:30:00+00:00",
        expected_slots=["delivery_address"],
    )
    assert state.to_metadata_patch() == {
        "dialogue_kernel": {
            "state": state.model_dump(mode="json"),
            "traces": [],
        }
    }


def test_dialogue_state_load_returns_defaults_for_missing_or_invalid_metadata() -> None:
    assert DialogueState.load(None).slots == DialogueSlots()
    assert (
        DialogueState.load({"dialogue_state": {"slots": "bad"}}).slots
        == DialogueSlots()
    )


def test_dialogue_state_imports_selected_items_from_canonical_quote_frame() -> None:
    conversation = SimpleNamespace(
        id="conv-quote-frame",
        customer_name="Lilia",
        metadata_={
            "order_runtime": {
                "quote_frame": {
                    "source": "selection_confirmation",
                    "status": "collecting_details",
                    "lines": [
                        {"sku": "SKYLAND-NOVO-2400", "quantity": 2},
                        {"sku": "CH-616-NEW-BLACK", "quantity": 4},
                    ],
                }
            }
        },
    )

    state = DialogueState.from_conversation(conversation)

    assert state.active_flow == "quote_details"
    assert state.slots.selected_items == [
        {"sku": "SKYLAND-NOVO-2400", "quantity": 2},
        {"sku": "CH-616-NEW-BLACK", "quantity": 4},
    ]


def test_dialogue_state_treats_quoted_quote_frame_as_post_quotation_hold() -> None:
    conversation = SimpleNamespace(
        id="conv-quoted-frame",
        customer_name="Lilia",
        metadata_={
            "order_runtime": {
                "quote_frame": {
                    "source": "selection_confirmation",
                    "status": "quoted",
                    "lines": [{"sku": "CH-616", "quantity": 2}],
                }
            }
        },
    )

    state = DialogueState.from_conversation(conversation)

    assert state.active_flow == "post_quotation_hold"
    assert state.slots.quote_sent is True
    assert state.slots.post_quotation_status == "sent"
    assert state.slots.selected_items == []


def test_dialogue_state_falls_back_to_legacy_state_when_kernel_state_missing() -> None:
    metadata = {
        "dialogue_kernel": {"thread_id": "conversation:fixture", "flow": "legacy"},
        "dialogue_state": {
            "version": 1,
            "active_flow": "quotation",
            "slots": {"customer_name": "Mira"},
        },
    }

    state = DialogueState.load(metadata)

    assert state.thread_id == "conversation:fixture"
    assert state.active_flow == "quotation"
    assert state.slots.customer_name == "Mira"


def test_dialogue_state_loads_expected_answer_frames() -> None:
    metadata = {
        "dialogue_kernel": {
            "state": {
                "version": 1,
                "active_flow": "product_selection",
                "expected_answer_frames": [
                    {
                        "frame_id": "product_preference:test",
                        "flow": "product_selection",
                        "question_kind": "product_preference",
                        "prompt_key": "workspace_luma_novo_preference",
                        "status": "active",
                        "priority": 80,
                        "asked_at": "2026-06-02T10:00:00+00:00",
                        "expires_at": "2026-06-02T10:30:00+00:00",
                        "max_customer_turns": 6,
                        "turns_seen": 1,
                        "expected_slots": [
                            {
                                "slot": "workspace_preference",
                                "required": True,
                                "accepted_values": ["open", "private"],
                                "aliases": {"open": ["more open", "for team", "novo"]},
                            }
                        ],
                        "source_refs": [
                            {"kind": "product_family", "value": "SKYLAND NOVO"}
                        ],
                        "filled_slots": {"workspace_preference": "open"},
                        "metadata": {"origin": "legacy_bridge"},
                    }
                ],
            }
        }
    }

    state = DialogueState.load(metadata)

    frame = state.expected_answer_frames[0]
    assert frame.frame_id == "product_preference:test"
    assert frame.flow == "product_selection"
    assert frame.question_kind == "product_preference"
    assert frame.priority == 80
    assert frame.turns_seen == 1
    assert frame.expected_slots[0].slot == "workspace_preference"
    assert frame.expected_slots[0].aliases["open"] == [
        "more open",
        "for team",
        "novo",
    ]
    assert frame.source_refs == [{"kind": "product_family", "value": "SKYLAND NOVO"}]
    assert frame.filled_slots == {"workspace_preference": "open"}
    assert (
        state.to_metadata_patch()["dialogue_kernel"]["state"]["expected_answer_frames"][
            0
        ]["frame_id"]
        == "product_preference:test"
    )


def test_dialogue_state_ignores_invalid_expected_answer_frames_only() -> None:
    metadata = {
        "dialogue_kernel": {
            "thread_id": "conversation:fixture",
            "state": {
                "version": 1,
                "active_flow": "quote_details",
                "slots": {"customer_name": "Mira"},
                "expected_answer_frames": [
                    {"frame_id": "missing-required-fields"},
                    {
                        "frame_id": "quote_details:test",
                        "flow": "quotation_build",
                        "question_kind": "quote_details",
                        "prompt_key": "ask_quote_details",
                        "expected_slots": [{"slot": "delivery_address"}],
                    },
                ],
            },
        }
    }

    state = DialogueState.load(metadata)

    assert state.thread_id == "conversation:fixture"
    assert state.active_flow == "quote_details"
    assert state.slots.customer_name == "Mira"
    assert [frame.frame_id for frame in state.expected_answer_frames] == [
        "quote_details:test"
    ]


def test_dialogue_state_dual_reads_legacy_quote_hold_without_rewriting_it() -> None:
    state = DialogueState.load(
        {
            "sales_memory": {"quotation_hold": "yes"},
            "dialogue_kernel": {
                "state": {
                    "version": 1,
                    "active_flow": "quote_details",
                    "slots": {
                        "customer_name": "Mira",
                        "selected_items": [{"sku": "CH-616", "quantity": 2}],
                    },
                }
            },
        }
    )

    assert state.quote_consent is QuoteConsent.DEFERRED
    assert state.quote_lifecycle is QuoteLifecycle.QUOTE_OFFERED
    patch = state.to_metadata_patch()
    assert patch["dialogue_kernel"]["state"]["version"] == 2
    assert patch["dialogue_kernel"]["state"]["quote_consent"] == "deferred"
    assert "quote_on_hold" not in str(patch)


def test_dialogue_state_canonical_quote_workflow_wins_over_stale_kernel_state() -> None:
    state = DialogueState.load(
        {
            "order_runtime": {
                "quote_workflow": {
                    "version": 2,
                    "consent": "declined",
                    "lifecycle": "consultation",
                }
            },
            "dialogue_kernel": {
                "state": {
                    "version": 2,
                    "quote_consent": "granted",
                    "quote_lifecycle": "collecting_details",
                }
            },
        }
    )

    assert state.quote_consent is QuoteConsent.DECLINED
    assert state.quote_lifecycle is QuoteLifecycle.CONSULTATION
