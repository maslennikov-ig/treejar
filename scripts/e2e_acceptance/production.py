"""Local-only capability adapters for the trusted Noor acceptance runner.

The module deliberately has no network or subprocess implementation.  Real
transports can only be introduced in a separately authorized delivery stream;
these contracts make their safety boundary explicit and testable first.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.evidence import redact_payload, validate_redacted_payload
from scripts.e2e_acceptance.policy import ReadbackObservation, TrustedAcceptanceRegistry


class ProductionAdapterError(ValueError):
    """A local adapter request is unsafe, malformed, or unauthorized."""


class DispatchTimeoutError(ProductionAdapterError):
    """The fake transport reached its deterministic timeout before dispatch."""


class DispatchUncertainError(ProductionAdapterError):
    """The request may have been dispatched and therefore cannot be retried."""


class Capability(StrEnum):
    """Closed implementation-owned capability vocabulary."""

    WEBHOOK_INBOUND = "webhook.inbound"
    OUTBOUND_TEXT = "outbound_text"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CapabilityTransport(Protocol):
    def preflight(self, capability: Capability, request: Mapping[str, Any]) -> None:
        """Fail before any dispatch when the transport knows it cannot start."""

    def request(self, capability: str, request: Mapping[str, Any]) -> dict[str, Any]:
        """Execute the capability request once."""


@dataclass
class FakeHttpTransport:
    """Deterministic local HTTP stand-in; it never opens a socket."""

    responses: Mapping[str, Mapping[str, Any]]
    timeout_capabilities: frozenset[str] = frozenset()
    uncertain_capabilities: frozenset[str] = frozenset()
    calls: tuple[tuple[str, dict[str, Any]], ...] = field(default_factory=tuple)

    def preflight(self, capability: Capability, request: Mapping[str, Any]) -> None:
        if capability.value in self.timeout_capabilities:
            raise DispatchTimeoutError(
                f"fake timeout before dispatch: {capability.value}"
            )

    def request(self, capability: str, request: Mapping[str, Any]) -> dict[str, Any]:
        copied = dict(request)
        self.calls = (*self.calls, (capability, copied))
        if capability in self.uncertain_capabilities:
            raise DispatchUncertainError(f"fake failure after dispatch: {capability}")
        try:
            return dict(self.responses[capability])
        except KeyError as exc:
            raise ProductionAdapterError(
                f"unknown fake capability: {capability}"
            ) from exc


@dataclass
class FakeReadOnlySshTransport:
    """Deterministic collector-only SSH stand-in with no command execution API."""

    responses: Mapping[str, bytes]
    timeout_reads: frozenset[str] = frozenset()
    reads: tuple[str, ...] = field(default_factory=tuple)

    @property
    def response_digests(self) -> dict[str, str]:
        return {
            source: hashlib.sha256(payload).hexdigest()
            for source, payload in self.responses.items()
        }

    def read(self, source: str) -> bytes:
        if source in self.timeout_reads:
            raise DispatchTimeoutError(f"fake collector timeout: {source}")
        try:
            payload = self.responses[source]
        except KeyError as exc:
            raise ProductionAdapterError(f"unknown collector source: {source}") from exc
        self.reads = (*self.reads, source)
        return bytes(payload)


@dataclass(frozen=True)
class CapabilityDispatcher:
    """Dispatch strictly by authorized typed capability, never scenario identity."""

    transports: Mapping[Capability | str, CapabilityTransport]

    def __post_init__(self) -> None:
        normalized: dict[Capability, CapabilityTransport] = {}
        for identity, transport in self.transports.items():
            try:
                capability = Capability(identity)
            except ValueError as exc:
                raise ProductionAdapterError(
                    "capability registry rejects non-capability identity"
                ) from exc
            if capability in normalized:
                raise ProductionAdapterError("capability registry has duplicate entry")
            normalized[capability] = transport
        object.__setattr__(self, "transports", normalized)

    def _transport(self, capability: str) -> tuple[Capability, CapabilityTransport]:
        try:
            typed = Capability(capability)
        except ValueError as exc:
            raise ProductionAdapterError("capability is not registered") from exc
        try:
            return typed, self.transports[typed]
        except KeyError as exc:
            raise ProductionAdapterError("capability is not registered") from exc

    def preflight(self, *, capability: str, request: Mapping[str, Any]) -> None:
        typed, transport = self._transport(capability)
        transport.preflight(typed, request)

    def dispatch(
        self, *, capability: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        typed, transport = self._transport(capability)
        return transport.request(typed.value, request)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _safe_relative(value: str) -> str:
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ProductionAdapterError("protected relative path is unsafe")
    return value


def _read_protected_json(root: Path, relative: str) -> dict[str, Any]:
    try:
        payload = execution._read_protected(root, _safe_relative(relative))
        parsed = json.loads(payload)
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        execution.ExecutionValidationError,
    ) as exc:
        raise ProductionAdapterError("protected JSON payload is invalid") from exc
    if not isinstance(parsed, dict):
        raise ProductionAdapterError("protected JSON payload must be an object")
    return parsed


def _write_or_validate_exact(root: Path, relative: str, value: object) -> str:
    """Continue a crash-replayed producer write only when bytes are identical."""

    expected = _digest(value)
    try:
        return execution._write_exclusive(root, relative, value)
    except execution.ExecutionValidationError as exc:
        try:
            actual = hashlib.sha256(
                execution._read_protected(root, relative)
            ).hexdigest()
        except execution.ExecutionValidationError as read_error:
            raise exc from read_error
        if actual != expected:
            raise ProductionAdapterError(
                "protected producer replay differs from committed bytes"
            ) from exc
        return actual


class AdapterDispatchResult(_StrictModel):
    """No raw adapter response crosses the protected adapter boundary."""

    action_id: str = Field(min_length=1)
    raw_ref: str = Field(min_length=1)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tracked_ref: str = Field(min_length=1)
    tracked_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    projection: dict[str, Any]


def _runtime_projection_root(
    journal: execution.ProtectedExecutionJournal,
) -> Path:
    if not journal.authorization.store_ids.tracked_store_id:
        raise ProductionAdapterError("authorization lacks tracked store identity")
    # The authority receipt separately binds journal.protected_root. StoreIdentities
    # bind the canonical final publication roots and must not be repurposed for
    # mutable execution-time projections.
    return journal.protected_root / "tracked" / journal.run_id


def write_protected_message(
    journal: execution.ProtectedExecutionJournal,
    *,
    action_id: str,
    payload: Mapping[str, Any],
) -> str:
    """Seal a raw outbound message in the journal's 0700/0600 protected store."""

    if not action_id:
        raise ProductionAdapterError("action identity is required")
    return execution._write_exclusive(
        journal.run_root, f"requests/{action_id}.json", dict(payload)
    )


@dataclass
class WazzupWebhookAdapter:
    """Permit-bound webhook adapter backed only by a local capability transport."""

    adapter_id: str
    journal: execution.ProtectedExecutionJournal
    dispatcher: CapabilityDispatcher

    def dispatch(
        self,
        reservation: execution.ActionReservation,
        *,
        message_path: str,
        execution_id: str,
        step_id: str,
        capability: str,
        operation_permission: str,
        destination_digest: str,
        payload_digest: str,
        idempotency_key: str,
        capability_units: dict[str, int],
    ) -> AdapterDispatchResult:
        if reservation.adapter_id != self.adapter_id:
            raise ProductionAdapterError("reservation adapter identity drift")
        message = _read_protected_json(self.journal.run_root, message_path)
        if _digest(message) != payload_digest:
            raise ProductionAdapterError("protected message payload digest drift")
        # This is intentionally the last operation before permit consumption.
        self.dispatcher.preflight(capability=capability, request=message)
        # This is intentionally the last operation before adapter I/O.
        self.journal.consume_permit(
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
        try:
            response = self.dispatcher.dispatch(capability=capability, request=message)
        except DispatchUncertainError:
            # The journal remains ``unknown``; a collector must reconcile it.
            raise
        raw_ref = f"adapter-responses/{reservation.action_id}.json"
        raw_digest = _write_or_validate_exact(
            self.journal.run_root,
            raw_ref,
            response,
        )
        redacted = redact_payload(response)
        validate_redacted_payload(redacted)
        tracked_ref = f"adapter-responses/{reservation.action_id}.json"
        tracked_digest = _write_or_validate_exact(
            _runtime_projection_root(self.journal),
            tracked_ref,
            {"raw_sha256": raw_digest, "response": redacted},
        )
        return AdapterDispatchResult(
            action_id=reservation.action_id,
            raw_ref=raw_ref,
            raw_sha256=raw_digest,
            tracked_ref=tracked_ref,
            tracked_sha256=tracked_digest,
            projection=redacted,
        )


def dispatch_local_action(
    *,
    journal: execution.ProtectedExecutionJournal,
    dispatcher: CapabilityDispatcher,
    reservation: execution.ActionReservation,
    message_path: str,
    request: Mapping[str, Any],
) -> AdapterDispatchResult:
    """Perform one permit-bound local adapter dispatch from a sealed action."""

    return WazzupWebhookAdapter(
        adapter_id=reservation.adapter_id,
        journal=journal,
        dispatcher=dispatcher,
    ).dispatch(reservation, message_path=message_path, **dict(request))


@dataclass(frozen=True)
class ProtectedRunPlan:
    """A digest-bound plan loaded only from the protected run root."""

    actions: tuple[dict[str, Any], ...]
    evaluator: dict[str, Any]
    plan_digest: str
    evaluator_digest: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ProtectedRunPlan:
        actions = payload.get("actions")
        evaluator = payload.get("evaluator")
        if not isinstance(actions, list) or not all(
            isinstance(item, dict) for item in actions
        ):
            raise ProductionAdapterError("protected run plan actions are invalid")
        if not isinstance(evaluator, dict):
            raise ProductionAdapterError("protected evaluator configuration is invalid")
        action_ids = [
            str(item.get("action_id", item.get("spec", {}).get("action_id", "")))
            for item in actions
        ]
        if not all(action_ids) or len(action_ids) != len(set(action_ids)):
            raise ProductionAdapterError(
                "protected run plan action identities are invalid"
            )
        identity = {"actions": actions, "evaluator": evaluator}
        return cls(
            actions=tuple(dict(item) for item in actions),
            evaluator=dict(evaluator),
            plan_digest=_digest(identity),
            evaluator_digest=_digest(evaluator),
        )

    @classmethod
    def load(cls, protected_root: Path, relative_path: str) -> ProtectedRunPlan:
        return cls.from_payload(_read_protected_json(protected_root, relative_path))


@dataclass(frozen=True)
class ProductionUnitCommit:
    artifact: Any
    receipt: Any


def commit_execution_unit_source(
    *,
    registry: TrustedAcceptanceRegistry,
    journal: execution.ProtectedExecutionJournal,
    sealed_plan: ProtectedRunPlan,
    ordinal: int,
    outcome: execution.OutcomeValue,
    source: Mapping[str, Any],
    observed_at: datetime | None = None,
) -> ProductionUnitCommit:
    """Commit one typed unit from an authorization-selected production producer."""

    from scripts.e2e_acceptance.coordinator import (
        ProducerArtifact,
        ProducerReceipt,
        ProductionRunCoordinator,
        validate_publication_source,
    )

    if (
        not isinstance(registry, TrustedAcceptanceRegistry)
        or journal.phase != "executing"
        or ordinal < 1
        or ordinal > len(registry.compiled_plan.execution_ids)
    ):
        raise ProductionAdapterError("production unit commit boundary is invalid")
    load_sealed_run_plan(journal, sealed_plan)
    execution_id = registry.compiled_plan.execution_ids[ordinal - 1]
    kind = (
        "scenario"
        if execution_id in registry.compiled_policy.scenarios
        else "evidence_block"
    )
    typed_source = validate_publication_source(kind, dict(source))
    attempt_items = [
        item
        for item in typed_source.evidence
        if item.evidence_id == typed_source.execution.attempt_ref
        and item.producer == "protected-attempt-committer"
    ]
    if len(attempt_items) != 1:
        raise ProductionAdapterError("production unit lacks one protected attempt")
    attempt = attempt_items[0].payload
    protected_commit_ref = attempt.get("protected_commit_ref")
    try:
        commit_payload = execution._read_protected(
            journal.run_root, str(protected_commit_ref)
        )
        protected_commit = json.loads(commit_payload)
    except (execution.ExecutionValidationError, json.JSONDecodeError) as exc:
        raise ProductionAdapterError(
            "production unit protected attempt commit is unavailable"
        ) from exc
    if (
        attempt.get("schema_version") != "noor-e2e-committed-execution/v2"
        or attempt.get("run_id") != journal.run_id
        or attempt.get("registry_id") != registry.registry_id
        or attempt.get("execution_id") != execution_id
        or attempt.get("outcome") != outcome
        or attempt.get("authorization_digest") != journal.authorization_digest
        or attempt.get("protected_commit_digest")
        != hashlib.sha256(commit_payload).hexdigest()
        or protected_commit.get("schema_version") != "noor-e2e-attempt-commit/v2"
        or protected_commit.get("status") != "committed"
        or protected_commit.get("run_id") != journal.run_id
        or protected_commit.get("execution_id") != execution_id
        or protected_commit.get("authorization_digest") != journal.authorization_digest
        or protected_commit.get("attempt_digest") != attempt.get("attempt_digest")
        or protected_commit.get("semantic_digest") != attempt.get("semantic_digest")
    ):
        raise ProductionAdapterError("production unit attempt/outcome binding drift")
    for turn in getattr(typed_source, "turns", ()):
        try:
            transcript_relative = f"transcripts/{execution_id}/{turn['attempt_id']}/{turn['turn_id']}.json"
            receipt_relative = (
                f"producer-receipts/transcripts/{execution_id}/"
                f"{turn['attempt_id']}/{turn['turn_id']}.json"
            )
            transcript_payload = execution._read_protected(
                journal.run_root, transcript_relative
            )
            transcript_receipt_payload = execution._read_protected(
                journal.run_root, receipt_relative
            )
            transcript_receipt = json.loads(transcript_receipt_payload)
        except (
            KeyError,
            execution.ExecutionValidationError,
            json.JSONDecodeError,
        ) as exc:
            raise ProductionAdapterError(
                "production scenario transcript source is unavailable"
            ) from exc
        if (
            turn.get("execution_id") != execution_id
            or turn.get("transcript_digest")
            != hashlib.sha256(transcript_payload).hexdigest()
            or turn.get("producer_receipt_digest")
            != hashlib.sha256(transcript_receipt_payload).hexdigest()
            or transcript_receipt.get("authorization_digest")
            != journal.authorization_digest
            or transcript_receipt.get("attempt_digest") != attempt.get("attempt_digest")
            or transcript_receipt.get("attempt_phase_head_digest")
            != attempt.get("phase_head_digest")
        ):
            raise ProductionAdapterError(
                "production scenario transcript/attempt binding drift"
            )
    producer = (
        journal.authorization.adapter_ids[0]
        if kind == "scenario"
        else journal.authorization.collector_ids[0]
    )
    issued_at = observed_at or datetime.now(UTC)
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise ProductionAdapterError("production unit time must be aware")
    sealed_payload = execution._read_protected(journal.run_root, "run-plan/sealed.json")
    artifact = ProducerArtifact(
        schema_version="noor-e2e-coordinator-producer-artifact/v1",
        status="committed",
        registry_id=registry.registry_id,
        run_id=journal.run_id,
        authorization_digest=journal.authorization_digest,
        sealed_plan_sha256=hashlib.sha256(sealed_payload).hexdigest(),
        ordinal=ordinal,
        execution_id=execution_id,
        kind=kind,
        outcome=outcome,
        producer=producer,
        observed_at=issued_at,
        source=typed_source.model_dump(mode="json"),
        source_sha256=_digest(typed_source.model_dump(mode="json")),
    )
    artifact_payload = _canonical_bytes(artifact.model_dump(mode="json"))
    receipt = ProducerReceipt(
        schema_version="noor-e2e-coordinator-producer-receipt/v1",
        status="committed",
        registry_id=registry.registry_id,
        run_id=journal.run_id,
        authorization_digest=journal.authorization_digest,
        ordinal=ordinal,
        execution_id=execution_id,
        producer=producer,
        artifact_sha256=hashlib.sha256(artifact_payload).hexdigest(),
        source_sha256=artifact.source_sha256,
        issued_at=issued_at,
        expires_at=issued_at + timedelta(minutes=5),
    )
    _write_or_validate_exact(
        journal.run_root,
        ProductionRunCoordinator.producer_artifact_path(ordinal),
        artifact.model_dump(mode="json"),
    )
    _write_or_validate_exact(
        journal.run_root,
        ProductionRunCoordinator.producer_receipt_path(ordinal),
        receipt.model_dump(mode="json"),
    )
    return ProductionUnitCommit(artifact=artifact, receipt=receipt)


class BaselineReadbackArtifact(_StrictModel):
    schema_version: str = "noor-e2e-baseline-readback-artifact/v2"
    registry_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    collector_id: str = Field(min_length=1)
    collector_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    journal_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    inventory_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation: ReadbackObservation

    @model_validator(mode="after")
    def _bind_observation(self) -> BaselineReadbackArtifact:
        if (
            self.observation.phase != "baseline"
            or self.observation.run_id != self.run_id
            or self.observation.preflight_digest != self.preflight_digest
            or self.observation.collector_id != self.collector_id
            or self.observation.collector_artifact_digest
            != self.collector_artifact_digest
            or self.observation.causal_event_digest != self.journal_head_digest
            or self.observation.observed_at != self.observed_at
            or _digest(self.observation.inventory) != self.inventory_digest
        ):
            raise ValueError("baseline artifact observation binding drift")
        return self


class BaselineReadbackProducerReceipt(_StrictModel):
    schema_version: str = "noor-e2e-baseline-readback-producer-receipt/v2"
    producer: str = "independent-readback-collector"
    registry_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    collector_id: str = Field(min_length=1)
    collector_artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    journal_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    inventory_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _fresh_window(self) -> BaselineReadbackProducerReceipt:
        if (
            any(
                value.tzinfo is None or value.utcoffset() is None
                for value in (self.observed_at, self.issued_at, self.expires_at)
            )
            or not self.observed_at <= self.issued_at < self.expires_at
        ):
            raise ValueError("baseline receipt window is invalid")
        return self


def _validate_plan_actions(
    journal: execution.ProtectedExecutionJournal, plan: ProtectedRunPlan
) -> None:
    expected = {
        spec.action_id: spec.model_dump(mode="json")
        for spec in journal.authorization.action_specs
    }
    actual: dict[str, dict[str, Any]] = {}
    for item in plan.actions:
        spec = item.get("spec")
        message_path = item.get("message_path")
        if (
            set(item) != {"spec", "message_path"}
            or not isinstance(spec, dict)
            or not isinstance(message_path, str)
            or not message_path
            or spec.get("action_id") in actual
        ):
            raise ProductionAdapterError("sealed plan action layout is invalid")
        actual[str(spec["action_id"])] = spec
    if actual != expected:
        raise ProductionAdapterError("sealed plan full action identity drift")


def seal_run_plan(
    journal: execution.ProtectedExecutionJournal, plan: ProtectedRunPlan
) -> str:
    """Anchor the exact plan/evaluator/action identities before preflight."""

    if journal.phase != "prepared":
        raise ProductionAdapterError("run plan can only be sealed before preflight")
    _validate_plan_actions(journal, plan)
    digest = _write_or_validate_exact(
        journal.run_root,
        "run-plan/sealed.json",
        {
            "schema_version": "noor-e2e-sealed-run-plan/v2",
            "plan_digest": plan.plan_digest,
            "evaluator_digest": plan.evaluator_digest,
            "actions": list(plan.actions),
            "evaluator": plan.evaluator,
        },
    )
    if journal._sealed_run_plan_digest is not None:
        if journal._sealed_run_plan_digest != digest:
            raise ProductionAdapterError("run plan seal replay differs from committed")
        return digest
    journal._append_event(
        phase="prepared",
        kind="run_plan_sealed",
        data={
            "plan_digest": plan.plan_digest,
            "evaluator_digest": plan.evaluator_digest,
            "sealed_plan_digest": digest,
        },
    )
    journal._sealed_run_plan_digest = digest
    return digest


def load_sealed_run_plan(
    journal: execution.ProtectedExecutionJournal, submitted: ProtectedRunPlan
) -> ProtectedRunPlan:
    """Reject any plan, evaluator or action replacement after preparation."""

    payload = _read_protected_json(journal.run_root, "run-plan/sealed.json")
    if payload.get("schema_version") != "noor-e2e-sealed-run-plan/v2":
        raise ProductionAdapterError("sealed run plan schema drift")
    sealed = ProtectedRunPlan.from_payload(payload)
    if (
        payload.get("plan_digest") != sealed.plan_digest
        or payload.get("evaluator_digest") != sealed.evaluator_digest
        or sealed != submitted
    ):
        raise ProductionAdapterError("submitted plan differs from sealed plan")
    _validate_plan_actions(journal, sealed)
    return sealed


def _optional_protected_payload(root: Path, relative: str) -> bytes | None:
    try:
        return execution._read_protected(root, relative)
    except FileNotFoundError:
        return None
    except execution.ExecutionValidationError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            return None
        raise ProductionAdapterError("protected collector payload is invalid") from exc
    except OSError as exc:
        raise ProductionAdapterError("protected collector payload is invalid") from exc


def _load_baseline_artifact(
    journal: execution.ProtectedExecutionJournal,
    *,
    source_id: str,
    inventory: Mapping[str, Any],
) -> tuple[BaselineReadbackArtifact, str] | None:
    payload = _optional_protected_payload(
        journal.run_root, "collector-artifacts/baseline-readback.json"
    )
    if payload is None:
        return None
    try:
        artifact = BaselineReadbackArtifact.model_validate(json.loads(payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ProductionAdapterError("baseline collector artifact is invalid") from exc
    if (
        journal.previous_event_digest is None
        or artifact.registry_id != journal.authorization.registry_id
        or artifact.run_id != journal.run_id
        or artifact.authorization_digest != journal.authorization_digest
        or artifact.preflight_digest != journal.authorization.preflight_digest
        or artifact.collector_id not in journal.authorization.collector_ids
        or artifact.collector_artifact_digest
        != journal.authorization.readback_collector_digest
        or artifact.journal_head_digest != journal.previous_event_digest
        or artifact.observation.source_id != source_id
        or artifact.inventory_digest != _digest(inventory)
    ):
        raise ProductionAdapterError("baseline collector replay binding drift")
    return artifact, hashlib.sha256(payload).hexdigest()


def _load_final_artifact(
    journal: execution.ProtectedExecutionJournal,
    *,
    source_id: str,
    inventory: Mapping[str, Any],
) -> tuple[execution.ProtectedFinalReadbackArtifact, str] | None:
    payload = _optional_protected_payload(
        journal.run_root, "collector-artifacts/final-readback.json"
    )
    if payload is None:
        return None
    try:
        artifact = execution.ProtectedFinalReadbackArtifact.model_validate(
            json.loads(payload)
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise ProductionAdapterError("final collector artifact is invalid") from exc
    if (
        journal.previous_event_digest is None
        or journal._final_turn_occurred_at is None
        or artifact.registry_id != journal.authorization.registry_id
        or artifact.run_id != journal.run_id
        or artifact.authorization_digest != journal.authorization_digest
        or artifact.preflight_digest != journal.authorization.preflight_digest
        or artifact.collector_id not in journal.authorization.collector_ids
        or artifact.collector_artifact_digest
        != journal.authorization.readback_collector_digest
        or artifact.journal_head_digest != journal.previous_event_digest
        or artifact.final_turn_anchor_at != journal._final_turn_occurred_at
        or artifact.observation.source_id != source_id
        or artifact.inventory_digest != _digest(inventory)
    ):
        raise ProductionAdapterError("final collector replay binding drift")
    return artifact, hashlib.sha256(payload).hexdigest()


def _load_or_collect_raw(
    collector: IndependentReadOnlyCollector,
    journal: execution.ProtectedExecutionJournal,
    *,
    phase: str,
    replay_raw: bytes | None,
) -> tuple[bytes, dict[str, Any]]:
    relative = f"collector-raw/{phase}.json"
    payload = _optional_protected_payload(journal.run_root, relative)
    if payload is None:
        raw = collector.transport.read(collector.source_name)
        inventory = collector._inventory(raw)
        _write_or_validate_exact(
            journal.run_root, relative, {"raw": raw.decode("utf-8")}
        )
        return raw, inventory
    try:
        committed = json.loads(payload)
        raw_text = committed["raw"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ProductionAdapterError("protected collector raw is invalid") from exc
    if not isinstance(raw_text, str):
        raise ProductionAdapterError("protected collector raw is invalid")
    raw = raw_text.encode("utf-8")
    inventory = collector._inventory(raw)
    if replay_raw is not None:
        collector._inventory(replay_raw)
        _write_or_validate_exact(
            journal.run_root, relative, {"raw": replay_raw.decode("utf-8")}
        )
    return raw, inventory


@dataclass
class IndependentReadOnlyCollector:
    """Read-only collector; it owns no mutation-capable adapter or dispatcher."""

    collector_id: str
    transport: FakeReadOnlySshTransport
    source_name: str = "inventory"

    @staticmethod
    def _inventory(raw: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(raw)
            inventory = payload["inventory"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ProductionAdapterError("collector response lacks inventory") from exc
        if not isinstance(inventory, dict):
            raise ProductionAdapterError("collector inventory must be an object")
        return inventory

    def observe(
        self,
        *,
        source_id: str,
        run_id: str,
        preflight_digest: str,
        collector_artifact_digest: str,
        causal_event_digest: str,
        observed_at: datetime | None = None,
    ) -> ReadbackObservation:
        raw = self.transport.read(self.source_name)
        return ReadbackObservation.build(
            phase="baseline",
            collector_id=self.collector_id,
            source_id=source_id,
            run_id=run_id,
            preflight_digest=preflight_digest,
            collector_artifact_digest=collector_artifact_digest,
            causal_event_digest=causal_event_digest,
            observed_at=observed_at or datetime.now(UTC),
            inventory=self._inventory(raw),
        )

    def seal_baseline(
        self,
        journal: execution.ProtectedExecutionJournal,
        *,
        source_id: str,
        observed_at: datetime | None = None,
        replay_raw: bytes | None = None,
    ) -> ReadbackObservation:
        """Commit an independent baseline producer artifact before execution."""

        if (
            journal.phase != "prepared"
            or self.collector_id not in journal.authorization.collector_ids
            or tuple(journal.authorization.collector_ids) != (self.collector_id,)
            or journal.previous_event_digest is None
        ):
            raise ProductionAdapterError("baseline collector is not solely authorized")
        raw, inventory = _load_or_collect_raw(
            self, journal, phase="baseline", replay_raw=replay_raw
        )
        existing = _load_baseline_artifact(
            journal, source_id=source_id, inventory=inventory
        )
        if existing is None:
            observation = ReadbackObservation.build(
                phase="baseline",
                collector_id=self.collector_id,
                source_id=source_id,
                run_id=journal.run_id,
                preflight_digest=journal.authorization.preflight_digest,
                collector_artifact_digest=journal.authorization.readback_collector_digest,
                causal_event_digest=journal.previous_event_digest,
                observed_at=observed_at or datetime.now(UTC),
                inventory=inventory,
            )
            artifact = BaselineReadbackArtifact(
                registry_id=journal.authorization.registry_id,
                run_id=journal.run_id,
                authorization_digest=journal.authorization_digest,
                preflight_digest=journal.authorization.preflight_digest,
                collector_id=self.collector_id,
                collector_artifact_digest=observation.collector_artifact_digest,
                journal_head_digest=journal.previous_event_digest,
                observed_at=observation.observed_at,
                inventory_digest=_digest(observation.inventory),
                observation=observation,
            )
            artifact_sha256 = _write_or_validate_exact(
                journal.run_root,
                "collector-artifacts/baseline-readback.json",
                artifact.model_dump(mode="json"),
            )
        else:
            artifact, artifact_sha256 = existing
            observation = artifact.observation
        receipt = BaselineReadbackProducerReceipt(
            registry_id=artifact.registry_id,
            run_id=artifact.run_id,
            authorization_digest=artifact.authorization_digest,
            preflight_digest=artifact.preflight_digest,
            collector_id=artifact.collector_id,
            collector_artifact_digest=artifact.collector_artifact_digest,
            artifact_sha256=artifact_sha256,
            journal_head_digest=artifact.journal_head_digest,
            inventory_digest=artifact.inventory_digest,
            observed_at=artifact.observed_at,
            issued_at=artifact.observed_at,
            expires_at=artifact.observed_at + timedelta(minutes=5),
        )
        _write_or_validate_exact(
            journal.run_root,
            "producer-receipts/baseline-readback.json",
            receipt.model_dump(mode="json"),
        )
        _write_or_validate_exact(
            _runtime_projection_root(journal),
            "collector-projections/baseline-readback.json",
            {
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "inventory_digest": _digest(inventory),
            },
        )
        return observation

    def commit_final_pair(
        self,
        journal: execution.ProtectedExecutionJournal,
        *,
        source_id: str,
        observed_at: datetime | None = None,
        replay_raw: bytes | None = None,
    ) -> ReadbackObservation:
        if self.collector_id not in journal.authorization.collector_ids:
            raise ProductionAdapterError("collector is not authorized")
        if journal.phase == "final_readback_sealed":
            return _load_sealed_final_observation(journal)
        if (
            journal.phase != "final_turn_anchored"
            or journal.previous_event_digest is None
            or journal._final_turn_occurred_at is None
        ):
            raise ProductionAdapterError("final collector requires final-turn anchor")
        raw, inventory = _load_or_collect_raw(
            self, journal, phase="final", replay_raw=replay_raw
        )
        existing = _load_final_artifact(
            journal, source_id=source_id, inventory=inventory
        )
        if existing is None:
            observation = ReadbackObservation.build(
                phase="final",
                collector_id=self.collector_id,
                source_id=source_id,
                run_id=journal.run_id,
                preflight_digest=journal.authorization.preflight_digest,
                collector_artifact_digest=journal.authorization.readback_collector_digest,
                causal_event_digest=journal.previous_event_digest,
                observed_at=observed_at or datetime.now(UTC),
                inventory=inventory,
            )
            artifact = execution.ProtectedFinalReadbackArtifact(
                schema_version="noor-e2e-final-readback-artifact/v2",
                registry_id=journal.authorization.registry_id,
                run_id=journal.run_id,
                authorization_digest=journal.authorization_digest,
                preflight_digest=journal.authorization.preflight_digest,
                collector_id=self.collector_id,
                collector_artifact_digest=observation.collector_artifact_digest,
                journal_head_digest=journal.previous_event_digest,
                final_turn_anchor_at=journal._final_turn_occurred_at,
                observed_at=observation.observed_at,
                inventory_digest=_digest(observation.inventory),
                observation=observation,
            )
            artifact_sha256 = _write_or_validate_exact(
                journal.run_root,
                "collector-artifacts/final-readback.json",
                artifact.model_dump(mode="json"),
            )
        else:
            artifact, artifact_sha256 = existing
            observation = artifact.observation
        issued_at = observation.observed_at
        receipt = execution.FinalReadbackProducerReceipt(
            schema_version="noor-e2e-final-readback-producer-receipt/v2",
            registry_id=artifact.registry_id,
            run_id=artifact.run_id,
            authorization_digest=artifact.authorization_digest,
            preflight_digest=artifact.preflight_digest,
            producer="independent-readback-collector",
            collector_id=artifact.collector_id,
            collector_artifact_digest=artifact.collector_artifact_digest,
            artifact_sha256=artifact_sha256,
            journal_head_digest=artifact.journal_head_digest,
            inventory_digest=artifact.inventory_digest,
            observed_at=artifact.observed_at,
            issued_at=issued_at,
            expires_at=issued_at + timedelta(minutes=5),
        )
        _write_or_validate_exact(
            journal.run_root,
            "producer-receipts/final-readback.json",
            receipt.model_dump(mode="json"),
        )
        _write_or_validate_exact(
            _runtime_projection_root(journal),
            "collector-projections/final-readback.json",
            {
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "inventory_digest": _digest(inventory),
            },
        )
        return observation

    def seal_final(
        self,
        journal: execution.ProtectedExecutionJournal,
        *,
        source_id: str,
        observed_at: datetime | None = None,
        replay_raw: bytes | None = None,
    ) -> ReadbackObservation:
        """Compatibility owner that commits the pair and advances the journal."""

        observation = self.commit_final_pair(
            journal,
            source_id=source_id,
            observed_at=observed_at,
            replay_raw=replay_raw,
        )
        if journal.phase == "final_turn_anchored":
            receipt_digest = hashlib.sha256(
                execution._read_protected(
                    journal.run_root, "producer-receipts/final-readback.json"
                )
            ).hexdigest()
            journal.seal_final_readback(observation, receipt_digest=receipt_digest)
        return observation


def _load_sealed_final_observation(
    journal: execution.ProtectedExecutionJournal,
) -> ReadbackObservation:
    """Read the immutable final producer pair after a completed seal."""

    try:
        artifact_payload = execution._read_protected(
            journal.run_root, "collector-artifacts/final-readback.json"
        )
        receipt_payload = execution._read_protected(
            journal.run_root, "producer-receipts/final-readback.json"
        )
        artifact = execution.ProtectedFinalReadbackArtifact.model_validate(
            json.loads(artifact_payload)
        )
        receipt = execution.FinalReadbackProducerReceipt.model_validate(
            json.loads(receipt_payload)
        )
    except (
        ValueError,
        json.JSONDecodeError,
        execution.ExecutionValidationError,
    ) as exc:
        raise ProductionAdapterError("sealed final collector pair is invalid") from exc
    if (
        artifact.registry_id != journal.authorization.registry_id
        or artifact.run_id != journal.run_id
        or artifact.authorization_digest != journal.authorization_digest
        or artifact.preflight_digest != journal.authorization.preflight_digest
        or artifact.collector_id not in journal.authorization.collector_ids
        or receipt.artifact_sha256 != hashlib.sha256(artifact_payload).hexdigest()
        or receipt.collector_id != artifact.collector_id
        or receipt.inventory_digest != artifact.inventory_digest
    ):
        raise ProductionAdapterError("sealed final collector binding drift")
    return artifact.observation


def seal_fixed_final_readback(
    journal: execution.ProtectedExecutionJournal,
    *,
    current_time: datetime | None = None,
) -> ReadbackObservation:
    """Seal only the fixed collector-owned final pair; never read caller paths."""

    if journal.phase == "final_readback_sealed":
        return _load_sealed_final_observation(journal)
    try:
        artifact_payload = execution._read_protected(
            journal.run_root, "collector-artifacts/final-readback.json"
        )
        artifact = execution.ProtectedFinalReadbackArtifact.model_validate(
            json.loads(artifact_payload)
        )
        receipt_payload = execution._read_protected(
            journal.run_root, "producer-receipts/final-readback.json"
        )
    except (
        ValueError,
        json.JSONDecodeError,
        execution.ExecutionValidationError,
    ) as exc:
        raise ProductionAdapterError("fixed final collector pair is invalid") from exc
    journal.seal_final_readback(
        artifact.observation,
        receipt_digest=hashlib.sha256(receipt_payload).hexdigest(),
        current_time=current_time,
    )
    return artifact.observation


def load_protected_baseline(
    journal: execution.ProtectedExecutionJournal,
    *,
    artifact_path: str,
    current_time: datetime | None = None,
) -> ReadbackObservation:
    """Load only the collector-owned baseline artifact and receipt pair."""

    if artifact_path != "collector-artifacts/baseline-readback.json":
        raise ProductionAdapterError("baseline must select the producer artifact")
    now = current_time or datetime.now(UTC)
    try:
        artifact_payload = execution._read_protected(journal.run_root, artifact_path)
        receipt_payload = execution._read_protected(
            journal.run_root, "producer-receipts/baseline-readback.json"
        )
        artifact = BaselineReadbackArtifact.model_validate(json.loads(artifact_payload))
        receipt = BaselineReadbackProducerReceipt.model_validate(
            json.loads(receipt_payload)
        )
    except (
        ValueError,
        json.JSONDecodeError,
        execution.ExecutionValidationError,
    ) as exc:
        raise ProductionAdapterError("baseline producer artifact is invalid") from exc
    if (
        journal.phase != "prepared"
        or journal.previous_event_digest is None
        or tuple(journal.authorization.collector_ids) != (artifact.collector_id,)
        or artifact.registry_id != journal.authorization.registry_id
        or artifact.run_id != journal.run_id
        or artifact.authorization_digest != journal.authorization_digest
        or artifact.preflight_digest != journal.authorization.preflight_digest
        or artifact.collector_artifact_digest
        != journal.authorization.readback_collector_digest
        or artifact.journal_head_digest != journal.previous_event_digest
        or receipt.producer != "independent-readback-collector"
        or receipt.registry_id != artifact.registry_id
        or receipt.run_id != artifact.run_id
        or receipt.authorization_digest != artifact.authorization_digest
        or receipt.preflight_digest != artifact.preflight_digest
        or receipt.collector_id != artifact.collector_id
        or receipt.collector_artifact_digest != artifact.collector_artifact_digest
        or receipt.journal_head_digest != artifact.journal_head_digest
        or receipt.inventory_digest != artifact.inventory_digest
        or receipt.observed_at != artifact.observed_at
        or receipt.artifact_sha256 != hashlib.sha256(artifact_payload).hexdigest()
        or artifact.observed_at > now
        or now - artifact.observed_at > timedelta(minutes=5)
        or not receipt.issued_at <= now < receipt.expires_at
    ):
        raise ProductionAdapterError("baseline producer receipt binding drift")
    return artifact.observation


__all__ = [
    "CapabilityDispatcher",
    "BaselineReadbackArtifact",
    "BaselineReadbackProducerReceipt",
    "DispatchTimeoutError",
    "DispatchUncertainError",
    "dispatch_local_action",
    "FakeHttpTransport",
    "FakeReadOnlySshTransport",
    "IndependentReadOnlyCollector",
    "ProductionAdapterError",
    "ProtectedRunPlan",
    "ProductionUnitCommit",
    "commit_execution_unit_source",
    "WazzupWebhookAdapter",
    "load_protected_baseline",
    "seal_fixed_final_readback",
    "load_sealed_run_plan",
    "seal_run_plan",
    "write_protected_message",
]
