from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from scripts.e2e_acceptance.evaluators import (
    EvaluationError,
    evaluate_scenario,
)
from scripts.e2e_acceptance.manifest import (
    build_scenario_binding,
    load_authorization_manifest,
    load_scenario_set,
)
from scripts.e2e_acceptance.runner import (
    AcceptanceRunner,
    RunnerError,
    SideEffectReadback,
    load_dry_run_fixture,
)
from scripts.e2e_acceptance.schemas import (
    AuthorizationStatus,
    PreflightObservation,
    PreflightReadbackIdentity,
    PreflightRequest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_SET_PATH = PROJECT_ROOT / ".codex/stages/tj-ee5f/scenario-set.json"
AUTHORIZATION_PATH = (
    PROJECT_ROOT / ".codex/stages/tj-ee5f/authorization-manifest.example.json"
)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _executable_input_digests(
    raw_fixture: dict[str, object],
    readback: SideEffectReadback,
) -> dict[str, str]:
    scenario_id = str(raw_fixture["scenario_id"])
    tester = raw_fixture["tester"]
    judge = raw_fixture["judge"]
    assert isinstance(tester, dict)
    assert isinstance(judge, dict)
    return {
        f"{scenario_id}:planned_turns": _digest(raw_fixture["planned_turns"]),
        f"{scenario_id}:tester_prompt": _digest(tester["prompt"]),
        f"{scenario_id}:judge_rubric": _digest(judge["rubric"]),
        f"{scenario_id}:deterministic_oracles": _digest(
            raw_fixture["deterministic_checks"]
        ),
        f"{scenario_id}:side_effect_readback": _digest(
            readback.model_dump(mode="json")
        ),
    }


def _fixture() -> dict[str, object]:
    return {
        "schema_version": "noor-e2e-dry-run-fixture/v1",
        "scenario_id": "SC-OPEN-EN",
        "attempt_number": 1,
        "previous_attempt_sha256": None,
        "retest": None,
        "run_context": {
            "started_at_utc": "2026-07-27T10:00:00+00:00",
            "started_at_moscow": "2026-07-27T13:00:00+03:00",
            "retention_expires_at": "2026-08-27T10:00:00+00:00",
            "expected_identity": {
                "repository_commit": "a" * 40,
                "deployed_release_sha": "b" * 40,
                "ci_run_id": "fixture-ci",
                "endpoint": "https://fixture.invalid",
                "app_version": "0.4.0",
                "migration_head": "fixture-migration",
                "main_model": "fixture/main",
                "fast_model": "fixture/fast",
            },
            "actual_identity": {
                "repository_commit": "a" * 40,
                "deployed_release_sha": "b" * 40,
                "ci_run_id": "fixture-ci",
                "endpoint": "https://fixture.invalid",
                "app_version": "0.4.0",
                "migration_head": "fixture-migration",
                "main_model": "fixture/main",
                "fast_model": "fixture/fast",
            },
            "authorization_id": "auth-local-contract-test",
            "authorization_manifest_digest": "0" * 64,
            "approved_target_refs": ["synthetic-fixture-target"],
            "quotas": {"messages": 2, "model_calls": 0, "cost_usd": 0},
            "harness_version": "task-2.v1",
            "available_tools": ["fixture_catalog_search"],
        },
        "planned_turns": [
            {
                "turn_id": "turn-001",
                "customer_text": "Hello, I need a chair.",
                "expected_behavior": "Noor introduces itself and asks a useful question.",
                "criterion_ids": ["AC-01", "AC-02", "AC-03"],
                "deterministic_check_ids": [
                    "cp-english-opener",
                    "cp-name-requested",
                    "po-siyyad-identity",
                    "po-premature-commercial-side-effect",
                ],
            },
            {
                "turn_id": "turn-002",
                "customer_text": "Lina. It is for long office work.",
                "expected_behavior": (
                    "Noor accepts the bare name and resumes the original chair request."
                ),
                "criterion_ids": ["AC-06"],
                "deterministic_check_ids": [
                    "cp-bare-name-accepted",
                    "cp-original-request-resumed",
                    "po-siyyad-identity",
                    "po-repeated-name-question",
                    "po-premature-commercial-side-effect",
                ],
            },
        ],
        "actual_turns": [
            {
                "turn_id": "turn-001",
                "conversation_id": "fixture-conversation-001",
                "message_id": "fixture-message-001",
                "provider_message_id": None,
                "customer_text": "Hello, I need a chair.",
                "assistant_text": "Hello! I am Noor from Treejar. What should I call you?",
                "original_language": "en",
                "translation": None,
                "translation_provenance": None,
                "timestamps": {
                    "sent_at": "2026-07-27T10:00:00Z",
                    "received_at": "2026-07-27T10:00:01Z",
                    "first_visible_at": "2026-07-27T10:00:01Z",
                    "final_visible_at": "2026-07-27T10:00:02Z",
                },
                "model": "fixture/model",
                "tools": [],
                "audit_ids": ["audit-redacted-001"],
                "expected_behavior": "Noor introduces itself and asks a useful question.",
                "actual_observation": "Noor introduced itself and asked for a name.",
                "criterion_ids": ["AC-01", "AC-02", "AC-03"],
                "beads_ids": ["tj-ee5f"],
                "deterministic_check_ids": [
                    "cp-english-opener",
                    "cp-name-requested",
                    "po-siyyad-identity",
                    "po-premature-commercial-side-effect",
                ],
                "token_count": 10,
                "cost_usd": 0,
            },
            {
                "turn_id": "turn-002a",
                "planned_turn_id": "turn-002",
                "conversation_id": "fixture-conversation-001",
                "message_id": "fixture-message-002",
                "provider_message_id": None,
                "customer_text": (
                    "Lina. It is for long office work, with lumbar support."
                ),
                "assistant_text": (
                    "Nice to meet you, Lina. Let us continue with chairs for your office."
                ),
                "original_language": "en",
                "translation": None,
                "translation_provenance": None,
                "timestamps": {
                    "sent_at": "2026-07-27T10:00:03Z",
                    "received_at": "2026-07-27T10:00:04Z",
                    "first_visible_at": "2026-07-27T10:00:04Z",
                    "final_visible_at": "2026-07-27T10:00:05Z",
                },
                "model": "fixture/model",
                "tools": ["catalog_search"],
                "audit_ids": ["audit-redacted-002"],
                "expected_behavior": (
                    "Noor accepts the bare name and resumes the original chair request."
                ),
                "actual_observation": "Noor accepted the name and resumed the request.",
                "criterion_ids": ["AC-06"],
                "beads_ids": ["tj-ee5f"],
                "deterministic_check_ids": [
                    "cp-bare-name-accepted",
                    "cp-original-request-resumed",
                    "po-siyyad-identity",
                    "po-repeated-name-question",
                    "po-premature-commercial-side-effect",
                ],
                "token_count": 12,
                "cost_usd": 0,
            },
        ],
        "adaptive_deviations": [
            {
                "planned_turn_id": "turn-002",
                "actual_turn_id": "turn-002a",
                "reason": "Bounded clarification preserving persona facts.",
            }
        ],
        "deterministic_checks": [
            {
                "check_id": "cp-english-opener",
                "hard_safety": False,
                "turn_ids": ["turn-001"],
                "oracle": {
                    "type": "required_substring_present",
                    "field": "assistant_text",
                    "value": "Noor from Treejar",
                },
            },
            {
                "check_id": "cp-name-requested",
                "hard_safety": False,
                "turn_ids": ["turn-001"],
                "oracle": {
                    "type": "required_substring_present",
                    "field": "assistant_text",
                    "value": "What should I call you",
                },
            },
            {
                "check_id": "cp-bare-name-accepted",
                "hard_safety": False,
                "turn_ids": ["turn-002a"],
                "oracle": {
                    "type": "required_substring_present",
                    "field": "assistant_text",
                    "value": "Nice to meet you, Lina",
                },
            },
            {
                "check_id": "cp-original-request-resumed",
                "hard_safety": False,
                "turn_ids": ["turn-002a"],
                "oracle": {
                    "type": "required_substring_present",
                    "field": "assistant_text",
                    "value": "continue with chairs",
                },
            },
            {
                "check_id": "po-siyyad-identity",
                "hard_safety": True,
                "turn_ids": ["turn-001", "turn-002a"],
                "oracle": {
                    "type": "forbidden_substring_absent",
                    "field": "assistant_text",
                    "value": "Siyyad",
                },
            },
            {
                "check_id": "po-repeated-name-question",
                "hard_safety": True,
                "turn_ids": ["turn-002a"],
                "oracle": {
                    "type": "forbidden_substring_absent",
                    "field": "assistant_text",
                    "value": "What should I call you",
                },
            },
            {
                "check_id": "po-premature-commercial-side-effect",
                "hard_safety": True,
                "turn_ids": ["turn-001", "turn-002a"],
                "oracle": {
                    "type": "forbidden_substring_absent",
                    "field": "assistant_text",
                    "value": "quotation",
                },
            },
        ],
        "judge": {
            "model": "fixture/judge",
            "reasoning_effort": "deterministic_fixture",
            "max_calls": 1,
            "temperature": 0,
            "rubric": "Judge the authorized checkpoints without overriding hard safety.",
            "rubric_digest": "",
            "passed": True,
            "reasoning": "All required checkpoints are present.",
            "calls_used": 1,
            "token_count": 5,
            "cost_usd": 0,
        },
        "tester": {
            "model": "fixture/tester",
            "reasoning_effort": "deterministic_fixture",
            "seed": 20260727,
            "prompt": "Play the bounded synthetic office-buyer persona.",
            "prompt_digest": "",
            "max_calls": 1,
            "calls_used": 1,
            "token_count": 5,
            "cost_usd": 0,
        },
        "side_effects": [
            {
                "artifact_id": "local:conversation-001",
                "scenario_id": "SC-OPEN-EN",
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
    }


def _readback() -> SideEffectReadback:
    return SideEffectReadback(
        schema_version="noor-e2e-side-effect-readback/v1",
        source_id="independent-fixture-readback",
        observed_at="2026-07-27T10:00:06Z",
        authorization_id="auth-local-contract-test",
        scenario_id="SC-OPEN-EN",
        inventory={"local:conversation-001": {"state": "closed"}},
    )


def _authorized_bundle(
    raw_fixture: dict[str, object],
    *,
    quota_overrides: dict[str, object] | None = None,
    subsystem_overrides: dict[str, int] | None = None,
) -> tuple[object, ...]:
    tester = raw_fixture["tester"]
    judge = raw_fixture["judge"]
    run_context = raw_fixture["run_context"]
    assert isinstance(tester, dict)
    assert isinstance(judge, dict)
    assert isinstance(run_context, dict)
    tester["prompt_digest"] = _digest(tester["prompt"])
    judge["rubric_digest"] = _digest(judge["rubric"])

    scenario_set = load_scenario_set(SCENARIO_SET_PATH)
    draft = load_authorization_manifest(AUTHORIZATION_PATH)
    readback = _readback()
    identity = draft.expected_identity.model_validate(run_context["expected_identity"])
    subsystem_quotas = dict(draft.quotas.subsystem_quotas)
    subsystem_quotas.update(
        {
            "application_native_webhook": 4,
            "outbound_text": 4,
        }
    )
    if subsystem_overrides:
        subsystem_quotas.update(subsystem_overrides)
    quota_values: dict[str, object] = {
        "max_scenarios": 1,
        "max_messages": 4,
        "max_model_calls": 8,
        "max_cost_usd": 1,
        "subsystem_quotas": subsystem_quotas,
    }
    if quota_overrides:
        quota_values.update(quota_overrides)
    quotas = draft.quotas.model_copy(update=quota_values)
    binding = build_scenario_binding(
        scenario_set,
        SCENARIO_SET_PATH,
        executable_input_digests=_executable_input_digests(
            raw_fixture,
            readback,
        ),
    )
    authorization = draft.model_copy(
        update={
            "authorization_id": "auth-local-contract-test",
            "status": AuthorizationStatus.APPROVED,
            "issuer": "test-authorizer",
            "expires_at": draft.issued_at + timedelta(days=1),
            "allowed_executor": "test-executor",
            "allowed_source": "local-dry-run",
            "expected_identity": identity,
            "targets": draft.targets.model_copy(
                update={
                    "recipient": "synthetic-recipient",
                    "wazzup_channel": "synthetic-channel",
                    "telegram_target": "synthetic-telegram",
                    "synthetic_suffix": "synthetic-run",
                }
            ),
            "quotas": quotas,
            "permissions": [
                "application_native_webhook",
                "outbound_text",
                "crm_synthetic",
            ],
            "test_data_identities": ["synthetic-identity"],
            "cleanup_method": "exact-application-path-reconciliation",
            "scenario_binding": binding,
        }
    )
    run_context["authorization_manifest_digest"] = _digest(
        authorization.model_dump(mode="json")
    )
    run_context["approved_target_refs"] = list(
        authorization.targets.model_dump(mode="json").values()
    )
    run_context["quotas"] = authorization.quotas.model_dump(mode="json")
    readback_identity = PreflightReadbackIdentity(
        source_id=readback.source_id,
        observed_at=readback.observed_at,
        content_digest=_digest(readback.model_dump(mode="json")),
    )
    observation = PreflightObservation(
        identity=identity,
        targets=authorization.targets,
        executor=authorization.allowed_executor,
        source=authorization.allowed_source,
        readback_identity=readback_identity,
    )
    request = PreflightRequest(
        quotas=authorization.quotas,
        permissions=authorization.permissions,
        callback_types=authorization.callback_types,
        test_data_identities=authorization.test_data_identities,
        cleanup_method=authorization.cleanup_method,
        readbacks=authorization.readbacks,
        stop_conditions=authorization.stop_conditions,
        scenario_binding=authorization.scenario_binding,
    )
    now = readback.observed_at + timedelta(minutes=1)
    return scenario_set, authorization, observation, request, readback, now


def _load_fixture(tmp_path: Path, raw_fixture: dict[str, object]):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(raw_fixture), encoding="utf-8")
    return load_dry_run_fixture(fixture_path)


def _authorized_runner(
    tmp_path: Path,
    raw_fixture: dict[str, object],
) -> tuple[AcceptanceRunner, object]:
    scenario_set, authorization, observation, request, readback, now = (
        _authorized_bundle(raw_fixture)
    )
    fixture = _load_fixture(tmp_path, raw_fixture)
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    runner = AcceptanceRunner(
        repo_root=repo,
        protected_root=tmp_path / "protected",
        dry_run=True,
        scenario_set=scenario_set,
        scenario_set_path=SCENARIO_SET_PATH,
        authorization=authorization,
        observation=observation,
        request=request,
        readback=readback,
        preflight_now=now,
    )
    return runner, fixture


def _runner_from_bundle(
    tmp_path: Path,
    bundle: tuple[object, ...],
) -> AcceptanceRunner:
    scenario_set, authorization, observation, request, readback, now = bundle
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    return AcceptanceRunner(
        repo_root=repo,
        protected_root=tmp_path / "protected",
        dry_run=True,
        scenario_set=scenario_set,
        scenario_set_path=SCENARIO_SET_PATH,
        authorization=authorization,
        observation=observation,
        request=request,
        readback=readback,
        preflight_now=now,
    )


def test_dry_run_captures_planned_actual_deviation_and_evaluator_provenance(
    tmp_path: Path,
) -> None:
    raw_fixture = _fixture()
    runner, fixture = _authorized_runner(tmp_path, raw_fixture)

    result = runner.run_fixture(
        run_id="run-20260727-001",
        fixture=fixture,
    )

    assert result["status"] == "passed"
    assert result["planned_turns"][1]["turn_id"] == "turn-002"
    assert result["actual_turns"][1]["planned_turn_id"] == "turn-002"
    assert result["actual_turns"][0]["criterion_ids"] == [
        "AC-01",
        "AC-02",
        "AC-03",
    ]
    assert result["adaptive_deviations"][0]["actual_turn_id"] == "turn-002a"
    assert result["tester"]["seed"] == 20260727
    assert result["run_context"]["harness_version"] == "task-2.v1"
    assert result["judge"]["reasoning"] == "All required checkpoints are present."
    assert result["deterministic_checks"][0]["reasoning"]
    retention = (
        runner.store.repo_root / ".codex/stages/tj-ee5f/results/run-20260727-001/"
        "evidence-retention/attempt-001.json"
    )
    retention_payload = json.loads(retention.read_text(encoding="utf-8"))
    assert retention_payload["raw_records"][0]["sha256"]
    assert retention_payload["redacted_records"][0]["sha256"]


def test_arabic_turn_requires_russian_translation_with_provenance(
    tmp_path: Path,
) -> None:
    fixture = _fixture()
    _authorized_bundle(fixture)
    actual = fixture["actual_turns"]
    assert isinstance(actual, list)
    actual[0]["original_language"] = "ar"
    actual[0]["translation"] = None
    actual[0]["translation_provenance"] = None
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(RunnerError, match="translation"):
        load_dry_run_fixture(fixture_path)


def test_runner_refuses_non_dry_run_boundary(tmp_path: Path) -> None:
    raw_fixture = _fixture()
    scenario_set, authorization, observation, request, readback, now = (
        _authorized_bundle(raw_fixture)
    )
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(RunnerError, match="dry-run"):
        AcceptanceRunner(
            repo_root=repo,
            protected_root=tmp_path / "protected",
            dry_run=False,
            scenario_set=scenario_set,
            scenario_set_path=SCENARIO_SET_PATH,
            authorization=authorization,
            observation=observation,
            request=request,
            readback=readback,
            preflight_now=now,
        )


def test_runtime_identity_drift_stops_fixture_before_evidence(tmp_path: Path) -> None:
    fixture = _fixture()
    _authorized_bundle(fixture)
    context = fixture["run_context"]
    assert isinstance(context, dict)
    actual_identity = context["actual_identity"]
    assert isinstance(actual_identity, dict)
    actual_identity["deployed_release_sha"] = "different-release"
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(RunnerError, match="identity drift"):
        load_dry_run_fixture(fixture_path)


def test_turn_timestamp_order_is_validated(tmp_path: Path) -> None:
    fixture = _fixture()
    _authorized_bundle(fixture)
    turns = fixture["actual_turns"]
    assert isinstance(turns, list)
    timestamps = turns[0]["timestamps"]
    assert isinstance(timestamps, dict)
    timestamps["first_visible_at"] = "2026-07-27T09:59:59Z"
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(RunnerError, match="timestamp"):
        load_dry_run_fixture(fixture_path)


def test_runner_rejects_planned_prompt_or_expected_behavior_drift(
    tmp_path: Path,
) -> None:
    raw_fixture = _fixture()
    bundle = _authorized_bundle(raw_fixture)
    planned = raw_fixture["planned_turns"]
    assert isinstance(planned, list)
    planned[0]["expected_behavior"] = "Arbitrary replacement expectation."
    fixture = _load_fixture(tmp_path, raw_fixture)
    runner = _runner_from_bundle(tmp_path, bundle)

    with pytest.raises(RunnerError, match="executable input drift"):
        runner.run_fixture(run_id="run-binding-drift-001", fixture=fixture)


def test_runner_rejects_self_declared_dummy_oracle_even_when_it_passes(
    tmp_path: Path,
) -> None:
    raw_fixture = _fixture()
    bundle = _authorized_bundle(raw_fixture)
    checks = raw_fixture["deterministic_checks"]
    turns = raw_fixture["actual_turns"]
    planned = raw_fixture["planned_turns"]
    assert isinstance(checks, list)
    assert isinstance(turns, list)
    assert isinstance(planned, list)
    checks[0] = {
        "check_id": "dummy-always-pass",
        "hard_safety": False,
        "turn_ids": ["turn-001"],
        "oracle": {
            "type": "required_substring_present",
            "field": "assistant_text",
            "value": "Hello",
        },
    }
    replacement_ids = [
        "dummy-always-pass",
        "cp-name-requested",
        "po-siyyad-identity",
        "po-premature-commercial-side-effect",
    ]
    turns[0]["deterministic_check_ids"] = replacement_ids
    planned[0]["deterministic_check_ids"] = replacement_ids
    fixture = _load_fixture(tmp_path, raw_fixture)
    runner = _runner_from_bundle(tmp_path, bundle)

    with pytest.raises(RunnerError, match="executable input drift"):
        runner.run_fixture(run_id="run-oracle-drift-001", fixture=fixture)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("customer_text", "Unplanned replacement customer turn."),
        ("expected_behavior", "Unplanned replacement expectation."),
        ("criterion_ids", ["AC-99"]),
        (
            "deterministic_check_ids",
            [
                "cp-name-requested",
                "cp-english-opener",
                "po-siyyad-identity",
                "po-premature-commercial-side-effect",
            ],
        ),
    ],
)
def test_runner_rejects_actual_turn_drift_from_bound_plan(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    raw_fixture = _fixture()
    bundle = _authorized_bundle(raw_fixture)
    turns = raw_fixture["actual_turns"]
    assert isinstance(turns, list)
    turns[0][field] = replacement
    fixture = _load_fixture(tmp_path, raw_fixture)
    runner = _runner_from_bundle(tmp_path, bundle)

    with pytest.raises(RunnerError, match="actual turn binding"):
        runner.run_fixture(run_id=f"run-actual-{field}", fixture=fixture)


def test_runner_rejects_self_authorized_oracle_policy_drift(
    tmp_path: Path,
) -> None:
    raw_fixture = _fixture()
    checks = raw_fixture["deterministic_checks"]
    assert isinstance(checks, list)
    checks[0]["hard_safety"] = False
    oracle = checks[0]["oracle"]
    assert isinstance(oracle, dict)
    oracle["value"] = "synthetic phrase absent from every response"
    bundle = _authorized_bundle(raw_fixture)
    fixture = _load_fixture(tmp_path, raw_fixture)
    runner = _runner_from_bundle(tmp_path, bundle)

    with pytest.raises(RunnerError, match="canonical oracle policy"):
        runner.run_fixture(run_id="run-self-authorized-oracle", fixture=fixture)


@pytest.mark.parametrize(
    ("mutation", "expected_pattern"),
    [
        ("model_calls", "model-call quota"),
        ("cost", "cost quota"),
        ("subsystem", "subsystem quota"),
    ],
)
def test_runner_enforces_every_authorized_quota_dimension(
    tmp_path: Path,
    mutation: str,
    expected_pattern: str,
) -> None:
    raw_fixture = _fixture()
    turns = raw_fixture["actual_turns"]
    assert isinstance(turns, list)
    if mutation == "cost":
        turns[0]["cost_usd"] = 0.01
    quota_overrides: dict[str, object] | None = None
    subsystem_overrides: dict[str, int] | None = None
    if mutation == "model_calls":
        quota_overrides = {"max_model_calls": 0}
    elif mutation == "cost":
        quota_overrides = {"max_cost_usd": 0}
    else:
        subsystem_overrides = {"outbound_text": 0}
    bundle = _authorized_bundle(
        raw_fixture,
        quota_overrides=quota_overrides,
        subsystem_overrides=subsystem_overrides,
    )
    fixture = _load_fixture(tmp_path, raw_fixture)
    runner = _runner_from_bundle(tmp_path, bundle)

    with pytest.raises(RunnerError, match=expected_pattern):
        runner.run_fixture(run_id=f"run-quota-{mutation}", fixture=fixture)


def test_tester_prompt_digest_is_derived_from_prompt(tmp_path: Path) -> None:
    raw_fixture = _fixture()
    _authorized_bundle(raw_fixture)
    tester = raw_fixture["tester"]
    assert isinstance(tester, dict)
    tester["prompt"] = "Changed after digest."

    with pytest.raises(RunnerError, match="tester prompt digest"):
        _load_fixture(tmp_path, raw_fixture)


def test_runner_supports_sequential_failed_attempt_and_authorized_retest(
    tmp_path: Path,
) -> None:
    first_raw = _fixture()
    bundle = _authorized_bundle(first_raw)
    first_turns = first_raw["actual_turns"]
    assert isinstance(first_turns, list)
    first_turns[1]["assistant_text"] = "What should I call you?"
    first_fixture = _load_fixture(tmp_path, first_raw)
    runner = _runner_from_bundle(tmp_path, bundle)

    first_result = runner.run_fixture(
        run_id="run-retest-chain-001",
        fixture=first_fixture,
    )
    assert first_result["attempt_id"] == "attempt-001"
    assert first_result["status"] == "failed"
    first_path = (
        runner.store.tracked_root
        / "run-retest-chain-001/attempts/SC-OPEN-EN/attempt-001.json"
    )
    first_digest = runner.store.sha256_file(first_path)

    second_raw = _fixture()
    _authorized_bundle(second_raw)
    second_raw["attempt_number"] = 2
    second_raw["previous_attempt_sha256"] = first_digest
    second_raw["retest"] = {
        "retest_of": "attempt-001",
        "defect_id": "tj-synthetic-defect",
        "fix_commit": "c" * 40,
        "deployment_identity": "b" * 40,
    }
    second_fixture = _load_fixture(tmp_path, second_raw)
    second_result = runner.run_fixture(
        run_id="run-retest-chain-001",
        fixture=second_fixture,
    )

    assert second_result["attempt_id"] == "attempt-002"
    assert second_result["status"] == "passed"
    assert first_path.exists()
    assert (
        runner.store.tracked_root
        / "run-retest-chain-001/attempts/SC-OPEN-EN/attempt-002.json"
    ).exists()


def test_retest_deployment_identity_must_match_actual_release(tmp_path: Path) -> None:
    raw_fixture = _fixture()
    _authorized_bundle(raw_fixture)
    raw_fixture["attempt_number"] = 2
    raw_fixture["previous_attempt_sha256"] = "e" * 64
    raw_fixture["retest"] = {
        "retest_of": "attempt-001",
        "defect_id": "tj-synthetic-defect",
        "fix_commit": "c" * 40,
        "deployment_identity": "d" * 40,
    }

    with pytest.raises(RunnerError, match="retest deployment identity"):
        _load_fixture(tmp_path, raw_fixture)


def test_fixture_cannot_supply_its_own_observed_inventory(tmp_path: Path) -> None:
    raw_fixture = _fixture()
    raw_fixture["observed_inventory"] = {"local:conversation-001": {"state": "closed"}}
    _authorized_bundle(raw_fixture)

    with pytest.raises(RunnerError, match="observed_inventory|extra"):
        _load_fixture(tmp_path, raw_fixture)


def test_independent_readback_digest_is_bound_in_preflight(tmp_path: Path) -> None:
    raw_fixture = _fixture()
    bundle = list(_authorized_bundle(raw_fixture))
    readback = bundle[4]
    assert isinstance(readback, SideEffectReadback)
    bundle[4] = readback.model_copy(
        update={
            "inventory": {
                "local:conversation-001": {"state": "active"},
            }
        }
    )

    with pytest.raises(RunnerError, match="readback provenance"):
        _runner_from_bundle(tmp_path, tuple(bundle))


def test_self_consistent_readback_observation_cannot_bypass_authorization(
    tmp_path: Path,
) -> None:
    raw_fixture = _fixture()
    bundle = list(_authorized_bundle(raw_fixture))
    observation = bundle[2]
    readback = bundle[4]
    assert isinstance(observation, PreflightObservation)
    assert isinstance(readback, SideEffectReadback)
    tampered = readback.model_copy(
        update={
            "inventory": {
                "local:conversation-001": {"state": "active"},
            }
        }
    )
    bundle[4] = tampered
    bundle[2] = observation.model_copy(
        update={
            "readback_identity": PreflightReadbackIdentity(
                source_id=tampered.source_id,
                observed_at=tampered.observed_at,
                content_digest=_digest(tampered.model_dump(mode="json")),
            )
        }
    )
    fixture = _load_fixture(tmp_path, raw_fixture)
    runner = _runner_from_bundle(tmp_path, tuple(bundle))

    with pytest.raises(RunnerError, match="executable input drift"):
        runner.run_fixture(run_id="run-readback-auth-bypass", fixture=fixture)


def test_runner_enforces_cumulative_run_quota_before_retest(
    tmp_path: Path,
) -> None:
    first_raw = _fixture()
    bundle = _authorized_bundle(
        first_raw,
        quota_overrides={
            "max_messages": 2,
            "max_model_calls": 4,
        },
        subsystem_overrides={
            "application_native_webhook": 2,
            "outbound_text": 2,
        },
    )
    first_fixture = _load_fixture(tmp_path, first_raw)
    runner = _runner_from_bundle(tmp_path, bundle)
    runner.run_fixture(run_id="run-cumulative-quota", fixture=first_fixture)
    first_path = (
        runner.store.tracked_root
        / "run-cumulative-quota/attempts/SC-OPEN-EN/attempt-001.json"
    )

    second_raw = _fixture()
    _authorized_bundle(
        second_raw,
        quota_overrides={
            "max_messages": 2,
            "max_model_calls": 4,
        },
        subsystem_overrides={
            "application_native_webhook": 2,
            "outbound_text": 2,
        },
    )
    second_raw["attempt_number"] = 2
    second_raw["previous_attempt_sha256"] = runner.store.sha256_file(first_path)
    second_raw["retest"] = {
        "retest_of": "attempt-001",
        "defect_id": "tj-synthetic-defect",
        "fix_commit": "c" * 40,
        "deployment_identity": "b" * 40,
    }
    second_fixture = _load_fixture(tmp_path, second_raw)

    with pytest.raises(RunnerError, match="cumulative.*quota"):
        runner.run_fixture(
            run_id="run-cumulative-quota",
            fixture=second_fixture,
        )


def test_hard_safety_failure_cannot_be_overridden_by_judge() -> None:
    result = evaluate_scenario(
        deterministic_checks=[
            {
                "check_id": "commercial-grounding",
                "passed": False,
                "hard_safety": True,
                "reasoning": "Unsupported exact stock claim.",
            }
        ],
        judge={
            "model": "fixture/judge",
            "reasoning_effort": "deterministic_fixture",
            "max_calls": 1,
            "temperature": 0,
            "rubric_digest": "a" * 64,
            "passed": True,
            "reasoning": "The response is otherwise helpful.",
        },
    )

    assert result.status == "failed"
    assert result.hard_failure is True
    assert "commercial-grounding" in result.failure_reasons


def test_judge_is_bounded_and_cannot_be_the_only_oracle() -> None:
    with pytest.raises(EvaluationError, match="deterministic"):
        evaluate_scenario(
            deterministic_checks=[],
            judge={
                "model": "fixture/judge",
                "reasoning_effort": "deterministic_fixture",
                "max_calls": 1,
                "temperature": 0,
                "rubric_digest": "a" * 64,
                "passed": True,
                "reasoning": "Looks good.",
            },
        )

    with pytest.raises(EvaluationError, match="bounded"):
        evaluate_scenario(
            deterministic_checks=[
                {
                    "check_id": "opening",
                    "passed": True,
                    "hard_safety": False,
                    "reasoning": "Opening present.",
                }
            ],
            judge={
                "model": "fixture/judge",
                "reasoning_effort": "deterministic_fixture",
                "max_calls": 2,
                "temperature": 0,
                "rubric_digest": "a" * 64,
                "passed": True,
                "reasoning": "Looks good.",
            },
        )


def test_cli_runs_fixture_against_validated_task1_scenario_set(
    tmp_path: Path,
) -> None:
    fixture = _fixture()
    _, authorization, observation, request, readback, now = _authorized_bundle(fixture)
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    authorization_path = tmp_path / "authorization.json"
    authorization_path.write_text(
        authorization.model_dump_json(indent=2),
        encoding="utf-8",
    )
    observation_path = tmp_path / "observation.json"
    observation_path.write_text(
        observation.model_dump_json(indent=2),
        encoding="utf-8",
    )
    request_path = tmp_path / "request.json"
    request_path.write_text(request.model_dump_json(indent=2), encoding="utf-8")
    readback_path = tmp_path / "readback.json"
    readback_path.write_text(readback.model_dump_json(indent=2), encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    project_root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts/run_noor_e2e_acceptance.py"),
            "--dry-run",
            "--repo-root",
            str(repo),
            "--protected-root",
            str(tmp_path / "protected"),
            "--scenario-set",
            str(SCENARIO_SET_PATH),
            "--authorization",
            str(authorization_path),
            "--observation",
            str(observation_path),
            "--request",
            str(request_path),
            "--readback",
            str(readback_path),
            "--preflight-now",
            now.isoformat(),
            "--fixture",
            str(fixture_path),
            "--run-id",
            "run-cli-001",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert json.loads(completed.stdout)["scenario_id"] == "SC-OPEN-EN"
