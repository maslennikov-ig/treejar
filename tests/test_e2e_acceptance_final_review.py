"""RED reproductions for final trusted-run and generic-runner review findings."""

from __future__ import annotations

import hashlib
import inspect
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.test_e2e_acceptance_trusted_execution import (
    _authorization,
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
        "schema_version": "noor-e2e-protected-execution-snapshot/v2",
        "run_id": run_id,
        "registry_id": registry.registry_id,
        "execution_ids": list(registry.compiled_plan.execution_ids),
        "run": json.loads((tracked / "registry/run.json").read_text(encoding="utf-8")),
        "report": report,
        "evidence": evidence,
        "attempt_commits": attempt_commits,
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
            "schema_version": "noor-e2e-protected-execution-snapshot-commit/v2",
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
        },
    )


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

    with pytest.raises(Exception, match="turn|scenario.*coverage|report.*coverage"):
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
    authorization = _authorization(registry)
    run_id = "future-anchor-run"
    now = datetime.now(UTC)
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id=run_id,
        authorization=authorization,
    )
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

    with pytest.raises(Exception, match="timestamp|occurred|predate|final-turn"):
        journal.seal_final_readback(final)


def test_trusted_run_module_has_no_public_caller_root_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy, _, trusted = _modules()
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

    with pytest.raises(Exception, match="turn|scenario.*coverage|report.*coverage"):
        registry.finalize_run(run_id)

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
    } <= set(trusted.ProtectedSnapshotCommit.model_fields)


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
