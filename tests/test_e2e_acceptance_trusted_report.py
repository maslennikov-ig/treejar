"""Trusted run loading, canonical rollups, and typed report tests."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

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
):
    policy, execution, trusted = _modules()
    registry = policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)
    tracked = tmp_path / "tracked"
    protected = tmp_path / "protected"
    run_id = "synthetic-trusted-run"
    tracked_run = tracked / run_id
    protected_run = protected / run_id
    now = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    authorization = execution.ExecutionAuthorizationV2(
        schema_version="noor-e2e-authorization/v2",
        authorization_id="synthetic-report-auth",
        status="approved",
        issued_at=now - timedelta(minutes=2),
        expires_at=now + timedelta(hours=1),
        task1_authorization_digest="1" * 64,
        policy_digest=registry.compiled_policy.policy_digest,
        compiler_id=registry.compiled_plan.compiler_id,
        compiled_plan_digest=registry.compiled_plan.plan_digest,
        execution_ids=registry.compiled_plan.execution_ids,
        execution_input_digests={
            identity: "2" * 64 for identity in registry.compiled_plan.execution_ids
        },
        adapter_ids=("fake-local-adapter",),
        store_ids=execution.StoreIdentities(
            raw_store_id="synthetic-raw-store",
            tracked_store_id="synthetic-tracked-store",
            anchor_store_id="synthetic-anchor-store",
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
        observed_at=now - timedelta(minutes=1),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    final = policy.ReadbackObservation.build(
        phase="final",
        collector_id="independent-readback-collector",
        source_id="synthetic-final",
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
            "status": "blocked",
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
    index = {
        "schema_version": "noor-e2e-evidence-index/v2",
        "run_id": run_id,
        "entries": index_entries,
    }
    index_digest = _write_json(tracked_run / "registry/evidence-index.json", index)
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
    if partial_scope:
        criteria = criteria[:1]
    executions = [
        {
            "execution_id": identity,
            "outcome": "PASS",
            "evidence_refs": ["fresh"],
        }
        for identity in registry.compiled_plan.execution_ids
    ]
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
        },
        "tester": {
            "model": "fixture/tester",
            "reasoning_effort": "none",
            "seed": 20260727,
            "config_digest": "3" * 64,
        },
        "judge": {
            "model": "fixture/judge",
            "reasoning_effort": "none",
            "seed": 20260727,
            "config_digest": "4" * 64,
        },
        "turns": [
            {
                "execution_id": "SC-OPEN-EN",
                "attempt_id": "attempt-001",
                "turn_id": "turn-001",
                "question": "Synthetic exact question.",
                "answer": (
                    "Contact +15550001111"
                    if leaked_answer
                    else "Synthetic exact answer."
                ),
                "sent_at": now.isoformat(),
                "received_at": (now + timedelta(seconds=1)).isoformat(),
                "first_visible_at": (now + timedelta(seconds=2)).isoformat(),
                "final_visible_at": (now + timedelta(seconds=3)).isoformat(),
                "delivered_at": (now + timedelta(seconds=4)).isoformat(),
                "conversation_id": "synthetic-conversation",
                "message_id": "synthetic-message",
                "provider_message_id": "synthetic-provider",
                "model": "fixture/model",
                "tools": ["fixture_tool"],
                "tool_outcomes": ["fixture outcome"],
                "audit_ids": ["synthetic-audit"],
                "media_refs": ["media/synthetic.png"],
                "token_count": 10,
                "cost_usd": 0,
                "deviation": None,
                "evaluator_reasoning": "Structured checks passed.",
            }
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
                "checksum_refs": ["fresh"],
            }
        ],
        "latency": {"p50_ms": 1000, "p95_ms": 2000, "max_ms": 3000},
        "limitations": ["Synthetic local dry-run only."],
        "external_gates": ["Live execution is not authorized."],
        "defects": [
            {
                "defect_id": "synthetic-defect",
                "root_cause": "Synthetic root cause.",
                "violated_invariant": "Synthetic invariant.",
                "fix": "Synthetic fix.",
                "retest": "Synthetic retest.",
                "checksum_refs": ["fresh"],
            }
        ],
    }
    report_digest = _write_json(
        tracked_run / "registry/report-payload.json",
        report_payload,
    )
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
        "side_effect_closeout": "passed",
        "evidence_index_digest": index_digest,
        "report_payload_digest": report_digest,
    }
    run_digest = _write_json(tracked_run / "registry/run.json", run_document)
    authorization_digest = trusted.canonical_digest(
        authorization.model_dump(mode="json")
    )
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
        "attempt_chain_heads": {
            identity: "6" * 64 for identity in registry.compiled_plan.execution_ids
        },
    }
    _write_json(protected_run / "registry/anchor.json", anchor)
    return registry, tracked_run, protected_run


def test_registry_loads_real_index_and_calculates_canonical_mode_rollups(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)

    registry._load_verified_run_roots(tracked, protected)

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
        registry._load_verified_run_roots(tracked, protected)


def test_typed_russian_report_and_final_serialized_privacy(
    tmp_path: Path,
) -> None:
    registry, tracked, protected = _build_verified_run(tmp_path)
    registry._load_verified_run_roots(tracked, protected)
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
        leaked_registry._load_verified_run_roots(
            leaked_tracked,
            leaked_protected,
        )
