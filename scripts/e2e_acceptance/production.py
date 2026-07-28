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
from scripts.e2e_acceptance.policy import ReadbackObservation


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


def _tracked_root(journal: execution.ProtectedExecutionJournal) -> Path:
    root = journal.protected_root / "tracked"
    if (
        not journal.authorization.store_ids.tracked_store_id
        or execution.store_root_digest(root)
        != journal.authorization.store_ids.tracked_root_digest
    ):
        raise ProductionAdapterError("authorization lacks tracked store identity")
    return root / journal.run_id


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
            _tracked_root(self.journal),
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
    journal._append_event(
        phase="prepared",
        kind="run_plan_sealed",
        data={
            "plan_digest": plan.plan_digest,
            "evaluator_digest": plan.evaluator_digest,
            "sealed_plan_digest": digest,
        },
    )
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
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
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
    ) -> ReadbackObservation:
        """Commit an independent baseline producer artifact before execution."""

        if (
            journal.phase != "prepared"
            or self.collector_id not in journal.authorization.collector_ids
            or tuple(journal.authorization.collector_ids) != (self.collector_id,)
            or journal.previous_event_digest is None
        ):
            raise ProductionAdapterError("baseline collector is not solely authorized")
        raw = self.transport.read(self.source_name)
        inventory = self._inventory(raw)
        _write_or_validate_exact(
            journal.run_root,
            "collector-raw/baseline.json",
            {"raw": raw.decode("utf-8")},
        )
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
        tracked_payload = {
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "inventory_digest": _digest(inventory),
        }
        _write_or_validate_exact(
            _tracked_root(journal),
            "collector-projections/baseline-readback.json",
            tracked_payload,
        )
        _write_or_validate_exact(
            journal.run_root,
            "producer-receipts/baseline-readback.json",
            receipt.model_dump(mode="json"),
        )
        return observation

    def seal_final(
        self,
        journal: execution.ProtectedExecutionJournal,
        *,
        source_id: str,
        observed_at: datetime | None = None,
    ) -> ReadbackObservation:
        if self.collector_id not in journal.authorization.collector_ids:
            raise ProductionAdapterError("collector is not authorized")
        if (
            journal.previous_event_digest is None
            or journal._final_turn_occurred_at is None
        ):
            raise ProductionAdapterError("final collector requires final-turn anchor")
        raw = self.transport.read(self.source_name)
        inventory = self._inventory(raw)
        _write_or_validate_exact(
            journal.run_root, "collector-raw/final.json", {"raw": raw.decode("utf-8")}
        )
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
            _tracked_root(journal),
            "collector-projections/final-readback.json",
            {
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "inventory_digest": _digest(inventory),
            },
        )
        receipt_digest = _write_or_validate_exact(
            journal.run_root,
            "producer-receipts/final-readback.json",
            receipt.model_dump(mode="json"),
        )
        journal.seal_final_readback(observation, receipt_digest=receipt_digest)
        return observation


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
    "WazzupWebhookAdapter",
    "load_protected_baseline",
    "load_sealed_run_plan",
    "seal_run_plan",
    "write_protected_message",
]
