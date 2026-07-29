from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


def _transcript_fact(attempt) -> dict[str, object]:
    actual = attempt.actual_turns[0]
    timeline = actual.timeline
    duration_ms = int(
        (timeline.final_visible_at - timeline.sent_at).total_seconds() * 1000
    )
    return {
        "turn_id": actual.actual_turn_id,
        "question": "Need four synthetic chairs.",
        "answer": "Four synthetic chairs are available.",
        "sent_at": timeline.sent_at.isoformat(),
        "received_at": timeline.first_visible_at.isoformat(),
        "first_visible_at": timeline.first_visible_at.isoformat(),
        "final_visible_at": timeline.final_visible_at.isoformat(),
        "delivered_at": timeline.delivered_at.isoformat(),
        "duration_ms": duration_ms,
        "conversation_id": "synthetic-conversation",
        "message_id": "synthetic-message",
        "provider_message_id": "synthetic-provider-message",
        "model": actual.model_id,
        "tools": list(actual.tool_refs),
        "tool_outcomes": [],
        "audit_ids": list(actual.audit_refs),
        "media_refs": [],
        "token_count": actual.token_count,
        "cost_usd": actual.cost_usd,
        "deviation": None,
        "evaluator_reasoning": "Protected checks passed.",
    }


def test_independent_live_producer_materializes_timing_cost_and_side_effects(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.coordinator import (
        ProductionRunCoordinator,
        ProtectedJournalAcceptancePort,
    )
    from scripts.e2e_acceptance.live_producer import IndependentExecutionProducer
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        issue_decisive_producer_handle,
    )

    from tests.test_e2e_acceptance_production import _prepared_executed_producer

    registry, authority, journal, plan, attempt = _prepared_executed_producer(tmp_path)
    execution_id = attempt.execution_id
    disposition = {
        "artifact_id": "synthetic:item",
        "scenario_id": execution_id,
        "subsystem": "outbound_text",
        "artifact_type": "synthetic_conversation",
        "expected_effect": {"state": "closed"},
        "disposition": "cleaned",
        "owner": journal.authorization.side_effect_authority.cleanup_owner,
        "cleanup_authority": (
            journal.authorization.side_effect_authority.cleanup_authority
        ),
        "follow_up_suppressed": True,
        "checksum_refs": ["collector:synthetic-item"],
    }
    raw = json.dumps(
        {
            "schema_version": "noor-e2e-live-execution-observation/v1",
            "execution_id": execution_id,
            "observed_at": datetime.now(UTC).isoformat(),
            "attempt": attempt.model_dump(mode="json"),
            "transcript_facts": [_transcript_fact(attempt)],
            "side_effect_dispositions": [disposition],
        }
    ).encode()
    producer = IndependentExecutionProducer(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={f"execution:{execution_id}": raw}
        ),
    )
    handle = issue_decisive_producer_handle(
        registry=registry,
        journal=journal,
        authority=authority,
        sealed_plan=plan,
    )

    source_ref = producer.materialize_next(
        producer_handle=handle,
        observed_at=datetime.now(UTC),
    )
    artifact = ProductionRunCoordinator(
        registry=registry,
        authorization=authority._authorization,
        protected_root=journal.protected_root,
        run_id=journal.run_id,
        journal=ProtectedJournalAcceptancePort(journal=journal),
        current_time=datetime.now(UTC),
    ).publish_next_from_decisive_producer(handle, source_ref)

    assert artifact.outcome == "PASS"
    assert artifact.source["turns"][0]["duration_ms"] == 2
    assert artifact.source["turns"][0]["cost_usd"] == 0
    assert artifact.source["side_effect_dispositions"][0] == {
        **disposition,
        "retention_pre_authorized": None,
        "retention_owner": None,
        "retention_authority_digest": None,
        "retention_expires_at": None,
        "final_disposition_date": None,
    }
    assert (
        journal.run_root / f"collector-raw/executions/{execution_id}.json"
    ).read_bytes() == raw


def test_live_runtime_is_sealed_in_plan_and_bound_to_authority() -> None:
    from scripts.e2e_acceptance.live_transport import (
        LiveRuntimeConfig,
        build_live_runtime_components,
    )
    from scripts.e2e_acceptance.production import (
        ProductionAdapterError,
        ProtectedRunPlan,
    )

    runtime = {
        "schema_version": "noor-e2e-live-runtime/v1",
        "adapter_id": "wazzup-webhook-adapter",
        "webhook_endpoint": "https://noor.starec.ai/api/v1/webhook/wazzup",
        "target_digest": "a" * 64,
        "collector_id": "independent-readback-collector",
        "ssh_host_alias": "noor-production",
        "source_commands": {
            "baseline": ["/usr/bin/cat", "/var/lib/noor/baseline.json"],
            "final": ["/usr/bin/cat", "/var/lib/noor/final.json"],
        },
    }
    evaluator = {
        "schema_version": "noor-e2e-protected-evaluator/v1",
        "publication": {"seed": 1},
        "decisive_producers": [
            {
                "producer_id": "wazzup-webhook-adapter",
                "producer_kind": "adapter",
                "capability": "outbound_text",
                "source_identity": "wazzup-webhook-adapter",
                "config_digest": "b" * 64,
            }
        ],
    }
    plain = ProtectedRunPlan.from_payload({"actions": [], "evaluator": evaluator})
    live = ProtectedRunPlan.from_payload(
        {"actions": [], "evaluator": evaluator, "runtime": runtime}
    )
    assert live.runtime == runtime
    assert live.plan_digest != plain.plan_digest

    config = LiveRuntimeConfig.model_validate(live.runtime)
    authority = SimpleNamespace(
        adapter_ids=("wazzup-webhook-adapter",),
        collector_ids=("independent-readback-collector",),
        live_binding=SimpleNamespace(target_digest="a" * 64),
    )

    class HttpClient:
        pass

    class SshRunner:
        def run(self, *args, **kwargs):
            return subprocess.CompletedProcess([], 0, stdout=b"{}")

    components = build_live_runtime_components(
        config=config,
        authorization=authority,
        http_client=HttpClient(),
        ssh_runner=SshRunner(),
    )
    assert components.collector.collector_id == "independent-readback-collector"
    assert components.producer.collector_id == "independent-readback-collector"

    with pytest.raises(ProductionAdapterError, match="target"):
        build_live_runtime_components(
            config=config,
            authorization=SimpleNamespace(
                **{
                    **vars(authority),
                    "live_binding": SimpleNamespace(target_digest="c" * 64),
                }
            ),
            http_client=HttpClient(),
            ssh_runner=SshRunner(),
        )


def test_execution_authority_accepts_only_named_real_webhook_adapter() -> None:
    from scripts.e2e_acceptance import execution

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _authorization

    registry = build_canonical_test_registry()
    base = _authorization(registry, trusted=False)
    adapter_ids = ("wazzup-webhook-adapter",)
    action_specs = tuple(
        item.model_copy(update={"adapter_id": adapter_ids[0]})
        for item in base.action_specs
    )
    candidate = base.model_copy(
        update={
            "adapter_ids": adapter_ids,
            "action_specs": action_specs,
            "live_binding": base.live_binding.model_copy(
                update={"adapter_ids_digest": execution._digest(adapter_ids)}
            ),
        }
    )

    registry._load_execution_authorization(candidate)
    registry.validate_execution_authorization(candidate)


def test_independent_reconciliation_settles_collector_reported_actual_cost(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance import execution

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _issued_authority

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(
        registry, protected_root=root, run_id="actual-cost-run"
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root,
        run_id="actual-cost-run",
        authority=authority,
    )
    now = datetime.now(UTC)
    journal.seal_baseline(
        execution.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="baseline",
            run_id=journal.run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
            causal_event_digest="a" * 64,
            observed_at=now,
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
    spec = journal.authorization.action_specs[0]
    charge = spec.quota_charge
    request = spec.model_dump(mode="python", exclude={"quota_charge"})
    action_id = request.pop("action_id")
    adapter_id = request.pop("adapter_id")
    subsystem = request.pop("subsystem")
    reservation = journal.reserve_action(
        action_id=action_id,
        adapter_id=adapter_id,
        subsystem=subsystem,
        messages=charge.messages,
        model_calls=charge.model_calls,
        cost_usd=charge.max_cost_usd,
        **request,
    )
    journal.consume_permit(
        reservation,
        adapter_id=adapter_id,
        **request,
    )
    receipt = execution.UnknownActionReconciliationReceipt(
        schema_version="noor-e2e-unknown-action-reconciliation/v2",
        registry_id=registry.registry_id,
        run_id=journal.run_id,
        authorization_digest=journal.authorization_digest,
        action_id=action_id,
        reservation_digest=reservation.reservation_digest,
        collector_id="independent-readback-collector",
        producer="independent-readback-collector",
        causal_event_digest=journal.previous_event_digest,
        observed_at=now,
        expires_at=now.replace(year=now.year + 1),
        resolved_state="succeeded",
        inventory_digest="d" * 64,
        actual_cost_usd=0.10,
    )
    receipt_digest = execution._write_exclusive(
        journal.run_root,
        f"independent-reconciliation/{action_id}.json",
        receipt.model_dump(mode="json"),
    )

    settlement = journal.reconcile_and_settle_action(
        action_id=action_id,
        receipt_digest=receipt_digest,
    )

    assert settlement.actual_cost_usd == 0.10


def test_cli_live_plan_collects_preflight_dispatches_and_reconciles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from scripts import run_noor_e2e_acceptance as cli
    from scripts.e2e_acceptance import execution, production

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import (
        _action_quota_charge,
        _action_request,
        _authority_bundle_inputs,
    )

    registry = build_canonical_test_registry()
    root = (tmp_path / "protected").resolve()
    run_id = "live-cli-run"
    payload = {
        "messages": [
            {
                "messageId": "synthetic-message",
                "chatId": "synthetic-chat",
                "chatType": "whatsapp",
                "authorType": "client",
                "channelId": "synthetic-channel",
                "text": "synthetic text",
                "dateTime": "2026-07-29T09:00:00Z",
                "type": "text",
                "status": "inbound",
            }
        ]
    }
    request = _action_request()
    request.update(
        {
            "capability": "webhook.inbound",
            "payload_digest": production._digest(payload),
        }
    )
    spec = execution.AuthorizedActionSpec(
        action_id="synthetic-action",
        adapter_id="wazzup-webhook-adapter",
        subsystem="outbound_text",
        quota_charge=_action_quota_charge(execution),
        **request,
    )
    inputs = _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id=run_id,
        now=datetime.now(UTC),
        action_specs=execution.AuthorizedActionSpecs(
            schema_version="noor-e2e-authorized-action-specs/v2",
            specs=(spec,),
        ),
    )
    inputs["adapter_ids"] = execution.AuthorityAdapterIds(
        schema_version="noor-e2e-authority-adapter-ids/v2",
        values=("wazzup-webhook-adapter",),
    )
    execution._write_test_authority_bundle(**inputs)

    runtime = {
        "schema_version": "noor-e2e-live-runtime/v1",
        "adapter_id": "wazzup-webhook-adapter",
        "webhook_endpoint": "https://noor.starec.ai/api/v1/webhook/wazzup",
        "target_digest": execution._digest(
            inputs["authorization"].targets.model_dump(mode="json")
        ),
        "collector_id": "independent-readback-collector",
        "ssh_host_alias": "noor-production",
        "source_commands": {
            "baseline": ["/usr/bin/cat", "/var/lib/noor/baseline.json"],
            "final": ["/usr/bin/cat", "/var/lib/noor/final.json"],
            "reconciliation:synthetic-action": [
                "/usr/bin/cat",
                "/var/lib/noor/reconciliation.json",
            ],
        },
    }
    plan_payload = {
        "actions": [
            {
                "spec": spec.model_dump(mode="json"),
                "message_path": "requests/synthetic-action.json",
            }
        ],
        "evaluator": {
            "schema_version": "noor-e2e-protected-evaluator/v1",
            "publication": {"seed": 1},
            "decisive_producers": [
                {
                    "producer_id": "wazzup-webhook-adapter",
                    "producer_kind": "adapter",
                    "capability": "outbound_text",
                    "source_identity": "wazzup-webhook-adapter",
                    "config_digest": "b" * 64,
                }
            ],
        },
        "runtime": runtime,
    }
    execution._write_exclusive(root, "input-plan.json", plan_payload)

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> object:
            return {"ok": True}

    class HttpClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def post(self, url: str, **kwargs: object) -> Response:
            self.calls.append({"url": url, **kwargs})
            return Response()

    class SshRunner:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def run(self, args: list[str], **kwargs: object):
            self.calls.append(args)
            source_file = args[-1]
            if source_file.endswith("baseline.json"):
                payload = {"inventory": {"synthetic:item": {"state": "absent"}}}
            elif source_file.endswith("reconciliation.json"):
                payload = {
                    "schema_version": "noor-e2e-live-action-reconciliation/v1",
                    "action_id": "synthetic-action",
                    "observed_at": datetime.now(UTC).isoformat(),
                    "resolved_state": "succeeded",
                    "inventory": {"synthetic:item": {"state": "present"}},
                    "actual_cost_usd": 0.10,
                }
            else:
                payload = {"inventory": {"synthetic:item": {"state": "closed"}}}
            return subprocess.CompletedProcess(
                args, 0, stdout=json.dumps(payload).encode()
            )

    http_client = HttpClient()
    ssh_runner = SshRunner()
    monkeypatch.setattr(cli, "_canonical_registry", lambda _: registry)
    monkeypatch.setattr(cli, "_http_client_factory", lambda: http_client)
    monkeypatch.setattr(cli, "_ssh_runner", ssh_runner)
    args = SimpleNamespace(
        repo_root=Path.cwd(),
        protected_root=root,
        run_id=run_id,
        run_plan="input-plan.json",
    )

    cli._lifecycle_result(SimpleNamespace(command="prepare", **vars(args)))
    preflight = cli._lifecycle_result(
        SimpleNamespace(
            command="preflight",
            baseline="collector-artifacts/baseline-readback.json",
            **vars(args),
        )
    )
    _, journal = cli._authority_and_journal(registry, root, run_id, create=False)
    production.write_protected_message(
        journal, action_id="synthetic-action", payload=payload
    )
    dispatched = cli._lifecycle_result(
        SimpleNamespace(command="execute-resume", **vars(args))
    )
    reconciled = cli._lifecycle_result(
        SimpleNamespace(
            command="reconcile-action",
            action_id="synthetic-action",
            **vars(args),
        )
    )

    assert preflight["phase"] == "baseline_sealed"
    assert dispatched["state"] == "unknown"
    assert reconciled["settled_actual_cost_usd"] == 0.10
    assert len(http_client.calls) == 1
    assert [call[-1] for call in ssh_runner.calls] == [
        "/var/lib/noor/baseline.json",
        "/var/lib/noor/reconciliation.json",
    ]


def test_completed_mixed_run_seals_ordered_transcript_manifest(
    tmp_path: Path,
) -> None:
    from scripts.run_noor_e2e_acceptance import (
        _seal_transcript_manifest_if_complete,
    )

    execution_id = "SC-OPEN-EN"
    turn_id = "turn-001"
    attempt_id = f"attempt:{execution_id}"
    transcript_ref = f"transcripts/{execution_id}/{attempt_id}/{turn_id}.json"
    receipt_ref = (
        f"producer-receipts/transcripts/{execution_id}/{attempt_id}/{turn_id}.json"
    )
    source_ref = "producer-observations/01.json"
    for relative, payload in (
        (transcript_ref, {"turn": turn_id}),
        (receipt_ref, {"receipt": turn_id}),
        (
            source_ref,
            {
                "execution_id": execution_id,
                "transcript_facts": [{"turn_id": turn_id}],
            },
        ),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    registry = SimpleNamespace(
        registry_id="a" * 64,
        compiled_plan=SimpleNamespace(execution_ids=(execution_id, "SC-BLOCKED")),
    )
    journal = SimpleNamespace(run_id="mixed-run", run_root=tmp_path)

    _seal_transcript_manifest_if_complete(
        registry=registry,
        journal=journal,
        accepted_ordinal=2,
    )

    manifest = json.loads((tmp_path / "transcripts/manifest.json").read_text())
    assert [row[:3] for row in manifest["ordered_turns"]] == [
        [execution_id, attempt_id, turn_id]
    ]
