"""Typed contracts for the Noor E2E acceptance preparation manifests."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Reject undeclared state so contract drift is observable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    EXCLUDED_BY_CLIENT = "EXCLUDED_BY_CLIENT"


class EvidenceMode(StrEnum):
    FRESH = "fresh"
    REUSED_EXACT = "reused_exact"
    EXTERNAL_GATE = "external_gate"


class AuthorizationStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REVOKED = "revoked"


class FreshEvidenceRequirement(StrEnum):
    BEADS_ISSUE_CLOSED = "beads_issue_closed"
    DEPLOYED_RELEASE_IDENTITY = "deployed_release_identity"
    RUNTIME_MODEL_SERVICE_READBACK = "runtime_model_service_readback"
    PROVIDER_SMOKE_5_OF_5 = "provider_smoke_5_of_5"
    MANUAL_SEMANTIC_REVIEW_PASS = "manual_semantic_review_pass"


class ClientEvidenceRequirement(StrEnum):
    APPROVED_IMPLEMENTATION_OR_EXCLUSION = (
        "client-approved implementation evidence or explicit client exclusion"
    )
    EXACT_SYNTHETIC_REWARD_AUTHORIZATION = "exact synthetic reward authorization"


class CriterionIdentity(StrictModel):
    criterion_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    text_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ScopeSnapshot(StrictModel):
    schema_version: Literal["scope-criterion-snapshot/v1"]
    goal_id: Literal["tj-ee5f"]
    source_kind: Literal["beads"]
    source_id: Literal["tj-ee5f"]
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    criteria: list[CriterionIdentity] = Field(min_length=1)


class SourceSection(StrictModel):
    start_locator: str = Field(min_length=1)
    end_locator: str | None
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceReference(StrictModel):
    path: str = Field(min_length=1)
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sections: list[SourceSection] = Field(min_length=1)


class PrecedenceDecision(StrictModel):
    disposition: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    supersedes: list[str] = Field(default_factory=list)


class ObservableOracle(StrictModel):
    checks: list[str] = Field(min_length=1)
    failure_condition: str = Field(min_length=1)


class DependencyGate(StrictModel):
    issue_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    required_outcome: Outcome
    evidence_required: list[FreshEvidenceRequirement | ClientEvidenceRequirement] = (
        Field(min_length=1)
    )


class TraceabilityCriterion(StrictModel):
    criterion_id: str = Field(min_length=1)
    criterion_text_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sources: list[str] = Field(min_length=1)
    precedence: PrecedenceDecision
    oracle: ObservableOracle
    evidence_mode: EvidenceMode
    freshness_identity: list[str] = Field(min_length=1)
    owner: str = Field(min_length=1)
    scenario_ids: list[str] = Field(default_factory=list)
    evidence_block_ids: list[str] = Field(default_factory=list)
    accepted_regressions: list[str] = Field(default_factory=list)
    open_known_risks: list[str] = Field(default_factory=list)
    dependency: DependencyGate | None = None
    report_owner: str = Field(min_length=1)

    @model_validator(mode="after")
    def _has_evidence_owner(self) -> TraceabilityCriterion:
        if not self.scenario_ids and not self.evidence_block_ids:
            raise ValueError(
                "traceability criterion needs a scenario or evidence block"
            )
        return self


class TraceabilityManifest(StrictModel):
    schema_version: Literal["noor-e2e-traceability/v1"]
    goal_id: Literal["tj-ee5f"]
    scope_source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope_provenance_path: str = Field(min_length=1)
    scope_provenance_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    precedence_order: list[str] = Field(min_length=1)
    outcome_values: list[Outcome]
    evidence_mode_values: list[EvidenceMode]
    source_registry: dict[str, SourceReference]
    criteria: list[TraceabilityCriterion] = Field(min_length=1)


ScenarioKind = Literal[
    "isolated_customer",
    "high_risk_paraphrase",
    "longitudinal_customer",
    "provider_canary",
]
ScenarioLanguage = Literal["en", "ar", "mixed", "n/a"]


class ScenarioDefinition(StrictModel):
    scenario_id: str = Field(min_length=1)
    kind: ScenarioKind
    language: ScenarioLanguage
    variant_family: str | None = None
    persona: str = Field(min_length=1)
    starting_state: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    facts: list[str] = Field(min_length=1)
    checkpoints: list[str] = Field(min_length=1)
    prohibited_outcomes: list[str] = Field(min_length=1)
    stop_conditions: list[str] = Field(min_length=1)
    readbacks: list[str] = Field(min_length=1)
    criterion_ids: list[str] = Field(min_length=1)
    required_permissions: list[str]
    report_owner: str = Field(min_length=1)


EvidenceBlockKind = Literal[
    "runtime",
    "admin",
    "quality",
    "load",
    "security",
    "backup",
    "availability",
    "catalog_coverage",
    "referral",
]


class EvidenceBlockDefinition(StrictModel):
    block_id: str = Field(min_length=1)
    kind: EvidenceBlockKind
    evidence_mode: EvidenceMode
    criterion_ids: list[str] = Field(min_length=1)
    oracle_checks: list[str] = Field(min_length=1)
    freshness_identity: list[str] = Field(min_length=1)
    stop_conditions: list[str] = Field(min_length=1)
    required_permissions: list[str]
    report_owner: str = Field(min_length=1)
    external_gate: str | None = None


class ScenarioSet(StrictModel):
    schema_version: Literal["noor-e2e-scenario-set/v1"]
    goal_id: Literal["tj-ee5f"]
    scenario_set_version: str = Field(min_length=1)
    deterministic_seed: int = Field(ge=0)
    scenarios: list[ScenarioDefinition] = Field(min_length=1)
    evidence_blocks: list[EvidenceBlockDefinition] = Field(min_length=1)


class RuntimeIdentity(StrictModel):
    repository_commit: str = Field(min_length=1)
    deployed_release_sha: str = Field(min_length=1)
    ci_run_id: str = Field(min_length=1)
    endpoint: str = Field(pattern=r"^https://")
    app_version: str = Field(min_length=1)
    migration_head: str = Field(min_length=1)
    main_model: str = Field(min_length=1)
    fast_model: str = Field(min_length=1)


class AuthorizationTargets(StrictModel):
    recipient: str = Field(min_length=1)
    wazzup_channel: str = Field(min_length=1)
    telegram_target: str = Field(min_length=1)
    synthetic_suffix: str = Field(min_length=1)


class AuthorizationQuotas(StrictModel):
    max_scenarios: int = Field(ge=0)
    max_messages: int = Field(ge=0)
    max_model_calls: int = Field(ge=0)
    max_cost_usd: float = Field(ge=0)
    subsystem_quotas: dict[str, int]

    @model_validator(mode="after")
    def _non_negative_subsystem_quotas(self) -> AuthorizationQuotas:
        if not self.subsystem_quotas:
            raise ValueError("subsystem quotas must be explicit")
        if any(value < 0 for value in self.subsystem_quotas.values()):
            raise ValueError("subsystem quotas must be non-negative")
        return self


class ScenarioExecutionBinding(StrictModel):
    scenario_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    scenario_set_version: str = Field(min_length=1)
    deterministic_seed: int = Field(ge=0)
    scenario_ids: list[str] = Field(min_length=1)
    evidence_block_ids: list[str] = Field(min_length=1)
    executable_input_digests: dict[str, str]

    @model_validator(mode="after")
    def _explicit_executable_inputs(self) -> ScenarioExecutionBinding:
        if not self.executable_input_digests:
            raise ValueError("executable input digests must be explicit")
        if any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.executable_input_digests.values()
        ):
            raise ValueError("executable input digests must be SHA-256 hex values")
        return self


class AuthorizationManifest(StrictModel):
    schema_version: Literal["noor-e2e-authorization/v1"]
    authorization_id: str = Field(min_length=1)
    status: AuthorizationStatus
    issuer: str = Field(min_length=1)
    issued_at: datetime
    expires_at: datetime
    allowed_executor: str = Field(min_length=1)
    allowed_source: str = Field(min_length=1)
    expected_identity: RuntimeIdentity
    targets: AuthorizationTargets
    quotas: AuthorizationQuotas
    permissions: list[str]
    callback_types: list[str]
    test_data_identities: list[str] = Field(min_length=1)
    cleanup_method: str = Field(min_length=1)
    readbacks: list[str] = Field(min_length=1)
    stop_conditions: list[str] = Field(min_length=1)
    scenario_binding: ScenarioExecutionBinding

    @model_validator(mode="after")
    def _valid_window(self) -> AuthorizationManifest:
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("authorization timestamps must be timezone-aware")
        if self.expires_at <= self.issued_at:
            raise ValueError("authorization expiry must follow issue time")
        return self


class PreflightObservation(StrictModel):
    identity: RuntimeIdentity
    targets: AuthorizationTargets
    executor: str = Field(min_length=1)
    source: str = Field(min_length=1)


class PreflightRequest(StrictModel):
    quotas: AuthorizationQuotas
    permissions: list[str]
    callback_types: list[str]
    test_data_identities: list[str]
    cleanup_method: str = Field(min_length=1)
    readbacks: list[str]
    stop_conditions: list[str]
    scenario_binding: ScenarioExecutionBinding


class FrozenBeadsRecord(StrictModel):
    issue_id: Literal["tj-ee5f", "tj-ee5f.1"]
    canonical_record: dict[str, Any]
    canonical_record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ScopeSourceProvenance(StrictModel):
    schema_version: Literal["scope-source-provenance/v1"]
    goal_id: Literal["tj-ee5f"]
    scope_anchor_path: Literal[".codex/goals/tj-ee5f/scope-criterion-snapshot.json"]
    criteria_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    anchor_creation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    anchor_blob_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    beads_records: list[FrozenBeadsRecord] = Field(min_length=2, max_length=2)
    beads_records_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CriterionResult(StrictModel):
    criterion_id: str = Field(min_length=1)
    outcome: Outcome
    evidence_mode: EvidenceMode
    evidence_refs: list[str]
