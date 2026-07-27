"""Load one anchored acceptance run and render its canonical client report."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from scripts.e2e_acceptance.evidence import (
    EvidenceError,
    validate_redacted_payload,
    validate_redacted_text,
)
from scripts.e2e_acceptance.execution import (
    ExecutionAuthorizationV2,
    OutcomeValue,
    aggregate_criterion_outcome,
    store_root_digest,
)
from scripts.e2e_acceptance.policy import (
    ClassifierResult,
    PolicyValidationError,
    ReadbackObservation,
    ReadbackResult,
    StructuredEvent,
    ToolResult,
)
from scripts.e2e_acceptance.schemas import EvidenceMode


class TrustedRunError(PolicyValidationError):
    """A tracked run and its protected anchor do not form one trusted result."""


_PROTECTED_STORE_ROOT = (
    Path.home()
    / ".local"
    / "state"
    / "treejar"
    / "noor-e2e-acceptance"
    / "protected-runs"
)


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


def canonical_digest(value: object) -> str:
    """Return the newline-terminated canonical JSON identity used by run anchors."""

    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None or os.open not in os.supports_dir_fd:
        raise TrustedRunError("secure descriptor-relative run loading is unavailable")
    return cast("int", os.O_RDONLY | nofollow | directory)


def _open_root(root: Path) -> int:
    if not root.is_absolute() or any(
        part in {"", ".", ".."} for part in root.parts[1:]
    ):
        raise TrustedRunError("trusted run root must be absolute and normalized")
    current_fd = os.open("/", _directory_flags())
    try:
        for part in root.parts[1:]:
            child_fd = os.open(part, _directory_flags(), dir_fd=current_fd)
            os.close(current_fd)
            current_fd = child_fd
    except OSError as exc:
        os.close(current_fd)
        raise TrustedRunError(
            f"trusted run root violates no-follow policy: {exc}"
        ) from exc
    return current_fd


def _read_file(root: Path, relative: str, *, protected: bool = False) -> bytes:
    path = Path(relative)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise TrustedRunError(f"unsafe trusted run path: {relative}")
    root_fd = _open_root(root)
    current_fd = root_fd
    try:
        for part in path.parts[:-1]:
            child_fd = os.open(part, _directory_flags(), dir_fd=current_fd)
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = child_fd
        file_fd = os.open(
            path.parts[-1],
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=current_fd,
        )
        try:
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise TrustedRunError(f"trusted run object is not regular: {relative}")
            if protected and stat.S_IMODE(metadata.st_mode) != 0o600:
                raise TrustedRunError(f"protected anchor mode must be 0600: {relative}")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(file_fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(file_fd)
    except OSError as exc:
        raise TrustedRunError(
            f"trusted run path violates no-follow policy: {exc}"
        ) from exc
    finally:
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)
    return b"".join(chunks)


def _parse_json(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustedRunError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise TrustedRunError(f"{label} root must be an object")
    return value


class EvidenceIndexEntry(_StrictModel):
    evidence_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer: str = Field(min_length=1)


class EvidenceIndex(_StrictModel):
    schema_version: Literal["noor-e2e-evidence-index/v2"]
    run_id: str = Field(min_length=1)
    entries: tuple[EvidenceIndexEntry, ...] = Field(min_length=1)


class ExecutionRow(_StrictModel):
    execution_id: str = Field(min_length=1)
    outcome: OutcomeValue
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    attempt_ref: str = Field(min_length=1)


AttemptPhaseName = Literal[
    "prepared",
    "baseline_sealed",
    "executing",
    "final_turn_anchored",
    "final_readback_sealed",
    "evaluated",
    "attempt_committed",
]


class AttemptPhase(_StrictModel):
    cursor: int = Field(ge=1, le=7)
    phase: AttemptPhaseName
    previous_event_digest: str | None
    event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CommittedExecutionArtifact(_StrictModel):
    schema_version: Literal["noor-e2e-committed-execution/v2"]
    run_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    outcome: OutcomeValue
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    protected_commit_ref: str = Field(min_length=1)
    protected_commit_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tracked_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase_chain: tuple[AttemptPhase, ...] = Field(min_length=7, max_length=7)
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class AttemptProducerReceipt(_StrictModel):
    schema_version: Literal["noor-e2e-attempt-producer-receipt/v2"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    attempt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tracked_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tracked_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    protected_commit_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CriterionRow(_StrictModel):
    criterion_id: str = Field(min_length=1)
    outcome: OutcomeValue
    evidence_mode: EvidenceMode
    obligation_outcomes: dict[str, OutcomeValue] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    reasoning: str = Field(min_length=1)


class TrustedRunDocument(_StrictModel):
    schema_version: Literal["noor-e2e-trusted-run/v2"]
    run_id: str = Field(min_length=1)
    authorization: ExecutionAuthorizationV2
    baseline: ReadbackObservation
    final: ReadbackObservation
    final_visible_at: tuple[datetime, ...]
    delivered_at: tuple[datetime, ...]
    action_at: tuple[datetime, ...]
    executions: tuple[ExecutionRow, ...] = Field(min_length=1)
    criteria: tuple[CriterionRow, ...] = Field(min_length=1)
    open_p0_p1: tuple[str, ...]
    side_effect_closeout: Literal["passed", "failed", "blocked"]
    evidence_index_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TrustedRunAnchor(_StrictModel):
    schema_version: Literal["noor-e2e-trusted-run-anchor/v2"]
    run_id: str = Field(min_length=1)
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    compiled_plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_index_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    criterion_ids: tuple[str, ...] = Field(min_length=1)
    execution_ids: tuple[str, ...] = Field(min_length=1)
    phase_journal_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_chain_heads: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def _attempt_heads_are_digests(self) -> TrustedRunAnchor:
        if any(
            len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in self.attempt_chain_heads.values()
        ):
            raise ValueError("attempt chain head digest is invalid")
        return self


class RuntimeIdentityReport(_StrictModel):
    repository_commit: str
    deployed_release_sha: str
    ci_run_id: str
    app_version: str
    migration_head: str
    models: tuple[str, ...]
    services: dict[str, str]
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class EvaluatorReport(_StrictModel):
    model: str
    reasoning_effort: str
    seed: int
    config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class TurnReport(_StrictModel):
    execution_id: str
    attempt_id: str
    turn_id: str
    question: str
    answer: str
    sent_at: datetime
    received_at: datetime
    first_visible_at: datetime
    final_visible_at: datetime
    delivered_at: datetime | None
    conversation_id: str
    message_id: str
    provider_message_id: str
    model: str
    tools: tuple[str, ...]
    tool_outcomes: tuple[str, ...]
    audit_ids: tuple[str, ...]
    media_refs: tuple[str, ...]
    token_count: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    deviation: str | None
    evaluator_reasoning: str
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class ReportExecution(_StrictModel):
    execution_id: str = Field(min_length=1)
    outcome: OutcomeValue
    attempt_ref: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class ReportCriterion(_StrictModel):
    criterion_id: str
    evidence_mode: EvidenceMode
    outcome: OutcomeValue
    evidence_refs: tuple[str, ...]
    reasoning: str


class SideEffectReport(_StrictModel):
    artifact_id: str
    subsystem: str
    artifact_type: str
    baseline: dict[str, Any]
    final: dict[str, Any]
    disposition: str
    owner: str
    checksum_refs: tuple[str, ...]


class LatencyReport(_StrictModel):
    p50_ms: int = Field(ge=0)
    p95_ms: int = Field(ge=0)
    max_ms: int = Field(ge=0)
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class DefectReport(_StrictModel):
    defect_id: str
    root_cause: str
    violated_invariant: str
    fix: str
    retest: str
    checksum_refs: tuple[str, ...]


class ReportSourceArtifact(_StrictModel):
    schema_version: Literal["noor-e2e-report-source/v2"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_sections_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verified_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReportProducerReceipt(_StrictModel):
    schema_version: Literal["noor-e2e-report-producer-receipt/v2"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    tracked_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_sections_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verified_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


DecisiveEvidenceKind = Literal[
    "classifier_result",
    "structured_event",
    "tool_result",
    "readback_result",
]


class MaterializedDecisiveEnvelope(_StrictModel):
    schema_version: Literal["noor-e2e-decisive-evidence-envelope/v2"]
    evidence_kind: DecisiveEvidenceKind
    artifact: dict[str, Any]


class DecisiveArtifactReceipt(_StrictModel):
    schema_version: Literal["noor-e2e-decisive-producer-receipt/v2"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    attempt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    assertion_id: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    tracked_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ClientReportPayload(_StrictModel):
    schema_version: Literal["noor-e2e-client-report/v2"]
    run_id: str
    title: str
    generated_at: datetime
    identity: RuntimeIdentityReport
    tester: EvaluatorReport
    judge: EvaluatorReport
    turns: tuple[TurnReport, ...]
    executions: tuple[ReportExecution, ...] = Field(min_length=1)
    criteria: tuple[ReportCriterion, ...] = Field(min_length=1)
    side_effects: tuple[SideEffectReport, ...]
    latency: LatencyReport
    limitations: tuple[str, ...]
    external_gates: tuple[str, ...]
    defects: tuple[DefectReport, ...]


class VerifiedRun(_StrictModel):
    rollups: dict[str, bool]
    report_bytes: bytes


class VerifiedExecutionSnapshot(_StrictModel):
    schema_version: Literal["noor-e2e-verified-execution-snapshot/v2"]
    run_id: str = Field(min_length=1)
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_ids: tuple[str, ...] = Field(min_length=29, max_length=29)
    tracked_files: dict[str, dict[str, Any]] = Field(min_length=32)
    protected_files: dict[str, dict[str, Any]] = Field(min_length=31)
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def _report_sections_digest(payload: ClientReportPayload) -> str:
    return canonical_digest(
        {
            "identity": payload.identity.model_dump(mode="json"),
            "tester": payload.tester.model_dump(mode="json"),
            "judge": payload.judge.model_dump(mode="json"),
            "turns": [item.model_dump(mode="json") for item in payload.turns],
            "executions": [item.model_dump(mode="json") for item in payload.executions],
            "side_effects": [
                item.model_dump(mode="json") for item in payload.side_effects
            ],
            "latency": payload.latency.model_dump(mode="json"),
            "defects": [item.model_dump(mode="json") for item in payload.defects],
        }
    )


def _verified_report_snapshot_digest(payload: ClientReportPayload) -> str:
    return canonical_digest(
        {
            "run_id": payload.run_id,
            "executions": [item.model_dump(mode="json") for item in payload.executions],
            "criteria": [item.model_dump(mode="json") for item in payload.criteria],
            "turn_evidence": {
                item.execution_id: list(item.evidence_refs) for item in payload.turns
            },
        }
    )


def _unique[T](items: tuple[T, ...], field: str, label: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for item in items:
        identity = str(getattr(item, field))
        if identity in result:
            raise TrustedRunError(f"duplicate {label}: {identity}")
        result[identity] = item
    return result


def _validate_evidence_mode(
    row: CriterionRow,
    evidence: dict[str, dict[str, Any]],
) -> bool:
    objects = [evidence[identity] for identity in row.evidence_refs]
    expected_status = {
        "PASS": "passed",
        "FAIL": "failed",
        "BLOCKED": "blocked",
        "EXCLUDED_BY_CLIENT": "excluded",
    }[row.outcome]
    if row.evidence_mode is EvidenceMode.FRESH:
        return all(
            item.get("status") == expected_status
            and isinstance(item.get("freshness_identity"), dict)
            and bool(item["freshness_identity"])
            for item in objects
        )
    if row.evidence_mode is EvidenceMode.REUSED_EXACT:
        return all(
            item.get("status") == expected_status
            and isinstance(item.get("reused_exact_identity"), dict)
            and bool(item["reused_exact_identity"])
            for item in objects
        )
    expected_resolution = {
        "PASS": "implemented",
        "FAIL": "failed",
        "BLOCKED": "blocked",
        "EXCLUDED_BY_CLIENT": "excluded_by_client",
    }[row.outcome]
    return all(
        item.get("status") == expected_status
        and item.get("external_gate_resolution") == expected_resolution
        for item in objects
    )


_ATTEMPT_PHASES: tuple[AttemptPhaseName, ...] = (
    "prepared",
    "baseline_sealed",
    "executing",
    "final_turn_anchored",
    "final_readback_sealed",
    "evaluated",
    "attempt_committed",
)


def _validate_attempt_phase_chain(artifact: CommittedExecutionArtifact) -> None:
    previous: str | None = None
    for cursor, (phase, event) in enumerate(
        zip(_ATTEMPT_PHASES, artifact.phase_chain, strict=True),
        start=1,
    ):
        identity = {
            "cursor": cursor,
            "phase": phase,
            "previous_event_digest": previous,
            "run_id": artifact.run_id,
            "execution_id": artifact.execution_id,
            "attempt_digest": artifact.attempt_digest,
            "semantic_digest": artifact.semantic_digest,
            "authorization_digest": artifact.authorization_digest,
            "protected_commit_digest": artifact.protected_commit_digest,
        }
        expected = canonical_digest(identity)
        if (
            event.cursor != cursor
            or event.phase != phase
            or event.previous_event_digest != previous
            or event.event_digest != expected
        ):
            raise TrustedRunError(f"attempt phase chain drift: {artifact.execution_id}")
        previous = expected
    if artifact.phase_head_digest != previous:
        raise TrustedRunError(
            f"attempt phase head binding drift: {artifact.execution_id}"
        )


def _validate_protected_attempt_commit(
    payload: bytes,
    *,
    artifact: CommittedExecutionArtifact,
    authorization_digest: str,
) -> None:
    value = _parse_json(payload, "protected attempt commit")
    if (
        value.get("schema_version") != "noor-e2e-attempt-commit/v2"
        or value.get("status") != "committed"
        or value.get("run_id") != artifact.run_id
        or value.get("execution_id") != artifact.execution_id
        or value.get("attempt_digest") != artifact.attempt_digest
        or value.get("authorization_digest") != authorization_digest
        or value.get("semantic_digest") != artifact.semantic_digest
        or value.get("raw_digest") != artifact.raw_digest
        or value.get("tracked_digest") != artifact.tracked_digest
    ):
        raise TrustedRunError(
            f"protected attempt commit binding drift: {artifact.execution_id}"
        )


def _load_decisive_evidence(
    registry: Any,
    run_id: str,
    *,
    artifact_digest: str,
) -> None:
    tracked_root = (
        registry._repo_root / ".codex" / "stages" / "tj-ee5f" / "results" / run_id
    )
    protected_root = _PROTECTED_STORE_ROOT / run_id
    relative = f"evidence/decisive/{artifact_digest}.json"
    tracked_payload = _read_file(tracked_root, relative)
    try:
        envelope = MaterializedDecisiveEnvelope.model_validate(
            _parse_json(tracked_payload, "structured evidence envelope")
        )
        artifact: ClassifierResult | StructuredEvent | ToolResult | ReadbackResult
        if envelope.evidence_kind == "classifier_result":
            artifact = ClassifierResult.model_validate(envelope.artifact)
        elif envelope.evidence_kind == "tool_result":
            artifact = ToolResult.model_validate(envelope.artifact)
        elif envelope.evidence_kind == "readback_result":
            artifact = ReadbackResult.model_validate(envelope.artifact)
        else:
            artifact = StructuredEvent.model_validate(envelope.artifact)
        receipt = DecisiveArtifactReceipt.model_validate(
            _parse_json(
                _read_file(
                    protected_root,
                    f"producer-receipts/decisive/{artifact_digest}.json",
                    protected=True,
                ),
                "protected structured producer receipt",
            )
        )
    except (TrustedRunError, ValueError) as exc:
        raise TrustedRunError(
            f"protected structured producer receipt invalid: {exc}"
        ) from exc
    if (
        artifact.artifact_digest != artifact_digest
        or artifact.run_id != run_id
        or receipt.evidence_id != f"decisive:{artifact_digest}"
        or receipt.relative_path != relative
        or receipt.tracked_sha256 != _sha256(tracked_payload)
        or receipt.registry_id != registry.registry_id
        or receipt.artifact_digest != artifact.artifact_digest
        or receipt.run_id != artifact.run_id
        or receipt.attempt_digest != artifact.attempt_digest
        or receipt.preflight_digest != artifact.preflight_digest
        or receipt.assertion_id != artifact.assertion_id
        or receipt.producer != artifact.producer
        or artifact.attempt_digest not in registry._trusted_attempt_digests
        or not any(
            artifact.preflight_digest == getattr(item, "preflight_digest", None)
            for item in registry._trusted_authorizations.values()
        )
    ):
        raise TrustedRunError("decisive evidence protected receipt drift")
    assertion = registry.compiled_policy.assertions.get(artifact.assertion_id)
    if assertion is None or artifact.producer not in assertion.oracle.allowed_producers:
        raise TrustedRunError("decisive evidence oracle producer drift")
    if isinstance(artifact, ClassifierResult):
        if (
            assertion.oracle.kind != "classifier_result"
            or artifact.policy_digest != registry.compiled_policy.policy_digest
            or artifact.evaluator_digest
            != registry.classifier_evaluator_digest(artifact.assertion_id)
            or artifact.classifier_id != assertion.oracle.classifier_id
        ):
            raise TrustedRunError("classifier protected receipt binding drift")
        registry._trusted_classifier_digests.add(artifact.artifact_digest)
    else:
        if assertion.oracle.kind == "classifier_result":
            raise TrustedRunError("structured decisive oracle kind drift")
        registry._trusted_structured_digests.add(artifact.artifact_digest)


def _render_report(payload: ClientReportPayload, rollups: dict[str, bool]) -> bytes:
    lines = [
        f"# {payload.title}",
        "",
        f"Идентификатор запуска: `{payload.run_id}`",
        f"Сформирован: {payload.generated_at.isoformat()}",
        "",
        "## Итог",
        "",
        f"- Полнота покрытия: {'да' if rollups['coverage_complete'] else 'нет'}",
        f"- Полнота исполнения: {'да' if rollups['execution_complete'] else 'нет'}",
        f"- Требования выполнены: {'да' if rollups['requirements_met'] else 'нет'}",
        "",
        "## Идентичность среды",
        "",
        f"- Commit: `{payload.identity.repository_commit}`",
        f"- Release: `{payload.identity.deployed_release_sha}`",
        f"- CI: `{payload.identity.ci_run_id}`",
        f"- Версия: `{payload.identity.app_version}`",
        f"- Миграция: `{payload.identity.migration_head}`",
        f"- Модели: {', '.join(payload.identity.models)}",
        f"- Сервисы: {json.dumps(payload.identity.services, ensure_ascii=False, sort_keys=True)}",
        "",
        "## Диалоги",
        "",
    ]
    for turn in payload.turns:
        lines.extend(
            [
                f"### {turn.execution_id} / {turn.attempt_id} / {turn.turn_id}",
                "",
                f"Вопрос: {turn.question}",
                "",
                f"Ответ: {turn.answer}",
                "",
                f"Время: sent={turn.sent_at.isoformat()}, received={turn.received_at.isoformat()}, "
                f"first_visible={turn.first_visible_at.isoformat()}, "
                f"final_visible={turn.final_visible_at.isoformat()}, "
                f"delivered={turn.delivered_at.isoformat() if turn.delivered_at else 'n/a'}",
                f"Идентификаторы: conversation={turn.conversation_id}, "
                f"message={turn.message_id}, provider={turn.provider_message_id}",
                f"Модель: {turn.model}; tools: {', '.join(turn.tools) or 'нет'}",
                f"Результаты tools: {', '.join(turn.tool_outcomes) or 'нет'}",
                f"Аудит: {', '.join(turn.audit_ids) or 'нет'}; media: "
                f"{', '.join(turn.media_refs) or 'нет'}",
                f"Токены: {turn.token_count}; стоимость USD: {turn.cost_usd}",
                f"Отклонение: {turn.deviation or 'нет'}",
                f"Оценка: {turn.evaluator_reasoning}",
                "",
            ]
        )
    lines.extend(["## Критерии", ""])
    for criterion_report in payload.criteria:
        lines.append(
            f"- {criterion_report.criterion_id}: {criterion_report.outcome} "
            f"({criterion_report.evidence_mode.value}); "
            f"evidence={', '.join(criterion_report.evidence_refs)}; "
            f"{criterion_report.reasoning}"
        )
    lines.extend(["", "## Побочные эффекты", ""])
    for side_effect in payload.side_effects:
        lines.append(
            f"- {side_effect.artifact_id} / {side_effect.subsystem} / "
            f"{side_effect.artifact_type}: {side_effect.disposition}; "
            f"owner={side_effect.owner}; "
            f"baseline={json.dumps(side_effect.baseline, ensure_ascii=False, sort_keys=True)}; "
            f"final={json.dumps(side_effect.final, ensure_ascii=False, sort_keys=True)}; "
            f"checksums={', '.join(side_effect.checksum_refs)}"
        )
    lines.extend(
        [
            "",
            "## Производительность",
            "",
            f"- p50: {payload.latency.p50_ms} ms",
            f"- p95: {payload.latency.p95_ms} ms",
            f"- max: {payload.latency.max_ms} ms",
            "",
            "## Ограничения и внешние условия",
            "",
            *(f"- {item}" for item in payload.limitations),
            *(f"- {item}" for item in payload.external_gates),
            "",
            "## Дефекты",
            "",
        ]
    )
    for defect in payload.defects:
        lines.extend(
            [
                f"### {defect.defect_id}",
                "",
                f"- Первопричина: {defect.root_cause}",
                f"- Нарушенный инвариант: {defect.violated_invariant}",
                f"- Исправление: {defect.fix}",
                f"- Ретест: {defect.retest}",
                f"- Checksums: {', '.join(defect.checksum_refs)}",
                "",
            ]
        )
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def _write_snapshot_tree(
    root: Path,
    files: dict[str, dict[str, Any]],
) -> None:
    for relative, value in files.items():
        parts = Path(relative)
        if (
            parts.is_absolute()
            or not parts.parts
            or any(part in {"", ".", ".."} for part in parts.parts)
        ):
            raise TrustedRunError("verified snapshot contains unsafe path")
        destination = root / parts
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(destination, flags, 0o600)
        try:
            os.write(fd, _canonical_bytes(value))
            os.fsync(fd)
        finally:
            os.close(fd)


def _finalize_verified_run(registry: Any, run_id: str) -> None:
    """Publish one independently verified protected snapshot by run identity."""

    if not run_id or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-._"
        for character in run_id.lower()
    ):
        raise TrustedRunError("finalization run identity is unsafe")
    staging_payload = _read_file(
        _PROTECTED_STORE_ROOT,
        f".staging/{run_id}.json",
        protected=True,
    )
    try:
        snapshot = VerifiedExecutionSnapshot.model_validate(
            _parse_json(staging_payload, "verified execution snapshot")
        )
    except ValueError as exc:
        raise TrustedRunError(f"verified execution snapshot invalid: {exc}") from exc
    identity = snapshot.model_dump(mode="json", exclude={"snapshot_digest"})
    expected_executions = registry.compiled_plan.execution_ids
    expected_attempts = {
        f"attempts/{execution_id}.json" for execution_id in expected_executions
    }
    expected_receipts = {
        f"producer-receipts/attempts/{execution_id}.json"
        for execution_id in expected_executions
    }
    required_tracked = {
        "registry/run.json",
        "registry/evidence-index.json",
        "registry/report-payload.json",
        "evidence/report-source.json",
        *expected_attempts,
    }
    required_protected = {
        "registry/anchor.json",
        "producer-receipts/report-source.json",
        *expected_receipts,
    }
    if (
        snapshot.run_id != run_id
        or snapshot.registry_id != registry.registry_id
        or snapshot.execution_ids != expected_executions
        or snapshot.snapshot_digest != canonical_digest(identity)
        or not required_tracked <= set(snapshot.tracked_files)
        or not required_protected <= set(snapshot.protected_files)
    ):
        raise TrustedRunError("verified execution snapshot scope/digest drift")
    tracked_root = (
        registry._repo_root / ".codex" / "stages" / "tj-ee5f" / "results" / run_id
    )
    protected_root = _PROTECTED_STORE_ROOT / run_id
    if tracked_root.exists() or protected_root.exists():
        raise TrustedRunError("finalized run identity already exists")
    tracked_root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _PROTECTED_STORE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    tracked_staging = Path(
        tempfile.mkdtemp(prefix=f".{run_id}.", dir=tracked_root.parent)
    )
    protected_staging = Path(
        tempfile.mkdtemp(prefix=f".{run_id}.", dir=_PROTECTED_STORE_ROOT)
    )
    try:
        _write_snapshot_tree(tracked_staging, snapshot.tracked_files)
        _write_snapshot_tree(protected_staging, snapshot.protected_files)
        os.rename(tracked_staging, tracked_root)
        os.rename(protected_staging, protected_root)
        _load_verified_run(registry, run_id)
    except Exception:
        shutil.rmtree(tracked_staging, ignore_errors=True)
        shutil.rmtree(protected_staging, ignore_errors=True)
        shutil.rmtree(tracked_root, ignore_errors=True)
        shutil.rmtree(protected_root, ignore_errors=True)
        raise


def _load_verified_run(
    registry: Any,
    run_id: str,
) -> VerifiedRun:
    """Verify fixed run artifacts against the registry and protected anchor."""

    if not run_id or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-._"
        for character in run_id.lower()
    ):
        raise TrustedRunError("trusted run identity is unsafe")
    tracked_root = (
        registry._repo_root / ".codex" / "stages" / "tj-ee5f" / "results" / run_id
    )
    protected_root = _PROTECTED_STORE_ROOT / run_id
    run_payload = _read_file(tracked_root, "registry/run.json")
    index_payload = _read_file(tracked_root, "registry/evidence-index.json")
    report_payload_bytes = _read_file(tracked_root, "registry/report-payload.json")
    anchor_payload = _read_file(protected_root, "registry/anchor.json", protected=True)
    try:
        run = TrustedRunDocument.model_validate(_parse_json(run_payload, "trusted run"))
        index = EvidenceIndex.model_validate(
            _parse_json(index_payload, "evidence index")
        )
        report = ClientReportPayload.model_validate(
            _parse_json(report_payload_bytes, "report payload")
        )
        anchor = TrustedRunAnchor.model_validate(
            _parse_json(anchor_payload, "protected run anchor")
        )
    except ValueError as exc:
        raise TrustedRunError(f"trusted run schema is invalid: {exc}") from exc

    if len({run.run_id, index.run_id, report.run_id, anchor.run_id}) != 1:
        raise TrustedRunError("trusted run identity drift")
    expected_criteria = tuple(registry.compiled_plan.criteria)
    expected_executions = registry.compiled_plan.execution_ids
    criteria = _unique(run.criteria, "criterion_id", "criterion result")
    executions = _unique(run.executions, "execution_id", "execution result")
    report_criteria = _unique(report.criteria, "criterion_id", "report criterion")
    report_executions = _unique(
        report.executions,
        "execution_id",
        "report execution",
    )
    if (
        len(criteria) != 30
        or set(criteria) != set(expected_criteria)
        or tuple(criteria) != expected_criteria
        or tuple(anchor.criterion_ids) != expected_criteria
    ):
        raise TrustedRunError("criterion scope must be exact canonical 30")
    if (
        len(executions) != 29
        or set(executions) != set(expected_executions)
        or tuple(executions) != expected_executions
        or tuple(anchor.execution_ids) != expected_executions
        or set(anchor.attempt_chain_heads) != set(expected_executions)
    ):
        raise TrustedRunError("execution scope must be exact canonical 29")
    if set(report_criteria) != set(expected_criteria):
        raise TrustedRunError("typed report criterion scope drift")
    if tuple(report_executions) != expected_executions:
        raise TrustedRunError("typed report execution scope drift")

    expected_anchor = {
        "policy_digest": registry.compiled_policy.policy_digest,
        "compiled_plan_digest": registry.compiled_plan.plan_digest,
        "authorization_digest": canonical_digest(
            run.authorization.model_dump(mode="json")
        ),
        "baseline_digest": run.baseline.content_digest,
        "final_digest": run.final.content_digest,
        "run_document_sha256": _sha256(run_payload),
        "evidence_index_sha256": _sha256(index_payload),
        "report_payload_sha256": _sha256(report_payload_bytes),
    }
    for field, expected in expected_anchor.items():
        if getattr(anchor, field) != expected:
            raise TrustedRunError(f"protected anchor {field} drift")
    if run.final.causal_event_digest != anchor.phase_journal_head_digest:
        raise TrustedRunError("final readback protected causal event binding drift")
    if (
        run.evidence_index_digest != anchor.evidence_index_sha256
        or run.report_payload_digest != anchor.report_payload_sha256
    ):
        raise TrustedRunError("tracked run digest binding drift")
    stores = run.authorization.store_ids
    if (
        stores.raw_root_digest != store_root_digest(protected_root)
        or stores.anchor_root_digest != store_root_digest(protected_root)
        or stores.tracked_root_digest != store_root_digest(tracked_root)
    ):
        raise TrustedRunError("authorization store root binding drift")

    registry._load_execution_authorization(run.authorization)
    registry.validate_execution_authorization(run.authorization)
    registry._load_trusted_readback(run.baseline)
    registry._load_trusted_readback(run.final)
    registry.validate_readback_window(
        baseline=run.baseline,
        final=run.final,
        final_visible_at=run.final_visible_at,
        delivered_at=run.delivered_at,
        action_at=run.action_at,
    )

    entries = _unique(index.entries, "evidence_id", "evidence index identity")
    evidence: dict[str, dict[str, Any]] = {}
    for identity, entry in entries.items():
        payload = _read_file(tracked_root, entry.relative_path)
        if _sha256(payload) != entry.sha256:
            raise TrustedRunError(f"evidence checksum drift: {identity}")
        evidence[identity] = _parse_json(payload, f"evidence {identity}")
        try:
            validate_redacted_payload(evidence[identity])
        except EvidenceError as exc:
            raise TrustedRunError(f"evidence privacy validation failed: {exc}") from exc

    for identity, criterion_row in criteria.items():
        plan = registry.compiled_plan.criteria[identity]
        if criterion_row.evidence_mode is not plan.evidence_mode:
            raise TrustedRunError(f"criterion evidence mode drift: {identity}")
        if not set(criterion_row.evidence_refs) <= set(evidence):
            raise TrustedRunError(f"criterion evidence reference drift: {identity}")
        exclusion_evidence_is_valid = (
            plan.allows_client_exclusion
            and criterion_row.outcome == "EXCLUDED_BY_CLIENT"
            and all(
                evidence[ref].get("status") == "excluded"
                and evidence[ref].get("external_gate_resolution")
                == "excluded_by_client"
                for ref in criterion_row.evidence_refs
            )
        )
        aggregate = aggregate_criterion_outcome(
            plan,
            criterion_row.obligation_outcomes,
            valid_exclusions=frozenset(
                key
                for key, outcome in criterion_row.obligation_outcomes.items()
                if outcome == "EXCLUDED_BY_CLIENT" and exclusion_evidence_is_valid
            ),
        )
        if aggregate != criterion_row.outcome:
            raise TrustedRunError(f"criterion all_required outcome drift: {identity}")
        if not _validate_evidence_mode(criterion_row, evidence):
            raise TrustedRunError(f"criterion evidence mode proof failed: {identity}")
        report_row = report_criteria[identity]
        if (
            report_row.outcome != criterion_row.outcome
            or report_row.evidence_mode is not criterion_row.evidence_mode
            or report_row.evidence_refs != criterion_row.evidence_refs
        ):
            raise TrustedRunError(f"typed report criterion binding drift: {identity}")

    authorization_digest = canonical_digest(run.authorization.model_dump(mode="json"))
    verified_attempt_digests: set[str] = set()
    for identity, execution_row in executions.items():
        if not set(execution_row.evidence_refs) <= set(evidence):
            raise TrustedRunError(f"execution evidence reference drift: {identity}")
        if execution_row.attempt_ref not in evidence:
            raise TrustedRunError(
                f"execution committed attempt reference missing: {identity}"
            )
        entry = entries[execution_row.attempt_ref]
        if entry.producer != "protected-attempt-committer":
            raise TrustedRunError(
                f"execution attempt producer is not trusted: {identity}"
            )
        try:
            attempt = CommittedExecutionArtifact.model_validate(
                evidence[execution_row.attempt_ref]
            )
        except ValueError as exc:
            raise TrustedRunError(
                f"execution committed attempt schema invalid: {identity}: {exc}"
            ) from exc
        _validate_attempt_phase_chain(attempt)
        if not attempt.protected_commit_ref.startswith(
            "attempts/"
        ) or not attempt.protected_commit_ref.endswith("/commit.json"):
            raise TrustedRunError(
                f"execution protected commit reference drift: {identity}"
            )
        protected_commit = _read_file(
            protected_root,
            attempt.protected_commit_ref,
            protected=True,
        )
        if _sha256(protected_commit) != attempt.protected_commit_digest:
            raise TrustedRunError(
                f"execution protected commit digest drift: {identity}"
            )
        _validate_protected_attempt_commit(
            protected_commit,
            artifact=attempt,
            authorization_digest=authorization_digest,
        )
        try:
            receipt = AttemptProducerReceipt.model_validate(
                _parse_json(
                    _read_file(
                        protected_root,
                        f"producer-receipts/attempts/{identity}.json",
                        protected=True,
                    ),
                    f"protected attempt producer receipt {identity}",
                )
            )
        except (TrustedRunError, ValueError) as exc:
            raise TrustedRunError(
                f"protected attempt producer receipt invalid: {identity}: {exc}"
            ) from exc
        if (
            attempt.run_id != run.run_id
            or attempt.execution_id != identity
            or attempt.outcome != execution_row.outcome
            or attempt.authorization_digest != authorization_digest
            or attempt.registry_id != registry.registry_id
            or attempt.evidence_refs != execution_row.evidence_refs
            or anchor.attempt_chain_heads[identity] != attempt.phase_head_digest
            or receipt.registry_id != registry.registry_id
            or receipt.run_id != run.run_id
            or receipt.execution_id != identity
            or receipt.attempt_digest != attempt.attempt_digest
            or receipt.authorization_digest != authorization_digest
            or receipt.semantic_digest != attempt.semantic_digest
            or receipt.raw_digest != attempt.raw_digest
            or receipt.tracked_digest != attempt.tracked_digest
            or receipt.phase_head_digest != attempt.phase_head_digest
            or receipt.tracked_sha256 != entry.sha256
            or receipt.protected_commit_digest != attempt.protected_commit_digest
        ):
            raise TrustedRunError(
                f"execution committed attempt binding drift: {identity}"
            )
        verified_attempt_digests.add(attempt.attempt_digest)
        report_execution = report_executions[identity]
        if (
            report_execution.outcome != execution_row.outcome
            or report_execution.attempt_ref != execution_row.attempt_ref
            or report_execution.evidence_refs != execution_row.evidence_refs
        ):
            raise TrustedRunError(f"typed report execution binding drift: {identity}")

    scenario_ids = tuple(registry.compiled_policy.scenarios)
    turn_execution_ids = tuple(turn.execution_id for turn in report.turns)
    if (
        len(report.turns) != len(scenario_ids)
        or len(set(turn_execution_ids)) != len(scenario_ids)
        or set(turn_execution_ids) != set(scenario_ids)
    ):
        raise TrustedRunError("typed report scenario turn coverage drift")
    for turn in report.turns:
        execution_row = executions[turn.execution_id]
        if (
            turn.attempt_id != execution_row.attempt_ref
            or execution_row.attempt_ref not in turn.evidence_refs
            or not set(turn.evidence_refs) <= set(evidence)
        ):
            raise TrustedRunError(
                f"typed report turn evidence binding drift: {turn.execution_id}"
            )
    report_refs = (
        *report.identity.evidence_refs,
        *report.tester.evidence_refs,
        *report.judge.evidence_refs,
        *report.latency.evidence_refs,
        *(ref for item in report.side_effects for ref in item.checksum_refs),
        *(ref for item in report.defects for ref in item.checksum_refs),
    )
    if not set(report_refs) <= set(evidence):
        raise TrustedRunError("typed report evidence reference drift")
    report_sources = [
        entry
        for entry in index.entries
        if entry.producer == "protected-report-materializer"
    ]
    if len(report_sources) != 1:
        raise TrustedRunError("typed report requires one protected report source")
    report_source_entry = report_sources[0]
    try:
        report_source = ReportSourceArtifact.model_validate(
            evidence[report_source_entry.evidence_id]
        )
    except ValueError as exc:
        raise TrustedRunError(f"protected report source schema invalid: {exc}") from exc
    try:
        report_receipt = ReportProducerReceipt.model_validate(
            _parse_json(
                _read_file(
                    protected_root,
                    "producer-receipts/report-source.json",
                    protected=True,
                ),
                "protected report producer receipt",
            )
        )
    except (TrustedRunError, ValueError) as exc:
        raise TrustedRunError(
            f"protected report producer receipt invalid: {exc}"
        ) from exc
    report_payload_sha256 = _sha256(report_payload_bytes)
    snapshot_digest = _verified_report_snapshot_digest(report)
    if (
        report_source_entry.evidence_id not in report_refs
        or report_source.registry_id != registry.registry_id
        or report_source.report_sections_digest != _report_sections_digest(report)
        or report_source.report_payload_sha256 != report_payload_sha256
        or report_source.verified_snapshot_digest != snapshot_digest
        or report_receipt.registry_id != registry.registry_id
        or report_receipt.tracked_sha256 != report_source_entry.sha256
        or report_receipt.report_sections_digest != report_source.report_sections_digest
        or report_receipt.report_payload_sha256 != report_payload_sha256
        or report_receipt.verified_snapshot_digest != snapshot_digest
    ):
        raise TrustedRunError("typed report protected source binding drift")
    try:
        validate_redacted_payload(report.model_dump(mode="json"))
    except EvidenceError as exc:
        raise TrustedRunError(f"report privacy validation failed: {exc}") from exc
    registry._trusted_attempt_digests.update(verified_attempt_digests)

    rollups = {
        "coverage_complete": True,
        "execution_complete": True,
        "requirements_met": (
            all(row.outcome == "PASS" for row in criteria.values())
            and all(row.outcome == "PASS" for row in executions.values())
            and not run.open_p0_p1
            and run.side_effect_closeout == "passed"
        ),
    }
    rendered = _render_report(report, rollups)
    try:
        validate_redacted_text(rendered.decode("utf-8"))
    except EvidenceError as exc:
        raise TrustedRunError(f"final report privacy validation failed: {exc}") from exc
    return VerifiedRun(rollups=rollups, report_bytes=rendered)
