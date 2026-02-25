from src.llm.pii import mask_pii, unmask_pii


def test_mask_pii_emails() -> None:
    text = "My email is test@example.com and secondary is foo.bar@domain.co.uk"
    masked, pii_map = mask_pii(text)

    assert "test@example.com" not in masked
    assert "foo.bar@domain.co.uk" not in masked
    assert "[PII-" in masked
    assert len(pii_map) == 2
    assert "test@example.com" in pii_map.values()


def test_mask_pii_phones() -> None:
    text = "Call me at +1 (555) 123-4567 or 8-800-555-35-35"
    masked, pii_map = mask_pii(text)

    assert "[PII-" in masked
    assert len(pii_map) == 2


def test_mask_pii_mixed() -> None:
    text = "Contact 88005553535 or admin@treejar.com"
    masked, pii_map = mask_pii(text)

    assert "[PII-" in masked
    assert "admin@treejar.com" in pii_map.values()


def test_unmask_pii() -> None:
    pii_map = {"<EMAIL_0>": "user@example.com", "<PHONE_0>": "12345"}
    masked_text = "I have sent the info to <EMAIL_0>. Call <PHONE_0>."

    result = unmask_pii(masked_text, pii_map)
    assert result == "I have sent the info to user@example.com. Call 12345."


def test_unmask_pii_missing_key() -> None:
    pii_map = {"<EMAIL_0>": "user@example.com"}
    masked_text = "Info sent to <EMAIL_0> and <PHONE_0>."

    # Should leave unknown tokens as is without crashing
    result = unmask_pii(masked_text, pii_map)
    assert result == "Info sent to user@example.com and <PHONE_0>."
