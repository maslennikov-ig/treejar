"""Conservative production gate producer for unavailable live proof.

This module never executes a customer or provider action. It can only derive a
``BLOCKED`` result for the next canonical execution from the immutable scenario
kind and the trusted registry. The caller cannot select an execution, outcome,
producer, criterion set, or reason.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.policy import (
    ClassifierResult,
    OracleEvidence,
    ReadbackObservation,
    ReadbackResult,
    StructuredEvent,
)
from scripts.e2e_acceptance.production import (
    DecisiveProducerHandle,
    ProductionAdapterError,
    ProtectedEvaluatorConfig,
    _evaluator_bindings,
    _execution_assertion_ids,
    _producer_handle_record,
    _ProducerHandleRecord,
    _read_protected_json,
    _write_or_validate_bytes,
    _write_or_validate_exact,
    _write_producer_observation,
)

BlockReason = Literal[
    "disjoint_identity_unavailable",
    "provider_origin_unavailable",
    "independent_evidence_unavailable",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _ServerToolTraceFact(_StrictModel):
    call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    arguments_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: Literal["returned"]


class _TranscriptFact(_StrictModel):
    turn_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    sent_at: datetime
    received_at: datetime
    first_visible_at: datetime
    final_visible_at: datetime
    delivered_at: datetime | None
    duration_ms: int = Field(ge=0)
    conversation_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    provider_message_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tool_traces: tuple[_ServerToolTraceFact, ...]
    tools: tuple[str, ...]
    tool_outcomes: tuple[str, ...]
    audit_ids: tuple[str, ...]
    media_refs: tuple[str, ...]
    token_count: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    deviation: str | None
    evaluator_reasoning: str = Field(min_length=1)

    @model_validator(mode="after")
    def _timeline_and_duration(self) -> _TranscriptFact:
        required = (
            self.sent_at,
            self.received_at,
            self.first_visible_at,
            self.final_visible_at,
        )
        if any(value.tzinfo is None or value.utcoffset() is None for value in required):
            raise ValueError("live transcript timestamps must be timezone-aware")
        if not (
            self.sent_at
            <= self.received_at
            <= self.first_visible_at
            <= self.final_visible_at
        ):
            raise ValueError("live transcript timeline is invalid")
        if self.delivered_at is not None and (
            self.delivered_at.tzinfo is None
            or self.delivered_at.utcoffset() is None
            or self.delivered_at < self.final_visible_at
        ):
            raise ValueError("live transcript delivery time is invalid")
        derived = int((self.final_visible_at - self.sent_at).total_seconds() * 1000)
        if self.duration_ms != derived:
            raise ValueError("live transcript duration differs from timestamps")
        if len(self.tools) != len(self.tool_outcomes):
            raise ValueError("live transcript tool outcomes are incomplete")
        if self.tools != tuple(item.tool_name for item in self.tool_traces):
            raise ValueError("live transcript tool trace names drift")
        return self


class _ServerSideEffectFact(_StrictModel):
    artifact_id: str = Field(min_length=1)
    subsystem: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    baseline_readback: dict[str, Any]
    expected_effect: dict[str, Any]
    final_readback: dict[str, Any]
    disposition: Literal[
        "voided",
        "closed",
        "resolved",
        "retained_as_test_evidence",
        "cleanup_pending",
    ]
    follow_up_suppressed: bool
    checksum_refs: tuple[str, ...] = Field(min_length=1)


class _LiveExecutionObservation(_StrictModel):
    schema_version: Literal["noor-e2e-server-execution-observation/v1"]
    execution_id: str = Field(min_length=1)
    observed_at: datetime
    transcript_facts: tuple[_TranscriptFact, ...]
    side_effect_facts: tuple[_ServerSideEffectFact, ...]
    baseline_inventory: dict[str, dict[str, Any]]
    final_inventory: dict[str, dict[str, Any]]

    @model_validator(mode="after")
    def _aware_observation(self) -> _LiveExecutionObservation:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("live execution observation time must be aware")
        changed = {
            identity
            for identity in set(self.baseline_inventory) | set(self.final_inventory)
            if self.baseline_inventory.get(identity)
            != self.final_inventory.get(identity)
        }
        listed = [item.artifact_id for item in self.side_effect_facts]
        if changed != set(listed) or len(listed) != len(set(listed)):
            raise ValueError("live side effects do not cover inventory delta")
        return self


class _SemanticJudgeConfig(_StrictModel):
    schema_version: Literal["noor-e2e-semantic-judge/v1"]
    action_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    operation_permission: Literal["paid_model_call"]
    subsystem: Literal["model"]
    destination_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=1)
    capability_units: dict[str, int]
    model: str = Field(min_length=1)
    temperature: Literal[0]
    max_calls: Literal[1]
    max_cost_usd: float = Field(gt=0)
    rubric_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _finite_cost(self) -> _SemanticJudgeConfig:
        if (
            not math.isfinite(self.max_cost_usd)
            or self.capability_units != {"model": 1}
            or self.destination_digest
            != execution._digest(
                {
                    "adapter_id": self.adapter_id,
                    "model": self.model,
                    "transport": "openrouter-chat-completions",
                }
            )
        ):
            raise ValueError("semantic judge action identity is invalid")
        return self


class _TrustedEvidenceRef(_StrictModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_path: str = Field(min_length=1)
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _safe_path(self) -> _TrustedEvidenceRef:
        paths = (self.relative_path, self.receipt_path)
        if any(
            value.startswith("/")
            or any(part in {"", ".", ".."} for part in value.split("/"))
            for value in paths
        ):
            raise ValueError("trusted evidence path is unsafe")
        return self


class _SemanticScenarioConfig(_StrictModel):
    execution_id: str = Field(min_length=1)
    planned_turns: tuple[execution.PlannedTurnV2, ...] = Field(min_length=1)
    tester_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    judge_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_text_sha256: dict[str, str] = Field(min_length=1)
    trusted_evidence_refs: dict[str, _TrustedEvidenceRef] = Field(default_factory=dict)
    judge: _SemanticJudgeConfig

    @model_validator(mode="after")
    def _bind_turns_and_judge(self) -> _SemanticScenarioConfig:
        turn_ids = tuple(item.turn_id for item in self.planned_turns)
        if (
            len(turn_ids) != len(set(turn_ids))
            or set(self.input_text_sha256) != set(turn_ids)
            or any(
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in self.input_text_sha256.values()
            )
            or self.judge.step_id != f"{self.execution_id}:semantic-judge"
            or self.judge.idempotency_key
            != f"{self.judge.action_id}:{self.execution_id}"
            or self.judge_config_digest
            != execution._digest(self.judge.model_dump(mode="json"))
        ):
            raise ValueError("semantic scenario turn/judge binding drift")
        return self


class _SemanticCompilerConfig(_StrictModel):
    schema_version: Literal["noor-e2e-semantic-compiler/v1"]
    compiler_id: Literal["treejar.live-semantic-compiler.v1"]
    scenarios: dict[str, _SemanticScenarioConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _bind_scenario_keys(self) -> _SemanticCompilerConfig:
        if any(key != value.execution_id for key, value in self.scenarios.items()):
            raise ValueError("semantic compiler scenario key drift")
        action_ids = [item.judge.action_id for item in self.scenarios.values()]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("semantic judge actions must be unique")
        return self


class _JudgeVerdict(_StrictModel):
    assertion_id: str = Field(min_length=1)
    passed: bool
    reason: str = Field(min_length=1, max_length=600)


class _JudgeDecisionEnvelope(_StrictModel):
    schema_version: Literal["noor-e2e-semantic-judge-result/v1"]
    execution_id: str = Field(min_length=1)
    observation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdicts: tuple[_JudgeVerdict, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_verdicts(self) -> _JudgeDecisionEnvelope:
        identities = [item.assertion_id for item in self.verdicts]
        if len(identities) != len(set(identities)):
            raise ValueError("semantic judge verdicts must be unique")
        return self


class _JudgeTransport(Protocol):
    def request(self, request: Mapping[str, Any]) -> bytes: ...


class _LiveActionReconciliation(_StrictModel):
    schema_version: Literal["noor-e2e-server-action-reconciliation/v1"]
    action_id: str = Field(min_length=1)
    observed_at: datetime
    resolved_state: Literal["succeeded", "failed"]
    inventory: dict[str, Any]
    actual_cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def _aware_and_finite(self) -> _LiveActionReconciliation:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("live reconciliation time must be aware")
        return self


class _ReadOnlyTransport(Protocol):
    def read(self, source: str) -> bytes: ...


def _semantic_config(record: _ProducerHandleRecord) -> _SemanticScenarioConfig:
    evaluator = ProtectedEvaluatorConfig.model_validate(record.sealed_plan.evaluator)
    raw = evaluator.publication.get("semantic_compiler")
    try:
        config = _SemanticCompilerConfig.model_validate(raw)
        scenario = config.scenarios[record.execution_id]
    except (KeyError, TypeError, ValidationError) as exc:
        raise ProductionAdapterError(
            "sealed semantic compiler configuration is unavailable"
        ) from exc
    authorized_digest = record.journal.authorization.execution_input_digests[
        record.execution_id
    ]
    if (
        execution.scenario_input_digest(
            execution_id=record.execution_id,
            planned_turns=scenario.planned_turns,
            tester_config_digest=scenario.tester_config_digest,
            judge_config_digest=scenario.judge_config_digest,
        )
        != authorized_digest
    ):
        raise ProductionAdapterError("sealed semantic scenario input binding drift")
    return scenario


def _criterion_ids(record: _ProducerHandleRecord) -> tuple[str, ...]:
    return tuple(
        criterion.criterion_id
        for criterion in record.registry.compiled_plan.criteria.values()
        if record.execution_id in criterion.obligation_ids
    )


def _assertion_payload(
    record: _ProducerHandleRecord,
) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "assertion_id": assertion_id,
            "canonical_text": record.registry.compiled_policy.assertions[
                assertion_id
            ].canonical_text,
            "oracle_kind": record.registry.compiled_policy.assertions[
                assertion_id
            ].oracle.kind,
        }
        for assertion_id in sorted(
            _execution_assertion_ids(record.registry, record.execution_id)
        )
        if record.registry.compiled_policy.assertions[assertion_id].oracle.kind
        not in {"external_gate_evidence", "reused_exact_evidence"}
    )


def _judge_request(
    *,
    record: _ProducerHandleRecord,
    scenario: _SemanticScenarioConfig,
    observation: _LiveExecutionObservation,
    observation_sha256: str,
) -> dict[str, Any]:
    assertions = _assertion_payload(record)
    if execution._digest(assertions) != scenario.judge.rubric_digest:
        raise ProductionAdapterError("sealed semantic judge rubric binding drift")
    facts = {
        "execution_id": record.execution_id,
        "observation_sha256": observation_sha256,
        "assertions": assertions,
        "turns": [
            {
                "turn_id": item.turn_id,
                "question": item.question,
                "answer": item.answer,
                "tools": item.tools,
                "tool_outcomes": item.tool_outcomes,
                "duration_ms": item.duration_ms,
                "media_refs": item.media_refs,
            }
            for item in observation.transcript_facts
        ],
        "side_effects": [
            {
                "artifact_id": item.artifact_id,
                "subsystem": item.subsystem,
                "artifact_type": item.artifact_type,
                "baseline_readback": item.baseline_readback,
                "expected_effect": item.expected_effect,
                "final_readback": item.final_readback,
                "disposition": item.disposition,
            }
            for item in observation.side_effect_facts
        ],
        "baseline_inventory": observation.baseline_inventory,
        "final_inventory": observation.final_inventory,
    }
    response_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "execution_id",
            "observation_sha256",
            "verdicts",
        ],
        "properties": {
            "schema_version": {
                "type": "string",
                "const": "noor-e2e-semantic-judge-result/v1",
            },
            "execution_id": {"type": "string", "const": record.execution_id},
            "observation_sha256": {
                "type": "string",
                "const": observation_sha256,
            },
            "verdicts": {
                "type": "array",
                "minItems": len(assertions),
                "maxItems": len(assertions),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["assertion_id", "passed", "reason"],
                    "properties": {
                        "assertion_id": {"type": "string"},
                        "passed": {"type": "boolean"},
                        "reason": {"type": "string", "minLength": 1, "maxLength": 600},
                    },
                },
            },
        },
    }
    return {
        "model": scenario.judge.model,
        "temperature": scenario.judge.temperature,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Evaluate every assertion only from the supplied facts. "
                    "Missing proof fails. Return the required JSON."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    facts,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "noor_e2e_semantic_verdicts",
                "strict": True,
                "schema": response_schema,
            },
        },
    }


def _judge_action(
    *,
    record: _ProducerHandleRecord,
    scenario: _SemanticScenarioConfig,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    matches = [
        item
        for item in record.sealed_plan.actions
        if isinstance(item.get("spec"), dict)
        and item["spec"].get("action_id") == scenario.judge.action_id
    ]
    if len(matches) != 1:
        raise ProductionAdapterError("sealed semantic judge action is unavailable")
    action = matches[0]
    spec = dict(action["spec"])
    message_path = action.get("message_path")
    if not isinstance(message_path, str):
        raise ProductionAdapterError("sealed semantic judge request path is invalid")
    request = _read_protected_json(record.journal.run_root, message_path)
    expected_request = {
        "schema_version": "noor-e2e-semantic-judge-action/v1",
        "execution_id": record.execution_id,
        "source_ref": f"collector-raw/executions/{record.execution_id}.json",
        "judge_config_digest": scenario.judge_config_digest,
    }
    charge = spec.get("quota_charge")
    if (
        request != expected_request
        or spec.get("execution_id") != record.execution_id
        or spec.get("step_id") != scenario.judge.step_id
        or spec.get("capability") != "model.classify"
        or spec.get("operation_permission") != scenario.judge.operation_permission
        or spec.get("adapter_id") != scenario.judge.adapter_id
        or spec.get("subsystem") != scenario.judge.subsystem
        or spec.get("destination_digest") != scenario.judge.destination_digest
        or spec.get("payload_digest") != execution._digest(request)
        or spec.get("idempotency_key") != scenario.judge.idempotency_key
        or spec.get("capability_units") != scenario.judge.capability_units
        or not isinstance(charge, dict)
        or charge.get("messages") != 0
        or charge.get("model_calls") != 1
        or charge.get("max_cost_usd") != scenario.judge.max_cost_usd
        or charge.get("cost_settlement") != "bounded_actual"
    ):
        raise ProductionAdapterError("sealed semantic judge action binding drift")
    return spec, request, message_path


def _parse_judge_response(
    *,
    raw: bytes,
    record: _ProducerHandleRecord,
    scenario: _SemanticScenarioConfig,
    observation_sha256: str,
) -> tuple[_JudgeDecisionEnvelope, float, int]:
    try:
        payload = json.loads(raw)
        choices = payload["choices"]
        usage = payload["usage"]
        provider_model = payload["model"]
        content = choices[0]["message"]["content"]
        cost = float(usage["cost"])
        total_tokens = int(usage["total_tokens"])
        decision = _JudgeDecisionEnvelope.model_validate(json.loads(content))
    except (
        IndexError,
        KeyError,
        TypeError,
        ValueError,
        ValidationError,
        json.JSONDecodeError,
    ) as exc:
        raise ProductionAdapterError("semantic judge response is invalid") from exc
    expected_assertions = {item["assertion_id"] for item in _assertion_payload(record)}
    if (
        provider_model != scenario.judge.model
        or decision.execution_id != record.execution_id
        or decision.observation_sha256 != observation_sha256
        or {item.assertion_id for item in decision.verdicts} != expected_assertions
        or not math.isfinite(cost)
        or cost < 0
        or cost > scenario.judge.max_cost_usd
        or total_tokens < 0
    ):
        raise ProductionAdapterError("semantic judge response binding drift")
    return decision, cost, total_tokens


def _run_or_replay_judge(
    *,
    producer_handle: DecisiveProducerHandle,
    scenario: _SemanticScenarioConfig,
    observation: _LiveExecutionObservation,
    observation_sha256: str,
    transport: _JudgeTransport | None,
) -> tuple[_JudgeDecisionEnvelope, str, datetime]:
    record = _producer_handle_record(producer_handle)
    spec, static_request, _ = _judge_action(record=record, scenario=scenario)
    action_id = scenario.judge.action_id
    raw_ref = f"judge-raw/{record.execution_id}.json"
    receipt_ref = f"producer-receipts/judges/{record.execution_id}.json"
    state = record.journal._actions.get(action_id)
    try:
        receipt = _read_protected_json(record.journal.run_root, receipt_ref)
    except ProductionAdapterError:
        receipt = None
    if state == "succeeded":
        if receipt is None:
            raise ProductionAdapterError("semantic judge receipt is unavailable")
        raw = execution._read_protected(record.journal.run_root, raw_ref)
        decision, actual_cost, total_tokens = _parse_judge_response(
            raw=raw,
            record=record,
            scenario=scenario,
            observation_sha256=observation_sha256,
        )
        raw_sha256 = hashlib.sha256(raw).hexdigest()
        if (
            receipt.get("schema_version") != "noor-e2e-semantic-judge-receipt/v1"
            or receipt.get("run_id") != record.journal.run_id
            or receipt.get("execution_id") != record.execution_id
            or receipt.get("action_id") != action_id
            or receipt.get("authorization_digest")
            != record.journal.authorization_digest
            or receipt.get("judge_config_digest") != scenario.judge_config_digest
            or receipt.get("observation_sha256") != observation_sha256
            or receipt.get("raw_ref") != raw_ref
            or receipt.get("raw_sha256") != raw_sha256
            or receipt.get("actual_cost_usd") != actual_cost
            or receipt.get("total_tokens") != total_tokens
        ):
            raise ProductionAdapterError("semantic judge receipt binding drift")
        settlement = record.journal._journal_cost_settlements.get(action_id)
        if (
            settlement is None
            or settlement.actual_cost_usd != actual_cost
            or settlement.reservation_digest
            != record.journal._reservations[action_id].reservation_digest
        ):
            raise ProductionAdapterError(
                "semantic judge action settlement binding drift"
            )
        try:
            judged_at = datetime.fromisoformat(str(receipt["judged_at"]))
        except (KeyError, ValueError) as exc:
            raise ProductionAdapterError(
                "semantic judge receipt time is invalid"
            ) from exc
        return decision, raw_sha256, judged_at

    if state in {"unknown", "failed"}:
        raise ProductionAdapterError(
            "semantic judge outcome is unknown; retry is forbidden"
        )
    if receipt is not None:
        raise ProductionAdapterError("semantic judge receipt precedes terminal action")
    if transport is None:
        raise ProductionAdapterError("semantic judge transport is unavailable")
    charge = dict(spec["quota_charge"])
    reserve_values = dict(spec)
    reserve_values.pop("quota_charge")
    reserve_values.pop("action_id")
    reserve_values.pop("adapter_id")
    reserve_values.pop("subsystem")
    if state == "reserved":
        reservation = record.journal._reservations[action_id]
    else:
        reservation = record.journal.reserve_action(
            action_id=action_id,
            adapter_id=str(spec["adapter_id"]),
            subsystem=str(spec["subsystem"]),
            messages=int(charge["messages"]),
            model_calls=int(charge["model_calls"]),
            cost_usd=float(charge["max_cost_usd"]),
            **reserve_values,
        )
    dynamic_request = _judge_request(
        record=record,
        scenario=scenario,
        observation=observation,
        observation_sha256=observation_sha256,
    )
    record.journal.consume_permit(
        reservation,
        adapter_id=reservation.adapter_id,
        execution_id=reservation.execution_id,
        step_id=reservation.step_id,
        capability=reservation.capability,
        operation_permission=reservation.operation_permission,
        destination_digest=reservation.destination_digest,
        payload_digest=execution._digest(static_request),
        idempotency_key=reservation.idempotency_key,
        capability_units=reservation.capability_units,
    )
    raw = transport.request(dynamic_request)
    if not isinstance(raw, bytes):
        raise ProductionAdapterError("semantic judge transport returned non-bytes")
    raw_sha256 = _write_or_validate_bytes(record.journal.run_root, raw_ref, raw)
    decision, actual_cost, total_tokens = _parse_judge_response(
        raw=raw,
        record=record,
        scenario=scenario,
        observation_sha256=observation_sha256,
    )
    judged_at = datetime.now(UTC)
    receipt_digest = _write_or_validate_exact(
        record.journal.run_root,
        receipt_ref,
        {
            "schema_version": "noor-e2e-semantic-judge-receipt/v1",
            "run_id": record.journal.run_id,
            "execution_id": record.execution_id,
            "action_id": action_id,
            "authorization_digest": record.journal.authorization_digest,
            "judge_config_digest": scenario.judge_config_digest,
            "observation_sha256": observation_sha256,
            "raw_ref": raw_ref,
            "raw_sha256": raw_sha256,
            "actual_cost_usd": actual_cost,
            "total_tokens": total_tokens,
            "judged_at": judged_at.isoformat(),
        },
    )
    record.journal.complete_action(
        reservation,
        state="succeeded",
        outcome_digest=raw_sha256,
        trusted_receipt_digest=receipt_digest,
        actual_cost_usd=actual_cost,
    )
    return decision, raw_sha256, judged_at


def _load_baseline(record: _ProducerHandleRecord) -> ReadbackObservation:
    try:
        artifact = _read_protected_json(
            record.journal.run_root,
            "collector-artifacts/baseline-readback.json",
        )
        observation = ReadbackObservation.model_validate(artifact["observation"])
    except (KeyError, ValidationError, ProductionAdapterError) as exc:
        raise ProductionAdapterError(
            "protected baseline observation is unavailable"
        ) from exc
    authorization = record.journal.authorization
    if (
        observation.phase != "baseline"
        or observation.run_id != record.journal.run_id
        or observation.content_digest != record.journal._baseline_content_digest
        or observation.preflight_digest != authorization.preflight_digest
        or observation.collector_id not in authorization.collector_ids
        or observation.collector_artifact_digest
        != authorization.readback_collector_digest
    ):
        raise ProductionAdapterError("protected baseline observation binding drift")
    return observation


def _retention_for(
    *,
    record: _ProducerHandleRecord,
    artifact_id: str,
    observed_at: datetime,
) -> execution.AuthorizedRetentionSpec:
    criterion_ids = _criterion_ids(record)
    matches = [
        item
        for item in record.journal.authorization.side_effect_authority.retention_authorities
        if item.artifact_id == artifact_id
        and item.execution_id == record.execution_id
        and item.criterion_ids == criterion_ids
        and item.cleanup_owner
        == record.journal.authorization.side_effect_authority.cleanup_owner
        and item.cleanup_authority
        == record.journal.authorization.side_effect_authority.cleanup_authority
        and item.issued_at <= observed_at < item.expires_at
    ]
    if len(matches) != 1:
        raise ProductionAdapterError(
            "active side effect lacks exact preauthorized retention"
        )
    return matches[0]


def _compile_side_effects(
    *,
    record: _ProducerHandleRecord,
    observation: _LiveExecutionObservation,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    final_inventory = {
        artifact_id: dict(value)
        for artifact_id, value in observation.final_inventory.items()
    }
    authority = record.journal.authorization.side_effect_authority
    dispositions: list[dict[str, Any]] = []
    for fact in observation.side_effect_facts:
        disposition = fact.disposition
        retention_fields: dict[str, Any] = {}
        if disposition == "cleanup_pending":
            retention = _retention_for(
                record=record,
                artifact_id=fact.artifact_id,
                observed_at=observation.observed_at,
            )
            disposition = "retained_as_test_evidence"
            final_inventory[fact.artifact_id] = {
                **fact.final_readback,
                "state": "retained",
            }
            retention_fields = {
                "retention_pre_authorized": True,
                "retention_owner": retention.retention_owner,
                "retention_authority_digest": execution._digest(
                    retention.model_dump(mode="json")
                ),
                "retention_expires_at": retention.expires_at.isoformat(),
                "final_disposition_date": observation.observed_at.isoformat(),
            }
        dispositions.append(
            {
                "artifact_id": fact.artifact_id,
                "scenario_id": record.execution_id,
                "subsystem": fact.subsystem,
                "artifact_type": fact.artifact_type,
                "expected_effect": fact.expected_effect,
                "disposition": disposition,
                "owner": authority.cleanup_owner,
                "cleanup_authority": authority.cleanup_authority,
                "follow_up_suppressed": fact.follow_up_suppressed,
                "checksum_refs": fact.checksum_refs,
                **retention_fields,
            }
        )
    return final_inventory, dispositions


def _load_trusted_evidence(
    *,
    record: _ProducerHandleRecord,
    scenario: _SemanticScenarioConfig,
) -> dict[str, StructuredEvent]:
    required = {
        assertion_id
        for assertion_id in _execution_assertion_ids(
            record.registry, record.execution_id
        )
        if record.registry.compiled_policy.assertions[assertion_id].oracle.kind
        in {"external_gate_evidence", "reused_exact_evidence"}
    }
    if set(scenario.trusted_evidence_refs) != required:
        raise ProductionAdapterError(
            "sealed trusted evidence references do not cover external assertions"
        )
    binding = _evaluator_bindings(record.sealed_plan).get("trusted-evidence-registry")
    if required and (
        binding is None
        or binding.producer_kind != "trusted-registry"
        or binding.source_identity != "trusted-evidence-registry"
    ):
        raise ProductionAdapterError("trusted evidence producer is not sealed")
    result: dict[str, StructuredEvent] = {}
    for assertion_id, source in scenario.trusted_evidence_refs.items():
        raw = execution._read_protected(record.journal.run_root, source.relative_path)
        if hashlib.sha256(raw).hexdigest() != source.sha256:
            raise ProductionAdapterError("protected trusted evidence digest drift")
        receipt_raw = execution._read_protected(
            record.journal.run_root, source.receipt_path
        )
        if hashlib.sha256(receipt_raw).hexdigest() != source.receipt_sha256:
            raise ProductionAdapterError(
                "protected trusted evidence receipt digest drift"
            )
        try:
            payload = json.loads(raw)
            receipt = json.loads(receipt_raw)
            artifact_payload = (
                payload["artifact"]
                if isinstance(payload, dict) and "artifact" in payload
                else payload
            )
            artifact = StructuredEvent.model_validate(artifact_payload)
        except (KeyError, TypeError, ValidationError, json.JSONDecodeError) as exc:
            raise ProductionAdapterError(
                "protected trusted evidence is invalid"
            ) from exc
        assertion = record.registry.compiled_policy.assertions[assertion_id]
        prefix = (
            "trusted-registry:external-gate:"
            if assertion.oracle.kind == "external_gate_evidence"
            else "trusted-registry:reused:"
        )
        authorization = record.journal.authorization
        if (
            artifact.assertion_id != assertion_id
            or artifact.producer != "trusted-evidence-registry"
            or artifact.producer not in assertion.oracle.allowed_producers
            or not artifact.source_id.startswith(prefix)
            or artifact.run_id != record.journal.run_id
            or artifact.attempt_digest
            != authorization.execution_input_digests[record.execution_id]
            or artifact.preflight_digest != authorization.preflight_digest
            or not authorization.issued_at
            <= artifact.observed_at
            < authorization.expires_at
            or not isinstance(receipt, dict)
            or receipt.get("schema_version") != "noor-e2e-trusted-evidence-receipt/v1"
            or receipt.get("registry_id") != record.registry.registry_id
            or receipt.get("run_id") != record.journal.run_id
            or receipt.get("execution_id") != record.execution_id
            or receipt.get("assertion_id") != assertion_id
            or receipt.get("producer") != "trusted-evidence-registry"
            or receipt.get("artifact_ref") != source.relative_path
            or receipt.get("artifact_sha256") != source.sha256
        ):
            raise ProductionAdapterError("protected trusted evidence binding drift")
        result[assertion_id] = artifact
    return result


def _compile_oracles(
    *,
    record: _ProducerHandleRecord,
    scenario: _SemanticScenarioConfig,
    decision: _JudgeDecisionEnvelope,
    observation: _LiveExecutionObservation,
    observation_sha256: str,
    judge_sha256: str,
    judged_at: datetime,
    trusted_evidence: Mapping[str, StructuredEvent],
) -> tuple[OracleEvidence, ...]:
    verdicts = {item.assertion_id: item for item in decision.verdicts}
    bindings = _evaluator_bindings(record.sealed_plan)
    attempt_digest = record.journal.authorization.execution_input_digests[
        record.execution_id
    ]
    evidence: list[OracleEvidence] = []
    for assertion_id in sorted(
        _execution_assertion_ids(record.registry, record.execution_id)
    ):
        assertion = record.registry.compiled_policy.assertions[assertion_id]
        trusted = trusted_evidence.get(assertion_id)
        if trusted is not None:
            evidence.append(
                OracleEvidence(
                    assertion_id=assertion_id,
                    structured_events=(trusted,),
                    tool_results=(),
                    readbacks=(),
                    classifier_results=(),
                    text_supplements=(),
                )
            )
            continue
        try:
            verdict = verdicts[assertion_id]
        except KeyError as exc:
            raise ProductionAdapterError(
                "semantic judge verdict coverage is incomplete"
            ) from exc
        common = {
            "assertion_id": assertion_id,
            "run_id": record.journal.run_id,
            "attempt_digest": attempt_digest,
            "preflight_digest": record.journal.authorization.preflight_digest,
            "passed": verdict.passed,
            "reason": verdict.reason,
        }
        if assertion.oracle.kind == "classifier_result":
            producer = assertion.oracle.allowed_producers[0]
            binding = bindings.get(producer)
            if (
                binding is None
                or binding.producer_kind != "classifier"
                or binding.source_identity != assertion.oracle.classifier_id
                or binding.config_digest != scenario.judge_config_digest
            ):
                raise ProductionAdapterError(
                    "semantic classifier producer is not config-bound"
                )
            classifier_artifact = ClassifierResult.build(
                **common,
                policy_digest=record.registry.compiled_policy.policy_digest,
                evaluator_digest=record.registry.classifier_evaluator_digest(
                    assertion_id
                ),
                classifier_id=str(assertion.oracle.classifier_id),
                producer=producer,
                source_id=f"judge-raw/{record.execution_id}.json",
                source_digest=judge_sha256,
                observed_at=judged_at,
            )
            evidence.append(
                OracleEvidence(
                    assertion_id=assertion_id,
                    structured_events=(),
                    tool_results=(),
                    readbacks=(),
                    classifier_results=(classifier_artifact,),
                    text_supplements=(),
                )
            )
            continue
        if assertion.oracle.kind == "independent_readback":
            producer = "independent-readback-collector"
            binding = bindings.get(producer)
            if (
                producer not in assertion.oracle.allowed_producers
                or binding is None
                or binding.producer_kind != "collector"
                or binding.source_identity != producer
            ):
                raise ProductionAdapterError("semantic readback producer is not sealed")
            readback_artifact = ReadbackResult.build(
                **common,
                producer=producer,
                source_id=f"collector-raw/executions/{record.execution_id}.json",
                source_digest=observation_sha256,
                observed_at=observation.observed_at,
                collector_id=producer,
            )
            evidence.append(
                OracleEvidence(
                    assertion_id=assertion_id,
                    structured_events=(),
                    tool_results=(),
                    readbacks=(readback_artifact,),
                    classifier_results=(),
                    text_supplements=(),
                )
            )
            continue
        if assertion.oracle.kind not in {"structured_event", "structured_evidence"}:
            raise ProductionAdapterError("trusted external evidence is unavailable")
        producer = "production-policy-classifier"
        binding = bindings.get(producer)
        if (
            producer not in assertion.oracle.allowed_producers
            or binding is None
            or binding.producer_kind != "classifier"
            or binding.config_digest != scenario.judge_config_digest
        ):
            raise ProductionAdapterError(
                "semantic structured producer is not config-bound"
            )
        structured_artifact = StructuredEvent.build(
            **common,
            producer=producer,
            source_id=f"judge-raw/{record.execution_id}.json",
            source_digest=judge_sha256,
            observed_at=judged_at,
        )
        evidence.append(
            OracleEvidence(
                assertion_id=assertion_id,
                structured_events=(structured_artifact,),
                tool_results=(),
                readbacks=(),
                classifier_results=(),
                text_supplements=(),
            )
        )
    return tuple(evidence)


def _compile_attempt(
    *,
    producer_handle: DecisiveProducerHandle,
    observation: _LiveExecutionObservation,
    observation_sha256: str,
    transport: _JudgeTransport | None,
) -> tuple[execution.ScenarioAttemptV2, list[dict[str, Any]]]:
    record = _producer_handle_record(producer_handle)
    scenario = _semantic_config(record)
    if len(scenario.planned_turns) != len(observation.transcript_facts):
        raise ProductionAdapterError("live transcript cardinality differs from plan")
    actual_turns: list[execution.ActualTurnV2] = []
    for planned, fact in zip(
        scenario.planned_turns, observation.transcript_facts, strict=True
    ):
        if (
            fact.turn_id != planned.turn_id
            or hashlib.sha256(fact.question.encode("utf-8")).hexdigest()
            != scenario.input_text_sha256[planned.turn_id]
        ):
            raise ProductionAdapterError("live transcript differs from sealed turn")
        actual_turns.append(
            execution.ActualTurnV2(
                actual_turn_id=fact.turn_id,
                planned_turn_id=planned.turn_id,
                customer_input_digest=planned.customer_input_digest,
                expected_behavior_digest=planned.expected_behavior_digest,
                criterion_ids=planned.criterion_ids,
                assertion_ids=planned.assertion_ids,
                event_refs=(
                    f"collector-raw/executions/{record.execution_id}.json",
                    f"message:{fact.message_id}",
                    *fact.media_refs,
                ),
                tool_refs=fact.tools,
                audit_refs=tuple(f"outbound-audit:{item}" for item in fact.audit_ids),
                timeline=execution.TurnTimelineV2(
                    sent_at=fact.sent_at,
                    first_visible_at=fact.first_visible_at,
                    final_visible_at=fact.final_visible_at,
                    delivered_at=fact.delivered_at,
                ),
                model_id=fact.model,
                token_count=fact.token_count,
                cost_usd=fact.cost_usd,
            )
        )
    baseline = _load_baseline(record)
    final_inventory, dispositions = _compile_side_effects(
        record=record,
        observation=observation,
    )
    trusted_evidence = _load_trusted_evidence(
        record=record,
        scenario=scenario,
    )
    if observation.observed_at < max(
        item.final_visible_at for item in observation.transcript_facts
    ) or baseline.observed_at >= min(
        item.sent_at for item in observation.transcript_facts
    ):
        raise ProductionAdapterError("live semantic readback timing drift")
    if record.journal.previous_event_digest is None:
        raise ProductionAdapterError("live semantic causal event is unavailable")
    try:
        collector_id = record.journal.authorization.collector_ids[0]
    except IndexError as exc:
        raise ProductionAdapterError(
            "live semantic collector identity is unavailable"
        ) from exc
    decision, judge_sha256, judged_at = _run_or_replay_judge(
        producer_handle=producer_handle,
        scenario=scenario,
        observation=observation,
        observation_sha256=observation_sha256,
        transport=transport,
    )
    final = ReadbackObservation.build(
        phase="final",
        collector_id=collector_id,
        source_id=f"collector-raw/executions/{record.execution_id}.json",
        run_id=record.journal.run_id,
        preflight_digest=record.journal.authorization.preflight_digest,
        collector_artifact_digest=(
            record.journal.authorization.readback_collector_digest
        ),
        causal_event_digest=record.journal.previous_event_digest,
        observed_at=observation.observed_at,
        inventory=final_inventory,
    )
    return (
        execution.ScenarioAttemptV2(
            schema_version="noor-e2e-scenario-attempt/v2",
            execution_id=record.execution_id,
            planned_turns=scenario.planned_turns,
            actual_turns=tuple(actual_turns),
            adaptive_deviations=(),
            oracle_evidence=_compile_oracles(
                record=record,
                scenario=scenario,
                decision=decision,
                observation=observation,
                observation_sha256=observation_sha256,
                judge_sha256=judge_sha256,
                judged_at=judged_at,
                trusted_evidence=trusted_evidence,
            ),
            permission_evidence=record.registry.compiled_policy.scenarios[
                record.execution_id
            ].required_permissions,
            readback_evidence=record.registry.compiled_policy.scenarios[
                record.execution_id
            ].required_readbacks,
            baseline=baseline,
            final=final,
            action_at=tuple(item.sent_at for item in observation.transcript_facts),
            tester_config_digest=scenario.tester_config_digest,
            judge_config_digest=scenario.judge_config_digest,
        ),
        dispositions,
    )


@dataclass(frozen=True)
class IndependentExecutionProducer:
    """Materialize the next attempt only from an allowlisted read-only source."""

    collector_id: str
    transport: _ReadOnlyTransport
    judge_transport: _JudgeTransport | None = None

    def collect_next(
        self,
        *,
        producer_handle: DecisiveProducerHandle,
        observed_at: datetime | None = None,
    ) -> str:
        record = _producer_handle_record(producer_handle)
        if self.collector_id not in record.journal.authorization.collector_ids:
            raise ProductionAdapterError("live execution collector is not authorized")
        source = f"execution:{record.execution_id}"
        raw = self.transport.read(source)
        try:
            observation = _LiveExecutionObservation.model_validate(json.loads(raw))
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProductionAdapterError(
                "live execution observation is invalid"
            ) from exc
        now = observed_at or datetime.now(UTC)
        if (
            observation.execution_id != record.execution_id
            or now.tzinfo is None
            or now.utcoffset() is None
            or observation.observed_at > now
        ):
            raise ProductionAdapterError("live execution observation time is invalid")
        raw_ref = f"collector-raw/executions/{record.execution_id}.json"
        raw_sha256 = _write_or_validate_bytes(
            record.journal.run_root,
            raw_ref,
            raw,
        )
        _write_or_validate_exact(
            record.journal.run_root,
            f"producer-receipts/live-executions/{record.execution_id}.json",
            {
                "schema_version": "noor-e2e-live-execution-collector-receipt/v2",
                "registry_id": record.registry.registry_id,
                "run_id": record.journal.run_id,
                "authorization_digest": record.journal.authorization_digest,
                "execution_id": record.execution_id,
                "collector_id": self.collector_id,
                "source": source,
                "raw_ref": raw_ref,
                "raw_sha256": raw_sha256,
                "observed_at": observation.observed_at.isoformat(),
            },
        )
        return raw_ref

    def materialize_next(
        self,
        *,
        producer_handle: DecisiveProducerHandle,
        observed_at: datetime | None = None,
    ) -> str:
        raw_ref = self.collect_next(
            producer_handle=producer_handle,
            observed_at=observed_at,
        )
        record = _producer_handle_record(producer_handle)
        raw = execution._read_protected(record.journal.run_root, raw_ref)
        try:
            observation = _LiveExecutionObservation.model_validate(json.loads(raw))
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProductionAdapterError(
                "live execution observation is invalid"
            ) from exc
        attempt, dispositions = _compile_attempt(
            producer_handle=producer_handle,
            observation=observation,
            observation_sha256=hashlib.sha256(raw).hexdigest(),
            transport=self.judge_transport,
        )
        return _write_producer_observation(
            producer_handle=producer_handle,
            attempted=attempt,
            transcript_facts=[
                item.model_dump(mode="json") for item in observation.transcript_facts
            ],
            side_effect_dispositions=dispositions,
        )


@dataclass(frozen=True)
class IndependentActionReconciler:
    """Derive an uncertain action receipt from one allowlisted SSH readback."""

    collector_id: str
    transport: _ReadOnlyTransport

    def materialize(
        self,
        journal: execution.ProtectedExecutionJournal,
        *,
        action_id: str,
        current_time: datetime | None = None,
    ) -> str:
        if self.collector_id not in journal.authorization.collector_ids:
            raise ProductionAdapterError("action reconciler is not authorized")
        reservation = journal._reservations.get(action_id)
        if reservation is None or journal._actions.get(action_id) != "unknown":
            raise ProductionAdapterError(
                "action reconciliation requires an unknown reservation"
            )
        try:
            lower_bound, causal_event_digest = journal.action_reconciliation_boundary(
                action_id
            )
        except execution.ExecutionValidationError as exc:
            raise ProductionAdapterError(
                "live action reconciliation lower bound is unavailable"
            ) from exc
        source = f"reconciliation:{action_id}"
        raw = self.transport.read(source)
        try:
            observation = _LiveActionReconciliation.model_validate(json.loads(raw))
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProductionAdapterError(
                "live action reconciliation is invalid"
            ) from exc
        now = current_time or datetime.now(UTC)
        if (
            observation.action_id != action_id
            or now.tzinfo is None
            or now.utcoffset() is None
            or observation.observed_at > now
            or observation.observed_at < lower_bound
            or observation.actual_cost_usd > reservation.cost_usd
        ):
            raise ProductionAdapterError("live action reconciliation binding drift")
        raw_ref = f"collector-raw/reconciliations/{action_id}.json"
        _write_or_validate_bytes(journal.run_root, raw_ref, raw)
        receipt = execution.UnknownActionReconciliationReceipt(
            schema_version="noor-e2e-unknown-action-reconciliation/v2",
            registry_id=journal.authorization.registry_id,
            run_id=journal.run_id,
            authorization_digest=journal.authorization_digest,
            action_id=action_id,
            reservation_digest=reservation.reservation_digest,
            collector_id=self.collector_id,
            producer="independent-readback-collector",
            causal_event_digest=causal_event_digest,
            observed_at=observation.observed_at,
            expires_at=min(
                observation.observed_at + timedelta(minutes=5),
                journal.authorization.expires_at,
            ),
            resolved_state=observation.resolved_state,
            inventory_digest=execution._digest(observation.inventory),
            actual_cost_usd=observation.actual_cost_usd,
        )
        return _write_or_validate_exact(
            journal.run_root,
            f"independent-reconciliation/{action_id}.json",
            receipt.model_dump(mode="json"),
        )


def _reason_for_next_execution(record: _ProducerHandleRecord) -> BlockReason:
    execution_id = record.execution_id
    scenario = record.registry.compiled_policy.scenarios.get(execution_id)
    if scenario is None:
        return "independent_evidence_unavailable"
    if "provider_originated_canary" in scenario.required_permissions:
        return "provider_origin_unavailable"
    return "disjoint_identity_unavailable"


def materialize_next_conservative_gate(
    *,
    producer_handle: DecisiveProducerHandle,
    current_time: datetime | None = None,
) -> str:
    """Write a protected zero-turn ``BLOCKED`` source for the next execution."""

    record = _producer_handle_record(producer_handle)
    now = current_time or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ProductionAdapterError("live gate time must be timezone-aware")
    if (
        record.journal._execution_started_at is None
        or record.journal._execution_started_event_digest is None
        or now < record.journal._execution_started_at
    ):
        raise ProductionAdapterError("live gate requires started execution")
    expires_at = min(
        now + timedelta(minutes=5), record.journal.authorization.expires_at
    )
    if expires_at <= now:
        raise ProductionAdapterError("live gate authority is expired")

    criterion_ids = tuple(
        criterion.criterion_id
        for criterion in record.registry.compiled_plan.criteria.values()
        if record.execution_id in criterion.obligation_ids
    )
    if not criterion_ids:
        raise ProductionAdapterError("live gate criterion scope is empty")
    reason = _reason_for_next_execution(record)
    context = {
        "schema_version": "noor-e2e-live-block-context/v1",
        "registry_id": record.registry.registry_id,
        "run_id": record.journal.run_id,
        "authorization_digest": record.journal.authorization_digest,
        "execution_id": record.execution_id,
        "criterion_ids": criterion_ids,
        "execution_started_event_digest": (
            record.journal._execution_started_event_digest
        ),
        "producer": "trusted-evidence-registry",
        "reason_code": reason,
        "observed_at": now.isoformat(),
    }
    context_digest = _write_or_validate_exact(
        record.journal.run_root,
        f"gate-evidence-context/{record.execution_id}.json",
        context,
    )
    artifact = execution.GateEvidenceArtifact(
        schema_version="noor-e2e-gate-evidence/v2",
        registry_id=record.registry.registry_id,
        run_id=record.journal.run_id,
        authorization_digest=record.journal.authorization_digest,
        execution_id=record.execution_id,
        criterion_ids=criterion_ids,
        execution_owner=record.journal.authorization.authorization_id,
        execution_started_event_digest=record.journal._execution_started_event_digest,
        outcome="BLOCKED",
        producer="trusted-evidence-registry",
        observed_at=now,
        evidence_digest=context_digest,
    )
    artifact_sha256 = _write_or_validate_exact(
        record.journal.run_root,
        f"gate-evidence/{record.execution_id}.json",
        artifact.model_dump(mode="json"),
    )
    receipt = execution.GateEvidenceReceipt(
        schema_version="noor-e2e-gate-evidence-receipt/v2",
        registry_id=record.registry.registry_id,
        run_id=record.journal.run_id,
        authorization_digest=record.journal.authorization_digest,
        execution_id=record.execution_id,
        criterion_ids=criterion_ids,
        execution_owner=record.journal.authorization.authorization_id,
        execution_started_event_digest=record.journal._execution_started_event_digest,
        artifact_sha256=artifact_sha256,
        outcome="BLOCKED",
        producer="trusted-evidence-registry",
        issued_at=now,
        expires_at=expires_at,
    )
    receipt_digest = _write_or_validate_exact(
        record.journal.run_root,
        f"producer-receipts/gates/{record.execution_id}.json",
        receipt.model_dump(mode="json"),
    )
    attempted = execution.GateAttemptV2(
        schema_version="noor-e2e-gate-attempt/v2",
        execution_id=record.execution_id,
        outcome="BLOCKED",
        run_started_at=record.journal._execution_started_at,
        execution_started_event_digest=record.journal._execution_started_event_digest,
        receipt_digest=receipt_digest,
    )
    return _write_producer_observation(
        producer_handle=producer_handle,
        attempted=attempted,
        transcript_facts=[],
    )


__all__ = [
    "IndependentActionReconciler",
    "IndependentExecutionProducer",
    "materialize_next_conservative_gate",
]
