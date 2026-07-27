"""Registry-owned rollup/report facade and safe defect-draft helper."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from scripts.e2e_acceptance.evidence import EvidenceError, validate_redacted_payload
from scripts.e2e_acceptance.policy import (
    PolicyValidationError,
    TrustedAcceptanceRegistry,
)

ReportError = PolicyValidationError


def calculate_rollups(registry: TrustedAcceptanceRegistry) -> dict[str, bool]:
    """Return rollups from a run already verified by the sole trust center."""

    return registry.calculate_rollups()


def render_client_report(
    registry: TrustedAcceptanceRegistry,
    output_path: Path,
) -> None:
    """Serialize only the registry-owned typed report payload."""

    registry.write_report(output_path)


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
