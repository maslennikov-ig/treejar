from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from scripts.e2e_acceptance.manifest import (
    ManifestValidationError,
    load_authorization_manifest,
    load_scenario_set,
    load_scope_snapshot,
    load_traceability_manifest,
    validate_contract_bundle,
    validate_preflight,
    validate_scope_anchor_immutable,
    validate_source_digests,
)
from scripts.e2e_acceptance.schemas import (
    AuthorizationManifest,
    AuthorizationStatus,
    CriterionResult,
    EvidenceMode,
    Outcome,
    PreflightObservation,
    PreflightRequest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE_ROOT = REPO_ROOT / ".codex" / "stages" / "tj-ee5f"
SCOPE_PATH = (
    REPO_ROOT / ".codex" / "goals" / "tj-ee5f" / "scope-criterion-snapshot.json"
)
TRACEABILITY_PATH = STAGE_ROOT / "traceability-manifest.json"
SCENARIO_SET_PATH = STAGE_ROOT / "scenario-set.json"
AUTHORIZATION_PATH = STAGE_ROOT / "authorization-manifest.example.json"


def test_outcome_and_evidence_mode_are_independent_axes() -> None:
    blocked_fresh = CriterionResult(
        criterion_id="AC-01",
        outcome=Outcome.BLOCKED,
        evidence_mode=EvidenceMode.FRESH,
        evidence_refs=[],
    )
    passed_external_gate = CriterionResult(
        criterion_id="AC-02",
        outcome=Outcome.PASS,
        evidence_mode=EvidenceMode.EXTERNAL_GATE,
        evidence_refs=["results/run-1/gate.json"],
    )

    assert blocked_fresh.outcome is Outcome.BLOCKED
    assert blocked_fresh.evidence_mode is EvidenceMode.FRESH
    assert passed_external_gate.outcome is Outcome.PASS
    assert passed_external_gate.evidence_mode is EvidenceMode.EXTERNAL_GATE
    assert {item.value for item in Outcome} == {
        "PASS",
        "FAIL",
        "BLOCKED",
        "EXCLUDED_BY_CLIENT",
    }
    assert {item.value for item in EvidenceMode} == {
        "fresh",
        "reused_exact",
        "external_gate",
    }


def test_scope_snapshot_is_pure_and_matches_immutable_creation_blob() -> None:
    snapshot = load_scope_snapshot(SCOPE_PATH)

    assert snapshot.schema_version == "scope-criterion-snapshot/v1"
    assert len(snapshot.criteria) == 30
    assert all(item.text_digest for item in snapshot.criteria)
    assert validate_scope_anchor_immutable(REPO_ROOT, SCOPE_PATH) is None

    raw = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
    assert set(raw) == {
        "schema_version",
        "goal_id",
        "source_kind",
        "source_id",
        "source_digest",
        "criteria",
    }
    assert all(
        set(item) == {"criterion_id", "text", "text_digest"} for item in raw["criteria"]
    )


def test_scope_snapshot_schema_rejects_mutable_traceability_state(
    tmp_path: Path,
) -> None:
    raw = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
    raw["criteria"][0]["owner"] = "scenario-owner"
    drifted = tmp_path / "scope.json"
    drifted.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="scope criterion"):
        load_scope_snapshot(drifted)


def test_traceability_covers_every_scope_criterion_with_owner_and_oracle() -> None:
    snapshot = load_scope_snapshot(SCOPE_PATH)
    traceability = load_traceability_manifest(TRACEABILITY_PATH)
    scenario_set = load_scenario_set(SCENARIO_SET_PATH)

    validate_contract_bundle(snapshot, traceability, scenario_set)

    assert {item.criterion_id for item in traceability.criteria} == {
        item.criterion_id for item in snapshot.criteria
    }
    assert all(item.owner and item.oracle.checks for item in traceability.criteria)
    assert all(item.sources for item in traceability.criteria)


def test_traceability_and_scenario_links_must_be_reciprocal() -> None:
    snapshot = load_scope_snapshot(SCOPE_PATH)
    traceability = load_traceability_manifest(TRACEABILITY_PATH)
    scenario_set = load_scenario_set(SCENARIO_SET_PATH)
    scenarios = list(scenario_set.scenarios)
    scenarios[0] = scenarios[0].model_copy(
        update={
            "criterion_ids": [
                item for item in scenarios[0].criterion_ids if item != "AC-01"
            ]
        }
    )
    drifted = scenario_set.model_copy(update={"scenarios": scenarios})

    with pytest.raises(ManifestValidationError, match="owner mismatch"):
        validate_contract_bundle(snapshot, traceability, drifted)


def test_traceability_source_digests_match_repository_content() -> None:
    traceability = load_traceability_manifest(TRACEABILITY_PATH)

    validate_source_digests(traceability, REPO_ROOT)

    registry = dict(traceability.source_registry)
    registry["project-tz"] = registry["project-tz"].model_copy(
        update={"content_digest": "0" * 64}
    )
    drifted = traceability.model_copy(update={"source_registry": registry})
    with pytest.raises(
        ManifestValidationError, match="project-tz content digest drift"
    ):
        validate_source_digests(drifted, REPO_ROOT)


def test_open_grounding_dependency_is_a_non_passing_external_gate() -> None:
    traceability = load_traceability_manifest(TRACEABILITY_PATH)
    grounding_gate = next(
        item for item in traceability.criteria if item.criterion_id == "AC-30"
    )

    assert grounding_gate.evidence_mode is EvidenceMode.EXTERNAL_GATE
    assert grounding_gate.dependency is not None
    assert grounding_gate.dependency.issue_id == "tj-r1f3"
    assert grounding_gate.dependency.status == "in_progress"
    assert grounding_gate.dependency.required_outcome is Outcome.PASS
    assert grounding_gate.precedence.disposition == "hard_dependency_non_pass"


def test_grounding_dependency_has_a_versioned_closed_freshness_transition() -> None:
    snapshot = load_scope_snapshot(SCOPE_PATH)
    traceability = load_traceability_manifest(TRACEABILITY_PATH)
    scenario_set = load_scenario_set(SCENARIO_SET_PATH)
    criteria = []
    for criterion in traceability.criteria:
        if criterion.criterion_id not in {"AC-07", "AC-30"}:
            criteria.append(criterion)
            continue
        assert criterion.dependency is not None
        criteria.append(
            criterion.model_copy(
                update={
                    "dependency": criterion.dependency.model_copy(
                        update={"status": "closed"}
                    ),
                    "open_known_risks": [
                        risk for risk in criterion.open_known_risks if risk != "tj-r1f3"
                    ],
                    "precedence": criterion.precedence.model_copy(
                        update={"disposition": "dependency_closed_freshness_required"}
                    ),
                }
            )
        )
    transitioned = traceability.model_copy(update={"criteria": criteria})

    validate_contract_bundle(snapshot, transitioned, scenario_set)


def test_scenario_set_has_isolated_languages_variants_journey_and_blocks() -> None:
    scenario_set = load_scenario_set(SCENARIO_SET_PATH)

    isolated_languages = {
        scenario.language
        for scenario in scenario_set.scenarios
        if scenario.kind == "isolated_customer"
    }
    variants = {
        scenario.variant_family
        for scenario in scenario_set.scenarios
        if scenario.kind == "high_risk_paraphrase"
    }
    block_kinds = {block.kind for block in scenario_set.evidence_blocks}

    assert isolated_languages >= {"en", "ar"}
    assert variants >= {
        "grounding",
        "name_gate",
        "quotation",
        "manager_handoff",
        "media",
    }
    assert (
        sum(
            scenario.kind == "longitudinal_customer"
            for scenario in scenario_set.scenarios
        )
        == 1
    )
    assert block_kinds >= {"admin", "load", "security", "backup"}
    assert all(scenario.stop_conditions for scenario in scenario_set.scenarios)
    assert all(scenario.report_owner for scenario in scenario_set.scenarios)


def _approved_authorization() -> AuthorizationManifest:
    draft = load_authorization_manifest(AUTHORIZATION_PATH)
    return draft.model_copy(
        update={
            "authorization_id": "auth-local-contract-test",
            "status": AuthorizationStatus.APPROVED,
            "issuer": "test-authorizer",
            "expires_at": draft.issued_at + timedelta(hours=1),
            "allowed_executor": "test-executor",
            "allowed_source": "local-contract-test",
            "expected_identity": draft.expected_identity.model_copy(
                update={
                    "repository_commit": "a" * 40,
                    "deployed_release_sha": "b" * 40,
                    "ci_run_id": "123456",
                    "app_version": "0.4.0",
                    "migration_head": "test-migration-head",
                    "main_model": "test/main-model",
                    "fast_model": "test/fast-model",
                }
            ),
            "targets": draft.targets.model_copy(
                update={
                    "recipient": "synthetic-recipient",
                    "wazzup_channel": "synthetic-channel",
                    "telegram_target": "synthetic-telegram",
                    "synthetic_suffix": "test-run-suffix",
                }
            ),
            "test_data_identities": ["synthetic-identity-set"],
            "cleanup_method": "exact-application-path-reconciliation",
        }
    )


def _approved_preflight() -> tuple[
    PreflightObservation,
    PreflightRequest,
    datetime,
]:
    authorization = _approved_authorization()
    now = authorization.issued_at + timedelta(minutes=5)
    observation = PreflightObservation(
        identity=authorization.expected_identity,
        targets=authorization.targets,
        executor=authorization.allowed_executor,
        source=authorization.allowed_source,
    )
    request = PreflightRequest(
        quotas=authorization.quotas,
        permissions=authorization.permissions,
        callback_types=authorization.callback_types,
        test_data_identities=authorization.test_data_identities,
        cleanup_method=authorization.cleanup_method,
        readbacks=authorization.readbacks,
    )

    validate_preflight(authorization, observation, request, now=now)
    return observation, request, now


def test_exact_authorization_preflight_accepts_only_matching_contract() -> None:
    observation, request, now = _approved_preflight()
    authorization = _approved_authorization()

    assert validate_preflight(authorization, observation, request, now=now) is None


@pytest.mark.parametrize(
    ("axis", "mutate", "error"),
    [
        (
            "release",
            lambda observation, request: (
                observation.model_copy(
                    update={
                        "identity": observation.identity.model_copy(
                            update={"deployed_release_sha": "f" * 40}
                        )
                    }
                ),
                request,
            ),
            "identity drift",
        ),
        (
            "model",
            lambda observation, request: (
                observation.model_copy(
                    update={
                        "identity": observation.identity.model_copy(
                            update={"main_model": "unapproved/model"}
                        )
                    }
                ),
                request,
            ),
            "identity drift",
        ),
        (
            "target",
            lambda observation, request: (
                observation.model_copy(
                    update={
                        "targets": observation.targets.model_copy(
                            update={"recipient": "different-synthetic-recipient"}
                        )
                    }
                ),
                request,
            ),
            "target drift",
        ),
        (
            "quota",
            lambda observation, request: (
                observation,
                request.model_copy(
                    update={
                        "quotas": request.quotas.model_copy(
                            update={
                                "max_model_calls": request.quotas.max_model_calls + 1
                            }
                        )
                    }
                ),
            ),
            "quota drift",
        ),
        (
            "permission",
            lambda observation, request: (
                observation,
                request.model_copy(
                    update={
                        "permissions": sorted(
                            {*request.permissions, "deploy_production"}
                        )
                    }
                ),
            ),
            "permission drift",
        ),
    ],
)
def test_preflight_rejects_release_model_target_quota_and_permission_drift(
    axis: str,
    mutate: object,
    error: str,
) -> None:
    del axis
    observation, request, now = _approved_preflight()
    authorization = _approved_authorization()
    changed_observation, changed_request = mutate(observation, request)  # type: ignore[operator]

    with pytest.raises(ManifestValidationError, match=error):
        validate_preflight(
            authorization,
            changed_observation,
            changed_request,
            now=now,
        )


def test_preflight_rejects_draft_and_expired_authorization() -> None:
    observation, request, _ = _approved_preflight()
    authorization = load_authorization_manifest(AUTHORIZATION_PATH)

    with pytest.raises(ManifestValidationError, match="not approved"):
        validate_preflight(
            authorization,
            observation,
            request,
            now=authorization.issued_at + timedelta(minutes=1),
        )

    approved = _approved_authorization()
    with pytest.raises(ManifestValidationError, match="expired"):
        validate_preflight(
            approved,
            observation,
            request,
            now=approved.expires_at + timedelta(seconds=1),
        )


def test_preflight_rejects_approved_manifest_with_unresolved_placeholders() -> None:
    draft = load_authorization_manifest(AUTHORIZATION_PATH)
    unresolved = draft.model_copy(
        update={
            "status": AuthorizationStatus.APPROVED,
            "expected_identity": draft.expected_identity.model_copy(
                update={
                    "repository_commit": "a" * 40,
                    "deployed_release_sha": "b" * 40,
                }
            ),
        }
    )
    observation = PreflightObservation(
        identity=unresolved.expected_identity,
        targets=unresolved.targets,
        executor=unresolved.allowed_executor,
        source=unresolved.allowed_source,
    )
    request = PreflightRequest(
        quotas=unresolved.quotas,
        permissions=unresolved.permissions,
        callback_types=unresolved.callback_types,
        test_data_identities=unresolved.test_data_identities,
        cleanup_method=unresolved.cleanup_method,
        readbacks=unresolved.readbacks,
    )

    with pytest.raises(ManifestValidationError, match="unresolved exact"):
        validate_preflight(
            unresolved,
            observation,
            request,
            now=unresolved.issued_at,
        )


def test_schema_rejects_outcome_used_as_evidence_mode() -> None:
    with pytest.raises(ValidationError):
        CriterionResult(
            criterion_id="AC-01",
            outcome=Outcome.PASS,
            evidence_mode="PASS",  # type: ignore[arg-type]
            evidence_refs=[],
        )


def test_preflight_requires_timezone_aware_current_time() -> None:
    observation, request, _ = _approved_preflight()
    authorization = _approved_authorization()

    with pytest.raises(ManifestValidationError, match="timezone-aware"):
        validate_preflight(
            authorization,
            observation,
            request,
            now=datetime.now(tz=UTC).replace(tzinfo=None),
        )
