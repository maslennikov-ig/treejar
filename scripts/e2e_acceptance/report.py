"""Russian client-report source and structured acceptance rollups."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.e2e_acceptance.evidence import (
    EvidenceError,
    load_verified_evidence_index,
    validate_redacted_payload,
    validate_redacted_text,
)
from scripts.e2e_acceptance.schemas import EvidenceMode, TraceabilityManifest


class ReportError(ValueError):
    """Report input is incomplete or contains restricted material."""


def calculate_rollups(
    results: Mapping[str, object],
    *,
    evidence_root: Path,
    traceability: TraceabilityManifest,
) -> dict[str, bool]:
    try:
        evidence = load_verified_evidence_index(evidence_root)
    except EvidenceError as exc:
        raise ReportError(str(exc)) from exc
    criteria = results.get("criteria")
    if not isinstance(criteria, list):
        raise ReportError("criteria results are required")
    criterion_rows = [item for item in criteria if isinstance(item, Mapping)]
    traceability_by_id = {item.criterion_id: item for item in traceability.criteria}
    scope_ids_raw = results.get("scope_criterion_ids")
    if not isinstance(scope_ids_raw, list) or not all(
        isinstance(item, str) and item for item in scope_ids_raw
    ):
        raise ReportError("immutable scope criterion IDs are required")
    result_ids = {
        str(item.get("criterion_id"))
        for item in criterion_rows
        if item.get("criterion_id")
    }
    coverage_complete = (
        len(scope_ids_raw) == len(set(scope_ids_raw))
        and len(criterion_rows) == len(result_ids)
        and set(scope_ids_raw) == result_ids
        and all(
            item.get("criterion_id")
            and item.get("outcome")
            and item.get("evidence_mode")
            and "evidence_refs" in item
            and item.get("criterion_id") in traceability_by_id
            and item.get("evidence_mode")
            == traceability_by_id[str(item.get("criterion_id"))].evidence_mode.value
            for item in criterion_rows
        )
    )
    executions = results.get("executions")
    if not isinstance(executions, list) or not all(
        isinstance(item, Mapping) for item in executions
    ):
        raise ReportError("scenario/evidence-block execution results are required")
    planned_execution_ids = results.get("planned_execution_ids")
    if not isinstance(planned_execution_ids, list) or not all(
        isinstance(item, str) and item for item in planned_execution_ids
    ):
        raise ReportError("planned scenario/evidence-block IDs are required")
    execution_ids = {
        str(item.get("execution_id")) for item in executions if item.get("execution_id")
    }
    authorization_ref = results.get("authorization_evidence_ref")
    authorization_evidence = (
        evidence.get(authorization_ref) if isinstance(authorization_ref, str) else None
    )
    authorized_execution_ids = (
        set(authorization_evidence.get("authorized_execution_ids", []))
        if isinstance(authorization_evidence, Mapping)
        and isinstance(authorization_evidence.get("authorized_execution_ids"), list)
        else set()
    )
    execution_complete = (
        coverage_complete
        and len(planned_execution_ids) == len(set(planned_execution_ids))
        and len(executions) == len(execution_ids)
        and set(planned_execution_ids) == execution_ids
        and all(
            item.get("outcome") in {"PASS", "FAIL", "BLOCKED", "EXCLUDED_BY_CLIENT"}
            and (
                item.get("outcome") != "PASS"
                or item.get("execution_id") in authorized_execution_ids
            )
            for item in executions
        )
    )
    run_identity_ref = results.get("run_identity_evidence_ref")
    run_identity_evidence = (
        evidence.get(run_identity_ref) if isinstance(run_identity_ref, str) else None
    )
    authorization_verified = (
        isinstance(authorization_evidence, Mapping)
        and authorization_evidence.get("status") == "passed"
        and isinstance(authorization_evidence.get("manifest_digest"), str)
        and len(str(authorization_evidence.get("manifest_digest"))) == 64
        and isinstance(authorization_evidence.get("scenario_binding_digest"), str)
        and len(str(authorization_evidence.get("scenario_binding_digest"))) == 64
    )
    run_identity_verified = (
        isinstance(run_identity_evidence, Mapping)
        and run_identity_evidence.get("status") == "passed"
        and run_identity_evidence.get("expected_equals_actual") is True
    )

    def passing_criterion_has_proof(item: Mapping[str, object]) -> bool:
        if item.get("outcome") != "PASS":
            return True
        refs = item.get("evidence_refs")
        criterion_id = item.get("criterion_id")
        contract = (
            traceability_by_id.get(str(criterion_id))
            if criterion_id is not None
            else None
        )
        if (
            not isinstance(refs, list)
            or not refs
            or not all(isinstance(ref, str) and ref in evidence for ref in refs)
            or contract is None
            or item.get("evidence_mode") != contract.evidence_mode.value
        ):
            return False
        if contract.evidence_mode is EvidenceMode.FRESH:
            return all(
                isinstance(evidence[str(ref)].get("freshness_identity"), Mapping)
                and bool(evidence[str(ref)].get("freshness_identity"))
                for ref in refs
            )
        if contract.evidence_mode is EvidenceMode.REUSED_EXACT:
            return all(
                bool(evidence[str(ref)].get("reused_exact_identity")) for ref in refs
            )
        if contract.evidence_mode is EvidenceMode.EXTERNAL_GATE:
            return (
                contract.dependency is not None
                and contract.dependency.status == "implemented"
            )
        return False

    requirements_met = (
        execution_complete
        and all(item.get("outcome") == "PASS" for item in criterion_rows)
        and all(passing_criterion_has_proof(item) for item in criterion_rows)
        and authorization_verified
        and run_identity_verified
        and not results.get("open_p0_p1")
        and results.get("side_effect_closeout") == "passed"
    )
    return {
        "coverage_complete": coverage_complete,
        "execution_complete": execution_complete,
        "requirements_met": requirements_met,
    }


def build_defect_draft(
    *,
    scenario_id: str,
    severity: str,
    summary: str,
    expected: str,
    actual: str,
    evidence_path: str,
    criterion_ids: Sequence[str],
    historical_regressions: Sequence[str],
) -> dict[str, object]:
    if severity not in {"P0", "P1", "P2", "P3"}:
        raise ReportError(f"invalid defect severity: {severity}")
    draft: dict[str, object] = {
        "schema_version": "noor-e2e-defect-draft/v1",
        "parent": "tj-ee5f",
        "discovered_from": "tj-ee5f.1",
        "severity": severity,
        "summary": summary,
        "minimal_reproduction": {"scenario_id": scenario_id},
        "expected": expected,
        "actual": actual,
        "evidence_path": evidence_path,
        "customer_business_impact": "Requires acceptance-owner assessment.",
        "severity_rationale": f"Classified {severity} under the accepted design.",
        "acceptance_criteria": list(criterion_ids),
        "historical_regressions": list(historical_regressions),
        "status": "draft_not_created_in_beads",
    }
    try:
        validate_redacted_payload(draft)
    except EvidenceError as exc:
        raise ReportError(str(exc)) from exc
    return draft


def _yes_no(value: bool) -> str:
    return "да" if value else "нет"


def _as_mappings(value: object, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(
        isinstance(item, Mapping) for item in value
    ):
        raise ReportError(f"{label} must be a list of objects")
    return list(value)


def _write_report_exclusive(output_path: Path, payload: bytes) -> None:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None or os.open not in os.supports_dir_fd:
        raise ReportError(
            "safe report output requires O_NOFOLLOW, O_DIRECTORY, and dir_fd"
        )
    parent_fd = -1
    file_fd = -1
    try:
        parent_fd = os.open(
            output_path.parent,
            os.O_RDONLY | nofollow | directory | getattr(os, "O_CLOEXEC", 0),
        )
        file_fd = os.open(
            output_path.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | nofollow
            | getattr(os, "O_CLOEXEC", 0),
            0o644,
            dir_fd=parent_fd,
        )
        os.fchmod(file_fd, 0o644)
        with os.fdopen(file_fd, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(file_fd)
        os.fsync(parent_fd)
    except FileExistsError as exc:
        raise ReportError(f"report output already exists: {output_path}") from exc
    except OSError as exc:
        raise ReportError(f"cannot safely create report output: {exc}") from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def render_client_report(
    results: Mapping[str, object],
    output_path: Path,
    *,
    evidence_root: Path,
    traceability: TraceabilityManifest,
) -> Path:
    try:
        validate_redacted_payload(results)
    except EvidenceError as exc:
        raise ReportError(str(exc)) from exc
    runtime = results.get("runtime_identity")
    if not isinstance(runtime, Mapping):
        raise ReportError("runtime identity is required")
    scenarios = _as_mappings(results.get("scenarios"), "scenarios")
    defects = _as_mappings(results.get("defects", []), "defects")
    rollups = calculate_rollups(
        results,
        evidence_root=evidence_root,
        traceability=traceability,
    )

    lines = [
        "# Приёмочное тестирование Noor",
        "",
        f"Идентификатор запуска: `{results.get('run_id', 'не указан')}`.",
        "",
        "## Среда и методика",
        "",
        f"- Commit репозитория: `{runtime.get('repository_commit', 'не указан')}`",
        f"- Релиз: `{runtime.get('deployed_release_sha', 'не указан')}`",
        f"- CI run: `{runtime.get('ci_run_id', 'не указан')}`",
        f"- Версия приложения: `{runtime.get('app_version', 'не указана')}`",
        f"- Migration head: `{runtime.get('migration_head', 'не указан')}`",
        f"- Endpoint: `{runtime.get('endpoint', 'не указан')}`",
        f"- Основная модель: `{runtime.get('main_model', 'не указана')}`",
        f"- Быстрая модель: `{runtime.get('fast_model', 'не указана')}`",
        "- Проверка сочетает детерминированные правила и ограниченную оценку агента.",
        "- Все приведённые диалоги взяты только из редактированного слоя доказательств.",
        "",
        f"- Latency summary: `{results.get('latency_summary', {})}`",
        "",
        "## Ограничения и внешние gates",
        "",
        f"- Ограничения: `{results.get('limitations', [])}`",
        f"- Внешние gates: `{results.get('external_gates', [])}`",
        "",
        "## Критерии и доказательства",
        "",
        "| Критерий | Outcome | Режим | Доказательства |",
        "|---|---|---|---|",
    ]
    for criterion in _as_mappings(results.get("criteria"), "criteria"):
        refs = criterion.get("evidence_refs", [])
        lines.append(
            f"| {criterion.get('criterion_id', '')} | "
            f"{criterion.get('outcome', '')} | "
            f"{criterion.get('evidence_mode', '')} | {refs} |"
        )
    lines.extend(
        [
            "",
            "## Сценарии и точные диалоги",
            "",
        ]
    )
    for scenario in scenarios:
        lines.extend(
            [
                f"### {scenario.get('scenario_id', 'неизвестный сценарий')}",
                "",
                f"Статус: `{scenario.get('status', 'не указан')}`.",
                "",
                f"Ожидалось: {scenario.get('expected', 'не указано')}",
                "",
                f"Фактически: {scenario.get('actual', 'не указано')}",
                "",
            ]
        )
        deviations = scenario.get("adaptive_deviations", [])
        lines.extend(
            [
                f"Tester config: `{scenario.get('tester', {})}`.",
                "",
                f"Judge config/reasoning: `{scenario.get('judge', {})}`.",
                "",
                f"Adaptive deviations: `{deviations}`.",
                "",
                f"Evaluator result/reasoning: `{scenario.get('evaluation', {})}`.",
                "",
                f"Evidence refs: `{scenario.get('evidence_refs', [])}`.",
                "",
            ]
        )
        turns = _as_mappings(scenario.get("turns"), "scenario turns")
        for index, turn in enumerate(turns, start=1):
            turn_identity = ""
            if turn.get("turn_id"):
                turn_identity = (
                    f" Фактический ID: `{turn['turn_id']}`; "
                    f"план: `{turn.get('planned_turn_id', turn['turn_id'])}`."
                )
            lines.extend(
                [
                    f"**Ход {index}. Вопрос:** "
                    f"{turn.get('customer_text', '')}{turn_identity}",
                    "",
                    f"**Ответ Noor:** {turn.get('assistant_text', '')}",
                    "",
                ]
            )
            if turn.get("translation"):
                lines.extend(
                    [
                        f"Перевод для отчёта: {turn['translation']}",
                        "",
                    ]
                )
            if turn.get("translation_provenance"):
                lines.extend(
                    [
                        f"Provenance перевода: `{turn['translation_provenance']}`.",
                        "",
                    ]
                )
            lines.extend(
                [
                    "Время: "
                    f"первый видимый ответ {turn.get('first_visible_seconds', 'н/д')} с; "
                    f"финальный текст {turn.get('final_text_seconds', 'н/д')} с.",
                    "",
                ]
            )
            details = [
                f"язык `{turn.get('original_language', 'не указан')}`",
                f"модель `{turn.get('model', 'не указана')}`",
                f"route `{turn.get('routing_suffix', 'не указан')}`",
                f"tools `{turn.get('tools', [])}`",
                f"tool outcomes `{turn.get('tool_outcomes', [])}`",
                f"media refs `{turn.get('media_refs', [])}`",
                f"audit IDs `{turn.get('audit_ids', [])}`",
                f"tokens `{turn.get('token_count', 'н/д')}`",
                f"cost `{turn.get('cost_usd', 'н/д')}`",
            ]
            lines.extend(
                [
                    "Correlation IDs: "
                    f"conversation `{turn.get('conversation_id', 'н/д')}`, "
                    f"message `{turn.get('message_id', 'н/д')}`, "
                    f"provider `{turn.get('provider_message_id', 'н/д')}`.",
                    "Полные timestamps: "
                    f"sent `{turn.get('sent_at', 'н/д')}`, "
                    f"received `{turn.get('received_at', 'н/д')}`, "
                    f"first-visible `{turn.get('first_visible_at', 'н/д')}`, "
                    f"final-visible `{turn.get('final_visible_at', 'н/д')}`, "
                    f"delivered `{turn.get('delivered_at', 'н/д')}`.",
                    "Трассировка: " + "; ".join(details) + ".",
                    f"Ожидалось: {turn.get('expected_behavior', 'не указано')}",
                    f"Наблюдение: {turn.get('actual_observation', 'не указано')}",
                    f"Проверки: `{turn.get('deterministic_check_ids', [])}`.",
                    "",
                ]
            )
        if scenario.get("initial_failure_ref"):
            lines.extend(
                [
                    f"Исходная ошибка: `{scenario['initial_failure_ref']}`.",
                    f"Дефект: `{scenario.get('defect_id', 'не указан')}`.",
                    f"Исправление: `{scenario.get('fix_commit', 'не указано')}`.",
                    f"Повторная проверка: `{scenario.get('retest_ref', 'не указана')}`.",
                    "",
                ]
            )

    lines.extend(["## Побочные эффекты", ""])
    for entry in _as_mappings(results.get("side_effects", []), "side effects"):
        lines.extend(
            [
                f"- `{entry.get('artifact_id', '')}` / "
                f"scenario `{entry.get('scenario_id', '')}` / "
                f"subsystem `{entry.get('subsystem', '')}` / "
                f"type `{entry.get('artifact_type', '')}`.",
                f"  - creation path `{entry.get('creation_path', '')}`; "
                f"baseline `{entry.get('baseline_readback')}`; "
                f"expected `{entry.get('expected_effect')}`.",
                f"  - final `{entry.get('final_readback')}`; "
                f"disposition `{entry.get('disposition')}`; "
                f"follow-up suppressed "
                f"`{entry.get('follow_up_suppressed', False)}`.",
                f"  - cleanup owner `{entry.get('cleanup_owner', '')}`; "
                f"authority `{entry.get('cleanup_authority', '')}`.",
            ]
        )
    lines.extend(["", "## Evidence и checksums", ""])
    for checksum in _as_mappings(
        results.get("evidence_checksums", []), "evidence checksums"
    ):
        lines.append(
            f"- `{checksum.get('relative_path', '')}`: `{checksum.get('sha256', '')}`"
        )
    lines.extend(
        [
            "",
            f"Authorization evidence: "
            f"`{results.get('authorization_evidence_ref', '')}`.",
            "",
            f"Run identity evidence: `{results.get('run_identity_evidence_ref', '')}`.",
            "",
        ]
    )

    lines.extend(["## Найденные дефекты, исправления и ретесты", ""])
    if not defects:
        lines.extend(["Дефекты не зарегистрированы.", ""])
    for defect in defects:
        lines.extend(
            [
                f"### {defect.get('defect_id', 'черновик дефекта')}",
                "",
                f"- Критичность: `{defect.get('severity', 'не указана')}`",
                f"- Проблема: {defect.get('summary', 'не указана')}",
                f"- Root cause: {defect.get('root_cause', 'не указан')}",
                f"- Invariant test: `{defect.get('invariant_test', 'не указан')}`",
                f"- Исходное evidence: "
                f"`{defect.get('initial_failure_ref', 'не указано')}`",
                f"- Исправление: {defect.get('fix', 'не выполнено')}",
                f"- Fix commit: `{defect.get('fix_commit', 'не указан')}`",
                f"- Deployed release: `{defect.get('deployed_release', 'не указан')}`",
                f"- Ретест: {defect.get('retest', 'не выполнен')}",
                f"- Retest evidence: `{defect.get('retest_ref', 'не указано')}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Итог",
            "",
            f"- coverage_complete: {_yes_no(rollups['coverage_complete'])}",
            f"- execution_complete: {_yes_no(rollups['execution_complete'])}",
            f"- requirements_met: {_yes_no(rollups['requirements_met'])}",
            f"- Закрытие побочных эффектов: `{results.get('side_effect_closeout', 'не подтверждено')}`",
            "",
            "PDF формируется только после содержательного утверждения этого Markdown.",
            "",
        ]
    )
    rendered = "\n".join(lines)
    try:
        validate_redacted_text(rendered)
    except EvidenceError as exc:
        raise ReportError(str(exc)) from exc
    _write_report_exclusive(output_path, rendered.encode("utf-8"))
    return output_path
