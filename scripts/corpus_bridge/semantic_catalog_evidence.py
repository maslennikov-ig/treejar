"""Build and validate protected semantic catalog evidence for measured rounds."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import pathlib
import re
import statistics
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sentence_transformers import SentenceTransformer
from sqlalchemy import Table, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings
from src.integrations.catalog.treejar_catalog import TreejarCatalogClient
from src.integrations.inventory.sync import _normalize_treejar_product
from src.models.product import Product
from src.rag import pipeline as rag_pipeline
from src.schemas.product import ProductSearchQuery

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EVIDENCE_SCHEMA = "treejar-semantic-catalog-evidence/v1"
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIMENSIONS = 1024
RETRIEVAL_ENTRYPOINT = "src.rag.pipeline.search_products"
RETRIEVAL_LIMIT = 3
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_REVISION_PATTERN = r"^[0-9a-f]{40}$"

# The identity of the evidence a measured round is allowed to consume. These
# were command-line arguments, which made the pin only as strong as what the
# operator typed: an artifact built on a stale catalog passed every check by
# being described accurately. The repository is the record now, so replacing
# the authoritative catalog, qrels or model is a reviewed commit rather than a
# different flag. `tj-rcg5` produced these on 2026-08-13; the digests are the
# ones recorded in the bead and in `.codex/handoff.md`.
PINNED_CATALOG_SHA256 = (
    "979e791b1d5c52e53976ec455fb301aab59e1e4848601d1a7939d4efe18df2d7"
)
PINNED_EMBEDDING_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
PINNED_PGVECTOR_EXTENSION = "0.8.5"
PINNED_QRELS_SHA256: dict[str, str] = {
    "openings-20": ("cddfb117c4d304ba26ac7f8e1a50e298280c4c209dbea89f1bdacc7cbd16a79b"),
    "retrieval-golden": (
        "cb3cf2991c98b8d525f4dfec695e092c2be4ecd2d996e6399c23b5a866208055"
    ),
}


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CatalogIdentity(_StrictModel):
    sha256: str = Field(pattern=_SHA256_PATTERN)
    rows: int = Field(gt=0)


class EmbeddingIdentity(_StrictModel):
    model: str
    revision: str = Field(pattern=_REVISION_PATTERN)
    dimensions: int
    normalized: bool


class RetrievalIdentity(_StrictModel):
    entrypoint: str
    code_sha: str = Field(pattern=_SHA256_PATTERN)
    pgvector_python: str
    pgvector_extension: str
    distance: str
    search_mode: str
    ann_indexes: tuple[str, ...]
    limit: int = Field(gt=0)
    query_source: str


class QrelsIdentity(_StrictModel):
    sha256: str = Field(pattern=_SHA256_PATTERN)


class QuerySetIdentity(_StrictModel):
    sha256: str = Field(pattern=_SHA256_PATTERN)
    count: int = Field(gt=0)


class EvidenceProduct(_StrictModel):
    id: str
    sku: str
    name: str
    category: str | None = None
    price_aed: float
    stock: int


class RetrievalResultEvidence(_StrictModel):
    dialog_id: int
    query_sha256: str = Field(pattern=_SHA256_PATTERN)
    rows_present: bool
    catalog_relevant: bool
    relevant_skus: tuple[str, ...]
    products: tuple[EvidenceProduct, ...]


class SemanticCatalogEvidence(_StrictModel):
    schema_version: str
    catalog: CatalogIdentity
    embedding: EmbeddingIdentity
    retrieval: RetrievalIdentity
    qrels: QrelsIdentity
    query_set: QuerySetIdentity
    results: tuple[RetrievalResultEvidence, ...]


class RetrievalQrel(_StrictModel):
    dialog_id: int
    relevant_skus: tuple[str, ...]
    forbidden_skus: tuple[str, ...]
    require_relevant_result: bool
    exact_sku: str | None


class RetrievalQrels(_StrictModel):
    schema_version: str
    entries: tuple[RetrievalQrel, ...]


class CatalogSnapshotProduct(_StrictModel):
    id: uuid.UUID
    sku: str = Field(min_length=1)
    name_en: str = Field(min_length=1)
    name_ar: str | None
    description_en: str | None
    description_ar: str | None
    category: str | None
    subcategory: str | None
    price: float = Field(ge=0)
    currency: str = Field(min_length=1)
    stock: int = Field(ge=0)
    is_active: bool


class CatalogSnapshot(_StrictModel):
    schema_version: str
    source: str = Field(min_length=1)
    captured_at: str | None = None
    products: tuple[CatalogSnapshotProduct, ...]


class PinnedEmbeddingEngine:
    """The production embedding behavior with an immutable offline revision."""

    def __init__(self, *, model: str, revision: str) -> None:
        if model != EMBEDDING_MODEL:
            raise ValueError(f"embedding model must be {EMBEDDING_MODEL}")
        if not re.fullmatch(_REVISION_PATTERN, revision):
            raise ValueError("embedding revision must be a full 40-character hash")
        self.model_name = model
        self.revision = revision
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(
                self.model_name,
                revision=self.revision,
                local_files_only=True,
                trust_remote_code=False,
            )
        return self._model

    def embed(self, value: str) -> list[float]:
        embedding = self._get_model().encode(value, normalize_embeddings=True)
        values = embedding.tolist()
        if len(values) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"embedding dimension {len(values)} != {EMBEDDING_DIMENSIONS}"
            )
        return values

    def embed_batch(self, values: list[str]) -> list[list[float]]:
        embeddings = self._get_model().encode(values, normalize_embeddings=True)
        rows = [embedding.tolist() for embedding in embeddings]
        if any(len(row) != EMBEDDING_DIMENSIONS for row in rows):
            raise ValueError(f"embedding dimension must be {EMBEDDING_DIMENSIONS}")
        return rows

    async def embed_async(self, value: str) -> list[float]:
        import asyncio

        return await asyncio.to_thread(self.embed, value)

    async def embed_batch_async(self, values: list[str]) -> list[list[float]]:
        import asyncio

        return await asyncio.to_thread(self.embed_batch, values)


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _query_sha256(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def evaluate_retrieval(
    results: tuple[RetrievalResultEvidence, ...],
    qrels_document: dict[str, Any],
    *,
    top_k: int,
) -> dict[str, Any]:
    """Report retrieval metrics without letting means hide hard failures."""
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    try:
        qrels = RetrievalQrels.model_validate(qrels_document)
    except ValidationError as exc:
        raise ValueError(f"retrieval qrels are invalid: {exc}") from exc
    if qrels.schema_version != "treejar-semantic-retrieval-qrels/v1":
        raise ValueError("retrieval qrels schema version mismatch")
    if [entry.dialog_id for entry in qrels.entries] != [
        result.dialog_id for result in results
    ]:
        raise ValueError("retrieval qrels must match result dialog order exactly")

    per_query: list[dict[str, Any]] = []
    hard_failures: list[str] = []
    for result, qrel in zip(results, qrels.entries, strict=True):
        retrieved = [product.sku for product in result.products[:top_k]]
        relevant = set(qrel.relevant_skus)
        forbidden = sorted(set(retrieved).intersection(qrel.forbidden_skus))
        relevant_hits = [sku for sku in retrieved if sku in relevant]
        precision = len(relevant_hits) / top_k
        recall = len(set(relevant_hits)) / len(relevant) if relevant else 0.0
        dcg = sum(
            1.0 / math.log2(rank + 1)
            for rank, sku in enumerate(retrieved, start=1)
            if sku in relevant
        )
        ideal_hits = min(len(relevant), top_k)
        idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
        ndcg = dcg / idcg if idcg else 0.0

        if forbidden:
            hard_failures.append(
                f"dialog {result.dialog_id}: forbidden SKU(s) in top-{top_k}: "
                + ", ".join(forbidden)
            )
        if qrel.require_relevant_result and not relevant_hits:
            hard_failures.append(
                f"dialog {result.dialog_id}: no relevant SKU in top-{top_k}"
            )
        if qrel.exact_sku and (not retrieved or retrieved[0] != qrel.exact_sku):
            hard_failures.append(
                f"dialog {result.dialog_id}: exact SKU {qrel.exact_sku} is not rank 1"
            )
        judged_relevant = bool(relevant_hits)
        if result.catalog_relevant != judged_relevant:
            hard_failures.append(
                f"dialog {result.dialog_id}: catalog_relevant does not match qrels"
            )
        if result.relevant_skus != tuple(relevant_hits):
            hard_failures.append(
                f"dialog {result.dialog_id}: relevant_skus do not match qrels/top-k"
            )

        per_query.append(
            {
                "dialog_id": result.dialog_id,
                "precision_at_3": precision,
                "recall_at_3": recall,
                "ndcg_at_3": ndcg,
                "relevant_skus": sorted(set(relevant_hits)),
                "forbidden_skus": forbidden,
            }
        )

    aggregate = {
        "queries": len(per_query),
        "precision_at_3": statistics.fmean(row["precision_at_3"] for row in per_query),
        "recall_at_3": statistics.fmean(row["recall_at_3"] for row in per_query),
        "ndcg_at_3": statistics.fmean(row["ndcg_at_3"] for row in per_query),
    }
    return {
        "aggregate": aggregate,
        "per_query": per_query,
        "hard_failures": hard_failures,
        "passed": not hard_failures,
    }


def retrieval_contract_sha(repo_root: pathlib.Path = REPO_ROOT) -> str:
    """Bind evidence to every source file that owns retrieval semantics."""
    paths = (
        pathlib.Path("src/models/product.py"),
        pathlib.Path("src/rag/embeddings.py"),
        pathlib.Path("src/rag/pipeline.py"),
        pathlib.Path("src/schemas/product.py"),
        pathlib.Path("scripts/corpus_bridge/semantic_catalog_evidence.py"),
    )
    digest = hashlib.sha256()
    for relative in paths:
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update((repo_root / relative).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _require_protected_file(
    path: pathlib.Path, *, repo_root: pathlib.Path = REPO_ROOT
) -> pathlib.Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"semantic retrieval evidence is missing: {path}")
    resolved = path.resolve()
    root = repo_root.resolve()
    git_metadata = (root / ".git").resolve()
    inside_root = resolved == root or root in resolved.parents
    inside_git = resolved == git_metadata or git_metadata in resolved.parents
    if inside_root and not inside_git:
        raise ValueError("semantic retrieval evidence must stay outside the repository")
    if path.stat().st_mode & 0o077:
        raise ValueError("semantic retrieval evidence must have mode 0600")
    return resolved


def _read_json(path: pathlib.Path, *, label: str) -> Any:
    _require_protected_file(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON: {exc}") from exc


def _load_snapshot(path: pathlib.Path) -> CatalogSnapshot:
    try:
        snapshot = CatalogSnapshot.model_validate(
            _read_json(path, label="catalog snapshot")
        )
    except ValidationError as exc:
        raise ValueError(f"catalog snapshot is invalid: {exc}") from exc
    if snapshot.schema_version != "treejar-semantic-catalog-snapshot/v1":
        raise ValueError("catalog snapshot schema version mismatch")
    if not snapshot.products:
        raise ValueError("catalog snapshot contains no products")
    ids = [product.id for product in snapshot.products]
    skus = [product.sku.casefold() for product in snapshot.products]
    if len(set(ids)) != len(ids):
        raise ValueError("catalog snapshot contains duplicate product ids")
    if len(set(skus)) != len(skus):
        raise ValueError("catalog snapshot contains duplicate SKUs")
    return snapshot


def _load_scenarios(path: pathlib.Path) -> list[dict[str, Any]]:
    raw = _read_json(path, label="frozen scenarios")
    rows = raw.get("scenarios") if isinstance(raw, dict) else raw
    if not isinstance(rows, list) or not rows:
        raise ValueError("frozen scenarios must contain a non-empty list")
    scenarios: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"frozen scenario {index} must be an object")
        if not isinstance(row.get("dialog_id"), int):
            raise ValueError(f"frozen scenario {index} has no integer dialog_id")
        if not isinstance(row.get("opening"), str) or not row["opening"].strip():
            raise ValueError(f"frozen scenario {index} has no opening")
        scenarios.append(dict(row))
    ids = [int(row["dialog_id"]) for row in scenarios]
    if len(set(ids)) != len(ids):
        raise ValueError("frozen scenarios contain duplicate dialog ids")
    return scenarios


def _load_qrels(
    path: pathlib.Path, scenarios: list[dict[str, Any]]
) -> tuple[RetrievalQrels, dict[str, Any]]:
    raw = _read_json(path, label="retrieval qrels")
    if not isinstance(raw, dict):
        raise ValueError("retrieval qrels root must be an object")
    try:
        qrels = RetrievalQrels.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"retrieval qrels are invalid: {exc}") from exc
    if qrels.schema_version != "treejar-semantic-retrieval-qrels/v1":
        raise ValueError("retrieval qrels schema version mismatch")
    expected_ids = [int(row["dialog_id"]) for row in scenarios]
    actual_ids = [entry.dialog_id for entry in qrels.entries]
    if actual_ids != expected_ids:
        raise ValueError("retrieval qrels must match frozen dialog order exactly")
    return qrels, raw


def _validate_local_database_url(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("semantic evidence database must be PostgreSQL")
    if url.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("semantic evidence database must use a loopback host")
    if not (url.database or "").startswith("treejar_semantic_evidence"):
        raise ValueError(
            "semantic evidence database name must start with treejar_semantic_evidence"
        )


def _protected_output_path(
    path: pathlib.Path, *, repo_root: pathlib.Path = REPO_ROOT
) -> pathlib.Path:
    if path.exists():
        raise ValueError(f"protected output already exists: {path}")
    parent = path.parent
    root = repo_root.resolve()
    resolved_parent = parent.resolve()
    git_metadata = (root / ".git").resolve()
    inside_root = resolved_parent == root or root in resolved_parent.parents
    inside_git = (
        resolved_parent == git_metadata or git_metadata in resolved_parent.parents
    )
    if inside_root and not inside_git:
        raise ValueError("protected output must stay outside the repository")
    if parent.is_symlink():
        raise ValueError("protected output directory must not be a symlink")
    parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    parent.chmod(0o700)
    return path.resolve()


def _atomic_write_json(path: pathlib.Path, value: object) -> None:
    resolved = _protected_output_path(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=resolved.parent)
    temporary_path = pathlib.Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(resolved)
        resolved.chmod(0o600)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _product_embedding_text(product: CatalogSnapshotProduct) -> str:
    return (
        f"{product.name_en} | {product.category or ''} | {product.description_en or ''}"
    )


async def produce_evidence(
    *,
    database_url: str,
    catalog_snapshot_path: pathlib.Path,
    scenarios_path: pathlib.Path,
    qrels_path: pathlib.Path,
    output_path: pathlib.Path,
    model: str,
    revision: str,
) -> tuple[SemanticCatalogEvidence, dict[str, Any]]:
    """Produce immutable evidence through the production retrieval function."""
    _validate_local_database_url(database_url)
    snapshot = _load_snapshot(catalog_snapshot_path)
    scenarios = _load_scenarios(scenarios_path)
    qrels, raw_qrels = _load_qrels(qrels_path, scenarios)
    _protected_output_path(output_path)
    report_path = output_path.with_name(f"{output_path.stem}-report.json")
    _protected_output_path(report_path)
    embedding_engine = PinnedEmbeddingEngine(model=model, revision=revision)
    db_engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    table_created = False
    product_table = cast("Table", Product.__table__)
    try:
        async with db_engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            existing = await connection.scalar(text("SELECT to_regclass('products')"))
            if existing is not None:
                raise ValueError(
                    "semantic evidence database is not empty: products table exists"
                )
            await connection.run_sync(product_table.create)
            table_created = True

        embedding_rows = await embedding_engine.embed_batch_async(
            [_product_embedding_text(product) for product in snapshot.products]
        )
        async with session_factory() as session:
            for source, embedding in zip(
                snapshot.products, embedding_rows, strict=True
            ):
                session.add(
                    Product(
                        id=source.id,
                        sku=source.sku,
                        zoho_item_id=None,
                        name_en=source.name_en,
                        name_ar=source.name_ar,
                        description_en=source.description_en,
                        description_ar=source.description_ar,
                        category=source.category,
                        subcategory=source.subcategory,
                        price=source.price,
                        currency=source.currency,
                        stock=source.stock,
                        image_url=None,
                        attributes={"semantic_snapshot": snapshot.source},
                        embedding=embedding,
                        is_active=source.is_active,
                        synced_at=None,
                    )
                )
            await session.commit()

        async with db_engine.connect() as connection:
            extension_version = await connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            indexes = (
                await connection.execute(
                    text(
                        "SELECT indexname, indexdef FROM pg_indexes "
                        "WHERE schemaname = current_schema() AND tablename = 'products'"
                    )
                )
            ).all()
        ann_indexes = tuple(
            str(name)
            for name, definition in indexes
            if " using hnsw " in str(definition).casefold()
            or " using ivfflat " in str(definition).casefold()
        )
        if ann_indexes:
            raise ValueError("ANN indexes are forbidden: " + ", ".join(ann_indexes))

        qrels_by_id = {entry.dialog_id: entry for entry in qrels.entries}
        results: list[RetrievalResultEvidence] = []
        async with session_factory() as session:
            for scenario in scenarios:
                query = str(scenario["opening"])
                search_result = await rag_pipeline.search_products(
                    session,
                    ProductSearchQuery(query=query, limit=RETRIEVAL_LIMIT),
                    embedding_engine,  # type: ignore[arg-type]
                )
                products = tuple(
                    EvidenceProduct(
                        id=str(product.id),
                        sku=product.sku,
                        name=product.name_en,
                        category=product.category,
                        price_aed=float(product.price),
                        stock=product.stock,
                    )
                    for product in search_result.products
                )
                qrel = qrels_by_id[int(scenario["dialog_id"])]
                relevant = bool(
                    {product.sku for product in products}.intersection(
                        qrel.relevant_skus
                    )
                )
                results.append(
                    RetrievalResultEvidence(
                        dialog_id=int(scenario["dialog_id"]),
                        query_sha256=_query_sha256(query),
                        rows_present=bool(products),
                        catalog_relevant=relevant,
                        relevant_skus=tuple(
                            product.sku
                            for product in products
                            if product.sku in qrel.relevant_skus
                        ),
                        products=products,
                    )
                )

        evidence = SemanticCatalogEvidence(
            schema_version=EVIDENCE_SCHEMA,
            catalog=CatalogIdentity(
                sha256=_sha256_json(snapshot.model_dump(mode="json")),
                rows=len(snapshot.products),
            ),
            embedding=EmbeddingIdentity(
                model=model,
                revision=revision,
                dimensions=EMBEDDING_DIMENSIONS,
                normalized=True,
            ),
            retrieval=RetrievalIdentity(
                entrypoint=RETRIEVAL_ENTRYPOINT,
                code_sha=retrieval_contract_sha(),
                pgvector_python=importlib.metadata.version("pgvector"),
                pgvector_extension=str(extension_version),
                distance="cosine",
                search_mode="exact",
                ann_indexes=ann_indexes,
                limit=RETRIEVAL_LIMIT,
                query_source="frozen_opening",
            ),
            qrels=QrelsIdentity(sha256=_sha256_json(raw_qrels)),
            query_set=QuerySetIdentity(
                sha256=_sha256_json(scenarios), count=len(scenarios)
            ),
            results=tuple(results),
        )
        report = evaluate_retrieval(evidence.results, raw_qrels, top_k=RETRIEVAL_LIMIT)
        report_document = {
            "schema_version": "treejar-semantic-retrieval-report/v1",
            "created_at": datetime.now(UTC).isoformat(),
            "catalog_sha256": evidence.catalog.sha256,
            "query_set_sha256": evidence.query_set.sha256,
            "qrels_sha256": evidence.qrels.sha256,
            "embedding_revision": evidence.embedding.revision,
            "retrieval_code_sha": evidence.retrieval.code_sha,
            **report,
        }
        _atomic_write_json(report_path, report_document)
        if not report["passed"]:
            raise ValueError(
                "semantic retrieval hard constraints failed: "
                + "; ".join(report["hard_failures"])
            )
        _atomic_write_json(output_path, evidence.model_dump(mode="json"))
        return evidence, report
    finally:
        if table_created:
            async with db_engine.begin() as connection:
                await connection.run_sync(product_table.drop, checkfirst=True)
        await db_engine.dispose()


async def capture_catalog_snapshot(
    output_path: pathlib.Path,
) -> tuple[CatalogSnapshot, str]:
    """Capture a hydrated read-only catalog snapshot through production code."""
    _protected_output_path(output_path)
    products: list[CatalogSnapshotProduct] = []
    async with TreejarCatalogClient() as client:
        async for raw_product in client.iter_all_products(
            limit=settings.catalog_api_page_size
        ):
            normalized = _normalize_treejar_product(raw_product)
            if normalized is None:
                continue
            sku = str(normalized["sku"])
            products.append(
                CatalogSnapshotProduct(
                    id=uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"https://treejartrading.ae/products/{sku.casefold()}",
                    ),
                    sku=sku,
                    name_en=str(normalized["name_en"]),
                    name_ar=None,
                    description_en=normalized.get("description_en"),
                    description_ar=None,
                    category=normalized.get("category"),
                    subcategory=normalized.get("subcategory"),
                    price=float(normalized["price"]),
                    currency=str(normalized["currency"]),
                    stock=int(normalized["stock"]),
                    is_active=bool(normalized["is_active"]),
                )
            )
    products.sort(key=lambda product: (product.sku.casefold(), str(product.id)))
    snapshot = CatalogSnapshot(
        schema_version="treejar-semantic-catalog-snapshot/v1",
        source="treejar_catalog_api_hydrated",
        captured_at=datetime.now(UTC).isoformat(),
        products=tuple(products),
    )
    if not snapshot.products:
        raise ValueError("catalog snapshot capture returned no products")
    digest = _sha256_json(snapshot.model_dump(mode="json"))
    _atomic_write_json(output_path, snapshot.model_dump(mode="json"))
    return snapshot, digest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture-snapshot")
    capture.add_argument("--output", type=pathlib.Path, required=True)
    produce = subparsers.add_parser("produce")
    produce.add_argument("--database-url", required=True)
    produce.add_argument("--catalog-snapshot", type=pathlib.Path, required=True)
    produce.add_argument("--scenarios", type=pathlib.Path, required=True)
    produce.add_argument("--qrels", type=pathlib.Path, required=True)
    produce.add_argument("--output", type=pathlib.Path, required=True)
    produce.add_argument("--model", default=EMBEDDING_MODEL, choices=[EMBEDDING_MODEL])
    produce.add_argument("--revision", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--evidence", type=pathlib.Path, required=True)
    validate.add_argument("--scenarios", type=pathlib.Path, required=True)
    validate.add_argument("--catalog-sha256", required=True)
    validate.add_argument("--embedding-revision", required=True)
    validate.add_argument("--qrels-sha256", required=True)
    validate.add_argument("--pgvector-extension", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        if args.command == "capture-snapshot":
            snapshot, digest = asyncio.run(capture_catalog_snapshot(args.output))
            public = {
                "schema_version": snapshot.schema_version,
                "catalog_rows": len(snapshot.products),
                "catalog_sha256": digest,
                "output": str(args.output),
            }
        elif args.command == "produce":
            evidence, report = asyncio.run(
                produce_evidence(
                    database_url=args.database_url,
                    catalog_snapshot_path=args.catalog_snapshot,
                    scenarios_path=args.scenarios,
                    qrels_path=args.qrels,
                    output_path=args.output,
                    model=args.model,
                    revision=args.revision,
                )
            )
            public = {
                "schema_version": evidence.schema_version,
                "catalog_rows": evidence.catalog.rows,
                "catalog_sha256": evidence.catalog.sha256,
                "query_set_sha256": evidence.query_set.sha256,
                "qrels_sha256": evidence.qrels.sha256,
                "embedding_model": evidence.embedding.model,
                "embedding_revision": evidence.embedding.revision,
                "retrieval_code_sha": evidence.retrieval.code_sha,
                "pgvector_python": evidence.retrieval.pgvector_python,
                "pgvector_extension": evidence.retrieval.pgvector_extension,
                "search_mode": evidence.retrieval.search_mode,
                "query_source": evidence.retrieval.query_source,
                "aggregate": report["aggregate"],
                "hard_failure_count": len(report["hard_failures"]),
                "output": str(args.output),
            }
        else:
            scenarios = _load_scenarios(args.scenarios)
            evidence = load_and_validate_evidence(
                args.evidence,
                scenarios=scenarios,
                expected_catalog_sha256=args.catalog_sha256,
                expected_embedding_revision=args.embedding_revision,
                expected_qrels_sha256=args.qrels_sha256,
                expected_pgvector_extension=args.pgvector_extension,
            )
            public = {
                "validated": True,
                "schema_version": evidence.schema_version,
                "catalog_rows": evidence.catalog.rows,
                "catalog_sha256": evidence.catalog.sha256,
                "query_set_sha256": evidence.query_set.sha256,
                "qrels_sha256": evidence.qrels.sha256,
                "embedding_revision": evidence.embedding.revision,
                "retrieval_code_sha": evidence.retrieval.code_sha,
                "pgvector_python": evidence.retrieval.pgvector_python,
                "pgvector_extension": evidence.retrieval.pgvector_extension,
                "search_mode": evidence.retrieval.search_mode,
                "query_source": evidence.retrieval.query_source,
            }
        print(json.dumps(public, indent=2, sort_keys=True))
    except (OSError, ValueError, RuntimeError, ValidationError) as exc:
        print(f"semantic catalog evidence failed: {exc}", file=sys.stderr)
        return 2
    return 0


def load_and_validate_evidence(
    path: pathlib.Path,
    *,
    scenarios: list[dict[str, Any]],
    expected_catalog_sha256: str,
    expected_embedding_revision: str,
    expected_qrels_sha256: str,
    expected_pgvector_extension: str,
    expected_retrieval_code_sha: str | None = None,
    repo_root: pathlib.Path = REPO_ROOT,
) -> SemanticCatalogEvidence:
    """Load one protected artifact or fail before measured provider work."""
    resolved = _require_protected_file(path, repo_root=repo_root)
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
        evidence = SemanticCatalogEvidence.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"semantic retrieval evidence is invalid: {exc}") from exc

    expected_code_sha = expected_retrieval_code_sha or retrieval_contract_sha(repo_root)
    expected_query_set_sha = _sha256_json(scenarios)
    installed_pgvector = importlib.metadata.version("pgvector")
    expected_ids = [int(scenario["dialog_id"]) for scenario in scenarios]
    actual_ids = [result.dialog_id for result in evidence.results]
    if len(set(actual_ids)) != len(actual_ids):
        raise ValueError("semantic retrieval evidence contains duplicate dialog ids")

    checks = (
        (evidence.schema_version == EVIDENCE_SCHEMA, "schema version mismatch"),
        (
            evidence.catalog.sha256 == expected_catalog_sha256,
            "catalog digest mismatch",
        ),
        (evidence.embedding.model == EMBEDDING_MODEL, "embedding model mismatch"),
        (
            evidence.embedding.revision == expected_embedding_revision,
            "embedding revision mismatch",
        ),
        (
            evidence.embedding.dimensions == EMBEDDING_DIMENSIONS,
            "embedding dimensions mismatch",
        ),
        (evidence.embedding.normalized, "embeddings must be normalized"),
        (
            evidence.retrieval.entrypoint == RETRIEVAL_ENTRYPOINT,
            "retrieval entrypoint mismatch",
        ),
        (evidence.retrieval.code_sha == expected_code_sha, "retrieval code mismatch"),
        (
            evidence.retrieval.pgvector_python == installed_pgvector,
            "pgvector Python version mismatch",
        ),
        (
            evidence.retrieval.pgvector_extension == expected_pgvector_extension,
            "pgvector extension version mismatch",
        ),
        (evidence.retrieval.distance == "cosine", "retrieval distance mismatch"),
        (evidence.retrieval.search_mode == "exact", "retrieval must be exact"),
        (not evidence.retrieval.ann_indexes, "ANN indexes are forbidden"),
        (evidence.retrieval.limit == RETRIEVAL_LIMIT, "retrieval limit mismatch"),
        (
            evidence.retrieval.query_source == "frozen_opening",
            "query source mismatch",
        ),
        (
            evidence.query_set.sha256 == expected_query_set_sha,
            "query-set digest mismatch",
        ),
        (evidence.qrels.sha256 == expected_qrels_sha256, "qrels digest mismatch"),
        (evidence.query_set.count == len(scenarios), "query-set count mismatch"),
        (actual_ids == expected_ids, "results must match frozen dialog order exactly"),
    )
    for passed, message in checks:
        if not passed:
            raise ValueError(f"semantic retrieval evidence {message}")

    for scenario, result in zip(scenarios, evidence.results, strict=True):
        opening = str(scenario["opening"])
        if result.query_sha256 != _query_sha256(opening):
            raise ValueError(
                f"semantic retrieval evidence query digest mismatch for dialog "
                f"{result.dialog_id}"
            )
        if result.rows_present != bool(result.products):
            raise ValueError(
                f"semantic retrieval evidence rows_present mismatch for dialog "
                f"{result.dialog_id}"
            )
        product_skus = {product.sku for product in result.products}
        if len(set(result.relevant_skus)) != len(result.relevant_skus):
            raise ValueError(
                f"semantic retrieval evidence duplicate relevant SKU for dialog "
                f"{result.dialog_id}"
            )
        if not set(result.relevant_skus).issubset(product_skus):
            raise ValueError(
                f"semantic retrieval evidence relevant SKU outside top-k for dialog "
                f"{result.dialog_id}"
            )
        if result.catalog_relevant != bool(result.relevant_skus):
            raise ValueError(
                f"semantic retrieval evidence catalog_relevant mismatch for dialog "
                f"{result.dialog_id}"
            )
        if len(result.products) > evidence.retrieval.limit:
            raise ValueError(
                f"semantic retrieval evidence exceeds top-k for dialog "
                f"{result.dialog_id}"
            )
    return evidence


if __name__ == "__main__":
    raise SystemExit(main())
