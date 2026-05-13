from weasyprint import HTML

from src.services.pdf.generator import render_quotation_html


def test_render_quotation_template() -> None:
    context = {
        "quote_number": "SA 270226 - R1",
        "trn": "100418386400003",
        "date": "27-02-2026",
        "customer": {
            "name": "Test User",
            "company": "Test Co",
            "email": "test@testco.com",
            "address": "Dubai, UAE",
        },
        "items": [
            {
                "sku": "ITEM-1",
                "name": "Test Table",
                "description": "A very nice table",
                "quantity": 2,
                "unit_price": 500.0,
                "total_price": 1000.0,
            }
        ],
        "subtotal": 1000.0,
        "vat_amount": 50.0,
        "grand_total": 1050.0,
        "manager": {
            "name": "Syed Amanullah",
            "phone": "+971545467851",
            "email": "syed.h@treejartrading.ae",
        },
    }

    html = render_quotation_html(context=context)

    # Assertions to ensure context is injected properly
    assert "Test Co" in html
    assert "SA 270226 - R1" in html
    assert "Test Table" in html
    assert "1050.00" in html
    assert "@page {" in html  # Checking if CSS is injected
    assert "Skyland" not in html


def test_render_quotation_template_omits_empty_optional_customer_fields() -> None:
    context = {
        "quote_number": "SA 270226 - R2",
        "trn": "100418386400003",
        "date": "27-02-2026",
        "customer": {
            "name": "Лилия",
            "company": "",
            "email": "",
            "phone": "+971501234567",
            "address": "",
        },
        "items": [
            {
                "sku": "ITEM-1",
                "name": "Test Table",
                "description": "A very nice table",
                "quantity": 2,
                "unit_price": 500.0,
                "total_price": 1000.0,
            }
        ],
        "subtotal": 1000.0,
        "vat_amount": 50.0,
        "grand_total": 1050.0,
        "manager": {
            "name": "Syed Amanullah",
            "phone": "+971545467851",
            "email": "syed.h@treejartrading.ae",
        },
    }

    html = render_quotation_html(context=context)

    assert "Treejar Trading FZC LLC" in html
    assert "Skyland" not in html
    assert "<strong>Name:</strong> Лилия" in html
    assert "<strong>Phone:</strong> +971501234567" in html
    assert "<strong>Address:</strong>" not in html
    assert "UAE" not in html
    assert "<strong>Company:</strong>" not in html
    assert "<strong>Email:</strong>" not in html


def test_compact_quotation_pdf_keeps_three_realistic_items_on_one_page() -> None:
    description = (
        "Ergonomic chair with adjustable height, breathable mesh back, nylon base, "
        "and durable caster wheels."
    )
    items = [
        {
            "sku": f"CHAIR-{index:02d}",
            "name": f"Premium ergonomic office chair model {index}",
            "description": description,
            "quantity": 1,
            "unit_price": 575.0,
            "total_price": 575.0,
        }
        for index in range(1, 4)
    ]
    subtotal = sum(item["total_price"] for item in items)
    context = {
        "quote_number": "SA 270226 - R3",
        "trn": "100418386400003",
        "date": "27-02-2026",
        "customer": {
            "name": "Test User",
            "company": "Treejar Test Procurement LLC",
            "phone": "+971501234567",
            "email": "procurement@example.com",
            "address": "Office 1201, Business Bay, Dubai, UAE",
        },
        "items": items,
        "subtotal": subtotal,
        "vat_amount": subtotal * 0.05,
        "grand_total": subtotal * 1.05,
        "manager": {
            "name": "Syed Amanullah",
            "phone": "+971545467851",
            "email": "syed.h@treejartrading.ae",
        },
    }

    html = render_quotation_html(context=context)
    rendered_pdf = HTML(string=html).render()

    assert len(rendered_pdf.pages) == 1
