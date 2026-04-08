from __future__ import annotations

from unittest.mock import patch


def test_translate_quality_rating_for_owner_facing_views() -> None:
    from src.services.report_localization import translate_quality_rating

    assert translate_quality_rating("poor") == "плохо"
    assert translate_quality_rating("satisfactory") == "удовлетворительно"
    assert translate_quality_rating("good") == "хорошо"
    assert translate_quality_rating("excellent") == "отлично"


def test_translate_report_trigger_for_owner_facing_views() -> None:
    from src.services.report_localization import translate_report_trigger

    assert translate_report_trigger("idle 3h") == "нет ответа 3 часа"
    assert translate_report_trigger("closed") == "диалог закрыт"
    assert translate_report_trigger("customer_angry") == "клиент недоволен"
    assert translate_report_trigger("complex_order") == "сложный заказ"


def test_translate_sales_stage_for_owner_facing_views() -> None:
    from src.services.report_localization import translate_sales_stage

    assert translate_sales_stage("greeting") == "приветствие"
    assert translate_sales_stage("qualifying") == "квалификация"
    assert translate_sales_stage("closing") == "закрытие"


def test_unknown_trigger_uses_russian_fallback_and_logs_miss() -> None:
    from src.services.report_localization import translate_report_trigger

    with patch("src.services.report_localization.logfire.info") as mock_logfire:
        result = translate_report_trigger(
            "mystery english trigger",
            surface="weekly_report",
            module="reports",
        )

    assert result == "иная причина"
    mock_logfire.assert_called_once()
    assert mock_logfire.call_args.args[0] == "owner_localization.miss"
    assert mock_logfire.call_args.kwargs["surface"] == "weekly_report"
    assert mock_logfire.call_args.kwargs["module"] == "reports"
    assert mock_logfire.call_args.kwargs["value"] == "mystery english trigger"


def test_unknown_stage_uses_russian_fallback_and_logs_miss() -> None:
    from src.services.report_localization import translate_sales_stage

    with patch("src.services.report_localization.logfire.info") as mock_logfire:
        result = translate_sales_stage(
            "mystery_stage",
            surface="quality_review",
            module="owner_review_formatters",
        )

    assert result == "неизвестный этап"
    mock_logfire.assert_called_once()


def test_unknown_rating_uses_russian_fallback_and_logs_miss() -> None:
    from src.services.report_localization import translate_quality_rating

    with patch("src.services.report_localization.logfire.info") as mock_logfire:
        result = translate_quality_rating(
            "mystery_rating",
            surface="quality_alert",
            module="notifications",
        )

    assert result == "неизвестно"
    mock_logfire.assert_called_once()


def test_translate_quality_block_name_for_owner_facing_views() -> None:
    from src.services.report_localization import translate_quality_block_name

    assert translate_quality_block_name("Opening & Trust") == "Открытие и доверие"
    assert (
        translate_quality_block_name("Relationship & Discovery")
        == "Контакт и выявление потребностей"
    )


def test_translate_red_flag_by_code_for_owner_facing_views() -> None:
    from src.services.report_localization import (
        translate_red_flag_explanation,
        translate_red_flag_title,
    )

    assert translate_red_flag_title("missing_identity") == "Нет идентификации"
    assert (
        translate_red_flag_explanation("missing_identity")
        == "Ассистент не представился как Siyyad из Treejar в первом ответе."
    )
