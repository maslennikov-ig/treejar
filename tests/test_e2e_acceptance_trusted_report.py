"""Trusted run loading, canonical rollups, and typed report tests."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.e2e_acceptance_backend import build_test_registry

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _modules():
    policy = importlib.import_module("scripts.e2e_acceptance.policy")
    execution = importlib.import_module("scripts.e2e_acceptance.execution")
    trusted = importlib.import_module("scripts.e2e_acceptance.trusted_run")
    return policy, execution, trusted


def _bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: object) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = _bytes(value)
    path.write_bytes(payload)
    path.chmod(0o600)
    return hashlib.sha256(payload).hexdigest()


def _build_verified_run(
    tmp_path: Path,
    *,
    partial_scope: bool = False,
    leaked_answer: bool = False,
    task1_digest_drift: bool = False,
    invalid_blocked_gate: bool = False,
    self_authorized_exclusion: bool = False,
    without_attempts: bool = False,
    incomplete_turns: bool = False,
    missing_attempt_receipts: bool = False,
    missing_report_receipt: bool = False,
    protected_attempt_digest_drift: bool = False,
):
    policy, execution, trusted = _modules()
    source_registry = policy.TrustedAcceptanceRegistry.from_canonical_repo()
    contract_paths = (
        ".codex/goals/tj-ee5f/scope-criterion-snapshot.json",
        ".codex/goals/tj-ee5f/scope-source-provenance.json",
        ".codex/stages/tj-ee5f/traceability-manifest.json",
        ".codex/stages/tj-ee5f/scenario-set.json",
        ".codex/stages/tj-ee5f/authorization-manifest.example.json",
    )
    for relative in contract_paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT_ROOT / relative, destination)
    (tmp_path / ".git").mkdir()
    registry = build_test_registry(tmp_path, source_registry.compiled_policy)
    tracked = tmp_path / ".codex/stages/tj-ee5f/results"
    protected = trusted._published_protected_root(registry)
    run_id = "synthetic-trusted-run"
    tracked_run = tracked / run_id
    protected_run = protected / run_id
    now = datetime.now(UTC)
    authorization = execution.ExecutionAuthorizationV2(
        schema_version="noor-e2e-authorization/v2",
        authorization_id="synthetic-report-auth",
        status="approved",
        issued_at=now - timedelta(minutes=2),
        expires_at=now + timedelta(hours=1),
        task1_authorization_digest=(
            "0" * 64 if task1_digest_drift else registry.task1_authorization_digest
        ),
        task1_input_digests=registry.task1_input_digests,
        preflight_digest="8" * 64,
        readback_collector_digest="9" * 64,
        policy_digest=registry.compiled_policy.policy_digest,
        compiler_id=registry.compiled_plan.compiler_id,
        compiled_plan_digest=registry.compiled_plan.plan_digest,
        execution_ids=registry.compiled_plan.execution_ids,
        execution_input_digests={
            identity: "2" * 64 for identity in registry.compiled_plan.execution_ids
        },
        adapter_ids=("fake-local-adapter",),
        collector_ids=("independent-readback-collector",),
        permissions=("fixture:execute",),
        live_binding=execution.ExactLiveAuthorizationBinding(
            v1_manifest_digest="1" * 64,
            preflight_request_digest="2" * 64,
            preflight_observation_digest="3" * 64,
            runtime_identity_digest="4" * 64,
            target_digest="5" * 64,
            permissions_digest=execution._digest(("fixture:execute",)),
            cleanup_retention_digest="6" * 64,
            execution_set_digest=execution._digest(
                {
                    "execution_ids": registry.compiled_plan.execution_ids,
                    "input_digests": {
                        identity: "2" * 64
                        for identity in registry.compiled_plan.execution_ids
                    },
                    "quotas": {
                        "max_scenarios": 29,
                        "max_messages": 100,
                        "max_model_calls": 100,
                        "max_cost_usd": 10.0,
                        "subsystem_quotas": {"outbound_text": 100},
                    },
                }
            ),
            adapter_ids_digest=execution._digest(("fake-local-adapter",)),
            collector_ids_digest=execution._digest(("independent-readback-collector",)),
            stores_digest=execution._digest(
                {
                    "raw_store_id": "synthetic-raw-store",
                    "tracked_store_id": "synthetic-tracked-store",
                    "anchor_store_id": "synthetic-anchor-store",
                    "raw_root_digest": execution.store_root_digest(protected_run),
                    "tracked_root_digest": execution.store_root_digest(tracked_run),
                    "anchor_root_digest": execution.store_root_digest(protected_run),
                }
            ),
            preflight_observed_at=now - timedelta(minutes=1),
        ),
        store_ids=execution.StoreIdentities(
            raw_store_id="synthetic-raw-store",
            tracked_store_id="synthetic-tracked-store",
            anchor_store_id="synthetic-anchor-store",
            raw_root_digest=execution.store_root_digest(protected_run),
            tracked_root_digest=execution.store_root_digest(tracked_run),
            anchor_root_digest=execution.store_root_digest(protected_run),
        ),
        registry_id=registry.registry_id,
        quotas=execution.ProtectedQuotas(
            max_scenarios=29,
            max_messages=100,
            max_model_calls=100,
            max_cost_usd=10,
            subsystem_quotas={"outbound_text": 100},
        ),
    )
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id=run_id,
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=now - timedelta(minutes=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    final = policy.ReadbackObservation.build(
        phase="final",
        collector_id="independent-readback-collector",
        source_id="synthetic-final",
        run_id=run_id,
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="5" * 64,
        observed_at=now + timedelta(seconds=10),
        inventory={"synthetic:item": {"state": "closed"}},
    )
    evidence_values = {
        "fresh": {
            "status": "passed",
            "freshness_identity": {"release": "synthetic-release"},
        },
        "reuse": {
            "status": "passed",
            "reused_exact_identity": {"source": "synthetic-security-proof"},
        },
        "gate": {
            "status": "passed" if invalid_blocked_gate else "blocked",
            "external_gate_resolution": "blocked",
        },
    }
    index_entries = []
    for identity, value in evidence_values.items():
        relative = f"evidence/{identity}.json"
        digest = _write_json(tracked_run / relative, value)
        index_entries.append(
            {
                "evidence_id": identity,
                "relative_path": relative,
                "sha256": digest,
                "producer": "trusted-evidence-registry",
            }
        )
    criteria = []
    for criterion in registry.compiled_plan.criteria.values():
        if criterion.evidence_mode.value == "fresh":
            outcome, ref = "PASS", "fresh"
        elif criterion.evidence_mode.value == "reused_exact":
            outcome, ref = "PASS", "reuse"
        else:
            outcome, ref = "BLOCKED", "gate"
        criteria.append(
            {
                "criterion_id": criterion.criterion_id,
                "outcome": outcome,
                "evidence_mode": criterion.evidence_mode.value,
                "obligation_outcomes": {
                    identity: outcome for identity in criterion.obligation_ids
                },
                "evidence_refs": [ref],
                "reasoning": "Synthetic local contract evidence.",
            }
        )
    if self_authorized_exclusion:
        criterion = next(row for row in criteria if row["criterion_id"] == "AC-21")
        criterion["outcome"] = "EXCLUDED_BY_CLIENT"
        criterion["obligation_outcomes"] = {
            identity: "EXCLUDED_BY_CLIENT"
            for identity in criterion["obligation_outcomes"]
        }
    if partial_scope:
        criteria = criteria[:1]
    authorization_digest = trusted.canonical_digest(
        authorization.model_dump(mode="json")
    )
    attempt_chain_heads = {}
    executions = []
    for identity in registry.compiled_plan.execution_ids:
        attempt_ref = f"attempt:{identity}"
        executions.append(
            {
                "execution_id": identity,
                "outcome": "PASS",
                "evidence_refs": ["fresh"],
                "attempt_ref": attempt_ref,
            }
        )
        if without_attempts:
            continue
        attempt_digest = hashlib.sha256(identity.encode()).hexdigest()
        semantic_digest = hashlib.sha256(f"semantic:{identity}".encode()).hexdigest()
        raw_digest = hashlib.sha256(f"raw:{identity}".encode()).hexdigest()
        tracked_digest = hashlib.sha256(f"tracked:{identity}".encode()).hexdigest()
        transaction_id = f"{identity.lower()}-attempt-001"
        protected_commit_ref = f"attempts/{transaction_id}/commit.json"
        protected_commit_digest = _write_json(
            protected_run / protected_commit_ref,
            {
                "schema_version": "noor-e2e-attempt-commit/v2",
                "transaction_id": transaction_id,
                "run_id": run_id,
                "execution_id": identity,
                "attempt_digest": (
                    "0" * 64 if protected_attempt_digest_drift else attempt_digest
                ),
                "status": "committed",
                "authorization_digest": authorization_digest,
                "semantic_digest": semantic_digest,
                "raw_digest": raw_digest,
                "tracked_digest": tracked_digest,
            },
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
            event = {
                "cursor": cursor,
                "phase": phase,
                "previous_event_digest": previous,
                "run_id": run_id,
                "execution_id": identity,
                "attempt_digest": attempt_digest,
                "semantic_digest": semantic_digest,
                "authorization_digest": authorization_digest,
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
        attempt = {
            "schema_version": "noor-e2e-committed-execution/v2",
            "run_id": run_id,
            "execution_id": identity,
            "outcome": "PASS",
            "authorization_digest": authorization_digest,
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
        relative = f"attempts/{identity}.json"
        digest = _write_json(tracked_run / relative, attempt)
        attempt_chain_heads[identity] = previous
        index_entries.append(
            {
                "evidence_id": attempt_ref,
                "relative_path": relative,
                "sha256": digest,
                "producer": "protected-attempt-committer",
            }
        )
        if not missing_attempt_receipts:
            _write_json(
                protected_run / f"producer-receipts/attempts/{identity}.json",
                {
                    "schema_version": "noor-e2e-attempt-producer-receipt/v2",
                    "registry_id": registry.registry_id,
                    "run_id": run_id,
                    "execution_id": identity,
                    "attempt_digest": attempt_digest,
                    "authorization_digest": authorization_digest,
                    "semantic_digest": semantic_digest,
                    "raw_digest": raw_digest,
                    "tracked_digest": tracked_digest,
                    "phase_head_digest": previous,
                    "tracked_sha256": digest,
                    "protected_commit_digest": protected_commit_digest,
                },
            )
    if without_attempts:
        attempt_chain_heads = {
            identity: "6" * 64 for identity in registry.compiled_plan.execution_ids
        }
    scenario_ids = tuple(registry.compiled_policy.scenarios)
    if incomplete_turns:
        scenario_ids = scenario_ids[:1]
    report_payload = {
        "schema_version": "noor-e2e-client-report/v2",
        "run_id": run_id,
        "title": "Приёмочное тестирование Noor",
        "generated_at": (now + timedelta(seconds=11)).isoformat(),
        "identity": {
            "repository_commit": "a" * 40,
            "deployed_release_sha": "b" * 40,
            "ci_run_id": "synthetic-ci",
            "app_version": "synthetic-app",
            "migration_head": "synthetic-migration",
            "models": ["fixture/model"],
            "services": {"api": "synthetic-ready"},
            "evidence_refs": ["report-source"],
        },
        "tester": {
            "model": "fixture/tester",
            "reasoning_effort": "none",
            "seed": 20260727,
            "config_digest": "3" * 64,
            "evidence_refs": ["report-source"],
        },
        "judge": {
            "model": "fixture/judge",
            "reasoning_effort": "none",
            "seed": 20260727,
            "config_digest": "4" * 64,
            "evidence_refs": ["report-source"],
        },
        "turns": [
            {
                "execution_id": identity,
                "attempt_id": f"attempt:{identity}",
                "turn_id": f"turn-{position:03d}",
                "question": "Synthetic exact question.",
                "answer": (
                    "Contact +15550001111"
                    if leaked_answer and position == 1
                    else "Synthetic exact answer."
                ),
                "sent_at": now.isoformat(),
                "received_at": (now + timedelta(seconds=1)).isoformat(),
                "first_visible_at": (now + timedelta(seconds=2)).isoformat(),
                "final_visible_at": (now + timedelta(seconds=3)).isoformat(),
                "delivered_at": (now + timedelta(seconds=4)).isoformat(),
                "conversation_id": f"synthetic-conversation-{position}",
                "message_id": f"synthetic-message-{position}",
                "provider_message_id": f"synthetic-provider-{position}",
                "model": "fixture/model",
                "tools": ["fixture_tool"],
                "tool_outcomes": ["fixture outcome"],
                "audit_ids": ["synthetic-audit"],
                "media_refs": ["media/synthetic.png"],
                "token_count": 10,
                "cost_usd": 0,
                "deviation": None,
                "evaluator_reasoning": "Structured checks passed.",
                "transcript_digest": hashlib.sha256(
                    f"transcript:{identity}".encode()
                ).hexdigest(),
                "producer_receipt_digest": hashlib.sha256(
                    f"receipt:{identity}".encode()
                ).hexdigest(),
                "evidence_refs": [
                    f"attempt:{identity}",
                    "report-source",
                ],
            }
            for position, identity in enumerate(scenario_ids, start=1)
        ],
        "executions": [
            {
                "execution_id": row["execution_id"],
                "outcome": row["outcome"],
                "attempt_ref": row["attempt_ref"],
                "evidence_refs": row["evidence_refs"],
            }
            for row in executions
        ],
        "criteria": [
            {
                "criterion_id": row["criterion_id"],
                "evidence_mode": row["evidence_mode"],
                "outcome": row["outcome"],
                "evidence_refs": row["evidence_refs"],
                "reasoning": row["reasoning"],
            }
            for row in criteria
        ],
        "side_effects": [
            {
                "artifact_id": "synthetic:item",
                "subsystem": "conversation",
                "artifact_type": "conversation",
                "baseline": {"state": "absent"},
                "final": {"state": "closed"},
                "disposition": "closed",
                "owner": "acceptance-owner",
                "checksum_refs": ["report-source"],
            }
        ],
        "latency": {
            "p50_ms": 1000,
            "p95_ms": 2000,
            "max_ms": 3000,
            "evidence_refs": ["report-source"],
        },
        "limitations": ["Synthetic local dry-run only."],
        "external_gates": ["Live execution is not authorized."],
        "defects": [
            {
                "defect_id": "synthetic-defect",
                "root_cause": "Synthetic root cause.",
                "violated_invariant": "Synthetic invariant.",
                "fix": "Synthetic fix.",
                "retest": "Synthetic retest.",
                "checksum_refs": ["report-source"],
            }
        ],
    }
    validated_report = trusted.ClientReportPayload.model_validate(report_payload)
    expected_report_digest = hashlib.sha256(_bytes(report_payload)).hexdigest()
    verified_snapshot_digest = trusted._verified_report_snapshot_digest(
        validated_report
    )
    report_source = {
        "schema_version": "noor-e2e-report-source/v2",
        "registry_id": registry.registry_id,
        "report_sections_digest": trusted._report_sections_digest(validated_report),
        "report_payload_sha256": expected_report_digest,
        "verified_snapshot_digest": verified_snapshot_digest,
    }
    report_source_digest = _write_json(
        tracked_run / "evidence/report-source.json",
        report_source,
    )
    index_entries.append(
        {
            "evidence_id": "report-source",
            "relative_path": "evidence/report-source.json",
            "sha256": report_source_digest,
            "producer": "protected-report-materializer",
        }
    )
    if not missing_report_receipt:
        _write_json(
            protected_run / "producer-receipts/report-source.json",
            {
                "schema_version": "noor-e2e-report-producer-receipt/v2",
                "registry_id": registry.registry_id,
                "tracked_sha256": report_source_digest,
                "report_sections_digest": report_source["report_sections_digest"],
                "report_payload_sha256": expected_report_digest,
                "verified_snapshot_digest": verified_snapshot_digest,
            },
        )
    index = {
        "schema_version": "noor-e2e-evidence-index/v2",
        "run_id": run_id,
        "entries": index_entries,
    }
    index_digest = _write_json(tracked_run / "registry/evidence-index.json", index)
    report_digest = _write_json(
        tracked_run / "registry/report-payload.json",
        report_payload,
    )
    assert report_digest == expected_report_digest
    run_document = {
        "schema_version": "noor-e2e-trusted-run/v2",
        "run_id": run_id,
        "authorization": authorization.model_dump(mode="json"),
        "baseline": baseline.model_dump(mode="json"),
        "final": final.model_dump(mode="json"),
        "final_visible_at": [(now + timedelta(seconds=3)).isoformat()],
        "delivered_at": [(now + timedelta(seconds=4)).isoformat()],
        "action_at": [(now + timedelta(seconds=5)).isoformat()],
        "executions": executions,
        "criteria": criteria,
        "open_p0_p1": [],
        "side_effect_ledger_digest": trusted.canonical_digest(
            report_payload["side_effects"]
        ),
        "final_inventory_digest": trusted.canonical_digest(final.inventory),
        "evidence_index_digest": index_digest,
        "report_payload_digest": report_digest,
    }
    run_digest = _write_json(tracked_run / "registry/run.json", run_document)
    anchor = {
        "schema_version": "noor-e2e-trusted-run-anchor/v2",
        "run_id": run_id,
        "policy_digest": registry.compiled_policy.policy_digest,
        "compiled_plan_digest": registry.compiled_plan.plan_digest,
        "authorization_digest": authorization_digest,
        "baseline_digest": baseline.content_digest,
        "final_digest": final.content_digest,
        "run_document_sha256": run_digest,
        "evidence_index_sha256": index_digest,
        "report_payload_sha256": report_digest,
        "criterion_ids": [row["criterion_id"] for row in criteria],
        "execution_ids": list(registry.compiled_plan.execution_ids),
        "phase_journal_head_digest": "5" * 64,
        "attempt_chain_heads": attempt_chain_heads,
    }
    _write_json(protected_run / "registry/anchor.json", anchor)
    tracked_manifest = {
        path.relative_to(tracked_run).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in tracked_run.rglob("*.json")
    }
    protected_manifest = {
        path.relative_to(protected_run).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in protected_run.rglob("*.json")
    }
    _write_json(
        protected_run / "final-commit.json",
        {
            "schema_version": "noor-e2e-published-run-commit/v2",
            "status": "committed",
            "run_id": run_id,
            "registry_id": registry.registry_id,
            "snapshot_digest": "7" * 64,
            "tracked_tree_digest": trusted.canonical_digest(tracked_manifest),
            "protected_tree_digest": trusted.canonical_digest(protected_manifest),
        },
    )
    return registry, tracked_run, protected_run


def test_registry_loads_real_index_and_calculates_canonical_mode_rollups(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)

    registry.open_run(run_id="synthetic-trusted-run")

    assert registry.calculate_rollups() == {
        "coverage_complete": True,
        "execution_complete": True,
        "requirements_met": False,
    }


def test_registry_rejects_one_of_30_scope_even_with_matching_anchor(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(
        tmp_path,
        partial_scope=True,
    )

    with pytest.raises(Exception, match="exact.*30|criterion.*scope"):
        registry.open_run(run_id="synthetic-trusted-run")


def test_typed_russian_report_and_final_serialized_privacy(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    registry.open_run(run_id="synthetic-trusted-run")
    output = tmp_path / "report.md"

    registry.write_report(output)

    report = output.read_text(encoding="utf-8")
    assert "# Приёмочное тестирование Noor" in report
    assert "Synthetic exact question." in report
    assert "Synthetic exact answer." in report
    assert "fixture_tool" in report
    assert "p95" in report
    assert "Synthetic root cause." in report
    assert "AC-01" in report
    assert oct(os.stat(output).st_mode & 0o777) == "0o600"

    leaked_registry, leaked_tracked, leaked_protected = _build_verified_run(
        tmp_path / "leak",
        leaked_answer=True,
    )
    with pytest.raises(Exception, match="phone|privacy|redact"):
        leaked_registry.open_run(run_id="synthetic-trusted-run")


def test_report_turns_are_bound_to_committed_transcript_identity() -> None:
    """A report row is a projection of a protected transcript, not caller prose."""

    _, _, trusted = _modules()

    assert {
        "transcript_digest",
        "producer_receipt_digest",
    } <= set(trusted.TurnReport.model_fields)
