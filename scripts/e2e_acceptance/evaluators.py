"""Deterministic and bounded-judge evaluation for Noor acceptance scenarios."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


class EvaluationError(ValueError):
    """Evaluator configuration or evidence is incomplete."""


@dataclass(frozen=True)
class EvaluationResult:
    status: str
    hard_failure: bool
    failure_reasons: tuple[str, ...]
    judge_reasoning: str


def evaluate_scenario(
    *,
    deterministic_checks: Sequence[Mapping[str, object]],
    judge: Mapping[str, object],
) -> EvaluationResult:
    """Combine hard deterministic checks with one reproducible judge decision."""

    if not deterministic_checks:
        raise EvaluationError("deterministic checks are required")
    if (
        judge.get("max_calls") != 1
        or judge.get("temperature") != 0
        or not judge.get("model")
        or not judge.get("rubric_digest")
        or not judge.get("reasoning")
    ):
        raise EvaluationError("judge must be bounded to one deterministic call")

    failures: list[str] = []
    hard_failure = False
    for check in deterministic_checks:
        check_id = str(check.get("check_id", ""))
        if not check_id or not check.get("reasoning"):
            raise EvaluationError("deterministic checks need IDs and reasoning")
        if check.get("passed") is not True:
            failures.append(check_id)
            hard_failure = hard_failure or check.get("hard_safety") is True
    if judge.get("passed") is not True:
        failures.append("bounded-judge")

    return EvaluationResult(
        status="failed" if failures else "passed",
        hard_failure=hard_failure,
        failure_reasons=tuple(failures),
        judge_reasoning=str(judge["reasoning"]),
    )
