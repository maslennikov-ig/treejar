"""Manager response adapter — polishes raw manager drafts into customer-friendly messages.

Uses a PydanticAI Agent with the fast OpenRouter model to transform short,
technical manager responses into warm, professional answers suitable for
WhatsApp delivery to Treejar customers.
"""

from __future__ import annotations

import logging
from typing import cast

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from src.core.config import settings
from src.llm.safety import (
    PATH_AUTO_FAQ_CANDIDATE,
    PATH_RESPONSE_ADAPTER,
    model_name_for_path,
    model_settings_for_path,
    run_agent_with_safety,
)
from src.services.auto_faq_types import AutoFAQCandidate

logger = logging.getLogger(__name__)
ADAPTER_MODEL_NAME = model_name_for_path(PATH_RESPONSE_ADAPTER)
AUTO_FAQ_CANDIDATE_MODEL_NAME = model_name_for_path(PATH_AUTO_FAQ_CANDIDATE)


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

COMBINED_AUTO_FAQ_SYSTEM_PROMPT = """\
You are a senior customer service writer and knowledge-base editor at Treejar, \
a premium office furniture company in the UAE.

You must produce a structured result with:
1. customer_message: a warm, professional WhatsApp-ready reply to the customer.
2. kb_candidate: a generalized English FAQ candidate, or null when the manager \
draft is not safe and reusable as global knowledge.

Customer message rules:
- Preserve all factual content from the manager draft.
- Do not invent prices, dates, delivery promises, discounts, or policies.
- Reply in the requested language code.
- Use WhatsApp formatting only.

FAQ candidate rules:
- Write the candidate in English, as a reusable Q&A for future customers.
- Generalize the customer question without names, order details, locations, \
dates, discounts, project logistics, or one-off commitments.
- Include only facts explicitly supported by the manager draft.
- Set confidence from 0.0 to 1.0. Use below 0.75 when the answer is \
context-specific, uncertain, or only useful for this customer.
- Return kb_candidate as null if there is no broadly reusable FAQ fact.
"""


class ManagerReplyWithAutoFAQResult(BaseModel):
    """Structured combined output for explicit add-to-KB manager replies."""

    model_config = ConfigDict(str_strip_whitespace=True)

    customer_message: str = Field(min_length=1, max_length=3000)
    kb_candidate: AutoFAQCandidate | None = None


adapter_model = OpenAIChatModel(
    ADAPTER_MODEL_NAME,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
    settings=model_settings_for_path(
        PATH_RESPONSE_ADAPTER,
        model_name=ADAPTER_MODEL_NAME,
    ),
)

response_adapter_agent: Agent[None, str] = Agent(
    model=adapter_model,
    system_prompt=ADAPTER_SYSTEM_PROMPT,
    retries=0,
    model_settings=model_settings_for_path(
        PATH_RESPONSE_ADAPTER,
        model_name=ADAPTER_MODEL_NAME,
    ),
)

auto_faq_manager_reply_model = OpenAIChatModel(
    AUTO_FAQ_CANDIDATE_MODEL_NAME,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
    settings=model_settings_for_path(
        PATH_AUTO_FAQ_CANDIDATE,
        model_name=AUTO_FAQ_CANDIDATE_MODEL_NAME,
    ),
)

auto_faq_manager_reply_agent: Agent[None, ManagerReplyWithAutoFAQResult] = Agent(
    model=auto_faq_manager_reply_model,
    output_type=ManagerReplyWithAutoFAQResult,
    system_prompt=COMBINED_AUTO_FAQ_SYSTEM_PROMPT,
    retries=0,
    model_settings=model_settings_for_path(
        PATH_AUTO_FAQ_CANDIDATE,
        model_name=AUTO_FAQ_CANDIDATE_MODEL_NAME,
    ),
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
    result = await run_agent_with_safety(
        response_adapter_agent,
        PATH_RESPONSE_ADAPTER,
        user_prompt,
        model_name=ADAPTER_MODEL_NAME,
    )
    return cast("str", result.output)


async def adapt_manager_response_with_faq_candidate(
    question: str, draft: str, language: str = "en"
) -> ManagerReplyWithAutoFAQResult:
    """Adapt a manager reply and propose a KB candidate in one LLM call.

    This function is only for explicit "add to KB" manager actions. Normal
    manager replies should use :func:`adapt_manager_response` so they do not
    generate Auto-FAQ candidates.
    """
    user_prompt = (
        f"Customer question: {question}\n\n"
        f"Manager draft: {draft}\n\n"
        f"Requested customer message language code: '{language}'.\n"
        "Return the structured customer_message and kb_candidate fields."
    )

    logger.info("Adapting manager response with Auto-FAQ candidate: %s", question[:80])
    result = await run_agent_with_safety(
        auto_faq_manager_reply_agent,
        PATH_AUTO_FAQ_CANDIDATE,
        user_prompt,
        model_name=AUTO_FAQ_CANDIDATE_MODEL_NAME,
    )
    return cast("ManagerReplyWithAutoFAQResult", result.output)
