from __future__ import annotations

import inspect
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

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


def test_gate_only_authority_accepts_no_action_specs() -> None:
    from scripts.e2e_acceptance import execution

    specs = execution.AuthorizedActionSpecs(
        schema_version="noor-e2e-authorized-action-specs/v2",
        specs=(),
    )

    assert specs.specs == ()


def test_record_blocked_starts_gate_only_execution_after_baseline(
    monkeypatch,
) -> None:
    import scripts.run_noor_e2e_acceptance as cli

    class Journal:
        phase = "baseline_sealed"

        def begin_execution(self) -> None:
            self.phase = "executing"

    journal = Journal()
    plan = SimpleNamespace(plan_digest="a" * 64)
    artifact = SimpleNamespace(
        ordinal=1,
        execution_id="SC-OPEN-EN",
        outcome="BLOCKED",
    )

    class Coordinator:
        accepted = False

        def publish_next_from_decisive_producer(self, handle, source_ref):
            return artifact

        def accept_next(self):
            self.accepted = True
            return SimpleNamespace(ordinal=artifact.ordinal)

    coordinator = Coordinator()
    monkeypatch.setattr(cli, "_canonical_registry", lambda _: object())
    monkeypatch.setattr(
        cli, "_authority_and_journal", lambda *args, **kwargs: (object(), journal)
    )
    monkeypatch.setattr(cli.ProtectedRunPlan, "load", lambda *args, **kwargs: plan)
    monkeypatch.setattr(cli, "load_sealed_run_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(
        cli, "issue_decisive_producer_handle", lambda **kwargs: object()
    )
    monkeypatch.setattr(
        cli, "materialize_next_conservative_gate", lambda **kwargs: "source.json"
    )
    recorded_gates = []
    monkeypatch.setattr(
        cli,
        "_record_committed_gate",
        lambda journal, execution_id, ordinal: recorded_gates.append(
            (execution_id, ordinal)
        ),
    )
    coordinator_calls = 0

    def coordinator_factory(*args, **kwargs):
        nonlocal coordinator_calls
        coordinator_calls += 1
        return coordinator

    monkeypatch.setattr(cli, "_coordinator", coordinator_factory)

    result = cli._lifecycle_result(
        SimpleNamespace(
            command="record-blocked",
            repo_root=Path.cwd(),
            protected_root=Path.cwd(),
            run_id="gate-only",
            run_plan="input-plan.json",
        )
    )

    assert journal.phase == "executing"
    assert coordinator.accepted is True
    assert coordinator_calls == 2
    assert recorded_gates == [("SC-OPEN-EN", 1)]
    assert result["outcome"] == "BLOCKED"


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
    from scripts.run_noor_e2e_acceptance import _record_committed_gate

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
    _record_committed_gate(journal, artifact.execution_id, artifact.ordinal)

    assert artifact.outcome == "BLOCKED"
    assert artifact.kind == "scenario"
    assert artifact.source["turns"] == []
    assert (
        journal.run_root / f"gate-evidence-context/{artifact.execution_id}.json"
    ).is_file()
    assert journal._recorded_gates[artifact.execution_id].outcome == "BLOCKED"
