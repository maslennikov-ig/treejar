"""RED reproductions for final trusted-run and generic-runner review findings."""

from __future__ import annotations

import inspect
import json
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
)

EVIDENCE_BLOCK_IDS = tuple(
    item["block_id"]
    for item in json.loads(
        (PROJECT_ROOT / ".codex/stages/tj-ee5f/scenario-set.json").read_text(
            encoding="utf-8"
        )
    )["evidence_blocks"]
)


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
        registry._load_verified_run_roots(tracked, protected)


def test_trusted_report_rejects_one_turn_for_twenty_scenario_executions(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        incomplete_turns=True,
    )

    with pytest.raises(Exception, match="turn|scenario.*coverage|report.*coverage"):
        registry._load_verified_run_roots(tracked, protected)


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
        registry._load_verified_run_roots(tracked, protected)


def test_blocked_outcome_still_requires_valid_evidence_mode_proof(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        invalid_blocked_gate=True,
    )

    with pytest.raises(Exception, match="evidence mode|external gate"):
        registry._load_verified_run_roots(tracked, protected)


def test_excluded_by_client_cannot_authorize_itself(tmp_path: Path) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        self_authorized_exclusion=True,
    )

    with pytest.raises(Exception, match="exclusion|excluded_by_client|external gate"):
        registry._load_verified_run_roots(tracked, protected)


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


def test_trusted_run_module_has_no_public_caller_root_loader() -> None:
    _, _, trusted = _modules()

    assert not hasattr(trusted, "load_verified_run")


def test_trusted_run_rejects_attempt_producer_without_protected_receipt(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        missing_attempt_receipts=True,
    )

    with pytest.raises(Exception, match="protected.*receipt|producer.*receipt"):
        registry._load_verified_run_roots(tracked, protected)


def test_trusted_run_rejects_report_producer_without_protected_receipt(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        missing_report_receipt=True,
    )

    with pytest.raises(Exception, match="protected.*receipt|producer.*receipt"):
        registry._load_verified_run_roots(tracked, protected)


def test_registry_materializer_uses_fixed_roots() -> None:
    policy, _, _ = _modules()

    parameters = inspect.signature(
        policy.TrustedAcceptanceRegistry.open_materializer
    ).parameters

    assert "tracked_root" not in parameters
    assert "protected_root" not in parameters
