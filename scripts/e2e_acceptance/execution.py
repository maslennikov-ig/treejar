"""Protected local execution state for the Noor acceptance trust center."""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from scripts.e2e_acceptance.evidence import (
    redact_payload,
    validate_redacted_payload,
)
from scripts.e2e_acceptance.schemas import EvidenceMode

if TYPE_CHECKING:
    from scripts.e2e_acceptance.policy import CompiledPolicy, ReadbackObservation

COMPILER_ID = "treejar.acceptance-policy-compiler.v2"
LOCAL_ADAPTER_IDS = ("fake-local-adapter",)
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


class ExecutionAuthorizationV2(_StrictModel):
    schema_version: Literal["noor-e2e-authorization/v2"]
    authorization_id: str = Field(min_length=1)
    status: Literal["approved"]
    issued_at: datetime
    expires_at: datetime
    task1_authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    compiler_id: str = Field(min_length=1)
    compiled_plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_ids: tuple[str, ...] = Field(min_length=1)
    adapter_ids: tuple[str, ...] = Field(min_length=1)
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
        return self


def validate_execution_authorization(
    authorization: object,
    *,
    policy: CompiledPolicy,
    plan: CompiledExecutionPlan,
    registry_id: str,
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
    if authorization.registry_id != registry_id:
        raise ExecutionValidationError("authorization registry drift")
    return authorization


class QuotaUsage(_StrictModel):
    messages: int = 0
    model_calls: int = 0
    cost_usd: float = 0
    subsystem_usage: dict[str, int] = Field(default_factory=dict)


ActionState = Literal["reserved", "succeeded", "failed", "unknown"]


class ActionReservation(_StrictModel):
    action_id: str
    adapter_id: str
    subsystem: str
    messages: int
    model_calls: int
    cost_usd: float
    reservation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AttemptRecovery(_StrictModel):
    transaction_id: str
    status: Literal["committed", "aborted"]
    raw_digest: str | None
    tracked_digest: str | None
    commit_digest: str


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

    def write_tracked(self, payload: object) -> str:
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

    def __init__(self, adapter_id: str) -> None:
        if adapter_id not in LOCAL_ADAPTER_IDS:
            raise ExecutionValidationError("only fake local adapter is available")
        self.adapter_id = adapter_id

    def execute(self, reservation: ActionReservation | None) -> dict[str, str]:
        if reservation is None or reservation.adapter_id != self.adapter_id:
            raise ExecutionValidationError(
                "adapter call requires a protected action reservation"
            )
        return {
            "status": "synthetic",
            "reservation_digest": reservation.reservation_digest,
        }


class ProtectedExecutionJournal:
    """Append-only phase/action journal under a protected external root."""

    def __init__(
        self,
        *,
        protected_root: Path,
        run_id: str,
        authorization: ExecutionAuthorizationV2,
    ) -> None:
        if not run_id or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-._"
            for character in run_id.lower()
        ):
            raise ExecutionValidationError("run identity is unsafe")
        self.protected_root = protected_root
        self.run_id = run_id
        self.run_root = protected_root / run_id
        self.authorization = authorization
        self.authorization_digest = _digest(authorization.model_dump(mode="json"))
        self.phase = "prepared"
        self.cursor = 0
        self.previous_event_digest: str | None = None
        self.quota_usage = QuotaUsage()
        self._actions: dict[str, ActionState] = {}
        self._reservations: dict[str, ActionReservation] = {}

    @classmethod
    def create(
        cls,
        *,
        protected_root: Path,
        run_id: str,
        authorization: ExecutionAuthorizationV2,
    ) -> ProtectedExecutionJournal:
        journal = cls(
            protected_root=protected_root,
            run_id=run_id,
            authorization=authorization,
        )
        fd = _open_absolute_chain(journal.run_root, create=True)
        os.fchmod(fd, 0o700)
        os.close(fd)
        journal._append_event(
            phase="prepared",
            kind="prepared",
            data={
                "authorization_digest": journal.authorization_digest,
                "anchor_store_id": authorization.store_ids.anchor_store_id,
            },
        )
        return journal

    @classmethod
    def open(
        cls,
        *,
        protected_root: Path,
        run_id: str,
        authorization: ExecutionAuthorizationV2,
    ) -> ProtectedExecutionJournal:
        journal = cls(
            protected_root=protected_root,
            run_id=run_id,
            authorization=authorization,
        )
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
            ):
                raise ExecutionValidationError("journal authorization binding drift")
            journal._apply_loaded_event(event)
            previous_digest = hashlib.sha256(payload).hexdigest()
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
            self._consume(reservation)
        elif kind == "action_completed":
            self._actions[str(data["action_id"])] = str(data["state"])  # type: ignore[assignment]

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
        self._transition(
            expected="baseline_sealed",
            target="executing",
            kind="execution_started",
            data={},
        )

    def _consume(self, reservation: ActionReservation) -> None:
        subsystems = dict(self.quota_usage.subsystem_usage)
        subsystems[reservation.subsystem] = subsystems.get(reservation.subsystem, 0) + 1
        self.quota_usage = QuotaUsage(
            messages=self.quota_usage.messages + reservation.messages,
            model_calls=self.quota_usage.model_calls + reservation.model_calls,
            cost_usd=self.quota_usage.cost_usd + reservation.cost_usd,
            subsystem_usage=subsystems,
        )

    def reserve_action(
        self,
        *,
        action_id: str,
        adapter_id: str,
        subsystem: str,
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
        if action_id in self._actions:
            raise ExecutionValidationError("action identity is already reserved")
        identity = {
            "action_id": action_id,
            "adapter_id": adapter_id,
            "subsystem": subsystem,
            "messages": messages,
            "model_calls": model_calls,
            "cost_usd": cost_usd,
            "authorization_digest": self.authorization_digest,
            "next_cursor": self.cursor + 1,
        }
        reservation = ActionReservation(
            action_id=action_id,
            adapter_id=adapter_id,
            subsystem=subsystem,
            messages=messages,
            model_calls=model_calls,
            cost_usd=cost_usd,
            reservation_digest=_digest(identity),
        )
        projected_messages = self.quota_usage.messages + messages
        projected_calls = self.quota_usage.model_calls + model_calls
        projected_cost = self.quota_usage.cost_usd + cost_usd
        projected_subsystem = self.quota_usage.subsystem_usage.get(subsystem, 0) + 1
        quotas = self.authorization.quotas
        if (
            projected_messages > quotas.max_messages
            or projected_calls > quotas.max_model_calls
            or projected_cost > quotas.max_cost_usd
            or projected_subsystem > quotas.subsystem_quotas.get(subsystem, 0)
        ):
            raise ExecutionValidationError("protected action reservation exceeds quota")
        self._append_event(
            phase="executing",
            kind="action_reserved",
            data={"reservation": reservation.model_dump(mode="json")},
        )
        self._reservations[action_id] = reservation
        self._actions[action_id] = "reserved"
        self._consume(reservation)
        return reservation

    def complete_action(
        self,
        reservation: ActionReservation,
        *,
        state: Literal["succeeded", "failed", "unknown"],
        outcome_digest: str,
    ) -> None:
        if self._actions.get(reservation.action_id) != "reserved":
            raise ExecutionValidationError("action completion lacks active reservation")
        if self._reservations.get(reservation.action_id) != reservation:
            raise ExecutionValidationError("action reservation identity drift")
        if len(outcome_digest) != 64:
            raise ExecutionValidationError("action outcome digest must be SHA-256")
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

    def anchor_final_turn(self, *, event_digest: str, occurred_at: datetime) -> None:
        if any(state in {"reserved", "unknown"} for state in self._actions.values()):
            raise ExecutionValidationError(
                "unknown or uncompleted action blocks final-turn closeout"
            )
        self._transition(
            expected="executing",
            target="final_turn_anchored",
            kind="final_turn_anchored",
            data={
                "event_digest": event_digest,
                "occurred_at": occurred_at.isoformat(),
            },
        )

    def begin_attempt(
        self,
        *,
        execution_id: str,
        attempt_number: int,
        intent_digest: str,
    ) -> AttemptTransaction:
        transaction_id = f"{execution_id.lower()}-attempt-{attempt_number:03d}"
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
        status: Literal["committed", "aborted"]
        if abort or raw_digest is None or tracked_digest is None:
            status = "aborted"
        else:
            status = "committed"
        record = {
            "schema_version": "noor-e2e-attempt-commit/v2",
            "transaction_id": transaction_id,
            "status": status,
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
