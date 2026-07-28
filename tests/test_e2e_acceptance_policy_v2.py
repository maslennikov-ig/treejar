"""Invariant tests for the replanned generic acceptance trust center."""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.e2e_acceptance_backend import build_canonical_test_registry

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


def _fresh_checkout_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    remote: str,
    top_level: Path | None = None,
    common_dir: Path | None = None,
) -> tuple[object, Path]:
    policy = _policy_module()
    repo_root = tmp_path / "treejar"
    policy_path = repo_root / "scripts/e2e_acceptance/policy.py"
    policy_path.parent.mkdir(parents=True)
    policy_path.touch()
    expected_top_level = top_level or repo_root
    expected_common_dir = common_dir or repo_root / ".git"
    expected_common_dir.mkdir(parents=True, exist_ok=True)

    def canonical_run(
        command: list[str], **_: object
    ) -> subprocess.CompletedProcess[str]:
        if command[-1] == "--show-toplevel":
            return subprocess.CompletedProcess(
                command, 0, f"{expected_top_level}\n", ""
            )
        if command[-1] == "origin":
            return subprocess.CompletedProcess(command, 0, f"{remote}\n", "")
        if command[-1] == "--git-common-dir":
            return subprocess.CompletedProcess(
                command, 0, f"{expected_common_dir}\n", ""
            )
        raise AssertionError(f"unexpected git command: {command}")

    monkeypatch.setattr(policy, "__file__", str(policy_path))
    monkeypatch.setattr(policy.subprocess, "run", canonical_run)

    return policy, repo_root


@pytest.mark.parametrize(
    "remote",
    [
        "https://github.com/maslennikov-ig/treejar",
        "https://github.com/maslennikov-ig/treejar.git",
    ],
)
def test_canonical_https_origin_accepts_both_fresh_checkout_spellings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    remote: str,
) -> None:
    policy, repo_root = _fresh_checkout_identity(
        tmp_path,
        monkeypatch,
        remote=remote,
    )

    assert policy.TrustedAcceptanceRegistry._canonical_repo_root() == repo_root


@pytest.mark.parametrize(
    "remote",
    [
        "http://github.com/maslennikov-ig/treejar",
        "git@github.com:maslennikov-ig/treejar.git",
        "https://github.com/other-owner/treejar.git",
        "https://github.com/maslennikov-ig/other-repository.git",
        "https://github.com/maslennikov-ig/treejar.git?query=1",
        "https://github.com/maslennikov-ig/treejar.git#fragment",
        "https://user@github.com/maslennikov-ig/treejar.git",
    ],
)
def test_canonical_https_origin_rejects_noncanonical_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    remote: str,
) -> None:
    policy, _ = _fresh_checkout_identity(tmp_path, monkeypatch, remote=remote)

    with pytest.raises(policy.PolicyValidationError):
        policy.TrustedAcceptanceRegistry._canonical_repo_root()


@pytest.mark.parametrize("drift", ["top-level", "common-dir"])
def test_canonical_https_origin_rejects_fresh_checkout_path_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    repo_root = tmp_path / "treejar"
    top_level = tmp_path / "other-checkout" if drift == "top-level" else repo_root
    common_dir = tmp_path / "work/.git" if drift == "common-dir" else repo_root / ".git"
    policy, _ = _fresh_checkout_identity(
        tmp_path,
        monkeypatch,
        remote="https://github.com/maslennikov-ig/treejar.git",
        top_level=top_level,
        common_dir=common_dir,
    )

    with pytest.raises(policy.PolicyValidationError):
        policy.TrustedAcceptanceRegistry._canonical_repo_root()


@pytest.mark.parametrize("scenario_id", NON_OPEN_SCENARIOS)
def test_generic_compiler_accepts_each_non_open_scenario(scenario_id: str) -> None:
    registry = build_canonical_test_registry()

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
    registry = build_canonical_test_registry()
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

    registry = build_canonical_test_registry()
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
    registry = build_canonical_test_registry()
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
    context = registry._verified_evidence_context()
    registry._set_test_context(
        context.model_copy(
            update={
                "classifier_digests": context.classifier_digests
                | {result.artifact_digest}
            }
        )
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
    registry = build_canonical_test_registry()
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

    context = registry._verified_evidence_context()
    registry._set_test_context(
        context.model_copy(
            update={
                "readback_digests": context.readback_digests
                | {baseline.content_digest, stale_final.content_digest}
            }
        )
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
    registry = build_canonical_test_registry()
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
    registry = build_canonical_test_registry()

    with pytest.raises(TypeError):
        registry.calculate_rollups(
            scope_criterion_ids=["AC-01"],
            planned_execution_ids=["SC-OPEN-EN"],
        )


def test_report_output_rejects_intermediate_parent_symlink(tmp_path: Path) -> None:
    policy = _policy_module()
    registry = build_canonical_test_registry()
    outside = tmp_path / "outside"
    outside.mkdir()
    safe = tmp_path / "safe"
    safe.mkdir()
    (safe / "redirect").symlink_to(outside, target_is_directory=True)

    with pytest.raises(policy.PolicyValidationError, match="symlink|no-follow"):
        registry.write_report(safe / "redirect" / "report.md")

    assert not (outside / "report.md").exists()
