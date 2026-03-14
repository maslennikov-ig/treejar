import datetime
from typing import Any

from logfire import Logfire
from sqlalchemy import select

from src.core.database import async_session_factory
from src.core.redis import get_redis_client
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.messaging.wazzup import WazzupProvider
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.schemas.common import EscalationStatus

logfire = Logfire()


async def run_automatic_followups(ctx: dict[str, Any]) -> None:
    """Cron job to process and send follow-up messages."""
    logfire.info("Starting automatic follow-ups cron job")

    async with async_session_factory() as db:
        now = datetime.datetime.now(datetime.UTC)

        # We target conversations that have not been escalated, have no messages in last X hours
        # and match 24h, 72h (3d), or 168h (7d) inactivity within a 1-hour window.

        intervals = [
            (24, 25),  # 1 day
            (72, 73),  # 3 days
            (168, 169),  # 7 days
        ]

        for min_hrs, max_hrs in intervals:
            min_time = now - datetime.timedelta(hours=max_hrs)
            max_time = now - datetime.timedelta(hours=min_hrs)

            stmt = select(Conversation).where(
                Conversation.updated_at >= min_time,
                Conversation.updated_at < max_time,
                Conversation.escalation_status == EscalationStatus.NONE.value,
            )

            result = await db.execute(stmt)
            conversations: list[Conversation] = list(result.scalars().all())

            logfire.info(
                "Found {count} conversations for {hours}h follow-up",
                count=len(conversations),
                hours=min_hrs,
            )

            for conv in conversations:
                try:
                    await _process_followup_for_conversation(db, conv)
                except Exception as e:
                    logfire.error(
                        "Failed to process followup for {conv_id}: {error}",
                        conv_id=conv.id,
                        error=str(e),
                    )


async def _process_followup_for_conversation(db: Any, conv: Conversation) -> None:
    """Generates and sends a follow-up for a specific conversation."""
    logfire.info(f"Processing follow-up for conversation {conv.id}")

    # We simulate a "system" ping to the agent, asking it to draft a follow-up.
    system_instruction = "SYSTEM: The user has been inactive. Draft a polite, short follow-up acknowledging the previous quotes/discussion. Make it a single short paragraph. Do not push, just offer help."

    redis = get_redis_client()
    engine = EmbeddingEngine()
    zoho_crm = ZohoCRMClient(redis)
    messaging = WazzupProvider()
    zoho = None

    from src.integrations.inventory.zoho_inventory import ZohoInventoryClient

    zoho = ZohoInventoryClient(redis)

    # Normally, process_message saves user message, calls LLM, saves AIMessage, sends message.
    # Because this is a system-initiated message, we will call the LLM directly
    # and then use messaging_client to send it, and save the AI message manually to DB.

    from src.llm.context import build_message_history
    from src.llm.engine import SalesDeps, sales_agent
    from src.llm.pii import unmask_pii
    from src.models.message import Message

    # 1. Provide context
    pii_map: dict[str, str] = {}
    history = await build_message_history(db, conv.id, pii_map)

    # Fetch CRM Context
    crm_context = None
    if conv.phone:
        from src.core.cache import get_cached_crm_profile

        crm_context = await get_cached_crm_profile(redis, conv.phone)

    deps = SalesDeps(
        db=db,
        redis=redis,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map=pii_map,
        crm_context=crm_context,
    )

    # 2. Call LLM with the instruction appended to history as a faux System requirement
    # Or simply run the agent with the internal message
    result = await sales_agent.run(
        system_instruction,
        deps=deps,
        message_history=history,
    )

    final_text = unmask_pii(result.output, pii_map)

    # 3. Save AI message to DB
    ai_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=final_text,
        tokens_in=result.usage().input_tokens if result.usage() else None,
        tokens_out=result.usage().output_tokens if result.usage() else None,
    )
    db.add(ai_msg)
    await db.commit()

    # 4. Send message
    await messaging.send_text(conv.phone, final_text)
    logfire.info(f"Follow-up sent successfully to {conv.phone}")
