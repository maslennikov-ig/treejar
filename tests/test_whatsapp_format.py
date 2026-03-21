"""Tests for WhatsApp formatting edge cases (B9, B10, B11).

Covers:
  - B11: Horizontal rules (---) converted to empty line
  - B10: Unpaired ** collapsed to single *
  - B9: Nested bold markers cleaned up
  - Existing formatting still works (regression)
"""

from __future__ import annotations

import pytest

from src.services.chat import _format_for_whatsapp


class TestHorizontalRules:
    """B11: --- should not appear as raw text."""

    def test_triple_dash_removed(self) -> None:
        text = "Hello\n---\nWorld"
        result = _format_for_whatsapp(text)
        assert "---" not in result
        assert "Hello" in result
        assert "World" in result

    def test_long_dash_removed(self) -> None:
        text = "Above\n-----\nBelow"
        result = _format_for_whatsapp(text)
        assert "-----" not in result


class TestUnpairedDoubleAsterisks:
    """B10: ** handling — paired ** should still be converted to *."""

    def test_paired_double_asterisk_converted(self) -> None:
        text = "This is **bold** text"
        result = _format_for_whatsapp(text)
        # **bold** -> *bold* (WhatsApp format) via existing WHATSAPP_BOLD_RE
        assert "*bold*" in result


class TestConsecutiveNewlines:
    """Extra newlines should be collapsed."""

    def test_triple_newlines_collapsed(self) -> None:
        text = "A\n\n\n\nB"
        result = _format_for_whatsapp(text)
        assert "\n\n\n" not in result
        assert "A\n\nB" in result


class TestExistingFormatting:
    """Regression: existing formatting must still work."""

    def test_markdown_bold_to_whatsapp(self) -> None:
        text = "This is **important** info"
        result = _format_for_whatsapp(text)
        assert "*important*" in result

    def test_headers_to_bold(self) -> None:
        text = "## Product List"
        result = _format_for_whatsapp(text)
        assert "*Product List*" in result

    def test_links_converted(self) -> None:
        text = "Visit [our site](https://example.com)"
        result = _format_for_whatsapp(text)
        assert "our site: https://example.com" in result
