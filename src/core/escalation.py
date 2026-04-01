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
            "Type of escalation: 'order_confirmation' for triggers 1,3,19 "
            "(concrete B2B order, high-value order, or explicit order confirmation), "
            "'human_requested' for trigger 12 (explicit manager request), "
            "'general' for all other triggers."
        ),
    )


ESCALATION_SYSTEM_PROMPT = """
You are an escalation detection agent. Your job is to analyze the user's incoming message and determine if it explicitly matches any of the following triggers for handing the chat over to a human manager.

IMPORTANT RULES:
- DO NOT escalate simple product questions, even if they mention "wholesale", "MOQ", or "bulk".
- Only escalate if the customer shows CLEAR INTENT to place a large order, not just asking for information.
- Questions like "what is your MOQ?" or "do you sell wholesale?" are normal inquiries the bot can handle. DO NOT escalate these.

TRIGGERS:
1. Customer places a concrete B2B/wholesale ORDER with quantities, company name, or delivery details (NOT just asking about wholesale/MOQ)
2. Wants to become an official distributor or dealer (not just wholesale buyer)
3. Order value clearly exceeds 10,000 AED (customer specifies quantities/items that total over this)
4. Asking for a customized/modified product (not in catalog)
5. Requesting a site visit or in-person meeting
6. Requesting a physical sample to be shipped
7. Highly technical questions about materials, certifications, or compliance that the bot cannot answer
8. Complaining about a delayed existing order
9. Received a damaged or wrong product
10. Asking for a refund or return
11. Expressing strong frustration or using profanity
12. Explicitly asking to "speak to a human", "manager", or "real person"
13. Asking for a special discount beyond normal bounds (negotiating price)
14. Threatening legal action
15. Reporting a bug or technical issue on the website
16. Asking questions about job openings or careers
17. Media or PR inquiries
18. Repeatedly asking the same question the bot cannot answer (3+ times)
19. Customer explicitly confirms they want to place an order / proceed to payment / finalize a deal

Return should_escalate=True ONLY if a trigger STRONGLY matches. Provide the reason.
If the message is just an inquiry or question, return should_escalate=False.

Also classify the escalation_type:
- 'order_confirmation' ONLY if trigger 1, 3, or 19 applies (customer is actively placing/confirming a concrete order)
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
