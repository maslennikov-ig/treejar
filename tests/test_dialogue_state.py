from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from src.dialogue.reducer import (
    append_trace_bounded,
    apply_extracted_details,
    build_trace,
    expire_expected_answer_frames,
    mark_frame_fulfilled,
    mark_frame_interrupted,
    mark_quote_sent,
    push_expected_answer_frame,
    set_last_question,
)
from src.dialogue.state import (
    DialogueDecision,
    DialogueSlots,
    DialogueState,
    ExpectedAnswerFrame,
    ExpectedSlot,
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


def test_expected_answer_frame_reducers_manage_lifecycle() -> None:
    original = DialogueState(active_flow="intake")
    frame = ExpectedAnswerFrame(
        frame_id="product_preference:test",
        flow="product_selection",
        question_kind="product_preference",
        prompt_key="workspace_luma_novo_preference",
        priority=80,
        max_customer_turns=1,
        expected_slots=[
            ExpectedSlot(
                slot="workspace_preference",
                accepted_values=["open", "private"],
                aliases={"open": ["more open"]},
            )
        ],
    )

    pushed = push_expected_answer_frame(original, frame)
    fulfilled = mark_frame_fulfilled(
        pushed,
        "product_preference:test",
        filled_slots={"workspace_preference": "open"},
    )
    interrupted = mark_frame_interrupted(pushed, "product_preference:test")
    expired = expire_expected_answer_frames(pushed)
    expired = expire_expected_answer_frames(expired)

    assert original.expected_answer_frames == []
    assert pushed.active_flow == "product_selection"
    assert pushed.expected_answer_frames[0].status == "active"
    assert fulfilled.expected_answer_frames[0].status == "fulfilled"
    assert fulfilled.expected_answer_frames[0].filled_slots == {
        "workspace_preference": "open"
    }
    assert interrupted.expected_answer_frames[0].status == "interrupted"
    assert expired.expected_answer_frames[0].status == "expired"
    assert expired.expected_answer_frames[0].turns_seen == 2


def test_expected_answer_frame_push_replaces_duplicates_and_bounds_frames() -> None:
    state = DialogueState()

    for index in range(10):
        state = push_expected_answer_frame(
            state,
            ExpectedAnswerFrame(
                frame_id=f"active:{index}",
                flow="product_selection",
                question_kind="product_preference",
                prompt_key="workspace_luma_novo_preference",
                priority=index,
                expected_slots=[ExpectedSlot(slot="workspace_preference")],
            ),
        )
    state = push_expected_answer_frame(
        state,
        ExpectedAnswerFrame(
            frame_id="active:9",
            flow="product_selection",
            question_kind="product_preference",
            prompt_key="workspace_luma_novo_preference",
            priority=100,
            expected_slots=[ExpectedSlot(slot="workspace_preference")],
            metadata={"retried": True},
        ),
    )
    for index in range(22):
        state = push_expected_answer_frame(
            state,
            ExpectedAnswerFrame(
                frame_id=f"history:{index}",
                flow="quote_details",
                question_kind="quote_details",
                prompt_key="ask_quote_details",
                status="fulfilled",
                expected_slots=[ExpectedSlot(slot="delivery_address")],
            ),
        )

    active_frames = [
        frame for frame in state.expected_answer_frames if frame.status == "active"
    ]
    history_frames = [
        frame for frame in state.expected_answer_frames if frame.status != "active"
    ]

    assert len(active_frames) == 8
    assert active_frames[0].frame_id == "active:9"
    assert active_frames[0].metadata == {"retried": True}
    assert len({frame.frame_id for frame in active_frames}) == 8
    assert len(history_frames) == 20
    assert history_frames[0].frame_id == "history:2"
    assert history_frames[-1].frame_id == "history:21"


def test_reducer_functions_return_new_state_without_mutating_original() -> None:
    original = DialogueState(active_flow="intake")
    updated = apply_extracted_details(
        original,
        {
            "customer_name": "Aisha",
            "company": "Treejar",
            "selected_items": [{"sku": "CP-2.1S", "quantity": 1}],
            "pending_product_refs": ["CH 616"],
        },
    )
    asked = set_last_question(
        updated,
        flow="quotation",
        prompt_key="ask_address",
        expected_slots=["delivery_address"],
        asked_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )
    quoted = mark_quote_sent(asked, post_quotation_status="sent")

    assert original.slots.customer_name is None
    assert original.slots.selected_items == []
    assert updated is not original
    assert updated.slots.customer_name == "Aisha"
    assert updated.slots.pending_product_refs == ["CH 616"]
    assert asked.last_question is not None
    assert asked.last_question.asked_at == datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    assert quoted.slots.quote_sent is True
    assert quoted.slots.post_quotation_status == "sent"


def test_build_trace_computes_slot_diff_and_serializes_bounded_payload() -> None:
    before = DialogueState(active_flow="intake")
    after = apply_extracted_details(
        before,
        {
            "customer_name": "Omar",
            "delivery_address": "Business Bay",
        },
    )
    decision = DialogueDecision(
        action="ask_next",
        flow="quotation",
        response_text="Please share the company name.",
        handled=True,
        side_effects_allowed=False,
        metadata={"large": "x" * 500},
    )

    trace = build_trace(
        mode="shadow",
        legacy_route="legacy_quotation",
        kernel_route="quotation",
        decision=decision,
        before_state=before,
        after_state=after,
        mismatch_reason="route_diff",
    )
    serialized = trace.to_bounded_dict(max_text_length=40)

    assert trace.slot_diff == {
        "customer_name": {"before": None, "after": "Omar"},
        "delivery_address": {"before": None, "after": "Business Bay"},
    }
    assert serialized["decision"]["metadata"]["large"].endswith("...")
    assert len(serialized["decision"]["metadata"]["large"]) == 40
    assert serialized["mismatch_reason"] == "route_diff"


def test_append_trace_bounded_keeps_newest_entries() -> None:
    state = DialogueState()

    for index in range(5):
        decision = DialogueDecision(action=f"a{index}", flow="quotation")
        trace = build_trace(
            mode="shadow",
            decision=decision,
            before_state=state,
            after_state=state,
        )
        state = append_trace_bounded(state, trace, limit=3)

    assert [item.decision.action for item in state.trace_history] == ["a2", "a3", "a4"]


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


def test_reconcile_dialogue_state_removes_impossible_slot_combinations() -> None:
    from src.dialogue.reducer import reconcile_dialogue_state

    state = DialogueState(
        active_flow="quote_details",
        quote_consent=QuoteConsent.NOT_REQUESTED,
        quote_lifecycle=QuoteLifecycle.COLLECTING_DETAILS,
        slots={
            "customer_name": "Lina",
            "company": "Northstar LLC",
            "customer_type": "individual",
            "delivery_address": "000 total budget",
            "selected_items": [{"sku": "CH-616", "quantity": 4}],
        },
    )

    reconciled = reconcile_dialogue_state(state)

    assert reconciled.slots.company == "Northstar LLC"
    assert reconciled.slots.customer_type is None
    assert reconciled.slots.delivery_address is None
    assert reconciled.quote_lifecycle is QuoteLifecycle.QUOTE_OFFERED
    assert reconciled.active_flow == "product_selection"
    assert reconciled.sales_stage == "solution"


def test_a_quantity_already_recorded_is_not_asked_for_again() -> None:
    """`tj-o29r`: the parser binds a quantity only in the `10 x SKU` shape, so
    "10 chairs. CH 616 NEW black" reached the runner without one and the
    conversation asked for a number it had been given. The slot now answers."""

    from src.dialogue.runner import _quantity_key

    # The three forms the runtime uses for one SKU must compare equal.
    assert _quantity_key("CH-616") == _quantity_key("CH 616") == _quantity_key("ch616")
    assert _quantity_key("CH-616") != _quantity_key("CH-620")
    assert _quantity_key(None) == ""
