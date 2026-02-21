from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqladmin import Admin

from src.core.config import settings
from src.core.database import engine
from src.core.redis import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup: verify connections
    yield
    # Shutdown: close connections
    await redis_client.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Register routes
    from src.api.v1.router import api_v1_router

    app.include_router(api_v1_router, prefix="/api/v1")

    # Mount SQLAdmin
    Admin(app, engine, title="Treejar Admin")

    return app


app = create_app()
