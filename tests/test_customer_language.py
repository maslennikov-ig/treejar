from src.services.customer_language import (
    customer_language_name,
    is_arabic_customer_language,
    normalize_customer_language,
)


def test_customer_language_normalizes_arabic_locale_variants() -> None:
    assert normalize_customer_language("ar") == "ar"
    assert normalize_customer_language("ar-SA") == "ar"
    assert normalize_customer_language("ar_AE") == "ar"
    assert normalize_customer_language("Arabic") == "ar"
    assert normalize_customer_language("العربية") == "ar"
    assert is_arabic_customer_language("ar-SA") is True
    assert customer_language_name("ar_AE") == "Arabic"


def test_customer_language_falls_back_to_english_for_unsupported_output_languages() -> (
    None
):
    assert normalize_customer_language("ru") == "en"
    assert normalize_customer_language("Russian") == "en"
    assert normalize_customer_language(None) == "en"
    assert is_arabic_customer_language("ru") is False
    assert customer_language_name("Russian") == "English"
