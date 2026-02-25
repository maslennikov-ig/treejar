import re
import uuid

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# Matches an optional '+' and 1-4 digits, followed by 6-14 digits mixed with spaces, dashes, or parens
PHONE_PATTERN = re.compile(r"\+?\d{1,4}(?:[\s\-()]*\d){6,14}")


def mask_pii(text: str) -> tuple[str, dict[str, str]]:
    """
    Masks emails and phone numbers in the given text.
    Returns the masked text and a mapping of placeholders to original values.
    """
    pii_map: dict[str, str] = {}
    masked_text = text

    def repl(match: re.Match[str]) -> str:
        original = match.group(0)
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
