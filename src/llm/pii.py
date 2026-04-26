import re
import uuid

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# Matches an optional '+' and 1-4 digits, followed by 6-14 digits mixed with spaces, dashes, or parens
PHONE_PATTERN = re.compile(r"\+?\d{1,4}(?:[\s\-()]*\d){6,14}")
PRODUCT_CODE_LABEL_PATTERN = re.compile(
    r"(?:\bsku\b|\bmodel\b|\bitem\b|\barticle\b|\bproduct\s+code\b)\s*[:#-]?\s*$",
    re.IGNORECASE,
)


def _is_labeled_product_code(text: str, match: re.Match[str]) -> bool:
    prefix = text[max(0, match.start() - 32) : match.start()]
    return PRODUCT_CODE_LABEL_PATTERN.search(prefix) is not None


def mask_pii(text: str) -> tuple[str, dict[str, str]]:
    """
    Masks emails and phone numbers in the given text.
    Returns the masked text and a mapping of placeholders to original values.
    """
    pii_map: dict[str, str] = {}
    masked_text = text

    def repl(match: re.Match[str]) -> str:
        original = match.group(0)
        if _is_labeled_product_code(masked_text, match):
            return original
        placeholder = f"[PII-{uuid.uuid4().hex[:4]}]"
        pii_map[placeholder] = original
        return placeholder

    # Mask emails
    masked_text = EMAIL_PATTERN.sub(repl, masked_text)

    # Mask phones
    masked_text = PHONE_PATTERN.sub(repl, masked_text)

    return masked_text, pii_map


def unmask_pii(text: str, pii_map: dict[str, str]) -> str:
    """
    Restores original values in the text using the provided PII map.
    """
    unmasked_text = text
    for placeholder, original in pii_map.items():
        unmasked_text = unmasked_text.replace(placeholder, original)
    return unmasked_text
