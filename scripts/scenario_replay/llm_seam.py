"""The one seam every model call crosses: ``AsyncCompletions.create``.

Core chat, claim-contract repairs, the prose agent and the repair judge all go
through pydantic-ai's OpenAI chat model, which calls
``client.chat.completions.create``. Intercepting there gives three things in one
place: a hard pre-call budget stop using provider-reported cost, a per-call
record of the tool calls the model asked for, and -- in dry mode -- a stub model
that answers without any network while the rest of the pipeline runs unchanged.

A second guard sits under it on httpx: in live mode only ``openrouter.ai`` may be
reached, in dry mode nothing may.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
from openai.types.chat import ChatCompletion


class BudgetExhausted(BaseException):  # noqa: N818 - must escape `except Exception`
    """Raised before a call that could take spend past the cap.

    A BaseException on purpose: the reply pipeline converts ordinary exceptions
    into a customer apology, which would disguise the stop as a product failure.
    """


@dataclass
class CallRecord:
    index: int
    model: str
    kind: str
    cost_usd: float
    cost_source: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    finish_reason: str | None = None
    reasoning: Any = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    text: str | None = None
    elapsed_s: float | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [], "")}


def _tool_names(kwargs: Mapping[str, Any]) -> list[str]:
    tools = kwargs.get("tools")
    if not isinstance(tools, list):
        return []
    names: list[str] = []
    for tool in tools:
        function = tool.get("function") if isinstance(tool, Mapping) else None
        if isinstance(function, Mapping) and function.get("name"):
            names.append(str(function["name"]))
    return names


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, Mapping) and part.get("type") == "text"
        )
    return ""


def _call_kind(kwargs: Mapping[str, Any]) -> str:
    names = _tool_names(kwargs)
    if "final_result" in names and len(names) == 1:
        return "structured_output"
    if names:
        return "tool_agent"
    return "text_only"


def _parse_arguments(raw: Any) -> Any:
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except ValueError:
        return raw


class CostMeter:
    """Pre-call budget stop and per-call ledger for one replay run."""

    def __init__(
        self,
        *,
        max_cost_usd: float,
        price_in_per_mtok: float,
        price_out_per_mtok: float,
        min_reserve_usd: float,
        responder: Callable[[Mapping[str, Any]], ChatCompletion] | None = None,
    ) -> None:
        self.max_cost_usd = max_cost_usd
        self.price_in = price_in_per_mtok
        self.price_out = price_out_per_mtok
        self.min_reserve = min_reserve_usd
        self.responder = responder
        self.spent = 0.0
        self.max_call_cost = 0.0
        self.calls: list[CallRecord] = []
        self.turn_calls: list[CallRecord] = []
        self.stopped_reason: str | None = None
        self._seen_tool_call_ids: set[str] = set()

    @property
    def reserve(self) -> float:
        return max(self.max_call_cost, self.min_reserve)

    def start_turn(self) -> None:
        self.turn_calls = []

    def _estimate(self, prompt: int | None, completion: int | None) -> float:
        return (
            (prompt or 0) * self.price_in + (completion or 0) * self.price_out
        ) / 1e6

    def _new_tool_results(self, kwargs: Mapping[str, Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for message in kwargs.get("messages") or []:
            if not isinstance(message, Mapping) or message.get("role") != "tool":
                continue
            call_id = str(message.get("tool_call_id") or "")
            if not call_id or call_id in self._seen_tool_call_ids:
                continue
            self._seen_tool_call_ids.add(call_id)
            results.append(
                {
                    "tool_call_id": call_id,
                    "content": _content_text(message.get("content"))[:8000],
                }
            )
        return results

    async def intercept(
        self, original: Any, completions: Any, *args: Any, **kwargs: Any
    ) -> Any:
        if self.stopped_reason is not None:
            raise BudgetExhausted(self.stopped_reason)
        if self.spent + self.reserve > self.max_cost_usd:
            self.stopped_reason = (
                f"next call could exceed cap: spent {self.spent:.6f} + reserve "
                f"{self.reserve:.6f} > {self.max_cost_usd:.6f} USD"
            )
            raise BudgetExhausted(self.stopped_reason)
        model = str(kwargs.get("model") or "")
        record = CallRecord(
            index=len(self.calls) + 1,
            model=model,
            kind=_call_kind(kwargs),
            cost_usd=0.0,
            cost_source="none",
            tool_results=self._new_tool_results(kwargs),
        )
        extra_body = kwargs.get("extra_body")
        if isinstance(extra_body, Mapping) and "reasoning" in extra_body:
            record.reasoning = extra_body["reasoning"]
        started = time.monotonic()
        try:
            if self.responder is not None:
                response = self.responder(kwargs)
            else:
                response = await original(completions, *args, **kwargs)
        except Exception as exc:
            record.error = f"{type(exc).__name__}: {str(exc)[:300]}"
            record.cost_source = "none_error"
            self._append(record)
            raise
        record.elapsed_s = round(time.monotonic() - started, 2)
        self._describe(record, response)
        self._append(record)
        return response

    def _append(self, record: CallRecord) -> None:
        self.calls.append(record)
        self.turn_calls.append(record)
        self.spent += record.cost_usd
        self.max_call_cost = max(self.max_call_cost, record.cost_usd)

    def _describe(self, record: CallRecord, response: Any) -> None:
        usage = getattr(response, "usage", None)
        extra = getattr(usage, "model_extra", None) or {}
        record.prompt_tokens = getattr(usage, "prompt_tokens", None)
        record.completion_tokens = getattr(usage, "completion_tokens", None)
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        record.cached_tokens = getattr(prompt_details, "cached_tokens", None)
        completion_details = getattr(usage, "completion_tokens_details", None)
        record.reasoning_tokens = getattr(completion_details, "reasoning_tokens", None)
        cost = extra.get("cost") if isinstance(extra, Mapping) else None
        if self.responder is not None:
            record.cost_usd, record.cost_source = 0.0, "stub"
        elif isinstance(cost, (int, float)) and cost >= 0:
            record.cost_usd, record.cost_source = float(cost), "provider"
        else:
            record.cost_usd = self._estimate(
                record.prompt_tokens, record.completion_tokens
            )
            record.cost_source = "token_estimate"
        choices = getattr(response, "choices", None) or []
        if choices:
            choice = choices[0]
            record.finish_reason = getattr(choice, "finish_reason", None)
            message = getattr(choice, "message", None)
            record.text = getattr(message, "content", None)
            for call in getattr(message, "tool_calls", None) or []:
                function = getattr(call, "function", None)
                record.tool_calls.append(
                    {
                        "id": getattr(call, "id", None),
                        "name": getattr(function, "name", None),
                        "arguments": _parse_arguments(
                            getattr(function, "arguments", None)
                        ),
                    }
                )


# --- Network guard -----------------------------------------------------------


@dataclass
class NetworkGuard:
    allowed_hosts: frozenset[str]
    blocked: list[str] = field(default_factory=list)

    def check(self, request: httpx.Request) -> None:
        host = request.url.host
        if host in self.allowed_hosts:
            return
        self.blocked.append(f"{request.method} {host}{request.url.path}")
        raise httpx.ConnectError(
            f"scenario replay network guard blocked {host}", request=request
        )


# --- Stub model --------------------------------------------------------------


def _completion(
    *,
    model: str,
    content: str | None = None,
    tool_calls: Sequence[tuple[str, dict[str, Any]]] = (),
) -> ChatCompletion:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": f"stub-call-{name}-{index}-{time.monotonic_ns()}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
            for index, (name, arguments) in enumerate(tool_calls)
        ]
    return ChatCompletion.model_validate(
        {
            "id": f"stub-{time.monotonic_ns()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                    "message": message,
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "total_tokens": 20,
                "cost": 0.0,
            },
        }
    )


class StubModel:
    """A deterministic no-network model that exercises the wiring.

    First request of a turn: run the turn's ``stub_plan`` (one tool call per
    request) when the scenario gives one, else call ``search_products`` with
    the customer text. When ``escalate_to_manager`` is offered -- the policy
    only offers it on a handoff turn -- and the plan did not call it, call it.
    After the tool results: name up to three catalog rows the turn returned,
    restate the verified math lines the tools computed, and close on a
    question. Structured output (the repair judge): approve. It is a wiring
    probe, not a sales model, so reply-semantics checks are live-only.
    """

    _EVIDENCE_LINE_RE = re.compile(
        r"^(?:Verified line math|Verified multi-item total|Verified turnkey "
        r"package math|Budget check|\d+ × [^:\n]+: Budget check)[^\n]*",
        re.MULTILINE,
    )

    def __init__(self, catalog_rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = list(catalog_rows)
        self._answered: set[str] = set()
        self.turn_plan: list[dict[str, Any]] = []

    def start_turn(self, plan: Sequence[Mapping[str, Any]] | None) -> None:
        self.turn_plan = [dict(step) for step in plan or ()]

    def _rows_in(self, text: str) -> list[Mapping[str, Any]]:
        found: list[tuple[int, Mapping[str, Any]]] = []
        for row in self._rows:
            for needle in (str(row["sku"]), str(row["name_en"])):
                position = text.find(needle)
                if position >= 0:
                    found.append((position, row))
                    break
        found.sort(key=lambda item: item[0])
        unique: dict[str, Mapping[str, Any]] = {}
        for _, row in found:
            unique.setdefault(str(row["sku"]), row)
        return list(unique.values())

    @staticmethod
    def _current_turn(messages: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        # A tool contract (`ToolReturn.content`) arrives as a user message, so
        # the turn starts after the last assistant message that ended a turn:
        # one with text and no tool calls.
        boundary = max(
            (
                i
                for i, m in enumerate(messages)
                if m.get("role") == "assistant" and not m.get("tool_calls")
            ),
            default=-1,
        )
        return list(messages[boundary + 1 :])

    def _reply(self, model: str, turn: Sequence[Mapping[str, Any]]) -> ChatCompletion:
        tool_texts = [
            _content_text(m.get("content")) for m in turn if m.get("role") == "tool"
        ]
        called = [
            str((call.get("function") or {}).get("name"))
            for m in turn
            if m.get("role") == "assistant"
            for call in (m.get("tool_calls") or [])
            if isinstance(call, Mapping)
        ]
        rows: list[Mapping[str, Any]] = []
        for text in tool_texts:
            for row in self._rows_in(text):
                if all(str(row["sku"]) != str(r["sku"]) for r in rows):
                    rows.append(row)
        lines = [
            f"{row['name_en']} is AED {float(row['price']):,.0f} per unit (excl. 5% VAT)."
            for row in rows[:3]
        ]
        evidence: list[str] = []
        for text in tool_texts:
            for match in self._EVIDENCE_LINE_RE.finditer(text):
                if match.group(0) not in evidence:
                    evidence.append(match.group(0))
        lines.extend(evidence[:4])
        arabic = any(
            m.get("role") == "user"
            and re.search(r"[\u0600-\u06ff]", _content_text(m.get("content")))
            for m in turn[:1]
        )
        if "escalate_to_manager" in called:
            lines.append(
                "سيتولى أحد المديرين متابعة المشروع. ما اسم الشركة، وما موعد "
                "التسليم المطلوب، وما موقع التسليم في الإمارات؟"
                if arabic
                else "A manager will take this over. What is your company name, "
                "target delivery timeline and delivery location in the UAE?"
            )
        elif rows:
            lines.append(
                "هل ترغب أن أجهز عرض سعر رسمي؟"
                if arabic
                else "Would you like me to prepare a quotation?"
            )
        if not lines:
            lines = ["Thank you. Which item would you like to go ahead with?"]
        return _completion(model=model, content=" ".join(lines))

    def __call__(self, kwargs: Mapping[str, Any]) -> ChatCompletion:
        model = str(kwargs.get("model") or "stub")
        names = _tool_names(kwargs)
        messages = [m for m in kwargs.get("messages") or [] if isinstance(m, Mapping)]
        last = messages[-1] if messages else {}
        if "final_result" in names and "search_products" not in names:
            return _completion(
                model=model,
                tool_calls=[
                    ("final_result", {"answer": "approve", "rationale": "stub"})
                ],
            )
        turn = self._current_turn(messages)
        called = [
            str((call.get("function") or {}).get("name"))
            for m in turn
            if m.get("role") == "assistant"
            for call in (m.get("tool_calls") or [])
            if isinstance(call, Mapping)
        ]
        is_tool_agent = "search_products" in names
        if is_tool_agent and (last.get("role") == "user" or called):
            step_index = len(called)
            if self.turn_plan:
                if step_index < len(self.turn_plan):
                    step = self.turn_plan[step_index]
                    tool = str(step["tool"])
                    if tool in names:
                        return _completion(
                            model=model,
                            tool_calls=[(tool, dict(step.get("arguments") or {}))],
                        )
            elif step_index == 0:
                text = re.sub(r"\s+", " ", _content_text(last.get("content"))).strip()
                return _completion(
                    model=model,
                    tool_calls=[
                        ("search_products", {"query": text[:200], "max_results": 3})
                    ],
                )
            if "escalate_to_manager" in names and "escalate_to_manager" not in called:
                return _completion(
                    model=model,
                    tool_calls=[
                        (
                            "escalate_to_manager",
                            {
                                "reason": "Stub: handoff route offered by policy",
                                "escalation_type": "general",
                            },
                        )
                    ],
                )
            self._answered.update(
                str(m.get("tool_call_id")) for m in turn if m.get("role") == "tool"
            )
            return self._reply(model, turn)
        tool_results = {
            str(m.get("tool_call_id")): _content_text(m.get("content"))
            for m in messages
            if m.get("role") == "tool"
        }
        fresh = [cid for cid in tool_results if cid not in self._answered]
        if fresh:
            self._answered.update(fresh)
            return self._reply(model, turn)
        return _completion(
            model=model,
            content="Thank you. Which item would you like to go ahead with?",
        )
