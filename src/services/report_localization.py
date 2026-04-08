"""Presentation-only localization helpers for owner-facing reports and alerts."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping

import logfire

from src.schemas.common import SalesStage

logger = logging.getLogger(__name__)

_QUALITY_RATING_LABELS: Mapping[str, str] = {
    "poor": "плохо",
    "satisfactory": "удовлетворительно",
    "good": "хорошо",
    "excellent": "отлично",
}

_SALES_STAGE_LABELS: Mapping[str, str] = {
    SalesStage.GREETING.value: "приветствие",
    SalesStage.QUALIFYING.value: "квалификация",
    SalesStage.NEEDS_ANALYSIS.value: "анализ потребностей",
    SalesStage.SOLUTION.value: "подбор решения",
    SalesStage.COMPANY_DETAILS.value: "данные компании",
    SalesStage.QUOTING.value: "подготовка предложения",
    SalesStage.CLOSING.value: "закрытие",
    SalesStage.FEEDBACK.value: "обратная связь",
}

_REPORT_TRIGGER_LABELS: Mapping[str, str] = {
    "idle 3h": "нет ответа 3 часа",
    "closed": "диалог закрыт",
    "customer_angry": "клиент недоволен",
    "customer angry": "клиент недоволен",
    "complex_order": "сложный заказ",
    "complex order": "сложный заказ",
    "human_requested": "запрошен менеджер",
    "human requested": "запрошен менеджер",
    "customer asked for manager": "запрошен менеджер",
    "customer asked for a manager": "запрошен менеджер",
    "customer requested human": "запрошен менеджер",
    "customer wants human": "запрошен менеджер",
    "manager requested": "запрошен менеджер",
    "manager_requested": "запрошен менеджер",
    "order_confirmation": "подтверждение заказа",
    "order confirmation": "подтверждение заказа",
    "customer not convinced": "клиент не готов к покупке",
    "order > 10k aed": "заказ свыше 10 000 AED",
    "b2b wholesale order": "оптовый B2B-заказ",
    "low_score": "оценка ниже порога",
    "threshold_breach": "оценка ниже порога",
}

_QUALITY_BLOCK_LABELS: Mapping[str, str] = {
    "opening & trust": "Открытие и доверие",
    "relationship & discovery": "Контакт и выявление потребностей",
    "consultative solution": "Консультативное решение",
    "conversion & next step": "Конверсия и следующий шаг",
}

_QUALITY_RULE_LABELS: Mapping[int, str] = {
    1: "Приветствие, имя и компания в начале",
    2: "Вежливое и профессиональное начало",
    3: "Уточнение, как обращаться к клиенту",
    4: "Дружелюбный тон и активное слушание",
    5: "Искренний интерес к потребностям клиента",
    6: "Комплимент или признательность",
    7: "Ценность предложения Treejar",
    8: "Уточняющие вопросы по требованиям",
    9: "Фокус на задаче клиента",
    10: "Комплексное решение после диагностики",
    11: "Скидка, пакетное предложение или бонус",
    12: "Сбор контактных данных",
    13: "Понимание бизнеса клиента",
    14: "Подтверждение деталей и следующего шага",
    15: "Согласование следующего контакта",
}

_MANAGER_RULE_LABELS: Mapping[int, str] = {
    1: "Быстрый подхват после бота",
    2: "Использование собранного контекста",
    3: "Профессиональный тон",
    4: "Решение причины эскалации",
    5: "Проактивность и дополнительные варианты",
    6: "Работа с возражениями",
    7: "Движение к закрытию",
    8: "Полнота информации",
    9: "Сбор данных для CRM/КП",
    10: "Фиксация итога и следующего шага",
}

_CRITERION_STATUS_LABELS: Mapping[int, str] = {
    0: "не выполнено",
    1: "частично выполнено",
    2: "выполнено",
}

_RED_FLAG_TITLE_LABELS: Mapping[str, str] = {
    "missing_identity": "Нет идентификации",
    "hard_deflection": "Жёсткая переадресация",
    "unverified_commitment": "Неподтверждённое обещание",
    "ignored_question": "Вопрос клиента проигнорирован",
    "bad_tone": "Неподходящий тон",
}

_RED_FLAG_EXPLANATION_LABELS: Mapping[str, str] = {
    "missing_identity": "Ассистент не представился как Siyyad из Treejar в первом ответе.",
    "hard_deflection": "Ассистент слишком быстро перевёл клиента на менеджера без попытки помочь.",
    "unverified_commitment": "Ассистент пообещал факты или обязательства без подтверждения в контексте.",
    "ignored_question": "Прямой вопрос клиента не получил содержательного ответа.",
    "bad_tone": "В диалоге использован неподходящий или отталкивающий тон.",
}


def owner_na() -> str:
    """Owner-facing replacement for N/A."""
    return "н/д"


def owner_unknown(*, kind: str = "generic") -> str:
    """Owner-facing replacement for unknown values."""
    if kind == "person":
        return "не указан"
    if kind == "stage":
        return "неизвестный этап"
    if kind == "trigger":
        return "иная причина"
    return "неизвестно"


def _contains_cyrillic(value: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", value))


def _log_localization_miss(*, surface: str, module: str, value: str) -> None:
    logfire.info(
        "owner_localization.miss",
        surface=surface,
        module=module,
        value=value,
    )
    logger.warning(
        "owner_localization.miss surface=%s module=%s value=%s",
        surface,
        module,
        value,
    )


def _translate_mapped_value(
    value: str | None,
    mapping: Mapping[str, str],
    *,
    fallback: str,
    surface: str,
    module: str,
) -> str:
    if value is None:
        return fallback

    raw = value.strip()
    if not raw:
        return fallback

    normalized = raw.lower()
    if normalized in {"n/a", "na"}:
        return owner_na()

    if normalized in {"unknown", "none"}:
        return fallback

    if normalized in mapping:
        return mapping[normalized]

    if _contains_cyrillic(raw):
        return raw

    _log_localization_miss(surface=surface, module=module, value=raw)
    return fallback


def translate_quality_rating(
    value: str | None,
    *,
    surface: str = "owner_output",
    module: str = "report_localization",
) -> str:
    """Translate canonical quality/manager rating to Russian for display only."""
    return _translate_mapped_value(
        value,
        _QUALITY_RATING_LABELS,
        fallback=owner_unknown(),
        surface=surface,
        module=module,
    )


def translate_sales_stage(
    value: str | None,
    *,
    surface: str = "owner_output",
    module: str = "report_localization",
) -> str:
    """Translate canonical sales stage to Russian for display only."""
    return _translate_mapped_value(
        value,
        _SALES_STAGE_LABELS,
        fallback=owner_unknown(kind="stage"),
        surface=surface,
        module=module,
    )


def translate_report_trigger(
    value: str | None,
    *,
    surface: str = "owner_output",
    module: str = "report_localization",
) -> str:
    """Translate escalation trigger/reason for owner-facing report output."""
    return _translate_mapped_value(
        value,
        _REPORT_TRIGGER_LABELS,
        fallback=owner_unknown(kind="trigger"),
        surface=surface,
        module=module,
    )


def translate_quality_block_name(
    value: str | None,
    *,
    surface: str = "quality_review",
    module: str = "report_localization",
) -> str:
    """Translate weighted quality block names for owner-facing rendering."""
    return _translate_mapped_value(
        value,
        _QUALITY_BLOCK_LABELS,
        fallback="Блок оценки",
        surface=surface,
        module=module,
    )


def translate_quality_rule_name(
    rule_number: int | None,
    value: str | None = None,
    *,
    surface: str = "quality_review",
    module: str = "report_localization",
) -> str:
    """Translate quality criterion name for owner-facing rendering."""
    if rule_number is not None and rule_number in _QUALITY_RULE_LABELS:
        return _QUALITY_RULE_LABELS[rule_number]
    return _translate_mapped_value(
        value,
        {},
        fallback="Критерий оценки",
        surface=surface,
        module=module,
    )


def translate_manager_rule_name(
    rule_number: int | None,
    value: str | None = None,
    *,
    surface: str = "manager_review",
    module: str = "report_localization",
) -> str:
    """Translate manager criterion name for owner-facing rendering."""
    if rule_number is not None and rule_number in _MANAGER_RULE_LABELS:
        return _MANAGER_RULE_LABELS[rule_number]
    return _translate_mapped_value(
        value,
        {},
        fallback="Критерий оценки менеджера",
        surface=surface,
        module=module,
    )


def translate_criterion_status(score: int | None) -> str:
    """Translate criterion score bucket for owner-facing rendering."""
    if score is None:
        return owner_na()
    return _CRITERION_STATUS_LABELS.get(score, owner_unknown())


def translate_red_flag_title(
    code: str | None,
    value: str | None = None,
    *,
    surface: str = "red_flag_warning",
    module: str = "report_localization",
) -> str:
    """Translate red-flag title deterministically for owner-facing rendering."""
    if code:
        translated = _RED_FLAG_TITLE_LABELS.get(code.strip().lower())
        if translated:
            return translated
    return _translate_mapped_value(
        value,
        {},
        fallback="Критический сигнал",
        surface=surface,
        module=module,
    )


def translate_red_flag_explanation(
    code: str | None,
    value: str | None = None,
    *,
    surface: str = "red_flag_warning",
    module: str = "report_localization",
) -> str:
    """Translate red-flag explanation deterministically for owner-facing rendering."""
    if code:
        translated = _RED_FLAG_EXPLANATION_LABELS.get(code.strip().lower())
        if translated:
            return translated
    return _translate_mapped_value(
        value,
        {},
        fallback="Требуется ручная проверка диалога.",
        surface=surface,
        module=module,
    )
