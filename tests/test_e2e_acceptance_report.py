"""Report facade must never accept caller-owned scope/results/evidence."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from scripts.e2e_acceptance.policy import (
    PolicyValidationError,
    TrustedAcceptanceRegistry,
)
from scripts.e2e_acceptance.report import (
    ReportError,
    build_defect_draft,
    calculate_rollups,
    render_client_report,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_rollup_and_report_facades_accept_registry_only() -> None:
    assert list(inspect.signature(calculate_rollups).parameters) == ["registry"]
    assert list(inspect.signature(render_client_report).parameters) == [
        "registry",
        "output_path",
    ]


def test_unloaded_registry_cannot_claim_rollups() -> None:
    registry = TrustedAcceptanceRegistry.from_canonical_repo()

    with pytest.raises(PolicyValidationError):
        calculate_rollups(registry)


def test_defect_draft_is_typed_and_privacy_checked() -> None:
    draft = build_defect_draft(
        scenario_id="SC-OPEN-EN",
        severity="P1",
        summary="Synthetic failure",
        expected="Expected",
        actual="Actual",
        evidence_path="registry/evidence-index.json",
        criterion_ids=["AC-01"],
        historical_regressions=["tj-synthetic"],
    )

    assert draft["status"] == "draft_not_created_in_beads"
    with pytest.raises(ReportError, match="severity"):
        build_defect_draft(
            scenario_id="SC-OPEN-EN",
            severity="P9",
            summary="Synthetic failure",
            expected="Expected",
            actual="Actual",
            evidence_path="registry/evidence-index.json",
            criterion_ids=["AC-01"],
            historical_regressions=[],
        )
