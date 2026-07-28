from __future__ import annotations

import json
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.e2e_acceptance.evidence import (
    EvidenceError,
    EvidenceStore,
    validate_redacted_payload,
)
from scripts.e2e_acceptance.evidence import (
    validate_side_effect_closeout as _validate_side_effect_closeout,
)

_CLOSEOUT_NOW = datetime(2026, 7, 28, tzinfo=UTC)
_RETENTION_AUTHORITY = {
    "artifact_id": "crm:test-001",
    "cleanup_owner": "acceptance-owner",
    "cleanup_authority": "application-path-only",
    "retention_owner": "client-owner",
    "issued_at": "2026-07-27T00:00:00+00:00",
    "expires_at": "2026-08-27T00:00:00+00:00",
    "authority_digest": "a" * 64,
}


def validate_side_effect_closeout(
    entries,
    *,
    observed_inventory,
    authorized_cleanup_owner="acceptance-owner",
    authorized_cleanup_authority="application-path-only",
    authorized_retentions=None,
    current_time=_CLOSEOUT_NOW,
):
    return _validate_side_effect_closeout(
        entries,
        observed_inventory=observed_inventory,
        authorized_cleanup_owner=authorized_cleanup_owner,
        authorized_cleanup_authority=authorized_cleanup_authority,
        authorized_retentions=(
            {"crm:test-001": _RETENTION_AUTHORITY}
            if authorized_retentions is None
            else authorized_retentions
        ),
        current_time=current_time,
    )


def _store(tmp_path: Path) -> EvidenceStore:
    repo = tmp_path / "repo"
    repo.mkdir()
    protected = tmp_path / "protected"
    return EvidenceStore(repo_root=repo, protected_root=protected)


def test_raw_evidence_is_outside_git_private_and_checksummed(tmp_path: Path) -> None:
    store = _store(tmp_path)

    record = store.write_raw_json(
        "run-20260727-001",
        "turns/turn-001.json",
        {"phone": "+15550001111", "authorization": "Bearer private-token"},
    )

    assert not record.path.is_relative_to(store.repo_root)
    assert stat.S_IMODE(record.path.stat().st_mode) == 0o600
    assert record.sha256 == store.sha256_file(record.path)


def test_protected_root_inside_repository_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(EvidenceError, match="outside"):
        EvidenceStore(repo_root=repo, protected_root=repo / ".raw")


def test_protected_root_symlink_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    actual = tmp_path / "actual-protected"
    actual.mkdir()
    alias = tmp_path / "protected-alias"
    alias.symlink_to(actual, target_is_directory=True)

    with pytest.raises(EvidenceError, match="symlink"):
        EvidenceStore(repo_root=repo, protected_root=alias)


def test_redacted_evidence_removes_recursive_sensitive_material(tmp_path: Path) -> None:
    store = _store(tmp_path)
    payload = {
        "question": "Call +1 (555) 010.42.42",
        "nested": {
            "api_key": "top-secret",
            "private_manager": {"name": "Victor", "mobile": "89991234567"},
            "production_logs": ["unbounded raw log line"],
        },
        "safe": "Synthetic customer asks about a chair.",
    }

    record = store.write_redacted_json(
        "run-20260727-001", "turns/turn-001.json", payload
    )
    saved = json.loads(record.path.read_text(encoding="utf-8"))

    assert record.path.is_relative_to(store.repo_root)
    assert saved["question"] == "Call [REDACTED_PHONE]"
    assert saved["nested"]["api_key"] == "[REDACTED_SECRET]"
    assert saved["nested"]["private_manager"] == "[REDACTED_MANAGER_DATA]"
    assert saved["nested"]["production_logs"] == "[REDACTED_UNRESTRICTED_LOG]"
    validate_redacted_payload(saved)


@pytest.mark.parametrize(
    "payload,pattern",
    [
        ({"text": "token=abc123"}, "credential"),
        ({"text": "phone +15550001111"}, "phone"),
        ({"private_manager": {"name": "Real Person"}}, "manager"),
        ({"openrouter_api_key": "secret-value"}, "credential"),
        ({"manager_phone": "+15550001111"}, "manager"),
        ({"raw_logs": ["everything"]}, "log"),
    ],
)
def test_redaction_validator_rejects_forbidden_material(
    payload: dict[str, object], pattern: str
) -> None:
    with pytest.raises(EvidenceError, match=pattern):
        validate_redacted_payload(payload)


def test_attempts_are_append_only_and_cannot_be_rewritten(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = {
        "attempt_id": "attempt-001",
        "scenario_id": "SCN-OPENING-EN",
        "attempt_number": 1,
        "status": "failed",
        "previous_attempt_sha256": None,
    }
    store.append_attempt("run-20260727-001", first)

    with pytest.raises(EvidenceError, match="append-only"):
        store.append_attempt("run-20260727-001", first)

    with pytest.raises(EvidenceError, match="next attempt"):
        store.append_attempt(
            "run-20260727-001",
            {
                "attempt_id": "attempt-003",
                "scenario_id": "SCN-OPENING-EN",
                "attempt_number": 3,
                "status": "passed",
            },
        )


def test_manual_attempt_rewrite_breaks_integrity_chain_before_append(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    first = {
        "attempt_id": "attempt-001",
        "scenario_id": "SCN-OPENING-EN",
        "attempt_number": 1,
        "status": "failed",
        "previous_attempt_sha256": None,
    }
    first_record = store.append_attempt("run-20260727-001", first)
    original_digest = first_record.sha256
    rewritten = json.loads(first_record.path.read_text(encoding="utf-8"))
    rewritten["status"] = "passed"
    first_record.path.write_text(json.dumps(rewritten), encoding="utf-8")

    with pytest.raises(EvidenceError, match="integrity"):
        store.append_attempt(
            "run-20260727-001",
            {
                "attempt_id": "attempt-002",
                "scenario_id": "SCN-OPENING-EN",
                "attempt_number": 2,
                "status": "passed",
                "previous_attempt_sha256": original_digest,
                "retest_of": "attempt-001",
                "defect_id": "tj-synthetic-defect",
                "fix_commit": "a" * 40,
                "deployment_identity": "b" * 40,
            },
        )


def test_forged_tracked_attempt_and_sidecar_cannot_bypass_protected_anchor(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    first = {
        "attempt_id": "attempt-001",
        "scenario_id": "SCN-OPENING-EN",
        "attempt_number": 1,
        "status": "failed",
        "previous_attempt_sha256": None,
    }
    first_record = store.append_attempt("run-20260727-001", first)
    rewritten = json.loads(first_record.path.read_text(encoding="utf-8"))
    rewritten["status"] = "passed"
    first_record.path.write_text(
        json.dumps(rewritten, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    forged_digest = store.sha256_file(first_record.path)
    sidecar = (
        store.tracked_root
        / "run-20260727-001/integrity/SCN-OPENING-EN/attempt-001.sha256"
    )
    sidecar.write_text(f"{forged_digest}\n", encoding="ascii")

    with pytest.raises(EvidenceError, match="protected anchor"):
        store.append_attempt(
            "run-20260727-001",
            {
                "attempt_id": "attempt-002",
                "scenario_id": "SCN-OPENING-EN",
                "attempt_number": 2,
                "status": "passed",
                "previous_attempt_sha256": forged_digest,
            },
        )


def test_redacted_and_raw_checksums_are_both_auditable(tmp_path: Path) -> None:
    store = _store(tmp_path)
    raw = store.write_raw_json(
        "run-20260727-001", "turn.json", {"phone": "79991234567"}
    )
    redacted = store.write_redacted_json(
        "run-20260727-001", "turn.json", {"phone": "79991234567"}
    )

    manifest = store.build_retention_manifest(
        "run-20260727-001",
        raw_records=[raw],
        redacted_records=[redacted],
        owner="acceptance-owner",
        created_at="2026-07-27T00:00:00Z",
        expires_at="2026-08-27T00:00:00Z",
    )

    assert manifest["redaction_validation"] == "passed"
    assert manifest["created_at"] == "2026-07-27T00:00:00Z"
    assert manifest["raw_records"][0]["sha256"] == raw.sha256
    assert manifest["redacted_records"][0]["sha256"] == redacted.sha256
    assert "+1555" not in json.dumps(manifest)


def test_retention_manifest_rejects_tampered_redacted_record(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    redacted = store.write_redacted_json(
        "run-20260727-001",
        "turn.json",
        {"safe": "synthetic evidence"},
    )
    redacted.path.write_text('{"safe":"changed after write"}\n', encoding="utf-8")

    with pytest.raises(EvidenceError, match="integrity"):
        store.build_retention_manifest(
            "run-20260727-001",
            raw_records=[],
            redacted_records=[redacted],
            owner="acceptance-owner",
            created_at="2026-07-27T00:00:00Z",
            expires_at="2026-08-27T00:00:00Z",
        )


def test_evidence_write_rejects_symlinked_intermediate_directory(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    run_root = store.tracked_root / "run-20260727-001"
    run_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (run_root / "turns").symlink_to(outside, target_is_directory=True)

    with pytest.raises(EvidenceError, match="securely create|unsafe"):
        store.write_redacted_json(
            "run-20260727-001",
            "turns/turn-001.json",
            {"safe": "synthetic evidence"},
        )

    assert not (outside / "turn-001.json").exists()


@pytest.mark.parametrize(
    "disposition",
    ["cleanup_pending", "cleanup_blocked", "unknown"],
)
def test_nonterminal_side_effect_disposition_blocks_closeout(
    disposition: str,
) -> None:
    ledger = [
        {
            "artifact_id": "crm:test-001",
            "scenario_id": "SCN-CRM",
            "subsystem": "crm",
            "artifact_type": "crm_deal",
            "creation_path": "fixture",
            "cleanup_owner": "acceptance-owner",
            "cleanup_authority": "application-path-only",
            "baseline_readback": {"state": "absent"},
            "expected_effect": {"state": "created_for_test"},
            "follow_up_suppressed": True,
            "final_readback": {"state": "test"},
            "disposition": disposition,
        }
    ]

    with pytest.raises(EvidenceError, match="nonterminal"):
        validate_side_effect_closeout(
            ledger,
            observed_inventory={"crm:test-001": {"state": "test"}},
        )


def test_retained_side_effect_requires_preapproval_owner_expiry_and_readback() -> None:
    ledger = [
        {
            "artifact_id": "crm:test-001",
            "scenario_id": "SCN-CRM",
            "subsystem": "crm",
            "artifact_type": "crm_deal",
            "creation_path": "fixture",
            "cleanup_owner": "acceptance-owner",
            "cleanup_authority": "application-path-only",
            "baseline_readback": {"state": "absent"},
            "expected_effect": {"state": "created_for_test"},
            "follow_up_suppressed": True,
            "final_readback": {"state": "retained"},
            "disposition": "retained_as_test_evidence",
            "retention_pre_authorized": True,
            "retention_owner": "client-owner",
            "retention_authority_digest": "a" * 64,
            "retention_expires_at": "2026-08-27T00:00:00Z",
            "final_disposition_date": "2026-07-27T00:00:00Z",
        }
    ]

    validate_side_effect_closeout(
        ledger,
        observed_inventory={"crm:test-001": {"state": "retained"}},
    )

    missing_expiry = [{**ledger[0], "retention_expires_at": None}]
    with pytest.raises(EvidenceError, match="retention"):
        validate_side_effect_closeout(
            missing_expiry,
            observed_inventory={"crm:test-001": {"state": "retained"}},
        )

    expired = {
        **ledger[0],
        "retention_expires_at": "2026-07-27T12:00:00Z",
        "final_disposition_date": "2026-07-27T00:00:00Z",
    }
    expired_authority = {
        **_RETENTION_AUTHORITY,
        "expires_at": "2026-07-27T12:00:00+00:00",
    }
    with pytest.raises(EvidenceError, match="retention.*time|retention.*authority"):
        validate_side_effect_closeout(
            [expired],
            observed_inventory={"crm:test-001": {"state": "retained"}},
            authorized_retentions={"crm:test-001": expired_authority},
        )


def test_retention_rejects_garbage_expiry_and_untrusted_owner() -> None:
    entry = {
        "artifact_id": "crm:test-001",
        "scenario_id": "SCN-CRM",
        "subsystem": "crm",
        "artifact_type": "crm_deal",
        "creation_path": "fixture",
        "cleanup_owner": "acceptance-owner",
        "cleanup_authority": "application-path-only",
        "baseline_readback": {"state": "absent"},
        "expected_effect": {"state": "created_for_test"},
        "follow_up_suppressed": True,
        "final_readback": {"state": "retained"},
        "disposition": "retained_as_test_evidence",
        "retention_pre_authorized": True,
        "retention_owner": "caller-invented-owner",
        "retention_expires_at": "not-a-time",
        "final_disposition_date": "also-not-a-time",
    }

    with pytest.raises(EvidenceError, match="retention.*time|retention.*owner"):
        validate_side_effect_closeout(
            [entry],
            observed_inventory={"crm:test-001": {"state": "retained"}},
        )


def test_retention_rejects_arbitrary_owner_with_valid_aware_times() -> None:
    now = datetime.now(UTC)
    entry = {
        "artifact_id": "crm:test-001",
        "scenario_id": "SCN-CRM",
        "subsystem": "crm",
        "artifact_type": "crm_deal",
        "creation_path": "fixture",
        "cleanup_owner": "caller-invented-owner",
        "cleanup_authority": "caller-invented-authority",
        "baseline_readback": {"state": "absent"},
        "expected_effect": {"state": "created_for_test"},
        "follow_up_suppressed": True,
        "final_readback": {"state": "retained"},
        "disposition": "retained_as_test_evidence",
        "retention_pre_authorized": True,
        "retention_owner": "caller-invented-owner",
        "retention_authority_digest": "a" * 64,
        "retention_expires_at": (now + timedelta(days=1)).isoformat(),
        "final_disposition_date": now.isoformat(),
    }

    with pytest.raises(EvidenceError, match="cleanup.*authority|retention.*authority"):
        validate_side_effect_closeout(
            [entry],
            observed_inventory={"crm:test-001": {"state": "retained"}},
            authorized_cleanup_owner="acceptance-owner",
            authorized_cleanup_authority="application-path-only",
            authorized_retentions={},
            current_time=now,
        )


def test_missing_readback_and_unlisted_artifact_block_closeout() -> None:
    ledger = [
        {
            "artifact_id": "local:test-001",
            "scenario_id": "SCN-OPENING-EN",
            "subsystem": "conversation",
            "artifact_type": "conversation",
            "creation_path": "fixture",
            "cleanup_owner": "acceptance-owner",
            "cleanup_authority": "application-path-only",
            "baseline_readback": {"state": "absent"},
            "expected_effect": {"state": "created_for_test"},
            "follow_up_suppressed": True,
            "final_readback": None,
            "disposition": "closed",
        }
    ]
    with pytest.raises(EvidenceError, match="readback"):
        validate_side_effect_closeout(
            ledger,
            observed_inventory={"local:test-001": {"state": "closed"}},
        )

    ledger[0]["final_readback"] = {"state": "closed"}
    with pytest.raises(EvidenceError, match="unlisted"):
        validate_side_effect_closeout(
            ledger,
            observed_inventory={
                "local:test-001": {"state": "closed"},
                "crm:unlisted-002": {"state": "active"},
            },
        )


def test_missing_baseline_or_expected_effect_blocks_closeout() -> None:
    entry = {
        "artifact_id": "local:test-001",
        "scenario_id": "SCN-OPENING-EN",
        "subsystem": "conversation",
        "artifact_type": "conversation",
        "creation_path": "fixture",
        "cleanup_owner": "acceptance-owner",
        "cleanup_authority": "application-path-only",
        "baseline_readback": None,
        "expected_effect": {"state": "created_for_test"},
        "follow_up_suppressed": True,
        "final_readback": {"state": "closed"},
        "disposition": "closed",
    }
    with pytest.raises(EvidenceError, match="baseline"):
        validate_side_effect_closeout(
            [entry],
            observed_inventory={"local:test-001": {"state": "closed"}},
        )


def test_side_effect_disposition_must_match_typed_final_state() -> None:
    entry = {
        "artifact_id": "local:test-001",
        "scenario_id": "SCN-OPENING-EN",
        "subsystem": "conversation",
        "artifact_type": "conversation",
        "creation_path": "fixture",
        "cleanup_owner": "acceptance-owner",
        "cleanup_authority": "application-path-only",
        "baseline_readback": {"state": "absent"},
        "expected_effect": {"state": "created_for_test"},
        "follow_up_suppressed": True,
        "final_readback": {"state": "active"},
        "disposition": "closed",
    }

    with pytest.raises(EvidenceError, match="terminal invariant"):
        validate_side_effect_closeout(
            [entry],
            observed_inventory={"local:test-001": {"state": "active"}},
        )


def test_side_effect_observed_inventory_must_match_final_readback() -> None:
    entry = {
        "artifact_id": "local:test-001",
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

    with pytest.raises(EvidenceError, match="observed inventory"):
        validate_side_effect_closeout(
            [entry],
            observed_inventory={"local:test-001": {"state": "active"}},
        )


def test_redaction_closes_alias_camelcase_and_dotted_phone_bypasses(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    payload = {
        "authToken": "credential-value",
        "fullLogs": ["unbounded line"],
        "contact": "synthetic +155.500.011.11",
    }

    record = store.write_redacted_json("run-20260727-001", "alias.json", payload)
    serialized = record.path.read_text(encoding="utf-8")
    saved = json.loads(serialized)

    assert saved["authToken"] == "[REDACTED_SECRET]"
    assert saved["fullLogs"] == "[REDACTED_UNRESTRICTED_LOG]"
    assert saved["contact"] == "synthetic [REDACTED_PHONE]"
    assert "credential-value" not in serialized
    assert "155.500" not in serialized


@pytest.mark.parametrize("alias", ["managerMobile", "manager_mobile"])
def test_redaction_closes_manager_mobile_aliases(
    tmp_path: Path,
    alias: str,
) -> None:
    store = _store(tmp_path)

    record = store.write_redacted_json(
        "run-20260727-001",
        f"{alias}.json",
        {alias: "synthetic private manager contact"},
    )
    saved = json.loads(record.path.read_text(encoding="utf-8"))

    assert saved[alias] == "[REDACTED_MANAGER_DATA]"
