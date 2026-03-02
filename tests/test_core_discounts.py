from src.core.discounts import apply_discount, get_discount_percentage


def test_get_discount_percentage():
    assert get_discount_percentage("Wholesale") == 15
    assert get_discount_percentage("Developer") == 5
    assert get_discount_percentage("Unknown") == 0

def test_apply_discount():
    assert apply_discount(100.0, "Wholesale") == 85.0
    assert apply_discount(100.0, "Unknown") == 100.0
