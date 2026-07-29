from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
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
        "tool_traces": [
            {
                "call_id": f"call-{index}",
                "tool_name": tool_name,
                "arguments_digest": "a" * 64,
                "outcome_digest": "b" * 64,
                "state": "returned",
            }
            for index, tool_name in enumerate(actual.tool_refs)
        ],
        "tools": list(actual.tool_refs),
        "tool_outcomes": [],
        "audit_ids": list(actual.audit_refs),
        "media_refs": [],
        "token_count": actual.token_count,
        "cost_usd": actual.cost_usd,
        "deviation": None,
        "evaluator_reasoning": "Protected checks passed.",
    }


class _PassJudgeTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def request(self, request) -> bytes:
        self.calls.append(dict(request))
        facts = json.loads(request["messages"][1]["content"])
        result = {
            "schema_version": "noor-e2e-semantic-judge-result/v1",
            "execution_id": facts["execution_id"],
            "observation_sha256": facts["observation_sha256"],
            "verdicts": [
                {
                    "assertion_id": item["assertion_id"],
                    "passed": True,
                    "reason": "The protected production facts satisfy this check.",
                }
                for item in facts["assertions"]
            ],
        }
        return json.dumps(
            {
                "model": request["model"],
                "choices": [{"message": {"content": json.dumps(result)}}],
                "usage": {"total_tokens": 123, "cost": 0.02},
            }
        ).encode()


def test_independent_live_producer_collects_server_facts_without_caller_evaluation(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.live_producer import IndependentExecutionProducer
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        ProductionAdapterError,
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
        "baseline_readback": {"state": "absent"},
        "expected_effect": {"state": "closed"},
        "final_readback": {"state": "closed"},
        "disposition": "resolved",
        "owner": journal.authorization.side_effect_authority.cleanup_owner,
        "cleanup_authority": (
            journal.authorization.side_effect_authority.cleanup_authority
        ),
        "follow_up_suppressed": True,
        "checksum_refs": ["collector:synthetic-item"],
    }
    raw = json.dumps(
        {
            "schema_version": "noor-e2e-server-execution-observation/v1",
            "execution_id": execution_id,
            "observed_at": datetime.now(UTC).isoformat(),
            "transcript_facts": [_transcript_fact(attempt)],
            "side_effect_facts": [
                {
                    key: value
                    for key, value in disposition.items()
                    if key
                    in {
                        "artifact_id",
                        "subsystem",
                        "artifact_type",
                        "baseline_readback",
                        "expected_effect",
                        "final_readback",
                        "disposition",
                        "follow_up_suppressed",
                        "checksum_refs",
                    }
                }
            ],
            "baseline_inventory": {},
            "final_inventory": {"synthetic:item": {"state": "closed"}},
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

    source_ref = producer.collect_next(
        producer_handle=handle,
        observed_at=datetime.now(UTC),
    )
    assert source_ref == f"collector-raw/executions/{execution_id}.json"
    assert (
        journal.run_root / f"collector-raw/executions/{execution_id}.json"
    ).read_bytes() == raw
    assert not (journal.run_root / "collector-raw/evaluations").exists()

    with pytest.raises(ProductionAdapterError, match="semantic compiler"):
        producer.materialize_next(
            producer_handle=handle,
            observed_at=datetime.now(UTC),
        )


def test_live_semantic_compiler_uses_sealed_plan_observation_and_one_judge_call(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.live_producer import IndependentExecutionProducer
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        _write_or_validate_exact,
        issue_decisive_producer_handle,
        produce_validated_execution_attempt,
    )

    from tests.test_e2e_acceptance_production import _prepared_executed_producer

    question = "Need four synthetic chairs."
    registry, authority, journal, plan, attempt = _prepared_executed_producer(
        tmp_path,
        semantic_customer_text=question,
    )
    execution_id = attempt.execution_id
    observed_at = datetime.now(UTC)
    disposition = {
        "artifact_id": "synthetic:item",
        "subsystem": "outbound_text",
        "artifact_type": "synthetic_conversation",
        "baseline_readback": {"state": "absent"},
        "expected_effect": {"state": "closed"},
        "final_readback": {"state": "closed"},
        "disposition": "resolved",
        "follow_up_suppressed": True,
        "checksum_refs": ["collector:synthetic-item"],
    }
    raw = json.dumps(
        {
            "schema_version": "noor-e2e-server-execution-observation/v1",
            "execution_id": execution_id,
            "observed_at": observed_at.isoformat(),
            "transcript_facts": [_transcript_fact(attempt)],
            "side_effect_facts": [disposition],
            "baseline_inventory": {"synthetic:item": {"state": "absent"}},
            "final_inventory": {"synthetic:item": {"state": "closed"}},
        }
    ).encode()
    _write_or_validate_exact(
        journal.run_root,
        "collector-artifacts/baseline-readback.json",
        {"observation": attempt.baseline.model_dump(mode="json")},
    )

    judge = _PassJudgeTransport()
    producer = IndependentExecutionProducer(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={f"execution:{execution_id}": raw}
        ),
        judge_transport=judge,
    )
    handle = issue_decisive_producer_handle(
        registry=registry,
        journal=journal,
        authority=authority,
        sealed_plan=plan,
    )

    source_ref = producer.materialize_next(
        producer_handle=handle,
        observed_at=observed_at + timedelta(seconds=1),
    )
    assert (
        producer.materialize_next(
            producer_handle=handle,
            observed_at=observed_at + timedelta(seconds=1),
        )
        == source_ref
    )
    produced = produce_validated_execution_attempt(
        producer_handle=handle,
        source_output_ref=source_ref,
    )

    assert produced.artifact["outcome"] == "PASS"
    assert len(judge.calls) == 1
    assert judge.calls[0]["temperature"] == 0
    action_id = f"judge-{execution_id.lower()}"
    assert journal._actions[action_id] == "succeeded"
    assert journal._journal_cost_settlements[action_id].actual_cost_usd == 0.02
    assert (
        journal.run_root / f"producer-receipts/judges/{execution_id}.json"
    ).is_file()
    events = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((journal.run_root / "journal").glob("*.json"))
    ]
    permit_events = [
        event for event in events if event["kind"] == "semantic_request_permit_consumed"
    ]
    assert len(permit_events) == 1
    assert permit_events[0]["data"]["permit"]["dynamic_request_sha256"] == (
        hashlib.sha256(
            (
                json.dumps(
                    judge.calls[0],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode()
        ).hexdigest()
    )
    request_path = journal.run_root / f"semantic-requests/{action_id}.json"
    request_payload = json.loads(request_path.read_text(encoding="utf-8"))
    request_payload["model"] = "tampered/model"
    request_path.write_text(json.dumps(request_payload), encoding="utf-8")
    from scripts.e2e_acceptance import execution

    with pytest.raises(
        execution.ExecutionValidationError,
        match="semantic request|digest",
    ):
        execution.ProtectedExecutionJournal.open(
            protected_root=journal.protected_root,
            run_id=journal.run_id,
            authority=authority,
        )


def test_live_semantic_compiler_rejects_question_hash_not_bound_to_planned_turn(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.live_producer import _semantic_config
    from scripts.e2e_acceptance.production import (
        _producer_handle_record,
        issue_decisive_producer_handle,
    )

    from tests.test_e2e_acceptance_production import _prepared_executed_producer

    registry, authority, journal, plan, _ = _prepared_executed_producer(
        tmp_path,
        semantic_customer_text="Need four synthetic chairs.",
        planned_customer_input_digest="1" * 64,
    )
    handle = issue_decisive_producer_handle(
        registry=registry,
        journal=journal,
        authority=authority,
        sealed_plan=plan,
    )

    with pytest.raises(Exception, match="input binding"):
        _semantic_config(_producer_handle_record(handle))


@pytest.mark.parametrize("preauthorized", [False, True])
def test_live_semantic_compiler_requires_exact_retention_for_active_effect(
    tmp_path: Path,
    preauthorized: bool,
) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.live_producer import IndependentExecutionProducer
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        ProductionAdapterError,
        _write_or_validate_exact,
        issue_decisive_producer_handle,
    )

    from tests.test_e2e_acceptance_production import _prepared_executed_producer

    artifact_id = "crm:contact:contact-test"
    question = "Need four synthetic chairs."
    registry, authority, journal, plan, attempt = _prepared_executed_producer(
        tmp_path,
        semantic_customer_text=question,
        retention_artifact_id=artifact_id if preauthorized else None,
    )
    observed_at = datetime.now(UTC)
    raw = json.dumps(
        {
            "schema_version": "noor-e2e-server-execution-observation/v1",
            "execution_id": attempt.execution_id,
            "observed_at": observed_at.isoformat(),
            "transcript_facts": [_transcript_fact(attempt)],
            "side_effect_facts": [
                {
                    "artifact_id": artifact_id,
                    "subsystem": "crm",
                    "artifact_type": "crm_contact",
                    "baseline_readback": {"state": "absent"},
                    "expected_effect": {"state": "active"},
                    "final_readback": {"state": "active", "status": "customer"},
                    "disposition": "cleanup_pending",
                    "follow_up_suppressed": True,
                    "checksum_refs": ["collector:contact-test"],
                }
            ],
            "baseline_inventory": {artifact_id: {"state": "absent"}},
            "final_inventory": {artifact_id: {"state": "active", "status": "customer"}},
        }
    ).encode()
    _write_or_validate_exact(
        journal.run_root,
        "collector-artifacts/baseline-readback.json",
        {"observation": attempt.baseline.model_dump(mode="json")},
    )
    judge = _PassJudgeTransport()
    producer = IndependentExecutionProducer(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={f"execution:{attempt.execution_id}": raw}
        ),
        judge_transport=judge,
    )
    handle = issue_decisive_producer_handle(
        registry=registry,
        journal=journal,
        authority=authority,
        sealed_plan=plan,
    )

    if not preauthorized:
        with pytest.raises(ProductionAdapterError, match="retention"):
            producer.materialize_next(
                producer_handle=handle,
                observed_at=observed_at + timedelta(seconds=1),
            )
        assert judge.calls == []
        return

    source_ref = producer.materialize_next(
        producer_handle=handle,
        observed_at=observed_at + timedelta(seconds=1),
    )
    source = json.loads(execution._read_protected(journal.run_root, source_ref))
    final = source["attempt"]["final"]["inventory"][artifact_id]
    disposition = source["side_effect_dispositions"][0]
    retention = journal.authorization.side_effect_authority.retention_authorities[0]

    assert final["state"] == "retained"
    assert disposition["disposition"] == "retained_as_test_evidence"
    assert disposition["retention_pre_authorized"] is True
    assert disposition["retention_owner"] == retention.retention_owner
    assert disposition["retention_authority_digest"] == execution._digest(
        retention.model_dump(mode="json")
    )
    assert len(judge.calls) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("step_id", "different-step"),
        ("capability", "outbound_text"),
        ("operation_permission", "fixture:execute"),
        ("subsystem", "outbound_text"),
        ("destination_digest", "e" * 64),
        ("payload_digest", "f" * 64),
        ("idempotency_key", "different-idempotency"),
        ("capability_units", {"model": 2}),
    ],
)
def test_semantic_compiler_rejects_authorized_judge_action_identity_drift(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    from scripts.e2e_acceptance.live_producer import (
        _judge_action,
        _semantic_config,
    )
    from scripts.e2e_acceptance.production import (
        ProductionAdapterError,
        _producer_handle_record,
        issue_decisive_producer_handle,
    )

    from tests.test_e2e_acceptance_production import _prepared_executed_producer

    registry, authority, journal, plan, _ = _prepared_executed_producer(
        tmp_path,
        semantic_customer_text="Need four synthetic chairs.",
        judge_action_updates={field: value},
    )
    handle = issue_decisive_producer_handle(
        registry=registry,
        journal=journal,
        authority=authority,
        sealed_plan=plan,
    )
    record = _producer_handle_record(handle)

    with pytest.raises(ProductionAdapterError, match="action binding"):
        _judge_action(record=record, scenario=_semantic_config(record))


def test_semantic_judge_unknown_action_is_never_retried(tmp_path: Path) -> None:
    import hashlib

    from scripts.e2e_acceptance.live_producer import (
        IndependentExecutionProducer,
        _LiveExecutionObservation,
        _run_or_replay_judge,
        _semantic_config,
    )
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        ProductionAdapterError,
        _producer_handle_record,
        issue_decisive_producer_handle,
    )

    from tests.test_e2e_acceptance_production import _prepared_executed_producer

    registry, authority, journal, plan, attempt = _prepared_executed_producer(
        tmp_path,
        semantic_customer_text="Need four synthetic chairs.",
    )
    observed_at = datetime.now(UTC)
    raw = json.dumps(
        {
            "schema_version": "noor-e2e-server-execution-observation/v1",
            "execution_id": attempt.execution_id,
            "observed_at": observed_at.isoformat(),
            "transcript_facts": [_transcript_fact(attempt)],
            "side_effect_facts": [],
            "baseline_inventory": {"synthetic:item": {"state": "closed"}},
            "final_inventory": {"synthetic:item": {"state": "closed"}},
        }
    ).encode()
    producer = IndependentExecutionProducer(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={f"execution:{attempt.execution_id}": raw}
        ),
    )
    handle = issue_decisive_producer_handle(
        registry=registry,
        journal=journal,
        authority=authority,
        sealed_plan=plan,
    )
    producer.collect_next(
        producer_handle=handle,
        observed_at=observed_at + timedelta(seconds=1),
    )
    record = _producer_handle_record(handle)
    scenario = _semantic_config(record)
    observation = _LiveExecutionObservation.model_validate(json.loads(raw))

    class UncertainJudge:
        def __init__(self) -> None:
            self.calls = 0

        def request(self, request) -> bytes:
            self.calls += 1
            raise RuntimeError("outcome uncertain after dispatch")

    uncertain = UncertainJudge()
    with pytest.raises(RuntimeError, match="uncertain"):
        _run_or_replay_judge(
            producer_handle=handle,
            scenario=scenario,
            observation=observation,
            observation_sha256=hashlib.sha256(raw).hexdigest(),
            transport=uncertain,
        )
    assert uncertain.calls == 1
    assert journal._actions[scenario.judge.action_id] == "unknown"

    replacement = _PassJudgeTransport()
    with pytest.raises(ProductionAdapterError, match="retry is forbidden"):
        _run_or_replay_judge(
            producer_handle=handle,
            scenario=scenario,
            observation=observation,
            observation_sha256=hashlib.sha256(raw).hexdigest(),
            transport=replacement,
        )
    assert replacement.calls == []

    from scripts.e2e_acceptance.live_producer import IndependentActionReconciler

    class NoWazzupRead:
        def read(self, source: str) -> bytes:
            raise AssertionError(f"unexpected Wazzup read: {source}")

    with pytest.raises(
        ProductionAdapterError,
        match="Wazzup action",
    ):
        IndependentActionReconciler(
            collector_id="independent-readback-collector",
            transport=NoWazzupRead(),
        ).materialize(journal, action_id=scenario.judge.action_id)
    assert journal._actions[scenario.judge.action_id] == "unknown"


def test_live_runtime_is_sealed_in_plan_and_bound_to_authority() -> None:
    from scripts.e2e_acceptance import execution
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
        "judge_endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "judge_adapter_id": "openrouter-judge-adapter",
        "judge_timeout_seconds": 75,
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
        adapter_ids=("wazzup-webhook-adapter", "openrouter-judge-adapter"),
        collector_ids=("independent-readback-collector",),
        live_binding=SimpleNamespace(
            target_digest="a" * 64,
            runtime_transport_digest=execution.runtime_transport_digest(config),
        ),
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
    assert components.producer.judge_transport.timeout_seconds == 75

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


def test_openrouter_judge_transport_uses_bound_timeout_without_retry() -> None:
    from scripts.e2e_acceptance.live_transport import (
        OneShotOpenRouterJudgeTransport,
    )

    class Response:
        content = b'{"ok":true}'

        def raise_for_status(self) -> None:
            return None

    class Client:
        def __init__(self) -> None:
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return Response()

    client = Client()
    transport = OneShotOpenRouterJudgeTransport(
        endpoint="https://openrouter.ai/api/v1/chat/completions",
        api_key="protected-key",
        client=client,
        timeout_seconds=75,
    )

    raw = transport.request(
        {
            "model": "fixture/judge",
            "temperature": 0,
            "messages": [{"role": "user", "content": "{}"}],
            "response_format": {"type": "json_schema"},
        }
    )

    assert raw == Response.content
    assert len(client.calls) == 1
    _, kwargs = client.calls[0]
    assert kwargs["timeout"] == 75
    assert kwargs["follow_redirects"] is False
    assert kwargs["headers"]["Authorization"] == "Bearer protected-key"


@pytest.mark.parametrize(
    "field",
    [
        "webhook_endpoint",
        "ssh_host_alias",
        "source_commands",
        "judge_timeout_seconds",
    ],
)
def test_live_runtime_rejects_transport_identity_drift(field: str) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.live_transport import (
        LiveRuntimeConfig,
        build_live_runtime_components,
    )
    from scripts.e2e_acceptance.production import ProductionAdapterError

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
    changed = json.loads(json.dumps(runtime))
    if field == "webhook_endpoint":
        changed[field] = "https://drift.invalid/api/v1/webhook/wazzup"
    elif field == "ssh_host_alias":
        changed[field] = "drift-production"
    elif field == "judge_timeout_seconds":
        changed[field] = 75
    else:
        changed[field]["final"] = ["/usr/bin/cat", "/var/lib/noor/drift.json"]
    base_config = LiveRuntimeConfig.model_validate(runtime)
    authority = SimpleNamespace(
        adapter_ids=("wazzup-webhook-adapter",),
        collector_ids=("independent-readback-collector",),
        live_binding=SimpleNamespace(
            target_digest="a" * 64,
            runtime_transport_digest=execution.runtime_transport_digest(base_config),
        ),
    )

    with pytest.raises(ProductionAdapterError, match="runtime transport"):
        build_live_runtime_components(
            config=LiveRuntimeConfig.model_validate(changed),
            authorization=authority,
            http_client=SimpleNamespace(),
            ssh_runner=SimpleNamespace(),
        )


@pytest.mark.parametrize(
    ("judge_enabled", "adapter_ids"),
    [
        (False, ("wazzup-webhook-adapter",)),
        (
            True,
            ("wazzup-webhook-adapter", "openrouter-judge-adapter"),
        ),
    ],
)
def test_execution_authority_accepts_only_exact_runtime_adapter_set(
    judge_enabled: bool,
    adapter_ids: tuple[str, ...],
) -> None:
    from scripts.e2e_acceptance import execution

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _authorization

    registry = build_canonical_test_registry()
    base = _authorization(registry, trusted=False)
    runtime = execution.RuntimeTransportConfig(
        schema_version="noor-e2e-live-runtime/v1",
        adapter_id="wazzup-webhook-adapter",
        webhook_endpoint="https://noor.starec.ai/api/v1/webhook/wazzup",
        target_digest=base.live_binding.target_digest,
        collector_id="independent-readback-collector",
        ssh_host_alias="noor-production",
        source_commands={
            "baseline": ("/usr/bin/cat", "/var/lib/noor/baseline.json"),
            "final": ("/usr/bin/cat", "/var/lib/noor/final.json"),
        },
        judge_endpoint=(
            "https://openrouter.ai/api/v1/chat/completions" if judge_enabled else None
        ),
        judge_adapter_id=("openrouter-judge-adapter" if judge_enabled else None),
    )
    action_specs = tuple(
        item.model_copy(update={"adapter_id": adapter_ids[0]})
        for item in base.action_specs
    )
    candidate = base.model_copy(
        update={
            "adapter_ids": adapter_ids,
            "action_specs": action_specs,
            "live_binding": base.live_binding.model_copy(
                update={
                    "adapter_ids_digest": execution._digest(adapter_ids),
                    "runtime_transport_digest": execution.runtime_transport_digest(
                        runtime
                    ),
                }
            ),
        }
    )

    execution.validate_execution_authorization(
        candidate,
        policy=registry.compiled_policy,
        plan=registry.compiled_plan,
        registry_id=registry.registry_id,
        runtime_transport=runtime,
    )


@pytest.mark.parametrize(
    "adapter_ids",
    [
        ("openrouter-judge-adapter",),
        ("fake-local-adapter", "wazzup-webhook-adapter"),
        ("wazzup-webhook-adapter", "fake-local-adapter"),
        (
            "fake-local-adapter",
            "wazzup-webhook-adapter",
            "openrouter-judge-adapter",
        ),
    ],
)
def test_execution_authority_rejects_mixed_or_partial_adapter_sets(
    adapter_ids: tuple[str, ...],
) -> None:
    from scripts.e2e_acceptance import execution

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _authorization

    registry = build_canonical_test_registry()
    base = _authorization(registry, trusted=False)
    candidate = base.model_copy(
        update={
            "adapter_ids": adapter_ids,
            "action_specs": tuple(
                item.model_copy(update={"adapter_id": adapter_ids[0]})
                for item in base.action_specs
            ),
            "live_binding": base.live_binding.model_copy(
                update={
                    "adapter_ids_digest": execution._digest(adapter_ids),
                    "runtime_transport_digest": "f" * 64,
                }
            ),
        }
    )

    with pytest.raises(
        execution.ExecutionValidationError,
        match="adapter|runtime transport",
    ):
        execution.validate_execution_authorization(
            candidate,
            policy=registry.compiled_policy,
            plan=registry.compiled_plan,
            registry_id=registry.registry_id,
        )


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
    reconciliation_observed_at = datetime.now(UTC)
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
        observed_at=reconciliation_observed_at,
        expires_at=reconciliation_observed_at.replace(
            year=reconciliation_observed_at.year + 1
        ),
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


def _prepared_unknown_action(tmp_path: Path, *, run_id: str):
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import _write_or_validate_exact

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import (
        _action_quota_charge,
        _issued_authority,
    )

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
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
    request = {
        "execution_id": "SC-OPEN-EN",
        "step_id": "fixture-step-001",
        "capability": "webhook.inbound",
        "operation_permission": "fixture:execute",
        "destination_digest": "a" * 64,
        "payload_digest": execution._digest(payload),
        "idempotency_key": "fixture-idempotency-001",
        "capability_units": {"outbound_text": 1},
    }
    spec = execution.AuthorizedActionSpec(
        action_id="synthetic-action",
        adapter_id="wazzup-webhook-adapter",
        subsystem="outbound_text",
        quota_charge=_action_quota_charge(execution),
        **request,
    )
    authority = _issued_authority(
        registry,
        protected_root=root,
        run_id=run_id,
        action_specs=execution.AuthorizedActionSpecs(
            schema_version="noor-e2e-authorized-action-specs/v2",
            specs=(spec,),
        ),
        runtime_wazzup=True,
    )
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root,
        run_id=run_id,
        authority=authority,
    )
    journal.seal_baseline(
        execution.ReadbackObservation.build(
            phase="baseline",
            collector_id="independent-readback-collector",
            source_id="baseline",
            run_id=journal.run_id,
            preflight_digest=journal.authorization.preflight_digest,
            collector_artifact_digest=journal.authorization.readback_collector_digest,
            causal_event_digest="a" * 64,
            observed_at=datetime.now(UTC) - timedelta(seconds=1),
            inventory={"synthetic:item": {"state": "absent"}},
        )
    )
    journal.begin_execution()
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
    _write_or_validate_exact(
        journal.run_root,
        f"requests/{action_id}.json",
        payload,
    )
    journal.consume_permit(reservation, adapter_id=adapter_id, **request)
    return registry, journal, reservation


def _wazzup_reconciliation_payload(observed_at: datetime) -> dict[str, object]:
    return {
        "schema_version": "noor-e2e-wazzup-action-reconciliation/v2",
        "adapter_id": "wazzup-webhook-adapter",
        "capability": "webhook.inbound",
        "observed_at": observed_at.isoformat(),
        "resolved_state": "succeeded",
        "source_message_ids": ["synthetic-message"],
        "audit_ids": ["synthetic-audit"],
        "outbound_provider_message_ids": ["synthetic-provider-message"],
        "outbound_statuses": ["delivered"],
        "inventory": {"synthetic:item": {"state": "present"}},
        "actual_cost_usd": 0.10,
    }


def test_live_reconciliation_requires_current_action_causal_identity(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.live_producer import IndependentActionReconciler
    from scripts.e2e_acceptance.production import FakeReadOnlySshTransport

    _, journal, reservation = _prepared_unknown_action(
        tmp_path, run_id="live-causal-reconciliation"
    )
    observed_at = datetime.now(UTC)
    raw = json.dumps(_wazzup_reconciliation_payload(observed_at)).encode()

    digest = IndependentActionReconciler(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={f"reconciliation:{reservation.action_id}": raw}
        ),
    ).materialize(
        journal,
        action_id=reservation.action_id,
        current_time=observed_at + timedelta(seconds=1),
    )

    receipt = execution.UnknownActionReconciliationReceipt.model_validate(
        json.loads(
            execution._read_protected(
                journal.run_root,
                f"independent-reconciliation/{reservation.action_id}.json",
            )
        )
    )
    assert len(digest) == 64
    assert receipt.causal_event_digest == journal.previous_event_digest


def test_live_reconciler_rejects_pre_dispatch_stale_snapshot(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.live_producer import IndependentActionReconciler
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        ProductionAdapterError,
    )

    _, journal, reservation = _prepared_unknown_action(
        tmp_path, run_id="live-stale-reconciliation"
    )
    now = datetime.now(UTC)
    raw = json.dumps(
        _wazzup_reconciliation_payload(
            reservation.issued_at - timedelta(microseconds=1)
        )
    ).encode()

    with pytest.raises(ProductionAdapterError, match="binding|lower bound|stale"):
        IndependentActionReconciler(
            collector_id="independent-readback-collector",
            transport=FakeReadOnlySshTransport(
                responses={f"reconciliation:{reservation.action_id}": raw}
            ),
        ).materialize(
            journal,
            action_id=reservation.action_id,
            current_time=now,
        )


def test_live_reconciler_rejects_server_supplied_journal_binding(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.live_producer import IndependentActionReconciler
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        ProductionAdapterError,
    )

    _, journal, reservation = _prepared_unknown_action(
        tmp_path, run_id="live-causal-drift"
    )
    now = datetime.now(UTC)
    payload = _wazzup_reconciliation_payload(now)
    payload["causal_event_digest"] = "b" * 64
    raw = json.dumps(payload).encode()

    with pytest.raises(ProductionAdapterError, match="invalid"):
        IndependentActionReconciler(
            collector_id="independent-readback-collector",
            transport=FakeReadOnlySshTransport(
                responses={f"reconciliation:{reservation.action_id}": raw}
            ),
        ).materialize(
            journal,
            action_id=reservation.action_id,
            current_time=now + timedelta(seconds=1),
        )


def test_journal_rejects_reconciliation_observed_before_permit_consumption(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance import execution

    registry, journal, reservation = _prepared_unknown_action(
        tmp_path, run_id="stale-reconciliation"
    )
    now = datetime.now(UTC)
    receipt = execution.UnknownActionReconciliationReceipt(
        schema_version="noor-e2e-unknown-action-reconciliation/v2",
        registry_id=registry.registry_id,
        run_id=journal.run_id,
        authorization_digest=journal.authorization_digest,
        action_id=reservation.action_id,
        reservation_digest=reservation.reservation_digest,
        collector_id="independent-readback-collector",
        producer="independent-readback-collector",
        causal_event_digest=journal.previous_event_digest,
        observed_at=reservation.issued_at - timedelta(microseconds=1),
        expires_at=now + timedelta(minutes=1),
        resolved_state="succeeded",
        inventory_digest="d" * 64,
        actual_cost_usd=0.10,
    )
    receipt_digest = execution._write_exclusive(
        journal.run_root,
        f"independent-reconciliation/{reservation.action_id}.json",
        receipt.model_dump(mode="json"),
    )

    with pytest.raises(
        execution.ExecutionValidationError, match="fresh independent reconciliation"
    ):
        journal.reconcile_unknown_action(
            action_id=reservation.action_id,
            receipt_digest=receipt_digest,
        )


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
    execution._write_test_authority_bundle(
        **inputs,
        runtime_transport=execution.RuntimeTransportConfig.model_validate(runtime),
    )
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
                payload = _wazzup_reconciliation_payload(datetime.now(UTC))
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
