from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from src.core.config import settings


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form.get("username"), form.get("password")

        if username == settings.admin_username and password == settings.admin_password:
            request.session.update({"token": "admin_session"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("token") == "admin_session"


authentication_backend = AdminAuth(secret_key=settings.app_secret_key)
