"""Protected local execution state for the Noor acceptance trust center."""

from __future__ import annotations

import hashlib
import json
import math
import os
import weakref
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, NoReturn, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from scripts.e2e_acceptance.evidence import (
    redact_payload,
    validate_redacted_payload,
)
from scripts.e2e_acceptance.manifest import validate_preflight
from scripts.e2e_acceptance.policy import (
    CompiledPolicy,
    OracleEvidence,
    ReadbackObservation,
    TrustedAcceptanceRegistry,
)
from scripts.e2e_acceptance.schemas import (
    AuthorizationManifest,
    EvidenceMode,
    PreflightObservation,
    PreflightRequest,
)

COMPILER_ID = "treejar.acceptance-policy-compiler.v2"
LOCAL_ADAPTER_IDS = ("fake-local-adapter",)
_MAX_PREFLIGHT_AGE = timedelta(minutes=15)
_MAX_FINAL_READBACK_AGE = timedelta(minutes=5)
_PHASES = (
    "prepared",
    "baseline_sealed",
    "executing",
    "final_turn_anchored",
    "final_readback_sealed",
    "evaluated",
    "attempt_committed",
)


class ExecutionValidationError(ValueError):
    """Protected execution state or authorization is invalid."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class CriterionPlan(_StrictModel):
    criterion_id: str
    evidence_mode: EvidenceMode
    aggregation: Literal["all_required"]
    scenario_ids: tuple[str, ...]
    evidence_block_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...] = Field(min_length=1)
    allows_client_exclusion: bool


class CompiledExecutionPlan(_StrictModel):
    schema_version: Literal["noor-e2e-compiled-plan/v2"]
    compiler_id: Literal["treejar.acceptance-policy-compiler.v2"]
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_ids: tuple[str, ...] = Field(min_length=29, max_length=29)
    criteria: dict[str, CriterionPlan]
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def build_compiled_plan(policy: CompiledPolicy) -> CompiledExecutionPlan:
    execution_ids = (*policy.scenarios.keys(), *policy.evidence_blocks.keys())
    if len(execution_ids) != 29 or len(set(execution_ids)) != 29:
        raise ExecutionValidationError("compiled execution scope must be exact 29")
    criteria: dict[str, CriterionPlan] = {}
    for criterion in policy.criteria.values():
        obligation_ids = (
            *criterion.scenario_ids,
            *criterion.evidence_block_ids,
        )
        if not obligation_ids or len(obligation_ids) != len(set(obligation_ids)):
            raise ExecutionValidationError(
                f"criterion obligations are invalid: {criterion.criterion_id}"
            )
        if not set(obligation_ids) <= set(execution_ids):
            raise ExecutionValidationError(
                f"criterion obligation is outside execution plan: "
                f"{criterion.criterion_id}"
            )
        criteria[criterion.criterion_id] = CriterionPlan(
            criterion_id=criterion.criterion_id,
            evidence_mode=criterion.evidence_mode,
            aggregation="all_required",
            scenario_ids=criterion.scenario_ids,
            evidence_block_ids=criterion.evidence_block_ids,
            obligation_ids=obligation_ids,
            allows_client_exclusion=criterion.allows_client_exclusion,
        )
    if len(criteria) != 30:
        raise ExecutionValidationError("compiled criterion scope must be exact 30")
    identity = {
        "schema_version": "noor-e2e-compiled-plan/v2",
        "compiler_id": COMPILER_ID,
        "policy_digest": policy.policy_digest,
        "execution_ids": execution_ids,
        "criteria": {
            key: value.model_dump(mode="json") for key, value in criteria.items()
        },
    }
    return CompiledExecutionPlan(
        **identity,
        plan_digest=_digest(identity),
    )


OutcomeValue = Literal["PASS", "FAIL", "BLOCKED", "EXCLUDED_BY_CLIENT"]


def aggregate_criterion_outcome(
    plan: CriterionPlan,
    outcomes: dict[str, OutcomeValue],
    *,
    valid_exclusions: frozenset[str],
) -> OutcomeValue:
    unknown = set(outcomes) - set(plan.obligation_ids)
    if unknown:
        raise ExecutionValidationError(
            f"criterion outcome contains unknown obligations: {sorted(unknown)}"
        )
    missing = set(plan.obligation_ids) - set(outcomes)
    if missing:
        return "BLOCKED"
    if any(value == "FAIL" for value in outcomes.values()):
        return "FAIL"
    excluded = {
        identity
        for identity, value in outcomes.items()
        if value == "EXCLUDED_BY_CLIENT"
    }
    if excluded:
        if (
            plan.evidence_mode is not EvidenceMode.EXTERNAL_GATE
            or not excluded <= valid_exclusions
        ):
            raise ExecutionValidationError(
                "criterion exclusion is not a valid Task 1 external gate"
            )
        if any(value == "BLOCKED" for value in outcomes.values()):
            return "BLOCKED"
        return "EXCLUDED_BY_CLIENT"
    if any(value == "BLOCKED" for value in outcomes.values()):
        return "BLOCKED"
    return "PASS"


class StoreIdentities(_StrictModel):
    raw_store_id: str = Field(min_length=1)
    tracked_store_id: str = Field(min_length=1)
    anchor_store_id: str = Field(min_length=1)
    raw_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tracked_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    anchor_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _stores_are_distinct(self) -> StoreIdentities:
        if len({self.raw_store_id, self.tracked_store_id, self.anchor_store_id}) != 3:
            raise ValueError("authorization store bindings must be distinct")
        return self


class ProtectedQuotas(_StrictModel):
    max_scenarios: int = Field(ge=0)
    max_messages: int = Field(ge=0)
    max_model_calls: int = Field(ge=0)
    max_cost_usd: float = Field(ge=0)
    subsystem_quotas: dict[str, int] = Field(min_length=1)

    @model_validator(mode="after")
    def _non_negative_subsystems(self) -> ProtectedQuotas:
        if any(value < 0 for value in self.subsystem_quotas.values()):
            raise ValueError("subsystem quota must be non-negative")
        return self


class ExactLiveAuthorizationBinding(_StrictModel):
    """Digest-only bridge from one approved v1 manifest and fresh preflight."""

    v1_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_observation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_identity_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    permissions_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    cleanup_retention_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_ids_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    collector_ids_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    stores_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_observed_at: datetime

    @model_validator(mode="after")
    def _aware_preflight_time(self) -> ExactLiveAuthorizationBinding:
        if (
            self.preflight_observed_at.tzinfo is None
            or self.preflight_observed_at.utcoffset() is None
        ):
            raise ValueError("preflight bridge observation time must be aware")
        return self


class AuthorizedQuotaCharge(_StrictModel):
    messages: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    max_cost_usd: float = Field(ge=0)
    cost_settlement: Literal["exact", "bounded_actual"]

    @model_validator(mode="after")
    def _finite_cost(self) -> AuthorizedQuotaCharge:
        if not math.isfinite(self.max_cost_usd):
            raise ValueError("authorized quota cost must be finite")
        return self


class AuthorizedActionSpec(_StrictModel):
    action_id: str
    execution_id: str
    step_id: str
    capability: str
    operation_permission: str
    adapter_id: str
    subsystem: str
    destination_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=1)
    capability_units: dict[str, int] = Field(min_length=1)
    quota_charge: AuthorizedQuotaCharge


class AuthorizedRetentionSpec(_StrictModel):
    authority_id: str = Field(min_length=1)
    issuer: Literal["client-retention-authority"]
    artifact_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    cleanup_owner: str = Field(min_length=1)
    cleanup_authority: str = Field(min_length=1)
    retention_owner: str = Field(min_length=1)
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _valid_window(self) -> AuthorizedRetentionSpec:
        if (
            self.issued_at.tzinfo is None
            or self.issued_at.utcoffset() is None
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("authorized retention window is invalid")
        return self


class SideEffectAuthority(_StrictModel):
    issuer: Literal["protected-side-effect-authority"]
    cleanup_owner: str = Field(min_length=1)
    cleanup_authority: str = Field(min_length=1)
    retention_authorities: tuple[AuthorizedRetentionSpec, ...] = ()

    @model_validator(mode="after")
    def _unique_artifacts(self) -> SideEffectAuthority:
        identities = [item.artifact_id for item in self.retention_authorities]
        if len(identities) != len(set(identities)):
            raise ValueError("retention authority artifact IDs must be unique")
        return self


class ClientExclusionAuthority(_StrictModel):
    authority_id: str = Field(min_length=1)
    issuer: Literal["client-exclusion-authority"]
    execution_id: str = Field(min_length=1)
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _valid_window(self) -> ClientExclusionAuthority:
        if (
            self.issued_at.tzinfo is None
            or self.issued_at.utcoffset() is None
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("client exclusion authority window is invalid")
        return self


class ProtectedExecutionAuthorities(_StrictModel):
    schema_version: Literal["noor-e2e-protected-execution-authorities/v2"]
    client_exclusions: tuple[ClientExclusionAuthority, ...]
    side_effect_authority: SideEffectAuthority

    @model_validator(mode="after")
    def _unique_authorities(self) -> ProtectedExecutionAuthorities:
        exclusion_ids = [item.authority_id for item in self.client_exclusions]
        exclusion_executions = [item.execution_id for item in self.client_exclusions]
        if len(exclusion_ids) != len(set(exclusion_ids)) or len(
            exclusion_executions
        ) != len(set(exclusion_executions)):
            raise ValueError("client exclusion authorities must be unique")
        retention_ids = [
            item.authority_id
            for item in self.side_effect_authority.retention_authorities
        ]
        if len(retention_ids) != len(set(retention_ids)):
            raise ValueError("retention authority IDs must be unique")
        return self


class ExecutionAuthorizationV2(_StrictModel):
    schema_version: Literal["noor-e2e-authorization/v2"]
    authorization_id: str = Field(min_length=1)
    status: Literal["approved"]
    issued_at: datetime
    expires_at: datetime
    task1_authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    task1_input_digests: dict[str, str] = Field(min_length=1)
    preflight_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    readback_collector_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    compiler_id: str = Field(min_length=1)
    compiled_plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_ids: tuple[str, ...] = Field(min_length=1)
    execution_input_digests: dict[str, str] = Field(min_length=29)
    adapter_ids: tuple[str, ...] = Field(min_length=1)
    collector_ids: tuple[str, ...] = Field(min_length=1)
    permissions: tuple[str, ...]
    action_specs: tuple[AuthorizedActionSpec, ...] = Field(min_length=1)
    client_exclusion_authorities: dict[str, str] = Field(default_factory=dict)
    client_exclusion_grants: tuple[ClientExclusionAuthority, ...] = ()
    side_effect_authority: SideEffectAuthority
    live_binding: ExactLiveAuthorizationBinding
    store_ids: StoreIdentities
    registry_id: str = Field(min_length=1)
    quotas: ProtectedQuotas

    @model_validator(mode="after")
    def _valid_window(self) -> ExecutionAuthorizationV2:
        if (
            self.issued_at.tzinfo is None
            or self.issued_at.utcoffset() is None
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("authorization v2 window is invalid")
        if set(self.execution_input_digests) != set(self.execution_ids) or any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.execution_input_digests.values()
        ):
            raise ValueError("authorization v2 executable input binding drift")
        if any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.task1_input_digests.values()
        ):
            raise ValueError("authorization Task 1 input digest binding drift")
        if any(
            execution_id not in self.execution_ids
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for execution_id, value in self.client_exclusion_authorities.items()
        ):
            raise ValueError("authorization client exclusion binding drift")
        expected_exclusions = {
            grant.execution_id: _digest(grant.model_dump(mode="json"))
            for grant in self.client_exclusion_grants
        }
        if self.client_exclusion_authorities != expected_exclusions:
            raise ValueError("authorization client exclusion grant drift")
        return self


class AuthorizedActionSpecs(_StrictModel):
    schema_version: Literal["noor-e2e-authorized-action-specs/v2"]
    specs: tuple[AuthorizedActionSpec, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_action_ids(self) -> AuthorizedActionSpecs:
        if len({item.action_id for item in self.specs}) != len(self.specs):
            raise ValueError("authorized action IDs must be unique")
        return self


class AuthorityAdapterIds(_StrictModel):
    schema_version: Literal["noor-e2e-authority-adapter-ids/v2"]
    values: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_adapter_ids(self) -> AuthorityAdapterIds:
        if len(set(self.values)) != len(self.values):
            raise ValueError("authority adapter IDs must be unique")
        return self


class AuthorityCollectorIds(_StrictModel):
    schema_version: Literal["noor-e2e-authority-collector-ids/v2"]
    values: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_collector_ids(self) -> AuthorityCollectorIds:
        if len(set(self.values)) != len(self.values):
            raise ValueError("authority collector IDs must be unique")
        return self


class Task1AuthorityBindings(_StrictModel):
    schema_version: Literal["noor-e2e-task1-authority-bindings/v2"]
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_digests: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def _sha256_input_digests(self) -> Task1AuthorityBindings:
        if any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.input_digests.values()
        ):
            raise ValueError("Task 1 authority input digests must be SHA-256")
        return self


_AUTHORITY_PAYLOAD_PATHS = {
    "authorization_manifest": "authorization-v1.json",
    "preflight_request": "preflight-request.json",
    "preflight_observation": "preflight-observation.json",
    "action_specs": "authorized-action-specs.json",
    "store_identities": "store-identities.json",
    "adapter_ids": "adapter-ids.json",
    "collector_ids": "collector-ids.json",
    "task1_bindings": "task1-bindings.json",
    "execution_authorities": "execution-authorities.json",
}
_AUTHORITY_STORE_ROOT_KEYS = frozenset({"raw", "tracked", "anchor"})


class AuthorityBundleReceipt(_StrictModel):
    """Persistent registry-issued binding for one run and protected journal root."""

    schema_version: Literal["noor-e2e-authority-bundle-receipt/v2"]
    registry_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    protected_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_root_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    store_root_digests: dict[str, str] = Field(min_length=3, max_length=3)
    payload_digests: dict[str, str] = Field(
        min_length=len(_AUTHORITY_PAYLOAD_PATHS),
        max_length=len(_AUTHORITY_PAYLOAD_PATHS),
    )
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _exact_receipt_contract(self) -> AuthorityBundleReceipt:
        if (
            self.issued_at.tzinfo is None
            or self.issued_at.utcoffset() is None
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("authority bundle receipt window is invalid")
        if (
            set(self.payload_digests) != set(_AUTHORITY_PAYLOAD_PATHS)
            or set(self.store_root_digests) != _AUTHORITY_STORE_ROOT_KEYS
        ):
            raise ValueError("authority bundle receipt coverage is incomplete")
        for digest in (
            *self.payload_digests.values(),
            *self.store_root_digests.values(),
        ):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError("authority bundle receipt digest is invalid")
        return self


_HANDLE_TOKEN = object()


@dataclass(frozen=True)
class ExecutionAuthorizationHandle:
    """Opaque, non-serializable capability issued after protected receipt validation."""

    _authorization: ExecutionAuthorizationV2
    _protected_root: Path
    _run_id: str
    _registry_id: str
    _receipt_digest: str
    _token: object

    def __getstate__(self) -> object:
        raise TypeError("execution authority handles are not serializable")

    def __reduce__(self) -> NoReturn:
        raise TypeError("execution authority handles are not serializable")


@dataclass(frozen=True)
class _AuthorityHandleRecord:
    handle_ref: weakref.ReferenceType[ExecutionAuthorizationHandle]
    registry: TrustedAcceptanceRegistry
    registry_id: str
    protected_root: Path
    run_id: str
    authorization_digest: str
    receipt_digest: str


_AUTHORITY_HANDLE_RECORDS: dict[int, _AuthorityHandleRecord] = {}


def _register_authority_handle(
    handle: ExecutionAuthorizationHandle,
    *,
    registry: TrustedAcceptanceRegistry,
) -> ExecutionAuthorizationHandle:
    identity = id(handle)

    def _discard(_: object) -> None:
        _AUTHORITY_HANDLE_RECORDS.pop(identity, None)

    _AUTHORITY_HANDLE_RECORDS[identity] = _AuthorityHandleRecord(
        handle_ref=weakref.ref(handle, _discard),
        registry=registry,
        registry_id=handle._registry_id,
        protected_root=handle._protected_root,
        run_id=handle._run_id,
        authorization_digest=authorization_digest(handle._authorization),
        receipt_digest=handle._receipt_digest,
    )
    return handle


def _validate_run_id(run_id: str) -> None:
    if not run_id or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-._"
        for character in run_id.lower()
    ):
        raise ExecutionValidationError("run identity is unsafe")


def _authority_bundle_relative(run_id: str, name: str) -> str:
    _validate_run_id(run_id)
    return f"authority-bundles/{run_id}/{name}"


def _validated_protected_root(root: Path, *, create: bool) -> Path:
    if not root.is_absolute() or any(
        part in {"", ".", ".."} for part in root.parts[1:]
    ):
        raise ExecutionValidationError(
            "protected authority root must be absolute and normalized"
        )
    fd = _open_absolute_chain(root, create=create)
    os.close(fd)
    return root


def _expected_store_root_digests(root: Path) -> dict[str, str]:
    return {
        "raw": store_root_digest(root),
        "tracked": store_root_digest(root / "tracked"),
        "anchor": store_root_digest(root / "anchors"),
    }


def _parse_authority_payload(
    payload: bytes,
    model: type[BaseModel],
    *,
    label: str,
) -> BaseModel:
    try:
        return model.model_validate(json.loads(payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ExecutionValidationError(
            f"protected authority {label} payload is invalid"
        ) from exc


def _execution_criterion_ids(
    plan: CompiledExecutionPlan,
    execution_id: str,
) -> tuple[str, ...]:
    return tuple(
        item.criterion_id
        for item in plan.criteria.values()
        if execution_id in item.obligation_ids
    )


def _validate_protected_execution_authorities(
    authorities: ProtectedExecutionAuthorities,
    *,
    authorization: AuthorizationManifest,
    plan: CompiledExecutionPlan,
    bundle_issued_at: datetime,
) -> None:
    side_effects = authorities.side_effect_authority
    if (
        side_effects.cleanup_owner != authorization.allowed_executor
        or side_effects.cleanup_authority != authorization.cleanup_method
    ):
        raise ExecutionValidationError("protected side-effect owner/authority drift")
    for exclusion in authorities.client_exclusions:
        criteria = _execution_criterion_ids(plan, exclusion.execution_id)
        if (
            exclusion.execution_id not in plan.execution_ids
            or exclusion.criterion_ids != criteria
            or not criteria
            or not all(plan.criteria[item].allows_client_exclusion for item in criteria)
            or not authorization.issued_at
            <= exclusion.issued_at
            < bundle_issued_at
            < exclusion.expires_at
            <= authorization.expires_at
        ):
            raise ExecutionValidationError(
                "protected client exclusion execution/criterion/window drift"
            )
    for retention in side_effects.retention_authorities:
        criteria = _execution_criterion_ids(plan, retention.execution_id)
        if (
            retention.execution_id not in plan.execution_ids
            or retention.criterion_ids != criteria
            or not criteria
            or retention.cleanup_owner != side_effects.cleanup_owner
            or retention.cleanup_authority != side_effects.cleanup_authority
            or not authorization.issued_at
            <= retention.issued_at
            < bundle_issued_at
            < retention.expires_at
            <= authorization.expires_at
        ):
            raise ExecutionValidationError(
                "protected retention execution/criterion/owner/window drift"
            )


def issue_execution_authorization_handle(
    *,
    registry: TrustedAcceptanceRegistry,
    protected_root: Path,
    run_id: str,
    current_time: datetime | None = None,
) -> ExecutionAuthorizationHandle:
    """Rebuild exact v2 authority from one persistent protected typed bundle."""

    if not isinstance(registry, TrustedAcceptanceRegistry):
        raise ExecutionValidationError("trusted acceptance registry is required")
    _validate_run_id(run_id)
    root = _validated_protected_root(protected_root, create=False)
    now = current_time or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ExecutionValidationError("authority issue time must be timezone-aware")
    receipt_payload = _read_protected(
        root, _authority_bundle_relative(run_id, "receipt.json")
    )
    try:
        receipt = AuthorityBundleReceipt.model_validate(json.loads(receipt_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ExecutionValidationError(
            "protected authority bundle receipt is invalid"
        ) from exc
    if (
        receipt.registry_id != registry.registry_id
        or receipt.run_id != run_id
        or receipt.protected_root_digest != store_root_digest(root)
        or receipt.run_root_digest != store_root_digest(root / run_id)
        or receipt.store_root_digests != _expected_store_root_digests(root)
        or not receipt.issued_at <= now < receipt.expires_at
    ):
        raise ExecutionValidationError("protected authority bundle receipt drift")

    payloads: dict[str, bytes] = {}
    for identity, filename in _AUTHORITY_PAYLOAD_PATHS.items():
        payload = _read_protected(root, _authority_bundle_relative(run_id, filename))
        if hashlib.sha256(payload).hexdigest() != receipt.payload_digests[identity]:
            raise ExecutionValidationError(
                f"protected authority {identity} payload digest drift"
            )
        payloads[identity] = payload

    authorization_v1 = cast(
        "AuthorizationManifest",
        _parse_authority_payload(
            payloads["authorization_manifest"],
            AuthorizationManifest,
            label="authorization manifest",
        ),
    )
    request = cast(
        "PreflightRequest",
        _parse_authority_payload(
            payloads["preflight_request"],
            PreflightRequest,
            label="preflight request",
        ),
    )
    observation = cast(
        "PreflightObservation",
        _parse_authority_payload(
            payloads["preflight_observation"],
            PreflightObservation,
            label="preflight observation",
        ),
    )
    action_specs = cast(
        "AuthorizedActionSpecs",
        _parse_authority_payload(
            payloads["action_specs"],
            AuthorizedActionSpecs,
            label="action specs",
        ),
    )
    stores = cast(
        "StoreIdentities",
        _parse_authority_payload(
            payloads["store_identities"],
            StoreIdentities,
            label="store identities",
        ),
    )
    adapters = cast(
        "AuthorityAdapterIds",
        _parse_authority_payload(
            payloads["adapter_ids"],
            AuthorityAdapterIds,
            label="adapter IDs",
        ),
    )
    collectors = cast(
        "AuthorityCollectorIds",
        _parse_authority_payload(
            payloads["collector_ids"],
            AuthorityCollectorIds,
            label="collector IDs",
        ),
    )
    task1 = cast(
        "Task1AuthorityBindings",
        _parse_authority_payload(
            payloads["task1_bindings"],
            Task1AuthorityBindings,
            label="Task 1 bindings",
        ),
    )
    execution_authorities = cast(
        "ProtectedExecutionAuthorities",
        _parse_authority_payload(
            payloads["execution_authorities"],
            ProtectedExecutionAuthorities,
            label="execution authorities",
        ),
    )
    if (
        stores.raw_root_digest != receipt.store_root_digests["raw"]
        or stores.tracked_root_digest != receipt.store_root_digests["tracked"]
        or stores.anchor_root_digest != receipt.store_root_digests["anchor"]
        or task1.authorization_digest != registry.task1_authorization_digest
        or task1.input_digests != registry.task1_input_digests
    ):
        raise ExecutionValidationError(
            "protected authority Task 1/store root binding drift"
        )
    if (
        receipt.issued_at < authorization_v1.issued_at
        or receipt.expires_at > authorization_v1.expires_at
    ):
        raise ExecutionValidationError(
            "protected authority receipt exceeds authorization window"
        )
    _validate_protected_execution_authorities(
        execution_authorities,
        authorization=authorization_v1,
        plan=registry.compiled_plan,
        bundle_issued_at=receipt.issued_at,
    )

    authorization = build_execution_authorization_from_v1(
        authorization_v1,
        observation,
        request,
        policy=registry.compiled_policy,
        plan=registry.compiled_plan,
        registry_id=registry.registry_id,
        task1_authorization_digest=task1.authorization_digest,
        task1_input_digests=task1.input_digests,
        adapter_ids=adapters.values,
        collector_ids=collectors.values,
        action_specs=action_specs.specs,
        execution_authorities=execution_authorities,
        store_ids=stores,
        current_time=now,
    )
    validate_execution_authorization(
        authorization,
        policy=registry.compiled_policy,
        plan=registry.compiled_plan,
        registry_id=registry.registry_id,
        current_time=now,
    )
    return _register_authority_handle(
        ExecutionAuthorizationHandle(
            authorization,
            root,
            run_id,
            registry.registry_id,
            hashlib.sha256(receipt_payload).hexdigest(),
            _HANDLE_TOKEN,
        ),
        registry=registry,
    )


def _write_test_authority_bundle(
    *,
    registry: TrustedAcceptanceRegistry,
    protected_root: Path,
    run_id: str,
    authorization: AuthorizationManifest,
    request: PreflightRequest,
    observation: PreflightObservation,
    action_specs: AuthorizedActionSpecs,
    store_ids: StoreIdentities,
    adapter_ids: AuthorityAdapterIds,
    collector_ids: AuthorityCollectorIds,
    task1_bindings: Task1AuthorityBindings,
    execution_authorities: ProtectedExecutionAuthorities,
    receipt_issued_at: datetime,
    receipt_expires_at: datetime,
) -> AuthorityBundleReceipt:
    """Fixture-only producer for a complete persistent typed authority bundle."""

    if not isinstance(registry, TrustedAcceptanceRegistry):
        raise ExecutionValidationError("trusted acceptance registry is required")
    _validate_run_id(run_id)
    root = _validated_protected_root(protected_root, create=True)
    expected_store_roots = _expected_store_root_digests(root)
    if (
        store_ids.raw_root_digest != expected_store_roots["raw"]
        or store_ids.tracked_root_digest != expected_store_roots["tracked"]
        or store_ids.anchor_root_digest != expected_store_roots["anchor"]
    ):
        raise ExecutionValidationError("test authority store root binding drift")
    payload_models: dict[str, BaseModel] = {
        "authorization_manifest": authorization,
        "preflight_request": request,
        "preflight_observation": observation,
        "action_specs": action_specs,
        "store_identities": store_ids,
        "adapter_ids": adapter_ids,
        "collector_ids": collector_ids,
        "task1_bindings": task1_bindings,
        "execution_authorities": execution_authorities,
    }
    payload_digests = {
        identity: _write_exclusive(
            root,
            _authority_bundle_relative(run_id, _AUTHORITY_PAYLOAD_PATHS[identity]),
            model.model_dump(mode="json"),
        )
        for identity, model in payload_models.items()
    }
    receipt = AuthorityBundleReceipt(
        schema_version="noor-e2e-authority-bundle-receipt/v2",
        registry_id=registry.registry_id,
        run_id=run_id,
        protected_root_digest=store_root_digest(root),
        run_root_digest=store_root_digest(root / run_id),
        store_root_digests=expected_store_roots,
        payload_digests=payload_digests,
        issued_at=receipt_issued_at,
        expires_at=receipt_expires_at,
    )
    _write_exclusive(
        root,
        _authority_bundle_relative(run_id, "receipt.json"),
        receipt.model_dump(mode="json"),
    )
    return receipt


def _authorization_from_handle(
    authority: object,
    *,
    protected_root: Path,
    run_id: str,
    registry: TrustedAcceptanceRegistry | None = None,
) -> ExecutionAuthorizationV2:
    record = _AUTHORITY_HANDLE_RECORDS.get(id(authority))
    if (
        not isinstance(authority, ExecutionAuthorizationHandle)
        or authority._token is not _HANDLE_TOKEN
        or record is None
        or record.handle_ref() is not authority
        or authority._protected_root != protected_root
        or authority._run_id != run_id
        or authority._authorization.registry_id != authority._registry_id
        or record.registry_id != authority._registry_id
        or record.protected_root != authority._protected_root
        or record.run_id != authority._run_id
        or record.authorization_digest != authorization_digest(authority._authorization)
        or record.receipt_digest != authority._receipt_digest
        or (registry is not None and record.registry is not registry)
    ):
        raise ExecutionValidationError("registry-issued authority handle binding drift")
    root = _validated_protected_root(protected_root, create=False)
    receipt_payload = _read_protected(
        root, _authority_bundle_relative(run_id, "receipt.json")
    )
    try:
        receipt = AuthorityBundleReceipt.model_validate(json.loads(receipt_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ExecutionValidationError(
            "protected authority bundle receipt is invalid"
        ) from exc
    now = datetime.now(UTC)
    if (
        hashlib.sha256(receipt_payload).hexdigest() != authority._receipt_digest
        or receipt.registry_id != record.registry.registry_id
        or receipt.registry_id != authority._registry_id
        or receipt.run_id != run_id
        or receipt.protected_root_digest != store_root_digest(root)
        or receipt.run_root_digest != store_root_digest(root / run_id)
        or not receipt.issued_at <= now < receipt.expires_at
        or not authority._authorization.issued_at
        <= now
        < authority._authorization.expires_at
    ):
        raise ExecutionValidationError("registry-issued authority handle receipt drift")
    return authority._authorization


def build_execution_authorization_from_v1(
    authorization: AuthorizationManifest,
    observation: PreflightObservation,
    request: PreflightRequest,
    *,
    policy: CompiledPolicy,
    plan: CompiledExecutionPlan,
    registry_id: str,
    task1_authorization_digest: str,
    task1_input_digests: dict[str, str],
    adapter_ids: tuple[str, ...],
    collector_ids: tuple[str, ...],
    action_specs: tuple[AuthorizedActionSpec, ...],
    execution_authorities: ProtectedExecutionAuthorities,
    store_ids: StoreIdentities,
    current_time: datetime,
) -> ExecutionAuthorizationV2:
    """Build executable authority solely from an approved v1/preflight pair.

    The public v1 model is read here as a typed immutable source; arbitrary
    mappings never cross this boundary.  Only digests of protected identities
    are carried into v2 so tracked output cannot disclose targets.
    """

    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ExecutionValidationError("bridge time must be timezone-aware")
    validate_preflight(authorization, observation, request, now=current_time)
    readback = observation.readback_identity
    if (
        readback is None
        or readback.observed_at > current_time
        or current_time - readback.observed_at > _MAX_PREFLIGHT_AGE
    ):
        raise ExecutionValidationError(
            "successful preflight is missing, stale, or future-dated"
        )
    execution_ids = tuple(
        [
            *authorization.scenario_binding.scenario_ids,
            *authorization.scenario_binding.evidence_block_ids,
        ]
    )
    if execution_ids != plan.execution_ids or set(
        authorization.scenario_binding.executable_input_digests
    ) != set(plan.execution_ids):
        raise ExecutionValidationError("approved authorization execution set drift")
    if not adapter_ids or not collector_ids:
        raise ExecutionValidationError(
            "approved adapter and collector IDs are required"
        )
    quotas = ProtectedQuotas(**authorization.quotas.model_dump(mode="json"))
    side_effect_authority = execution_authorities.side_effect_authority
    client_exclusion_grants = execution_authorities.client_exclusions
    client_exclusion_authorities = {
        item.execution_id: _digest(item.model_dump(mode="json"))
        for item in client_exclusion_grants
    }
    binding = ExactLiveAuthorizationBinding(
        v1_manifest_digest=_digest(authorization.model_dump(mode="json")),
        preflight_request_digest=_digest(request.model_dump(mode="json")),
        preflight_observation_digest=_digest(observation.model_dump(mode="json")),
        runtime_identity_digest=_digest(
            authorization.expected_identity.model_dump(mode="json")
        ),
        target_digest=_digest(authorization.targets.model_dump(mode="json")),
        permissions_digest=_digest(tuple(authorization.permissions)),
        cleanup_retention_digest=_digest(
            {
                "side_effect_authority": side_effect_authority.model_dump(mode="json"),
                "client_exclusion_authorities": client_exclusion_authorities,
                "client_exclusion_grants": [
                    item.model_dump(mode="json") for item in client_exclusion_grants
                ],
            }
        ),
        execution_set_digest=_digest(
            {
                "execution_ids": execution_ids,
                "input_digests": authorization.scenario_binding.executable_input_digests,
                "quotas": authorization.quotas.model_dump(mode="json"),
            }
        ),
        adapter_ids_digest=_digest(adapter_ids),
        collector_ids_digest=_digest(collector_ids),
        stores_digest=_digest(store_ids.model_dump(mode="json")),
        preflight_observed_at=readback.observed_at,
    )
    return ExecutionAuthorizationV2(
        schema_version="noor-e2e-authorization/v2",
        authorization_id=authorization.authorization_id,
        status="approved",
        issued_at=authorization.issued_at,
        expires_at=authorization.expires_at,
        task1_authorization_digest=task1_authorization_digest,
        task1_input_digests=task1_input_digests,
        preflight_digest=_digest(
            {
                "request": request.model_dump(mode="json"),
                "observation": observation.model_dump(mode="json"),
            }
        ),
        readback_collector_digest=_digest(collector_ids),
        policy_digest=policy.policy_digest,
        compiler_id=plan.compiler_id,
        compiled_plan_digest=plan.plan_digest,
        execution_ids=execution_ids,
        execution_input_digests=authorization.scenario_binding.executable_input_digests,
        adapter_ids=adapter_ids,
        collector_ids=collector_ids,
        permissions=tuple(authorization.permissions),
        action_specs=action_specs,
        client_exclusion_authorities=client_exclusion_authorities,
        client_exclusion_grants=client_exclusion_grants,
        side_effect_authority=side_effect_authority,
        live_binding=binding,
        store_ids=store_ids,
        registry_id=registry_id,
        quotas=quotas,
    )


def authorization_digest(authorization: ExecutionAuthorizationV2) -> str:
    return _digest(authorization.model_dump(mode="json"))


def store_root_digest(root: Path) -> str:
    if not root.is_absolute() or any(
        part in {"", ".", ".."} for part in root.parts[1:]
    ):
        raise ExecutionValidationError("store root must be absolute and normalized")
    return _digest(
        {
            "schema_version": "noor-e2e-store-root/v2",
            "absolute_path": str(root),
        }
    )


def validate_execution_authorization(
    authorization: object,
    *,
    policy: CompiledPolicy,
    plan: CompiledExecutionPlan,
    registry_id: str,
    current_time: datetime | None = None,
) -> ExecutionAuthorizationV2:
    if not isinstance(authorization, ExecutionAuthorizationV2):
        schema = getattr(authorization, "schema_version", "")
        raise ExecutionValidationError(
            f"{schema or 'unknown'} is archival; executor requires authorization/v2"
        )
    if authorization.policy_digest != policy.policy_digest:
        raise ExecutionValidationError("authorization policy drift")
    if authorization.compiler_id != plan.compiler_id:
        raise ExecutionValidationError("authorization compiler drift")
    if authorization.compiled_plan_digest != plan.plan_digest:
        raise ExecutionValidationError("authorization compiled plan drift")
    if authorization.execution_ids != plan.execution_ids:
        raise ExecutionValidationError(
            "authorization execution drift: exact canonical 29 required"
        )
    if authorization.adapter_ids != LOCAL_ADAPTER_IDS:
        raise ExecutionValidationError("authorization adapter is not allowed")
    if authorization.live_binding.adapter_ids_digest != _digest(
        authorization.adapter_ids
    ) or authorization.live_binding.collector_ids_digest != _digest(
        authorization.collector_ids
    ):
        raise ExecutionValidationError("authorization adapter/collector binding drift")
    if authorization.live_binding.permissions_digest != _digest(
        authorization.permissions
    ):
        raise ExecutionValidationError("authorization permission binding drift")
    if authorization.live_binding.cleanup_retention_digest != _digest(
        {
            "side_effect_authority": authorization.side_effect_authority.model_dump(
                mode="json"
            ),
            "client_exclusion_authorities": (
                authorization.client_exclusion_authorities
            ),
            "client_exclusion_grants": [
                item.model_dump(mode="json")
                for item in authorization.client_exclusion_grants
            ],
        }
    ):
        raise ExecutionValidationError(
            "authorization cleanup/retention authority binding drift"
        )
    for exclusion in authorization.client_exclusion_grants:
        criteria = _execution_criterion_ids(plan, exclusion.execution_id)
        if (
            exclusion.criterion_ids != criteria
            or not criteria
            or not all(plan.criteria[item].allows_client_exclusion for item in criteria)
            or not authorization.issued_at
            <= exclusion.issued_at
            < exclusion.expires_at
            <= authorization.expires_at
        ):
            raise ExecutionValidationError(
                "authorization client exclusion authority drift"
            )
    side_effects = authorization.side_effect_authority
    for retention in side_effects.retention_authorities:
        if (
            retention.criterion_ids
            != _execution_criterion_ids(plan, retention.execution_id)
            or retention.cleanup_owner != side_effects.cleanup_owner
            or retention.cleanup_authority != side_effects.cleanup_authority
            or not authorization.issued_at
            <= retention.issued_at
            < retention.expires_at
            <= authorization.expires_at
        ):
            raise ExecutionValidationError("authorization retention authority drift")
    if authorization.live_binding.execution_set_digest != _digest(
        {
            "execution_ids": authorization.execution_ids,
            "input_digests": authorization.execution_input_digests,
            "quotas": authorization.quotas.model_dump(mode="json"),
        }
    ):
        raise ExecutionValidationError("authorization execution/quota binding drift")
    if authorization.live_binding.stores_digest != _digest(
        authorization.store_ids.model_dump(mode="json")
    ):
        raise ExecutionValidationError("authorization store binding drift")
    if len({item.action_id for item in authorization.action_specs}) != len(
        authorization.action_specs
    ) or any(
        item.adapter_id not in authorization.adapter_ids
        or item.operation_permission not in authorization.permissions
        or item.execution_id not in authorization.execution_ids
        for item in authorization.action_specs
    ):
        raise ExecutionValidationError("authorization protected action spec drift")
    if authorization.registry_id != registry_id:
        raise ExecutionValidationError("authorization registry drift")
    now = current_time or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ExecutionValidationError("authorization validity time must be aware")
    if not authorization.issued_at <= now < authorization.expires_at:
        raise ExecutionValidationError(
            "authorization validity is expired or not active"
        )
    return authorization


class QuotaUsage(_StrictModel):
    messages: int = 0
    model_calls: int = 0
    cost_usd: float = 0
    subsystem_usage: dict[str, int] = Field(default_factory=dict)


ActionState = Literal["reserved", "succeeded", "failed", "unknown"]


class ActionReservation(_StrictModel):
    action_id: str
    run_id: str
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_id: str
    step_id: str
    capability: str
    operation_permission: str
    adapter_id: str
    subsystem: str
    destination_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=1)
    capability_units: dict[str, int] = Field(min_length=1)
    messages: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    issued_at: datetime
    expires_at: datetime
    reservation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _finite_cost(self) -> ActionReservation:
        if not math.isfinite(self.cost_usd):
            raise ValueError("reservation cost must be finite")
        if (
            self.issued_at.tzinfo is None
            or self.issued_at.utcoffset() is None
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("reservation permit window is invalid")
        if any(value <= 0 for value in self.capability_units.values()):
            raise ValueError("reservation capability units must be positive")
        return self


class ActionCostSettlement(_StrictModel):
    schema_version: Literal["noor-e2e-action-cost-settlement/v2"]
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    reservation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reserved_cost_usd: float = Field(ge=0)
    actual_cost_usd: float = Field(ge=0)
    cost_settlement: Literal["exact", "bounded_actual"]
    settled_at: datetime
    settlement_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bounded_actual_cost(self) -> ActionCostSettlement:
        if (
            not math.isfinite(self.reserved_cost_usd)
            or not math.isfinite(self.actual_cost_usd)
            or self.actual_cost_usd > self.reserved_cost_usd
            or (
                self.cost_settlement == "exact"
                and self.actual_cost_usd != self.reserved_cost_usd
            )
            or self.settled_at.tzinfo is None
            or self.settled_at.utcoffset() is None
        ):
            raise ValueError("action cost settlement exceeds authorized maximum")
        return self


class UnknownActionReconciliationReceipt(_StrictModel):
    """Independent, one-use evidence needed to resolve an uncertain dispatch."""

    schema_version: Literal["noor-e2e-unknown-action-reconciliation/v2"]
    registry_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    action_id: str = Field(min_length=1)
    reservation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    collector_id: str = Field(min_length=1)
    producer: Literal["independent-readback-collector"]
    causal_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    expires_at: datetime
    resolved_state: Literal["succeeded", "failed"]
    inventory_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _valid_window(self) -> UnknownActionReconciliationReceipt:
        if (
            self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.observed_at
        ):
            raise ValueError("reconciliation receipt window is invalid")
        return self


class AttemptRecovery(_StrictModel):
    transaction_id: str
    status: Literal["committed", "aborted"]
    raw_digest: str | None
    tracked_digest: str | None
    commit_digest: str


class PlannedTurnV2(_StrictModel):
    turn_id: str = Field(min_length=1)
    customer_input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_behavior_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    assertion_ids: tuple[str, ...] = Field(min_length=1)


class TurnTimelineV2(_StrictModel):
    sent_at: datetime
    first_visible_at: datetime
    final_visible_at: datetime
    delivered_at: datetime | None

    @model_validator(mode="after")
    def _ordered(self) -> TurnTimelineV2:
        values = [self.sent_at, self.first_visible_at, self.final_visible_at]
        if any(item.tzinfo is None or item.utcoffset() is None for item in values):
            raise ValueError("turn timeline must be timezone-aware")
        if values != sorted(values):
            raise ValueError("turn timeline order is invalid")
        if self.delivered_at is not None and (
            self.delivered_at.tzinfo is None
            or self.delivered_at.utcoffset() is None
            or self.delivered_at < self.final_visible_at
        ):
            raise ValueError("turn delivery timestamp is invalid")
        return self


class ActualTurnV2(_StrictModel):
    actual_turn_id: str = Field(min_length=1)
    planned_turn_id: str = Field(min_length=1)
    customer_input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_behavior_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    assertion_ids: tuple[str, ...] = Field(min_length=1)
    event_refs: tuple[str, ...] = Field(min_length=1)
    tool_refs: tuple[str, ...]
    audit_refs: tuple[str, ...] = Field(min_length=1)
    timeline: TurnTimelineV2
    model_id: str = Field(min_length=1)
    token_count: int = Field(ge=0)
    cost_usd: float = Field(ge=0)


class AdaptiveDeviationV2(_StrictModel):
    planned_turn_id: str = Field(min_length=1)
    actual_turn_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ScenarioAttemptV2(_StrictModel):
    schema_version: Literal["noor-e2e-scenario-attempt/v2"]
    execution_id: str = Field(min_length=1)
    planned_turns: tuple[PlannedTurnV2, ...] = Field(min_length=1)
    actual_turns: tuple[ActualTurnV2, ...] = Field(min_length=1)
    adaptive_deviations: tuple[AdaptiveDeviationV2, ...]
    oracle_evidence: tuple[OracleEvidence, ...] = Field(min_length=1)
    permission_evidence: tuple[str, ...]
    readback_evidence: tuple[str, ...]
    baseline: ReadbackObservation
    final: ReadbackObservation
    action_at: tuple[datetime, ...]
    tester_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    judge_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceBlockAttemptV2(_StrictModel):
    schema_version: Literal["noor-e2e-evidence-block-attempt/v2"]
    execution_id: str = Field(min_length=1)
    evidence_collection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    oracle_evidence: tuple[OracleEvidence, ...] = Field(min_length=1)
    permission_evidence: tuple[str, ...]


class GateEvidenceReceipt(_StrictModel):
    """Receipt emitted before execution by a protected independent gate source."""

    schema_version: Literal["noor-e2e-gate-evidence-receipt/v2"]
    registry_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_id: str = Field(min_length=1)
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    execution_owner: str = Field(min_length=1)
    execution_started_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["BLOCKED", "EXCLUDED_BY_CLIENT"]
    producer: Literal[
        "independent-readback-collector",
        "trusted-evidence-registry",
        "client-exclusion-authority",
    ]
    issued_at: datetime
    expires_at: datetime
    client_authority_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def _valid_window(self) -> GateEvidenceReceipt:
        if (
            self.issued_at.tzinfo is None
            or self.issued_at.utcoffset() is None
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("gate receipt window is invalid")
        return self


class GateEvidenceArtifact(_StrictModel):
    """Producer-owned gate evidence committed independently of the attempt."""

    schema_version: Literal["noor-e2e-gate-evidence/v2"]
    registry_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_id: str = Field(min_length=1)
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    execution_owner: str = Field(min_length=1)
    execution_started_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["BLOCKED", "EXCLUDED_BY_CLIENT"]
    producer: Literal[
        "independent-readback-collector",
        "trusted-evidence-registry",
        "client-exclusion-authority",
    ]
    observed_at: datetime
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProtectedFinalReadbackArtifact(_StrictModel):
    """Independent collector output used as the only final inventory source."""

    schema_version: Literal["noor-e2e-final-readback-artifact/v2"]
    registry_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    collector_id: str = Field(min_length=1)
    collector_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    journal_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_turn_anchor_at: datetime
    observed_at: datetime
    inventory_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation: ReadbackObservation

    @model_validator(mode="after")
    def _exact_observation_binding(self) -> ProtectedFinalReadbackArtifact:
        if (
            self.observation.phase != "final"
            or self.observation.run_id != self.run_id
            or self.observation.preflight_digest != self.preflight_digest
            or self.observation.collector_id != self.collector_id
            or self.observation.collector_artifact_digest
            != self.collector_artifact_digest
            or self.observation.causal_event_digest != self.journal_head_digest
            or self.observation.observed_at != self.observed_at
            or _digest(self.observation.inventory) != self.inventory_digest
            or self.final_turn_anchor_at.tzinfo is None
            or self.final_turn_anchor_at.utcoffset() is None
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
            or self.observed_at < self.final_turn_anchor_at
        ):
            raise ValueError("final readback artifact observation binding drift")
        return self


class FinalReadbackProducerReceipt(_StrictModel):
    """Receipt from the protected independent final-readback producer store."""

    schema_version: Literal["noor-e2e-final-readback-producer-receipt/v2"]
    registry_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer: Literal["independent-readback-collector"]
    collector_id: str = Field(min_length=1)
    collector_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    journal_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    inventory_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _valid_window(self) -> FinalReadbackProducerReceipt:
        values = (self.observed_at, self.issued_at, self.expires_at)
        if (
            any(item.tzinfo is None or item.utcoffset() is None for item in values)
            or not self.observed_at <= self.issued_at < self.expires_at
        ):
            raise ValueError("final readback receipt window is invalid")
        return self


class GateAttemptV2(_StrictModel):
    schema_version: Literal["noor-e2e-gate-attempt/v2"]
    execution_id: str = Field(min_length=1)
    outcome: Literal["BLOCKED", "EXCLUDED_BY_CLIENT"]
    run_started_at: datetime
    execution_started_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


ExecutedAttemptV2 = ScenarioAttemptV2 | EvidenceBlockAttemptV2


class ValidatedAttempt(_StrictModel):
    execution_id: str
    plan_digest: str
    attempt_digest: str
    outcome: Literal["PASS", "FAIL"]
    oracle_decisions: tuple[dict[str, Any], ...]


def scenario_input_digest(
    *,
    execution_id: str,
    planned_turns: tuple[PlannedTurnV2, ...],
    tester_config_digest: str,
    judge_config_digest: str,
) -> str:
    return _digest(
        {
            "execution_id": execution_id,
            "planned_turns": [item.model_dump(mode="json") for item in planned_turns],
            "tester_config_digest": tester_config_digest,
            "judge_config_digest": judge_config_digest,
        }
    )


def scenario_plan_digest(attempt: ScenarioAttemptV2) -> str:
    return scenario_input_digest(
        execution_id=attempt.execution_id,
        planned_turns=attempt.planned_turns,
        tester_config_digest=attempt.tester_config_digest,
        judge_config_digest=attempt.judge_config_digest,
    )


def evidence_block_input_digest(attempt: EvidenceBlockAttemptV2) -> str:
    return _digest(
        {
            "execution_id": attempt.execution_id,
            "evidence_collection_digest": attempt.evidence_collection_digest,
            "evaluator_config_digest": attempt.evaluator_config_digest,
        }
    )


class GenericAcceptanceRunner:
    """Validate locally captured attempts against the universal compiled policy."""

    def __init__(
        self,
        *,
        registry: TrustedAcceptanceRegistry,
        authority: ExecutionAuthorizationHandle,
        journal: ProtectedExecutionJournal,
    ) -> None:
        authorization = _authorization_from_handle(
            authority,
            protected_root=journal.protected_root,
            run_id=journal.run_id,
            registry=registry,
        )
        validate_execution_authorization(
            authorization,
            policy=registry.compiled_policy,
            plan=registry.compiled_plan,
            registry_id=registry.registry_id,
        )
        if (
            authorization.task1_authorization_digest
            != registry.task1_authorization_digest
            or authorization.task1_input_digests != registry.task1_input_digests
        ):
            raise ExecutionValidationError(
                "authority handle Task 1 immutable binding drift"
            )
        if journal.authorization_digest != _digest(
            authorization.model_dump(mode="json")
        ):
            raise ExecutionValidationError("journal authorization binding drift")
        self.registry = registry
        self.authorization = authorization
        self.journal = journal

    def validate_attempt(self, attempt: ScenarioAttemptV2) -> ValidatedAttempt:
        if (
            attempt.baseline.run_id != self.journal.run_id
            or attempt.final.run_id != self.journal.run_id
        ):
            raise ExecutionValidationError("readback run identity drift")
        scenario = self.registry.compiled_policy.scenarios.get(attempt.execution_id)
        if scenario is None:
            raise ExecutionValidationError(
                "generic scenario runner requires a canonical scenario execution"
            )
        plan_digest = scenario_plan_digest(attempt)
        if (
            self.authorization.execution_input_digests.get(attempt.execution_id)
            != plan_digest
        ):
            raise ExecutionValidationError("authorized planned input digest drift")

        planned_by_id = {item.turn_id: item for item in attempt.planned_turns}
        actual_by_plan = {item.planned_turn_id: item for item in attempt.actual_turns}
        if (
            len(planned_by_id) != len(attempt.planned_turns)
            or len(actual_by_plan) != len(attempt.actual_turns)
            or set(planned_by_id) != set(actual_by_plan)
        ):
            raise ExecutionValidationError("actual turns lack exact planned coverage")

        canonical_assertions = {
            item.assertion_id
            for group in (scenario.checkpoints, scenario.prohibited_outcomes)
            for item in group.values()
        }
        for criterion_id in scenario.criterion_ids:
            canonical_assertions.update(
                item.assertion_id
                for item in self.registry.compiled_policy.criteria[
                    criterion_id
                ].oracle_checks.values()
            )
        planned_criteria = {
            criterion_id
            for item in attempt.planned_turns
            for criterion_id in item.criterion_ids
        }
        planned_assertions = {
            assertion_id
            for item in attempt.planned_turns
            for assertion_id in item.assertion_ids
        }
        if planned_criteria != set(scenario.criterion_ids):
            raise ExecutionValidationError("planned criterion coverage drift")
        if planned_assertions != canonical_assertions:
            raise ExecutionValidationError("planned canonical oracle coverage drift")

        expected_deviations: set[tuple[str, str]] = set()
        for planned_id, planned in planned_by_id.items():
            actual = actual_by_plan[planned_id]
            if (
                actual.expected_behavior_digest != planned.expected_behavior_digest
                or actual.criterion_ids != planned.criterion_ids
                or actual.assertion_ids != planned.assertion_ids
            ):
                raise ExecutionValidationError("actual turn plan binding drift")
            if (
                actual.actual_turn_id != planned_id
                or actual.customer_input_digest != planned.customer_input_digest
            ):
                expected_deviations.add((planned_id, actual.actual_turn_id))
        actual_deviations = {
            (item.planned_turn_id, item.actual_turn_id)
            for item in attempt.adaptive_deviations
        }
        if actual_deviations != expected_deviations:
            raise ExecutionValidationError("adaptive deviation coverage drift")

        evidence_by_assertion = {
            item.assertion_id: item for item in attempt.oracle_evidence
        }
        if (
            len(evidence_by_assertion) != len(attempt.oracle_evidence)
            or set(evidence_by_assertion) != canonical_assertions
        ):
            raise ExecutionValidationError("structured oracle evidence coverage drift")
        decisions = tuple(
            self.registry.evaluate_oracle(
                assertion_id,
                evidence_by_assertion[assertion_id],
            )
            for assertion_id in sorted(canonical_assertions)
        )
        if set(attempt.permission_evidence) != set(scenario.required_permissions):
            raise ExecutionValidationError("permission evidence coverage drift")
        if set(attempt.readback_evidence) != set(scenario.required_readbacks):
            raise ExecutionValidationError("readback evidence coverage drift")

        final_visible = [
            item.timeline.final_visible_at for item in attempt.actual_turns
        ]
        delivered = [
            item.timeline.delivered_at
            for item in attempt.actual_turns
            if item.timeline.delivered_at is not None
        ]
        self.registry.validate_readback_window(
            baseline=attempt.baseline,
            final=attempt.final,
            final_visible_at=final_visible,
            delivered_at=delivered,
            action_at=attempt.action_at,
        )
        if self.journal.phase != "executing":
            raise ExecutionValidationError(
                "attempt validation requires executing phase"
            )
        outcome: Literal["PASS", "FAIL"] = (
            "PASS" if all(item.passed for item in decisions) else "FAIL"
        )
        return ValidatedAttempt(
            execution_id=attempt.execution_id,
            plan_digest=plan_digest,
            attempt_digest=_digest(attempt.model_dump(mode="json")),
            outcome=outcome,
            oracle_decisions=tuple(item.model_dump(mode="json") for item in decisions),
        )

    def validate_gate_attempt(
        self,
        attempt: GateAttemptV2,
        *,
        current_time: datetime | None = None,
    ) -> GateAttemptV2:
        """Validate a zero-turn non-pass without inventing an executed turn."""

        try:
            artifact_payload = _read_protected(
                self.journal.run_root,
                f"gate-evidence/{attempt.execution_id}.json",
            )
            artifact = GateEvidenceArtifact.model_validate(json.loads(artifact_payload))
            receipt_payload = _read_protected(
                self.journal.run_root,
                f"producer-receipts/gates/{attempt.execution_id}.json",
            )
            receipt = GateEvidenceReceipt.model_validate(json.loads(receipt_payload))
        except (ExecutionValidationError, ValueError, json.JSONDecodeError) as exc:
            raise ExecutionValidationError(
                "gate attempt requires a protected producer receipt"
            ) from exc
        now = current_time or datetime.now(UTC)
        criteria = tuple(
            item.criterion_id
            for item in self.registry.compiled_plan.criteria.values()
            if attempt.execution_id in item.obligation_ids
        )
        if (
            attempt.execution_id not in self.authorization.execution_ids
            or artifact.registry_id != self.registry.registry_id
            or artifact.run_id != self.journal.run_id
            or artifact.authorization_digest != self.journal.authorization_digest
            or artifact.execution_id != attempt.execution_id
            or artifact.criterion_ids != criteria
            or artifact.execution_owner != self.authorization.authorization_id
            or artifact.execution_started_event_digest
            != self.journal._execution_started_event_digest
            or artifact.outcome != attempt.outcome
            or receipt.registry_id != artifact.registry_id
            or receipt.run_id != artifact.run_id
            or receipt.execution_id != attempt.execution_id
            or hashlib.sha256(receipt_payload).hexdigest() != attempt.receipt_digest
            or receipt.artifact_sha256 != hashlib.sha256(artifact_payload).hexdigest()
            or receipt.authorization_digest != self.journal.authorization_digest
            or receipt.criterion_ids != criteria
            or receipt.execution_owner != self.authorization.authorization_id
            or receipt.execution_started_event_digest
            != self.journal._execution_started_event_digest
            or receipt.outcome != attempt.outcome
            or receipt.producer != artifact.producer
            or receipt.issued_at != artifact.observed_at
            or attempt.run_started_at.tzinfo is None
            or attempt.run_started_at.utcoffset() is None
            or self.journal._execution_started_at is None
            or attempt.run_started_at != self.journal._execution_started_at
            or attempt.execution_started_event_digest
            != self.journal._execution_started_event_digest
            or not receipt.issued_at <= now < receipt.expires_at
        ):
            raise ExecutionValidationError("gate attempt protected receipt drift")
        criterion_models = [
            self.registry.compiled_plan.criteria[criterion_id]
            for criterion_id in criteria
        ]
        if not criterion_models:
            raise ExecutionValidationError("gate attempt criterion binding drift")
        if attempt.outcome == "BLOCKED":
            if (
                receipt.producer
                not in {
                    "independent-readback-collector",
                    "trusted-evidence-registry",
                }
                or self.journal._execution_started_at is None
                or receipt.issued_at < self.journal._execution_started_at
                or receipt.client_authority_digest is not None
            ):
                raise ExecutionValidationError(
                    "blocked gate lacks independent evidence"
                )
        else:
            matching_grants = [
                item
                for item in self.authorization.client_exclusion_grants
                if item.execution_id == attempt.execution_id
            ]
            expected_client_authority = (
                self.authorization.client_exclusion_authorities.get(
                    attempt.execution_id
                )
            )
            if (
                receipt.producer != "client-exclusion-authority"
                or not all(item.allows_client_exclusion for item in criterion_models)
                or len(matching_grants) != 1
                or expected_client_authority is None
                or receipt.client_authority_digest != expected_client_authority
                or receipt.client_authority_digest
                != _digest(matching_grants[0].model_dump(mode="json"))
                or receipt.criterion_ids != matching_grants[0].criterion_ids
                or not matching_grants[0].issued_at
                <= receipt.issued_at
                < receipt.expires_at
                <= matching_grants[0].expires_at
                or receipt.issued_at >= attempt.run_started_at
                or receipt.issued_at < self.authorization.issued_at
            ):
                raise ExecutionValidationError(
                    "client exclusion lacks pre-existing protected authority"
                )
        return attempt

    def validate_evidence_block(
        self,
        attempt: EvidenceBlockAttemptV2,
    ) -> ValidatedAttempt:
        block = self.registry.compiled_policy.evidence_blocks.get(attempt.execution_id)
        if block is None:
            raise ExecutionValidationError(
                "generic evidence runner requires a canonical evidence block"
            )
        plan_digest = evidence_block_input_digest(attempt)
        if (
            self.authorization.execution_input_digests.get(attempt.execution_id)
            != plan_digest
        ):
            raise ExecutionValidationError(
                "authorized evidence-block input digest drift"
            )
        canonical_assertions = {
            item.assertion_id for item in block.oracle_checks.values()
        }
        for criterion_id in block.criterion_ids:
            canonical_assertions.update(
                item.assertion_id
                for item in self.registry.compiled_policy.criteria[
                    criterion_id
                ].oracle_checks.values()
            )
        evidence_by_assertion = {
            item.assertion_id: item for item in attempt.oracle_evidence
        }
        if (
            len(evidence_by_assertion) != len(attempt.oracle_evidence)
            or set(evidence_by_assertion) != canonical_assertions
        ):
            raise ExecutionValidationError(
                "evidence-block structured oracle coverage drift"
            )
        if set(attempt.permission_evidence) != set(block.required_permissions):
            raise ExecutionValidationError("evidence-block permission coverage drift")
        if self.journal.phase != "executing":
            raise ExecutionValidationError(
                "evidence-block validation requires executing phase"
            )
        decisions = tuple(
            self.registry.evaluate_oracle(
                assertion_id,
                evidence_by_assertion[assertion_id],
            )
            for assertion_id in sorted(canonical_assertions)
        )
        return ValidatedAttempt(
            execution_id=attempt.execution_id,
            plan_digest=plan_digest,
            attempt_digest=_digest(attempt.model_dump(mode="json")),
            outcome=("PASS" if all(item.passed for item in decisions) else "FAIL"),
            oracle_decisions=tuple(item.model_dump(mode="json") for item in decisions),
        )


def _directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None or os.open not in os.supports_dir_fd:
        raise ExecutionValidationError("descriptor-relative no-follow I/O unavailable")
    return cast("int", os.O_RDONLY | nofollow | directory)


def _open_absolute_chain(path: Path, *, create: bool) -> int:
    if not path.is_absolute() or any(
        part in {"", ".", ".."} for part in path.parts[1:]
    ):
        raise ExecutionValidationError("protected path must be absolute and normalized")
    flags = _directory_flags()
    current_fd = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            if create:
                with suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=current_fd)
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
    except OSError as exc:
        os.close(current_fd)
        raise ExecutionValidationError(
            f"protected path violates no-follow policy: {exc}"
        ) from exc
    return current_fd


def _validated_relative(value: str) -> tuple[str, ...]:
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ExecutionValidationError("protected relative path is unsafe")
    return path.parts


def _open_relative_parent(
    root: Path,
    relative: str,
    *,
    create: bool,
) -> tuple[int, str]:
    parts = _validated_relative(relative)
    current_fd = _open_absolute_chain(root, create=create)
    flags = _directory_flags()
    try:
        for part in parts[:-1]:
            if create:
                with suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=current_fd)
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
    except OSError as exc:
        os.close(current_fd)
        raise ExecutionValidationError(
            f"protected parent violates no-follow policy: {exc}"
        ) from exc
    return current_fd, parts[-1]


def _write_exclusive(root: Path, relative: str, value: object) -> str:
    payload = _canonical_bytes(value)
    parent_fd, name = _open_relative_parent(root, relative, create=True)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(name, flags, 0o600, dir_fd=parent_fd)
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise ExecutionValidationError(
            f"protected exclusive write failed: {relative}: {exc}"
        ) from exc
    finally:
        os.close(parent_fd)
    return hashlib.sha256(payload).hexdigest()


def _read_protected(root: Path, relative: str) -> bytes:
    parent_fd, name = _open_relative_parent(root, relative, create=False)
    try:
        fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
        try:
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(fd)
    except OSError as exc:
        raise ExecutionValidationError(
            f"protected read failed: {relative}: {exc}"
        ) from exc
    finally:
        os.close(parent_fd)
    return b"".join(chunks)


class AttemptTransaction:
    def __init__(
        self,
        *,
        journal: ProtectedExecutionJournal,
        transaction_id: str,
    ) -> None:
        self._journal = journal
        self.transaction_id = transaction_id

    def write_raw(self, payload: object) -> str:
        return _write_exclusive(
            self._journal.run_root,
            f"attempts/{self.transaction_id}/raw.json",
            payload,
        )

    def write_tracked(self) -> str:
        """Derive the tracked payload only from the already sealed raw bytes."""

        raw = _read_protected(
            self._journal.run_root,
            f"attempts/{self.transaction_id}/raw.json",
        )
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExecutionValidationError(
                "sealed raw attempt JSON is invalid"
            ) from exc
        redacted = redact_payload(payload)
        validate_redacted_payload(redacted)
        return _write_exclusive(
            self._journal.run_root,
            f"attempts/{self.transaction_id}/tracked.json",
            redacted,
        )

    def commit(self) -> AttemptRecovery:
        return self._journal._finish_attempt(self.transaction_id, abort=False)


class FakeLocalAdapter:
    """No-network adapter used by Task 2 contract tests only."""

    def __init__(
        self,
        *,
        adapter_id: str,
        journal: ProtectedExecutionJournal | None,
    ) -> None:
        if adapter_id not in LOCAL_ADAPTER_IDS:
            raise ExecutionValidationError("only fake local adapter is available")
        self.adapter_id = adapter_id
        self._journal = journal

    def execute(
        self,
        reservation: ActionReservation | None,
        *,
        execution_id: str,
        step_id: str,
        capability: str,
        operation_permission: str,
        destination_digest: str,
        payload_digest: str,
        idempotency_key: str,
        capability_units: dict[str, int],
    ) -> dict[str, str]:
        if (
            reservation is None
            or self._journal is None
            or reservation.adapter_id != self.adapter_id
        ):
            raise ExecutionValidationError(
                "adapter call requires a protected action reservation"
            )
        self._journal.consume_permit(
            reservation,
            adapter_id=self.adapter_id,
            execution_id=execution_id,
            step_id=step_id,
            capability=capability,
            operation_permission=operation_permission,
            destination_digest=destination_digest,
            payload_digest=payload_digest,
            idempotency_key=idempotency_key,
            capability_units=capability_units,
        )
        return {
            "status": "synthetic",
            "reservation_digest": reservation.reservation_digest,
        }


def _write_test_final_readback_bundle(
    journal: ProtectedExecutionJournal,
    observation: ReadbackObservation,
    *,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> str:
    """Fixture-only stand-in for the Task 2 independent collector producer."""

    if journal._final_turn_occurred_at is None or journal.previous_event_digest is None:
        raise ExecutionValidationError(
            "final readback producer requires a final-turn journal anchor"
        )
    receipt_issued_at = issued_at or observation.observed_at
    receipt_expires_at = expires_at or receipt_issued_at + _MAX_FINAL_READBACK_AGE
    artifact = ProtectedFinalReadbackArtifact(
        schema_version="noor-e2e-final-readback-artifact/v2",
        registry_id=journal.authorization.registry_id,
        run_id=journal.run_id,
        authorization_digest=journal.authorization_digest,
        preflight_digest=journal.authorization.preflight_digest,
        collector_id=observation.collector_id,
        collector_artifact_digest=observation.collector_artifact_digest,
        journal_head_digest=journal.previous_event_digest,
        final_turn_anchor_at=journal._final_turn_occurred_at,
        observed_at=observation.observed_at,
        inventory_digest=_digest(observation.inventory),
        observation=observation,
    )
    artifact_sha256 = _write_exclusive(
        journal.run_root,
        "collector-artifacts/final-readback.json",
        artifact.model_dump(mode="json"),
    )
    receipt = FinalReadbackProducerReceipt(
        schema_version="noor-e2e-final-readback-producer-receipt/v2",
        registry_id=artifact.registry_id,
        run_id=artifact.run_id,
        authorization_digest=artifact.authorization_digest,
        preflight_digest=artifact.preflight_digest,
        producer="independent-readback-collector",
        collector_id=artifact.collector_id,
        collector_artifact_digest=artifact.collector_artifact_digest,
        journal_head_digest=artifact.journal_head_digest,
        artifact_sha256=artifact_sha256,
        inventory_digest=artifact.inventory_digest,
        observed_at=artifact.observed_at,
        issued_at=receipt_issued_at,
        expires_at=receipt_expires_at,
    )
    return _write_exclusive(
        journal.run_root,
        "producer-receipts/final-readback.json",
        receipt.model_dump(mode="json"),
    )


def _write_test_gate_evidence_bundle(
    *,
    registry: TrustedAcceptanceRegistry,
    journal: ProtectedExecutionJournal,
    execution_id: str,
    outcome: Literal["BLOCKED", "EXCLUDED_BY_CLIENT"],
    producer: Literal[
        "independent-readback-collector",
        "trusted-evidence-registry",
        "client-exclusion-authority",
    ],
    observed_at: datetime,
    expires_at: datetime,
    client_authority_digest: str | None = None,
) -> str:
    """Fixture-only stand-in for protected gate evidence producers."""

    if journal._execution_started_event_digest is None:
        raise ExecutionValidationError(
            "gate producer requires journal-owned execution start"
        )
    criterion_ids = tuple(
        criterion.criterion_id
        for criterion in registry.compiled_plan.criteria.values()
        if execution_id in criterion.obligation_ids
    )
    artifact = GateEvidenceArtifact(
        schema_version="noor-e2e-gate-evidence/v2",
        registry_id=registry.registry_id,
        run_id=journal.run_id,
        authorization_digest=journal.authorization_digest,
        execution_id=execution_id,
        criterion_ids=criterion_ids,
        execution_owner=journal.authorization.authorization_id,
        execution_started_event_digest=journal._execution_started_event_digest,
        outcome=outcome,
        producer=producer,
        observed_at=observed_at,
        evidence_digest=_digest(
            {
                "execution_id": execution_id,
                "criterion_ids": criterion_ids,
                "outcome": outcome,
                "observed_at": observed_at.isoformat(),
            }
        ),
    )
    artifact_sha256 = _write_exclusive(
        journal.run_root,
        f"gate-evidence/{execution_id}.json",
        artifact.model_dump(mode="json"),
    )
    receipt = GateEvidenceReceipt(
        schema_version="noor-e2e-gate-evidence-receipt/v2",
        registry_id=artifact.registry_id,
        run_id=artifact.run_id,
        authorization_digest=artifact.authorization_digest,
        execution_id=execution_id,
        criterion_ids=criterion_ids,
        execution_owner=artifact.execution_owner,
        execution_started_event_digest=artifact.execution_started_event_digest,
        artifact_sha256=artifact_sha256,
        outcome=outcome,
        producer=producer,
        issued_at=observed_at,
        expires_at=expires_at,
        client_authority_digest=client_authority_digest,
    )
    return _write_exclusive(
        journal.run_root,
        f"producer-receipts/gates/{execution_id}.json",
        receipt.model_dump(mode="json"),
    )


class ProtectedExecutionJournal:
    """Append-only phase/action journal under a protected external root."""

    def __init__(
        self,
        *,
        protected_root: Path,
        run_id: str,
        authorization: ExecutionAuthorizationV2,
        authority_receipt_digest: str,
    ) -> None:
        _validate_run_id(run_id)
        self.protected_root = protected_root
        self.run_id = run_id
        self.run_root = protected_root / run_id
        self.authorization = authorization
        self.authorization_digest = _digest(authorization.model_dump(mode="json"))
        self.authority_receipt_digest = authority_receipt_digest
        self.phase = "prepared"
        self.cursor = 0
        self.previous_event_digest: str | None = None
        self.quota_usage = QuotaUsage()
        self._actions: dict[str, ActionState] = {}
        self._reservations: dict[str, ActionReservation] = {}
        self._attempted_executions: list[str] = []
        self._authorization_scenarios = 0
        self._authorization_action_ids: set[str] = set()
        self._authorization_idempotency_keys: set[str] = set()
        self._authorization_reservation_digests: dict[str, str] = {}
        self._authorization_reservation_runs: dict[str, str] = {}
        self._authorization_cost_settlements: dict[str, ActionCostSettlement] = {}
        self._authorization_ledger_cursor = 0
        self._authorization_ledger_head: str | None = None
        self._final_turn_occurred_at: datetime | None = None
        self._execution_started_at: datetime | None = None
        self._execution_started_event_digest: str | None = None

    @classmethod
    def create(
        cls,
        *,
        protected_root: Path,
        run_id: str,
        authority: ExecutionAuthorizationHandle,
    ) -> ProtectedExecutionJournal:
        authorization = _authorization_from_handle(
            authority,
            protected_root=protected_root,
            run_id=run_id,
        )
        journal = cls(
            protected_root=protected_root,
            run_id=run_id,
            authorization=authorization,
            authority_receipt_digest=authority._receipt_digest,
        )
        journal._reload_authorization_ledger()
        fd = _open_absolute_chain(journal.run_root, create=True)
        os.fchmod(fd, 0o700)
        os.close(fd)
        journal._append_event(
            phase="prepared",
            kind="prepared",
            data={
                "authorization_digest": journal.authorization_digest,
                "anchor_store_id": authorization.store_ids.anchor_store_id,
                "authority_receipt_digest": authority._receipt_digest,
            },
        )
        return journal

    @classmethod
    def open(
        cls,
        *,
        protected_root: Path,
        run_id: str,
        authority: ExecutionAuthorizationHandle,
    ) -> ProtectedExecutionJournal:
        authorization = _authorization_from_handle(
            authority,
            protected_root=protected_root,
            run_id=run_id,
        )
        journal = cls(
            protected_root=protected_root,
            run_id=run_id,
            authorization=authorization,
            authority_receipt_digest=authority._receipt_digest,
        )
        journal._reload_authorization_ledger()
        journal_fd = _open_absolute_chain(
            journal.run_root / "journal",
            create=False,
        )
        try:
            names = sorted(os.listdir(journal_fd))
        finally:
            os.close(journal_fd)
        previous_digest: str | None = None
        for expected_cursor, name in enumerate(names, start=1):
            if name != f"{expected_cursor:06d}.json":
                raise ExecutionValidationError("journal cursor sequence drift")
            payload = _read_protected(journal.run_root, f"journal/{name}")
            try:
                event = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ExecutionValidationError("journal event JSON invalid") from exc
            if (
                event.get("cursor") != expected_cursor
                or event.get("previous_event_digest") != previous_digest
            ):
                raise ExecutionValidationError("journal digest/cursor causality drift")
            if expected_cursor == 1 and (
                event.get("kind") != "prepared"
                or event.get("data", {}).get("authorization_digest")
                != journal.authorization_digest
                or event.get("data", {}).get("authority_receipt_digest")
                != journal.authority_receipt_digest
            ):
                raise ExecutionValidationError("journal authorization binding drift")
            journal._apply_loaded_event(event)
            previous_digest = hashlib.sha256(payload).hexdigest()
            if event.get("kind") == "execution_started":
                journal._execution_started_event_digest = previous_digest
        if not names:
            raise ExecutionValidationError("protected journal is empty")
        journal.previous_event_digest = previous_digest
        return journal

    def _apply_loaded_event(self, event: dict[str, Any]) -> None:
        self.cursor = int(event["cursor"])
        self.phase = str(event["phase"])
        kind = str(event["kind"])
        data = event.get("data", {})
        if kind == "action_reserved":
            reservation = ActionReservation.model_validate(data["reservation"])
            self._reservations[reservation.action_id] = reservation
            self._actions[reservation.action_id] = "reserved"
        elif kind == "action_completed":
            self._actions[str(data["action_id"])] = str(data["state"])  # type: ignore[assignment]
        elif kind == "unknown_action_reconciled":
            receipt = UnknownActionReconciliationReceipt.model_validate(data)
            self._actions[receipt.action_id] = receipt.resolved_state
        elif kind == "permit_consumed":
            self._actions[str(data["action_id"])] = "unknown"
        elif kind == "action_cost_settled":
            settlement = ActionCostSettlement.model_validate(data["settlement"])
            if (
                self._authorization_cost_settlements.get(settlement.action_id)
                != settlement
            ):
                raise ExecutionValidationError(
                    "journal cost settlement differs from authorization ledger"
                )
        elif kind == "attempt_intent":
            self._attempted_executions.append(str(data["execution_id"]))
        elif kind == "execution_started":
            started_at = datetime.fromisoformat(str(data["started_at"]))
            if started_at.tzinfo is None or started_at.utcoffset() is None:
                raise ExecutionValidationError("execution start timestamp is invalid")
            self._execution_started_at = started_at
        elif kind == "final_turn_anchored":
            occurred_at = datetime.fromisoformat(str(data["occurred_at"]))
            if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
                raise ExecutionValidationError("final-turn anchor timestamp is invalid")
            self._final_turn_occurred_at = occurred_at

    def _append_event(
        self,
        *,
        phase: str,
        kind: str,
        data: dict[str, Any],
    ) -> str:
        cursor = self.cursor + 1
        event = {
            "schema_version": "noor-e2e-protected-event/v2",
            "cursor": cursor,
            "phase": phase,
            "kind": kind,
            "previous_event_digest": self.previous_event_digest,
            "data": data,
        }
        digest = _write_exclusive(
            self.run_root,
            f"journal/{cursor:06d}.json",
            event,
        )
        self.cursor = cursor
        self.previous_event_digest = digest
        self.phase = phase
        return digest

    def _transition(
        self,
        *,
        expected: str,
        target: str,
        kind: str,
        data: dict[str, Any],
    ) -> str:
        if self.phase != expected:
            raise ExecutionValidationError(
                f"phase transition requires {expected}, got {self.phase}"
            )
        expected_index = _PHASES.index(expected)
        if _PHASES[expected_index + 1] != target:
            raise ExecutionValidationError("phase transition is not canonical")
        return self._append_event(phase=target, kind=kind, data=data)

    def seal_baseline(self, observation: ReadbackObservation) -> None:
        if observation.phase != "baseline":
            raise ExecutionValidationError("baseline observation phase drift")
        if (
            observation.run_id != self.run_id
            or observation.preflight_digest != self.authorization.preflight_digest
            or observation.collector_artifact_digest
            != self.authorization.readback_collector_digest
        ):
            raise ExecutionValidationError("baseline preflight/run binding drift")
        self._transition(
            expected="prepared",
            target="baseline_sealed",
            kind="baseline_sealed",
            data={
                "source_id": observation.source_id,
                "collector_id": observation.collector_id,
                "observed_at": observation.observed_at.isoformat(),
                "content_digest": observation.content_digest,
            },
        )

    def begin_execution(self) -> None:
        started_at = datetime.now(UTC)
        self._execution_started_event_digest = self._transition(
            expected="baseline_sealed",
            target="executing",
            kind="execution_started",
            data={"started_at": started_at.isoformat()},
        )
        self._execution_started_at = started_at

    def _consume(self, reservation: ActionReservation) -> None:
        subsystems = dict(self.quota_usage.subsystem_usage)
        subsystems[reservation.subsystem] = (
            subsystems.get(reservation.subsystem, 0)
            + reservation.capability_units[reservation.subsystem]
        )
        self.quota_usage = QuotaUsage(
            messages=self.quota_usage.messages + reservation.messages,
            model_calls=self.quota_usage.model_calls + reservation.model_calls,
            cost_usd=self.quota_usage.cost_usd + reservation.cost_usd,
            subsystem_usage=subsystems,
        )

    @property
    def _authorization_ledger_root(self) -> Path:
        return (
            self.protected_root / ".authorization-ledgers" / self.authorization_digest
        )

    def _reload_authorization_ledger(self) -> None:
        self.quota_usage = QuotaUsage()
        self._authorization_scenarios = 0
        self._authorization_action_ids = set()
        self._authorization_idempotency_keys = set()
        self._authorization_reservation_digests = {}
        self._authorization_reservation_runs = {}
        self._authorization_cost_settlements = {}
        self._authorization_ledger_cursor = 0
        self._authorization_ledger_head = None
        try:
            ledger_fd = _open_absolute_chain(
                self._authorization_ledger_root,
                create=False,
            )
        except ExecutionValidationError:
            return
        try:
            names = sorted(os.listdir(ledger_fd))
        finally:
            os.close(ledger_fd)
        previous: str | None = None
        for expected, name in enumerate(names, start=1):
            if name != f"{expected:06d}.json":
                raise ExecutionValidationError(
                    "authorization quota ledger cursor sequence drift"
                )
            payload = _read_protected(
                self._authorization_ledger_root,
                name,
            )
            try:
                event = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ExecutionValidationError(
                    "authorization quota ledger JSON invalid"
                ) from exc
            if (
                event.get("cursor") != expected
                or event.get("previous_event_digest") != previous
                or event.get("authorization_digest") != self.authorization_digest
            ):
                raise ExecutionValidationError(
                    "authorization quota ledger causality drift"
                )
            if event.get("kind") == "action_reserved":
                reservation = ActionReservation.model_validate(event["reservation"])
                if (
                    reservation.action_id in self._authorization_action_ids
                    or reservation.idempotency_key
                    in self._authorization_idempotency_keys
                ):
                    raise ExecutionValidationError(
                        "authorization action/idempotency ledger duplicate"
                    )
                self._authorization_action_ids.add(reservation.action_id)
                self._authorization_idempotency_keys.add(reservation.idempotency_key)
                self._authorization_reservation_digests[reservation.action_id] = (
                    reservation.reservation_digest
                )
                self._authorization_reservation_runs[reservation.action_id] = (
                    reservation.run_id
                )
                self._consume(reservation)
            elif event.get("kind") == "action_cost_settled":
                settlement = ActionCostSettlement.model_validate(event["settlement"])
                if (
                    settlement.authorization_digest != self.authorization_digest
                    or self._authorization_reservation_runs.get(settlement.action_id)
                    != settlement.run_id
                    or self._authorization_reservation_digests.get(settlement.action_id)
                    != settlement.reservation_digest
                    or settlement.action_id in self._authorization_cost_settlements
                ):
                    raise ExecutionValidationError(
                        "authorization action cost settlement drift"
                    )
                self._authorization_cost_settlements[settlement.action_id] = settlement
            elif event.get("kind") == "scenario_reserved":
                self._authorization_scenarios += 1
            else:
                raise ExecutionValidationError(
                    "authorization quota ledger event kind drift"
                )
            previous = hashlib.sha256(payload).hexdigest()
        self._authorization_ledger_cursor = len(names)
        self._authorization_ledger_head = previous

    def _append_authorization_ledger(
        self,
        *,
        kind: Literal[
            "action_reserved",
            "action_cost_settled",
            "scenario_reserved",
        ],
        data: dict[str, Any],
    ) -> None:
        event = {
            "schema_version": "noor-e2e-authorization-quota-event/v2",
            "cursor": self._authorization_ledger_cursor + 1,
            "previous_event_digest": self._authorization_ledger_head,
            "authorization_digest": self.authorization_digest,
            "kind": kind,
            **data,
        }
        digest = _write_exclusive(
            self._authorization_ledger_root,
            f"{self._authorization_ledger_cursor + 1:06d}.json",
            event,
        )
        self._authorization_ledger_cursor += 1
        self._authorization_ledger_head = digest

    def reserve_action(
        self,
        *,
        action_id: str,
        adapter_id: str,
        subsystem: str,
        execution_id: str,
        step_id: str,
        capability: str,
        operation_permission: str,
        destination_digest: str,
        payload_digest: str,
        idempotency_key: str,
        capability_units: dict[str, int],
        messages: int,
        model_calls: int,
        cost_usd: float,
    ) -> ActionReservation:
        if self.phase != "executing":
            raise ExecutionValidationError(
                "action reservation requires executing phase"
            )
        if adapter_id not in self.authorization.adapter_ids:
            raise ExecutionValidationError("action adapter is not authorized")
        if execution_id not in self.authorization.execution_ids:
            raise ExecutionValidationError("action execution is not authorized")
        if operation_permission not in self.authorization.permissions:
            raise ExecutionValidationError(
                "action operation permission is not authorized"
            )
        if (
            not step_id
            or not capability
            or not idempotency_key
            or len(destination_digest) != 64
            or len(payload_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in destination_digest + payload_digest
            )
            or set(capability_units) != {subsystem}
            or any(value <= 0 for value in capability_units.values())
        ):
            raise ExecutionValidationError("action request binding is invalid")
        issued_at = datetime.now(UTC)
        if (
            not self.authorization.issued_at
            <= issued_at
            < self.authorization.expires_at
        ):
            raise ExecutionValidationError(
                "action reservation authorization is expired"
            )
        requested_identity = {
            "action_id": action_id,
            "execution_id": execution_id,
            "step_id": step_id,
            "capability": capability,
            "operation_permission": operation_permission,
            "adapter_id": adapter_id,
            "subsystem": subsystem,
            "destination_digest": destination_digest,
            "payload_digest": payload_digest,
            "idempotency_key": idempotency_key,
            "capability_units": capability_units,
        }
        matching_specs = [
            spec
            for spec in self.authorization.action_specs
            if spec.model_dump(mode="json", exclude={"quota_charge"})
            == requested_identity
        ]
        if len(matching_specs) != 1:
            raise ExecutionValidationError("protected authorized action spec mismatch")
        if (
            messages < 0
            or model_calls < 0
            or cost_usd < 0
            or not math.isfinite(cost_usd)
        ):
            raise ExecutionValidationError(
                "reservation quota values must be non-negative and finite"
            )
        charge = matching_specs[0].quota_charge
        if (
            messages != charge.messages
            or model_calls != charge.model_calls
            or cost_usd != charge.max_cost_usd
        ):
            raise ExecutionValidationError(
                "protected action quota charge undercharge or drift"
            )
        if action_id in self._actions:
            raise ExecutionValidationError("action identity is already reserved")
        self._reload_authorization_ledger()
        if (
            action_id in self._authorization_action_ids
            or idempotency_key in self._authorization_idempotency_keys
        ):
            raise ExecutionValidationError(
                "authorization action/idempotency identity was already consumed"
            )
        identity = {
            "action_id": action_id,
            "run_id": self.run_id,
            "authorization_digest": self.authorization_digest,
            "execution_id": execution_id,
            "step_id": step_id,
            "capability": capability,
            "operation_permission": operation_permission,
            "adapter_id": adapter_id,
            "subsystem": subsystem,
            "destination_digest": destination_digest,
            "payload_digest": payload_digest,
            "idempotency_key": idempotency_key,
            "capability_units": capability_units,
            "messages": messages,
            "model_calls": model_calls,
            "cost_usd": cost_usd,
            "issued_at": issued_at.isoformat(),
            "expires_at": self.authorization.expires_at.isoformat(),
            "next_cursor": self.cursor + 1,
        }
        reservation = ActionReservation(
            action_id=action_id,
            run_id=self.run_id,
            authorization_digest=self.authorization_digest,
            execution_id=execution_id,
            step_id=step_id,
            capability=capability,
            operation_permission=operation_permission,
            adapter_id=adapter_id,
            subsystem=subsystem,
            destination_digest=destination_digest,
            payload_digest=payload_digest,
            idempotency_key=idempotency_key,
            capability_units=capability_units,
            messages=messages,
            model_calls=model_calls,
            cost_usd=cost_usd,
            issued_at=issued_at,
            expires_at=self.authorization.expires_at,
            reservation_digest=_digest(identity),
        )
        projected_messages = self.quota_usage.messages + messages
        projected_calls = self.quota_usage.model_calls + model_calls
        projected_cost = self.quota_usage.cost_usd + cost_usd
        projected_subsystem = (
            self.quota_usage.subsystem_usage.get(subsystem, 0)
            + capability_units[subsystem]
        )
        quotas = self.authorization.quotas
        if (
            projected_messages > quotas.max_messages
            or projected_calls > quotas.max_model_calls
            or projected_cost > quotas.max_cost_usd
            or projected_subsystem > quotas.subsystem_quotas.get(subsystem, 0)
        ):
            raise ExecutionValidationError("protected action reservation exceeds quota")
        self._append_authorization_ledger(
            kind="action_reserved",
            data={"reservation": reservation.model_dump(mode="json")},
        )
        self._append_event(
            phase="executing",
            kind="action_reserved",
            data={"reservation": reservation.model_dump(mode="json")},
        )
        self._reservations[action_id] = reservation
        self._actions[action_id] = "reserved"
        self._consume(reservation)
        self._authorization_action_ids.add(action_id)
        self._authorization_idempotency_keys.add(idempotency_key)
        self._authorization_reservation_digests[action_id] = (
            reservation.reservation_digest
        )
        self._authorization_reservation_runs[action_id] = reservation.run_id
        return reservation

    def consume_permit(
        self,
        reservation: ActionReservation,
        *,
        adapter_id: str,
        execution_id: str,
        step_id: str,
        capability: str,
        operation_permission: str,
        destination_digest: str,
        payload_digest: str,
        idempotency_key: str,
        capability_units: dict[str, int],
    ) -> None:
        """Atomically validate and consume the one-use protected permit."""

        if (
            self.phase != "executing"
            or adapter_id != reservation.adapter_id
            or reservation.run_id != self.run_id
            or reservation.authorization_digest != self.authorization_digest
            or execution_id != reservation.execution_id
            or step_id != reservation.step_id
            or capability != reservation.capability
            or operation_permission != reservation.operation_permission
            or destination_digest != reservation.destination_digest
            or payload_digest != reservation.payload_digest
            or idempotency_key != reservation.idempotency_key
            or capability_units != reservation.capability_units
            or not reservation.issued_at <= datetime.now(UTC) < reservation.expires_at
            or self._actions.get(reservation.action_id) != "reserved"
            or self._reservations.get(reservation.action_id) != reservation
        ):
            raise ExecutionValidationError(
                "forged, reused, or missing protected reservation"
            )
        self._append_event(
            phase="executing",
            kind="permit_consumed",
            data={
                "action_id": reservation.action_id,
                "reservation_digest": reservation.reservation_digest,
                "adapter_id": adapter_id,
                "execution_id": execution_id,
                "step_id": step_id,
                "capability": capability,
                "operation_permission": operation_permission,
                "destination_digest": destination_digest,
                "payload_digest": payload_digest,
                "idempotency_key": idempotency_key,
                "capability_units": capability_units,
            },
        )
        self._actions[reservation.action_id] = "unknown"

    def complete_action(
        self,
        reservation: ActionReservation,
        *,
        state: Literal["succeeded", "failed", "unknown"],
        outcome_digest: str,
    ) -> None:
        if self._actions.get(reservation.action_id) != "unknown":
            raise ExecutionValidationError("action completion lacks active reservation")
        if self._reservations.get(reservation.action_id) != reservation:
            raise ExecutionValidationError("action reservation identity drift")
        if len(outcome_digest) != 64:
            raise ExecutionValidationError("action outcome digest must be SHA-256")
        if state != "unknown":
            raise ExecutionValidationError(
                "dispatch result cannot terminalize an uncertain action; "
                "independent reconciliation is required"
            )
        self._append_event(
            phase="executing",
            kind="action_completed",
            data={
                "action_id": reservation.action_id,
                "reservation_digest": reservation.reservation_digest,
                "state": state,
                "outcome_digest": outcome_digest,
            },
        )
        self._actions[reservation.action_id] = state

    def settle_action_cost(
        self,
        reservation: ActionReservation,
        *,
        actual_cost_usd: float,
    ) -> ActionCostSettlement:
        """Record bounded actual cost without releasing consumed quota."""

        if self._actions.get(reservation.action_id) not in {
            "succeeded",
            "failed",
        }:
            raise ExecutionValidationError(
                "action cost settlement requires independent terminal reconciliation"
            )
        if self._reservations.get(reservation.action_id) != reservation:
            raise ExecutionValidationError("action cost settlement reservation drift")
        if reservation.action_id in self._authorization_cost_settlements:
            raise ExecutionValidationError("action cost is already settled")
        spec = next(
            (
                item
                for item in self.authorization.action_specs
                if item.action_id == reservation.action_id
            ),
            None,
        )
        if (
            spec is None
            or reservation.messages != spec.quota_charge.messages
            or reservation.model_calls != spec.quota_charge.model_calls
            or reservation.cost_usd != spec.quota_charge.max_cost_usd
        ):
            raise ExecutionValidationError("action cost settlement authority drift")
        settled_at = datetime.now(UTC)
        identity = {
            "schema_version": "noor-e2e-action-cost-settlement/v2",
            "authorization_digest": self.authorization_digest,
            "run_id": self.run_id,
            "action_id": reservation.action_id,
            "reservation_digest": reservation.reservation_digest,
            "reserved_cost_usd": reservation.cost_usd,
            "actual_cost_usd": actual_cost_usd,
            "cost_settlement": spec.quota_charge.cost_settlement,
            "settled_at": settled_at.isoformat(),
        }
        try:
            settlement = ActionCostSettlement(
                **identity,
                settlement_digest=_digest(identity),
            )
        except ValueError as exc:
            raise ExecutionValidationError(
                "action cost settlement exceeds authorized maximum"
            ) from exc
        self._append_authorization_ledger(
            kind="action_cost_settled",
            data={"settlement": settlement.model_dump(mode="json")},
        )
        self._authorization_cost_settlements[reservation.action_id] = settlement
        self._append_event(
            phase="executing",
            kind="action_cost_settled",
            data={"settlement": settlement.model_dump(mode="json")},
        )
        return settlement

    def reconcile_unknown_action(
        self,
        *,
        action_id: str,
        receipt_digest: str,
    ) -> None:
        """Resolve unknown dispatch only from an independent fresh collector."""

        if len(receipt_digest) != 64 or any(
            character not in "0123456789abcdef" for character in receipt_digest
        ):
            raise ExecutionValidationError("reconciliation receipt digest is invalid")
        try:
            payload = _read_protected(
                self.run_root,
                f"independent-reconciliation/{action_id}.json",
            )
            receipt = UnknownActionReconciliationReceipt.model_validate(
                json.loads(payload)
            )
        except (ExecutionValidationError, ValueError, json.JSONDecodeError) as exc:
            raise ExecutionValidationError(
                "unknown action needs a protected independent reconciliation receipt"
            ) from exc
        reservation = self._reservations.get(action_id)
        if (
            reservation is None
            or self._actions.get(action_id) != "unknown"
            or receipt.registry_id != self.authorization.registry_id
            or receipt.run_id != self.run_id
            or receipt.authorization_digest != self.authorization_digest
            or receipt.action_id != action_id
            or receipt.reservation_digest != reservation.reservation_digest
            or receipt.collector_id not in self.authorization.collector_ids
            or receipt.producer != "independent-readback-collector"
            or hashlib.sha256(payload).hexdigest() != receipt_digest
            or receipt.causal_event_digest != self.previous_event_digest
            or not receipt.observed_at <= datetime.now(UTC) < receipt.expires_at
        ):
            raise ExecutionValidationError(
                "unknown action requires a fresh independent reconciliation receipt"
            )
        self._append_event(
            phase="executing",
            kind="unknown_action_reconciled",
            data=receipt.model_dump(mode="json"),
        )
        self._actions[action_id] = receipt.resolved_state

    def anchor_final_turn(self, *, event_digest: str, occurred_at: datetime) -> None:
        if any(state in {"reserved", "unknown"} for state in self._actions.values()):
            raise ExecutionValidationError(
                "unknown or uncompleted action blocks final-turn closeout"
            )
        if (
            len(event_digest) != 64
            or any(character not in "0123456789abcdef" for character in event_digest)
            or occurred_at.tzinfo is None
            or occurred_at.utcoffset() is None
        ):
            raise ExecutionValidationError("final-turn anchor identity is invalid")
        self._transition(
            expected="executing",
            target="final_turn_anchored",
            kind="final_turn_anchored",
            data={
                "event_digest": event_digest,
                "occurred_at": occurred_at.isoformat(),
            },
        )
        self._final_turn_occurred_at = occurred_at

    def seal_final_readback(
        self,
        observation: ReadbackObservation,
        *,
        receipt_digest: str | None = None,
        current_time: datetime | None = None,
    ) -> None:
        try:
            artifact_payload = _read_protected(
                self.run_root,
                "collector-artifacts/final-readback.json",
            )
            artifact = ProtectedFinalReadbackArtifact.model_validate(
                json.loads(artifact_payload)
            )
            receipt_payload = _read_protected(
                self.run_root,
                "producer-receipts/final-readback.json",
            )
            receipt = FinalReadbackProducerReceipt.model_validate(
                json.loads(receipt_payload)
            )
        except (ExecutionValidationError, ValueError, json.JSONDecodeError) as exc:
            raise ExecutionValidationError(
                "final readback requires a protected collector producer receipt"
            ) from exc
        now = current_time or datetime.now(UTC)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ExecutionValidationError(
                "final readback validation time must be aware"
            )
        if (
            self._final_turn_occurred_at is None
            or receipt_digest is None
            or hashlib.sha256(receipt_payload).hexdigest() != receipt_digest
            or receipt.artifact_sha256 != hashlib.sha256(artifact_payload).hexdigest()
            or artifact.observation != observation
            or artifact.registry_id != self.authorization.registry_id
            or artifact.run_id != self.run_id
            or artifact.authorization_digest != self.authorization_digest
            or artifact.preflight_digest != self.authorization.preflight_digest
            or artifact.collector_id not in self.authorization.collector_ids
            or tuple(self.authorization.collector_ids) != (artifact.collector_id,)
            or artifact.collector_artifact_digest
            != self.authorization.readback_collector_digest
            or artifact.journal_head_digest != self.previous_event_digest
            or artifact.final_turn_anchor_at != self._final_turn_occurred_at
            or artifact.inventory_digest != _digest(observation.inventory)
            or receipt.registry_id != artifact.registry_id
            or receipt.run_id != artifact.run_id
            or receipt.authorization_digest != artifact.authorization_digest
            or receipt.preflight_digest != artifact.preflight_digest
            or receipt.collector_id != artifact.collector_id
            or receipt.collector_artifact_digest != artifact.collector_artifact_digest
            or receipt.journal_head_digest != artifact.journal_head_digest
            or receipt.inventory_digest != artifact.inventory_digest
            or receipt.observed_at != artifact.observed_at
            or receipt.producer != "independent-readback-collector"
            or artifact.observed_at < self._final_turn_occurred_at
            or artifact.observed_at > now
            or now - artifact.observed_at > _MAX_FINAL_READBACK_AGE
            or not receipt.issued_at <= now < receipt.expires_at
        ):
            raise ExecutionValidationError(
                "final readback protected collector receipt binding drift"
            )
        if (
            observation.phase != "final"
            or observation.run_id != self.run_id
            or observation.preflight_digest != self.authorization.preflight_digest
            or observation.collector_artifact_digest
            != self.authorization.readback_collector_digest
            or observation.causal_event_digest != self.previous_event_digest
        ):
            raise ExecutionValidationError(
                "final readback protected causality/preflight binding drift"
            )
        self._transition(
            expected="final_turn_anchored",
            target="final_readback_sealed",
            kind="final_readback_sealed",
            data={
                "source_id": observation.source_id,
                "collector_id": observation.collector_id,
                "observed_at": observation.observed_at.isoformat(),
                "content_digest": observation.content_digest,
                "causal_event_digest": observation.causal_event_digest,
                "collector_receipt_digest": receipt_digest,
                "inventory_digest": artifact.inventory_digest,
            },
        )

    def mark_evaluated(self, *, evaluation_digest: str) -> None:
        if len(evaluation_digest) != 64 or any(
            character not in "0123456789abcdef" for character in evaluation_digest
        ):
            raise ExecutionValidationError("evaluation digest must be SHA-256")
        self._transition(
            expected="final_readback_sealed",
            target="evaluated",
            kind="evaluated",
            data={"evaluation_digest": evaluation_digest},
        )

    def commit_phase(self, *, attempt_chain_digest: str) -> None:
        if len(attempt_chain_digest) != 64 or any(
            character not in "0123456789abcdef" for character in attempt_chain_digest
        ):
            raise ExecutionValidationError("attempt chain digest must be SHA-256")
        self._transition(
            expected="evaluated",
            target="attempt_committed",
            kind="attempt_committed",
            data={"attempt_chain_digest": attempt_chain_digest},
        )

    def begin_attempt(
        self,
        *,
        execution_id: str,
        attempt_number: int,
        intent_digest: str,
    ) -> AttemptTransaction:
        if self.phase != "executing":
            raise ExecutionValidationError(
                "attempt intent requires contiguous executing phase"
            )
        if execution_id not in self.authorization.execution_ids:
            raise ExecutionValidationError(
                "attempt requires a canonical execution identity"
            )
        if attempt_number < 1:
            raise ExecutionValidationError("attempt number must be positive")
        if len(intent_digest) != 64 or any(
            character not in "0123456789abcdef" for character in intent_digest
        ):
            raise ExecutionValidationError("attempt intent digest must be SHA-256")
        self._reload_authorization_ledger()
        if self._authorization_scenarios >= self.authorization.quotas.max_scenarios:
            raise ExecutionValidationError(
                "authorization-scoped scenario quota exceeded"
            )
        transaction_id = f"{execution_id.lower()}-attempt-{attempt_number:03d}"
        self._append_authorization_ledger(
            kind="scenario_reserved",
            data={
                "run_id": self.run_id,
                "transaction_id": transaction_id,
                "execution_id": execution_id,
            },
        )
        self._authorization_scenarios += 1
        _write_exclusive(
            self.run_root,
            f"attempts/{transaction_id}/intent.json",
            {
                "schema_version": "noor-e2e-attempt-intent/v2",
                "transaction_id": transaction_id,
                "execution_id": execution_id,
                "attempt_number": attempt_number,
                "intent_digest": intent_digest,
                "authorization_digest": self.authorization_digest,
            },
        )
        self._append_event(
            phase="executing",
            kind="attempt_intent",
            data={
                "transaction_id": transaction_id,
                "execution_id": execution_id,
                "attempt_number": attempt_number,
                "intent_digest": intent_digest,
            },
        )
        self._attempted_executions.append(execution_id)
        return AttemptTransaction(journal=self, transaction_id=transaction_id)

    def _optional_digest(self, relative: str) -> str | None:
        try:
            return hashlib.sha256(_read_protected(self.run_root, relative)).hexdigest()
        except ExecutionValidationError:
            return None

    def _finish_attempt(
        self,
        transaction_id: str,
        *,
        abort: bool,
    ) -> AttemptRecovery:
        raw_digest = self._optional_digest(f"attempts/{transaction_id}/raw.json")
        tracked_digest = self._optional_digest(
            f"attempts/{transaction_id}/tracked.json"
        )
        execution_id: str | None = None
        attempt_digest: str | None = None
        semantic_digest: str | None = None
        status: Literal["committed", "aborted"]
        if abort or raw_digest is None or tracked_digest is None:
            status = "aborted"
        else:
            intent_payload = _read_protected(
                self.run_root,
                f"attempts/{transaction_id}/intent.json",
            )
            raw_payload = _read_protected(
                self.run_root,
                f"attempts/{transaction_id}/raw.json",
            )
            tracked_payload = _read_protected(
                self.run_root,
                f"attempts/{transaction_id}/tracked.json",
            )
            try:
                intent = json.loads(intent_payload)
                raw = json.loads(raw_payload)
                tracked = json.loads(tracked_payload)
            except json.JSONDecodeError as exc:
                raise ExecutionValidationError(
                    "attempt raw/tracked semantic envelope is invalid"
                ) from exc
            expected_execution = intent.get("execution_id")
            semantic_fields = (
                "schema_version",
                "execution_id",
                "outcome",
                "semantic_digest",
            )
            if (
                expected_execution not in self.authorization.execution_ids
                or not isinstance(raw, dict)
                or not isinstance(tracked, dict)
                or any(
                    field not in raw or field not in tracked
                    for field in semantic_fields
                )
                or any(raw[field] != tracked[field] for field in semantic_fields)
                or raw["execution_id"] != expected_execution
                or raw["schema_version"] != "noor-e2e-attempt-result/v2"
                or raw["outcome"]
                not in {"PASS", "FAIL", "BLOCKED", "EXCLUDED_BY_CLIENT"}
                or not isinstance(raw["semantic_digest"], str)
                or len(raw["semantic_digest"]) != 64
            ):
                raise ExecutionValidationError(
                    "attempt raw/tracked semantic binding drift"
                )
            execution_id = str(expected_execution)
            attempt_digest = str(intent["intent_digest"])
            semantic_digest = str(raw["semantic_digest"])
            status = "committed"
        record = {
            "schema_version": "noor-e2e-attempt-commit/v2",
            "transaction_id": transaction_id,
            "run_id": self.run_id,
            "execution_id": execution_id,
            "attempt_digest": attempt_digest,
            "status": status,
            "authorization_digest": self.authorization_digest,
            "semantic_digest": semantic_digest,
            "raw_digest": raw_digest,
            "tracked_digest": tracked_digest,
        }
        commit_digest = _write_exclusive(
            self.run_root,
            f"attempts/{transaction_id}/commit.json",
            record,
        )
        return AttemptRecovery(
            transaction_id=transaction_id,
            status=status,
            raw_digest=raw_digest,
            tracked_digest=tracked_digest,
            commit_digest=commit_digest,
        )

    def recover_attempt(self, transaction_id: str) -> AttemptRecovery:
        return self._finish_attempt(transaction_id, abort=True)
