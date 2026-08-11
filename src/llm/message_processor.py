"""Runtime implementation behind :func:`src.llm.engine.process_message`.

The split that created this module took the engine in as a parameter --
``runtime: Any`` -- and read 160 names off it at the top of the call. That kept
the ``src.llm.engine.*`` patch points the suite has always used, and it cost
every type in the file: each of those names was ``Any``, so Mypy checked nothing
across two thousand lines of the hottest path in the product. A call to
``_catalog_planning_for_turn`` with four positional arguments and an invented
keyword passed clean.

Importing the module gets both. ``engine.foo`` is still resolved at the moment
of use, so patching ``src.llm.engine.foo`` still lands, and Mypy knows what
``engine.foo`` is. Most collaborators do not need even that and are imported
from the module that defines them; the handful that must stay engine-resolved
are the ones the suite patches, and
``tests/test_llm_message_processor_patch_points.py`` derives that set from the
suite rather than trusting anyone to keep a second list correct.
"""

from __future__ import annotations

import datetime
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal

from pydantic_ai._run_context import RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.usage import RunUsage

import src.llm.engine as engine
from src.core.config import settings
from src.dialogue.order_guards import quotation_claimed_without_call
from src.dialogue.order_state import (
    QuoteConsent,
    QuoteLifecycle,
    QuoteWorkflowState,
    quote_workflow_from_metadata,
)
from src.dialogue.runner import (
    quote_consent_signal,
    record_legacy_route,
)
from src.llm.catalog_planning import (
    CLAIM_CONTRACT_SCOPE_KEY,
    SalesDeps,
    _catalog_decision_defects,
    _catalog_decision_output_is_valid,
    _catalog_decision_repair_directive,
    _catalog_decision_runtime_directive,
    _catalog_planning_for_turn,
    _catalog_recovery_output_is_valid,
    _claim_contract_directive,
    _claim_contract_runs_every_catalog_turn,
    _complete_verified_cross_sell_for_recovery,
    _enforce_claim_contract,
    _log_claim_contract,
    _materialize_verified_catalog_facts,
    _should_override_policy_for_catalog_fact_query,
    _store_catalog_planning,
    _turn_owes_the_company_question,
    _verified_prose_response,
    _verify_volunteered_claims,
    catalog_anchor_line,
    grounded_amounts_for_turn,
)
from src.llm.closed_question_guard import response_asks_customer_name
from src.llm.grounding_output import GroundingOutputAction
from src.llm.order_quote_routes import (
    build_declared_static_response,
)
from src.llm.pii import (
    mask_pii,
    unmask_pii,
)
from src.llm.response_policy import (
    ReplyPolicyState,
    render_reply,
)
from src.llm.response_policy import (
    last_assistant_asked_quote_customer_details as _last_assistant_asked_quote_customer_details,
)
from src.llm.response_runtime import (
    PendingReferenceRoute,
    _product_media_is_referenced,
    _response_from_rendered_reply,
)
from src.llm.safety import (
    PATH_CORE_CHAT,
    get_llm_usage_telemetry,
    model_name_for_path,
    model_settings_for_path,
    run_agent_with_safety,
)
from src.llm.verified_answers import (
    build_clarification_response,
    build_quote_or_proposal_clarification_response,
    build_sales_fallback_response,
    build_service_handoff_reason,
    build_service_handoff_response,
    build_service_runtime_directives,
    is_quote_or_proposal_request,
)
from src.models.conversation import Conversation
from src.services.bot_behavior_rules import (
    BehaviorRuleSearchContext,
    rule_to_applied_dict,
)
from src.services.customer_identity import build_bounded_returning_customer_context
from src.services.customer_language import (
    is_arabic_customer_language,
    is_strongly_arabic_customer_text,
)
from src.services.escalation_state import is_active_human_handoff
from src.services.runtime_execution_evidence import (
    extract_runtime_tool_traces,
)

if TYPE_CHECKING:
    from uuid import UUID

    from pydantic_ai.messages import (
        ModelRequest as ModelRequestT,
    )
    from pydantic_ai.messages import (
        ModelResponse as ModelResponseT,
    )
    from pydantic_ai.usage import RunUsage as RunUsageT
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.dialogue.runner import DialogueKernelResult as DialogueKernelResultT
    from src.integrations.crm.zoho_crm import ZohoCRMClient
    from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
    from src.integrations.messaging.base import MessagingProvider
    from src.llm.catalog_planning import SalesDeps as SalesDepsT
    from src.llm.response_policy import (
        RenderedReply as RenderedReplyT,
    )
    from src.llm.response_policy import (
        ReplyProvenance as ReplyProvenanceT,
    )
    from src.llm.response_runtime import (
        LLMResponse as LLMResponseT,
    )
    from src.llm.response_runtime import (
        ProductMediaPayload as ProductMediaPayloadT,
    )
    from src.llm.safety import (
        OpenRouterTelemetryChatModel as OpenAIChatModelT,
    )
    from src.models.conversation import Conversation as ConversationT
    from src.rag.embeddings import EmbeddingEngine
    from src.services.chat_latency import ChatLatencyTrace
    from src.services.runtime_execution_evidence import (
        RuntimeToolTrace as RuntimeToolTraceT,
    )


logger = logging.getLogger("src.llm.engine")


async def process_message_impl(
    *,
    pending_reference_route: Callable[..., Awaitable[PendingReferenceRoute]],
    order_quote_route: Callable[..., Awaitable[LLMResponseT | None]],
    conversation_id: UUID,
    combined_text: str,
    db: AsyncSession,
    redis: Any,
    embedding_engine: EmbeddingEngine,
    zoho_client: ZohoInventoryClient,
    messaging_client: MessagingProvider,
    crm_client: ZohoCRMClient | None = None,
    source_message_id: str | None = None,
    latency_trace: ChatLatencyTrace | None = None,
) -> LLMResponseT:
    """Process an incoming message through the PydanticAI agent.

    1. Loads conversation
    2. Applies optional PII masking
    3. Builds message history
    4. Runs LLM agent
    5. Unmasks PII in response when masking was enabled
    """

    # Resolved through the engine module at call time, so the patch points the
    # suite has always used keep working -- and, because the module is imported
    # rather than passed in as an object, mypy still checks every call below.
    MIXED_PRODUCT_SERVICE_DIRECTIVES = engine.MIXED_PRODUCT_SERVICE_DIRECTIVES
    OpenAIChatModel = engine.OpenAIChatModel
    PRODUCT_PREFERENCE_ANSWER_DIRECTIVES = engine.PRODUCT_PREFERENCE_ANSWER_DIRECTIVES
    VERIFIED_POLICY_REPAIR_KEY = engine.VERIFIED_POLICY_REPAIR_KEY
    _POST_QUOTATION_GENERIC_ACCEPTANCE_EXACT = (
        engine._POST_QUOTATION_GENERIC_ACCEPTANCE_EXACT
    )
    _accepts_exact_item_quote_followup = engine._accepts_exact_item_quote_followup
    _active_pending_quote_selection_from_conversation = (
        engine._active_pending_quote_selection_from_conversation
    )
    _capture_expected_answer_frames_from_assistant_response = (
        engine._capture_expected_answer_frames_from_assistant_response
    )
    _clear_pending_quote_brief_confirmation = (
        engine._clear_pending_quote_brief_confirmation
    )
    _consume_name_gate_pending_request = engine._consume_name_gate_pending_request
    _create_or_reuse_sales_opportunity = engine._create_or_reuse_sales_opportunity
    _customer_facts_int_config = engine._customer_facts_int_config
    _detail_capture_acknowledgement = engine._detail_capture_acknowledgement
    _dialogue_kernel_bool_config = engine._dialogue_kernel_bool_config
    _dialogue_kernel_product_preference_match = (
        engine._dialogue_kernel_product_preference_match
    )
    _exact_quote_followup_candidates = engine._exact_quote_followup_candidates
    _extract_ordered_unlabeled_quote_brief = (
        engine._extract_ordered_unlabeled_quote_brief
    )
    _extract_pending_name_gate_reply_name = engine._extract_pending_name_gate_reply_name
    _extract_quote_customer_details = engine._extract_quote_customer_details
    _extract_sales_memory_updates = engine._extract_sales_memory_updates
    _extract_sales_opportunity_request = engine._extract_sales_opportunity_request
    _extract_terse_quote_customer_details = engine._extract_terse_quote_customer_details
    _has_active_sales_detail_capture_context = (
        engine._has_active_sales_detail_capture_context
    )
    _has_affirmative_quote_resume_intent = engine._has_affirmative_quote_resume_intent
    _has_canonical_quote_workflow = engine._has_canonical_quote_workflow
    _has_detail_capture_handoff_blocker = engine._has_detail_capture_handoff_blocker
    _has_explicit_quote_hold = engine._has_explicit_quote_hold
    _has_explicit_quote_opt_in = engine._has_explicit_quote_opt_in
    _has_pending_proposal_decision = engine._has_pending_proposal_decision
    _has_quote_customer_details_beyond_name = (
        engine._has_quote_customer_details_beyond_name
    )
    _has_quote_reply_purchase_selection_update = (
        engine._has_quote_reply_purchase_selection_update
    )
    _has_quote_resume_consultative_priority = (
        engine._has_quote_resume_consultative_priority
    )
    _has_quoted_quote_frame = engine._has_quoted_quote_frame
    _is_mixed_product_service_request = engine._is_mixed_product_service_request
    _is_name_gate_completion_reply = engine._is_name_gate_completion_reply
    _is_neutral_detail_capture_update = engine._is_neutral_detail_capture_update
    _is_post_quotation_acceptance = engine._is_post_quotation_acceptance
    _is_post_quotation_context_preserving_reply = (
        engine._is_post_quotation_context_preserving_reply
    )
    _is_product_preference_answer = engine._is_product_preference_answer
    _is_service_confirmation_reply = engine._is_service_confirmation_reply
    _is_specific_delivery_address = engine._is_specific_delivery_address
    _last_assistant_asked_quote_brief_confirmation = (
        engine._last_assistant_asked_quote_brief_confirmation
    )
    _last_assistant_message = engine._last_assistant_message
    _last_assistant_offered_quote_for_selection = (
        engine._last_assistant_offered_quote_for_selection
    )
    _mark_quotation_accepted = engine._mark_quotation_accepted
    _name_gate_pending_intent_from_metadata = (
        engine._name_gate_pending_intent_from_metadata
    )
    _name_gate_pending_request_from_metadata = (
        engine._name_gate_pending_request_from_metadata
    )
    _normalize_customer_facts_mode = engine._normalize_customer_facts_mode
    _materialize_verified_catalog_recovery = (
        engine._materialize_verified_catalog_recovery
    )
    _normalize_text = engine._normalize_text
    _order_quote_route_for_turn = order_quote_route
    _try_verified_catalog_plan = engine._try_verified_catalog_plan
    _string_value = engine._string_value
    _pending_quote_brief_confirmation_from_metadata = (
        engine._pending_quote_brief_confirmation_from_metadata
    )
    _pending_quote_has_unresolved_items = engine._pending_quote_has_unresolved_items
    _pending_reference_route_for_turn = pending_reference_route
    _post_quotation_accepted_response = engine._post_quotation_accepted_response
    _post_quotation_acknowledgement_response = (
        engine._post_quotation_acknowledgement_response
    )
    _post_quotation_context_acknowledgement_response = (
        engine._post_quotation_context_acknowledgement_response
    )
    _product_preference_frame_directives = engine._product_preference_frame_directives
    _quote_customer_details_from_metadata = engine._quote_customer_details_from_metadata
    _quote_intent_frame_from_metadata = engine._quote_intent_frame_from_metadata
    _quote_intent_frame_from_text = engine._quote_intent_frame_from_text
    _quote_offer_allowed_for_turn = engine._quote_offer_allowed_for_turn
    _run_customer_facts_layer = engine._run_customer_facts_layer
    _sales_opportunity_response = engine._sales_opportunity_response
    _sales_opportunity_title = engine._sales_opportunity_title
    _service_confirmation_handoff_text = engine._service_confirmation_handoff_text
    _showroom_location_response = engine._showroom_location_response
    _store_applied_bot_rules = engine._store_applied_bot_rules
    _store_confirmed_quote_brief_address = engine._store_confirmed_quote_brief_address
    _store_extracted_quote_customer_details = (
        engine._store_extracted_quote_customer_details
    )
    _store_kernel_quantity_prompt_frame = engine._store_kernel_quantity_prompt_frame
    _store_name_gate_pending_request = engine._store_name_gate_pending_request
    _store_quote_intent_frame = engine._store_quote_intent_frame
    _store_quote_workflow = engine._store_quote_workflow
    _store_sales_memory_updates = engine._store_sales_memory_updates
    _strip_synthetic_test_marker = engine._strip_synthetic_test_marker
    _suspend_quote_workflow = engine._suspend_quote_workflow
    _turn_runtime_directives = engine._turn_runtime_directives
    build_message_history = engine.build_message_history
    evaluate_verified_answer_policy = engine.evaluate_verified_answer_policy
    prose_agent = engine.prose_agent
    run_dialogue_kernel = engine.run_dialogue_kernel
    sales_agent = engine.sales_agent
    search_behavior_rules = engine.search_behavior_rules
    context_started = latency_trace.start_phase() if latency_trace is not None else None
    combined_text = _strip_synthetic_test_marker(combined_text)
    dialogue_kernel_result: DialogueKernelResultT | None = None

    def _is_first_turn(
        history_messages: list[ModelRequestT | ModelResponseT],
    ) -> bool:
        user_turns = 0
        assistant_turns = 0

        for message in history_messages:
            if isinstance(message, ModelRequest) and any(
                isinstance(part, UserPromptPart) for part in message.parts
            ):
                user_turns += 1
            elif isinstance(message, ModelResponse) and any(
                isinstance(part, TextPart) for part in message.parts
            ):
                assistant_turns += 1

        return assistant_turns == 0 and user_turns >= 1

    def _has_escalation(conversation: ConversationT) -> bool:
        return is_active_human_handoff(conversation.escalation_status)

    def _get_verified_policy_repair_state() -> dict[str, int | str] | None:
        assert conv is not None
        metadata = conv.metadata_ if isinstance(conv.metadata_, dict) else {}
        state = metadata.get(VERIFIED_POLICY_REPAIR_KEY)
        if not isinstance(state, dict):
            return None
        kind = state.get("kind")
        count = state.get("count")
        if not isinstance(kind, str) or not isinstance(count, int):
            return None
        return {"kind": kind, "count": count}

    async def _set_verified_policy_repair_state(kind: str, count: int) -> None:
        assert conv is not None
        metadata = dict(conv.metadata_ or {})
        metadata[VERIFIED_POLICY_REPAIR_KEY] = {"kind": kind, "count": count}
        conv.metadata_ = metadata
        await db.flush()

    async def _clear_verified_policy_repair_state() -> None:
        assert conv is not None
        metadata = dict(conv.metadata_ or {})
        if VERIFIED_POLICY_REPAIR_KEY not in metadata:
            return
        metadata.pop(VERIFIED_POLICY_REPAIR_KEY, None)
        conv.metadata_ = metadata
        await db.flush()

    # Filled only on the name-gate path, where the catalog can be read.
    opening_anchor_line: list[str | None] = [None]

    def _deferred_product_media_for_response(
        response_deps: SalesDepsT,
        *,
        allow_product_media: bool,
        response_text: str,
    ) -> tuple[ProductMediaPayloadT, ...]:
        if response_deps.quotation_created:
            if response_deps.pending_product_media:
                logger.warning(
                    "Suppressed %d deferred product media item(s) after quotation "
                    "creation for conversation %s in %s mode",
                    len(response_deps.pending_product_media),
                    response_deps.conversation.id,
                    response_deps.tool_mode,
                )
            return ()
        if allow_product_media:
            referenced_media = tuple(
                item
                for item in response_deps.pending_product_media
                if _product_media_is_referenced(item, response_text)
            )
            suppressed_count = len(response_deps.pending_product_media) - len(
                referenced_media
            )
            if suppressed_count:
                logger.info(
                    "Suppressed %d deferred product media item(s) not referenced "
                    "by the final response for conversation %s",
                    suppressed_count,
                    response_deps.conversation.id,
                )
            return referenced_media
        if response_deps.pending_product_media:
            logger.warning(
                "Suppressed %d deferred product media item(s) for conversation %s "
                "in %s mode",
                len(response_deps.pending_product_media),
                response_deps.conversation.id,
                response_deps.tool_mode,
            )
        return ()

    name_gate_resume_customer_name: str | None = None

    def _known_customer_name_for_guards() -> str:
        assert conv is not None
        quote_details = _quote_customer_details_from_metadata(conv)
        return (
            _string_value(name_gate_resume_customer_name)
            or _string_value(quote_details.get("name"))
            or _string_value(conv.customer_name)
        )

    def _render_customer_reply(
        text: str,
        *,
        response_deps: SalesDepsT,
        provenance: ReplyProvenanceT,
        model_name: str,
    ) -> RenderedReplyT:
        assert conv is not None
        quote_details = _quote_customer_details_from_metadata(conv)
        delivery_address = _string_value(quote_details.get("address"))
        if delivery_address and not _is_specific_delivery_address(delivery_address):
            delivery_address = ""
        quote_workflow = quote_workflow_from_metadata(
            response_deps.conversation.metadata_
        )
        rendered = render_reply(
            unmask_pii(text, pii_map),
            state=ReplyPolicyState(
                language=str(response_deps.conversation.language),
                is_first_turn=is_first_turn,
                customer_name=_known_customer_name_for_guards() or None,
                anchor_line=opening_anchor_line[0],
                company=_string_value(quote_details.get("company")) or None,
                customer_type=(
                    _string_value(quote_details.get("customer_type")) or None
                ),
                delivery_address=delivery_address or None,
                previous_assistant_turns=tuple(
                    entry.removeprefix("assistant: ")
                    for entry in (response_deps.recent_history or ())
                    if entry.startswith("assistant: ")
                ),
                owes_company_question=_turn_owes_the_company_question(response_deps),
                quote_consent_granted=(quote_workflow.consent is QuoteConsent.GRANTED),
                inventory_confirmed=response_deps.inventory_confirmed,
                grounded_amounts=grounded_amounts_for_turn(
                    response_deps,
                    customer_text=combined_text,
                ),
                required_tool_disclosure=(
                    _string_value(response_deps.required_cross_sell_disclosure) or None
                ),
            ),
            provenance=provenance,
        )
        if rendered.grounding.action is not GroundingOutputAction.UNCHANGED:
            logger.warning(
                "Enforced customer output: action=%s violations=%s "
                "model=%s language=%s",
                rendered.grounding.action,
                [violation.value for violation in rendered.grounding.violations],
                model_name,
                response_deps.conversation.language,
            )
        return rendered

    def _build_llm_response(
        result: Any,
        model_name: str,
        *,
        response_deps: SalesDepsT | None = None,
        allow_product_media: bool = True,
        text_provenance: Literal["model", "model_repaired"] = "model",
        route_suffix: str | None = None,
    ) -> LLMResponseT:
        assert conv is not None
        response_deps = response_deps or deps
        if route_suffix:
            model_name = f"{model_name}|{route_suffix}"
        rendered = _render_customer_reply(
            result.output,
            response_deps=response_deps,
            provenance=text_provenance,
            model_name=model_name,
        )
        if quotation_claimed_without_call(
            rendered.text, quotation_created=response_deps.quotation_created
        ):
            # Recorded, not rewritten: withdrawing the tool is the elimination,
            # and blocking a whole response over one sentence is out of scope.
            logger.error(
                "Reply asserts a prepared quotation with no successful call: "
                "conversation=%s model=%s executed_tools=%s",
                response_deps.conversation.id,
                model_name,
                response_deps.executed_tool_names,
            )
        usage = result.usage()
        usage_telemetry = get_llm_usage_telemetry(result)
        if conv is not None and not model_name.startswith("dialogue-kernel|"):
            record_legacy_route(
                conv,
                dialogue_kernel_result,
                legacy_route=model_name,
            )
            _capture_expected_answer_frames_from_assistant_response(
                conv,
                response_text=rendered.text,
                dialogue_kernel_mode=dialogue_kernel_mode,
            )
        return _response_from_rendered_reply(
            rendered,
            tokens_in=usage.input_tokens if usage else None,
            tokens_out=usage.output_tokens if usage else None,
            cost=usage_telemetry.cost if usage_telemetry is not None else None,
            model=model_name,
            usage_provenance="provider_reported",
            deferred_product_media=_deferred_product_media_for_response(
                response_deps,
                allow_product_media=allow_product_media,
                response_text=rendered.text,
            ),
            tool_traces=extract_runtime_tool_traces(result),
        )

    # The model runtime used to be built inside the try block below, which put
    # it out of reach of every route that runs before it. sales-opportunity is
    # one of those, and it needs the model to write its sentence (tj-swgu.3).
    # Memoised, so a turn that never reaches the model still pays nothing.
    model_runtime: tuple[str, OpenAIChatModelT] | None = None
    failed_run_usage: RunUsageT | None = None

    async def _ensure_model_runtime() -> tuple[str, OpenAIChatModelT]:
        nonlocal model_runtime
        if model_runtime is None:
            from src.core.config import get_system_config

            name = model_name_for_path(
                PATH_CORE_CHAT,
                await get_system_config(
                    db, "openrouter_model_main", settings.openrouter_model_main
                ),
            )
            model_runtime = (
                name,
                OpenAIChatModel(
                    name,
                    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
                    settings=model_settings_for_path(PATH_CORE_CHAT, model_name=name),
                ),
            )
        return model_runtime

    async def _run_prose_agent(directive: str, run_deps: SalesDepsT) -> Any:
        """Run the rewrite on its own, away from the product system prompt."""

        runtime_model_name, runtime_model = await _ensure_model_runtime()
        return await run_agent_with_safety(
            prose_agent,
            PATH_CORE_CHAT,
            user_prompt=directive,
            deps=run_deps,
            message_history=[],
            model=runtime_model,
            model_name=runtime_model_name,
            usage=RunUsage(),
        )

    async def _run_agent(run_deps: SalesDepsT) -> Any:
        nonlocal failed_run_usage
        runtime_model_name, runtime_model = await _ensure_model_runtime()
        agent_started = (
            latency_trace.start_phase() if latency_trace is not None else None
        )
        run_usage = RunUsage()
        try:
            result = await run_agent_with_safety(
                sales_agent,
                PATH_CORE_CHAT,
                user_prompt=masked_text,
                deps=run_deps,
                message_history=history,
                model=runtime_model,
                model_name=runtime_model_name,
                usage=run_usage,
            )
            if run_deps.inventory_confirmed:
                deps.inventory_confirmed = True
            return result
        except (UnexpectedModelBehavior, TimeoutError):
            failed_run_usage = run_usage
            raise
        finally:
            if latency_trace is not None and agent_started is not None:
                latency_trace.finish_phase("model_tools", agent_started)

    def _build_static_response(
        text: str,
        model_name: str,
        *,
        response_deps: SalesDepsT | None = None,
        allow_product_media: bool = True,
        tool_traces: tuple[RuntimeToolTraceT, ...] = (),
    ) -> LLMResponseT:
        assert conv is not None
        response_deps = response_deps or deps
        rendered = _render_customer_reply(
            text,
            response_deps=response_deps,
            provenance="deterministic_static",
            model_name=model_name,
        )
        if conv is not None and not model_name.startswith("dialogue-kernel|"):
            record_legacy_route(
                conv,
                dialogue_kernel_result,
                legacy_route=model_name,
            )
            _capture_expected_answer_frames_from_assistant_response(
                conv,
                response_text=rendered.text,
                dialogue_kernel_mode=dialogue_kernel_mode,
            )
        return _response_from_rendered_reply(
            rendered,
            tokens_in=0,
            tokens_out=0,
            cost=None,
            model=model_name,
            usage_provenance="deterministic_static",
            deferred_product_media=_deferred_product_media_for_response(
                response_deps,
                allow_product_media=allow_product_media,
                response_text=rendered.text,
            ),
            tool_traces=tool_traces,
        )

    async def _build_policy_handoff_response(
        model_name: str, decision_language: str, decision_text: str
    ) -> LLMResponseT:
        assert conv is not None
        final_text = (
            decision_text
            if decision_text
            else build_service_handoff_response(policy_decision, decision_language)
        )
        response_model = f"{model_name}|verified-policy"
        rendered = _render_customer_reply(
            final_text,
            response_deps=deps,
            provenance="deterministic_static",
            model_name=response_model,
        )
        if conv is not None:
            record_legacy_route(
                conv,
                dialogue_kernel_result,
                legacy_route=response_model,
            )
        return _response_from_rendered_reply(
            rendered,
            tokens_in=0,
            tokens_out=0,
            cost=None,
            model=response_model,
            usage_provenance="deterministic_static",
            deferred_product_media=_deferred_product_media_for_response(
                deps,
                allow_product_media=False,
                response_text=rendered.text,
            ),
        )

    # Load conversation (already loaded by caller typically, but we fetch to be safe/fresh)
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise ValueError(f"Conversation {conversation_id} not found")

    from src.core.cache import get_cached_crm_profile, set_cached_crm_profile

    # Fetch CRM Profile for context enrichment
    crm_context = None
    if crm_client and conv.phone:
        crm_context = await get_cached_crm_profile(redis, conv.phone)
        if not crm_context:
            contact = await crm_client.find_contact_by_phone(conv.phone)
            if contact:
                crm_context = build_bounded_returning_customer_context(contact)
                await set_cached_crm_profile(redis, conv.phone, crm_context)
            else:
                crm_context = build_bounded_returning_customer_context(None)

    # Optional shared dict for PII placeholders across history.
    pii_map: dict[str, str] = {}

    # Process history (also populates pii_map when PII masking is enabled).
    history = await build_message_history(db, conversation_id, pii_map)

    # Keep contact details visible by default for deterministic fact extraction.
    masked_text, new_piis = mask_pii(combined_text)
    pii_map.update(new_piis)
    is_first_turn = _is_first_turn(history)
    if (
        is_first_turn
        and not is_arabic_customer_language(conv.language)
        and is_strongly_arabic_customer_text(combined_text)
    ):
        conv.language = "ar"
        await db.flush()

    # Escalation is now handled by the agent's escalate_to_manager tool.
    # The agent decides when to escalate based on full conversation context.
    # Build recent history for potential escalation context
    recent_history: list[str] = []
    for message in history:
        if isinstance(message, ModelRequest):
            for request_part in message.parts:
                if isinstance(request_part, UserPromptPart):
                    recent_history.append(f"user: {request_part.content}")
        elif isinstance(message, ModelResponse):
            for response_part in message.parts:
                if isinstance(response_part, TextPart):
                    recent_history.append(f"assistant: {response_part.content}")
    recent_history = recent_history[-5:]
    current_user_entry = f"user: {masked_text}"
    if not recent_history or recent_history[-1] != current_user_entry:
        recent_history.append(current_user_entry)
    catalog_planning = _catalog_planning_for_turn(
        conv,
        recent_history,
        masked_text,
    )
    await _store_catalog_planning(db, conv, catalog_planning)

    deps = SalesDeps(
        db=db,
        redis=redis,
        conversation=conv,
        embedding_engine=embedding_engine,
        zoho_inventory=zoho_client,
        zoho_crm=crm_client,
        messaging_client=messaging_client,
        pii_map=pii_map,
        crm_context=crm_context,
        user_query=masked_text,
        recent_history=recent_history,
        defer_product_media=True,
        source_message_id=source_message_id,
        catalog_planning=catalog_planning,
    )

    from src.core.config import get_system_config

    customer_facts_mode = _normalize_customer_facts_mode(
        await get_system_config(
            db,
            "customer_facts_mode",
            settings.customer_facts_mode,
        )
    )
    customer_facts_trace_enabled = _dialogue_kernel_bool_config(
        await get_system_config(
            db,
            "customer_facts_trace_enabled",
            str(settings.customer_facts_trace_enabled).lower(),
        ),
        default=settings.customer_facts_trace_enabled,
    )
    customer_facts_fast_extractor_enabled = _dialogue_kernel_bool_config(
        await get_system_config(
            db,
            "customer_facts_fast_extractor_enabled",
            str(settings.customer_facts_fast_extractor_enabled).lower(),
        ),
        default=settings.customer_facts_fast_extractor_enabled,
    )
    customer_facts_max_context_orders = _customer_facts_int_config(
        await get_system_config(
            db,
            "customer_facts_max_context_orders",
            str(settings.customer_facts_max_context_orders),
        ),
        default=settings.customer_facts_max_context_orders,
        minimum=0,
        maximum=10,
    )
    claim_contract_every_catalog_turn = _claim_contract_runs_every_catalog_turn(
        await get_system_config(
            db,
            CLAIM_CONTRACT_SCOPE_KEY,
            "requested_gaps",
        )
    )
    dialogue_kernel_mode = await get_system_config(
        db,
        "dialogue_kernel_mode",
        settings.dialogue_kernel_mode,
    )
    dialogue_kernel_trace_enabled = _dialogue_kernel_bool_config(
        await get_system_config(
            db,
            "dialogue_kernel_trace_enabled",
            str(settings.dialogue_kernel_trace_enabled).lower(),
        ),
        default=settings.dialogue_kernel_trace_enabled,
    )
    dialogue_kernel_enforced_flows = await get_system_config(
        db,
        "dialogue_kernel_enforced_flows",
        settings.dialogue_kernel_enforced_flows,
    )

    customer_facts_run = await _run_customer_facts_layer(
        db,
        conversation=conv,
        text=combined_text,
        mode=customer_facts_mode,
        trace_enabled=customer_facts_trace_enabled,
        fast_extractor_enabled=customer_facts_fast_extractor_enabled,
        max_context_orders=customer_facts_max_context_orders,
        source_message_id=source_message_id,
    )
    if customer_facts_run.context_text:
        deps = replace(deps, customer_facts_context=customer_facts_run.context_text)
    if customer_facts_run.past_order_response:
        db_model_main = await get_system_config(
            db, "openrouter_model_main", settings.openrouter_model_main
        )
        db_model_main = model_name_for_path(PATH_CORE_CHAT, db_model_main)
        return build_declared_static_response(
            customer_facts_run.past_order_response,
            route="customer-facts-past-order",
            build_static_response=_build_static_response,
            model_prefix=db_model_main,
            allow_product_media=False,
        )

    if _has_pending_proposal_decision(conv) and _is_post_quotation_acceptance(
        combined_text,
        recent_history,
    ):
        from src.integrations.notifications.escalation import (
            notify_manager_escalation,
        )
        from src.schemas.common import EscalationType

        accepted_at = datetime.datetime.now(datetime.UTC)
        _mark_quotation_accepted(
            conv,
            accepted_at=accepted_at,
            customer_text=combined_text,
        )
        if not is_active_human_handoff(conv.escalation_status):
            await notify_manager_escalation(
                conversation=conv,
                reason=(
                    "Customer accepted the quotation/proposal after the PDF was sent. "
                    "Manager should proceed with the next commercial steps."
                ),
                recent_messages=deps.recent_history or [],
                db=db,
                escalation_type=EscalationType.ORDER_CONFIRMATION,
            )
        await db.flush()
        db_model_main = await get_system_config(
            db, "openrouter_model_main", settings.openrouter_model_main
        )
        db_model_main = model_name_for_path(PATH_CORE_CHAT, db_model_main)
        return build_declared_static_response(
            _post_quotation_accepted_response(str(conv.language)),
            route="post-quotation-accepted",
            build_static_response=_build_static_response,
            model_prefix=db_model_main,
            allow_product_media=False,
        )

    if (
        _has_pending_proposal_decision(conv)
        and _normalize_text(combined_text) in _POST_QUOTATION_GENERIC_ACCEPTANCE_EXACT
    ):
        db_model_main = await get_system_config(
            db, "openrouter_model_main", settings.openrouter_model_main
        )
        db_model_main = model_name_for_path(PATH_CORE_CHAT, db_model_main)
        return build_declared_static_response(
            _post_quotation_acknowledgement_response(str(conv.language)),
            route="post-quotation-ack",
            build_static_response=_build_static_response,
            model_prefix=db_model_main,
            allow_product_media=False,
        )

    if _has_quoted_quote_frame(conv) and _is_post_quotation_context_preserving_reply(
        combined_text
    ):
        db_model_main = await get_system_config(
            db, "openrouter_model_main", settings.openrouter_model_main
        )
        db_model_main = model_name_for_path(PATH_CORE_CHAT, db_model_main)
        return build_declared_static_response(
            _post_quotation_context_acknowledgement_response(str(conv.language)),
            route="post-quotation-context-ack",
            build_static_response=_build_static_response,
            model_prefix=db_model_main,
            allow_product_media=False,
        )

    if _has_explicit_quote_hold(combined_text):
        await _suspend_quote_workflow(
            db,
            conv,
            consent=quote_consent_signal(combined_text, []) or QuoteConsent.DECLINED,
        )

    order_runtime_blocks_kernel_reply = (
        _active_pending_quote_selection_from_conversation(conv) is not None
        or _quote_intent_frame_from_metadata(conv) is not None
    )

    try:
        dialogue_kernel_result = await run_dialogue_kernel(
            conversation=conv,
            text=combined_text,
            recent_history=recent_history,
            is_first_turn=is_first_turn,
            mode=dialogue_kernel_mode,
            enforced_flows=dialogue_kernel_enforced_flows,
            trace_enabled=dialogue_kernel_trace_enabled,
        )
    except Exception:
        if str(dialogue_kernel_mode or "").strip().casefold() != "shadow":
            raise
        logger.warning(
            "Dialogue kernel shadow run failed for conversation %s; "
            "continuing legacy path",
            conv.id,
            exc_info=True,
        )
        dialogue_kernel_result = None
    if dialogue_kernel_result is not None:
        kernel_workflow = QuoteWorkflowState(
            consent=dialogue_kernel_result.state.quote_consent,
            lifecycle=dialogue_kernel_result.state.quote_lifecycle,
        )
        current_workflow = quote_workflow_from_metadata(conv.metadata_)
        kernel_consent_value = dialogue_kernel_result.decision.metadata.get(
            "quote_consent"
        )
        kernel_has_explicit_consent = isinstance(kernel_consent_value, str)
        kernel_grant_is_current_turn = (
            kernel_consent_value == QuoteConsent.GRANTED.value
            and (
                _has_explicit_quote_opt_in(combined_text)
                or (
                    _last_assistant_offered_quote_for_selection(recent_history)
                    and _has_affirmative_quote_resume_intent(combined_text)
                )
            )
        )
        canonical_blocks_stale_kernel_grant = (
            _has_canonical_quote_workflow(conv)
            and current_workflow.consent
            in {QuoteConsent.DEFERRED, QuoteConsent.DECLINED}
            and kernel_workflow.consent is QuoteConsent.GRANTED
            and not kernel_grant_is_current_turn
        )
        if kernel_workflow != current_workflow and (
            kernel_grant_is_current_turn
            or (
                kernel_has_explicit_consent
                and kernel_workflow.consent is not QuoteConsent.GRANTED
            )
            or (
                not _has_canonical_quote_workflow(conv)
                and current_workflow.consent is QuoteConsent.NOT_REQUESTED
                and kernel_workflow.consent is not QuoteConsent.GRANTED
            )
        ):
            await _store_quote_workflow(db, conv, kernel_workflow)
    if (
        dialogue_kernel_result is not None
        and dialogue_kernel_result.should_use_kernel
        and not canonical_blocks_stale_kernel_grant
        and dialogue_kernel_result.decision.action != "product_preference_answer"
        and not (
            order_runtime_blocks_kernel_reply
            and dialogue_kernel_result.decision.flow != "quote_details"
        )
    ):
        if dialogue_kernel_result.decision.flow == "name_gate":
            await _store_name_gate_pending_request(db, conv, combined_text)
        if dialogue_kernel_result.decision.flow == "quote_details":
            raw_details = dialogue_kernel_result.decision.metadata.get(
                "quote_customer_details"
            )
            if isinstance(raw_details, Mapping):
                quote_details: dict[str, str] = {}
                name = raw_details.get("customer_name")
                address = raw_details.get("delivery_address")
                company = raw_details.get("company")
                customer_type = raw_details.get("customer_type")
                if isinstance(name, str) and name.strip():
                    quote_details["name"] = name.strip()
                if isinstance(address, str) and address.strip():
                    quote_details["address"] = address.strip()
                if isinstance(company, str) and company.strip():
                    quote_details["company"] = company.strip()
                if isinstance(customer_type, str) and customer_type.strip():
                    quote_details["customer_type"] = customer_type.strip()
                await _store_extracted_quote_customer_details(db, conv, quote_details)
        if dialogue_kernel_result.decision.flow == "product_selection":
            await _store_kernel_quantity_prompt_frame(
                db,
                conv,
                combined_text=combined_text,
                masked_text=masked_text,
                response_text=dialogue_kernel_result.decision.response_text or "",
            )
        return _build_static_response(
            dialogue_kernel_result.decision.response_text or "",
            f"dialogue-kernel|{dialogue_kernel_result.decision.flow}",
            allow_product_media=False,
        )

    customer_name_was_unknown = not str(conv.customer_name or "").strip()
    current_quote_customer_details = _extract_quote_customer_details(combined_text)
    current_quote_intent_frame: Mapping[str, Any] | None = (
        _quote_intent_frame_from_text(combined_text)
    )
    current_sales_memory_updates = _extract_sales_memory_updates(combined_text)
    current_sales_opportunity_request = _extract_sales_opportunity_request(
        combined_text
    )
    pending_name_gate_request = _name_gate_pending_request_from_metadata(conv)
    pending_name_gate_intent = _name_gate_pending_intent_from_metadata(conv)
    resumed_name_gate_intent: str | None = None
    pending_quote_selection_at_start = (
        _active_pending_quote_selection_from_conversation(conv)
    )
    has_pending_quote_selection = pending_quote_selection_at_start is not None
    pending_unconsented_detail_keys: set[str] = set()
    if has_pending_quote_selection and not current_quote_customer_details:
        identity_candidates = _extract_terse_quote_customer_details(combined_text)
        pending_unconsented_detail_keys = set(identity_candidates).intersection(
            {"customer_type", "email", "phone", "address"}
        )
        current_quote_customer_details = {
            key: value
            for key, value in identity_candidates.items()
            if key in {"name", "company"}
        }
    pending_exact_quote_followup_candidates = (
        _exact_quote_followup_candidates(
            selection=pending_quote_selection_at_start,
            combined_text=combined_text,
            masked_text=masked_text,
        )
        if pending_quote_selection_at_start is not None
        and _accepts_exact_item_quote_followup(pending_quote_selection_at_start)
        and _pending_quote_has_unresolved_items(pending_quote_selection_at_start)
        else ()
    )
    assistant_asked_quote_details = _last_assistant_asked_quote_customer_details(
        recent_history,
        quote_context_active=(
            has_pending_quote_selection or order_runtime_blocks_kernel_reply
        ),
    )
    assistant_offered_quote_selection = _last_assistant_offered_quote_for_selection(
        recent_history
    )
    quote_offer_reply_has_consultative_priority = (
        _has_quote_resume_consultative_priority(combined_text)
        or _has_quote_resume_consultative_priority(masked_text)
    )
    quote_reply_updates_purchase_selection = _has_quote_reply_purchase_selection_update(
        combined_text, masked_text
    )
    assistant_supports_quote_resume = assistant_asked_quote_details or (
        assistant_offered_quote_selection
        and not quote_offer_reply_has_consultative_priority
        and (
            _has_explicit_quote_opt_in(combined_text)
            or _has_explicit_quote_opt_in(masked_text)
            or _has_affirmative_quote_resume_intent(combined_text)
            or _has_affirmative_quote_resume_intent(masked_text)
        )
    )
    explicit_quote_consent = not quote_offer_reply_has_consultative_priority and (
        _has_explicit_quote_opt_in(combined_text)
        or _has_explicit_quote_opt_in(masked_text)
        or (
            (
                assistant_offered_quote_selection
                or (has_pending_quote_selection and assistant_asked_quote_details)
            )
            and (
                _has_affirmative_quote_resume_intent(combined_text)
                or _has_affirmative_quote_resume_intent(masked_text)
            )
        )
    )
    quote_workflow = quote_workflow_from_metadata(conv.metadata_)
    if explicit_quote_consent:
        quote_workflow = QuoteWorkflowState(
            consent=QuoteConsent.GRANTED,
            lifecycle=QuoteLifecycle.QUOTE_REQUESTED,
        )
        await _store_quote_workflow(db, conv, quote_workflow)
    quote_consent_granted = quote_workflow.consent is QuoteConsent.GRANTED
    unconsented_quote_details = (
        not quote_consent_granted
        and not quote_offer_reply_has_consultative_priority
        and not quote_reply_updates_purchase_selection
        and bool(
            (has_pending_quote_selection or assistant_asked_quote_details)
            and (
                pending_unconsented_detail_keys
                or set(current_quote_customer_details).intersection(
                    {"customer_type", "email", "phone", "address"}
                )
            )
        )
    )
    quote_detail_context_active = quote_consent_granted and (
        assistant_supports_quote_resume or has_pending_quote_selection
    )
    quote_brief_confirmation_details: dict[str, str] | None = None
    confirmed_quote_brief_address: str | None = None
    pending_quote_brief_confirmation = _pending_quote_brief_confirmation_from_metadata(
        conv
    )
    if (
        pending_quote_brief_confirmation
        and _last_assistant_asked_quote_brief_confirmation(recent_history)
        and _has_affirmative_quote_resume_intent(combined_text)
    ):
        current_quote_customer_details = {
            **current_quote_customer_details,
            **pending_quote_brief_confirmation,
        }
        confirmed_quote_brief_address = _string_value(
            pending_quote_brief_confirmation.get("address")
        )
        await _clear_pending_quote_brief_confirmation(db, conv)
    if quote_detail_context_active:
        unlabeled_quote_brief = _extract_ordered_unlabeled_quote_brief(combined_text)
        if unlabeled_quote_brief and unlabeled_quote_brief.needs_confirmation:
            quote_brief_confirmation_details = unlabeled_quote_brief.details
            current_quote_customer_details = {}
        elif unlabeled_quote_brief:
            terse_quote_customer_details = unlabeled_quote_brief.details
            current_quote_customer_details = {
                **current_quote_customer_details,
                **terse_quote_customer_details,
            }
            await _clear_pending_quote_brief_confirmation(db, conv)
        else:
            terse_quote_customer_details = (
                {}
                if pending_exact_quote_followup_candidates
                else _extract_terse_quote_customer_details(combined_text)
            )
            if terse_quote_customer_details:
                current_quote_customer_details = {
                    **current_quote_customer_details,
                    **terse_quote_customer_details,
                }
                await _clear_pending_quote_brief_confirmation(db, conv)
    if (
        not quote_detail_context_active
        and current_quote_customer_details
        and pending_quote_brief_confirmation
    ):
        await _clear_pending_quote_brief_confirmation(db, conv)
    # A bare "Alex" is only a name because we just asked for one. Until
    # 2026-08-10 the only thing that ever asked was the name gate, so this read
    # its parked request; now any route can ask, and the reply has to land the
    # same way. The condition is on what we actually sent, not on what the
    # engine believes it did.
    if pending_name_gate_request or response_asks_customer_name(
        _last_assistant_message(recent_history)
    ):
        pending_reply_name = _extract_pending_name_gate_reply_name(
            combined_text,
            current_quote_customer_details,
        )
        if pending_reply_name and not current_quote_customer_details.get("name"):
            current_quote_customer_details = {
                **current_quote_customer_details,
                "name": pending_reply_name,
            }

    if (
        is_first_turn
        and customer_name_was_unknown
        and not _string_value(current_quote_customer_details.get("name"))
    ):
        # The turn is no longer spent on the question. It runs to the end like
        # any other, and `apply_opening_guard` folds the name request onto the
        # answer -- owner decision of 2026-08-10, on the measurement that 36% of
        # customers never send a second message and so never got past this
        # point. Nothing is deferred for a later resume, because nothing is
        # deferred at all.
        #
        # The anchor is still read here, where the catalog is in reach, so the
        # opening carries a price when the reply itself found none.
        opening_anchor_line[0] = await catalog_anchor_line(db, str(conv.language))

    # Store customer details from the original, unmasked text before any route
    # can call create_quotation. Phone is enough to create a draft, while the
    # other fields are optional PDF details when the customer provides them.
    if current_quote_customer_details:
        allowed_quote_customer_details = (
            current_quote_customer_details
            if quote_consent_granted
            else {
                key: value
                for key, value in current_quote_customer_details.items()
                if key in {"name", "company"}
            }
        )
        await _store_extracted_quote_customer_details(
            db,
            conv,
            allowed_quote_customer_details,
        )
        if quote_consent_granted and confirmed_quote_brief_address:
            await _store_confirmed_quote_brief_address(
                db,
                conv,
                confirmed_quote_brief_address,
            )
    if (
        current_quote_intent_frame is not None
        and pending_quote_selection_at_start is None
    ):
        await _store_quote_intent_frame(db, conv, combined_text)
    if current_sales_memory_updates:
        await _store_sales_memory_updates(db, conv, current_sales_memory_updates)

    name_gate_completion_reply = _is_name_gate_completion_reply(
        combined_text,
        current_quote_customer_details,
        pending_request_exists=bool(pending_name_gate_request),
    )
    if (
        name_gate_completion_reply
        and quote_detail_context_active
        and _has_quote_customer_details_beyond_name(current_quote_customer_details)
    ):
        await _consume_name_gate_pending_request(db, conv)
        pending_name_gate_request = None
    elif name_gate_completion_reply:
        captured_customer_name = _string_value(current_quote_customer_details["name"])
        resumed_name_gate_intent = pending_name_gate_intent
        pending_name_gate_request = await _consume_name_gate_pending_request(db, conv)
        if pending_name_gate_request:
            name_gate_resume_customer_name = captured_customer_name
            combined_text = pending_name_gate_request
            masked_text, pending_piis = mask_pii(combined_text)
            pii_map.update(pending_piis)
            resumed_quote_customer_details = _extract_quote_customer_details(
                combined_text
            )
            if resumed_quote_customer_details:
                if not _string_value(resumed_quote_customer_details.get("name")):
                    resumed_quote_customer_details = {
                        **resumed_quote_customer_details,
                        "name": captured_customer_name,
                    }
                if not quote_consent_granted:
                    resumed_quote_customer_details = {
                        key: value
                        for key, value in resumed_quote_customer_details.items()
                        if key in {"name", "company"}
                    }
                await _store_extracted_quote_customer_details(
                    db,
                    conv,
                    resumed_quote_customer_details,
                )
            pending_user_entry = f"user: {masked_text}"
            if pending_user_entry not in recent_history:
                recent_history.append(pending_user_entry)
            recent_history = recent_history[-5:]
            deps = replace(
                deps,
                user_query=masked_text,
                recent_history=recent_history,
                runtime_directives=(
                    *deps.runtime_directives,
                    f"Customer name is {captured_customer_name}. Continue the "
                    "customer's prior request now that their name is known. "
                    "Acknowledge the name briefly. Do not ask for their name "
                    "again, and do not ask what they need again.",
                ),
            )
            current_quote_customer_details = _quote_customer_details_from_metadata(conv)
            current_quote_intent_frame = _quote_intent_frame_from_metadata(
                conv
            ) or _quote_intent_frame_from_text(combined_text)
            current_sales_opportunity_request = _extract_sales_opportunity_request(
                combined_text
            )
        else:
            # Nothing was parked, so there is no prior request to resume. If a
            # quotation is pending, though, the name that just arrived is the
            # detail it was waiting for, and the quote route below owes an
            # answer -- not "Thank you, Alex. How can I help you?"
            if (
                not _has_detail_capture_handoff_blocker(combined_text)
                and not has_pending_quote_selection
            ):
                if (
                    _has_active_sales_detail_capture_context(
                        conv,
                        deps.recent_history,
                    )
                    and not quote_reply_updates_purchase_selection
                    and _is_neutral_detail_capture_update(
                        text=combined_text,
                        customer_details=current_quote_customer_details,
                        sales_memory_updates=current_sales_memory_updates,
                    )
                ):
                    return build_declared_static_response(
                        _detail_capture_acknowledgement(
                            current_quote_customer_details,
                            current_sales_memory_updates,
                        ),
                        route="detail-capture",
                        build_static_response=_build_static_response,
                        allow_product_media=False,
                    )
                return build_declared_static_response(
                    f"Thank you, {current_quote_customer_details['name']}. "
                    "How can I help you with your office furniture requirement?",
                    route="name-capture",
                    build_static_response=_build_static_response,
                    allow_product_media=False,
                )

    if unconsented_quote_details:
        return build_declared_static_response(
            (
                "I have kept the selected items, but I will collect customer and "
                "delivery details only after you explicitly confirm that you want "
                "a formal quotation."
            ),
            route="quote-consent-required",
            build_static_response=_build_static_response,
            allow_product_media=False,
        )

    offer_quote_for_turn = await _quote_offer_allowed_for_turn(
        db,
        conv,
        combined_text,
    )
    if current_sales_opportunity_request is not None and not offer_quote_for_turn:
        current_sales_opportunity_request = replace(
            current_sales_opportunity_request,
            quote_consent=quote_workflow_from_metadata(conv.metadata_).consent,
        )

    if current_sales_opportunity_request is not None:
        opportunity_result = await _create_or_reuse_sales_opportunity(
            deps,
            title=_sales_opportunity_title(deps),
            amount=current_sales_opportunity_request.amount,
            allow_reuse=True,
        )
        response_model = (
            "sales-opportunity"
            if opportunity_result.verified
            else "sales-opportunity-unverified"
        )
        return await _verified_prose_response(
            verified_text=_sales_opportunity_response(
                current_sales_opportunity_request,
                opportunity_result,
                language=str(conv.language),
            ),
            deps=deps,
            model_name=response_model,
            customer_text=combined_text,
            build_static_response=_build_static_response,
            build_llm_response=_build_llm_response,
            run_prose_agent=_run_prose_agent,
        )

    if (
        not quote_detail_context_active
        and not quote_reply_updates_purchase_selection
        and _has_active_sales_detail_capture_context(conv, deps.recent_history)
        # An acknowledgement is not an answer. The customer's opening question
        # is stored while the name gate runs, and on 2026-08-09 R03 showed what
        # happens when this route fires on the turn that completes the gate:
        # "hi do u have ch616 in black" -> name gate -> "Omar" -> "Thanks, I've
        # noted name: Omar." The question was never served and the turn carried
        # nothing. Reading the metadata here is too late -- the pending request
        # has already been consumed by this point -- so the test is whether this
        # turn is the one that completed the gate.
        and not name_gate_completion_reply
        # The same rule, generalised on 2026-08-10 when the gate was removed. A
        # customer answering the last detail a pending quotation was waiting for
        # is owed the quotation, not "Thanks, I've noted name: Alex." The quote
        # route below either completes it or asks for what is still missing
        # while carrying the verified price and stock, and both beat a receipt.
        and not has_pending_quote_selection
        and _is_neutral_detail_capture_update(
            text=combined_text,
            customer_details=current_quote_customer_details,
            sales_memory_updates=current_sales_memory_updates,
        )
    ):
        return build_declared_static_response(
            _detail_capture_acknowledgement(
                current_quote_customer_details,
                current_sales_memory_updates,
            ),
            route="detail-capture",
            build_static_response=_build_static_response,
            allow_product_media=False,
        )

    resolved_pending_reference = await _pending_reference_route_for_turn(
        db=db,
        conversation=conv,
        recent_history=deps.recent_history,
        combined_text=combined_text,
        masked_text=masked_text,
    )
    order_quote_response = None
    if not unconsented_quote_details:
        order_quote_response = await _order_quote_route_for_turn(
            phase="pre_policy",
            db=db,
            conversation=conv,
            deps=deps,
            masked_text=masked_text,
            combined_text=combined_text,
            is_first_turn=is_first_turn,
            pending_quote_selection_at_start=pending_quote_selection_at_start,
            pending_exact_quote_followup_candidates=(
                pending_exact_quote_followup_candidates
            ),
            current_quote_intent_frame=current_quote_intent_frame,
            current_quote_customer_details=current_quote_customer_details,
            assistant_supports_quote_resume=assistant_supports_quote_resume,
            quote_detail_context_active=quote_detail_context_active,
            has_pending_quote_selection=has_pending_quote_selection,
            pending_reference_route=resolved_pending_reference,
            zoho_client=zoho_client,
            crm_context=crm_context,
            trace_enabled=dialogue_kernel_trace_enabled,
            build_static_response=_build_static_response,
            clear_verified_policy_repair_state=_clear_verified_policy_repair_state,
            offer_quote=offer_quote_for_turn,
            resumed_name_gate_intent=resumed_name_gate_intent,
            # The pre-policy phase used to run before the model existed, so it
            # could only ever send route text. The runtime is memoised now, so
            # selection-confirmation gets its sentence written here too
            # (tj-swgu.3); a turn that never reaches the model still builds
            # nothing.
            run_agent=_run_agent,
            build_llm_response=_build_llm_response,
            run_prose_agent=_run_prose_agent,
        )
    if order_quote_response is not None:
        return order_quote_response

    if latency_trace is not None and context_started is not None:
        latency_trace.finish_phase("llm_context", context_started)

    # Pre-compute FAQ search results (once per message, not per tool roundtrip)
    faq_started = latency_trace.start_phase() if latency_trace is not None else None
    try:
        from src.rag.pipeline import search_knowledge

        deps.faq_context = await search_knowledge(
            db, masked_text, embedding_engine, limit=3
        )
    except Exception:
        logger.warning("FAQ knowledge base search failed", exc_info=True)
    finally:
        if latency_trace is not None and faq_started is not None:
            latency_trace.finish_phase("faq_rag", faq_started)

    behavior_started = (
        latency_trace.start_phase() if latency_trace is not None else None
    )
    try:
        metadata = conv.metadata_ if isinstance(conv.metadata_, dict) else {}
        segment = None
        if crm_context:
            segment = crm_context.get("Segment") or crm_context.get("segment")
        segment = segment or metadata.get("segment")
        rules = await search_behavior_rules(
            db,
            context=BehaviorRuleSearchContext(
                message=masked_text,
                stage=str(conv.sales_stage) if conv.sales_stage else None,
                language=str(conv.language) if conv.language else None,
                segment=str(segment) if segment else None,
            ),
            embedding_engine=embedding_engine,
        )
        deps.behavior_rules = [rule_to_applied_dict(rule) for rule in rules]
        await _store_applied_bot_rules(db, conv, deps.behavior_rules)
    except Exception:
        logger.warning("Bot behavior rule search failed", exc_info=True)
    finally:
        if latency_trace is not None and behavior_started is not None:
            latency_trace.finish_phase("behavior_rag", behavior_started)

    policy_decision = evaluate_verified_answer_policy(
        masked_text, deps.faq_context or []
    )
    if _should_override_policy_for_catalog_fact_query(
        combined_text,
        policy_decision,
    ):
        policy_decision = replace(
            policy_decision,
            question_class="product",
            policy_action="allow",
            requires_manager_handoff=False,
            sales_fallback_intent=None,
        )
    if (
        assistant_offered_quote_selection
        and quote_offer_reply_has_consultative_priority
        and not _has_detail_capture_handoff_blocker(combined_text)
    ):
        policy_decision = replace(
            policy_decision,
            question_class="product",
            policy_action="allow",
            requires_manager_handoff=False,
            sales_fallback_intent=None,
        )
    product_preference_frame_match = _dialogue_kernel_product_preference_match(
        dialogue_kernel_result
    )

    try:
        from src.core.config import get_system_config

        db_model_main, dynamic_model = await _ensure_model_runtime()

        def _build_verified_catalog_recovery_response(
            recovery_text: str,
            recovery_traces: tuple[RuntimeToolTraceT, ...],
            *,
            run_deps: SalesDepsT,
            usage: Any,
            cost: float | None,
            route_suffix: str = "verified-catalog-functional-failure",
            allow_product_media: bool = True,
        ) -> LLMResponseT:
            response_model = f"{db_model_main}|{route_suffix}"
            rendered = _render_customer_reply(
                recovery_text,
                response_deps=run_deps,
                provenance="deterministic_replacement",
                model_name=response_model,
            )
            record_legacy_route(
                conv,
                dialogue_kernel_result,
                legacy_route=response_model,
            )
            _capture_expected_answer_frames_from_assistant_response(
                conv,
                response_text=rendered.text,
                dialogue_kernel_mode=dialogue_kernel_mode,
            )
            return _response_from_rendered_reply(
                rendered,
                tokens_in=usage.input_tokens,
                tokens_out=usage.output_tokens,
                cost=cost,
                model=response_model,
                usage_provenance="provider_reported",
                deferred_product_media=_deferred_product_media_for_response(
                    run_deps,
                    allow_product_media=allow_product_media,
                    response_text=rendered.text,
                ),
                tool_traces=recovery_traces,
            )

        if (
            not policy_decision.is_order_status
            and policy_decision.sales_fallback_intent is not None
        ):
            await _clear_verified_policy_repair_state()
            return build_declared_static_response(
                build_sales_fallback_response(
                    policy_decision.sales_fallback_intent,
                    str(deps.conversation.language),
                ),
                route="sales-fallback",
                build_static_response=_build_static_response,
                model_prefix=db_model_main,
            )

        order_quote_response = None
        if not unconsented_quote_details:
            order_quote_response = await _order_quote_route_for_turn(
                phase="post_policy",
                db=db,
                conversation=conv,
                deps=deps,
                masked_text=masked_text,
                combined_text=combined_text,
                is_first_turn=is_first_turn,
                pending_quote_selection_at_start=pending_quote_selection_at_start,
                pending_exact_quote_followup_candidates=(
                    pending_exact_quote_followup_candidates
                ),
                current_quote_intent_frame=current_quote_intent_frame,
                current_quote_customer_details=current_quote_customer_details,
                assistant_supports_quote_resume=assistant_supports_quote_resume,
                quote_detail_context_active=quote_detail_context_active,
                has_pending_quote_selection=has_pending_quote_selection,
                pending_reference_route=resolved_pending_reference,
                zoho_client=zoho_client,
                crm_context=crm_context,
                trace_enabled=dialogue_kernel_trace_enabled,
                build_static_response=_build_static_response,
                clear_verified_policy_repair_state=(
                    _clear_verified_policy_repair_state
                ),
                db_model_main=db_model_main,
                dynamic_model=dynamic_model,
                run_agent=_run_agent,
                build_llm_response=_build_llm_response,
                run_prose_agent=_run_prose_agent,
                has_escalation=_has_escalation,
                quote_brief_confirmation_details=quote_brief_confirmation_details,
                offer_quote=offer_quote_for_turn,
                resumed_name_gate_intent=resumed_name_gate_intent,
            )
        if order_quote_response is not None:
            return order_quote_response

        if (
            not policy_decision.is_order_status
            and policy_decision.question_class == "service_low_risk"
            and policy_decision.policy_action == "allow"
            and is_quote_or_proposal_request(masked_text)
            and not _has_explicit_quote_hold(masked_text)
        ):
            await _clear_verified_policy_repair_state()
            return build_declared_static_response(
                build_quote_or_proposal_clarification_response(
                    str(deps.conversation.language)
                ),
                route="proposal-clarify",
                build_static_response=_build_static_response,
                model_prefix=db_model_main,
            )

        if not policy_decision.is_order_status and (
            _is_mixed_product_service_request(masked_text)
            or _is_mixed_product_service_request(combined_text)
        ):
            result = await _run_agent(
                replace(
                    deps,
                    tool_mode="full",
                    runtime_directives=(
                        *deps.runtime_directives,
                        *MIXED_PRODUCT_SERVICE_DIRECTIVES,
                    ),
                )
            )
            await _clear_verified_policy_repair_state()
            return _build_llm_response(result, db_model_main)

        if not policy_decision.is_order_status and _is_service_confirmation_reply(
            combined_text,
            deps.recent_history,
        ):
            from src.integrations.notifications.escalation import (
                notify_manager_escalation,
            )
            from src.schemas.common import EscalationType

            if not is_active_human_handoff(deps.conversation.escalation_status):
                await notify_manager_escalation(
                    conversation=deps.conversation,
                    reason=(
                        "Customer confirmed they want assembly/installation service "
                        "after the assistant asked a service confirmation question. "
                        "Manager should confirm service conditions and next steps."
                    ),
                    recent_messages=deps.recent_history or [],
                    db=deps.db,
                    escalation_type=EscalationType.GENERAL,
                )
            await _clear_verified_policy_repair_state()
            return build_declared_static_response(
                _service_confirmation_handoff_text(),
                route="service-confirmation-handoff",
                build_static_response=_build_static_response,
                model_prefix=db_model_main,
                allow_product_media=False,
            )

        if (
            not policy_decision.is_order_status
            and not (
                policy_decision.question_class == "service_high_risk"
                and policy_decision.policy_action == "handoff"
            )
            and "showroom" in policy_decision.matched_topics
        ):
            await _clear_verified_policy_repair_state()
            return build_declared_static_response(
                _showroom_location_response(str(deps.conversation.language)),
                route="showroom-location",
                build_static_response=_build_static_response,
                model_prefix=db_model_main,
                allow_product_media=False,
            )

        if (
            not policy_decision.is_order_status
            and policy_decision.sales_fallback_intent is None
            and (
                product_preference_frame_match is not None
                or _is_product_preference_answer(combined_text, deps.recent_history)
                or _is_product_preference_answer(masked_text, deps.recent_history)
            )
        ):
            frame_directives = (
                _product_preference_frame_directives(product_preference_frame_match)
                if product_preference_frame_match is not None
                else ()
            )
            result = await _run_agent(
                replace(
                    deps,
                    tool_mode="full",
                    runtime_directives=(
                        *deps.runtime_directives,
                        *PRODUCT_PREFERENCE_ANSWER_DIRECTIVES,
                        *frame_directives,
                    ),
                )
            )
            await _clear_verified_policy_repair_state()
            return _build_llm_response(result, db_model_main)

        policy_action = policy_decision.policy_action
        if not policy_decision.is_order_status and policy_action == "clarify":
            repair_state = _get_verified_policy_repair_state()
            repair_count = (
                repair_state.get("count") if repair_state is not None else None
            )
            if (
                repair_state is not None
                and repair_state.get("kind") == "benign_no_match"
                and isinstance(repair_count, int)
                and repair_count >= 1
            ):
                policy_action = "handoff"
                await _clear_verified_policy_repair_state()
            else:
                await _set_verified_policy_repair_state("benign_no_match", 1)
                return build_declared_static_response(
                    build_clarification_response(str(deps.conversation.language)),
                    route="verified-policy-clarify",
                    build_static_response=_build_static_response,
                    model_prefix=db_model_main,
                )

        if (
            not policy_decision.is_order_status
            and policy_decision.sales_fallback_intent is not None
        ):
            await _clear_verified_policy_repair_state()
            return build_declared_static_response(
                build_sales_fallback_response(
                    policy_decision.sales_fallback_intent,
                    str(deps.conversation.language),
                ),
                route="sales-fallback",
                build_static_response=_build_static_response,
                model_prefix=db_model_main,
            )

        if not policy_decision.is_order_status and policy_action == "handoff":
            from src.integrations.notifications.escalation import (
                notify_manager_escalation,
            )
            from src.schemas.common import EscalationType

            await notify_manager_escalation(
                conversation=deps.conversation,
                reason=build_service_handoff_reason(masked_text, policy_decision),
                recent_messages=deps.recent_history or [],
                db=deps.db,
                escalation_type=EscalationType.GENERAL,
            )
            await _clear_verified_policy_repair_state()
            return await _build_policy_handoff_response(
                db_model_main,
                str(deps.conversation.language),
                build_service_handoff_response(
                    policy_decision, str(deps.conversation.language)
                ),
            )

        if not policy_decision.is_order_status and policy_decision.question_class in {
            "service_low_risk",
            "service_high_risk",
        }:
            result = await _run_agent(
                replace(
                    deps,
                    tool_mode="service_policy",
                    runtime_directives=(
                        *deps.runtime_directives,
                        *build_service_runtime_directives(policy_decision),
                    ),
                )
            )
            await _clear_verified_policy_repair_state()
            return _build_llm_response(result, db_model_main)

        verified_catalog_plan = await _try_verified_catalog_plan(deps)
        if verified_catalog_plan is not None:
            fallback_text, plan_traces = verified_catalog_plan
            decision_directive = _catalog_decision_runtime_directive(deps)
            if decision_directive is None:
                await _clear_verified_policy_repair_state()
                return build_declared_static_response(
                    fallback_text,
                    route="verified-catalog-functional-failure",
                    build_static_response=_build_static_response,
                    model_prefix=db_model_main,
                    response_deps=deps,
                    allow_product_media=False,
                    tool_traces=plan_traces,
                )
            run_deps = replace(
                deps,
                tool_mode="catalog_materialization",
                runtime_directives=(
                    *deps.runtime_directives,
                    decision_directive,
                ),
            )
            try:
                result = await _run_agent(run_deps)
            except (UnexpectedModelBehavior, TimeoutError):
                await _clear_verified_policy_repair_state()
                return _build_verified_catalog_recovery_response(
                    fallback_text,
                    plan_traces,
                    run_deps=run_deps,
                    usage=failed_run_usage or RunUsage(),
                    cost=dynamic_model.provider_cost_snapshot(),
                    route_suffix="verified-catalog-functional-failure",
                    allow_product_media=False,
                )
            decision_provenance: Literal["model", "model_repaired"] = "model"
            defects = _catalog_decision_defects(
                unmask_pii(result.output, pii_map), run_deps
            )
            if defects:
                # One repair pass naming the defect, then the template. The
                # check is right to fire; replacing the whole reply is what
                # dropped a product family on S05 (tj-swgu.2).
                repair_directive = _catalog_decision_repair_directive(defects)
                repaired = None
                if repair_directive is not None:
                    repair_deps = replace(
                        run_deps,
                        runtime_directives=(
                            *run_deps.runtime_directives,
                            repair_directive,
                        ),
                    )
                    try:
                        candidate = await _run_agent(repair_deps)
                    except (UnexpectedModelBehavior, TimeoutError):
                        candidate = None
                    if candidate is not None and _catalog_decision_output_is_valid(
                        unmask_pii(candidate.output, pii_map), repair_deps
                    ):
                        repaired = candidate
                if repaired is None:
                    usage = result.usage() or RunUsage()
                    usage_telemetry = get_llm_usage_telemetry(result)
                    await _clear_verified_policy_repair_state()
                    return _build_verified_catalog_recovery_response(
                        fallback_text,
                        plan_traces,
                        run_deps=run_deps,
                        usage=usage,
                        cost=(
                            usage_telemetry.cost
                            if usage_telemetry is not None
                            else dynamic_model.provider_cost_snapshot()
                        ),
                        route_suffix="verified-catalog-functional-failure",
                        allow_product_media=False,
                    )
                result = repaired
                decision_provenance = "model_repaired"
            await _clear_verified_policy_repair_state()
            response = _build_llm_response(
                result,
                f"{db_model_main}|verified-catalog-plan",
                response_deps=deps,
                allow_product_media=False,
                text_provenance=decision_provenance,
            )
            return replace(response, tool_traces=plan_traces)

        run_deps = deps
        turn_directives = _turn_runtime_directives(
            combined_text,
            masked_text,
            sales_stage=str(getattr(deps.conversation, "sales_stage", "") or ""),
        )
        if turn_directives:
            run_deps = replace(
                deps,
                runtime_directives=(
                    *deps.runtime_directives,
                    *turn_directives,
                ),
            )
        try:
            result = await _run_agent(run_deps)
        except (UnexpectedModelBehavior, TimeoutError):
            explicit_quote_hold = _has_explicit_quote_hold(
                masked_text
            ) or _has_explicit_quote_hold(combined_text)
            await _complete_verified_cross_sell_for_recovery(
                RunContext(
                    deps=run_deps,
                    retry=0,
                    messages=history,
                    prompt=masked_text,
                    model=dynamic_model,
                    usage=failed_run_usage or RunUsage(),
                ),
                explicit_quote_hold=explicit_quote_hold,
            )
            recovery_traces = tuple(run_deps.recovery_tool_traces)
            recovery_text = _materialize_verified_catalog_recovery(
                run_deps,
                recovery_traces,
                explicit_quote_hold=explicit_quote_hold,
            )
            if recovery_text is None:
                raise
            await _clear_verified_policy_repair_state()
            usage = failed_run_usage or RunUsage()
            return _build_verified_catalog_recovery_response(
                recovery_text,
                recovery_traces,
                run_deps=run_deps,
                usage=usage,
                cost=dynamic_model.provider_cost_snapshot(),
            )
        recovery_traces = tuple(run_deps.recovery_tool_traces)
        recovery_text = _materialize_verified_catalog_recovery(
            run_deps,
            recovery_traces,
            explicit_quote_hold=(
                _has_explicit_quote_hold(masked_text)
                or _has_explicit_quote_hold(combined_text)
            ),
        )
        if recovery_text is not None and not _catalog_recovery_output_is_valid(
            unmask_pii(result.output, pii_map), run_deps
        ):
            await _clear_verified_policy_repair_state()
            usage = result.usage() or RunUsage()
            usage_telemetry = get_llm_usage_telemetry(result)
            return _build_verified_catalog_recovery_response(
                recovery_text,
                recovery_traces,
                run_deps=run_deps,
                usage=usage,
                cost=(
                    usage_telemetry.cost
                    if usage_telemetry is not None
                    else dynamic_model.provider_cost_snapshot()
                ),
            )
        verified_catalog_facts = _materialize_verified_catalog_facts(run_deps)
        if verified_catalog_facts is not None:
            repair_payload = json.dumps(
                {
                    "candidate_response": str(result.output),
                    "verified_catalog_facts": verified_catalog_facts,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            repair_deps = replace(
                run_deps,
                tool_mode="catalog_materialization",
                runtime_directives=(
                    *run_deps.runtime_directives,
                    _claim_contract_directive(repair_payload),
                ),
            )
            repaired_result = await _run_agent(repair_deps)
            repaired_result, contract = await _enforce_claim_contract(
                repaired_result,
                repair_deps=repair_deps,
                repair_payload=repair_payload,
                run_agent=_run_agent,
            )
            _log_claim_contract(contract, run_deps.conversation.id, scope="requested")
            await _clear_verified_policy_repair_state()
            return replace(
                _build_llm_response(
                    repaired_result,
                    db_model_main,
                    response_deps=repair_deps,
                    text_provenance="model_repaired",
                    route_suffix="catalog-fact-repair",
                ),
                tool_traces=recovery_traces,
            )
        if claim_contract_every_catalog_turn:
            verified_result, volunteered = await _verify_volunteered_claims(
                result,
                run_deps=run_deps,
                run_agent=_run_agent,
            )
            _log_claim_contract(
                volunteered, run_deps.conversation.id, scope="volunteered"
            )
            if verified_result is not result:
                await _clear_verified_policy_repair_state()
                return replace(
                    _build_llm_response(
                        verified_result,
                        db_model_main,
                        response_deps=run_deps,
                        text_provenance="model_repaired",
                        route_suffix="claim-contract-turn",
                    ),
                    tool_traces=recovery_traces,
                )
        await _clear_verified_policy_repair_state()
        return replace(
            _build_llm_response(
                result,
                db_model_main,
                response_deps=run_deps,
            ),
            tool_traces=recovery_traces,
        )

    except Exception:
        conv_id_str = str(conv.id) if conv else "unknown"
        phone_str = str(conv.phone) if conv else "unknown"
        logger.exception(
            "LLM generation failed for conv_id=%s phone=%s",
            conv_id_str,
            phone_str,
        )
        # NOTE: We do not surface exc details in model= to avoid info leakage
        db_model_label = db_model_main if "db_model_main" in locals() else "unknown"
        response_model = f"{db_model_label}|error"
        rendered = _render_customer_reply(
            "I apologize, but I am experiencing a temporary issue. Please try again in a moment.",
            response_deps=deps,
            provenance="deterministic_static",
            model_name=response_model,
        )
        return _response_from_rendered_reply(
            rendered,
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            model=response_model,
            usage_provenance="deterministic_static",
        )
