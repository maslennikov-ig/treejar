from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from src.core.database import async_session_factory
from src.models.conversation import Conversation
from src.models.message import Message
from src.models.metrics_snapshot import MetricsSnapshot


async def calculate_and_store_metrics(ctx: dict[str, Any]) -> None:
    """
    Background job to aggregate metrics and store them in the MetricsSnapshot table.
    We calculate 'all_time' metrics to keep the dashboard fast.
    """
    async with async_session_factory() as db:
        # Total conversations
        total_convs = await db.scalar(select(func.count(Conversation.id))) or 0

        # Messages sent by assistant
        msgs_sent = (
            await db.scalar(
                select(func.count(Message.id)).where(Message.role == "assistant")
            )
            or 0
        )

        # LLM Cost USD
        cost = await db.scalar(select(func.sum(Message.cost))) or 0.0

        # Escalations
        escalations = (
            await db.scalar(
                select(func.count(Conversation.id)).where(
                    Conversation.escalation_status != "none"
                )
            )
            or 0
        )

        # Deals created
        deals = (
            await db.scalar(
                select(func.count(Conversation.id)).where(
                    Conversation.zoho_deal_id.is_not(None)
                )
            )
            or 0
        )

        # Quotes generated
        quotes = (
            await db.scalar(
                select(func.count(Message.id)).where(Message.message_type == "quote")
            )
            or 0
        )

        # Prepare the UPSERT statement
        stmt = insert(MetricsSnapshot).values(
            period="all_time",
            total_conversations=total_convs,
            messages_sent=msgs_sent,
            avg_response_time_ms=0.0,
            llm_cost_usd=float(cost),
            escalations=escalations,
            deals_created=deals,
            quotes_generated=quotes,
        )

        # On conflict (e.g., if 'all_time' already exists), update the values
        stmt = stmt.on_conflict_do_update(
            index_elements=["period"],
            set_=dict(
                total_conversations=stmt.excluded.total_conversations,
                messages_sent=stmt.excluded.messages_sent,
                avg_response_time_ms=stmt.excluded.avg_response_time_ms,
                llm_cost_usd=stmt.excluded.llm_cost_usd,
                escalations=stmt.excluded.escalations,
                deals_created=stmt.excluded.deals_created,
                quotes_generated=stmt.excluded.quotes_generated,
            ),
        )

        await db.execute(stmt)
        await db.commit()
