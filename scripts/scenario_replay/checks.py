"""Automatic, reported (never asserted) checks over a replayed scenario.

Each check is declared in the scenario file and reads only the turn records the
harness produced: the final customer reply, the tool calls the model made, the
media that would be sent and the decision state after the turn. A check returns
``pass``, ``fail``, ``not_applicable`` or ``observed`` with the evidence it used,
so a reader can overrule it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

Turn = Mapping[str, Any]
CheckFn = Callable[[Mapping[str, Any], Sequence[Turn]], dict[str, Any]]

_UNCONFIRMED_RE = re.compile(
    r"[^.!?\n]*\b(?:isn['’]t|is not|are not|aren['’]t|not|un)[\s-]*confirmed\b[^.!?\n]*",
    re.IGNORECASE,
)


def _turn(turns: Sequence[Turn], number: int) -> Turn | None:
    for turn in turns:
        if turn.get("index") == number:
            return turn
    return None


def _reply(turn: Turn | None) -> str:
    return str((turn or {}).get("reply") or "")


def _selected_turns(spec: Mapping[str, Any], turns: Sequence[Turn]) -> list[Turn]:
    wanted = spec.get("turns")
    if wanted is None and "turn" in spec:
        wanted = [spec["turn"]]
    if wanted is None:
        return [t for t in turns if t.get("reply") is not None]
    return [t for n in wanted if (t := _turn(turns, int(n))) is not None]


def _missing(spec: Mapping[str, Any], turns: Sequence[Turn]) -> list[int]:
    wanted = spec.get("turns") or ([spec["turn"]] if "turn" in spec else [])
    return [
        int(n)
        for n in wanted
        if (t := _turn(turns, int(n))) is None or t.get("reply") is None
    ]


def _result(
    spec: Mapping[str, Any], status: str, evidence: Any, **extra: Any
) -> dict[str, Any]:
    return {
        "type": spec["type"],
        "description": spec.get("description", ""),
        "status": status,
        "evidence": evidence,
        **extra,
    }


def no_unconfirmed_claim(
    spec: Mapping[str, Any], turns: Sequence[Turn]
) -> dict[str, Any]:
    hits = []
    for turn in _selected_turns(spec, turns):
        for match in _UNCONFIRMED_RE.finditer(_reply(turn)):
            hits.append({"turn": turn["index"], "sentence": match.group(0).strip()})
    missing = _missing(spec, turns)
    status = "fail" if hits else ("incomplete" if missing else "pass")
    return _result(spec, status, hits, missing_turns=missing)


def _media_text(turn: Turn) -> str:
    return "\n".join(
        f"{item.get('sku') or item.get('product_key', '')} | {item.get('caption', '')}"
        for item in turn.get("media") or []
    )


def media_covers_offered(
    spec: Mapping[str, Any], turns: Sequence[Turn]
) -> dict[str, Any]:
    turn = _turn(turns, int(spec["turn"]))
    if turn is None or turn.get("reply") is None:
        return _result(spec, "incomplete", "turn did not run")
    reply = _reply(turn)
    media = _media_text(turn)
    rows = []
    for item in spec["items"]:
        offered = bool(re.search(item["offered_pattern"], reply, re.IGNORECASE))
        in_media = bool(re.search(item["media_pattern"], media, re.IGNORECASE))
        rows.append({"label": item["label"], "offered": offered, "in_media": in_media})
    offered_rows = [r for r in rows if r["offered"]]
    if len(offered_rows) < len(rows):
        status = "not_applicable"
    else:
        status = "pass" if all(r["in_media"] for r in rows) else "fail"
    return _result(spec, status, {"items": rows, "media": media.splitlines()})


def no_price_after_selection(
    spec: Mapping[str, Any], turns: Sequence[Turn]
) -> dict[str, Any]:
    hits = []
    skipped = []
    for turn in _selected_turns(spec, turns):
        if re.search(spec["asked_pattern"], str(turn.get("user") or ""), re.IGNORECASE):
            skipped.append(turn["index"])
            continue
        for pattern in spec["price_patterns"]:
            for match in re.finditer(pattern, _reply(turn)):
                hits.append({"turn": turn["index"], "match": match.group(0)})
    missing = _missing(spec, turns)
    status = "fail" if hits else ("incomplete" if missing else "pass")
    return _result(spec, status, hits, skipped_turns_customer_asked=skipped)


def _tool_calls(turn: Turn) -> list[Mapping[str, Any]]:
    return list(turn.get("tools_called") or [])


def records_items_without_alternative(
    spec: Mapping[str, Any], turns: Sequence[Turn]
) -> dict[str, Any]:
    turn = _turn(turns, int(spec["turn"]))
    if turn is None or turn.get("reply") is None:
        return _result(spec, "incomplete", "turn did not run")
    skus = [str(s) for s in spec["skus"]]
    recorded_by_tool: dict[str, list[str]] = {}
    for call in _tool_calls(turn):
        blob = json.dumps(call.get("arguments"), ensure_ascii=False).casefold()
        for sku in skus:
            if sku.casefold() in blob:
                recorded_by_tool.setdefault(sku, []).append(str(call.get("name")))
    selected = [
        str(item.get("sku", ""))
        for item in (turn.get("state") or {}).get("selected_items") or []
    ]
    in_state = {
        sku: any(sku.casefold() == s.casefold() for s in selected) for sku in skus
    }
    reply = _reply(turn)
    alternatives = [
        pattern
        for pattern in spec.get("alternative_patterns", [])
        if re.search(pattern, reply, re.IGNORECASE)
    ]
    recorded = all(in_state[sku] for sku in skus)
    status = "pass" if recorded and not alternatives else "fail"
    return _result(
        spec,
        status,
        {
            "tools_naming_sku": recorded_by_tool,
            "selected_items_after_turn": selected,
            "recorded_in_state": in_state,
            "alternative_mentions": alternatives,
        },
    )


def positive_answer(spec: Mapping[str, Any], turns: Sequence[Turn]) -> dict[str, Any]:
    turn = _turn(turns, int(spec["turn"]))
    if turn is None or turn.get("reply") is None:
        return _result(spec, "incomplete", "turn did not run")
    reply = _reply(turn)
    required = {
        p: bool(re.search(p, reply, re.IGNORECASE)) for p in spec["require_patterns"]
    }
    forbidden = [
        m.group(0)
        for p in spec.get("forbid_patterns", [])
        for m in re.finditer(p, reply, re.IGNORECASE)
    ]
    status = "pass" if all(required.values()) and not forbidden else "fail"
    return _result(spec, status, {"required": required, "forbidden_hits": forbidden})


def prior_bot_asked(spec: Mapping[str, Any], turns: Sequence[Turn]) -> dict[str, Any]:
    turn = _turn(turns, int(spec["turn"]) - 1)
    if turn is None or turn.get("reply") is None:
        return _result(spec, "incomplete", "previous turn did not run")
    questions = [
        q.strip()
        for q in re.findall(r"[^.!?\n]*\?", _reply(turn))
        if re.search(spec["pattern"], q, re.IGNORECASE)
    ]
    status = "observed" if questions else "not_observed"
    return _result(spec, status, questions)


def proceeds_to_quote(spec: Mapping[str, Any], turns: Sequence[Turn]) -> dict[str, Any]:
    rows = []
    for turn in _selected_turns(spec, turns):
        reply = _reply(turn)
        tools = [str(c.get("name")) for c in _tool_calls(turn)]
        proceeds = (
            bool(re.search(spec["proceed_pattern"], reply, re.IGNORECASE))
            or "create_quotation" in tools
        )
        relist = [
            m.group(0)
            for p in spec.get("relist_patterns", [])
            for m in re.finditer(p, reply, re.IGNORECASE)
        ]
        rows.append(
            {
                "turn": turn["index"],
                "proceeds": proceeds,
                "relisting_hits": relist,
                "tools": tools,
            }
        )
    missing = _missing(spec, turns)
    ok = all(r["proceeds"] and not r["relisting_hits"] for r in rows)
    status = "incomplete" if missing and ok else ("pass" if ok else "fail")
    return _result(spec, status, rows, missing_turns=missing)


_STRUCTURED_LEAK_RE = re.compile(
    r'^\s*[\[{]|"(?:claims|claim_type|field_path|answer)"\s*:', re.IGNORECASE
)


def no_structured_leak(
    spec: Mapping[str, Any], turns: Sequence[Turn]
) -> dict[str, Any]:
    """The customer text must never be a tool/contract JSON payload."""

    hits = []
    for turn in _selected_turns(spec, turns):
        match = _STRUCTURED_LEAK_RE.search(_reply(turn))
        if match:
            hits.append({"turn": turn["index"], "reply_start": _reply(turn)[:160]})
    return _result(spec, "fail" if hits else "pass", hits)


CHECKS: dict[str, CheckFn] = {
    "no_structured_leak": no_structured_leak,
    "no_unconfirmed_claim": no_unconfirmed_claim,
    "media_covers_offered": media_covers_offered,
    "no_price_after_selection": no_price_after_selection,
    "records_items_without_alternative": records_items_without_alternative,
    "positive_answer": positive_answer,
    "prior_bot_asked": prior_bot_asked,
    "proceeds_to_quote": proceeds_to_quote,
}


def run_checks(
    specs: Sequence[Mapping[str, Any]], turns: Sequence[Turn]
) -> list[dict[str, Any]]:
    results = []
    for spec in specs:
        check = CHECKS.get(str(spec.get("type")))
        if check is None:
            results.append(_result(spec, "error", f"unknown check {spec.get('type')}"))
            continue
        results.append(check(spec, turns))
    return results
