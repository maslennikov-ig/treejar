#!/usr/bin/env python3
"""Send PDF via Wazzup using contentUri.

Saves the PDF to FastAPI static dir, uses the app's public URL for contentUri.

Usage:
    docker exec -e PYTHONPATH=/app treejar-app-1 python scripts/send_test_pdf.py
"""

import asyncio
import datetime as _dt
import logging
import os
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("send_pdf")

WAZZUP_CHANNEL_ID = "b49b1b9d-757f-4104-b56d-8f43d62cc515"
USER_WHATSAPP_PHONE = "79262810921"
TEST_CONTACT_PHONE = "+971000000001"


async def main() -> None:
    import redis.asyncio as aioredis

    from src.core.config import settings
    from src.core.discounts import apply_discount
    from src.integrations.crm.zoho_crm import ZohoCRMClient
    from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
    from src.services.pdf.generator import generate_pdf, render_quotation_html

    redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    # 1. Get real data
    crm = ZohoCRMClient(redis_client=redis)
    inventory = ZohoInventoryClient(redis_client=redis)

    contact = await crm.find_contact_by_phone(TEST_CONTACT_PHONE)
    assert contact, "Test contact not found"
    segment = contact.get("Segment")
    log.info(f"CRM segment: {segment}")

    data = await inventory.get_items(page=1, per_page=3)
    items = data.get("items", [])
    assert items, "No Inventory items"

    # 2. Build PDF
    template_items = []
    subtotal = 0.0
    for inv_item in items[:3]:
        bp = float(inv_item.get("rate", 0) or inv_item.get("price", 0) or 100)
        up = apply_discount(bp, segment)
        qty = 2
        tot = up * qty
        subtotal += tot
        template_items.append({
            "sku": inv_item.get("sku", "N/A"),
            "name": inv_item.get("name", "Unknown"),
            "description": inv_item.get("description", ""),
            "quantity": qty,
            "unit_price": up,
            "total_price": tot,
            "image_url": inv_item.get("image_document_id"),
        })

    vat = subtotal * 0.05
    pdf_context = {
        "quote_number": "INTEG-PDF-002",
        "trn": "100418386400003",
        "date": _dt.date.today().strftime("%d %B %Y"),
        "customer": {"name": "Integration TestBot", "company": "Test Co.", "email": "test@test.test", "address": "UAE"},
        "items": template_items,
        "subtotal": subtotal,
        "vat_amount": vat,
        "grand_total": subtotal + vat,
        "manager": {"name": "Syed Amanullah", "phone": "+971545467851", "email": "syed.h@treejartrading.ae"},
    }

    html = render_quotation_html(pdf_context)
    pdf_bytes = await generate_pdf(html)
    log.info(f"PDF generated: {len(pdf_bytes)} bytes")

    # 3. Save to a publicly accessible static path served by nginx
    static_dir = Path("/app/frontend/admin/dist/assets")
    static_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = static_dir / "test_quotation.pdf"
    pdf_path.write_bytes(pdf_bytes)
    log.info(f"Saved to {pdf_path}")

    # The app is served at dev.noor.starec.ai (port 8003 internally)
    # Static assets are mounted at /admin/assets/
    public_url = "https://dev.noor.starec.ai/admin/assets/test_quotation.pdf"
    log.info(f"Public URL: {public_url}")

    # 4. Send via Wazzup with contentUri
    async with httpx.AsyncClient(timeout=30.0) as http:
        payload = {
            "channelId": WAZZUP_CHANNEL_ID,
            "chatType": "whatsapp",
            "chatId": USER_WHATSAPP_PHONE,
            "contentUri": public_url,
        }
        resp = await http.post(
            "https://api.wazzup24.com/v3/message",
            headers={"Authorization": f"Bearer {settings.wazzup_api_key}"},
            json=payload,
        )
        log.info(f"Wazzup response: {resp.status_code} {resp.text}")
        resp.raise_for_status()

        # Send caption separately
        payload2 = {
            "channelId": WAZZUP_CHANNEL_ID,
            "chatType": "whatsapp",
            "chatId": USER_WHATSAPP_PHONE,
            "text": "🧪 Тестовый PDF (INTEG-PDF-002) — реальные данные из Zoho Inventory со скидкой 15% Wholesale",
        }
        resp2 = await http.post(
            "https://api.wazzup24.com/v3/message",
            headers={"Authorization": f"Bearer {settings.wazzup_api_key}"},
            json=payload2,
        )
        log.info(f"Wazzup caption: {resp2.status_code} {resp2.text}")

    await crm.close()
    await inventory.close()
    await redis.aclose()
    log.info("✅ Done! Check WhatsApp.")


if __name__ == "__main__":
    asyncio.run(main())
