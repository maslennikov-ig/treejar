"""In-process stand-ins for everything the reply pipeline touches except the model.

The database is the one stand-in with real query semantics. Catalog rows,
messages, outbound audits and the other ORM tables live in a private in-memory
SQLite engine so that every ``select(Product)...`` the runtime issues is
evaluated for real against the snapshot, instead of each call site being
patched and silently drifting. The conversation itself is a plain in-memory ORM
object, as in ``tests/test_decision_state.py``; it survives between turns and
carries the decision state, quote workflow and sales stage.

Nothing here opens a socket. Zoho, CRM, Wazzup and Redis are recorders.
"""

from __future__ import annotations

import datetime
import json
import re
import uuid
from collections.abc import AsyncIterator, Callable, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import Delete, Insert, Select, Update
from sqlalchemy.sql.schema import Table
from sqlalchemy.sql.visitors import iterate

import src.models  # noqa: F401  (registers every mapped table)
from src.models.base import Base
from src.models.conversation import Conversation
from src.models.product import Product
from src.schemas.product import ProductRead, ProductSearchQuery, ProductSearchResult

_SNAPSHOT_TIMESTAMP = datetime.datetime(2026, 9, 23, 0, 0, 0)
# `system_configs.value` uses a type SQLite cannot compile. System config is
# answered by the harness's `get_system_config` stand-in instead.
_UNSUPPORTED_TABLES = frozenset({"system_configs"})


# --- Catalog -----------------------------------------------------------------


def load_catalog_rows(path: Path) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError(f"{path} is not a list of catalog rows")
    return rows


class CatalogStore:
    """A private SQLite engine seeded with the read-only catalog snapshot."""

    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self.engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        tables = [
            table
            for table in Base.metadata.sorted_tables
            if table.name not in _UNSUPPORTED_TABLES
        ]
        Base.metadata.create_all(self.engine, tables=tables)
        self.session = Session(self.engine, expire_on_commit=False)
        self.rows = [dict(row) for row in rows]
        for row in self.rows:
            self.session.add(
                Product(
                    id=uuid.UUID(str(row["id"])),
                    sku=str(row["sku"]),
                    name_en=str(row["name_en"]),
                    name_ar=row.get("name_ar"),
                    description_en=row.get("description_en"),
                    category=row.get("category"),
                    subcategory=row.get("subcategory"),
                    price=float(row["price"]),
                    currency=str(row.get("currency") or "AED"),
                    stock=int(row.get("stock") or 0),
                    image_url=row.get("image_url"),
                    zoho_item_id=row.get("zoho_item_id"),
                    attributes=row.get("attributes"),
                    is_active=bool(row.get("is_active", True)),
                    created_at=_SNAPSHOT_TIMESTAMP,
                    updated_at=_SNAPSHOT_TIMESTAMP,
                )
            )
        self.session.commit()

    def sku_for_key(self, product_key: str) -> str | None:
        for row in self.rows:
            if product_key in (str(row["id"]), str(row["sku"])):
                return str(row["sku"])
        return None

    def products(self) -> list[Product]:
        from sqlalchemy import select

        return list(self.session.execute(select(Product)).scalars().all())

    def close(self) -> None:
        self.session.close()
        self.engine.dispose()


# --- Lexical stand-in for pgvector search ------------------------------------

_NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
}
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "the",
        "for",
        "of",
        "to",
        "in",
        "on",
        "with",
        "our",
        "we",
        "us",
        "i",
        "me",
        "my",
        "is",
        "are",
        "be",
        "need",
        "want",
        "please",
        "can",
        "you",
        "your",
        "office",
        "furniture",
        "people",
        "person",
        "persons",
        "team",
        "setup",
        "set",
        "up",
    ]
)
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _tokens(text: str | None) -> set[str]:
    tokens: set[str] = set()
    for raw in _TOKEN_RE.findall(str(text or "").casefold()):
        parts = [raw, *raw.split("-")] if "-" in raw else [raw]
        for part in parts:
            part = _NUMBER_WORDS.get(part, part)
            if len(part) > 3 and part.endswith("s") and not part.isdigit():
                part = part[:-1]
            tokens.add(part)
    return tokens


def lexical_rank(
    products: Iterable[Product], query: ProductSearchQuery
) -> list[Product]:
    """Deterministic ranking that honours the production SQL filters.

    `src.rag.pipeline.search_products` filters active rows, price bounds and --
    because `ProductSearchQuery.in_stock_only` defaults to True -- `stock > 0`,
    then orders by embedding distance. The filters are reproduced exactly; the
    ordering is a weighted token overlap, which is the part a replay cannot
    reproduce without the production embeddings.
    """

    query_tokens = {t for t in _tokens(query.query) if t not in _STOPWORDS}
    scored: list[tuple[float, int, Product]] = []
    for index, product in enumerate(products):
        if not product.is_active:
            continue
        if query.category and product.category != query.category:
            continue
        price = float(product.price)
        if query.min_price is not None and price < query.min_price:
            continue
        if query.max_price is not None and price > query.max_price:
            continue
        if query.in_stock_only and not int(product.stock or 0) > 0:
            continue
        fields = (
            (3.0, _tokens(product.name_en) | _tokens(product.sku)),
            (2.0, _tokens(product.category)),
            (1.0, _tokens(product.description_en)),
        )
        score = 0.0
        for token in query_tokens:
            weight = max((w for w, bag in fields if token in bag), default=0.0)
            if weight and any(ch.isdigit() for ch in token):
                weight *= 2
            score += weight
        scored.append((score, index, product))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [product for _, _, product in scored[: query.limit]]


def lexical_search_factory(
    get_store: Callable[[], CatalogStore], log: list[dict[str, Any]]
) -> Any:
    """Stand-in for `src.rag.pipeline.search_products` (patched on the engine)."""

    async def search_products(
        db: Any, query: ProductSearchQuery, embedding_engine: Any
    ) -> ProductSearchResult:
        ranked = lexical_rank(get_store().products(), query)
        log.append(
            {
                "query": query.query,
                "min_price": query.min_price,
                "max_price": query.max_price,
                "limit": query.limit,
                "in_stock_only": query.in_stock_only,
                "results": [p.sku for p in ranked],
            }
        )
        reads = [ProductRead.model_validate(p) for p in ranked]
        return ProductSearchResult(
            products=reads, query_interpreted=query.query, total_found=len(reads)
        )

    return search_products


# --- Database ----------------------------------------------------------------


class ListResult:
    """Result shape for queries the harness answers without SQLite."""

    def __init__(self, objects: Sequence[Any] = ()) -> None:
        self._objects = list(objects)
        self.rowcount = len(self._objects)

    def scalars(self) -> ListResult:
        return self

    def all(self) -> list[Any]:
        return list(self._objects)

    def fetchall(self) -> list[Any]:
        return list(self._objects)

    def first(self) -> Any | None:
        return self._objects[0] if self._objects else None

    def scalar(self) -> Any | None:
        return self.first()

    def scalar_one_or_none(self) -> Any | None:
        return self.first()

    def one_or_none(self) -> Any | None:
        return self.first()

    def scalar_one(self) -> Any:
        if len(self._objects) != 1:
            raise LookupError("expected exactly one row")
        return self._objects[0]

    def one(self) -> Any:
        return self.scalar_one()

    def unique(self) -> ListResult:
        return self

    def mappings(self) -> ListResult:
        return self

    def __iter__(self) -> Any:
        return iter(self._objects)


@dataclass
class DbLog:
    reads: dict[str, int] = field(default_factory=dict)
    adds: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    conversation_writes: list[str] = field(default_factory=list)

    def drain(self) -> dict[str, Any]:
        out = {
            "reads": dict(self.reads),
            "adds": dict(self.adds),
            "errors": list(self.errors),
            "conversation_writes": list(self.conversation_writes),
        }
        self.reads.clear()
        self.adds.clear()
        self.errors.clear()
        self.conversation_writes.clear()
        return out


def _statement_tables(statement: Any) -> set[str]:
    if isinstance(statement, (Insert, Update, Delete)):
        return {str(statement.table.name)}  # type: ignore[attr-defined]
    names: set[str] = set()
    for element in iterate(statement):
        if isinstance(element, Table):
            names.add(str(element.name))
    return names


class FakeAsyncSession:
    """AsyncSession surface over the SQLite store plus one in-memory conversation."""

    def __init__(self, store: CatalogStore, conversation: Conversation) -> None:
        self._sync = store.session
        self.conversation = conversation
        self.log = DbLog()
        self.info: dict[str, Any] = {}

    def _count(self, bucket: dict[str, int], key: str) -> None:
        bucket[key] = bucket.get(key, 0) + 1

    def _apply_conversation_update(self, statement: Update) -> None:
        mapper = Conversation.__mapper__
        values = getattr(statement, "_values", None) or {}
        for column, value in values.items():
            key = getattr(column, "key", str(column))
            try:
                attr = mapper.get_property_by_column(mapper.columns[key]).key
            except Exception:
                attr = key
            literal = getattr(value, "value", value)
            if hasattr(literal, "__clause_element__") or type(
                literal
            ).__module__.startswith("sqlalchemy"):
                self.log.conversation_writes.append(f"skipped expression for {attr}")
                continue
            setattr(self.conversation, attr, literal)
            self.log.conversation_writes.append(f"set {attr}")

    async def execute(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        tables = _statement_tables(statement)
        label = ",".join(sorted(tables)) or type(statement).__name__
        self._count(self.log.reads, label)
        if tables and tables <= {"conversations"}:
            if isinstance(statement, Select):
                return ListResult([self.conversation])
            if isinstance(statement, Update):
                self._apply_conversation_update(statement)
            else:
                self.log.conversation_writes.append(type(statement).__name__)
            return ListResult([])
        if tables & _UNSUPPORTED_TABLES:
            return ListResult([])
        try:
            if params is None:
                result = self._sync.execute(statement, **kwargs)
            else:
                result = self._sync.execute(statement, params, **kwargs)
        except Exception as exc:
            self.log.errors.append(
                f"execute {label}: {type(exc).__name__}: {exc}"[:300]
            )
            return ListResult([])
        if getattr(result, "returns_rows", False):
            return result.freeze()()
        return result

    async def scalar(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        return (await self.execute(statement, params, **kwargs)).scalar()

    async def scalars(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        return (await self.execute(statement, params, **kwargs)).scalars()

    async def get(self, entity: Any, ident: Any, **kwargs: Any) -> Any:
        if entity is Conversation:
            return self.conversation if ident == self.conversation.id else None
        self._count(self.log.reads, f"get:{getattr(entity, '__tablename__', entity)}")
        try:
            return self._sync.get(entity, ident)
        except Exception as exc:
            self.log.errors.append(f"get {entity}: {type(exc).__name__}: {exc}"[:300])
            return None

    def add(self, instance: Any, _warn: bool = True) -> None:
        if instance is self.conversation or isinstance(instance, Conversation):
            return
        self._count(self.log.adds, type(instance).__name__)
        self._sync.add(instance)

    def add_all(self, instances: Iterable[Any]) -> None:
        for instance in instances:
            self.add(instance)

    async def flush(self, objects: Any = None) -> None:
        try:
            self._sync.flush()
        except Exception as exc:
            self.log.errors.append(f"flush: {type(exc).__name__}: {exc}"[:300])
            self._sync.rollback()

    async def commit(self) -> None:
        await self.flush()
        self._sync.commit()

    async def rollback(self) -> None:
        self._sync.rollback()

    async def refresh(self, instance: Any, *args: Any, **kwargs: Any) -> None:
        return None

    async def delete(self, instance: Any) -> None:
        if isinstance(instance, Conversation):
            return
        try:
            self._sync.delete(instance)
        except Exception as exc:
            self.log.errors.append(f"delete: {type(exc).__name__}: {exc}"[:300])

    async def merge(self, instance: Any, **kwargs: Any) -> Any:
        if isinstance(instance, Conversation):
            return self.conversation
        return self._sync.merge(instance)

    def expunge(self, instance: Any) -> None:
        return None

    async def close(self) -> None:
        return None

    def in_transaction(self) -> bool:
        return True

    @property
    def no_autoflush(self) -> Any:
        return self._sync.no_autoflush

    @asynccontextmanager
    async def _nested(self) -> AsyncIterator[None]:
        yield

    def begin_nested(self) -> Any:
        return self._nested()

    async def run_sync(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        return fn(self._sync, *args, **kwargs)


# --- External services -------------------------------------------------------


@dataclass
class CallRecorder:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def record(self, service: str, method: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append(
            {
                "service": service,
                "method": method,
                "args": [_short(a) for a in args],
                "kwargs": {k: _short(v) for k, v in kwargs.items()},
            }
        )

    def drain(self) -> list[dict[str, Any]]:
        out = list(self.calls)
        self.calls.clear()
        return out


def _short(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value if not isinstance(value, str) else value[:300]
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, (list, tuple)):
        return [_short(v) for v in list(value)[:20]]
    if isinstance(value, dict):
        return {str(k): _short(v) for k, v in list(value.items())[:20]}
    return type(value).__name__


class QuotationGatesPassed(Exception):  # noqa: N818 - a control-flow signal
    """Raised at the first Zoho write boundary of `_create_quotation`."""


class FakeZohoInventory:
    """Zoho Inventory reads answered from the snapshot plus live-stock overrides."""

    def __init__(
        self,
        store: CatalogStore,
        recorder: CallRecorder,
        live_stock_overrides: Mapping[str, int] | None = None,
    ) -> None:
        self._recorder = recorder
        self._overrides = {
            k.strip().casefold(): int(v)
            for k, v in (live_stock_overrides or {}).items()
        }
        self._rows = {str(r["sku"]).strip().casefold(): r for r in store.rows}
        self.quotation_boundary_armed = False

    def _item(self, sku: str) -> dict[str, Any] | None:
        key = str(sku or "").strip().casefold()
        row = self._rows.get(key)
        if row is None:
            return None
        stock = self._overrides.get(key, int(row.get("stock") or 0))
        return {
            "item_id": f"fake-zoho-{row['id']}",
            "sku": row["sku"],
            "name": row["name_en"],
            "description": "",
            "rate": float(row["price"]),
            "stock_on_hand": stock,
            "available_stock": stock,
            "unit": "pcs",
        }

    async def get_stock_bulk(self, skus: Sequence[str]) -> list[dict[str, Any]]:
        self._recorder.record("zoho_inventory", "get_stock_bulk", list(skus))
        if self.quotation_boundary_armed:
            raise QuotationGatesPassed
        return [item for sku in skus if (item := self._item(sku)) is not None]

    async def get_stock(self, sku: str) -> dict[str, Any] | None:
        self._recorder.record("zoho_inventory", "get_stock", sku)
        return self._item(sku)

    async def get_item(self, item_id: str) -> dict[str, Any] | None:
        self._recorder.record("zoho_inventory", "get_item", item_id)
        for key in self._rows:
            item = self._item(key)
            if item and item["item_id"] == item_id:
                return item
        return None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)

        async def _unintercepted(*args: Any, **kwargs: Any) -> None:
            self._recorder.record("zoho_inventory", name, *args, **kwargs)
            return None

        return _unintercepted


class FakeCRM:
    """New customer: nothing found; writes are recorded and acknowledged."""

    def __init__(self, recorder: CallRecorder) -> None:
        self._recorder = recorder

    async def find_contact_by_phone(self, phone: str) -> None:
        self._recorder.record("zoho_crm", "find_contact_by_phone", "<phone>")
        return None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)

        async def _recorded(*args: Any, **kwargs: Any) -> dict[str, Any]:
            self._recorder.record("zoho_crm", name, *args, **kwargs)
            return {"id": f"fake-crm-{name}"}

        return _recorded


class FakeMessaging:
    """Wazzup stand-in: records what would be sent."""

    def __init__(self, recorder: CallRecorder) -> None:
        self._recorder = recorder
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"fake-wazzup-{self._counter}"

    async def send_text(self, chat_id: str, text: str, **kwargs: Any) -> str:
        self._recorder.record("wazzup", "send_text", text=text)
        return self._next_id()

    async def send_media(
        self,
        chat_id: str,
        url: str | None = None,
        caption: str | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
        **kwargs: Any,
    ) -> str:
        self._recorder.record(
            "wazzup", "send_media", url=url, caption=caption, content=content
        )
        return self._next_id()

    async def mark_read(self, chat_id: str, message_id: str) -> bool:
        return True

    def __getattr__(self, name: str) -> Any:
        # Only unknown *send* methods are recorded; optional hooks such as
        # `outbound_chat_id` must look absent, as on a provider without them.
        if not name.startswith("send_"):
            raise AttributeError(name)

        async def _recorded(*args: Any, **kwargs: Any) -> str:
            self._recorder.record("wazzup", name, *args, **kwargs)
            return self._next_id()

        return _recorded


class FakeRedis:
    """Enough of redis.asyncio for the reply path, backed by dicts."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.lists: dict[str, list[Any]] = {}
        self.hashes: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> Any:
        return self.values.get(key)

    async def set(self, key: str, value: Any, *args: Any, **kwargs: Any) -> bool:
        if kwargs.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    async def setex(self, key: str, ttl: Any, value: Any) -> bool:
        self.values[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            for store in (self.values, self.lists, self.hashes):
                if key in store:
                    del store[key]
                    removed += 1
        return removed

    async def exists(self, *keys: str) -> int:
        return sum(1 for k in keys if k in self.values or k in self.lists)

    async def incr(self, key: str, amount: int = 1) -> int:
        value = int(self.values.get(key) or 0) + amount
        self.values[key] = value
        return value

    async def expire(self, *args: Any, **kwargs: Any) -> bool:
        return True

    async def ttl(self, key: str) -> int:
        return -1

    async def lpush(self, key: str, *values: Any) -> int:
        self.lists.setdefault(key, [])[:0] = list(reversed(values))
        return len(self.lists[key])

    async def rpush(self, key: str, *values: Any) -> int:
        self.lists.setdefault(key, []).extend(values)
        return len(self.lists[key])

    async def llen(self, key: str) -> int:
        return len(self.lists.get(key, []))

    async def lrange(self, key: str, start: int, end: int) -> list[Any]:
        items = self.lists.get(key, [])
        return items[start : None if end == -1 else end + 1]

    async def hget(self, key: str, field_name: str) -> Any:
        return self.hashes.get(key, {}).get(field_name)

    async def hset(self, key: str, *args: Any, **kwargs: Any) -> int:
        mapping = dict(kwargs.get("mapping") or {})
        if len(args) >= 2:
            mapping[args[0]] = args[1]
        self.hashes.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def hgetall(self, key: str) -> dict[str, Any]:
        return dict(self.hashes.get(key, {}))

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)

        async def _noop(*args: Any, **kwargs: Any) -> None:
            return None

        return _noop


class StubEmbedding:
    """Vector search is replaced by lexical ranking; nothing should embed."""

    async def embed_async(self, text: str) -> list[float]:
        return [0.0] * 1024

    def embed(self, text: str) -> list[float]:
        return [0.0] * 1024
