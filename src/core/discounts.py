DISCOUNTS = {
    "Wholesale": 15,
    "Retail chain B2B": 15,
    "Horeca": 10,
    "Design Agency": 10,
    "Developer": 5
}

def get_discount_percentage(segment: str) -> int:
    return DISCOUNTS.get(segment, 0)

def apply_discount(price: float, segment: str) -> float:
    discount = get_discount_percentage(segment)
    return price * (1 - (discount / 100.0))
