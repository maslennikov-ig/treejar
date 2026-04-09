from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


class TreejarCatalogClient:
    """Async client for the canonical Treejar catalog API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.base_url = base_url or settings.catalog_api_url
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.catalog_api_timeout_seconds
        )
        self.max_retries = (
            max_retries if max_retries is not None else settings.catalog_api_max_retries
        )
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
        )

    async def _request_json(self, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.client.request("GET", "", params=params)
                if (
                    response.status_code in {429, 500, 502, 503, 504}
                    and attempt < self.max_retries
                ):
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                response.raise_for_status()
            except (httpx.NetworkError, httpx.TimeoutException):
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                raise

            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Treejar catalog API returned a non-object response")
            return payload

        raise RuntimeError("Unreachable")

    @staticmethod
    def _normalize_categories(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        normalized: list[dict[str, Any]] = []
        for raw_category in value:
            if not isinstance(raw_category, dict):
                continue
            category = dict(raw_category)
            category["children"] = TreejarCatalogClient._normalize_categories(
                raw_category.get("children")
            )
            normalized.append(category)
        return normalized

    @staticmethod
    def _normalize_products(value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [dict(product) for product in value if isinstance(product, dict)]

    @staticmethod
    def _flatten_categories(
        categories: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        flattened: list[dict[str, Any]] = []
        for category in categories:
            flattened.append(category)
            children = category.get("children")
            if isinstance(children, list):
                flattened.extend(TreejarCatalogClient._flatten_categories(children))
        return flattened

    @staticmethod
    def _dedupe_key(product: dict[str, Any]) -> str | None:
        raw_sku = product.get("sku")
        if isinstance(raw_sku, str) and raw_sku.strip():
            return raw_sku.strip().lower()

        raw_slug = product.get("slug")
        if isinstance(raw_slug, str) and raw_slug.strip():
            return f"slug::{raw_slug.strip().lower()}"

        return None

    async def get_stats(self) -> dict[str, Any]:
        return await self._request_json({"action": "stats"})

    async def get_categories(self) -> list[dict[str, Any]]:
        payload = await self._request_json({"action": "categories"})
        return self._normalize_categories(payload.get("categories"))

    async def get_category_products(
        self,
        slug: str,
        *,
        limit: int,
        offset: int = 0,
    ) -> dict[str, Any]:
        payload = await self._request_json(
            {
                "action": "category_products",
                "slug": slug,
                "limit": limit,
                "offset": offset,
            }
        )

        total = payload.get("total", 0)
        limit_value = payload.get("limit", limit)
        offset_value = payload.get("offset", offset)
        has_more = payload.get("hasMore", False)

        return {
            "products": self._normalize_products(payload.get("products")),
            "total": total if isinstance(total, int) else 0,
            "limit": limit_value if isinstance(limit_value, int) else limit,
            "offset": offset_value if isinstance(offset_value, int) else offset,
            "hasMore": bool(has_more),
        }

    async def get_product(self, slug: str) -> dict[str, Any]:
        payload = await self._request_json({"action": "product", "slug": slug})
        product = payload.get("product")
        if not isinstance(product, dict):
            raise ValueError(
                f"Treejar catalog product payload missing product for {slug}"
            )
        return dict(product)

    async def iter_all_products(
        self, *, limit: int | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        page_size = limit or settings.catalog_api_page_size
        categories = self._flatten_categories(await self.get_categories())
        seen_keys: set[str] = set()

        for category in categories:
            slug = category.get("slug")
            if not isinstance(slug, str) or not slug.strip():
                continue

            offset = 0
            while True:
                page = await self.get_category_products(
                    slug, limit=page_size, offset=offset
                )
                products = page["products"]
                if not products:
                    break

                for summary in products:
                    hydrated = dict(summary)
                    summary_slug = summary.get("slug")
                    if isinstance(summary_slug, str) and summary_slug.strip():
                        try:
                            hydrated = {
                                **summary,
                                **await self.get_product(summary_slug),
                            }
                        except Exception:
                            logger.warning(
                                "Falling back to summary payload for Treejar slug %s",
                                summary_slug,
                                exc_info=True,
                            )

                    dedupe_key = self._dedupe_key(hydrated)
                    if dedupe_key is None or dedupe_key in seen_keys:
                        continue

                    seen_keys.add(dedupe_key)
                    yield hydrated

                if not page["hasMore"]:
                    break
                offset += len(products)

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> TreejarCatalogClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        await self.close()
