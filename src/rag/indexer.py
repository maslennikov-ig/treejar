from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_upsert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge_base import KnowledgeBase
from src.rag.embeddings import EmbeddingEngine

logger = logging.getLogger(__name__)


async def index_documents(db: AsyncSession) -> int:
    """Parse markdown files from docs/ and index them into knowledge_base.

    Returns:
        The number of new/updated chunks indexed.
    """
    engine = EmbeddingEngine()

    docs_dir = Path("docs")
    if not docs_dir.exists():
        logger.warning("Docs directory %s does not exist.", docs_dir.absolute())
        return 0

    chunks_to_index = []

    # 1. Parse FAQ
    faq_path = docs_dir / "faq.md"
    if faq_path.exists():
        chunks_to_index.extend(_parse_faq(faq_path))

    # 2. Parse Sales Rules
    rules_path = docs_dir / "04-sales-dialogue-guidelines.md"
    if rules_path.exists():
        chunks_to_index.extend(_parse_sales_rules(rules_path))

    # 3. Parse Company Values
    values_path = docs_dir / "05-company-values.md"
    if values_path.exists():
        chunks_to_index.extend(_parse_company_values(values_path))

    if not chunks_to_index:
        logger.info("No documents found or successfully parsed to index.")
        return 0

    logger.info("Parsed %d document chunks. Indexing...", len(chunks_to_index))

    # Generate embeddings and prepare inserts
    values = []

    # Batch generate embeddings to prevent memory explosion
    # Though there's only a few dozen here, good practice.
    batch_size = 32
    for i in range(0, len(chunks_to_index), batch_size):
        batch = chunks_to_index[i : i + batch_size]
        texts = [c["content"] for c in batch]

        embeddings = await engine.embed_batch_async(texts)

        for chunk, embedding in zip(batch, embeddings, strict=False):
            chunk["embedding"] = embedding
            values.append(chunk)

    # Upsert into PostgreSQL
    try:
        stmt = pg_upsert(KnowledgeBase).values(values)

        stmt = stmt.on_conflict_do_update(
            # We assume a chunk is unique by its source + title
            index_elements=["source", "title"],
            set_={
                "content": stmt.excluded.content,
                "embedding": stmt.excluded.embedding,
                "category": stmt.excluded.category,
                "language": stmt.excluded.language,
            }
        )

        await db.execute(stmt)
        await db.commit()

        return len(values)

    except Exception as e:
        await db.rollback()
        logger.error("Error indexing knowledge base: %s", e)
        return 0


def _parse_faq(path: Path) -> list[dict[str, Any]]:
    """Parse FAQ markdown file into chunks."""
    content = path.read_text(encoding="utf-8")

    chunks = []
    # Split by '## ' headers which denote individual Q&A
    parts = content.split("\n## ")

    for i, part in enumerate(parts):
        # The first part is usually the title/intro
        if i == 0 or not part.strip():
            continue

        lines = part.split("\n", 1)
        if len(lines) < 2:
            continue

        title = lines[0].strip()
        body = lines[1].strip()

        chunks.append({
            "source": "faq",
            "category": "faq",
            "title": title,
            "content": f"Q: {title}\nA: {body}",
            "language": "en", # Mostly English with some context
        })

    return chunks


def _parse_sales_rules(path: Path) -> list[dict[str, Any]]:
    """Parse Sales Dialogue Guidelines Markdown table into chunks."""
    content = path.read_text(encoding="utf-8")
    chunks = []

    lines = content.split("\n")
    # Finding the table rows
    for line in lines:
        if line.startswith("|") and not line.startswith("| -"):
            cols = [c.strip() for c in line.split("|")[1:-1]]
            # We skip the header row
            if len(cols) >= 5 and cols[0].isdigit():
                rule_number = cols[0]
                rule_ru = cols[1]
                expl_ru = cols[2]
                rule_en = cols[3]
                expl_en = cols[4]

                # We save bilingual content
                combined = (
                    f"Rule: {rule_en}\nExplanation: {expl_en}\n\n"
                    f"Правило: {rule_ru}\nОбъяснение: {expl_ru}"
                )

                chunks.append({
                    "source": "rules",
                    "category": "sales_rules",
                    "title": f"Rule {rule_number}: {rule_en}",
                    "content": combined,
                    "language": "bilingual",
                })

    # Also grab bullet points at the bottom
    extra_rules = []
    for line in lines:
        if line.startswith("Добавить правило") or line.startswith("Делать фоллоу ап") or line.startswith("Наша задача"):
            extra_rules.append(line.strip())

    if extra_rules:
        chunks.append({
            "source": "rules",
            "category": "sales_rules",
            "title": "Additional Rules",
            "content": "\n".join(extra_rules),
            "language": "ru",
        })

    return chunks


def _parse_company_values(path: Path) -> list[dict[str, Any]]:
    """Parse Company Values Markdown into chunks."""
    content = path.read_text(encoding="utf-8")
    chunks = []

    # Split by the list item numbers (e.g., 1️⃣, 2️⃣) or standard formatting
    lines = content.split("\n")
    current_title = None
    current_body: list[str] = []
    language = "ru"

    for line in lines:
        # Detect if we switched to EN section
        if "Treejar Values (EN" in line:
            language = "en"

        # Matches emoji numbers or standard *11)
        if "️⃣" in line or line.strip().startswith("*1") or line.strip().startswith("*2"):
            # Save previous chunk
            if current_title:
                title_clean = current_title.split("**")[-2] if "**" in current_title else current_title
                chunks.append({
                    "source": "values",
                    "category": "company_values",
                    "title": title_clean.strip(" *1234567890)"),
                    "content": "\n".join(current_body).strip(" *"),
                    "language": language,
                })

            current_title = line.strip()
            current_body = []
        elif current_title and line.strip() and not line.startswith("---") and "Хочешь, чтобы" not in line:
            current_body.append(line.strip())

    # Save the last one
    if current_title:
        title_clean = current_title.split("**")[-2] if "**" in current_title else current_title
        chunks.append({
            "source": "values",
            "category": "company_values",
            "title": title_clean.strip(" *1234567890)"),
            "content": "\n".join(current_body).strip(" *"),
            "language": language,
        })

    return chunks
