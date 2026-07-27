"""Code-owned execution-policy compiler and acceptance trust center."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from scripts.e2e_acceptance.manifest import (
    ManifestValidationError,
    load_scenario_set,
    load_scope_provenance,
    load_scope_snapshot,
    load_traceability_manifest,
    validate_contract_bundle,
)
from scripts.e2e_acceptance.schemas import EvidenceMode

_SCOPE_PATH = Path(".codex/goals/tj-ee5f/scope-criterion-snapshot.json")
_PROVENANCE_PATH = Path(".codex/goals/tj-ee5f/scope-source-provenance.json")
_TRACEABILITY_PATH = Path(".codex/stages/tj-ee5f/traceability-manifest.json")
_SCENARIO_SET_PATH = Path(".codex/stages/tj-ee5f/scenario-set.json")
_TASK1_AUTHORIZATION_PATH = Path(
    ".codex/stages/tj-ee5f/authorization-manifest.example.json"
)
_POLICY_PATH = Path(".codex/stages/tj-ee5f/execution-policy-v2.json")
_POLICY_SHA256 = "4c36af96ea2ad304265fe72d1ca75b57b1105f0a03b25148d0d664501ab67b2c"


class PolicyValidationError(ValueError):
    """A policy, trusted registry input, or output boundary is unsafe."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


OracleKind = Literal[
    "structured_event",
    "classifier_result",
    "authorization_permission",
    "independent_readback",
    "structured_evidence",
    "reused_exact_evidence",
    "external_gate_evidence",
]


class OracleSpec(_StrictModel):
    kind: OracleKind
    decisive: Literal[True]
    classifier_id: str | None = None
    allowed_producers: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _classifier_contract(self) -> OracleSpec:
        if (self.kind == "classifier_result") != (self.classifier_id is not None):
            raise ValueError("classifier oracle identity is inconsistent")
        return self


class AssertionSpec(_StrictModel):
    assertion_id: str = Field(min_length=1)
    canonical_text: str = Field(min_length=1)
    source_text_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    structured_required: Literal[True]
    oracle_id: str = Field(min_length=1)


class CapabilitySpec(_StrictModel):
    name: str = Field(min_length=1)
    oracle_id: str = Field(min_length=1)


class ScenarioPolicySpec(_StrictModel):
    scenario_id: str = Field(min_length=1)
    checkpoints: tuple[AssertionSpec, ...] = Field(min_length=1)
    prohibited_outcomes: tuple[AssertionSpec, ...] = Field(min_length=1)
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    required_permissions: tuple[CapabilitySpec, ...]
    required_readbacks: tuple[CapabilitySpec, ...] = Field(min_length=1)


class EvidenceBlockPolicySpec(_StrictModel):
    block_id: str = Field(min_length=1)
    oracle_checks: tuple[AssertionSpec, ...] = Field(min_length=1)
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    required_permissions: tuple[CapabilitySpec, ...]


class CriterionPolicySpec(_StrictModel):
    criterion_id: str = Field(min_length=1)
    evidence_mode: EvidenceMode
    oracle_checks: tuple[AssertionSpec, ...] = Field(min_length=1)
    failure_condition: str = Field(min_length=1)
    scenario_ids: tuple[str, ...]
    evidence_block_ids: tuple[str, ...]


class ExecutionPolicyManifest(_StrictModel):
    schema_version: Literal["noor-e2e-execution-policy/v2"]
    dsl_version: Literal["noor-e2e-oracle-dsl/v2"]
    policy_version: str = Field(min_length=1)
    scenario_set_version: str = Field(min_length=1)
    oracle_registry: dict[str, OracleSpec]
    scenarios: tuple[ScenarioPolicySpec, ...] = Field(min_length=1)
    evidence_blocks: tuple[EvidenceBlockPolicySpec, ...] = Field(min_length=1)
    criteria: tuple[CriterionPolicySpec, ...] = Field(min_length=1)


_CODE_OWNED_REGISTRY: dict[str, OracleSpec] = {
    "checkpoint.structured.v2": OracleSpec(
        kind="structured_event",
        decisive=True,
        allowed_producers=(
            "runtime-event-source",
            "audit-event-source",
            "production-policy-classifier",
        ),
    ),
    "prohibited.classifier.v2": OracleSpec(
        kind="classifier_result",
        decisive=True,
        classifier_id="scenario_policy.v2",
        allowed_producers=("production-policy-classifier",),
    ),
    "manager_faithfulness.v1": OracleSpec(
        kind="classifier_result",
        decisive=True,
        classifier_id="manager_faithfulness.v1",
        allowed_producers=("production-manager-fidelity-classifier",),
    ),
    "permission.authorization.v2": OracleSpec(
        kind="authorization_permission",
        decisive=True,
        allowed_producers=("validated-authorization-manifest",),
    ),
    "readback.independent.v2": OracleSpec(
        kind="independent_readback",
        decisive=True,
        allowed_producers=("independent-readback-collector",),
    ),
    "criterion.fresh.v2": OracleSpec(
        kind="structured_evidence",
        decisive=True,
        allowed_producers=(
            "runtime-event-source",
            "audit-event-source",
            "production-policy-classifier",
            "independent-readback-collector",
        ),
    ),
    "criterion.reused_exact.v2": OracleSpec(
        kind="reused_exact_evidence",
        decisive=True,
        allowed_producers=("trusted-evidence-registry",),
    ),
    "criterion.external_gate.v2": OracleSpec(
        kind="external_gate_evidence",
        decisive=True,
        allowed_producers=("trusted-evidence-registry",),
    ),
    "block.oracle.v2": OracleSpec(
        kind="independent_readback",
        decisive=True,
        allowed_producers=(
            "independent-readback-collector",
            "trusted-evidence-registry",
        ),
    ),
}


class CompiledAssertion(_StrictModel):
    assertion_id: str
    canonical_text: str
    source_text_digest: str
    structured_required: Literal[True]
    oracle_id: str
    oracle: OracleSpec


class CompiledScenario(_StrictModel):
    scenario_id: str
    checkpoints: dict[str, CompiledAssertion]
    prohibited_outcomes: dict[str, CompiledAssertion]
    criterion_ids: tuple[str, ...]
    required_permissions: tuple[str, ...]
    required_readbacks: tuple[str, ...]


class CompiledEvidenceBlock(_StrictModel):
    block_id: str
    oracle_checks: dict[str, CompiledAssertion]
    criterion_ids: tuple[str, ...]
    required_permissions: tuple[str, ...]


class CompiledCriterion(_StrictModel):
    criterion_id: str
    evidence_mode: EvidenceMode
    oracle_checks: dict[str, CompiledAssertion]
    failure_condition: str
    scenario_ids: tuple[str, ...]
    evidence_block_ids: tuple[str, ...]
    allows_client_exclusion: bool


class CompiledPolicy(_StrictModel):
    policy_version: str
    dsl_version: str
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    scenarios: dict[str, CompiledScenario]
    evidence_blocks: dict[str, CompiledEvidenceBlock]
    criteria: dict[str, CompiledCriterion]
    assertions: dict[str, CompiledAssertion]


class _EvidenceItem(_StrictModel):
    assertion_id: str
    producer: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    passed: bool
    reason: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    attempt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def build(cls, **values: Any) -> _EvidenceItem:
        identity = {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in values.items()
        }
        return cls(**values, artifact_digest=_canonical_digest(identity))

    @model_validator(mode="after")
    def _aware_time(self) -> _EvidenceItem:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("oracle evidence timestamp must be timezone-aware")
        identity = self.model_dump(mode="python", exclude={"artifact_digest"})
        identity["observed_at"] = self.observed_at.isoformat()
        if self.artifact_digest != _canonical_digest(identity):
            raise ValueError("oracle evidence artifact digest mismatch")
        return self


class StructuredEvent(_EvidenceItem):
    pass


class ToolResult(_EvidenceItem):
    tool_name: str = Field(min_length=1)


class ReadbackResult(_EvidenceItem):
    collector_id: str = Field(min_length=1)


class ClassifierResult(_StrictModel):
    assertion_id: str = Field(min_length=1)
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    attempt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    classifier_id: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    passed: bool
    reason: str = Field(min_length=1)
    artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def build(cls, **values: Any) -> ClassifierResult:
        identity = {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in values.items()
        }
        return cls(**values, artifact_digest=_canonical_digest(identity))

    @model_validator(mode="after")
    def _aware_time(self) -> ClassifierResult:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("classifier timestamp must be timezone-aware")
        identity = self.model_dump(mode="python", exclude={"artifact_digest"})
        identity["observed_at"] = self.observed_at.isoformat()
        if self.artifact_digest != _canonical_digest(identity):
            raise ValueError("classifier artifact digest mismatch")
        return self


class OracleEvidence(_StrictModel):
    assertion_id: str = Field(min_length=1)
    structured_events: tuple[StructuredEvent, ...]
    tool_results: tuple[ToolResult, ...]
    readbacks: tuple[ReadbackResult, ...]
    classifier_results: tuple[ClassifierResult, ...]
    text_supplements: tuple[str, ...]


class OracleDecision(_StrictModel):
    assertion_id: str
    passed: bool
    decisive_evidence_kind: str
    reason: str


ReadbackPhase = Literal["baseline", "final"]


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class ReadbackObservation(_StrictModel):
    schema_version: Literal["noor-e2e-readback/v2"]
    phase: ReadbackPhase
    collector_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    preflight_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    collector_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    causal_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    inventory: dict[str, dict[str, Any]] = Field(min_length=1)

    @classmethod
    def build(
        cls,
        *,
        phase: ReadbackPhase,
        collector_id: str,
        source_id: str,
        run_id: str,
        preflight_digest: str,
        collector_artifact_digest: str,
        causal_event_digest: str,
        observed_at: datetime,
        inventory: dict[str, dict[str, Any]],
    ) -> ReadbackObservation:
        identity = {
            "schema_version": "noor-e2e-readback/v2",
            "phase": phase,
            "collector_id": collector_id,
            "source_id": source_id,
            "run_id": run_id,
            "preflight_digest": preflight_digest,
            "collector_artifact_digest": collector_artifact_digest,
            "causal_event_digest": causal_event_digest,
            "observed_at": observed_at.isoformat(),
            "inventory": inventory,
        }
        return cls(
            **identity,
            content_digest=_canonical_digest(identity),
        )

    @model_validator(mode="after")
    def _identity_is_valid(self) -> ReadbackObservation:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("readback timestamp must be timezone-aware")
        identity = {
            "schema_version": self.schema_version,
            "phase": self.phase,
            "collector_id": self.collector_id,
            "source_id": self.source_id,
            "run_id": self.run_id,
            "preflight_digest": self.preflight_digest,
            "collector_artifact_digest": self.collector_artifact_digest,
            "causal_event_digest": self.causal_event_digest,
            "observed_at": self.observed_at.isoformat(),
            "inventory": self.inventory,
        }
        if self.content_digest != _canonical_digest(identity):
            raise ValueError("readback content digest mismatch")
        return self


def _safe_json(repo_root: Path, relative: Path) -> tuple[dict[str, Any], bytes]:
    if not repo_root.is_absolute() or repo_root.is_symlink() or not repo_root.is_dir():
        raise PolicyValidationError(
            "repository root must be an absolute real directory"
        )
    parts = relative.parts
    if (
        not parts
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise PolicyValidationError("trusted policy path is unsafe")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    root_fd = os.open(repo_root, os.O_RDONLY | directory | nofollow)
    current_fd = root_fd
    try:
        for part in parts[:-1]:
            child_fd = os.open(
                part,
                os.O_RDONLY | directory | nofollow,
                dir_fd=current_fd,
            )
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = child_fd
        file_fd = os.open(parts[-1], os.O_RDONLY | nofollow, dir_fd=current_fd)
        try:
            chunks: list[bytes] = []
            while True:
                chunk = os.read(file_fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(file_fd)
    except OSError as exc:
        raise PolicyValidationError(f"trusted policy path is unsafe: {exc}") from exc
    finally:
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)
    payload = b"".join(chunks)
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicyValidationError("execution policy is not valid JSON") from exc
    if not isinstance(value, dict):
        raise PolicyValidationError("execution policy root must be an object")
    return value, payload


def _unique_by_id[T](items: Sequence[T], field: str, label: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for item in items:
        identity = getattr(item, field)
        if identity in result:
            raise PolicyValidationError(f"duplicate {label}: {identity}")
        result[identity] = item
    return result


def _compile_assertions(
    items: Sequence[AssertionSpec],
    registry: Mapping[str, OracleSpec],
    seen_assertion_ids: set[str],
) -> dict[str, CompiledAssertion]:
    compiled: dict[str, CompiledAssertion] = {}
    for item in items:
        if item.canonical_text in compiled:
            raise PolicyValidationError(
                f"duplicate canonical assertion text: {item.canonical_text}"
            )
        if item.assertion_id in seen_assertion_ids:
            raise PolicyValidationError(
                f"duplicate policy assertion ID: {item.assertion_id}"
            )
        oracle = registry.get(item.oracle_id)
        if oracle is None:
            raise PolicyValidationError(f"unknown code-owned oracle: {item.oracle_id}")
        seen_assertion_ids.add(item.assertion_id)
        expected_text_digest = hashlib.sha256(
            item.canonical_text.encode("utf-8")
        ).hexdigest()
        if item.source_text_digest != expected_text_digest:
            raise PolicyValidationError(
                f"source text digest drift: {item.assertion_id}"
            )
        compiled[item.canonical_text] = CompiledAssertion(
            assertion_id=item.assertion_id,
            canonical_text=item.canonical_text,
            source_text_digest=item.source_text_digest,
            structured_required=item.structured_required,
            oracle_id=item.oracle_id,
            oracle=oracle,
        )
    return compiled


def _exact_list(
    label: str, policy_values: Sequence[str], canonical: Sequence[str]
) -> None:
    if len(policy_values) != len(set(policy_values)) or tuple(policy_values) != tuple(
        canonical
    ):
        raise PolicyValidationError(f"{label} canonical binding drift")


def _compile_policy(repo_root: Path) -> CompiledPolicy:
    snapshot = load_scope_snapshot(repo_root / _SCOPE_PATH)
    provenance = load_scope_provenance(
        repo_root / _PROVENANCE_PATH,
        snapshot=snapshot,
        repo_root=repo_root,
    )
    traceability = load_traceability_manifest(repo_root / _TRACEABILITY_PATH)
    scenario_set = load_scenario_set(repo_root / _SCENARIO_SET_PATH)
    validate_contract_bundle(snapshot, provenance, traceability, scenario_set)

    raw, payload = _safe_json(repo_root, _POLICY_PATH)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != _POLICY_SHA256:
        raise PolicyValidationError("code-owned execution policy digest drift")
    try:
        manifest = ExecutionPolicyManifest.model_validate(raw)
    except ValidationError as exc:
        raise PolicyValidationError(f"invalid execution policy: {exc}") from exc
    if manifest.oracle_registry != _CODE_OWNED_REGISTRY:
        raise PolicyValidationError("code-owned capability/oracle registry drift")
    if manifest.scenario_set_version != scenario_set.scenario_set_version:
        raise PolicyValidationError("execution policy scenario-set version drift")

    policy_scenarios = _unique_by_id(manifest.scenarios, "scenario_id", "scenario")
    canonical_scenarios = {item.scenario_id: item for item in scenario_set.scenarios}
    if set(policy_scenarios) != set(canonical_scenarios):
        raise PolicyValidationError("execution policy scenario scope drift")

    policy_blocks = _unique_by_id(
        manifest.evidence_blocks, "block_id", "evidence block"
    )
    canonical_blocks = {item.block_id: item for item in scenario_set.evidence_blocks}
    if set(policy_blocks) != set(canonical_blocks):
        raise PolicyValidationError("execution policy evidence-block scope drift")

    policy_criteria = _unique_by_id(manifest.criteria, "criterion_id", "criterion")
    canonical_criteria = {item.criterion_id: item for item in traceability.criteria}
    if set(policy_criteria) != {item.criterion_id for item in snapshot.criteria}:
        raise PolicyValidationError("execution policy criterion scope drift")

    seen_assertion_ids: set[str] = set()
    compiled_scenarios: dict[str, CompiledScenario] = {}
    for identity, scenario_spec in policy_scenarios.items():
        canonical_scenario = canonical_scenarios[identity]
        _exact_list(
            f"{identity} checkpoints",
            [item.canonical_text for item in scenario_spec.checkpoints],
            canonical_scenario.checkpoints,
        )
        _exact_list(
            f"{identity} prohibited outcomes",
            [item.canonical_text for item in scenario_spec.prohibited_outcomes],
            canonical_scenario.prohibited_outcomes,
        )
        _exact_list(
            f"{identity} criteria",
            scenario_spec.criterion_ids,
            canonical_scenario.criterion_ids,
        )
        _exact_list(
            f"{identity} permissions",
            [item.name for item in scenario_spec.required_permissions],
            canonical_scenario.required_permissions,
        )
        _exact_list(
            f"{identity} readbacks",
            [item.name for item in scenario_spec.required_readbacks],
            canonical_scenario.readbacks,
        )
        for capability in (
            *scenario_spec.required_permissions,
            *scenario_spec.required_readbacks,
        ):
            oracle = manifest.oracle_registry.get(capability.oracle_id)
            if oracle is None:
                raise PolicyValidationError(
                    f"{identity} capability uses unknown oracle"
                )
            expected_kind = (
                "authorization_permission"
                if capability in scenario_spec.required_permissions
                else "independent_readback"
            )
            if oracle.kind != expected_kind:
                raise PolicyValidationError(f"{identity} capability oracle kind drift")
        compiled_scenarios[identity] = CompiledScenario(
            scenario_id=identity,
            checkpoints=_compile_assertions(
                scenario_spec.checkpoints,
                manifest.oracle_registry,
                seen_assertion_ids,
            ),
            prohibited_outcomes=_compile_assertions(
                scenario_spec.prohibited_outcomes,
                manifest.oracle_registry,
                seen_assertion_ids,
            ),
            criterion_ids=scenario_spec.criterion_ids,
            required_permissions=tuple(
                item.name for item in scenario_spec.required_permissions
            ),
            required_readbacks=tuple(
                item.name for item in scenario_spec.required_readbacks
            ),
        )

    compiled_blocks: dict[str, CompiledEvidenceBlock] = {}
    for identity, block_spec in policy_blocks.items():
        canonical_block = canonical_blocks[identity]
        _exact_list(
            f"{identity} oracle checks",
            [item.canonical_text for item in block_spec.oracle_checks],
            canonical_block.oracle_checks,
        )
        _exact_list(
            f"{identity} criteria",
            block_spec.criterion_ids,
            canonical_block.criterion_ids,
        )
        _exact_list(
            f"{identity} permissions",
            [item.name for item in block_spec.required_permissions],
            canonical_block.required_permissions,
        )
        compiled_blocks[identity] = CompiledEvidenceBlock(
            block_id=identity,
            oracle_checks=_compile_assertions(
                block_spec.oracle_checks,
                manifest.oracle_registry,
                seen_assertion_ids,
            ),
            criterion_ids=block_spec.criterion_ids,
            required_permissions=tuple(
                item.name for item in block_spec.required_permissions
            ),
        )

    compiled_criteria: dict[str, CompiledCriterion] = {}
    for identity, criterion_spec in policy_criteria.items():
        canonical_criterion = canonical_criteria[identity]
        _exact_list(
            f"{identity} oracle checks",
            [item.canonical_text for item in criterion_spec.oracle_checks],
            canonical_criterion.oracle.checks,
        )
        _exact_list(
            f"{identity} scenarios",
            criterion_spec.scenario_ids,
            canonical_criterion.scenario_ids,
        )
        _exact_list(
            f"{identity} evidence blocks",
            criterion_spec.evidence_block_ids,
            canonical_criterion.evidence_block_ids,
        )
        if (
            criterion_spec.evidence_mode is not canonical_criterion.evidence_mode
            or criterion_spec.failure_condition
            != canonical_criterion.oracle.failure_condition
        ):
            raise PolicyValidationError(f"{identity} oracle contract drift")
        compiled_criteria[identity] = CompiledCriterion(
            criterion_id=identity,
            evidence_mode=criterion_spec.evidence_mode,
            oracle_checks=_compile_assertions(
                criterion_spec.oracle_checks,
                manifest.oracle_registry,
                seen_assertion_ids,
            ),
            failure_condition=criterion_spec.failure_condition,
            scenario_ids=criterion_spec.scenario_ids,
            evidence_block_ids=criterion_spec.evidence_block_ids,
            allows_client_exclusion=bool(
                canonical_criterion.dependency
                and canonical_criterion.dependency.resolution_outcomes
                and any(
                    resolution.value == "excluded_by_client"
                    and outcome.value == "EXCLUDED_BY_CLIENT"
                    for resolution, outcome in (
                        canonical_criterion.dependency.resolution_outcomes.items()
                    )
                )
            ),
        )

    all_assertions = {
        item.assertion_id: item
        for scenario in compiled_scenarios.values()
        for group in (scenario.checkpoints, scenario.prohibited_outcomes)
        for item in group.values()
    }
    all_assertions.update(
        {
            item.assertion_id: item
            for block in compiled_blocks.values()
            for item in block.oracle_checks.values()
        }
    )
    all_assertions.update(
        {
            item.assertion_id: item
            for criterion in compiled_criteria.values()
            for item in criterion.oracle_checks.values()
        }
    )
    if set(all_assertions) != seen_assertion_ids:
        raise PolicyValidationError("compiled assertion registry drift")
    return CompiledPolicy(
        policy_version=manifest.policy_version,
        dsl_version=manifest.dsl_version,
        policy_digest=digest,
        scenarios=compiled_scenarios,
        evidence_blocks=compiled_blocks,
        criteria=compiled_criteria,
        assertions=all_assertions,
    )


def _open_output_parent(output_path: Path) -> tuple[int, str]:
    if not output_path.is_absolute():
        raise PolicyValidationError("report output path must be absolute")
    parts = output_path.parts
    if len(parts) < 2 or any(part in {"", ".", ".."} for part in parts[1:]):
        raise PolicyValidationError("report output path is unsafe")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    current_fd = os.open("/", os.O_RDONLY | directory | nofollow)
    try:
        for part in parts[1:-1]:
            next_fd = os.open(
                part,
                os.O_RDONLY | directory | nofollow,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
    except OSError as exc:
        os.close(current_fd)
        raise PolicyValidationError(
            f"report parent violates no-follow/symlink policy: {exc}"
        ) from exc
    return current_fd, parts[-1]


class TrustedAcceptanceRegistry:
    """Single trust center for canonical policy, evidence, rollups, and reports."""

    def __init__(self, *, repo_root: Path, compiled_policy: CompiledPolicy) -> None:
        from scripts.e2e_acceptance.execution import build_compiled_plan

        self._repo_root = repo_root
        self.compiled_policy = compiled_policy
        self.compiled_plan = build_compiled_plan(compiled_policy)
        self.registry_id = _canonical_digest(
            {
                "schema_version": "noor-e2e-trusted-registry/v2",
                "policy_digest": compiled_policy.policy_digest,
                "compiled_plan_digest": self.compiled_plan.plan_digest,
                "compiler_id": self.compiled_plan.compiler_id,
            }
        )
        self._assertions = compiled_policy.assertions
        self._verified_rollups: dict[str, bool] | None = None
        self._report_bytes: bytes | None = None
        self._trusted_authorization_digests: set[str] = set()
        self._trusted_authorizations: dict[str, object] = {}
        self._trusted_readback_digests: set[str] = set()
        self._trusted_classifier_digests: set[str] = set()
        self._trusted_structured_digests: set[str] = set()
        task1_paths = (
            _SCOPE_PATH,
            _PROVENANCE_PATH,
            _TRACEABILITY_PATH,
            _SCENARIO_SET_PATH,
        )
        self.task1_input_digests = {
            path.as_posix(): hashlib.sha256(_safe_json(repo_root, path)[1]).hexdigest()
            for path in task1_paths
        }
        self.task1_authorization_digest = hashlib.sha256(
            _safe_json(repo_root, _TASK1_AUTHORIZATION_PATH)[1]
        ).hexdigest()

    def classifier_evaluator_digest(self, assertion_id: str) -> str:
        assertion = self._assertions.get(assertion_id)
        if assertion is None or assertion.oracle.kind != "classifier_result":
            raise PolicyValidationError("classifier assertion identity is invalid")
        return _canonical_digest(
            {
                "schema_version": "noor-e2e-classifier-evaluator/v2",
                "assertion_id": assertion_id,
                "policy_digest": self.compiled_policy.policy_digest,
                "oracle_id": assertion.oracle_id,
                "oracle": assertion.oracle.model_dump(mode="json"),
            }
        )

    @classmethod
    def open_contracts(cls, repo_root: Path) -> TrustedAcceptanceRegistry:
        try:
            compiled = _compile_policy(repo_root)
        except ManifestValidationError as exc:
            raise PolicyValidationError(str(exc)) from exc
        return cls(repo_root=repo_root, compiled_policy=compiled)

    def evaluate_oracle(
        self,
        assertion_id: str,
        evidence: OracleEvidence,
    ) -> OracleDecision:
        assertion = self._assertions.get(assertion_id)
        if assertion is None or evidence.assertion_id != assertion_id:
            raise PolicyValidationError("oracle evidence assertion binding drift")
        oracle = assertion.oracle
        if oracle.kind == "classifier_result":
            matches = [
                item
                for item in evidence.classifier_results
                if item.assertion_id == assertion_id
                and item.policy_digest == self.compiled_policy.policy_digest
                and item.evaluator_digest
                == self.classifier_evaluator_digest(assertion_id)
                and item.artifact_digest in self._trusted_classifier_digests
                and item.classifier_id == oracle.classifier_id
                and item.producer in oracle.allowed_producers
            ]
            if not matches:
                raise PolicyValidationError(
                    "required classifier assertion binding evidence is missing"
                )
            passed = all(item.passed for item in matches)
            return OracleDecision(
                assertion_id=assertion_id,
                passed=passed,
                decisive_evidence_kind="classifier_result",
                reason="; ".join(item.reason for item in matches),
            )
        structured_matches = [
            item
            for item in (
                *evidence.structured_events,
                *evidence.tool_results,
                *evidence.readbacks,
            )
            if item.assertion_id == assertion_id
            and item.producer in oracle.allowed_producers
            and item.artifact_digest in self._trusted_structured_digests
        ]
        if not structured_matches:
            raise PolicyValidationError(
                "required trusted structured artifact evidence is missing"
            )
        passed = all(item.passed for item in structured_matches)
        return OracleDecision(
            assertion_id=assertion_id,
            passed=passed,
            decisive_evidence_kind=oracle.kind,
            reason="; ".join(item.reason for item in structured_matches),
        )

    def validate_execution_authorization(self, authorization: object) -> None:
        from scripts.e2e_acceptance.execution import (
            authorization_digest,
            validate_execution_authorization,
        )

        validated = validate_execution_authorization(
            authorization,
            policy=self.compiled_policy,
            plan=self.compiled_plan,
            registry_id=self.registry_id,
        )
        if (
            validated.task1_authorization_digest != self.task1_authorization_digest
            or validated.task1_input_digests != self.task1_input_digests
        ):
            raise PolicyValidationError(
                "authorization Task 1 immutable bundle digest drift"
            )
        digest = authorization_digest(validated)
        if digest not in self._trusted_authorization_digests:
            raise PolicyValidationError(
                "trusted execution authorization has not been loaded"
            )

    def _load_execution_authorization(self, authorization: object) -> None:
        """Trust an authorization after a protected loader (or local test seam)."""

        from scripts.e2e_acceptance.execution import (
            authorization_digest,
            validate_execution_authorization,
        )

        validated = validate_execution_authorization(
            authorization,
            policy=self.compiled_policy,
            plan=self.compiled_plan,
            registry_id=self.registry_id,
        )
        if (
            validated.task1_authorization_digest != self.task1_authorization_digest
            or validated.task1_input_digests != self.task1_input_digests
        ):
            raise PolicyValidationError(
                "authorization Task 1 immutable bundle digest drift"
            )
        digest = authorization_digest(validated)
        self._trusted_authorization_digests.add(digest)
        self._trusted_authorizations[digest] = validated

    def _load_trusted_readback(self, observation: ReadbackObservation) -> None:
        if not self._trusted_authorizations:
            raise PolicyValidationError(
                "trusted authorization required before readback loading"
            )
        if not any(
            observation.preflight_digest == getattr(item, "preflight_digest", None)
            and observation.collector_artifact_digest
            == getattr(item, "readback_collector_digest", None)
            for item in self._trusted_authorizations.values()
        ):
            raise PolicyValidationError("preflight-bound readback collector drift")
        self._trusted_readback_digests.add(observation.content_digest)

    def _load_local_readback_fixture(self, observation: ReadbackObservation) -> None:
        """Test-only seam for temporal contract tests; never used by run loading."""

        if (
            observation.collector_id != "independent-readback-collector"
            or observation.preflight_digest != "8" * 64
            or observation.collector_artifact_digest != "9" * 64
        ):
            raise PolicyValidationError("local readback fixture binding drift")
        self._trusted_readback_digests.add(observation.content_digest)

    def _load_classifier_artifact(
        self,
        result: ClassifierResult,
        *,
        run_id: str,
        attempt_digest: str,
    ) -> None:
        if (
            result.run_id != run_id
            or result.attempt_digest != attempt_digest
            or result.policy_digest != self.compiled_policy.policy_digest
            or result.evaluator_digest
            != self.classifier_evaluator_digest(result.assertion_id)
            or not any(
                result.preflight_digest == getattr(item, "preflight_digest", None)
                for item in self._trusted_authorizations.values()
            )
        ):
            raise PolicyValidationError(
                "classifier run/attempt/preflight registry binding drift"
            )
        self._trusted_classifier_digests.add(result.artifact_digest)

    def _load_structured_artifact(
        self,
        result: _EvidenceItem,
        *,
        run_id: str,
        attempt_digest: str,
        preflight_digest: str,
    ) -> None:
        assertion = self._assertions.get(result.assertion_id)
        if (
            assertion is None
            or assertion.oracle.kind == "classifier_result"
            or result.producer not in assertion.oracle.allowed_producers
            or result.run_id != run_id
            or result.attempt_digest != attempt_digest
            or result.preflight_digest != preflight_digest
        ):
            raise PolicyValidationError(
                "structured artifact protected provenance binding drift"
            )
        self._trusted_structured_digests.add(result.artifact_digest)

    def _load_local_classifier_fixture(self, result: ClassifierResult) -> None:
        if (
            result.preflight_digest != "8" * 64
            or result.policy_digest != self.compiled_policy.policy_digest
            or result.evaluator_digest
            != self.classifier_evaluator_digest(result.assertion_id)
        ):
            raise PolicyValidationError("local classifier fixture binding drift")
        self._trusted_classifier_digests.add(result.artifact_digest)

    def validate_readback_window(
        self,
        *,
        baseline: ReadbackObservation,
        final: ReadbackObservation,
        final_visible_at: Sequence[datetime],
        delivered_at: Sequence[datetime],
        action_at: Sequence[datetime],
    ) -> None:
        if (
            baseline.content_digest not in self._trusted_readback_digests
            or final.content_digest not in self._trusted_readback_digests
        ):
            raise PolicyValidationError(
                "trusted preflight-bound readback artifacts are required"
            )
        if (
            baseline.run_id != final.run_id
            or baseline.preflight_digest != final.preflight_digest
            or baseline.collector_artifact_digest != final.collector_artifact_digest
        ):
            raise PolicyValidationError("preflight-bound readback identity drift")
        if baseline.phase != "baseline" or final.phase != "final":
            raise PolicyValidationError("baseline/final readback phase drift")
        if baseline.source_id == final.source_id:
            raise PolicyValidationError(
                "baseline and final readback source identities must be distinct"
            )
        if baseline.observed_at >= final.observed_at:
            raise PolicyValidationError("final readback must follow baseline")
        timeline = [*final_visible_at, *delivered_at, *action_at]
        if not timeline:
            raise PolicyValidationError("final readback timeline is empty")
        if any(item.tzinfo is None or item.utcoffset() is None for item in timeline):
            raise PolicyValidationError("readback timeline must be timezone-aware")
        if baseline.observed_at >= min(timeline):
            raise PolicyValidationError("baseline readback must precede every action")
        if final.observed_at < max(timeline):
            raise PolicyValidationError(
                "final readback must occur after every visible, delivery, and action time"
            )

    def calculate_rollups(self) -> dict[str, bool]:
        if self._verified_rollups is None:
            raise PolicyValidationError(
                "trusted run/evidence registry has not been loaded"
            )
        return dict(self._verified_rollups)

    def _load_verified_run_roots(
        self,
        tracked_root: Path,
        protected_root: Path,
    ) -> None:
        """Internal test seam; public callers must use the fixed run layout."""

        from scripts.e2e_acceptance.trusted_run import load_verified_run

        verified = load_verified_run(self, tracked_root, protected_root)
        self._verified_rollups = dict(verified.rollups)
        self._report_bytes = verified.report_bytes

    def open_run(
        self,
        *,
        run_id: str,
    ) -> None:
        if not run_id or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-._"
            for character in run_id.lower()
        ):
            raise PolicyValidationError("trusted run identity is unsafe")
        tracked_root = (
            self._repo_root / ".codex" / "stages" / "tj-ee5f" / "results" / run_id
        )
        protected_root = (
            Path.home()
            / ".local"
            / "state"
            / "treejar"
            / "noor-e2e-acceptance"
            / "protected-runs"
        )
        self._load_verified_run_roots(
            tracked_root,
            protected_root / run_id,
        )

    def write_report(self, output_path: Path) -> None:
        parent_fd, name = _open_output_parent(output_path)
        try:
            if self._report_bytes is None:
                raise PolicyValidationError(
                    "trusted typed report payload has not been loaded"
                )
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(name, flags, 0o600, dir_fd=parent_fd)
            except OSError as exc:
                raise PolicyValidationError(
                    f"report output violates exclusive no-follow policy: {exc}"
                ) from exc
            try:
                os.write(fd, self._report_bytes)
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            os.close(parent_fd)
