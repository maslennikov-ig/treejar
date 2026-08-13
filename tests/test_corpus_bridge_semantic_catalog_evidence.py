"""Semantic catalog evidence is exact, versioned, protected, and fail-closed."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import uuid
from types import SimpleNamespace

import pytest
from scripts.corpus_bridge import semantic_catalog_evidence as semantic
from scripts.corpus_bridge.semantic_catalog_evidence import load_and_validate_evidence
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_artifact(*, opening: str = "synthetic desk request") -> dict[str, object]:
    scenarios = [{"dialog_id": 7, "length_stratum": 2, "opening": opening}]
    return {
        "schema_version": "treejar-semantic-catalog-evidence/v1",
        "catalog": {"sha256": "a" * 64, "rows": 2},
        "embedding": {
            "model": "BAAI/bge-m3",
            "revision": "b" * 40,
            "dimensions": 1024,
            "normalized": True,
        },
        "retrieval": {
            "entrypoint": "src.rag.pipeline.search_products",
            "code_sha": "c" * 64,
            "pgvector_python": "0.4.2",
            "pgvector_extension": "0.8.1",
            "distance": "cosine",
            "search_mode": "exact",
            "ann_indexes": [],
            "limit": 3,
            "query_source": "frozen_opening",
        },
        "qrels": {"sha256": "d" * 64},
        "query_set": {"sha256": _sha256_json(scenarios), "count": 1},
        "results": [
            {
                "dialog_id": 7,
                "query_sha256": hashlib.sha256(opening.encode("utf-8")).hexdigest(),
                "rows_present": True,
                "catalog_relevant": False,
                "relevant_skus": [],
                "products": [
                    {
                        "id": "00000000-0000-0000-0000-000000000002",
                        "sku": "CHAIR-2",
                        "name": "Synthetic Chair",
                        "category": "chairs",
                        "price_aed": 200.0,
                        "stock": 4,
                    },
                    {
                        "id": "00000000-0000-0000-0000-000000000001",
                        "sku": "DESK-1",
                        "name": "Synthetic Desk",
                        "category": "desks",
                        "price_aed": 500.0,
                        "stock": 3,
                    },
                ],
            }
        ],
    }


def test_validation_preserves_retrieval_order_without_inventing_relevance(
    tmp_path: pathlib.Path,
) -> None:
    """Catch bool(products) relevance and post-retrieval sorting regressions."""
    path = tmp_path / "retrieval-evidence.json"
    path.write_text(json.dumps(_valid_artifact()), encoding="utf-8")
    path.chmod(0o600)
    scenarios = [
        {"dialog_id": 7, "length_stratum": 2, "opening": "synthetic desk request"}
    ]

    evidence = load_and_validate_evidence(
        path,
        scenarios=scenarios,
        expected_catalog_sha256="a" * 64,
        expected_embedding_revision="b" * 40,
        expected_retrieval_code_sha="c" * 64,
        expected_qrels_sha256="d" * 64,
        expected_pgvector_extension="0.8.1",
    )

    assert evidence.results[0].rows_present is True
    assert evidence.results[0].catalog_relevant is False
    assert [product.sku for product in evidence.results[0].products] == [
        "CHAIR-2",
        "DESK-1",
    ]


@pytest.mark.parametrize(
    ("corruption", "message"),
    [
        ("catalog", "catalog digest mismatch"),
        ("revision", "embedding revision mismatch"),
        ("code", "retrieval code mismatch"),
        ("approximate", "retrieval must be exact"),
        ("ann", "ANN indexes are forbidden"),
        ("queries", "query-set digest mismatch"),
        ("qrels", "qrels digest mismatch"),
        ("extension", "pgvector extension version mismatch"),
        ("rows", "rows_present mismatch"),
    ],
)
def test_validation_rejects_stale_or_approximate_evidence(
    corruption: str,
    message: str,
    tmp_path: pathlib.Path,
) -> None:
    """Catch stale identity or approximate retrieval being accepted as parity."""
    artifact = _valid_artifact()
    if corruption == "catalog":
        artifact["catalog"]["sha256"] = "e" * 64
    elif corruption == "revision":
        artifact["embedding"]["revision"] = "e" * 40
    elif corruption == "code":
        artifact["retrieval"]["code_sha"] = "e" * 64
    elif corruption == "approximate":
        artifact["retrieval"]["search_mode"] = "approximate"
    elif corruption == "ann":
        artifact["retrieval"]["ann_indexes"] = ["products_embedding_hnsw"]
    elif corruption == "queries":
        artifact["query_set"]["sha256"] = "e" * 64
    elif corruption == "qrels":
        artifact["qrels"]["sha256"] = "e" * 64
    elif corruption == "extension":
        artifact["retrieval"]["pgvector_extension"] = "9.9.9"
    else:
        artifact["results"][0]["rows_present"] = False
    path = tmp_path / "retrieval-evidence.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(ValueError, match=message):
        load_and_validate_evidence(
            path,
            scenarios=[
                {
                    "dialog_id": 7,
                    "length_stratum": 2,
                    "opening": "synthetic desk request",
                }
            ],
            expected_catalog_sha256="a" * 64,
            expected_embedding_revision="b" * 40,
            expected_retrieval_code_sha="c" * 64,
            expected_qrels_sha256="d" * 64,
            expected_pgvector_extension="0.8.1",
        )


def test_validation_names_duplicate_dialog_results(
    tmp_path: pathlib.Path,
) -> None:
    """Catch one query result being replayed into two measured slots."""
    artifact = _valid_artifact()
    artifact["results"].append(dict(artifact["results"][0]))
    path = tmp_path / "retrieval-evidence.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(ValueError, match="duplicate dialog ids"):
        load_and_validate_evidence(
            path,
            scenarios=[
                {
                    "dialog_id": 7,
                    "length_stratum": 2,
                    "opening": "synthetic desk request",
                }
            ],
            expected_catalog_sha256="a" * 64,
            expected_embedding_revision="b" * 40,
            expected_retrieval_code_sha="c" * 64,
            expected_qrels_sha256="d" * 64,
            expected_pgvector_extension="0.8.1",
        )


def test_retrieval_metrics_do_not_average_away_a_forbidden_product() -> None:
    """Catch an aggregate score hiding one explicitly unsafe top-3 row."""
    raw_result = dict(_valid_artifact()["results"][0])
    raw_result["catalog_relevant"] = True
    raw_result["relevant_skus"] = ["DESK-1"]
    result = semantic.RetrievalResultEvidence.model_validate(raw_result)
    qrels = {
        "schema_version": "treejar-semantic-retrieval-qrels/v1",
        "entries": [
            {
                "dialog_id": 7,
                "relevant_skus": ["DESK-1", "DESK-2"],
                "forbidden_skus": ["CHAIR-2"],
                "require_relevant_result": True,
                "exact_sku": None,
            }
        ],
    }

    evaluation = semantic.evaluate_retrieval((result,), qrels, top_k=3)

    assert evaluation["aggregate"] == {
        "queries": 1,
        "precision_at_3": pytest.approx(1 / 3),
        "recall_at_3": pytest.approx(1 / 2),
        "ndcg_at_3": pytest.approx(0.3868528072),
    }
    assert evaluation["per_query"][0]["forbidden_skus"] == ["CHAIR-2"]
    assert evaluation["hard_failures"] == [
        "dialog 7: forbidden SKU(s) in top-3: CHAIR-2"
    ]
    assert evaluation["passed"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_producer_runs_pinned_bge_through_real_exact_pgvector_search(
    tmp_path: pathlib.Path,
) -> None:
    """Catch copied search SQL, ANN indexes, floating models, and DB residue."""
    database_url = os.getenv("SEMANTIC_EVIDENCE_DATABASE_URL")
    if not database_url:
        pytest.skip("SEMANTIC_EVIDENCE_DATABASE_URL is not configured")

    tmp_path.chmod(0o700)
    relevant_sku = "TJ-RCG5-STANDING-DESK-731"
    snapshot_path = tmp_path / "catalog-snapshot.json"
    scenarios_path = tmp_path / "scenarios.json"
    qrels_path = tmp_path / "qrels.json"
    output_path = tmp_path / "retrieval-evidence.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-semantic-catalog-snapshot/v1",
                "source": "synthetic-integration-test",
                "products": [
                    {
                        "id": str(uuid.UUID(int=1)),
                        "sku": relevant_sku,
                        "name_en": "Height adjustable standing desk",
                        "name_ar": None,
                        "description_en": "Height adjustable workstation for one person",
                        "description_ar": None,
                        "category": "Desks",
                        "subcategory": "Standing desks",
                        "price": 731.0,
                        "currency": "AED",
                        "stock": 5,
                        "is_active": True,
                    },
                    {
                        "id": str(uuid.UUID(int=2)),
                        "sku": "TJ-RCG5-CHAIR-002",
                        "name_en": "Synthetic visitor chair",
                        "name_ar": None,
                        "description_en": "Stackable chair for a waiting room",
                        "description_ar": None,
                        "category": "Chairs",
                        "subcategory": "Visitor chairs",
                        "price": 200.0,
                        "currency": "AED",
                        "stock": 4,
                        "is_active": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    scenarios = [
        {
            "dialog_id": 7001,
            "length_stratum": 1,
            "opening": "height adjustable workstation for one person",
        }
    ]
    scenarios_path.write_text(json.dumps(scenarios), encoding="utf-8")
    qrels_path.write_text(
        json.dumps(
            {
                "schema_version": "treejar-semantic-retrieval-qrels/v1",
                "entries": [
                    {
                        "dialog_id": 7001,
                        "relevant_skus": [relevant_sku],
                        "forbidden_skus": [],
                        "require_relevant_result": True,
                        "exact_sku": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    for path in (snapshot_path, scenarios_path, qrels_path):
        path.chmod(0o600)

    evidence, report = await semantic.produce_evidence(
        database_url=database_url,
        catalog_snapshot_path=snapshot_path,
        scenarios_path=scenarios_path,
        qrels_path=qrels_path,
        output_path=output_path,
        model=semantic.EMBEDDING_MODEL,
        revision="5617a9f61b028005a4858fdac845db406aefb181",
    )

    assert evidence.results[0].products[0].sku == relevant_sku
    assert evidence.retrieval.search_mode == "exact"
    assert evidence.retrieval.ann_indexes == ()
    assert report["passed"] is True
    assert output_path.stat().st_mode & 0o777 == 0o600
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            table = await connection.scalar(text("SELECT to_regclass('products')"))
        assert table is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_snapshot_capture_uses_production_normalization_and_protects_output(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch a summary-only cache or world-readable catalog export."""
    tmp_path.chmod(0o700)
    output_path = tmp_path / "catalog-snapshot.json"

    class FakeCatalogClient:
        async def __aenter__(self) -> FakeCatalogClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def iter_all_products(self, *, limit: int | None = None):
            assert limit is not None
            yield {
                "sku": "FULL-1",
                "slug": "full-product",
                "name": "Full product",
                "description": "Hydrated description required for embeddings",
                "category": "Desks",
                "price": "731.00",
                "currency": "AED",
                "stockQuantity": 5,
                "inStock": True,
            }

    monkeypatch.setattr(
        semantic,
        "TreejarCatalogClient",
        lambda: FakeCatalogClient(),
    )
    monkeypatch.setattr(
        semantic,
        "settings",
        SimpleNamespace(catalog_api_page_size=100),
    )

    snapshot, digest = await semantic.capture_catalog_snapshot(output_path)

    assert len(snapshot.products) == 1
    assert snapshot.products[0].description_en == (
        "Hydrated description required for embeddings"
    )
    assert snapshot.products[0].stock == 5
    assert len(digest) == 64
    assert output_path.stat().st_mode & 0o777 == 0o600


def test_snapshot_cli_prints_identity_without_catalog_body(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Catch protected descriptions or product names leaking through stdout."""
    tmp_path.chmod(0o700)
    output_path = tmp_path / "catalog-snapshot.json"

    class FakeCatalogClient:
        async def __aenter__(self) -> FakeCatalogClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def iter_all_products(self, *, limit: int | None = None):
            yield {
                "sku": "PRIVATE-1",
                "slug": "private-product",
                "name": "Private product body",
                "description": "Private description body",
                "price": 10,
                "currency": "AED",
                "stockQuantity": 1,
            }

    monkeypatch.setattr(semantic, "TreejarCatalogClient", lambda: FakeCatalogClient())
    monkeypatch.setattr(
        semantic, "settings", SimpleNamespace(catalog_api_page_size=100)
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "semantic_catalog_evidence.py",
            "capture-snapshot",
            "--output",
            str(output_path),
        ],
    )

    assert semantic.main() == 0

    public = json.loads(capsys.readouterr().out)
    assert public["catalog_rows"] == 1
    assert len(public["catalog_sha256"]) == 64
    assert "Private product body" not in str(public)
    assert "Private description body" not in str(public)


def test_validate_cli_checks_all_expected_identities_without_provider_work(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Catch an operator-only validation path omitting a stale identity check."""
    artifact = _valid_artifact()
    artifact["retrieval"]["code_sha"] = semantic.retrieval_contract_sha()
    evidence_path = tmp_path / "retrieval-evidence.json"
    scenarios_path = tmp_path / "scenarios.json"
    evidence_path.write_text(json.dumps(artifact), encoding="utf-8")
    scenarios_path.write_text(
        json.dumps(
            [
                {
                    "dialog_id": 7,
                    "length_stratum": 2,
                    "opening": "synthetic desk request",
                }
            ]
        ),
        encoding="utf-8",
    )
    evidence_path.chmod(0o600)
    scenarios_path.chmod(0o600)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "semantic_catalog_evidence.py",
            "validate",
            "--evidence",
            str(evidence_path),
            "--scenarios",
            str(scenarios_path),
            "--catalog-sha256",
            "a" * 64,
            "--embedding-revision",
            "b" * 40,
            "--qrels-sha256",
            "d" * 64,
            "--pgvector-extension",
            "0.8.1",
        ],
    )

    assert semantic.main() == 0

    public = json.loads(capsys.readouterr().out)
    assert public["validated"] is True
    assert public["catalog_sha256"] == "a" * 64
    assert public["qrels_sha256"] == "d" * 64
    assert "Synthetic Chair" not in str(public)
