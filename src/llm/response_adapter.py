"""Manager response adapter — polishes raw manager drafts into customer-friendly messages.

Uses a PydanticAI Agent with the fast OpenRouter model to transform short,
technical manager responses into warm, professional answers suitable for
WhatsApp delivery to Treejar customers.
"""

from __future__ import annotations

import asyncio
import logging

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from src.core.config import settings

logger = logging.getLogger(__name__)


ADAPTER_SYSTEM_PROMPT = """\
You are a senior customer service writer at Treejar, a premium office furniture \
company in the UAE.

Your task is to adapt a short, technical, or rough draft from a sales manager \
into a warm, professional, and clear message for the customer.

INSTRUCTIONS:
1. Rewrite the draft as a friendly, caring, and professional response on behalf of Treejar.
2. Preserve ALL factual content (numbers, dates, prices, conditions). \
   Do NOT invent or alter any facts.
3. Add a brief greeting and an offer of further help when appropriate.
4. Reply in the language specified in the user request (e.g. 'en', 'ar', 'ru').
5. Use WhatsApp formatting: *bold*, _italic_ (NOT Markdown headers or links).
6. Return ONLY the final message text, no commentary.
"""

adapter_model = OpenAIChatModel(
    settings.openrouter_model_fast,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
)

response_adapter_agent: Agent[None, str] = Agent(
    model=adapter_model,
    system_prompt=ADAPTER_SYSTEM_PROMPT,
)


async def adapt_manager_response(
    question: str, draft: str, language: str = "en"
) -> str:
    """Adapt a manager's rough draft into a polished customer message.

    Args:
        question: The original customer question.
        draft: The manager's short/technical response draft.
        language: The target language code (e.g., 'en', 'ar', 'ru').

    Returns:
        A polished, customer-friendly message ready for WhatsApp delivery in the target language.
    """
    user_prompt = (
        f"Customer question: {question}\n\n"
        f"Manager draft: {draft}\n\n"
        f"Rewrite the draft as a polished customer message in language code '{language}'.\n"
        "Translate the manager draft into the requested language if necessary."
    )

    logger.info("Adapting manager response for question: %s", question[:80])
    result = await asyncio.wait_for(
        response_adapter_agent.run(user_prompt), timeout=30.0
    )
    return result.output
