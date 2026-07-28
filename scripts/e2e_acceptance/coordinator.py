"""Protected, ordered acceptance of independently produced execution records.

This core deliberately has no CLI or journal implementation dependency.  A
future adapter supplies the narrow ``JournalAcceptancePort``; the coordinator
itself owns the canonical order, protected paths, validation and fold chain.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.policy import TrustedAcceptanceRegistry

_FRESHNESS = timedelta(minutes=15)
_ARTIFACT_DIR = "producer-artifacts"
_RECEIPT_DIR = "producer-receipts/coordinator"
_ACCEPTED_DIR = "coordinator/accepted"


class CoordinatorError(ValueError):
    """A production coordinator input or durable recovery state is unsafe."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _is_digest(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _read_json(root: Path, relative: str) -> tuple[dict[str, Any], bytes]:
    try:
        payload = execution._read_protected(root, relative)
        value = json.loads(payload)
    except (execution.ExecutionValidationError, json.JSONDecodeError) as exc:
        raise CoordinatorError(
            f"protected coordinator input is invalid: {relative}"
        ) from exc
    if not isinstance(value, dict):
        raise CoordinatorError(
            f"protected coordinator input is not an object: {relative}"
        )
    return value, payload


def _optional_json(root: Path, relative: str) -> tuple[dict[str, Any], bytes] | None:
    try:
        return _read_json(root, relative)
    except CoordinatorError as exc:
        if isinstance(exc.__cause__, execution.ExecutionValidationError) and isinstance(
            exc.__cause__.__cause__, FileNotFoundError
        ):
            return None
        raise


def _write_or_validate_exact(root: Path, relative: str, value: object) -> str:
    expected = _digest(value)
    try:
        return execution._write_exclusive(root, relative, value)
    except execution.ExecutionValidationError as exc:
        try:
            actual = _sha256(execution._read_protected(root, relative))
        except execution.ExecutionValidationError as read_error:
            raise CoordinatorError(
                "coordinator protected replay is unreadable"
            ) from read_error
        if actual != expected:
            raise CoordinatorError(
                "coordinator protected replay differs from committed"
            ) from exc
        return actual


class ProducerArtifact(_StrictModel):
    """The independently produced input for exactly one canonical execution."""

    schema_version: Literal["noor-e2e-coordinator-producer-artifact/v1"]
    status: Literal["committed"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sealed_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ordinal: int = Field(ge=1, le=29)
    execution_id: str = Field(min_length=1)
    kind: Literal["scenario", "evidence_block"]
    outcome: execution.OutcomeValue
    producer: str = Field(min_length=1)
    observed_at: datetime
    source: dict[str, Any]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _source_is_bound(self) -> ProducerArtifact:
        if (
            self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
            or self.source_sha256 != _digest(self.source)
        ):
            raise ValueError("producer artifact source/freshness binding drift")
        return self


class ProducerReceipt(_StrictModel):
    schema_version: Literal["noor-e2e-coordinator-producer-receipt/v1"]
    status: Literal["committed"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ordinal: int = Field(ge=1, le=29)
    execution_id: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _fresh_window(self) -> ProducerReceipt:
        if (
            self.issued_at.tzinfo is None
            or self.issued_at.utcoffset() is None
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("producer receipt window is invalid")
        return self


class JournalAcceptanceEvent(_StrictModel):
    schema_version: Literal["noor-e2e-coordinator-journal-acceptance/v1"]
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ordinal: int = Field(ge=1, le=29)
    execution_id: str = Field(min_length=1)
    accepted_payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    prior_fold_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _self_hash(self) -> JournalAcceptanceEvent:
        if self.event_digest != _digest(
            self.model_dump(mode="json", exclude={"event_digest"})
        ):
            raise ValueError("journal acceptance event digest drift")
        return self


class AcceptedExecutionRecord(_StrictModel):
    schema_version: Literal["noor-e2e-coordinator-accepted-record/v1"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sealed_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ordinal: int = Field(ge=1, le=29)
    artifact: ProducerArtifact
    receipt: ProducerReceipt
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_at: datetime
    prior_fold_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    fold_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    journal_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class FinalActivityProducerReceipt(_StrictModel):
    schema_version: Literal["noor-e2e-final-activity-producer-receipt/v1"]
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sealed_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_fold_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_record_digests: tuple[str, ...] = Field(min_length=29, max_length=29)
    issued_at: datetime
    receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _self_hash(self) -> FinalActivityProducerReceipt:
        if self.receipt_digest != _digest(
            self.model_dump(mode="json", exclude={"receipt_digest"})
        ):
            raise ValueError("final activity receipt digest drift")
        return self


class EvaluationRow(_StrictModel):
    criterion_id: str
    outcome: execution.OutcomeValue


class EvaluationBundle(_StrictModel):
    schema_version: Literal["noor-e2e-coordinator-evaluation-bundle/v1"]
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_fold_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisive_source_shas: tuple[str, ...] = Field(min_length=29, max_length=29)
    criteria: tuple[EvaluationRow, ...] = Field(min_length=1)
    bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _self_hash(self) -> EvaluationBundle:
        if self.bundle_digest != _digest(
            self.model_dump(mode="json", exclude={"bundle_digest"})
        ):
            raise ValueError("evaluation bundle digest drift")
        return self


class EvaluationReceipt(_StrictModel):
    schema_version: Literal["noor-e2e-coordinator-evaluation-receipt/v1"]
    run_id: str = Field(min_length=1)
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_activity_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _self_hash(self) -> EvaluationReceipt:
        if self.receipt_digest != _digest(
            self.model_dump(mode="json", exclude={"receipt_digest"})
        ):
            raise ValueError("evaluation receipt digest drift")
        return self


class JournalAcceptancePort(Protocol):
    """Future journal adapter; production core passes only derived event identity."""

    def record_acceptance(self, event: JournalAcceptanceEvent) -> str:
        """Persist this exact event idempotently and return its digest."""

    def read_acceptance(self, ordinal: int) -> JournalAcceptanceEvent | None:
        """Read the durable journal event bound to this accepted ordinal."""


@dataclass(frozen=True)
class ProtectedJournalAcceptancePort:
    """Append-only coordinator port backed by the protected execution journal."""

    journal: execution.ProtectedExecutionJournal

    def record_acceptance(self, event: JournalAcceptanceEvent) -> str:
        if (
            self.journal.phase != "executing"
            or event.run_id != self.journal.run_id
            or event.authorization_digest != self.journal.authorization_digest
            or event.ordinal > len(self.journal.authorization.execution_ids)
            or event.execution_id
            != self.journal.authorization.execution_ids[event.ordinal - 1]
        ):
            raise CoordinatorError("journal acceptance authority/order binding drift")
        existing = self.journal._coordinator_acceptance_events.get(event.ordinal)
        if existing is not None:
            if existing != event.model_dump(mode="json"):
                raise CoordinatorError(
                    "journal acceptance replay differs from committed"
                )
            return event.event_digest
        if event.ordinal != len(self.journal._coordinator_acceptance_events) + 1:
            raise CoordinatorError("journal acceptance is out of canonical order")
        self.journal._append_event(
            phase="executing",
            kind="coordinator_unit_accepted",
            data=event.model_dump(mode="json"),
        )
        self.journal._coordinator_acceptance_events[event.ordinal] = event.model_dump(
            mode="json"
        )
        return event.event_digest

    def read_acceptance(self, ordinal: int) -> JournalAcceptanceEvent | None:
        payload = self.journal._coordinator_acceptance_events.get(ordinal)
        if payload is None:
            return None
        try:
            return JournalAcceptanceEvent.model_validate(payload)
        except ValueError as exc:
            raise CoordinatorError(
                "journal acceptance replay payload is invalid"
            ) from exc


@dataclass(frozen=True)
class CoordinatorResult:
    final_activity: FinalActivityProducerReceipt
    evaluation: EvaluationBundle
    receipt: EvaluationReceipt


@dataclass(frozen=True)
class DecisiveEvidenceResolver:
    """Digest-addressable, current-run evidence only."""

    _sources: dict[str, dict[str, Any]]
    digests: tuple[str, ...]

    def resolve(self, source_sha256: str) -> dict[str, Any]:
        try:
            return dict(self._sources[source_sha256])
        except KeyError as exc:
            raise CoordinatorError(
                "decisive evidence digest is not accepted for this run"
            ) from exc


class ProductionRunCoordinator:
    """Accept the canonical 20+9 executions from fixed protected producer paths."""

    def __init__(
        self,
        *,
        registry: TrustedAcceptanceRegistry,
        authorization: execution.ExecutionAuthorizationV2,
        protected_root: Path,
        run_id: str,
        journal: JournalAcceptancePort,
        current_time: datetime | None = None,
    ) -> None:
        if not isinstance(registry, TrustedAcceptanceRegistry):
            raise CoordinatorError("trusted registry is required")
        self.registry = registry
        self.authorization = execution.validate_execution_authorization(
            authorization,
            policy=registry.compiled_policy,
            plan=registry.compiled_plan,
            registry_id=registry.registry_id,
            current_time=current_time,
        )
        self.authorization_digest = execution.authorization_digest(self.authorization)
        self.protected_root = protected_root.resolve(strict=True)
        self.run_id = run_id
        self.run_root = self.protected_root / run_id
        self.journal = journal
        self.current_time = current_time or datetime.now(UTC)
        if (
            self.current_time.tzinfo is None
            or self.current_time.utcoffset() is None
            or self.authorization.execution_ids != registry.compiled_plan.execution_ids
        ):
            raise CoordinatorError("coordinator authority/order binding drift")
        sealed, sealed_payload = _read_json(self.run_root, "run-plan/sealed.json")
        if (
            set(sealed)
            != {
                "schema_version",
                "plan_digest",
                "evaluator_digest",
                "actions",
                "evaluator",
            }
            or sealed.get("schema_version") != "noor-e2e-sealed-run-plan/v2"
            or not isinstance(sealed.get("actions"), list)
            or not isinstance(sealed.get("evaluator"), dict)
            or sealed.get("plan_digest")
            != _digest({"actions": sealed["actions"], "evaluator": sealed["evaluator"]})
            or sealed.get("evaluator_digest") != _digest(sealed["evaluator"])
        ):
            raise CoordinatorError("sealed plan binding drift")
        self.sealed_plan_sha256 = _sha256(sealed_payload)
        self._initial_fold_digest = _digest(
            {
                "registry_id": registry.registry_id,
                "run_id": run_id,
                "authorization_digest": self.authorization_digest,
                "compiled_plan_digest": registry.compiled_plan.plan_digest,
                "sealed_plan_sha256": self.sealed_plan_sha256,
            }
        )

    @staticmethod
    def producer_artifact_path(ordinal: int) -> str:
        return f"{_ARTIFACT_DIR}/{ordinal:02d}.json"

    @staticmethod
    def producer_receipt_path(ordinal: int) -> str:
        return f"{_RECEIPT_DIR}/{ordinal:02d}.json"

    @staticmethod
    def accepted_record_path(ordinal: int) -> str:
        return f"{_ACCEPTED_DIR}/{ordinal:02d}.json"

    def _expected_kind(
        self, execution_id: str
    ) -> Literal["scenario", "evidence_block"]:
        if execution_id in self.registry.compiled_policy.scenarios:
            return "scenario"
        if execution_id in self.registry.compiled_policy.evidence_blocks:
            return "evidence_block"
        raise CoordinatorError("canonical execution kind is unknown")

    def _validate_path_set(self, directory: str, expected: set[str]) -> None:
        """Enumerate one fixed protected directory through no-follow descriptors."""

        try:
            fd = execution._open_absolute_chain(self.run_root / directory, create=False)
        except execution.ExecutionValidationError as exc:
            if isinstance(exc.__cause__, FileNotFoundError):
                return
            raise CoordinatorError("coordinator protected directory is unsafe") from exc
        try:
            actual: set[str] = set()
            for name in os.listdir(fd):
                try:
                    item = os.stat(name, dir_fd=fd, follow_symlinks=False)
                except OSError as exc:
                    raise CoordinatorError(
                        "coordinator protected directory entry is unsafe"
                    ) from exc
                if not stat.S_ISREG(item.st_mode) or not name.endswith(".json"):
                    raise CoordinatorError(
                        "coordinator producer/record path-set is unsafe"
                    )
                actual.add(f"{directory}/{name}")
        finally:
            os.close(fd)
        if actual - expected:
            raise CoordinatorError(
                "coordinator producer/record path-set has extra entries"
            )

    def _validate_producer(
        self, ordinal: int
    ) -> tuple[ProducerArtifact, ProducerReceipt, str, str]:
        expected_execution = self.registry.compiled_plan.execution_ids[ordinal - 1]
        artifact_value, artifact_payload = _read_json(
            self.run_root, self.producer_artifact_path(ordinal)
        )
        receipt_value, receipt_payload = _read_json(
            self.run_root, self.producer_receipt_path(ordinal)
        )
        try:
            artifact = ProducerArtifact.model_validate(artifact_value)
            receipt = ProducerReceipt.model_validate(receipt_value)
        except ValueError as exc:
            raise CoordinatorError(
                "producer artifact/receipt contract is invalid"
            ) from exc
        if (
            artifact.registry_id != self.registry.registry_id
            or artifact.run_id != self.run_id
            or artifact.authorization_digest != self.authorization_digest
            or artifact.sealed_plan_sha256 != self.sealed_plan_sha256
            or artifact.ordinal != ordinal
            or artifact.execution_id != expected_execution
            or artifact.kind != self._expected_kind(expected_execution)
            or receipt.registry_id != artifact.registry_id
            or receipt.run_id != artifact.run_id
            or receipt.authorization_digest != artifact.authorization_digest
            or receipt.ordinal != ordinal
            or receipt.execution_id != expected_execution
            or receipt.producer != artifact.producer
            or receipt.artifact_sha256 != _sha256(artifact_payload)
            or receipt.source_sha256 != artifact.source_sha256
            or artifact.observed_at > self.current_time
            or self.current_time - artifact.observed_at > _FRESHNESS
            or not artifact.observed_at <= receipt.issued_at < receipt.expires_at
            or not receipt.issued_at <= self.current_time < receipt.expires_at
        ):
            raise CoordinatorError(
                "producer artifact/receipt binding or freshness drift"
            )
        return artifact, receipt, _sha256(artifact_payload), _sha256(receipt_payload)

    def _read_accepted_records(self) -> list[tuple[AcceptedExecutionRecord, str]]:
        expected_paths = {self.accepted_record_path(index) for index in range(1, 30)}
        self._validate_path_set(_ACCEPTED_DIR, expected_paths)
        records: list[tuple[AcceptedExecutionRecord, str]] = []
        previous = self._initial_fold_digest
        for ordinal, execution_id in enumerate(
            self.registry.compiled_plan.execution_ids, start=1
        ):
            loaded = _optional_json(self.run_root, self.accepted_record_path(ordinal))
            if loaded is None:
                break
            value, payload = loaded
            try:
                record = AcceptedExecutionRecord.model_validate(value)
            except ValueError as exc:
                raise CoordinatorError("accepted record is invalid") from exc
            expected_fold = _digest(
                {
                    "prior_fold_digest": previous,
                    "artifact_sha256": record.artifact_sha256,
                    "receipt_sha256": record.receipt_sha256,
                    "ordinal": ordinal,
                    "execution_id": execution_id,
                }
            )
            event_identity = {
                "schema_version": "noor-e2e-coordinator-journal-acceptance/v1",
                "run_id": self.run_id,
                "authorization_digest": self.authorization_digest,
                "ordinal": ordinal,
                "execution_id": execution_id,
                "accepted_payload_digest": _digest(
                    record.model_dump(mode="json", exclude={"journal_event_digest"})
                ),
                "prior_fold_digest": previous,
            }
            expected_event = _digest(event_identity)
            if (
                record.registry_id != self.registry.registry_id
                or record.run_id != self.run_id
                or record.authorization_digest != self.authorization_digest
                or record.sealed_plan_sha256 != self.sealed_plan_sha256
                or record.ordinal != ordinal
                or record.artifact.execution_id != execution_id
                or record.artifact.ordinal != ordinal
                or record.artifact.kind != self._expected_kind(execution_id)
                or record.artifact.sealed_plan_sha256 != self.sealed_plan_sha256
                or record.receipt.ordinal != ordinal
                or record.receipt.execution_id != execution_id
                or record.receipt.producer != record.artifact.producer
                or record.receipt.source_sha256 != record.artifact.source_sha256
                or record.artifact_sha256
                != _digest(record.artifact.model_dump(mode="json"))
                or record.receipt_sha256
                != _digest(record.receipt.model_dump(mode="json"))
                or record.receipt.artifact_sha256 != record.artifact_sha256
                or record.accepted_at.tzinfo is None
                or record.accepted_at.utcoffset() is None
                or record.artifact.observed_at > record.accepted_at
                or record.accepted_at - record.artifact.observed_at > _FRESHNESS
                or not record.artifact.observed_at
                <= record.receipt.issued_at
                < record.receipt.expires_at
                or not record.receipt.issued_at
                <= record.accepted_at
                < record.receipt.expires_at
                or record.prior_fold_digest != previous
                or record.fold_digest != expected_fold
                or record.journal_event_digest != expected_event
                or _sha256(payload) != _digest(record.model_dump(mode="json"))
            ):
                raise CoordinatorError("accepted record fold/journal binding drift")
            journal_event = JournalAcceptanceEvent(
                **event_identity,
                event_digest=expected_event,
            )
            if self.journal.read_acceptance(ordinal) != journal_event:
                raise CoordinatorError(
                    "accepted record journal event is not durably bound"
                )
            records.append((record, _sha256(payload)))
            previous = record.fold_digest
        for ordinal in range(len(records) + 1, 30):
            if (
                _optional_json(self.run_root, self.accepted_record_path(ordinal))
                is not None
            ):
                raise CoordinatorError(
                    "accepted records are missing, duplicate, or out of order"
                )
        return records

    def accept_next(self) -> AcceptedExecutionRecord:
        """Accept the only next ordinal from its fixed producer paths."""

        records = self._read_accepted_records()
        ordinal = len(records) + 1
        if ordinal > 29:
            raise CoordinatorError("all canonical executions are already accepted")
        expected_sources = {
            self.producer_artifact_path(index) for index in range(1, 30)
        }
        expected_receipts = {
            self.producer_receipt_path(index) for index in range(1, 30)
        }
        self._validate_path_set(_ARTIFACT_DIR, expected_sources)
        self._validate_path_set(_RECEIPT_DIR, expected_receipts)
        artifact, receipt, artifact_sha, receipt_sha = self._validate_producer(ordinal)
        previous = records[-1][0].fold_digest if records else self._initial_fold_digest
        fold = _digest(
            {
                "prior_fold_digest": previous,
                "artifact_sha256": artifact_sha,
                "receipt_sha256": receipt_sha,
                "ordinal": ordinal,
                "execution_id": artifact.execution_id,
            }
        )
        record_identity = {
            "schema_version": "noor-e2e-coordinator-accepted-record/v1",
            "registry_id": self.registry.registry_id,
            "run_id": self.run_id,
            "authorization_digest": self.authorization_digest,
            "sealed_plan_sha256": self.sealed_plan_sha256,
            "ordinal": ordinal,
            "artifact": artifact.model_dump(mode="json"),
            "receipt": receipt.model_dump(mode="json"),
            "artifact_sha256": artifact_sha,
            "receipt_sha256": receipt_sha,
            "accepted_at": _timestamp(self.current_time),
            "prior_fold_digest": previous,
            "fold_digest": fold,
        }
        event_identity = {
            "schema_version": "noor-e2e-coordinator-journal-acceptance/v1",
            "run_id": self.run_id,
            "authorization_digest": self.authorization_digest,
            "ordinal": ordinal,
            "execution_id": artifact.execution_id,
            "accepted_payload_digest": _digest(record_identity),
            "prior_fold_digest": previous,
        }
        event = JournalAcceptanceEvent(
            **event_identity, event_digest=_digest(event_identity)
        )
        if self.journal.record_acceptance(event) != event.event_digest:
            raise CoordinatorError("journal acceptance event binding drift")
        record = AcceptedExecutionRecord(
            **record_identity, journal_event_digest=event.event_digest
        )
        _write_or_validate_exact(
            self.run_root,
            self.accepted_record_path(ordinal),
            record.model_dump(mode="json"),
        )
        return record

    def accept_available(self) -> tuple[AcceptedExecutionRecord, ...]:
        """Accept contiguous fixed producer pairs; missing next input remains unaccepted."""

        while len(self._read_accepted_records()) < 29:
            ordinal = len(self._read_accepted_records()) + 1
            if (
                _optional_json(self.run_root, self.producer_artifact_path(ordinal))
                is None
            ):
                break
            self.accept_next()
        return tuple(record for record, _ in self._read_accepted_records())

    def decisive_evidence(self) -> DecisiveEvidenceResolver:
        """Resolve only this run's accepted protected records, never registry context."""

        records = self._read_accepted_records()
        if len(records) != 29:
            raise CoordinatorError(
                "decisive evidence requires all canonical accepted records"
            )
        digests = tuple(record.artifact.source_sha256 for record, _ in records)
        if len(set(digests)) != len(digests):
            raise CoordinatorError("decisive evidence source digest is duplicate")
        return DecisiveEvidenceResolver(
            _sources={
                record.artifact.source_sha256: record.artifact.source
                for record, _ in records
            },
            digests=digests,
        )

    def finalize(self) -> CoordinatorResult:
        records = self._read_accepted_records()
        if len(records) != 29:
            raise CoordinatorError("evaluation requires exactly 29 accepted records")
        decisive = self.decisive_evidence()
        fold = records[-1][0].fold_digest
        record_digests = tuple(digest for _, digest in records)
        final_identity = {
            "schema_version": "noor-e2e-final-activity-producer-receipt/v1",
            "run_id": self.run_id,
            "authorization_digest": self.authorization_digest,
            "sealed_plan_sha256": self.sealed_plan_sha256,
            "accepted_fold_digest": fold,
            "accepted_record_digests": record_digests,
            "issued_at": _timestamp(records[-1][0].accepted_at),
        }
        final = FinalActivityProducerReceipt(
            **final_identity, receipt_digest=_digest(final_identity)
        )
        outcomes = {
            record.artifact.execution_id: record.artifact.outcome
            for record, _ in records
        }
        rows = tuple(
            EvaluationRow(
                criterion_id=criterion_id,
                outcome=execution.aggregate_criterion_outcome(
                    criterion,
                    {
                        identity: outcomes[identity]
                        for identity in criterion.obligation_ids
                    },
                    valid_exclusions=frozenset(),
                ),
            )
            for criterion_id, criterion in self.registry.compiled_plan.criteria.items()
        )
        bundle_identity = {
            "schema_version": "noor-e2e-coordinator-evaluation-bundle/v1",
            "run_id": self.run_id,
            "authorization_digest": self.authorization_digest,
            "accepted_fold_digest": fold,
            "decisive_source_shas": decisive.digests,
            "criteria": [item.model_dump(mode="json") for item in rows],
        }
        bundle = EvaluationBundle(
            **bundle_identity, bundle_digest=_digest(bundle_identity)
        )
        receipt_identity = {
            "schema_version": "noor-e2e-coordinator-evaluation-receipt/v1",
            "run_id": self.run_id,
            "authorization_digest": self.authorization_digest,
            "bundle_digest": bundle.bundle_digest,
            "final_activity_receipt_digest": final.receipt_digest,
        }
        receipt = EvaluationReceipt(
            **receipt_identity, receipt_digest=_digest(receipt_identity)
        )
        _write_or_validate_exact(
            self.run_root,
            "coordinator/final-activity-receipt.json",
            final.model_dump(mode="json"),
        )
        _write_or_validate_exact(
            self.run_root,
            "coordinator/evaluation-bundle.json",
            bundle.model_dump(mode="json"),
        )
        _write_or_validate_exact(
            self.run_root,
            "coordinator/evaluation-receipt.json",
            receipt.model_dump(mode="json"),
        )
        return CoordinatorResult(
            final_activity=final, evaluation=bundle, receipt=receipt
        )


__all__ = [
    "AcceptedExecutionRecord",
    "CoordinatorError",
    "CoordinatorResult",
    "DecisiveEvidenceResolver",
    "EvaluationBundle",
    "EvaluationReceipt",
    "FinalActivityProducerReceipt",
    "JournalAcceptanceEvent",
    "JournalAcceptancePort",
    "ProtectedJournalAcceptancePort",
    "ProducerArtifact",
    "ProducerReceipt",
    "ProductionRunCoordinator",
]
