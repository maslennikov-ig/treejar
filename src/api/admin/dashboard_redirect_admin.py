from sqladmin import Admin
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response


class DashboardRedirectAdmin(Admin):
    """SQLAdmin wrapper that lands normal admins in the CRM dashboard."""

    async def login(self, request: Request) -> Response:
        if self.authentication_backend is None:
            raise HTTPException(
                status_code=503,
                detail="Authentication backend not configured.",
            )

        context: dict[str, str] = {}
        if request.method == "GET":
            return await self.templates.TemplateResponse(request, "sqladmin/login.html")

        ok = await self.authentication_backend.login(request)
        if not ok:
            context["error"] = "Invalid credentials."
            return await self.templates.TemplateResponse(
                request, "sqladmin/login.html", context, status_code=400
            )

        return RedirectResponse(url="/dashboard/", status_code=302)
