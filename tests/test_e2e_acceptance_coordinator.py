"""Protected-production coordinator contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.coordinator import (
    CoordinatorError,
    JournalAcceptanceEvent,
    ProducerArtifact,
    ProducerReceipt,
    ProductionRunCoordinator,
)

from tests.e2e_acceptance_backend import build_canonical_test_registry
from tests.test_e2e_acceptance_trusted_execution import _issued_authority


def test_coordinator_is_a_dedicated_protected_core() -> None:
    assert ProductionRunCoordinator.__name__ == "ProductionRunCoordinator"


@dataclass
class _Journal:
    events: dict[int, JournalAcceptanceEvent] = field(default_factory=dict)
    reject: bool = False

    def record_acceptance(self, event: JournalAcceptanceEvent) -> str:
        if self.reject:
            return "0" * 64
        existing = self.events.setdefault(event.ordinal, event)
        assert existing == event
        return existing.event_digest

    def read_acceptance(self, ordinal: int) -> JournalAcceptanceEvent | None:
        return self.events.get(ordinal)


def _digest(value: object) -> str:
    return hashlib.sha256(execution._canonical_bytes(value)).hexdigest()


def _coordinator(tmp_path: Path, *, journal: _Journal | None = None):
    registry = build_canonical_test_registry()
    root = (tmp_path / "protected").resolve()
    run_id = "coordinator-run"
    now = datetime.now(UTC)
    authority = _issued_authority(
        registry, protected_root=root, run_id=run_id, now=now
    )._authorization
    sealed = {
        "schema_version": "noor-e2e-sealed-run-plan/v2",
        "actions": [],
        "evaluator": {"seed": 7},
    }
    sealed["plan_digest"] = _digest(
        {"actions": sealed["actions"], "evaluator": sealed["evaluator"]}
    )
    sealed["evaluator_digest"] = _digest(sealed["evaluator"])
    execution._write_exclusive(root / run_id, "run-plan/sealed.json", sealed)
    port = journal or _Journal()
    coordinator = ProductionRunCoordinator(
        registry=registry,
        authorization=authority,
        protected_root=root,
        run_id=run_id,
        journal=port,
        current_time=now,
    )
    return coordinator, root, now, port


def _write_producer(
    coordinator: ProductionRunCoordinator,
    *,
    ordinal: int,
    now: datetime,
    execution_id: str | None = None,
    kind: str | None = None,
    status: str = "committed",
    source_sha256: str | None = None,
    receipt_source_sha256: str | None = None,
    observed_at: datetime | None = None,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> None:
    expected_id = coordinator.registry.compiled_plan.execution_ids[ordinal - 1]
    source = {"ordinal": ordinal, "decisive": "current-run"}
    artifact = ProducerArtifact(
        schema_version="noor-e2e-coordinator-producer-artifact/v1",
        status="committed",
        registry_id=coordinator.registry.registry_id,
        run_id=coordinator.run_id,
        authorization_digest=coordinator.authorization_digest,
        sealed_plan_sha256=coordinator.sealed_plan_sha256,
        ordinal=ordinal,
        execution_id=execution_id or expected_id,
        kind=kind or coordinator._expected_kind(expected_id),
        outcome="PASS",
        producer="independent-producer",
        observed_at=observed_at or now - timedelta(seconds=1),
        source=source,
        source_sha256=_digest(source),
    ).model_dump(mode="json")
    artifact["status"] = status
    if source_sha256 is not None:
        artifact["source_sha256"] = source_sha256
    artifact_payload = execution._canonical_bytes(artifact)
    receipt = ProducerReceipt(
        schema_version="noor-e2e-coordinator-producer-receipt/v1",
        status="committed",
        registry_id=coordinator.registry.registry_id,
        run_id=coordinator.run_id,
        authorization_digest=coordinator.authorization_digest,
        ordinal=ordinal,
        execution_id=execution_id or expected_id,
        producer="independent-producer",
        artifact_sha256=hashlib.sha256(artifact_payload).hexdigest(),
        source_sha256=receipt_source_sha256 or _digest(source),
        issued_at=issued_at or now - timedelta(seconds=1),
        expires_at=expires_at or now + timedelta(minutes=5),
    ).model_dump(mode="json")
    execution._write_exclusive(
        coordinator.run_root,
        coordinator.producer_artifact_path(ordinal),
        artifact,
    )
    execution._write_exclusive(
        coordinator.run_root,
        coordinator.producer_receipt_path(ordinal),
        receipt,
    )


def test_coordinator_accepts_exact_20_plus_9_order_and_recovers_idempotently(
    tmp_path: Path,
) -> None:
    coordinator, root, now, journal = _coordinator(tmp_path)
    assert len(coordinator.registry.compiled_plan.execution_ids) == 29
    assert (
        sum(
            execution_id in coordinator.registry.compiled_policy.scenarios
            for execution_id in coordinator.registry.compiled_plan.execution_ids
        )
        == 20
    )
    assert (
        sum(
            execution_id in coordinator.registry.compiled_policy.evidence_blocks
            for execution_id in coordinator.registry.compiled_plan.execution_ids
        )
        == 9
    )
    for ordinal in range(1, 30):
        _write_producer(coordinator, ordinal=ordinal, now=now)

    accepted = coordinator.accept_available()
    result = coordinator.finalize()

    assert [item.artifact.execution_id for item in accepted] == list(
        coordinator.registry.compiled_plan.execution_ids
    )
    assert sorted(journal.events) == list(range(1, 30))
    resolver = coordinator.decisive_evidence()
    assert len(resolver.digests) == 29
    assert resolver.resolve(resolver.digests[0]) == {
        "ordinal": 1,
        "decisive": "current-run",
    }
    assert len(result.evaluation.criteria) == 30
    assert coordinator.finalize() == result

    recovered = ProductionRunCoordinator(
        registry=coordinator.registry,
        authorization=coordinator.authorization,
        protected_root=root,
        run_id=coordinator.run_id,
        journal=journal,
        current_time=now,
    )
    assert recovered.accept_available() == accepted
    assert recovered.finalize() == result


@pytest.mark.parametrize(
    ("variant", "kwargs"),
    (
        ("wrong_execution", {"execution_id": "SC-NOT-CANONICAL"}),
        ("wrong_kind", {"kind": "evidence_block"}),
        ("aborted", {"status": "aborted"}),
        ("source_tamper", {"source_sha256": "0" * 64}),
        ("receipt_tamper", {"receipt_source_sha256": "0" * 64}),
        (
            "artifact_too_old_at_acceptance",
            {
                "observed_at": datetime.now(UTC) - timedelta(minutes=16),
                "expires_at": datetime.now(UTC) + timedelta(minutes=5),
            },
        ),
        (
            "receipt_expired_at_acceptance",
            {
                "observed_at": datetime.now(UTC) - timedelta(minutes=2),
                "issued_at": datetime.now(UTC) - timedelta(minutes=2),
                "expires_at": datetime.now(UTC) - timedelta(minutes=1),
            },
        ),
    ),
)
def test_coordinator_fails_closed_on_invalid_next_producer_boundary(
    tmp_path: Path,
    variant: str,
    kwargs: dict[str, object],
) -> None:
    coordinator, _, now, _ = _coordinator(tmp_path)
    _write_producer(coordinator, ordinal=1, now=now, **kwargs)

    with pytest.raises(CoordinatorError, match="producer"):
        coordinator.accept_next()


def test_coordinator_rejects_missing_out_of_order_and_extra_producer_paths(
    tmp_path: Path,
) -> None:
    coordinator, _, now, _ = _coordinator(tmp_path)
    _write_producer(coordinator, ordinal=2, now=now)

    assert coordinator.accept_available() == ()
    with pytest.raises(CoordinatorError, match="exactly 29"):
        coordinator.finalize()

    _write_producer(coordinator, ordinal=1, now=now)
    execution._write_exclusive(
        coordinator.run_root,
        "producer-artifacts/duplicate.json",
        {"unexpected": True},
    )
    with pytest.raises(CoordinatorError, match="extra"):
        coordinator.accept_next()


def test_coordinator_rejects_journal_event_digest_drift(tmp_path: Path) -> None:
    journal = _Journal(reject=True)
    coordinator, _, now, _ = _coordinator(tmp_path, journal=journal)
    _write_producer(coordinator, ordinal=1, now=now)

    with pytest.raises(CoordinatorError, match="journal acceptance"):
        coordinator.accept_next()


def test_coordinator_reopen_rejects_missing_durable_journal_event(
    tmp_path: Path,
) -> None:
    coordinator, root, now, journal = _coordinator(tmp_path)
    _write_producer(coordinator, ordinal=1, now=now)
    coordinator.accept_next()
    journal.events.clear()

    recovered = ProductionRunCoordinator(
        registry=coordinator.registry,
        authorization=coordinator.authorization,
        protected_root=root,
        run_id=coordinator.run_id,
        journal=journal,
        current_time=now,
    )
    with pytest.raises(CoordinatorError, match="durably bound"):
        recovered.accept_available()


def test_coordinator_allows_late_finalize_after_fresh_acceptance_and_rejects_duplicate_record(
    tmp_path: Path,
) -> None:
    coordinator, root, now, journal = _coordinator(tmp_path)
    _write_producer(coordinator, ordinal=1, now=now)
    coordinator.accept_next()
    first = execution._read_protected(
        coordinator.run_root, coordinator.accepted_record_path(1)
    )
    execution._write_exclusive(
        coordinator.run_root, coordinator.accepted_record_path(2), json.loads(first)
    )
    with pytest.raises(CoordinatorError, match="binding drift"):
        coordinator.finalize()

    # Freshness is checked at acceptance.  Once the durable acceptance record
    # and its journal event are bound, later finalization must recover safely.
    clean, clean_root, clean_now, clean_journal = _coordinator(tmp_path / "clean")
    for ordinal in range(1, 30):
        _write_producer(
            clean,
            ordinal=ordinal,
            now=clean_now,
            expires_at=clean_now + timedelta(minutes=1),
        )
    clean.accept_available()
    expected = clean.finalize()
    late = ProductionRunCoordinator(
        registry=clean.registry,
        authorization=clean.authorization,
        protected_root=clean_root,
        run_id=clean.run_id,
        journal=clean_journal,
        current_time=clean_now + timedelta(minutes=2),
    )
    assert late.finalize() == expected
