"""Replay the two approved stored repair cases without exposing their text.

The transcript-bearing inputs stay under the git-common protected corpus store.
The result journal contains dialog IDs, counts, outcomes, lengths, and digests;
it never copies a customer message or reply into the working tree.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.llm.grounding_output import (
    GroundingViolation,
    flagged_grounding_sentences,
    repair_grounding_output,
)
from src.llm.opening_guard import is_own_opening_plus_question
from src.llm.repair_judge import (
    REPAIR_JUDGE_MODEL,
    RepairJudgeEvidence,
    RepairJudgeProviderResult,
    RepairJudgeRequest,
    classify_repair_failure,
    review_flagged_reply,
    run_repair_judge,
)
from src.llm.response_policy import ReplyGuardFlag, ReplyPolicyState

SCHEMA_VERSION = "treejar-d6-live-repair/v1"
SOURCE_DIGESTS = {
    789: "f407f0dd9da81caf586d89c7e021268d0402e35ecb0b3fe1c5670761bbd19739",
    819: "bfd314ca34abaf66360aabbe6569ff2dffba50fd39f0a34022004ed639c2a2b7",
}
VIOLATIONS = {
    789: GroundingViolation.UNVERIFIED_CUSTOMER_OWNED_FURNITURE_SERVICE,
    819: GroundingViolation.FUTURE_STOCK_CHECK,
}
CALL_CAP = 20


@dataclass(frozen=True, slots=True)
class StoredRepairCase:
    dialog_id: int
    reply: str
    candidate: str
    state: ReplyPolicyState
    evidence: RepairJudgeEvidence
    flag: ReplyGuardFlag


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def protected_root() -> Path:
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not common:
        raise RuntimeError("cannot resolve git common directory")
    return Path(common).resolve() / "codex-orchestration" / "corpus-bridge"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _record_for_dialog(run_state: dict[str, Any], dialog_id: int) -> dict[str, Any]:
    for record in (run_state.get("records") or {}).values():
        if record.get("dialog_id") == dialog_id:
            return record
    raise ValueError(f"protected dialog {dialog_id} is missing")


def _grounded_amounts(record: dict[str, Any]) -> tuple[str, ...]:
    amounts: list[str] = []
    evidence = record.get("catalog_evidence")
    if isinstance(evidence, list):
        for product in evidence:
            if isinstance(product, dict) and product.get("price_aed") is not None:
                amounts.append(str(product["price_aed"]))
    return tuple(amounts)


def load_cases(root: Path) -> tuple[StoredRepairCase, StoredRepairCase]:
    run_789 = _read_json(root / "tj-vz7o-luna-glm-20260810-rerun/run-state.json")
    record_789 = _record_for_dialog(run_789, 789)
    reply_789 = str((record_789.get("generation") or {}).get("content") or "")

    run_819 = _read_json(root / "tj-vhto-round-20260811/run-state.json")
    record_819 = _record_for_dialog(run_819, 819)
    reading_pack = _read_json(root / "tj-vhto-round-20260811/repair-reading-pack.json")
    repair_819 = next(
        (item for item in reading_pack if item.get("dialog_id") == 819),
        None,
    )
    if repair_819 is None:
        raise ValueError("protected repair input for dialog 819 is missing")
    reply_819 = str(repair_819.get("input_content") or "")

    loaded: list[StoredRepairCase] = []
    for dialog_id, reply, record in (
        (789, reply_789, record_789),
        (819, reply_819, record_819),
    ):
        if _digest(reply) != SOURCE_DIGESTS[dialog_id]:
            raise ValueError(f"protected dialog {dialog_id} digest changed")
        language = str(record.get("language") or "en")
        violation = VIOLATIONS[dialog_id]
        candidate = repair_grounding_output(
            reply,
            language=language,
            violations=(violation,),
        ).text
        state = ReplyPolicyState(
            language=language,
            is_first_turn=True,
            grounded_amounts=tuple(_grounded_amounts(record)) or None,
        )
        loaded.append(
            StoredRepairCase(
                dialog_id=dialog_id,
                reply=reply,
                candidate=candidate,
                state=state,
                evidence=RepairJudgeEvidence(
                    language=language,
                    customer_message=str(record.get("opening") or ""),
                    grounded_amounts=_grounded_amounts(record),
                ),
                flag=ReplyGuardFlag(
                    guard_name="grounding_output",
                    reason="removing_guard_triggered",
                    details=(violation.value,),
                    candidate=candidate,
                    # Mirrors what render_reply attaches in production, so the
                    # measurement is of the path the customer is on.
                    flagged_sentences=flagged_grounding_sentences(
                        reply,
                        grounded_amounts=_grounded_amounts(record) or None,
                    ),
                ),
            )
        )
    return loaded[0], loaded[1]


def _safe_output_path(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    protected = root.resolve()
    if protected not in resolved.parents:
        raise ValueError("live replay output must stay in the protected corpus store")
    return resolved


def _write_journal(path: Path, journal: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(journal, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _new_journal(cases: tuple[StoredRepairCase, ...]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model": REPAIR_JUDGE_MODEL,
        "call_cap": CALL_CAP,
        "notify_on_failure_override": False,
        "cases": [
            {
                "dialog_id": case.dialog_id,
                "reply_digest": _digest(case.reply),
                "reply_length": len(case.reply),
                "candidate_digest": _digest(case.candidate),
                "candidate_length": len(case.candidate),
                "candidate_has_no_answer": is_own_opening_plus_question(
                    case.candidate,
                    language=case.state.language,
                ),
            }
            for case in cases
        ],
        "calls": [],
    }


async def run_live_replay(
    *,
    output_path: Path,
    repeats: int,
) -> dict[str, Any]:
    if repeats < 4 or repeats * 2 > CALL_CAP:
        raise ValueError(
            "repeats must be at least 4 and keep both dialogs within 20 calls"
        )
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is required for the approved live replay"
        )

    root = protected_root()
    cases = load_cases(root)
    output_path = _safe_output_path(output_path, root)
    journal = _read_json(output_path) if output_path.exists() else _new_journal(cases)
    if journal.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("live replay journal schema differs")

    calls = journal.setdefault("calls", [])
    if len(calls) > CALL_CAP:
        raise ValueError("existing live replay journal exceeds the approved cap")
    for case in cases:
        existing = [call for call in calls if call.get("dialog_id") == case.dialog_id]
        for repeat_number in range(len(existing) + 1, repeats + 1):
            if len(calls) >= CALL_CAP:
                raise RuntimeError("approved repair-judge call cap reached")
            record: dict[str, Any] = {
                "dialog_id": case.dialog_id,
                "repeat": repeat_number,
                "status": "started",
                "notify_on_failure_override": False,
            }
            calls.append(record)
            _write_journal(output_path, journal)

            request = RepairJudgeRequest(
                reply=case.reply,
                flags=(replace(case.flag, candidate=None),),
                evidence=case.evidence,
            )
            try:
                provider_result = await run_repair_judge(
                    request,
                    notify_on_failure=False,
                )
            except Exception as error:
                record.update(
                    {
                        "status": "failed",
                        "error_type": type(error).__name__,
                        "error_classification": classify_repair_failure(error),
                    }
                )
            else:

                async def replay_result(
                    _request: RepairJudgeRequest,
                    result: RepairJudgeProviderResult = provider_result,
                ) -> RepairJudgeProviderResult:
                    return result

                judged = await review_flagged_reply(
                    case.reply,
                    state=case.state,
                    flags=(case.flag,),
                    evidence=case.evidence,
                    runner=replay_result,
                )
                corrected = str(provider_result.decision.corrected_text or "")
                trace = judged.trace
                record.update(
                    {
                        "status": "completed",
                        "answer": provider_result.decision.answer,
                        "corrected_digest": _digest(corrected) if corrected else None,
                        "corrected_length": len(corrected),
                        "corrected_equals_candidate": bool(corrected)
                        and corrected == case.candidate,
                        "judged_digest": _digest(judged.text),
                        "judged_length": len(judged.text),
                        "provenance": judged.provenance,
                        "requires_handoff": bool(
                            trace is not None and trace.requires_handoff
                        ),
                        "rejection_reason": (
                            trace.rejection_reason if trace is not None else None
                        ),
                        "fallbacks": trace.counts.fallbacks if trace is not None else 0,
                        "unusable_customer_stub": (
                            trace is None or not trace.requires_handoff
                        )
                        and is_own_opening_plus_question(
                            judged.text,
                            language=case.state.language,
                        ),
                        "prompt_tokens": provider_result.prompt_tokens,
                        "completion_tokens": provider_result.completion_tokens,
                        "cost_usd": provider_result.cost_usd,
                    }
                )
            _write_journal(output_path, journal)
            print(
                f"dialog {case.dialog_id} call {repeat_number}/{repeats}: "
                f"{record['status']}"
            )
    return journal


def _summary(journal: dict[str, Any]) -> dict[str, Any]:
    calls = journal.get("calls") or []
    completed = [call for call in calls if call.get("status") == "completed"]
    corrected = [call for call in completed if call.get("corrected_digest")]
    return {
        "calls_started": len(calls),
        "calls_completed": len(completed),
        "calls_failed": sum(call.get("status") == "failed" for call in calls),
        "calls_by_dialog": {
            str(dialog_id): sum(call.get("dialog_id") == dialog_id for call in calls)
            for dialog_id in (789, 819)
        },
        "handoffs_by_dialog": {
            str(dialog_id): sum(
                call.get("dialog_id") == dialog_id and call.get("requires_handoff")
                for call in completed
            )
            for dialog_id in (789, 819)
        },
        "unusable_customer_stubs": sum(
            bool(call.get("unusable_customer_stub")) for call in completed
        ),
        "corrected_answers": len(corrected),
        "corrected_equal_to_candidate": sum(
            bool(call.get("corrected_equals_candidate")) for call in corrected
        ),
        "cost_usd": sum(float(call.get("cost_usd") or 0.0) for call in completed),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = protected_root()
    cases = load_cases(root)
    if args.dry_run:
        print(json.dumps(_new_journal(cases), indent=2, sort_keys=True))
        return 0
    output = args.output or root / "tj-q1a2-d6-live-20260812/results.json"
    journal = asyncio.run(run_live_replay(output_path=output, repeats=args.repeats))
    print(json.dumps(_summary(journal), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
