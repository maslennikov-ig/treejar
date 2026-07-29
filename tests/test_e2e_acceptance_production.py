"""Contract tests for the local-only production adapter boundary."""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI = PROJECT_ROOT / "scripts/run_noor_e2e_acceptance.py"


def test_cli_exposes_resumable_local_only_lifecycle() -> None:
    completed = subprocess.run(
        [sys.executable, str(CLI), "--help"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    for command in (
        "prepare",
        "preflight",
        "execute-resume",
        "reconcile-action",
        "record-attempt",
        "close-execution",
        "finalize",
    ):
        assert command in completed.stdout


def test_capability_dispatch_never_uses_scenario_identity() -> None:
    from scripts.e2e_acceptance.production import (
        CapabilityDispatcher,
        FakeHttpTransport,
        ProductionAdapterError,
    )

    transport = FakeHttpTransport(responses={"webhook.inbound": {"ok": True}})
    dispatcher = CapabilityDispatcher({"webhook.inbound": transport})

    assert dispatcher.dispatch(
        capability="webhook.inbound",
        request={"event": "message"},
    ) == {"ok": True}
    with pytest.raises(ProductionAdapterError, match="capability"):
        dispatcher.dispatch(capability="scenario-en-new-customer", request={})
    with pytest.raises(ProductionAdapterError, match="registry"):
        CapabilityDispatcher({"SC-OPEN-EN": transport})


def test_validated_attempt_producer_has_no_caller_selected_result_facts() -> None:
    """The public producer owns outcome and all result digests."""

    from scripts.e2e_acceptance.production import produce_validated_execution_attempt

    parameter_names = set(
        inspect.signature(produce_validated_execution_attempt).parameters
    )
    assert {
        "artifact",
        "attempted",
        "outcome",
        "passed",
        "reason",
        "producer",
        "execution_id",
        "semantic_digest",
        "evaluator_digest",
        "evidence_digest",
    }.isdisjoint(parameter_names)
    assert parameter_names == {"producer_handle", "source_output_ref"}


def test_validated_attempt_producer_rejects_arbitrary_handle() -> None:
    from scripts.e2e_acceptance.production import (
        ProductionAdapterError,
        produce_validated_execution_attempt,
    )

    with pytest.raises(ProductionAdapterError, match="handle"):
        produce_validated_execution_attempt(
            producer_handle=object(), source_output_ref="producer-observations/01.json"
        )


def test_source_identity_digest_excludes_evidence_but_binds_source_facts() -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import _attempt_source_identity_digest

    attempt = execution.EvidenceBlockAttemptV2(
        schema_version="noor-e2e-evidence-block-attempt/v2",
        execution_id="EB-01",
        evidence_collection_digest="a" * 64,
        evaluator_config_digest="b" * 64,
        oracle_evidence=(
            {
                "assertion_id": "A-01",
                "structured_events": [],
                "tool_results": [],
                "readbacks": [],
                "classifier_results": [],
                "text_supplements": [],
            },
        ),
        permission_evidence=(),
    )

    assert _attempt_source_identity_digest(
        attempt
    ) != execution.evidence_block_input_digest(attempt)
    assert _attempt_source_identity_digest(
        attempt.model_copy(update={"evidence_collection_digest": "c" * 64})
    ) != _attempt_source_identity_digest(attempt)
    assert _attempt_source_identity_digest(
        attempt.model_copy(update={"permission_evidence": ("fixture:execute",)})
    ) != _attempt_source_identity_digest(attempt)


def _prepared_gate_producer(tmp_path: Path):
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import ProtectedRunPlan, seal_run_plan

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import (
        _issued_authority,
    )

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(registry, protected_root=root, run_id="local-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    plan = ProtectedRunPlan.from_payload(
        {
            "actions": [
                {
                    "spec": item.model_dump(mode="json"),
                    "message_path": f"requests/{item.action_id}.json",
                }
                for item in journal.authorization.action_specs
            ],
            "evaluator": {
                "schema_version": "noor-e2e-protected-evaluator/v1",
                "publication": {"seed": 1},
                "decisive_producers": [
                    {
                        "producer_id": "fake-local-adapter",
                        "producer_kind": "adapter",
                        "capability": "outbound_text",
                        "source_identity": "fake-local-adapter",
                        "config_digest": "a" * 64,
                    }
                ],
            },
        }
    )
    seal_run_plan(journal, plan)
    now = datetime.now(UTC)
    journal.seal_baseline(
        execution.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="baseline",
            run_id="local-run",
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
            causal_event_digest="a" * 64,
            observed_at=now - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    execution_id = registry.compiled_plan.execution_ids[0]
    gate_observed_at = datetime.now(UTC)
    receipt_digest = execution._write_test_gate_evidence_bundle(
        registry=registry,
        journal=journal,
        execution_id=execution_id,
        outcome="BLOCKED",
        producer="independent-readback-collector",
        observed_at=gate_observed_at,
        expires_at=gate_observed_at + timedelta(minutes=1),
    )
    attempt = execution.GateAttemptV2(
        schema_version="noor-e2e-gate-attempt/v2",
        execution_id=execution_id,
        outcome="BLOCKED",
        run_started_at=journal._execution_started_at,
        execution_started_event_digest=journal._execution_started_event_digest,
        receipt_digest=receipt_digest,
    )
    return registry, authority, journal, plan, attempt


def _prepared_executed_producer(
    tmp_path: Path,
    *,
    semantic_customer_text: str | None = None,
    planned_customer_input_digest: str | None = None,
    retention_artifact_id: str | None = None,
    judge_action_updates: dict[str, object] | None = None,
):
    from scripts.e2e_acceptance import execution, policy
    from scripts.e2e_acceptance.production import ProtectedRunPlan, seal_run_plan

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import (
        _action_quota_charge,
        _action_request,
        _issued_authority,
    )

    registry = build_canonical_test_registry()
    scenario_id = registry.compiled_plan.execution_ids[0]
    scenario = registry.compiled_policy.scenarios[scenario_id]
    assertion_ids = {
        item.assertion_id
        for group in (scenario.checkpoints, scenario.prohibited_outcomes)
        for item in group.values()
    }
    for criterion_id in scenario.criterion_ids:
        assertion_ids.update(
            item.assertion_id
            for item in registry.compiled_policy.criteria[
                criterion_id
            ].oracle_checks.values()
        )
    semantic_input_digest = (
        hashlib.sha256(semantic_customer_text.encode()).hexdigest()
        if semantic_customer_text is not None
        else "1" * 64
    )
    planned = execution.PlannedTurnV2(
        turn_id="turn-001",
        customer_input_digest=planned_customer_input_digest or semantic_input_digest,
        expected_behavior_digest="2" * 64,
        criterion_ids=scenario.criterion_ids,
        assertion_ids=tuple(sorted(assertion_ids)),
    )
    semantic_judge = {
        "schema_version": "noor-e2e-semantic-judge/v1",
        "action_id": f"judge-{scenario_id.lower()}",
        "adapter_id": "openrouter-judge-adapter",
        "step_id": f"{scenario_id}:semantic-judge",
        "operation_permission": "paid_model_call",
        "subsystem": "model",
        "destination_digest": execution._digest(
            {
                "adapter_id": "openrouter-judge-adapter",
                "model": "fixture/judge",
                "transport": "openrouter-chat-completions",
            }
        ),
        "idempotency_key": f"judge-{scenario_id.lower()}:{scenario_id}",
        "capability_units": {"model": 1},
        "model": "fixture/judge",
        "temperature": 0,
        "max_calls": 1,
        "max_cost_usd": 0.5,
        "rubric_digest": execution._digest(
            tuple(
                {
                    "assertion_id": assertion_id,
                    "canonical_text": registry.compiled_policy.assertions[
                        assertion_id
                    ].canonical_text,
                    "oracle_kind": registry.compiled_policy.assertions[
                        assertion_id
                    ].oracle.kind,
                }
                for assertion_id in sorted(assertion_ids)
            )
        ),
    }
    judge_config_digest = (
        execution._digest(semantic_judge)
        if semantic_customer_text is not None
        else "6" * 64
    )
    input_digest = execution.scenario_input_digest(
        execution_id=scenario_id,
        planned_turns=(planned,),
        tester_config_digest="5" * 64,
        judge_config_digest=judge_config_digest,
    )
    root = tmp_path / "protected"
    input_digests = {
        identity: "0" * 64 for identity in registry.compiled_plan.execution_ids
    }
    input_digests[scenario_id] = input_digest
    action_specs = None
    judge_request = None
    if semantic_customer_text is not None:
        judge_request = {
            "schema_version": "noor-e2e-semantic-judge-action/v1",
            "execution_id": scenario_id,
            "source_ref": f"collector-raw/executions/{scenario_id}.json",
            "judge_config_digest": judge_config_digest,
        }
        judge_action_values = {
            "action_id": semantic_judge["action_id"],
            "execution_id": scenario_id,
            "step_id": semantic_judge["step_id"],
            "capability": "model.classify",
            "operation_permission": semantic_judge["operation_permission"],
            "adapter_id": "openrouter-judge-adapter",
            "subsystem": semantic_judge["subsystem"],
            "destination_digest": semantic_judge["destination_digest"],
            "payload_digest": execution._digest(judge_request),
            "idempotency_key": semantic_judge["idempotency_key"],
            "capability_units": semantic_judge["capability_units"],
            "quota_charge": execution.AuthorizedQuotaCharge(
                messages=0,
                model_calls=1,
                max_cost_usd=semantic_judge["max_cost_usd"],
                cost_settlement="bounded_actual",
            ),
        }
        judge_action_values.update(judge_action_updates or {})
        action_specs = execution.AuthorizedActionSpecs(
            schema_version="noor-e2e-authorized-action-specs/v2",
            specs=(
                execution.AuthorizedActionSpec(
                    action_id="synthetic-action",
                    adapter_id="wazzup-webhook-adapter",
                    subsystem="outbound_text",
                    quota_charge=_action_quota_charge(execution),
                    **_action_request(),
                ),
                execution.AuthorizedActionSpec(
                    action_id="negative",
                    adapter_id="wazzup-webhook-adapter",
                    subsystem="outbound_text",
                    quota_charge=_action_quota_charge(execution),
                    **_action_request(),
                ),
                execution.AuthorizedActionSpec(**judge_action_values),
            ),
        )
    protected_authorities = None
    if retention_artifact_id is not None:
        authority_now = datetime.now(UTC)
        protected_authorities = execution.ProtectedExecutionAuthorities(
            schema_version="noor-e2e-protected-execution-authorities/v2",
            client_exclusions=(),
            side_effect_authority=execution.SideEffectAuthority(
                issuer="protected-side-effect-authority",
                cleanup_owner="synthetic-local-executor",
                cleanup_authority="synthetic-cleanup",
                retention_authorities=(
                    execution.AuthorizedRetentionSpec(
                        authority_id=f"retain-{scenario_id.lower()}",
                        issuer="client-retention-authority",
                        artifact_id=retention_artifact_id,
                        execution_id=scenario_id,
                        criterion_ids=scenario.criterion_ids,
                        cleanup_owner="synthetic-local-executor",
                        cleanup_authority="synthetic-cleanup",
                        retention_owner="synthetic-retention-owner",
                        issued_at=authority_now - timedelta(minutes=1),
                        expires_at=authority_now + timedelta(minutes=30),
                    ),
                ),
            ),
        )
    authority = _issued_authority(
        registry,
        protected_root=root,
        run_id="local-run",
        execution_input_digests=input_digests,
        protected_authorities=protected_authorities,
        action_specs=action_specs,
        permissions=(
            ("fixture:execute", "paid_model_call")
            if semantic_customer_text is not None
            else None
        ),
        quotas=(
            execution.ProtectedQuotas(
                max_scenarios=29,
                max_messages=2,
                max_model_calls=2,
                max_cost_usd=1.0,
                subsystem_quotas={"outbound_text": 2, "model": 1},
            )
            if semantic_customer_text is not None
            else None
        ),
        runtime_with_judge=semantic_customer_text is not None,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    if judge_request is not None:
        execution._write_exclusive(
            journal.run_root,
            f"requests/{semantic_judge['action_id']}.json",
            judge_request,
        )
    bindings: dict[str, dict[str, str]] = {}
    oracle_evidence = []
    now = datetime.now(UTC)
    for assertion_id in sorted(assertion_ids):
        assertion = registry.compiled_policy.assertions[assertion_id]
        if assertion.oracle.kind == "classifier_result":
            producer = assertion.oracle.allowed_producers[0]
            classifier_id = assertion.oracle.classifier_id
            bindings[producer] = {
                "producer_kind": "classifier",
                "source_identity": classifier_id,
            }
            artifact = policy.ClassifierResult.build(
                assertion_id=assertion_id,
                policy_digest=registry.compiled_policy.policy_digest,
                evaluator_digest=registry.classifier_evaluator_digest(assertion_id),
                run_id="local-run",
                attempt_digest=input_digest,
                preflight_digest=journal.authorization.preflight_digest,
                classifier_id=classifier_id,
                producer=producer,
                source_id=f"{assertion_id}:classifier",
                source_digest="3" * 64,
                observed_at=now,
                passed=True,
                reason="Local classifier passed.",
            )
            oracle_evidence.append(
                policy.OracleEvidence(
                    assertion_id=assertion_id,
                    structured_events=(),
                    tool_results=(),
                    readbacks=(),
                    classifier_results=(artifact,),
                    text_supplements=(),
                )
            )
        else:
            producer = "production-policy-classifier"
            if producer not in assertion.oracle.allowed_producers:
                producer = assertion.oracle.allowed_producers[0]
            if producer == "independent-readback-collector":
                bindings[producer] = {
                    "producer_kind": "collector",
                    "source_identity": producer,
                }
            else:
                bindings[producer] = {
                    "producer_kind": "classifier",
                    "source_identity": "scenario_policy.v2",
                }
            artifact = policy.StructuredEvent.build(
                assertion_id=assertion_id,
                producer=producer,
                source_id=f"{assertion_id}:event",
                source_digest="4" * 64,
                observed_at=now,
                passed=True,
                reason="Local structured evidence passed.",
                run_id="local-run",
                attempt_digest=input_digest,
                preflight_digest=journal.authorization.preflight_digest,
            )
            oracle_evidence.append(
                policy.OracleEvidence(
                    assertion_id=assertion_id,
                    structured_events=(artifact,),
                    tool_results=(),
                    readbacks=(),
                    classifier_results=(),
                    text_supplements=(),
                )
            )
    publication: dict[str, object] = {"seed": 1}
    if semantic_customer_text is not None:
        publication["semantic_compiler"] = {
            "schema_version": "noor-e2e-semantic-compiler/v1",
            "compiler_id": "treejar.live-semantic-compiler.v1",
            "scenarios": {
                scenario_id: {
                    "execution_id": scenario_id,
                    "planned_turns": [planned.model_dump(mode="json")],
                    "tester_config_digest": "5" * 64,
                    "judge_config_digest": judge_config_digest,
                    "input_text_sha256": {planned.turn_id: semantic_input_digest},
                    "judge": semantic_judge,
                }
            },
        }
    plan = ProtectedRunPlan.from_payload(
        {
            "actions": [
                {
                    "spec": item.model_dump(mode="json"),
                    "message_path": f"requests/{item.action_id}.json",
                }
                for item in journal.authorization.action_specs
            ],
            "evaluator": {
                "schema_version": "noor-e2e-protected-evaluator/v1",
                "publication": publication,
                "decisive_producers": [
                    {
                        "producer_id": producer,
                        "producer_kind": binding["producer_kind"],
                        "capability": "outbound_text",
                        "source_identity": binding["source_identity"],
                        "config_digest": (
                            judge_config_digest
                            if binding["producer_kind"] == "classifier"
                            else "a" * 64
                        ),
                    }
                    for producer, binding in sorted(bindings.items())
                ],
            },
        }
    )
    seal_run_plan(journal, plan)
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="baseline",
        run_id="local-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
        causal_event_digest="4" * 64,
        observed_at=now - timedelta(seconds=2),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    final = policy.ReadbackObservation.build(
        phase="final",
        collector_id="independent-readback-collector",
        source_id="final",
        run_id="local-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
        causal_event_digest="5" * 64,
        observed_at=now + timedelta(seconds=2),
        inventory={"synthetic:item": {"state": "closed"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    timeline = execution.TurnTimelineV2(
        sent_at=now,
        first_visible_at=now + timedelta(milliseconds=1),
        final_visible_at=now + timedelta(milliseconds=2),
        delivered_at=now + timedelta(milliseconds=3),
    )
    actual = execution.ActualTurnV2(
        actual_turn_id="turn-001",
        planned_turn_id="turn-001",
        customer_input_digest=planned.customer_input_digest,
        expected_behavior_digest=planned.expected_behavior_digest,
        criterion_ids=planned.criterion_ids,
        assertion_ids=planned.assertion_ids,
        event_refs=("event",),
        tool_refs=(),
        audit_refs=("audit",),
        timeline=timeline,
        model_id="fixture/model",
        token_count=1,
        cost_usd=0,
    )
    attempt = execution.ScenarioAttemptV2(
        schema_version="noor-e2e-scenario-attempt/v2",
        execution_id=scenario_id,
        planned_turns=(planned,),
        actual_turns=(actual,),
        adaptive_deviations=(),
        oracle_evidence=tuple(oracle_evidence),
        permission_evidence=scenario.required_permissions,
        readback_evidence=scenario.required_readbacks,
        baseline=baseline,
        final=final,
        action_at=(now + timedelta(milliseconds=2),),
        tester_config_digest="5" * 64,
        judge_config_digest=judge_config_digest,
    )
    return registry, authority, journal, plan, attempt


def test_producer_handle_commits_only_private_protected_source_output(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.production import (
        _write_local_fake_producer_observation,
        issue_decisive_producer_handle,
        produce_validated_execution_attempt,
    )

    registry, authority, journal, plan, attempt = _prepared_gate_producer(tmp_path)
    handle = issue_decisive_producer_handle(
        registry=registry, journal=journal, authority=authority, sealed_plan=plan
    )
    source_ref = _write_local_fake_producer_observation(
        producer_handle=handle, attempted=attempt
    )

    produced = produce_validated_execution_attempt(
        producer_handle=handle, source_output_ref=source_ref
    )

    assert produced.artifact["execution_id"] == attempt.execution_id
    assert produced.artifact["outcome"] == "BLOCKED"
    assert (journal.run_root / produced.artifact["protected_commit_ref"]).is_file()


def test_producer_handle_derives_pass_from_private_executed_evidence(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.production import (
        _write_local_fake_producer_observation,
        issue_decisive_producer_handle,
        produce_validated_execution_attempt,
    )

    registry, authority, journal, plan, attempt = _prepared_executed_producer(tmp_path)
    handle = issue_decisive_producer_handle(
        registry=registry, journal=journal, authority=authority, sealed_plan=plan
    )
    source_ref = _write_local_fake_producer_observation(
        producer_handle=handle, attempted=attempt
    )

    produced = produce_validated_execution_attempt(
        producer_handle=handle, source_output_ref=source_ref
    )

    assert produced.artifact["execution_id"] == attempt.execution_id
    assert produced.artifact["outcome"] == "PASS"


def test_coordinator_publishes_a_produced_attempt_without_caller_result_facts(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.coordinator import (
        ProductionRunCoordinator,
        ProtectedJournalAcceptancePort,
    )
    from scripts.e2e_acceptance.production import (
        _write_local_fake_producer_observation,
        issue_decisive_producer_handle,
    )

    registry, authority, journal, plan, attempt = _prepared_executed_producer(tmp_path)
    coordinator = ProductionRunCoordinator(
        registry=registry,
        authorization=authority._authorization,
        protected_root=journal.protected_root,
        run_id=journal.run_id,
        journal=ProtectedJournalAcceptancePort(journal=journal),
        current_time=datetime.now(UTC),
    )
    handle = issue_decisive_producer_handle(
        registry=registry, journal=journal, authority=authority, sealed_plan=plan
    )
    source_ref = _write_local_fake_producer_observation(
        producer_handle=handle, attempted=attempt
    )

    artifact = coordinator.publish_next_from_decisive_producer(handle, source_ref)

    assert artifact.execution_id == attempt.execution_id
    assert artifact.outcome == "PASS"
    assert (journal.run_root / coordinator.producer_artifact_path(1)).is_file()


def test_producer_handle_rejects_missing_private_source_receipt(tmp_path: Path) -> None:
    from scripts.e2e_acceptance.production import (
        ProductionAdapterError,
        _write_local_fake_producer_observation,
        issue_decisive_producer_handle,
        produce_validated_execution_attempt,
    )

    registry, authority, journal, plan, attempt = _prepared_gate_producer(tmp_path)
    handle = issue_decisive_producer_handle(
        registry=registry, journal=journal, authority=authority, sealed_plan=plan
    )
    source_ref = _write_local_fake_producer_observation(
        producer_handle=handle, attempted=attempt
    )
    (journal.run_root / "producer-receipts/observations/01.json").unlink()

    with pytest.raises(ProductionAdapterError, match="protected JSON|receipt"):
        produce_validated_execution_attempt(
            producer_handle=handle, source_output_ref=source_ref
        )


def test_producer_handle_rejects_tampered_private_source_receipt(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.production import (
        ProductionAdapterError,
        _write_local_fake_producer_observation,
        issue_decisive_producer_handle,
        produce_validated_execution_attempt,
    )

    registry, authority, journal, plan, attempt = _prepared_gate_producer(tmp_path)
    handle = issue_decisive_producer_handle(
        registry=registry, journal=journal, authority=authority, sealed_plan=plan
    )
    source_ref = _write_local_fake_producer_observation(
        producer_handle=handle, attempted=attempt
    )
    receipt_path = journal.run_root / "producer-receipts/observations/01.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["source_attempt_digest"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(ProductionAdapterError, match="source receipt"):
        produce_validated_execution_attempt(
            producer_handle=handle, source_output_ref=source_ref
        )


@pytest.mark.parametrize(
    ("crash_relative", "after_write"),
    (
        ("produced-attempts/01.json", False),
        ("producer-receipts/attempts/SC-OPEN-EN.json", False),
    ),
)
def test_producer_recovers_committed_transaction_after_partial_public_pair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    crash_relative: str,
    after_write: bool,
) -> None:
    from scripts.e2e_acceptance import execution, production

    registry, authority, journal, plan, attempt = _prepared_gate_producer(tmp_path)
    handle = production.issue_decisive_producer_handle(
        registry=registry, journal=journal, authority=authority, sealed_plan=plan
    )
    source_ref = production._write_local_fake_producer_observation(
        producer_handle=handle, attempted=attempt
    )
    original_write = production._write_or_validate_exact

    def crash(target_root, relative, value):
        if relative == crash_relative and not after_write:
            raise RuntimeError("crash before public pair")
        digest = original_write(target_root, relative, value)
        if relative == crash_relative:
            raise RuntimeError("crash after public pair")
        return digest

    monkeypatch.setattr(production, "_write_or_validate_exact", crash)
    with pytest.raises(RuntimeError, match="crash"):
        production.produce_validated_execution_attempt(
            producer_handle=handle, source_output_ref=source_ref
        )
    monkeypatch.setattr(production, "_write_or_validate_exact", original_write)
    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=journal.protected_root,
        run_id=journal.run_id,
        authority=authority,
    )
    recovered_handle = production.issue_decisive_producer_handle(
        registry=registry, journal=reopened, authority=authority, sealed_plan=plan
    )
    recovered = production.produce_validated_execution_attempt(
        producer_handle=recovered_handle, source_output_ref=source_ref
    )

    assert recovered.artifact["execution_id"] == attempt.execution_id
    assert (reopened.run_root / "produced-attempts/01.json").is_file()
    assert (
        reopened.run_root / f"producer-receipts/attempts/{attempt.execution_id}.json"
    ).is_file()


@pytest.mark.parametrize("caller_outcome", ("PASS", "FAIL"))
def test_producer_recovery_rejects_caller_authored_committed_outcome(
    tmp_path: Path, caller_outcome: str
) -> None:
    from scripts.e2e_acceptance import production

    registry, authority, journal, plan, attempt = _prepared_gate_producer(tmp_path)
    handle = production.issue_decisive_producer_handle(
        registry=registry, journal=journal, authority=authority, sealed_plan=plan
    )
    source_ref = production._write_local_fake_producer_observation(
        producer_handle=handle, attempted=attempt
    )
    transaction = journal.begin_attempt(
        execution_id=attempt.execution_id,
        attempt_number=1,
        intent_digest="a" * 64,
    )
    transaction.write_raw(
        {
            "schema_version": "noor-e2e-attempt-result/v2",
            "execution_id": attempt.execution_id,
            "outcome": caller_outcome,
            "attempt_kind": "executed",
            "gate_attempt_digest": None,
            "attempt_digest": "a" * 64,
            "semantic_digest": "b" * 64,
            "evaluator_digest": "c" * 64,
            "evidence_digest": "d" * 64,
        }
    )
    transaction.write_tracked()
    assert transaction.commit().status == "committed"

    with pytest.raises(production.ProductionAdapterError, match="producer validation"):
        production.produce_validated_execution_attempt(
            producer_handle=handle, source_output_ref=source_ref
        )

    assert not (journal.run_root / "produced-attempts/01.json").exists()
    assert not (
        journal.run_root / f"producer-receipts/attempts/{attempt.execution_id}.json"
    ).exists()


def test_producer_recovery_rejects_tampered_committed_raw(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.e2e_acceptance import production

    registry, authority, journal, plan, attempt = _prepared_gate_producer(tmp_path)
    handle = production.issue_decisive_producer_handle(
        registry=registry, journal=journal, authority=authority, sealed_plan=plan
    )
    source_ref = production._write_local_fake_producer_observation(
        producer_handle=handle, attempted=attempt
    )
    original_write = production._write_or_validate_exact

    def crash_before_artifact(target_root, relative, value):
        if relative == "produced-attempts/01.json":
            raise RuntimeError("crash")
        return original_write(target_root, relative, value)

    monkeypatch.setattr(production, "_write_or_validate_exact", crash_before_artifact)
    with pytest.raises(RuntimeError, match="crash"):
        production.produce_validated_execution_attempt(
            producer_handle=handle, source_output_ref=source_ref
        )
    monkeypatch.setattr(production, "_write_or_validate_exact", original_write)
    raw_path = journal.run_root / "attempts/sc-open-en-attempt-001/raw.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw["outcome"] = "PASS"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(production.ProductionAdapterError, match="recovery binding"):
        production.produce_validated_execution_attempt(
            producer_handle=handle, source_output_ref=source_ref
        )


def test_producer_handle_rejects_cross_execution_source_reuse(tmp_path: Path) -> None:
    from scripts.e2e_acceptance.production import (
        ProductionAdapterError,
        _write_local_fake_producer_observation,
        issue_decisive_producer_handle,
        produce_validated_execution_attempt,
    )

    registry, authority, journal, plan, attempt = _prepared_gate_producer(tmp_path)
    first_handle = issue_decisive_producer_handle(
        registry=registry, journal=journal, authority=authority, sealed_plan=plan
    )
    first_ref = _write_local_fake_producer_observation(
        producer_handle=first_handle, attempted=attempt
    )
    produce_validated_execution_attempt(
        producer_handle=first_handle, source_output_ref=first_ref
    )
    second_handle = issue_decisive_producer_handle(
        registry=registry, journal=journal, authority=authority, sealed_plan=plan
    )

    with pytest.raises(ProductionAdapterError, match="source reference"):
        produce_validated_execution_attempt(
            producer_handle=second_handle, source_output_ref=first_ref
        )


def test_decisive_adapter_binding_requires_exact_authorized_source_identity(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.production import (
        DecisiveProducerBinding,
        ProductionAdapterError,
        _validate_decisive_binding,
    )

    registry, _, journal, _, _ = _prepared_gate_producer(tmp_path)
    with pytest.raises(ProductionAdapterError, match="authority drift"):
        _validate_decisive_binding(
            binding=DecisiveProducerBinding(
                producer_id="fake-local-adapter",
                producer_kind="adapter",
                capability="outbound_text",
                source_identity="forged-adapter",
                config_digest="a" * 64,
            ),
            journal=journal,
            registry=registry,
        )


def test_execution_assertion_scope_rejects_foreign_assertion(tmp_path: Path) -> None:
    from scripts.e2e_acceptance.production import (
        ProductionAdapterError,
        _execution_assertion_ids,
        _require_execution_assertion,
    )

    registry, _, _, _, attempt = _prepared_executed_producer(tmp_path)
    foreign = next(
        assertion_id
        for assertion_id in registry.compiled_policy.assertions
        if assertion_id not in _execution_assertion_ids(registry, attempt.execution_id)
    )

    with pytest.raises(ProductionAdapterError, match="ownership"):
        _require_execution_assertion(registry, attempt.execution_id, foreign)


def test_aborted_attempt_intent_cannot_advance_producer_execution_scope(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import (
        ProductionAdapterError,
        ProtectedRunPlan,
        issue_decisive_producer_handle,
        seal_run_plan,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _issued_authority

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(registry, protected_root=root, run_id="local-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    plan = ProtectedRunPlan.from_payload(
        {
            "actions": [
                {
                    "spec": item.model_dump(mode="json"),
                    "message_path": f"requests/{item.action_id}.json",
                }
                for item in journal.authorization.action_specs
            ],
            "evaluator": {
                "schema_version": "noor-e2e-protected-evaluator/v1",
                "publication": {"seed": 1},
                "decisive_producers": [
                    {
                        "producer_id": "fake-local-adapter",
                        "producer_kind": "adapter",
                        "capability": "outbound_text",
                        "source_identity": "fake-local-adapter",
                        "config_digest": "a" * 64,
                    }
                ],
            },
        }
    )
    seal_run_plan(journal, plan)
    now = datetime.now(UTC)
    journal.seal_baseline(
        execution.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="baseline",
            run_id="local-run",
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
            causal_event_digest="a" * 64,
            observed_at=now - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    transaction = journal.begin_attempt(
        execution_id=registry.compiled_plan.execution_ids[0],
        attempt_number=1,
        intent_digest="b" * 64,
    )
    assert transaction.commit().status == "aborted"

    with pytest.raises(ProductionAdapterError, match="uncommitted.*recovery"):
        issue_decisive_producer_handle(
            registry=registry,
            journal=journal,
            authority=authority,
            sealed_plan=plan,
        )


@pytest.mark.parametrize(
    "evaluator",
    (
        {"seed": 1},
        {
            "schema_version": "noor-e2e-protected-evaluator/v1",
            "publication": {},
            "decisive_producers": [],
        },
    ),
)
def test_protected_plan_rejects_arbitrary_or_empty_producer_config(
    evaluator: dict[str, object],
) -> None:
    from scripts.e2e_acceptance.production import (
        ProductionAdapterError,
        ProtectedRunPlan,
    )

    with pytest.raises(ProductionAdapterError, match="evaluator"):
        ProtectedRunPlan.from_payload(
            {"actions": [{"action_id": "fixture"}], "evaluator": evaluator}
        )


def test_fake_transport_marks_post_dispatch_failure_uncertain() -> None:
    from scripts.e2e_acceptance.production import (
        DispatchUncertainError,
        FakeHttpTransport,
    )

    transport = FakeHttpTransport(
        responses={"webhook.inbound": {"ok": True}},
        uncertain_capabilities={"webhook.inbound"},
    )

    with pytest.raises(DispatchUncertainError, match="after dispatch"):
        transport.request("webhook.inbound", {"event": "message"})
    assert transport.calls == (("webhook.inbound", {"event": "message"}),)


def test_read_only_collector_has_no_mutating_transport_surface() -> None:
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
    )

    raw = b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
    transport = FakeReadOnlySshTransport(responses={"inventory": raw})
    collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=transport,
    )

    observation = collector.observe(
        source_id="baseline",
        run_id="local-run",
        preflight_digest="a" * 64,
        collector_artifact_digest="b" * 64,
        causal_event_digest="c" * 64,
    )

    assert observation.inventory == {"synthetic:item": {"state": "absent"}}
    assert observation.collector_artifact_digest == "b" * 64
    assert not hasattr(collector, "execute")
    assert not hasattr(transport, "execute")
    assert hashlib.sha256(raw).hexdigest() == transport.response_digests["inventory"]


def test_collector_emits_task1_final_artifact_and_receipt_layout(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _issued_authority

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(registry, protected_root=root, run_id="local-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    now = datetime.now(UTC)
    baseline = execution.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="baseline",
        run_id="local-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
        causal_event_digest="a" * 64,
        observed_at=now - timedelta(seconds=2),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    journal.anchor_final_turn(
        event_digest="b" * 64, occurred_at=now - timedelta(seconds=1)
    )
    collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={
                "inventory": b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
            }
        ),
    )

    final = collector.seal_final(journal, source_id="final", observed_at=now)

    assert final.phase == "final"
    assert journal.phase == "final_readback_sealed"
    receipt = json.loads(
        execution._read_protected(
            journal.run_root, "producer-receipts/final-readback.json"
        )
    )
    assert receipt["producer"] == "independent-readback-collector"


def test_baseline_requires_producer_artifact_not_caller_json(tmp_path: Path) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
        load_protected_baseline,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _issued_authority

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(registry, protected_root=root, run_id="local-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    now = datetime.now(UTC)
    caller_json = execution.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="caller",
        run_id="local-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
        causal_event_digest=journal.previous_event_digest or "a" * 64,
        observed_at=now,
        inventory={"synthetic:item": {"state": "absent"}},
    )
    execution._write_exclusive(
        journal.run_root, "caller-baseline.json", caller_json.model_dump(mode="json")
    )

    with pytest.raises(Exception, match="producer"):
        load_protected_baseline(
            journal, artifact_path="caller-baseline.json", current_time=now
        )

    collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={
                "inventory": b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
            }
        ),
    )
    collector.seal_baseline(journal, source_id="collector", observed_at=now)
    # Simulate a restart after producer files are durable but before preflight seals.
    collector.seal_baseline(journal, source_id="collector", observed_at=now)
    assert (
        load_protected_baseline(
            journal,
            artifact_path="collector-artifacts/baseline-readback.json",
            current_time=now,
        ).phase
        == "baseline"
    )


def test_sealed_run_plan_rejects_replacement_after_restart(tmp_path: Path) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import (
        ProtectedRunPlan,
        load_sealed_run_plan,
        seal_run_plan,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _issued_authority

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(registry, protected_root=root, run_id="local-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    specs = [
        item.model_dump(mode="json") for item in journal.authorization.action_specs
    ]
    plan = ProtectedRunPlan.from_payload(
        {
            "actions": [
                {"spec": spec, "message_path": f"requests/{spec['action_id']}.json"}
                for spec in specs
            ],
            "evaluator": {
                "schema_version": "noor-e2e-protected-evaluator/v1",
                "publication": {"seed": 1},
                "decisive_producers": [
                    {
                        "producer_id": "fake-local-adapter",
                        "producer_kind": "adapter",
                        "capability": "outbound_text",
                        "source_identity": "fake-local-adapter",
                        "config_digest": "a" * 64,
                    }
                ],
            },
        }
    )

    seal_run_plan(journal, plan)
    assert load_sealed_run_plan(journal, plan) == plan
    replacement = ProtectedRunPlan.from_payload(
        {
            "actions": [
                {
                    "spec": spec,
                    "message_path": (
                        "requests/other.json"
                        if spec["action_id"] == "synthetic-action"
                        else f"requests/{spec['action_id']}.json"
                    ),
                }
                for spec in specs
            ],
            "evaluator": {
                "schema_version": "noor-e2e-protected-evaluator/v1",
                "publication": {"seed": 1},
                "decisive_producers": [
                    {
                        "producer_id": "fake-local-adapter",
                        "producer_kind": "adapter",
                        "capability": "outbound_text",
                        "source_identity": "fake-local-adapter",
                        "config_digest": "a" * 64,
                    }
                ],
            },
        }
    )
    with pytest.raises(Exception, match="sealed"):
        load_sealed_run_plan(journal, replacement)


def test_cli_does_not_expose_caller_selected_gate_recording() -> None:
    from scripts import run_noor_e2e_acceptance as cli

    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["record-gate"])


def test_adapter_consumes_exact_permit_before_transport_and_projects_checksum(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance import production

    root = (tmp_path / "protected").resolve()
    root.mkdir()
    events: list[str] = []

    class Journal:
        run_root = root
        protected_root = root
        run_id = "local-run"
        authorization = SimpleNamespace(
            store_ids=SimpleNamespace(
                tracked_store_id="tracked",
                tracked_root_digest=production.execution.store_root_digest(
                    (root / "tracked").resolve()
                ),
            )
        )

        def consume_permit(self, reservation, **request) -> None:
            events.append("permit")
            assert reservation.action_id == "action-1"
            assert request["payload_digest"] == production._digest({"text": "local"})

    class Transport:
        def preflight(self, capability, request) -> None:
            assert capability.value == "webhook.inbound"

        def request(self, capability, request):
            events.append("transport")
            assert capability == "webhook.inbound"
            assert request == {"text": "local"}
            return {"receipt": "local"}

    production.write_protected_message(
        Journal(), action_id="action-1", payload={"text": "local"}
    )
    adapter = production.WazzupWebhookAdapter(
        adapter_id="adapter-1",
        journal=Journal(),
        dispatcher=production.CapabilityDispatcher({"webhook.inbound": Transport()}),
    )
    reservation = SimpleNamespace(adapter_id="adapter-1", action_id="action-1")
    digest = production._digest({"text": "local"})

    result = adapter.dispatch(
        reservation,
        message_path="requests/action-1.json",
        execution_id="unit",
        step_id="step",
        capability="webhook.inbound",
        operation_permission="fixture:execute",
        destination_digest="a" * 64,
        payload_digest=digest,
        idempotency_key="idempotent",
        capability_units={"outbound_text": 1},
    )
    assert events == ["permit", "transport"]
    raw = production.execution._read_protected(root, "adapter-responses/action-1.json")
    tracked = json.loads(
        production.execution._read_protected(
            root, "tracked/local-run/adapter-responses/action-1.json"
        )
    )
    assert tracked["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert tracked["response"] == {"receipt": "local"}
    assert result.projection == {"receipt": "local"}
    assert "receipt" not in result.model_dump(exclude={"projection"})


def test_timeout_before_dispatch_does_not_create_transport_call() -> None:
    from scripts.e2e_acceptance.production import (
        Capability,
        DispatchTimeoutError,
        FakeHttpTransport,
    )

    transport = FakeHttpTransport(
        responses={"webhook.inbound": {"ok": True}},
        timeout_capabilities={"webhook.inbound"},
    )

    with pytest.raises(DispatchTimeoutError, match="before dispatch"):
        transport.preflight(Capability.WEBHOOK_INBOUND, {"event": "message"})
    assert transport.calls == ()


def test_adapter_pre_dispatch_timeout_leaves_permit_unconsumed(tmp_path: Path) -> None:
    from scripts.e2e_acceptance import production

    root = (tmp_path / "protected").resolve()
    root.mkdir()
    consumed: list[str] = []

    class Journal:
        run_root = root
        protected_root = root
        run_id = "local-run"
        authorization = SimpleNamespace(
            store_ids=SimpleNamespace(
                tracked_store_id="tracked",
                tracked_root_digest=production.execution.store_root_digest(
                    (root / "tracked").resolve()
                ),
            )
        )

        def consume_permit(self, reservation, **request) -> None:
            consumed.append(reservation.action_id)

    production.write_protected_message(
        Journal(), action_id="action-1", payload={"text": "local"}
    )
    digest = production._digest({"text": "local"})
    adapter = production.WazzupWebhookAdapter(
        adapter_id="adapter-1",
        journal=Journal(),
        dispatcher=production.CapabilityDispatcher(
            {
                "webhook.inbound": production.FakeHttpTransport(
                    responses={"webhook.inbound": {"ok": True}},
                    timeout_capabilities={"webhook.inbound"},
                )
            }
        ),
    )

    with pytest.raises(production.DispatchTimeoutError):
        adapter.dispatch(
            SimpleNamespace(adapter_id="adapter-1", action_id="action-1"),
            message_path="requests/action-1.json",
            execution_id="unit",
            step_id="step",
            capability="webhook.inbound",
            operation_permission="fixture:execute",
            destination_digest="a" * 64,
            payload_digest=digest,
            idempotency_key="idempotent",
            capability_units={"outbound_text": 1},
        )
    assert consumed == []


def test_adapter_nested_sensitive_response_stays_only_in_protected_raw(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance import production

    root = (tmp_path / "protected").resolve()
    root.mkdir()

    class Journal:
        run_root = root
        protected_root = root
        run_id = "local-run"
        authorization = SimpleNamespace(
            store_ids=SimpleNamespace(
                tracked_store_id="tracked",
                tracked_root_digest=production.execution.store_root_digest(
                    (root / "tracked").resolve()
                ),
            )
        )

        def consume_permit(self, reservation, **request) -> None:
            return None

    class Transport:
        def preflight(self, capability, request) -> None:
            return None

        def request(self, capability, request):
            return {"nested": {"production_logs": ["private raw collector record"]}}

    production.write_protected_message(
        Journal(), action_id="action-1", payload={"text": "local"}
    )
    result = production.WazzupWebhookAdapter(
        adapter_id="adapter-1",
        journal=Journal(),
        dispatcher=production.CapabilityDispatcher({"webhook.inbound": Transport()}),
    ).dispatch(
        SimpleNamespace(adapter_id="adapter-1", action_id="action-1"),
        message_path="requests/action-1.json",
        execution_id="unit",
        step_id="step",
        capability="webhook.inbound",
        operation_permission="fixture:execute",
        destination_digest="a" * 64,
        payload_digest=production._digest({"text": "local"}),
        idempotency_key="idempotent",
        capability_units={"outbound_text": 1},
    )
    raw = production.execution._read_protected(root, "adapter-responses/action-1.json")
    tracked = production.execution._read_protected(
        root, "tracked/local-run/adapter-responses/action-1.json"
    )
    assert b"private raw collector record" in raw
    assert b"private raw collector record" not in tracked
    assert b"private raw collector record" not in result.model_dump_json().encode()


def _prepared_collector_journal(tmp_path: Path):
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _issued_authority

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(registry, protected_root=root, run_id="local-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={
                "inventory": b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
            }
        ),
    )
    return execution, authority, root, journal, collector


def _final_collector_journal(tmp_path: Path):
    execution, authority, root, journal, collector = _prepared_collector_journal(
        tmp_path
    )
    now = datetime.now(UTC)
    journal.seal_baseline(
        execution.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="baseline",
            run_id="local-run",
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
            causal_event_digest="a" * 64,
            observed_at=now - timedelta(seconds=2),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    journal.anchor_final_turn(
        event_digest="b" * 64, occurred_at=now - timedelta(seconds=1)
    )
    return execution, authority, root, journal, collector


@pytest.mark.parametrize("phase", ("baseline", "final"))
def test_collector_validates_raw_before_writing_producer_files(
    tmp_path: Path, phase: str
) -> None:
    from scripts.e2e_acceptance.production import ProductionAdapterError

    setup = (
        _prepared_collector_journal if phase == "baseline" else _final_collector_journal
    )
    _, _, root, journal, collector = setup(tmp_path)
    collector.transport.responses["inventory"] = b'{"not_inventory":{}}'

    with pytest.raises(ProductionAdapterError, match="lacks inventory"):
        if phase == "baseline":
            collector.seal_baseline(journal, source_id="baseline")
        else:
            collector.seal_final(journal, source_id="final")

    assert not (root / "local-run" / "collector-raw" / f"{phase}.json").exists()
    assert not (
        root / "local-run" / "collector-artifacts" / f"{phase}-readback.json"
    ).exists()


@pytest.mark.parametrize(
    "crash_after",
    (
        "collector-raw/baseline.json",
        "collector-artifacts/baseline-readback.json",
        "producer-receipts/baseline-readback.json",
    ),
)
def test_baseline_collector_reopens_partial_producer_transaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, crash_after: str
) -> None:
    from scripts.e2e_acceptance import production

    execution, authority, root, journal, collector = _prepared_collector_journal(
        tmp_path
    )
    original_write = production._write_or_validate_exact

    def crash_after_write(target_root, relative, value):
        digest = original_write(target_root, relative, value)
        if relative == crash_after:
            raise RuntimeError(f"crash after {relative}")
        return digest

    monkeypatch.setattr(production, "_write_or_validate_exact", crash_after_write)
    with pytest.raises(RuntimeError, match="crash"):
        collector.seal_baseline(journal, source_id="baseline")
    monkeypatch.setattr(production, "_write_or_validate_exact", original_write)

    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=root, run_id="local-run", authority=authority
    )
    collector.transport.timeout_reads = frozenset({"inventory"})
    baseline = collector.seal_baseline(reopened, source_id="baseline")
    reopened.seal_baseline(baseline)
    assert reopened.phase == "baseline_sealed"
    assert (
        sum(
            "baseline_sealed" in path.read_text(encoding="utf-8")
            for path in (root / "local-run" / "journal").glob("*.json")
        )
        == 1
    )


@pytest.mark.parametrize(
    "crash_after",
    (
        "collector-raw/final.json",
        "collector-artifacts/final-readback.json",
        "producer-receipts/final-readback.json",
    ),
)
def test_final_collector_reopens_partial_producer_transaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, crash_after: str
) -> None:
    from scripts.e2e_acceptance import production

    execution, authority, root, journal, collector = _final_collector_journal(tmp_path)
    original_write = production._write_or_validate_exact

    def crash_after_write(target_root, relative, value):
        digest = original_write(target_root, relative, value)
        if relative == crash_after:
            raise RuntimeError(f"crash after {relative}")
        return digest

    monkeypatch.setattr(production, "_write_or_validate_exact", crash_after_write)
    with pytest.raises(RuntimeError, match="crash"):
        collector.seal_final(journal, source_id="final")
    monkeypatch.setattr(production, "_write_or_validate_exact", original_write)

    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=root, run_id="local-run", authority=authority
    )
    collector.transport.timeout_reads = frozenset({"inventory"})
    assert collector.seal_final(reopened, source_id="final").phase == "final"
    assert reopened.phase == "final_readback_sealed"
    assert (
        sum(
            "final_readback_sealed" in path.read_text(encoding="utf-8")
            for path in (root / "local-run" / "journal").glob("*.json")
        )
        == 1
    )


def test_final_collector_rejects_differing_replay_after_durable_raw(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.e2e_acceptance import production

    execution, authority, root, journal, collector = _final_collector_journal(tmp_path)
    original_write = production._write_or_validate_exact

    def crash_after_raw(target_root, relative, value):
        digest = original_write(target_root, relative, value)
        if relative == "collector-raw/final.json":
            raise RuntimeError("crash after raw")
        return digest

    monkeypatch.setattr(production, "_write_or_validate_exact", crash_after_raw)
    with pytest.raises(RuntimeError, match="crash"):
        collector.seal_final(journal, source_id="final")
    monkeypatch.setattr(production, "_write_or_validate_exact", original_write)
    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=root, run_id="local-run", authority=authority
    )
    with pytest.raises(production.ProductionAdapterError, match="differs"):
        collector.seal_final(
            reopened,
            source_id="final",
            replay_raw=b'{"inventory":{"synthetic:item":{"state":"present"}}}',
        )
    assert reopened.phase == "final_turn_anchored"


def test_final_collector_recovers_after_crash_before_and_after_journal_seal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    execution, authority, root, journal, collector = _final_collector_journal(tmp_path)
    original_append = journal._append_event

    def crash_after_journal_seal(**event):
        digest = original_append(**event)
        if event["kind"] == "final_readback_sealed":
            raise RuntimeError("crash after journal seal")
        return digest

    monkeypatch.setattr(journal, "_append_event", crash_after_journal_seal)
    with pytest.raises(RuntimeError, match="after journal seal"):
        collector.seal_final(journal, source_id="final")

    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=root, run_id="local-run", authority=authority
    )
    assert collector.seal_final(reopened, source_id="final").phase == "final"
    assert reopened.phase == "final_readback_sealed"
    assert (
        sum(
            "final_readback_sealed" in path.read_text(encoding="utf-8")
            for path in (root / "local-run" / "journal").glob("*.json")
        )
        == 1
    )


def test_cli_execute_resume_drives_once_then_reopen_blocks_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts import run_noor_e2e_acceptance as cli
    from scripts.e2e_acceptance import execution, production
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import (
        _action_quota_charge,
        _action_request,
        _issued_authority,
    )

    registry = build_canonical_test_registry()
    root = (tmp_path / "protected").resolve()
    payload = {"text": "local"}
    request = _action_request()
    request["payload_digest"] = production._digest(payload)
    spec = execution.AuthorizedActionSpec(
        action_id="synthetic-action",
        adapter_id="fake-local-adapter",
        subsystem="outbound_text",
        quota_charge=_action_quota_charge(execution),
        **request,
    )
    _issued_authority(
        registry,
        protected_root=root,
        run_id="local-run",
        action_specs=execution.AuthorizedActionSpecs(
            schema_version="noor-e2e-authorized-action-specs/v2", specs=(spec,)
        ),
    )
    plan_payload = {
        "actions": [
            {
                "spec": spec.model_dump(mode="json"),
                "message_path": "requests/synthetic-action.json",
            }
        ],
        "evaluator": {
            "schema_version": "noor-e2e-protected-evaluator/v1",
            "publication": {"seed": 1},
            "decisive_producers": [
                {
                    "producer_id": "fake-local-adapter",
                    "producer_kind": "adapter",
                    "capability": "outbound_text",
                    "source_identity": "fake-local-adapter",
                    "config_digest": "a" * 64,
                }
            ],
        },
    }
    execution._write_exclusive(root, "input-plan.json", plan_payload)
    monkeypatch.setattr(cli, "_canonical_registry", lambda _: registry)
    args = SimpleNamespace(
        repo_root=PROJECT_ROOT,
        protected_root=root,
        run_id="local-run",
        run_plan="input-plan.json",
    )

    prepared = cli._lifecycle_result(SimpleNamespace(command="prepare", **vars(args)))
    assert prepared["phase"] == "prepared"
    assert (
        cli._lifecycle_result(SimpleNamespace(command="prepare", **vars(args)))
        == prepared
    )
    _, journal = cli._authority_and_journal(registry, root, "local-run", create=False)
    production.write_protected_message(
        journal, action_id="synthetic-action", payload=payload
    )
    IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={
                "inventory": b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
            }
        ),
    ).seal_baseline(journal, source_id="baseline")
    preflight_args = SimpleNamespace(
        command="preflight",
        baseline="collector-artifacts/baseline-readback.json",
        **vars(args),
    )
    preflight = cli._lifecycle_result(preflight_args)
    assert preflight["phase"] == "baseline_sealed"
    assert cli._lifecycle_result(preflight_args) == preflight

    original_dispatch = cli.dispatch_local_action

    def crash_after_reservation_before_permit(**kwargs):
        raise RuntimeError("crash after reservation before adapter I/O")

    monkeypatch.setattr(
        cli, "dispatch_local_action", crash_after_reservation_before_permit
    )
    with pytest.raises(RuntimeError, match="reservation before adapter I/O"):
        cli._lifecycle_result(SimpleNamespace(command="execute-resume", **vars(args)))
    _, recovered = cli._authority_and_journal(registry, root, "local-run", create=False)
    reservation = recovered._reservations["synthetic-action"]
    assert recovered._actions == {"synthetic-action": "reserved"}
    assert recovered.quota_usage.cost_usd == 0.25

    monkeypatch.setattr(cli, "dispatch_local_action", original_dispatch)
    dispatched = cli._lifecycle_result(
        SimpleNamespace(command="execute-resume", **vars(args))
    )
    assert dispatched["action_id"] == "synthetic-action"
    assert dispatched["state"] == "unknown"
    _, permit_consumed = cli._authority_and_journal(
        registry, root, "local-run", create=False
    )
    assert (
        permit_consumed._reservations["synthetic-action"].reservation_digest
        == reservation.reservation_digest
    )
    assert permit_consumed.quota_usage.cost_usd == 0.25
    with pytest.raises(production.ProductionAdapterError, match="nonterminal"):
        cli._lifecycle_result(SimpleNamespace(command="execute-resume", **vars(args)))
    authority, reopened = cli._authority_and_journal(
        registry, root, "local-run", create=False
    )
    assert reopened._actions == {"synthetic-action": "unknown"}
    reservation = reopened._reservations["synthetic-action"]
    now = datetime.now(UTC)
    receipt = execution.UnknownActionReconciliationReceipt(
        schema_version="noor-e2e-unknown-action-reconciliation/v2",
        registry_id=registry.registry_id,
        run_id="local-run",
        authorization_digest=reopened.authorization_digest,
        action_id=reservation.action_id,
        reservation_digest=reservation.reservation_digest,
        collector_id="independent-readback-collector",
        producer="independent-readback-collector",
        causal_event_digest=reopened.previous_event_digest,
        observed_at=now,
        expires_at=now + timedelta(minutes=1),
        resolved_state="succeeded",
        inventory_digest="e" * 64,
    )
    execution._write_exclusive(
        reopened.run_root,
        "independent-reconciliation/synthetic-action.json",
        receipt.model_dump(mode="json"),
    )
    original_append = reopened._append_event

    def crash_after_reconciliation(*, phase, kind, data):
        digest = original_append(phase=phase, kind=kind, data=data)
        if kind == "unknown_action_reconciled":
            raise RuntimeError("crash after reconciliation")
        return digest

    reopened._append_event = crash_after_reconciliation
    with pytest.raises(RuntimeError, match="crash after reconciliation"):
        reopened.reconcile_and_settle_action(
            action_id="synthetic-action",
            receipt_digest=hashlib.sha256(
                execution._read_protected(
                    reopened.run_root,
                    "independent-reconciliation/synthetic-action.json",
                )
            ).hexdigest(),
        )
    reconciled = cli._lifecycle_result(
        SimpleNamespace(
            command="reconcile-action", action_id="synthetic-action", **vars(args)
        )
    )
    assert reconciled["state"] == "succeeded"
    assert reconciled["settled_reserved_max_cost_usd"] == 0.25
    _, settled_reopen = cli._authority_and_journal(
        registry, root, "local-run", create=False
    )
    with pytest.raises(Exception, match="replay differs"):
        settled_reopen.reconcile_and_settle_action(
            action_id="synthetic-action", receipt_digest="0" * 64
        )
    assert (
        cli._lifecycle_result(
            SimpleNamespace(
                command="reconcile-action", action_id="synthetic-action", **vars(args)
            )
        )
        == reconciled
    )
    assert cli._lifecycle_result(
        SimpleNamespace(command="execute-resume", **vars(args))
    ) == {
        "phase": "executing",
        "state": "complete",
        "plan_digest": production.ProtectedRunPlan.load(
            root, "input-plan.json"
        ).plan_digest,
    }
