"""Protected execution-state and authorization-v2 regression tests."""

from __future__ import annotations

import hashlib
import importlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.e2e_acceptance.manifest import load_authorization_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION_V1_PATH = (
    PROJECT_ROOT / ".codex/stages/tj-ee5f/authorization-manifest.example.json"
)
SCENARIO_IDS = tuple(
    item["scenario_id"]
    for item in json.loads(
        (PROJECT_ROOT / ".codex/stages/tj-ee5f/scenario-set.json").read_text(
            encoding="utf-8"
        )
    )["scenarios"]
)


def _modules():
    policy = importlib.import_module("scripts.e2e_acceptance.policy")
    execution = importlib.import_module("scripts.e2e_acceptance.execution")
    return policy, execution


def _registry():
    policy, _ = _modules()
    return policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)


def _authorization(registry, *, trusted: bool = True, **updates):
    _, execution = _modules()
    now = datetime.now(UTC)
    values = {
        "schema_version": "noor-e2e-authorization/v2",
        "authorization_id": "synthetic-local-auth-v2",
        "status": "approved",
        "issued_at": now - timedelta(minutes=1),
        "expires_at": now + timedelta(hours=1),
        "task1_authorization_digest": "a" * 64,
        "task1_input_digests": {"synthetic-task1-input": "7" * 64},
        "preflight_digest": "8" * 64,
        "readback_collector_digest": "9" * 64,
        "policy_digest": registry.compiled_policy.policy_digest,
        "compiler_id": registry.compiled_plan.compiler_id,
        "compiled_plan_digest": registry.compiled_plan.plan_digest,
        "execution_ids": tuple(registry.compiled_plan.execution_ids),
        "execution_input_digests": {
            identity: "0" * 64 for identity in registry.compiled_plan.execution_ids
        },
        "adapter_ids": ("fake-local-adapter",),
        "store_ids": execution.StoreIdentities(
            raw_store_id="synthetic-raw-store",
            tracked_store_id="synthetic-tracked-store",
            anchor_store_id="synthetic-anchor-store",
            raw_root_digest="b" * 64,
            tracked_root_digest="c" * 64,
            anchor_root_digest="b" * 64,
        ),
        "registry_id": registry.registry_id,
        "quotas": execution.ProtectedQuotas(
            max_scenarios=29,
            max_messages=2,
            max_model_calls=2,
            max_cost_usd=1.0,
            subsystem_quotas={"outbound_text": 2},
        ),
    }
    values.update(updates)
    authorization = execution.ExecutionAuthorizationV2(**values)
    if trusted:
        registry._load_execution_authorization(authorization)
    return authorization


def test_compiled_plan_has_exact_29_execution_ids_and_all_required_criteria() -> None:
    registry = _registry()
    scenario_set = json.loads(
        (PROJECT_ROOT / ".codex/stages/tj-ee5f/scenario-set.json").read_text(
            encoding="utf-8"
        )
    )
    expected_execution_ids = {
        item["scenario_id"] for item in scenario_set["scenarios"]
    } | {item["block_id"] for item in scenario_set["evidence_blocks"]}

    assert set(registry.compiled_plan.execution_ids) == expected_execution_ids
    assert len(registry.compiled_plan.execution_ids) == 29
    assert len(registry.compiled_plan.criteria) == 30
    assert all(
        plan.aggregation == "all_required"
        and set(plan.obligation_ids)
        == set(plan.scenario_ids) | set(plan.evidence_block_ids)
        for plan in registry.compiled_plan.criteria.values()
    )


def test_executor_rejects_v1_and_authorization_v2_cannot_shrink_execution() -> None:
    registry = _registry()
    archival_v1 = load_authorization_manifest(AUTHORIZATION_V1_PATH)
    with pytest.raises(Exception, match="v1|V1|authorization/v2"):
        registry.validate_execution_authorization(archival_v1)

    only_execution = registry.compiled_plan.execution_ids[0]
    with pytest.raises(Exception, match="29|execution.*drift"):
        _authorization(
            registry,
            execution_ids=(only_execution,),
            execution_input_digests={only_execution: "0" * 64},
        )


def test_authorization_v2_binds_policy_plan_compiler_adapters_and_stores() -> None:
    registry = _registry()
    valid = _authorization(registry, trusted=False)
    registry._load_execution_authorization(valid)
    registry.validate_execution_authorization(valid)

    for field, replacement in (
        ("policy_digest", "b" * 64),
        ("compiled_plan_digest", "c" * 64),
        ("compiler_id", "untrusted-compiler"),
        ("adapter_ids", ("live-adapter",)),
        ("registry_id", "untrusted-registry"),
    ):
        with pytest.raises(Exception, match="authorization.*drift|not allowed"):
            registry.validate_execution_authorization(
                valid.model_copy(update={field: replacement})
            )


def test_authorization_requires_trusted_load_current_time_and_task1_inputs() -> None:
    registry = _registry()
    valid = _authorization(registry, trusted=False)
    with pytest.raises(Exception, match="trusted.*authorization|not loaded"):
        registry.validate_execution_authorization(valid)

    expired = valid.model_copy(
        update={
            "issued_at": datetime.now(UTC) - timedelta(hours=2),
            "expires_at": datetime.now(UTC) - timedelta(hours=1),
        }
    )
    with pytest.raises(Exception, match="expired|validity"):
        registry._load_execution_authorization(expired)

    values = valid.model_dump()
    values.pop("task1_input_digests")
    with pytest.raises(Exception, match="Task 1|input"):
        type(valid)(**values)


def test_criterion_all_required_lattice_blocks_missing_and_validates_exclusion() -> (
    None
):
    _, execution = _modules()
    registry = _registry()
    fresh = registry.compiled_plan.criteria["AC-01"]

    assert (
        execution.aggregate_criterion_outcome(
            fresh,
            {fresh.obligation_ids[0]: "PASS"},
            valid_exclusions=frozenset(),
        )
        == "BLOCKED"
    )
    assert (
        execution.aggregate_criterion_outcome(
            fresh,
            {item: "PASS" for item in fresh.obligation_ids},
            valid_exclusions=frozenset(),
        )
        == "PASS"
    )
    invalid_excluded = {item: "PASS" for item in fresh.obligation_ids}
    invalid_excluded[fresh.obligation_ids[0]] = "EXCLUDED_BY_CLIENT"
    with pytest.raises(Exception, match="exclusion"):
        execution.aggregate_criterion_outcome(
            fresh,
            invalid_excluded,
            valid_exclusions=frozenset(),
        )


def test_phase_machine_uses_cursor_and_digest_causality(tmp_path: Path) -> None:
    policy, execution = _modules()
    registry = _registry()
    authorization = _authorization(registry)
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authorization=authorization,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=datetime(2026, 7, 27, 10, 0, tzinfo=UTC),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)

    event_path = tmp_path / "protected/synthetic-run/journal/000002.json"
    event = json.loads(event_path.read_text(encoding="utf-8"))
    event["previous_event_digest"] = "0" * 64
    event_path.write_text(json.dumps(event), encoding="utf-8")

    with pytest.raises(Exception, match="digest|causality"):
        execution.ProtectedExecutionJournal.open(
            protected_root=tmp_path / "protected",
            run_id="synthetic-run",
            authorization=authorization,
        )


def test_phase_machine_closes_in_exact_causal_order(tmp_path: Path) -> None:
    policy, execution = _modules()
    registry = _registry()
    authorization = _authorization(registry)
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authorization=authorization,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=datetime.now(UTC) - timedelta(minutes=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    journal.anchor_final_turn(
        event_digest="a" * 64,
        occurred_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    assert journal.previous_event_digest is not None
    final = policy.ReadbackObservation.build(
        phase="final",
        collector_id="independent-readback-collector",
        source_id="synthetic-final",
        run_id="synthetic-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest=journal.previous_event_digest,
        observed_at=datetime.now(UTC),
        inventory={"synthetic:item": {"state": "closed"}},
    )
    journal.seal_final_readback(final)
    journal.mark_evaluated(evaluation_digest="b" * 64)
    journal.commit_phase(attempt_chain_digest="c" * 64)

    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authorization=authorization,
    )
    assert reopened.phase == "attempt_committed"
    assert reopened.cursor == 7


def test_reserve_action_consumes_quota_and_unknown_blocks_closeout(
    tmp_path: Path,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    authorization = _authorization(registry)
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authorization=authorization,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=datetime(2026, 7, 27, 10, 0, tzinfo=UTC),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    reservation = journal.reserve_action(
        action_id="synthetic-action",
        adapter_id="fake-local-adapter",
        subsystem="outbound_text",
        messages=1,
        model_calls=0,
        cost_usd=0,
    )
    adapter = execution.FakeLocalAdapter(
        adapter_id="fake-local-adapter",
        journal=journal,
    )
    adapter.execute(reservation)
    journal.complete_action(
        reservation,
        state="unknown",
        outcome_digest="d" * 64,
    )

    assert journal.quota_usage.messages == 1
    assert journal.quota_usage.subsystem_usage["outbound_text"] == 1
    with pytest.raises(Exception, match="unknown"):
        journal.anchor_final_turn(
            event_digest="e" * 64,
            occurred_at=datetime(2026, 7, 27, 10, 1, tzinfo=UTC),
        )


def test_fake_adapter_refuses_unreserved_call() -> None:
    _, execution = _modules()
    registry = _registry()
    _authorization(registry)
    adapter = execution.FakeLocalAdapter(
        adapter_id="fake-local-adapter",
        journal=None,
    )

    with pytest.raises(Exception, match="reservation"):
        adapter.execute(None)


def test_classifier_result_cannot_be_reused_for_another_assertion() -> None:
    policy, _ = _modules()
    registry = _registry()
    classified = [
        assertion
        for assertion in registry.compiled_policy.assertions.values()
        if assertion.oracle.kind == "classifier_result"
        and assertion.oracle.classifier_id == "scenario_policy.v2"
    ]
    first, second = classified[:2]
    result = policy.ClassifierResult.build(
        assertion_id=first.assertion_id,
        policy_digest=registry.compiled_policy.policy_digest,
        evaluator_digest=registry.classifier_evaluator_digest(first.assertion_id),
        run_id="synthetic-run",
        attempt_digest="7" * 64,
        preflight_digest="8" * 64,
        classifier_id="scenario_policy.v2",
        producer="production-policy-classifier",
        source_id="synthetic-classifier-event",
        source_digest="a" * 64,
        observed_at=datetime.now(UTC),
        passed=True,
        reason="Structured classifier passed.",
    )
    registry._load_local_classifier_fixture(result)
    evidence = policy.OracleEvidence(
        assertion_id=second.assertion_id,
        structured_events=(),
        tool_results=(),
        readbacks=(),
        classifier_results=(result,),
        text_supplements=(),
    )

    with pytest.raises(Exception, match="assertion.*binding"):
        registry.evaluate_oracle(second.assertion_id, evidence)


def test_fake_adapter_rejects_publicly_forged_reservation(tmp_path: Path) -> None:
    policy, execution = _modules()
    registry = _registry()
    authorization = _authorization(registry)
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authorization=authorization,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=datetime.now(UTC) - timedelta(minutes=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    forged = execution.ActionReservation(
        action_id="forged",
        adapter_id="fake-local-adapter",
        subsystem="outbound_text",
        messages=0,
        model_calls=0,
        cost_usd=0,
        reservation_digest="f" * 64,
    )
    adapter = execution.FakeLocalAdapter(
        adapter_id="fake-local-adapter",
        journal=journal,
    )

    with pytest.raises(Exception, match="protected.*reservation|forged"):
        adapter.execute(forged)


def test_negative_quota_inputs_and_max_scenarios_are_enforced(
    tmp_path: Path,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    authorization = _authorization(
        registry,
        quotas=execution.ProtectedQuotas(
            max_scenarios=1,
            max_messages=2,
            max_model_calls=2,
            max_cost_usd=1,
            subsystem_quotas={"outbound_text": 2},
        ),
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authorization=authorization,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=datetime.now(UTC) - timedelta(minutes=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()

    with pytest.raises(Exception, match="non-negative|greater than or equal"):
        journal.reserve_action(
            action_id="negative",
            adapter_id="fake-local-adapter",
            subsystem="outbound_text",
            messages=-1,
            model_calls=-1,
            cost_usd=-1,
        )
    journal.begin_attempt(
        execution_id=registry.compiled_plan.execution_ids[0],
        attempt_number=1,
        intent_digest="a" * 64,
    )
    with pytest.raises(Exception, match="scenario.*quota"):
        journal.begin_attempt(
            execution_id=registry.compiled_plan.execution_ids[1],
            attempt_number=1,
            intent_digest="b" * 64,
        )


def test_scenario_quota_is_authorization_scoped_across_runs(
    tmp_path: Path,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    authorization = _authorization(
        registry,
        quotas=execution.ProtectedQuotas(
            max_scenarios=1,
            max_messages=1,
            max_model_calls=1,
            max_cost_usd=1,
            subsystem_quotas={"outbound_text": 1},
        ),
    )
    for run_id in ("synthetic-run-one", "synthetic-run-two"):
        journal = execution.ProtectedExecutionJournal.create(
            protected_root=tmp_path / "protected",
            run_id=run_id,
            authorization=authorization,
        )
        baseline = policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id=f"{run_id}-baseline",
            run_id=run_id,
            preflight_digest="8" * 64,
            collector_artifact_digest="9" * 64,
            causal_event_digest="4" * 64,
            observed_at=datetime.now(UTC) - timedelta(minutes=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
        journal.seal_baseline(baseline)
        journal.begin_execution()
        if run_id.endswith("one"):
            journal.begin_attempt(
                execution_id=registry.compiled_plan.execution_ids[0],
                attempt_number=1,
                intent_digest="a" * 64,
            )
        else:
            with pytest.raises(Exception, match="authorization-scoped scenario quota"):
                journal.begin_attempt(
                    execution_id=registry.compiled_plan.execution_ids[1],
                    attempt_number=1,
                    intent_digest="b" * 64,
                )


def test_attempt_commit_binds_raw_and_tracked_semantics(tmp_path: Path) -> None:
    policy, execution = _modules()
    registry = _registry()
    authorization = _authorization(registry)
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authorization=authorization,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=datetime.now(UTC) - timedelta(minutes=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    execution_id = registry.compiled_plan.execution_ids[0]
    transaction = journal.begin_attempt(
        execution_id=execution_id,
        attempt_number=1,
        intent_digest="a" * 64,
    )
    transaction.write_raw(
        {
            "schema_version": "noor-e2e-attempt-result/v2",
            "execution_id": execution_id,
            "outcome": "FAIL",
            "semantic_digest": "c" * 64,
        }
    )
    transaction.write_tracked()
    tracked_path = (
        tmp_path
        / "protected"
        / "synthetic-run"
        / "attempts"
        / transaction.transaction_id
        / "tracked.json"
    )
    tracked = json.loads(tracked_path.read_text(encoding="utf-8"))
    tracked["outcome"] = "PASS"
    tracked_path.write_text(json.dumps(tracked), encoding="utf-8")

    with pytest.raises(Exception, match="raw.*tracked|semantic"):
        transaction.commit()

    with pytest.raises(Exception, match="canonical execution"):
        journal.begin_attempt(
            execution_id="SC-NOT-CANONICAL",
            attempt_number=1,
            intent_digest="d" * 64,
        )


def test_interrupted_two_phase_attempt_recovers_as_aborted(tmp_path: Path) -> None:
    policy, execution = _modules()
    registry = _registry()
    authorization = _authorization(registry)
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authorization=authorization,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=datetime.now(UTC) - timedelta(minutes=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    transaction = journal.begin_attempt(
        execution_id="SC-OPEN-EN",
        attempt_number=1,
        intent_digest="f" * 64,
    )
    transaction.write_raw({"synthetic": "raw"})

    recovered = journal.recover_attempt(transaction.transaction_id)

    assert recovered.status == "aborted"
    assert recovered.raw_digest is not None
    assert recovered.tracked_digest is None
    assert recovered.commit_digest is not None


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_generic_runner_validates_every_canonical_scenario(
    tmp_path: Path,
    scenario_id: str,
) -> None:
    policy, execution = _modules()
    registry = _registry()
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
    planned = execution.PlannedTurnV2(
        turn_id="turn-001",
        customer_input_digest="1" * 64,
        expected_behavior_digest="2" * 64,
        criterion_ids=scenario.criterion_ids,
        assertion_ids=tuple(sorted(assertion_ids)),
    )
    timeline = execution.TurnTimelineV2(
        sent_at=datetime(2026, 7, 27, 10, 0, tzinfo=UTC),
        first_visible_at=datetime(2026, 7, 27, 10, 0, 1, tzinfo=UTC),
        final_visible_at=datetime(2026, 7, 27, 10, 0, 2, tzinfo=UTC),
        delivered_at=datetime(2026, 7, 27, 10, 0, 3, tzinfo=UTC),
    )
    actual = execution.ActualTurnV2(
        actual_turn_id="turn-001",
        planned_turn_id="turn-001",
        customer_input_digest=planned.customer_input_digest,
        expected_behavior_digest=planned.expected_behavior_digest,
        criterion_ids=planned.criterion_ids,
        assertion_ids=planned.assertion_ids,
        event_refs=("synthetic-event",),
        tool_refs=(),
        audit_refs=("synthetic-audit",),
        timeline=timeline,
        model_id="fixture/model",
        token_count=1,
        cost_usd=0,
    )
    attempt_binding_digest = execution.scenario_input_digest(
        execution_id=scenario_id,
        planned_turns=(planned,),
        tester_config_digest="5" * 64,
        judge_config_digest="6" * 64,
    )
    oracle_evidence = []
    for assertion_id in sorted(assertion_ids):
        assertion = registry.compiled_policy.assertions[assertion_id]
        if assertion.oracle.kind == "classifier_result":
            classifier = policy.ClassifierResult.build(
                assertion_id=assertion_id,
                policy_digest=registry.compiled_policy.policy_digest,
                evaluator_digest=registry.classifier_evaluator_digest(assertion_id),
                run_id=f"run-{scenario_id.lower()}",
                attempt_digest=attempt_binding_digest,
                preflight_digest="8" * 64,
                classifier_id=assertion.oracle.classifier_id,
                producer=assertion.oracle.allowed_producers[0],
                source_id=f"{assertion_id}:classifier",
                source_digest="3" * 64,
                observed_at=datetime(2026, 7, 27, 10, 0, 2, tzinfo=UTC),
                passed=True,
                reason="Structured classifier passed.",
            )
            oracle_evidence.append(
                policy.OracleEvidence(
                    assertion_id=assertion_id,
                    structured_events=(),
                    tool_results=(),
                    readbacks=(),
                    classifier_results=(classifier,),
                    text_supplements=(),
                )
            )
        else:
            event = policy.StructuredEvent(
                assertion_id=assertion_id,
                producer=assertion.oracle.allowed_producers[0],
                source_id=f"{assertion_id}:event",
                source_digest="4" * 64,
                observed_at=datetime(2026, 7, 27, 10, 0, 2, tzinfo=UTC),
                passed=True,
                reason="Structured evidence passed.",
            )
            oracle_evidence.append(
                policy.OracleEvidence(
                    assertion_id=assertion_id,
                    structured_events=(event,),
                    tool_results=(),
                    readbacks=(),
                    classifier_results=(),
                    text_supplements=(),
                )
            )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id=f"{scenario_id}:baseline",
        run_id=f"run-{scenario_id.lower()}",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=datetime(2026, 7, 27, 9, 59, tzinfo=UTC),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    final = policy.ReadbackObservation.build(
        phase="final",
        collector_id="independent-readback-collector",
        source_id=f"{scenario_id}:final",
        run_id=f"run-{scenario_id.lower()}",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="5" * 64,
        observed_at=datetime(2026, 7, 27, 10, 0, 5, tzinfo=UTC),
        inventory={"synthetic:item": {"state": "closed"}},
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
        action_at=(datetime(2026, 7, 27, 10, 0, 4, tzinfo=UTC),),
        tester_config_digest="5" * 64,
        judge_config_digest="6" * 64,
    )
    plan_digest = execution.scenario_plan_digest(attempt)
    input_digests = {
        identity: "0" * 64 for identity in registry.compiled_plan.execution_ids
    }
    input_digests[scenario_id] = plan_digest
    authorization = _authorization(
        registry,
        execution_input_digests=input_digests,
    )
    registry._load_trusted_readback(baseline)
    registry._load_trusted_readback(final)
    for item in oracle_evidence:
        for classifier in item.classifier_results:
            registry._load_classifier_artifact(
                classifier,
                run_id=f"run-{scenario_id.lower()}",
                attempt_digest=plan_digest,
            )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id=f"run-{scenario_id.lower()}",
        authorization=authorization,
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    runner = execution.GenericAcceptanceRunner(
        registry=registry,
        authorization=authorization,
        journal=journal,
    )

    result = runner.validate_attempt(attempt)

    assert result.execution_id == scenario_id
    assert result.outcome == "PASS"
    assert result.plan_digest == plan_digest
    assert (
        result.attempt_digest
        == hashlib.sha256(
            (
                json.dumps(
                    attempt.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        ).hexdigest()
    )
