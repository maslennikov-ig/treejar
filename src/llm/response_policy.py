"""Shared response-policy composition helpers."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import partial
from typing import Literal

from src.llm.closed_question_guard import (
    apply_closed_question_guard,
    response_asks_customer_name,
)
from src.llm.grounding_output import (
    GroundingOutputResult,
    classify_grounding_output,
    flagged_grounding_sentences,
    repair_grounding_output,
)
from src.llm.opening_guard import apply_opening_guard, opening_replacement_covers
from src.llm.sales_turn_guard import (
    carry_the_company_question,
    collapse_question_form,
    commit_to_what_you_deferred,
    only_asks_were_dropped,
    refuse_to_chase_the_name,
)
from src.services.customer_language import is_arabic_customer_language

logger = logging.getLogger(__name__)

ReplyProvenance = Literal[
    "model",
    "model_repaired",
    "deterministic_replacement",
    "deterministic_static",
]


class AskKind(StrEnum):
    """A semantic customer ask chosen from state before generation."""

    SALES_DISCOVERY = "sales_discovery"
    CUSTOMER_NAME = "customer_name"
    COMPANY_ACTIVITY = "company_activity"
    QUOTE_DETAILS = "quote_details"


def permitted_asks_for_turn(
    *,
    is_first_turn: bool,
    customer_name: str | None,
    customer_name_asked: bool,
    owes_company_question: bool,
    quote_consent_granted: bool,
) -> frozenset[AskKind]:
    """Derive the semantic asks allowed on this turn from explicit state."""

    permitted = {AskKind.SALES_DISCOVERY}
    if (
        is_first_turn
        and not str(customer_name or "").strip()
        and not customer_name_asked
    ):
        permitted.add(AskKind.CUSTOMER_NAME)
    if owes_company_question:
        permitted.add(AskKind.COMPANY_ACTIVITY)
    if quote_consent_granted:
        permitted.add(AskKind.QUOTE_DETAILS)
    return frozenset(permitted)


def format_permitted_asks_prompt(permitted: frozenset[AskKind]) -> str:
    """Render the pre-generation decision without re-deriving it."""

    lines = ["[PERMITTED ASKS THIS TURN]"]
    for ask in AskKind:
        status = "allowed" if ask in permitted else "forbidden"
        lines.append(f"- {ask.value}: {status}")
    lines.append(
        "Ask only types marked allowed. Phrase an allowed ask naturally; "
        "do not add a forbidden ask."
    )
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ReplyPolicyState:
    """Explicit state consumed by the customer-facing text policy."""

    language: str
    is_first_turn: bool = False
    customer_name: str | None = None
    current_message_customer_name: str | None = None
    customer_name_asked: bool = False
    ask_before_filling: bool = False
    permitted_asks: frozenset[AskKind] | None = None
    anchor_line: str | None = None
    company: str | None = None
    customer_type: str | None = None
    delivery_address: str | None = None
    owes_company_question: bool = False
    quote_consent_granted: bool = False
    inventory_confirmed: bool = False
    grounded_amounts: tuple[object, ...] | None = None
    required_tool_disclosure: str | None = None


@dataclass(frozen=True, slots=True)
class RenderedReply:
    """Customer text after the single response-policy chain."""

    text: str
    provenance: ReplyProvenance
    grounding: GroundingOutputResult
    policy_state: ReplyPolicyState
    flags: tuple[ReplyGuardFlag, ...] = ()
    emitted_asks: frozenset[AskKind] = frozenset()


class GuardMode(StrEnum):
    """What a deterministic guard is allowed to do to the customer's text.

    `REDUCING` is the third answer, added on 2026-08-11 after the second one
    was found to cost the customer something. Declaring the selling turn
    `REMOVING` was literally correct -- it removes and writes nothing back --
    but it stopped a fix that was earned by measurement: the model asks five
    questions in a numbered list, the customer answers none of them and leaves,
    and 36% leave anyway. Deferring that to a judge is slower, costs a call, and
    under D3 the judge may hand the form back.

    So the line moved to where the customer actually stands. A surplus question
    is the reply's own ask and costs them nothing; everything else is the answer
    they came for. A reducing guard may drop the first and may not touch the
    second, and it proves that at runtime rather than declaring it. When the
    proof fails it behaves exactly like `REMOVING`: no edit, one flag, and the
    judge reads it.
    """

    REPLACING = "replacing"
    REDUCING = "reducing"
    REMOVING = "removing"


ReplacementCoverage = Callable[[str, str], bool]


@dataclass(frozen=True, slots=True)
class GuardDeclaration:
    """The customer-text effect a guard is allowed to have."""

    name: str
    mode: GuardMode
    reason: str
    replacement_covers: ReplacementCoverage | None = None
    reduction_preserves: ReplacementCoverage | None = None


@dataclass(frozen=True, slots=True)
class ReplyGuardFlag:
    """A deterministic question for the repair judge, never a verdict."""

    guard_name: str
    reason: str
    details: tuple[str, ...] = ()
    candidate: str | None = None
    # The exact sentences the guard matched. The candidate is a finished answer
    # and anchors whoever reads it; these are the question itself.
    flagged_sentences: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GuardApplication:
    """Guard output before any temporary replay-compatibility bridge."""

    text: str
    candidate: str
    flags: tuple[ReplyGuardFlag, ...] = ()


def apply_first_turn_opening_guard(
    text: str,
    *,
    language: str,
    is_first_turn: bool,
    customer_name: str | None,
    anchor_line: str | None,
    ask_customer_name: bool = True,
) -> str:
    """Apply the existing opening guard from explicit turn state."""

    return apply_opening_guard(
        text,
        language=language,
        is_first_turn=is_first_turn,
        customer_name=customer_name,
        anchor_line=anchor_line,
        ask_customer_name=ask_customer_name,
    )


def _customer_name_for_turn(state: ReplyPolicyState) -> str | None:
    """Name already persisted or observed in the current inbound message."""

    return state.customer_name or state.current_message_customer_name


def _permitted_asks_for_policy_state(state: ReplyPolicyState) -> frozenset[AskKind]:
    if state.permitted_asks is not None:
        return state.permitted_asks
    return permitted_asks_for_turn(
        is_first_turn=state.is_first_turn,
        customer_name=_customer_name_for_turn(state),
        customer_name_asked=state.customer_name_asked,
        owes_company_question=state.owes_company_question,
        quote_consent_granted=state.quote_consent_granted,
    )


def repair_closed_questions(
    text: str,
    *,
    language: str,
    customer_name: str | None,
    company: str | None,
    customer_type: str | None,
    delivery_address: str | None,
) -> str:
    """Repair questions for values already present in explicit state."""

    result = apply_closed_question_guard(
        text,
        language=language,
        customer_name=customer_name,
        company=company,
        customer_type=customer_type,
        delivery_address=delivery_address,
    )
    return result.text if result.repaired else text


def _last_assistant_message(recent_history: Sequence[str] | None) -> str:
    for entry in reversed(recent_history or ()):
        if entry.startswith("assistant: "):
            return entry.removeprefix("assistant: ").strip()
    return ""


def last_assistant_asked_quote_customer_details(
    recent_history: Sequence[str] | None,
    *,
    quote_context_active: bool = False,
) -> bool:
    """Whether the latest assistant turn requests quotation customer details."""

    last_assistant = " ".join(
        _last_assistant_message(recent_history).casefold().split()
    )
    if not last_assistant:
        return False
    text_has_quote_context = bool(
        re.search(
            r"\b(?:quote|quotation|commercial\s+(?:offer|proposal))\b",
            last_assistant,
        )
        or re.search(
            r"(?:عرض\s+السعر|عرض\s+أسعار|عرض\s+تجاري)",
            last_assistant,
        )
    )
    if not quote_context_active and not text_has_quote_context:
        return False

    english_field = (
        r"(?:company(?:\s+name)?|(?:specific\s+)?delivery\s+address|address|"
        r"(?:customer|full)\s+name|(?:customer\s+)?email(?:\s+address)?|"
        r"(?:phone|mobile)(?:\s+number)?)"
    )
    english_field_value = (
        rf"(?:(?:your|the)\s+)?{english_field}"
        r"(?=\s*(?:[(),;:/?!.]|\d{1,2}[.)]|$|\band\b|\bor\b|\bfor\b|"
        r"\bto\b|\bbefore\b|\bso\b))"
    )
    english_field_prefix = r"\s*(?:[:,-]\s*)?(?:\d{1,2}[.)]\s*)?"
    english_requests = (
        rf"\b(?:please\s+)?(?:share|provide|send){english_field_prefix}"
        rf"{english_field_value}",
        rf"\b(?:can|could|may)\s+i\s+(?:get|have)\s+{english_field_value}",
        rf"\b(?:can|could|may)\s+you\s+(?:share|provide|send)"
        rf"{english_field_prefix}{english_field_value}",
        rf"\bwhat(?:'s|\s+is)\s+(?:your|the)\s+{english_field_value}",
        rf"\bplease\s+let\s+me\s+know\s+{english_field_value}",
        rf"\b(?:please\s+)?confirm\s+{english_field_value}",
        rf"\b(?:i|we)(?:'ll)?\s+(?:just\s+)?need{english_field_prefix}"
        rf"{english_field_value}",
        r"\b(?:please\s+)?confirm\s+you\s+are\s+buying\s+as\s+an\s+individual\b",
    )
    if any(re.search(pattern, last_assistant) for pattern in english_requests):
        return True

    arabic_field = (
        r"(?:اسم\s+العميل|اسم\s+الشركة|عنوان\s+التوصيل(?:\s+المحدد)?|"
        r"البريد\s+الإلكتروني|رقم\s+الهاتف)"
    )
    arabic_field_value = (
        rf"{arabic_field}"
        r"(?=\s*(?:[،؛,:.?؟!]|$|و|أو|لإعداد|قبل))"
    )
    return bool(
        re.search(
            rf"(?:يرجى\s+(?:مشاركة|تزويد)|"
            rf"هل\s+يمكنك\s+(?:مشاركة|تزويد|إرسال)|"
            rf"(?:من\s+فضلك\s+)?(?:شارك|زودني|أرسل)|(?:أحتاج|نحتاج))"
            rf"\s*[:،-]?\s*{arabic_field_value}",
            last_assistant,
        )
    )


def guard_premature_quote_detail_collection(
    text: str,
    *,
    language: str,
    quote_consent_granted: bool,
) -> str:
    """Replace pre-consent detail collection with the quotation opt-in."""

    if quote_consent_granted:
        return text
    if not last_assistant_asked_quote_customer_details(
        [f"assistant: {text}"],
        quote_context_active=True,
    ):
        return text

    prefix = _premature_quote_request_prefix(text)
    offer = (
        "هل ترغب أن أجهز عرض سعر رسمي؟"
        if is_arabic_customer_language(language)
        else "Would you like me to prepare a formal quotation?"
    )
    return f"{prefix}\n\n{offer}" if prefix else offer


def _premature_quote_request_prefix(text: str) -> str:
    """Text before the quote-detail request that a replacement must retain."""

    quote_match = re.search(
        r"\b(?:quote|quotation|commercial\s+(?:offer|proposal))\b|"
        r"(?:عرض\s+السعر|عرض\s+أسعار|عرض\s+تجاري)",
        text,
        flags=re.IGNORECASE,
    )
    detail_match = re.search(
        r"\b(?:company(?:\s+name)?|(?:specific\s+)?delivery\s+address|"
        r"(?:customer|full)\s+name|(?:customer\s+)?email(?:\s+address)?|"
        r"(?:phone|mobile)(?:\s+number)?)\b|"
        r"(?:اسم\s+العميل|اسم\s+الشركة|عنوان\s+التوصيل(?:\s+المحدد)?|"
        r"البريد\s+الإلكتروني|رقم\s+الهاتف)",
        text,
        flags=re.IGNORECASE,
    )
    anchors = [
        match.start() for match in (quote_match, detail_match) if match is not None
    ]
    request_start = min(anchors) if anchors else 0
    sentence_starts = [0]
    for separator in ("\n", ". ", "? ", "! "):
        boundary = text.rfind(separator, 0, request_start)
        if boundary >= 0:
            sentence_starts.append(boundary + len(separator))
    return text[: max(sentence_starts)].rstrip()


def _normalized_words(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\w+", str(text or "").casefold(), flags=re.UNICODE))


def _words_appear_in_order(required: Sequence[str], available: Sequence[str]) -> bool:
    cursor = iter(available)
    return all(any(word == candidate for candidate in cursor) for word in required)


def _closed_question_replacement_covers(_before: str, after: str) -> bool:
    normalized = " ".join(after.casefold().split())
    english = "i already have" in normalized and (
        "continue with your request" in normalized or "please share" in normalized
    )
    arabic = (
        "لدي" in normalized
        and "بالفعل" in normalized
        and ("سأتابع طلبك" in normalized or "يرجى مشاركة" in normalized)
    )
    return english or arabic


def _premature_quote_replacement_covers(before: str, after: str) -> bool:
    has_opt_in = (
        "Would you like me to prepare a formal quotation?" in after
        or "هل ترغب أن أجهز عرض سعر رسمي؟" in after
    )
    prefix_words = _normalized_words(_premature_quote_request_prefix(before))
    return has_opt_in and _words_appear_in_order(prefix_words, _normalized_words(after))


def _additive_replacement_covers(before: str, after: str) -> bool:
    return _words_appear_in_order(_normalized_words(before), _normalized_words(after))


RESPONSE_GUARD_DECLARATIONS: dict[str, GuardDeclaration] = {
    "closed_question": GuardDeclaration(
        name="closed_question",
        mode=GuardMode.REPLACING,
        reason="Replaces a standalone known-slot question with acknowledgement and the next action.",
        replacement_covers=_closed_question_replacement_covers,
    ),
    "premature_quote_details": GuardDeclaration(
        name="premature_quote_details",
        mode=GuardMode.REPLACING,
        reason="Keeps the answer and replaces pre-consent data collection with quotation opt-in.",
        replacement_covers=_premature_quote_replacement_covers,
    ),
    "first_turn_opening": GuardDeclaration(
        name="first_turn_opening",
        mode=GuardMode.REPLACING,
        reason="Deduplicates greeting and identity only after the canonical identity and capability replace them.",
        replacement_covers=opening_replacement_covers,
    ),
    "question_form": GuardDeclaration(
        name="question_form",
        mode=GuardMode.REDUCING,
        reason="Drops the reply's surplus questions and form items; every other sentence survives in place.",
        reduction_preserves=only_asks_were_dropped,
    ),
    "name_chase": GuardDeclaration(
        name="name_chase",
        mode=GuardMode.REDUCING,
        reason="Drops a repeat request for a name the customer has already declined, and nothing else.",
        reduction_preserves=only_asks_were_dropped,
    ),
    "company_question": GuardDeclaration(
        name="company_question",
        mode=GuardMode.REPLACING,
        reason="Only folds in the rule 13 activity question and preserves the original reply.",
        replacement_covers=_additive_replacement_covers,
    ),
    "deferred_commitment": GuardDeclaration(
        name="deferred_commitment",
        mode=GuardMode.REPLACING,
        reason="Only inserts a named follow-up commitment and preserves the original reply.",
        replacement_covers=_additive_replacement_covers,
    ),
    "grounding_output": GuardDeclaration(
        name="grounding_output",
        mode=GuardMode.REMOVING,
        reason="May drop unsupported sentences without replacing their content.",
    ),
}


def _has_meaningful_reply(text: str) -> bool:
    return any(character.isalnum() for character in text)


def apply_guard_with_reply_bound(
    text: str,
    *,
    guard_name: str,
    guard: Callable[[str], str],
) -> str:
    candidate = guard(text)
    if _has_meaningful_reply(text) and not _has_meaningful_reply(candidate):
        logger.error(
            "Response guard removed the reply: guard=%s before_chars=%d after_chars=%d",
            guard_name,
            len(text),
            len(candidate),
        )
        return text
    return candidate


def apply_declared_guard(
    text: str,
    *,
    declaration: GuardDeclaration,
    guard: Callable[[str], str],
    flagged: bool | None = None,
    flag_details: tuple[str, ...] = (),
) -> GuardApplication:
    """Apply one declaration without letting a removing guard edit the reply."""

    candidate = guard(text)
    detected = candidate != text if flagged is None else flagged
    if declaration.mode is GuardMode.REDUCING:
        if candidate == text:
            return GuardApplication(text=text, candidate=candidate)
        preserves = declaration.reduction_preserves
        if preserves is not None and preserves(text, candidate):
            return GuardApplication(text=candidate, candidate=candidate)
        logger.error(
            "Response guard reduction lost content: guard=%s before_chars=%d "
            "after_chars=%d",
            declaration.name,
            len(text),
            len(candidate),
        )
        return GuardApplication(
            text=text,
            candidate=candidate,
            flags=(
                ReplyGuardFlag(
                    guard_name=declaration.name,
                    reason="reduction_lost_content",
                    details=flag_details,
                    candidate=candidate,
                ),
            ),
        )

    if declaration.mode is GuardMode.REMOVING:
        if not detected:
            return GuardApplication(text=text, candidate=candidate)
        return GuardApplication(
            text=text,
            candidate=candidate,
            flags=(
                ReplyGuardFlag(
                    guard_name=declaration.name,
                    reason="removing_guard_triggered",
                    details=flag_details,
                    candidate=candidate,
                ),
            ),
        )

    if candidate == text:
        return GuardApplication(text=text, candidate=candidate)
    covers = declaration.replacement_covers
    if covers is not None and covers(text, candidate):
        return GuardApplication(text=candidate, candidate=candidate)

    logger.error(
        "Response guard replacement lacked coverage: guard=%s before_chars=%d "
        "after_chars=%d",
        declaration.name,
        len(text),
        len(candidate),
    )
    return GuardApplication(
        text=text,
        candidate=candidate,
        flags=(
            ReplyGuardFlag(
                guard_name=declaration.name,
                reason="replacement_coverage_failed",
                details=flag_details,
                candidate=candidate,
            ),
        ),
    )


def _render_declared_guard(
    text: str,
    *,
    guard_name: str,
    guard: Callable[[str], str],
    flagged: bool | None = None,
    flag_details: tuple[str, ...] = (),
) -> tuple[str, tuple[ReplyGuardFlag, ...]]:
    declaration = RESPONSE_GUARD_DECLARATIONS[guard_name]
    application = apply_declared_guard(
        text,
        declaration=declaration,
        guard=guard,
        flagged=flagged,
        flag_details=flag_details,
    )
    return application.text, application.flags


def append_required_tool_disclosure(text: str, disclosure: str | None) -> str:
    """Append a required disclosure once, using normalized comparison."""

    normalized_disclosure = " ".join(str(disclosure or "").casefold().split())
    normalized_text = " ".join(text.casefold().split())
    if not normalized_disclosure or normalized_disclosure in normalized_text:
        return text
    return f"{text.rstrip()}\n\n{disclosure}"


def render_reply(
    text: str,
    *,
    state: ReplyPolicyState,
    provenance: ReplyProvenance,
) -> RenderedReply:
    """Apply the one customer-facing text policy, independent of provenance."""

    raised_flags: list[ReplyGuardFlag] = []
    permitted_asks = _permitted_asks_for_policy_state(state)
    rendered, flags = _render_declared_guard(
        text,
        guard_name="closed_question",
        guard=partial(
            repair_closed_questions,
            language=state.language,
            customer_name=_customer_name_for_turn(state),
            company=state.company,
            customer_type=state.customer_type,
            delivery_address=state.delivery_address,
        ),
    )
    raised_flags.extend(flags)
    rendered, flags = _render_declared_guard(
        rendered,
        guard_name="premature_quote_details",
        guard=partial(
            guard_premature_quote_detail_collection,
            language=state.language,
            quote_consent_granted=AskKind.QUOTE_DETAILS in permitted_asks,
        ),
    )
    raised_flags.extend(flags)
    rendered, flags = _render_declared_guard(
        rendered,
        guard_name="first_turn_opening",
        guard=partial(
            apply_first_turn_opening_guard,
            language=state.language,
            is_first_turn=state.is_first_turn,
            customer_name=_customer_name_for_turn(state),
            anchor_line=state.anchor_line,
            ask_customer_name=AskKind.CUSTOMER_NAME in permitted_asks,
        ),
    )
    raised_flags.extend(flags)
    if rendered.strip():
        # Safe on first turns: this REDUCING guard applies only when its
        # executable proof shows that every answer word survived and only
        # surplus asks were dropped.
        rendered, flags = _render_declared_guard(
            rendered,
            guard_name="question_form",
            guard=collapse_question_form,
            flag_details=("deterministic_fold_would_lose_content",),
        )
        raised_flags.extend(flags)

        if not state.is_first_turn:
            # Deliberately still gated on first turns: the measured bad replies
            # were unchanged by this guard even with a known name, so there is
            # no evidence for widening its blast radius.
            rendered, flags = _render_declared_guard(
                rendered,
                guard_name="name_chase",
                guard=partial(
                    refuse_to_chase_the_name,
                    # The slot itself, not the permission derived from it: on a
                    # later turn the name ask is never permitted anyway, so
                    # reading the permission would have made this guard strip
                    # every name question, including the first one we owe.
                    customer_name_asked=state.customer_name_asked,
                    customer_name=_customer_name_for_turn(state),
                    ask_before_filling=state.ask_before_filling,
                ),
                flag_details=("deterministic_fold_would_lose_content",),
            )
            raised_flags.extend(flags)

        if not state.is_first_turn and AskKind.COMPANY_ACTIVITY in permitted_asks:
            # This additive discovery ask was designed and measured for later
            # selling turns; the first-turn set supplies no reason to move it.
            rendered, flags = _render_declared_guard(
                rendered,
                guard_name="company_question",
                guard=partial(carry_the_company_question, language=state.language),
            )
            raised_flags.extend(flags)
    rendered, flags = _render_declared_guard(
        rendered,
        guard_name="deferred_commitment",
        guard=partial(commit_to_what_you_deferred, language=state.language),
    )
    raised_flags.extend(flags)
    rendered_before_grounding = rendered
    violations = classify_grounding_output(
        rendered,
        inventory_confirmed=state.inventory_confirmed,
        grounded_amounts=state.grounded_amounts,
    )
    grounding = repair_grounding_output(
        rendered,
        language=state.language,
        violations=violations,
        inventory_confirmed=state.inventory_confirmed,
        grounded_amounts=state.grounded_amounts,
    )
    rendered, flags = _render_declared_guard(
        rendered,
        guard_name="grounding_output",
        guard=lambda _current: grounding.text,
        flagged=bool(violations),
        flag_details=tuple(violation.value for violation in violations),
    )
    if violations:
        matched = flagged_grounding_sentences(
            rendered_before_grounding,
            inventory_confirmed=state.inventory_confirmed,
            grounded_amounts=state.grounded_amounts,
        )
        flags = tuple(replace(flag, flagged_sentences=matched) for flag in flags)
    raised_flags.extend(flags)
    rendered = apply_guard_with_reply_bound(
        rendered,
        guard_name="tool_disclosures",
        guard=partial(
            append_required_tool_disclosure,
            disclosure=state.required_tool_disclosure,
        ),
    )
    # Permission is decided from state before generation. This observation is
    # narrower: it records whether the selected customer text still carries
    # the permitted name ask after every reducing guard has run.
    emitted_asks = frozenset(
        {AskKind.CUSTOMER_NAME}
        if AskKind.CUSTOMER_NAME in permitted_asks
        and response_asks_customer_name(rendered)
        else ()
    )
    return RenderedReply(
        text=rendered,
        provenance=provenance,
        grounding=grounding,
        policy_state=state,
        flags=tuple(raised_flags),
        emitted_asks=emitted_asks,
    )
