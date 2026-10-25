from __future__ import annotations

import secrets
from urllib.parse import urlencode, urlsplit

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse

from src.core.config import settings

ADMIN_LOGIN_PATH = "/admin/login"
DEFAULT_ADMIN_REDIRECT = "/dashboard/"
_SESSION_NEXT_KEY = "admin_login_next"
_EXCLUDED_NEXT_PATHS = {
    "/admin/login",
    "/admin/logout",
    "/dashboard/telegram-login",
}


def has_admin_session(request: Request) -> bool:
    """Return True when the request carries an active admin session cookie."""
    try:
        return request.session.get("token") == "admin_session"
    except AssertionError:
        return False


def sanitize_admin_next_path(
    raw_next: str | None,
    *,
    default: str = DEFAULT_ADMIN_REDIRECT,
) -> str:
    """Validate and normalize a local post-login redirect target.

    Accepts only same-origin relative paths under ``/dashboard`` or ``/admin``
    (excluding login/logout endpoints) and strips schemes, hosts, or control chars.
    """
    if not raw_next:
        return default
    candidate = raw_next.strip()
    if (
        not candidate
        or not candidate.startswith("/")
        or candidate.startswith("//")
        or candidate.startswith("/\\")
        or any(ch in candidate for ch in ("\r", "\n", "\x00"))
    ):
        return default

    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return default

    path = parsed.path
    if path == "/dashboard":
        path = "/dashboard/"
    elif path == "/admin":
        path = "/admin/"

    if path in _EXCLUDED_NEXT_PATHS:
        return default
    if not (path.startswith("/dashboard/") or path.startswith("/admin/")):
        return default

    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def remember_admin_login_next(request: Request, raw_next: str | None) -> str:
    """Persist a sanitized post-login target in the session when non-default."""
    target = sanitize_admin_next_path(raw_next)
    try:
        if target != DEFAULT_ADMIN_REDIRECT:
            request.session[_SESSION_NEXT_KEY] = target
        else:
            request.session.pop(_SESSION_NEXT_KEY, None)
    except AssertionError:
        pass
    return target


def pop_admin_login_next(
    request: Request,
    explicit_next: str | None = None,
) -> str:
    """Consume any saved post-login target, preferring an explicit value."""
    saved: str | None = None
    try:
        raw_saved = request.session.pop(_SESSION_NEXT_KEY, None)
        if isinstance(raw_saved, str):
            saved = raw_saved
    except AssertionError:
        saved = None

    chosen = explicit_next.strip() if explicit_next and explicit_next.strip() else saved
    return sanitize_admin_next_path(chosen)


def build_admin_login_redirect(
    request: Request,
    *,
    reason: str | None = None,
    status_code: int = 302,
    preserve_current_target: bool = True,
) -> RedirectResponse:
    """Redirect unauthenticated browser navigation to ``/admin/login``."""
    target = DEFAULT_ADMIN_REDIRECT
    if preserve_current_target:
        raw_target = request.url.path
        if request.url.query:
            raw_target = f"{raw_target}?{request.url.query}"
        target = remember_admin_login_next(request, raw_target)
    else:
        try:
            existing = request.session.get(_SESSION_NEXT_KEY)
            if isinstance(existing, str):
                target = sanitize_admin_next_path(existing)
        except AssertionError:
            target = DEFAULT_ADMIN_REDIRECT

    params: dict[str, str] = {}
    if target != DEFAULT_ADMIN_REDIRECT:
        params["next"] = target
    if reason:
        params["reason"] = reason

    login_url = ADMIN_LOGIN_PATH
    if params:
        login_url = f"{ADMIN_LOGIN_PATH}?{urlencode(params)}"
    return RedirectResponse(url=login_url, status_code=status_code)


class AdminAuth(AuthenticationBackend):
    def __init__(self, secret_key: str) -> None:
        # The root FastAPI app owns the shared session boundary for
        # /admin, /dashboard, and /api/v1/admin.
        self.middlewares = []

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))

        is_valid_user = secrets.compare_digest(username, settings.admin_username)
        is_valid_pass = secrets.compare_digest(password, settings.admin_password)

        if is_valid_user and is_valid_pass:
            request.session.update({"token": "admin_session"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return has_admin_session(request)


authentication_backend = AdminAuth(secret_key=settings.app_secret_key)
