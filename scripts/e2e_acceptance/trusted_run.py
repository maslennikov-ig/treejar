"""Load one anchored acceptance run and render its canonical client report."""

from __future__ import annotations

import hashlib
import json
import os
import stat
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
)
from scripts.e2e_acceptance.policy import (
    PolicyValidationError,
    ReadbackObservation,
)
from scripts.e2e_acceptance.schemas import EvidenceMode


class TrustedRunError(PolicyValidationError):
    """A tracked run and its protected anchor do not form one trusted result."""


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


class EvaluatorReport(_StrictModel):
    model: str
    reasoning_effort: str
    seed: int
    config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


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


class DefectReport(_StrictModel):
    defect_id: str
    root_cause: str
    violated_invariant: str
    fix: str
    retest: str
    checksum_refs: tuple[str, ...]


class ClientReportPayload(_StrictModel):
    schema_version: Literal["noor-e2e-client-report/v2"]
    run_id: str
    title: str
    generated_at: datetime
    identity: RuntimeIdentityReport
    tester: EvaluatorReport
    judge: EvaluatorReport
    turns: tuple[TurnReport, ...]
    criteria: tuple[ReportCriterion, ...] = Field(min_length=1)
    side_effects: tuple[SideEffectReport, ...]
    latency: LatencyReport
    limitations: tuple[str, ...]
    external_gates: tuple[str, ...]
    defects: tuple[DefectReport, ...]


class VerifiedRun(_StrictModel):
    rollups: dict[str, bool]
    report_bytes: bytes


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
    if row.outcome != "PASS":
        return True
    if row.evidence_mode is EvidenceMode.FRESH:
        return all(
            item.get("status") == "passed"
            and isinstance(item.get("freshness_identity"), dict)
            and bool(item["freshness_identity"])
            for item in objects
        )
    if row.evidence_mode is EvidenceMode.REUSED_EXACT:
        return all(
            item.get("status") == "passed"
            and isinstance(item.get("reused_exact_identity"), dict)
            and bool(item["reused_exact_identity"])
            for item in objects
        )
    return all(
        item.get("status") == "passed"
        and item.get("external_gate_resolution") == "implemented"
        for item in objects
    )


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


def load_verified_run(
    registry: Any,
    tracked_root: Path,
    protected_root: Path,
) -> VerifiedRun:
    """Verify fixed run artifacts against the registry and protected anchor."""

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
        aggregate = aggregate_criterion_outcome(
            plan,
            criterion_row.obligation_outcomes,
            valid_exclusions=frozenset(
                key
                for key, outcome in criterion_row.obligation_outcomes.items()
                if outcome == "EXCLUDED_BY_CLIENT"
                and plan.evidence_mode is EvidenceMode.EXTERNAL_GATE
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

    for identity, execution_row in executions.items():
        if not set(execution_row.evidence_refs) <= set(evidence):
            raise TrustedRunError(f"execution evidence reference drift: {identity}")
    try:
        validate_redacted_payload(report.model_dump(mode="json"))
    except EvidenceError as exc:
        raise TrustedRunError(f"report privacy validation failed: {exc}") from exc

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
