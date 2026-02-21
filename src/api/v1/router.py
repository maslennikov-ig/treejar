from __future__ import annotations

from fastapi import APIRouter

from src.api.v1 import (
    admin,
    conversations,
    crm,
    health,
    inventory,
    products,
    quality,
    webhook,
)

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])
api_v1_router.include_router(
    conversations.router, prefix="/conversations", tags=["Conversations"]
)
api_v1_router.include_router(products.router, prefix="/products", tags=["Products"])
api_v1_router.include_router(crm.router, prefix="/crm", tags=["CRM"])
api_v1_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_v1_router.include_router(quality.router, prefix="/quality", tags=["Quality"])
api_v1_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
