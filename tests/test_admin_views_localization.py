from __future__ import annotations


def test_admin_view_names_are_localized_for_owner_ui() -> None:
    from src.api.admin.views import (
        ConversationAdmin,
        EscalationAdmin,
        FeedbackAdmin,
        KnowledgeBaseAdmin,
        MessageAdmin,
        MetricsSnapshotAdmin,
        ProductAdmin,
        QualityReviewAdmin,
        ReferralAdmin,
        SystemConfigAdmin,
        SystemPromptAdmin,
    )

    assert ConversationAdmin.name == "Диалог"
    assert ConversationAdmin.name_plural == "Диалоги"
    assert MessageAdmin.name == "Сообщение"
    assert ProductAdmin.name == "Товар"
    assert KnowledgeBaseAdmin.name == "База знаний"
    assert QualityReviewAdmin.name == "Оценка качества"
    assert QualityReviewAdmin.name_plural == "Оценки качества"
    assert EscalationAdmin.name == "Эскалация"
    assert SystemConfigAdmin.name == "Системная настройка"
    assert MetricsSnapshotAdmin.name == "Снимок метрик"
    assert SystemPromptAdmin.name == "Системный промпт"
    assert ReferralAdmin.name == "Реферал"
    assert FeedbackAdmin.name == "Обратная связь"
