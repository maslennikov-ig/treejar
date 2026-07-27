"""Protected execution-state and authorization-v2 regression tests."""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.e2e_acceptance.manifest import load_authorization_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION_V1_PATH = (
    PROJECT_ROOT / ".codex/stages/tj-ee5f/authorization-manifest.example.json"
)


def _modules():
    policy = importlib.import_module("scripts.e2e_acceptance.policy")
    execution = importlib.import_module("scripts.e2e_acceptance.execution")
    return policy, execution


def _registry():
    policy, _ = _modules()
    return policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)


def _authorization(registry, **updates):
    _, execution = _modules()
    now = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
    values = {
        "schema_version": "noor-e2e-authorization/v2",
        "authorization_id": "synthetic-local-auth-v2",
        "status": "approved",
        "issued_at": now - timedelta(minutes=1),
        "expires_at": now + timedelta(hours=1),
        "task1_authorization_digest": "a" * 64,
        "policy_digest": registry.compiled_policy.policy_digest,
        "compiler_id": registry.compiled_plan.compiler_id,
        "compiled_plan_digest": registry.compiled_plan.plan_digest,
        "execution_ids": tuple(registry.compiled_plan.execution_ids),
        "adapter_ids": ("fake-local-adapter",),
        "store_ids": execution.StoreIdentities(
            raw_store_id="synthetic-raw-store",
            tracked_store_id="synthetic-tracked-store",
            anchor_store_id="synthetic-anchor-store",
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
    return execution.ExecutionAuthorizationV2(**values)


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

    shrunk = _authorization(
        registry,
        execution_ids=tuple(registry.compiled_plan.execution_ids[:1]),
    )
    with pytest.raises(Exception, match="exact.*29|execution.*drift"):
        registry.validate_execution_authorization(shrunk)


def test_authorization_v2_binds_policy_plan_compiler_adapters_and_stores() -> None:
    registry = _registry()
    valid = _authorization(registry)
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
        observed_at=datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
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
        observed_at=datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
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
    adapter = execution.FakeLocalAdapter("fake-local-adapter")
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
            occurred_at=datetime(2026, 7, 27, 10, 1, tzinfo=timezone.utc),
        )


def test_fake_adapter_refuses_unreserved_call() -> None:
    _, execution = _modules()
    adapter = execution.FakeLocalAdapter("fake-local-adapter")

    with pytest.raises(Exception, match="reservation"):
        adapter.execute(None)


def test_interrupted_two_phase_attempt_recovers_as_aborted(tmp_path: Path) -> None:
    _, execution = _modules()
    registry = _registry()
    authorization = _authorization(registry)
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authorization=authorization,
    )
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
