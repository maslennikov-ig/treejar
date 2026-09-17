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

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal

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
    quote_workflow_from_metadata,
)
from src.dialogue.runner import (
    record_legacy_route,
)
from src.llm.catalog_planning import (
    CLAIM_CONTRACT_SCOPE_KEY,
    SalesDeps,
    _claim_contract_directive,
    _claim_contract_runs_every_catalog_turn,
    _enforce_claim_contract,
    _log_claim_contract,
    _materialize_claim_rows,
    _materialize_verified_catalog_facts,
    _turn_owes_the_company_question,
    _verify_volunteered_claims,
    grounded_amounts_for_turn,
)
from src.llm.grounding_output import GroundingOutputAction
from src.llm.outbound_reply_guard import finalize_customer_reply_text
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


def _limited_stock_product_references(deps: SalesDepsT) -> tuple[str, ...]:
    """Names and SKUs for retrieved rows whose verified stock is 1--4."""

    rows_by_sku = {
        row.sku.strip().casefold(): row for row in deps.claim_rows.values() if row.sku
    }
    references: list[str] = []
    for snapshot in deps.stock_snapshots.values():
        if not 1 <= snapshot.available < 5:
            continue
        references.append(snapshot.sku)
        row = rows_by_sku.get(snapshot.sku.strip().casefold())
        if row is None:
            continue
        for field in ("name", "name_en", "display_name"):
            value = str(row.fields.get(field, "") or "").strip()
            if value:
                references.append(value)
    return tuple(dict.fromkeys(references))


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
    opening_anchor_has_limited_stock: bool = False
    opening_anchor_grounded_amounts: tuple[float, ...] = ()
    name_gate_resume_customer_name: str | None = None
    failed_run_usage: RunUsageT | None = None
    permitted_asks_cache: frozenset[AskKind] | None = None
    completed_model_history: list[ModelRequestT | ModelResponseT] | None = None

    # The verified-answer repair counter lives in conversation metadata; these
    # three keep their zero-argument shape because several call sites hand the
    # clearer to the order/quote adapter as a `Callable[[], Awaitable[None]]`.

    async def clear_repair_state(self) -> None:
        await _drop_verified_policy_repair_state(self.conv, self.db)

    def permitted_asks(self) -> frozenset[AskKind]:
        """Read current workflow state, including changes made by model tools."""

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
        grounded_amounts = grounded_amounts_for_turn(
            response_deps,
            customer_text=self.combined_text,
        )
        if grounded_amounts is not None:
            grounded_amounts = (
                *grounded_amounts,
                *self.opening_anchor_grounded_amounts,
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
                anchor_has_limited_stock=self.opening_anchor_has_limited_stock,
                limited_stock_product_references=(
                    _limited_stock_product_references(response_deps)
                ),
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
                grounded_amounts=grounded_amounts,
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
                message_history=(
                    self.completed_model_history
                    if run_deps.tool_mode == "catalog_materialization"
                    and self.completed_model_history is not None
                    else self.history
                ),
                model=runtime_model,
                model_name=runtime_model_name,
                usage=run_usage,
            )
            all_messages = getattr(result, "all_messages", None)
            if callable(all_messages):
                completed = all_messages()
                if isinstance(completed, list):
                    self.completed_model_history = list(completed)
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
                    retrieved_catalog_rows=(
                        (_materialize_claim_rows(turn.deps) or {})
                        if getattr(turn.deps, "claim_rows", None)
                        else {}
                    ),
                    recent_history=tuple(
                        getattr(turn.deps, "recent_history", None) or ()
                    )[-6:],
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

    state = response.repair_policy_state
    language = (
        state.language
        if state is not None
        else str(getattr(turn.deps.conversation, "language", "en") or "en")
    )
    response.text = finalize_customer_reply_text(response.text, language=language)
    response.deferred_product_media = tuple(
        item
        for item in response.deferred_product_media
        if _product_media_is_referenced(item, response.text)
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
    customer_facts_max_context_orders: int
    claim_contract_every_catalog_turn: bool


async def _read_turn_config(turn: _Turn) -> _TurnConfig:
    """Every system-config read the turn makes, taken once and named."""

    # Imported at call time, not at module import: the suite patches
    # `src.core.config.get_system_config`, and a module-level binding would
    # freeze the real one before the patch lands.
    from src.core.config import get_system_config

    turn.dialogue_kernel_mode = "disabled"
    return _TurnConfig(
        customer_facts_mode=engine._normalize_customer_facts_mode(
            await get_system_config(
                turn.db,
                "customer_facts_mode",
                settings.customer_facts_mode,
            )
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
    )


async def _sales_agent_route(
    turn: _Turn,
    *,
    db_model_main: str,
    dynamic_model: OpenAIChatModelT,
    claim_contract_every_catalog_turn: bool,
) -> LLMResponseT:
    """The ordinary turn: the sales agent runs, and its claims are checked."""

    run_deps = turn.deps
    result = await turn.run_agent(run_deps)
    recovery_traces = tuple(run_deps.recovery_tool_traces)
    verified_catalog_facts = _materialize_verified_catalog_facts(run_deps)
    if verified_catalog_facts is not None:
        repair_payload = json.dumps(
            {
                "candidate_response": str(result.output),
                "verified_catalog_facts": verified_catalog_facts,
                "retrieved_rows": _materialize_claim_rows(run_deps),
                "customer_request": turn.masked_text,
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
    # Search intent and constraints come from model tool arguments, not a
    # keyword-derived plan that can silently negate the customer's request.

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
    )

    # One extraction is read by both the pre-persistence response policy and
    # the later durable quote/customer-detail capture. They cannot disagree on
    # what the current inbound message supplied.
    current_message_quote_customer_details: dict[str, str] = {}

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


async def _load_customer_memory(turn: _Turn, config: _TurnConfig) -> None:
    """Load durable customer context; never return a prewritten customer answer."""
    if config.customer_facts_mode != "enforce":
        return
    from src.services.customer_memory import load_existing_customer_context

    try:
        context = await load_existing_customer_context(
            turn.db,
            conversation=turn.conv,
            max_past_orders=config.customer_facts_max_context_orders,
        )
        turn.deps.customer_facts_context = context
    except Exception:
        logger.warning(
            "Customer memory read failed; using conversation history", exc_info=True
        )


async def _retrieve_context(turn: _Turn) -> None:
    """Retrieve evidence for the model without selecting a semantic route."""

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

    Load factual context, let the main model choose tools and answer, then check
    factual claims and delivery constraints. Legacy adapters are accepted only
    for API compatibility and are never invoked.
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

    # Intent and next action belong to the tool-using model. Historical route
    # adapters must not inspect the wording, mutate consent or execute actions
    # before the model sees the original message and conversation history.
    await _load_customer_memory(turn, config)
    await _retrieve_context(turn)

    db_model_main = "unknown"
    try:
        db_model_main, dynamic_model = await turn.model_runtime.get()
        response = await _sales_agent_route(
            turn,
            db_model_main=db_model_main,
            dynamic_model=dynamic_model,
            claim_contract_every_catalog_turn=config.claim_contract_every_catalog_turn,
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
