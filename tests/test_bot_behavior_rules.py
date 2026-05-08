from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import pytest


def _rule(**overrides: Any) -> Any:
    from src.models.bot_behavior_rule import BotBehaviorRule

    data = {
        "id": uuid.uuid4(),
        "title": "Default rule",
        "type": "hard_rule",
        "status": "active",
        "priority": 50,
        "scope": "global",
        "stage": None,
        "language": None,
        "segment": None,
        "instruction": "Default instruction.",
        "trigger_examples": [],
        "embedding": [0.1] * 1024,
        "created_by": "admin",
        "updated_by": "admin",
        "created_at": datetime(2026, 5, 8, 12, 0, 0),
        "updated_at": None,
        "archived_at": None,
    }
    data.update(overrides)
    return BotBehaviorRule(**data)


@pytest.mark.asyncio
async def test_search_behavior_rules_filters_status_scope_and_sorts_priority() -> None:
    from src.services.bot_behavior_rules import (
        BehaviorRuleSearchContext,
        search_behavior_rules,
    )

    hard_match = _rule(
        title="Ask name",
        priority=10,
        scope="stage",
        stage="greeting",
        instruction="Ask how to address the customer when their name is missing.",
    )
    segment_match = _rule(
        title="Wholesale upsell",
        type="upsell_rule",
        priority=40,
        scope="segment",
        segment="Wholesale",
        instruction="Offer bulk-friendly alternatives after answering the main need.",
    )
    draft_rule = _rule(title="Draft rule", status="draft", priority=1)
    wrong_stage = _rule(title="Wrong stage", stage="feedback", priority=5)

    class FakeScalarResult:
        def __init__(self, rows: list[Any]) -> None:
            self._rows = rows

        def all(self) -> list[Any]:
            return self._rows

    class FakeResult:
        def __init__(self, rows: list[Any]) -> None:
            self._rows = rows

        def scalars(self) -> FakeScalarResult:
            return FakeScalarResult(self._rows)

    class FakeDB:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, _stmt: object) -> FakeResult:
            self.calls += 1
            if self.calls == 1:
                return FakeResult([hard_match, draft_rule, wrong_stage])
            return FakeResult([segment_match])

    class FakeEmbeddingEngine:
        async def embed_async(self, text: str) -> list[float]:
            assert "chairs" in text.lower()
            return [0.2] * 1024

    rules = await search_behavior_rules(
        db=FakeDB(),
        context=BehaviorRuleSearchContext(
            message="I need 20 chairs",
            stage="greeting",
            language="en",
            segment="wholesale",
        ),
        embedding_engine=FakeEmbeddingEngine(),
    )

    assert [rule.title for rule in rules] == ["Ask name", "Wholesale upsell"]


def test_format_behavior_rules_prompt_keeps_rules_separate_from_faq() -> None:
    from src.services.bot_behavior_rules import format_behavior_rules_prompt

    block = format_behavior_rules_prompt(
        [
            _rule(
                id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                title="Ask name",
                priority=10,
                instruction="Ask how to address the customer.",
            )
        ]
    )

    assert block.startswith("[BOT OPERATING RULES]")
    assert "Ask name" in block
    assert "Ask how to address the customer." in block
    assert "[KNOWLEDGE BASE" not in block
