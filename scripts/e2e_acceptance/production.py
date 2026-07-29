"""Local-only capability adapters for the trusted Noor acceptance runner.

The module deliberately has no network or subprocess implementation.  Real
transports can only be introduced in a separately authorized delivery stream;
these contracts make their safety boundary explicit and testable first.
"""

from __future__ import annotations

import hashlib
import json
import os
import weakref
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.evidence import redact_payload, validate_redacted_payload
from scripts.e2e_acceptance.policy import (
    ClassifierResult,
    OracleDecision,
    OracleEvidence,
    ReadbackObservation,
    ReadbackResult,
    StructuredEvent,
    ToolResult,
    TrustedAcceptanceRegistry,
)


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


def _write_or_validate_bytes(root: Path, relative: str, payload: bytes) -> str:
    """Seal exact producer bytes, preserving their original digest on replay."""

    expected = hashlib.sha256(payload).hexdigest()
    parent_fd, name = execution._open_relative_parent(root, relative, create=True)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(name, flags, 0o600, dir_fd=parent_fd)
        except FileExistsError:
            actual = execution._read_protected(root, relative)
            if actual != payload:
                raise ProductionAdapterError(
                    "protected producer replay differs from committed bytes"
                ) from None
            return expected
        try:
            remaining = memoryview(payload)
            while remaining:
                written = os.write(fd, remaining)
                if written == 0:
                    raise OSError("protected producer raw write made no progress")
                remaining = remaining[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise ProductionAdapterError("protected producer raw write failed") from exc
    finally:
        os.close(parent_fd)
    return expected


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


class DecisiveProducerBinding(_StrictModel):
    producer_id: str = Field(min_length=1)
    producer_kind: Literal["adapter", "collector", "classifier", "trusted-registry"]
    capability: str = Field(min_length=1)
    source_identity: str = Field(min_length=1)
    config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProtectedEvaluatorConfig(_StrictModel):
    """Exact evaluator and decisive-producer registry sealed with the run plan."""

    schema_version: Literal["noor-e2e-protected-evaluator/v1"]
    publication: dict[str, Any]
    decisive_producers: tuple[DecisiveProducerBinding, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_producers(self) -> ProtectedEvaluatorConfig:
        identities = [item.producer_id for item in self.decisive_producers]
        if len(identities) != len(set(identities)):
            raise ValueError("decisive producer identities must be unique")
        return self


@dataclass(frozen=True)
class ProtectedRunPlan:
    """A digest-bound plan loaded only from the protected run root."""

    actions: tuple[dict[str, Any], ...]
    evaluator: dict[str, Any]
    runtime: dict[str, Any] | None
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
        try:
            evaluator_config = ProtectedEvaluatorConfig.model_validate(evaluator)
        except ValueError as exc:
            raise ProductionAdapterError(
                "protected evaluator configuration is invalid"
            ) from exc
        action_ids = [
            str(item.get("action_id", item.get("spec", {}).get("action_id", "")))
            for item in actions
        ]
        if not all(action_ids) or len(action_ids) != len(set(action_ids)):
            raise ProductionAdapterError(
                "protected run plan action identities are invalid"
            )
        normalized_evaluator = evaluator_config.model_dump(mode="json")
        runtime = payload.get("runtime")
        if runtime is not None and not isinstance(runtime, dict):
            raise ProductionAdapterError(
                "protected run plan runtime configuration is invalid"
            )
        identity = {"actions": actions, "evaluator": normalized_evaluator}
        if runtime is not None:
            identity["runtime"] = runtime
        return cls(
            actions=tuple(dict(item) for item in actions),
            evaluator=normalized_evaluator,
            runtime=dict(runtime) if runtime is not None else None,
            plan_digest=_digest(identity),
            evaluator_digest=_digest(normalized_evaluator),
        )

    @classmethod
    def load(cls, protected_root: Path, relative_path: str) -> ProtectedRunPlan:
        return cls.from_payload(_read_protected_json(protected_root, relative_path))


@dataclass(frozen=True)
class ProducedAttempt:
    """One producer-owned committed execution ready for coordinator publication."""

    artifact: dict[str, Any]
    receipt: dict[str, Any]


@dataclass(frozen=True)
class LocalFakeAttemptProducer:
    """Task-2 deterministic local producer for the sealed fake adapter flow."""

    observed_at: datetime

    @staticmethod
    def _assertion_ids(
        registry: TrustedAcceptanceRegistry, execution_id: str
    ) -> tuple[str, ...]:
        scenario = registry.compiled_policy.scenarios.get(execution_id)
        if scenario is not None:
            assertion_ids = {
                item.assertion_id
                for group in (scenario.checkpoints, scenario.prohibited_outcomes)
                for item in group.values()
            }
            criterion_ids = scenario.criterion_ids
        else:
            block = registry.compiled_policy.evidence_blocks[execution_id]
            assertion_ids = {item.assertion_id for item in block.oracle_checks.values()}
            criterion_ids = block.criterion_ids
        for criterion_id in criterion_ids:
            assertion_ids.update(
                item.assertion_id
                for item in registry.compiled_policy.criteria[
                    criterion_id
                ].oracle_checks.values()
            )
        return tuple(sorted(assertion_ids))

    @staticmethod
    def _binding(assertion: Any) -> tuple[str, str, str]:
        if assertion.oracle.kind == "classifier_result":
            return (
                assertion.oracle.allowed_producers[0],
                "classifier",
                str(assertion.oracle.classifier_id),
            )
        if assertion.oracle.kind == "independent_readback":
            return (
                "independent-readback-collector",
                "collector",
                "independent-readback-collector",
            )
        if "production-policy-classifier" in assertion.oracle.allowed_producers:
            return (
                "production-policy-classifier",
                "classifier",
                "scenario_policy.v2",
            )
        if "trusted-evidence-registry" in assertion.oracle.allowed_producers:
            return (
                "trusted-evidence-registry",
                "trusted-registry",
                "trusted-evidence-registry",
            )
        raise ProductionAdapterError("local fake lacks an allowed producer binding")

    def evaluator(self, registry: TrustedAcceptanceRegistry) -> dict[str, Any]:
        bindings: dict[str, tuple[str, str]] = {}
        for execution_id in registry.compiled_plan.execution_ids:
            for assertion_id in self._assertion_ids(registry, execution_id):
                producer, producer_kind, source_identity = self._binding(
                    registry.compiled_policy.assertions[assertion_id]
                )
                bindings[producer] = (producer_kind, source_identity)
        return {
            "schema_version": "noor-e2e-protected-evaluator/v1",
            "publication": {
                "schema_version": "noor-e2e-publication-metadata/v1",
                "title": "Приёмочное тестирование Noor",
                "tester": {
                    "model": "production/fake-tester",
                    "reasoning_effort": "none",
                    "seed": 11,
                    "config_digest": "3" * 64,
                    "evidence_refs": ["report-source"],
                },
                "judge": {
                    "model": "production/fake-judge",
                    "reasoning_effort": "none",
                    "seed": 11,
                    "config_digest": "4" * 64,
                    "evidence_refs": ["report-source"],
                },
                "limitations": ["Local deterministic fake production flow."],
                "external_gates": [],
            },
            "decisive_producers": [
                {
                    "producer_id": producer,
                    "producer_kind": producer_kind,
                    "capability": "outbound_text",
                    "source_identity": source_identity,
                    "config_digest": _digest(
                        {
                            "producer": producer,
                            "producer_kind": producer_kind,
                            "source_identity": source_identity,
                        }
                    ),
                }
                for producer, (producer_kind, source_identity) in sorted(
                    bindings.items()
                )
            ],
        }

    def _planned_turn(
        self, registry: TrustedAcceptanceRegistry, execution_id: str
    ) -> execution.PlannedTurnV2:
        scenario = registry.compiled_policy.scenarios[execution_id]
        return execution.PlannedTurnV2(
            turn_id=f"turn-{execution_id.lower()}",
            customer_input_digest=_digest({"input": execution_id}),
            expected_behavior_digest=_digest({"expected": execution_id}),
            criterion_ids=scenario.criterion_ids,
            assertion_ids=self._assertion_ids(registry, execution_id),
        )

    def execution_input_digests(
        self, registry: TrustedAcceptanceRegistry
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        for execution_id in registry.compiled_plan.execution_ids:
            if execution_id in registry.compiled_policy.scenarios:
                planned = self._planned_turn(registry, execution_id)
                result[execution_id] = execution.scenario_input_digest(
                    execution_id=execution_id,
                    planned_turns=(planned,),
                    tester_config_digest="5" * 64,
                    judge_config_digest="6" * 64,
                )
            else:
                result[execution_id] = execution.evidence_block_input_digest(
                    execution.EvidenceBlockAttemptV2(
                        schema_version="noor-e2e-evidence-block-attempt/v2",
                        execution_id=execution_id,
                        evidence_collection_digest=_digest(
                            {"collection": execution_id}
                        ),
                        evaluator_config_digest=_digest({"evaluator": execution_id}),
                        oracle_evidence=(
                            OracleEvidence(
                                assertion_id=self._assertion_ids(
                                    registry, execution_id
                                )[0],
                                structured_events=(),
                                tool_results=(),
                                readbacks=(),
                                classifier_results=(),
                                text_supplements=(),
                            ),
                        ),
                        permission_evidence=registry.compiled_policy.evidence_blocks[
                            execution_id
                        ].required_permissions,
                    )
                )
        return result

    def _oracle_evidence(
        self,
        registry: TrustedAcceptanceRegistry,
        journal: execution.ProtectedExecutionJournal,
        execution_id: str,
    ) -> tuple[OracleEvidence, ...]:
        attempt_digest = journal.authorization.execution_input_digests[execution_id]
        evidence: list[OracleEvidence] = []
        for assertion_id in self._assertion_ids(registry, execution_id):
            assertion = registry.compiled_policy.assertions[assertion_id]
            producer, _, source_identity = self._binding(assertion)
            source_id = (
                f"trusted-registry:{'external-gate' if assertion.oracle.kind == 'external_gate_evidence' else 'reused'}:{assertion_id}"
                if producer == "trusted-evidence-registry"
                else f"local:{assertion_id}"
            )
            common = {
                "assertion_id": assertion_id,
                "run_id": journal.run_id,
                "attempt_digest": attempt_digest,
                "preflight_digest": journal.authorization.preflight_digest,
                "producer": producer,
                "source_id": source_id,
                "source_digest": _digest({"source": assertion_id}),
                "observed_at": self.observed_at,
                "passed": True,
                "reason": "Local deterministic evidence passed.",
            }
            if assertion.oracle.kind == "classifier_result":
                artifact = ClassifierResult.build(
                    **common,
                    policy_digest=registry.compiled_policy.policy_digest,
                    evaluator_digest=registry.classifier_evaluator_digest(assertion_id),
                    classifier_id=source_identity,
                )
                evidence.append(
                    OracleEvidence(
                        assertion_id=assertion_id,
                        structured_events=(),
                        tool_results=(),
                        readbacks=(),
                        classifier_results=(artifact,),
                        text_supplements=(),
                    )
                )
            elif assertion.oracle.kind == "independent_readback":
                artifact = ReadbackResult.build(
                    **common, collector_id="independent-readback-collector"
                )
                evidence.append(
                    OracleEvidence(
                        assertion_id=assertion_id,
                        structured_events=(),
                        tool_results=(),
                        readbacks=(artifact,),
                        classifier_results=(),
                        text_supplements=(),
                    )
                )
            else:
                artifact = StructuredEvent.build(**common)
                evidence.append(
                    OracleEvidence(
                        assertion_id=assertion_id,
                        structured_events=(artifact,),
                        tool_results=(),
                        readbacks=(),
                        classifier_results=(),
                        text_supplements=(),
                    )
                )
        return tuple(evidence)

    def _attempt(
        self,
        registry: TrustedAcceptanceRegistry,
        journal: execution.ProtectedExecutionJournal,
        execution_id: str,
    ) -> execution.ExecutedAttemptV2:
        oracle_evidence = self._oracle_evidence(registry, journal, execution_id)
        if execution_id not in registry.compiled_policy.scenarios:
            block = registry.compiled_policy.evidence_blocks[execution_id]
            return execution.EvidenceBlockAttemptV2(
                schema_version="noor-e2e-evidence-block-attempt/v2",
                execution_id=execution_id,
                evidence_collection_digest=_digest({"collection": execution_id}),
                evaluator_config_digest=_digest({"evaluator": execution_id}),
                oracle_evidence=oracle_evidence,
                permission_evidence=block.required_permissions,
            )
        scenario = registry.compiled_policy.scenarios[execution_id]
        planned = self._planned_turn(registry, execution_id)
        baseline = ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id=f"local-baseline-{execution_id}",
            run_id=journal.run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
            causal_event_digest=_digest({"baseline": execution_id}),
            observed_at=self.observed_at - timedelta(seconds=3),
            inventory={"synthetic:item": {"state": "absent"}},
        )
        final = ReadbackObservation.build(
            phase="final",
            collector_id="independent-readback-collector",
            source_id=f"local-final-{execution_id}",
            run_id=journal.run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
            causal_event_digest=_digest({"final": execution_id}),
            observed_at=self.observed_at + timedelta(seconds=2),
            inventory={"synthetic:item": {"state": "absent"}},
        )
        timeline = execution.TurnTimelineV2(
            sent_at=self.observed_at - timedelta(seconds=2),
            first_visible_at=self.observed_at - timedelta(seconds=1),
            final_visible_at=self.observed_at,
            delivered_at=self.observed_at + timedelta(seconds=1),
        )
        actual = execution.ActualTurnV2(
            actual_turn_id=planned.turn_id,
            planned_turn_id=planned.turn_id,
            customer_input_digest=planned.customer_input_digest,
            expected_behavior_digest=planned.expected_behavior_digest,
            criterion_ids=planned.criterion_ids,
            assertion_ids=planned.assertion_ids,
            event_refs=(f"event:{execution_id}",),
            tool_refs=(),
            audit_refs=(f"audit:{execution_id}",),
            timeline=timeline,
            model_id="production/fake-main",
            token_count=1,
            cost_usd=0,
        )
        return execution.ScenarioAttemptV2(
            schema_version="noor-e2e-scenario-attempt/v2",
            execution_id=execution_id,
            planned_turns=(planned,),
            actual_turns=(actual,),
            adaptive_deviations=(),
            oracle_evidence=oracle_evidence,
            permission_evidence=scenario.required_permissions,
            readback_evidence=scenario.required_readbacks,
            baseline=baseline,
            final=final,
            action_at=(self.observed_at,),
            tester_config_digest="5" * 64,
            judge_config_digest="6" * 64,
        )

    def emit_next(
        self,
        *,
        registry: TrustedAcceptanceRegistry,
        journal: execution.ProtectedExecutionJournal,
        authority: execution.ExecutionAuthorizationHandle,
        sealed_plan: ProtectedRunPlan,
        execution_id: str,
    ) -> Any:
        from scripts.e2e_acceptance.coordinator import (
            ProductionRunCoordinator,
            ProtectedJournalAcceptancePort,
        )

        producer_handle = issue_decisive_producer_handle(
            registry=registry,
            journal=journal,
            authority=authority,
            sealed_plan=sealed_plan,
        )
        source_output_ref = _write_local_fake_producer_observation(
            producer_handle=producer_handle,
            attempted=self._attempt(registry, journal, execution_id),
        )
        artifact = ProductionRunCoordinator(
            registry=registry,
            authorization=authority._authorization,
            protected_root=journal.protected_root,
            run_id=journal.run_id,
            journal=ProtectedJournalAcceptancePort(journal=journal),
            current_time=datetime.now(UTC),
        ).publish_next_from_decisive_producer(producer_handle, source_output_ref)
        if execution_id == registry.compiled_plan.execution_ids[-1]:
            self._write_transcript_manifest(registry, journal)
        return artifact

    @staticmethod
    def _write_transcript_manifest(
        registry: TrustedAcceptanceRegistry,
        journal: execution.ProtectedExecutionJournal,
    ) -> None:
        """Project the final local-fake transcript index from sealed transcript pairs."""

        ordered_turns: list[list[str]] = []
        for execution_id in registry.compiled_plan.execution_ids:
            if execution_id not in registry.compiled_policy.scenarios:
                continue
            attempt_id = f"attempt:{execution_id}"
            turn_id = f"turn-{execution_id.lower()}"
            transcript_relative = (
                f"transcripts/{execution_id}/{attempt_id}/{turn_id}.json"
            )
            receipt_relative = f"producer-receipts/transcripts/{execution_id}/{attempt_id}/{turn_id}.json"
            ordered_turns.append(
                [
                    execution_id,
                    attempt_id,
                    turn_id,
                    hashlib.sha256(
                        execution._read_protected(journal.run_root, transcript_relative)
                    ).hexdigest(),
                    hashlib.sha256(
                        execution._read_protected(journal.run_root, receipt_relative)
                    ).hexdigest(),
                ]
            )
        _write_or_validate_exact(
            journal.run_root,
            "transcripts/manifest.json",
            {
                "schema_version": "noor-e2e-protected-transcript-manifest/v2",
                "registry_id": registry.registry_id,
                "run_id": journal.run_id,
                "ordered_turns": ordered_turns,
            },
        )


@dataclass(frozen=True)
class _ProducedPublication:
    """Protected producer result ready for the coordinator's private write."""

    artifact: dict[str, Any]
    receipt: dict[str, Any]
    source: dict[str, Any]
    observed_at: datetime


_PRODUCER_HANDLE_TOKEN = object()


@dataclass(frozen=True)
class DecisiveProducerHandle:
    """Non-serializable authority for one next, sealed execution source."""

    _token: object
    _run_id: str
    _registry_id: str

    def __getstate__(self) -> object:
        raise TypeError("decisive producer handles are not serializable")

    def __reduce__(self) -> object:
        raise TypeError("decisive producer handles are not serializable")


@dataclass(frozen=True)
class _ProducerHandleRecord:
    handle_ref: weakref.ReferenceType[DecisiveProducerHandle]
    registry: TrustedAcceptanceRegistry
    journal: execution.ProtectedExecutionJournal
    authority: execution.ExecutionAuthorizationHandle
    sealed_plan: ProtectedRunPlan
    execution_id: str
    ordinal: int


_PRODUCER_HANDLE_RECORDS: dict[int, _ProducerHandleRecord] = {}


def _next_execution_scope(
    registry: TrustedAcceptanceRegistry, journal: execution.ProtectedExecutionJournal
) -> tuple[int, str]:
    if journal.phase != "executing":
        raise ProductionAdapterError("no canonical execution remains for producer")
    for ordinal, execution_id in enumerate(
        registry.compiled_plan.execution_ids, start=1
    ):
        receipt_payload = _optional_protected_payload(
            journal.run_root, f"producer-receipts/attempts/{execution_id}.json"
        )
        if receipt_payload is None:
            # An intent is not coverage.  Recovery must decide its exact retry
            # disposition before this boundary can issue another producer handle.
            transaction_id = f"{execution_id.lower()}-attempt-001"
            committed = _optional_protected_payload(
                journal.run_root, f"attempts/{transaction_id}/commit.json"
            )
            if committed is not None:
                try:
                    commit = json.loads(committed)
                except json.JSONDecodeError as exc:
                    raise ProductionAdapterError(
                        "committed producer recovery payload is invalid"
                    ) from exc
                if not isinstance(commit, dict):
                    raise ProductionAdapterError(
                        "committed producer recovery payload is invalid"
                    )
                if commit.get("status") == "committed":
                    return ordinal, execution_id
            if execution_id in journal._attempted_executions:
                raise ProductionAdapterError(
                    "uncommitted producer intent requires recovery"
                )
            return ordinal, execution_id
        try:
            payload = json.loads(receipt_payload)
        except json.JSONDecodeError as exc:
            raise ProductionAdapterError(
                "committed producer receipt is invalid"
            ) from exc
        if not isinstance(payload, dict):
            raise ProductionAdapterError("committed producer receipt is invalid")
        if (
            payload.get("schema_version") != "noor-e2e-attempt-producer-receipt/v2"
            or payload.get("registry_id") != registry.registry_id
            or payload.get("run_id") != journal.run_id
            or payload.get("authorization_digest") != journal.authorization_digest
            or payload.get("execution_id") != execution_id
        ):
            raise ProductionAdapterError("committed producer receipt binding drift")
    raise ProductionAdapterError("no canonical execution remains for producer")


def issue_decisive_producer_handle(
    *,
    registry: TrustedAcceptanceRegistry,
    journal: execution.ProtectedExecutionJournal,
    authority: execution.ExecutionAuthorizationHandle,
    sealed_plan: ProtectedRunPlan,
) -> DecisiveProducerHandle:
    """Issue an opaque capability for exactly the journal's next execution."""

    load_sealed_run_plan(journal, sealed_plan)
    execution.GenericAcceptanceRunner(
        registry=registry,
        authority=authority,
        journal=journal,
    )
    ordinal, execution_id = _next_execution_scope(registry, journal)
    handle = DecisiveProducerHandle(
        _token=_PRODUCER_HANDLE_TOKEN,
        _run_id=journal.run_id,
        _registry_id=registry.registry_id,
    )
    identity = id(handle)

    def _discard(_: object) -> None:
        _PRODUCER_HANDLE_RECORDS.pop(identity, None)

    _PRODUCER_HANDLE_RECORDS[identity] = _ProducerHandleRecord(
        handle_ref=weakref.ref(handle, _discard),
        registry=registry,
        journal=journal,
        authority=authority,
        sealed_plan=sealed_plan,
        execution_id=execution_id,
        ordinal=ordinal,
    )
    return handle


def _producer_handle_record(handle: object) -> _ProducerHandleRecord:
    record = _PRODUCER_HANDLE_RECORDS.get(id(handle))
    if (
        not isinstance(handle, DecisiveProducerHandle)
        or handle._token is not _PRODUCER_HANDLE_TOKEN
        or record is None
        or record.handle_ref() is not handle
        or handle._run_id != record.journal.run_id
        or handle._registry_id != record.registry.registry_id
    ):
        raise ProductionAdapterError("decisive producer handle is invalid")
    ordinal, execution_id = _next_execution_scope(record.registry, record.journal)
    if (ordinal, execution_id) != (record.ordinal, record.execution_id):
        raise ProductionAdapterError("decisive producer handle execution is stale")
    load_sealed_run_plan(record.journal, record.sealed_plan)
    return record


def _evaluator_bindings(plan: ProtectedRunPlan) -> dict[str, DecisiveProducerBinding]:
    config = ProtectedEvaluatorConfig.model_validate(plan.evaluator)
    return {item.producer_id: item for item in config.decisive_producers}


def _execution_assertion_ids(
    registry: TrustedAcceptanceRegistry, execution_id: str
) -> frozenset[str]:
    """Return every canonical assertion owned by one execution scope."""

    scenario = registry.compiled_policy.scenarios.get(execution_id)
    if scenario is not None:
        assertion_ids = {
            item.assertion_id
            for group in (scenario.checkpoints, scenario.prohibited_outcomes)
            for item in group.values()
        }
        criterion_ids = scenario.criterion_ids
    else:
        block = registry.compiled_policy.evidence_blocks.get(execution_id)
        if block is None:
            raise ProductionAdapterError("decisive evidence execution is unknown")
        assertion_ids = {item.assertion_id for item in block.oracle_checks.values()}
        criterion_ids = block.criterion_ids
    for criterion_id in criterion_ids:
        assertion_ids.update(
            item.assertion_id
            for item in registry.compiled_policy.criteria[
                criterion_id
            ].oracle_checks.values()
        )
    return frozenset(assertion_ids)


def _require_execution_assertion(
    registry: TrustedAcceptanceRegistry, execution_id: str, assertion_id: str
) -> None:
    if assertion_id not in _execution_assertion_ids(registry, execution_id):
        raise ProductionAdapterError("decisive evidence criterion ownership drift")


def _validate_decisive_binding(
    *,
    binding: DecisiveProducerBinding,
    journal: execution.ProtectedExecutionJournal,
    registry: TrustedAcceptanceRegistry | None,
    artifact: object | None = None,
) -> None:
    """Validate a plan producer against exact authority and evidence kind."""

    authorization = journal.authorization
    if binding.producer_kind == "adapter":
        valid = (
            binding.producer_id == binding.source_identity
            and binding.source_identity in authorization.adapter_ids
        )
    elif binding.producer_kind == "collector":
        valid = (
            binding.producer_id == binding.source_identity
            and binding.source_identity in authorization.collector_ids
        )
    elif binding.producer_kind == "classifier":
        valid = bool(binding.source_identity)
        if isinstance(artifact, ClassifierResult) and registry is not None:
            assertion = registry.compiled_policy.assertions.get(artifact.assertion_id)
            valid = valid and (
                assertion is not None
                and artifact.policy_digest == registry.compiled_policy.policy_digest
                and artifact.evaluator_digest
                == registry.classifier_evaluator_digest(artifact.assertion_id)
                and artifact.classifier_id == assertion.oracle.classifier_id
                and artifact.classifier_id == binding.source_identity
            )
    else:
        valid = binding.source_identity == "trusted-evidence-registry"
        if artifact is not None and registry is not None:
            assertion = registry.compiled_policy.assertions.get(
                getattr(artifact, "assertion_id", "")
            )
            prefix = (
                "trusted-registry:reused:"
                if assertion is not None
                and assertion.oracle.kind == "reused_exact_evidence"
                else "trusted-registry:external-gate:"
                if assertion is not None
                and assertion.oracle.kind == "external_gate_evidence"
                else None
            )
            valid = valid and (
                isinstance(artifact, StructuredEvent)
                and artifact.producer == "trusted-evidence-registry"
                and prefix is not None
                and artifact.source_id.startswith(prefix)
            )
    if not valid:
        raise ProductionAdapterError("sealed decisive producer authority drift")


def _observation_relative(record: _ProducerHandleRecord) -> str:
    return f"producer-observations/{record.ordinal:02d}.json"


def _observation_receipt_relative(record: _ProducerHandleRecord) -> str:
    return f"producer-receipts/observations/{record.ordinal:02d}.json"


def _evidence_items(attempted: execution.ExecutedAttemptV2) -> tuple[object, ...]:
    return tuple(
        item
        for evidence in attempted.oracle_evidence
        for item in (
            *evidence.structured_events,
            *evidence.tool_results,
            *evidence.readbacks,
            *evidence.classifier_results,
        )
    )


def _attempt_source_identity_digest(
    attempted: execution.ExecutedAttemptV2 | execution.GateAttemptV2,
) -> str:
    """Digest all observed source facts, excluding only derived oracle output."""

    identity = attempted.model_dump(mode="json")
    identity.pop("oracle_evidence", None)
    return execution._digest(identity)


def _write_producer_observation(
    *,
    producer_handle: DecisiveProducerHandle,
    attempted: execution.ExecutedAttemptV2 | execution.GateAttemptV2,
    transcript_facts: list[dict[str, Any]],
    side_effect_dispositions: list[dict[str, Any]] | None = None,
) -> str:
    """Private bridge from a typed producer result to protected publication state."""

    record = _producer_handle_record(producer_handle)
    if attempted.execution_id != record.execution_id:
        raise ProductionAdapterError("producer observation execution binding drift")
    attempt_payload = attempted.model_dump(mode="json")
    source_attempt_digest = _attempt_source_identity_digest(attempted)
    criterion_ids = tuple(
        criterion.criterion_id
        for criterion in record.registry.compiled_plan.criteria.values()
        if record.execution_id in criterion.obligation_ids
    )
    if not criterion_ids:
        raise ProductionAdapterError("producer observation criterion scope is empty")
    bindings = _evaluator_bindings(record.sealed_plan)
    authorized_input_digest = record.journal.authorization.execution_input_digests[
        record.execution_id
    ]
    items = (
        ()
        if isinstance(attempted, execution.GateAttemptV2)
        else _evidence_items(attempted)
    )
    decisive_receipts: list[dict[str, str]] = []
    for artifact in items:
        binding = bindings.get(artifact.producer)
        if binding is None:
            raise ProductionAdapterError("producer observation is not sealed")
        _validate_decisive_binding(
            binding=binding,
            journal=record.journal,
            registry=record.registry,
            artifact=artifact,
        )
        if artifact.attempt_digest != authorized_input_digest:
            raise ProductionAdapterError(
                "producer observation authorized input binding drift"
            )
        kind = (
            "classifier_result"
            if isinstance(artifact, ClassifierResult)
            else "structured_event"
            if isinstance(artifact, StructuredEvent)
            else "tool_result"
            if isinstance(artifact, ToolResult)
            else "readback_result"
        )
        envelope = {
            "schema_version": "noor-e2e-decisive-observation/v1",
            "evidence_kind": kind,
            "artifact": artifact.model_dump(mode="json"),
            "execution_id": record.execution_id,
            "criterion_ids": criterion_ids,
            "source_attempt_digest": source_attempt_digest,
            "authorized_input_digest": authorized_input_digest,
            "source_identity": binding.source_identity,
        }
        digest = artifact.artifact_digest
        _write_or_validate_exact(
            record.journal.run_root, f"decisive/{digest}.json", envelope
        )
        receipt_relative = f"producer-receipts/decisive/{digest}.json"
        receipt_digest = _write_or_validate_exact(
            record.journal.run_root,
            receipt_relative,
            {
                "schema_version": "noor-e2e-decisive-producer-receipt/v3",
                "registry_id": record.registry.registry_id,
                "artifact_digest": digest,
                "run_id": record.journal.run_id,
                "execution_id": record.execution_id,
                "criterion_ids": criterion_ids,
                "attempt_digest": artifact.attempt_digest,
                "source_attempt_digest": source_attempt_digest,
                "authorized_input_digest": authorized_input_digest,
                "preflight_digest": artifact.preflight_digest,
                "assertion_id": artifact.assertion_id,
                "producer": artifact.producer,
                "producer_kind": binding.producer_kind,
                "source_identity": binding.source_identity,
                "config_digest": binding.config_digest,
                "relative_path": f"decisive/{digest}.json",
                "tracked_sha256": _digest(envelope),
            },
        )
        decisive_receipts.append(
            {
                "artifact_digest": digest,
                "relative_path": receipt_relative,
                "receipt_digest": receipt_digest,
            }
        )
    if not isinstance(attempted, execution.ScenarioAttemptV2) and transcript_facts:
        raise ProductionAdapterError("non-scenario producer cannot publish transcripts")
    if isinstance(attempted, execution.ScenarioAttemptV2):
        if len(transcript_facts) != len(attempted.actual_turns):
            raise ProductionAdapterError("producer transcript cardinality drift")
        expected_turn_ids = tuple(
            item.actual_turn_id for item in attempted.actual_turns
        )
        if tuple(item.get("turn_id") for item in transcript_facts) != expected_turn_ids:
            raise ProductionAdapterError("producer transcript identity drift")
    source_ref = _observation_relative(record)
    source = {
        "schema_version": "noor-e2e-protected-source-observation/v1",
        "registry_id": record.registry.registry_id,
        "run_id": record.journal.run_id,
        "authorization_digest": record.journal.authorization_digest,
        "ordinal": record.ordinal,
        "execution_id": record.execution_id,
        "criterion_ids": criterion_ids,
        "attempt": attempt_payload,
        "source_attempt_digest": source_attempt_digest,
        "authorized_input_digest": authorized_input_digest,
        "decisive_receipts": decisive_receipts,
        "publication_facts": [
            {
                "criterion_id": criterion_id,
                "evidence_mode": record.registry.compiled_plan.criteria[
                    criterion_id
                ].evidence_mode.value,
            }
            for criterion_id in criterion_ids
        ],
        "transcript_facts": transcript_facts,
        "side_effect_dispositions": side_effect_dispositions or [],
    }
    _write_or_validate_exact(record.journal.run_root, source_ref, source)
    _write_or_validate_exact(
        record.journal.run_root,
        _observation_receipt_relative(record),
        {
            "schema_version": "noor-e2e-protected-source-observation-receipt/v1",
            "registry_id": record.registry.registry_id,
            "run_id": record.journal.run_id,
            "authorization_digest": record.journal.authorization_digest,
            "ordinal": record.ordinal,
            "execution_id": record.execution_id,
            "criterion_ids": criterion_ids,
            "relative_path": source_ref,
            "source_attempt_digest": source_attempt_digest,
            "authorized_input_digest": authorized_input_digest,
            "tracked_sha256": _digest(source),
        },
    )
    return source_ref


def _write_local_fake_producer_observation(
    *,
    producer_handle: DecisiveProducerHandle,
    attempted: execution.ExecutedAttemptV2 | execution.GateAttemptV2,
) -> str:
    """Private fake adapter: derive deterministic transcript facts once."""

    record = _producer_handle_record(producer_handle)
    transcript_facts: list[dict[str, Any]] = []
    if isinstance(attempted, execution.ScenarioAttemptV2):
        for actual in attempted.actual_turns:
            timeline = actual.timeline
            transcript_facts.append(
                {
                    "turn_id": actual.actual_turn_id,
                    "question": f"Deterministic question for {record.execution_id}.",
                    "answer": f"Deterministic answer for {record.execution_id}.",
                    "sent_at": timeline.sent_at.isoformat().replace("+00:00", "Z"),
                    "received_at": timeline.first_visible_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "first_visible_at": timeline.first_visible_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "final_visible_at": timeline.final_visible_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "delivered_at": (
                        timeline.delivered_at.isoformat().replace("+00:00", "Z")
                        if timeline.delivered_at is not None
                        else None
                    ),
                    "conversation_id": f"local-{record.execution_id}",
                    "message_id": actual.actual_turn_id,
                    "provider_message_id": f"local-{actual.actual_turn_id}",
                    "model": actual.model_id,
                    "tools": list(actual.tool_refs),
                    "tool_outcomes": ["passed"] * len(actual.tool_refs),
                    "audit_ids": list(actual.audit_refs),
                    "media_refs": [],
                    "token_count": actual.token_count,
                    "cost_usd": actual.cost_usd,
                    "duration_ms": max(
                        int(
                            (
                                timeline.final_visible_at - timeline.sent_at
                            ).total_seconds()
                            * 1000
                        ),
                        0,
                    ),
                    "deviation": None,
                    "evaluator_reasoning": "Protected deterministic checks passed.",
                }
            )
    return _write_producer_observation(
        producer_handle=producer_handle,
        attempted=attempted,
        transcript_facts=transcript_facts,
    )


@dataclass(frozen=True)
class ProtectedEvidenceResolver:
    """Evaluate an in-flight attempt from fixed protected producer pairs.

    ``TrustedAcceptanceRegistry`` deliberately only trusts a finalized run.
    This resolver is the narrow pre-acceptance bridge: every candidate named
    by an oracle must have its exact protected artifact and producer receipt
    below this run root.  It never changes registry context and cannot reuse a
    global fresh marker.
    """

    registry: TrustedAcceptanceRegistry
    journal: execution.ProtectedExecutionJournal
    execution_id: str
    source_attempt_digest: str
    sealed_plan: ProtectedRunPlan
    source_output_ref: str

    def _criterion_ids(self) -> tuple[str, ...]:
        return tuple(
            criterion.criterion_id
            for criterion in self.registry.compiled_plan.criteria.values()
            if self.execution_id in criterion.obligation_ids
        )

    def validate_readback_window(
        self,
        *,
        baseline: ReadbackObservation,
        final: ReadbackObservation,
        final_visible_at: tuple[datetime, ...] | list[datetime],
        delivered_at: tuple[datetime, ...] | list[datetime],
        action_at: tuple[datetime, ...] | list[datetime],
    ) -> None:
        """Validate current-run readbacks from the same protected observation."""

        source = _read_protected_json(self.journal.run_root, self.source_output_ref)
        ordinal = source.get("ordinal")
        if not isinstance(ordinal, int) or ordinal < 1:
            raise ProductionAdapterError("protected current-run readback receipt drift")
        receipt = _read_protected_json(
            self.journal.run_root,
            f"producer-receipts/observations/{ordinal:02d}.json",
        )
        attempt = source.get("attempt")
        if (
            not isinstance(attempt, dict)
            or attempt.get("baseline") != baseline.model_dump(mode="json")
            or attempt.get("final") != final.model_dump(mode="json")
            or source.get("run_id") != self.journal.run_id
            or source.get("execution_id") != self.execution_id
            or source.get("authorization_digest") != self.journal.authorization_digest
            or receipt.get("relative_path") != self.source_output_ref
            or receipt.get("tracked_sha256") != _digest(source)
            or receipt.get("source_attempt_digest") != self.source_attempt_digest
        ):
            raise ProductionAdapterError("protected current-run readback receipt drift")
        authorization = self.journal.authorization
        if (
            baseline.run_id != final.run_id
            or baseline.run_id != self.journal.run_id
            or baseline.preflight_digest != final.preflight_digest
            or baseline.preflight_digest != authorization.preflight_digest
            or baseline.collector_artifact_digest != final.collector_artifact_digest
            or baseline.collector_artifact_digest
            != authorization.readback_collector_digest
            or baseline.collector_id not in authorization.collector_ids
            or final.collector_id not in authorization.collector_ids
            or baseline.phase != "baseline"
            or final.phase != "final"
            or baseline.source_id == final.source_id
            or baseline.observed_at >= final.observed_at
        ):
            raise ProductionAdapterError("current-run readback identity drift")
        timeline = [*final_visible_at, *delivered_at, *action_at]
        if (
            not timeline
            or any(item.tzinfo is None or item.utcoffset() is None for item in timeline)
            or baseline.observed_at >= min(timeline)
            or final.observed_at < max(timeline)
        ):
            raise ProductionAdapterError("current-run readback timing drift")

    def _artifact(self, artifact: object) -> object:
        digest = getattr(artifact, "artifact_digest", None)
        if not isinstance(digest, str):
            raise ProductionAdapterError("oracle artifact lacks digest")
        try:
            envelope = _read_protected_json(
                self.journal.run_root, f"decisive/{digest}.json"
            )
            receipt = _read_protected_json(
                self.journal.run_root,
                f"producer-receipts/decisive/{digest}.json",
            )
        except ProductionAdapterError as exc:
            raise ProductionAdapterError(
                "protected decisive evidence is missing"
            ) from exc
        payload = envelope.get("artifact")
        kind = envelope.get("evidence_kind")
        if not isinstance(payload, dict) or kind not in {
            "classifier_result",
            "structured_event",
            "tool_result",
            "readback_result",
        }:
            raise ProductionAdapterError("protected decisive evidence envelope drift")
        model = {
            "classifier_result": ClassifierResult,
            "structured_event": StructuredEvent,
            "tool_result": ToolResult,
            "readback_result": ReadbackResult,
        }[kind]
        try:
            materialized = model.model_validate(payload)
        except ValueError as exc:
            raise ProductionAdapterError(
                "protected decisive artifact is invalid"
            ) from exc
        assertion = self.registry.compiled_policy.assertions.get(
            materialized.assertion_id
        )
        if (
            assertion is None
            or materialized.producer not in assertion.oracle.allowed_producers
        ):
            raise ProductionAdapterError("decisive evidence producer is unauthorized")
        if (
            materialized != artifact
            or materialized.run_id != self.journal.run_id
            or materialized.attempt_digest != receipt.get("attempt_digest")
            or materialized.preflight_digest
            != self.journal.authorization.preflight_digest
            or envelope.get("execution_id") != self.execution_id
            or tuple(envelope.get("criterion_ids", ())) != self._criterion_ids()
            or envelope.get("source_attempt_digest") != self.source_attempt_digest
            or envelope.get("authorized_input_digest")
            != self.journal.authorization.execution_input_digests[self.execution_id]
            or receipt.get("schema_version") != "noor-e2e-decisive-producer-receipt/v3"
            or receipt.get("registry_id") != self.registry.registry_id
            or receipt.get("artifact_digest") != digest
            or receipt.get("run_id") != self.journal.run_id
            or receipt.get("execution_id") != self.execution_id
            or tuple(receipt.get("criterion_ids", ())) != self._criterion_ids()
            or receipt.get("attempt_digest") != materialized.attempt_digest
            or receipt.get("source_attempt_digest") != self.source_attempt_digest
            or receipt.get("authorized_input_digest")
            != self.journal.authorization.execution_input_digests[self.execution_id]
            or materialized.attempt_digest
            != self.journal.authorization.execution_input_digests[self.execution_id]
            or receipt.get("preflight_digest") != materialized.preflight_digest
            or receipt.get("assertion_id") != materialized.assertion_id
            or receipt.get("producer") != materialized.producer
            or receipt.get("source_identity") != envelope.get("source_identity")
            or receipt.get("relative_path") != f"decisive/{digest}.json"
            or receipt.get("tracked_sha256") != _digest(envelope)
        ):
            raise ProductionAdapterError("protected decisive evidence receipt drift")
        binding = _evaluator_bindings(
            load_sealed_run_plan(self.journal, self.sealed_plan)
        ).get(materialized.producer)
        if (
            binding is None
            or receipt.get("producer_kind") != binding.producer_kind
            or receipt.get("source_identity") != binding.source_identity
            or receipt.get("config_digest") != binding.config_digest
        ):
            raise ProductionAdapterError("protected decisive producer binding drift")
        _validate_decisive_binding(
            binding=binding,
            journal=self.journal,
            registry=self.registry,
            artifact=materialized,
        )
        _require_execution_assertion(
            self.registry, self.execution_id, materialized.assertion_id
        )
        expected_type = {
            "classifier_result": ClassifierResult,
            "independent_readback": ReadbackResult,
            "structured_event": StructuredEvent,
            "structured_evidence": StructuredEvent,
            "reused_exact_evidence": StructuredEvent,
            "external_gate_evidence": StructuredEvent,
        }.get(assertion.oracle.kind)
        if expected_type is None or not isinstance(materialized, expected_type):
            raise ProductionAdapterError("protected decisive evidence kind drift")
        if isinstance(materialized, ReadbackResult) and (
            materialized.collector_id not in self.journal.authorization.collector_ids
            or materialized.collector_id != receipt.get("source_identity")
        ):
            raise ProductionAdapterError("protected readback collector binding drift")
        if isinstance(materialized, ClassifierResult) and (
            materialized.policy_digest != self.registry.compiled_policy.policy_digest
            or materialized.evaluator_digest
            != self.registry.classifier_evaluator_digest(materialized.assertion_id)
            or materialized.classifier_id != assertion.oracle.classifier_id
        ):
            raise ProductionAdapterError("protected classifier evaluator binding drift")
        if (
            not isinstance(materialized, ClassifierResult)
            and assertion.oracle.kind == "classifier_result"
        ):
            raise ProductionAdapterError("protected decisive evidence kind drift")
        return materialized

    def evaluate_oracle(
        self, assertion_id: str, evidence: OracleEvidence
    ) -> OracleDecision:
        assertion = self.registry.compiled_policy.assertions.get(assertion_id)
        if assertion is None or evidence.assertion_id != assertion_id:
            raise ProductionAdapterError("oracle assertion binding drift")
        candidates: tuple[object, ...]
        if assertion.oracle.kind == "classifier_result":
            candidates = tuple(
                item
                for item in evidence.classifier_results
                if item.assertion_id == assertion_id
                and item.policy_digest == self.registry.compiled_policy.policy_digest
                and item.evaluator_digest
                == self.registry.classifier_evaluator_digest(assertion_id)
                and item.classifier_id == assertion.oracle.classifier_id
                and item.producer in assertion.oracle.allowed_producers
            )
        else:
            candidates = tuple(
                item
                for item in (
                    *evidence.structured_events,
                    *evidence.tool_results,
                    *evidence.readbacks,
                )
                if item.assertion_id == assertion_id
                and item.producer in assertion.oracle.allowed_producers
            )
        verified = tuple(self._artifact(item) for item in candidates)
        if not verified:
            raise ProductionAdapterError(
                "required protected decisive evidence is missing"
            )
        return OracleDecision(
            assertion_id=assertion_id,
            passed=all(bool(item.passed) for item in verified),
            decisive_evidence_kind=assertion.oracle.kind,
            reason="; ".join(str(item.reason) for item in verified),
        )


def _derive_produced_attempt(
    *,
    record: _ProducerHandleRecord,
    attempted: execution.ExecutedAttemptV2 | execution.GateAttemptV2,
    validated: execution.ValidatedAttempt,
) -> ProducedAttempt:
    """Rebuild the public pair only from producer-validated transaction bytes."""

    transaction_id = f"{record.execution_id.lower()}-attempt-001"
    root = record.journal.run_root
    try:
        raw_payload = execution._read_protected(
            root, f"attempts/{transaction_id}/raw.json"
        )
        tracked_payload = execution._read_protected(
            root, f"attempts/{transaction_id}/tracked.json"
        )
        commit_payload = execution._read_protected(
            root, f"attempts/{transaction_id}/commit.json"
        )
        raw = json.loads(raw_payload)
        tracked = json.loads(tracked_payload)
        commit = json.loads(commit_payload)
    except (execution.ExecutionValidationError, json.JSONDecodeError) as exc:
        raise ProductionAdapterError(
            "committed producer recovery is incomplete"
        ) from exc
    if (
        not isinstance(raw, dict)
        or not isinstance(tracked, dict)
        or not isinstance(commit, dict)
    ):
        raise ProductionAdapterError("committed producer recovery is invalid")
    gate_attempt = attempted if isinstance(attempted, execution.GateAttemptV2) else None
    try:
        expected_raw = execution._validated_attempt_result_payload(
            validated,
            gate_attempt=gate_attempt,
        )
        expected_tracked = redact_payload(expected_raw)
        validate_redacted_payload(expected_tracked)
    except execution.ExecutionValidationError as exc:
        raise ProductionAdapterError(
            "committed producer recovery binding drift: producer validation"
        ) from exc
    raw_digest = hashlib.sha256(raw_payload).hexdigest()
    tracked_digest = hashlib.sha256(tracked_payload).hexdigest()
    commit_digest = hashlib.sha256(commit_payload).hexdigest()
    required = {
        "schema_version": "noor-e2e-attempt-commit/v2",
        "transaction_id": transaction_id,
        "status": "committed",
        "run_id": record.journal.run_id,
        "execution_id": record.execution_id,
        "attempt_kind": expected_raw["attempt_kind"],
        "attempt_digest": expected_raw["attempt_digest"],
        "authorization_digest": record.journal.authorization_digest,
        "semantic_digest": expected_raw["semantic_digest"],
        "gate_attempt_digest": expected_raw["gate_attempt_digest"],
        "evaluator_digest": expected_raw["evaluator_digest"],
        "evidence_digest": expected_raw["evidence_digest"],
        "raw_digest": raw_digest,
        "tracked_digest": tracked_digest,
    }
    if (
        raw != expected_raw
        or tracked != expected_tracked
        or tracked_payload != _canonical_bytes(expected_tracked)
        or any(commit.get(key) != value for key, value in required.items())
    ):
        raise ProductionAdapterError(
            "committed producer recovery binding drift: producer validation"
        )
    try:
        attempt_digest = str(raw["attempt_digest"])
        semantic_digest = str(raw["semantic_digest"])
        evaluator_digest = str(raw["evaluator_digest"])
        evidence_digest = str(raw["evidence_digest"])
        outcome = str(raw["outcome"])
        attempt_kind = str(raw["attempt_kind"])
    except KeyError as exc:
        raise ProductionAdapterError(
            "committed producer recovery schema is incomplete"
        ) from exc
    if outcome not in {
        "PASS",
        "FAIL",
        "BLOCKED",
        "EXCLUDED_BY_CLIENT",
    } or attempt_kind not in {"executed", "gate"}:
        raise ProductionAdapterError("committed producer recovery result is invalid")
    phases: list[dict[str, Any]] = []
    previous: str | None = None
    for cursor, phase in enumerate(execution._PHASES, start=1):
        identity = {
            "cursor": cursor,
            "phase": phase,
            "previous_event_digest": previous,
            "run_id": record.journal.run_id,
            "execution_id": record.execution_id,
            "attempt_digest": attempt_digest,
            "semantic_digest": semantic_digest,
            "authorization_digest": record.journal.authorization_digest,
            "protected_commit_digest": commit_digest,
        }
        previous = _digest(identity)
        phases.append(
            {
                "cursor": cursor,
                "phase": phase,
                "previous_event_digest": identity["previous_event_digest"],
                "event_digest": previous,
            }
        )
    artifact = {
        "schema_version": "noor-e2e-committed-execution/v2",
        "run_id": record.journal.run_id,
        "execution_id": record.execution_id,
        "outcome": outcome,
        "attempt_kind": attempt_kind,
        "gate_attempt": attempted.model_dump(mode="json")
        if attempt_kind == "gate"
        else None,
        "authorization_digest": record.journal.authorization_digest,
        "attempt_digest": attempt_digest,
        "semantic_digest": semantic_digest,
        "registry_id": record.registry.registry_id,
        "protected_commit_ref": f"attempts/{transaction_id}/commit.json",
        "protected_commit_digest": commit_digest,
        "raw_digest": raw_digest,
        "tracked_digest": tracked_digest,
        "phase_head_digest": previous,
        "phase_chain": phases,
        "evidence_refs": [
            f"attempt:{record.execution_id}",
            *[
                f"mode-{record.ordinal:02d}-{criterion.criterion_id}"
                for criterion in record.registry.compiled_plan.criteria.values()
                if record.execution_id in criterion.obligation_ids
            ],
        ],
    }
    receipt = {
        "schema_version": "noor-e2e-attempt-producer-receipt/v2",
        "registry_id": record.registry.registry_id,
        "run_id": record.journal.run_id,
        "execution_id": record.execution_id,
        "attempt_kind": attempt_kind,
        "attempt_digest": attempt_digest,
        "authorization_digest": record.journal.authorization_digest,
        "semantic_digest": semantic_digest,
        "evaluator_digest": evaluator_digest,
        "evidence_digest": evidence_digest,
        "raw_digest": raw_digest,
        "tracked_digest": tracked_digest,
        "phase_head_digest": previous,
        "tracked_sha256": _digest(artifact),
        "protected_commit_digest": commit_digest,
    }
    _write_or_validate_exact(
        root, f"produced-attempts/{record.ordinal:02d}.json", artifact
    )
    _write_or_validate_exact(
        root, f"producer-receipts/attempts/{record.execution_id}.json", receipt
    )
    return ProducedAttempt(artifact=artifact, receipt=receipt)


def produce_validated_execution_attempt(
    *,
    producer_handle: DecisiveProducerHandle,
    source_output_ref: str,
) -> ProducedAttempt:
    """Commit only the protected observation selected by an opaque handle."""

    record = _producer_handle_record(producer_handle)
    registry = record.registry
    journal = record.journal
    if source_output_ref != _observation_relative(record):
        raise ProductionAdapterError("protected producer source reference drift")
    source = _read_protected_json(journal.run_root, source_output_ref)
    receipt = _read_protected_json(
        journal.run_root, _observation_receipt_relative(record)
    )
    criterion_ids = tuple(
        criterion.criterion_id
        for criterion in registry.compiled_plan.criteria.values()
        if record.execution_id in criterion.obligation_ids
    )
    if (
        source.get("schema_version") != "noor-e2e-protected-source-observation/v1"
        or source.get("registry_id") != registry.registry_id
        or source.get("run_id") != journal.run_id
        or source.get("authorization_digest") != journal.authorization_digest
        or source.get("ordinal") != record.ordinal
        or source.get("execution_id") != record.execution_id
        or source.get("authorized_input_digest")
        != journal.authorization.execution_input_digests[record.execution_id]
        or tuple(source.get("criterion_ids", ())) != criterion_ids
        or receipt.get("schema_version")
        != "noor-e2e-protected-source-observation-receipt/v1"
        or receipt.get("registry_id") != registry.registry_id
        or receipt.get("run_id") != journal.run_id
        or receipt.get("authorization_digest") != journal.authorization_digest
        or receipt.get("ordinal") != record.ordinal
        or receipt.get("execution_id") != record.execution_id
        or receipt.get("authorized_input_digest")
        != journal.authorization.execution_input_digests[record.execution_id]
        or tuple(receipt.get("criterion_ids", ())) != criterion_ids
        or receipt.get("relative_path") != source_output_ref
        or receipt.get("source_attempt_digest") != source.get("source_attempt_digest")
        or receipt.get("tracked_sha256") != _digest(source)
    ):
        raise ProductionAdapterError("protected producer source receipt drift")
    raw_attempt = source.get("attempt")
    if not isinstance(raw_attempt, dict):
        raise ProductionAdapterError("protected producer source attempt is invalid")
    try:
        schema_version = raw_attempt.get("schema_version")
        attempted: execution.ExecutedAttemptV2 | execution.GateAttemptV2
        if schema_version == "noor-e2e-scenario-attempt/v2":
            attempted = execution.ScenarioAttemptV2.model_validate(raw_attempt)
        elif schema_version == "noor-e2e-evidence-block-attempt/v2":
            attempted = execution.EvidenceBlockAttemptV2.model_validate(raw_attempt)
        elif schema_version == "noor-e2e-gate-attempt/v2":
            attempted = execution.GateAttemptV2.model_validate(raw_attempt)
        else:
            raise ValueError("unknown source attempt schema")
    except ValueError as exc:
        raise ProductionAdapterError(
            "protected producer source attempt is invalid"
        ) from exc
    source_attempt_digest = _attempt_source_identity_digest(attempted)
    if (
        source_attempt_digest != source.get("source_attempt_digest")
        or attempted.execution_id != record.execution_id
    ):
        raise ProductionAdapterError("protected producer source attempt binding drift")
    resolver = ProtectedEvidenceResolver(
        registry=registry,
        journal=journal,
        execution_id=attempted.execution_id,
        source_attempt_digest=source_attempt_digest,
        sealed_plan=record.sealed_plan,
        source_output_ref=source_output_ref,
    )
    runner = execution.GenericAcceptanceRunner(
        registry=registry,
        authority=record.authority,
        journal=journal,
        oracle_evaluator=resolver.evaluate_oracle,
        readback_validator=resolver.validate_readback_window,
    )
    gate_attempt: execution.GateAttemptV2 | None = None
    if isinstance(attempted, execution.GateAttemptV2):
        gate_attempt = attempted
        validated = runner.validate_gate_as_attempt(attempted)
    elif isinstance(attempted, execution.ScenarioAttemptV2):
        validated = runner.validate_attempt(attempted)
    else:
        validated = runner.validate_evidence_block(attempted)
    existing_commit = _optional_protected_payload(
        journal.run_root,
        f"attempts/{record.execution_id.lower()}-attempt-001/commit.json",
    )
    if existing_commit is not None:
        return _derive_produced_attempt(
            record=record,
            attempted=attempted,
            validated=validated,
        )
    transaction = journal.begin_attempt(
        execution_id=validated.execution_id,
        attempt_number=1,
        intent_digest=validated.attempt_digest,
    )
    raw_digest, tracked_digest = transaction.write_validated(
        validated, gate_attempt=gate_attempt
    )
    recovery = transaction.commit()
    if recovery.status != "committed":
        raise ProductionAdapterError("validated producer did not commit attempt")
    return _derive_produced_attempt(
        record=record,
        attempted=attempted,
        validated=validated,
    )


def _derive_protected_publication_source(
    *,
    record: _ProducerHandleRecord,
    produced: ProducedAttempt,
    source_output_ref: str,
) -> dict[str, Any]:
    """Project publication facts from sealed observation and committed receipts only."""

    source = _read_protected_json(record.journal.run_root, source_output_ref)
    attempt = produced.artifact
    if (
        attempt.get("execution_id") != record.execution_id
        or attempt.get("registry_id") != record.registry.registry_id
        or attempt.get("authorization_digest") != record.journal.authorization_digest
        or source.get("execution_id") != record.execution_id
        or source.get("source_attempt_digest")
        != _attempt_source_identity_digest(
            execution.GateAttemptV2.model_validate(source["attempt"])
            if source.get("attempt", {}).get("schema_version")
            == "noor-e2e-gate-attempt/v2"
            else execution.ScenarioAttemptV2.model_validate(source["attempt"])
            if source.get("attempt", {}).get("schema_version")
            == "noor-e2e-scenario-attempt/v2"
            else execution.EvidenceBlockAttemptV2.model_validate(source["attempt"])
        )
    ):
        raise ProductionAdapterError("protected publication source binding drift")
    source_attempt = source.get("attempt", {})
    is_gate = source_attempt.get("schema_version") == "noor-e2e-gate-attempt/v2"
    kind = (
        "scenario"
        if record.execution_id in record.registry.compiled_policy.scenarios
        else "evidence_block"
    )
    attempt_ref = f"attempt:{record.execution_id}"
    status = {
        "PASS": "passed",
        "FAIL": "failed",
        "BLOCKED": "blocked",
        "EXCLUDED_BY_CLIENT": "excluded",
    }[str(attempt["outcome"])]
    evidence: list[dict[str, Any]] = [
        {
            "evidence_id": attempt_ref,
            "producer": "protected-attempt-committer",
            "payload": attempt,
        }
    ]
    evidence_refs = [attempt_ref]
    publication_facts = source.get("publication_facts")
    if not isinstance(publication_facts, list) or not publication_facts:
        raise ProductionAdapterError("protected publication facts are unavailable")
    for fact in publication_facts:
        if not isinstance(fact, dict):
            raise ProductionAdapterError("protected publication fact is invalid")
        criterion_id = fact.get("criterion_id")
        mode = fact.get("evidence_mode")
        if (
            not isinstance(criterion_id, str)
            or criterion_id not in record.registry.compiled_plan.criteria
            or record.execution_id
            not in record.registry.compiled_plan.criteria[criterion_id].obligation_ids
            or mode
            != record.registry.compiled_plan.criteria[criterion_id].evidence_mode.value
        ):
            raise ProductionAdapterError(
                "protected publication criterion binding drift"
            )
        evidence_id = f"mode-{record.ordinal:02d}-{criterion_id}"
        payload: dict[str, Any] = {
            "status": status,
            "criterion_id": criterion_id,
            "source_attempt_digest": source["source_attempt_digest"],
        }
        if mode == "fresh":
            payload["freshness_identity"] = {
                "run_id": record.journal.run_id,
                "execution_id": record.execution_id,
            }
        elif mode == "reused_exact":
            payload["reused_exact_identity"] = {
                "registry_id": record.registry.registry_id,
                "execution_id": record.execution_id,
            }
        elif mode == "external_gate":
            payload["external_gate_resolution"] = {
                "PASS": "implemented",
                "FAIL": "failed",
                "BLOCKED": "blocked",
                "EXCLUDED_BY_CLIENT": "excluded_by_client",
            }[str(attempt["outcome"])]
        else:
            raise ProductionAdapterError(
                "protected publication evidence mode is invalid"
            )
        evidence.append(
            {
                "evidence_id": evidence_id,
                "producer": "protected-publication-projector",
                "payload": payload,
            }
        )
        evidence_refs.append(evidence_id)
    result: dict[str, Any] = {
        "schema_version": (
            "noor-e2e-scenario-publication-source/v1"
            if kind == "scenario"
            else "noor-e2e-evidence-block-publication-source/v1"
        ),
        "kind": kind,
        "execution": {"attempt_ref": attempt_ref, "evidence_refs": evidence_refs},
        "evidence": evidence,
    }
    if kind == "scenario":
        facts = source.get("transcript_facts")
        if not isinstance(facts, list) or (not facts and not is_gate):
            raise ProductionAdapterError(
                "protected scenario transcript facts are unavailable"
            )
        turns: list[dict[str, Any]] = []
        for raw_fact in facts:
            if not isinstance(raw_fact, dict) or not isinstance(
                raw_fact.get("turn_id"), str
            ):
                raise ProductionAdapterError(
                    "protected scenario transcript fact is invalid"
                )
            attempt_id = f"attempt:{record.execution_id}"
            turn_id = raw_fact["turn_id"]
            transcript = {
                "schema_version": "noor-e2e-protected-transcript/v2",
                "registry_id": record.registry.registry_id,
                "run_id": record.journal.run_id,
                "execution_id": record.execution_id,
                "attempt_id": attempt_id,
                "turn_id": turn_id,
                "turn": {
                    **raw_fact,
                    "execution_id": record.execution_id,
                    "attempt_id": attempt_id,
                    "evidence_refs": evidence_refs,
                },
            }
            transcript_digest = _write_or_validate_exact(
                record.journal.run_root,
                f"transcripts/{record.execution_id}/{attempt_id}/{turn_id}.json",
                transcript,
            )
            receipt_digest = _write_or_validate_exact(
                record.journal.run_root,
                f"producer-receipts/transcripts/{record.execution_id}/{attempt_id}/{turn_id}.json",
                {
                    "schema_version": "noor-e2e-transcript-producer-receipt/v2",
                    "registry_id": record.registry.registry_id,
                    "run_id": record.journal.run_id,
                    "execution_id": record.execution_id,
                    "attempt_id": attempt_id,
                    "turn_id": turn_id,
                    "transcript_sha256": transcript_digest,
                    "authorization_digest": record.journal.authorization_digest,
                    "attempt_digest": attempt["attempt_digest"],
                    "attempt_phase_head_digest": attempt["phase_head_digest"],
                },
            )
            turns.append(
                {
                    **raw_fact,
                    "execution_id": record.execution_id,
                    "attempt_id": attempt_id,
                    "transcript_digest": transcript_digest,
                    "producer_receipt_digest": receipt_digest,
                    "evidence_refs": evidence_refs,
                }
            )
        result["turns"] = turns
        dispositions = source.get("side_effect_dispositions")
        if not isinstance(dispositions, list):
            raise ProductionAdapterError(
                "protected side-effect dispositions are unavailable"
            )
        result["side_effect_dispositions"] = dispositions
    return result


def _produce_publication_unit(
    *, producer_handle: DecisiveProducerHandle, source_output_ref: str
) -> _ProducedPublication:
    """The coordinator's internal bridge from opaque producer to typed source."""

    record = _producer_handle_record(producer_handle)
    produced = produce_validated_execution_attempt(
        producer_handle=producer_handle, source_output_ref=source_output_ref
    )
    return _ProducedPublication(
        artifact=produced.artifact,
        receipt=produced.receipt,
        source=_derive_protected_publication_source(
            record=record, produced=produced, source_output_ref=source_output_ref
        ),
        observed_at=datetime.now(UTC),
    )


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


def _validate_evaluator_bindings(
    journal: execution.ProtectedExecutionJournal, plan: ProtectedRunPlan
) -> None:
    """Require each sealed producer to map to an authorized local source."""

    config = ProtectedEvaluatorConfig.model_validate(plan.evaluator)
    for producer in config.decisive_producers:
        _validate_decisive_binding(
            binding=producer,
            journal=journal,
            # Registry-specific classifier evidence is validated when the
            # protected artifact is materialized; sealing only sees authority.
            registry=None,
        )


def seal_run_plan(
    journal: execution.ProtectedExecutionJournal, plan: ProtectedRunPlan
) -> str:
    """Anchor the exact plan/evaluator/action identities before preflight."""

    if journal.phase != "prepared":
        raise ProductionAdapterError("run plan can only be sealed before preflight")
    _validate_plan_actions(journal, plan)
    _validate_evaluator_bindings(journal, plan)
    sealed_payload = {
        "schema_version": "noor-e2e-sealed-run-plan/v2",
        "plan_digest": plan.plan_digest,
        "evaluator_digest": plan.evaluator_digest,
        "actions": list(plan.actions),
        "evaluator": plan.evaluator,
    }
    if plan.runtime is not None:
        sealed_payload["runtime"] = plan.runtime
    digest = _write_or_validate_exact(
        journal.run_root,
        "run-plan/sealed.json",
        sealed_payload,
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
    _validate_evaluator_bindings(journal, sealed)
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
        source = (
            collector.source_names.get(phase, collector.source_name)
            if collector.source_names is not None
            else collector.source_name
        )
        raw = collector.transport.read(source)
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
    source_names: Mapping[str, str] | None = None

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
    "LocalFakeAttemptProducer",
    "ProductionAdapterError",
    "ProtectedRunPlan",
    "ProtectedEvaluatorConfig",
    "DecisiveProducerBinding",
    "ProtectedEvidenceResolver",
    "DecisiveProducerHandle",
    "ProducedAttempt",
    "issue_decisive_producer_handle",
    "produce_validated_execution_attempt",
    "WazzupWebhookAdapter",
    "load_protected_baseline",
    "seal_fixed_final_readback",
    "load_sealed_run_plan",
    "seal_run_plan",
    "write_protected_message",
]
