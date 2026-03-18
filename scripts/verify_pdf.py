"""Script 10: Verify PDF / quotation generation.

Run inside Docker:
    docker compose -p treejar-prod exec app python scripts/verify_pdf.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


async def main() -> None:
    print("=" * 60)
    print("Script 10: PDF / Quotation Generation Verification")
    print("=" * 60)

    # 1. Module imports
    print("\n--- 10.1 Module imports ---")
    try:
        from src.services.pdf.generator import generate_pdf, render_quotation_html

        ok("PDF generator modules imported OK")
    except ImportError as e:
        fail(f"Import error: {e}")
        return

    # 2. Render HTML
    print("\n--- 10.2 HTML rendering ---")
    try:
        context = {
            "company_name": "Test LLC",
            "customer_name": "John Doe",
            "items": [
                {"name": "Office Chair", "qty": 2, "price": 500.0, "total": 1000.0},
                {"name": "Desk Lamp", "qty": 1, "price": 150.0, "total": 150.0},
            ],
            "subtotal": 1150.0,
            "discount": 50.0,
            "total": 1100.0,
            "currency": "AED",
            "date": "2026-03-18",
            "quotation_number": "QT-TEST-001",
        }
        html = render_quotation_html(context)
        if html and len(html) > 100:
            ok(f"HTML rendered ({len(html)} chars)")
        else:
            fail("HTML rendering returned empty or too short")
    except Exception as e:
        fail(f"HTML rendering failed: {e}")
        html = None

    # 3. PDF generation
    print("\n--- 10.3 PDF generation ---")
    if html:
        try:
            pdf_bytes = await generate_pdf(html)
            if pdf_bytes and len(pdf_bytes) > 100:
                ok(f"PDF generated ({len(pdf_bytes)} bytes)")
                # Quick PDF signature check
                if pdf_bytes[:4] == b"%PDF":
                    ok("PDF header signature valid")
                else:
                    fail("PDF header signature invalid (not %PDF)")
            else:
                fail("PDF generation returned empty or too small")
        except Exception as e:
            fail(f"PDF generation failed: {e}")
    else:
        fail("Cannot generate PDF — HTML step failed")

    # 4. LLM tool check
    print("\n--- 10.4 LLM quotation tool ---")
    try:
        from src.llm.engine import create_quotation  # noqa: F401

        ok("create_quotation LLM tool exists")
    except ImportError as e:
        fail(f"create_quotation import error: {e}")

    print("\n" + "=" * 60)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
