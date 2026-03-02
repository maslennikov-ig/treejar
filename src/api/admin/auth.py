import secrets

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from src.core.config import settings


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

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
        return request.session.get("token") == "admin_session"


authentication_backend = AdminAuth(secret_key=settings.app_secret_key)
