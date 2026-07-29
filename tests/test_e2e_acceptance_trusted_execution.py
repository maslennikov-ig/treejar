"""Protected execution-state and authorization-v2 regression tests."""

from __future__ import annotations

import hashlib
import importlib
import json
import pickle
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.e2e_acceptance.evidence import validate_side_effect_closeout
from scripts.e2e_acceptance.manifest import load_authorization_manifest
from scripts.e2e_acceptance.schemas import PreflightReadbackIdentity

from tests.e2e_acceptance_backend import build_canonical_test_registry

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
EVIDENCE_BLOCK_IDS = tuple(
    item["block_id"]
    for item in json.loads(
        (PROJECT_ROOT / ".codex/stages/tj-ee5f/scenario-set.json").read_text(
            encoding="utf-8"
        )
    )["evidence_blocks"]
)


def _modules():
    policy = importlib.import_module("scripts.e2e_acceptance.policy")
    execution = importlib.import_module("scripts.e2e_acceptance.execution")
    return policy, execution


def _registry():
    return build_canonical_test_registry()


def _trust_decisive_for_unit(registry, *items) -> None:
    policy, _ = _modules()
    context = registry._verified_evidence_context()
    classifier_digests = context.classifier_digests
    structured_digests = context.structured_digests
    for item in items:
        if isinstance(item, policy.ClassifierResult):
            classifier_digests = classifier_digests | {item.artifact_digest}
        else:
            structured_digests = structured_digests | {item.artifact_digest}
    registry._set_test_context(
        context.model_copy(
            update={
                "classifier_digests": classifier_digests,
                "structured_digests": structured_digests,
            }
        )
    )


def _authorization(registry, *, trusted: bool = True, **updates):
    _, execution = _modules()
    now = datetime.now(UTC)
    values = {
        "schema_version": "noor-e2e-authorization/v2",
        "authorization_id": "synthetic-local-auth-v2",
        "status": "approved",
        "issued_at": now - timedelta(minutes=1),
        "expires_at": now + timedelta(hours=1),
        "task1_authorization_digest": registry.task1_authorization_digest,
        "task1_input_digests": registry.task1_input_digests,
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
        "collector_ids": ("independent-readback-collector",),
        "permissions": ("fixture:execute",),
        "action_specs": (
            execution.AuthorizedActionSpec(
                action_id="synthetic-action",
                adapter_id="fake-local-adapter",
                subsystem="outbound_text",
                quota_charge=_action_quota_charge(execution),
                **_action_request(),
            ),
            execution.AuthorizedActionSpec(
                action_id="negative",
                adapter_id="fake-local-adapter",
                subsystem="outbound_text",
                quota_charge=_action_quota_charge(execution),
                **_action_request(),
            ),
        ),
        "side_effect_authority": execution.SideEffectAuthority(
            issuer="protected-side-effect-authority",
            cleanup_owner="acceptance-owner",
            cleanup_authority="application-path-only",
        ),
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
    values["live_binding"] = execution.ExactLiveAuthorizationBinding(
        v1_manifest_digest="1" * 64,
        preflight_request_digest="2" * 64,
        preflight_observation_digest="3" * 64,
        runtime_identity_digest="4" * 64,
        target_digest="5" * 64,
        permissions_digest=execution._digest(values["permissions"]),
        cleanup_retention_digest=execution._digest(
            {
                "side_effect_authority": values["side_effect_authority"].model_dump(
                    mode="json"
                ),
                "client_exclusion_authorities": {},
                "client_exclusion_grants": [],
            }
        ),
        execution_set_digest=execution._digest(
            {
                "execution_ids": values["execution_ids"],
                "input_digests": values["execution_input_digests"],
                "quotas": values["quotas"].model_dump(mode="json"),
            }
        ),
        adapter_ids_digest=execution._digest(values["adapter_ids"]),
        collector_ids_digest=execution._digest(values["collector_ids"]),
        stores_digest=execution._digest(values["store_ids"].model_dump(mode="json")),
        preflight_observed_at=now - timedelta(minutes=1),
    )
    values.update(updates)
    if (
        any(
            name in updates
            for name in (
                "execution_ids",
                "execution_input_digests",
                "quotas",
                "adapter_ids",
                "collector_ids",
                "permissions",
                "store_ids",
            )
        )
        and "live_binding" not in updates
    ):
        values["live_binding"] = values["live_binding"].model_copy(
            update={
                "permissions_digest": execution._digest(values["permissions"]),
                "execution_set_digest": execution._digest(
                    {
                        "execution_ids": values["execution_ids"],
                        "input_digests": values["execution_input_digests"],
                        "quotas": values["quotas"].model_dump(mode="json"),
                    }
                ),
                "adapter_ids_digest": execution._digest(values["adapter_ids"]),
                "collector_ids_digest": execution._digest(values["collector_ids"]),
                "stores_digest": execution._digest(
                    values["store_ids"].model_dump(mode="json")
                ),
            }
        )
    authorization = execution.ExecutionAuthorizationV2(**values)
    if trusted:
        registry._load_execution_authorization(authorization)
    return authorization


def _action_request(*, execution_id: str = "SC-OPEN-EN") -> dict[str, object]:
    return {
        "execution_id": execution_id,
        "step_id": "fixture-step-001",
        "capability": "outbound_text",
        "operation_permission": "fixture:execute",
        "destination_digest": "a" * 64,
        "payload_digest": "b" * 64,
        "idempotency_key": "fixture-idempotency-001",
        "capability_units": {"outbound_text": 1},
    }


def _action_quota_charge(execution):
    return execution.AuthorizedQuotaCharge(
        messages=1,
        model_calls=1,
        max_cost_usd=0.25,
        cost_settlement="bounded_actual",
    )


def _authority_bundle_inputs(
    registry,
    *,
    protected_root: Path,
    run_id: str,
    now: datetime | None = None,
    quotas=None,
    execution_input_digests: dict[str, str] | None = None,
    protected_authorities=None,
    action_specs=None,
    permissions: tuple[str, ...] | None = None,
):
    _, execution = _modules()
    current_time = now or datetime.now(UTC)
    draft = load_authorization_manifest(AUTHORIZATION_V1_PATH)
    exact_input_digests = execution_input_digests or {
        identity: "0" * 64 for identity in registry.compiled_plan.execution_ids
    }
    scenario_binding = draft.scenario_binding.model_copy(
        update={
            "scenario_ids": list(SCENARIO_IDS),
            "evidence_block_ids": list(EVIDENCE_BLOCK_IDS),
            "executable_input_digests": exact_input_digests,
        }
    )
    v1_quotas = (
        type(draft.quotas).model_validate(quotas.model_dump(mode="json"))
        if quotas is not None
        else draft.quotas.model_copy(
            update={
                "max_scenarios": 29,
                "max_messages": 2,
                "max_model_calls": 2,
                "max_cost_usd": 1.0,
                "subsystem_quotas": {"outbound_text": 2},
            }
        )
    )
    authorization = draft.model_copy(
        update={
            "authorization_id": "synthetic-local-auth-v1",
            "status": type(draft.status).APPROVED,
            "issuer": "synthetic-local-issuer",
            "issued_at": current_time - timedelta(minutes=2),
            "expires_at": current_time + timedelta(hours=1),
            "allowed_executor": "synthetic-local-executor",
            "allowed_source": "synthetic-local-source",
            "expected_identity": draft.expected_identity.model_copy(
                update={
                    "repository_commit": "1" * 40,
                    "deployed_release_sha": "2" * 40,
                    "ci_run_id": "synthetic-ci-run",
                    "app_version": "synthetic-app-version",
                    "migration_head": "synthetic-migration-head",
                    "main_model": "synthetic-main-model",
                    "fast_model": "synthetic-fast-model",
                }
            ),
            "targets": draft.targets.model_copy(
                update={
                    "recipient": "synthetic-recipient",
                    "wazzup_channel": "synthetic-channel",
                    "telegram_target": "synthetic-telegram-target",
                    "synthetic_suffix": "synthetic-run-suffix",
                }
            ),
            "quotas": v1_quotas,
            "permissions": list(permissions or ("fixture:execute",)),
            "callback_types": ["synthetic-callback"],
            "test_data_identities": ["synthetic-test-identity"],
            "cleanup_method": "synthetic-cleanup",
            "readbacks": ["synthetic-readback"],
            "stop_conditions": ["synthetic-stop"],
            "scenario_binding": scenario_binding,
        }
    )
    authorization = type(draft).model_validate(authorization.model_dump(mode="json"))
    request = execution.PreflightRequest(
        quotas=authorization.quotas,
        permissions=authorization.permissions,
        callback_types=authorization.callback_types,
        test_data_identities=authorization.test_data_identities,
        cleanup_method=authorization.cleanup_method,
        readbacks=authorization.readbacks,
        stop_conditions=authorization.stop_conditions,
        scenario_binding=authorization.scenario_binding,
    )
    observation = execution.PreflightObservation(
        identity=authorization.expected_identity,
        targets=authorization.targets,
        executor=authorization.allowed_executor,
        source=authorization.allowed_source,
        readback_identity=PreflightReadbackIdentity(
            source_id="synthetic-preflight-readback",
            observed_at=current_time - timedelta(seconds=30),
            content_digest="7" * 64,
        ),
    )
    exact_action_specs = action_specs or execution.AuthorizedActionSpecs(
        schema_version="noor-e2e-authorized-action-specs/v2",
        specs=(
            execution.AuthorizedActionSpec(
                action_id="synthetic-action",
                adapter_id="fake-local-adapter",
                subsystem="outbound_text",
                quota_charge=_action_quota_charge(execution),
                **_action_request(),
            ),
            execution.AuthorizedActionSpec(
                action_id="negative",
                adapter_id="fake-local-adapter",
                subsystem="outbound_text",
                quota_charge=_action_quota_charge(execution),
                **_action_request(),
            ),
        ),
    )
    stores = execution.StoreIdentities(
        raw_store_id="synthetic-raw-store",
        tracked_store_id="synthetic-tracked-store",
        anchor_store_id="synthetic-anchor-store",
        raw_root_digest=execution.store_root_digest(protected_root.resolve()),
        tracked_root_digest=execution.store_root_digest(
            (protected_root / "tracked").resolve()
        ),
        anchor_root_digest=execution.store_root_digest(
            (protected_root / "anchors").resolve()
        ),
    )
    execution_authorities = (
        protected_authorities
        if protected_authorities is not None
        else execution.ProtectedExecutionAuthorities(
            schema_version="noor-e2e-protected-execution-authorities/v2",
            client_exclusions=(),
            side_effect_authority=execution.SideEffectAuthority(
                issuer="protected-side-effect-authority",
                cleanup_owner=authorization.allowed_executor,
                cleanup_authority=authorization.cleanup_method,
            ),
        )
    )
    return {
        "registry": registry,
        "protected_root": protected_root,
        "run_id": run_id,
        "authorization": authorization,
        "request": request,
        "observation": observation,
        "action_specs": exact_action_specs,
        "store_ids": stores,
        "adapter_ids": execution.AuthorityAdapterIds(
            schema_version="noor-e2e-authority-adapter-ids/v2",
            values=("fake-local-adapter",),
        ),
        "collector_ids": execution.AuthorityCollectorIds(
            schema_version="noor-e2e-authority-collector-ids/v2",
            values=("independent-readback-collector",),
        ),
        "task1_bindings": execution.Task1AuthorityBindings(
            schema_version="noor-e2e-task1-authority-bindings/v2",
            authorization_digest=registry.task1_authorization_digest,
            input_digests=registry.task1_input_digests,
        ),
        "execution_authorities": execution_authorities,
        "receipt_issued_at": current_time - timedelta(seconds=1),
        "receipt_expires_at": current_time + timedelta(minutes=5),
    }


def _issued_authority(
    registry,
    *,
    protected_root: Path,
    run_id: str,
    now: datetime | None = None,
    quotas=None,
    execution_input_digests: dict[str, str] | None = None,
    protected_authorities=None,
    action_specs=None,
    permissions: tuple[str, ...] | None = None,
):
    _, execution = _modules()
    current_time = now or datetime.now(UTC)
    inputs = _authority_bundle_inputs(
        registry,
        protected_root=protected_root,
        run_id=run_id,
        now=current_time,
        quotas=quotas,
        execution_input_digests=execution_input_digests,
        protected_authorities=protected_authorities,
        action_specs=action_specs,
        permissions=permissions,
    )
    execution._write_test_authority_bundle(**inputs)
    return execution.issue_execution_authorization_handle(
        registry=registry,
        protected_root=protected_root,
        run_id=run_id,
        current_time=current_time,
    )


def _reconciled_action_journal(
    tmp_path: Path,
    *,
    run_id: str,
    registry=None,
    authority=None,
    action_id: str = "synthetic-action",
    action_request: dict[str, object] | None = None,
):
    policy, execution = _modules()
    registry = registry or _registry()
    protected_root = tmp_path / "protected"
    authority = authority or _issued_authority(
        registry,
        protected_root=protected_root,
        run_id=run_id,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=protected_root,
        run_id=run_id,
        authority=authority,
    )
    baseline_now = datetime.now(UTC)
    journal.seal_baseline(
        policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id=f"{run_id}-baseline",
            run_id=run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=(journal.authorization.readback_collector_digest),
            causal_event_digest="4" * 64,
            observed_at=baseline_now - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    exact_action_request = action_request or _action_request()
    reservation = journal.reserve_action(
        action_id=action_id,
        adapter_id="fake-local-adapter",
        subsystem="outbound_text",
        **exact_action_request,
        messages=1,
        model_calls=1,
        cost_usd=0.25,
    )
    execution.FakeLocalAdapter(
        adapter_id="fake-local-adapter",
        journal=journal,
    ).execute(reservation, **exact_action_request)
    journal.complete_action(
        reservation,
        state="unknown",
        outcome_digest="d" * 64,
    )
    now = datetime.now(UTC)
    receipt = execution.UnknownActionReconciliationReceipt(
        schema_version="noor-e2e-unknown-action-reconciliation/v2",
        registry_id=registry.registry_id,
        run_id=run_id,
        authorization_digest=execution.authorization_digest(journal.authorization),
        action_id=reservation.action_id,
        reservation_digest=reservation.reservation_digest,
        collector_id="independent-readback-collector",
        producer="independent-readback-collector",
        causal_event_digest=journal.previous_event_digest,
        observed_at=now,
        expires_at=now + timedelta(minutes=1),
        resolved_state="failed",
        inventory_digest="e" * 64,
    )
    receipt_digest = execution._write_exclusive(
        journal.run_root,
        f"independent-reconciliation/{reservation.action_id}.json",
        receipt.model_dump(mode="json"),
    )
    journal.reconcile_unknown_action(
        action_id=reservation.action_id,
        receipt_digest=receipt_digest,
    )
    return execution, authority, journal, reservation, now


def _persisted_cost_settlements(journal):
    authorization = {}
    intents = {}
    commits = {}
    for path in sorted(journal._authorization_ledger_root.glob("*.json")):
        event = json.loads(path.read_text(encoding="utf-8"))
        if event["kind"] == "action_cost_settled":
            settlement = event["settlement"]
            if settlement["run_id"] == journal.run_id:
                authorization[settlement["action_id"]] = settlement["settlement_digest"]
    for path in sorted((journal.run_root / "journal").glob("*.json")):
        event = json.loads(path.read_text(encoding="utf-8"))
        if event["kind"] == "action_cost_settlement_intent":
            settlement = event["data"]["settlement"]
            intents[settlement["action_id"]] = settlement["settlement_digest"]
        elif event["kind"] == "action_cost_settled":
            settlement = event["data"]["settlement"]
            commits[settlement["action_id"]] = settlement["settlement_digest"]
    return authorization, intents, commits


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
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authority=authority,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
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
            authority=authority,
        )


def test_phase_machine_closes_in_exact_causal_order(tmp_path: Path) -> None:
    policy, execution = _modules()
    registry = _registry()
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authority=authority,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
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
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
        causal_event_digest=journal.previous_event_digest,
        observed_at=datetime.now(UTC),
        inventory={"synthetic:item": {"state": "closed"}},
    )
    receipt_digest = execution._write_test_final_readback_bundle(journal, final)
    journal.seal_final_readback(final, receipt_digest=receipt_digest)
    journal.mark_evaluated(evaluation_digest="b" * 64)
    journal.commit_phase(attempt_chain_digest="c" * 64)

    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authority=authority,
    )
    assert reopened.phase == "attempt_committed"
    assert reopened.cursor == 7


def test_reserve_action_consumes_quota_and_unknown_blocks_closeout(
    tmp_path: Path,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authority=authority,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
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
        **_action_request(),
        messages=1,
        model_calls=1,
        cost_usd=0.25,
    )
    adapter = execution.FakeLocalAdapter(
        adapter_id="fake-local-adapter",
        journal=journal,
    )
    adapter.execute(reservation, **_action_request())
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


def test_unknown_dispatch_requires_protected_independent_reconciliation(
    tmp_path: Path,
) -> None:
    """A direct adapter result cannot turn a consumed permit into a terminal fact."""

    policy, execution = _modules()
    registry = _registry()
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id="reconciliation-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="reconciliation-run",
        authority=authority,
    )
    authorization = journal.authorization
    baseline_now = datetime.now(UTC)
    journal.seal_baseline(
        policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="reconciliation-baseline",
            run_id="reconciliation-run",
            preflight_digest=authorization.preflight_digest,
            collector_artifact_digest=authorization.readback_collector_digest,
            causal_event_digest="4" * 64,
            observed_at=baseline_now - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    reservation = journal.reserve_action(
        action_id="synthetic-action",
        adapter_id="fake-local-adapter",
        subsystem="outbound_text",
        **_action_request(),
        messages=1,
        model_calls=1,
        cost_usd=0.25,
    )
    execution.FakeLocalAdapter(
        adapter_id="fake-local-adapter", journal=journal
    ).execute(reservation, **_action_request())
    with pytest.raises(Exception, match="independent reconciliation"):
        journal.complete_action(
            reservation,
            state="failed",
            outcome_digest="d" * 64,
        )
    now = datetime.now(UTC)
    receipt = execution.UnknownActionReconciliationReceipt(
        schema_version="noor-e2e-unknown-action-reconciliation/v2",
        registry_id=registry.registry_id,
        run_id="reconciliation-run",
        authorization_digest=execution.authorization_digest(authorization),
        action_id=reservation.action_id,
        reservation_digest=reservation.reservation_digest,
        collector_id="independent-readback-collector",
        producer="independent-readback-collector",
        causal_event_digest=journal.previous_event_digest,
        observed_at=now,
        expires_at=now + timedelta(minutes=1),
        resolved_state="failed",
        inventory_digest="e" * 64,
    )
    receipt_digest = execution._write_exclusive(
        journal.run_root,
        f"independent-reconciliation/{reservation.action_id}.json",
        receipt.model_dump(mode="json"),
    )
    journal.reconcile_unknown_action(
        action_id=reservation.action_id,
        receipt_digest=receipt_digest,
    )
    with pytest.raises(Exception, match="cost settlement|authorized maximum"):
        journal.settle_action_cost(reservation, actual_cost_usd=0.26)
    settlement = journal.settle_action_cost(
        reservation,
        actual_cost_usd=0.10,
    )
    assert settlement.actual_cost_usd == 0.10
    assert journal.quota_usage.cost_usd == 0.25
    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=tmp_path / "protected",
        run_id="reconciliation-run",
        authority=authority,
    )
    assert reopened.quota_usage.cost_usd == 0.25
    with pytest.raises(Exception, match="already settled"):
        reopened.settle_action_cost(reservation, actual_cost_usd=0.10)
    journal.anchor_final_turn(event_digest="f" * 64, occurred_at=now)


def test_action_cost_settlement_after_final_anchor_fails_without_phase_regression(
    tmp_path: Path,
) -> None:
    execution, authority, journal, reservation, now = _reconciled_action_journal(
        tmp_path,
        run_id="late-settlement-run",
    )
    journal.anchor_final_turn(event_digest="f" * 64, occurred_at=now)

    with pytest.raises(Exception, match="executing phase"):
        journal.settle_action_cost(reservation, actual_cost_usd=0.10)

    assert journal.phase == "final_turn_anchored"
    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=tmp_path / "protected",
        run_id="late-settlement-run",
        authority=authority,
    )
    assert reopened.phase == "final_turn_anchored"


def test_reopen_rejects_duplicate_cost_settlement_phase_regression(
    tmp_path: Path,
) -> None:
    execution, authority, journal, reservation, now = _reconciled_action_journal(
        tmp_path,
        run_id="settlement-replay-run",
    )
    settlement = journal.settle_action_cost(
        reservation,
        actual_cost_usd=0.10,
    )
    assert journal.phase == "executing"
    journal.anchor_final_turn(event_digest="f" * 64, occurred_at=now)
    journal._append_event(
        phase="executing",
        kind="action_cost_settled",
        data={"settlement": settlement.model_dump(mode="json")},
    )

    with pytest.raises(Exception, match="phase regression|duplicate"):
        execution.ProtectedExecutionJournal.open(
            protected_root=tmp_path / "protected",
            run_id="settlement-replay-run",
            authority=authority,
        )


@pytest.mark.parametrize(
    "crash_boundary",
    ("before_intent", "after_intent", "after_authorization", "after_commit"),
)
def test_cost_settlement_crash_recovers_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_boundary: str,
) -> None:
    execution, authority, journal, reservation, now = _reconciled_action_journal(
        tmp_path,
        run_id=f"settlement-crash-{crash_boundary}",
    )

    class InjectedCrash(RuntimeError):
        pass

    original_authorization_append = journal._append_authorization_ledger
    original_journal_append = journal._append_event
    with monkeypatch.context() as crash:
        if crash_boundary == "before_intent":

            def fail_intent_append(*, phase, kind, data):
                if kind == "action_cost_settlement_intent":
                    raise InjectedCrash("before settlement intent")
                return original_journal_append(phase=phase, kind=kind, data=data)

            crash.setattr(journal, "_append_event", fail_intent_append)
        elif crash_boundary == "after_intent":

            def fail_authorization_append(*, kind, data):
                if kind == "action_cost_settled":
                    raise InjectedCrash("after settlement intent")
                return original_authorization_append(kind=kind, data=data)

            crash.setattr(
                journal,
                "_append_authorization_ledger",
                fail_authorization_append,
            )
        elif crash_boundary == "after_authorization":

            def fail_journal_commit(*, phase, kind, data):
                if kind == "action_cost_settled":
                    raise InjectedCrash("after authorization settlement")
                return original_journal_append(phase=phase, kind=kind, data=data)

            crash.setattr(journal, "_append_event", fail_journal_commit)
        else:

            def fail_after_journal_commit(*, phase, kind, data):
                digest = original_journal_append(phase=phase, kind=kind, data=data)
                if kind == "action_cost_settled":
                    raise InjectedCrash("after journal settlement commit")
                return digest

            crash.setattr(journal, "_append_event", fail_after_journal_commit)

        with pytest.raises(InjectedCrash):
            journal.settle_action_cost(
                reservation,
                actual_cost_usd=0.10,
            )

    if crash_boundary == "after_intent":
        with pytest.raises(Exception, match="differs from intent"):
            journal.settle_action_cost(
                reservation,
                actual_cost_usd=0.11,
            )
    if crash_boundary in {"before_intent", "after_intent"}:
        retried = journal.settle_action_cost(
            reservation,
            actual_cost_usd=0.10,
        )
        assert retried.actual_cost_usd == 0.10
    if crash_boundary == "after_authorization":
        with pytest.raises(Exception, match="incomplete.*settlement|settlement.*drift"):
            journal.anchor_final_turn(event_digest="f" * 64, occurred_at=now)

    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=tmp_path / "protected",
        run_id=f"settlement-crash-{crash_boundary}",
        authority=authority,
    )
    authorization, intents, commits = _persisted_cost_settlements(reopened)
    assert authorization == intents == commits
    assert set(commits) == {reservation.action_id}
    assert reopened.quota_usage.cost_usd == 0.25
    with pytest.raises(Exception, match="already settled"):
        reopened.settle_action_cost(reservation, actual_cost_usd=0.10)
    reopened.anchor_final_turn(event_digest="f" * 64, occurred_at=now)


@pytest.mark.parametrize("tamper", ("missing", "extra", "different"))
def test_cost_settlement_reopen_rejects_tampered_store_mismatch(
    tmp_path: Path,
    tamper: str,
) -> None:
    execution, authority, journal, reservation, _ = _reconciled_action_journal(
        tmp_path,
        run_id=f"settlement-tamper-{tamper}",
    )
    settlement = journal.settle_action_cost(
        reservation,
        actual_cost_usd=0.10,
    )
    journal_paths = sorted((journal.run_root / "journal").glob("*.json"))
    settlement_paths = [
        path
        for path in journal_paths
        if json.loads(path.read_text(encoding="utf-8"))["kind"]
        in {"action_cost_settlement_intent", "action_cost_settled"}
    ]

    if tamper == "missing":
        for path in reversed(settlement_paths):
            path.unlink()
    elif tamper == "extra":
        journal._append_event(
            phase=journal.phase,
            kind="action_cost_settled",
            data={"settlement": settlement.model_dump(mode="json")},
        )
    else:
        commit_path = settlement_paths[-1]
        event = json.loads(commit_path.read_text(encoding="utf-8"))
        event["data"]["settlement"]["actual_cost_usd"] = 0.11
        identity = {
            key: value
            for key, value in event["data"]["settlement"].items()
            if key != "settlement_digest"
        }
        event["data"]["settlement"]["settlement_digest"] = execution._digest(identity)
        commit_path.write_bytes(execution._canonical_bytes(event))

    with pytest.raises(Exception, match="settlement|digest|duplicate|drift"):
        execution.ProtectedExecutionJournal.open(
            protected_root=tmp_path / "protected",
            run_id=f"settlement-tamper-{tamper}",
            authority=authority,
        )


def test_cost_settlement_consistency_is_run_scoped_but_quota_is_global(
    tmp_path: Path,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    protected_root = tmp_path / "protected"
    now = datetime.now(UTC)
    quotas = execution.ProtectedQuotas(
        max_scenarios=29,
        max_messages=1,
        max_model_calls=1,
        max_cost_usd=0.25,
        subsystem_quotas={"outbound_text": 1},
    )

    def action_spec(action_id: str, idempotency_key: str):
        return execution.AuthorizedActionSpec(
            action_id=action_id,
            adapter_id="fake-local-adapter",
            subsystem="outbound_text",
            quota_charge=_action_quota_charge(execution),
            **{
                **_action_request(),
                "idempotency_key": idempotency_key,
            },
        )

    action_specs = execution.AuthorizedActionSpecs(
        schema_version="noor-e2e-authorized-action-specs/v2",
        specs=(
            action_spec("synthetic-action", "fixture-idempotency-001"),
            action_spec("negative", "fixture-idempotency-001"),
            action_spec("quota-action", "fixture-idempotency-002"),
        ),
    )
    run_one_authority = _issued_authority(
        registry,
        protected_root=protected_root,
        run_id="settlement-run-one",
        now=now,
        quotas=quotas,
        action_specs=action_specs,
    )
    run_two_authority = _issued_authority(
        registry,
        protected_root=protected_root,
        run_id="settlement-run-two",
        now=now,
        quotas=quotas,
        action_specs=action_specs,
    )
    assert execution.authorization_digest(
        run_one_authority._authorization
    ) == execution.authorization_digest(run_two_authority._authorization)

    _, _, run_one, reservation, _ = _reconciled_action_journal(
        tmp_path,
        run_id="settlement-run-one",
        registry=registry,
        authority=run_one_authority,
    )
    run_one.settle_action_cost(reservation, actual_cost_usd=0.10)

    run_two = execution.ProtectedExecutionJournal.create(
        protected_root=protected_root,
        run_id="settlement-run-two",
        authority=run_two_authority,
    )
    assert run_two.phase == "prepared"
    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=protected_root,
        run_id="settlement-run-two",
        authority=run_two_authority,
    )
    assert reopened.phase == "prepared"
    assert reopened.quota_usage.messages == 1
    assert reopened.quota_usage.model_calls == 1
    assert reopened.quota_usage.cost_usd == 0.25

    reopened.seal_baseline(
        policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="settlement-run-two-baseline",
            run_id="settlement-run-two",
            preflight_digest=reopened.authorization.preflight_digest,
            collector_artifact_digest=(
                reopened.authorization.readback_collector_digest
            ),
            causal_event_digest="4" * 64,
            observed_at=now - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    reopened.begin_execution()
    with pytest.raises(Exception, match="action|idempotency.*consumed"):
        reopened.reserve_action(
            action_id="synthetic-action",
            adapter_id="fake-local-adapter",
            subsystem="outbound_text",
            **_action_request(),
            messages=1,
            model_calls=1,
            cost_usd=0.25,
        )
    with pytest.raises(Exception, match="action|idempotency.*consumed"):
        reopened.reserve_action(
            action_id="negative",
            adapter_id="fake-local-adapter",
            subsystem="outbound_text",
            **_action_request(),
            messages=1,
            model_calls=1,
            cost_usd=0.25,
        )
    with pytest.raises(Exception, match="quota"):
        reopened.reserve_action(
            action_id="quota-action",
            adapter_id="fake-local-adapter",
            subsystem="outbound_text",
            **{
                **_action_request(),
                "idempotency_key": "fixture-idempotency-002",
            },
            messages=1,
            model_calls=1,
            cost_usd=0.25,
        )


def test_cost_settlement_recovery_filters_exact_current_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, execution = _modules()
    registry = _registry()
    protected_root = tmp_path / "protected"
    now = datetime.now(UTC)
    quotas = execution.ProtectedQuotas(
        max_scenarios=29,
        max_messages=2,
        max_model_calls=2,
        max_cost_usd=0.50,
        subsystem_quotas={"outbound_text": 2},
    )
    run_two_request = {
        **_action_request(),
        "idempotency_key": "fixture-idempotency-002",
    }
    action_specs = execution.AuthorizedActionSpecs(
        schema_version="noor-e2e-authorized-action-specs/v2",
        specs=(
            execution.AuthorizedActionSpec(
                action_id="synthetic-action",
                adapter_id="fake-local-adapter",
                subsystem="outbound_text",
                quota_charge=_action_quota_charge(execution),
                **_action_request(),
            ),
            execution.AuthorizedActionSpec(
                action_id="negative",
                adapter_id="fake-local-adapter",
                subsystem="outbound_text",
                quota_charge=_action_quota_charge(execution),
                **run_two_request,
            ),
        ),
    )
    run_one_authority = _issued_authority(
        registry,
        protected_root=protected_root,
        run_id="recovery-run-one",
        now=now,
        quotas=quotas,
        action_specs=action_specs,
    )
    run_two_authority = _issued_authority(
        registry,
        protected_root=protected_root,
        run_id="recovery-run-two",
        now=now,
        quotas=quotas,
        action_specs=action_specs,
    )
    _, _, run_one, run_one_reservation, _ = _reconciled_action_journal(
        tmp_path,
        run_id="recovery-run-one",
        registry=registry,
        authority=run_one_authority,
    )
    run_one.settle_action_cost(run_one_reservation, actual_cost_usd=0.10)
    _, _, run_two, run_two_reservation, _ = _reconciled_action_journal(
        tmp_path,
        run_id="recovery-run-two",
        registry=registry,
        authority=run_two_authority,
        action_id="negative",
        action_request=run_two_request,
    )

    class InjectedCrash(RuntimeError):
        pass

    original_append = run_two._append_event

    def fail_commit(*, phase, kind, data):
        if kind == "action_cost_settled":
            raise InjectedCrash("after run-two authorization settlement")
        return original_append(phase=phase, kind=kind, data=data)

    with monkeypatch.context() as crash:
        crash.setattr(run_two, "_append_event", fail_commit)
        with pytest.raises(InjectedCrash):
            run_two.settle_action_cost(
                run_two_reservation,
                actual_cost_usd=0.10,
            )

    reopened_two = execution.ProtectedExecutionJournal.open(
        protected_root=protected_root,
        run_id="recovery-run-two",
        authority=run_two_authority,
    )
    authorization, intents, commits = _persisted_cost_settlements(reopened_two)
    assert authorization == intents == commits
    assert set(commits) == {"negative"}
    assert reopened_two.quota_usage.cost_usd == 0.50

    reopened_one = execution.ProtectedExecutionJournal.open(
        protected_root=protected_root,
        run_id="recovery-run-one",
        authority=run_one_authority,
    )
    authorization, intents, commits = _persisted_cost_settlements(reopened_one)
    assert authorization == intents == commits
    assert set(commits) == {"synthetic-action"}
    assert reopened_one.quota_usage.cost_usd == 0.50


@pytest.mark.parametrize(
    "tamper",
    ("missing_journal_run", "wrong_journal_run", "mislabeled_authorization_run"),
)
def test_cost_settlement_rejects_cross_run_record_tamper(
    tmp_path: Path,
    tamper: str,
) -> None:
    _, execution = _modules()
    registry = _registry()
    protected_root = tmp_path / "protected"
    now = datetime.now(UTC)
    quotas = execution.ProtectedQuotas(
        max_scenarios=29,
        max_messages=2,
        max_model_calls=2,
        max_cost_usd=0.50,
        subsystem_quotas={"outbound_text": 2},
    )
    run_two_request = {
        **_action_request(),
        "idempotency_key": "fixture-idempotency-002",
    }
    action_specs = execution.AuthorizedActionSpecs(
        schema_version="noor-e2e-authorized-action-specs/v2",
        specs=(
            execution.AuthorizedActionSpec(
                action_id="synthetic-action",
                adapter_id="fake-local-adapter",
                subsystem="outbound_text",
                quota_charge=_action_quota_charge(execution),
                **_action_request(),
            ),
            execution.AuthorizedActionSpec(
                action_id="negative",
                adapter_id="fake-local-adapter",
                subsystem="outbound_text",
                quota_charge=_action_quota_charge(execution),
                **run_two_request,
            ),
        ),
    )
    run_one_authority = _issued_authority(
        registry,
        protected_root=protected_root,
        run_id="tamper-run-one",
        now=now,
        quotas=quotas,
        action_specs=action_specs,
    )
    run_two_authority = _issued_authority(
        registry,
        protected_root=protected_root,
        run_id="tamper-run-two",
        now=now,
        quotas=quotas,
        action_specs=action_specs,
    )
    _, _, run_one, run_one_reservation, _ = _reconciled_action_journal(
        tmp_path,
        run_id="tamper-run-one",
        registry=registry,
        authority=run_one_authority,
    )
    run_one.settle_action_cost(run_one_reservation, actual_cost_usd=0.10)
    _, _, run_two, run_two_reservation, _ = _reconciled_action_journal(
        tmp_path,
        run_id="tamper-run-two",
        registry=registry,
        authority=run_two_authority,
        action_id="negative",
        action_request=run_two_request,
    )
    run_two.settle_action_cost(run_two_reservation, actual_cost_usd=0.10)

    if tamper == "mislabeled_authorization_run":
        ledger_path = next(
            path
            for path in reversed(
                sorted(run_two._authorization_ledger_root.glob("*.json"))
            )
            if json.loads(path.read_text(encoding="utf-8"))
            .get("settlement", {})
            .get("action_id")
            == "negative"
        )
        event = json.loads(ledger_path.read_text(encoding="utf-8"))
        event["settlement"]["run_id"] = "tamper-run-one"
        identity = {
            key: value
            for key, value in event["settlement"].items()
            if key != "settlement_digest"
        }
        event["settlement"]["settlement_digest"] = execution._digest(identity)
        ledger_path.write_bytes(execution._canonical_bytes(event))
    else:
        journal_events = [
            (
                path,
                json.loads(path.read_text(encoding="utf-8")),
            )
            for path in sorted((run_two.run_root / "journal").glob("*.json"))
        ]
        intent_path, intent = next(
            item
            for item in journal_events
            if item[1]["kind"] == "action_cost_settlement_intent"
        )
        commit_path, commit = next(
            item for item in journal_events if item[1]["kind"] == "action_cost_settled"
        )
        for event in (intent, commit):
            settlement = event["data"]["settlement"]
            if tamper == "missing_journal_run":
                settlement.pop("run_id")
            else:
                settlement["run_id"] = "tamper-run-one"
                identity = {
                    key: value
                    for key, value in settlement.items()
                    if key != "settlement_digest"
                }
                settlement["settlement_digest"] = execution._digest(identity)
        intent_path.write_bytes(execution._canonical_bytes(intent))
        intent_digest = hashlib.sha256(intent_path.read_bytes()).hexdigest()
        commit["previous_event_digest"] = intent_digest
        commit["data"]["intent_event_digest"] = intent_digest
        commit_path.write_bytes(execution._canonical_bytes(commit))

    with pytest.raises(Exception, match="settlement|run|drift|validation"):
        execution.ProtectedExecutionJournal.open(
            protected_root=protected_root,
            run_id="tamper-run-two",
            authority=run_two_authority,
        )


def test_zero_turn_gate_requires_protected_receipted_evidence(tmp_path: Path) -> None:
    """A shaped BLOCKED object cannot substitute for a committed gate receipt."""

    _, execution = _modules()
    registry = _registry()
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id="gate-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="gate-run",
        authority=authority,
    )
    authorization = journal.authorization
    now = datetime.now(UTC)
    journal.seal_baseline(
        _modules()[0].ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="gate-baseline",
            run_id="gate-run",
            preflight_digest=authorization.preflight_digest,
            collector_artifact_digest=authorization.readback_collector_digest,
            causal_event_digest="4" * 64,
            observed_at=now - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    runner = execution.GenericAcceptanceRunner(
        registry=registry,
        authority=authority,
        journal=journal,
    )
    execution_id = registry.compiled_plan.execution_ids[0]
    receipt_digest = execution._write_test_gate_evidence_bundle(
        registry=registry,
        journal=journal,
        execution_id=execution_id,
        outcome="BLOCKED",
        producer="independent-readback-collector",
        observed_at=datetime.now(UTC),
        expires_at=now + timedelta(minutes=1),
    )
    attempt = execution.GateAttemptV2(
        schema_version="noor-e2e-gate-attempt/v2",
        execution_id=execution_id,
        outcome="BLOCKED",
        run_started_at=journal._execution_started_at,
        execution_started_event_digest=journal._execution_started_event_digest,
        receipt_digest=receipt_digest,
    )
    assert runner.validate_gate_attempt(attempt) == attempt
    with pytest.raises(Exception, match="protected producer receipt|receipt drift"):
        runner.validate_gate_attempt(
            attempt.model_copy(update={"receipt_digest": "0" * 64})
        )

    protected_attempt_digest = execution._digest(attempt.model_dump(mode="json"))
    original_append = journal._append_event

    def crash_before_gate_event(*, phase, kind, data):
        if kind == "gate_recorded":
            raise RuntimeError("crash before gate event")
        return original_append(phase=phase, kind=kind, data=data)

    journal._append_event = crash_before_gate_event
    with pytest.raises(RuntimeError, match="crash before gate event"):
        journal.record_gate_attempt(
            attempt, protected_attempt_digest=protected_attempt_digest
        )
    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=tmp_path / "protected",
        run_id="gate-run",
        authority=authority,
    )
    reopened.record_gate_attempt(
        attempt, protected_attempt_digest=protected_attempt_digest
    )
    after_event = execution.ProtectedExecutionJournal.open(
        protected_root=tmp_path / "protected",
        run_id="gate-run",
        authority=authority,
    )
    after_event.record_gate_attempt(
        attempt, protected_attempt_digest=protected_attempt_digest
    )
    record_path = after_event.run_root / f"recorded-gates/{execution_id}.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    for field, value in (
        ("schema_version", "tampered"),
        ("journal_head_digest", "0" * 64),
    ):
        tampered = dict(record)
        tampered[field] = value
        record_path.write_text(json.dumps(tampered), encoding="utf-8")
        with pytest.raises(Exception, match="replay drift"):
            after_event.record_gate_attempt(
                attempt, protected_attempt_digest=protected_attempt_digest
            )
    record_path.write_text(json.dumps(record), encoding="utf-8")
    assert reopened._recorded_gates == {execution_id: attempt}
    with pytest.raises(Exception, match="replay|commit-ready"):
        reopened.record_gate_attempt(
            attempt.model_copy(update={"outcome": "EXCLUDED_BY_CLIENT"}),
            protected_attempt_digest=protected_attempt_digest,
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
        adapter.execute(None, **_action_request())


@pytest.mark.parametrize("run_id", (".", "..", "nested/run"))
def test_run_id_rejects_path_escape_before_journal_write(run_id: str) -> None:
    _, execution = _modules()

    with pytest.raises(Exception, match="run identity"):
        execution._validate_run_id(run_id)
    execution._validate_run_id("synthetic-run.v2_1")


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
    _trust_decisive_for_unit(registry, result)
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
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authority=authority,
    )
    authorization = journal.authorization
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
        causal_event_digest="4" * 64,
        observed_at=datetime.now(UTC) - timedelta(minutes=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    forged = execution.ActionReservation(
        action_id="forged",
        run_id="synthetic-run",
        authorization_digest=execution.authorization_digest(authorization),
        **_action_request(),
        adapter_id="fake-local-adapter",
        subsystem="outbound_text",
        messages=0,
        model_calls=0,
        cost_usd=0,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
        reservation_digest="f" * 64,
    )
    adapter = execution.FakeLocalAdapter(
        adapter_id="fake-local-adapter",
        journal=journal,
    )

    with pytest.raises(Exception, match="protected.*reservation|forged"):
        adapter.execute(forged, **_action_request())


def test_negative_quota_inputs_and_max_scenarios_are_enforced(
    tmp_path: Path,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    quotas = execution.ProtectedQuotas(
        max_scenarios=1,
        max_messages=2,
        max_model_calls=2,
        max_cost_usd=1,
        subsystem_quotas={"outbound_text": 2},
    )
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        quotas=quotas,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authority=authority,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
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
            **_action_request(),
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


@pytest.mark.parametrize(
    ("messages", "model_calls", "cost_usd"),
    (
        (0, 1, 0.25),
        (1, 0, 0.25),
        (1, 1, 0),
    ),
    ids=("zero-message", "zero-model-call", "zero-cost-reservation"),
)
def test_protected_action_spec_rejects_quota_undercharge(
    tmp_path: Path,
    messages: int,
    model_calls: int,
    cost_usd: float,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    run_id = f"undercharge-{messages}-{model_calls}-{cost_usd}"
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id=run_id,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id=run_id,
        authority=authority,
    )
    journal.seal_baseline(
        policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id=f"{run_id}-baseline",
            run_id=run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=(journal.authorization.readback_collector_digest),
            causal_event_digest="4" * 64,
            observed_at=datetime.now(UTC) - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()

    with pytest.raises(Exception, match="quota charge|undercharge"):
        journal.reserve_action(
            action_id="synthetic-action",
            adapter_id="fake-local-adapter",
            subsystem="outbound_text",
            **_action_request(),
            messages=messages,
            model_calls=model_calls,
            cost_usd=cost_usd,
        )


def test_scenario_quota_is_authorization_scoped_across_runs(
    tmp_path: Path,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    quotas = execution.ProtectedQuotas(
        max_scenarios=1,
        max_messages=1,
        max_model_calls=1,
        max_cost_usd=1,
        subsystem_quotas={"outbound_text": 1},
    )
    authority_now = datetime.now(UTC)
    for run_id in ("synthetic-run-one", "synthetic-run-two"):
        authority = _issued_authority(
            registry,
            protected_root=tmp_path / "protected",
            run_id=run_id,
            now=authority_now,
            quotas=quotas,
        )
        journal = execution.ProtectedExecutionJournal.create(
            protected_root=tmp_path / "protected",
            run_id=run_id,
            authority=authority,
        )
        baseline = policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id=f"{run_id}-baseline",
            run_id=run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
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
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authority=authority,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
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
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="synthetic-run",
        authority=authority,
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
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
    input_digests = {
        identity: "0" * 64 for identity in registry.compiled_plan.execution_ids
    }
    input_digests[scenario_id] = attempt_binding_digest
    run_id = f"run-{scenario_id.lower()}"
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id=run_id,
        execution_input_digests=input_digests,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id=run_id,
        authority=authority,
    )
    authorization = journal.authorization
    oracle_evidence = []
    for assertion_id in sorted(assertion_ids):
        assertion = registry.compiled_policy.assertions[assertion_id]
        if assertion.oracle.kind == "classifier_result":
            classifier = policy.ClassifierResult.build(
                assertion_id=assertion_id,
                policy_digest=registry.compiled_policy.policy_digest,
                evaluator_digest=registry.classifier_evaluator_digest(assertion_id),
                run_id=run_id,
                attempt_digest=attempt_binding_digest,
                preflight_digest=authorization.preflight_digest,
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
            event = policy.StructuredEvent.build(
                assertion_id=assertion_id,
                producer=assertion.oracle.allowed_producers[0],
                source_id=f"{assertion_id}:event",
                source_digest="4" * 64,
                observed_at=datetime(2026, 7, 27, 10, 0, 2, tzinfo=UTC),
                passed=True,
                reason="Structured evidence passed.",
                run_id=run_id,
                attempt_digest=attempt_binding_digest,
                preflight_digest=authorization.preflight_digest,
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
        run_id=run_id,
        preflight_digest=authorization.preflight_digest,
        collector_artifact_digest=authorization.readback_collector_digest,
        causal_event_digest="4" * 64,
        observed_at=datetime(2026, 7, 27, 9, 59, tzinfo=UTC),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    final = policy.ReadbackObservation.build(
        phase="final",
        collector_id="independent-readback-collector",
        source_id=f"{scenario_id}:final",
        run_id=run_id,
        preflight_digest=authorization.preflight_digest,
        collector_artifact_digest=authorization.readback_collector_digest,
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
    assert plan_digest == attempt_binding_digest
    registry._load_trusted_readback(baseline)
    registry._load_trusted_readback(final)
    for item in oracle_evidence:
        for classifier in item.classifier_results:
            _trust_decisive_for_unit(registry, classifier)
        for structured in (
            *item.structured_events,
            *item.tool_results,
            *item.readbacks,
        ):
            _trust_decisive_for_unit(registry, structured)
    journal.seal_baseline(baseline)
    journal.begin_execution()
    runner = execution.GenericAcceptanceRunner(
        registry=registry,
        authority=authority,
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


@pytest.mark.parametrize("block_id", EVIDENCE_BLOCK_IDS)
def test_generic_runner_validates_every_canonical_evidence_block(
    tmp_path: Path,
    block_id: str,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    block = registry.compiled_policy.evidence_blocks[block_id]
    assertion_ids = {item.assertion_id for item in block.oracle_checks.values()}
    for criterion_id in block.criterion_ids:
        assertion_ids.update(
            item.assertion_id
            for item in registry.compiled_policy.criteria[
                criterion_id
            ].oracle_checks.values()
        )
    input_seed = execution.EvidenceBlockAttemptV2(
        schema_version="noor-e2e-evidence-block-attempt/v2",
        execution_id=block_id,
        evidence_collection_digest="1" * 64,
        evaluator_config_digest="2" * 64,
        oracle_evidence=(
            policy.OracleEvidence(
                assertion_id=next(iter(assertion_ids)),
                structured_events=(),
                tool_results=(),
                readbacks=(),
                classifier_results=(),
                text_supplements=(),
            ),
        ),
        permission_evidence=block.required_permissions,
    )
    plan_digest = execution.evidence_block_input_digest(input_seed)
    run_id = f"run-{block_id.lower()}"
    input_digests = {
        identity: "0" * 64 for identity in registry.compiled_plan.execution_ids
    }
    input_digests[block_id] = plan_digest
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id=run_id,
        execution_input_digests=input_digests,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id=run_id,
        authority=authority,
    )
    authorization = journal.authorization
    oracle_evidence = []
    for assertion_id in sorted(assertion_ids):
        assertion = registry.compiled_policy.assertions[assertion_id]
        if assertion.oracle.kind == "classifier_result":
            classifier = policy.ClassifierResult.build(
                assertion_id=assertion_id,
                policy_digest=registry.compiled_policy.policy_digest,
                evaluator_digest=registry.classifier_evaluator_digest(assertion_id),
                run_id=run_id,
                attempt_digest=plan_digest,
                preflight_digest=authorization.preflight_digest,
                classifier_id=assertion.oracle.classifier_id,
                producer=assertion.oracle.allowed_producers[0],
                source_id=f"{assertion_id}:classifier",
                source_digest="3" * 64,
                observed_at=datetime.now(UTC),
                passed=True,
                reason="Structured classifier passed.",
            )
            _trust_decisive_for_unit(registry, classifier)
            item = policy.OracleEvidence(
                assertion_id=assertion_id,
                structured_events=(),
                tool_results=(),
                readbacks=(),
                classifier_results=(classifier,),
                text_supplements=(),
            )
        else:
            event = policy.StructuredEvent.build(
                assertion_id=assertion_id,
                producer=assertion.oracle.allowed_producers[0],
                source_id=f"{assertion_id}:event",
                source_digest="4" * 64,
                observed_at=datetime.now(UTC),
                passed=True,
                reason="Structured evidence passed.",
                run_id=run_id,
                attempt_digest=plan_digest,
                preflight_digest=authorization.preflight_digest,
            )
            _trust_decisive_for_unit(registry, event)
            item = policy.OracleEvidence(
                assertion_id=assertion_id,
                structured_events=(event,),
                tool_results=(),
                readbacks=(),
                classifier_results=(),
                text_supplements=(),
            )
        oracle_evidence.append(item)
    attempt = input_seed.model_copy(update={"oracle_evidence": tuple(oracle_evidence)})
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id=f"{block_id}:baseline",
        run_id=run_id,
        preflight_digest=authorization.preflight_digest,
        collector_artifact_digest=authorization.readback_collector_digest,
        causal_event_digest="5" * 64,
        observed_at=datetime.now(UTC),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    runner = execution.GenericAcceptanceRunner(
        registry=registry,
        authority=authority,
        journal=journal,
    )

    result = runner.validate_evidence_block(attempt)

    assert result.execution_id == block_id
    assert result.outcome == "PASS"
    assert result.plan_digest == plan_digest


def test_v1_authorization_can_enter_v2_only_through_exact_preflight_bridge() -> None:
    """A caller-built v2 document must not substitute for approved v1 authority."""

    _, execution = _modules()

    assert hasattr(execution, "build_execution_authorization_from_v1")


def test_registry_factory_rebuilds_authority_from_protected_typed_payloads(
    tmp_path: Path,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    inputs = _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id="factory-run",
    )

    execution._write_test_authority_bundle(**inputs)
    handle = execution.issue_execution_authorization_handle(
        registry=registry,
        protected_root=root,
        run_id="factory-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root,
        run_id="factory-run",
        authority=handle,
    )

    assert journal.authorization.registry_id == registry.registry_id
    with pytest.raises(TypeError):
        json.dumps(handle)
    with pytest.raises(TypeError):
        pickle.dumps(handle)


@pytest.mark.parametrize("missing_name", ["receipt.json", "preflight-request.json"])
def test_authority_factory_rejects_missing_receipt_or_payload(
    tmp_path: Path,
    missing_name: str,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    run_id = "missing-bundle-run"
    inputs = _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id=run_id,
    )
    execution._write_test_authority_bundle(**inputs)
    (root / "authority-bundles" / run_id / missing_name).unlink()

    with pytest.raises(Exception, match="protected|receipt|payload"):
        execution.issue_execution_authorization_handle(
            registry=registry,
            protected_root=root,
            run_id=run_id,
        )


def test_authority_factory_rejects_forged_payload_and_receipt(
    tmp_path: Path,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"

    payload_inputs = _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id="forged-payload-run",
    )
    execution._write_test_authority_bundle(**payload_inputs)
    payload_path = (
        root / "authority-bundles" / "forged-payload-run" / "preflight-request.json"
    )
    payload_path.write_bytes(payload_path.read_bytes() + b" ")
    with pytest.raises(Exception, match="payload digest drift"):
        execution.issue_execution_authorization_handle(
            registry=registry,
            protected_root=root,
            run_id="forged-payload-run",
        )

    receipt_inputs = _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id="forged-receipt-run",
    )
    execution._write_test_authority_bundle(**receipt_inputs)
    receipt_path = root / "authority-bundles" / "forged-receipt-run" / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["registry_id"] = "forged-registry"
    receipt_path.write_bytes(execution._canonical_bytes(receipt))
    with pytest.raises(Exception, match="receipt drift"):
        execution.issue_execution_authorization_handle(
            registry=registry,
            protected_root=root,
            run_id="forged-receipt-run",
        )


def test_authority_factory_rejects_task1_other_registry_and_run_drift(
    tmp_path: Path,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    run_id = "exact-owner-run"
    inputs = _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id=run_id,
    )
    execution._write_test_authority_bundle(**inputs)

    other_registry = _registry()
    other_registry.registry_id = "other-registry"
    with pytest.raises(Exception, match="receipt drift"):
        execution.issue_execution_authorization_handle(
            registry=other_registry,
            protected_root=root,
            run_id=run_id,
        )
    with pytest.raises(Exception, match="protected|receipt"):
        execution.issue_execution_authorization_handle(
            registry=registry,
            protected_root=root,
            run_id="other-run",
        )

    bundle_root = root / "authority-bundles" / run_id
    task1_path = bundle_root / "task1-bindings.json"
    task1 = json.loads(task1_path.read_text(encoding="utf-8"))
    task1["authorization_digest"] = "f" * 64
    task1_path.write_bytes(execution._canonical_bytes(task1))
    receipt_path = bundle_root / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["payload_digests"]["task1_bindings"] = hashlib.sha256(
        task1_path.read_bytes()
    ).hexdigest()
    receipt_path.write_bytes(execution._canonical_bytes(receipt))
    with pytest.raises(Exception, match="Task 1"):
        execution.issue_execution_authorization_handle(
            registry=registry,
            protected_root=root,
            run_id=run_id,
        )


@pytest.mark.parametrize(
    "observation_delta",
    [timedelta(minutes=-16), timedelta(seconds=1)],
    ids=["stale", "future"],
)
def test_authority_factory_rejects_stale_or_future_preflight(
    tmp_path: Path,
    observation_delta: timedelta,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    run_id = f"preflight-{observation_delta.total_seconds():g}"
    now = datetime.now(UTC)
    inputs = _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id=run_id,
        now=now,
    )
    observation = inputs["observation"]
    inputs["observation"] = observation.model_copy(
        update={
            "readback_identity": observation.readback_identity.model_copy(
                update={"observed_at": now + observation_delta}
            )
        }
    )
    execution._write_test_authority_bundle(**inputs)

    with pytest.raises(Exception, match="stale|future"):
        execution.issue_execution_authorization_handle(
            registry=registry,
            protected_root=root,
            run_id=run_id,
            current_time=now,
        )


def test_authority_factory_rejects_store_root_and_symlink_root_drift(
    tmp_path: Path,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    run_id = "store-drift-run"
    inputs = _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id=run_id,
    )
    execution._write_test_authority_bundle(**inputs)
    bundle_root = root / "authority-bundles" / run_id
    stores_path = bundle_root / "store-identities.json"
    stores = json.loads(stores_path.read_text(encoding="utf-8"))
    stores["anchor_root_digest"] = "f" * 64
    stores_path.write_bytes(execution._canonical_bytes(stores))
    receipt_path = bundle_root / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["payload_digests"]["store_identities"] = hashlib.sha256(
        stores_path.read_bytes()
    ).hexdigest()
    receipt_path.write_bytes(execution._canonical_bytes(receipt))

    with pytest.raises(Exception, match="store root binding drift"):
        execution.issue_execution_authorization_handle(
            registry=registry,
            protected_root=root,
            run_id=run_id,
        )

    symlink = tmp_path / "protected-link"
    symlink.symlink_to(root, target_is_directory=True)
    with pytest.raises(Exception, match="no-follow|protected.*root|receipt drift"):
        execution.issue_execution_authorization_handle(
            registry=registry,
            protected_root=symlink,
            run_id=run_id,
        )


def test_authority_handle_rejects_other_run_root_and_registry(
    tmp_path: Path,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    handle = _issued_authority(
        registry,
        protected_root=root,
        run_id="bound-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root,
        run_id="bound-run",
        authority=handle,
    )
    (tmp_path / "other-root").mkdir()

    for other_root, other_run in (
        (tmp_path / "other-root", "bound-run"),
        (root, "other-run"),
    ):
        with pytest.raises(Exception, match="authority handle"):
            execution.ProtectedExecutionJournal.create(
                protected_root=other_root,
                run_id=other_run,
                authority=handle,
            )

    other_registry = _registry()
    other_registry.registry_id = "other-registry"
    with pytest.raises(Exception, match="authority handle"):
        execution.GenericAcceptanceRunner(
            registry=other_registry,
            authority=handle,
            journal=journal,
        )


def test_dataclass_replace_cannot_substitute_extra_authorized_action(
    tmp_path: Path,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    handle = _issued_authority(
        registry,
        protected_root=root,
        run_id="replace-handle-run",
    )
    extra_action = handle._authorization.action_specs[0].model_copy(
        update={"action_id": "forged-extra-action"}
    )
    substituted = replace(
        handle,
        _authorization=handle._authorization.model_copy(
            update={
                "action_specs": (
                    *handle._authorization.action_specs,
                    extra_action,
                )
            }
        ),
    )

    with pytest.raises(Exception, match="authority handle|authorization.*drift"):
        execution.ProtectedExecutionJournal.create(
            protected_root=root,
            run_id="replace-handle-run",
            authority=substituted,
        )


def test_reparsed_v2_cannot_substitute_for_authority_handle(tmp_path: Path) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    handle = _issued_authority(
        registry,
        protected_root=root,
        run_id="reparsed-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root,
        run_id="reparsed-run",
        authority=handle,
    )
    reparsed = execution.ExecutionAuthorizationV2.model_validate_json(
        journal.authorization.model_dump_json()
    )

    with pytest.raises(Exception, match="authority handle"):
        execution.ProtectedExecutionJournal.open(
            protected_root=root,
            run_id="reparsed-run",
            authority=reparsed,
        )
    with pytest.raises(TypeError):
        execution.issue_execution_authorization_handle(
            registry=registry,
            protected_root=root,
            run_id="reparsed-run",
            authorization=reparsed,
        )


def test_permit_contract_binds_the_exact_request_identity() -> None:
    """External permits must carry every value revalidated immediately before I/O."""

    _, execution = _modules()

    assert {
        "run_id",
        "authorization_digest",
        "execution_id",
        "step_id",
        "capability",
        "operation_permission",
        "destination_digest",
        "payload_digest",
        "idempotency_key",
        "capability_units",
        "issued_at",
        "expires_at",
    } <= set(execution.ActionReservation.model_fields)


def test_caller_built_authorization_cannot_open_a_protected_journal(
    tmp_path: Path,
) -> None:
    """Typed caller input is not registry-owned executable authority."""

    _, execution = _modules()
    registry = _registry()
    caller_authorization = _authorization(registry, trusted=False)

    with pytest.raises(Exception, match="authority handle"):
        execution.ProtectedExecutionJournal.create(
            protected_root=tmp_path / "protected",
            run_id="caller-auth-run",
            authority=caller_authorization,
        )


def test_persistent_authority_handle_binds_exact_protected_root(
    tmp_path: Path,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    handle = _issued_authority(
        registry,
        protected_root=root,
        run_id="authority-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root,
        run_id="authority-run",
        authority=handle,
    )
    assert journal.authorization_digest == execution.authorization_digest(
        journal.authorization
    )
    (tmp_path / "other").mkdir()
    with pytest.raises(Exception, match="authority handle"):
        execution.ProtectedExecutionJournal.create(
            protected_root=tmp_path / "other",
            run_id="authority-run",
            authority=handle,
        )


def test_final_readback_rejects_caller_object_without_collector_receipt(
    tmp_path: Path,
) -> None:
    """A caller-built observation is not independent final inventory."""

    policy, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    run_id = "caller-final-readback"
    authority = _issued_authority(
        registry,
        protected_root=root,
        run_id=run_id,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root,
        run_id=run_id,
        authority=authority,
    )
    authorization = journal.authorization
    now = datetime.now(UTC)
    journal.seal_baseline(
        policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="caller-final-baseline",
            run_id=run_id,
            preflight_digest=authorization.preflight_digest,
            collector_artifact_digest=authorization.readback_collector_digest,
            causal_event_digest="1" * 64,
            observed_at=now - timedelta(seconds=2),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    journal.anchor_final_turn(
        event_digest="2" * 64,
        occurred_at=now - timedelta(seconds=1),
    )
    caller_final = policy.ReadbackObservation.build(
        phase="final",
        collector_id="independent-readback-collector",
        source_id="caller-built-final",
        run_id=run_id,
        preflight_digest=authorization.preflight_digest,
        collector_artifact_digest=authorization.readback_collector_digest,
        causal_event_digest=journal.previous_event_digest,
        observed_at=now,
        inventory={"synthetic:item": {"state": "closed"}},
    )

    with pytest.raises(Exception, match="collector.*receipt|producer.*receipt"):
        journal.seal_final_readback(caller_final)


def test_gate_receipt_binds_full_protected_provenance() -> None:
    _, execution = _modules()

    assert {
        "registry_id",
        "run_id",
        "authorization_digest",
        "execution_id",
        "criterion_ids",
        "execution_owner",
        "execution_started_event_digest",
        "artifact_sha256",
    } <= set(execution.GateEvidenceReceipt.model_fields)


@pytest.mark.parametrize(
    "variant",
    ("stale", "future", "wrong-collector", "wrong-head"),
)
def test_final_readback_rejects_invalid_collector_provenance(
    tmp_path: Path,
    variant: str,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    run_id = f"invalid-final-{variant}"
    now = datetime.now(UTC)
    authority = _issued_authority(
        registry,
        protected_root=root,
        run_id=run_id,
        now=now,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root,
        run_id=run_id,
        authority=authority,
    )
    authorization = journal.authorization
    anchor_at = (
        now - timedelta(minutes=7) if variant == "stale" else now - timedelta(seconds=2)
    )
    observed_at = {
        "stale": now - timedelta(minutes=6),
        "future": now + timedelta(seconds=1),
    }.get(variant, now - timedelta(seconds=1))
    journal.seal_baseline(
        policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id=f"{variant}-baseline",
            run_id=run_id,
            preflight_digest=authorization.preflight_digest,
            collector_artifact_digest=authorization.readback_collector_digest,
            causal_event_digest="1" * 64,
            observed_at=anchor_at - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    journal.anchor_final_turn(event_digest="2" * 64, occurred_at=anchor_at)
    final = policy.ReadbackObservation.build(
        phase="final",
        collector_id=(
            "caller-collector"
            if variant == "wrong-collector"
            else "independent-readback-collector"
        ),
        source_id=f"{variant}-final",
        run_id=run_id,
        preflight_digest=authorization.preflight_digest,
        collector_artifact_digest=authorization.readback_collector_digest,
        causal_event_digest=(
            "f" * 64 if variant == "wrong-head" else journal.previous_event_digest
        ),
        observed_at=observed_at,
        inventory={"synthetic:item": {"state": "closed"}},
    )

    with pytest.raises(Exception, match="collector|receipt|binding|fresh|future"):
        receipt_digest = execution._write_test_final_readback_bundle(journal, final)
        journal.seal_final_readback(
            final,
            receipt_digest=receipt_digest,
            current_time=now,
        )


def test_future_blocked_gate_and_unbound_client_exclusion_fail_closed(
    tmp_path: Path,
) -> None:
    policy, execution = _modules()
    registry = _registry()

    for run_id, execution_id, outcome, producer, observed_at in (
        (
            "future-blocked-gate",
            registry.compiled_plan.execution_ids[0],
            "BLOCKED",
            "independent-readback-collector",
            datetime.now(UTC) + timedelta(seconds=1),
        ),
        (
            "unbound-client-exclusion",
            "EB-REFERRAL",
            "EXCLUDED_BY_CLIENT",
            "client-exclusion-authority",
            datetime.now(UTC) - timedelta(seconds=30),
        ),
    ):
        root = tmp_path / run_id
        authority = _issued_authority(
            registry,
            protected_root=root,
            run_id=run_id,
        )
        journal = execution.ProtectedExecutionJournal.create(
            protected_root=root,
            run_id=run_id,
            authority=authority,
        )
        authorization = journal.authorization
        now = datetime.now(UTC)
        journal.seal_baseline(
            policy.ReadbackObservation.build(
                phase="baseline",
                collector_id="independent-readback-collector",
                source_id=f"{run_id}-baseline",
                run_id=run_id,
                preflight_digest=authorization.preflight_digest,
                collector_artifact_digest=authorization.readback_collector_digest,
                causal_event_digest="1" * 64,
                observed_at=now - timedelta(seconds=1),
                inventory={"synthetic:item": {"state": "absent"}},
            )
        )
        journal.begin_execution()
        receipt_digest = execution._write_test_gate_evidence_bundle(
            registry=registry,
            journal=journal,
            execution_id=execution_id,
            outcome=outcome,
            producer=producer,
            observed_at=observed_at,
            expires_at=now + timedelta(minutes=1),
            client_authority_digest=(
                "a" * 64 if outcome == "EXCLUDED_BY_CLIENT" else None
            ),
        )
        attempt = execution.GateAttemptV2(
            schema_version="noor-e2e-gate-attempt/v2",
            execution_id=execution_id,
            outcome=outcome,
            run_started_at=journal._execution_started_at,
            execution_started_event_digest=journal._execution_started_event_digest,
            receipt_digest=receipt_digest,
        )
        runner = execution.GenericAcceptanceRunner(
            registry=registry,
            authority=authority,
            journal=journal,
        )

        with pytest.raises(Exception, match="receipt drift|client exclusion"):
            runner.validate_gate_attempt(attempt, current_time=now)


def test_protected_client_exclusion_authority_issues_valid_gate(
    tmp_path: Path,
) -> None:
    policy, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    run_id = "protected-client-exclusion"
    execution_id = "EB-REFERRAL"
    now = datetime.now(UTC)
    criterion_ids = tuple(
        item.criterion_id
        for item in registry.compiled_plan.criteria.values()
        if execution_id in item.obligation_ids
    )
    exclusion = execution.ClientExclusionAuthority(
        authority_id="client-exclusion-001",
        issuer="client-exclusion-authority",
        execution_id=execution_id,
        criterion_ids=criterion_ids,
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=30),
    )
    protected_authorities = execution.ProtectedExecutionAuthorities(
        schema_version="noor-e2e-protected-execution-authorities/v2",
        client_exclusions=(exclusion,),
        side_effect_authority=execution.SideEffectAuthority(
            issuer="protected-side-effect-authority",
            cleanup_owner="synthetic-local-executor",
            cleanup_authority="synthetic-cleanup",
        ),
    )
    authority = _issued_authority(
        registry,
        protected_root=root,
        run_id=run_id,
        now=now,
        protected_authorities=protected_authorities,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root,
        run_id=run_id,
        authority=authority,
    )
    journal.seal_baseline(
        policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="protected-exclusion-baseline",
            run_id=run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=(journal.authorization.readback_collector_digest),
            causal_event_digest="1" * 64,
            observed_at=now - timedelta(seconds=2),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    client_authority_digest = execution._digest(exclusion.model_dump(mode="json"))
    receipt_digest = execution._write_test_gate_evidence_bundle(
        registry=registry,
        journal=journal,
        execution_id=execution_id,
        outcome="EXCLUDED_BY_CLIENT",
        producer="client-exclusion-authority",
        observed_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=1),
        client_authority_digest=client_authority_digest,
    )
    attempt = execution.GateAttemptV2(
        schema_version="noor-e2e-gate-attempt/v2",
        execution_id=execution_id,
        outcome="EXCLUDED_BY_CLIENT",
        run_started_at=journal._execution_started_at,
        execution_started_event_digest=journal._execution_started_event_digest,
        receipt_digest=receipt_digest,
    )
    runner = execution.GenericAcceptanceRunner(
        registry=registry,
        authority=authority,
        journal=journal,
    )

    assert runner.validate_gate_attempt(attempt, current_time=now) == attempt


def test_protected_retention_authority_issues_valid_retained_evidence(
    tmp_path: Path,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    run_id = "protected-retention"
    execution_id = "SC-OPEN-EN"
    now = datetime.now(UTC)
    criterion_ids = tuple(
        item.criterion_id
        for item in registry.compiled_plan.criteria.values()
        if execution_id in item.obligation_ids
    )
    retention = execution.AuthorizedRetentionSpec(
        authority_id="retention-001",
        issuer="client-retention-authority",
        artifact_id="synthetic:item",
        execution_id=execution_id,
        criterion_ids=criterion_ids,
        cleanup_owner="synthetic-local-executor",
        cleanup_authority="synthetic-cleanup",
        retention_owner="client-owner",
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=30),
    )
    protected_authorities = execution.ProtectedExecutionAuthorities(
        schema_version="noor-e2e-protected-execution-authorities/v2",
        client_exclusions=(),
        side_effect_authority=execution.SideEffectAuthority(
            issuer="protected-side-effect-authority",
            cleanup_owner="synthetic-local-executor",
            cleanup_authority="synthetic-cleanup",
            retention_authorities=(retention,),
        ),
    )
    authority = _issued_authority(
        registry,
        protected_root=root,
        run_id=run_id,
        now=now,
        protected_authorities=protected_authorities,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root,
        run_id=run_id,
        authority=authority,
    )
    issued = journal.authorization.side_effect_authority.retention_authorities[0]
    issued_payload = issued.model_dump(mode="json")
    authority_digest = execution._digest(issued_payload)
    entry = {
        "artifact_id": issued.artifact_id,
        "scenario_id": issued.execution_id,
        "subsystem": "conversation",
        "artifact_type": "conversation",
        "creation_path": "application-authorized",
        "cleanup_owner": issued.cleanup_owner,
        "cleanup_authority": issued.cleanup_authority,
        "baseline_readback": {"state": "absent"},
        "expected_effect": {"state": "created_for_test"},
        "follow_up_suppressed": True,
        "final_readback": {"state": "retained"},
        "disposition": "retained_as_test_evidence",
        "retention_pre_authorized": True,
        "retention_owner": issued.retention_owner,
        "retention_authority_digest": authority_digest,
        "retention_expires_at": issued.expires_at.isoformat(),
        "final_disposition_date": now.isoformat(),
    }

    validate_side_effect_closeout(
        [entry],
        observed_inventory={issued.artifact_id: {"state": "retained"}},
        authorized_cleanup_owner=issued.cleanup_owner,
        authorized_cleanup_authority=issued.cleanup_authority,
        authorized_retentions={
            issued.artifact_id: {
                **issued_payload,
                "authority_digest": authority_digest,
            }
        },
        current_time=now,
    )


@pytest.mark.parametrize(
    "variant",
    (
        "exclusion-criterion",
        "exclusion-window",
        "retention-owner",
        "retention-expiry",
    ),
)
def test_protected_execution_authority_semantic_drift_fails_closed(
    tmp_path: Path,
    variant: str,
) -> None:
    _, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    run_id = f"authority-drift-{variant}"
    now = datetime.now(UTC)
    exclusion_execution = "EB-REFERRAL"
    retention_execution = "SC-OPEN-EN"
    exclusion_criteria = tuple(
        item.criterion_id
        for item in registry.compiled_plan.criteria.values()
        if exclusion_execution in item.obligation_ids
    )
    retention_criteria = tuple(
        item.criterion_id
        for item in registry.compiled_plan.criteria.values()
        if retention_execution in item.obligation_ids
    )
    protected_authorities = execution.ProtectedExecutionAuthorities(
        schema_version="noor-e2e-protected-execution-authorities/v2",
        client_exclusions=(
            execution.ClientExclusionAuthority(
                authority_id="client-exclusion-drift",
                issuer="client-exclusion-authority",
                execution_id=exclusion_execution,
                criterion_ids=exclusion_criteria,
                issued_at=now - timedelta(minutes=1),
                expires_at=now + timedelta(minutes=30),
            ),
        ),
        side_effect_authority=execution.SideEffectAuthority(
            issuer="protected-side-effect-authority",
            cleanup_owner="synthetic-local-executor",
            cleanup_authority="synthetic-cleanup",
            retention_authorities=(
                execution.AuthorizedRetentionSpec(
                    authority_id="retention-drift",
                    issuer="client-retention-authority",
                    artifact_id="synthetic:item",
                    execution_id=retention_execution,
                    criterion_ids=retention_criteria,
                    cleanup_owner="synthetic-local-executor",
                    cleanup_authority="synthetic-cleanup",
                    retention_owner="client-owner",
                    issued_at=now - timedelta(minutes=1),
                    expires_at=now + timedelta(minutes=30),
                ),
            ),
        ),
    )
    inputs = _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id=run_id,
        now=now,
        protected_authorities=protected_authorities,
    )
    execution._write_test_authority_bundle(**inputs)
    bundle_root = root / "authority-bundles" / run_id
    authorities_path = bundle_root / "execution-authorities.json"
    payload = json.loads(authorities_path.read_text(encoding="utf-8"))
    if variant == "exclusion-criterion":
        payload["client_exclusions"][0]["criterion_ids"] = ["AC-01"]
    elif variant == "exclusion-window":
        payload["client_exclusions"][0]["issued_at"] = now.isoformat()
    elif variant == "retention-owner":
        payload["side_effect_authority"]["retention_authorities"][0][
            "cleanup_owner"
        ] = "forged-owner"
    else:
        payload["side_effect_authority"]["retention_authorities"][0]["expires_at"] = (
            now + timedelta(hours=2)
        ).isoformat()
    authorities_path.write_bytes(execution._canonical_bytes(payload))
    receipt_path = bundle_root / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["payload_digests"]["execution_authorities"] = hashlib.sha256(
        authorities_path.read_bytes()
    ).hexdigest()
    receipt_path.write_bytes(execution._canonical_bytes(receipt))

    with pytest.raises(Exception, match="protected.*drift|authority.*drift"):
        execution.issue_execution_authorization_handle(
            registry=registry,
            protected_root=root,
            run_id=run_id,
            current_time=now,
        )


def test_reservation_rejects_request_not_present_in_protected_action_spec(
    tmp_path: Path,
) -> None:
    """A well-shaped digest is insufficient without an exact protected action spec."""

    policy, execution = _modules()
    registry = _registry()
    authority = _issued_authority(
        registry,
        protected_root=tmp_path / "protected",
        run_id="unlisted-action-run",
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=tmp_path / "protected",
        run_id="unlisted-action-run",
        authority=authority,
    )
    authorization = journal.authorization
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="unlisted-action-baseline",
        run_id="unlisted-action-run",
        preflight_digest=authorization.preflight_digest,
        collector_artifact_digest=authorization.readback_collector_digest,
        causal_event_digest="1" * 64,
        observed_at=datetime.now(UTC) - timedelta(seconds=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()

    with pytest.raises(Exception, match="action spec|protected action"):
        journal.reserve_action(
            action_id="unlisted-action",
            adapter_id="fake-local-adapter",
            subsystem="outbound_text",
            **_action_request(),
            messages=0,
            model_calls=0,
            cost_usd=0,
        )


def test_reservation_recovery_reuses_ledger_reservation_without_recharging_quota(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A crash after the durable quota reservation cannot spend it a second time."""

    policy, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    authority = _issued_authority(
        registry, protected_root=root, run_id="reservation-recovery-run"
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="reservation-recovery-run", authority=authority
    )
    now = datetime.now(UTC)
    journal.seal_baseline(
        policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="reservation-recovery-baseline",
            run_id=journal.run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
            causal_event_digest="a" * 64,
            observed_at=now - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    original_append = journal._append_event

    def crash_before_reservation_journal(**event):
        if event["kind"] == "action_reserved":
            raise RuntimeError("crash after reservation ledger")
        return original_append(**event)

    monkeypatch.setattr(journal, "_append_event", crash_before_reservation_journal)
    request = _action_request()
    with pytest.raises(RuntimeError, match="reservation ledger"):
        journal.reserve_action(
            action_id="synthetic-action",
            adapter_id="fake-local-adapter",
            subsystem="outbound_text",
            **request,
            messages=1,
            model_calls=1,
            cost_usd=0.25,
        )

    reopened = execution.ProtectedExecutionJournal.open(
        protected_root=root, run_id="reservation-recovery-run", authority=authority
    )
    recovered = reopened._reservations["synthetic-action"]
    assert reopened._actions == {"synthetic-action": "reserved"}
    assert reopened.quota_usage.messages == 1
    assert reopened.quota_usage.model_calls == 1
    assert reopened.quota_usage.cost_usd == 0.25
    assert (
        reopened.reserve_action(
            action_id="synthetic-action",
            adapter_id="fake-local-adapter",
            subsystem="outbound_text",
            **request,
            messages=1,
            model_calls=1,
            cost_usd=0.25,
        )
        == recovered
    )
    assert reopened.quota_usage.cost_usd == 0.25


def test_consumed_permit_cannot_be_automatically_retried(
    tmp_path: Path,
) -> None:
    """Once I/O may have happened, only independent reconciliation may proceed."""

    policy, execution = _modules()
    registry = _registry()
    root = tmp_path / "protected"
    authority = _issued_authority(
        registry, protected_root=root, run_id="permit-retry-run"
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="permit-retry-run", authority=authority
    )
    journal.seal_baseline(
        policy.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="permit-retry-baseline",
            run_id=journal.run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
            causal_event_digest="a" * 64,
            observed_at=datetime.now(UTC) - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    request = _action_request()
    reservation = journal.reserve_action(
        action_id="synthetic-action",
        adapter_id="fake-local-adapter",
        subsystem="outbound_text",
        **request,
        messages=1,
        model_calls=1,
        cost_usd=0.25,
    )
    journal.consume_permit(reservation, adapter_id="fake-local-adapter", **request)

    with pytest.raises(Exception, match="consumed|reservation"):
        journal.reserve_action(
            action_id="synthetic-action",
            adapter_id="fake-local-adapter",
            subsystem="outbound_text",
            **request,
            messages=1,
            model_calls=1,
            cost_usd=0.25,
        )
