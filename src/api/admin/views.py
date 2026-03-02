from sqladmin import Admin, ModelView

from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.models.knowledge_base import KnowledgeBase
from src.models.message import Message
from src.models.product import Product
from src.models.quality_review import QualityReview
from src.models.system_config import SystemConfig


class ConversationAdmin(ModelView, model=Conversation):
    column_list = [Conversation.id, Conversation.created_at, Conversation.updated_at]
    name = "Conversation"
    name_plural = "Conversations"
    icon = "fa-solid fa-comments"


class MessageAdmin(ModelView, model=Message):
    column_list = [Message.id, Message.conversation_id, Message.role, Message.created_at]
    name = "Message"
    name_plural = "Messages"
    icon = "fa-solid fa-message"


class ProductAdmin(ModelView, model=Product):
    column_list = [Product.sku, Product.name_en, Product.is_active, Product.price, Product.stock]
    name = "Product"
    name_plural = "Products"
    icon = "fa-solid fa-box"


class KnowledgeBaseAdmin(ModelView, model=KnowledgeBase):
    column_list = [KnowledgeBase.id, KnowledgeBase.created_at]
    name = "Knowledge Base"
    name_plural = "Knowledge Base"
    icon = "fa-solid fa-book"


class QualityReviewAdmin(ModelView, model=QualityReview):
    column_list = [QualityReview.id, QualityReview.conversation_id, QualityReview.total_score, QualityReview.created_at]
    name = "Quality Review"
    name_plural = "Quality Reviews"
    icon = "fa-solid fa-star"


class EscalationAdmin(ModelView, model=Escalation):
    column_list = [Escalation.id, Escalation.conversation_id, Escalation.status, Escalation.created_at]
    name = "Escalation"
    name_plural = "Escalations"
    icon = "fa-solid fa-triangle-exclamation"


class SystemConfigAdmin(ModelView, model=SystemConfig):
    column_list = [SystemConfig.key, SystemConfig.value, SystemConfig.updated_at]
    name = "System Config"
    name_plural = "System Configs"
    icon = "fa-solid fa-gear"


def setup_admin_views(admin_app: Admin) -> None:
    admin_app.add_view(ConversationAdmin)
    admin_app.add_view(MessageAdmin)
    admin_app.add_view(ProductAdmin)
    admin_app.add_view(KnowledgeBaseAdmin)
    admin_app.add_view(QualityReviewAdmin)
    admin_app.add_view(EscalationAdmin)
    admin_app.add_view(SystemConfigAdmin)
