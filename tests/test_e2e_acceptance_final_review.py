"""RED reproductions for final trusted-run and generic-runner review findings."""

from __future__ import annotations

import hashlib
import inspect
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_e2e_acceptance_trusted_execution import (
    _issued_authority,
    _registry,
)
from tests.test_e2e_acceptance_trusted_report import (
    PROJECT_ROOT,
    _build_verified_run,
    _modules,
    _write_json,
)

EVIDENCE_BLOCK_IDS = tuple(
    item["block_id"]
    for item in json.loads(
        (PROJECT_ROOT / ".codex/stages/tj-ee5f/scenario-set.json").read_text(
            encoding="utf-8"
        )
    )["evidence_blocks"]
)


def test_snapshot_writer_rejects_intermediate_symlink_without_external_write(
    tmp_path: Path,
) -> None:
    """Creating a snapshot must not traverse a symlink below its operator root."""

    _, _, trusted = _modules()
    operator_root = tmp_path / "operator"
    outside = tmp_path / "outside"
    operator_root.mkdir()
    outside.mkdir()
    (operator_root / "execution-snapshots").symlink_to(
        outside, target_is_directory=True
    )

    with pytest.raises(Exception, match="no-follow|snapshot root|protected"):
        trusted._write_snapshot_tree(
            operator_root / "execution-snapshots" / "synthetic-run",
            {"snapshot.json": {"status": "committed"}},
        )

    assert not (outside / "synthetic-run").exists()


def _stage_protected_execution_snapshot(
    registry,
    tracked: Path,
    protected: Path,
    *,
    report_mutation=None,
) -> None:
    _, _, trusted = _modules()
    run_id = "synthetic-trusted-run"
    index = json.loads(
        (tracked / "registry/evidence-index.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (tracked / "registry/report-payload.json").read_text(encoding="utf-8")
    )
    if report_mutation is not None:
        report_mutation(report)
    evidence = []
    attempt_commits = {}
    transcript_artifacts = {
        path.relative_to(protected).as_posix(): json.loads(
            path.read_text(encoding="utf-8")
        )
        for parent in (
            protected / "transcripts",
            protected / "producer-receipts" / "transcripts",
        )
        if parent.exists()
        for path in parent.rglob("*.json")
    }
    collector_artifacts = {
        relative: json.loads((protected / relative).read_text(encoding="utf-8"))
        for relative in (
            "collector-artifacts/final-readback.json",
            "producer-receipts/final-readback.json",
        )
    }
    for entry in index["entries"]:
        payload = json.loads(
            (tracked / entry["relative_path"]).read_text(encoding="utf-8")
        )
        evidence.append(
            {
                "evidence_id": entry["evidence_id"],
                "relative_path": entry["relative_path"],
                "producer": entry["producer"],
                "payload": payload,
            }
        )
        if entry["producer"] == "protected-attempt-committer":
            attempt_commits[payload["execution_id"]] = json.loads(
                (protected / payload["protected_commit_ref"]).read_text(
                    encoding="utf-8"
                )
            )
    snapshot_identity = {
        # Frozen pre-production fixture: compatibility is explicit and cannot
        # be emitted by the v2 production materializer.
        "schema_version": "noor-e2e-protected-execution-snapshot/v1",
        "run_id": run_id,
        "registry_id": registry.registry_id,
        "execution_ids": list(registry.compiled_plan.execution_ids),
        "run": json.loads((tracked / "registry/run.json").read_text(encoding="utf-8")),
        "report": report,
        "evidence": evidence,
        "attempt_commits": attempt_commits,
        "transcript_artifacts": transcript_artifacts,
        "collector_artifacts": collector_artifacts,
        "gate_artifacts": {},
    }
    snapshot = {
        **snapshot_identity,
        "snapshot_digest": trusted.canonical_digest(snapshot_identity),
    }
    source_root = trusted._execution_snapshot_root(registry) / run_id
    snapshot_sha256 = _write_json(source_root / "snapshot.json", snapshot)
    attempt_chain_heads = {
        record["payload"]["execution_id"]: record["payload"]["phase_head_digest"]
        for record in evidence
        if record["producer"] == "protected-attempt-committer"
    }
    _write_json(
        source_root / "commit.json",
        {
            "schema_version": "noor-e2e-protected-execution-snapshot-commit/v1",
            "status": "committed",
            "run_id": run_id,
            "registry_id": registry.registry_id,
            "snapshot_sha256": snapshot_sha256,
            "snapshot_digest": snapshot["snapshot_digest"],
            "authorization_digest": trusted.canonical_digest(
                snapshot["run"]["authorization"]
            ),
            "journal_head_digest": snapshot["run"]["final"]["causal_event_digest"],
            "attempt_chain_heads_digest": trusted.canonical_digest(attempt_chain_heads),
            "operator_store_digest": trusted.store_root_digest(
                trusted._operator_root(registry)
            ),
            "final_readback_receipt_digest": hashlib.sha256(
                (protected / "producer-receipts/final-readback.json").read_bytes()
            ).hexdigest(),
            "final_inventory_digest": snapshot["run"]["final_inventory_digest"],
        },
    )


def _promote_fixture_snapshot_to_production_v2(
    registry, run_id: str
) -> tuple[Path, Path]:
    """Convert only a fixture copy into the explicit strict production shape."""

    _, _, trusted = _modules()
    source_root = trusted._execution_snapshot_root(registry) / run_id
    snapshot_path = source_root / "snapshot.json"
    commit_path = source_root / "commit.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    causal_head = snapshot["run"]["final"]["causal_event_digest"]
    terminal_head = "d" * 64
    evaluator = {"fixture": "sealed"}
    sealed_plan = {
        "schema_version": "noor-e2e-sealed-run-plan/v2",
        "actions": [],
        "evaluator": evaluator,
        "plan_digest": trusted.canonical_digest(
            {"actions": [], "evaluator": evaluator}
        ),
        "evaluator_digest": trusted.canonical_digest(evaluator),
    }
    snapshot.update(
        {
            "schema_version": "noor-e2e-protected-execution-snapshot/v2",
            "sealed_plan": sealed_plan,
            "evaluator": evaluator,
            "sealed_plan_digest": hashlib.sha256(
                trusted._canonical_bytes(sealed_plan)
            ).hexdigest(),
            "evaluator_digest": sealed_plan["evaluator_digest"],
            "terminal_journal_phase": "attempt_committed",
            "terminal_journal_head_digest": terminal_head,
            "final_causal_event_digest": causal_head,
        }
    )
    identity = {
        key: value for key, value in snapshot.items() if key != "snapshot_digest"
    }
    snapshot["snapshot_digest"] = trusted.canonical_digest(identity)
    snapshot_sha256 = _write_json(snapshot_path, snapshot)
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    commit.update(
        {
            "schema_version": "noor-e2e-protected-execution-snapshot-commit/v2",
            "snapshot_sha256": snapshot_sha256,
            "snapshot_digest": snapshot["snapshot_digest"],
            "sealed_plan_digest": snapshot["sealed_plan_digest"],
            "evaluator_digest": snapshot["evaluator_digest"],
            "terminal_journal_phase": "attempt_committed",
            "journal_head_digest": terminal_head,
            "terminal_journal_head_digest": terminal_head,
            "final_causal_event_digest": causal_head,
        }
    )
    _write_json(commit_path, commit)
    return snapshot_path, commit_path


def _refresh_test_publication_marker(
    registry,
    tracked: Path,
    protected: Path,
) -> None:
    _, _, trusted = _modules()
    marker_path = protected / "final-commit.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker_path.unlink()
    tracked_manifest = {
        path.relative_to(tracked).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in tracked.rglob("*.json")
    }
    protected_manifest = {
        path.relative_to(protected).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in protected.rglob("*.json")
    }
    marker["tracked_tree_digest"] = trusted.canonical_digest(tracked_manifest)
    marker["protected_tree_digest"] = trusted.canonical_digest(protected_manifest)
    _write_json(marker_path, marker)


@pytest.mark.parametrize("block_id", EVIDENCE_BLOCK_IDS)
def test_generic_runner_exposes_validation_for_every_evidence_block(
    block_id: str,
) -> None:
    _, execution, _ = _modules()

    validator = getattr(
        execution.GenericAcceptanceRunner,
        "validate_evidence_block",
        None,
    )

    assert callable(validator), f"{block_id} has no generic runner validation path"


def test_trusted_run_rejects_execution_rows_without_committed_attempt_artifacts(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        without_attempts=True,
    )

    with pytest.raises(Exception, match="attempt|commit|phase"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_trusted_report_rejects_one_turn_for_twenty_scenario_executions(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        incomplete_turns=True,
    )

    with pytest.raises(
        Exception,
        match="turn|scenario.*coverage|report.*coverage|transcript",
    ):
        registry.open_run(run_id="synthetic-trusted-run")


def test_public_open_run_does_not_accept_caller_selected_protected_root() -> None:
    policy, _, _ = _modules()

    parameters = inspect.signature(policy.TrustedAcceptanceRegistry.open_run).parameters

    assert "protected_root" not in parameters


def test_trusted_run_rejects_task1_bundle_digest_drift(tmp_path: Path) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        task1_digest_drift=True,
    )

    with pytest.raises(Exception, match="Task 1|task1|authorization.*digest"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_blocked_outcome_still_requires_valid_evidence_mode_proof(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        invalid_blocked_gate=True,
    )

    with pytest.raises(Exception, match="evidence mode|external gate"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_excluded_by_client_cannot_authorize_itself(tmp_path: Path) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        self_authorized_exclusion=True,
    )

    with pytest.raises(Exception, match="exclusion|excluded_by_client|external gate"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_caller_forged_structured_pass_is_not_decisive() -> None:
    policy, _, _ = _modules()
    registry = _registry()
    assertion = next(
        item
        for item in registry.compiled_policy.assertions.values()
        if item.oracle.kind == "structured_event"
    )
    forged = policy.StructuredEvent.build(
        assertion_id=assertion.assertion_id,
        producer=assertion.oracle.allowed_producers[0],
        source_id="caller-authored",
        source_digest="a" * 64,
        observed_at=datetime.now(UTC),
        passed=True,
        reason="Caller says this passed.",
        run_id="caller-run",
        attempt_digest="b" * 64,
        preflight_digest="c" * 64,
    )
    evidence = policy.OracleEvidence(
        assertion_id=assertion.assertion_id,
        structured_events=(forged,),
        tool_results=(),
        readbacks=(),
        classifier_results=(),
        text_supplements=(),
    )

    with pytest.raises(Exception, match="trusted|protected|artifact"):
        registry.evaluate_oracle(assertion.assertion_id, evidence)


def test_final_readback_cannot_predate_final_turn_anchor(tmp_path: Path) -> None:
    policy, execution, _ = _modules()
    registry = _registry()
    run_id = "future-anchor-run"
    now = datetime.now(UTC)
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id=run_id,
        now=now,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id=run_id,
        authority=authority,
    )
    authorization = journal.authorization
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id=run_id,
        preflight_digest=authorization.preflight_digest,
        collector_artifact_digest=authorization.readback_collector_digest,
        causal_event_digest="4" * 64,
        observed_at=now - timedelta(minutes=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    journal.anchor_final_turn(
        event_digest="a" * 64,
        occurred_at=now + timedelta(minutes=1),
    )
    final = policy.ReadbackObservation.build(
        phase="final",
        collector_id="independent-readback-collector",
        source_id="synthetic-final",
        run_id=run_id,
        preflight_digest=authorization.preflight_digest,
        collector_artifact_digest=authorization.readback_collector_digest,
        causal_event_digest=journal.previous_event_digest,
        observed_at=now,
        inventory={"synthetic:item": {"state": "closed"}},
    )

    with pytest.raises(
        Exception,
        match="timestamp|occurred|predate|final-turn|observation binding",
    ):
        receipt_digest = execution._write_test_final_readback_bundle(journal, final)
        journal.seal_final_readback(final, receipt_digest=receipt_digest)


def test_trusted_run_module_has_no_public_caller_root_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy, execution_module, trusted = _modules()
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "forged-outside-pytest")

    assert not hasattr(trusted, "load_verified_run")
    assert not hasattr(
        policy.TrustedAcceptanceRegistry,
        "_load_verified_run_fixture",
    )


def test_trusted_run_rejects_attempt_producer_without_protected_receipt(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        missing_attempt_receipts=True,
    )

    with pytest.raises(Exception, match="protected.*receipt|producer.*receipt"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_trusted_run_rejects_report_producer_without_protected_receipt(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        missing_report_receipt=True,
    )

    with pytest.raises(Exception, match="protected.*receipt|producer.*receipt"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_attempt_phase_heads_are_unique_and_execution_bound(
    tmp_path: Path,
) -> None:
    _, _, protected = _build_verified_run(tmp_path)
    anchor = json.loads(
        (protected / "registry/anchor.json").read_text(encoding="utf-8")
    )

    heads = tuple(anchor["attempt_chain_heads"].values())

    assert len(heads) == 29
    assert len(set(heads)) == 29


def test_attempt_receipt_raw_digest_drift_is_rejected(tmp_path: Path) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    execution_id = registry.compiled_plan.execution_ids[0]
    receipt_path = protected / "producer-receipts" / "attempts" / f"{execution_id}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["raw_digest"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(Exception, match="attempt.*binding|receipt|final commit marker"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_public_decisive_loader_uses_identities_not_roots() -> None:
    policy, _, _ = _modules()

    parameters = inspect.signature(
        policy.TrustedAcceptanceRegistry.load_decisive_evidence
    ).parameters

    assert "tracked_root" not in parameters
    assert "protected_root" not in parameters
    assert not hasattr(
        policy.TrustedAcceptanceRegistry,
        "_load_structured_artifact",
    )


def test_fixed_root_loader_registers_receipted_structured_evidence(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    policy, _, _ = _modules()
    registry.open_run(run_id="synthetic-trusted-run")
    assertion = next(
        item
        for item in registry.compiled_policy.assertions.values()
        if item.oracle.kind == "structured_event"
    )
    attempt_digest = json.loads(
        (
            tracked / "attempts" / f"{registry.compiled_plan.execution_ids[0]}.json"
        ).read_text(encoding="utf-8")
    )["attempt_digest"]
    event = policy.StructuredEvent.build(
        assertion_id=assertion.assertion_id,
        producer=assertion.oracle.allowed_producers[0],
        source_id="protected-structured-source",
        source_digest="d" * 64,
        observed_at=datetime.now(UTC),
        passed=True,
        reason="Protected structured evidence passed.",
        run_id="synthetic-trusted-run",
        attempt_digest=attempt_digest,
        preflight_digest="8" * 64,
    )
    relative = f"evidence/decisive/{event.artifact_digest}.json"
    tracked_sha256 = _write_json(
        tracked / relative,
        {
            "schema_version": "noor-e2e-decisive-evidence-envelope/v2",
            "evidence_kind": "structured_event",
            "artifact": event.model_dump(mode="json"),
        },
    )
    _write_json(
        protected / f"producer-receipts/decisive/{event.artifact_digest}.json",
        {
            "schema_version": "noor-e2e-decisive-producer-receipt/v2",
            "registry_id": registry.registry_id,
            "artifact_digest": event.artifact_digest,
            "run_id": event.run_id,
            "attempt_digest": event.attempt_digest,
            "preflight_digest": event.preflight_digest,
            "assertion_id": event.assertion_id,
            "producer": event.producer,
            "evidence_id": f"decisive:{event.artifact_digest}",
            "relative_path": relative,
            "tracked_sha256": tracked_sha256,
        },
    )
    _refresh_test_publication_marker(registry, tracked, protected)
    loaded = registry.load_decisive_evidence(
        run_id="synthetic-trusted-run",
        artifact_digest=event.artifact_digest,
    )
    decision = registry.evaluate_oracle(
        assertion.assertion_id,
        policy.OracleEvidence(
            assertion_id=assertion.assertion_id,
            structured_events=[event],
            tool_results=[],
            readbacks=[],
            classifier_results=[],
            text_supplements=[],
        ),
    )

    assert loaded == event
    assert decision.passed is True
    unbound = policy.StructuredEvent.build(
        assertion_id=assertion.assertion_id,
        producer=assertion.oracle.allowed_producers[0],
        source_id="protected-structured-source",
        source_digest="d" * 64,
        observed_at=datetime.now(UTC),
        passed=True,
        reason="Receipt exists but attempt was never committed.",
        run_id="synthetic-trusted-run",
        attempt_digest="0" * 64,
        preflight_digest="8" * 64,
    )
    unbound_relative = f"evidence/decisive/{unbound.artifact_digest}.json"
    unbound_sha256 = _write_json(
        tracked / unbound_relative,
        {
            "schema_version": "noor-e2e-decisive-evidence-envelope/v2",
            "evidence_kind": "structured_event",
            "artifact": unbound.model_dump(mode="json"),
        },
    )
    _write_json(
        protected / f"producer-receipts/decisive/{unbound.artifact_digest}.json",
        {
            "schema_version": "noor-e2e-decisive-producer-receipt/v2",
            "registry_id": registry.registry_id,
            "artifact_digest": unbound.artifact_digest,
            "run_id": unbound.run_id,
            "attempt_digest": unbound.attempt_digest,
            "preflight_digest": unbound.preflight_digest,
            "assertion_id": unbound.assertion_id,
            "producer": unbound.producer,
            "evidence_id": f"decisive:{unbound.artifact_digest}",
            "relative_path": unbound_relative,
            "tracked_sha256": unbound_sha256,
        },
    )
    _refresh_test_publication_marker(registry, tracked, protected)

    with pytest.raises(Exception, match="receipt|attempt"):
        registry.load_decisive_evidence(
            run_id="synthetic-trusted-run",
            artifact_digest=unbound.artifact_digest,
        )


def test_fixed_root_loader_registers_receipted_classifier_evidence(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    policy, _, _ = _modules()
    registry.open_run(run_id="synthetic-trusted-run")
    assertion = next(
        item
        for item in registry.compiled_policy.assertions.values()
        if item.oracle.kind == "classifier_result"
    )
    attempt_digest = json.loads(
        (
            tracked / "attempts" / f"{registry.compiled_plan.execution_ids[0]}.json"
        ).read_text(encoding="utf-8")
    )["attempt_digest"]
    result = policy.ClassifierResult.build(
        assertion_id=assertion.assertion_id,
        policy_digest=registry.compiled_policy.policy_digest,
        evaluator_digest=registry.classifier_evaluator_digest(assertion.assertion_id),
        run_id="synthetic-trusted-run",
        attempt_digest=attempt_digest,
        preflight_digest="8" * 64,
        classifier_id=assertion.oracle.classifier_id,
        producer=assertion.oracle.allowed_producers[0],
        source_id="protected-classifier-source",
        source_digest="d" * 64,
        observed_at=datetime.now(UTC),
        passed=True,
        reason="Protected classifier evidence passed.",
    )
    relative = f"evidence/decisive/{result.artifact_digest}.json"
    tracked_sha256 = _write_json(
        tracked / relative,
        {
            "schema_version": "noor-e2e-decisive-evidence-envelope/v2",
            "evidence_kind": "classifier_result",
            "artifact": result.model_dump(mode="json"),
        },
    )
    _write_json(
        protected / f"producer-receipts/decisive/{result.artifact_digest}.json",
        {
            "schema_version": "noor-e2e-decisive-producer-receipt/v2",
            "registry_id": registry.registry_id,
            "artifact_digest": result.artifact_digest,
            "run_id": result.run_id,
            "attempt_digest": result.attempt_digest,
            "preflight_digest": result.preflight_digest,
            "assertion_id": result.assertion_id,
            "producer": result.producer,
            "evidence_id": f"decisive:{result.artifact_digest}",
            "relative_path": relative,
            "tracked_sha256": tracked_sha256,
        },
    )
    _refresh_test_publication_marker(registry, tracked, protected)

    loaded = registry.load_decisive_evidence(
        run_id="synthetic-trusted-run",
        artifact_digest=result.artifact_digest,
    )

    assert loaded == result


def test_finalizer_publishes_only_complete_verified_snapshot(tmp_path: Path) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    _stage_protected_execution_snapshot(registry, tracked, protected)
    shutil.rmtree(tracked)
    shutil.rmtree(protected)

    registry.finalize_run(run_id)
    registry.open_run(run_id=run_id)

    assert registry.calculate_rollups()["coverage_complete"] is True
    assert (tracked / "registry/run.json").is_file()
    assert (protected / "registry/anchor.json").is_file()


def test_production_v2_snapshot_has_no_implicit_legacy_field_bypass(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    _stage_protected_execution_snapshot(registry, tracked, protected)
    source_root = _modules()[2]._execution_snapshot_root(registry) / run_id
    snapshot_path = source_root / "snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["schema_version"] = "noor-e2e-protected-execution-snapshot/v2"
    _write_json(snapshot_path, snapshot)
    shutil.rmtree(tracked)
    shutil.rmtree(protected)

    with pytest.raises(Exception, match="sealed_plan|terminal_journal"):
        registry.finalize_run(run_id)


def test_production_v2_snapshot_rejects_terminal_journal_head_drift(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    _stage_protected_execution_snapshot(registry, tracked, protected)
    snapshot_path, commit_path = _promote_fixture_snapshot_to_production_v2(
        registry, run_id
    )
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    commit["journal_head_digest"] = "f" * 64
    _write_json(commit_path, commit)
    shutil.rmtree(tracked)
    shutil.rmtree(protected)

    with pytest.raises(
        Exception, match="collector_artifacts|baseline_sealed|snapshot binding drift"
    ):
        registry.finalize_run(run_id)


def test_production_v2_snapshot_rejects_final_causal_head_drift(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    _stage_protected_execution_snapshot(registry, tracked, protected)
    snapshot_path, commit_path = _promote_fixture_snapshot_to_production_v2(
        registry, run_id
    )
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["final_causal_event_digest"] = "f" * 64
    identity = {
        key: value for key, value in snapshot.items() if key != "snapshot_digest"
    }
    snapshot["snapshot_digest"] = _modules()[2].canonical_digest(identity)
    snapshot_sha256 = _write_json(snapshot_path, snapshot)
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    commit["snapshot_sha256"] = snapshot_sha256
    commit["snapshot_digest"] = snapshot["snapshot_digest"]
    commit["final_causal_event_digest"] = "f" * 64
    _write_json(commit_path, commit)
    shutil.rmtree(tracked)
    shutil.rmtree(protected)

    with pytest.raises(
        Exception, match="collector_artifacts|baseline_sealed|snapshot binding drift"
    ):
        registry.finalize_run(run_id)


def _rewrite_protected_journal(
    protected: Path,
    journal,
    transform,
) -> None:
    events = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((protected / "journal").glob("*.json"))
    ]
    transform(events)
    for path in (protected / "journal").glob("*.json"):
        path.unlink()
    previous = None
    for cursor, event in enumerate(events, start=1):
        event["cursor"] = cursor
        event["previous_event_digest"] = previous
        previous = _write_json(
            protected / f"journal/{cursor:06d}.json",
            event,
        )
    journal.previous_event_digest = previous


def _seal_materializer_acceptance_journal(
    registry,
    tracked: Path,
    protected: Path,
    journal,
    *,
    gate_records: tuple[dict[str, object], ...] = (),
) -> None:
    policy, _, trusted = _modules()
    run_path = tracked / "registry/run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    for path in (protected / "journal").glob("*.json"):
        path.unlink()

    previous = None

    def append(phase: str, kind: str, data: dict[str, object]) -> str:
        nonlocal previous
        cursor = len(tuple((protected / "journal").glob("*.json"))) + 1
        event = {
            "schema_version": "noor-e2e-protected-event/v2",
            "cursor": cursor,
            "phase": phase,
            "kind": kind,
            "previous_event_digest": previous,
            "data": data,
        }
        previous = _write_json(protected / f"journal/{cursor:06d}.json", event)
        return previous

    append(
        "prepared",
        "prepared",
        {"authorization_digest": journal.authorization_digest},
    )
    baseline = policy.ReadbackObservation.model_validate(run["baseline"])
    append(
        "baseline_sealed",
        "baseline_sealed",
        {
            "source_id": baseline.source_id,
            "collector_id": baseline.collector_id,
            "observed_at": baseline.observed_at.isoformat(),
            "content_digest": baseline.content_digest,
        },
    )
    append(
        "executing",
        "execution_started",
        {"started_at": baseline.observed_at.isoformat()},
    )
    for original_record in gate_records:
        record = dict(original_record)
        record["journal_head_digest"] = previous
        execution_id = str(record["execution_id"])
        _write_json(protected / f"recorded-gates/{execution_id}.json", record)
        append("executing", "gate_recorded", record)

    final_anchor = max(
        datetime.fromisoformat(value)
        for field in ("final_visible_at", "delivered_at", "action_at")
        for value in run[field]
    )
    final_turn_digest = append(
        "final_turn_anchored",
        "final_turn_anchored",
        {
            "event_digest": "d" * 64,
            "occurred_at": final_anchor.isoformat(),
        },
    )
    original_final = policy.ReadbackObservation.model_validate(run["final"])
    final = policy.ReadbackObservation.build(
        phase="final",
        collector_id=original_final.collector_id,
        source_id=original_final.source_id,
        run_id=original_final.run_id,
        preflight_digest=original_final.preflight_digest,
        collector_artifact_digest=original_final.collector_artifact_digest,
        causal_event_digest=final_turn_digest,
        observed_at=original_final.observed_at,
        inventory=original_final.inventory,
    )
    run["final"] = final.model_dump(mode="json")
    _write_json(run_path, run)

    artifact_path = protected / "collector-artifacts/final-readback.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact.update(
        authorization_digest=journal.authorization_digest,
        journal_head_digest=final_turn_digest,
        final_turn_anchor_at=final_anchor.isoformat(),
        observed_at=final.observed_at.isoformat(),
        inventory_digest=trusted.canonical_digest(final.inventory),
        observation=final.model_dump(mode="json"),
    )
    artifact_sha256 = _write_json(artifact_path, artifact)
    receipt_path = protected / "producer-receipts/final-readback.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.update(
        authorization_digest=journal.authorization_digest,
        journal_head_digest=final_turn_digest,
        artifact_sha256=artifact_sha256,
        inventory_digest=trusted.canonical_digest(final.inventory),
        observed_at=final.observed_at.isoformat(),
    )
    receipt_digest = _write_json(receipt_path, receipt)
    append(
        "final_readback_sealed",
        "final_readback_sealed",
        {
            "source_id": final.source_id,
            "collector_id": final.collector_id,
            "observed_at": final.observed_at.isoformat(),
            "content_digest": final.content_digest,
            "causal_event_digest": final.causal_event_digest,
            "collector_receipt_digest": receipt_digest,
            "inventory_digest": trusted.canonical_digest(final.inventory),
        },
    )
    append("evaluated", "evaluated", {"evaluation_digest": "e" * 64})
    append(
        "attempt_committed",
        "attempt_committed",
        {"attempt_chain_digest": "f" * 64},
    )
    journal.previous_event_digest = previous


def _production_materializer_inputs(tmp_path: Path):
    registry, tracked, protected = _build_verified_run(tmp_path)
    policy, execution_module, trusted = _modules()
    from scripts.e2e_acceptance.coordinator import (
        JournalAcceptanceEvent,
        ProducerArtifact,
        ProducerReceipt,
        ProductionRunCoordinator,
    )
    from scripts.e2e_acceptance.production import (
        BaselineReadbackArtifact,
        BaselineReadbackProducerReceipt,
    )

    run = json.loads((tracked / "registry/run.json").read_text(encoding="utf-8"))
    report = json.loads(
        (tracked / "registry/report-payload.json").read_text(encoding="utf-8")
    )
    run_id = run["run_id"]
    runtime_identity = {
        "repository_commit": report["identity"]["repository_commit"],
        "deployed_release_sha": report["identity"]["deployed_release_sha"],
        "ci_run_id": report["identity"]["ci_run_id"],
        "app_version": report["identity"]["app_version"],
        "migration_head": report["identity"]["migration_head"],
        "main_model": report["identity"]["models"][0],
        "fast_model": report["identity"]["models"][-1],
    }
    authorization_v1_source = {"expected_identity": runtime_identity}
    preflight_observation_source = {"identity": runtime_identity}
    run["authorization"]["live_binding"].update(
        {
            "v1_manifest_digest": trusted.canonical_digest(authorization_v1_source),
            "preflight_observation_digest": trusted.canonical_digest(
                preflight_observation_source
            ),
            "runtime_identity_digest": trusted.canonical_digest(runtime_identity),
        }
    )
    authorization_digest = trusted.canonical_digest(run["authorization"])
    authority_root = protected.parent / "authority-bundles" / run_id
    authorization_v1_sha = _write_json(
        authority_root / "authorization-v1.json", authorization_v1_source
    )
    preflight_observation_sha = _write_json(
        authority_root / "preflight-observation.json",
        preflight_observation_source,
    )
    _write_json(
        authority_root / "receipt.json",
        {
            "schema_version": "noor-e2e-authority-bundle-receipt/v2",
            "registry_id": registry.registry_id,
            "run_id": run_id,
            "payload_digests": {
                "authorization_manifest": authorization_v1_sha,
                "preflight_observation": preflight_observation_sha,
            },
        },
    )
    attempts_by_execution = {}
    for row in run["executions"]:
        attempt_path = tracked / f"attempts/{row['execution_id']}.json"
        attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
        commit_path = protected / attempt["protected_commit_ref"]
        commit = json.loads(commit_path.read_text(encoding="utf-8"))
        commit["authorization_digest"] = authorization_digest
        attempt["authorization_digest"] = authorization_digest
        attempt["protected_commit_digest"] = _write_json(commit_path, commit)
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
            identity = {
                "cursor": cursor,
                "phase": phase,
                "previous_event_digest": previous,
                "run_id": run_id,
                "execution_id": row["execution_id"],
                "attempt_digest": attempt["attempt_digest"],
                "semantic_digest": attempt["semantic_digest"],
                "authorization_digest": authorization_digest,
                "protected_commit_digest": attempt["protected_commit_digest"],
            }
            previous = trusted.canonical_digest(identity)
            phase_chain.append(
                {
                    "cursor": cursor,
                    "phase": phase,
                    "previous_event_digest": identity["previous_event_digest"],
                    "event_digest": previous,
                }
            )
        attempt["phase_chain"] = phase_chain
        attempt["phase_head_digest"] = previous
        _write_json(attempt_path, attempt)
        attempts_by_execution[row["execution_id"]] = attempt
    for turn in report["turns"]:
        attempt = attempts_by_execution[turn["execution_id"]]
        receipt_path = (
            protected
            / "producer-receipts/transcripts"
            / turn["execution_id"]
            / turn["attempt_id"]
            / f"{turn['turn_id']}.json"
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["authorization_digest"] = authorization_digest
        receipt["attempt_phase_head_digest"] = attempt["phase_head_digest"]
        turn["producer_receipt_digest"] = _write_json(receipt_path, receipt)
    manifest_path = protected / "transcripts/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ordered_turns"] = [
        [
            turn["execution_id"],
            turn["attempt_id"],
            turn["turn_id"],
            turn["transcript_digest"],
            turn["producer_receipt_digest"],
        ]
        for turn in report["turns"]
    ]
    _write_json(manifest_path, manifest)
    _write_json(tracked / "registry/run.json", run)
    _write_json(tracked / "registry/report-payload.json", report)
    side_effects = []
    for item in report["side_effects"]:
        side_effects.append(
            {
                key: value
                for key, value in item.items()
                if key not in {"baseline", "final"}
            }
        )
    plan = SimpleNamespace(
        actions=(),
        evaluator={
            "publication": {
                "schema_version": "noor-e2e-publication-metadata/v1",
                "title": report["title"],
                "tester": report["tester"],
                "judge": report["judge"],
                "limitations": report["limitations"],
                "external_gates": report["external_gates"],
            }
        },
    )
    plan.plan_digest = trusted.canonical_digest(
        {"actions": list(plan.actions), "evaluator": plan.evaluator}
    )
    plan.evaluator_digest = trusted.canonical_digest(plan.evaluator)
    sealed = {
        "schema_version": "noor-e2e-sealed-run-plan/v2",
        "plan_digest": plan.plan_digest,
        "evaluator_digest": plan.evaluator_digest,
        "actions": list(plan.actions),
        "evaluator": plan.evaluator,
    }
    _write_json(protected / "run-plan/sealed.json", sealed)
    journal = SimpleNamespace(
        phase="attempt_committed",
        run_id=run_id,
        protected_root=protected.parent,
        run_root=protected,
        authorization_digest=trusted.canonical_digest(run["authorization"]),
        authorization=execution_module.ExecutionAuthorizationV2.model_validate(
            run["authorization"]
        ),
        previous_event_digest=None,
        _actions={},
        _recorded_gates={},
        _coordinator_acceptance_events={},
    )
    prepared_event = {
        "schema_version": "noor-e2e-protected-event/v2",
        "cursor": 1,
        "phase": "prepared",
        "kind": "prepared",
        "previous_event_digest": None,
        "data": {"authorization_digest": journal.authorization_digest},
    }
    prepared_digest = _write_json(protected / "journal/000001.json", prepared_event)
    original_baseline = policy.ReadbackObservation.model_validate(run["baseline"])
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id=original_baseline.collector_id,
        source_id=original_baseline.source_id,
        run_id=run_id,
        preflight_digest=original_baseline.preflight_digest,
        collector_artifact_digest=original_baseline.collector_artifact_digest,
        causal_event_digest=prepared_digest,
        observed_at=original_baseline.observed_at,
        inventory=original_baseline.inventory,
    )
    run["baseline"] = baseline.model_dump(mode="json")
    _write_json(tracked / "registry/run.json", run)
    baseline_event = {
        "schema_version": "noor-e2e-protected-event/v2",
        "cursor": 2,
        "phase": "baseline_sealed",
        "kind": "baseline_sealed",
        "previous_event_digest": prepared_digest,
        "data": {
            "source_id": baseline.source_id,
            "collector_id": baseline.collector_id,
            "observed_at": baseline.observed_at.isoformat(),
            "content_digest": baseline.content_digest,
        },
    }
    baseline_event_digest = _write_json(
        protected / "journal/000002.json", baseline_event
    )
    terminal_event = {
        "schema_version": "noor-e2e-protected-event/v2",
        "cursor": 3,
        "phase": "attempt_committed",
        "kind": "attempt_committed",
        "previous_event_digest": baseline_event_digest,
        "data": {},
    }
    journal.previous_event_digest = _write_json(
        protected / "journal/000003.json", terminal_event
    )
    baseline_artifact = BaselineReadbackArtifact(
        registry_id=registry.registry_id,
        run_id=run_id,
        authorization_digest=journal.authorization_digest,
        preflight_digest=baseline.preflight_digest,
        collector_id=baseline.collector_id,
        collector_artifact_digest=baseline.collector_artifact_digest,
        journal_head_digest=baseline.causal_event_digest,
        observed_at=baseline.observed_at,
        inventory_digest=trusted.canonical_digest(baseline.inventory),
        observation=baseline,
    ).model_dump(mode="json")
    artifact_sha256 = hashlib.sha256(
        trusted._canonical_bytes(baseline_artifact)
    ).hexdigest()
    _write_json(
        protected / "collector-artifacts/baseline-readback.json", baseline_artifact
    )
    baseline_receipt = BaselineReadbackProducerReceipt(
        registry_id=registry.registry_id,
        run_id=run_id,
        authorization_digest=journal.authorization_digest,
        preflight_digest=baseline.preflight_digest,
        collector_id=baseline.collector_id,
        collector_artifact_digest=baseline.collector_artifact_digest,
        artifact_sha256=artifact_sha256,
        journal_head_digest=baseline.causal_event_digest,
        inventory_digest=trusted.canonical_digest(baseline.inventory),
        observed_at=baseline.observed_at,
        issued_at=baseline.observed_at,
        expires_at=baseline.observed_at + timedelta(minutes=5),
    ).model_dump(mode="json")
    _write_json(
        protected / "producer-receipts/baseline-readback.json", baseline_receipt
    )
    _seal_materializer_acceptance_journal(
        registry,
        tracked,
        protected,
        journal,
    )
    index = json.loads(
        (tracked / "registry/evidence-index.json").read_text(encoding="utf-8")
    )
    evidence_by_id = {
        entry["evidence_id"]: {
            "evidence_id": entry["evidence_id"],
            "producer": entry["producer"],
            "payload": json.loads(
                (tracked / entry["relative_path"]).read_text(encoding="utf-8")
            ),
        }
        for entry in index["entries"]
        if entry["evidence_id"] != "report-source"
    }
    execution_by_id = {row["execution_id"]: row for row in run["executions"]}
    turns_by_execution: dict[str, list[dict]] = {}
    for turn in report["turns"]:
        turns_by_execution.setdefault(turn["execution_id"], []).append(turn)

    class _Port:
        def __init__(self):
            self.events: dict[int, JournalAcceptanceEvent] = {}

        def record_acceptance(self, event):
            self.events[event.ordinal] = event
            return event.event_digest

        def read_acceptance(self, ordinal):
            return self.events.get(ordinal)

    port = _Port()
    coordinator = ProductionRunCoordinator(
        registry=registry,
        authorization=journal.authorization,
        protected_root=protected.parent,
        run_id=run_id,
        journal=port,
        current_time=datetime.now(UTC),
    )
    generic_ids = ("fresh", "reuse", "gate")
    for ordinal, execution_id in enumerate(
        registry.compiled_plan.execution_ids, start=1
    ):
        row = execution_by_id[execution_id]
        attempt = evidence_by_id[row["attempt_ref"]]
        unit_evidence = [attempt]
        if ordinal == 1:
            unit_evidence.extend(evidence_by_id[item] for item in generic_ids)
        kind = coordinator._expected_kind(execution_id)
        source = {
            "schema_version": (
                "noor-e2e-scenario-publication-source/v1"
                if kind == "scenario"
                else "noor-e2e-evidence-block-publication-source/v1"
            ),
            "kind": kind,
            "execution": {
                "attempt_ref": row["attempt_ref"],
                "evidence_refs": row["evidence_refs"],
            },
            "evidence": unit_evidence,
        }
        if kind == "scenario":
            source["turns"] = turns_by_execution[execution_id]
            source["side_effect_dispositions"] = side_effects if ordinal == 1 else []
        producer = (
            coordinator.authorization.adapter_ids[0]
            if kind == "scenario"
            else coordinator.authorization.collector_ids[0]
        )
        artifact = ProducerArtifact(
            schema_version="noor-e2e-coordinator-producer-artifact/v1",
            status="committed",
            registry_id=registry.registry_id,
            run_id=run_id,
            authorization_digest=journal.authorization_digest,
            sealed_plan_sha256=coordinator.sealed_plan_sha256,
            ordinal=ordinal,
            execution_id=execution_id,
            kind=kind,
            outcome=row["outcome"],
            producer=producer,
            observed_at=coordinator.current_time - timedelta(seconds=1),
            source=source,
            source_sha256=trusted.canonical_digest(source),
        ).model_dump(mode="json")
        artifact_payload = trusted._canonical_bytes(artifact)
        receipt = ProducerReceipt(
            schema_version="noor-e2e-coordinator-producer-receipt/v1",
            status="committed",
            registry_id=registry.registry_id,
            run_id=run_id,
            authorization_digest=journal.authorization_digest,
            ordinal=ordinal,
            execution_id=execution_id,
            producer=producer,
            artifact_sha256=hashlib.sha256(artifact_payload).hexdigest(),
            source_sha256=trusted.canonical_digest(source),
            issued_at=coordinator.current_time - timedelta(seconds=1),
            expires_at=coordinator.current_time + timedelta(minutes=5),
        ).model_dump(mode="json")
        _write_json(protected / coordinator.producer_artifact_path(ordinal), artifact)
        _write_json(protected / coordinator.producer_receipt_path(ordinal), receipt)
    coordinator.accept_available()
    journal._coordinator_acceptance_events = {
        ordinal: event.model_dump(mode="json") for ordinal, event in port.events.items()
    }
    return registry, tracked, protected, journal, plan


def test_materialize_execution_snapshot_builds_and_loads_strict_production_v2(
    tmp_path: Path,
) -> None:
    registry, _, _, journal, plan = _production_materializer_inputs(tmp_path)
    _, _, trusted = _modules()

    snapshot = trusted.materialize_execution_snapshot(registry, journal, plan)

    assert snapshot.terminal_journal_head_digest == journal.previous_event_digest
    assert (
        snapshot.final_causal_event_digest
        == json.loads(
            (
                registry.repo_root
                / ".codex/stages/tj-ee5f/results"
                / journal.run_id
                / "registry/run.json"
            ).read_text(encoding="utf-8")
        )["final"]["causal_event_digest"]
    )
    assert snapshot.terminal_journal_head_digest != snapshot.final_causal_event_digest
    assert tuple(snapshot.journal_events) == tuple(
        f"journal/{cursor:06d}.json"
        for cursor in range(1, len(snapshot.journal_events) + 1)
    )
    commit = json.loads(
        (
            trusted._execution_snapshot_root(registry) / journal.run_id / "commit.json"
        ).read_text(encoding="utf-8")
    )
    assert commit["journal_events_digest"] == trusted.canonical_digest(
        snapshot.journal_events
    )
    assert (
        trusted._load_protected_execution_snapshot(registry, journal.run_id) == snapshot
    )


def test_materializer_never_reads_prewritten_tracked_candidate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Tracked result bytes are a publication target, never candidate input."""

    registry, tracked, _, journal, plan = _production_materializer_inputs(tmp_path)
    _, _, trusted = _modules()
    original_read = trusted._read_file

    def reject_tracked_candidate_read(root, relative, **kwargs):
        if root == tracked:
            raise AssertionError(f"tracked candidate read: {relative}")
        return original_read(root, relative, **kwargs)

    monkeypatch.setattr(trusted, "_read_file", reject_tracked_candidate_read)

    trusted.materialize_execution_snapshot(registry, journal, plan)


def test_strict_snapshot_materializes_after_receipt_expiry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Recovery uses the protected acceptance proof, not a new five-minute window."""

    registry, _, _, journal, plan = _production_materializer_inputs(tmp_path)
    _, _, trusted = _modules()
    future = datetime.now(UTC) + timedelta(hours=1)
    monkeypatch.setattr(
        trusted,
        "datetime",
        SimpleNamespace(now=lambda timezone: future),
    )

    snapshot = trusted.materialize_execution_snapshot(registry, journal, plan)

    assert snapshot.run_id == journal.run_id


@pytest.mark.parametrize("event_mode", ("missing", "tampered"))
def test_materializer_rejects_invalid_final_readback_acceptance_event(
    tmp_path: Path,
    event_mode: str,
) -> None:
    registry, _, protected, journal, plan = _production_materializer_inputs(tmp_path)
    _, _, trusted = _modules()

    def mutate(events):
        final_event = next(
            event for event in events if event["kind"] == "final_readback_sealed"
        )
        if event_mode == "missing":
            events.remove(final_event)
        else:
            final_event["data"]["content_digest"] = "0" * 64

    _rewrite_protected_journal(protected, journal, mutate)

    with pytest.raises(Exception, match="final readback.*journal|acceptance"):
        trusted.materialize_execution_snapshot(registry, journal, plan)


def test_materializer_requires_baseline_producer_pair_and_sealed_journal_chain(
    tmp_path: Path,
) -> None:
    """A production snapshot cannot be derived from caller-authored baseline data."""

    registry, _, protected, journal, plan = _production_materializer_inputs(tmp_path)
    _, _, trusted = _modules()
    (protected / "collector-artifacts/baseline-readback.json").unlink()

    with pytest.raises(Exception, match="baseline"):
        trusted.materialize_execution_snapshot(registry, journal, plan)


def test_materializer_ignores_self_consistent_tracked_baseline_substitution(
    tmp_path: Path,
) -> None:
    """The protected baseline producer pair, not tracked input, is authoritative."""

    registry, tracked, _, journal, plan = _production_materializer_inputs(tmp_path)
    policy, _, trusted = _modules()
    run_path = tracked / "registry/run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    baseline = policy.ReadbackObservation.model_validate(run["baseline"])
    replacement = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id=baseline.collector_id,
        source_id=baseline.source_id,
        run_id=baseline.run_id,
        preflight_digest=baseline.preflight_digest,
        collector_artifact_digest=baseline.collector_artifact_digest,
        causal_event_digest=baseline.causal_event_digest,
        observed_at=baseline.observed_at,
        inventory={"synthetic:item": {"state": "forged"}},
    )
    run["baseline"] = replacement.model_dump(mode="json")
    _write_json(run_path, run)

    snapshot = trusted.materialize_execution_snapshot(registry, journal, plan)
    assert snapshot.run["baseline"]["content_digest"] != replacement.content_digest


def test_materializer_recovers_only_identical_snapshot_after_commit_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry, tracked, _, journal, plan = _production_materializer_inputs(tmp_path)
    _, _, trusted = _modules()
    original_write = trusted._write_snapshot_tree

    def crash_before_commit(root, files):
        if set(files) == {"commit.json"}:
            raise OSError("crash before snapshot commit")
        return original_write(root, files)

    monkeypatch.setattr(trusted, "_write_snapshot_tree", crash_before_commit)
    with pytest.raises(OSError, match="crash before snapshot commit"):
        trusted.materialize_execution_snapshot(registry, journal, plan)
    snapshot_root = trusted._execution_snapshot_root(registry) / journal.run_id
    assert (snapshot_root / "snapshot.json").is_file()
    assert not (snapshot_root / "commit.json").exists()

    monkeypatch.setattr(trusted, "_write_snapshot_tree", original_write)
    trusted.materialize_execution_snapshot(registry, journal, plan)
    index = json.loads(
        (tracked / "registry/evidence-index.json").read_text(encoding="utf-8")
    )
    evidence_path = tracked / index["entries"][0]["relative_path"]
    evidence_path.write_text("{}\n", encoding="utf-8")
    evidence_path.chmod(0o600)
    recovered = trusted.materialize_execution_snapshot(registry, journal, plan)
    assert recovered.run_id == journal.run_id


@pytest.mark.parametrize("event_mode", ("valid", "missing", "tampered"))
def test_materializer_includes_and_validates_all_four_gate_artifacts(
    tmp_path: Path,
    event_mode: str,
) -> None:
    registry, tracked, protected, journal, plan = _production_materializer_inputs(
        tmp_path
    )
    _, execution, trusted = _modules()
    run = json.loads((tracked / "registry/run.json").read_text(encoding="utf-8"))
    index_path = tracked / "registry/evidence-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entry = next(
        item
        for item in index["entries"]
        if item["producer"] == "protected-attempt-committer"
    )
    committed_path = tracked / entry["relative_path"]
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    execution_id = committed["execution_id"]
    now = datetime.now(UTC)
    criterion_ids = tuple(
        item.criterion_id
        for item in registry.compiled_plan.criteria.values()
        if execution_id in item.obligation_ids
    )
    started_digest = "a" * 64
    artifact = execution.GateEvidenceArtifact(
        schema_version="noor-e2e-gate-evidence/v2",
        registry_id=registry.registry_id,
        run_id=journal.run_id,
        authorization_digest=journal.authorization_digest,
        execution_id=execution_id,
        criterion_ids=criterion_ids,
        execution_owner=run["authorization"]["authorization_id"],
        execution_started_event_digest=started_digest,
        outcome="BLOCKED",
        producer="independent-readback-collector",
        observed_at=now,
        evidence_digest="b" * 64,
    ).model_dump(mode="json")
    artifact_sha256 = hashlib.sha256(trusted._canonical_bytes(artifact)).hexdigest()
    receipt = execution.GateEvidenceReceipt(
        schema_version="noor-e2e-gate-evidence-receipt/v2",
        registry_id=registry.registry_id,
        run_id=journal.run_id,
        authorization_digest=journal.authorization_digest,
        execution_id=execution_id,
        criterion_ids=criterion_ids,
        execution_owner=run["authorization"]["authorization_id"],
        execution_started_event_digest=started_digest,
        artifact_sha256=artifact_sha256,
        outcome="BLOCKED",
        producer="independent-readback-collector",
        issued_at=now,
        expires_at=now + timedelta(minutes=1),
    ).model_dump(mode="json")
    receipt_sha256 = hashlib.sha256(trusted._canonical_bytes(receipt)).hexdigest()
    gate = execution.GateAttemptV2(
        schema_version="noor-e2e-gate-attempt/v2",
        execution_id=execution_id,
        outcome="BLOCKED",
        run_started_at=now - timedelta(seconds=1),
        execution_started_event_digest=started_digest,
        receipt_digest=receipt_sha256,
    )
    gate_payload = gate.model_dump(mode="json")
    gate_sha256 = hashlib.sha256(trusted._canonical_bytes(gate_payload)).hexdigest()
    committed.update(attempt_kind="gate", outcome="BLOCKED", gate_attempt=gate_payload)
    protected_commit_path = protected / committed["protected_commit_ref"]
    protected_commit = json.loads(protected_commit_path.read_text(encoding="utf-8"))
    protected_commit.update(
        attempt_kind="gate",
        gate_attempt_digest=trusted.canonical_digest(gate_payload),
    )
    protected_commit_digest = _write_json(protected_commit_path, protected_commit)
    committed["protected_commit_digest"] = protected_commit_digest
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
        event = {
            "cursor": cursor,
            "phase": phase,
            "previous_event_digest": previous,
            "run_id": journal.run_id,
            "execution_id": execution_id,
            "attempt_digest": committed["attempt_digest"],
            "semantic_digest": committed["semantic_digest"],
            "authorization_digest": journal.authorization_digest,
            "protected_commit_digest": protected_commit_digest,
        }
        previous = trusted.canonical_digest(event)
        phase_chain.append(
            {
                "cursor": cursor,
                "phase": phase,
                "previous_event_digest": event["previous_event_digest"],
                "event_digest": previous,
            }
        )
    committed["phase_chain"] = phase_chain
    committed["phase_head_digest"] = previous
    entry["sha256"] = _write_json(committed_path, committed)
    _write_json(index_path, index)
    for payload, relative in (
        (run, tracked / "registry/run.json"),
        (
            json.loads(
                (tracked / "registry/report-payload.json").read_text(encoding="utf-8")
            ),
            tracked / "registry/report-payload.json",
        ),
    ):
        for row in payload["executions"]:
            if row["execution_id"] == execution_id:
                row["outcome"] = "BLOCKED"
        if "turns" in payload:
            payload["turns"] = [
                row for row in payload["turns"] if row["execution_id"] != execution_id
            ]
        if "criteria" in payload:
            for row in payload["criteria"]:
                if execution_id in row.get("obligation_outcomes", {}):
                    row["obligation_outcomes"][execution_id] = "BLOCKED"
                    row["outcome"] = "BLOCKED"
                if row["criterion_id"] in criterion_ids:
                    row["outcome"] = "BLOCKED"
        _write_json(relative, payload)
    shutil.rmtree(protected / "transcripts" / execution_id)
    shutil.rmtree(protected / "producer-receipts" / "transcripts" / execution_id)
    manifest_path = protected / "transcripts/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ordered_turns"] = [
        row for row in manifest["ordered_turns"] if row[0] != execution_id
    ]
    _write_json(manifest_path, manifest)
    recorded_gate = {
        "schema_version": "noor-e2e-recorded-gate/v2",
        "execution_id": execution_id,
        "outcome": "BLOCKED",
        "gate_attempt_sha256": gate_sha256,
        "journal_head_digest": "c" * 64,
        "gate_attempt": gate_payload,
    }
    for relative, payload in {
        f"gate-attempts/{execution_id}.json": gate_payload,
        f"gate-evidence/{execution_id}.json": artifact,
        f"producer-receipts/gates/{execution_id}.json": receipt,
        f"recorded-gates/{execution_id}.json": recorded_gate,
    }.items():
        _write_json(protected / relative, payload)
    journal._recorded_gates = {execution_id: gate}
    _seal_materializer_acceptance_journal(
        registry,
        tracked,
        protected,
        journal,
        gate_records=(recorded_gate,),
    )
    if event_mode != "valid":

        def mutate(events):
            gate_event = next(
                event for event in events if event["kind"] == "gate_recorded"
            )
            if event_mode == "missing":
                events.remove(gate_event)
            else:
                gate_event["data"]["outcome"] = "EXCLUDED_BY_CLIENT"

        _rewrite_protected_journal(protected, journal, mutate)

    # The coordinator accepted an executed unit before this attempted rewrite.
    # A later self-consistent gate quartet must not replace that durable source.
    with pytest.raises(
        Exception,
        match="gate.*path-set|gate.*journal|acceptance",
    ):
        trusted.materialize_execution_snapshot(registry, journal, plan)


def test_finalizer_rejects_extra_transcript_snapshot_path(tmp_path: Path) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    _stage_protected_execution_snapshot(registry, tracked, protected)
    _, _, trusted = _modules()
    source_root = trusted._execution_snapshot_root(registry) / run_id
    snapshot_path = source_root / "snapshot.json"
    commit_path = source_root / "commit.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["transcript_artifacts"]["transcripts/extra.json"] = {
        "schema_version": "noor-e2e-protected-transcript/v2",
        "registry_id": registry.registry_id,
        "run_id": run_id,
        "execution_id": registry.compiled_plan.execution_ids[0],
        "attempt_id": "phantom-attempt",
        "turn_id": "phantom-turn",
        "turn": {},
    }
    snapshot_identity = {
        key: value for key, value in snapshot.items() if key != "snapshot_digest"
    }
    snapshot["snapshot_digest"] = trusted.canonical_digest(snapshot_identity)
    snapshot_sha256 = _write_json(snapshot_path, snapshot)
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    commit["snapshot_sha256"] = snapshot_sha256
    commit["snapshot_digest"] = snapshot["snapshot_digest"]
    _write_json(commit_path, commit)
    shutil.rmtree(tracked)
    shutil.rmtree(protected)

    with pytest.raises(Exception, match="transcript.*path-set|ordered path-set"):
        registry.finalize_run(run_id)


def test_loader_requires_exact_independent_final_inventory_commit(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    receipt_path = protected / "producer-receipts/final-readback.json"
    receipt_path.unlink()
    _refresh_test_publication_marker(registry, tracked, protected)

    with pytest.raises(Exception, match="final readback|producer|receipt"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_loader_rejects_self_consistent_forged_collector_inventory(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    policy, _, trusted = _modules()
    run = json.loads((tracked / "registry/run.json").read_text(encoding="utf-8"))
    original = policy.ReadbackObservation.model_validate(run["final"])
    forged = policy.ReadbackObservation.build(
        phase="final",
        collector_id=original.collector_id,
        source_id="forged-independent-final",
        run_id=original.run_id,
        preflight_digest=original.preflight_digest,
        collector_artifact_digest=original.collector_artifact_digest,
        causal_event_digest=original.causal_event_digest,
        observed_at=original.observed_at,
        inventory={"synthetic:item": {"state": "active"}},
    )
    artifact_path = protected / "collector-artifacts/final-readback.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["observation"] = forged.model_dump(mode="json")
    artifact["inventory_digest"] = trusted.canonical_digest(forged.inventory)
    artifact_sha256 = _write_json(artifact_path, artifact)
    receipt_path = protected / "producer-receipts/final-readback.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["artifact_sha256"] = artifact_sha256
    receipt["inventory_digest"] = artifact["inventory_digest"]
    _write_json(receipt_path, receipt)
    _refresh_test_publication_marker(registry, tracked, protected)

    with pytest.raises(Exception, match="final readback.*binding|inventory"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_finalizer_removes_partial_publish_when_inner_receipt_is_invalid(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    _stage_protected_execution_snapshot(
        registry,
        tracked,
        protected,
        report_mutation=lambda report: report.__setitem__(
            "turns",
            report["turns"][:1],
        ),
    )
    shutil.rmtree(tracked)
    shutil.rmtree(protected)

    with pytest.raises(
        Exception,
        match="turn|scenario.*coverage|report.*coverage|transcript",
    ):
        registry.finalize_run(run_id)

    assert not tracked.exists()
    assert not protected.exists()


def test_finalizer_rejects_private_derived_payload_before_any_publication_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A failed privacy check must leave neither staging nor tracked results."""

    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    evidence_path = tracked / "evidence/fresh.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["token"] = "secret-derived-payload"
    _write_json(evidence_path, evidence)
    index_path = tracked / "registry/evidence-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    fresh = next(item for item in index["entries"] if item["evidence_id"] == "fresh")
    fresh["sha256"] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    _write_json(index_path, index)
    _stage_protected_execution_snapshot(registry, tracked, protected)
    shutil.rmtree(tracked)
    shutil.rmtree(protected)
    _, _, trusted = _modules()
    writes: list[set[str]] = []
    original_write = trusted._write_snapshot_tree

    def record_write(root, files):
        writes.append(set(files))
        return original_write(root, files)

    monkeypatch.setattr(trusted, "_write_snapshot_tree", record_write)

    with pytest.raises(Exception, match="privacy"):
        registry.finalize_run(run_id)

    assert writes == []
    assert not tracked.exists()
    assert not protected.exists()


def test_finalizer_rejects_private_rendered_markdown_before_any_publication_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Markdown receives its own pre-write privacy check, not a loader-only one."""

    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    report_path = tracked / "registry/report-payload.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["title"] = "Synthetic report +1 202 555 0198"
    _write_json(report_path, report)
    _stage_protected_execution_snapshot(registry, tracked, protected)
    shutil.rmtree(tracked)
    shutil.rmtree(protected)
    _, _, trusted = _modules()
    monkeypatch.setattr(trusted, "validate_redacted_payload", lambda payload: None)
    writes: list[set[str]] = []
    original_write = trusted._write_snapshot_tree

    def record_write(root, files):
        writes.append(set(files))
        return original_write(root, files)

    monkeypatch.setattr(trusted, "_write_snapshot_tree", record_write)

    with pytest.raises(Exception, match="privacy"):
        registry.finalize_run(run_id)

    assert writes == []
    assert not tracked.exists()
    assert not protected.exists()


def test_runtime_has_no_replaceable_root_or_public_signer_api() -> None:
    policy, _, trusted = _modules()

    loader_parameters = inspect.signature(trusted._load_verified_run).parameters

    assert tuple(loader_parameters) == ("registry", "run_id")
    assert not hasattr(policy.TrustedAcceptanceRegistry, "_fixed_run_roots")
    assert not hasattr(policy.TrustedAcceptanceRegistry, "open_materializer")
    assert tuple(
        inspect.signature(policy.TrustedAcceptanceRegistry.finalize_run).parameters
    ) == ("self", "run_id")


def test_runtime_has_no_mutable_operator_root_hook() -> None:
    _, _, trusted = _modules()

    assert not hasattr(trusted, "_PROTECTED_STORE_ROOT")


def test_production_registry_has_only_no_arg_canonical_factory() -> None:
    policy, _, _ = _modules()

    assert tuple(inspect.signature(policy.TrustedAcceptanceRegistry).parameters) == ()
    assert (
        tuple(
            inspect.signature(
                policy.TrustedAcceptanceRegistry.from_canonical_repo
            ).parameters
        )
        == ()
    )
    assert not hasattr(policy.TrustedAcceptanceRegistry, "open_contracts")


def test_production_trust_path_has_no_object_setattr_context_replacement() -> None:
    policy, _, trusted = _modules()

    assert "object.__setattr__" not in inspect.getsource(policy)
    assert "object.__setattr__" not in inspect.getsource(trusted)


def test_snapshot_commit_binds_journal_authorization_attempts_and_store() -> None:
    _, _, trusted = _modules()

    assert {
        "authorization_digest",
        "journal_head_digest",
        "attempt_chain_heads_digest",
        "operator_store_digest",
        "final_readback_receipt_digest",
        "final_inventory_digest",
    } <= set(trusted.ProtectedSnapshotCommit.model_fields)


def test_committed_execution_requires_typed_executed_or_gate_variant() -> None:
    _, _, trusted = _modules()

    assert {"attempt_kind", "gate_attempt"} <= set(
        trusted.CommittedExecutionArtifact.model_fields
    )


def test_finalizer_derives_side_effect_closeout_from_ledger_and_inventory() -> None:
    """The final run contract cannot accept an operator-authored closeout flag."""

    _, _, trusted = _modules()

    assert "side_effect_closeout" not in trusted.TrustedRunDocument.model_fields
    assert {
        "side_effect_ledger_digest",
        "final_inventory_digest",
    } <= set(trusted.TrustedRunDocument.model_fields)


def test_registry_trust_context_is_frozen_and_has_no_mutable_digest_stores() -> None:
    registry = _registry()

    for name in (
        "_trusted_authorization_digests",
        "_trusted_authorizations",
        "_trusted_readback_digests",
        "_trusted_classifier_digests",
        "_trusted_structured_digests",
        "_trusted_attempt_digests",
    ):
        assert not hasattr(registry, name)
    assert not hasattr(registry, "_replace_verified_evidence_context")
    context = registry._verified_evidence_context()
    assert isinstance(context.classifier_digests, frozenset)
    with pytest.raises((AttributeError, TypeError)):
        context.classifier_digests.add("0" * 64)


def test_finalizer_refuses_caller_authored_staging_snapshot(tmp_path: Path) -> None:
    registry, _, protected = _build_verified_run(tmp_path)
    run_id = "caller-staging-only"
    _write_json(
        protected.parent / ".staging" / f"{run_id}.json",
        {
            "schema_version": "noor-e2e-verified-execution-snapshot/v2",
            "run_id": run_id,
        },
    )

    with pytest.raises(Exception, match="protected committed execution snapshot"):
        registry.finalize_run(run_id)


def test_loader_rejects_publication_without_protected_final_commit_marker(
    tmp_path: Path,
) -> None:
    registry, _, protected = _build_verified_run(tmp_path)
    (protected / "final-commit.json").unlink()

    with pytest.raises(Exception, match="final commit marker"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_finalizer_recovers_crash_after_tracked_publication(tmp_path: Path) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    _stage_protected_execution_snapshot(registry, tracked, protected)
    shutil.rmtree(tracked)
    shutil.rmtree(protected)
    tracked.mkdir(parents=True)
    _write_json(tracked / "partial.json", {"status": "prepared"})

    registry.finalize_run(run_id)
    registry.open_run(run_id=run_id)

    assert not (tracked / "partial.json").exists()
    assert (protected / "final-commit.json").is_file()


@pytest.mark.parametrize(
    "marker_bytes",
    (
        b"",
        b'{"schema_version":"noor-e2e-published-run-commit/v2"',
        b"{}\n",
    ),
    ids=("empty", "truncated", "invalid-contract"),
)
def test_finalizer_recovers_partial_final_commit_marker(
    tmp_path: Path,
    marker_bytes: bytes,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    _stage_protected_execution_snapshot(registry, tracked, protected)
    marker = protected / "final-commit.json"
    marker.write_bytes(marker_bytes)
    marker.chmod(0o600)

    registry.finalize_run(run_id)
    registry.open_run(run_id=run_id)

    recovered = json.loads(marker.read_text(encoding="utf-8"))
    assert recovered["status"] == "committed"
    assert not tuple(protected.glob(".final-commit.*"))


def test_finalizer_retries_after_crash_before_final_commit_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    _stage_protected_execution_snapshot(registry, tracked, protected)
    shutil.rmtree(tracked)
    shutil.rmtree(protected)
    _, _, trusted = _modules()
    original_replace = trusted.os.replace

    def crash_before_commit(source, destination) -> None:
        if Path(destination).name == "final-commit.json":
            raise OSError("simulated crash before final marker rename")
        original_replace(source, destination)

    monkeypatch.setattr(trusted.os, "replace", crash_before_commit)
    with pytest.raises(OSError, match="simulated crash"):
        registry.finalize_run(run_id)

    assert not tracked.exists()
    assert not protected.exists()
    monkeypatch.setattr(trusted.os, "replace", original_replace)
    registry.finalize_run(run_id)
    registry.open_run(run_id=run_id)

    assert (protected / "final-commit.json").is_file()


def test_finalizer_removes_orphan_staging_for_same_run(tmp_path: Path) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    run_id = "synthetic-trusted-run"
    _stage_protected_execution_snapshot(registry, tracked, protected)
    shutil.rmtree(tracked)
    shutil.rmtree(protected)
    tracked_orphan = tracked.parent / f".{run_id}.orphan"
    protected_orphan = protected.parent / f".{run_id}.orphan"
    tracked_orphan.mkdir()
    protected_orphan.mkdir()

    registry.finalize_run(run_id)

    assert not tracked_orphan.exists()
    assert not protected_orphan.exists()


def test_runtime_has_no_local_or_caller_decisive_artifact_loader() -> None:
    policy, _, _ = _modules()

    for name in (
        "_load_local_classifier_fixture",
        "_load_classifier_artifact",
        "_load_local_structured_fixture",
        "_register_protected_structured_artifact",
    ):
        assert not hasattr(policy.TrustedAcceptanceRegistry, name)


def test_attempt_digest_must_match_protected_commit(tmp_path: Path) -> None:
    registry, _, _ = _build_verified_run(
        tmp_path,
        protected_attempt_digest_drift=True,
    )

    with pytest.raises(Exception, match="attempt.*digest|protected.*commit"):
        registry.open_run(run_id="synthetic-trusted-run")
