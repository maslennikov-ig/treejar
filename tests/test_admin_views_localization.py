from __future__ import annotations


def test_admin_view_names_are_localized_for_owner_ui() -> None:
    from src.api.admin.views import (
        ConversationAdmin,
        ConversationSummaryAdmin,
        EscalationAdmin,
        FeedbackAdmin,
        KnowledgeBaseAdmin,
        ManagerReviewAdmin,
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
    assert ConversationSummaryAdmin.name == "Сводка диалога"
    assert MessageAdmin.name == "Сообщение"
    assert ProductAdmin.name == "Товар"
    assert KnowledgeBaseAdmin.name == "База знаний"
    assert QualityReviewAdmin.name == "Оценка качества"
    assert QualityReviewAdmin.name_plural == "Оценки качества"
    assert EscalationAdmin.name == "Эскалация"
    assert ManagerReviewAdmin.name == "Оценка менеджера"
    assert SystemConfigAdmin.name == "Системная настройка"
    assert MetricsSnapshotAdmin.name == "Снимок метрик"
    assert SystemPromptAdmin.name == "Системный промпт"
    assert ReferralAdmin.name == "Реферал"
    assert FeedbackAdmin.name == "Обратная связь"


def test_admin_view_registry_includes_runtime_audit_models() -> None:
    from src.api.admin.views import (
        ConversationSummaryAdmin,
        ManagerReviewAdmin,
        setup_admin_views,
    )

    class FakeAdmin:
        def __init__(self) -> None:
            self.views: list[type] = []

        def add_view(self, view: type) -> None:
            self.views.append(view)

    admin = FakeAdmin()
    setup_admin_views(admin)

    assert ConversationSummaryAdmin in admin.views
    assert ManagerReviewAdmin in admin.views


def test_generated_and_audit_views_have_explicit_read_only_policy() -> None:
    from src.api.admin.views import (
        ConversationAdmin,
        ConversationSummaryAdmin,
        FeedbackAdmin,
        ManagerReviewAdmin,
        MessageAdmin,
        MetricsSnapshotAdmin,
        ProductAdmin,
        QualityReviewAdmin,
        ReferralAdmin,
    )

    for view in (
        ConversationAdmin,
        ConversationSummaryAdmin,
        MessageAdmin,
        ProductAdmin,
        QualityReviewAdmin,
        ManagerReviewAdmin,
        MetricsSnapshotAdmin,
        ReferralAdmin,
        FeedbackAdmin,
    ):
        assert view.can_create is False
        assert view.can_edit is False
        assert view.can_delete is False
