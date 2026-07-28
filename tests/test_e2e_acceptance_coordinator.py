"""Protected-production coordinator contracts."""

from __future__ import annotations

import hashlib
import json
import shutil
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

from tests.e2e_acceptance_backend import (
    build_canonical_test_registry,
    build_test_registry,
)
from tests.test_e2e_acceptance_trusted_execution import (
    _authority_bundle_inputs,
    _issued_authority,
)


def test_coordinator_is_a_dedicated_protected_core() -> None:
    assert ProductionRunCoordinator.__name__ == "ProductionRunCoordinator"


def test_production_authority_bundle_commit_is_validated_idempotent_and_issuable(
    tmp_path: Path,
) -> None:
    source_registry = build_canonical_test_registry()
    project_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    for relative in (
        ".codex/goals/tj-ee5f/scope-criterion-snapshot.json",
        ".codex/goals/tj-ee5f/scope-source-provenance.json",
        ".codex/stages/tj-ee5f/traceability-manifest.json",
        ".codex/stages/tj-ee5f/scenario-set.json",
        ".codex/stages/tj-ee5f/authorization-manifest.example.json",
    ):
        destination = repo_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project_root / relative, destination)
    (repo_root / ".git").mkdir()
    registry = build_test_registry(repo_root, source_registry.compiled_policy)
    root = (tmp_path / "protected").resolve()
    run_id = "production-authority-commit"
    now = datetime.now(UTC)
    inputs = _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id=run_id,
        now=now,
    )
    published_protected = (
        registry.repo_root
        / ".git"
        / "codex-orchestration"
        / "noor-e2e-acceptance"
        / "published-runs"
        / run_id
    )
    published_tracked = (
        registry.repo_root / ".codex" / "stages" / "tj-ee5f" / "results" / run_id
    )
    inputs["store_ids"] = inputs["store_ids"].model_copy(
        update={
            "raw_root_digest": execution.store_root_digest(published_protected),
            "tracked_root_digest": execution.store_root_digest(published_tracked),
            "anchor_root_digest": execution.store_root_digest(published_protected),
        }
    )

    receipt = execution.commit_execution_authority_bundle(**inputs)
    assert execution.commit_execution_authority_bundle(**inputs) == receipt
    handle = execution.issue_execution_authorization_handle(
        registry=registry,
        protected_root=root,
        run_id=run_id,
        current_time=now,
    )
    assert handle._authorization.registry_id == registry.registry_id

    drifted = dict(inputs)
    drifted["collector_ids"] = inputs["collector_ids"].model_copy(
        update={"values": ("different-collector",)}
    )
    with pytest.raises(Exception, match="semantic|collector|replay|binding"):
        execution.commit_execution_authority_bundle(**drifted)


def test_protected_journal_port_persists_and_replays_exact_acceptance_event(
    tmp_path: Path,
) -> None:
    source_registry = build_canonical_test_registry()
    project_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    for relative in (
        ".codex/goals/tj-ee5f/scope-criterion-snapshot.json",
        ".codex/goals/tj-ee5f/scope-source-provenance.json",
        ".codex/stages/tj-ee5f/traceability-manifest.json",
        ".codex/stages/tj-ee5f/scenario-set.json",
        ".codex/stages/tj-ee5f/authorization-manifest.example.json",
    ):
        destination = repo_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project_root / relative, destination)
    (repo_root / ".git").mkdir()
    registry = build_test_registry(repo_root, source_registry.compiled_policy)
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
    producer_id: str | None = None,
) -> None:
    expected_id = coordinator.registry.compiled_plan.execution_ids[ordinal - 1]
    expected_kind = kind or coordinator._expected_kind(expected_id)
    attempt_ref = f"attempt:{expected_id}"
    source = {
        "schema_version": (
            "noor-e2e-scenario-publication-source/v1"
            if expected_kind == "scenario"
            else "noor-e2e-evidence-block-publication-source/v1"
        ),
        "kind": expected_kind,
        "execution": {
            "attempt_ref": attempt_ref,
            "evidence_refs": [attempt_ref],
        },
        "evidence": [
            {
                "evidence_id": attempt_ref,
                "producer": "protected-attempt-committer",
                "payload": {
                    "execution_id": expected_id,
                    "ordinal": ordinal,
                    "decisive": "current-run",
                },
            }
        ],
    }
    if expected_kind == "scenario":
        source["turns"] = [
            {
                "execution_id": execution_id or expected_id,
                "attempt_id": f"attempt-{ordinal}",
                "turn_id": f"turn-{ordinal}",
            }
        ]
    producer = producer_id or (
        coordinator.authorization.adapter_ids[0]
        if expected_kind == "scenario"
        else coordinator.authorization.collector_ids[0]
    )
    artifact = ProducerArtifact(
        schema_version="noor-e2e-coordinator-producer-artifact/v1",
        status="committed",
        registry_id=coordinator.registry.registry_id,
        run_id=coordinator.run_id,
        authorization_digest=coordinator.authorization_digest,
        sealed_plan_sha256=coordinator.sealed_plan_sha256,
        ordinal=ordinal,
        execution_id=execution_id or expected_id,
        kind=expected_kind,
        outcome="PASS",
        producer=producer,
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
        producer=producer,
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
    assert resolver.resolve(resolver.digests[0])["kind"] == "scenario"
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
        ("unauthorized_producer", {"producer_id": "unauthorized-producer"}),
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
    from scripts.e2e_acceptance.manifest import load_authorization_manifest
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
        ProtectedRunPlan,
        commit_execution_unit_source,
    )
    from scripts.e2e_acceptance.schemas import PreflightReadbackIdentity
    from scripts.e2e_acceptance.trusted_run import TurnReport

    source_registry = build_canonical_test_registry()
    project_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    for relative in (
        ".codex/goals/tj-ee5f/scope-criterion-snapshot.json",
        ".codex/goals/tj-ee5f/scope-source-provenance.json",
        ".codex/stages/tj-ee5f/traceability-manifest.json",
        ".codex/stages/tj-ee5f/scenario-set.json",
        ".codex/stages/tj-ee5f/authorization-manifest.example.json",
    ):
        destination = repo_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project_root / relative, destination)
    (repo_root / ".git").mkdir()
    registry = build_test_registry(repo_root, source_registry.compiled_policy)
    root = (tmp_path / "protected").resolve()
    run_id = "cli-coordinator-run"
    now = datetime.now(UTC)
    draft = load_authorization_manifest(
        project_root / ".codex/stages/tj-ee5f/authorization-manifest.example.json"
    )
    scenario_set = json.loads(
        (project_root / ".codex/stages/tj-ee5f/scenario-set.json").read_text(
            encoding="utf-8"
        )
    )
    scenario_binding = draft.scenario_binding.model_copy(
        update={
            "scenario_ids": [item["scenario_id"] for item in scenario_set["scenarios"]],
            "evidence_block_ids": [
                item["block_id"] for item in scenario_set["evidence_blocks"]
            ],
            "executable_input_digests": {
                identity: "0" * 64 for identity in registry.compiled_plan.execution_ids
            },
        }
    )
    v1_quotas = draft.quotas.model_copy(
        update={
            "max_scenarios": 29,
            "max_messages": 2,
            "max_model_calls": 2,
            "max_cost_usd": 1.0,
            "subsystem_quotas": {"outbound_text": 2},
        }
    )
    authorization_v1 = type(draft).model_validate(
        draft.model_copy(
            update={
                "authorization_id": "production-fake-authority",
                "status": type(draft.status).APPROVED,
                "issuer": "production-fake-upstream",
                "issued_at": now - timedelta(minutes=2),
                "expires_at": now + timedelta(hours=1),
                "allowed_executor": "production-fake-executor",
                "allowed_source": "production-fake-source",
                "expected_identity": draft.expected_identity.model_copy(
                    update={
                        "repository_commit": "1" * 40,
                        "deployed_release_sha": "2" * 40,
                        "ci_run_id": "production-fake-ci",
                        "app_version": "production-fake-app",
                        "migration_head": "production-fake-migration",
                        "main_model": "production/fake-main",
                        "fast_model": "production/fake-fast",
                    }
                ),
                "targets": draft.targets.model_copy(
                    update={
                        "recipient": "production-fake-recipient",
                        "wazzup_channel": "production-fake-channel",
                        "telegram_target": "production-fake-telegram",
                        "synthetic_suffix": "production-fake-suffix",
                    }
                ),
                "quotas": v1_quotas,
                "permissions": ["fixture:execute"],
                "callback_types": ["production-fake-callback"],
                "test_data_identities": ["production-fake-test-data"],
                "cleanup_method": "production-fake-cleanup",
                "readbacks": ["production-fake-readback"],
                "stop_conditions": ["production-fake-stop"],
                "scenario_binding": scenario_binding,
            }
        ).model_dump(mode="json")
    )
    preflight_request = execution.PreflightRequest(
        quotas=authorization_v1.quotas,
        permissions=authorization_v1.permissions,
        callback_types=authorization_v1.callback_types,
        test_data_identities=authorization_v1.test_data_identities,
        cleanup_method=authorization_v1.cleanup_method,
        readbacks=authorization_v1.readbacks,
        stop_conditions=authorization_v1.stop_conditions,
        scenario_binding=authorization_v1.scenario_binding,
    )
    preflight_observation = execution.PreflightObservation(
        identity=authorization_v1.expected_identity,
        targets=authorization_v1.targets,
        executor=authorization_v1.allowed_executor,
        source=authorization_v1.allowed_source,
        readback_identity=PreflightReadbackIdentity(
            source_id="production-fake-preflight",
            observed_at=now - timedelta(seconds=30),
            content_digest="7" * 64,
        ),
    )
    action_specs = execution.AuthorizedActionSpecs(
        schema_version="noor-e2e-authorized-action-specs/v2",
        specs=(
            execution.AuthorizedActionSpec(
                action_id="production-fake-action",
                execution_id=registry.compiled_plan.execution_ids[0],
                step_id="production-fake-step",
                capability="outbound_text",
                operation_permission="fixture:execute",
                adapter_id="fake-local-adapter",
                subsystem="outbound_text",
                destination_digest="a" * 64,
                payload_digest="b" * 64,
                idempotency_key="production-fake-idempotency",
                capability_units={"outbound_text": 1},
                quota_charge=execution.AuthorizedQuotaCharge(
                    messages=1,
                    model_calls=1,
                    max_cost_usd=0.25,
                    cost_settlement="bounded_actual",
                ),
            ),
        ),
    )
    published_protected = (
        registry.repo_root
        / ".git"
        / "codex-orchestration"
        / "noor-e2e-acceptance"
        / "published-runs"
        / run_id
    )
    published_tracked = (
        registry.repo_root / ".codex" / "stages" / "tj-ee5f" / "results" / run_id
    )
    stores = execution.StoreIdentities(
        raw_store_id="production-fake-raw",
        tracked_store_id="production-fake-tracked",
        anchor_store_id="production-fake-anchor",
        raw_root_digest=execution.store_root_digest(published_protected),
        tracked_root_digest=execution.store_root_digest(published_tracked),
        anchor_root_digest=execution.store_root_digest(published_protected),
    )
    execution_authorities = execution.ProtectedExecutionAuthorities(
        schema_version="noor-e2e-protected-execution-authorities/v2",
        client_exclusions=(),
        side_effect_authority=execution.SideEffectAuthority(
            issuer="protected-side-effect-authority",
            cleanup_owner=authorization_v1.allowed_executor,
            cleanup_authority=authorization_v1.cleanup_method,
        ),
    )
    execution.commit_execution_authority_bundle(
        registry=registry,
        protected_root=root,
        run_id=run_id,
        authorization=authorization_v1,
        request=preflight_request,
        observation=preflight_observation,
        action_specs=action_specs,
        store_ids=stores,
        adapter_ids=execution.AuthorityAdapterIds(
            schema_version="noor-e2e-authority-adapter-ids/v2",
            values=("fake-local-adapter",),
        ),
        collector_ids=execution.AuthorityCollectorIds(
            schema_version="noor-e2e-authority-collector-ids/v2",
            values=("independent-readback-collector",),
        ),
        task1_bindings=execution.Task1AuthorityBindings(
            schema_version="noor-e2e-task1-authority-bindings/v2",
            authorization_digest=registry.task1_authorization_digest,
            input_digests=registry.task1_input_digests,
        ),
        execution_authorities=execution_authorities,
        receipt_issued_at=now - timedelta(seconds=1),
        receipt_expires_at=now + timedelta(minutes=5),
    )
    authority = execution.issue_execution_authorization_handle(
        registry=registry,
        protected_root=root,
        run_id=run_id,
        current_time=now,
    )
    plan_payload = {
        "actions": [
            {
                "spec": spec.model_dump(mode="json"),
                "message_path": f"requests/{spec.action_id}.json",
            }
            for spec in authority._authorization.action_specs
        ],
        "evaluator": {
            "publication": {
                "schema_version": "noor-e2e-publication-metadata/v1",
                "title": "Приёмочное тестирование Noor",
                "tester": {
                    "model": "production/fake-tester",
                    "reasoning_effort": "none",
                    "seed": 11,
                    "config_digest": "3" * 64,
                    "evidence_refs": ["report-source"],
                },
                "judge": {
                    "model": "production/fake-judge",
                    "reasoning_effort": "none",
                    "seed": 11,
                    "config_digest": "4" * 64,
                    "evidence_refs": ["report-source"],
                },
                "limitations": ["Local deterministic fake production flow."],
                "external_gates": [],
            }
        },
    }
    execution._write_exclusive(root, "input-plan.json", plan_payload)
    monkeypatch.setattr(cli, "_canonical_registry", lambda _: registry)
    args = {
        "repo_root": Path.cwd(),
        "protected_root": root,
        "run_id": run_id,
        "run_plan": "input-plan.json",
    }
    cli._lifecycle_result(type("Args", (), {"command": "prepare", **args})())
    _, journal = cli._authority_and_journal(registry, root, run_id, create=False)
    plan = ProtectedRunPlan.load(root, "input-plan.json")
    collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={
                "inventory": b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
            }
        ),
        source_name="inventory",
    )
    collector.seal_baseline(
        journal,
        source_id="cli-coordinator-baseline",
        observed_at=now - timedelta(seconds=1),
    )
    cli._lifecycle_result(
        type(
            "Args",
            (),
            {
                "command": "preflight",
                "repo_root": Path.cwd(),
                "protected_root": root,
                "run_id": run_id,
                "baseline": "collector-artifacts/baseline-readback.json",
            },
        )()
    )
    _, journal = cli._authority_and_journal(registry, root, run_id, create=False)
    journal.begin_execution()
    coordinator = ProductionRunCoordinator(
        registry=registry,
        authorization=authority._authorization,
        protected_root=root,
        run_id=run_id,
        journal=ProtectedJournalAcceptancePort(journal=journal),
        current_time=now,
    )
    transcript_manifest = []
    for ordinal in range(1, 30):
        execution_id = registry.compiled_plan.execution_ids[ordinal - 1]
        kind = coordinator._expected_kind(execution_id)
        if ordinal == 1:
            missing_attempt_ref = f"attempt:{execution_id}"
            with pytest.raises(Exception, match="attempt commit|unavailable"):
                commit_execution_unit_source(
                    registry=registry,
                    journal=journal,
                    sealed_plan=plan,
                    ordinal=ordinal,
                    outcome="PASS",
                    source={
                        "schema_version": "noor-e2e-scenario-publication-source/v1",
                        "kind": "scenario",
                        "execution": {
                            "attempt_ref": missing_attempt_ref,
                            "evidence_refs": ["fresh"],
                        },
                        "evidence": [
                            {
                                "evidence_id": missing_attempt_ref,
                                "producer": "protected-attempt-committer",
                                "payload": {
                                    "schema_version": "noor-e2e-committed-execution/v2",
                                    "execution_id": execution_id,
                                    "protected_commit_ref": "missing/commit.json",
                                },
                            }
                        ],
                        "turns": [
                            {
                                "execution_id": execution_id,
                                "attempt_id": "missing",
                                "turn_id": "missing",
                            }
                        ],
                    },
                    observed_at=now - timedelta(milliseconds=100),
                )
            assert not (
                coordinator.run_root / coordinator.producer_artifact_path(ordinal)
            ).exists()
        attempt_digest = _digest(
            {"run_id": run_id, "execution_id": execution_id, "ordinal": ordinal}
        )
        semantic_digest = _digest({"execution_id": execution_id, "outcome": "PASS"})
        raw_digest = _digest({"execution_id": execution_id, "store": "raw"})
        tracked_digest = _digest({"execution_id": execution_id, "store": "tracked"})
        protected_commit_ref = f"attempts/{execution_id.lower()}/commit.json"
        protected_commit = {
            "schema_version": "noor-e2e-attempt-commit/v2",
            "status": "committed",
            "run_id": run_id,
            "execution_id": execution_id,
            "attempt_kind": "executed",
            "attempt_digest": attempt_digest,
            "authorization_digest": coordinator.authorization_digest,
            "semantic_digest": semantic_digest,
            "raw_digest": raw_digest,
            "tracked_digest": tracked_digest,
            "gate_attempt_digest": None,
        }
        protected_commit_digest = execution._write_exclusive(
            coordinator.run_root, protected_commit_ref, protected_commit
        )
        previous = None
        phase_chain = []
        for cursor, phase in enumerate(
            (
                "prepared",
                "baseline_sealed",
                "executing",
                "final_turn_anchored",
                "final_readback_sealed",
                "evaluated",
                "attempt_committed",
            ),
            start=1,
        ):
            phase_identity = {
                "cursor": cursor,
                "phase": phase,
                "previous_event_digest": previous,
                "run_id": run_id,
                "execution_id": execution_id,
                "attempt_digest": attempt_digest,
                "semantic_digest": semantic_digest,
                "authorization_digest": coordinator.authorization_digest,
                "protected_commit_digest": protected_commit_digest,
            }
            previous = _digest(phase_identity)
            phase_chain.append(
                {
                    "cursor": cursor,
                    "phase": phase,
                    "previous_event_digest": phase_identity["previous_event_digest"],
                    "event_digest": previous,
                }
            )
        attempt_ref = f"attempt:{execution_id}"
        committed_attempt = {
            "schema_version": "noor-e2e-committed-execution/v2",
            "run_id": run_id,
            "execution_id": execution_id,
            "outcome": "PASS",
            "attempt_kind": "executed",
            "gate_attempt": None,
            "authorization_digest": coordinator.authorization_digest,
            "attempt_digest": attempt_digest,
            "semantic_digest": semantic_digest,
            "registry_id": registry.registry_id,
            "protected_commit_ref": protected_commit_ref,
            "protected_commit_digest": protected_commit_digest,
            "raw_digest": raw_digest,
            "tracked_digest": tracked_digest,
            "phase_head_digest": previous,
            "phase_chain": phase_chain,
            "evidence_refs": ["fresh"],
        }
        unit_evidence = [
            {
                "evidence_id": attempt_ref,
                "producer": "protected-attempt-committer",
                "payload": committed_attempt,
            }
        ]
        if ordinal == 1:
            unit_evidence.extend(
                (
                    {
                        "evidence_id": "fresh",
                        "producer": "independent-fake-evaluator",
                        "payload": {
                            "status": "passed",
                            "freshness_identity": {"run_id": run_id},
                        },
                    },
                    {
                        "evidence_id": "reuse",
                        "producer": "independent-fake-evaluator",
                        "payload": {
                            "status": "passed",
                            "reused_exact_identity": {"run_id": run_id},
                        },
                    },
                    {
                        "evidence_id": "gate",
                        "producer": "independent-fake-evaluator",
                        "payload": {
                            "status": "passed",
                            "external_gate_resolution": "implemented",
                        },
                    },
                )
            )
        source = {
            "schema_version": (
                "noor-e2e-scenario-publication-source/v1"
                if kind == "scenario"
                else "noor-e2e-evidence-block-publication-source/v1"
            ),
            "kind": kind,
            "execution": {
                "attempt_ref": attempt_ref,
                "evidence_refs": ["fresh"],
            },
            "evidence": unit_evidence,
        }
        if kind == "scenario":
            attempt_id = f"attempt:{execution_id}"
            turn_id = f"turn-{ordinal:03d}"
            turn = {
                "execution_id": execution_id,
                "attempt_id": attempt_id,
                "turn_id": turn_id,
                "question": f"Deterministic question {ordinal}.",
                "answer": f"Deterministic answer {ordinal}.",
                "sent_at": (now - timedelta(milliseconds=800)).isoformat(),
                "received_at": (now - timedelta(milliseconds=700)).isoformat(),
                "first_visible_at": (now - timedelta(milliseconds=600)).isoformat(),
                "final_visible_at": (now - timedelta(milliseconds=500)).isoformat(),
                "delivered_at": (now - timedelta(milliseconds=400)).isoformat(),
                "conversation_id": f"conversation-{ordinal}",
                "message_id": f"message-{ordinal}",
                "provider_message_id": f"provider-{ordinal}",
                "model": "production/fake-main",
                "tools": ["fake_tool"],
                "tool_outcomes": ["passed"],
                "audit_ids": [f"audit-{ordinal}"],
                "media_refs": [],
                "token_count": 10,
                "cost_usd": 0.0,
                "deviation": None,
                "evaluator_reasoning": "Protected deterministic checks passed.",
                "evidence_refs": [attempt_ref, "fresh"],
            }
            transcript = {
                "schema_version": "noor-e2e-protected-transcript/v2",
                "registry_id": registry.registry_id,
                "run_id": run_id,
                "execution_id": execution_id,
                "attempt_id": attempt_id,
                "turn_id": turn_id,
                "turn": TurnReport.model_validate(
                    {
                        **turn,
                        "transcript_digest": "0" * 64,
                        "producer_receipt_digest": "0" * 64,
                    }
                ).model_dump(
                    mode="json",
                    exclude={"transcript_digest", "producer_receipt_digest"},
                ),
            }
            transcript_digest = execution._write_exclusive(
                coordinator.run_root,
                f"transcripts/{execution_id}/{attempt_id}/{turn_id}.json",
                transcript,
            )
            transcript_receipt = {
                "schema_version": "noor-e2e-transcript-producer-receipt/v2",
                "registry_id": registry.registry_id,
                "run_id": run_id,
                "execution_id": execution_id,
                "attempt_id": attempt_id,
                "turn_id": turn_id,
                "transcript_sha256": transcript_digest,
                "authorization_digest": coordinator.authorization_digest,
                "attempt_digest": attempt_digest,
                "attempt_phase_head_digest": previous,
            }
            transcript_receipt_digest = execution._write_exclusive(
                coordinator.run_root,
                (
                    f"producer-receipts/transcripts/{execution_id}/"
                    f"{attempt_id}/{turn_id}.json"
                ),
                transcript_receipt,
            )
            turn.update(
                transcript_digest=transcript_digest,
                producer_receipt_digest=transcript_receipt_digest,
            )
            source["turns"] = [turn]
            source["side_effect_dispositions"] = []
            transcript_manifest.append(
                [
                    execution_id,
                    attempt_id,
                    turn_id,
                    transcript_digest,
                    transcript_receipt_digest,
                ]
            )
        commit_execution_unit_source(
            registry=registry,
            journal=journal,
            sealed_plan=plan,
            ordinal=ordinal,
            outcome="PASS",
            source=source,
            observed_at=now - timedelta(milliseconds=100),
        )
    execution._write_exclusive(
        coordinator.run_root,
        "transcripts/manifest.json",
        {
            "schema_version": "noor-e2e-protected-transcript-manifest/v2",
            "registry_id": registry.registry_id,
            "run_id": run_id,
            "ordered_turns": transcript_manifest,
        },
    )
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
    final_collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={
                "inventory": b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
            }
        ),
        source_name="inventory",
    )
    final_collector.commit_final_pair(
        anchored,
        source_id="cli-coordinator-final",
        observed_at=datetime.now(UTC),
    )

    closed = cli._lifecycle_result(
        type("Args", (), {"command": "close-execution", **args})()
    )
    assert closed == {"run_id": run_id, "phase": "attempt_committed"}
    reopened = cli._lifecycle_result(
        type("Args", (), {"command": "close-execution", **args})()
    )
    assert reopened == closed
    tracked_candidate = (
        registry.repo_root
        / ".codex"
        / "stages"
        / "tj-ee5f"
        / "results"
        / run_id
        / "registry"
    )
    tracked_candidate.mkdir(parents=True)
    for name in ("run.json", "evidence-index.json", "report-payload.json"):
        (tracked_candidate / name).write_text(
            '{"forged":"tracked-candidate"}\n', encoding="utf-8"
        )

    finalized = cli._lifecycle_result(
        type("Args", (), {"command": "finalize", **args})()
    )
    assert finalized == {"run_id": run_id, "finalized": True}
    published = json.loads((tracked_candidate / "run.json").read_text(encoding="utf-8"))
    assert "forged" not in published

    report_output = tmp_path / "verified-report.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_noor_e2e_acceptance.py",
            "verify-run",
            "--repo-root",
            str(registry.repo_root),
            "--run-id",
            run_id,
            "--report-output",
            str(report_output),
        ],
    )
    assert cli.main() == 0
    assert report_output.is_file()
