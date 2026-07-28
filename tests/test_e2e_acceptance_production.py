"""Contract tests for the local-only production adapter boundary."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI = PROJECT_ROOT / "scripts/run_noor_e2e_acceptance.py"


def test_cli_exposes_resumable_local_only_lifecycle() -> None:
    completed = subprocess.run(
        [sys.executable, str(CLI), "--help"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    for command in (
        "prepare",
        "preflight",
        "execute-resume",
        "record-gate",
        "finalize",
    ):
        assert command in completed.stdout


def test_capability_dispatch_never_uses_scenario_identity() -> None:
    from scripts.e2e_acceptance.production import (
        CapabilityDispatcher,
        FakeHttpTransport,
        ProductionAdapterError,
    )

    transport = FakeHttpTransport(responses={"webhook.inbound": {"ok": True}})
    dispatcher = CapabilityDispatcher({"webhook.inbound": transport})

    assert dispatcher.dispatch(
        capability="webhook.inbound",
        request={"event": "message"},
    ) == {"ok": True}
    with pytest.raises(ProductionAdapterError, match="capability"):
        dispatcher.dispatch(capability="scenario-en-new-customer", request={})
    with pytest.raises(ProductionAdapterError, match="registry"):
        CapabilityDispatcher({"SC-OPEN-EN": transport})


def test_fake_transport_marks_post_dispatch_failure_uncertain() -> None:
    from scripts.e2e_acceptance.production import (
        DispatchUncertainError,
        FakeHttpTransport,
    )

    transport = FakeHttpTransport(
        responses={"webhook.inbound": {"ok": True}},
        uncertain_capabilities={"webhook.inbound"},
    )

    with pytest.raises(DispatchUncertainError, match="after dispatch"):
        transport.request("webhook.inbound", {"event": "message"})
    assert transport.calls == (("webhook.inbound", {"event": "message"}),)


def test_read_only_collector_has_no_mutating_transport_surface() -> None:
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
    )

    raw = b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
    transport = FakeReadOnlySshTransport(responses={"inventory": raw})
    collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=transport,
    )

    observation = collector.observe(
        source_id="baseline",
        run_id="local-run",
        preflight_digest="a" * 64,
        collector_artifact_digest="b" * 64,
        causal_event_digest="c" * 64,
    )

    assert observation.inventory == {"synthetic:item": {"state": "absent"}}
    assert observation.collector_artifact_digest == "b" * 64
    assert not hasattr(collector, "execute")
    assert not hasattr(transport, "execute")
    assert hashlib.sha256(raw).hexdigest() == transport.response_digests["inventory"]


def test_collector_emits_task1_final_artifact_and_receipt_layout(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _issued_authority

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(registry, protected_root=root, run_id="local-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    now = datetime.now(UTC)
    baseline = execution.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="baseline",
        run_id="local-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
        causal_event_digest="a" * 64,
        observed_at=now - timedelta(seconds=2),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    journal.anchor_final_turn(
        event_digest="b" * 64, occurred_at=now - timedelta(seconds=1)
    )
    collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={
                "inventory": b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
            }
        ),
    )

    final = collector.seal_final(journal, source_id="final", observed_at=now)

    assert final.phase == "final"
    assert journal.phase == "final_readback_sealed"
    receipt = json.loads(
        execution._read_protected(
            journal.run_root, "producer-receipts/final-readback.json"
        )
    )
    assert receipt["producer"] == "independent-readback-collector"


def test_baseline_requires_producer_artifact_not_caller_json(tmp_path: Path) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
        load_protected_baseline,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _issued_authority

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(registry, protected_root=root, run_id="local-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    now = datetime.now(UTC)
    caller_json = execution.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="caller",
        run_id="local-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
        causal_event_digest=journal.previous_event_digest or "a" * 64,
        observed_at=now,
        inventory={"synthetic:item": {"state": "absent"}},
    )
    execution._write_exclusive(
        journal.run_root, "caller-baseline.json", caller_json.model_dump(mode="json")
    )

    with pytest.raises(Exception, match="producer"):
        load_protected_baseline(
            journal, artifact_path="caller-baseline.json", current_time=now
        )

    collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={
                "inventory": b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
            }
        ),
    )
    collector.seal_baseline(journal, source_id="collector", observed_at=now)
    # Simulate a restart after producer files are durable but before preflight seals.
    collector.seal_baseline(journal, source_id="collector", observed_at=now)
    assert (
        load_protected_baseline(
            journal,
            artifact_path="collector-artifacts/baseline-readback.json",
            current_time=now,
        ).phase
        == "baseline"
    )


def test_sealed_run_plan_rejects_replacement_after_restart(tmp_path: Path) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import (
        ProtectedRunPlan,
        load_sealed_run_plan,
        seal_run_plan,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _issued_authority

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(registry, protected_root=root, run_id="local-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    specs = [
        item.model_dump(mode="json") for item in journal.authorization.action_specs
    ]
    plan = ProtectedRunPlan.from_payload(
        {
            "actions": [
                {"spec": spec, "message_path": f"requests/{spec['action_id']}.json"}
                for spec in specs
            ],
            "evaluator": {"seed": 1},
        }
    )

    seal_run_plan(journal, plan)
    assert load_sealed_run_plan(journal, plan) == plan
    replacement = ProtectedRunPlan.from_payload(
        {
            "actions": [
                {
                    "spec": spec,
                    "message_path": (
                        "requests/other.json"
                        if spec["action_id"] == "synthetic-action"
                        else f"requests/{spec['action_id']}.json"
                    ),
                }
                for spec in specs
            ],
            "evaluator": {"seed": 1},
        }
    )
    with pytest.raises(Exception, match="sealed"):
        load_sealed_run_plan(journal, replacement)


def test_record_gate_uses_opaque_authority_not_public_authorization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts import run_noor_e2e_acceptance as cli
    from scripts.e2e_acceptance import execution

    root = (tmp_path / "protected").resolve()
    root.mkdir()
    recorded: list[dict[str, object]] = []

    class Journal:
        run_root = root
        previous_event_digest = "c" * 64

        def _append_event(self, **event) -> None:
            recorded.append(event)

    journal = Journal()
    gate = execution.GateAttemptV2(
        schema_version="noor-e2e-gate-attempt/v2",
        execution_id="EB-RUNTIME",
        outcome="BLOCKED",
        run_started_at=datetime.now(UTC),
        execution_started_event_digest="a" * 64,
        receipt_digest="b" * 64,
    )
    execution._write_exclusive(root, "gate.json", gate.model_dump(mode="json"))
    opaque_authority = object()
    captured: dict[str, object] = {}

    class Runner:
        def __init__(self, *, registry, authority, journal) -> None:
            captured.update(registry=registry, authority=authority, journal=journal)

        def validate_gate_attempt(self, attempt, *, current_time):
            return SimpleNamespace(
                execution_id=attempt.execution_id, outcome=attempt.outcome
            )

    monkeypatch.setattr(cli, "_canonical_registry", lambda _: "registry")
    monkeypatch.setattr(
        cli,
        "_authority_and_journal",
        lambda *args, **kwargs: (opaque_authority, journal),
    )
    monkeypatch.setattr(execution, "GenericAcceptanceRunner", Runner)
    args = SimpleNamespace(
        command="record-gate",
        repo_root=PROJECT_ROOT,
        protected_root=root,
        run_id="local-run",
        gate_attempt="gate.json",
    )

    assert cli._lifecycle_result(args) == {
        "execution_id": "EB-RUNTIME",
        "outcome": "BLOCKED",
    }
    assert captured["authority"] is opaque_authority
    assert recorded[0]["kind"] == "gate_recorded"


def test_adapter_consumes_exact_permit_before_transport_and_projects_checksum(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance import production

    root = (tmp_path / "protected").resolve()
    root.mkdir()
    events: list[str] = []

    class Journal:
        run_root = root
        protected_root = root
        run_id = "local-run"
        authorization = SimpleNamespace(
            store_ids=SimpleNamespace(
                tracked_store_id="tracked",
                tracked_root_digest=production.execution.store_root_digest(
                    (root / "tracked").resolve()
                ),
            )
        )

        def consume_permit(self, reservation, **request) -> None:
            events.append("permit")
            assert reservation.action_id == "action-1"
            assert request["payload_digest"] == production._digest({"text": "local"})

    class Transport:
        def preflight(self, capability, request) -> None:
            assert capability.value == "webhook.inbound"

        def request(self, capability, request):
            events.append("transport")
            assert capability == "webhook.inbound"
            assert request == {"text": "local"}
            return {"receipt": "local"}

    production.write_protected_message(
        Journal(), action_id="action-1", payload={"text": "local"}
    )
    adapter = production.WazzupWebhookAdapter(
        adapter_id="adapter-1",
        journal=Journal(),
        dispatcher=production.CapabilityDispatcher({"webhook.inbound": Transport()}),
    )
    reservation = SimpleNamespace(adapter_id="adapter-1", action_id="action-1")
    digest = production._digest({"text": "local"})

    result = adapter.dispatch(
        reservation,
        message_path="requests/action-1.json",
        execution_id="unit",
        step_id="step",
        capability="webhook.inbound",
        operation_permission="fixture:execute",
        destination_digest="a" * 64,
        payload_digest=digest,
        idempotency_key="idempotent",
        capability_units={"outbound_text": 1},
    )
    assert events == ["permit", "transport"]
    raw = production.execution._read_protected(root, "adapter-responses/action-1.json")
    tracked = json.loads(
        production.execution._read_protected(
            root, "tracked/local-run/adapter-responses/action-1.json"
        )
    )
    assert tracked["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert tracked["response"] == {"receipt": "local"}
    assert result.projection == {"receipt": "local"}
    assert "receipt" not in result.model_dump(exclude={"projection"})


def test_timeout_before_dispatch_does_not_create_transport_call() -> None:
    from scripts.e2e_acceptance.production import (
        Capability,
        DispatchTimeoutError,
        FakeHttpTransport,
    )

    transport = FakeHttpTransport(
        responses={"webhook.inbound": {"ok": True}},
        timeout_capabilities={"webhook.inbound"},
    )

    with pytest.raises(DispatchTimeoutError, match="before dispatch"):
        transport.preflight(Capability.WEBHOOK_INBOUND, {"event": "message"})
    assert transport.calls == ()


def test_adapter_pre_dispatch_timeout_leaves_permit_unconsumed(tmp_path: Path) -> None:
    from scripts.e2e_acceptance import production

    root = (tmp_path / "protected").resolve()
    root.mkdir()
    consumed: list[str] = []

    class Journal:
        run_root = root
        protected_root = root
        run_id = "local-run"
        authorization = SimpleNamespace(
            store_ids=SimpleNamespace(
                tracked_store_id="tracked",
                tracked_root_digest=production.execution.store_root_digest(
                    (root / "tracked").resolve()
                ),
            )
        )

        def consume_permit(self, reservation, **request) -> None:
            consumed.append(reservation.action_id)

    production.write_protected_message(
        Journal(), action_id="action-1", payload={"text": "local"}
    )
    digest = production._digest({"text": "local"})
    adapter = production.WazzupWebhookAdapter(
        adapter_id="adapter-1",
        journal=Journal(),
        dispatcher=production.CapabilityDispatcher(
            {
                "webhook.inbound": production.FakeHttpTransport(
                    responses={"webhook.inbound": {"ok": True}},
                    timeout_capabilities={"webhook.inbound"},
                )
            }
        ),
    )

    with pytest.raises(production.DispatchTimeoutError):
        adapter.dispatch(
            SimpleNamespace(adapter_id="adapter-1", action_id="action-1"),
            message_path="requests/action-1.json",
            execution_id="unit",
            step_id="step",
            capability="webhook.inbound",
            operation_permission="fixture:execute",
            destination_digest="a" * 64,
            payload_digest=digest,
            idempotency_key="idempotent",
            capability_units={"outbound_text": 1},
        )
    assert consumed == []


def test_cli_execute_resume_drives_once_then_reopen_blocks_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts import run_noor_e2e_acceptance as cli
    from scripts.e2e_acceptance import execution, production
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import (
        _action_quota_charge,
        _action_request,
        _issued_authority,
    )

    registry = build_canonical_test_registry()
    root = (tmp_path / "protected").resolve()
    payload = {"text": "local"}
    request = _action_request()
    request["payload_digest"] = production._digest(payload)
    spec = execution.AuthorizedActionSpec(
        action_id="synthetic-action",
        adapter_id="fake-local-adapter",
        subsystem="outbound_text",
        quota_charge=_action_quota_charge(execution),
        **request,
    )
    _issued_authority(
        registry,
        protected_root=root,
        run_id="local-run",
        action_specs=execution.AuthorizedActionSpecs(
            schema_version="noor-e2e-authorized-action-specs/v2", specs=(spec,)
        ),
    )
    plan_payload = {
        "actions": [
            {
                "spec": spec.model_dump(mode="json"),
                "message_path": "requests/synthetic-action.json",
            }
        ],
        "evaluator": {"seed": 1},
    }
    execution._write_exclusive(root, "input-plan.json", plan_payload)
    monkeypatch.setattr(cli, "_canonical_registry", lambda _: registry)
    args = SimpleNamespace(
        repo_root=PROJECT_ROOT,
        protected_root=root,
        run_id="local-run",
        run_plan="input-plan.json",
    )

    assert (
        cli._lifecycle_result(SimpleNamespace(command="prepare", **vars(args)))["phase"]
        == "prepared"
    )
    _, journal = cli._authority_and_journal(registry, root, "local-run", create=False)
    production.write_protected_message(
        journal, action_id="synthetic-action", payload=payload
    )
    IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={
                "inventory": b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
            }
        ),
    ).seal_baseline(journal, source_id="baseline")
    assert (
        cli._lifecycle_result(
            SimpleNamespace(
                command="preflight",
                baseline="collector-artifacts/baseline-readback.json",
                **vars(args),
            )
        )["phase"]
        == "baseline_sealed"
    )

    with pytest.raises(Exception, match="unknown"):
        cli._lifecycle_result(SimpleNamespace(command="execute-resume", **vars(args)))
    _, reopened = cli._authority_and_journal(registry, root, "local-run", create=False)
    assert reopened._actions == {"synthetic-action": "unknown"}
    with pytest.raises(Exception, match="nonterminal"):
        cli._lifecycle_result(SimpleNamespace(command="execute-resume", **vars(args)))
