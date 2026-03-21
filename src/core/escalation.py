from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from src.core.config import settings
from src.schemas.common import EscalationType


class EscalationEvaluation(BaseModel):
    should_escalate: bool = Field(
        description="True if any of the escalation triggers apply to this message."
    )
    reason: str | None = Field(
        default=None,
        description="The specific trigger reason if should_escalate is True, else None.",
    )
    escalation_type: EscalationType = Field(
        default=EscalationType.GENERAL,
        description=(
            "Type of escalation: 'order_confirmation' for triggers 1,3 "
            "(B2B/wholesale order, high-value order), "
            "'human_requested' for trigger 12 (explicit manager request), "
            "'general' for all other triggers."
        ),
    )


ESCALATION_SYSTEM_PROMPT = """
You are an escalation detection agent. Your job is to analyze the user's incoming message and determine if it explicitly matches any of the following 18 triggers for handing the chat over to a human manager.

TRIGGERS:
1. B2B / Wholesale inquiry
2. Wants to become a distributor/dealer
3. Order value likely exceeds 10,000 AED
4. Asking for a customized product
5. Requesting a site visit or meeting
6. Requesting a physical sample
7. Highly technical questions about materials or certifications
8. Complaining about a delayed order
9. Received a damaged/wrong product
10. Asking for a refund or return
11. Expressing strong frustration or using profanity
12. Explicitly asking to "speak to a human" or "manager"
13. Asking for a special discount beyond normal bounds
14. Threatening legal action
15. Reporting a bug or technical issue on the website
16. Asking questions about job openings/careers
17. Media/PR inquiries
18. Repeatedly asking the same question the bot cannot answer

Return should_escalate=True if ANY of these strongly match. Provide the reason.
If none match, return should_escalate=False.

Also classify the escalation_type:
- 'order_confirmation' if trigger 1 or 3 applies (B2B/wholesale or high-value order)
- 'human_requested' if trigger 12 applies (customer explicitly asked for a human)
- 'general' for all other triggers
"""


escalation_model = OpenAIChatModel(
    settings.openrouter_model_fast,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
)

escalation_agent = Agent(
    model=escalation_model,
    system_prompt=ESCALATION_SYSTEM_PROMPT,
    output_type=EscalationEvaluation,
)


async def evaluate_escalation_triggers(message: str) -> EscalationEvaluation:
    """Evaluate if a message triggers an escalation."""
    result = await escalation_agent.run(message)
    return result.output
