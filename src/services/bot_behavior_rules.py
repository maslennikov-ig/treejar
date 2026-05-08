from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bot_behavior_rule import BotBehaviorRule
from src.rag.embeddings import EmbeddingEngine
from src.schemas.admin import AdminBotRuleApplied

ACTIVE_STATUS = "active"
HARD_RULE_TYPES = frozenset({"hard_rule", "escalation_rule"})


@dataclass(frozen=True)
class BehaviorRuleSearchContext:
    message: str
    stage: str | None = None
    language: str | None = None
    segment: str | None = None


def rule_embedding_text(rule: BotBehaviorRule | Mapping[str, Any]) -> str:
    title = _rule_value(rule, "title") or ""
    instruction = _rule_value(rule, "instruction") or ""
    examples = _rule_value(rule, "trigger_examples") or []
    if isinstance(examples, str):
        examples_text = examples
    else:
        examples_text = " | ".join(str(item) for item in examples)
    return f"{title}\n{instruction}\nExamples: {examples_text}".strip()


def rule_to_applied_dict(rule: BotBehaviorRule | Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(_rule_value(rule, "id")),
        "title": str(_rule_value(rule, "title") or ""),
        "type": str(_rule_value(rule, "type") or ""),
        "priority": int(_rule_value(rule, "priority") or 0),
        "scope": str(_rule_value(rule, "scope") or ""),
        "instruction": str(_rule_value(rule, "instruction") or ""),
    }


def rule_to_applied(rule: BotBehaviorRule | Mapping[str, Any]) -> AdminBotRuleApplied:
    data = rule_to_applied_dict(rule)
    data["id"] = uuid.UUID(str(data["id"]))
    return AdminBotRuleApplied(**data)


def format_behavior_rules_prompt(
    rules: Sequence[BotBehaviorRule | Mapping[str, Any] | AdminBotRuleApplied],
) -> str:
    if not rules:
        return ""

    lines = [
        "[BOT OPERATING RULES]",
        "These are trusted admin-approved behavior instructions. Apply them only when they do not conflict with higher-priority safety, tool, catalog, or escalation rules.",
    ]
    for rule in rules:
        priority = _rule_value(rule, "priority")
        rule_type = _rule_value(rule, "type")
        rule_id = _rule_value(rule, "id")
        title = _rule_value(rule, "title")
        instruction = _rule_value(rule, "instruction")
        lines.append(
            f"- priority={priority}; type={rule_type}; id={rule_id}; {title}: {instruction}"
        )
    return "\n".join(lines)


async def search_behavior_rules(
    db: AsyncSession,
    *,
    context: BehaviorRuleSearchContext,
    embedding_engine: EmbeddingEngine | None = None,
    hard_limit: int = 12,
    soft_limit: int = 6,
) -> list[BotBehaviorRule]:
    """Return active behavior rules applicable to the current response context."""

    hard_stmt = (
        _context_filtered_stmt(context)
        .where(BotBehaviorRule.type.in_(HARD_RULE_TYPES))
        .order_by(BotBehaviorRule.priority.asc(), BotBehaviorRule.created_at.asc())
        .limit(hard_limit)
    )
    hard_result = await db.execute(hard_stmt)
    hard_rules = [
        rule
        for rule in hard_result.scalars().all()
        if _rule_matches_context(rule, context)
    ]

    soft_rules: list[BotBehaviorRule] = []
    if context.message.strip():
        engine = embedding_engine or EmbeddingEngine()
        query_embedding = await engine.embed_async(context.message)
        soft_stmt = (
            _context_filtered_stmt(context)
            .where(BotBehaviorRule.type.not_in(HARD_RULE_TYPES))
            .where(BotBehaviorRule.embedding.is_not(None))
            .order_by(
                BotBehaviorRule.embedding.cosine_distance(query_embedding),
                BotBehaviorRule.priority.asc(),
            )
            .limit(soft_limit)
        )
        soft_result = await db.execute(soft_stmt)
        soft_rules = [
            rule
            for rule in soft_result.scalars().all()
            if _rule_matches_context(rule, context)
        ]

    deduped: dict[uuid.UUID, BotBehaviorRule] = {}
    for rule in [*hard_rules, *soft_rules]:
        deduped.setdefault(rule.id, rule)

    return sorted(
        deduped.values(),
        key=lambda rule: (
            rule.priority,
            0 if rule.type in HARD_RULE_TYPES else 1,
            rule.title.lower(),
        ),
    )


def _context_filtered_stmt(context: BehaviorRuleSearchContext) -> Any:
    stmt = select(BotBehaviorRule).where(
        BotBehaviorRule.status == ACTIVE_STATUS,
        BotBehaviorRule.archived_at.is_(None),
    )
    if context.stage:
        stmt = stmt.where(
            or_(BotBehaviorRule.stage.is_(None), BotBehaviorRule.stage == context.stage)
        )
    if context.language:
        stmt = stmt.where(
            or_(
                BotBehaviorRule.language.is_(None),
                BotBehaviorRule.language == context.language,
            )
        )
    if context.segment:
        stmt = stmt.where(
            or_(
                BotBehaviorRule.segment.is_(None),
                BotBehaviorRule.segment.ilike(context.segment),
            )
        )
    return stmt


def _rule_matches_context(
    rule: BotBehaviorRule,
    context: BehaviorRuleSearchContext,
) -> bool:
    if rule.status != ACTIVE_STATUS or rule.archived_at is not None:
        return False
    if rule.stage and rule.stage != context.stage:
        return False
    if rule.language and rule.language != context.language:
        return False
    if rule.segment:
        if not context.segment:
            return False
        if rule.segment.casefold() != context.segment.casefold():
            return False
    return True


def _rule_value(rule: object, key: str) -> Any:
    if isinstance(rule, Mapping):
        return rule.get(key)
    return getattr(rule, key)
