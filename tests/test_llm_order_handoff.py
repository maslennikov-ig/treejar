import pytest

from src.llm.order_handoff import is_high_confidence_first_turn_order


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I need 200 chairs delivered to Dubai Marina by next week", True),
        ("We need 40 workstations installed in Abu Dhabi next Monday", True),
        ("We need 20 chairs for next week, what options do you have?", False),
        ("What is your MOQ for chairs?", False),
        ("What are your wholesale prices for bulk orders?", False),
        ("Can you quote bulk pricing for desks?", False),
    ],
)
def test_is_high_confidence_first_turn_order(text: str, expected: bool) -> None:
    assert is_high_confidence_first_turn_order(text) is expected
