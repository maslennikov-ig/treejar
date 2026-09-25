from src.core.chat_id import base_chat_id


def test_suffixes_are_dropped_from_the_customer_number() -> None:
    assert base_chat_id("79689818825#archived-20260925123859-69d8dba5") == (
        "79689818825"
    )
    assert base_chat_id("79262810921#r4-a") == "79262810921"


def test_a_plain_number_is_kept() -> None:
    assert base_chat_id(" +971501234567 ") == "+971501234567"
    assert base_chat_id("#tag-only") == "#tag-only"
