"""Regression tests for universal Treejar × Noor brand favicons and app icons."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from PIL import Image

from src.core.config import settings
from src.main import BRAND_ASSET_MEDIA_TYPES, BRAND_STATIC_DIR, create_app

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_brand_assets_exist_and_stay_in_sync() -> None:
    landing_public = REPO_ROOT / "frontend" / "landing" / "public"
    admin_public = REPO_ROOT / "frontend" / "admin" / "public"
    docs_favicon = REPO_ROOT / "docs" / "assets" / "favicon.svg"

    for asset_name in BRAND_ASSET_MEDIA_TYPES:
        canonical = BRAND_STATIC_DIR / asset_name
        assert canonical.is_file(), f"Missing canonical asset: {canonical}"
        canonical_bytes = canonical.read_bytes()
        assert len(canonical_bytes) > 0

        assert (landing_public / asset_name).read_bytes() == canonical_bytes
        assert (admin_public / asset_name).read_bytes() == canonical_bytes

    assert docs_favicon.read_bytes() == (BRAND_STATIC_DIR / "favicon.svg").read_bytes()


def test_brand_binary_icon_dimensions_and_formats() -> None:
    ico_bytes = (BRAND_STATIC_DIR / "favicon.ico").read_bytes()
    reserved, ico_type, count = struct.unpack("<HHH", ico_bytes[:6])
    assert (reserved, ico_type, count) == (0, 1, 3)

    with Image.open(BRAND_STATIC_DIR / "favicon.ico") as ico_img:
        assert sorted(ico_img.info.get("sizes", [])) == [(16, 16), (32, 32), (48, 48)]

    with Image.open(BRAND_STATIC_DIR / "favicon-32x32.png") as png_32:
        assert png_32.size == (32, 32)
        assert png_32.mode == "RGBA"
        corner_pixel = png_32.getpixel((0, 0))
        assert isinstance(corner_pixel, tuple) and corner_pixel[3] == 0

    with Image.open(BRAND_STATIC_DIR / "apple-touch-icon.png") as apple_img:
        assert apple_img.size == (180, 180)
        assert apple_img.mode == "RGB"

    with Image.open(BRAND_STATIC_DIR / "icon-192.png") as png_192:
        assert png_192.size == (192, 192)

    with Image.open(BRAND_STATIC_DIR / "icon-512.png") as png_512:
        assert png_512.size == (512, 512)


@pytest.mark.asyncio
async def test_public_favicon_routes_served_at_root_and_dashboard_without_auth(
    client: AsyncClient,
) -> None:
    # Ensure /dashboard/ itself remains auth-gated while brand icons stay public.
    dashboard_resp = await client.get("/dashboard/", follow_redirects=False)
    assert dashboard_resp.status_code in (302, 303, 401)

    for asset_name, expected_media_type in BRAND_ASSET_MEDIA_TYPES.items():
        expected_bytes = (BRAND_STATIC_DIR / asset_name).read_bytes()

        for prefix in ("", "/dashboard"):
            url = f"{prefix}/{asset_name}"
            resp = await client.get(url, follow_redirects=False)
            assert resp.status_code == 200, f"GET failed for {url}"
            assert resp.headers["content-type"].startswith(expected_media_type)
            assert resp.content == expected_bytes

            head_resp = await client.head(url, follow_redirects=False)
            assert head_resp.status_code == 200, f"HEAD failed for {url}"


@pytest.mark.asyncio
async def test_sqladmin_login_and_views_include_brand_favicon(
    client: AsyncClient,
) -> None:
    login_page = await client.get("/admin/login")
    assert login_page.status_code == 200
    assert 'href="/favicon.svg"' in login_page.text
    assert 'href="/apple-touch-icon.png"' in login_page.text
    assert 'src="/favicon.svg"' in login_page.text

    await client.post(
        "/admin/login",
        data={
            "username": settings.admin_username,
            "password": settings.admin_password,
        },
    )
    admin_root = await client.get("/admin/")
    assert admin_root.status_code == 200
    assert 'href="/favicon.svg"' in admin_root.text
    assert 'src="/favicon.svg"' in admin_root.text


def test_openapi_docs_use_local_brand_favicon_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_docs_enabled", True)
    test_client = TestClient(create_app())

    for docs_path in ("/docs", "/redoc"):
        resp = test_client.get(docs_path)
        assert resp.status_code == 200
        assert "/favicon.svg" in resp.text
        assert "fastapi.tiangolo.com" not in resp.text


def test_frontend_and_standalone_html_surfaces_declare_favicon() -> None:
    for html_rel in ("frontend/landing/index.html", "frontend/admin/index.html"):
        html_text = (REPO_ROOT / html_rel).read_text(encoding="utf-8")
        assert 'rel="icon" href="/favicon.ico"' in html_text
        assert 'rel="icon" type="image/svg+xml" href="/favicon.svg"' in html_text
        assert (
            'rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png"'
            in html_text
        )
        assert (
            'rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png"'
            in html_text
        )
        assert 'rel="manifest" href="/site.webmanifest"' in html_text

    admin_app_tsx = (REPO_ROOT / "frontend" / "admin" / "src" / "App.tsx").read_text(
        encoding="utf-8"
    )
    sidebar_tsx = (
        REPO_ROOT / "frontend" / "admin" / "src" / "components" / "Sidebar.tsx"
    ).read_text(encoding="utf-8")
    assert 'src="/dashboard/favicon.svg"' in admin_app_tsx
    assert 'src="/dashboard/favicon.svg"' in sidebar_tsx

    standalone_html_files = sorted(
        list((REPO_ROOT / "docs" / "client").glob("*.html"))
        + list((REPO_ROOT / "docs" / "offers").glob("*.html"))
    )
    assert standalone_html_files
    for doc_html in standalone_html_files:
        content = doc_html.read_text(encoding="utf-8")
        assert 'rel="icon" type="image/svg+xml"' in content, (
            f"Missing favicon in {doc_html}"
        )
