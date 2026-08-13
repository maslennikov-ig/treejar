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
from dataclasses import dataclass, replace
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
    opening_wants_a_price_anchor,
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
from src.llm.repair_judge import (
    RepairJudgeEvidence,
    RepairJudgeRunner,
    RepairJudgeTrace,
    repair_manager_handoff_text,
    review_flagged_reply_with_pii,
    unavailable_repair_judge_trace,
)
from src.llm.response_policy import (
    AskKind,
    ReplyPolicyState,
    permitted_asks_for_turn,
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
        ExactQuoteCandidate as ExactQuoteCandidateT,
    )
    from src.llm.response_runtime import (
        LLMResponse as LLMResponseT,
    )
    from src.llm.response_runtime import (
        ProductMediaPayload as ProductMediaPayloadT,
    )
    from src.llm.response_runtime import (
        SalesOpportunityRequest as SalesOpportunityRequestT,
    )
    from src.llm.safety import (
        OpenRouterTelemetryChatModel as OpenAIChatModelT,
    )
    from src.llm.verified_answers import (
        VerifiedAnswerDecision as VerifiedAnswerDecisionT,
    )
    from src.models.conversation import Conversation as ConversationT
    from src.rag.embeddings import EmbeddingEngine
    from src.services.chat_latency import ChatLatencyTrace
    from src.services.runtime_execution_evidence import (
        RuntimeToolTrace as RuntimeToolTraceT,
    )


logger = logging.getLogger("src.llm.engine")


# `tj-rt7w.10`. These three closed over nothing at all: they were nested only
# because everything was. At module level they are unit-testable, and Mypy
# checks their callers.
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


# `tj-rt7w.10`. The repair-state trio closed over exactly `conv` and `db`, so it
# is state passed in, not state captured. Twenty call sites -- several handing
# the clearer to the order/quote adapter as a `Callable[[], Awaitable[None]]` --
# keep their zero-argument shape through a `partial` bound once the conversation
# is loaded.
def _verified_policy_repair_state(conv: ConversationT) -> dict[str, int | str] | None:
    metadata = conv.metadata_ if isinstance(conv.metadata_, dict) else {}
    state = metadata.get(engine.VERIFIED_POLICY_REPAIR_KEY)
    if not isinstance(state, dict):
        return None
    kind = state.get("kind")
    count = state.get("count")
    if not isinstance(kind, str) or not isinstance(count, int):
        return None
    return {"kind": kind, "count": count}


async def _store_verified_policy_repair_state(
    conv: ConversationT, db: AsyncSession, kind: str, count: int
) -> None:
    metadata = dict(conv.metadata_ or {})
    metadata[engine.VERIFIED_POLICY_REPAIR_KEY] = {"kind": kind, "count": count}
    conv.metadata_ = metadata
    await db.flush()


async def _drop_verified_policy_repair_state(
    conv: ConversationT, db: AsyncSession
) -> None:
    metadata = dict(conv.metadata_ or {})
    if engine.VERIFIED_POLICY_REPAIR_KEY not in metadata:
        return
    metadata.pop(engine.VERIFIED_POLICY_REPAIR_KEY, None)
    conv.metadata_ = metadata
    await db.flush()


class _LazyModelRuntime:
    """One chat model per turn, built the first time a run needs it.

    `tj-rt7w.10`. This was a closure over a `nonlocal` -- the memo and the thing
    it memoized were the same name, so neither could be read or tested on its
    own. `OpenAIChatModel` stays engine-resolved because the suite patches it
    there.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._runtime: tuple[str, OpenAIChatModelT] | None = None

    async def get(self) -> tuple[str, OpenAIChatModelT]:
        if self._runtime is None:
            from src.core.config import get_system_config

            name = model_name_for_path(
                PATH_CORE_CHAT,
                await get_system_config(
                    self._db, "openrouter_model_main", settings.openrouter_model_main
                ),
            )
            self._runtime = (
                name,
                engine.OpenAIChatModel(
                    name,
                    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
                    settings=model_settings_for_path(PATH_CORE_CHAT, model_name=name),
                ),
            )
        return self._runtime


async def _run_prose_agent_on(
    model_runtime: _LazyModelRuntime, directive: str, run_deps: SalesDepsT
) -> Any:
    """Run the rewrite on its own, away from the product system prompt."""

    runtime_model_name, runtime_model = await model_runtime.get()
    return await run_agent_with_safety(
        engine.prose_agent,
        PATH_CORE_CHAT,
        user_prompt=directive,
        deps=run_deps,
        message_history=[],
        model=runtime_model,
        model_name=runtime_model_name,
        usage=RunUsage(),
    )


@dataclass
class _Turn:
    """The state one turn shares, and the operations that read and write it.

    `tj-rt7w.10`. These were fourteen locals and six closures inside a
    two-thousand-line function. Several of the locals are reassigned while the
    turn runs -- the name gate replaces the customer text and rebuilds `deps` --
    so nothing could be bound early and no phase could be lifted out. Named
    fields on one object carry the same values across function boundaries and
    say, for the first time, what a turn actually consists of.

    `opening_anchor_line` was a one-element list for exactly this reason: a
    closure cannot assign to an enclosing local. It is a field now.
    """

    # Fixed for the turn.
    pending_reference_route: Callable[..., Awaitable[PendingReferenceRoute]]
    order_quote_route: Callable[..., Awaitable[LLMResponseT | None]]
    db: AsyncSession
    redis: Any
    conversation_id: UUID
    embedding_engine: EmbeddingEngine
    zoho_client: ZohoInventoryClient
    messaging_client: MessagingProvider
    crm_client: ZohoCRMClient | None
    source_message_id: str | None
    latency_trace: ChatLatencyTrace | None
    context_started: float | None
    conv: ConversationT
    crm_context: dict[str, str] | None
    pii_map: dict[str, str]
    history: list[ModelRequestT | ModelResponseT]
    is_first_turn: bool
    model_runtime: _LazyModelRuntime
    current_message_quote_customer_details: dict[str, str]

    # Written as the turn runs.
    combined_text: str
    masked_text: str
    recent_history: list[str]
    deps: SalesDepsT
    dialogue_kernel_mode: str = ""
    dialogue_kernel_result: DialogueKernelResultT | None = None
    opening_anchor_line: str | None = None
    name_gate_resume_customer_name: str | None = None
    failed_run_usage: RunUsageT | None = None
    permitted_asks_cache: frozenset[AskKind] | None = None

    # The verified-answer repair counter lives in conversation metadata; these
    # three keep their zero-argument shape because several call sites hand the
    # clearer to the order/quote adapter as a `Callable[[], Awaitable[None]]`.
    def repair_state(self) -> dict[str, int | str] | None:
        return _verified_policy_repair_state(self.conv)

    async def set_repair_state(self, kind: str, count: int) -> None:
        await _store_verified_policy_repair_state(self.conv, self.db, kind, count)

    async def clear_repair_state(self) -> None:
        await _drop_verified_policy_repair_state(self.conv, self.db)

    async def run_prose_agent(self, directive: str, run_deps: SalesDepsT) -> Any:
        return await _run_prose_agent_on(self.model_runtime, directive, run_deps)

    def permitted_asks(self) -> frozenset[AskKind]:
        """Compute the turn's ask contract once, before prompt or guard uses it."""

        if self.permitted_asks_cache is None:
            quote_workflow = quote_workflow_from_metadata(self.conv.metadata_)
            self.permitted_asks_cache = permitted_asks_for_turn(
                is_first_turn=self.is_first_turn,
                customer_name=self.known_customer_name() or None,
                customer_name_asked=engine._customer_name_was_asked(self.conv),
                owes_company_question=_turn_owes_the_company_question(self.deps),
                quote_consent_granted=(quote_workflow.consent is QuoteConsent.GRANTED),
                company_activity_asked_previous_turn=(
                    engine._company_activity_was_asked_previous_turn(self.conv)
                ),
            )
        return self.permitted_asks_cache

    def known_customer_name(self) -> str:
        quote_details = engine._quote_customer_details_from_metadata(self.conv)
        return (
            engine._string_value(self.name_gate_resume_customer_name)
            or engine._string_value(
                self.current_message_quote_customer_details.get("name")
            )
            or engine._string_value(quote_details.get("name"))
            or engine._string_value(self.conv.customer_name)
        )

    def render_reply(
        self,
        text: str,
        *,
        response_deps: SalesDepsT,
        provenance: ReplyProvenanceT,
        model_name: str,
    ) -> RenderedReplyT:
        quote_details = engine._quote_customer_details_from_metadata(self.conv)
        delivery_address = engine._string_value(quote_details.get("address"))
        if delivery_address and not engine._is_specific_delivery_address(
            delivery_address
        ):
            delivery_address = ""
        quote_workflow = quote_workflow_from_metadata(
            response_deps.conversation.metadata_
        )
        rendered = render_reply(
            unmask_pii(text, self.pii_map),
            state=ReplyPolicyState(
                language=str(response_deps.conversation.language),
                is_first_turn=self.is_first_turn,
                customer_name=(engine._string_value(self.conv.customer_name) or None),
                current_message_customer_name=(self.known_customer_name() or None),
                customer_name_asked=engine._customer_name_was_asked(self.conv),
                permitted_asks=self.permitted_asks(),
                anchor_line=self.opening_anchor_line,
                company=engine._string_value(quote_details.get("company")) or None,
                customer_type=(
                    engine._string_value(quote_details.get("customer_type")) or None
                ),
                delivery_address=delivery_address or None,
                owes_company_question=_turn_owes_the_company_question(response_deps),
                company_activity_asked_previous_turn=(
                    engine._company_activity_was_asked_previous_turn(self.conv)
                ),
                quote_consent_granted=(quote_workflow.consent is QuoteConsent.GRANTED),
                inventory_confirmed=response_deps.inventory_confirmed,
                grounded_amounts=grounded_amounts_for_turn(
                    response_deps,
                    customer_text=self.combined_text,
                ),
                required_tool_disclosure=(
                    engine._string_value(response_deps.required_cross_sell_disclosure)
                    or None
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

    def _record_reply_on_conversation(
        self, model_name: str, response_text: str
    ) -> None:
        if model_name.startswith("dialogue-kernel|"):
            return
        record_legacy_route(
            self.conv,
            self.dialogue_kernel_result,
            legacy_route=model_name,
        )
        engine._capture_expected_answer_frames_from_assistant_response(
            self.conv,
            response_text=response_text,
            dialogue_kernel_mode=self.dialogue_kernel_mode,
        )

    def build_llm_response(
        self,
        result: Any,
        model_name: str,
        *,
        response_deps: SalesDepsT | None = None,
        allow_product_media: bool = True,
        text_provenance: Literal["model", "model_repaired"] = "model",
        route_suffix: str | None = None,
    ) -> LLMResponseT:
        response_deps = response_deps or self.deps
        if route_suffix:
            model_name = f"{model_name}|{route_suffix}"
        rendered = self.render_reply(
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

    def build_static_response(
        self,
        text: str,
        model_name: str,
        *,
        response_deps: SalesDepsT | None = None,
        allow_product_media: bool = True,
        tool_traces: tuple[RuntimeToolTraceT, ...] = (),
    ) -> LLMResponseT:
        response_deps = response_deps or self.deps
        rendered = self.render_reply(
            text,
            response_deps=response_deps,
            provenance="deterministic_static",
            model_name=model_name,
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

    async def build_policy_handoff_response(
        self,
        model_name: str,
        decision_language: str,
        decision_text: str,
        *,
        policy_decision: VerifiedAnswerDecisionT,
    ) -> LLMResponseT:
        final_text = (
            decision_text
            if decision_text
            else build_service_handoff_response(policy_decision, decision_language)
        )
        response_model = f"{model_name}|verified-policy"
        rendered = self.render_reply(
            final_text,
            response_deps=self.deps,
            provenance="deterministic_static",
            model_name=response_model,
        )
        return _response_from_rendered_reply(
            rendered,
            tokens_in=0,
            tokens_out=0,
            cost=None,
            model=response_model,
            usage_provenance="deterministic_static",
            deferred_product_media=_deferred_product_media_for_response(
                self.deps,
                allow_product_media=False,
                response_text=rendered.text,
            ),
        )

    def build_replacement_response(
        self,
        text: str,
        tool_traces: tuple[RuntimeToolTraceT, ...],
        *,
        run_deps: SalesDepsT,
        usage: Any,
        cost: float | None,
        model_name: str,
        allow_product_media: bool = True,
    ) -> LLMResponseT:
        """The verified text the catalog planner prepared, sent instead of the model's."""

        rendered = self.render_reply(
            text,
            response_deps=run_deps,
            provenance="deterministic_replacement",
            model_name=model_name,
        )
        return _response_from_rendered_reply(
            rendered,
            tokens_in=usage.input_tokens,
            tokens_out=usage.output_tokens,
            cost=cost,
            model=model_name,
            usage_provenance="provider_reported",
            deferred_product_media=_deferred_product_media_for_response(
                run_deps,
                allow_product_media=allow_product_media,
                response_text=rendered.text,
            ),
            tool_traces=tool_traces,
        )

    async def run_agent(self, run_deps: SalesDepsT) -> Any:
        # Keep the exact dependency object that tools mutate. Copying it here
        # lost inventory/product evidence before the reply was rendered.
        run_deps.permitted_asks = self.permitted_asks()
        runtime_model_name, runtime_model = await self.model_runtime.get()
        agent_started = (
            self.latency_trace.start_phase() if self.latency_trace is not None else None
        )
        run_usage = RunUsage()
        try:
            result = await run_agent_with_safety(
                engine.sales_agent,
                PATH_CORE_CHAT,
                user_prompt=self.masked_text,
                deps=run_deps,
                message_history=self.history,
                model=runtime_model,
                model_name=runtime_model_name,
                usage=run_usage,
            )
            if run_deps.inventory_confirmed:
                self.deps.inventory_confirmed = True
            return result
        except (UnexpectedModelBehavior, TimeoutError):
            self.failed_run_usage = run_usage
            raise
        finally:
            if self.latency_trace is not None and agent_started is not None:
                self.latency_trace.finish_phase("model_tools", agent_started)


async def _finalize_turn_response(
    turn: _Turn,
    response: LLMResponseT,
    *,
    runner: RepairJudgeRunner | None = None,
) -> LLMResponseT:
    """Run flagged text through the judge, then record the actual final reply."""

    if response.repair_flags:
        state = response.repair_policy_state
        if state is None:
            raise RuntimeError("flagged reply is missing its policy state")

        try:
            judged = await review_flagged_reply_with_pii(
                response.text,
                state=state,
                flags=response.repair_flags,
                evidence=RepairJudgeEvidence(
                    language=state.language,
                    customer_message=turn.masked_text,
                    inventory_confirmed=state.inventory_confirmed,
                    grounded_amounts=tuple(
                        str(amount) for amount in (state.grounded_amounts or ())
                    ),
                    executed_tool_names=tuple(sorted(turn.deps.executed_tool_names)),
                    quote_consent_granted=state.quote_consent_granted,
                ),
                provenance=response.text_provenance,
                pii_map=turn.pii_map,
                runner=runner,
            )
        except Exception as error:
            logger.warning(
                "Repair judge unavailable; using manager handoff: error_type=%s",
                type(error).__name__,
            )
            response.repair_trace = unavailable_repair_judge_trace(
                response.repair_flags, error=error
            )
        else:
            response.text = judged.text
            response.text_provenance = judged.provenance
            response.repair_flags = judged.remaining_flags
            response.repair_trace = judged.trace
            if judged.emitted_asks is not None:
                response.emitted_asks = judged.emitted_asks

        if response.repair_trace is not None and response.repair_trace.requires_handoff:
            await _apply_repair_manager_handoff(
                turn,
                response,
                state=state,
                trace=response.repair_trace,
            )

        response.deferred_product_media = tuple(
            item
            for item in response.deferred_product_media
            if _product_media_is_referenced(item, response.text)
        )
        if response.repair_trace is not None:
            trace = response.repair_trace
            logger.info(
                "Repair judge completed: model=%s answer=%s flags=%d "
                "calls=%d approvals=%d corrections=%d cannot_fix=%d "
                "rejected=%d fallbacks=%d provider_failures=%d "
                "requires_handoff=%s",
                trace.model,
                trace.answer,
                trace.counts.flags,
                trace.counts.calls,
                trace.counts.approvals,
                trace.counts.corrections,
                trace.counts.cannot_fix,
                trace.counts.rejected_corrections,
                trace.counts.fallbacks,
                trace.counts.provider_failures,
                trace.requires_handoff,
            )

    turn._record_reply_on_conversation(response.model, response.text)
    if AskKind.CUSTOMER_NAME in response.emitted_asks:
        # This is selected-output metadata from the policy chain. A permitted
        # ask folded away before delivery must not close the persistent slot.
        engine._record_customer_name_asked(turn.deps.conversation)
    if AskKind.COMPANY_ACTIVITY in response.emitted_asks:
        engine._record_company_activity_asked(turn.deps.conversation)
    else:
        engine._clear_company_activity_asked(turn.deps.conversation)
    return response


def _repair_manager_handoff_reason(trace: RepairJudgeTrace) -> str:
    guards = ",".join(sorted({flag.guard_name for flag in trace.flags})) or "unknown"
    outcome = trace.rejection_reason or trace.answer
    return (
        "Repair judge fallback: "
        f"outcome={outcome}; model={trace.model}; guards={guards}."
    )


async def _apply_repair_manager_handoff(
    turn: _Turn,
    response: LLMResponseT,
    *,
    state: ReplyPolicyState,
    trace: RepairJudgeTrace,
) -> None:
    """Persist a handoff, then replace the unsafe draft with a customer notice."""

    from src.integrations.notifications.escalation import notify_manager_escalation
    from src.schemas.common import EscalationType

    if not is_active_human_handoff(turn.deps.conversation.escalation_status):
        await notify_manager_escalation(
            conversation=turn.deps.conversation,
            reason=_repair_manager_handoff_reason(trace),
            recent_messages=turn.deps.recent_history or [],
            db=turn.db,
            escalation_type=EscalationType.GENERAL,
        )

    rendered = render_reply(
        repair_manager_handoff_text(state.language),
        state=state,
        provenance="deterministic_static",
    )
    if rendered.flags:
        raise RuntimeError("repair manager handoff notice raised a removal flag")
    response.text = rendered.text
    response.text_provenance = rendered.provenance
    response.repair_flags = ()
    response.emitted_asks = rendered.emitted_asks
    response.deferred_product_media = ()


@dataclass(frozen=True)
class _TurnConfig:
    """The system-config reads a turn makes, taken once at the top."""

    customer_facts_mode: str
    customer_facts_trace_enabled: bool
    customer_facts_fast_extractor_enabled: bool
    customer_facts_max_context_orders: int
    claim_contract_every_catalog_turn: bool
    dialogue_kernel_trace_enabled: bool
    dialogue_kernel_enforced_flows: str


@dataclass
class _QuoteFacts:
    """What this turn's text and the stored quote state say about the quote.

    Read once, then amended by the name gate: a resumed turn replaces the
    customer text, so the details, the intent frame, and the opportunity
    request are all re-read against the request that was parked.
    """

    customer_name_was_unknown: bool
    current_quote_customer_details: dict[str, str]
    current_quote_intent_frame: Mapping[str, Any] | None
    current_sales_memory_updates: dict[str, str]
    current_sales_opportunity_request: SalesOpportunityRequestT | None
    pending_name_gate_request: str | None
    pending_name_gate_intent: str | None
    pending_quote_selection_at_start: Mapping[str, Any] | None
    has_pending_quote_selection: bool
    pending_exact_quote_followup_candidates: tuple[ExactQuoteCandidateT, ...]
    assistant_offered_quote_selection: bool
    assistant_supports_quote_resume: bool
    quote_offer_reply_has_consultative_priority: bool
    quote_reply_updates_purchase_selection: bool
    quote_consent_granted: bool
    unconsented_quote_details: bool
    quote_detail_context_active: bool
    quote_brief_confirmation_details: dict[str, str] | None
    confirmed_quote_brief_address: str | None
    resumed_name_gate_intent: str | None = None
    name_gate_completion_reply: bool = False
    offer_quote_for_turn: bool = False


async def _read_turn_config(turn: _Turn) -> _TurnConfig:
    """Every system-config read the turn makes, taken once and named."""

    # Imported at call time, not at module import: the suite patches
    # `src.core.config.get_system_config`, and a module-level binding would
    # freeze the real one before the patch lands.
    from src.core.config import get_system_config

    turn.dialogue_kernel_mode = await get_system_config(
        turn.db,
        "dialogue_kernel_mode",
        settings.dialogue_kernel_mode,
    )
    return _TurnConfig(
        customer_facts_mode=engine._normalize_customer_facts_mode(
            await get_system_config(
                turn.db,
                "customer_facts_mode",
                settings.customer_facts_mode,
            )
        ),
        customer_facts_trace_enabled=engine._dialogue_kernel_bool_config(
            await get_system_config(
                turn.db,
                "customer_facts_trace_enabled",
                str(settings.customer_facts_trace_enabled).lower(),
            ),
            default=settings.customer_facts_trace_enabled,
        ),
        customer_facts_fast_extractor_enabled=engine._dialogue_kernel_bool_config(
            await get_system_config(
                turn.db,
                "customer_facts_fast_extractor_enabled",
                str(settings.customer_facts_fast_extractor_enabled).lower(),
            ),
            default=settings.customer_facts_fast_extractor_enabled,
        ),
        customer_facts_max_context_orders=engine._customer_facts_int_config(
            await get_system_config(
                turn.db,
                "customer_facts_max_context_orders",
                str(settings.customer_facts_max_context_orders),
            ),
            default=settings.customer_facts_max_context_orders,
            minimum=0,
            maximum=10,
        ),
        claim_contract_every_catalog_turn=_claim_contract_runs_every_catalog_turn(
            await get_system_config(
                turn.db,
                CLAIM_CONTRACT_SCOPE_KEY,
                "requested_gaps",
            )
        ),
        dialogue_kernel_trace_enabled=engine._dialogue_kernel_bool_config(
            await get_system_config(
                turn.db,
                "dialogue_kernel_trace_enabled",
                str(settings.dialogue_kernel_trace_enabled).lower(),
            ),
            default=settings.dialogue_kernel_trace_enabled,
        ),
        dialogue_kernel_enforced_flows=await get_system_config(
            turn.db,
            "dialogue_kernel_enforced_flows",
            settings.dialogue_kernel_enforced_flows,
        ),
    )


async def _read_quote_facts(
    turn: _Turn, *, order_runtime_blocks_kernel_reply: bool
) -> _QuoteFacts:
    """What the customer text and the stored quote state say about this turn.

    `tj-rt7w.10`. Twenty-two locals computed in one run, several of them
    consumed a thousand lines below. Naming the set is what lets the routes
    that use it live in their own functions.
    """

    customer_name_was_unknown = not str(turn.conv.customer_name or "").strip()
    current_quote_customer_details = dict(turn.current_message_quote_customer_details)
    current_quote_intent_frame: Mapping[str, Any] | None = (
        engine._quote_intent_frame_from_text(turn.combined_text)
    )
    current_sales_memory_updates = engine._extract_sales_memory_updates(
        turn.combined_text
    )
    current_sales_opportunity_request = engine._extract_sales_opportunity_request(
        turn.combined_text
    )
    pending_name_gate_request = engine._name_gate_pending_request_from_metadata(
        turn.conv
    )
    pending_name_gate_intent = engine._name_gate_pending_intent_from_metadata(turn.conv)
    pending_quote_selection_at_start = (
        engine._active_pending_quote_selection_from_conversation(turn.conv)
    )
    has_pending_quote_selection = pending_quote_selection_at_start is not None
    pending_unconsented_detail_keys: set[str] = set()
    if has_pending_quote_selection and not current_quote_customer_details:
        identity_candidates = engine._extract_terse_quote_customer_details(
            turn.combined_text
        )
        pending_unconsented_detail_keys = set(identity_candidates).intersection(
            {"customer_type", "email", "phone", "address"}
        )
        current_quote_customer_details = {
            key: value
            for key, value in identity_candidates.items()
            if key in {"name", "company"}
        }
    pending_exact_quote_followup_candidates = (
        engine._exact_quote_followup_candidates(
            selection=pending_quote_selection_at_start,
            combined_text=turn.combined_text,
            masked_text=turn.masked_text,
        )
        if pending_quote_selection_at_start is not None
        and engine._accepts_exact_item_quote_followup(pending_quote_selection_at_start)
        and engine._pending_quote_has_unresolved_items(pending_quote_selection_at_start)
        else ()
    )
    assistant_asked_quote_details = _last_assistant_asked_quote_customer_details(
        turn.recent_history,
        quote_context_active=(
            has_pending_quote_selection or order_runtime_blocks_kernel_reply
        ),
    )
    assistant_offered_quote_selection = (
        engine._last_assistant_offered_quote_for_selection(turn.recent_history)
    )
    quote_offer_reply_has_consultative_priority = (
        engine._has_quote_resume_consultative_priority(turn.combined_text)
        or engine._has_quote_resume_consultative_priority(turn.masked_text)
    )
    quote_reply_updates_purchase_selection = (
        engine._has_quote_reply_purchase_selection_update(
            turn.combined_text, turn.masked_text
        )
    )
    assistant_supports_quote_resume = assistant_asked_quote_details or (
        assistant_offered_quote_selection
        and not quote_offer_reply_has_consultative_priority
        and (
            engine._has_explicit_quote_opt_in(turn.combined_text)
            or engine._has_explicit_quote_opt_in(turn.masked_text)
            or engine._has_affirmative_quote_resume_intent(turn.combined_text)
            or engine._has_affirmative_quote_resume_intent(turn.masked_text)
        )
    )
    explicit_quote_consent = not quote_offer_reply_has_consultative_priority and (
        engine._has_explicit_quote_opt_in(turn.combined_text)
        or engine._has_explicit_quote_opt_in(turn.masked_text)
        or (
            (
                assistant_offered_quote_selection
                or (has_pending_quote_selection and assistant_asked_quote_details)
            )
            and (
                engine._has_affirmative_quote_resume_intent(turn.combined_text)
                or engine._has_affirmative_quote_resume_intent(turn.masked_text)
            )
        )
    )
    quote_workflow = quote_workflow_from_metadata(turn.conv.metadata_)
    if explicit_quote_consent:
        quote_workflow = QuoteWorkflowState(
            consent=QuoteConsent.GRANTED,
            lifecycle=QuoteLifecycle.QUOTE_REQUESTED,
        )
        await engine._store_quote_workflow(turn.db, turn.conv, quote_workflow)
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
    pending_quote_brief_confirmation = (
        engine._pending_quote_brief_confirmation_from_metadata(turn.conv)
    )
    if (
        pending_quote_brief_confirmation
        and engine._last_assistant_asked_quote_brief_confirmation(turn.recent_history)
        and engine._has_affirmative_quote_resume_intent(turn.combined_text)
    ):
        current_quote_customer_details = {
            **current_quote_customer_details,
            **pending_quote_brief_confirmation,
        }
        confirmed_quote_brief_address = engine._string_value(
            pending_quote_brief_confirmation.get("address")
        )
        await engine._clear_pending_quote_brief_confirmation(turn.db, turn.conv)
    if quote_detail_context_active:
        unlabeled_quote_brief = engine._extract_ordered_unlabeled_quote_brief(
            turn.combined_text
        )
        if unlabeled_quote_brief and unlabeled_quote_brief.needs_confirmation:
            quote_brief_confirmation_details = unlabeled_quote_brief.details
            current_quote_customer_details = {}
        elif unlabeled_quote_brief:
            terse_quote_customer_details = unlabeled_quote_brief.details
            current_quote_customer_details = {
                **current_quote_customer_details,
                **terse_quote_customer_details,
            }
            await engine._clear_pending_quote_brief_confirmation(turn.db, turn.conv)
        else:
            terse_quote_customer_details = (
                {}
                if pending_exact_quote_followup_candidates
                else engine._extract_terse_quote_customer_details(turn.combined_text)
            )
            if terse_quote_customer_details:
                current_quote_customer_details = {
                    **current_quote_customer_details,
                    **terse_quote_customer_details,
                }
                await engine._clear_pending_quote_brief_confirmation(turn.db, turn.conv)
    if (
        not quote_detail_context_active
        and current_quote_customer_details
        and pending_quote_brief_confirmation
    ):
        await engine._clear_pending_quote_brief_confirmation(turn.db, turn.conv)
    return _QuoteFacts(
        customer_name_was_unknown=customer_name_was_unknown,
        current_quote_customer_details=current_quote_customer_details,
        current_quote_intent_frame=current_quote_intent_frame,
        current_sales_memory_updates=current_sales_memory_updates,
        current_sales_opportunity_request=current_sales_opportunity_request,
        pending_name_gate_request=pending_name_gate_request,
        pending_name_gate_intent=pending_name_gate_intent,
        pending_quote_selection_at_start=pending_quote_selection_at_start,
        has_pending_quote_selection=has_pending_quote_selection,
        pending_exact_quote_followup_candidates=(
            pending_exact_quote_followup_candidates
        ),
        assistant_offered_quote_selection=assistant_offered_quote_selection,
        assistant_supports_quote_resume=assistant_supports_quote_resume,
        quote_offer_reply_has_consultative_priority=(
            quote_offer_reply_has_consultative_priority
        ),
        quote_reply_updates_purchase_selection=quote_reply_updates_purchase_selection,
        quote_consent_granted=quote_consent_granted,
        unconsented_quote_details=unconsented_quote_details,
        quote_detail_context_active=quote_detail_context_active,
        quote_brief_confirmation_details=quote_brief_confirmation_details,
        confirmed_quote_brief_address=confirmed_quote_brief_address,
    )


async def _verified_policy_routes(
    turn: _Turn,
    facts: _QuoteFacts,
    *,
    policy_decision: VerifiedAnswerDecisionT,
    product_preference_frame_match: dict[str, Any] | None,
    resolved_pending_reference: PendingReferenceRoute,
    trace_enabled: bool,
    db_model_main: str,
    dynamic_model: OpenAIChatModelT,
) -> LLMResponseT | None:
    """The routes the verified-answer policy selects, and the order/quote adapter.

    Each one either answers the turn or declines it; `None` means the sales
    agent runs.
    """

    if (
        not policy_decision.is_order_status
        and policy_decision.sales_fallback_intent is not None
    ):
        await turn.clear_repair_state()
        return build_declared_static_response(
            build_sales_fallback_response(
                policy_decision.sales_fallback_intent,
                str(turn.deps.conversation.language),
            ),
            route="sales-fallback",
            build_static_response=turn.build_static_response,
            model_prefix=db_model_main,
        )

    order_quote_response = None
    if not facts.unconsented_quote_details:
        order_quote_response = await turn.order_quote_route(
            phase="post_policy",
            db=turn.db,
            conversation=turn.conv,
            deps=turn.deps,
            masked_text=turn.masked_text,
            combined_text=turn.combined_text,
            is_first_turn=turn.is_first_turn,
            pending_quote_selection_at_start=facts.pending_quote_selection_at_start,
            pending_exact_quote_followup_candidates=(
                facts.pending_exact_quote_followup_candidates
            ),
            current_quote_intent_frame=facts.current_quote_intent_frame,
            current_quote_customer_details=facts.current_quote_customer_details,
            assistant_supports_quote_resume=facts.assistant_supports_quote_resume,
            quote_detail_context_active=facts.quote_detail_context_active,
            has_pending_quote_selection=facts.has_pending_quote_selection,
            pending_reference_route=resolved_pending_reference,
            zoho_client=turn.zoho_client,
            crm_context=turn.crm_context,
            trace_enabled=trace_enabled,
            build_static_response=turn.build_static_response,
            clear_verified_policy_repair_state=(turn.clear_repair_state),
            db_model_main=db_model_main,
            dynamic_model=dynamic_model,
            run_agent=turn.run_agent,
            build_llm_response=turn.build_llm_response,
            run_prose_agent=turn.run_prose_agent,
            has_escalation=_has_escalation,
            quote_brief_confirmation_details=facts.quote_brief_confirmation_details,
            offer_quote=facts.offer_quote_for_turn,
            resumed_name_gate_intent=facts.resumed_name_gate_intent,
        )
    if order_quote_response is not None:
        return order_quote_response

    if (
        not policy_decision.is_order_status
        and policy_decision.question_class == "service_low_risk"
        and policy_decision.policy_action == "allow"
        and is_quote_or_proposal_request(turn.masked_text)
        and not engine._has_explicit_quote_hold(turn.masked_text)
    ):
        await turn.clear_repair_state()
        return build_declared_static_response(
            build_quote_or_proposal_clarification_response(
                str(turn.deps.conversation.language)
            ),
            route="proposal-clarify",
            build_static_response=turn.build_static_response,
            model_prefix=db_model_main,
        )

    if not policy_decision.is_order_status and (
        engine._is_mixed_product_service_request(turn.masked_text)
        or engine._is_mixed_product_service_request(turn.combined_text)
    ):
        result = await turn.run_agent(
            replace(
                turn.deps,
                tool_mode="full",
                runtime_directives=(
                    *turn.deps.runtime_directives,
                    *engine.MIXED_PRODUCT_SERVICE_DIRECTIVES,
                ),
            )
        )
        await turn.clear_repair_state()
        return turn.build_llm_response(result, db_model_main)

    if not policy_decision.is_order_status and engine._is_service_confirmation_reply(
        turn.combined_text,
        turn.deps.recent_history,
    ):
        from src.integrations.notifications.escalation import (
            notify_manager_escalation,
        )
        from src.schemas.common import EscalationType

        if not is_active_human_handoff(turn.deps.conversation.escalation_status):
            await notify_manager_escalation(
                conversation=turn.deps.conversation,
                reason=(
                    "Customer confirmed they want assembly/installation service "
                    "after the assistant asked a service confirmation question. "
                    "Manager should confirm service conditions and next steps."
                ),
                recent_messages=turn.deps.recent_history or [],
                db=turn.deps.db,
                escalation_type=EscalationType.GENERAL,
            )
        await turn.clear_repair_state()
        return build_declared_static_response(
            engine._service_confirmation_handoff_text(),
            route="service-confirmation-handoff",
            build_static_response=turn.build_static_response,
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
        await turn.clear_repair_state()
        return build_declared_static_response(
            engine._showroom_location_response(str(turn.deps.conversation.language)),
            route="showroom-location",
            build_static_response=turn.build_static_response,
            model_prefix=db_model_main,
            allow_product_media=False,
        )

    if (
        not policy_decision.is_order_status
        and policy_decision.sales_fallback_intent is None
        and (
            product_preference_frame_match is not None
            or engine._is_product_preference_answer(
                turn.combined_text, turn.deps.recent_history
            )
            or engine._is_product_preference_answer(
                turn.masked_text, turn.deps.recent_history
            )
        )
    ):
        frame_directives = (
            engine._product_preference_frame_directives(product_preference_frame_match)
            if product_preference_frame_match is not None
            else ()
        )
        result = await turn.run_agent(
            replace(
                turn.deps,
                tool_mode="full",
                runtime_directives=(
                    *turn.deps.runtime_directives,
                    *engine.PRODUCT_PREFERENCE_ANSWER_DIRECTIVES,
                    *frame_directives,
                ),
            )
        )
        await turn.clear_repair_state()
        return turn.build_llm_response(result, db_model_main)

    policy_action = policy_decision.policy_action
    if not policy_decision.is_order_status and policy_action == "clarify":
        repair_state = turn.repair_state()
        repair_count = repair_state.get("count") if repair_state is not None else None
        if (
            repair_state is not None
            and repair_state.get("kind") == "benign_no_match"
            and isinstance(repair_count, int)
            and repair_count >= 1
        ):
            policy_action = "handoff"
            await turn.clear_repair_state()
        else:
            await turn.set_repair_state("benign_no_match", 1)
            return build_declared_static_response(
                build_clarification_response(str(turn.deps.conversation.language)),
                route="verified-policy-clarify",
                build_static_response=turn.build_static_response,
                model_prefix=db_model_main,
            )

    if (
        not policy_decision.is_order_status
        and policy_decision.sales_fallback_intent is not None
    ):
        await turn.clear_repair_state()
        return build_declared_static_response(
            build_sales_fallback_response(
                policy_decision.sales_fallback_intent,
                str(turn.deps.conversation.language),
            ),
            route="sales-fallback",
            build_static_response=turn.build_static_response,
            model_prefix=db_model_main,
        )

    if not policy_decision.is_order_status and policy_action == "handoff":
        from src.integrations.notifications.escalation import (
            notify_manager_escalation,
        )
        from src.schemas.common import EscalationType

        await notify_manager_escalation(
            conversation=turn.deps.conversation,
            reason=build_service_handoff_reason(turn.masked_text, policy_decision),
            recent_messages=turn.deps.recent_history or [],
            db=turn.deps.db,
            escalation_type=EscalationType.GENERAL,
        )
        await turn.clear_repair_state()
        return await turn.build_policy_handoff_response(
            db_model_main,
            str(turn.deps.conversation.language),
            build_service_handoff_response(
                policy_decision, str(turn.deps.conversation.language)
            ),
            policy_decision=policy_decision,
        )

    if not policy_decision.is_order_status and policy_decision.question_class in {
        "service_low_risk",
        "service_high_risk",
    }:
        result = await turn.run_agent(
            replace(
                turn.deps,
                tool_mode="service_policy",
                runtime_directives=(
                    *turn.deps.runtime_directives,
                    *build_service_runtime_directives(policy_decision),
                ),
            )
        )
        await turn.clear_repair_state()
        return turn.build_llm_response(result, db_model_main)
    return None


async def _verified_catalog_plan_route(
    turn: _Turn,
    *,
    db_model_main: str,
    dynamic_model: OpenAIChatModelT,
) -> LLMResponseT | None:
    """The planner prepared verified catalog text; the model gets one pass to use it."""

    verified_catalog_plan = await engine._try_verified_catalog_plan(turn.deps)
    if verified_catalog_plan is None:
        return None
    fallback_text, plan_traces = verified_catalog_plan
    decision_directive = _catalog_decision_runtime_directive(turn.deps)
    if decision_directive is None:
        await turn.clear_repair_state()
        return build_declared_static_response(
            fallback_text,
            route="verified-catalog-functional-failure",
            build_static_response=turn.build_static_response,
            model_prefix=db_model_main,
            response_deps=turn.deps,
            allow_product_media=False,
            tool_traces=plan_traces,
        )
    run_deps = replace(
        turn.deps,
        tool_mode="catalog_materialization",
        runtime_directives=(
            *turn.deps.runtime_directives,
            decision_directive,
        ),
    )
    try:
        result = await turn.run_agent(run_deps)
    except (UnexpectedModelBehavior, TimeoutError):
        await turn.clear_repair_state()
        return turn.build_replacement_response(
            fallback_text,
            plan_traces,
            run_deps=run_deps,
            usage=turn.failed_run_usage or RunUsage(),
            cost=dynamic_model.provider_cost_snapshot(),
            model_name=f"{db_model_main}|verified-catalog-functional-failure",
            allow_product_media=False,
        )
    decision_provenance: Literal["model", "model_repaired"] = "model"
    defects = _catalog_decision_defects(
        unmask_pii(result.output, turn.pii_map), run_deps
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
                candidate = await turn.run_agent(repair_deps)
            except (UnexpectedModelBehavior, TimeoutError):
                candidate = None
            if candidate is not None and _catalog_decision_output_is_valid(
                unmask_pii(candidate.output, turn.pii_map), repair_deps
            ):
                repaired = candidate
        if repaired is None:
            usage = result.usage() or RunUsage()
            usage_telemetry = get_llm_usage_telemetry(result)
            await turn.clear_repair_state()
            return turn.build_replacement_response(
                fallback_text,
                plan_traces,
                run_deps=run_deps,
                usage=usage,
                cost=(
                    usage_telemetry.cost
                    if usage_telemetry is not None
                    else dynamic_model.provider_cost_snapshot()
                ),
                model_name=(f"{db_model_main}|verified-catalog-functional-failure"),
                allow_product_media=False,
            )
        result = repaired
        decision_provenance = "model_repaired"
    await turn.clear_repair_state()
    response = turn.build_llm_response(
        result,
        f"{db_model_main}|verified-catalog-plan",
        response_deps=turn.deps,
        allow_product_media=False,
        text_provenance=decision_provenance,
    )
    return replace(response, tool_traces=plan_traces)


async def _sales_agent_route(
    turn: _Turn,
    *,
    db_model_main: str,
    dynamic_model: OpenAIChatModelT,
    claim_contract_every_catalog_turn: bool,
) -> LLMResponseT:
    """The ordinary turn: the sales agent runs, and its claims are checked."""

    run_deps = turn.deps
    turn_directives = engine._turn_runtime_directives(
        turn.combined_text,
        turn.masked_text,
        sales_stage=str(getattr(turn.deps.conversation, "sales_stage", "") or ""),
        opening_states_the_offer=turn.is_first_turn,
        language=str(turn.deps.conversation.language or ""),
    )
    if turn_directives:
        run_deps = replace(
            turn.deps,
            runtime_directives=(
                *turn.deps.runtime_directives,
                *turn_directives,
            ),
        )
    try:
        result = await turn.run_agent(run_deps)
    except (UnexpectedModelBehavior, TimeoutError):
        explicit_quote_hold = engine._has_explicit_quote_hold(
            turn.masked_text
        ) or engine._has_explicit_quote_hold(turn.combined_text)
        await _complete_verified_cross_sell_for_recovery(
            RunContext(
                deps=run_deps,
                retry=0,
                messages=turn.history,
                prompt=turn.masked_text,
                model=dynamic_model,
                usage=turn.failed_run_usage or RunUsage(),
            ),
            explicit_quote_hold=explicit_quote_hold,
        )
        recovery_traces = tuple(run_deps.recovery_tool_traces)
        recovery_text = engine._materialize_verified_catalog_recovery(
            run_deps,
            recovery_traces,
            explicit_quote_hold=explicit_quote_hold,
        )
        if recovery_text is None:
            raise
        await turn.clear_repair_state()
        usage = turn.failed_run_usage or RunUsage()
        return turn.build_replacement_response(
            recovery_text,
            recovery_traces,
            run_deps=run_deps,
            usage=usage,
            cost=dynamic_model.provider_cost_snapshot(),
            model_name=f"{db_model_main}|verified-catalog-functional-failure",
        )
    recovery_traces = tuple(run_deps.recovery_tool_traces)
    recovery_text = engine._materialize_verified_catalog_recovery(
        run_deps,
        recovery_traces,
        explicit_quote_hold=(
            engine._has_explicit_quote_hold(turn.masked_text)
            or engine._has_explicit_quote_hold(turn.combined_text)
        ),
    )
    if recovery_text is not None and not _catalog_recovery_output_is_valid(
        unmask_pii(result.output, turn.pii_map), run_deps
    ):
        await turn.clear_repair_state()
        usage = result.usage() or RunUsage()
        usage_telemetry = get_llm_usage_telemetry(result)
        return turn.build_replacement_response(
            recovery_text,
            recovery_traces,
            run_deps=run_deps,
            usage=usage,
            cost=(
                usage_telemetry.cost
                if usage_telemetry is not None
                else dynamic_model.provider_cost_snapshot()
            ),
            model_name=f"{db_model_main}|verified-catalog-functional-failure",
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
        repaired_result = await turn.run_agent(repair_deps)
        repaired_result, contract = await _enforce_claim_contract(
            repaired_result,
            repair_deps=repair_deps,
            repair_payload=repair_payload,
            run_agent=turn.run_agent,
        )
        _log_claim_contract(contract, run_deps.conversation.id, scope="requested")
        await turn.clear_repair_state()
        return replace(
            turn.build_llm_response(
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
            run_agent=turn.run_agent,
        )
        _log_claim_contract(volunteered, run_deps.conversation.id, scope="volunteered")
        if verified_result is not result:
            await turn.clear_repair_state()
            return replace(
                turn.build_llm_response(
                    verified_result,
                    db_model_main,
                    response_deps=run_deps,
                    text_provenance="model_repaired",
                    route_suffix="claim-contract-turn",
                ),
                tool_traces=recovery_traces,
            )
    await turn.clear_repair_state()
    return replace(
        turn.build_llm_response(
            result,
            db_model_main,
            response_deps=run_deps,
        ),
        tool_traces=recovery_traces,
    )


async def _load_turn(
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
    crm_client: ZohoCRMClient | None,
    source_message_id: str | None,
    latency_trace: ChatLatencyTrace | None,
) -> _Turn:
    """Load the conversation, mask, build the history, and assemble the turn."""

    context_started = latency_trace.start_phase() if latency_trace is not None else None
    combined_text = engine._strip_synthetic_test_marker(combined_text)
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
    history = await engine.build_message_history(db, conversation_id, pii_map)

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

    # One extraction is read by both the pre-persistence response policy and
    # the later durable quote/customer-detail capture. They cannot disagree on
    # what the current inbound message supplied.
    current_message_quote_customer_details = engine._extract_quote_customer_details(
        combined_text
    )

    turn = _Turn(
        pending_reference_route=pending_reference_route,
        order_quote_route=order_quote_route,
        db=db,
        redis=redis,
        conversation_id=conversation_id,
        embedding_engine=embedding_engine,
        zoho_client=zoho_client,
        messaging_client=messaging_client,
        crm_client=crm_client,
        source_message_id=source_message_id,
        latency_trace=latency_trace,
        context_started=context_started,
        conv=conv,
        crm_context=crm_context,
        pii_map=pii_map,
        history=history,
        is_first_turn=is_first_turn,
        current_message_quote_customer_details=(current_message_quote_customer_details),
        # Memoised: the runtime used to be built inside the generation block,
        # out of reach of every route that runs before it, and
        # sales-opportunity needs the model to write its sentence (tj-swgu.3).
        # A turn that never reaches the model still pays nothing.
        model_runtime=_LazyModelRuntime(db),
        combined_text=combined_text,
        masked_text=masked_text,
        recent_history=recent_history,
        deps=deps,
    )
    return turn


async def _customer_facts_and_quotation_routes(
    turn: _Turn, config: _TurnConfig
) -> LLMResponseT | None:
    """The customer-facts layer, then the routes a pending quotation owns."""

    # See `_read_turn_config`: this import stays inside the call so the suite's
    # `src.core.config.get_system_config` patch still lands.
    from src.core.config import get_system_config

    customer_facts_run = await engine._run_customer_facts_layer(
        turn.db,
        conversation=turn.conv,
        text=turn.combined_text,
        mode=config.customer_facts_mode,
        trace_enabled=config.customer_facts_trace_enabled,
        fast_extractor_enabled=config.customer_facts_fast_extractor_enabled,
        max_context_orders=config.customer_facts_max_context_orders,
        source_message_id=turn.source_message_id,
    )
    if customer_facts_run.context_text:
        turn.deps = replace(
            turn.deps, customer_facts_context=customer_facts_run.context_text
        )
    if customer_facts_run.past_order_response:
        db_model_main = await get_system_config(
            turn.db, "openrouter_model_main", settings.openrouter_model_main
        )
        db_model_main = model_name_for_path(PATH_CORE_CHAT, db_model_main)
        return build_declared_static_response(
            customer_facts_run.past_order_response,
            route="customer-facts-past-order",
            build_static_response=turn.build_static_response,
            model_prefix=db_model_main,
            allow_product_media=False,
        )

    if engine._has_pending_proposal_decision(
        turn.conv
    ) and engine._is_post_quotation_acceptance(
        turn.combined_text,
        turn.recent_history,
    ):
        from src.integrations.notifications.escalation import (
            notify_manager_escalation,
        )
        from src.schemas.common import EscalationType

        accepted_at = datetime.datetime.now(datetime.UTC)
        engine._mark_quotation_accepted(
            turn.conv,
            accepted_at=accepted_at,
            customer_text=turn.combined_text,
        )
        if not is_active_human_handoff(turn.conv.escalation_status):
            await notify_manager_escalation(
                conversation=turn.conv,
                reason=(
                    "Customer accepted the quotation/proposal after the PDF was sent. "
                    "Manager should proceed with the next commercial steps."
                ),
                recent_messages=turn.deps.recent_history or [],
                db=turn.db,
                escalation_type=EscalationType.ORDER_CONFIRMATION,
            )
        await turn.db.flush()
        db_model_main = await get_system_config(
            turn.db, "openrouter_model_main", settings.openrouter_model_main
        )
        db_model_main = model_name_for_path(PATH_CORE_CHAT, db_model_main)
        return build_declared_static_response(
            engine._post_quotation_accepted_response(str(turn.conv.language)),
            route="post-quotation-accepted",
            build_static_response=turn.build_static_response,
            model_prefix=db_model_main,
            allow_product_media=False,
        )

    if (
        engine._has_pending_proposal_decision(turn.conv)
        and engine._normalize_text(turn.combined_text)
        in engine._POST_QUOTATION_GENERIC_ACCEPTANCE_EXACT
    ):
        db_model_main = await get_system_config(
            turn.db, "openrouter_model_main", settings.openrouter_model_main
        )
        db_model_main = model_name_for_path(PATH_CORE_CHAT, db_model_main)
        return build_declared_static_response(
            engine._post_quotation_acknowledgement_response(str(turn.conv.language)),
            route="post-quotation-ack",
            build_static_response=turn.build_static_response,
            model_prefix=db_model_main,
            allow_product_media=False,
        )

    if engine._has_quoted_quote_frame(
        turn.conv
    ) and engine._is_post_quotation_context_preserving_reply(turn.combined_text):
        db_model_main = await get_system_config(
            turn.db, "openrouter_model_main", settings.openrouter_model_main
        )
        db_model_main = model_name_for_path(PATH_CORE_CHAT, db_model_main)
        return build_declared_static_response(
            engine._post_quotation_context_acknowledgement_response(
                str(turn.conv.language)
            ),
            route="post-quotation-context-ack",
            build_static_response=turn.build_static_response,
            model_prefix=db_model_main,
            allow_product_media=False,
        )

    if engine._has_explicit_quote_hold(turn.combined_text):
        await engine._suspend_quote_workflow(
            turn.db,
            turn.conv,
            consent=quote_consent_signal(turn.combined_text, [])
            or QuoteConsent.DECLINED,
        )
    return None


async def _dialogue_kernel_route(
    turn: _Turn, config: _TurnConfig
) -> tuple[LLMResponseT | None, bool]:
    """Run the dialogue kernel, store what it decided, and answer when it owns the turn.

    Returns the reply, if the kernel owns this turn, and whether the order
    runtime blocks a kernel reply -- which the quote facts below need.
    """

    order_runtime_blocks_kernel_reply = (
        engine._active_pending_quote_selection_from_conversation(turn.conv) is not None
        or engine._quote_intent_frame_from_metadata(turn.conv) is not None
    )

    try:
        turn.dialogue_kernel_result = await engine.run_dialogue_kernel(
            conversation=turn.conv,
            text=turn.combined_text,
            recent_history=turn.recent_history,
            is_first_turn=turn.is_first_turn,
            mode=turn.dialogue_kernel_mode,
            enforced_flows=config.dialogue_kernel_enforced_flows,
            trace_enabled=config.dialogue_kernel_trace_enabled,
        )
    except Exception:
        if str(turn.dialogue_kernel_mode or "").strip().casefold() != "shadow":
            raise
        logger.warning(
            "Dialogue kernel shadow run failed for conversation %s; "
            "continuing legacy path",
            turn.conv.id,
            exc_info=True,
        )
        turn.dialogue_kernel_result = None
    if turn.dialogue_kernel_result is not None:
        kernel_workflow = QuoteWorkflowState(
            consent=turn.dialogue_kernel_result.state.quote_consent,
            lifecycle=turn.dialogue_kernel_result.state.quote_lifecycle,
        )
        current_workflow = quote_workflow_from_metadata(turn.conv.metadata_)
        kernel_consent_value = turn.dialogue_kernel_result.decision.metadata.get(
            "quote_consent"
        )
        kernel_has_explicit_consent = isinstance(kernel_consent_value, str)
        kernel_grant_is_current_turn = (
            kernel_consent_value == QuoteConsent.GRANTED.value
            and (
                engine._has_explicit_quote_opt_in(turn.combined_text)
                or (
                    engine._last_assistant_offered_quote_for_selection(
                        turn.recent_history
                    )
                    and engine._has_affirmative_quote_resume_intent(turn.combined_text)
                )
            )
        )
        canonical_blocks_stale_kernel_grant = (
            engine._has_canonical_quote_workflow(turn.conv)
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
                not engine._has_canonical_quote_workflow(turn.conv)
                and current_workflow.consent is QuoteConsent.NOT_REQUESTED
                and kernel_workflow.consent is not QuoteConsent.GRANTED
            )
        ):
            await engine._store_quote_workflow(turn.db, turn.conv, kernel_workflow)
    if (
        turn.dialogue_kernel_result is not None
        and turn.dialogue_kernel_result.should_use_kernel
        and not canonical_blocks_stale_kernel_grant
        and turn.dialogue_kernel_result.decision.action != "product_preference_answer"
        and not (
            order_runtime_blocks_kernel_reply
            and turn.dialogue_kernel_result.decision.flow != "quote_details"
        )
    ):
        if turn.dialogue_kernel_result.decision.flow == "name_gate":
            await engine._store_name_gate_pending_request(
                turn.db, turn.conv, turn.combined_text
            )
        if turn.dialogue_kernel_result.decision.flow == "quote_details":
            raw_details = turn.dialogue_kernel_result.decision.metadata.get(
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
                await engine._store_extracted_quote_customer_details(
                    turn.db, turn.conv, quote_details
                )
        if turn.dialogue_kernel_result.decision.flow == "product_selection":
            await engine._store_kernel_quantity_prompt_frame(
                turn.db,
                turn.conv,
                combined_text=turn.combined_text,
                masked_text=turn.masked_text,
                response_text=turn.dialogue_kernel_result.decision.response_text or "",
            )
        return (
            turn.build_static_response(
                turn.dialogue_kernel_result.decision.response_text or "",
                f"dialogue-kernel|{turn.dialogue_kernel_result.decision.flow}",
                allow_product_media=False,
            ),
            order_runtime_blocks_kernel_reply,
        )
    return None, order_runtime_blocks_kernel_reply


async def _capture_details_and_name_gate_routes(
    turn: _Turn, facts: _QuoteFacts
) -> LLMResponseT | None:
    """Store what the customer just gave, and answer if that is the whole turn.

    The name gate lives here: when the reply completes it, the parked request
    is resumed, which replaces the turn's text and rebuilds `deps` and the
    quote facts against it.
    """

    # A bare "Alex" is only a name because we just asked for one. Until
    # 2026-08-10 the only thing that ever asked was the name gate, so this read
    # its parked request; now any route can ask, and the reply has to land the
    # same way. The condition is on what we actually sent, not on what the
    # engine believes it did.
    if facts.pending_name_gate_request or response_asks_customer_name(
        engine._last_assistant_message(turn.recent_history)
    ):
        pending_reply_name = engine._extract_pending_name_gate_reply_name(
            turn.combined_text,
            facts.current_quote_customer_details,
        )
        if pending_reply_name and not facts.current_quote_customer_details.get("name"):
            facts.current_quote_customer_details = {
                **facts.current_quote_customer_details,
                "name": pending_reply_name,
            }

    if (
        turn.is_first_turn
        and facts.customer_name_was_unknown
        and not engine._string_value(facts.current_quote_customer_details.get("name"))
    ):
        # The turn is no longer spent on the question. It runs to the end like
        # any other, and `apply_opening_guard` folds the name request onto the
        # answer -- owner decision of 2026-08-10, on the measurement that 36% of
        # customers never send a second message and so never got past this
        # point. Nothing is deferred for a later resume, because nothing is
        # deferred at all.
        #
        # The anchor is still read here, where the catalog is in reach, so the
        # opening carries a price when the reply itself found none. `tj-7vhq`:
        # not on a message that is about something other than furniture, where a
        # price list only contradicts the answer that follows it.
        turn.opening_anchor_line = (
            await catalog_anchor_line(turn.db, str(turn.conv.language))
            if opening_wants_a_price_anchor(turn.combined_text)
            else None
        )

    # Store customer details from the original, unmasked text before any route
    # can call create_quotation. Phone is enough to create a draft, while the
    # other fields are optional PDF details when the customer provides them.
    if facts.current_quote_customer_details:
        allowed_quote_customer_details = (
            facts.current_quote_customer_details
            if facts.quote_consent_granted
            else {
                key: value
                for key, value in facts.current_quote_customer_details.items()
                if key in {"name", "company"}
            }
        )
        await engine._store_extracted_quote_customer_details(
            turn.db,
            turn.conv,
            allowed_quote_customer_details,
        )
        if facts.quote_consent_granted and facts.confirmed_quote_brief_address:
            await engine._store_confirmed_quote_brief_address(
                turn.db,
                turn.conv,
                facts.confirmed_quote_brief_address,
            )
    if (
        facts.current_quote_intent_frame is not None
        and facts.pending_quote_selection_at_start is None
    ):
        await engine._store_quote_intent_frame(turn.db, turn.conv, turn.combined_text)
    if facts.current_sales_memory_updates:
        await engine._store_sales_memory_updates(
            turn.db, turn.conv, facts.current_sales_memory_updates
        )

    facts.name_gate_completion_reply = engine._is_name_gate_completion_reply(
        turn.combined_text,
        facts.current_quote_customer_details,
        pending_request_exists=bool(facts.pending_name_gate_request),
    )
    if (
        facts.name_gate_completion_reply
        and facts.quote_detail_context_active
        and engine._has_quote_customer_details_beyond_name(
            facts.current_quote_customer_details
        )
    ):
        await engine._consume_name_gate_pending_request(turn.db, turn.conv)
        facts.pending_name_gate_request = None
    elif facts.name_gate_completion_reply:
        captured_customer_name = engine._string_value(
            facts.current_quote_customer_details["name"]
        )
        facts.resumed_name_gate_intent = facts.pending_name_gate_intent
        facts.pending_name_gate_request = (
            await engine._consume_name_gate_pending_request(turn.db, turn.conv)
        )
        if facts.pending_name_gate_request:
            turn.name_gate_resume_customer_name = captured_customer_name
            turn.combined_text = facts.pending_name_gate_request
            turn.masked_text, pending_piis = mask_pii(turn.combined_text)
            turn.pii_map.update(pending_piis)
            resumed_quote_customer_details = engine._extract_quote_customer_details(
                turn.combined_text
            )
            if resumed_quote_customer_details:
                if not engine._string_value(resumed_quote_customer_details.get("name")):
                    resumed_quote_customer_details = {
                        **resumed_quote_customer_details,
                        "name": captured_customer_name,
                    }
                if not facts.quote_consent_granted:
                    resumed_quote_customer_details = {
                        key: value
                        for key, value in resumed_quote_customer_details.items()
                        if key in {"name", "company"}
                    }
                await engine._store_extracted_quote_customer_details(
                    turn.db,
                    turn.conv,
                    resumed_quote_customer_details,
                )
            pending_user_entry = f"user: {turn.masked_text}"
            if pending_user_entry not in turn.recent_history:
                turn.recent_history.append(pending_user_entry)
            turn.recent_history = turn.recent_history[-5:]
            turn.deps = replace(
                turn.deps,
                user_query=turn.masked_text,
                recent_history=turn.recent_history,
                runtime_directives=(
                    *turn.deps.runtime_directives,
                    f"Customer name is {captured_customer_name}. Continue the "
                    "customer's prior request now that their name is known. "
                    "Acknowledge the name briefly. Do not ask for their name "
                    "again, and do not ask what they need again.",
                ),
            )
            facts.current_quote_customer_details = (
                engine._quote_customer_details_from_metadata(turn.conv)
            )
            facts.current_quote_intent_frame = engine._quote_intent_frame_from_metadata(
                turn.conv
            ) or engine._quote_intent_frame_from_text(turn.combined_text)
            facts.current_sales_opportunity_request = (
                engine._extract_sales_opportunity_request(turn.combined_text)
            )
        else:
            # Nothing was parked, so there is no prior request to resume. If a
            # quotation is pending, though, the name that just arrived is the
            # detail it was waiting for, and the quote route below owes an
            # answer -- not "Thank you, Alex. How can I help you?"
            if (
                not engine._has_detail_capture_handoff_blocker(turn.combined_text)
                and not facts.has_pending_quote_selection
            ):
                if (
                    engine._has_active_sales_detail_capture_context(
                        turn.conv,
                        turn.deps.recent_history,
                    )
                    and not facts.quote_reply_updates_purchase_selection
                    and engine._is_neutral_detail_capture_update(
                        text=turn.combined_text,
                        customer_details=facts.current_quote_customer_details,
                        sales_memory_updates=facts.current_sales_memory_updates,
                    )
                ):
                    return build_declared_static_response(
                        engine._detail_capture_acknowledgement(
                            facts.current_quote_customer_details,
                            facts.current_sales_memory_updates,
                        ),
                        route="detail-capture",
                        build_static_response=turn.build_static_response,
                        allow_product_media=False,
                    )
                return build_declared_static_response(
                    f"Thank you, {facts.current_quote_customer_details['name']}. "
                    "How can I help you with your office furniture requirement?",
                    route="name-capture",
                    build_static_response=turn.build_static_response,
                    allow_product_media=False,
                )
    return None


async def _pre_policy_routes(turn: _Turn, facts: _QuoteFacts) -> LLMResponseT | None:
    """Consent, the sales opportunity, and the detail-capture acknowledgement."""

    if facts.unconsented_quote_details:
        return build_declared_static_response(
            (
                "I have kept the selected items, but I will collect customer and "
                "delivery details only after you explicitly confirm that you want "
                "a formal quotation."
            ),
            route="quote-consent-required",
            build_static_response=turn.build_static_response,
            allow_product_media=False,
        )

    facts.offer_quote_for_turn = await engine._quote_offer_allowed_for_turn(
        turn.db,
        turn.conv,
        turn.combined_text,
    )
    if (
        facts.current_sales_opportunity_request is not None
        and not facts.offer_quote_for_turn
    ):
        facts.current_sales_opportunity_request = replace(
            facts.current_sales_opportunity_request,
            quote_consent=quote_workflow_from_metadata(turn.conv.metadata_).consent,
        )

    if facts.current_sales_opportunity_request is not None:
        opportunity_result = await engine._create_or_reuse_sales_opportunity(
            turn.deps,
            title=engine._sales_opportunity_title(turn.deps),
            amount=facts.current_sales_opportunity_request.amount,
            allow_reuse=True,
        )
        response_model = (
            "sales-opportunity"
            if opportunity_result.verified
            else "sales-opportunity-unverified"
        )
        return await _verified_prose_response(
            verified_text=engine._sales_opportunity_response(
                facts.current_sales_opportunity_request,
                opportunity_result,
                language=str(turn.conv.language),
            ),
            deps=turn.deps,
            model_name=response_model,
            customer_text=turn.combined_text,
            build_static_response=turn.build_static_response,
            build_llm_response=turn.build_llm_response,
            run_prose_agent=turn.run_prose_agent,
        )

    if (
        not facts.quote_detail_context_active
        and not facts.quote_reply_updates_purchase_selection
        and engine._has_active_sales_detail_capture_context(
            turn.conv, turn.deps.recent_history
        )
        # An acknowledgement is not an answer. The customer's opening question
        # is stored while the name gate runs, and on 2026-08-09 R03 showed what
        # happens when this route fires on the turn that completes the gate:
        # "hi do u have ch616 in black" -> name gate -> "Omar" -> "Thanks, I've
        # noted name: Omar." The question was never served and the turn carried
        # nothing. Reading the metadata here is too late -- the pending request
        # has already been consumed by this point -- so the test is whether this
        # turn is the one that completed the gate.
        and not facts.name_gate_completion_reply
        # The same rule, generalised on 2026-08-10 when the gate was removed. A
        # customer answering the last detail a pending quotation was waiting for
        # is owed the quotation, not "Thanks, I've noted name: Alex." The quote
        # route below either completes it or asks for what is still missing
        # while carrying the verified price and stock, and both beat a receipt.
        and not facts.has_pending_quote_selection
        and engine._is_neutral_detail_capture_update(
            text=turn.combined_text,
            customer_details=facts.current_quote_customer_details,
            sales_memory_updates=facts.current_sales_memory_updates,
        )
    ):
        return build_declared_static_response(
            engine._detail_capture_acknowledgement(
                facts.current_quote_customer_details,
                facts.current_sales_memory_updates,
            ),
            route="detail-capture",
            build_static_response=turn.build_static_response,
            allow_product_media=False,
        )
    return None


async def _search_context_and_policy(
    turn: _Turn, facts: _QuoteFacts
) -> tuple[VerifiedAnswerDecisionT, dict[str, Any] | None]:
    """FAQ and behaviour-rule retrieval, then the verified-answer policy call."""

    if turn.latency_trace is not None and turn.context_started is not None:
        turn.latency_trace.finish_phase("llm_context", turn.context_started)

    # Pre-compute FAQ search results (once per message, not per tool roundtrip)
    faq_started = (
        turn.latency_trace.start_phase() if turn.latency_trace is not None else None
    )
    try:
        from src.rag.pipeline import search_knowledge

        turn.deps.faq_context = await search_knowledge(
            turn.db, turn.masked_text, turn.embedding_engine, limit=3
        )
    except Exception:
        logger.warning("FAQ knowledge base search failed", exc_info=True)
    finally:
        if turn.latency_trace is not None and faq_started is not None:
            turn.latency_trace.finish_phase("faq_rag", faq_started)

    behavior_started = (
        turn.latency_trace.start_phase() if turn.latency_trace is not None else None
    )
    try:
        metadata = turn.conv.metadata_ if isinstance(turn.conv.metadata_, dict) else {}
        segment = None
        if turn.crm_context:
            segment = turn.crm_context.get("Segment") or turn.crm_context.get("segment")
        segment = segment or metadata.get("segment")
        rules = await engine.search_behavior_rules(
            turn.db,
            context=BehaviorRuleSearchContext(
                message=turn.masked_text,
                stage=str(turn.conv.sales_stage) if turn.conv.sales_stage else None,
                language=str(turn.conv.language) if turn.conv.language else None,
                segment=str(segment) if segment else None,
            ),
            embedding_engine=turn.embedding_engine,
        )
        turn.deps.behavior_rules = [rule_to_applied_dict(rule) for rule in rules]
        await engine._store_applied_bot_rules(
            turn.db, turn.conv, turn.deps.behavior_rules
        )
    except Exception:
        logger.warning("Bot behavior rule search failed", exc_info=True)
    finally:
        if turn.latency_trace is not None and behavior_started is not None:
            turn.latency_trace.finish_phase("behavior_rag", behavior_started)

    policy_decision = engine.evaluate_verified_answer_policy(
        turn.masked_text, turn.deps.faq_context or []
    )
    if _should_override_policy_for_catalog_fact_query(
        turn.combined_text,
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
        facts.assistant_offered_quote_selection
        and facts.quote_offer_reply_has_consultative_priority
        and not engine._has_detail_capture_handoff_blocker(turn.combined_text)
    ):
        policy_decision = replace(
            policy_decision,
            question_class="product",
            policy_action="allow",
            requires_manager_handoff=False,
            sales_fallback_intent=None,
        )
    product_preference_frame_match = engine._dialogue_kernel_product_preference_match(
        turn.dialogue_kernel_result
    )
    return policy_decision, product_preference_frame_match


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

    The turn is a sequence of phases over one `_Turn`. Each phase either answers
    the turn or returns `None` and hands it on; the last one always answers.
    """

    turn = await _load_turn(
        pending_reference_route=pending_reference_route,
        order_quote_route=order_quote_route,
        conversation_id=conversation_id,
        combined_text=combined_text,
        db=db,
        redis=redis,
        embedding_engine=embedding_engine,
        zoho_client=zoho_client,
        messaging_client=messaging_client,
        crm_client=crm_client,
        source_message_id=source_message_id,
        latency_trace=latency_trace,
    )
    config = await _read_turn_config(turn)

    response = await _customer_facts_and_quotation_routes(turn, config)
    if response is not None:
        return await _finalize_turn_response(turn, response)

    response, order_runtime_blocks_kernel_reply = await _dialogue_kernel_route(
        turn, config
    )
    if response is not None:
        return await _finalize_turn_response(turn, response)

    facts = await _read_quote_facts(
        turn, order_runtime_blocks_kernel_reply=order_runtime_blocks_kernel_reply
    )
    response = await _capture_details_and_name_gate_routes(turn, facts)
    if response is not None:
        return await _finalize_turn_response(turn, response)

    response = await _pre_policy_routes(turn, facts)
    if response is not None:
        return await _finalize_turn_response(turn, response)

    resolved_pending_reference = await turn.pending_reference_route(
        db=turn.db,
        conversation=turn.conv,
        recent_history=turn.deps.recent_history,
        combined_text=turn.combined_text,
        masked_text=turn.masked_text,
    )
    order_quote_response = None
    if not facts.unconsented_quote_details:
        order_quote_response = await turn.order_quote_route(
            phase="pre_policy",
            db=turn.db,
            conversation=turn.conv,
            deps=turn.deps,
            masked_text=turn.masked_text,
            combined_text=turn.combined_text,
            is_first_turn=turn.is_first_turn,
            pending_quote_selection_at_start=facts.pending_quote_selection_at_start,
            pending_exact_quote_followup_candidates=(
                facts.pending_exact_quote_followup_candidates
            ),
            current_quote_intent_frame=facts.current_quote_intent_frame,
            current_quote_customer_details=facts.current_quote_customer_details,
            assistant_supports_quote_resume=facts.assistant_supports_quote_resume,
            quote_detail_context_active=facts.quote_detail_context_active,
            has_pending_quote_selection=facts.has_pending_quote_selection,
            pending_reference_route=resolved_pending_reference,
            zoho_client=turn.zoho_client,
            crm_context=turn.crm_context,
            trace_enabled=config.dialogue_kernel_trace_enabled,
            build_static_response=turn.build_static_response,
            clear_verified_policy_repair_state=turn.clear_repair_state,
            offer_quote=facts.offer_quote_for_turn,
            resumed_name_gate_intent=facts.resumed_name_gate_intent,
            # The pre-policy phase used to run before the model existed, so it
            # could only ever send route text. The runtime is memoised now, so
            # selection-confirmation gets its sentence written here too
            # (tj-swgu.3); a turn that never reaches the model still builds
            # nothing.
            run_agent=turn.run_agent,
            build_llm_response=turn.build_llm_response,
            run_prose_agent=turn.run_prose_agent,
        )
    if order_quote_response is not None:
        return await _finalize_turn_response(turn, order_quote_response)

    policy_decision, product_preference_frame_match = await _search_context_and_policy(
        turn, facts
    )

    db_model_main = "unknown"
    try:
        db_model_main, dynamic_model = await turn.model_runtime.get()
        response = await _verified_policy_routes(
            turn,
            facts,
            policy_decision=policy_decision,
            product_preference_frame_match=product_preference_frame_match,
            resolved_pending_reference=resolved_pending_reference,
            trace_enabled=config.dialogue_kernel_trace_enabled,
            db_model_main=db_model_main,
            dynamic_model=dynamic_model,
        )
        if response is None:
            response = await _verified_catalog_plan_route(
                turn,
                db_model_main=db_model_main,
                dynamic_model=dynamic_model,
            )
        if response is None:
            response = await _sales_agent_route(
                turn,
                db_model_main=db_model_main,
                dynamic_model=dynamic_model,
                claim_contract_every_catalog_turn=(
                    config.claim_contract_every_catalog_turn
                ),
            )

    except Exception:
        logger.exception(
            "LLM generation failed for conv_id=%s phone=%s",
            str(turn.conv.id),
            str(turn.conv.phone),
        )
        # NOTE: We do not surface exc details in model= to avoid info leakage.
        # `db_model_main` is "unknown" until the runtime resolves, which is what
        # the `locals()` probe here used to be testing for.
        response_model = f"{db_model_main}|error"
        rendered = turn.render_reply(
            "I apologize, but I am experiencing a temporary issue. Please try again in a moment.",
            response_deps=turn.deps,
            provenance="deterministic_static",
            model_name=response_model,
        )
        response = _response_from_rendered_reply(
            rendered,
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            model=response_model,
            usage_provenance="deterministic_static",
        )

    return await _finalize_turn_response(turn, response)
