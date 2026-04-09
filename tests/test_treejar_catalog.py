from unittest.mock import AsyncMock

import httpx
import pytest

from src.integrations.catalog.treejar_catalog import TreejarCatalogClient


def _response(payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request(
            "GET",
            "https://new.treejartrading.ae/api/catalog",
        ),
    )


@pytest.mark.asyncio
async def test_get_categories_parses_live_like_payload() -> None:
    client = TreejarCatalogClient()

    payload = {
        "categories": [
            {
                "slug": "chairs",
                "name": "Chairs",
                "description": None,
                "productCount": 80,
                "children": [
                    {
                        "slug": "executive-chair",
                        "name": "Executive Chair",
                        "description": "Executive seating",
                        "productCount": 47,
                    }
                ],
            }
        ]
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client.client, "request", AsyncMock(return_value=_response(payload)))
        categories = await client.get_categories()

    assert categories[0]["slug"] == "chairs"
    assert categories[0]["children"][0]["slug"] == "executive-chair"
    await client.close()


@pytest.mark.asyncio
async def test_get_category_products_parses_pagination_payload() -> None:
    client = TreejarCatalogClient()

    payload = {
        "products": [
            {
                "slug": "executive-office-chair-ch-145-black-ch-145-black",
                "sku": "CH 145 black",
                "name": "Executive Office Chair CH 145 black",
                "price": 503,
                "salePrice": None,
                "onSale": False,
                "currency": "AED",
                "priceExclVAT": True,
                "brand": "FOSHAN BWELL FURNITURE CO.,LTD",
                "inStock": True,
                "stockQuantity": 109,
                "weight": None,
                "category": "Executive Chair",
                "categorySlug": "executive-chair",
                "image": "https://cdn.example/main.jpg",
                "url": "https://new.treejartrading.ae/product/example",
            }
        ],
        "total": 80,
        "limit": 2,
        "offset": 0,
        "hasMore": True,
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(client.client, "request", AsyncMock(return_value=_response(payload)))
        page = await client.get_category_products("chairs", limit=2, offset=0)

    assert page["total"] == 80
    assert page["hasMore"] is True
    assert page["products"][0]["sku"] == "CH 145 black"
    await client.close()


@pytest.mark.asyncio
async def test_iter_all_products_handles_categories_pagination_and_hydration() -> None:
    client = TreejarCatalogClient()
    client.get_categories = AsyncMock(
        return_value=[
            {
                "slug": "chairs",
                "name": "Chairs",
                "children": [
                    {
                        "slug": "executive-chair",
                        "name": "Executive Chair",
                        "children": [],
                    }
                ],
            }
        ]
    )
    client.get_category_products = AsyncMock(
        side_effect=[
            {
                "products": [
                    {"slug": "chair-1", "sku": "SKU-1", "name": "Chair 1"},
                    {"slug": "dup-a", "sku": "SKU-2", "name": "Chair 2"},
                ],
                "total": 3,
                "limit": 2,
                "offset": 0,
                "hasMore": True,
            },
            {
                "products": [
                    {"slug": "slug-only", "sku": None, "name": "Slug Only"},
                ],
                "total": 3,
                "limit": 2,
                "offset": 2,
                "hasMore": False,
            },
            {
                "products": [
                    {"slug": "dup-b", "sku": "SKU-2", "name": "Chair 2 duplicate"},
                ],
                "total": 1,
                "limit": 2,
                "offset": 0,
                "hasMore": False,
            },
        ]
    )
    client.get_product = AsyncMock(
        side_effect=[
            {
                "slug": "chair-1",
                "sku": "SKU-1",
                "name": "Chair 1",
                "description": "Hydrated chair 1",
            },
            {
                "slug": "dup-a",
                "sku": "SKU-2",
                "name": "Chair 2",
                "description": "Hydrated chair 2",
            },
            {
                "slug": "slug-only",
                "sku": None,
                "name": "Slug Only",
                "description": "Hydrated slug only",
            },
            {
                "slug": "dup-b",
                "sku": "SKU-2",
                "name": "Chair 2 duplicate",
                "description": "Duplicate hydrated chair 2",
            },
        ]
    )

    products = [product async for product in client.iter_all_products(limit=2)]

    assert [product["slug"] for product in products] == [
        "chair-1",
        "dup-a",
        "slug-only",
    ]
    assert client.get_category_products.await_count == 3
    assert client.get_product.await_count == 4
