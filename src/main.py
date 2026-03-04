from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from sqladmin import Admin

from src.core.config import settings
from src.core.database import engine
from src.core.redis import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    app.state.redis = redis_client
    yield
    # Shutdown
    await app.state.arq_pool.aclose()
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
    from src.api.admin.auth import authentication_backend
    admin = Admin(app, engine, title="Treejar Admin", authentication_backend=authentication_backend)

    from src.api.admin.views import setup_admin_views
    setup_admin_views(admin)

    # --- Landing Page SPA Integration ---
    import os
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    # Ensure dist directory exists for local development to avoid startup crash
    os.makedirs("frontend/landing/dist", exist_ok=True)
    index_path = "frontend/landing/dist/index.html"
    if not os.path.exists(index_path):
        with open(index_path, "w") as f:
            f.write("<html><body>Mock Index</body></html>")

    app.mount("/assets", StaticFiles(directory="frontend/landing/dist", html=True), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        dist_dir = "frontend/landing/dist"
        file_path = os.path.join(dist_dir, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))

    return app


app = create_app()
