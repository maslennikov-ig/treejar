"""Invariant tests for the replanned generic acceptance trust center."""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_SET_PATH = PROJECT_ROOT / ".codex/stages/tj-ee5f/scenario-set.json"
TRACEABILITY_PATH = PROJECT_ROOT / ".codex/stages/tj-ee5f/traceability-manifest.json"
SCOPE_PATH = PROJECT_ROOT / ".codex/goals/tj-ee5f/scope-criterion-snapshot.json"
NON_OPEN_SCENARIOS = [
    item["scenario_id"]
    for item in json.loads(SCENARIO_SET_PATH.read_text(encoding="utf-8"))["scenarios"]
    if item["scenario_id"] != "SC-OPEN-EN"
]


def _policy_module():
    return importlib.import_module("scripts.e2e_acceptance.policy")


@pytest.mark.parametrize("scenario_id", NON_OPEN_SCENARIOS)
def test_generic_compiler_accepts_each_non_open_scenario(scenario_id: str) -> None:
    policy = _policy_module()
    registry = policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)

    compiled = registry.compiled_policy.scenarios[scenario_id]

    canonical = {
        item["scenario_id"]: item
        for item in json.loads(SCENARIO_SET_PATH.read_text(encoding="utf-8"))[
            "scenarios"
        ]
    }[scenario_id]
    assert set(compiled.checkpoints) == set(canonical["checkpoints"])
    assert set(compiled.prohibited_outcomes) == set(canonical["prohibited_outcomes"])
    assert set(compiled.criterion_ids) == set(canonical["criterion_ids"])
    assert set(compiled.required_permissions) == set(canonical["required_permissions"])
    assert set(compiled.required_readbacks) == set(canonical["readbacks"])


def test_trusted_registry_owns_exact_30_plus_20_plus_9_scope() -> None:
    policy = _policy_module()
    registry = policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)
    scenario_set = json.loads(SCENARIO_SET_PATH.read_text(encoding="utf-8"))
    scope = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
    traceability = json.loads(TRACEABILITY_PATH.read_text(encoding="utf-8"))

    assert set(registry.compiled_policy.criteria) == {
        item["criterion_id"] for item in scope["criteria"]
    }
    assert set(registry.compiled_policy.criteria) == {
        item["criterion_id"] for item in traceability["criteria"]
    }
    assert set(registry.compiled_policy.scenarios) == {
        item["scenario_id"] for item in scenario_set["scenarios"]
    }
    assert set(registry.compiled_policy.evidence_blocks) == {
        item["block_id"] for item in scenario_set["evidence_blocks"]
    }


def test_policy_compiler_has_no_scenario_id_branch_or_free_text_inference() -> None:
    policy = _policy_module()
    source = inspect.getsource(policy)

    assert "if scenario_id" not in source
    assert "elif scenario_id" not in source
    assert "re.compile" not in source
    assert "hard_safety" not in source
    assert "allowed_oracle" not in source

    registry = policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)
    assert registry.compiled_policy.dsl_version == "noor-e2e-oracle-dsl/v2"
    assert all(
        binding.oracle.kind != "text_assertion"
        for scenario in registry.compiled_policy.scenarios.values()
        for binding in scenario.prohibited_outcomes.values()
    )
    for assertion in registry.compiled_policy.assertions.values():
        assert (
            assertion.source_text_digest
            == hashlib.sha256(assertion.canonical_text.encode("utf-8")).hexdigest()
        )
        assert assertion.structured_required is True


def test_manager_handoff_semantic_addition_requires_classifier_evidence() -> None:
    policy = _policy_module()
    registry = policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)
    scenario = registry.compiled_policy.scenarios["SC-ESCALATION"]
    binding = next(
        item
        for text, item in scenario.prohibited_outcomes.items()
        if "manager" in text.lower() and "fact" in text.lower()
    )

    result = policy.ClassifierResult.build(
        assertion_id=binding.assertion_id,
        policy_digest=registry.compiled_policy.policy_digest,
        evaluator_digest=registry.classifier_evaluator_digest(binding.assertion_id),
        run_id="synthetic-policy-run",
        attempt_digest="7" * 64,
        preflight_digest="8" * 64,
        classifier_id="manager_faithfulness.v1",
        producer="production-manager-fidelity-classifier",
        source_id="synthetic-classifier-event",
        source_digest="a" * 64,
        observed_at=datetime(2026, 7, 27, 10, 0, tzinfo=UTC),
        passed=False,
        reason="The delivered reply adds a fact absent from the draft.",
    )
    context = registry.verified_evidence_context
    object.__setattr__(
        registry,
        "_TrustedAcceptanceRegistry__verified_evidence_context",
        context.model_copy(
            update={
                "classifier_digests": context.classifier_digests
                | {result.artifact_digest}
            }
        ),
    )
    decision = registry.evaluate_oracle(
        binding.assertion_id,
        policy.OracleEvidence(
            assertion_id=binding.assertion_id,
            structured_events=[],
            tool_results=[],
            readbacks=[],
            classifier_results=[result],
            text_supplements=["A literal text check passed."],
        ),
    )

    assert decision.passed is False
    assert decision.decisive_evidence_kind == "classifier_result"


def test_final_readback_must_follow_every_visible_delivery_and_action() -> None:
    policy = _policy_module()
    registry = policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline-source",
        run_id="synthetic-policy-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=datetime(2026, 7, 27, 9, 59, tzinfo=UTC),
        inventory={"synthetic:conversation": {"state": "absent"}},
    )
    stale_final = policy.ReadbackObservation.build(
        phase="final",
        collector_id="independent-readback-collector",
        source_id="synthetic-final-source",
        run_id="synthetic-policy-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="5" * 64,
        observed_at=datetime(2026, 7, 27, 10, 0, 2, tzinfo=UTC),
        inventory={"synthetic:conversation": {"state": "closed"}},
    )

    context = registry.verified_evidence_context
    object.__setattr__(
        registry,
        "_TrustedAcceptanceRegistry__verified_evidence_context",
        context.model_copy(
            update={
                "readback_digests": context.readback_digests
                | {baseline.content_digest, stale_final.content_digest}
            }
        ),
    )
    with pytest.raises(policy.PolicyValidationError, match="final readback.*after"):
        registry.validate_readback_window(
            baseline=baseline,
            final=stale_final,
            final_visible_at=[datetime(2026, 7, 27, 10, 0, 3, tzinfo=UTC)],
            delivered_at=[datetime(2026, 7, 27, 10, 0, 4, tzinfo=UTC)],
            action_at=[datetime(2026, 7, 27, 10, 0, 5, tzinfo=UTC)],
        )


def test_caller_fabricated_final_readback_is_rejected() -> None:
    policy = _policy_module()
    registry = policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)
    baseline = policy.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="synthetic-baseline",
        run_id="synthetic-policy-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="4" * 64,
        observed_at=datetime.now(UTC) - timedelta(minutes=2),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    fabricated = policy.ReadbackObservation.build(
        phase="final",
        collector_id="not-preflight-bound",
        source_id="fabricated-final",
        run_id="synthetic-policy-run",
        preflight_digest="8" * 64,
        collector_artifact_digest="9" * 64,
        causal_event_digest="5" * 64,
        observed_at=datetime.now(UTC),
        inventory={"synthetic:item": {"state": "closed"}},
    )

    with pytest.raises(Exception, match="trusted.*readback|preflight"):
        registry.validate_readback_window(
            baseline=baseline,
            final=fabricated,
            final_visible_at=[datetime.now(UTC) - timedelta(seconds=3)],
            delivered_at=[datetime.now(UTC) - timedelta(seconds=2)],
            action_at=[datetime.now(UTC) - timedelta(seconds=1)],
        )


def test_rollup_and_report_api_do_not_accept_caller_scope_or_evidence() -> None:
    policy = _policy_module()
    rollup_signature = inspect.signature(
        policy.TrustedAcceptanceRegistry.calculate_rollups
    )
    report_signature = inspect.signature(policy.TrustedAcceptanceRegistry.write_report)

    assert list(rollup_signature.parameters) == ["self"]
    assert list(report_signature.parameters) == ["self", "output_path"]
    forbidden = {
        "scope_criterion_ids",
        "planned_execution_ids",
        "results",
        "evidence_root",
        "final_readback",
        "verified_refs",
    }
    assert forbidden.isdisjoint(rollup_signature.parameters)
    assert forbidden.isdisjoint(report_signature.parameters)


def test_partial_scope_and_execution_cannot_be_supplied_to_rollup() -> None:
    policy = _policy_module()
    registry = policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)

    with pytest.raises(TypeError):
        registry.calculate_rollups(
            scope_criterion_ids=["AC-01"],
            planned_execution_ids=["SC-OPEN-EN"],
        )


def test_report_output_rejects_intermediate_parent_symlink(tmp_path: Path) -> None:
    policy = _policy_module()
    registry = policy.TrustedAcceptanceRegistry.open_contracts(PROJECT_ROOT)
    outside = tmp_path / "outside"
    outside.mkdir()
    safe = tmp_path / "safe"
    safe.mkdir()
    (safe / "redirect").symlink_to(outside, target_is_directory=True)

    with pytest.raises(policy.PolicyValidationError, match="symlink|no-follow"):
        registry.write_report(safe / "redirect" / "report.md")

    assert not (outside / "report.md").exists()
