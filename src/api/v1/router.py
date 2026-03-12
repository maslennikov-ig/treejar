from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import require_api_key
from src.api.v1 import (
    admin,
    conversations,
    crm,
    health,
    inventory,
    notifications,
    products,
    quality,
    referrals,
    reports,
    webhook,
)

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])
api_v1_router.include_router(
    conversations.router, prefix="/conversations", tags=["Conversations"]
)
api_v1_router.include_router(products.router, prefix="/products", tags=["Products"])
api_v1_router.include_router(
    crm.router,
    prefix="/crm",
    tags=["CRM"],
    dependencies=[Depends(require_api_key)],
)
api_v1_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_v1_router.include_router(
    quality.router,
    prefix="/quality",
    tags=["Quality"],
    dependencies=[Depends(require_api_key)],
)
api_v1_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"],
    dependencies=[Depends(require_api_key)],
)
api_v1_router.include_router(
    reports.router,
    prefix="/reports",
    tags=["Reports"],
    dependencies=[Depends(require_api_key)],
)
api_v1_router.include_router(
    referrals.router,
    prefix="/referrals",
    tags=["Referrals"],
    dependencies=[Depends(require_api_key)],
)
api_v1_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
