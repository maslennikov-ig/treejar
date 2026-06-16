from __future__ import annotations

# Runtime helper bindings are loaded lazily from src.llm.engine after engine import
# completes. Direct imports here would recreate the old import-time cycle.
# ruff: noqa: TC004
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from importlib import import_module
from typing import TYPE_CHECKING, Any, Literal

from pydantic_ai import RunContext

from src.core.config import settings
from src.llm.order_handoff import is_high_confidence_first_turn_order
from src.llm.safety import PATH_CORE_CHAT, model_name_for_path
from src.llm.verified_answers import is_quote_or_proposal_request

if TYPE_CHECKING:
    from pydantic_ai.models.openai import OpenAIChatModel
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
    from src.llm.engine import (
        EXACT_QUOTE_PASS_2_DIRECTIVES,
        ORDER_HANDOFF_PASS_1_DIRECTIVES,
        ORDER_HANDOFF_PASS_2_DIRECTIVES,
        ORDER_RUNTIME_METADATA_KEY,
        ExactQuoteCandidate,
        LLMResponse,
        PendingReferenceRoute,
        SalesDeps,
        _accepts_exact_item_quote_followup,
        _active_pending_quote_selection_from_conversation,
        _active_quote_has_unresolved_items,
        _active_quote_items,
        _clear_pending_quote_selection,
        _clear_quote_intent_frame,
        _exact_quote_candidate_from_frame,
        _exact_quote_unresolved_candidates_from_metadata,
        _exact_quote_unresolved_items_message,
        _extract_missing_quantity_product_references,
        _extract_purchase_selection_for_context,
        _extract_purchase_selection_from_quote_details_reply,
        _extract_sales_order_quote_items,
        _first_selection_over_texts,
        _has_affirmative_quote_resume_intent,
        _is_pending_sales_order_quote,
        _last_assistant_asked_quote_customer_details,
        _last_assistant_offered_single_stock_price_quote_option,
        _missing_quantity_order_runtime_result,
        _missing_quantity_product_references_message,
        _missing_quantity_references_from_order_runtime_result,
        _pending_question_frame_from_references,
        _pending_quote_has_unresolved_items,
        _pending_quote_items_from_metadata,
        _pending_quote_missing_items_message,
        _quote_brief_confirmation_message,
        _quote_frame_repair_required_message,
        _quote_missing_required_details,
        _quote_missing_required_details_message,
        _resolve_exact_quote_candidate_sku,
        _resolve_purchase_selection_confirmation,
        _sales_order_followup_candidates,
        _sales_order_unresolved_candidates_from_metadata,
        _sales_order_unresolved_items_message,
        _should_resume_pending_quote_selection,
        _store_extracted_quote_customer_details,
        _store_pending_exact_quote,
        _store_pending_question_frame,
        _store_pending_quote_brief_confirmation,
        _store_pending_quote_from_last_assistant_selection,
        _store_pending_sales_order_quote,
        create_quotation,
        extract_exact_quote_candidate,
    )
    from src.models.conversation import Conversation

_ENGINE_BIND_NAMES = (
    "EXACT_QUOTE_PASS_2_DIRECTIVES",
    "ORDER_HANDOFF_PASS_1_DIRECTIVES",
    "ORDER_HANDOFF_PASS_2_DIRECTIVES",
    "ORDER_RUNTIME_METADATA_KEY",
    "_accepts_exact_item_quote_followup",
    "_active_pending_quote_selection_from_conversation",
    "_active_quote_has_unresolved_items",
    "_active_quote_items",
    "_clear_pending_quote_selection",
    "_clear_quote_intent_frame",
    "_exact_quote_candidate_from_frame",
    "_exact_quote_unresolved_candidates_from_metadata",
    "_exact_quote_unresolved_items_message",
    "_extract_missing_quantity_product_references",
    "_extract_purchase_selection_for_context",
    "_extract_purchase_selection_from_quote_details_reply",
    "_extract_sales_order_quote_items",
    "_first_selection_over_texts",
    "_has_affirmative_quote_resume_intent",
    "_is_pending_sales_order_quote",
    "_last_assistant_asked_quote_customer_details",
    "_last_assistant_offered_single_stock_price_quote_option",
    "_missing_quantity_order_runtime_result",
    "_missing_quantity_product_references_message",
    "_missing_quantity_references_from_order_runtime_result",
    "_pending_question_frame_from_references",
    "_pending_quote_has_unresolved_items",
    "_pending_quote_items_from_metadata",
    "_pending_quote_missing_items_message",
    "_quote_brief_confirmation_message",
    "_quote_frame_repair_required_message",
    "_quote_missing_required_details",
    "_quote_missing_required_details_message",
    "_resolve_exact_quote_candidate_sku",
    "_resolve_purchase_selection_confirmation",
    "_sales_order_followup_candidates",
    "_sales_order_unresolved_candidates_from_metadata",
    "_sales_order_unresolved_items_message",
    "_should_resume_pending_quote_selection",
    "_store_extracted_quote_customer_details",
    "_store_pending_exact_quote",
    "_store_pending_question_frame",
    "_store_pending_quote_brief_confirmation",
    "_store_pending_quote_from_last_assistant_selection",
    "_store_pending_sales_order_quote",
    "create_quotation",
    "extract_exact_quote_candidate",
)


def _bind_engine_globals() -> None:
    engine = import_module("src.llm.engine")
    for name in _ENGINE_BIND_NAMES:
        globals()[name] = getattr(engine, name)


@dataclass
class QuotationItem:
    sku: str
    quantity: int


@dataclass(frozen=True)
class OrderQuoteSideEffectPlan:
    items: list[QuotationItem]
    response_deps: SalesDeps
    prompt: str
    model_suffix: str
    build_response: Callable[..., LLMResponse]
    clear_verified_policy_repair_state: Callable[[], Any]
    clear_pending_quote_selection_on_created: bool = True
    clear_quote_intent_frame_on_created: bool = False


async def _execute_order_quote_side_effect(
    *,
    db: AsyncSession,
    conversation: Conversation,
    dynamic_model: OpenAIChatModel,
    db_model_main: str,
    plan: OrderQuoteSideEffectPlan,
) -> LLMResponse:
    _bind_engine_globals()

    from pydantic_ai.usage import RunUsage

    quote_ctx = RunContext(
        deps=plan.response_deps,
        retry=0,
        messages=[],
        prompt=plan.prompt,
        model=dynamic_model,
        usage=RunUsage(),
    )
    try:
        quote_text = await create_quotation(quote_ctx, plan.items)
    except Exception as exc:
        _append_quote_effect_trace(
            conversation,
            model_suffix=plan.model_suffix,
            item_count=len(plan.items),
            status="error",
            error_type=type(exc).__name__,
        )
        raise
    _append_quote_effect_trace(
        conversation,
        model_suffix=plan.model_suffix,
        item_count=len(plan.items),
        status="created" if plan.response_deps.quotation_created else "blocked",
    )
    if plan.response_deps.quotation_created:
        if plan.clear_pending_quote_selection_on_created:
            await _clear_pending_quote_selection(db, conversation)
        if plan.clear_quote_intent_frame_on_created:
            await _clear_quote_intent_frame(db, conversation)
    await plan.clear_verified_policy_repair_state()
    return plan.build_response(
        quote_text,
        f"{db_model_main}|{plan.model_suffix}",
        response_deps=plan.response_deps,
        allow_product_media=False,
    )


def _append_quote_effect_trace(
    conversation: Conversation,
    *,
    model_suffix: str,
    item_count: int,
    status: Literal["created", "blocked", "error"],
    error_type: str | None = None,
) -> None:
    _bind_engine_globals()

    metadata = dict(conversation.metadata_ or {})
    runtime = metadata.get(ORDER_RUNTIME_METADATA_KEY)
    runtime_metadata = dict(runtime) if isinstance(runtime, Mapping) else {}
    raw_traces = runtime_metadata.get("quote_effect_traces")
    traces = list(raw_traces) if isinstance(raw_traces, list) else []
    trace: dict[str, Any] = {
        "source": "adapter",
        "model_suffix": model_suffix,
        "item_count": max(int(item_count), 0),
        "status": status,
    }
    if error_type:
        trace["error_type"] = error_type[:80]
    traces.append(trace)
    runtime_metadata["quote_effect_traces"] = traces[-5:]
    metadata[ORDER_RUNTIME_METADATA_KEY] = runtime_metadata
    conversation.metadata_ = metadata


async def _order_quote_route_for_turn(
    *,
    phase: Literal["pre_policy", "post_policy"],
    db: AsyncSession,
    conversation: Conversation,
    deps: SalesDeps,
    masked_text: str,
    combined_text: str,
    is_first_turn: bool,
    pending_quote_selection_at_start: Mapping[str, Any] | None,
    pending_exact_quote_followup_candidates: tuple[ExactQuoteCandidate, ...],
    current_quote_intent_frame: Mapping[str, Any] | None,
    current_quote_customer_details: dict[str, str],
    assistant_supports_quote_resume: bool,
    quote_detail_context_active: bool,
    has_pending_quote_selection: bool,
    pending_reference_route: PendingReferenceRoute,
    zoho_client: ZohoInventoryClient,
    crm_context: dict[str, Any] | None,
    trace_enabled: bool,
    build_static_response: Callable[..., LLMResponse],
    clear_verified_policy_repair_state: Callable[[], Awaitable[None]],
    db_model_main: str | None = None,
    dynamic_model: OpenAIChatModel | None = None,
    run_agent: Callable[[SalesDeps], Awaitable[Any]] | None = None,
    build_llm_response: Callable[..., LLMResponse] | None = None,
    has_escalation: Callable[[Conversation], bool] | None = None,
    quote_brief_confirmation_details: Mapping[str, str] | None = None,
) -> LLMResponse | None:
    _bind_engine_globals()

    pending_reference_selection = pending_reference_route.selection

    if phase == "pre_policy":
        early_purchase_selection = None
        if (
            not quote_detail_context_active
            and pending_quote_selection_at_start is None
            and not pending_exact_quote_followup_candidates
            and current_quote_intent_frame is None
            and not is_quote_or_proposal_request(masked_text)
            and not is_quote_or_proposal_request(combined_text)
        ):
            early_purchase_selection = (
                pending_reference_selection
                or _first_selection_over_texts(
                    lambda text: _extract_purchase_selection_for_context(
                        text,
                        deps.recent_history,
                    ),
                    masked_text,
                    combined_text,
                )
            )
        if early_purchase_selection is None:
            return None

        from src.core.config import get_system_config

        route_model = await get_system_config(
            db, "openrouter_model_main", settings.openrouter_model_main
        )
        route_model = model_name_for_path(PATH_CORE_CHAT, route_model)
        await clear_verified_policy_repair_state()
        (
            selection_deps,
            confirmation_text,
        ) = await _resolve_purchase_selection_confirmation(
            db=db,
            conversation=conversation,
            deps=deps,
            purchase_selection=early_purchase_selection,
            zoho_client=zoho_client,
            crm_context=crm_context,
            trace_enabled=trace_enabled,
            clear_pending_reference_quantity=(
                pending_reference_route.clear_pending_reference_quantity
            ),
            clear_pending_question_frame=(
                pending_reference_route.clear_pending_question_frame
            ),
        )
        return build_static_response(
            confirmation_text,
            f"{route_model}|selection-confirmation",
            response_deps=selection_deps,
            allow_product_media=False,
        )

    assert db_model_main is not None
    assert dynamic_model is not None
    assert run_agent is not None
    assert build_llm_response is not None
    assert has_escalation is not None

    if quote_brief_confirmation_details is not None:
        await _store_pending_quote_brief_confirmation(
            db,
            conversation,
            quote_brief_confirmation_details,
        )
        await clear_verified_policy_repair_state()
        return build_static_response(
            _quote_brief_confirmation_message(quote_brief_confirmation_details),
            f"{db_model_main}|quote-brief-confirm",
            allow_product_media=False,
        )

    sales_order_items = _extract_sales_order_quote_items(masked_text)
    if sales_order_items is None:
        sales_order_items = _extract_sales_order_quote_items(combined_text)
    if sales_order_items is not None:
        resolved_quote_items: list[QuotationItem] = []
        unresolved_items: list[ExactQuoteCandidate] = []
        for item in sales_order_items:
            resolved_sku = await _resolve_exact_quote_candidate_sku(deps.db, item)
            if resolved_sku:
                resolved_quote_items.append(
                    QuotationItem(sku=resolved_sku, quantity=item.quantity)
                )
            else:
                unresolved_items.append(item)

        if unresolved_items or not resolved_quote_items:
            await _store_pending_sales_order_quote(
                db,
                conversation,
                resolved_items=resolved_quote_items,
                unresolved_items=tuple(unresolved_items),
            )
            await clear_verified_policy_repair_state()
            return build_static_response(
                _sales_order_unresolved_items_message(tuple(unresolved_items)),
                f"{db_model_main}|sales-order-clarify",
                allow_product_media=False,
            )

        sales_order_deps = replace(
            deps,
            tool_mode="exact_quote",
            runtime_directives=EXACT_QUOTE_PASS_2_DIRECTIVES,
        )
        await _store_pending_sales_order_quote(
            db,
            conversation,
            resolved_items=resolved_quote_items,
            unresolved_items=(),
        )
        return await _execute_order_quote_side_effect(
            db=db,
            conversation=conversation,
            dynamic_model=dynamic_model,
            db_model_main=db_model_main,
            plan=OrderQuoteSideEffectPlan(
                items=resolved_quote_items,
                response_deps=sales_order_deps,
                prompt=masked_text,
                model_suffix="sales-order-quote",
                build_response=build_static_response,
                clear_verified_policy_repair_state=(clear_verified_policy_repair_state),
            ),
        )

    pending_sales_order_quote = _active_pending_quote_selection_from_conversation(
        conversation
    )
    if (
        pending_sales_order_quote is not None
        and _is_pending_sales_order_quote(pending_sales_order_quote)
        and _pending_quote_has_unresolved_items(pending_sales_order_quote)
    ):
        followup_candidates = _sales_order_followup_candidates(
            selection=pending_sales_order_quote,
            combined_text=combined_text,
            masked_text=masked_text,
        )
        if not followup_candidates:
            await clear_verified_policy_repair_state()
            return build_static_response(
                _sales_order_unresolved_items_message(
                    _sales_order_unresolved_candidates_from_metadata(
                        pending_sales_order_quote
                    )
                ),
                f"{db_model_main}|sales-order-clarify",
                allow_product_media=False,
            )

        existing_quote_items = list(
            _pending_quote_items_from_metadata(pending_sales_order_quote)
        )
        resolved_followup_items: list[QuotationItem] = []
        still_unresolved_items: list[ExactQuoteCandidate] = []
        for item in followup_candidates:
            resolved_sku = await _resolve_exact_quote_candidate_sku(deps.db, item)
            if resolved_sku:
                resolved_followup_items.append(
                    QuotationItem(sku=resolved_sku, quantity=item.quantity)
                )
            else:
                still_unresolved_items.append(item)

        if still_unresolved_items or not resolved_followup_items:
            await _store_pending_sales_order_quote(
                db,
                conversation,
                resolved_items=[*existing_quote_items, *resolved_followup_items],
                unresolved_items=tuple(still_unresolved_items)
                or _sales_order_unresolved_candidates_from_metadata(
                    pending_sales_order_quote
                ),
            )
            await clear_verified_policy_repair_state()
            return build_static_response(
                _sales_order_unresolved_items_message(
                    tuple(still_unresolved_items)
                    or _sales_order_unresolved_candidates_from_metadata(
                        pending_sales_order_quote
                    )
                ),
                f"{db_model_main}|sales-order-clarify",
                allow_product_media=False,
            )

        sales_order_resume_deps = replace(
            deps,
            tool_mode="exact_quote",
            runtime_directives=EXACT_QUOTE_PASS_2_DIRECTIVES,
        )
        resolved_sales_order_items = [
            *existing_quote_items,
            *resolved_followup_items,
        ]
        await _store_pending_sales_order_quote(
            db,
            conversation,
            resolved_items=resolved_sales_order_items,
            unresolved_items=(),
        )
        return await _execute_order_quote_side_effect(
            db=db,
            conversation=conversation,
            dynamic_model=dynamic_model,
            db_model_main=db_model_main,
            plan=OrderQuoteSideEffectPlan(
                items=resolved_sales_order_items,
                response_deps=sales_order_resume_deps,
                prompt=masked_text,
                model_suffix="sales-order-quote-resume",
                build_response=build_static_response,
                clear_verified_policy_repair_state=(clear_verified_policy_repair_state),
            ),
        )

    if is_first_turn and is_high_confidence_first_turn_order(masked_text):
        first_result = await run_agent(
            replace(
                deps,
                tool_mode="order_handoff",
                runtime_directives=ORDER_HANDOFF_PASS_1_DIRECTIVES,
            )
        )
        if has_escalation(conversation):
            await clear_verified_policy_repair_state()
            return build_llm_response(first_result, db_model_main)

        second_result = await run_agent(
            replace(
                deps,
                tool_mode="order_handoff",
                runtime_directives=ORDER_HANDOFF_PASS_2_DIRECTIVES,
            )
        )
        await clear_verified_policy_repair_state()
        return build_llm_response(second_result, db_model_main)

    quote_multi_item_selection = None
    if pending_quote_selection_at_start is None and (
        is_quote_or_proposal_request(masked_text)
        or is_quote_or_proposal_request(combined_text)
    ):
        for candidate_text in (masked_text, combined_text):
            candidate_selection = _extract_purchase_selection_for_context(
                candidate_text,
                deps.recent_history,
            )
            if candidate_selection is not None and len(candidate_selection.items) > 1:
                quote_multi_item_selection = candidate_selection
                break
    if quote_multi_item_selection is not None:
        (
            selection_deps,
            confirmation_text,
        ) = await _resolve_purchase_selection_confirmation(
            db=db,
            conversation=conversation,
            deps=deps,
            purchase_selection=quote_multi_item_selection,
            zoho_client=zoho_client,
            crm_context=crm_context,
            trace_enabled=trace_enabled,
        )
        await _clear_quote_intent_frame(db, conversation)
        await clear_verified_policy_repair_state()
        return build_static_response(
            confirmation_text,
            f"{db_model_main}|selection-confirmation",
            response_deps=selection_deps,
            allow_product_media=False,
        )

    exact_quote_candidate = _exact_quote_candidate_from_frame(
        current_quote_intent_frame
    )
    if exact_quote_candidate is None:
        exact_quote_candidate = extract_exact_quote_candidate(masked_text)
    if exact_quote_candidate is None:
        exact_quote_candidate = extract_exact_quote_candidate(combined_text)
    if exact_quote_candidate:
        exact_quote_deps = replace(
            deps,
            tool_mode="exact_quote",
            runtime_directives=EXACT_QUOTE_PASS_2_DIRECTIVES,
        )
        resolved_exact_sku = await _resolve_exact_quote_candidate_sku(
            deps.db, exact_quote_candidate
        )
        if not resolved_exact_sku:
            unresolved_exact_items = (exact_quote_candidate,)
            await _store_pending_exact_quote(
                db,
                conversation,
                [],
                unresolved_items=unresolved_exact_items,
            )
            await _clear_quote_intent_frame(db, conversation)
            await clear_verified_policy_repair_state()
            return build_static_response(
                _exact_quote_unresolved_items_message(unresolved_exact_items),
                f"{db_model_main}|exact-quote-clarify-item",
                response_deps=exact_quote_deps,
                allow_product_media=False,
            )

        exact_quote_items = [
            QuotationItem(
                sku=resolved_exact_sku,
                quantity=exact_quote_candidate.quantity,
            )
        ]
        missing_required = _quote_missing_required_details(
            exact_quote_deps,
            exact_quote_items,
        )
        if missing_required:
            await _store_pending_exact_quote(db, conversation, exact_quote_items)
            await _clear_quote_intent_frame(db, conversation)
            await clear_verified_policy_repair_state()
            return build_static_response(
                _quote_missing_required_details_message(
                    missing_required,
                    language=str(conversation.language),
                ),
                f"{db_model_main}|exact-quote-missing-details",
                response_deps=exact_quote_deps,
                allow_product_media=False,
            )

        return await _execute_order_quote_side_effect(
            db=db,
            conversation=conversation,
            dynamic_model=dynamic_model,
            db_model_main=db_model_main,
            plan=OrderQuoteSideEffectPlan(
                items=exact_quote_items,
                response_deps=exact_quote_deps,
                prompt=masked_text,
                model_suffix="exact-quote-deterministic",
                build_response=build_static_response,
                clear_verified_policy_repair_state=(clear_verified_policy_repair_state),
                clear_quote_intent_frame_on_created=True,
            ),
        )

    quote_details_purchase_selection = None
    if assistant_supports_quote_resume:
        quote_details_purchase_selection = (
            _extract_purchase_selection_from_quote_details_reply(combined_text)
            or _extract_purchase_selection_from_quote_details_reply(masked_text)
        )

    purchase_selection = None
    suppress_purchase_selection_for_quote_details = (
        bool(current_quote_customer_details)
        and assistant_supports_quote_resume
        and quote_details_purchase_selection is None
    )
    if not suppress_purchase_selection_for_quote_details:
        purchase_selection = pending_reference_selection
        if purchase_selection is None:
            purchase_selection = quote_details_purchase_selection
        if purchase_selection is None:
            purchase_selection = _extract_purchase_selection_for_context(
                masked_text,
                deps.recent_history,
            )
        if purchase_selection is None:
            purchase_selection = _extract_purchase_selection_for_context(
                combined_text,
                deps.recent_history,
            )
    if purchase_selection is not None:
        await clear_verified_policy_repair_state()
        (
            selection_deps,
            confirmation_text,
        ) = await _resolve_purchase_selection_confirmation(
            db=db,
            conversation=conversation,
            deps=deps,
            purchase_selection=purchase_selection,
            zoho_client=zoho_client,
            crm_context=crm_context,
            trace_enabled=trace_enabled,
            clear_pending_reference_quantity=(
                pending_reference_route.clear_pending_reference_quantity
            ),
            clear_pending_question_frame=(
                pending_reference_route.clear_pending_question_frame
            ),
        )
        return build_static_response(
            confirmation_text,
            f"{db_model_main}|selection-confirmation",
            response_deps=selection_deps,
            allow_product_media=False,
        )

    missing_quantity_runtime_result = None
    missing_quantity_references: tuple[str, ...] = ()
    if not has_pending_quote_selection:
        missing_quantity_runtime_result = _missing_quantity_order_runtime_result(
            masked_text
        )
        if missing_quantity_runtime_result is None and masked_text != combined_text:
            missing_quantity_runtime_result = _missing_quantity_order_runtime_result(
                combined_text
            )
        if missing_quantity_runtime_result is not None:
            missing_quantity_references = (
                _missing_quantity_references_from_order_runtime_result(
                    missing_quantity_runtime_result
                )
            )
        else:
            missing_quantity_references = _extract_missing_quantity_product_references(
                masked_text
            )
            if not missing_quantity_references:
                missing_quantity_references = (
                    _extract_missing_quantity_product_references(combined_text)
                )
    if missing_quantity_references:
        if (
            missing_quantity_runtime_result is not None
            and missing_quantity_runtime_result.state.pending_question_frame is not None
        ):
            await _store_pending_question_frame(
                db,
                conversation,
                missing_quantity_runtime_result.state.pending_question_frame,
            )
        else:
            fallback_frame = _pending_question_frame_from_references(
                missing_quantity_references
            )
            if fallback_frame is not None:
                await _store_pending_question_frame(db, conversation, fallback_frame)
        await clear_verified_policy_repair_state()
        return build_static_response(
            _missing_quantity_product_references_message(
                missing_quantity_references,
                str(conversation.language),
            ),
            f"{db_model_main}|product-quantity-clarify",
            allow_product_media=False,
        )

    pending_quote_selection = _active_pending_quote_selection_from_conversation(
        conversation
    )
    if (
        pending_quote_selection is None
        and _last_assistant_offered_single_stock_price_quote_option(deps.recent_history)
        and (
            _has_affirmative_quote_resume_intent(combined_text)
            or _has_affirmative_quote_resume_intent(masked_text)
        )
    ):
        pending_quote_selection = (
            await _store_pending_quote_from_last_assistant_selection(
                db,
                conversation,
                deps.recent_history,
                require_single=True,
            )
        )

    if pending_quote_selection is not None:
        pending_quote_customer_details = current_quote_customer_details
        if pending_quote_customer_details:
            await _store_extracted_quote_customer_details(
                db,
                conversation,
                pending_quote_customer_details,
            )
        if (
            pending_exact_quote_followup_candidates
            and _accepts_exact_item_quote_followup(pending_quote_selection)
            and _active_quote_has_unresolved_items(
                conversation,
                pending_quote_selection,
            )
        ):
            existing_quote_items = list(
                _active_quote_items(conversation, pending_quote_selection)
            )
            resolved_exact_followup_items: list[QuotationItem] = []
            still_unresolved_exact_items: list[ExactQuoteCandidate] = []
            for item in pending_exact_quote_followup_candidates:
                resolved_sku = await _resolve_exact_quote_candidate_sku(
                    deps.db,
                    item,
                )
                if resolved_sku:
                    resolved_exact_followup_items.append(
                        QuotationItem(sku=resolved_sku, quantity=item.quantity)
                    )
                else:
                    still_unresolved_exact_items.append(item)

            if still_unresolved_exact_items or not resolved_exact_followup_items:
                exact_followup_unresolved_to_store: tuple[ExactQuoteCandidate, ...]
                if still_unresolved_exact_items:
                    exact_followup_unresolved_to_store = tuple(
                        still_unresolved_exact_items
                    )
                else:
                    exact_followup_unresolved_to_store = (
                        _exact_quote_unresolved_candidates_from_metadata(
                            pending_quote_selection
                        )
                    )
                await _store_pending_exact_quote(
                    db,
                    conversation,
                    [*existing_quote_items, *resolved_exact_followup_items],
                    unresolved_items=exact_followup_unresolved_to_store,
                )
                await clear_verified_policy_repair_state()
                return build_static_response(
                    _exact_quote_unresolved_items_message(
                        exact_followup_unresolved_to_store
                    ),
                    f"{db_model_main}|exact-quote-clarify-item",
                    allow_product_media=False,
                )

            resolved_exact_quote_items = [
                *existing_quote_items,
                *resolved_exact_followup_items,
            ]
            await _store_pending_exact_quote(
                db, conversation, resolved_exact_quote_items
            )

            missing_required = _quote_missing_required_details(
                deps,
                resolved_exact_quote_items,
            )
            if missing_required:
                await clear_verified_policy_repair_state()
                return build_static_response(
                    _quote_missing_required_details_message(
                        missing_required,
                        language=str(conversation.language),
                    ),
                    f"{db_model_main}|quote-resume-missing-details",
                    allow_product_media=False,
                )

            quote_resume_deps = replace(
                deps,
                tool_mode="exact_quote",
                runtime_directives=EXACT_QUOTE_PASS_2_DIRECTIVES,
            )
            return await _execute_order_quote_side_effect(
                db=db,
                conversation=conversation,
                dynamic_model=dynamic_model,
                db_model_main=db_model_main,
                plan=OrderQuoteSideEffectPlan(
                    items=resolved_exact_quote_items,
                    response_deps=quote_resume_deps,
                    prompt=masked_text,
                    model_suffix="quote-resume",
                    build_response=build_static_response,
                    clear_verified_policy_repair_state=(
                        clear_verified_policy_repair_state
                    ),
                ),
            )
        if _should_resume_pending_quote_selection(
            combined_text=combined_text,
            masked_text=masked_text,
            customer_details=pending_quote_customer_details,
        ):
            quote_items = _active_quote_items(conversation, pending_quote_selection)
            if not quote_items or _active_quote_has_unresolved_items(
                conversation,
                pending_quote_selection,
            ):
                await clear_verified_policy_repair_state()
                return build_static_response(
                    _pending_quote_missing_items_message(str(conversation.language)),
                    f"{db_model_main}|quote-resume-missing-items",
                )

            missing_required = _quote_missing_required_details(
                deps,
                list(quote_items),
            )
            if missing_required:
                await clear_verified_policy_repair_state()
                return build_static_response(
                    _quote_missing_required_details_message(
                        missing_required,
                        language=str(conversation.language),
                    ),
                    f"{db_model_main}|quote-resume-missing-details",
                    allow_product_media=False,
                )

            quote_resume_deps = replace(
                deps,
                tool_mode="exact_quote",
                runtime_directives=EXACT_QUOTE_PASS_2_DIRECTIVES,
            )
            return await _execute_order_quote_side_effect(
                db=db,
                conversation=conversation,
                dynamic_model=dynamic_model,
                db_model_main=db_model_main,
                plan=OrderQuoteSideEffectPlan(
                    items=list(quote_items),
                    response_deps=quote_resume_deps,
                    prompt=masked_text,
                    model_suffix="quote-resume",
                    build_response=build_static_response,
                    clear_verified_policy_repair_state=(
                        clear_verified_policy_repair_state
                    ),
                ),
            )
        if _last_assistant_asked_quote_customer_details(deps.recent_history):
            quote_items = _active_quote_items(conversation, pending_quote_selection)
            missing_required = _quote_missing_required_details(
                deps,
                list(quote_items),
            )
            if missing_required:
                await clear_verified_policy_repair_state()
                return build_static_response(
                    _quote_missing_required_details_message(
                        missing_required,
                        language=str(conversation.language),
                    ),
                    f"{db_model_main}|quote-resume-missing-details",
                    allow_product_media=False,
                )
    elif current_quote_customer_details and assistant_supports_quote_resume:
        await clear_verified_policy_repair_state()
        return build_static_response(
            _quote_frame_repair_required_message(str(conversation.language)),
            f"{db_model_main}|quote-frame-repair-missing-items",
            allow_product_media=False,
        )

    return None
