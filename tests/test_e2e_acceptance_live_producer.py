from __future__ import annotations

import inspect
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI = PROJECT_ROOT / "scripts/run_noor_e2e_acceptance.py"


def _prepared_without_test_gate(tmp_path: Path):
    from tests.test_e2e_acceptance_production import _prepared_gate_producer

    registry, authority, journal, plan, _ = _prepared_gate_producer(tmp_path)
    execution_id = registry.compiled_plan.execution_ids[0]
    (journal.run_root / f"gate-evidence/{execution_id}.json").unlink()
    (journal.run_root / f"producer-receipts/gates/{execution_id}.json").unlink()
    return registry, authority, journal, plan


def test_live_gate_producer_exposes_no_caller_selected_result_facts() -> None:
    from scripts.e2e_acceptance.live_producer import (
        materialize_next_conservative_gate,
    )

    parameters = set(inspect.signature(materialize_next_conservative_gate).parameters)
    assert parameters == {"producer_handle", "current_time"}
    assert {
        "execution_id",
        "outcome",
        "reason",
        "producer",
        "criterion_ids",
    }.isdisjoint(parameters)


def test_cli_exposes_live_authority_and_code_owned_blocking_without_outcome_flags() -> (
    None
):
    help_result = subprocess.run(
        [sys.executable, str(CLI), "--help"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    blocked_help = subprocess.run(
        [sys.executable, str(CLI), "record-blocked", "--help"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert help_result.returncode == blocked_help.returncode == 0
    assert "authorize-live" in help_result.stdout
    assert "record-blocked" in help_result.stdout
    assert "--outcome" not in blocked_help.stdout
    assert "--execution-id" not in blocked_help.stdout


def test_live_gate_producer_publishes_zero_turn_scenario_block(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.coordinator import (
        ProductionRunCoordinator,
        ProtectedJournalAcceptancePort,
    )
    from scripts.e2e_acceptance.live_producer import (
        materialize_next_conservative_gate,
    )
    from scripts.e2e_acceptance.production import issue_decisive_producer_handle

    registry, authority, journal, plan = _prepared_without_test_gate(tmp_path)
    coordinator = ProductionRunCoordinator(
        registry=registry,
        authorization=authority._authorization,
        protected_root=journal.protected_root,
        run_id=journal.run_id,
        journal=ProtectedJournalAcceptancePort(journal=journal),
        current_time=datetime.now(UTC),
    )
    handle = issue_decisive_producer_handle(
        registry=registry,
        journal=journal,
        authority=authority,
        sealed_plan=plan,
    )

    source_ref = materialize_next_conservative_gate(
        producer_handle=handle,
        current_time=datetime.now(UTC),
    )
    artifact = coordinator.publish_next_from_decisive_producer(handle, source_ref)

    assert artifact.outcome == "BLOCKED"
    assert artifact.kind == "scenario"
    assert artifact.source["turns"] == []
    assert (
        journal.run_root / f"gate-evidence-context/{artifact.execution_id}.json"
    ).is_file()
