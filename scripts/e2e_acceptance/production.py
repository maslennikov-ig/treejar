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
from pathlib import Path
from typing import Any, Protocol

from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.evidence import redact_payload, validate_redacted_payload
from scripts.e2e_acceptance.policy import ReadbackObservation


class ProductionAdapterError(ValueError):
    """A local adapter request is unsafe, malformed, or unauthorized."""


class DispatchTimeoutError(ProductionAdapterError):
    """The fake transport reached its deterministic timeout before dispatch."""


class DispatchUncertainError(ProductionAdapterError):
    """The request may have been dispatched and therefore cannot be retried."""


class CapabilityTransport(Protocol):
    def request(self, capability: str, request: Mapping[str, Any]) -> dict[str, Any]:
        """Execute the capability request once."""


@dataclass
class FakeHttpTransport:
    """Deterministic local HTTP stand-in; it never opens a socket."""

    responses: Mapping[str, Mapping[str, Any]]
    timeout_capabilities: frozenset[str] = frozenset()
    uncertain_capabilities: frozenset[str] = frozenset()
    calls: tuple[tuple[str, dict[str, Any]], ...] = field(default_factory=tuple)

    def request(self, capability: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if capability in self.timeout_capabilities:
            raise DispatchTimeoutError(f"fake timeout before dispatch: {capability}")
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

    transports: Mapping[str, CapabilityTransport]

    def dispatch(
        self, *, capability: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        if not capability or capability not in self.transports:
            raise ProductionAdapterError("capability is not registered")
        return self.transports[capability].request(capability, request)


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
    ) -> dict[str, Any]:
        if reservation.adapter_id != self.adapter_id:
            raise ProductionAdapterError("reservation adapter identity drift")
        message = _read_protected_json(self.journal.run_root, message_path)
        if _digest(message) != payload_digest:
            raise ProductionAdapterError("protected message payload digest drift")
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
        raw_digest = execution._write_exclusive(
            self.journal.run_root,
            f"adapter-responses/{reservation.action_id}.json",
            response,
        )
        redacted = redact_payload(response)
        validate_redacted_payload(redacted)
        execution._write_exclusive(
            self.journal.run_root,
            f"tracked/adapter-responses/{reservation.action_id}.json",
            {"raw_sha256": raw_digest, "response": redacted},
        )
        return response


@dataclass(frozen=True)
class ProtectedRunPlan:
    """A digest-bound plan loaded only from the protected run root."""

    actions: tuple[dict[str, Any], ...]
    evaluator: dict[str, Any]
    plan_digest: str
    evaluator_digest: str

    @classmethod
    def load(cls, protected_root: Path, relative_path: str) -> ProtectedRunPlan:
        payload = _read_protected_json(protected_root, relative_path)
        actions = payload.get("actions")
        evaluator = payload.get("evaluator")
        if not isinstance(actions, list) or not all(
            isinstance(item, dict) for item in actions
        ):
            raise ProductionAdapterError("protected run plan actions are invalid")
        if not isinstance(evaluator, dict):
            raise ProductionAdapterError("protected evaluator configuration is invalid")
        action_ids = [str(item.get("action_id", "")) for item in actions]
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
        execution._write_exclusive(
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
            inventory=self._inventory(raw),
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
        artifact_sha256 = execution._write_exclusive(
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
        receipt_digest = execution._write_exclusive(
            journal.run_root,
            "producer-receipts/final-readback.json",
            receipt.model_dump(mode="json"),
        )
        journal.seal_final_readback(observation, receipt_digest=receipt_digest)
        return observation


__all__ = [
    "CapabilityDispatcher",
    "DispatchTimeoutError",
    "DispatchUncertainError",
    "FakeHttpTransport",
    "FakeReadOnlySshTransport",
    "IndependentReadOnlyCollector",
    "ProductionAdapterError",
    "ProtectedRunPlan",
    "WazzupWebhookAdapter",
    "write_protected_message",
]
