"""Typed contracts for the Noor E2E acceptance preparation manifests."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

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


class SourceReference(StrictModel):
    path: str = Field(min_length=1)
    section: str = Field(min_length=1)
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


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
    evidence_required: list[str] = Field(min_length=1)


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


class CriterionResult(StrictModel):
    criterion_id: str = Field(min_length=1)
    outcome: Outcome
    evidence_mode: EvidenceMode
    evidence_refs: list[str]
