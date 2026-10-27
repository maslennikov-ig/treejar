from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from src.api.admin.auth import (
    build_admin_login_redirect,
    has_admin_session,
    pop_admin_login_next,
)
from src.api.admin.dashboard_redirect_admin import DashboardRedirectAdmin
from src.core.config import settings
from src.core.database import async_session_factory, engine
from src.core.redis import redis_client
from src.core.safe_logging import install_sensitive_url_filter
from src.integrations.notifications.telegram_webhook import sync_telegram_webhook
from src.services.admin_audit import log_admin_action
from src.services.telegram_admin_login import consume_telegram_admin_login_token

logger = logging.getLogger(__name__)

BRAND_STATIC_DIR = Path(__file__).resolve().parent / "static" / "brand"
BRAND_ASSET_MEDIA_TYPES: dict[str, str] = {
    "favicon.ico": "image/x-icon",
    "favicon.svg": "image/svg+xml",
    "favicon-32x32.png": "image/png",
    "apple-touch-icon.png": "image/png",
    "icon-192.png": "image/png",
    "icon-512.png": "image/png",
    "site.webmanifest": "application/manifest+json",
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    install_sensitive_url_filter()
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    app.state.redis = redis_client
    if settings.test_channel_restore_mode:
        logger.warning(
            "Telegram startup sync limited to the guarded webhook during "
            "test-channel restore"
        )
    await sync_telegram_webhook(
        sync_commands=not settings.test_channel_restore_mode,
    )
    yield
    # Shutdown
    await app.state.arq_pool.aclose()
    await redis_client.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.app_docs_enabled else None,
        lifespan=lifespan,
    )
    app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key)

    if settings.app_docs_enabled:

        @app.get("/docs", include_in_schema=False)
        async def custom_swagger_ui_html() -> HTMLResponse:
            return get_swagger_ui_html(
                openapi_url="/openapi.json",
                title=f"{settings.app_name} - Swagger UI",
                swagger_favicon_url="/favicon.svg",
            )

        @app.get("/redoc", include_in_schema=False)
        async def custom_redoc_html() -> HTMLResponse:
            return get_redoc_html(
                openapi_url="/openapi.json",
                title=f"{settings.app_name} - ReDoc",
                redoc_favicon_url="/favicon.svg",
            )

    # Register routes
    from src.api.v1.router import api_v1_router

    app.include_router(api_v1_router, prefix="/api/v1")

    # Telegram webhook for manager FAQ responses
    from src.api.telegram_webhook import router as telegram_router

    app.include_router(telegram_router, prefix="/api/v1")

    @app.api_route(
        "/api/{full_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        include_in_schema=False,
    )
    async def api_not_found(full_path: str) -> None:
        raise HTTPException(status_code=404, detail="Not Found")

    # Mount SQLAdmin
    from src.api.admin.auth import authentication_backend

    admin = DashboardRedirectAdmin(
        app,
        engine,
        title="Treejar Admin",
        logo_url="/favicon.svg",
        favicon_url="/favicon.svg",
        authentication_backend=authentication_backend,
    )

    from src.api.admin.views import setup_admin_views

    setup_admin_views(admin)

    # --- Brand Favicon & App Icon Routes ---
    def _register_brand_asset_route(
        route_path: str,
        asset_name: str,
        media_type: str,
    ) -> None:
        asset_path = BRAND_STATIC_DIR / asset_name

        @app.api_route(route_path, methods=["GET", "HEAD"], include_in_schema=False)
        async def serve_brand_asset() -> FileResponse:
            return FileResponse(
                asset_path,
                media_type=media_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )

    for _asset_name, _media_type in BRAND_ASSET_MEDIA_TYPES.items():
        _register_brand_asset_route(f"/{_asset_name}", _asset_name, _media_type)
        _register_brand_asset_route(
            f"/dashboard/{_asset_name}",
            _asset_name,
            _media_type,
        )

    # --- Landing Page SPA Integration ---
    import os

    # --- Admin Dashboard SPA Integration ---
    os.makedirs("frontend/admin/dist/assets", exist_ok=True)
    admin_index = "frontend/admin/dist/index.html"
    if not os.path.exists(admin_index):
        with open(admin_index, "w") as f:
            f.write("<html><body>Admin Dashboard (build required)</body></html>")

    app.mount(
        "/dashboard/assets",
        StaticFiles(directory="frontend/admin/dist/assets"),
        name="admin-assets",
    )

    @app.api_route("/admin", methods=["GET", "HEAD"], include_in_schema=False)
    async def redirect_admin_root(request: Request) -> RedirectResponse:
        target = f"/admin/?{request.url.query}" if request.url.query else "/admin/"
        return RedirectResponse(url=target, status_code=302)

    @app.get("/dashboard/telegram-login", include_in_schema=False)
    async def consume_dashboard_telegram_login(
        request: Request,
        token: str = "",
    ) -> RedirectResponse:
        identity = await consume_telegram_admin_login_token(redis_client, token)
        if identity is None:
            if has_admin_session(request):
                return RedirectResponse(
                    url=pop_admin_login_next(request),
                    status_code=303,
                )
            return build_admin_login_redirect(
                request,
                reason="expired_link",
                status_code=303,
                preserve_current_target=False,
            )

        async with async_session_factory() as db:
            await log_admin_action(
                db,
                action="admin_login.telegram",
                entity_type="admin_session",
                actor=f"telegram:{identity.user_id}",
                request=request,
                metadata={
                    "telegram_chat_id": identity.chat_id,
                    "telegram_user_id": identity.user_id,
                    "telegram_username": identity.username,
                    "telegram_first_name": identity.first_name,
                },
            )
            await db.commit()

        display_name = (
            identity.first_name
            or (f"@{identity.username}" if identity.username else None)
            or f"Telegram #{identity.user_id}"
        )
        request.session.update(
            {
                "token": "admin_session",
                "auth_method": "telegram",
                "admin_display_name": display_name,
                "admin_username": identity.username,
                "admin_actor": f"telegram:{identity.user_id}",
            }
        )
        return RedirectResponse(url=pop_admin_login_next(request), status_code=303)

    @app.api_route("/dashboard", methods=["GET", "HEAD"], include_in_schema=False)
    async def redirect_dashboard_root(request: Request) -> RedirectResponse:
        if not has_admin_session(request):
            return build_admin_login_redirect(request)
        target = (
            f"/dashboard/?{request.url.query}" if request.url.query else "/dashboard/"
        )
        return RedirectResponse(url=target, status_code=302)

    @app.api_route(
        "/dashboard/{full_path:path}",
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )
    async def serve_admin_spa(request: Request, full_path: str) -> Response:
        if not has_admin_session(request):
            return build_admin_login_redirect(request)
        dist_dir = os.path.realpath("frontend/admin/dist")
        if full_path:
            candidate = os.path.realpath(os.path.join(dist_dir, full_path))
            if candidate.startswith(f"{dist_dir}{os.sep}") and os.path.isfile(
                candidate
            ):
                return FileResponse(candidate)
        return FileResponse(os.path.join(dist_dir, "index.html"))

    @app.get("/client-self-test", include_in_schema=False)
    @app.get("/client-self-test/{full_path:path}", include_in_schema=False)
    async def serve_client_self_test_spa(full_path: str = "") -> FileResponse:
        dist_dir = "frontend/admin/dist"
        file_path = os.path.join(dist_dir, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))

    # --- Landing Page SPA ---
    # Ensure dist and assets directories exist for local development to avoid startup crash
    os.makedirs("frontend/landing/dist/assets", exist_ok=True)
    index_path = "frontend/landing/dist/index.html"
    if not os.path.exists(index_path):
        with open(index_path, "w") as f:
            f.write("<html><body>Mock Index</body></html>")

    app.mount(
        "/assets",
        StaticFiles(directory="frontend/landing/dist/assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        dist_dir = "frontend/landing/dist"
        file_path = os.path.join(dist_dir, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))

    return app


app = create_app()
