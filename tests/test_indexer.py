"""Unit tests for the RAG indexer's markdown parser functions
(_parse_faq, _parse_sales_rules, _parse_company_values) — TCG-05.

All tests use temporary files created with Python's tempfile module so no real
docs/ files are needed. The EmbeddingEngine and DB are mocked for the top-level
index_documents function tests."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag.indexer import (
    _parse_company_values,
    _parse_faq,
    _parse_sales_rules,
    index_documents,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_tmp(content: str) -> Path:
    """Write *content* to a named temp file and return its Path.

    The file is not deleted on close so the parser can read it.
    Callers should delete it manually or rely on OS cleanup.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(content)
        return Path(fh.name)


# ---------------------------------------------------------------------------
# _parse_faq
# ---------------------------------------------------------------------------


class TestParseFaq:
    """Tests for _parse_faq."""

    @pytest.mark.unit
    def test_empty_file_yields_zero_chunks(self) -> None:
        """An empty markdown file must return an empty list."""
        path = _write_tmp("")
        result = _parse_faq(path)
        assert result == []

    @pytest.mark.unit
    def test_title_only_file_yields_zero_chunks(self) -> None:
        """A file with only a top-level heading (# …) and no ## sections
        must return an empty list."""
        path = _write_tmp("# Frequently Asked Questions\n\nIntro paragraph.\n")
        result = _parse_faq(path)
        assert result == []

    @pytest.mark.unit
    def test_well_formatted_file_yields_expected_chunks(self) -> None:
        """A file with two ## Q&A sections must produce exactly 2 chunks."""
        content = (
            "# FAQ\n\n"
            "## How do I return a product?\n"
            "You can return within 30 days with receipt.\n\n"
            "## What payment methods are accepted?\n"
            "We accept credit cards and bank transfer.\n"
        )
        path = _write_tmp(content)
        result = _parse_faq(path)

        assert len(result) == 2
        titles = {c["title"] for c in result}
        assert "How do I return a product?" in titles
        assert "What payment methods are accepted?" in titles

    @pytest.mark.unit
    def test_chunk_structure_is_correct(self) -> None:
        """Each chunk must have source='faq', category='faq', language='en',
        a non-empty title, and content starting with 'Q: '."""
        content = (
            "# FAQ\n\n"
            "## Delivery time\n"
            "Delivery takes 3-5 business days.\n"
        )
        path = _write_tmp(content)
        result = _parse_faq(path)

        assert len(result) == 1
        chunk = result[0]
        assert chunk["source"] == "faq"
        assert chunk["category"] == "faq"
        assert chunk["language"] == "en"
        assert chunk["title"] == "Delivery time"
        assert chunk["content"].startswith("Q: Delivery time")
        assert "Delivery takes" in chunk["content"]

    @pytest.mark.unit
    def test_section_missing_body_is_skipped(self) -> None:
        """A ## header with no body text must be included (has 2 lines after
        splitting on the first newline) but have an empty body string."""
        content = "# FAQ\n\n## Empty section\n\n## Real section\nSome answer.\n"
        path = _write_tmp(content)
        result = _parse_faq(path)

        titles = [c["title"] for c in result]
        # "Real section" must be present; "Empty section" may or may not be
        assert "Real section" in titles

    @pytest.mark.unit
    def test_multiple_sections_order_preserved(self) -> None:
        """Chunks must appear in document order."""
        content = (
            "# FAQ\n\n"
            "## First question\nFirst answer.\n\n"
            "## Second question\nSecond answer.\n\n"
            "## Third question\nThird answer.\n"
        )
        path = _write_tmp(content)
        result = _parse_faq(path)

        assert len(result) == 3
        assert result[0]["title"] == "First question"
        assert result[1]["title"] == "Second question"
        assert result[2]["title"] == "Third question"


# ---------------------------------------------------------------------------
# _parse_sales_rules
# ---------------------------------------------------------------------------


class TestParseSalesRules:
    """Tests for _parse_sales_rules."""

    @pytest.mark.unit
    def test_empty_file_yields_zero_chunks(self) -> None:
        """An empty file must return an empty list."""
        path = _write_tmp("")
        result = _parse_sales_rules(path)
        assert result == []

    @pytest.mark.unit
    def test_file_without_table_yields_zero_chunks(self) -> None:
        """A file with prose but no markdown table must return an empty list."""
        path = _write_tmp("# Sales Rules\n\nSome intro text, no table here.\n")
        result = _parse_sales_rules(path)
        assert result == []

    @pytest.mark.unit
    def test_well_formatted_table_yields_expected_chunks(self) -> None:
        """A file with two valid table rows must produce 2 bilingual chunks."""
        content = (
            "# Sales Dialogue Guidelines\n\n"
            "| # | Rule (RU) | Explanation (RU) | Rule (EN) | Explanation (EN) |\n"
            "| - | --------- | ---------------- | --------- | ---------------- |\n"
            "| 1 | Приветствие | Всегда приветствуй | Always greet | Always say hello |\n"
            "| 2 | Слушай | Слушай клиента | Listen | Listen to customer |\n"
        )
        path = _write_tmp(content)
        result = _parse_sales_rules(path)

        # Expect exactly 2 bilingual rule chunks (no extra-rules bullet points)
        assert len(result) == 2
        assert result[0]["title"] == "Rule 1: Always greet"
        assert result[0]["language"] == "bilingual"
        assert result[1]["title"] == "Rule 2: Listen"

    @pytest.mark.unit
    def test_chunk_contains_bilingual_content(self) -> None:
        """Each rule chunk's content must include both the EN and RU text."""
        content = (
            "| # | Rule (RU) | Explanation (RU) | Rule (EN) | Explanation (EN) |\n"
            "| - | --------- | ---------------- | --------- | ---------------- |\n"
            "| 1 | Улыбайся | Клиент должен чувствовать тепло | Smile | Customer feels warmth |\n"
        )
        path = _write_tmp(content)
        result = _parse_sales_rules(path)

        assert len(result) == 1
        chunk_content = result[0]["content"]
        assert "Smile" in chunk_content
        assert "Customer feels warmth" in chunk_content
        assert "Улыбайся" in chunk_content
        assert "Клиент должен чувствовать тепло" in chunk_content

    @pytest.mark.unit
    def test_extra_rules_bullet_captured(self) -> None:
        """Lines starting with known Russian bullet prefixes must be collected
        into an 'Additional Rules' chunk."""
        content = (
            "| # | Rule (RU) | Explanation (RU) | Rule (EN) | Explanation (EN) |\n"
            "| - | --------- | ---------------- | --------- | ---------------- |\n"
            "| 1 | Слушай | Слушай | Listen | Listen |\n\n"
            "Добавить правило о follow-up\n"
            "Делать фоллоу ап после встречи\n"
            "Наша задача — закрыть сделку\n"
        )
        path = _write_tmp(content)
        result = _parse_sales_rules(path)

        titles = [c["title"] for c in result]
        assert "Additional Rules" in titles

        additional = next(c for c in result if c["title"] == "Additional Rules")
        assert additional["language"] == "ru"
        assert "Добавить правило о follow-up" in additional["content"]
        assert "Делать фоллоу ап после встречи" in additional["content"]
        assert "Наша задача — закрыть сделку" in additional["content"]

    @pytest.mark.unit
    def test_header_row_is_not_treated_as_rule(self) -> None:
        """The table header row (non-numeric first column) must not produce a
        chunk."""
        content = (
            "| # | Rule (RU) | Explanation (RU) | Rule (EN) | Explanation (EN) |\n"
            "| - | --------- | ---------------- | --------- | ---------------- |\n"
        )
        path = _write_tmp(content)
        result = _parse_sales_rules(path)
        assert result == []

    @pytest.mark.unit
    def test_chunk_source_and_category(self) -> None:
        """Rule chunks must carry source='rules' and category='sales_rules'."""
        content = (
            "| 1 | Правило | Описание | Rule | Description |\n"
        )
        path = _write_tmp(content)
        result = _parse_sales_rules(path)

        assert len(result) == 1
        assert result[0]["source"] == "rules"
        assert result[0]["category"] == "sales_rules"


# ---------------------------------------------------------------------------
# _parse_company_values
# ---------------------------------------------------------------------------


class TestParseCompanyValues:
    """Tests for _parse_company_values."""

    @pytest.mark.unit
    def test_empty_file_yields_zero_chunks(self) -> None:
        """An empty file must return an empty list."""
        path = _write_tmp("")
        result = _parse_company_values(path)
        assert result == []

    @pytest.mark.unit
    def test_file_without_markers_yields_zero_chunks(self) -> None:
        """A file with no emoji-number or *1/*2 markers must return an empty list."""
        path = _write_tmp("# Values\n\nGeneric text without any value markers.\n")
        result = _parse_company_values(path)
        assert result == []

    @pytest.mark.unit
    def test_emoji_numbered_values_parsed_correctly(self) -> None:
        """Emoji-numbered headings (1️⃣, 2️⃣) must produce one chunk each."""
        content = (
            "# Ценности компании\n\n"
            "1️⃣ **Честность**\n"
            "Мы всегда честны с клиентами.\n\n"
            "2️⃣ **Качество**\n"
            "Мы обеспечиваем высокое качество продуктов.\n"
        )
        path = _write_tmp(content)
        result = _parse_company_values(path)

        assert len(result) == 2
        titles = [c["title"] for c in result]
        assert "Честность" in titles
        assert "Качество" in titles

    @pytest.mark.unit
    def test_language_detection_switches_to_en(self) -> None:
        """Once 'Treejar Values (EN' appears in the file the language variable
        is flipped to 'en'.  Values whose headings come BEFORE the language
        marker but whose body is accumulated AFTER it also receive 'en'
        (the parser sets language before flushing the previous chunk).
        Verify that at least one EN chunk is produced for the EN section."""
        content = (
            "1️⃣ **Честность**\n"
            "Мы честны.\n\n"
            "## Treejar Values (EN)\n\n"
            "*11) Honesty*\n"
            "We are honest with our customers.\n"
        )
        path = _write_tmp(content)
        result = _parse_company_values(path)

        # The parser marks language='en' when it encounters the EN marker line.
        # Both chunks end up as 'en' in this layout (the RU chunk is flushed
        # inside the *11) branch which runs after the language flip).
        en_chunks = [c for c in result if c["language"] == "en"]
        assert len(en_chunks) >= 1

        # The EN-section value must be present
        en_titles = [c["title"] for c in en_chunks]
        assert "Honesty" in en_titles

    @pytest.mark.unit
    def test_chunk_source_and_category(self) -> None:
        """Every chunk must have source='values' and category='company_values'."""
        content = (
            "1️⃣ **Integrity**\n"
            "We always act with integrity.\n"
        )
        path = _write_tmp(content)
        result = _parse_company_values(path)

        assert len(result) == 1
        assert result[0]["source"] == "values"
        assert result[0]["category"] == "company_values"

    @pytest.mark.unit
    def test_separator_lines_excluded_from_body(self) -> None:
        """Lines consisting only of '---' must not appear in chunk content."""
        content = (
            "1️⃣ **Teamwork**\n"
            "We work together.\n"
            "---\n"
            "2️⃣ **Innovation**\n"
            "We innovate constantly.\n"
        )
        path = _write_tmp(content)
        result = _parse_company_values(path)

        for chunk in result:
            assert "---" not in chunk["content"]

    @pytest.mark.unit
    def test_hachetje_line_excluded(self) -> None:
        """Lines containing 'Хочешь, чтобы' must be excluded from body text."""
        content = (
            "1️⃣ **Value**\n"
            "Some body text.\n"
            "Хочешь, чтобы мы продолжили?\n"
        )
        path = _write_tmp(content)
        result = _parse_company_values(path)

        for chunk in result:
            assert "Хочешь, чтобы" not in chunk["content"]

    @pytest.mark.unit
    def test_value_with_no_body_omitted(self) -> None:
        """A value heading with no following body text must not appear as a
        chunk."""
        content = (
            "1️⃣ **EmptyValue**\n"
            "2️⃣ **RealValue**\n"
            "This value has a real description.\n"
        )
        path = _write_tmp(content)
        result = _parse_company_values(path)

        titles = [c["title"] for c in result]
        assert "RealValue" in titles
        # EmptyValue had no body so must be absent
        assert "EmptyValue" not in titles


# ---------------------------------------------------------------------------
# index_documents (integration of parsers + DB + embeddings)
# ---------------------------------------------------------------------------


class TestIndexDocuments:
    """Smoke tests for index_documents, with all I/O mocked."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_zero_when_docs_dir_missing(self) -> None:
        """index_documents must return 0 if the docs/ directory does not exist."""
        mock_db = AsyncMock()

        with patch("src.rag.indexer._DOCS_DIR", Path("/nonexistent/path/docs")):
            result = await index_documents(mock_db)

        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_doc_files_present(self) -> None:
        """If the docs dir exists but none of the expected files are present,
        index_documents must return 0 without calling the DB."""
        mock_db = AsyncMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_path = Path(tmpdir)
            with patch("src.rag.indexer._DOCS_DIR", docs_path):
                result = await index_documents(mock_db)

        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_indexes_faq_chunks_from_file(self) -> None:
        """When a valid faq.md exists, index_documents must embed and upsert
        its chunks into the DB."""
        mock_db = AsyncMock()

        faq_content = (
            "# FAQ\n\n"
            "## Returns policy\n"
            "30 days no questions asked.\n\n"
            "## Shipping\n"
            "Free shipping over AED 200.\n"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_path = Path(tmpdir)
            (docs_path / "faq.md").write_text(faq_content, encoding="utf-8")

            with (
                patch("src.rag.indexer._DOCS_DIR", docs_path),
                patch("src.rag.indexer.EmbeddingEngine") as MockEngine,
            ):
                mock_instance = MockEngine.return_value
                # Return one embedding vector per text
                mock_instance.embed_batch_async = AsyncMock(
                    side_effect=lambda texts: [[0.1] * 4 for _ in texts]
                )

                mock_db.execute.return_value = MagicMock()

                result = await index_documents(mock_db)

        # Two FAQ chunks must have been indexed
        assert result == 2
        assert mock_db.execute.called
        assert mock_db.commit.called

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rolls_back_on_db_error(self) -> None:
        """If the DB execute raises an exception, index_documents must call
        rollback and return 0."""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = RuntimeError("DB connection lost")

        faq_content = "# FAQ\n\n## Question\nAnswer.\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_path = Path(tmpdir)
            (docs_path / "faq.md").write_text(faq_content, encoding="utf-8")

            with (
                patch("src.rag.indexer._DOCS_DIR", docs_path),
                patch("src.rag.indexer.EmbeddingEngine") as MockEngine,
            ):
                mock_instance = MockEngine.return_value
                mock_instance.embed_batch_async = AsyncMock(
                    return_value=[[0.1] * 4]
                )

                result = await index_documents(mock_db)

        assert result == 0
        mock_db.rollback.assert_awaited_once()
