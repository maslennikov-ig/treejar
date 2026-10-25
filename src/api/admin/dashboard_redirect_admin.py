from __future__ import annotations

from typing import Any

from sqladmin import Admin
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from src.api.admin.auth import (
    DEFAULT_ADMIN_REDIRECT,
    has_admin_session,
    pop_admin_login_next,
    remember_admin_login_next,
    sanitize_admin_next_path,
)
from src.core.config import settings

_LOGIN_REASONS: dict[str, str] = {
    "expired_link": (
        "Одноразовая ссылка для входа устарела или уже была использована. "
        "Запросите новую команду /admin в боте или войдите по паролю ниже."
    ),
    "session_expired": (
        "Сессия администратора завершилась. Войдите снова, чтобы продолжить "
        "работу с выбранным разделом."
    ),
}


def _telegram_login_context() -> dict[str, Any]:
    username = settings.telegram_bot_username.strip().lstrip("@")
    if not username:
        username = "Treejar_Trading_bot"
    return {
        "telegram_admin_bot_username": username,
        "telegram_admin_bot_url": f"https://t.me/{username}?start=admin",
        "telegram_admin_command": "/admin",
        "next_url": DEFAULT_ADMIN_REDIRECT,
        "notice": None,
    }


class DashboardRedirectAdmin(Admin):
    """SQLAdmin wrapper that lands normal admins in the CRM dashboard."""

    async def login(self, request: Request) -> Response:
        if self.authentication_backend is None:
            raise HTTPException(
                status_code=503,
                detail="Authentication backend not configured.",
            )

        context = _telegram_login_context()
        query_next = request.query_params.get("next")
        reason = request.query_params.get("reason", "").strip()
        if reason in _LOGIN_REASONS:
            context["notice"] = _LOGIN_REASONS[reason]

        if request.method == "GET":
            if has_admin_session(request) and request.query_params.get("force") != "1":
                return RedirectResponse(
                    url=pop_admin_login_next(request, query_next),
                    status_code=302,
                )
            if query_next:
                context["next_url"] = remember_admin_login_next(request, query_next)
            else:
                context["next_url"] = sanitize_admin_next_path(
                    request.session.get("admin_login_next")
                    if "session" in request.scope
                    else None
                )
            return await self.templates.TemplateResponse(
                request,
                "sqladmin/login.html",
                context,
            )

        form = await request.form()
        raw_form_next = form.get("next")
        explicit_next = (
            raw_form_next
            if isinstance(raw_form_next, str) and raw_form_next.strip()
            else query_next
        )

        ok = await self.authentication_backend.login(request)
        if not ok:
            context["error"] = "Invalid credentials."
            context["next_url"] = remember_admin_login_next(request, explicit_next)
            return await self.templates.TemplateResponse(
                request, "sqladmin/login.html", context, status_code=400
            )

        return RedirectResponse(
            url=pop_admin_login_next(request, explicit_next),
            status_code=302,
        )
