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
    ProtectedJournalAcceptancePort,
)

from tests.e2e_acceptance_backend import build_canonical_test_registry
from tests.test_e2e_acceptance_trusted_execution import _issued_authority


def test_coordinator_is_a_dedicated_protected_core() -> None:
    assert ProductionRunCoordinator.__name__ == "ProductionRunCoordinator"


def test_protected_journal_port_persists_and_replays_exact_acceptance_event(
    tmp_path: Path,
) -> None:
    registry = build_canonical_test_registry()
    root = (tmp_path / "protected").resolve()
    authority = _issued_authority(registry, protected_root=root, run_id="port-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="port-run", authority=authority
    )
    baseline = execution.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="port-baseline",
        run_id="port-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
        causal_event_digest="a" * 64,
        observed_at=datetime.now(UTC) - timedelta(seconds=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    identity = {
        "schema_version": "noor-e2e-coordinator-journal-acceptance/v1",
        "run_id": "port-run",
        "authorization_digest": journal.authorization_digest,
        "ordinal": 1,
        "execution_id": registry.compiled_plan.execution_ids[0],
        "accepted_payload_digest": "b" * 64,
        "prior_fold_digest": "c" * 64,
    }
    event = JournalAcceptanceEvent(**identity, event_digest=_digest(identity))

    port = ProtectedJournalAcceptancePort(journal=journal)
    assert port.record_acceptance(event) == event.event_digest
    assert port.record_acceptance(event) == event.event_digest

    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=root, run_id="port-run", authority=authority
    )
    assert ProtectedJournalAcceptancePort(journal=reopened).read_acceptance(1) == event


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


def test_cli_records_fixed_29_pairs_then_closes_with_recoverable_final_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CLI accepts no caller-selected execution and resumes each close boundary."""

    from scripts import run_noor_e2e_acceptance as cli
    from scripts.e2e_acceptance.coordinator import ProtectedJournalAcceptancePort
    from scripts.e2e_acceptance.production import ProtectedRunPlan, seal_run_plan

    registry = build_canonical_test_registry()
    root = (tmp_path / "protected").resolve()
    run_id = "cli-coordinator-run"
    now = datetime.now(UTC)
    authority = _issued_authority(registry, protected_root=root, run_id=run_id, now=now)
    plan_payload = {
        "actions": [
            {
                "spec": spec.model_dump(mode="json"),
                "message_path": f"requests/{spec.action_id}.json",
            }
            for spec in authority._authorization.action_specs
        ],
        "evaluator": {"seed": 11},
    }
    execution._write_exclusive(root, "input-plan.json", plan_payload)
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id=run_id, authority=authority
    )
    plan = ProtectedRunPlan.load(root, "input-plan.json")
    seal_run_plan(journal, plan)
    journal.seal_baseline(
        execution.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="cli-coordinator-baseline",
            run_id=run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
            causal_event_digest="a" * 64,
            observed_at=now - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    coordinator = ProductionRunCoordinator(
        registry=registry,
        authorization=authority._authorization,
        protected_root=root,
        run_id=run_id,
        journal=ProtectedJournalAcceptancePort(journal=journal),
        current_time=now,
    )
    for ordinal in range(1, 30):
        _write_producer(coordinator, ordinal=ordinal, now=now)
    monkeypatch.setattr(cli, "_canonical_registry", lambda _: registry)
    args = {
        "repo_root": Path.cwd(),
        "protected_root": root,
        "run_id": run_id,
        "run_plan": "input-plan.json",
    }

    for ordinal, execution_id in enumerate(
        registry.compiled_plan.execution_ids, start=1
    ):
        result = cli._lifecycle_result(
            type("Args", (), {"command": "record-attempt", **args})()
        )
        assert result["ordinal"] == ordinal
        assert result["execution_id"] == execution_id

    with pytest.raises(Exception, match="fixed final collector pair"):
        cli._lifecycle_result(
            type("Args", (), {"command": "close-execution", **args})()
        )
    _, anchored = cli._authority_and_journal(registry, root, run_id, create=False)
    assert anchored.phase == "final_turn_anchored"
    observation = execution.ReadbackObservation.build(
        phase="final",
        collector_id="independent-readback-collector",
        source_id="cli-coordinator-final",
        run_id=run_id,
        preflight_digest=anchored.authorization.preflight_digest,
        collector_artifact_digest=anchored.authorization.readback_collector_digest,
        causal_event_digest=anchored.previous_event_digest or "b" * 64,
        observed_at=datetime.now(UTC),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    execution._write_test_final_readback_bundle(anchored, observation)

    original_seal = cli.seal_fixed_final_readback

    def crash_after_final_seal(*seal_args, **seal_kwargs):
        original_seal(*seal_args, **seal_kwargs)
        raise RuntimeError("crash after final seal")

    monkeypatch.setattr(cli, "seal_fixed_final_readback", crash_after_final_seal)
    with pytest.raises(RuntimeError, match="after final seal"):
        cli._lifecycle_result(
            type("Args", (), {"command": "close-execution", **args})()
        )
    monkeypatch.setattr(cli, "seal_fixed_final_readback", original_seal)
    _, sealed = cli._authority_and_journal(registry, root, run_id, create=False)
    assert sealed.phase == "final_readback_sealed"

    original_evaluated = execution.ProtectedExecutionJournal.mark_evaluated

    def crash_after_evaluated(self, *, evaluation_digest):
        original_evaluated(self, evaluation_digest=evaluation_digest)
        raise RuntimeError("crash after evaluated")

    monkeypatch.setattr(
        execution.ProtectedExecutionJournal, "mark_evaluated", crash_after_evaluated
    )
    with pytest.raises(RuntimeError, match="after evaluated"):
        cli._lifecycle_result(
            type("Args", (), {"command": "close-execution", **args})()
        )
    monkeypatch.setattr(
        execution.ProtectedExecutionJournal, "mark_evaluated", original_evaluated
    )
    _, evaluated = cli._authority_and_journal(registry, root, run_id, create=False)
    assert evaluated.phase == "evaluated"

    original_commit = execution.ProtectedExecutionJournal.commit_phase

    def crash_after_commit(self, *, attempt_chain_digest):
        original_commit(self, attempt_chain_digest=attempt_chain_digest)
        raise RuntimeError("crash after commit")

    monkeypatch.setattr(
        execution.ProtectedExecutionJournal, "commit_phase", crash_after_commit
    )
    with pytest.raises(RuntimeError, match="after commit"):
        cli._lifecycle_result(
            type("Args", (), {"command": "close-execution", **args})()
        )
    monkeypatch.setattr(
        execution.ProtectedExecutionJournal, "commit_phase", original_commit
    )
    _, committed = cli._authority_and_journal(registry, root, run_id, create=False)
    assert committed.phase == "attempt_committed"

    closed = cli._lifecycle_result(
        type("Args", (), {"command": "close-execution", **args})()
    )
    assert closed == {"run_id": run_id, "phase": "attempt_committed"}
    reopened = cli._lifecycle_result(
        type("Args", (), {"command": "close-execution", **args})()
    )
    assert reopened == closed
