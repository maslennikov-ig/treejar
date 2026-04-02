#!/usr/bin/env python3
"""Integration test runner — runs INSIDE the Docker container.

Usage (from host):
    docker exec treejar-app-1 python scripts/run_integration_tests.py

This script uses real APIs (Zoho CRM, Zoho Inventory, Wazzup) and
real infrastructure (Redis, DB) to verify the full pipeline works.
It sends a generated PDF quotation to WhatsApp as the final step.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import sys
import traceback

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("integration")

# Known test contact
TEST_CONTACT_PHONE = "+971000000001"
TEST_CONTACT_CRM_ID = "559571000034673035"
TEST_CONTACT_NAME = "Integration TestBot"
TEST_CONTACT_EMAIL = "integration-test@treejar.test"

# User's WhatsApp for PDF delivery
USER_WHATSAPP_PHONE = "79262810921"
WAZZUP_CHANNEL_ID = "b49b1b9d-757f-4104-b56d-8f43d62cc515"

# Results tracking
results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append((name, passed, detail))
    log.info(f"{status}: {name}" + (f" — {detail}" if detail else ""))


async def main() -> None:
    import redis.asyncio as aioredis

    from src.core.config import settings

    # ── Redis ──────────────────────────────────────────────────────
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis_client.ping()
        record("Redis connection", True)
    except Exception as e:
        record("Redis connection", False, str(e))
        log.error("Cannot proceed without Redis")
        return

    # ── Zoho CRM ──────────────────────────────────────────────────
    from src.integrations.crm.zoho_crm import ZohoCRMClient

    crm = ZohoCRMClient(redis_client=redis_client)
    contact = None
    segment = None

    try:
        contact = await crm.find_contact_by_phone(TEST_CONTACT_PHONE)
        assert contact is not None, "Test contact not found"
        assert contact["id"] == TEST_CONTACT_CRM_ID
        record("CRM: find test contact", True, f"ID={contact['id']}")
    except Exception as e:
        record("CRM: find test contact", False, str(e))

    if contact:
        segment = contact.get("Segment")
        try:
            assert segment is not None, "Segment is None"
            assert isinstance(segment, list), (
                f"Segment is {type(segment).__name__}, not list"
            )
            record("CRM: Segment is list", True, f"Segment={segment}")
        except Exception as e:
            record("CRM: Segment is list", False, str(e))

    # Non-existent phone
    try:
        none_result = await crm.find_contact_by_phone("+000000000000")
        assert none_result is None
        record("CRM: non-existent returns None", True)
    except Exception as e:
        record("CRM: non-existent returns None", False, str(e))

    # ── Zoho Inventory ────────────────────────────────────────────
    from src.integrations.inventory.zoho_inventory import ZohoInventoryClient

    inventory = ZohoInventoryClient(redis_client=redis_client)
    inventory_items = []

    try:
        data = await inventory.get_items(page=1, per_page=3)
        inventory_items = data.get("items", [])
        assert len(inventory_items) >= 1, "No items found"
        item = inventory_items[0]
        stock = item.get("stock_on_hand")
        assert stock is not None, "stock_on_hand is None"
        assert isinstance(stock, (int, float)), f"stock is {type(stock).__name__}"
        record(
            "Inventory: get_items", True, f"{len(inventory_items)} items, stock={stock}"
        )
    except Exception as e:
        record("Inventory: get_items", False, str(e))

    # get_stock by real SKU
    if inventory_items:
        real_sku = inventory_items[0].get("sku")
        if real_sku:
            try:
                stock_data = await inventory.get_stock(real_sku)
                assert stock_data is not None
                assert "stock_on_hand" in stock_data
                record("Inventory: get_stock(real SKU)", True, f"SKU={real_sku}")
            except Exception as e:
                record("Inventory: get_stock(real SKU)", False, str(e))

    # Fake SKU
    try:
        fake_result = await inventory.get_stock("NONEXISTENT-SKU-XYZ-99999")
        assert fake_result is None
        record("Inventory: fake SKU returns None", True)
    except Exception as e:
        record("Inventory: fake SKU returns None", False, str(e))

    # ── Discounts with real CRM segment ───────────────────────────
    from src.core.discounts import apply_discount, get_discount_percentage

    if segment:
        try:
            discount = get_discount_percentage(segment)
            assert isinstance(discount, int)
            assert discount == 15, f"Expected 15% for Wholesale, got {discount}%"
            price = apply_discount(1000.0, segment)
            assert price == 850.0, f"Expected 850.0, got {price}"
            record("Discounts: real CRM segment", True, f"{discount}% → {price} AED")
        except Exception as e:
            record("Discounts: real CRM segment", False, str(e))

    # ── PDF Generation ────────────────────────────────────────────
    pdf_bytes = None

    if inventory_items and segment is not None:
        try:
            from src.services.pdf.generator import generate_pdf, render_quotation_html

            template_items = []
            subtotal = 0.0

            for inv_item in inventory_items[:3]:
                base_price = float(
                    inv_item.get("rate", 0) or inv_item.get("price", 0) or 100
                )
                unit_price = apply_discount(base_price, segment)
                quantity = 2
                total_price = unit_price * quantity
                subtotal += total_price

                template_items.append(
                    {
                        "sku": inv_item.get("sku", "N/A"),
                        "name": inv_item.get("name", "Unknown"),
                        "description": inv_item.get("description", ""),
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": total_price,
                        "image_url": inv_item.get("image_document_id"),
                    }
                )

            vat_amount = subtotal * 0.05
            grand_total = subtotal + vat_amount

            pdf_context = {
                "quote_number": "INTEG-SERVER-001",
                "trn": "100418386400003",
                "date": _dt.date.today().strftime("%d %B %Y"),
                "customer": {
                    "name": TEST_CONTACT_NAME,
                    "company": "Integration Test Co.",
                    "email": TEST_CONTACT_EMAIL,
                    "address": "UAE",
                },
                "items": template_items,
                "subtotal": subtotal,
                "vat_amount": vat_amount,
                "grand_total": grand_total,
                "manager": {
                    "name": "Syed Amanullah",
                    "phone": "+971545467851",
                    "email": "syed.h@treejartrading.ae",
                },
            }

            html_content = render_quotation_html(pdf_context)
            assert len(html_content) > 100

            pdf_bytes = await generate_pdf(html_content)
            assert len(pdf_bytes) > 1000
            assert pdf_bytes[:5] == b"%PDF-"

            # Save inside container for reference
            with open("/tmp/integration_quotation.pdf", "wb") as f:
                f.write(pdf_bytes)

            record("PDF: generation", True, f"{len(pdf_bytes)} bytes")
        except Exception as e:
            record("PDF: generation", False, f"{e}\n{traceback.format_exc()}")

    # ── Wazzup: Send PDF via WhatsApp ─────────────────────────────
    if pdf_bytes:
        try:
            from src.integrations.messaging.wazzup import WazzupProvider

            wazzup = WazzupProvider(channel_id=WAZZUP_CHANNEL_ID)
            msg_id = await wazzup.send_media(
                chat_id=USER_WHATSAPP_PHONE,
                caption="🧪 Integration Test Quotation (INTEG-SERVER-001) — sent from Docker",
                content=pdf_bytes,
                content_type="application/pdf",
            )
            await wazzup.close()
            assert msg_id != ""
            record("Wazzup: send PDF to WhatsApp", True, f"msg_id={msg_id}")
        except Exception as e:
            record(
                "Wazzup: send PDF to WhatsApp", False, f"{e}\n{traceback.format_exc()}"
            )

    # ── Cleanup ───────────────────────────────────────────────────
    await crm.close()
    await inventory.close()
    await redis_client.aclose()

    # ── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("INTEGRATION TEST RESULTS")
    print("=" * 60)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)

    for name, ok, detail in results:
        status = "✅" if ok else "❌"
        line = f"  {status} {name}"
        if detail:
            line += f" — {detail}"
        print(line)

    print(f"\n{'=' * 60}")
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
