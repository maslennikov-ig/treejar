"""Made-to-order / zero-stock catalog fallback for runtime product search.

Lives outside ``src/rag/pipeline.py`` and ``src/schemas/product.py`` (just like
``src/rag/cached_embedding.py``) so ``PINNED_RETRIEVAL_CONTRACT_SHA`` in
``scripts/corpus_bridge/semantic_catalog_evidence.py`` remains byte-for-byte
intact without stranding frozen corpus-bridge artifacts.

Treejar's entire ``Sofas`` category (28 ``SOFA-*`` models priced 875-2750 AED)
and ``Custom Furniture`` rows (``EXE-*``, ``MTD-*``, ``CAB-*``, ``REP-*``) carry
``stock = 0`` in local ``products``. When the primary ``in_stock_only=True``
search misses the requested product or sofa family, this helper reuses the
cached query embedding to inspect ``Product.stock <= 0`` catalog items.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.llm.catalog_planning import (
    CatalogConcept,
    count_concept_matches,
    product_matches_concept,
)
from src.llm.verified_answers import classify_product_match, query_names_specific_item
from src.models.product import Product
from src.rag.cached_embedding import wrap_embedding_engine
from src.rag.embeddings import EmbeddingEngine
from src.rag.pipeline import search_products as rag_pipeline_search_products
from src.schemas.product import ProductRead, ProductSearchQuery, ProductSearchResult

_SOFA_REQUEST_RE = re.compile(
    r"\b(?:sofas?|couch(?:es)?|settees?|loveseats?|poufs?|ottomans?)\b"
    r"|(?:كنب|كنبة|أريكة|اريكة|صوفا)",
    re.IGNORECASE,
)
_CUSTOM_CATALOG_REQUEST_RE = re.compile(
    r"\b(?:custom(?:i[sz]ed)?|made[\s-]to[\s-](?:order|measure)|bespoke|"
    r"exe-[a-z]|mtd-[a-z]|cab-[a-z]|rep-[a-z])\b"
    r"|(?:تفصيل|حسب\s+الطلب|مقاس(?:ات)?\s+خاص)",
    re.IGNORECASE,
)
_PRODUCT_MATCH_RANK: dict[str, int] = {
    "missing": 0,
    "nearby": 1,
    "generic": 2,
    "exact": 3,
}


def _product_candidate_text(product: ProductRead) -> str:
    return (
        f"{product.name_en}\n{product.description_en or ''}\n{product.category or ''}"
    )


def _is_sofa_catalog_product(product: ProductRead) -> bool:
    if (product.category or "").strip().casefold() == "sofas":
        return True
    return bool(
        re.search(r"\bsofas?\b", f"{product.name_en} {product.sku}", re.IGNORECASE)
    )


async def apply_made_to_order_catalog_fallback(
    db: AsyncSession,
    query: ProductSearchQuery,
    embedding_engine: EmbeddingEngine,
    *,
    primary_result: ProductSearchResult,
) -> ProductSearchResult:
    """Inspect ``Product.stock <= 0`` when ``primary_result`` missed the target."""
    if not query.in_stock_only:
        return primary_result

    product_responses = list(primary_result.products)
    primary_match = classify_product_match(
        query.query,
        [_product_candidate_text(p) for p in product_responses],
        candidate_skus=[p.sku for p in product_responses],
    )
    primary_rank = _PRODUCT_MATCH_RANK[primary_match]
    sofa_requested = bool(_SOFA_REQUEST_RE.search(query.query))
    primary_has_sofa = any(_is_sofa_catalog_product(p) for p in product_responses)
    custom_requested = bool(_CUSTOM_CATALOG_REQUEST_RE.search(query.query))

    should_check_fallback = (not product_responses) or (
        primary_rank <= _PRODUCT_MATCH_RANK["nearby"]
        and (
            primary_match == "missing"
            or (sofa_requested and not primary_has_sofa)
            or custom_requested
            or query_names_specific_item(query.query)
        )
    )
    if not should_check_fallback:
        return primary_result

    query_vector = await embedding_engine.embed_async(query.query)
    fallback_stmt = select(Product).where(
        Product.is_active.is_(True),
        Product.embedding.is_not(None),
        Product.stock <= 0,
    )
    if query.category:
        fallback_stmt = fallback_stmt.where(Product.category == query.category)
    if query.min_price is not None:
        fallback_stmt = fallback_stmt.where(Product.price >= query.min_price)
    elif not custom_requested:
        # Exclude unpriced (0 AED) Custom Furniture placeholders unless
        # the query explicitly asks for custom/made-to-order or names them.
        fallback_stmt = fallback_stmt.where(Product.price > 0)
    if query.max_price is not None:
        fallback_stmt = fallback_stmt.where(Product.price <= query.max_price)
    fallback_stmt = fallback_stmt.order_by(
        Product.embedding.cosine_distance(query_vector)
    ).limit(query.limit)

    fallback_exec = await db.execute(fallback_stmt)
    fallback_products = fallback_exec.scalars().all()
    if not fallback_products:
        return primary_result

    fallback_responses = [ProductRead.model_validate(p) for p in fallback_products]
    fallback_match = classify_product_match(
        query.query,
        [_product_candidate_text(p) for p in fallback_responses],
        candidate_skus=[p.sku for p in fallback_responses],
    )
    fallback_rank = _PRODUCT_MATCH_RANK[fallback_match]
    fallback_has_sofa = any(_is_sofa_catalog_product(p) for p in fallback_responses)

    if (
        fallback_rank > primary_rank
        or (sofa_requested and fallback_has_sofa and not primary_has_sofa)
        or (
            not product_responses
            and (fallback_rank > 0 or query.category is not None or custom_requested)
        )
    ):
        return ProductSearchResult(
            products=fallback_responses,
            query_interpreted=primary_result.query_interpreted,
            total_found=len(fallback_responses),
        )
    return primary_result


async def augment_results_with_concept_candidates(
    db: AsyncSession,
    query: ProductSearchQuery,
    *,
    concepts: Sequence[CatalogConcept],
    existing_result: ProductSearchResult,
    min_results: int,
) -> ProductSearchResult:
    """Supplement vector results via SQL lexical/attribute lookup when concepts miss."""
    if not concepts:
        return existing_result
    matched_count = count_concept_matches(
        existing_result.products,
        concepts,
        name_of=lambda product: str(product.name_en),
        description_of=lambda product: product.description_en,
        category_of=lambda product: product.category,
        subcategory_of=lambda product: product.subcategory,
        attributes_of=lambda product: product.attributes,
    )
    if matched_count >= min_results:
        return existing_result

    sql_terms = tuple(
        dict.fromkeys(term for concept in concepts for term in concept.sql_terms)
    )
    if not sql_terms:
        return existing_result

    term_clauses = [
        clause
        for term in sql_terms
        for pattern in (f"%{term}%",)
        for clause in (
            Product.name_en.ilike(pattern),
            Product.category.ilike(pattern),
            Product.subcategory.ilike(pattern),
            Product.description_en.ilike(pattern),
            cast(Product.attributes, Text).ilike(pattern),
        )
    ]
    stmt = select(Product).where(
        Product.is_active.is_(True),
        or_(*term_clauses),
    )
    if query.category:
        stmt = stmt.where(Product.category == query.category)
    if query.min_price is not None:
        stmt = stmt.where(Product.price >= query.min_price)
    else:
        stmt = stmt.where(Product.price > 0)
    if query.max_price is not None:
        stmt = stmt.where(Product.price <= query.max_price)
    stmt = stmt.order_by(
        (Product.stock > 0).desc(),
        Product.stock.desc(),
        Product.price.asc(),
    ).limit(max(min_results * 5, 20))

    exec_res = await db.execute(stmt)
    raw_rows = list(exec_res.scalars().all())
    if not raw_rows:
        return existing_result

    merged = list(existing_result.products)
    seen_skus = {str(p.sku).strip().casefold() for p in merged}
    for row in raw_rows:
        candidate = ProductRead.model_validate(row)
        sku_key = str(candidate.sku).strip().casefold()
        if sku_key in seen_skus:
            continue
        if not any(
            product_matches_concept(
                concept,
                name=str(candidate.name_en),
                description=candidate.description_en,
                category=candidate.category,
                subcategory=candidate.subcategory,
                attributes=candidate.attributes,
            )
            for concept in concepts
        ):
            continue
        seen_skus.add(sku_key)
        merged.append(candidate)

    if len(merged) == len(existing_result.products):
        return existing_result
    return ProductSearchResult(
        products=merged,
        query_interpreted=existing_result.query_interpreted,
        total_found=len(merged),
    )


async def search_products_with_made_to_order_fallback(
    db: AsyncSession,
    query: ProductSearchQuery,
    embedding_engine: EmbeddingEngine,
) -> ProductSearchResult:
    """Run ``rag.pipeline.search_products`` with cached zero-stock fallback."""
    cached_engine = wrap_embedding_engine(embedding_engine)
    primary = await rag_pipeline_search_products(
        db=db, query=query, embedding_engine=cached_engine
    )
    return await apply_made_to_order_catalog_fallback(
        db=db,
        query=query,
        embedding_engine=cached_engine,
        primary_result=primary,
    )
