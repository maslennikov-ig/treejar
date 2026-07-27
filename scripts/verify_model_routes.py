"""Bounded no-side-effect verification for Noor's approved OpenRouter routes.

The script performs one catalog preflight, four synthetic sales grounding calls,
and one structured-output helper call. It never touches customer data, Wazzup,
Zoho, the database, or any business mutation endpoint.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from src.core.config import settings
from src.llm.communication_policy import EVIDENCE_GROUNDING_POLICY

MAIN_MODEL_ID = "z-ai/glm-5.2"
FAST_MODEL_ID = "deepseek/deepseek-v4-flash"
MAX_PAID_CALLS = 5

MAIN_REQUIRED_PARAMETERS = frozenset({"tools", "tool_choice"})
FAST_REQUIRED_PARAMETERS = frozenset(
    {
        "tools",
        "tool_choice",
        "response_format",
        "reasoning",
        "structured_outputs",
    }
)

_SENSITIVE_KEYS = frozenset(
    {"api_key", "authorization", "user_id", "userid", "user-id"}
)
_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)(authorization|api[_ -]?key|user[_ -]?id)([\"'=:\s]+)([^,\s}\"']+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_OPENROUTER_KEY_RE = re.compile(r"\bsk-or-[A-Za-z0-9_-]+\b")
_CLAUSE_NEGATION_RE = re.compile(
    r"\b(?:not|never|cannot|can't|cant|unable to|unconfirmed|"
    r"without confirmation|don't have|do not have|no evidence|not able to)\b"
)
_MEDICAL_BENEFIT_RE = re.compile(
    r"\b(?:great|good|helpful|beneficial|helps?|relieves?|reduces?|prevents?|"
    r"cures?|recommended|supports?|improves?|ideal)\b.{0,48}\b"
    r"(?:back pain|back health|pain relief|spinal health|spine|lumbar)\b"
    r"|\b(?:back pain|back health|pain relief|spinal health|spine|lumbar)\b"
    r".{0,48}\b(?:great|good|helpful|beneficial|helps?|relieves?|reduces?|"
    r"prevents?|cures?|recommended|supports?|improves?|ideal)\b"
)
_SHOWROOM_COMMITMENT_RE = re.compile(
    r"\b(?:appointment|visit|test(?:ing)? setup)\b.{0,24}\b"
    r"(?:booked|confirmed|scheduled|ready)\b"
    r"|\b(?:booked|confirmed|scheduled)\b.{0,24}\b(?:appointment|visit)\b"
)
_SAMPLE_FULFILLMENT_RE = re.compile(
    r"\b(?:we(?:'ll| will)|treejar will)\s+"
    r"(?:send|provide|deliver|courier|ship|dispatch)\b"
    r"|\b(?:samples?|swatches?)\b.{0,32}\b"
    r"(?:will arrive|are guaranteed|are confirmed for delivery)\b"
)
_STOCK_ASSERTION_RE = re.compile(
    r"\b(?:we|treejar|our (?:inventory|warehouse))\s+"
    r"(?:currently\s+)?(?:have|has|hold|holds|carry|carries)\b"
    r"|\b(?:\d+\s+)?units?\b.{0,24}\b(?:available|in stock|on hand)\b"
    r"|\b(?:available|on hand)\b.{0,24}\b(?:inventory|warehouse|stock)\b"
)
_FUTURE_CHECK_RE = re.compile(
    r"\b(?:let me|i can|i will|i'll|we can|we will|we'll)\s+"
    r"(?:check|confirm|look up|verify)\b"
)


@dataclass(frozen=True, slots=True)
class SalesSmokeCase:
    case_id: str
    evidence: str
    user_prompt: str
    expected_decisions: tuple[str, ...]


SALES_CASES: tuple[SalesSmokeCase, ...] = (
    SalesSmokeCase(
        case_id="showroom_visit",
        evidence=(
            "Customers may visit Treejar's UAE showroom to experience product "
            "quality. No particular product, appointment, or test setup is "
            "confirmed in this case."
        ),
        user_prompt="Can I visit your showroom and try the chairs?",
        expected_decisions=("allowed", "conditional"),
    ),
    SalesSmokeCase(
        case_id="project_samples",
        evidence=(
            "Samples may be arranged depending on project requirements. No "
            "specific material sample or delivery is confirmed in this case."
        ),
        user_prompt="Will you send me fabric samples?",
        expected_decisions=("conditional",),
    ),
    SalesSmokeCase(
        case_id="medical_inference",
        evidence=(
            "The Nova Task chair has seat-depth adjustment. There is no medical "
            "or health-outcome evidence in this case."
        ),
        user_prompt="Will the seat-depth adjustment reduce my back pain?",
        expected_decisions=("decline_unsupported",),
    ),
    SalesSmokeCase(
        case_id="missing_stock",
        evidence=(
            "AX-E1 is a valid catalog SKU. No current inventory result is "
            "available in this case."
        ),
        user_prompt="Is AX-E1 currently in stock?",
        expected_decisions=("verify", "conditional"),
    ),
)

_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["allowed", "conditional", "verify", "decline_unsupported"],
        },
        "reply": {"type": "string", "minLength": 1},
    },
    "required": ["decision", "reply"],
    "additionalProperties": False,
}

_ANSWER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_grounded_answer",
        "description": (
            "Submit the grounded customer-facing answer for this synthetic check."
        ),
        "strict": True,
        "parameters": _ANSWER_SCHEMA,
    },
}

_FAST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["product_inquiry"]},
        "language": {"type": "string", "enum": ["ru"]},
        "quantity": {"type": "integer"},
        "sku": {"type": "string"},
        "needs_stock_check": {"type": "boolean"},
    },
    "required": [
        "intent",
        "language",
        "quantity",
        "sku",
        "needs_stock_check",
    ],
    "additionalProperties": False,
}

_FAST_EXPECTED: dict[str, Any] = {
    "intent": "product_inquiry",
    "language": "ru",
    "quantity": 12,
    "sku": "AX-E1",
    "needs_stock_check": True,
}


def build_sales_payload(model: str, case: SalesSmokeCase) -> dict[str, Any]:
    """Build one forced-tool synthetic sales request."""

    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Noor, Treejar's UAE office-furniture sales "
                    "assistant. Use only the evidence supplied for this case.\n\n"
                    f"{EVIDENCE_GROUNDING_POLICY}\n\n"
                    f"[CASE EVIDENCE]\n{case.evidence}\n\n"
                    "Call submit_grounded_answer exactly once. Keep the reply "
                    "concise and do not mention this test."
                ),
            },
            {"role": "user", "content": case.user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 400,
        "tools": [_ANSWER_TOOL],
        "tool_choice": {
            "type": "function",
            "function": {"name": "submit_grounded_answer"},
        },
        "provider": {"require_parameters": True},
    }


def build_fast_payload(model: str) -> dict[str, Any]:
    """Build the strict structured-output helper request."""

    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract only explicit facts. Return the requested JSON "
                    "object and do not infer missing information."
                ),
            },
            {
                "role": "user",
                "content": "Мне нужно 12 кресел AX-E1. Есть ли они в наличии?",
            },
        ],
        "temperature": 0.0,
        "max_tokens": 250,
        "reasoning": {"enabled": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "fast_route_result",
                "strict": True,
                "schema": _FAST_SCHEMA,
            },
        },
        "provider": {"require_parameters": True},
    }


def assert_model_capabilities(
    catalog: Mapping[str, Mapping[str, Any]],
    main_model: str,
    fast_model: str,
) -> None:
    """Fail before paid calls when either approved route is unavailable."""

    requirements = {
        main_model: MAIN_REQUIRED_PARAMETERS,
        fast_model: FAST_REQUIRED_PARAMETERS,
    }
    failures: list[str] = []
    for model, required in requirements.items():
        metadata = catalog.get(model)
        if metadata is None:
            failures.append(f"{model}: missing from catalog")
            continue
        supported_raw = metadata.get("supported_parameters", [])
        supported = (
            {str(value) for value in supported_raw}
            if isinstance(supported_raw, list)
            else set()
        )
        missing = sorted(required - supported)
        if missing:
            failures.append(f"{model}: missing {', '.join(missing)}")
    if failures:
        raise RuntimeError("Model capability preflight failed: " + "; ".join(failures))


def _normalized(value: str) -> str:
    return " ".join(value.casefold().replace("’", "'").split())


def _contains_asserted_phrase(content: str, phrase: str) -> bool:
    start = 0
    while True:
        index = content.find(phrase, start)
        if index < 0:
            return False
        boundaries: list[int] = []
        for marker in (".", "!", "?", ";", ",", "\n", " but ", " however "):
            marker_index = content.rfind(marker, 0, index)
            if marker_index >= 0:
                boundaries.append(marker_index + len(marker))
        clause_prefix = content[max(boundaries, default=0) : index]
        if _CLAUSE_NEGATION_RE.search(clause_prefix) is None:
            return True
        start = index + len(phrase)


def _contains_asserted_pattern(content: str, pattern: re.Pattern[str]) -> bool:
    return any(
        _contains_asserted_phrase(content, match.group())
        for match in pattern.finditer(content)
    )


def evaluate_sales_answer(
    case_id: str,
    answer: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply deterministic semantic invariants to a synthetic sales answer."""

    case = next((item for item in SALES_CASES if item.case_id == case_id), None)
    if case is None:
        raise ValueError(f"Unknown sales smoke case: {case_id}")

    decision = answer.get("decision")
    reply_raw = answer.get("reply")
    reply = _normalized(reply_raw) if isinstance(reply_raw, str) else ""
    failures: list[str] = []
    if decision not in case.expected_decisions:
        failures.append(
            f"decision must be one of {case.expected_decisions}, received {decision!r}"
        )
    if not reply:
        failures.append("reply must be a non-empty string")

    if case_id == "showroom_visit":
        if (
            not any(
                marker in reply
                for marker in (
                    "may visit",
                    "can visit",
                    "welcome to visit",
                    "you're welcome to visit",
                )
            )
            or "showroom" not in reply
        ):
            failures.append("reply must preserve the allowed showroom visit")
        if any(
            marker in reply
            for marker in (
                "cannot visit",
                "can't visit",
                "not allowed to visit",
                "do not visit",
            )
        ):
            failures.append("reply contradicts the allowed showroom visit")
        for phrase in ("appointment is confirmed", "specific chair is available"):
            if _contains_asserted_phrase(reply, phrase):
                failures.append(f"unsupported commitment: {phrase}")
        if _contains_asserted_pattern(reply, _SHOWROOM_COMMITMENT_RE):
            failures.append("reply adds an unsupported showroom commitment")
    elif case_id == "project_samples":
        if "sample" not in reply or "project" not in reply:
            failures.append("reply must preserve the project-sample context")
        if not any(
            marker in reply
            for marker in (
                "samples may be arranged",
                "samples can be arranged",
                "can arrange samples",
            )
        ):
            failures.append("reply must preserve that samples can be arranged")
        if not any(
            marker in reply for marker in ("depending", "subject to", "based on")
        ):
            failures.append("reply must preserve the conditional sample wording")
        if any(
            marker in reply
            for marker in (
                "samples cannot",
                "samples can't",
                "cannot arrange samples",
                "can't arrange samples",
                "samples are not available",
            )
        ):
            failures.append("reply contradicts the conditional sample capability")
        for phrase in ("will provide", "will send", "guaranteed"):
            if _contains_asserted_phrase(reply, phrase):
                failures.append(f"unsupported sample promise: {phrase}")
        if _contains_asserted_pattern(reply, _SAMPLE_FULFILLMENT_RE):
            failures.append("reply adds unsupported sample fulfillment")
    elif case_id == "medical_inference":
        medical_benefit = _MEDICAL_BENEFIT_RE.search(reply)
        if medical_benefit and _contains_asserted_phrase(
            reply, medical_benefit.group()
        ):
            failures.append("reply adds an unsupported medical benefit")
        for phrase in (
            "will reduce back pain",
            "reduces back pain",
            "will prevent back pain",
            "prevents back pain",
            "will cure",
            "cures",
        ):
            if _contains_asserted_phrase(reply, phrase):
                failures.append(f"unsupported medical claim: {phrase}")
    elif case_id == "missing_stock":
        if not any(
            marker in reply
            for marker in (
                "unconfirmed",
                "cannot confirm",
                "can't confirm",
                "unable to confirm",
            )
        ):
            failures.append("reply must distinguish unconfirmed from unavailable")
        if _contains_asserted_pattern(reply, _FUTURE_CHECK_RE):
            failures.append(
                "reply promises a future stock check instead of using the tool"
            )
        for phrase in ("currently in stock", "is in stock", "available now"):
            if _contains_asserted_phrase(reply, phrase):
                failures.append(f"unsupported stock claim: {phrase}")
        if _contains_asserted_pattern(reply, _STOCK_ASSERTION_RE):
            failures.append("reply adds unsupported inventory availability")
        for phrase in (
            "ready to ship",
            "ready for shipment",
            "can ship",
            "will ship",
            "ready for delivery",
        ):
            if _contains_asserted_phrase(reply, phrase):
                failures.append(f"unsupported fulfillment claim: {phrase}")

    return {"passed": not failures, "failures": failures}


def build_sales_evidence_record(
    *,
    case: SalesSmokeCase,
    model: str,
    answer: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    latency_ms: float,
    status_code: int,
) -> dict[str, Any]:
    """Build an auditable record without retaining the raw provider payload."""

    reply_raw = answer.get("reply")
    reply = _sanitize_value(reply_raw) if isinstance(reply_raw, str) else ""
    failures = evaluation.get("failures")
    return {
        "case_id": case.case_id,
        "route": "main",
        "model": model,
        "passed": evaluation.get("passed") is True,
        "failures": list(failures) if isinstance(failures, list) else [],
        "observed_decision": answer.get("decision"),
        "reply": reply[:1000],
        "latency_ms": latency_ms,
        "status_code": status_code,
    }


def _parse_json_object(content: str) -> dict[str, Any]:
    candidate = content.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1]).strip()
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("response must be a JSON object")
    return parsed


def evaluate_fast_content(content: str) -> dict[str, Any]:
    """Validate exact fast-route JSON shape and values."""

    failures: list[str] = []
    parsed: dict[str, Any] | None = None
    try:
        parsed = _parse_json_object(content)
    except (json.JSONDecodeError, ValueError) as exc:
        failures.append(f"invalid JSON: {exc}")
    if parsed is not None:
        if set(parsed) != set(_FAST_EXPECTED):
            failures.append("JSON keys do not match the strict schema")
        if not isinstance(parsed.get("quantity"), int) or isinstance(
            parsed.get("quantity"), bool
        ):
            failures.append("quantity must be an integer")
        if not isinstance(parsed.get("needs_stock_check"), bool):
            failures.append("needs_stock_check must be a boolean")
        for key, expected in _FAST_EXPECTED.items():
            if parsed.get(key) != expected:
                failures.append(f"{key} does not match the explicit input")
    return {"passed": not failures, "failures": failures, "parsed": parsed}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]"
                if str(key).casefold() in _SENSITIVE_KEYS
                else _sanitize_value(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return _SENSITIVE_TEXT_RE.sub(r"\1\2[REDACTED]", value)
    return value


def sanitize_error(value: Any, *, api_key: str = "", limit: int = 500) -> str:
    """Return a bounded error string without credentials/provider identifiers."""

    sanitized = _sanitize_value(value)
    text = json.dumps(sanitized, ensure_ascii=False, default=str)
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _OPENROUTER_KEY_RE.sub("[REDACTED]", text)
    text = _SENSITIVE_TEXT_RE.sub(r"\1\2[REDACTED]", text)
    return text[:limit]


async def _fetch_catalog(
    client: httpx.AsyncClient,
    model_ids: Sequence[str],
    *,
    timeout: float,
) -> dict[str, Mapping[str, Any]]:
    response = await client.get("/models", timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", []) if isinstance(payload, Mapping) else []
    by_id = {
        str(item["id"]): item
        for item in data
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    return {model: by_id[model] for model in model_ids if model in by_id}


async def _post_completion(
    client: httpx.AsyncClient,
    payload: Mapping[str, Any],
    *,
    timeout: float,
) -> tuple[dict[str, Any], float, int]:
    started = time.perf_counter()
    response = await client.post(
        "/chat/completions", json=dict(payload), timeout=timeout
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("Provider response is not a JSON object")
    return body, elapsed_ms, response.status_code


def _message_from_response(response: Mapping[str, Any]) -> Mapping[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Provider response has no choices")
    first = choices[0]
    if not isinstance(first, Mapping) or not isinstance(first.get("message"), Mapping):
        raise RuntimeError("Provider response has no message")
    return first["message"]


def _tool_answer_from_response(response: Mapping[str, Any]) -> dict[str, Any]:
    message = _message_from_response(response)
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        raise RuntimeError("Expected exactly one grounded-answer tool call")
    call = calls[0]
    function = call.get("function") if isinstance(call, Mapping) else None
    if not isinstance(function, Mapping):
        raise RuntimeError("Grounded-answer tool call is malformed")
    if function.get("name") != "submit_grounded_answer":
        raise RuntimeError("Unexpected tool call")
    arguments = function.get("arguments")
    if not isinstance(arguments, str):
        raise RuntimeError("Grounded-answer arguments are missing")
    return _parse_json_object(arguments)


async def run_verification(*, timeout: float) -> dict[str, Any]:
    """Run the bounded verification and return sanitized durable evidence."""

    main_model = settings.openrouter_model_main
    fast_model = settings.openrouter_model_fast
    if main_model != MAIN_MODEL_ID or fast_model != FAST_MODEL_ID:
        raise RuntimeError(
            "Configured routes do not match the approved models: "
            f"main={main_model!r}, fast={fast_model!r}"
        )
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://noor.starec.ai",
        "X-Title": "Noor Model Route Verification",
    }
    records: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url.rstrip("/"),
        headers=headers,
    ) as client:
        catalog = await _fetch_catalog(
            client,
            (main_model, fast_model),
            timeout=timeout,
        )
        assert_model_capabilities(catalog, main_model, fast_model)

        for case in SALES_CASES:
            try:
                response, elapsed_ms, status_code = await _post_completion(
                    client,
                    build_sales_payload(main_model, case),
                    timeout=timeout,
                )
                answer = _tool_answer_from_response(response)
                evaluation = evaluate_sales_answer(case.case_id, answer)
                records.append(
                    build_sales_evidence_record(
                        case=case,
                        model=main_model,
                        answer=answer,
                        evaluation=evaluation,
                        latency_ms=elapsed_ms,
                        status_code=status_code,
                    )
                )
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                records.append(
                    {
                        "case_id": case.case_id,
                        "route": "main",
                        "model": main_model,
                        "passed": False,
                        "failures": [
                            sanitize_error(exc, api_key=settings.openrouter_api_key)
                        ],
                        "latency_ms": None,
                        "status_code": None,
                    }
                )

        try:
            response, elapsed_ms, status_code = await _post_completion(
                client,
                build_fast_payload(fast_model),
                timeout=timeout,
            )
            message = _message_from_response(response)
            content = message.get("content")
            if not isinstance(content, str):
                raise RuntimeError("Structured-output response has no text content")
            evaluation = evaluate_fast_content(content)
            records.append(
                {
                    "case_id": "structured_json",
                    "route": "fast",
                    "model": fast_model,
                    "passed": evaluation["passed"],
                    "failures": evaluation["failures"],
                    "latency_ms": elapsed_ms,
                    "status_code": status_code,
                    "reasoning_requested": False,
                }
            )
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            records.append(
                {
                    "case_id": "structured_json",
                    "route": "fast",
                    "model": fast_model,
                    "passed": False,
                    "failures": [
                        sanitize_error(exc, api_key=settings.openrouter_api_key)
                    ],
                    "latency_ms": None,
                    "status_code": None,
                    "reasoning_requested": False,
                }
            )

    passed = len(records) == MAX_PAID_CALLS and all(
        record["passed"] for record in records
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "synthetic_evidence_only": True,
        "external_business_mutations": False,
        "models": {"main": main_model, "fast": fast_model},
        "preflight": {
            "passed": True,
            "main_required_parameters": sorted(MAIN_REQUIRED_PARAMETERS),
            "fast_required_parameters": sorted(FAST_REQUIRED_PARAMETERS),
        },
        "cases": records,
        "summary": {
            "passed": passed,
            "paid_calls": len(records),
            "max_paid_calls": MAX_PAID_CALLS,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="Per-request timeout in seconds (default: 45).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON evidence path. The sanitized report is always printed.",
    )
    return parser.parse_args()


async def _async_main() -> int:
    args = _parse_args()
    try:
        report = await run_verification(timeout=args.timeout)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        report = {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "synthetic_evidence_only": True,
            "external_business_mutations": False,
            "summary": {"passed": False, "paid_calls": 0},
            "error": sanitize_error(exc, api_key=settings.openrouter_api_key),
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report.get("summary", {}).get("passed") is True else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_async_main()))
