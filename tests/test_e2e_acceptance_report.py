from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from scripts.e2e_acceptance.manifest import load_traceability_manifest
from scripts.e2e_acceptance.report import (
    ReportError,
    build_defect_draft,
    calculate_rollups,
    render_client_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRACEABILITY_PATH = PROJECT_ROOT / ".codex/stages/tj-ee5f/traceability-manifest.json"


def _results() -> dict[str, object]:
    return {
        "run_id": "run-20260727-001",
        "runtime_identity": {
            "repository_commit": "a" * 40,
            "deployed_release_sha": "deadbeef",
            "ci_run_id": "fixture-ci-run",
            "endpoint": "https://example.invalid",
            "app_version": "0.4.0",
            "migration_head": "fixture-migration-head",
            "main_model": "fixture/main",
            "fast_model": "fixture/fast",
        },
        "latency_summary": {
            "p50_seconds": 1.0,
            "p95_seconds": 2.5,
            "maximum_seconds": 3.0,
        },
        "limitations": ["Synthetic dry-run evidence only."],
        "external_gates": [
            {
                "criterion_id": "AC-21",
                "status": "blocked",
                "reason": "Client decision is pending.",
            }
        ],
        "criteria": [
            {
                "criterion_id": "AC-01",
                "outcome": "PASS",
                "evidence_mode": "fresh",
                "evidence_refs": ["attempts/SCN-OPENING-EN/attempt-001.json"],
                "authorized": True,
                "authorization_binding_verified": True,
                "freshness_verified": True,
            },
            {
                "criterion_id": "AC-21",
                "outcome": "BLOCKED",
                "evidence_mode": "external_gate",
                "evidence_refs": [],
                "authorized": False,
            },
        ],
        "scope_criterion_ids": ["AC-01", "AC-21"],
        "executions": [
            {
                "execution_id": "SCN-OPENING-EN",
                "authorized": True,
                "outcome": "PASS",
            },
            {
                "execution_id": "EB-REFERRAL",
                "authorized": False,
                "outcome": "BLOCKED",
            },
        ],
        "planned_execution_ids": ["SCN-OPENING-EN", "EB-REFERRAL"],
        "authorization_evidence_ref": "authorization/preflight.json",
        "run_identity_evidence_ref": "runtime/run-identity.json",
        "scenarios": [
            {
                "scenario_id": "SCN-OPENING-EN",
                "status": "fixed_and_retested",
                "turns": [
                    {
                        "customer_text": "Hello, I need a chair.",
                        "assistant_text": "Hello! I am Noor from Treejar.",
                        "original_language": "en",
                        "translation": None,
                        "turn_id": "turn-001",
                        "planned_turn_id": "turn-001",
                        "conversation_id": "fixture-conversation",
                        "message_id": "fixture-message",
                        "provider_message_id": "fixture-provider-message",
                        "sent_at": "2026-07-27T10:00:00Z",
                        "received_at": "2026-07-27T10:00:01Z",
                        "first_visible_at": "2026-07-27T10:00:01Z",
                        "final_visible_at": "2026-07-27T10:00:02Z",
                        "delivered_at": "2026-07-27T10:00:03Z",
                        "first_visible_seconds": 1.0,
                        "final_text_seconds": 2.0,
                        "model": "fixture/main",
                        "routing_suffix": "fixture-route",
                        "tools": ["fixture_tool"],
                        "tool_outcomes": ["success"],
                        "media_refs": ["media/synthetic-chair.png"],
                        "audit_ids": ["fixture-audit"],
                        "token_count": 42,
                        "cost_usd": 0.001,
                        "expected_behavior": "Noor introduces itself.",
                        "actual_observation": "Noor introduced itself.",
                        "deterministic_check_ids": ["introduction"],
                    }
                ],
                "adaptive_deviations": [
                    {
                        "planned_turn_id": "turn-001",
                        "actual_turn_id": "turn-001",
                        "reason": "No deviation.",
                    }
                ],
                "tester": {
                    "model": "fixture/tester",
                    "reasoning_effort": "deterministic",
                    "seed": 20260727,
                    "prompt_digest": "c" * 64,
                },
                "judge": {
                    "model": "fixture/judge",
                    "reasoning_effort": "deterministic",
                    "rubric_digest": "d" * 64,
                    "reasoning": "Authorized checkpoints passed.",
                },
                "evaluation": {
                    "hard_failure": False,
                    "failure_reasons": [],
                    "judge_reasoning": "Authorized checkpoints passed.",
                },
                "evidence_refs": ["attempts/SCN-OPENING-EN/attempt-001.json"],
                "expected": "Noor introduces itself.",
                "actual": "Noor introduced itself.",
                "initial_failure_ref": "attempt-001",
                "defect_id": "tj-example",
                "fix_commit": "abc1234",
                "retest_ref": "attempt-002",
            }
        ],
        "defects": [
            {
                "defect_id": "tj-example",
                "severity": "P2",
                "summary": "Opening lacked identity.",
                "root_cause": "The opener omitted the configured identity.",
                "invariant_test": "test_opening_identity_is_required",
                "fix": "Added identity guard.",
                "fix_commit": "f" * 40,
                "deployed_release": "d" * 40,
                "retest": "attempt-002 passed.",
                "initial_failure_ref": "attempt-001",
                "retest_ref": "attempt-002",
            }
        ],
        "side_effect_closeout": "passed",
        "side_effects": [
            {
                "artifact_id": "local:conversation",
                "scenario_id": "SCN-OPENING-EN",
                "subsystem": "conversation",
                "artifact_type": "conversation",
                "creation_path": "fixture",
                "cleanup_owner": "acceptance-owner",
                "cleanup_authority": "application-path-only",
                "baseline_readback": {"state": "absent"},
                "expected_effect": {"state": "created_for_test"},
                "follow_up_suppressed": True,
                "final_readback": {"state": "closed"},
                "disposition": "closed",
            }
        ],
        "evidence_checksums": [
            {
                "relative_path": "attempts/SCN-OPENING-EN/attempt-001.json",
                "sha256": "e" * 64,
            }
        ],
        "open_p0_p1": [],
    }


def _evidence_contract(tmp_path: Path) -> dict[str, object]:
    evidence_root = tmp_path / "evidence"
    evidence_payloads = {
        "attempts/SCN-OPENING-EN/attempt-001.json": {
            "schema_version": "noor-e2e-scenario-attempt/v1",
            "scenario_id": "SCN-OPENING-EN",
            "status": "passed",
            "freshness_identity": {
                "repository_commit": "a" * 40,
                "deployed_release_sha": "b" * 40,
            },
        },
        "runtime/run-identity.json": {
            "status": "passed",
            "expected_equals_actual": True,
        },
        "authorization/preflight.json": {
            "status": "passed",
            "manifest_digest": "a" * 64,
            "scenario_binding_digest": "b" * 64,
            "authorized_execution_ids": ["SCN-OPENING-EN"],
        },
    }
    entries = []
    for relative_path, payload in evidence_payloads.items():
        path = evidence_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = (
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        )
        path.write_text(serialized, encoding="utf-8")
        entries.append(
            {
                "relative_path": relative_path,
                "sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            }
        )
    (evidence_root / "evidence-index.json").write_text(
        json.dumps(
            {
                "schema_version": "noor-e2e-evidence-index/v1",
                "entries": entries,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "evidence_root": evidence_root,
        "traceability": load_traceability_manifest(TRACEABILITY_PATH),
    }


def test_rollups_keep_external_gate_independent_from_coverage(
    tmp_path: Path,
) -> None:
    rollups = calculate_rollups(_results(), **_evidence_contract(tmp_path))

    assert rollups == {
        "coverage_complete": True,
        "execution_complete": True,
        "requirements_met": False,
    }


def test_rollups_detect_missing_scope_or_planned_execution(tmp_path: Path) -> None:
    results = _results()
    criteria = results["criteria"]
    assert isinstance(criteria, list)
    criteria.pop()
    executions = results["executions"]
    assert isinstance(executions, list)
    executions.pop()

    assert calculate_rollups(results, **_evidence_contract(tmp_path)) == {
        "coverage_complete": False,
        "execution_complete": False,
        "requirements_met": False,
    }


def test_requirements_met_rejects_pass_without_verified_evidence_or_run_proof(
    tmp_path: Path,
) -> None:
    results = _results()
    criteria = results["criteria"]
    assert isinstance(criteria, list)
    criteria.pop()
    results["scope_criterion_ids"] = ["AC-01"]
    executions = results["executions"]
    assert isinstance(executions, list)
    executions.pop()
    results["planned_execution_ids"] = ["SCN-OPENING-EN"]

    criterion = criteria[0]
    assert isinstance(criterion, dict)
    criterion["evidence_refs"] = []
    contract = _evidence_contract(tmp_path)
    assert calculate_rollups(results, **contract)["requirements_met"] is False

    criterion["evidence_refs"] = ["attempts/SCN-OPENING-EN/attempt-001.json"]
    results["authorization_evidence_ref"] = "missing.json"
    assert calculate_rollups(results, **contract)["requirements_met"] is False


def test_requirements_met_resolves_actual_index_checksums_and_task1_modes(
    tmp_path: Path,
) -> None:
    results = _results()
    criteria = results["criteria"]
    executions = results["executions"]
    assert isinstance(criteria, list)
    assert isinstance(executions, list)
    criteria.pop()
    executions.pop()
    results["scope_criterion_ids"] = ["AC-01"]
    results["planned_execution_ids"] = ["SCN-OPENING-EN"]
    results["open_p0_p1"] = []

    contract = _evidence_contract(tmp_path)
    assert calculate_rollups(results, **contract)["requirements_met"] is True

    criterion = criteria[0]
    assert isinstance(criterion, dict)
    criterion["evidence_mode"] = "reused_exact"
    assert calculate_rollups(results, **contract)["requirements_met"] is False
    criterion["evidence_mode"] = "fresh"

    attempt = tmp_path / "evidence/attempts/SCN-OPENING-EN/attempt-001.json"
    attempt.write_text('{"status":"forged"}\n', encoding="utf-8")
    with pytest.raises(ReportError, match="integrity"):
        calculate_rollups(results, **contract)


def test_russian_report_contains_exact_qa_failure_fix_and_retest(
    tmp_path: Path,
) -> None:
    output = tmp_path / "report.md"

    render_client_report(_results(), output, **_evidence_contract(tmp_path))
    report = output.read_text(encoding="utf-8")

    assert "# Приёмочное тестирование Noor" in report
    assert "Hello, I need a chair." in report
    assert "Hello! I am Noor from Treejar." in report
    assert "attempt-001" in report
    assert "Added identity guard." in report
    assert "The opener omitted the configured identity." in report
    assert "test_opening_identity_is_required" in report
    assert "attempt-002 passed." in report
    assert "coverage_complete: да" in report
    assert "requirements_met: нет" in report
    assert "fixture-conversation" in report
    assert "fixture-provider-message" in report
    assert "fixture-ci-run" in report
    assert "fixture-migration-head" in report
    assert "2026-07-27T10:00:03Z" in report
    assert "fixture_tool" in report
    assert "media/synthetic-chair.png" in report
    assert "p95" in report
    assert "Synthetic dry-run evidence only." in report
    assert "Client decision is pending." in report
    assert "42" in report
    assert "0.001" in report
    assert "Authorized checkpoints passed." in report
    assert "local:conversation" in report
    assert "SCN-OPENING-EN" in report
    assert "created_for_test" in report
    assert "acceptance-owner" in report
    assert "application-path-only" in report
    assert "follow-up suppressed `True`" in report
    assert "eeeeeeee" in report
    assert "AC-01" in report


def test_report_rejects_phone_secret_private_manager_and_raw_logs(
    tmp_path: Path,
) -> None:
    results = _results()
    scenarios = results["scenarios"]
    assert isinstance(scenarios, list)
    scenarios[0]["turns"][0]["customer_text"] = "My phone is +15550001111"

    with pytest.raises(ReportError, match="phone"):
        render_client_report(
            results,
            tmp_path / "report.md",
            **_evidence_contract(tmp_path),
        )


def test_report_refuses_existing_or_symlink_output(tmp_path: Path) -> None:
    existing = tmp_path / "report.md"
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(ReportError, match="already exists"):
        render_client_report(
            _results(),
            existing,
            **_evidence_contract(tmp_path),
        )
    assert existing.read_text(encoding="utf-8") == "keep"

    target = tmp_path / "target.md"
    target.write_text("keep target", encoding="utf-8")
    alias = tmp_path / "alias.md"
    alias.symlink_to(target)
    with pytest.raises(ReportError, match="symlink|already exists"):
        render_client_report(
            _results(),
            alias,
            **_evidence_contract(tmp_path),
        )
    assert target.read_text(encoding="utf-8") == "keep target"


def test_defect_draft_preserves_reproduction_and_evidence_link() -> None:
    draft = build_defect_draft(
        scenario_id="SCN-STOCK",
        severity="P1",
        summary="Unsupported stock promise",
        expected="Stock remains unconfirmed without a tool result.",
        actual="The reply promised availability.",
        evidence_path="attempts/SCN-STOCK/attempt-001.json",
        criterion_ids=["AC-07"],
        historical_regressions=["tj-r1f3"],
    )

    assert draft["parent"] == "tj-ee5f"
    assert draft["discovered_from"] == "tj-ee5f.1"
    assert draft["minimal_reproduction"]["scenario_id"] == "SCN-STOCK"
    assert draft["evidence_path"].endswith("attempt-001.json")
    assert draft["acceptance_criteria"] == ["AC-07"]
