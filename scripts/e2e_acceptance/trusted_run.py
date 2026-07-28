"""Load one anchored acceptance run and render its canonical client report."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from scripts.e2e_acceptance.evidence import (
    EvidenceError,
    validate_redacted_payload,
    validate_redacted_text,
    validate_side_effect_closeout,
)
from scripts.e2e_acceptance.execution import (
    ExecutionAuthorizationV2,
    FinalReadbackProducerReceipt,
    GateAttemptV2,
    GateEvidenceArtifact,
    GateEvidenceReceipt,
    OutcomeValue,
    ProtectedFinalReadbackArtifact,
    aggregate_criterion_outcome,
    store_root_digest,
    validate_execution_authorization,
)
from scripts.e2e_acceptance.policy import (
    ClassifierResult,
    PolicyValidationError,
    ReadbackObservation,
    ReadbackResult,
    StructuredEvent,
    ToolResult,
    VerifiedEvidenceContext,
)
from scripts.e2e_acceptance.production import (
    BaselineReadbackArtifact,
    BaselineReadbackProducerReceipt,
)
from scripts.e2e_acceptance.schemas import EvidenceMode


class TrustedRunError(PolicyValidationError):
    """A tracked run and its protected anchor do not form one trusted result."""


def _git_common_dir(repo_root: Path) -> Path:
    marker = repo_root / ".git"
    if marker.is_dir() and not marker.is_symlink():
        return marker
    if not marker.is_file() or marker.is_symlink():
        raise TrustedRunError("canonical git metadata root is unavailable")
    try:
        prefix, raw_git_dir = marker.read_text(encoding="utf-8").strip().split(":", 1)
    except (OSError, ValueError) as exc:
        raise TrustedRunError("canonical git worktree marker is invalid") from exc
    if prefix != "gitdir":
        raise TrustedRunError("canonical git worktree marker is invalid")
    git_dir = Path(raw_git_dir.strip())
    if not git_dir.is_absolute():
        git_dir = (repo_root / git_dir).resolve(strict=True)
    common_marker = git_dir / "commondir"
    if common_marker.is_file() and not common_marker.is_symlink():
        common_dir = Path(common_marker.read_text(encoding="utf-8").strip())
        if not common_dir.is_absolute():
            common_dir = (git_dir / common_dir).resolve(strict=True)
        return common_dir
    return git_dir


def _operator_root(registry: Any) -> Path:
    return (
        _git_common_dir(registry.repo_root)
        / "codex-orchestration"
        / "noor-e2e-acceptance"
    )


def _published_protected_root(registry: Any) -> Path:
    return _operator_root(registry) / "published-runs"


def _execution_snapshot_root(registry: Any) -> Path:
    return _operator_root(registry) / "execution-snapshots"


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
    attempt_kind: Literal["executed", "gate"]
    gate_attempt: GateAttemptV2 | None = None
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

    @model_validator(mode="after")
    def _typed_attempt_variant(self) -> CommittedExecutionArtifact:
        if self.attempt_kind == "executed":
            if self.outcome not in {"PASS", "FAIL"} or self.gate_attempt is not None:
                raise ValueError("executed attempt variant outcome drift")
        elif (
            self.outcome not in {"BLOCKED", "EXCLUDED_BY_CLIENT"}
            or self.gate_attempt is None
            or self.gate_attempt.execution_id != self.execution_id
            or self.gate_attempt.outcome != self.outcome
        ):
            raise ValueError("gate attempt variant outcome drift")
        return self


class AttemptProducerReceipt(_StrictModel):
    schema_version: Literal["noor-e2e-attempt-producer-receipt/v2"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    attempt_kind: Literal["executed", "gate"]
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
    side_effect_ledger_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_inventory_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
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
    transcript_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class ProtectedTranscriptArtifact(_StrictModel):
    """The immutable producer-owned source for one visible customer turn."""

    schema_version: Literal["noor-e2e-protected-transcript/v2"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    turn: dict[str, Any]


class TranscriptProducerReceipt(_StrictModel):
    schema_version: Literal["noor-e2e-transcript-producer-receipt/v2"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    transcript_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_phase_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProtectedTranscriptManifest(_StrictModel):
    schema_version: Literal["noor-e2e-protected-transcript-manifest/v2"]
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    ordered_turns: tuple[tuple[str, str, str, str, str], ...]


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
    scenario_id: str
    subsystem: str
    artifact_type: str
    baseline: dict[str, Any]
    expected_effect: dict[str, Any]
    final: dict[str, Any]
    disposition: str
    owner: str
    cleanup_authority: str
    follow_up_suppressed: bool
    retention_pre_authorized: bool | None = None
    retention_owner: str | None = None
    retention_authority_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    retention_expires_at: datetime | None = None
    final_disposition_date: datetime | None = None
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
    evidence_context: VerifiedEvidenceContext


class ProtectedEvidenceRecord(_StrictModel):
    evidence_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    payload: dict[str, Any]


class ProtectedCommittedExecutionSnapshot(_StrictModel):
    schema_version: Literal["noor-e2e-protected-execution-snapshot/v2"]
    run_id: str = Field(min_length=1)
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_ids: tuple[str, ...] = Field(min_length=29, max_length=29)
    run: dict[str, Any]
    report: dict[str, Any]
    evidence: tuple[ProtectedEvidenceRecord, ...] = Field(min_length=30)
    attempt_commits: dict[str, dict[str, Any]] = Field(min_length=29, max_length=29)
    transcript_artifacts: dict[str, dict[str, Any]] = Field(min_length=1)
    collector_artifacts: dict[str, dict[str, Any]] = Field(min_length=4, max_length=4)
    gate_artifacts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    sealed_plan: dict[str, Any]
    evaluator: dict[str, Any]
    sealed_plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_journal_phase: Literal["attempt_committed"]
    terminal_journal_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_sealed_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_causal_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProtectedSnapshotCommit(_StrictModel):
    schema_version: Literal["noor-e2e-protected-execution-snapshot-commit/v2"]
    status: Literal["committed"]
    run_id: str = Field(min_length=1)
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    journal_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_chain_heads_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    operator_store_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_readback_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_readback_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_inventory_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sealed_plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_journal_phase: Literal["attempt_committed"]
    terminal_journal_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_sealed_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_causal_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class LegacyProtectedCommittedExecutionSnapshot(_StrictModel):
    """Read-only compatibility for pre-production final-review fixtures.

    Production materialization never emits this schema.  It exists solely so
    frozen fixture snapshots retain their originally explicit legacy boundary.
    """

    schema_version: Literal["noor-e2e-protected-execution-snapshot/v1"]
    run_id: str = Field(min_length=1)
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_ids: tuple[str, ...] = Field(min_length=29, max_length=29)
    run: dict[str, Any]
    report: dict[str, Any]
    evidence: tuple[ProtectedEvidenceRecord, ...] = Field(min_length=30)
    attempt_commits: dict[str, dict[str, Any]] = Field(min_length=29, max_length=29)
    transcript_artifacts: dict[str, dict[str, Any]] = Field(min_length=1)
    collector_artifacts: dict[str, dict[str, Any]] = Field(min_length=2, max_length=2)
    gate_artifacts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class LegacyProtectedSnapshotCommit(_StrictModel):
    schema_version: Literal["noor-e2e-protected-execution-snapshot-commit/v1"]
    status: Literal["committed"]
    run_id: str = Field(min_length=1)
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    journal_head_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_chain_heads_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    operator_store_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_readback_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_inventory_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class PublishedRunCommit(_StrictModel):
    schema_version: Literal["noor-e2e-published-run-commit/v2"]
    status: Literal["committed"]
    run_id: str = Field(min_length=1)
    registry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tracked_tree_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    protected_tree_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


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
        or value.get("attempt_kind") != artifact.attempt_kind
        or value.get("attempt_digest") != artifact.attempt_digest
        or value.get("authorization_digest") != authorization_digest
        or value.get("semantic_digest") != artifact.semantic_digest
        or value.get("raw_digest") != artifact.raw_digest
        or value.get("tracked_digest") != artifact.tracked_digest
        or value.get("gate_attempt_digest")
        != (
            canonical_digest(artifact.gate_attempt.model_dump(mode="json"))
            if artifact.gate_attempt is not None
            else None
        )
    ):
        raise TrustedRunError(
            f"protected attempt commit binding drift: {artifact.execution_id}"
        )


def _validate_readback_contract(
    run: TrustedRunDocument,
) -> None:
    baseline = run.baseline
    final = run.final
    timeline = [*run.final_visible_at, *run.delivered_at, *run.action_at]
    if (
        baseline.run_id != final.run_id
        or baseline.preflight_digest != final.preflight_digest
        or baseline.collector_artifact_digest != final.collector_artifact_digest
        or baseline.phase != "baseline"
        or final.phase != "final"
        or baseline.source_id == final.source_id
        or baseline.observed_at >= final.observed_at
        or not timeline
        or baseline.observed_at >= min(timeline)
        or final.observed_at < max(timeline)
    ):
        raise TrustedRunError("trusted readback window binding drift")


def _validate_final_readback_artifacts(
    registry: Any,
    run: TrustedRunDocument,
    artifacts: dict[str, dict[str, Any]],
    *,
    current_time: datetime,
) -> tuple[str, str]:
    artifact_relative = "collector-artifacts/final-readback.json"
    receipt_relative = "producer-receipts/final-readback.json"
    if set(artifacts) != {artifact_relative, receipt_relative}:
        raise TrustedRunError("final readback protected artifact path-set drift")
    try:
        artifact = ProtectedFinalReadbackArtifact.model_validate(
            artifacts[artifact_relative]
        )
        receipt = FinalReadbackProducerReceipt.model_validate(
            artifacts[receipt_relative]
        )
    except ValueError as exc:
        raise TrustedRunError(
            f"final readback protected producer artifact is invalid: {exc}"
        ) from exc
    authorization_digest = canonical_digest(run.authorization.model_dump(mode="json"))
    artifact_payload = _canonical_bytes(artifacts[artifact_relative])
    receipt_payload = _canonical_bytes(artifacts[receipt_relative])
    final_anchor_at = max((*run.final_visible_at, *run.delivered_at, *run.action_at))
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise TrustedRunError("final readback validation time must be aware")
    if (
        artifact.registry_id != registry.registry_id
        or artifact.run_id != run.run_id
        or artifact.authorization_digest != authorization_digest
        or artifact.preflight_digest != run.authorization.preflight_digest
        or tuple(run.authorization.collector_ids) != (artifact.collector_id,)
        or artifact.collector_artifact_digest
        != run.authorization.readback_collector_digest
        or artifact.journal_head_digest != run.final.causal_event_digest
        or artifact.final_turn_anchor_at != final_anchor_at
        or artifact.observation != run.final
        or artifact.inventory_digest != canonical_digest(run.final.inventory)
        or artifact.observed_at > current_time
        or current_time - artifact.observed_at > timedelta(minutes=5)
        or receipt.registry_id != artifact.registry_id
        or receipt.run_id != artifact.run_id
        or receipt.authorization_digest != authorization_digest
        or receipt.preflight_digest != artifact.preflight_digest
        or receipt.producer != "independent-readback-collector"
        or receipt.collector_id != artifact.collector_id
        or receipt.collector_artifact_digest != artifact.collector_artifact_digest
        or receipt.journal_head_digest != artifact.journal_head_digest
        or receipt.artifact_sha256 != _sha256(artifact_payload)
        or receipt.inventory_digest != artifact.inventory_digest
        or receipt.observed_at != artifact.observed_at
        or not receipt.issued_at <= current_time < receipt.expires_at
    ):
        raise TrustedRunError("final readback protected producer binding drift")
    return _sha256(receipt_payload), artifact.inventory_digest


def _validate_baseline_readback_artifacts(
    registry: Any,
    run: TrustedRunDocument,
    artifacts: dict[str, dict[str, Any]],
) -> str:
    artifact_relative = "collector-artifacts/baseline-readback.json"
    receipt_relative = "producer-receipts/baseline-readback.json"
    try:
        artifact = BaselineReadbackArtifact.model_validate(artifacts[artifact_relative])
        receipt = BaselineReadbackProducerReceipt.model_validate(
            artifacts[receipt_relative]
        )
    except (KeyError, ValueError) as exc:
        raise TrustedRunError(
            "baseline readback protected producer artifact is invalid"
        ) from exc
    authorization_digest = canonical_digest(run.authorization.model_dump(mode="json"))
    artifact_payload = _canonical_bytes(artifacts[artifact_relative])
    receipt_payload = _canonical_bytes(artifacts[receipt_relative])
    baseline = run.baseline
    if (
        artifact.registry_id != registry.registry_id
        or artifact.run_id != run.run_id
        or artifact.authorization_digest != authorization_digest
        or artifact.preflight_digest != run.authorization.preflight_digest
        or tuple(run.authorization.collector_ids) != (artifact.collector_id,)
        or artifact.collector_artifact_digest
        != run.authorization.readback_collector_digest
        or artifact.observation != baseline
        or artifact.inventory_digest != canonical_digest(baseline.inventory)
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
        or receipt.artifact_sha256 != _sha256(artifact_payload)
    ):
        raise TrustedRunError("baseline readback protected receipt binding drift")
    return _sha256(receipt_payload)


def _validate_snapshot_readback_artifacts(
    registry: Any,
    run: TrustedRunDocument,
    artifacts: dict[str, dict[str, Any]],
    *,
    current_time: datetime,
) -> tuple[str, str, str]:
    expected = {
        "collector-artifacts/baseline-readback.json",
        "producer-receipts/baseline-readback.json",
        "collector-artifacts/final-readback.json",
        "producer-receipts/final-readback.json",
    }
    if set(artifacts) != expected:
        raise TrustedRunError("readback protected artifact path-set drift")
    baseline_receipt_digest = _validate_baseline_readback_artifacts(
        registry, run, artifacts
    )
    final_receipt_digest, final_inventory_digest = _validate_final_readback_artifacts(
        registry,
        run,
        {
            relative: artifacts[relative]
            for relative in (
                "collector-artifacts/final-readback.json",
                "producer-receipts/final-readback.json",
            )
        },
        current_time=current_time,
    )
    return baseline_receipt_digest, final_receipt_digest, final_inventory_digest


def _validate_baseline_sealed_journal_chain(
    run_root: Path,
    baseline: ReadbackObservation,
    *,
    terminal_head_digest: str,
) -> str:
    journal_root = run_root / "journal"
    if not journal_root.is_dir() or journal_root.is_symlink():
        raise TrustedRunError("baseline sealed journal is unavailable")
    previous_digest: str | None = None
    baseline_sealed = False
    baseline_sealed_digest: str | None = None
    paths = sorted(journal_root.glob("*.json"))
    for cursor, path in enumerate(paths, start=1):
        if path.name != f"{cursor:06d}.json" or path.is_symlink():
            raise TrustedRunError("baseline sealed journal path/cursor drift")
        payload = _read_file(run_root, f"journal/{path.name}", protected=True)
        event = _parse_json(payload, "protected journal event")
        digest = _sha256(payload)
        if (
            event.get("cursor") != cursor
            or event.get("previous_event_digest") != previous_digest
        ):
            raise TrustedRunError("baseline sealed journal causality drift")
        if event.get("kind") == "baseline_sealed":
            data = event.get("data")
            if (
                baseline_sealed
                or event.get("phase") != "baseline_sealed"
                or not isinstance(data, dict)
                or data.get("source_id") != baseline.source_id
                or data.get("collector_id") != baseline.collector_id
                or data.get("observed_at") != baseline.observed_at.isoformat()
                or data.get("content_digest") != baseline.content_digest
            ):
                raise TrustedRunError("baseline sealed journal binding drift")
            baseline_sealed = True
            baseline_sealed_digest = digest
        previous_digest = digest
    if (
        not baseline_sealed
        or previous_digest != terminal_head_digest
        or not paths
        or _parse_json(
            _read_file(run_root, f"journal/{paths[-1].name}", protected=True),
            "protected terminal journal event",
        ).get("phase")
        != "attempt_committed"
    ):
        raise TrustedRunError("baseline sealed journal terminal-chain drift")
    if baseline_sealed_digest is None:
        raise TrustedRunError("baseline sealed journal digest is unavailable")
    return baseline_sealed_digest


def _validate_derived_publication_payload(payload: dict[str, Any]) -> None:
    """Validate public payloads while preserving the typed authorization manifest."""

    if "authorization" not in payload:
        validate_redacted_payload(payload)
        return
    validate_redacted_payload(
        {
            **{key: value for key, value in payload.items() if key != "authorization"},
            "authorization_manifest": payload["authorization"],
        }
    )


def _validate_gate_artifacts(
    registry: Any,
    run: TrustedRunDocument,
    attempts: dict[str, CommittedExecutionArtifact],
    artifacts: dict[str, dict[str, Any]],
    *,
    current_time: datetime,
) -> None:
    gate_attempts = {
        execution_id: attempt
        for execution_id, attempt in attempts.items()
        if attempt.attempt_kind == "gate"
    }
    expected_paths = {
        relative
        for execution_id in gate_attempts
        for relative in (
            f"gate-attempts/{execution_id}.json",
            f"gate-evidence/{execution_id}.json",
            f"producer-receipts/gates/{execution_id}.json",
            f"recorded-gates/{execution_id}.json",
        )
    }
    if set(artifacts) != expected_paths:
        raise TrustedRunError("typed gate protected artifact path-set drift")
    authorization_digest = canonical_digest(run.authorization.model_dump(mode="json"))
    for execution_id, committed in gate_attempts.items():
        gate_attempt = committed.gate_attempt
        if gate_attempt is None:
            raise TrustedRunError("typed gate attempt payload is missing")
        artifact_relative = f"gate-evidence/{execution_id}.json"
        receipt_relative = f"producer-receipts/gates/{execution_id}.json"
        attempt_relative = f"gate-attempts/{execution_id}.json"
        recorded_relative = f"recorded-gates/{execution_id}.json"
        try:
            materialized_attempt = GateAttemptV2.model_validate(
                artifacts[attempt_relative]
            )
            artifact = GateEvidenceArtifact.model_validate(artifacts[artifact_relative])
            receipt = GateEvidenceReceipt.model_validate(artifacts[receipt_relative])
        except ValueError as exc:
            raise TrustedRunError(
                f"typed gate protected artifact is invalid: {execution_id}: {exc}"
            ) from exc
        criterion_ids = tuple(
            criterion.criterion_id
            for criterion in registry.compiled_plan.criteria.values()
            if execution_id in criterion.obligation_ids
        )
        criterion_models = tuple(
            registry.compiled_plan.criteria[criterion_id]
            for criterion_id in criterion_ids
        )
        artifact_sha256 = _sha256(_canonical_bytes(artifacts[artifact_relative]))
        receipt_sha256 = _sha256(_canonical_bytes(artifacts[receipt_relative]))
        gate_attempt_sha256 = _sha256(_canonical_bytes(artifacts[attempt_relative]))
        recorded = artifacts[recorded_relative]
        common_drift = (
            materialized_attempt != gate_attempt
            or recorded
            != {
                "schema_version": "noor-e2e-recorded-gate/v2",
                "execution_id": execution_id,
                "outcome": committed.outcome,
                "gate_attempt_sha256": gate_attempt_sha256,
                "journal_head_digest": recorded.get("journal_head_digest"),
                "gate_attempt": gate_attempt.model_dump(mode="json"),
            }
            or artifact.registry_id != registry.registry_id
            or artifact.run_id != run.run_id
            or artifact.authorization_digest != authorization_digest
            or artifact.execution_id != execution_id
            or artifact.criterion_ids != criterion_ids
            or artifact.execution_owner != run.authorization.authorization_id
            or artifact.outcome != committed.outcome
            or receipt.registry_id != artifact.registry_id
            or receipt.run_id != artifact.run_id
            or receipt.authorization_digest != authorization_digest
            or receipt.execution_id != execution_id
            or receipt.criterion_ids != criterion_ids
            or receipt.execution_owner != artifact.execution_owner
            or receipt.execution_started_event_digest
            != artifact.execution_started_event_digest
            or gate_attempt.execution_started_event_digest
            != artifact.execution_started_event_digest
            or receipt.artifact_sha256 != artifact_sha256
            or receipt.outcome != artifact.outcome
            or receipt.producer != artifact.producer
            or receipt.issued_at != artifact.observed_at
            or gate_attempt.receipt_digest != receipt_sha256
            or gate_attempt.run_started_at.tzinfo is None
            or gate_attempt.run_started_at.utcoffset() is None
            or not receipt.issued_at <= current_time < receipt.expires_at
        )
        if common_drift:
            raise TrustedRunError(
                f"typed gate protected provenance drift: {execution_id}"
            )
        if committed.outcome == "BLOCKED":
            if (
                receipt.producer
                not in {
                    "independent-readback-collector",
                    "trusted-evidence-registry",
                }
                or receipt.issued_at < gate_attempt.run_started_at
                or receipt.client_authority_digest is not None
            ):
                raise TrustedRunError(
                    f"typed blocked gate lacks independent evidence: {execution_id}"
                )
        else:
            expected_authority = run.authorization.client_exclusion_authorities.get(
                execution_id
            )
            if (
                receipt.producer != "client-exclusion-authority"
                or not criterion_models
                or not all(
                    criterion.allows_client_exclusion for criterion in criterion_models
                )
                or expected_authority is None
                or receipt.client_authority_digest != expected_authority
                or receipt.issued_at >= gate_attempt.run_started_at
                or receipt.issued_at < run.authorization.issued_at
            ):
                raise TrustedRunError(
                    f"typed client exclusion authority drift: {execution_id}"
                )


def _load_decisive_evidence(
    registry: Any,
    run_id: str,
    *,
    artifact_digest: str,
) -> ClassifierResult | StructuredEvent | ToolResult | ReadbackResult:
    tracked_root = (
        registry.repo_root / ".codex" / "stages" / "tj-ee5f" / "results" / run_id
    )
    protected_root = _published_protected_root(registry) / run_id
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
    verified_context = _load_verified_run(registry, run_id).evidence_context
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
        or artifact.attempt_digest not in verified_context.attempt_digests
        or not any(
            artifact.preflight_digest == preflight
            for preflight, _ in verified_context.preflight_collectors
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
    else:
        if assertion.oracle.kind == "classifier_result":
            raise TrustedRunError("structured decisive oracle kind drift")
    return artifact


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
    root_fd = _open_or_create_snapshot_root(root)
    try:
        for relative, value in files.items():
            parts = _snapshot_relative_parts(relative)
            parent_fd = _open_or_create_snapshot_parent(root_fd, parts[:-1])
            try:
                flags = (
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                )
                fd = os.open(parts[-1], flags, 0o600, dir_fd=parent_fd)
                try:
                    payload = _canonical_bytes(value)
                    offset = 0
                    while offset < len(payload):
                        offset += os.write(fd, payload[offset:])
                    os.fsync(fd)
                finally:
                    os.close(fd)
                os.fsync(parent_fd)
            except OSError as exc:
                raise TrustedRunError(
                    f"protected snapshot write violates no-follow policy: {exc}"
                ) from exc
            finally:
                os.close(parent_fd)
        os.fsync(root_fd)
    finally:
        os.close(root_fd)


def _snapshot_relative_parts(relative: str) -> tuple[str, ...]:
    parts = Path(relative)
    if (
        parts.is_absolute()
        or not parts.parts
        or any(part in {"", ".", ".."} for part in parts.parts)
    ):
        raise TrustedRunError("verified snapshot contains unsafe path")
    return parts.parts


def _open_or_create_snapshot_root(root: Path) -> int:
    """Create/open an absolute snapshot root without following any component."""

    if not root.is_absolute() or any(
        part in {"", ".", ".."} for part in root.parts[1:]
    ):
        raise TrustedRunError("protected snapshot root is unsafe")
    current_fd = os.open("/", _directory_flags())
    try:
        for part in root.parts[1:]:
            created = False
            try:
                os.mkdir(part, mode=0o700, dir_fd=current_fd)
                created = True
            except FileExistsError:
                pass
            if created:
                os.fsync(current_fd)
            next_fd = os.open(part, _directory_flags(), dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
    except OSError as exc:
        os.close(current_fd)
        raise TrustedRunError(
            f"protected snapshot root violates no-follow policy: {exc}"
        ) from exc
    return current_fd


def _open_or_create_snapshot_parent(root_fd: int, directories: tuple[str, ...]) -> int:
    current_fd = os.dup(root_fd)
    try:
        for directory in directories:
            created = False
            try:
                os.mkdir(directory, mode=0o700, dir_fd=current_fd)
                created = True
            except FileExistsError:
                pass
            if created:
                os.fsync(current_fd)
            next_fd = os.open(directory, _directory_flags(), dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
    except OSError as exc:
        os.close(current_fd)
        raise TrustedRunError(
            f"protected snapshot parent violates no-follow policy: {exc}"
        ) from exc
    return current_fd


def _read_snapshot_file_if_present(root: Path, relative: str) -> bytes | None:
    root_fd = _open_or_create_snapshot_root(root)
    try:
        parts = _snapshot_relative_parts(relative)
        parent_fd = _open_or_create_snapshot_parent(root_fd, parts[:-1])
        try:
            try:
                file_fd = os.open(
                    parts[-1],
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=parent_fd,
                )
            except FileNotFoundError:
                return None
            try:
                metadata = os.fstat(file_fd)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or stat.S_IMODE(metadata.st_mode) != 0o600
                ):
                    raise TrustedRunError(
                        "protected snapshot file mode/type is invalid"
                    )
                chunks: list[bytes] = []
                while True:
                    chunk = os.read(file_fd, 1024 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                return b"".join(chunks)
            finally:
                os.close(file_fd)
        except OSError as exc:
            raise TrustedRunError(
                f"protected snapshot read violates no-follow policy: {exc}"
            ) from exc
        finally:
            os.close(parent_fd)
    finally:
        os.close(root_fd)


def _write_atomic_final_commit(
    root: Path,
    commit: PublishedRunCommit,
) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=".final-commit.", dir=root)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        payload = _canonical_bytes(commit.model_dump(mode="json"))
        offset = 0
        while offset < len(payload):
            offset += os.write(fd, payload[offset:])
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(temporary, root / "final-commit.json")
        _fsync_directory(root)
    except Exception:
        if fd >= 0:
            os.close(fd)
        temporary.unlink(missing_ok=True)
        raise


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, _directory_flags())
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _tree_digest(root: Path, *, exclude: frozenset[str] = frozenset()) -> str:
    if not root.is_dir() or root.is_symlink():
        raise TrustedRunError("published run tree is unavailable")
    manifest: dict[str, str] = {}
    for directory, directories, files in os.walk(root, followlinks=False):
        base = Path(directory)
        if any((base / name).is_symlink() for name in (*directories, *files)):
            raise TrustedRunError("published run tree contains a symlink")
        for name in files:
            relative = (base / name).relative_to(root).as_posix()
            if relative not in exclude:
                manifest[relative] = _sha256(
                    _read_file(root, relative, protected=False)
                )
    return canonical_digest(manifest)


def _tree_relative_files(
    root: Path,
    *,
    prefixes: tuple[str, ...],
) -> frozenset[str]:
    if not root.is_dir() or root.is_symlink():
        raise TrustedRunError("published run tree is unavailable")
    result: set[str] = set()
    for directory, directories, files in os.walk(root, followlinks=False):
        base = Path(directory)
        if any((base / name).is_symlink() for name in (*directories, *files)):
            raise TrustedRunError("published run tree contains a symlink")
        for name in files:
            path = base / name
            if not path.is_file():
                raise TrustedRunError("published run tree contains a non-file")
            relative = path.relative_to(root).as_posix()
            if relative.startswith(prefixes):
                result.add(relative)
    return frozenset(result)


def materialize_execution_snapshot(
    registry: Any,
    journal: Any,
    sealed_plan: Any,
) -> ProtectedCommittedExecutionSnapshot:
    """Package only canonical, independently produced candidate evidence.

    The caller supplies no roots: tracked candidate evidence is fixed under the
    stage result root and protected evidence is fixed to the current journal.
    """

    if (
        journal.phase != "attempt_committed"
        or journal.previous_event_digest is None
        or journal.run_root != journal.protected_root / journal.run_id
        or any(
            state not in {"succeeded", "failed"} for state in journal._actions.values()
        )
    ):
        raise TrustedRunError(
            "snapshot materialization requires a terminal attempt-committed journal"
        )
    run_id = journal.run_id
    tracked = registry.repo_root / ".codex" / "stages" / "tj-ee5f" / "results" / run_id
    try:
        sealed_payload = _read_file(
            journal.run_root, "run-plan/sealed.json", protected=True
        )
        sealed = _parse_json(
            sealed_payload,
            "sealed run plan",
        )
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
            or sealed.get("plan_digest") != sealed_plan.plan_digest
            or sealed.get("evaluator_digest") != sealed_plan.evaluator_digest
            or sealed.get("evaluator") != sealed_plan.evaluator
            or canonical_digest(
                {"actions": sealed.get("actions"), "evaluator": sealed.get("evaluator")}
            )
            != sealed_plan.plan_digest
            or canonical_digest(sealed.get("evaluator")) != sealed_plan.evaluator_digest
        ):
            raise TrustedRunError("sealed plan/evaluator drift")
        index = EvidenceIndex.model_validate(
            _parse_json(
                _read_file(tracked, "registry/evidence-index.json"),
                "candidate evidence index",
            )
        )
        run = _parse_json(_read_file(tracked, "registry/run.json"), "candidate run")
        report = _parse_json(
            _read_file(tracked, "registry/report-payload.json"), "candidate report"
        )
    except (ValueError, TrustedRunError) as exc:
        raise TrustedRunError("canonical candidate artifacts are incomplete") from exc
    try:
        run_document = TrustedRunDocument.model_validate(run)
        report_document = ClientReportPayload.model_validate(report)
    except ValueError as exc:
        raise TrustedRunError("candidate run or report contract is invalid") from exc
    if (
        index.run_id != run_id
        or run_document.run_id != run_id
        or report_document.run_id != run_id
        or canonical_digest(run_document.authorization.model_dump(mode="json"))
        != journal.authorization_digest
        or tuple(row.execution_id for row in run_document.executions)
        != registry.compiled_plan.execution_ids
        or len({entry.evidence_id for entry in index.entries}) != len(index.entries)
        or len({entry.relative_path for entry in index.entries}) != len(index.entries)
    ):
        raise TrustedRunError("canonical candidate run/report authorization drift")
    evidence_records: list[ProtectedEvidenceRecord] = []
    for entry in index.entries:
        payload = _read_file(tracked, entry.relative_path)
        if _sha256(payload) != entry.sha256:
            raise TrustedRunError("candidate evidence index checksum drift")
        evidence_records.append(
            ProtectedEvidenceRecord(
                evidence_id=entry.evidence_id,
                relative_path=entry.relative_path,
                producer=entry.producer,
                payload=_parse_json(payload, "candidate evidence"),
            )
        )
    evidence = tuple(evidence_records)
    attempt_commits = {
        record.payload["execution_id"]: _parse_json(
            _read_file(
                journal.run_root, record.payload["protected_commit_ref"], protected=True
            ),
            "protected attempt commit",
        )
        for record in evidence
        if record.producer == "protected-attempt-committer"
    }
    transcript_artifacts = {
        path.relative_to(journal.run_root).as_posix(): _parse_json(
            _read_file(
                journal.run_root,
                path.relative_to(journal.run_root).as_posix(),
                protected=True,
            ),
            "protected transcript artifact",
        )
        for base in (
            journal.run_root / "transcripts",
            journal.run_root / "producer-receipts" / "transcripts",
        )
        if base.exists()
        for path in base.rglob("*.json")
    }
    collector_artifacts = {
        relative: _parse_json(
            _read_file(journal.run_root, relative, protected=True),
            "final collector artifact",
        )
        for relative in (
            "collector-artifacts/baseline-readback.json",
            "producer-receipts/baseline-readback.json",
            "collector-artifacts/final-readback.json",
            "producer-receipts/final-readback.json",
        )
    }
    _validate_snapshot_readback_artifacts(
        registry,
        run_document,
        collector_artifacts,
        current_time=datetime.now(UTC),
    )
    baseline_sealed_event_digest = _validate_baseline_sealed_journal_chain(
        journal.run_root,
        run_document.baseline,
        terminal_head_digest=journal.previous_event_digest,
    )
    gate_artifacts: dict[str, dict[str, Any]] = {}
    for execution_id, gate in journal._recorded_gates.items():
        expected = gate.model_dump(mode="json")
        relatives = {
            f"gate-attempts/{execution_id}.json": expected,
            f"gate-evidence/{execution_id}.json": None,
            f"producer-receipts/gates/{execution_id}.json": None,
            f"recorded-gates/{execution_id}.json": None,
        }
        loaded = {
            relative: _parse_json(
                _read_file(journal.run_root, relative, protected=True),
                "recorded gate artifact",
            )
            for relative in relatives
        }
        record = loaded[f"recorded-gates/{execution_id}.json"]
        if (
            loaded[f"gate-attempts/{execution_id}.json"] != expected
            or record.get("execution_id") != execution_id
            or record.get("outcome") != gate.outcome
            or record.get("gate_attempt") != expected
            or record.get("gate_attempt_sha256") != _sha256(_canonical_bytes(expected))
        ):
            raise TrustedRunError("recorded gate artifact binding drift")
        gate_artifacts.update(loaded)
    expected_gate_paths = {
        relative
        for execution_id in journal._recorded_gates
        for relative in (
            f"gate-attempts/{execution_id}.json",
            f"gate-evidence/{execution_id}.json",
            f"producer-receipts/gates/{execution_id}.json",
            f"recorded-gates/{execution_id}.json",
        )
    }
    actual_gate_paths = {
        path.relative_to(journal.run_root).as_posix()
        for prefix in (
            "gate-attempts",
            "gate-evidence",
            "producer-receipts/gates",
            "recorded-gates",
        )
        for path in (journal.run_root / prefix).rglob("*.json")
        if path.is_file() and not path.is_symlink()
    }
    if actual_gate_paths != expected_gate_paths:
        raise TrustedRunError("recorded gate artifact path-set drift")
    try:
        attempt_models = {
            record.payload["execution_id"]: CommittedExecutionArtifact.model_validate(
                record.payload
            )
            for record in evidence
            if record.producer == "protected-attempt-committer"
        }
    except ValueError as exc:
        raise TrustedRunError("protected attempt commit is invalid") from exc
    _validate_gate_artifacts(
        registry,
        run_document,
        attempt_models,
        gate_artifacts,
        current_time=datetime.now(UTC),
    )
    identity = {
        "schema_version": "noor-e2e-protected-execution-snapshot/v2",
        "run_id": run_id,
        "registry_id": registry.registry_id,
        "execution_ids": list(registry.compiled_plan.execution_ids),
        "run": run,
        "report": report,
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "attempt_commits": attempt_commits,
        "transcript_artifacts": transcript_artifacts,
        "collector_artifacts": collector_artifacts,
        "gate_artifacts": gate_artifacts,
        "sealed_plan": sealed,
        "evaluator": sealed_plan.evaluator,
        "sealed_plan_digest": _sha256(sealed_payload),
        "evaluator_digest": sealed_plan.evaluator_digest,
        "terminal_journal_phase": journal.phase,
        "terminal_journal_head_digest": journal.previous_event_digest,
        "baseline_sealed_event_digest": baseline_sealed_event_digest,
        "final_causal_event_digest": run_document.final.causal_event_digest,
    }
    snapshot = ProtectedCommittedExecutionSnapshot(
        **identity, snapshot_digest=canonical_digest(identity)
    )
    # Validate the complete publication projection before writing either half
    # of the snapshot transaction.  Parsing the three candidate roots alone
    # is not enough: this also checks attempt commits, transcripts, final
    # collector receipts and the exact typed-gate artifact set together.
    _derive_publication(registry, snapshot)
    root = _execution_snapshot_root(registry) / run_id
    payload = _canonical_bytes(snapshot.model_dump(mode="json"))
    existing_snapshot = _read_snapshot_file_if_present(root, "snapshot.json")
    if existing_snapshot is not None:
        if existing_snapshot != payload:
            raise TrustedRunError("snapshot replay differs from committed bytes")
    else:
        _write_snapshot_tree(root, {"snapshot.json": snapshot.model_dump(mode="json")})
    attempt_heads = {
        record.payload["execution_id"]: record.payload["phase_head_digest"]
        for record in evidence
        if record.producer == "protected-attempt-committer"
    }
    commit = ProtectedSnapshotCommit(
        schema_version="noor-e2e-protected-execution-snapshot-commit/v2",
        status="committed",
        run_id=run_id,
        registry_id=registry.registry_id,
        snapshot_sha256=_sha256(payload),
        snapshot_digest=snapshot.snapshot_digest,
        authorization_digest=journal.authorization_digest,
        journal_head_digest=journal.previous_event_digest,
        attempt_chain_heads_digest=canonical_digest(attempt_heads),
        operator_store_digest=store_root_digest(_operator_root(registry)),
        baseline_readback_receipt_digest=_sha256(
            _read_file(
                journal.run_root,
                "producer-receipts/baseline-readback.json",
                protected=True,
            )
        ),
        final_readback_receipt_digest=_sha256(
            _read_file(
                journal.run_root,
                "producer-receipts/final-readback.json",
                protected=True,
            )
        ),
        final_inventory_digest=run["final_inventory_digest"],
        sealed_plan_digest=snapshot.sealed_plan_digest,
        evaluator_digest=sealed_plan.evaluator_digest,
        terminal_journal_phase=journal.phase,
        terminal_journal_head_digest=journal.previous_event_digest,
        baseline_sealed_event_digest=baseline_sealed_event_digest,
        final_causal_event_digest=run_document.final.causal_event_digest,
    )
    existing_commit = _read_snapshot_file_if_present(root, "commit.json")
    if existing_commit is not None:
        if existing_commit != _canonical_bytes(commit.model_dump(mode="json")):
            raise TrustedRunError("snapshot commit replay drift")
    else:
        _write_snapshot_tree(root, {"commit.json": commit.model_dump(mode="json")})
    return snapshot


def _load_protected_execution_snapshot(
    registry: Any,
    run_id: str,
) -> ProtectedCommittedExecutionSnapshot | LegacyProtectedCommittedExecutionSnapshot:
    root = _execution_snapshot_root(registry) / run_id
    try:
        snapshot_payload = _read_file(root, "snapshot.json", protected=True)
        snapshot_value = _parse_json(
            snapshot_payload, "protected committed execution snapshot"
        )
        commit_value = _parse_json(
            _read_file(root, "commit.json", protected=True),
            "protected committed execution snapshot marker",
        )
        legacy = snapshot_value.get("schema_version") == (
            "noor-e2e-protected-execution-snapshot/v1"
        )
        if legacy:
            snapshot = LegacyProtectedCommittedExecutionSnapshot.model_validate(
                snapshot_value
            )
            commit = LegacyProtectedSnapshotCommit.model_validate(commit_value)
        else:
            snapshot = ProtectedCommittedExecutionSnapshot.model_validate(
                snapshot_value
            )
            commit = ProtectedSnapshotCommit.model_validate(commit_value)
    except (TrustedRunError, ValueError) as exc:
        raise TrustedRunError(
            f"protected committed execution snapshot is invalid: {exc}"
        ) from exc
    identity = snapshot.model_dump(mode="json", exclude={"snapshot_digest"})
    attempt_chain_heads = {
        record.payload["execution_id"]: record.payload["phase_head_digest"]
        for record in snapshot.evidence
        if record.producer == "protected-attempt-committer"
    }
    try:
        run = TrustedRunDocument.model_validate(snapshot.run)
    except ValueError as exc:
        raise TrustedRunError(
            f"protected committed execution run is invalid: {exc}"
        ) from exc
    if legacy:
        final_receipt_digest, final_inventory_digest = (
            _validate_final_readback_artifacts(
                registry,
                run,
                snapshot.collector_artifacts,
                current_time=datetime.now(UTC),
            )
        )
        baseline_receipt_digest = None
    else:
        (
            baseline_receipt_digest,
            final_receipt_digest,
            final_inventory_digest,
        ) = _validate_snapshot_readback_artifacts(
            registry,
            run,
            snapshot.collector_artifacts,
            current_time=datetime.now(UTC),
        )
    authorization_digest = canonical_digest(snapshot.run["authorization"])
    common_binding_drift = (
        snapshot.run_id != run_id
        or snapshot.registry_id != registry.registry_id
        or snapshot.execution_ids != registry.compiled_plan.execution_ids
        or snapshot.snapshot_digest != canonical_digest(identity)
        or commit.run_id != run_id
        or commit.registry_id != registry.registry_id
        or commit.snapshot_sha256 != _sha256(snapshot_payload)
        or commit.snapshot_digest != snapshot.snapshot_digest
        or commit.authorization_digest != authorization_digest
        or commit.attempt_chain_heads_digest != canonical_digest(attempt_chain_heads)
        or commit.operator_store_digest != store_root_digest(_operator_root(registry))
        or (
            not legacy
            and commit.baseline_readback_receipt_digest != baseline_receipt_digest
        )
        or commit.final_readback_receipt_digest != final_receipt_digest
        or commit.final_inventory_digest != final_inventory_digest
    )
    if legacy:
        binding_drift = common_binding_drift or (
            commit.journal_head_digest != run.final.causal_event_digest
        )
    else:
        binding_drift = common_binding_drift or (
            snapshot.terminal_journal_phase != "attempt_committed"
            or snapshot.sealed_plan.get("schema_version")
            != "noor-e2e-sealed-run-plan/v2"
            or snapshot.sealed_plan.get("evaluator") != snapshot.evaluator
            or snapshot.sealed_plan.get("evaluator_digest") != snapshot.evaluator_digest
            or snapshot.sealed_plan.get("plan_digest")
            != canonical_digest(
                {
                    "actions": snapshot.sealed_plan.get("actions"),
                    "evaluator": snapshot.evaluator,
                }
            )
            or _sha256(_canonical_bytes(snapshot.sealed_plan))
            != snapshot.sealed_plan_digest
            or canonical_digest(snapshot.evaluator) != snapshot.evaluator_digest
            or snapshot.final_causal_event_digest != run.final.causal_event_digest
            or commit.journal_head_digest != snapshot.terminal_journal_head_digest
            or commit.terminal_journal_phase != snapshot.terminal_journal_phase
            or commit.terminal_journal_head_digest
            != snapshot.terminal_journal_head_digest
            or commit.baseline_sealed_event_digest
            != snapshot.baseline_sealed_event_digest
            or commit.final_causal_event_digest != snapshot.final_causal_event_digest
            or commit.sealed_plan_digest != snapshot.sealed_plan_digest
            or commit.evaluator_digest != snapshot.evaluator_digest
        )
    if binding_drift:
        raise TrustedRunError("protected committed execution snapshot binding drift")
    return snapshot


def _derive_publication(
    registry: Any,
    snapshot: ProtectedCommittedExecutionSnapshot,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    try:
        run = TrustedRunDocument.model_validate(snapshot.run)
        report = ClientReportPayload.model_validate(snapshot.report)
    except ValueError as exc:
        raise TrustedRunError(
            f"protected execution semantics are invalid: {exc}"
        ) from exc
    if run.run_id != snapshot.run_id or report.run_id != snapshot.run_id:
        raise TrustedRunError("protected execution semantic run identity drift")
    records = [
        record
        for record in snapshot.evidence
        if record.evidence_id != "report-source"
        and record.producer != "protected-report-materializer"
    ]
    evidence_ids = {record.evidence_id for record in records}
    if len(evidence_ids) != len(records):
        raise TrustedRunError("protected execution evidence identity drift")
    tracked_files = {record.relative_path: record.payload for record in records}
    if len(tracked_files) != len(records):
        raise TrustedRunError("protected execution evidence path drift")
    report_payload = report.model_dump(mode="json")
    try:
        for payload in tracked_files.values():
            _validate_derived_publication_payload(payload)
        _validate_derived_publication_payload(report_payload)
        prewrite_rollups = {
            "coverage_complete": True,
            "execution_complete": True,
            "requirements_met": (
                all(row.outcome == "PASS" for row in run.criteria)
                and all(row.outcome == "PASS" for row in run.executions)
                and not run.open_p0_p1
            ),
        }
        validate_redacted_text(_render_report(report, prewrite_rollups).decode("utf-8"))
    except EvidenceError as exc:
        raise TrustedRunError(
            f"derived publication privacy validation failed: {exc}"
        ) from exc
    report_payload_sha256 = _sha256(_canonical_bytes(report_payload))
    report_snapshot_digest = _verified_report_snapshot_digest(report)
    report_source = ReportSourceArtifact(
        schema_version="noor-e2e-report-source/v2",
        registry_id=registry.registry_id,
        report_sections_digest=_report_sections_digest(report),
        report_payload_sha256=report_payload_sha256,
        verified_snapshot_digest=report_snapshot_digest,
    )
    report_source_payload = report_source.model_dump(mode="json")
    tracked_files["evidence/report-source.json"] = report_source_payload
    entries = [
        EvidenceIndexEntry(
            evidence_id=record.evidence_id,
            relative_path=record.relative_path,
            sha256=_sha256(_canonical_bytes(record.payload)),
            producer=record.producer,
        )
        for record in records
    ]
    report_source_sha256 = _sha256(_canonical_bytes(report_source_payload))
    entries.append(
        EvidenceIndexEntry(
            evidence_id="report-source",
            relative_path="evidence/report-source.json",
            sha256=report_source_sha256,
            producer="protected-report-materializer",
        )
    )
    index = EvidenceIndex(
        schema_version="noor-e2e-evidence-index/v2",
        run_id=snapshot.run_id,
        entries=tuple(entries),
    )
    index_payload = index.model_dump(mode="json")
    index_sha256 = _sha256(_canonical_bytes(index_payload))
    run_payload = {
        **run.model_dump(mode="json"),
        "evidence_index_digest": index_sha256,
        "report_payload_digest": report_payload_sha256,
    }
    run = TrustedRunDocument.model_validate(run_payload)
    run_payload = run.model_dump(mode="json")
    tracked_files.update(
        {
            "registry/run.json": run_payload,
            "registry/evidence-index.json": index_payload,
            "registry/report-payload.json": report_payload,
        }
    )
    try:
        for payload in tracked_files.values():
            _validate_derived_publication_payload(payload)
    except EvidenceError as exc:
        raise TrustedRunError(
            f"derived publication privacy validation failed: {exc}"
        ) from exc
    authorization_digest = canonical_digest(run.authorization.model_dump(mode="json"))
    attempts_by_execution: dict[str, tuple[CommittedExecutionArtifact, str]] = {}
    for entry in entries:
        if entry.producer != "protected-attempt-committer":
            continue
        attempt = CommittedExecutionArtifact.model_validate(
            tracked_files[entry.relative_path]
        )
        _validate_attempt_phase_chain(attempt)
        attempts_by_execution[attempt.execution_id] = (attempt, entry.sha256)
    if set(attempts_by_execution) != set(snapshot.execution_ids):
        raise TrustedRunError("protected execution attempt scope drift")
    protected_files: dict[str, dict[str, Any]] = {}
    for execution_id in snapshot.execution_ids:
        attempt, tracked_sha256 = attempts_by_execution[execution_id]
        commit_payload = snapshot.attempt_commits.get(execution_id)
        if commit_payload is None:
            raise TrustedRunError("protected execution attempt commit is missing")
        commit_bytes = _canonical_bytes(commit_payload)
        if _sha256(commit_bytes) != attempt.protected_commit_digest:
            raise TrustedRunError("protected execution attempt commit digest drift")
        _validate_protected_attempt_commit(
            commit_bytes,
            artifact=attempt,
            authorization_digest=authorization_digest,
        )
        protected_files[attempt.protected_commit_ref] = commit_payload
        protected_files[f"producer-receipts/attempts/{execution_id}.json"] = (
            AttemptProducerReceipt(
                schema_version="noor-e2e-attempt-producer-receipt/v2",
                registry_id=registry.registry_id,
                run_id=snapshot.run_id,
                execution_id=execution_id,
                attempt_kind=attempt.attempt_kind,
                attempt_digest=attempt.attempt_digest,
                authorization_digest=authorization_digest,
                semantic_digest=attempt.semantic_digest,
                raw_digest=attempt.raw_digest,
                tracked_digest=attempt.tracked_digest,
                phase_head_digest=attempt.phase_head_digest,
                tracked_sha256=tracked_sha256,
                protected_commit_digest=attempt.protected_commit_digest,
            ).model_dump(mode="json")
        )
    protected_files["producer-receipts/report-source.json"] = ReportProducerReceipt(
        schema_version="noor-e2e-report-producer-receipt/v2",
        registry_id=registry.registry_id,
        tracked_sha256=report_source_sha256,
        report_sections_digest=report_source.report_sections_digest,
        report_payload_sha256=report_payload_sha256,
        verified_snapshot_digest=report_snapshot_digest,
    ).model_dump(mode="json")
    if isinstance(snapshot, ProtectedCommittedExecutionSnapshot):
        _validate_snapshot_readback_artifacts(
            registry,
            run,
            snapshot.collector_artifacts,
            current_time=datetime.now(UTC),
        )
    protected_files.update(snapshot.collector_artifacts)
    typed_attempts = {
        execution_id: value[0] for execution_id, value in attempts_by_execution.items()
    }
    _validate_gate_artifacts(
        registry,
        run,
        typed_attempts,
        snapshot.gate_artifacts,
        current_time=datetime.now(UTC),
    )
    protected_files.update(snapshot.gate_artifacts)
    expected_transcript_paths = {"transcripts/manifest.json"}
    expected_manifest_turns = []
    for turn in report.turns:
        transcript_relative = (
            f"transcripts/{turn.execution_id}/{turn.attempt_id}/{turn.turn_id}.json"
        )
        receipt_relative = (
            f"producer-receipts/transcripts/{turn.execution_id}/"
            f"{turn.attempt_id}/{turn.turn_id}.json"
        )
        expected_transcript_paths.update((transcript_relative, receipt_relative))
        expected_manifest_turns.append(
            (
                turn.execution_id,
                turn.attempt_id,
                turn.turn_id,
                turn.transcript_digest,
                turn.producer_receipt_digest,
            )
        )
        attempt_entry = attempts_by_execution.get(turn.execution_id)
        if attempt_entry is None:
            raise TrustedRunError("protected transcript attempt is missing")
        attempt = attempt_entry[0]
        try:
            transcript = ProtectedTranscriptArtifact.model_validate(
                snapshot.transcript_artifacts[transcript_relative]
            )
            transcript_receipt = TranscriptProducerReceipt.model_validate(
                snapshot.transcript_artifacts[receipt_relative]
            )
        except (KeyError, ValueError) as exc:
            raise TrustedRunError(
                "protected transcript snapshot artifact is invalid"
            ) from exc
        normalized_turn = turn.model_dump(
            mode="json",
            exclude={"transcript_digest", "producer_receipt_digest"},
        )
        if (
            _sha256(
                _canonical_bytes(snapshot.transcript_artifacts[transcript_relative])
            )
            != turn.transcript_digest
            or _sha256(
                _canonical_bytes(snapshot.transcript_artifacts[receipt_relative])
            )
            != turn.producer_receipt_digest
            or transcript.registry_id != registry.registry_id
            or transcript.run_id != snapshot.run_id
            or transcript.execution_id != turn.execution_id
            or transcript.attempt_id != turn.attempt_id
            or transcript.turn_id != turn.turn_id
            or transcript.turn != normalized_turn
            or transcript_receipt.registry_id != registry.registry_id
            or transcript_receipt.run_id != snapshot.run_id
            or transcript_receipt.execution_id != turn.execution_id
            or transcript_receipt.attempt_id != turn.attempt_id
            or transcript_receipt.turn_id != turn.turn_id
            or transcript_receipt.transcript_sha256 != turn.transcript_digest
            or transcript_receipt.authorization_digest != authorization_digest
            or transcript_receipt.attempt_digest != attempt.attempt_digest
            or transcript_receipt.attempt_phase_head_digest != attempt.phase_head_digest
        ):
            raise TrustedRunError("protected transcript snapshot binding drift")
    try:
        transcript_manifest = ProtectedTranscriptManifest.model_validate(
            snapshot.transcript_artifacts["transcripts/manifest.json"]
        )
    except (KeyError, ValueError) as exc:
        raise TrustedRunError(
            "protected transcript snapshot manifest is invalid"
        ) from exc
    if (
        set(snapshot.transcript_artifacts) != expected_transcript_paths
        or transcript_manifest.registry_id != registry.registry_id
        or transcript_manifest.run_id != snapshot.run_id
        or transcript_manifest.ordered_turns != tuple(expected_manifest_turns)
        or len(set(transcript_manifest.ordered_turns))
        != len(transcript_manifest.ordered_turns)
    ):
        raise TrustedRunError("protected transcript snapshot ordered path-set drift")
    for relative, payload in snapshot.transcript_artifacts.items():
        protected_files[relative] = payload
    protected_files["registry/anchor.json"] = TrustedRunAnchor(
        schema_version="noor-e2e-trusted-run-anchor/v2",
        run_id=snapshot.run_id,
        policy_digest=registry.compiled_policy.policy_digest,
        compiled_plan_digest=registry.compiled_plan.plan_digest,
        authorization_digest=authorization_digest,
        baseline_digest=run.baseline.content_digest,
        final_digest=run.final.content_digest,
        run_document_sha256=_sha256(_canonical_bytes(run_payload)),
        evidence_index_sha256=index_sha256,
        report_payload_sha256=report_payload_sha256,
        criterion_ids=tuple(row.criterion_id for row in run.criteria),
        execution_ids=tuple(row.execution_id for row in run.executions),
        phase_journal_head_digest=run.final.causal_event_digest,
        attempt_chain_heads={
            execution_id: attempts_by_execution[execution_id][0].phase_head_digest
            for execution_id in snapshot.execution_ids
        },
    ).model_dump(mode="json")
    return tracked_files, protected_files


def _finalize_verified_run(registry: Any, run_id: str) -> None:
    """Derive and commit one run from protected committed execution semantics."""

    if not run_id or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-._"
        for character in run_id.lower()
    ):
        raise TrustedRunError("finalization run identity is unsafe")
    snapshot = _load_protected_execution_snapshot(registry, run_id)
    tracked_files, protected_files = _derive_publication(registry, snapshot)
    tracked_root = (
        registry.repo_root / ".codex" / "stages" / "tj-ee5f" / "results" / run_id
    )
    protected_parent = _published_protected_root(registry)
    protected_root = protected_parent / run_id
    if protected_root.exists() and (protected_root / "final-commit.json").is_file():
        try:
            _load_verified_run(registry, run_id)
        except TrustedRunError:
            pass
        else:
            return
    if tracked_root.exists() or protected_root.exists():
        shutil.rmtree(tracked_root, ignore_errors=True)
        shutil.rmtree(protected_root, ignore_errors=True)
    tracked_root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    protected_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    for parent in (tracked_root.parent, protected_parent):
        for orphan in parent.glob(f".{run_id}.*"):
            if orphan.is_dir() and not orphan.is_symlink():
                shutil.rmtree(orphan)
    tracked_staging = Path(
        tempfile.mkdtemp(prefix=f".{run_id}.", dir=tracked_root.parent)
    )
    protected_staging = Path(
        tempfile.mkdtemp(prefix=f".{run_id}.", dir=protected_parent)
    )
    try:
        _write_snapshot_tree(tracked_staging, tracked_files)
        _write_snapshot_tree(protected_staging, protected_files)
        _fsync_directory(tracked_staging)
        _fsync_directory(protected_staging)
        tracked_tree_digest = _tree_digest(tracked_staging)
        protected_tree_digest = _tree_digest(protected_staging)
        os.rename(tracked_staging, tracked_root)
        os.rename(protected_staging, protected_root)
        _fsync_directory(tracked_root.parent)
        _fsync_directory(protected_parent)
        _write_atomic_final_commit(
            protected_root,
            PublishedRunCommit(
                schema_version="noor-e2e-published-run-commit/v2",
                status="committed",
                run_id=run_id,
                registry_id=registry.registry_id,
                snapshot_digest=snapshot.snapshot_digest,
                tracked_tree_digest=tracked_tree_digest,
                protected_tree_digest=protected_tree_digest,
            ),
        )
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
        registry.repo_root / ".codex" / "stages" / "tj-ee5f" / "results" / run_id
    )
    protected_root = _published_protected_root(registry) / run_id
    try:
        final_commit = PublishedRunCommit.model_validate(
            _parse_json(
                _read_file(
                    protected_root,
                    "final-commit.json",
                    protected=True,
                ),
                "protected final commit marker",
            )
        )
    except (TrustedRunError, ValueError) as exc:
        raise TrustedRunError(
            f"protected final commit marker is invalid: {exc}"
        ) from exc
    if (
        final_commit.run_id != run_id
        or final_commit.registry_id != registry.registry_id
        or final_commit.tracked_tree_digest != _tree_digest(tracked_root)
        or final_commit.protected_tree_digest
        != _tree_digest(
            protected_root,
            exclude=frozenset({"final-commit.json"}),
        )
    ):
        raise TrustedRunError("protected final commit marker binding drift")
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

    validated_authorization = validate_execution_authorization(
        run.authorization,
        policy=registry.compiled_policy,
        plan=registry.compiled_plan,
        registry_id=registry.registry_id,
    )
    if (
        validated_authorization.task1_authorization_digest
        != registry.task1_authorization_digest
        or validated_authorization.task1_input_digests != registry.task1_input_digests
    ):
        raise TrustedRunError("authorization Task 1 immutable bundle digest drift")
    _validate_readback_contract(run)
    try:
        final_readback_artifacts = {
            relative: _parse_json(
                _read_file(protected_root, relative, protected=True),
                "protected final readback producer artifact",
            )
            for relative in (
                "collector-artifacts/final-readback.json",
                "producer-receipts/final-readback.json",
            )
        }
    except TrustedRunError as exc:
        raise TrustedRunError(
            f"protected final readback producer receipt is missing: {exc}"
        ) from exc
    _, independent_inventory_digest = _validate_final_readback_artifacts(
        registry,
        run,
        final_readback_artifacts,
        current_time=datetime.now(UTC),
    )
    if run.final_inventory_digest != independent_inventory_digest:
        raise TrustedRunError(
            "trusted ledger inventory differs from independent collector commit"
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
    attempts_by_execution: dict[str, CommittedExecutionArtifact] = {}
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
            or receipt.attempt_kind != attempt.attempt_kind
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
        attempts_by_execution[identity] = attempt
        report_execution = report_executions[identity]
        if (
            report_execution.outcome != execution_row.outcome
            or report_execution.attempt_ref != execution_row.attempt_ref
            or report_execution.evidence_refs != execution_row.evidence_refs
        ):
            raise TrustedRunError(f"typed report execution binding drift: {identity}")

    expected_gate_paths = {
        relative
        for execution_id, attempt in attempts_by_execution.items()
        if attempt.attempt_kind == "gate"
        for relative in (
            f"gate-evidence/{execution_id}.json",
            f"producer-receipts/gates/{execution_id}.json",
        )
    }
    actual_gate_paths = _tree_relative_files(
        protected_root,
        prefixes=(
            "gate-attempts/",
            "gate-evidence/",
            "producer-receipts/gates/",
            "recorded-gates/",
        ),
    )
    if actual_gate_paths != expected_gate_paths:
        raise TrustedRunError("typed gate published artifact path-set drift")
    gate_artifacts = {
        relative: _parse_json(
            _read_file(protected_root, relative, protected=True),
            "typed gate protected producer artifact",
        )
        for relative in actual_gate_paths
    }
    _validate_gate_artifacts(
        registry,
        run,
        attempts_by_execution,
        gate_artifacts,
        current_time=datetime.now(UTC),
    )

    scenario_ids = tuple(registry.compiled_policy.scenarios)
    try:
        transcript_manifest = ProtectedTranscriptManifest.model_validate(
            _parse_json(
                _read_file(
                    protected_root,
                    "transcripts/manifest.json",
                    protected=True,
                ),
                "protected transcript manifest",
            )
        )
    except (TrustedRunError, ValueError) as exc:
        raise TrustedRunError("protected transcript manifest is invalid") from exc
    expected_manifest_turns = tuple(
        (
            turn.execution_id,
            turn.attempt_id,
            turn.turn_id,
            turn.transcript_digest,
            turn.producer_receipt_digest,
        )
        for turn in report.turns
    )
    expected_transcript_paths = {"transcripts/manifest.json"}
    for turn in report.turns:
        expected_transcript_paths.add(
            f"transcripts/{turn.execution_id}/{turn.attempt_id}/{turn.turn_id}.json"
        )
        expected_transcript_paths.add(
            f"producer-receipts/transcripts/{turn.execution_id}/"
            f"{turn.attempt_id}/{turn.turn_id}.json"
        )
    actual_transcript_paths = _tree_relative_files(
        protected_root,
        prefixes=("transcripts/", "producer-receipts/transcripts/"),
    )
    if (
        transcript_manifest.registry_id != registry.registry_id
        or transcript_manifest.run_id != run.run_id
        or transcript_manifest.ordered_turns != expected_manifest_turns
        or len(set(transcript_manifest.ordered_turns))
        != len(transcript_manifest.ordered_turns)
        or actual_transcript_paths != expected_transcript_paths
    ):
        raise TrustedRunError("protected transcript ordered-set binding drift")
    turns_by_execution: dict[str, list[TurnReport]] = {
        identity: [] for identity in scenario_ids
    }
    previous_scenario_position = -1
    for turn in report.turns:
        if turn.execution_id not in turns_by_execution:
            raise TrustedRunError("typed report turn has phantom execution")
        position = scenario_ids.index(turn.execution_id)
        if position < previous_scenario_position:
            raise TrustedRunError("typed report turn ordering drift")
        previous_scenario_position = position
        turns_by_execution[turn.execution_id].append(turn)
        execution_row = executions[turn.execution_id]
        if (
            turn.attempt_id != execution_row.attempt_ref
            or execution_row.attempt_ref not in turn.evidence_refs
            or not set(turn.evidence_refs) <= set(evidence)
            or not turn.transcript_digest
            or not turn.producer_receipt_digest
        ):
            raise TrustedRunError(
                f"typed report turn evidence binding drift: {turn.execution_id}"
            )
        transcript_relative = (
            f"transcripts/{turn.execution_id}/{turn.attempt_id}/{turn.turn_id}.json"
        )
        receipt_relative = (
            f"producer-receipts/transcripts/{turn.execution_id}/"
            f"{turn.attempt_id}/{turn.turn_id}.json"
        )
        try:
            transcript_payload = _read_file(
                protected_root,
                transcript_relative,
                protected=True,
            )
            transcript = ProtectedTranscriptArtifact.model_validate(
                _parse_json(transcript_payload, "protected transcript artifact")
            )
            receipt_payload = _read_file(
                protected_root,
                receipt_relative,
                protected=True,
            )
            transcript_receipt = TranscriptProducerReceipt.model_validate(
                _parse_json(receipt_payload, "protected transcript receipt")
            )
        except (TrustedRunError, ValueError) as exc:
            raise TrustedRunError(
                f"protected transcript/producer receipt is invalid: {turn.execution_id}"
            ) from exc
        reported_turn = turn.model_dump(
            mode="json",
            exclude={"transcript_digest", "producer_receipt_digest"},
        )
        attempt = attempts_by_execution[turn.execution_id]
        if (
            _sha256(transcript_payload) != turn.transcript_digest
            or _sha256(receipt_payload) != turn.producer_receipt_digest
            or transcript.registry_id != registry.registry_id
            or transcript.run_id != run.run_id
            or transcript.execution_id != turn.execution_id
            or transcript.attempt_id != turn.attempt_id
            or transcript.turn_id != turn.turn_id
            or transcript.turn != reported_turn
            or transcript_receipt.registry_id != registry.registry_id
            or transcript_receipt.run_id != run.run_id
            or transcript_receipt.execution_id != turn.execution_id
            or transcript_receipt.attempt_id != turn.attempt_id
            or transcript_receipt.turn_id != turn.turn_id
            or transcript_receipt.transcript_sha256 != turn.transcript_digest
            or transcript_receipt.authorization_digest != authorization_digest
            or transcript_receipt.attempt_digest != attempt.attempt_digest
            or transcript_receipt.attempt_phase_head_digest != attempt.phase_head_digest
        ):
            raise TrustedRunError(
                f"protected transcript field binding drift: {turn.execution_id}"
            )
    for execution_id, turns in turns_by_execution.items():
        execution_row = executions[execution_id]
        committed_attempt = attempts_by_execution[execution_id]
        if len({(turn.attempt_id, turn.turn_id) for turn in turns}) != len(turns):
            raise TrustedRunError("typed report duplicate transcript turn")
        if turns and committed_attempt.attempt_kind != "executed":
            raise TrustedRunError("gate attempt cannot contain transcript turns")
        if not turns and committed_attempt.attempt_kind != "gate":
            raise TrustedRunError(
                "executed scenario requires committed transcript turns"
            )
        if not turns and execution_row.outcome == "EXCLUDED_BY_CLIENT":
            criterion_outcomes = [
                row.outcome
                for row in criteria.values()
                if execution_id
                in registry.compiled_plan.criteria[row.criterion_id].obligation_ids
            ]
            if "EXCLUDED_BY_CLIENT" not in criterion_outcomes:
                raise TrustedRunError("zero-turn client exclusion lacks gate authority")

    if run.side_effect_ledger_digest != canonical_digest(
        [item.model_dump(mode="json") for item in report.side_effects]
    ) or run.final_inventory_digest != canonical_digest(run.final.inventory):
        raise TrustedRunError("computed side-effect ledger/inventory digest drift")
    try:
        retention_authorities = {}
        for authority in run.authorization.side_effect_authority.retention_authorities:
            retention_payload = authority.model_dump(mode="json")
            retention_authorities[authority.artifact_id] = {
                **retention_payload,
                "authority_digest": canonical_digest(retention_payload),
            }
        validate_side_effect_closeout(
            [
                {
                    "artifact_id": item.artifact_id,
                    "scenario_id": item.scenario_id,
                    "subsystem": item.subsystem,
                    "artifact_type": item.artifact_type,
                    "creation_path": "application-authorized",
                    "cleanup_owner": item.owner,
                    "cleanup_authority": item.cleanup_authority,
                    "baseline_readback": item.baseline,
                    "expected_effect": item.expected_effect,
                    "follow_up_suppressed": item.follow_up_suppressed,
                    "final_readback": item.final,
                    "disposition": item.disposition,
                    "retention_pre_authorized": item.retention_pre_authorized,
                    "retention_owner": item.retention_owner,
                    "retention_authority_digest": item.retention_authority_digest,
                    "retention_expires_at": item.retention_expires_at,
                    "final_disposition_date": item.final_disposition_date,
                }
                for item in report.side_effects
            ],
            observed_inventory=run.final.inventory,
            authorized_cleanup_owner=(
                run.authorization.side_effect_authority.cleanup_owner
            ),
            authorized_cleanup_authority=(
                run.authorization.side_effect_authority.cleanup_authority
            ),
            authorized_retentions=retention_authorities,
            current_time=datetime.now(UTC),
        )
    except EvidenceError as exc:
        raise TrustedRunError(f"computed side-effect closeout failed: {exc}") from exc
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
    context = VerifiedEvidenceContext(
        authorization_digests=frozenset({authorization_digest}),
        preflight_collectors=frozenset(
            {
                (
                    run.authorization.preflight_digest,
                    run.authorization.readback_collector_digest,
                )
            }
        ),
        readback_digests=frozenset(
            {run.baseline.content_digest, run.final.content_digest}
        ),
        attempt_digests=frozenset(verified_attempt_digests),
    )

    rollups = {
        "coverage_complete": True,
        "execution_complete": True,
        "requirements_met": (
            all(row.outcome == "PASS" for row in criteria.values())
            and all(row.outcome == "PASS" for row in executions.values())
            and not run.open_p0_p1
            and not run.open_p0_p1
        ),
    }
    rendered = _render_report(report, rollups)
    try:
        validate_redacted_text(rendered.decode("utf-8"))
    except EvidenceError as exc:
        raise TrustedRunError(f"final report privacy validation failed: {exc}") from exc
    return VerifiedRun(
        rollups=rollups,
        report_bytes=rendered,
        evidence_context=context,
    )
