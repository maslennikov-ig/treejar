"""Script 11: Verify health and API endpoints via HTTP.

Run from anywhere with network access to the server:
    python scripts/verify_api.py --base-url https://noor.starec.ai

Or inside Docker:
    docker compose -p treejar-prod exec app python scripts/verify_api.py --base-url http://localhost:8000
"""

import argparse
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

passed = 0
failed = 0


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"  ✅ {msg}")


def fail(msg: str) -> None:
    global failed
    failed += 1
    print(f"  ❌ {msg}")


async def check_endpoint(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    name: str,
    *,
    expect_status: int = 200,
) -> None:
    try:
        if method == "GET":
            resp = await client.get(path)
        elif method == "POST":
            resp = await client.post(path, json={})
        else:
            fail(f"Unknown method {method}")
            return

        if resp.status_code == expect_status:
            ok(f"{name}: {method} {path} → {resp.status_code}")
        else:
            fail(
                f"{name}: {method} {path} → {resp.status_code} (expected {expect_status})"
            )
    except Exception as e:
        fail(f"{name}: {method} {path} → ERROR: {e}")


async def main(base_url: str) -> None:
    print("=" * 60)
    print("Script 11: Health & API Endpoints Verification")
    print(f"  Target: {base_url}")
    print("=" * 60)

    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        # 1. Health endpoint
        print("\n--- 11.1 Health ---")
        await check_endpoint(client, "GET", "/api/v1/health", "Health check")

        # 2. Product endpoints
        print("\n--- 11.2 Products ---")
        await check_endpoint(client, "GET", "/api/v1/products/", "Product list")

        # 3. Conversation endpoints
        print("\n--- 11.3 Conversations ---")
        await check_endpoint(
            client, "GET", "/api/v1/conversations/", "Conversation list"
        )

        # 4. Quality endpoints
        print("\n--- 11.4 Quality ---")
        await check_endpoint(
            client,
            "GET",
            "/api/v1/quality/reviews/",
            "Quality reviews",
            expect_status=403,
        )

        # 5. Webhook endpoint (should accept POST but may require valid payload)
        print("\n--- 11.5 Webhook ---")
        try:
            # Just check the endpoint doesn't 500 — 403/422 is acceptable
            resp = await client.post(
                "/api/v1/webhook/wazzup",
                json={"messages": []},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code < 500:
                ok(f"Webhook endpoint reachable: {resp.status_code}")
            else:
                fail(f"Webhook returned 5xx: {resp.status_code}")
        except Exception as e:
            fail(f"Webhook check failed: {e}")

        # 6. Admin panel
        print("\n--- 11.6 Admin panel ---")
        try:
            resp = await client.get("/admin/", follow_redirects=True)
            if resp.status_code < 500:
                ok(f"Admin panel reachable: {resp.status_code}")
            else:
                fail(f"Admin panel 5xx: {resp.status_code}")
        except Exception as e:
            fail(f"Admin panel check failed: {e}")

        # 7. Metrics/dashboard API
        print("\n--- 11.7 Metrics ---")
        await check_endpoint(
            client, "GET", "/api/v1/admin/metrics", "Metrics API", expect_status=200
        )

    print("\n" + "=" * 60)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify API endpoints")
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE_URL", "http://localhost:8000"),
        help="Base URL of the API server",
    )
    args = parser.parse_args()
    asyncio.run(main(args.base_url))
