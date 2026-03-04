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
