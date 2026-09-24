"""API docs routes are opt-in via APP_DOCS_ENABLED."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.config import settings
from src.main import create_app

MARKERS = {"/docs": "swagger-ui", "/redoc": "redoc", "/openapi.json": '"openapi"'}


def _exposed(app: FastAPI) -> dict[str, bool]:
    client = TestClient(app)
    return {path: marker in client.get(path).text for path, marker in MARKERS.items()}


def test_docs_hidden_by_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_docs_enabled", False)
    app = create_app()
    assert not any(_exposed(app).values())
    # Schema generation stays available in-process for contract tests.
    assert app.openapi()["paths"]


def test_docs_exposed_on_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_docs_enabled", True)
    assert all(_exposed(create_app()).values())
