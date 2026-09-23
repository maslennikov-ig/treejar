"""Replay multi-turn customer scenarios through ``engine.process_message``.

A turn is processed the way ``src.services.chat`` processes an inbound batch:
the customer message is stored, ``process_message`` runs, the final reply is
stored, and the deferred product media are handed to the real
``_send_deferred_product_media`` (which writes the outbound audit rows later
turns resolve captions from). Only the edges are replaced; see ``fakes`` and
``llm_seam``.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import subprocess
import time
import uuid
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
from openai.resources.chat.completions import AsyncCompletions

from scenario_replay.checks import run_checks
from scenario_replay.fakes import (
    CallRecorder,
    CatalogStore,
    FakeAsyncSession,
    FakeCRM,
    FakeMessaging,
    FakeRedis,
    FakeZohoInventory,
    QuotationGatesPassed,
    StubEmbedding,
    lexical_search_factory,
    load_catalog_rows,
)
from scenario_replay.llm_seam import BudgetExhausted, CostMeter, NetworkGuard, StubModel

REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_MAIN_MODEL = "openai/gpt-6-luna"

LIMITATIONS = (
    "Vector search is replaced by deterministic lexical ranking over the snapshot; "
    "the production SQL filters (active, price bounds, in_stock_only -> stock>0) "
    "are reproduced exactly, ordering is not.",
    "Knowledge-base RAG and DB bot-behaviour rules return nothing; the file-based "
    "approved FAQ (src/llm/company_faq.py) still applies.",
    "Zoho item rate equals the snapshot catalog price; live stock equals snapshot "
    "stock except the scenario's live_stock_overrides.",
    "create_quotation runs its real consent and required-detail gates; at the first "
    "Zoho call it is short-circuited to a fake success (quote number, follow-up "
    "metadata), with no Zoho, PDF or send.",
    "Customer is new (CRM lookup returns nothing); Telegram, CRM and Wazzup are "
    "recorders. record_* tools are the real state tools.",
    "The system_prompts table is empty, so the in-code default prompt components "
    "are used; any production DB prompt override is not reproduced.",
)


@dataclass
class ReplayConfig:
    scenario_paths: list[Path]
    mode: str = "stub"  # "stub" (no network, no cost) or "live"
    max_cost_usd: float = 0.05
    model: str = PRODUCTION_MAIN_MODEL
    price_in_per_mtok: float = 2.0
    price_out_per_mtok: float = 12.0
    min_reserve_usd: float = 0.004
    echo: bool = True


class _LogCapture(logging.Handler):
    """Collects runtime warnings per turn (guards, repairs, swallowed failures)."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(("src", "scenario_replay")):
            message = f"{record.levelname} {record.name}: {record.getMessage()}"
            self.records.append(message[:400])

    def drain(self) -> list[str]:
        out = list(self.records)
        self.records.clear()
        return out


def _git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
        except OSError:
            return ""

    status = run("status", "--porcelain")
    return {
        "head": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty_paths": len(status.splitlines()) if status else 0,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_scenario(path: Path) -> dict[str, Any]:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(scenario, dict) or not scenario.get("turns"):
        raise ValueError(f"{path} is not a scenario file")
    return scenario


def _state_snapshot(conversation: Any) -> dict[str, Any]:
    from src.dialogue.order_state import quote_workflow_from_metadata
    from src.dialogue.state import DialogueState

    metadata = (
        conversation.metadata_ if isinstance(conversation.metadata_, dict) else {}
    )
    state = DialogueState.load(metadata)
    workflow = quote_workflow_from_metadata(metadata)
    proposal = state.last_proposal
    return {
        "sales_stage": conversation.sales_stage,
        "customer_name": conversation.customer_name,
        "language": conversation.language,
        "escalation_status": conversation.escalation_status,
        "selected_items": list(state.slots.selected_items),
        "slots": state.slots.model_dump(
            mode="json", exclude={"selected_items"}, exclude_defaults=True
        ),
        "last_proposal": proposal.model_dump(mode="json") if proposal else None,
        "quote_workflow": workflow.model_dump(mode="json"),
        "metadata_keys": sorted(metadata),
    }


def _route(response: Any) -> dict[str, Any]:
    trace = getattr(response, "repair_trace", None)
    return {
        "label": str(response.model),
        "text_provenance": response.text_provenance,
        "usage_provenance": response.usage_provenance,
        "repair_flags": [f.guard_name for f in response.repair_flags],
        "repair_judge": (
            {
                "answer": trace.answer,
                "requires_handoff": trace.requires_handoff,
                "guards": sorted({f.guard_name for f in trace.flags}),
            }
            if trace is not None
            else None
        ),
        "emitted_asks": sorted(str(a) for a in response.emitted_asks),
    }


class Replay:
    def __init__(self, config: ReplayConfig) -> None:
        self.config = config
        self.recorder = CallRecorder()
        self.search_log: list[dict[str, Any]] = []
        self.logs = _LogCapture()
        self.quote_counter = 0
        self.store: CatalogStore | None = None
        self.guard = NetworkGuard(
            allowed_hosts=frozenset({"openrouter.ai"})
            if config.mode == "live"
            else frozenset()
        )
        self.meter: CostMeter | None = None

    # -- patches ---------------------------------------------------------------

    def _install(self, stack: ExitStack, catalog_rows: list[dict[str, Any]]) -> None:
        from src.core.config import settings
        from src.dialogue.order_state import (
            QuoteConsent,
            QuoteLifecycle,
            QuoteWorkflowState,
        )
        from src.llm import engine
        from src.services.proposal_followup import record_proposal_sent

        config = self.config
        responder = StubModel(catalog_rows) if config.mode == "stub" else None
        self.meter = meter = CostMeter(
            max_cost_usd=config.max_cost_usd,
            price_in_per_mtok=config.price_in_per_mtok,
            price_out_per_mtok=config.price_out_per_mtok,
            min_reserve_usd=config.min_reserve_usd,
            responder=responder,
        )
        original_create = AsyncCompletions.create

        async def create(self_: Any, *args: Any, **kwargs: Any) -> Any:
            return await meter.intercept(original_create, self_, *args, **kwargs)

        stack.enter_context(patch.object(AsyncCompletions, "create", create))

        guard = self.guard
        original_async_send = httpx.AsyncClient.send
        original_sync_send = httpx.Client.send

        async def async_send(
            self_: Any, request: httpx.Request, *a: Any, **kw: Any
        ) -> Any:
            guard.check(request)
            return await original_async_send(self_, request, *a, **kw)

        def sync_send(self_: Any, request: httpx.Request, *a: Any, **kw: Any) -> Any:
            guard.check(request)
            return original_sync_send(self_, request, *a, **kw)

        stack.enter_context(patch.object(httpx.AsyncClient, "send", async_send))
        stack.enter_context(patch.object(httpx.Client, "send", sync_send))

        # Postgres is reached through asyncpg sockets, not httpx.
        import asyncpg

        async def no_postgres(*args: Any, **kwargs: Any) -> Any:
            guard.blocked.append("asyncpg.connect")
            raise ConnectionRefusedError("scenario replay blocks Postgres")

        stack.enter_context(patch.object(asyncpg, "connect", no_postgres))

        # Model resolution: production reads `system_configs.openrouter_model_main`
        # (and the env fallback agrees); everything downstream -- path policy,
        # reasoning effort -- is the runtime's own code.
        overrides = {"openrouter_model_main": config.model}

        async def get_system_config(_db: Any, key: str, default: str) -> str:
            return overrides.get(key, default)

        stack.enter_context(
            patch("src.core.config.get_system_config", get_system_config)
        )
        stack.enter_context(
            patch.object(settings, "openrouter_model_main", config.model)
        )

        stack.enter_context(
            patch.object(
                engine,
                "rag_search_products",
                lexical_search_factory(self._current_store, self.search_log),
            )
        )

        async def no_knowledge(*args: Any, **kwargs: Any) -> list[Any]:
            return []

        stack.enter_context(patch("src.rag.pipeline.search_knowledge", no_knowledge))
        stack.enter_context(patch.object(engine, "search_behavior_rules", no_knowledge))

        recorder = self.recorder

        def recording(name: str) -> Any:
            async def _record(*args: Any, **kwargs: Any) -> None:
                recorder.record(
                    "notification",
                    name,
                    **{
                        k: v
                        for k, v in kwargs.items()
                        if k in {"reason", "escalation_type"}
                    },
                )

            return _record

        stack.enter_context(
            patch(
                "src.integrations.notifications.escalation.notify_manager_escalation",
                recording("notify_manager_escalation"),
            )
        )
        stack.enter_context(
            patch(
                "src.services.notifications.notify_catalog_mismatch",
                recording("notify_catalog_mismatch"),
            )
        )
        stack.enter_context(
            patch(
                "src.llm.safety.notify_llm_safety_event", recording("llm_safety_event")
            )
        )

        async def send_scope_ok(*args: Any, **kwargs: Any) -> None:
            return None

        stack.enter_context(
            patch("src.services.outbound_safety._SendScope.check", send_scope_ok)
        )

        original_quotation = engine._create_quotation

        async def create_quotation_boundary(ctx: Any, items: Any) -> str:
            zoho = ctx.deps.zoho_inventory
            zoho.quotation_boundary_armed = True
            try:
                return str(await original_quotation(ctx, items))
            except QuotationGatesPassed:
                pass
            finally:
                zoho.quotation_boundary_armed = False
            self.quote_counter += 1
            quote_number = f"SO-REPLAY-{self.quote_counter:04d}"
            conversation = ctx.deps.conversation
            record_proposal_sent(
                conversation,
                sent_at=datetime.datetime.now(datetime.UTC),
                kp_message_id=quote_number,
                quote_number=quote_number,
                sale_order_id=f"fake-so-{self.quote_counter}",
            )
            recorder.record(
                "quotation",
                "create_quotation(fake success)",
                quote_number=quote_number,
                items=[item.model_dump() for item in items],
            )
            ctx.deps.quotation_created = True
            if engine._has_canonical_quote_workflow(conversation):
                await engine._store_quote_workflow(
                    ctx.deps.db,
                    conversation,
                    QuoteWorkflowState(
                        consent=QuoteConsent.GRANTED,
                        lifecycle=QuoteLifecycle.CREATED,
                    ),
                )
            return engine._quotation_prepared_message(conversation, quote_number)

        stack.enter_context(
            patch.object(engine, "_create_quotation", create_quotation_boundary)
        )

    def _current_store(self) -> CatalogStore:
        if self.store is None:
            raise RuntimeError("no scenario is running")
        return self.store

    # -- run -------------------------------------------------------------------

    async def run(self) -> dict[str, Any]:
        config = self.config
        scenarios = [(p, load_scenario(p)) for p in config.scenario_paths]
        catalog_paths = {
            REPO_ROOT / s.get("fixtures", {}).get("catalog", "") for _, s in scenarios
        }
        first_catalog = sorted(catalog_paths)[0]
        root_logger = logging.getLogger()
        root_logger.addHandler(self.logs)
        results: list[dict[str, Any]] = []
        started = time.monotonic()
        try:
            with ExitStack() as stack:
                self._install(stack, load_catalog_rows(first_catalog))
                for path, scenario in scenarios:
                    result = await self._run_scenario(path, scenario)
                    results.append(result)
                    if self.meter is not None and self.meter.stopped_reason:
                        break
        finally:
            root_logger.removeHandler(self.logs)
        meter = self.meter
        assert meter is not None
        ran = {r["id"] for r in results}
        return {
            "run": {
                "mode": "live model via OpenRouter; intercepted tools/DB/Redis/messaging"
                if config.mode == "live"
                else "dry: stub model at the completions seam; no network",
                "requested_main_model": config.model,
                "models_called": sorted({c.model for c in meter.calls}),
                "reasoning_sent": sorted(
                    {
                        json.dumps(c.reasoning, sort_keys=True)
                        for c in meter.calls
                        if c.reasoning
                    }
                ),
                "git": _git_state(),
                "catalog": {
                    str(p.relative_to(REPO_ROOT)): _sha256(p)
                    for p in sorted(catalog_paths)
                },
                "max_cost_usd": config.max_cost_usd,
                "total_cost_usd": round(meter.spent, 8),
                "cost_sources": sorted({c.cost_source for c in meter.calls}),
                "model_calls": len(meter.calls),
                "stopped_by_budget": meter.stopped_reason,
                "scenarios_not_run": [
                    s["id"] for _, s in scenarios if s["id"] not in ran
                ],
                "network_blocked": list(self.guard.blocked),
                "elapsed_s": round(time.monotonic() - started, 1),
                "limitations": list(LIMITATIONS),
            },
            "scenarios": results,
        }

    async def _run_scenario(
        self, path: Path, scenario: dict[str, Any]
    ) -> dict[str, Any]:
        from src.models.conversation import Conversation

        fixtures = scenario.get("fixtures", {})
        catalog_rows = load_catalog_rows(REPO_ROOT / fixtures["catalog"])
        self.store = store = CatalogStore(catalog_rows)
        customer = scenario.get("customer", {})
        conversation = Conversation(
            phone=str(customer.get("phone", "+971500000000")),
            language=str(customer.get("language", "en")),
            customer_name=None,
            sales_stage="greeting",
            status="active",
            escalation_status="none",
            metadata_={},
        )
        conversation.id = uuid.uuid4()
        db = FakeAsyncSession(store, conversation)
        zoho = FakeZohoInventory(
            store, self.recorder, fixtures.get("live_stock_overrides") or {}
        )
        crm = FakeCRM(self.recorder)
        messaging = FakeMessaging(self.recorder)
        redis = FakeRedis()
        embedding = StubEmbedding()
        turns: list[dict[str, Any]] = []
        self._echo(
            f"\n=== Scenario {scenario['id']} ({scenario.get('source_conversation', '')}) ==="
        )
        try:
            for number, turn_spec in enumerate(scenario["turns"], start=1):
                record = await self._run_turn(
                    scenario_id=str(scenario["id"]),
                    number=number,
                    text=str(turn_spec["text"]),
                    conversation=conversation,
                    db=db,
                    zoho=zoho,
                    crm=crm,
                    messaging=messaging,
                    redis=redis,
                    embedding=embedding,
                )
                turns.append(record)
                if record.get("status") == "budget_stopped":
                    break
        finally:
            store.close()
            self.store = None
        checks = run_checks(scenario.get("checks", []), turns)
        cost = round(sum(t.get("cost_usd", 0.0) for t in turns), 8)
        self._echo(f"--- Scenario {scenario['id']} cost ${cost:.6f}")
        for check in checks:
            self._echo(f"    check {check['type']}: {check['status']}")
        return {
            "id": scenario["id"],
            "file": str(path.relative_to(REPO_ROOT))
            if path.is_relative_to(REPO_ROOT)
            else str(path),
            "source_conversation": scenario.get("source_conversation"),
            "description": scenario.get("description"),
            "cost_usd": cost,
            "turns": turns,
            "checks": checks,
        }

    async def _run_turn(
        self,
        *,
        scenario_id: str,
        number: int,
        text: str,
        conversation: Any,
        db: FakeAsyncSession,
        zoho: FakeZohoInventory,
        crm: FakeCRM,
        messaging: FakeMessaging,
        redis: FakeRedis,
        embedding: StubEmbedding,
    ) -> dict[str, Any]:
        from src.llm import engine
        from src.models.message import Message, message_created_at_now
        from src.services.chat import _send_deferred_product_media
        from src.services.escalation_state import should_send_escalation_fallback
        from src.services.proposal_followup import record_customer_reply

        meter = self.meter
        assert meter is not None
        meter.start_turn()
        self.recorder.drain()
        self.logs.drain()
        db.log.drain()
        self.search_log.clear()
        label = f"{scenario_id}{number}"
        record: dict[str, Any] = {"index": number, "user": text}
        if should_send_escalation_fallback(conversation.escalation_status):
            record.update(
                status="skipped_escalation_fallback",
                reply=None,
                note="production sends the escalation fallback and skips the model",
            )
            self._echo(
                f"[{label}] skipped: escalation {conversation.escalation_status}"
            )
            return record

        source_message_id = f"replay-{scenario_id}-{number}"
        received_at = datetime.datetime.now(datetime.UTC)
        db.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=text,
                message_type="text",
                wazzup_message_id=source_message_id,
                created_at=message_created_at_now(),
            )
        )
        record_customer_reply(conversation, text=text, received_at=received_at)
        await db.commit()

        started = time.monotonic()
        response: Any = None
        try:
            response = await engine.process_message(
                conversation_id=conversation.id,
                combined_text=text,
                db=db,  # type: ignore[arg-type]
                redis=redis,
                embedding_engine=embedding,  # type: ignore[arg-type]
                zoho_client=zoho,  # type: ignore[arg-type]
                messaging_client=messaging,  # type: ignore[arg-type]
                crm_client=crm,  # type: ignore[arg-type]
                source_message_id=source_message_id,
            )
        except BudgetExhausted:
            pass
        except BaseExceptionGroup as group:
            if group.subgroup(BudgetExhausted) is None:
                raise
        record["elapsed_s"] = round(time.monotonic() - started, 1)
        record["model_calls"] = [c.as_dict() for c in meter.turn_calls]
        record["cost_usd"] = round(sum(c.cost_usd for c in meter.turn_calls), 8)
        if meter.stopped_reason is not None:
            record.update(
                status="budget_stopped",
                reply=None,
                discarded_reply=getattr(response, "text", None),
                stop_reason=meter.stopped_reason,
            )
            self._echo(f"[{label}] STOPPED by budget: {meter.stopped_reason}")
            return record
        assert response is not None

        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=response.text,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cost=response.cost,
                model=response.model,
                created_at=message_created_at_now(),
            )
        )
        await db.commit()
        store = self._current_store()
        media = [
            {
                "sku": store.sku_for_key(item.product_key),
                "product_key": item.product_key,
                "caption": item.caption,
                "url": item.url,
            }
            for item in response.deferred_product_media
        ]
        if response.deferred_product_media:
            await _send_deferred_product_media(
                db,
                provider=messaging,
                conversation_id=conversation.id,
                chat_id="replay-chat",
                source_message_id=source_message_id,
                follow_up_suppressed=False,
                media_items=response.deferred_product_media,
            )
        external = self.recorder.drain()
        tools_called = [
            {
                "name": call["name"],
                "arguments": call["arguments"],
                "model_call": c.index,
            }
            for c in meter.turn_calls
            for call in c.tool_calls
            if call.get("name") != "final_result"
        ]
        record.update(
            status="ok",
            reply=response.text,
            route=_route(response),
            tools_called=tools_called,
            media=media,
            media_sends=[e for e in external if e["method"] == "send_media"],
            external_calls=[e for e in external if e["method"] != "send_media"],
            catalog_searches=list(self.search_log),
            state=_state_snapshot(conversation),
            db=db.log.drain(),
            warnings=self.logs.drain(),
        )
        self._echo_turn(label, record)
        return record

    # -- output ----------------------------------------------------------------

    def _echo(self, line: str) -> None:
        if self.config.echo:
            print(line, flush=True)

    def _echo_turn(self, label: str, record: dict[str, Any]) -> None:
        if not self.config.echo:
            return
        tools = ", ".join(t["name"] for t in record["tools_called"]) or "-"
        media = (
            ", ".join(str(m["sku"] or m["product_key"]) for m in record["media"]) or "-"
        )
        print(
            f"\n[{label}] cost ${record['cost_usd']:.6f} calls={len(record['model_calls'])} "
            f"route={record['route']['label']} ({record['route']['text_provenance']})"
        )
        print(f"  USER: {record['user']}")
        print(f"  TOOLS: {tools}")
        print(f"  MEDIA: {media}")
        print("  BOT: " + record["reply"].replace("\n", "\n       "))


def recheck_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Re-run the scenario files' current checks over recorded turns (no model)."""

    for scenario in receipt["scenarios"]:
        spec = load_scenario(REPO_ROOT / scenario["file"])
        scenario["checks"] = run_checks(spec.get("checks", []), scenario["turns"])
    receipt["run"]["checks_rerun_offline"] = True
    return receipt
