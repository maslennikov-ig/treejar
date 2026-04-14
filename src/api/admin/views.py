from sqladmin import Admin, ModelView

from src.models.conversation import Conversation
from src.models.conversation_summary import ConversationSummary
from src.models.escalation import Escalation
from src.models.feedback import Feedback
from src.models.knowledge_base import KnowledgeBase
from src.models.manager_review import ManagerReview
from src.models.message import Message
from src.models.metrics_snapshot import MetricsSnapshot
from src.models.product import Product
from src.models.quality_review import QualityReview
from src.models.referral import Referral
from src.models.system_config import SystemConfig
from src.models.system_prompt import SystemPrompt


class ReadOnlyModelView(ModelView):
    can_create = False
    can_edit = False
    can_delete = False


class ConversationAdmin(ReadOnlyModelView, model=Conversation):
    column_list = [Conversation.id, Conversation.created_at, Conversation.updated_at]
    name = "Диалог"
    name_plural = "Диалоги"
    icon = "fa-solid fa-comments"


class MessageAdmin(ReadOnlyModelView, model=Message):
    column_list = [
        Message.id,
        Message.conversation_id,
        Message.role,
        Message.created_at,
    ]
    name = "Сообщение"
    name_plural = "Сообщения"
    icon = "fa-solid fa-message"


class ProductAdmin(ReadOnlyModelView, model=Product):
    column_list = [
        Product.sku,
        Product.name_en,
        Product.is_active,
        Product.price,
        Product.stock,
    ]
    column_details_exclude_list = [Product.embedding]
    form_excluded_columns = [Product.embedding]
    name = "Товар"
    name_plural = "Товары"
    icon = "fa-solid fa-box"


class KnowledgeBaseAdmin(ModelView, model=KnowledgeBase):
    can_create = True
    can_edit = True
    can_delete = True
    column_list = [KnowledgeBase.id, KnowledgeBase.created_at]
    column_details_exclude_list = [KnowledgeBase.embedding]
    form_excluded_columns = [KnowledgeBase.embedding]
    name = "База знаний"
    name_plural = "База знаний"
    icon = "fa-solid fa-book"


class QualityReviewAdmin(ReadOnlyModelView, model=QualityReview):
    column_list = [
        QualityReview.id,
        QualityReview.conversation_id,
        QualityReview.total_score,
        QualityReview.created_at,
    ]
    name = "Оценка качества"
    name_plural = "Оценки качества"
    icon = "fa-solid fa-star"


class EscalationAdmin(ModelView, model=Escalation):
    can_create = False
    can_edit = True
    can_delete = False
    column_list = [
        Escalation.id,
        Escalation.conversation_id,
        Escalation.status,
        Escalation.created_at,
    ]
    name = "Эскалация"
    name_plural = "Эскалации"
    icon = "fa-solid fa-triangle-exclamation"


class SystemConfigAdmin(ModelView, model=SystemConfig):
    can_create = True
    can_edit = True
    can_delete = False
    column_list = [SystemConfig.key, SystemConfig.value, SystemConfig.updated_at]
    name = "Системная настройка"
    name_plural = "Системные настройки"
    icon = "fa-solid fa-gear"


class MetricsSnapshotAdmin(ReadOnlyModelView, model=MetricsSnapshot):
    column_list = [
        MetricsSnapshot.period,
        MetricsSnapshot.total_conversations,
        MetricsSnapshot.llm_cost_usd,
        MetricsSnapshot.updated_at,
    ]
    name = "Снимок метрик"
    name_plural = "Снимки метрик"
    icon = "fa-solid fa-chart-line"


class SystemPromptAdmin(ModelView, model=SystemPrompt):
    can_create = False
    can_edit = True
    can_delete = False
    column_list = [
        SystemPrompt.name,
        SystemPrompt.version,
        SystemPrompt.is_active,
        SystemPrompt.updated_at,
    ]
    name = "Системный промпт"
    name_plural = "Системные промпты"
    icon = "fa-solid fa-scroll"


class ReferralAdmin(ReadOnlyModelView, model=Referral):
    column_list = [
        Referral.code,
        Referral.referrer_phone,
        Referral.referee_phone,
        Referral.status,
        Referral.created_at,
    ]
    name = "Реферал"
    name_plural = "Рефералы"
    icon = "fa-solid fa-share-nodes"


class FeedbackAdmin(ReadOnlyModelView, model=Feedback):
    column_list = [
        Feedback.id,
        Feedback.conversation_id,
        Feedback.rating_overall,
        Feedback.rating_delivery,
        Feedback.recommend,
        Feedback.created_at,
    ]
    name = "Обратная связь"
    name_plural = "Обратная связь"
    icon = "fa-solid fa-star-half-stroke"


class ConversationSummaryAdmin(ReadOnlyModelView, model=ConversationSummary):
    column_list = [
        ConversationSummary.conversation_id,
        ConversationSummary.model,
        ConversationSummary.version,
        ConversationSummary.updated_at,
    ]
    name = "Сводка диалога"
    name_plural = "Сводки диалогов"
    icon = "fa-solid fa-file-lines"


class ManagerReviewAdmin(ReadOnlyModelView, model=ManagerReview):
    column_list = [
        ManagerReview.manager_name,
        ManagerReview.conversation_id,
        ManagerReview.total_score,
        ManagerReview.rating,
        ManagerReview.created_at,
    ]
    name = "Оценка менеджера"
    name_plural = "Оценки менеджеров"
    icon = "fa-solid fa-user-check"


def setup_admin_views(admin_app: Admin) -> None:
    admin_app.add_view(ConversationAdmin)
    admin_app.add_view(ConversationSummaryAdmin)
    admin_app.add_view(MessageAdmin)
    admin_app.add_view(ProductAdmin)
    admin_app.add_view(KnowledgeBaseAdmin)
    admin_app.add_view(QualityReviewAdmin)
    admin_app.add_view(EscalationAdmin)
    admin_app.add_view(ManagerReviewAdmin)
    admin_app.add_view(SystemConfigAdmin)
    admin_app.add_view(SystemPromptAdmin)
    admin_app.add_view(MetricsSnapshotAdmin)
    admin_app.add_view(ReferralAdmin)
    admin_app.add_view(FeedbackAdmin)
