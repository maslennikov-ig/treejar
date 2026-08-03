"""Reproducible OpenRouter model battle for Noor's sales and helper routes.

The runner uses only fixed synthetic evidence. It never calls Treejar, Zoho,
Wazzup, or production databases and it does not change runtime configuration.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import random
import re
import statistics
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from src.core.config import settings

SALES_MODELS = ("z-ai/glm-5", "deepseek/deepseek-v4-flash")
SYSTEM_MODELS = ("nex-agi/nex-n2-mini", "deepseek/deepseek-v4-flash")
ORIGINAL_PROFILE = "original"
EXTENDED_PROFILE = "extended-2026-07-27"
CORE_HARD_PROFILE = "core-hard-2026-08-03"
BACKGROUND_HARD_PROFILE = "background-hard-2026-08-03"
MODEL_PROFILES = {
    ORIGINAL_PROFILE: {
        "sales": SALES_MODELS,
        "system": SYSTEM_MODELS,
    },
    EXTENDED_PROFILE: {
        "sales": (
            "z-ai/glm-5",
            "z-ai/glm-5.2",
            "deepseek/deepseek-v4-flash",
            "deepseek/deepseek-v4-pro",
        ),
        "system": (
            "nex-agi/nex-n2-mini",
            "z-ai/glm-5.2",
            "deepseek/deepseek-v4-flash",
            "deepseek/deepseek-v4-pro",
        ),
    },
    CORE_HARD_PROFILE: {
        "sales": (
            "z-ai/glm-5.2",
            "deepseek/deepseek-v4-flash-0731",
            "openai/gpt-5.6-luna",
            "xiaomi/mimo-v2.5-pro",
        ),
    },
    BACKGROUND_HARD_PROFILE: {
        "system": (
            "deepseek/deepseek-v4-flash",
            "z-ai/glm-5.2",
            "deepseek/deepseek-v4-flash-0731",
            "openai/gpt-5.6-luna",
            "xiaomi/mimo-v2.5-pro",
        ),
    },
}
DEFAULT_SEED = 27072026
_HARD_PROFILES = {CORE_HARD_PROFILE, BACKGROUND_HARD_PROFILE}
_FIRST_PARTY_PROVIDERS = {
    "deepseek": "deepseek",
    "openai": "openai",
    "xiaomi": "xiaomi",
    "z-ai": "z-ai",
}

_JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
_PATH_PART_RE = re.compile(r"([^[.\]]+)|\[(\d+)\]")
_NUMBER_RE = re.compile(r"(?<![\w-])\d[\d,]*(?:\.\d+)?%?")
_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\w)\+?\d(?:[\s()-]*\d){7,}(?!\w)")
_PROVIDER_SENSITIVE_TEXT_RE = re.compile(
    r"""(?i)(['"](?:api_key|authorization|user_id)['"]\s*:\s*['"])[^'"]+(['"])"""
)
_DASH_TRANSLATION = str.maketrans({"–": "-", "—": "-", "−": "-"})
_BLIND_REVIEW_DIMENSIONS = {
    "clarity",
    "factual_trust",
    "persuasion",
    "concision",
    "next_step",
}


@dataclass(frozen=True, slots=True)
class CandidateMetrics:
    model: str
    weighted_score: float
    hard_gates_passed: bool
    reliability: float
    p95_ms: float


@dataclass(frozen=True, slots=True)
class WinnerDecision:
    outcome: str
    winner: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class ProviderAttempt:
    attempt: int
    ok: bool
    status_code: int | None
    elapsed_ms: float
    response: dict[str, Any] | None
    error: str | None


class RequestCostBudget:
    """Reserve worst-case request cost before each provider attempt."""

    def __init__(
        self,
        *,
        catalog: Mapping[str, Mapping[str, Any]],
        estimated_costs: Mapping[str, float],
    ) -> None:
        self._catalog = catalog
        self._caps = {
            model: min(1.0, max(0.0, float(estimate)) * 1.25)
            for model, estimate in estimated_costs.items()
        }
        self._reserved = {model: 0.0 for model in estimated_costs}

    def reserve_request(self, model: str, payload: Mapping[str, Any]) -> float:
        pricing = self._catalog.get(model, {}).get("pricing", {})
        if not isinstance(pricing, Mapping):
            raise RuntimeError(f"Missing catalog pricing for {model}")
        try:
            prompt_price = float(pricing["prompt"])
            completion_price = float(pricing["completion"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Invalid catalog pricing for {model}") from exc
        prompt_payload = {
            "messages": payload.get("messages", []),
            "tools": payload.get("tools", []),
        }
        prompt_tokens = max(
            1,
            math.ceil(
                len(json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True)) / 4
            ),
        )
        max_tokens = payload.get("max_tokens", 0)
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int | float):
            raise RuntimeError("Request max_tokens must be numeric for cost preflight")
        worst_case = prompt_tokens * prompt_price + float(max_tokens) * completion_price
        cap = self._caps.get(model)
        if cap is None:
            raise RuntimeError(f"No cost cap configured for {model}")
        next_total = self._reserved.get(model, 0.0) + worst_case
        if next_total > cap + 1e-12:
            raise RuntimeError(
                "Model cost cap would be exceeded before provider request: "
                f"{model} reserved ${self._reserved.get(model, 0.0):.6f}, "
                f"next worst-case ${worst_case:.6f}, cap ${cap:.6f}"
            )
        self._reserved[model] = next_total
        return worst_case


def parse_json_content(content: str) -> Any:
    """Parse a JSON response, accepting a single common Markdown fence."""

    candidate = content.strip()
    match = _JSON_FENCE_RE.fullmatch(candidate)
    if match:
        candidate = match.group(1).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Response is not valid JSON: {exc.msg}") from exc


def _schema_type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return False


def validate_json_schema(
    value: Any,
    schema: Mapping[str, Any],
    *,
    path: str = "$",
) -> list[str]:
    """Validate the strict JSON-Schema subset used by the benchmark cases."""

    errors: list[str] = []
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        if not any(_schema_type_matches(value, item) for item in schema_type):
            errors.append(f"{path}: expected one of types {schema_type}")
            return errors
    elif isinstance(schema_type, str) and not _schema_type_matches(value, schema_type):
        errors.append(f"{path}: expected type {schema_type}")
        return errors

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} is not in enum {schema['enum']!r}")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: required property is missing")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key}: unexpected property")
        for key, child in value.items():
            child_schema = properties.get(key)
            if isinstance(child_schema, Mapping):
                errors.extend(
                    validate_json_schema(child, child_schema, path=f"{path}.{key}")
                )

    if isinstance(value, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path}: expected at least {min_items} items")
        if isinstance(max_items, int) and len(value) > max_items:
            errors.append(f"{path}: expected at most {max_items} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, child in enumerate(value):
                errors.extend(
                    validate_json_schema(
                        child,
                        item_schema,
                        path=f"{path}[{index}]",
                    )
                )

    if isinstance(value, str):
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{path}: shorter than minLength {min_length}")
        if isinstance(max_length, int) and len(value) > max_length:
            errors.append(f"{path}: longer than maxLength {max_length}")

    if isinstance(value, int | float) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, int | float) and value < minimum:
            errors.append(f"{path}: value {value!r} is below minimum {minimum!r}")
        if isinstance(maximum, int | float) and value > maximum:
            errors.append(f"{path}: value {value!r} is above maximum {maximum!r}")

    return errors


def _path_parts(path: str) -> list[str | int]:
    parts: list[str | int] = []
    for match in _PATH_PART_RE.finditer(path):
        if match.group(1) is not None:
            parts.append(match.group(1))
        else:
            parts.append(int(match.group(2)))
    return parts


def _get_path(value: Any, path: str) -> tuple[bool, Any]:
    current = value
    for part in _path_parts(path):
        if part == "$length":
            if isinstance(current, dict | list | str):
                current = len(current)
                continue
            return False, None
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return False, None
            current = current[part]
        else:
            if not isinstance(current, dict) or part not in current:
                return False, None
            current = current[part]
    return True, current


def _normalize_expected_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = value.translate(_DASH_TRANSLATION).casefold()
    return " ".join(normalized.split()).rstrip(" .!?،؛")


def _matches_expected(actual: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping) and set(expected) == {"$number"}:
        number = str(expected["$number"])
        if isinstance(actual, int | float) and not isinstance(actual, bool):
            return str(actual) == number
        if isinstance(actual, str):
            return number in extract_numeric_tokens(actual)
        return False
    if (
        isinstance(expected, Mapping)
        and set(expected) == {"$contains_all"}
        and isinstance(expected["$contains_all"], list)
        and isinstance(actual, str)
    ):
        normalized = _normalize_expected_value(actual)
        return all(
            _normalize_expected_value(fragment) in normalized
            for fragment in expected["$contains_all"]
        )
    return _normalize_expected_value(actual) == _normalize_expected_value(expected)


def score_expected_fields(
    payload: Any,
    expected_fields: Mapping[str, Any],
) -> tuple[int, int, list[str]]:
    """Compare path-addressed semantic golden values with normalized strings."""

    correct = 0
    mismatches: list[str] = []
    for raw_path, expected in expected_fields.items():
        path = raw_path.removeprefix("$.")
        exists, actual = _get_path(payload, path)
        display_path = f"$.{path}"
        if not exists:
            mismatches.append(f"{display_path}: missing")
            continue
        if _matches_expected(actual, expected):
            correct += 1
        else:
            mismatches.append(f"{display_path}: expected {expected!r}, got {actual!r}")
    return correct, len(expected_fields), mismatches


def percentile(values: Sequence[float], quantile: float) -> float:
    """Calculate a linearly interpolated percentile."""

    if not values:
        raise ValueError("Cannot calculate a percentile of an empty sequence")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * weight)


def models_for_profile(profile: str, suite: str) -> tuple[str, ...]:
    """Return the immutable candidate tuple for one benchmark route."""

    try:
        profile_suites = MODEL_PROFILES[profile]
    except KeyError as exc:
        raise ValueError(f"Unknown benchmark profile: {profile}") from exc
    try:
        return profile_suites[suite]
    except KeyError as exc:
        raise ValueError(f"Unknown suite: {suite}") from exc


def cases_for_profile(profile: str, suite: str) -> tuple[Any, ...]:
    """Return the immutable fixture set selected by a benchmark profile."""

    from scripts.model_battle_cases import (
        BACKGROUND_HARD_CASES,
        CORE_HARD_CASES,
        SALES_CASES,
        SYSTEM_CASES,
    )

    if suite == "sales":
        return CORE_HARD_CASES if profile == CORE_HARD_PROFILE else SALES_CASES
    if suite == "system":
        return (
            BACKGROUND_HARD_CASES
            if profile == BACKGROUND_HARD_PROFILE
            else SYSTEM_CASES
        )
    raise ValueError(f"Unknown suite: {suite}")


def merge_run_manifest(
    existing: Mapping[str, Any] | None,
    *,
    suites: Sequence[str],
    profile: str,
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    """Merge separately executed suites while rejecting incompatible evidence."""

    previous_suites: list[str] = []
    if existing:
        expected_identity = {
            "seed": seed,
            "repetitions": repetitions,
            "profile": profile,
            "production_changed": False,
            "synthetic_evidence_only": True,
        }
        mismatches = [
            field
            for field, expected in expected_identity.items()
            if existing.get(field) != expected
        ]
        if mismatches:
            raise ValueError(
                "Existing run manifest is incompatible for fields: "
                + ", ".join(mismatches)
            )
        raw_suites = existing.get("suites")
        if not isinstance(raw_suites, list) or not all(
            isinstance(suite, str) for suite in raw_suites
        ):
            raise ValueError("Existing run manifest has invalid suites")
        previous_suites = raw_suites
        raw_models = existing.get("models")
        if not isinstance(raw_models, Mapping):
            raise ValueError("Existing run manifest has invalid models")
        invalid_model_suites = [
            suite
            for suite in previous_suites
            if raw_models.get(suite) != list(models_for_profile(profile, suite))
        ]
        if invalid_model_suites:
            raise ValueError(
                "Existing run manifest has incompatible models for suites: "
                + ", ".join(invalid_model_suites)
            )

    requested_suites = set(previous_suites) | set(suites)
    merged_suites = [
        suite for suite in ("sales", "system") if suite in requested_suites
    ]
    merged: dict[str, Any] = {
        "seed": seed,
        "repetitions": repetitions,
        "suites": merged_suites,
        "profile": profile,
        "models": {
            suite: list(models_for_profile(profile, suite)) for suite in merged_suites
        },
        "production_changed": False,
        "synthetic_evidence_only": True,
        "staged": profile in _HARD_PROFILES,
    }
    if existing and isinstance(existing.get("job_matrix"), Mapping):
        merged["job_matrix"] = dict(existing["job_matrix"])
    return merged


def build_blind_pair(
    *,
    case_id: str,
    repetition: int,
    candidates: Mapping[str, str],
    seed: int,
    assignment_index: int | None = None,
) -> dict[str, Any]:
    """Build a deterministic anonymous group with a separate reveal key."""

    if len(candidates) < 2:
        raise ValueError("Blinded review requires at least two candidates")
    if len(candidates) > 26:
        raise ValueError("Blinded review supports at most 26 candidates")
    model_names = sorted(candidates)
    if len(model_names) == 2:
        material = f"{seed}:{case_id}:{repetition}".encode()
        if hashlib.sha256(material).digest()[0] % 2:
            model_names.reverse()
    else:
        random.Random(f"{seed}:multi-model-order").shuffle(model_names)
        if assignment_index is None:
            material = f"{seed}:{case_id}:{repetition}".encode()
            assignment_index = int.from_bytes(
                hashlib.sha256(material).digest()[:4],
                "big",
            )
        offset = assignment_index % len(model_names)
        model_names = model_names[offset:] + model_names[:offset]
    reveal = {chr(ord("A") + index): model for index, model in enumerate(model_names)}
    return {
        "case_id": case_id,
        "repetition": repetition,
        "answers": {label: candidates[model] for label, model in reveal.items()},
        "reveal": reveal,
    }


def normalize_blind_reviews(
    reviews: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize the single common reviewer alias without changing scores."""

    normalized: list[dict[str, Any]] = []
    for source in reviews:
        row = dict(source)
        if "scores" not in row and isinstance(row.get("answers"), Mapping):
            row["scores"] = row.pop("answers")
        normalized.append(row)
    return normalized


def blind_scores_digest(reviews: Sequence[Mapping[str, Any]]) -> str:
    """Return a canonical commitment for scores captured before identity reveal."""

    canonical = json.dumps(
        list(reviews),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_blind_scores_seal(
    reviews: Sequence[Mapping[str, Any]],
    expected_digest: str,
) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise ValueError("Blind score seal is not a SHA-256 digest")
    if blind_scores_digest(reviews) != expected_digest:
        raise ValueError("Blind score seal does not match the submitted review")


def evaluate_blind_reviews(
    reviews: Sequence[Mapping[str, Any]],
    key_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, float], dict[str, bool]]:
    """Validate completed blinded rubrics and reveal aggregate model quality."""

    review_by_pair = {
        (str(row["case_id"]), int(row["repetition"])): row for row in reviews
    }
    key_by_pair = {
        (str(row["case_id"]), int(row["repetition"])): row for row in key_rows
    }
    if set(review_by_pair) != set(key_by_pair):
        raise ValueError("Blind review pairs do not match the reveal key")

    points: dict[str, list[int]] = {}
    hard_gate_observations: dict[str, list[bool]] = {}
    for pair, key_row in key_by_pair.items():
        review = review_by_pair[pair]
        scores = review.get("scores")
        reveal = key_row.get("reveal")
        if not isinstance(scores, Mapping) or not isinstance(reveal, Mapping):
            raise ValueError(f"{pair}: missing scores or reveal mapping")
        if set(scores) != set(reveal):
            raise ValueError(f"{pair}: score labels do not match reveal labels")
        for label in sorted(reveal):
            label_review = scores.get(label)
            model = reveal.get(label)
            if not isinstance(label_review, Mapping) or not isinstance(model, str):
                raise ValueError(f"{pair}: incomplete label {label}")
            label_scores = label_review.get("scores")
            critical_failure = label_review.get("critical_failure")
            critical_reason = label_review.get("critical_failure_reason")
            if (
                not isinstance(label_scores, Mapping)
                or not isinstance(critical_failure, bool)
                or not isinstance(critical_reason, str)
            ):
                raise ValueError(f"{pair}: incomplete rubric for {label}")
            if critical_failure and not critical_reason.strip():
                raise ValueError(f"{pair}: critical failure for {label} lacks a reason")
            if set(label_scores) != _BLIND_REVIEW_DIMENSIONS:
                raise ValueError(f"{pair}: invalid review dimensions for {label}")
            values = list(label_scores.values())
            if not all(
                isinstance(value, int)
                and not isinstance(value, bool)
                and 1 <= value <= 5
                for value in values
            ):
                raise ValueError(f"{pair}: review scores must be integers from 1 to 5")
            points.setdefault(model, []).extend(values)
            hard_gate_observations.setdefault(model, []).append(not critical_failure)
    quality = {
        model: sum(model_points) / (len(model_points) * 5)
        for model, model_points in points.items()
    }
    hard_gates = {
        model: all(observations)
        for model, observations in hard_gate_observations.items()
    }
    return quality, hard_gates


def score_blind_reviews(
    reviews: Sequence[Mapping[str, Any]],
    key_rows: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    quality, _hard_gates = evaluate_blind_reviews(reviews, key_rows)
    return quality


def detect_evaluator_disagreements(
    evaluator_rows: Sequence[Mapping[str, Any]],
    blind_audits: Sequence[Mapping[str, Any]],
    key_rows: Sequence[Mapping[str, Any]],
    *,
    tolerance: float = 2.0,
) -> list[dict[str, Any]]:
    """Compare sealed blind audits with evaluator scores after identity reveal."""

    evaluator_by_key = {
        (str(row["case_id"]), int(row["repetition"]), str(row["model"])): row
        for row in evaluator_rows
    }
    key_by_pair = {
        (str(row["case_id"]), int(row["repetition"])): row for row in key_rows
    }
    disagreements: list[dict[str, Any]] = []
    for audit in blind_audits:
        pair = (str(audit["case_id"]), int(audit["repetition"]))
        key_row = key_by_pair.get(pair)
        scores = audit.get("scores")
        reveal = key_row.get("reveal") if isinstance(key_row, Mapping) else None
        if not isinstance(scores, Mapping) or not isinstance(reveal, Mapping):
            raise ValueError(f"{pair}: blind audit lacks sealed reveal mapping")
        for label, audit_score in scores.items():
            model = reveal.get(label)
            if not isinstance(model, str) or not isinstance(audit_score, Mapping):
                raise ValueError(f"{pair}: incomplete audit label {label}")
            evaluator = evaluator_by_key.get((*pair, model))
            if evaluator is None:
                raise ValueError(f"{pair}: missing evaluator row for {model}")
            expected_applicability = {
                str(item) for item in evaluator.get("applicable_rules", [])
            }
            audited_applicability = {
                str(item) for item in audit_score.get("applicable_rules", [])
            }
            if expected_applicability != audited_applicability:
                reason = "applicability"
            else:
                delta = abs(
                    float(evaluator.get("score_out_of_30", 0))
                    - float(audit_score.get("score_out_of_30", 0))
                )
                if delta <= tolerance:
                    continue
                reason = "score_delta"
            disagreements.append(
                {
                    "status": "EVAL_DISAGREEMENT",
                    "case_id": pair[0],
                    "repetition": pair[1],
                    "model": model,
                    "reason": reason,
                }
            )
    return disagreements


def select_winner(
    candidates: Sequence[CandidateMetrics],
    *,
    tie_band_points: float = 2.0,
    material_latency_ratio: float = 0.75,
    material_reliability_gap: float = 0.02,
) -> WinnerDecision:
    """Select a safe winner using hard gates before weighted efficiency."""

    if len(candidates) < 2:
        raise ValueError("Winner selection requires at least two candidates")
    safe = [candidate for candidate in candidates if candidate.hard_gates_passed]
    if not safe:
        return WinnerDecision(
            outcome="no_safe_replacement",
            winner=None,
            reason="All candidates failed at least one hard gate.",
        )
    if len(safe) == 1:
        return WinnerDecision(
            outcome="winner",
            winner=safe[0].model,
            reason="Every other candidate failed at least one hard gate.",
        )

    ordered = sorted(safe, key=lambda item: item.weighted_score, reverse=True)
    leader = ordered[0]
    score_gap = leader.weighted_score - ordered[1].weighted_score
    if score_gap >= tie_band_points:
        return WinnerDecision(
            outcome="winner",
            winner=leader.model,
            reason=f"Weighted score leads by {score_gap:.2f} points.",
        )

    contenders = [
        candidate
        for candidate in ordered
        if leader.weighted_score - candidate.weighted_score < tie_band_points
    ]
    by_reliability = sorted(
        contenders,
        key=lambda item: item.reliability,
        reverse=True,
    )
    reliability_gap = by_reliability[0].reliability - by_reliability[1].reliability
    if reliability_gap >= material_reliability_gap:
        reliable = by_reliability[0]
        return WinnerDecision(
            outcome="winner",
            winner=reliable.model,
            reason=(
                "Scores are inside the tie band, but first-pass reliability "
                f"leads by {reliability_gap:.2%}."
            ),
        )

    by_latency = sorted(contenders, key=lambda item: item.p95_ms)
    faster = by_latency[0]
    next_fastest = by_latency[1]
    if faster.p95_ms <= next_fastest.p95_ms * material_latency_ratio:
        return WinnerDecision(
            outcome="winner",
            winner=faster.model,
            reason=(
                "Scores are inside the tie band, but p95 latency has a "
                "material advantage."
            ),
        )
    return WinnerDecision(
        outcome="practical_tie",
        winner=None,
        reason=(
            "Leading safe candidates are within two points without a material "
            "latency or reliability advantage."
        ),
    )


def select_hard_profile_winner(
    profile: str,
    rows: Sequence[Mapping[str, Any]],
) -> WinnerDecision:
    """Apply the accepted hard-profile gates and deterministic baseline ties."""

    if profile == CORE_HARD_PROFILE:
        baseline = "z-ai/glm-5.2"
        expected_cases = {case.case_id for case in cases_for_profile(profile, "sales")}
        by_model: dict[str, list[Mapping[str, Any]]] = {}
        for row in rows:
            by_model.setdefault(str(row["model"]), []).append(row)
        ranked: list[tuple[str, float, float, float, float]] = []
        for model, model_rows in by_model.items():
            if any(
                not bool(row.get("objective", {}).get("hard_gate_passed"))
                for row in model_rows
            ):
                continue
            case_scores: list[float] = []
            all_scores: list[float] = []
            complete = True
            for case_id in expected_cases:
                scores = [
                    float(row["objective"]["score_out_of_30"])
                    for row in model_rows
                    if row["case_id"] == case_id
                ]
                if len(scores) != 3:
                    complete = False
                    break
                median = statistics.median(scores)
                if median < 20:
                    complete = False
                    break
                case_scores.append(median)
                all_scores.extend(scores)
            if not complete or statistics.fmean(case_scores) < 24:
                continue
            p95 = percentile(
                [float(row.get("latency_ms", 0)) for row in model_rows],
                0.95,
            )
            cost = sum(
                float(row.get("accounting", {}).get("cost_usd", 0))
                for row in model_rows
            )
            spread = statistics.pstdev(all_scores) if len(all_scores) > 1 else 0.0
            ranked.append((model, statistics.fmean(case_scores), spread, p95, cost))
    elif profile == BACKGROUND_HARD_PROFILE:
        baseline = "deepseek/deepseek-v4-flash"
        by_model = {}
        for row in rows:
            by_model.setdefault(str(row["model"]), []).append(row)
        ranked = []
        for model, model_rows in by_model.items():
            if not all(
                bool(row.get("success", row.get("first_pass_success")))
                and bool(row.get("json_parse_ok"))
                and bool(row.get("schema_ok"))
                and bool(row.get("critical_fields_ok", True))
                and not bool(row.get("pii_leakage", False))
                for row in model_rows
            ):
                continue
            correct = sum(int(row.get("semantic_correct", 0)) for row in model_rows)
            total = sum(int(row.get("semantic_total", 0)) for row in model_rows)
            accuracy = correct / total if total else 0.0
            if accuracy < 0.95:
                continue
            per_row = [
                int(row.get("semantic_correct", 0))
                / max(1, int(row.get("semantic_total", 0)))
                for row in model_rows
            ]
            p95 = percentile(
                [float(row.get("latency_ms", 0)) for row in model_rows],
                0.95,
            )
            cost = sum(
                float(row.get("accounting", {}).get("cost_usd", 0))
                for row in model_rows
            )
            spread = statistics.pstdev(per_row) * 30 if len(per_row) > 1 else 0.0
            ranked.append((model, accuracy * 30, spread, p95, cost))
    else:
        raise ValueError(f"Not a hard profile: {profile}")

    if not ranked:
        return WinnerDecision(
            outcome="no_safe_replacement",
            winner=None,
            reason="All candidates failed at least one hard-profile gate.",
        )
    ranked.sort(key=lambda item: (-item[1], item[2], item[3], item[4], item[0]))
    if len(ranked) == 1:
        return WinnerDecision(
            outcome="winner",
            winner=ranked[0][0],
            reason="Every other candidate failed a hard-profile gate.",
        )
    leader, runner_up = ranked[:2]
    gap = leader[1] - runner_up[1]
    observed_spread = max(leader[2], runner_up[2])
    if gap < 1.0 or gap < observed_spread:
        safe_models = {item[0] for item in ranked}
        tie_winner = baseline if baseline in safe_models else leader[0]
        return WinnerDecision(
            outcome="practical_tie",
            winner=tie_winner,
            reason="Quality difference is below one point or observed variation.",
        )
    return WinnerDecision(
        outcome="winner",
        winner=leader[0],
        reason=f"Quality leads by {gap:.2f} points after hard gates.",
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def assert_existing_run_evidence(
    output_dir: Path,
    manifest: Mapping[str, Any],
) -> None:
    """Reject a partial prior suite before merging new evidence metadata."""

    profile = str(manifest["profile"])
    repetitions = int(manifest["repetitions"])
    case_ids = {
        suite: [case.case_id for case in cases_for_profile(profile, suite)]
        for suite in manifest.get("suites", [])
    }
    for suite in manifest.get("suites", []):
        if suite not in case_ids:
            raise ValueError(f"Existing run manifest has unknown suite: {suite}")
        path = output_dir / f"{suite}_results.jsonl"
        if not path.exists():
            raise ValueError(f"Existing {suite} evidence is incomplete: file missing")
        rows = _read_jsonl(path)
        if any(str(row.get("suite")) != suite for row in rows):
            raise ValueError(f"Existing {suite} evidence contains a wrong suite tag")
        matrix = manifest.get("job_matrix", {}).get(suite)
        if profile in _HARD_PROFILES and isinstance(matrix, list):
            expected = {
                (
                    str(item["case_id"]),
                    int(item["repetition"]),
                    str(item["model"]),
                )
                for item in matrix
            }
        else:
            expected = {
                (case_id, repetition, model)
                for case_id in case_ids[suite]
                for repetition in range(1, repetitions + 1)
                for model in models_for_profile(profile, suite)
            }
        actual = [
            (str(row["case_id"]), int(row["repetition"]), str(row["model"]))
            for row in rows
        ]
        if len(actual) != len(expected) or set(actual) != expected:
            raise ValueError(
                f"Existing {suite} evidence is incomplete or contains duplicates"
            )


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def combine_hard_profile_selections(
    core_dir: Path,
    background_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Seal verified main and background decisions into one route handoff."""

    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite sealed selection: {output_path}")
    core_manifest = _read_json_object(core_dir / "run_manifest.json")
    background_manifest = _read_json_object(background_dir / "run_manifest.json")
    if core_manifest.get("profile") != CORE_HARD_PROFILE:
        raise ValueError("Core selection does not belong to the core hard profile")
    if background_manifest.get("profile") != BACKGROUND_HARD_PROFILE:
        raise ValueError(
            "Background selection does not belong to the background hard profile"
        )

    core_path = core_dir / "model_selection.json"
    background_path = background_dir / "model_selection.json"
    core = _read_json_object(core_path)
    background = _read_json_object(background_path)
    main_decision = core.get("openrouter_model_main")
    fast_decision = background.get("openrouter_model_fast")
    if not isinstance(main_decision, Mapping) or not isinstance(fast_decision, Mapping):
        raise ValueError("Both main and background route decisions are required")

    payload: dict[str, Any] = {
        "schema_version": "noor-model-selection/v1",
        "openrouter_model_main": dict(main_decision),
        "openrouter_model_fast": dict(fast_decision),
        "core_selection_sha256": hashlib.sha256(core_path.read_bytes()).hexdigest(),
        "background_selection_sha256": hashlib.sha256(
            background_path.read_bytes()
        ).hexdigest(),
        "production_changed": False,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload["sealed_sha256"] = hashlib.sha256(canonical).hexdigest()
    _write_json(output_path, payload)
    return payload


def _sanitize_provider_payload(value: Any) -> Any:
    """Remove provider/account identifiers before preserving raw evidence."""

    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]"
                if str(key).casefold() in {"api_key", "authorization", "user_id"}
                else _sanitize_provider_payload(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_provider_payload(item) for item in value]
    if isinstance(value, str):
        return _PROVIDER_SENSITIVE_TEXT_RE.sub(
            r"\1[REDACTED]\2",
            value,
        )
    return value


def _safe_error_text(value: Any, limit: int = 500) -> str:
    sanitized = _sanitize_provider_payload(value)
    text = str(sanitized)
    if settings.openrouter_api_key:
        text = text.replace(settings.openrouter_api_key, "[REDACTED]")
    text = _PROVIDER_SENSITIVE_TEXT_RE.sub(r"\1[REDACTED]\2", text)
    return text[:limit]


async def _request_with_retry(
    client: httpx.AsyncClient,
    *,
    payload: Mapping[str, Any],
    timeout_seconds: float,
    before_request: Callable[[], object] | None = None,
) -> list[ProviderAttempt]:
    attempts: list[ProviderAttempt] = []
    for attempt_number in (1, 2):
        if before_request is not None:
            before_request()
        started = time.perf_counter()
        try:
            response = await client.post(
                "/chat/completions",
                json=dict(payload),
                timeout=timeout_seconds,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            parsed: dict[str, Any] | None
            try:
                response_payload = response.json()
                parsed = (
                    response_payload
                    if isinstance(response_payload, dict)
                    else {"value": response_payload}
                )
                parsed = _sanitize_provider_payload(parsed)
            except ValueError:
                parsed = None
            ok = response.is_success and bool(parsed and parsed.get("choices"))
            error = None if ok else _safe_error_text(parsed or response.text)
            attempts.append(
                ProviderAttempt(
                    attempt=attempt_number,
                    ok=ok,
                    status_code=response.status_code,
                    elapsed_ms=round(elapsed_ms, 3),
                    response=parsed,
                    error=error,
                )
            )
        except (httpx.HTTPError, TimeoutError) as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            attempts.append(
                ProviderAttempt(
                    attempt=attempt_number,
                    ok=False,
                    status_code=None,
                    elapsed_ms=round(elapsed_ms, 3),
                    response=None,
                    error=_safe_error_text(exc),
                )
            )
        if attempts[-1].ok:
            break
        if attempts[-1].status_code is not None and not should_retry_status(
            attempts[-1].status_code
        ):
            break
    return attempts


def _choice_message(attempts: Sequence[ProviderAttempt]) -> dict[str, Any] | None:
    if not attempts or not attempts[-1].ok or attempts[-1].response is None:
        return None
    choices = attempts[-1].response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message")
    return message if isinstance(message, dict) else None


def _usage(attempts: Sequence[ProviderAttempt]) -> dict[str, Any]:
    if not attempts or attempts[-1].response is None:
        return {}
    value = attempts[-1].response.get("usage")
    return value if isinstance(value, dict) else {}


def summarize_attempt_accounting(
    attempts: Sequence[ProviderAttempt | Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate tokens, cache, cost, latency and routing from every attempt."""

    totals: dict[str, int | float] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": 0.0,
    }
    resolved_models: set[str] = set()
    providers: set[str] = set()
    endpoints: set[str] = set()
    for attempt in attempts:
        response = (
            attempt.response
            if isinstance(attempt, ProviderAttempt)
            else attempt.get("response")
        )
        elapsed_ms = (
            attempt.elapsed_ms
            if isinstance(attempt, ProviderAttempt)
            else attempt.get("elapsed_ms", 0)
        )
        if isinstance(elapsed_ms, int | float):
            totals["latency_ms"] += float(elapsed_ms)
        if not isinstance(response, Mapping):
            continue
        for field, target in (
            ("model", resolved_models),
            ("provider", providers),
            ("endpoint", endpoints),
        ):
            value = response.get(field)
            if isinstance(value, str) and value:
                target.add(value)
        usage = response.get("usage")
        if not isinstance(usage, Mapping):
            continue
        for source, target in (
            ("prompt_tokens", "input_tokens"),
            ("completion_tokens", "output_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            value = usage.get(source, 0)
            if isinstance(value, int | float) and not isinstance(value, bool):
                totals[target] += int(value)
        prompt_details = usage.get("prompt_tokens_details")
        if isinstance(prompt_details, Mapping):
            cached = prompt_details.get("cached_tokens", 0)
            if isinstance(cached, int | float) and not isinstance(cached, bool):
                totals["cached_tokens"] += int(cached)
        cost = usage.get("cost", 0)
        if isinstance(cost, int | float) and not isinstance(cost, bool):
            totals["cost_usd"] += float(cost)
    return {
        "attempts": len(attempts),
        "input_tokens": int(totals["input_tokens"]),
        "output_tokens": int(totals["output_tokens"]),
        "total_tokens": int(totals["total_tokens"]),
        "cached_tokens": int(totals["cached_tokens"]),
        "cost_usd": round(float(totals["cost_usd"]), 12),
        "latency_ms": round(float(totals["latency_ms"]), 3),
        "resolved_models": sorted(resolved_models),
        "providers": sorted(providers),
        "endpoints": sorted(endpoints),
    }


def enforce_model_cost_caps(
    rows: Sequence[Mapping[str, Any]],
    estimated_costs: Mapping[str, float],
) -> None:
    """Fail closed when all-attempt spend exceeds 1.25x estimate or USD 1."""

    actual: dict[str, float] = {}
    for row in rows:
        model = str(row["model"])
        accounting = row.get("accounting")
        if not isinstance(accounting, Mapping):
            continue
        cost = accounting.get("cost_usd", 0)
        if isinstance(cost, int | float) and not isinstance(cost, bool):
            actual[model] = actual.get(model, 0.0) + float(cost)
    exceeded: list[str] = []
    for model, estimate in estimated_costs.items():
        cap = min(1.0, max(0.0, float(estimate)) * 1.25)
        if actual.get(model, 0.0) > cap + 1e-12:
            exceeded.append(f"{model}: spent ${actual[model]:.6f}, cap ${cap:.6f}")
    if exceeded:
        raise RuntimeError("Model cost cap exceeded: " + "; ".join(exceeded))


def estimate_model_costs(
    catalog: Mapping[str, Mapping[str, Any]],
    *,
    profile: str,
    suite: str,
) -> dict[str, float]:
    """Estimate the maximum staged run from catalog prices before paid calls."""

    cases = cases_for_profile(profile, suite)
    if profile == BACKGROUND_HARD_PROFILE:
        planned_case_runs = len(cases) + 2 * min(3, len(cases))
    elif profile == CORE_HARD_PROFILE:
        planned_case_runs = len(cases) * 3
    else:
        planned_case_runs = len(cases)
    max_output_tokens = 2200 if suite == "sales" else 900
    maximum_input_tokens = max(
        1,
        max(
            math.ceil(
                (
                    len(case.system_prompt)
                    + len(case.user_prompt)
                    + (
                        sum(len(item["content"]) for item in case.conversation)
                        + len(json.dumps(case.tools, ensure_ascii=False))
                        + 3 * len(json.dumps(case.tool_results, ensure_ascii=False))
                        if suite == "sales"
                        else 0
                    )
                )
                / 4
            )
            for case in cases
        ),
    )
    maximum_provider_attempts = 6 if suite == "sales" else 2
    estimates: dict[str, float] = {}
    for model in models_for_profile(profile, suite):
        pricing = catalog.get(model, {}).get("pricing", {})
        if not isinstance(pricing, Mapping):
            raise RuntimeError(f"Missing catalog pricing for {model}")
        try:
            prompt_price = float(pricing["prompt"])
            completion_price = float(pricing["completion"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Invalid catalog pricing for {model}") from exc
        estimates[model] = round(
            planned_case_runs
            * maximum_provider_attempts
            * (
                maximum_input_tokens * prompt_price
                + max_output_tokens * completion_price
            ),
            12,
        )
    return estimates


def reasoning_was_observed(
    attempts: Sequence[ProviderAttempt | Mapping[str, Any]],
) -> bool:
    """Detect reasoning returned despite a reasoning-disabled request."""

    for attempt in attempts:
        response = (
            attempt.response
            if isinstance(attempt, ProviderAttempt)
            else attempt.get("response")
        )
        if not isinstance(response, Mapping):
            continue
        usage = response.get("usage")
        if isinstance(usage, Mapping):
            details = usage.get("completion_tokens_details")
            if isinstance(details, Mapping):
                tokens = details.get("reasoning_tokens")
                if isinstance(tokens, int | float) and tokens > 0:
                    return True
        choices = response.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, Mapping):
                    continue
                message = choice.get("message")
                if isinstance(message, Mapping) and (
                    message.get("reasoning") or message.get("reasoning_details")
                ):
                    return True
    return False


def should_retry_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def build_base_payload(
    *,
    model: str,
    messages: Sequence[Mapping[str, Any]],
    max_tokens: int,
    reasoning_enabled: bool | None = None,
) -> dict[str, Any]:
    owner = model.partition("/")[0]
    provider: dict[str, Any] = {"require_parameters": True}
    provider_slug = _FIRST_PARTY_PROVIDERS.get(owner)
    if provider_slug is not None:
        provider.update(
            {
                "only": [provider_slug],
                "allow_fallbacks": False,
            }
        )
    payload: dict[str, Any] = {
        "model": model,
        "messages": list(messages),
        "max_tokens": max_tokens,
        "provider": provider,
    }
    if reasoning_enabled is not None:
        payload["reasoning"] = {"enabled": reasoning_enabled}
    return payload


def _request_parameter_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _sanitize_provider_payload(payload[key])
        for key in (
            "model",
            "max_tokens",
            "provider",
            "reasoning",
            "tool_choice",
            "response_format",
        )
        if key in payload
    }


def _extract_tool_calls(message: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not message:
        return []
    raw = message.get("tool_calls")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _parse_tool_arguments(tool_call: Mapping[str, Any]) -> tuple[str, Any, str | None]:
    function = tool_call.get("function")
    if not isinstance(function, Mapping):
        return "", None, "missing function"
    name = function.get("name")
    raw_arguments = function.get("arguments")
    if not isinstance(name, str) or not isinstance(raw_arguments, str):
        return str(name or ""), None, "missing tool name or arguments"
    try:
        return name, json.loads(raw_arguments), None
    except json.JSONDecodeError as exc:
        return name, None, f"invalid tool JSON: {exc.msg}"


def _normal_text(value: str) -> str:
    return " ".join(value.translate(_DASH_TRANSLATION).casefold().split())


def _contains_asserted_phrase(content: str, phrase: str) -> bool:
    """Return true when a forbidden phrase occurs outside a negated clause."""

    start = 0
    while True:
        index = content.find(phrase, start)
        if index < 0:
            return False
        boundaries = [
            content.rfind(marker, 0, index) + len(marker)
            for marker in (".", "!", "?", ";", ",", "\n", " but ", " however ")
        ]
        clause_prefix = content[max(boundaries) : index]
        negated = re.search(
            r"\b(?:not|never|cannot|can't|cant|unable to|unconfirmed)\b",
            clause_prefix,
        )
        if negated is None:
            return True
        start = index + len(phrase)


def extract_numeric_tokens(value: str) -> set[str]:
    """Extract normalized numeric tokens for factual grounding checks."""

    return {token.rstrip("%").replace(",", "") for token in _NUMBER_RE.findall(value)}


def contains_pii_leakage(output: str, source: str) -> bool:
    """Detect contact details that were not present in the synthetic fixture."""

    output_pii = set(_EMAIL_RE.findall(output)) | set(_PHONE_RE.findall(output))
    source_pii = set(_EMAIL_RE.findall(source)) | set(_PHONE_RE.findall(source))
    return bool(output_pii - source_pii)


def retry_was_used(attempt_counts_by_round: Sequence[int]) -> bool:
    """A second tool round is not a provider retry."""

    return any(count > 1 for count in attempt_counts_by_round)


def _language_matches(content: str, expected_language: str | None) -> bool:
    if expected_language is None:
        return True
    letters = [character for character in content if character.isalpha()]
    if not letters:
        return False
    arabic_letters = len(_ARABIC_RE.findall(content))
    arabic_ratio = arabic_letters / len(letters)
    cyrillic_ratio = len(_CYRILLIC_RE.findall(content)) / len(letters)
    if expected_language == "ar":
        return arabic_ratio >= 0.35
    if expected_language == "en":
        return arabic_ratio < 0.10 and cyrillic_ratio < 0.10
    if expected_language == "ru":
        return cyrillic_ratio >= 0.35
    raise ValueError(f"Unsupported expected language: {expected_language}")


def score_sales_response(
    *,
    content: str,
    required_phrases: Sequence[str],
    forbidden_phrases: Sequence[str],
    expected_tools: Sequence[str],
    observed_tools: Sequence[str],
    expected_language: str | None,
    allowed_numbers: set[str],
    critical_required_phrases: Sequence[str] = (),
) -> dict[str, Any]:
    normalized = _normal_text(content)
    required_results = {
        phrase: _normal_text(phrase) in normalized for phrase in required_phrases
    }
    critical_required_results = {
        phrase: required_results.get(phrase, _normal_text(phrase) in normalized)
        for phrase in critical_required_phrases
    }
    forbidden_results = {
        phrase: not _contains_asserted_phrase(normalized, _normal_text(phrase))
        for phrase in forbidden_phrases
    }
    expected_tool_ok = list(observed_tools) == list(expected_tools)
    language_ok = _language_matches(content, expected_language)
    ungrounded_numbers = sorted(extract_numeric_tokens(content) - allowed_numbers)
    passed = (
        all(required_results.values())
        and all(forbidden_results.values())
        and expected_tool_ok
        and language_ok
        and not ungrounded_numbers
    )
    checks_total = len(required_results) + len(forbidden_results) + 3
    checks_passed = (
        sum(required_results.values())
        + sum(forbidden_results.values())
        + int(expected_tool_ok)
        + int(language_ok)
        + int(not ungrounded_numbers)
    )
    applicable_rules = [
        *(f"required:{phrase}" for phrase in required_phrases),
        *(f"forbidden:{phrase}" for phrase in forbidden_phrases),
        "tool_sequence",
        "language",
        "numeric_grounding",
    ]
    return {
        "passed": passed,
        "hard_gate_passed": (
            all(critical_required_results.values())
            and all(forbidden_results.values())
            and expected_tool_ok
            and language_ok
            and not ungrounded_numbers
        ),
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "score_out_of_30": round(30 * checks_passed / checks_total, 3),
        "applicable_rules": applicable_rules,
        "required_phrases": required_results,
        "critical_required_phrases": critical_required_results,
        "critical_required_phrases_passed": all(critical_required_results.values()),
        "forbidden_phrases": forbidden_results,
        "tool_sequence_ok": expected_tool_ok,
        "language_ok": language_ok,
        "ungrounded_numbers": ungrounded_numbers,
    }


async def _run_sales_case(
    client: httpx.AsyncClient,
    *,
    model: str,
    case: Any,
    repetition: int,
    cost_budget: RequestCostBudget | None = None,
) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": case.system_prompt},
    ]
    messages.extend(dict(item) for item in case.conversation)
    messages.append({"role": "user", "content": case.user_prompt})
    all_attempts: list[ProviderAttempt] = []
    attempt_counts_by_round: list[int] = []
    observed_tools: list[str] = []
    tool_argument_results: list[dict[str, Any]] = []
    final_content = ""
    request_parameters: list[dict[str, Any]] = []

    for _round in range(3):
        payload = build_base_payload(
            model=model,
            messages=messages,
            max_tokens=2200,
            reasoning_enabled=False,
        )
        if case.tools:
            payload["tools"] = list(case.tools)
            payload["tool_choice"] = "auto"
        request_parameters.append(_request_parameter_evidence(payload))
        attempts = await _request_with_retry(
            client,
            payload=payload,
            timeout_seconds=90.0,
            before_request=(
                None
                if cost_budget is None
                else lambda payload=payload: cost_budget.reserve_request(model, payload)
            ),
        )
        all_attempts.extend(attempts)
        attempt_counts_by_round.append(len(attempts))
        message = _choice_message(attempts)
        if message is None:
            break
        tool_calls = _extract_tool_calls(message)
        if not tool_calls:
            final_content = str(message.get("content") or "").strip()
            break

        messages.append(
            {
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": tool_calls,
            }
        )
        for tool_call in tool_calls:
            tool_name, arguments, parse_error = _parse_tool_arguments(tool_call)
            observed_tools.append(tool_name)
            expected_arguments = case.expected_tool_arguments.get(tool_name, {})
            correct, total, mismatches = score_expected_fields(
                arguments,
                expected_arguments,
            )
            tool_argument_results.append(
                {
                    "tool": tool_name,
                    "parse_error": parse_error,
                    "correct": correct,
                    "total": total,
                    "mismatches": mismatches,
                }
            )
            tool_result = case.tool_results.get(
                tool_name,
                {"error": "No synthetic tool result configured"},
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(tool_call.get("id") or tool_name),
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

    grounding_evidence = json.dumps(
        {
            "system_prompt": case.system_prompt,
            "user_prompt": case.user_prompt,
            "tool_results": case.tool_results,
        },
        ensure_ascii=False,
    )
    objective = score_sales_response(
        content=final_content,
        required_phrases=case.required_phrases,
        forbidden_phrases=case.forbidden_phrases,
        expected_tools=case.expected_tools,
        observed_tools=observed_tools,
        expected_language=case.expected_language,
        allowed_numbers=extract_numeric_tokens(grounding_evidence),
        critical_required_phrases=case.critical_required_phrases,
    )
    tool_args_ok = all(
        item["parse_error"] is None and item["correct"] == item["total"]
        for item in tool_argument_results
    )
    objective["tool_arguments_ok"] = tool_args_ok
    objective["passed"] = objective["passed"] and tool_args_ok
    objective["hard_gate_passed"] = objective["hard_gate_passed"] and tool_args_ok
    return {
        "suite": "sales",
        "case_id": case.case_id,
        "category": case.category,
        "model": model,
        "repetition": repetition,
        "success": bool(final_content),
        "first_pass_success": bool(all_attempts and all_attempts[0].ok),
        "retry_used": retry_was_used(attempt_counts_by_round),
        "latency_ms": round(sum(item.elapsed_ms for item in all_attempts), 3),
        "provider_attempts": [asdict(item) for item in all_attempts],
        "usage": _usage(all_attempts),
        "accounting": summarize_attempt_accounting(all_attempts),
        "request_parameters": request_parameters,
        "final_content": final_content,
        "observed_tools": observed_tools,
        "tool_arguments": tool_argument_results,
        "objective": objective,
    }


async def _run_system_case(
    client: httpx.AsyncClient,
    *,
    model: str,
    case: Any,
    repetition: int,
    cost_budget: RequestCostBudget | None = None,
) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": case.system_prompt},
        {"role": "user", "content": case.user_prompt},
    ]
    payload = build_base_payload(
        model=model,
        messages=messages,
        max_tokens=900,
        reasoning_enabled=False,
    )
    if case.tools:
        payload["tools"] = list(case.tools)
        payload["tool_choice"] = "auto"
    else:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": case.case_id.replace("-", "_"),
                "strict": True,
                "schema": case.schema,
            },
        }
    request_parameters = _request_parameter_evidence(payload)
    attempts = await _request_with_retry(
        client,
        payload=payload,
        timeout_seconds=45.0,
        before_request=(
            None
            if cost_budget is None
            else lambda: cost_budget.reserve_request(model, payload)
        ),
    )
    message = _choice_message(attempts)
    content = str(message.get("content") or "").strip() if message else ""
    tool_calls = _extract_tool_calls(message)

    parse_ok = False
    schema_errors: list[str] = []
    semantic_correct = 0
    semantic_total = len(case.expected_fields)
    semantic_mismatches: list[str] = []
    parsed: Any = None
    observed_tool = ""
    tool_parse_error: str | None = None

    if case.tools:
        if tool_calls:
            observed_tool, parsed, tool_parse_error = _parse_tool_arguments(
                tool_calls[0]
            )
            parse_ok = tool_parse_error is None
        else:
            tool_parse_error = "no tool call"
        semantic_correct, semantic_total, semantic_mismatches = (
            score_expected_fields(parsed, case.expected_fields)
            if parse_ok
            else (0, len(case.expected_fields), ["$: tool arguments unavailable"])
        )
        if observed_tool != case.expected_tool:
            semantic_mismatches.append(
                f"$.tool: expected {case.expected_tool!r}, got {observed_tool!r}"
            )
            semantic_total += 1
        else:
            semantic_correct += 1
            semantic_total += 1
    else:
        try:
            parsed = parse_json_content(content)
            parse_ok = True
            schema_errors = validate_json_schema(parsed, case.schema)
        except ValueError as exc:
            schema_errors = [str(exc)]
        if parse_ok:
            semantic_correct, semantic_total, semantic_mismatches = (
                score_expected_fields(parsed, case.expected_fields)
            )

    critical_fields_ok = True
    if case.critical_fields:
        critical_expected = {
            field: case.expected_fields[field] for field in case.critical_fields
        }
        critical_correct, critical_total, _critical_mismatches = (
            score_expected_fields(parsed, critical_expected)
            if parse_ok
            else (0, len(critical_expected), ["$: structured result unavailable"])
        )
        critical_fields_ok = critical_correct == critical_total

    return {
        "suite": "system",
        "case_id": case.case_id,
        "category": case.category,
        "model": model,
        "repetition": repetition,
        "success": bool(message),
        "first_pass_success": bool(attempts and attempts[0].ok),
        "retry_used": len(attempts) > 1,
        "reasoning_requested": False,
        "reasoning_observed": reasoning_was_observed(attempts),
        "latency_ms": round(sum(item.elapsed_ms for item in attempts), 3),
        "provider_attempts": [asdict(item) for item in attempts],
        "usage": _usage(attempts),
        "accounting": summarize_attempt_accounting(attempts),
        "request_parameters": [request_parameters],
        "content": content,
        "parsed": parsed,
        "json_parse_ok": parse_ok,
        "schema_ok": parse_ok and not schema_errors,
        "schema_errors": schema_errors,
        "semantic_correct": semantic_correct,
        "semantic_total": semantic_total,
        "semantic_mismatches": semantic_mismatches,
        "critical_fields_ok": critical_fields_ok,
        "pii_leakage": contains_pii_leakage(content, case.user_prompt),
        "observed_tool": observed_tool,
        "expected_tool": case.expected_tool,
        "tool_parse_error": tool_parse_error,
    }


async def _fetch_catalog(
    client: httpx.AsyncClient,
    models: Sequence[str],
) -> dict[str, Any]:
    response = await client.get("/models", timeout=30.0)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", [])
    by_id = {
        item.get("id"): item
        for item in data
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    missing = [model for model in models if model not in by_id]
    if missing:
        raise RuntimeError(f"Models missing from OpenRouter catalog: {missing}")
    return {model: by_id[model] for model in models}


def assert_catalog_capabilities(
    catalog: Mapping[str, Mapping[str, Any]],
    suites: Sequence[str],
    *,
    profile: str = ORIGINAL_PROFILE,
) -> None:
    """Fail before paid calls when a candidate lacks a required API feature."""

    requirements: dict[str, set[str]] = {}
    if "sales" in suites:
        for model in models_for_profile(profile, "sales"):
            requirements.setdefault(model, set()).update({"tools", "tool_choice"})
    if "system" in suites:
        for model in models_for_profile(profile, "system"):
            requirements.setdefault(model, set()).update(
                {
                    "tools",
                    "tool_choice",
                    "response_format",
                    "reasoning",
                    "structured_outputs",
                }
            )
    if profile in _HARD_PROFILES:
        for required in requirements.values():
            required.update({"max_tokens", "reasoning"})
    failures: list[str] = []
    for model, required in requirements.items():
        entry = catalog.get(model, {})
        supported_raw = entry.get("supported_parameters", [])
        supported = (
            {str(item) for item in supported_raw}
            if isinstance(supported_raw, list)
            else set()
        )
        missing = sorted(required - supported)
        if missing:
            failures.append(f"{model}: missing {', '.join(missing)}")
    if failures:
        raise RuntimeError(
            "OpenRouter catalog capability preflight failed: " + "; ".join(failures)
        )


def _build_jobs(
    *,
    suite: str,
    repetitions: int,
    seed: int,
    profile: str = ORIGINAL_PROFILE,
) -> list[tuple[str, Any, int]]:
    models = models_for_profile(profile, suite)
    cases = cases_for_profile(profile, suite)
    jobs = [
        (model, case, repetition)
        for case in cases
        for repetition in range(1, repetitions + 1)
        for model in models
    ]
    random.Random(f"{seed}:{suite}").shuffle(jobs)
    return jobs


def select_differentiating_system_cases(
    rows: Sequence[Mapping[str, Any]],
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    """Choose fixtures with the largest deterministic semantic score spread."""

    by_case: dict[str, list[float]] = {}
    for row in rows:
        total = int(row.get("semantic_total", 0))
        score = 0.0 if total <= 0 else int(row.get("semantic_correct", 0)) / total
        by_case.setdefault(str(row["case_id"]), []).append(score)
    ranked = sorted(
        by_case,
        key=lambda case_id: (
            -(max(by_case[case_id]) - min(by_case[case_id])),
            case_id,
        ),
    )
    return tuple(ranked[:limit])


def _round_zero_survivors(
    suite: str,
    rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    by_model: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_model.setdefault(str(row["model"]), []).append(row)
    survivors: list[str] = []
    for model, model_rows in by_model.items():
        if suite == "sales":
            passed = all(
                bool(row.get("objective", {}).get("hard_gate_passed"))
                for row in model_rows
            )
        elif suite == "system":
            schema_passed = all(
                bool(row.get("success", row.get("first_pass_success")))
                and bool(row.get("json_parse_ok"))
                and bool(row.get("schema_ok"))
                and bool(row.get("critical_fields_ok", True))
                and not bool(row.get("pii_leakage", False))
                for row in model_rows
            )
            correct = sum(int(row.get("semantic_correct", 0)) for row in model_rows)
            total = sum(int(row.get("semantic_total", 0)) for row in model_rows)
            passed = schema_passed and total > 0 and correct / total >= 0.95
        else:
            raise ValueError(f"Unknown suite: {suite}")
        if passed:
            survivors.append(model)
    return tuple(sorted(survivors))


def build_survivor_jobs(
    *,
    suite: str,
    profile: str,
    round_zero_rows: Sequence[Mapping[str, Any]],
    seed: int,
) -> list[tuple[str, Any, int]]:
    """Build repetitions two and three only for round-zero survivors."""

    survivors = _round_zero_survivors(suite, round_zero_rows)
    cases = cases_for_profile(profile, suite)
    if profile == BACKGROUND_HARD_PROFILE and suite == "system":
        differentiating = set(
            select_differentiating_system_cases(round_zero_rows, limit=3)
        )
        cases = tuple(case for case in cases if case.case_id in differentiating)
    jobs = [
        (model, case, repetition)
        for case in cases
        for repetition in (2, 3)
        for model in survivors
    ]
    random.Random(f"{seed}:{suite}:survivors").shuffle(jobs)
    return jobs


def _build_blind_files(
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    profile: str = ORIGINAL_PROFILE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases_by_id = {case.case_id: case for case in cases_for_profile(profile, "sales")}
    grouped: dict[tuple[str, int], dict[str, str]] = {}
    for row in rows:
        if row.get("suite") != "sales":
            continue
        key = (str(row["case_id"]), int(row["repetition"]))
        grouped.setdefault(key, {})[str(row["model"])] = str(row["final_content"])

    blind_rows: list[dict[str, Any]] = []
    reveal_rows: list[dict[str, Any]] = []
    for assignment_index, ((case_id, repetition), candidates) in enumerate(
        sorted(grouped.items())
    ):
        if len(candidates) < 2:
            continue
        pair = build_blind_pair(
            case_id=case_id,
            repetition=repetition,
            candidates=candidates,
            seed=seed,
            assignment_index=assignment_index,
        )
        blind_rows.append(
            {
                "case_id": pair["case_id"],
                "repetition": pair["repetition"],
                "scenario": {
                    "system_prompt": cases_by_id[case_id].system_prompt,
                    "conversation": list(cases_by_id[case_id].conversation),
                    "user_prompt": cases_by_id[case_id].user_prompt,
                    "rubric": {
                        "dimensions": sorted(_BLIND_REVIEW_DIMENSIONS),
                        "scale": "1=poor, 3=adequate, 5=excellent",
                        "instruction": (
                            "Score every answer independently using only the "
                            "synthetic scenario. Mark critical_failure only for "
                            "an invented commercial fact, wrong action/tool "
                            "outcome, wrong required language, or materially "
                            "unsafe advice. Do not infer model identity."
                        ),
                        "answer_contract": {
                            "scores": {
                                dimension: "integer 1..5"
                                for dimension in sorted(_BLIND_REVIEW_DIMENSIONS)
                            },
                            "critical_failure": "boolean",
                            "critical_failure_reason": "string; required when true",
                            "score_out_of_30": "number 0..30",
                            "applicable_rules": "sorted string array",
                        },
                    },
                },
                "answers": pair["answers"],
            }
        )
        reveal_rows.append(
            {
                "case_id": pair["case_id"],
                "repetition": pair["repetition"],
                "reveal": pair["reveal"],
            }
        )
    return blind_rows, reveal_rows


def score_battle(
    output_dir: Path,
    blind_scores_path: Path | None,
) -> dict[str, Any]:
    """Turn raw evidence plus completed blind scores into route decisions."""

    manifest = _read_json_object(output_dir / "run_manifest.json")
    profile = str(manifest["profile"])
    if profile == BACKGROUND_HARD_PROFILE:
        system_rows = rescore_system_rows(
            _read_jsonl(output_dir / "system_results.jsonl"),
            profile=profile,
        )
        decision = select_hard_profile_winner(profile, system_rows)
        result = {
            "openrouter_model_main": None,
            "openrouter_model_fast": asdict(decision),
            "eval_disagreements": [],
            "production_changed": False,
        }
        _write_jsonl(output_dir / "system_scored_results.jsonl", system_rows)
        _write_json(output_dir / "model_selection.json", result)
        return result

    if blind_scores_path is None:
        raise ValueError("Sales scoring requires a completed blind review file")
    sales_rows = rescore_sales_rows(
        _read_jsonl(output_dir / "sales_results.jsonl"),
        profile=profile,
    )
    blind_scores = parse_json_content(blind_scores_path.read_text(encoding="utf-8"))
    if not isinstance(blind_scores, list):
        raise ValueError("Blind scores must be a JSON array")
    blind_scores = normalize_blind_reviews(blind_scores)
    if profile == CORE_HARD_PROFILE:
        seal_path = output_dir / "sales_blind_scores.seal.json"
        seal = _read_json_object(seal_path)
        verify_blind_scores_seal(blind_scores, str(seal.get("sha256", "")))
        _blind_rows, blind_key = _build_blind_files(
            sales_rows,
            seed=int(manifest["seed"]),
            profile=profile,
        )
        commitment = _read_json_object(output_dir / "sales_blind_key.commitment.json")
        verify_blind_scores_seal(
            blind_key,
            str(commitment.get("sha256", "")),
        )
        _write_json(output_dir / "sales_blind_key.json", blind_key)
    else:
        blind_key = json.loads(
            (output_dir / "sales_blind_key.json").read_text(encoding="utf-8")
        )
        if not isinstance(blind_key, list):
            raise ValueError("Blind key must be a JSON array")
    _write_json(output_dir / "sales_blind_scores.json", blind_scores)
    _write_jsonl(output_dir / "sales_scored_results.jsonl", sales_rows)
    _write_json(output_dir / "sales_scored_aggregate.json", aggregate_rows(sales_rows))
    blind_quality, blind_hard_gates = evaluate_blind_reviews(
        blind_scores,
        blind_key,
    )

    if profile == CORE_HARD_PROFILE:
        for row in sales_rows:
            model = str(row["model"])
            if not blind_hard_gates.get(model, False):
                row["objective"]["hard_gate_passed"] = False
        disagreements = detect_evaluator_disagreements(
            [
                {
                    "case_id": row["case_id"],
                    "repetition": row["repetition"],
                    "model": row["model"],
                    "score_out_of_30": row["objective"]["score_out_of_30"],
                    "applicable_rules": row["objective"]["applicable_rules"],
                }
                for row in sales_rows
                if any(
                    key_row["case_id"] == row["case_id"]
                    and key_row["repetition"] == row["repetition"]
                    for key_row in blind_key
                )
            ],
            blind_scores,
            blind_key,
        )
        decision = (
            WinnerDecision(
                outcome="blocked",
                winner=None,
                reason="EVAL_DISAGREEMENT must be resolved before reveal acceptance.",
            )
            if disagreements
            else select_hard_profile_winner(profile, sales_rows)
        )
        result = {
            "openrouter_model_main": asdict(decision),
            "openrouter_model_fast": None,
            "blind_quality": blind_quality,
            "eval_disagreements": disagreements,
            "production_changed": False,
        }
        _write_json(output_dir / "model_selection.json", result)
        return result

    system_rows = rescore_system_rows(_read_jsonl(output_dir / "system_results.jsonl"))
    _write_jsonl(output_dir / "system_scored_results.jsonl", system_rows)
    _write_json(
        output_dir / "system_scored_aggregate.json",
        aggregate_rows(system_rows),
    )

    sales_metrics, sales_details = candidate_metrics_from_evidence(
        suite="sales",
        rows=sales_rows,
        blind_quality=blind_quality,
        blind_hard_gates=blind_hard_gates,
    )
    system_metrics, system_details = candidate_metrics_from_evidence(
        suite="system",
        rows=system_rows,
    )
    result = {
        "sales": {
            "candidates": [asdict(metric) for metric in sales_metrics],
            "details": sales_details,
            "decision": asdict(select_winner(sales_metrics)),
        },
        "system": {
            "candidates": [asdict(metric) for metric in system_metrics],
            "details": system_details,
            "decision": asdict(select_winner(system_metrics)),
        },
        "production_changed": False,
    }
    _write_json(output_dir / "route_decisions.json", result)
    return result


def rescore_sales_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    profile: str = ORIGINAL_PROFILE,
) -> list[dict[str, Any]]:
    """Reapply the current deterministic scorer without new provider calls."""

    cases_by_id = {case.case_id: case for case in cases_for_profile(profile, "sales")}
    rescored: list[dict[str, Any]] = []
    for source_row in rows:
        row = dict(source_row)
        case = cases_by_id[str(row["case_id"])]
        grounding_evidence = json.dumps(
            {
                "system_prompt": case.system_prompt,
                "conversation": case.conversation,
                "user_prompt": case.user_prompt,
                "tool_results": case.tool_results,
            },
            ensure_ascii=False,
        )
        objective = score_sales_response(
            content=str(row["final_content"]),
            required_phrases=case.required_phrases,
            forbidden_phrases=case.forbidden_phrases,
            expected_tools=case.expected_tools,
            observed_tools=[str(item) for item in row["observed_tools"]],
            expected_language=case.expected_language,
            allowed_numbers=extract_numeric_tokens(grounding_evidence),
            critical_required_phrases=case.critical_required_phrases,
        )
        tool_arguments = row.get("tool_arguments", [])
        tool_args_ok = all(
            item["parse_error"] is None and item["correct"] == item["total"]
            for item in tool_arguments
        )
        objective["tool_arguments_ok"] = tool_args_ok
        objective["passed"] = objective["passed"] and tool_args_ok
        objective["hard_gate_passed"] = objective["hard_gate_passed"] and tool_args_ok
        row["objective"] = objective
        rescored.append(row)
    return rescored


def rescore_system_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    profile: str = ORIGINAL_PROFILE,
) -> list[dict[str, Any]]:
    """Reapply current semantic normalization without new provider calls."""

    cases_by_id = {case.case_id: case for case in cases_for_profile(profile, "system")}
    rescored: list[dict[str, Any]] = []
    for source_row in rows:
        row = dict(source_row)
        case = cases_by_id[str(row["case_id"])]
        parsed = row.get("parsed")
        parse_ok = bool(row.get("json_parse_ok"))
        if parse_ok:
            correct, total, mismatches = score_expected_fields(
                parsed,
                case.expected_fields,
            )
        else:
            correct = 0
            total = len(case.expected_fields)
            unavailable = (
                "tool arguments unavailable"
                if case.tools
                else "structured result unavailable"
            )
            mismatches = [f"$: {unavailable}"]

        if case.tools:
            observed_tool = str(row.get("observed_tool") or "")
            if observed_tool != case.expected_tool:
                mismatches.append(
                    f"$.tool: expected {case.expected_tool!r}, got {observed_tool!r}"
                )
            else:
                correct += 1
            total += 1

        row["semantic_correct"] = correct
        row["semantic_total"] = total
        row["semantic_mismatches"] = mismatches
        if case.critical_fields:
            critical_expected = {
                field: case.expected_fields[field] for field in case.critical_fields
            }
            critical_correct, critical_total, _critical_mismatches = (
                score_expected_fields(parsed, critical_expected)
                if parse_ok
                else (0, len(critical_expected), [])
            )
            row["critical_fields_ok"] = critical_correct == critical_total
        else:
            row["critical_fields_ok"] = True
        rescored.append(row)
    return rescored


def aggregate_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    aggregate: dict[str, Any] = {}
    for model in sorted({str(row["model"]) for row in rows}):
        model_rows = [row for row in rows if row["model"] == model]
        latencies = [float(row["latency_ms"]) for row in model_rows]
        first_pass = sum(bool(row["first_pass_success"]) for row in model_rows)
        entry: dict[str, Any] = {
            "model": model,
            "runs": len(model_rows),
            "first_pass_reliability": first_pass / len(model_rows),
            "retry_rate": sum(bool(row["retry_used"]) for row in model_rows)
            / len(model_rows),
            "latency_ms": {
                "mean": statistics.fmean(latencies),
                "p50": percentile(latencies, 0.5),
                "p95": percentile(latencies, 0.95),
                "max": max(latencies),
            },
        }
        if model_rows[0]["suite"] == "sales":
            entry["objective_correctness"] = statistics.fmean(
                int(row["objective"]["checks_passed"])
                / int(row["objective"]["checks_total"])
                for row in model_rows
            )
            entry["case_pass_rate"] = sum(
                bool(row["objective"]["passed"]) for row in model_rows
            ) / len(model_rows)
        else:
            structured_rows = [
                row for row in model_rows if row["category"] != "tool_arguments"
            ]
            semantic_correct = sum(int(row["semantic_correct"]) for row in model_rows)
            semantic_total = sum(int(row["semantic_total"]) for row in model_rows)
            entry["json_schema_first_pass"] = sum(
                bool(
                    row["first_pass_success"]
                    and row["json_parse_ok"]
                    and row["schema_ok"]
                )
                for row in structured_rows
            ) / len(structured_rows)
            entry["semantic_accuracy"] = semantic_correct / semantic_total
            entry["tool_case_pass_rate"] = sum(
                bool(
                    row["category"] == "tool_arguments"
                    and not row["semantic_mismatches"]
                    and row["tool_parse_error"] is None
                )
                for row in model_rows
            ) / max(
                1,
                sum(row["category"] == "tool_arguments" for row in model_rows),
            )
            entry["reasoning_disable_honored"] = sum(
                not bool(row.get("reasoning_observed", False)) for row in model_rows
            ) / len(model_rows)
        aggregate[model] = entry
    return aggregate


def candidate_metrics_from_evidence(
    *,
    suite: str,
    rows: Sequence[Mapping[str, Any]],
    blind_quality: Mapping[str, float] | None = None,
    blind_hard_gates: Mapping[str, bool] | None = None,
) -> tuple[list[CandidateMetrics], dict[str, Any]]:
    """Apply the accepted weights and hard gates to raw run evidence."""

    models = sorted({str(row["model"]) for row in rows})
    if len(models) < 2:
        raise ValueError("Candidate scoring requires evidence for at least two models")
    aggregates = aggregate_rows(rows)
    fastest_p95 = min(float(aggregates[model]["latency_ms"]["p95"]) for model in models)
    metrics: list[CandidateMetrics] = []
    details: dict[str, Any] = {}

    for model in models:
        model_rows = [row for row in rows if row["model"] == model]
        aggregate = aggregates[model]
        reliability = float(aggregate["first_pass_reliability"])
        p95_ms = float(aggregate["latency_ms"]["p95"])
        latency_score = fastest_p95 / p95_ms if p95_ms else 1.0

        if suite == "sales":
            if blind_quality is None or model not in blind_quality:
                raise ValueError(f"Missing blinded sales quality for {model}")
            objective_correctness = float(aggregate["objective_correctness"])
            tool_route = statistics.fmean(
                (
                    float(bool(row["objective"]["tool_sequence_ok"]))
                    + float(bool(row["objective"]["tool_arguments_ok"]))
                )
                / 2
                for row in model_rows
            )
            quality = float(blind_quality[model])
            hard_gates = {
                "zero_critical_failures": all(
                    bool(row["objective"]["hard_gate_passed"]) for row in model_rows
                ),
                "zero_blind_review_critical_failures": (
                    True
                    if blind_hard_gates is None
                    else bool(blind_hard_gates.get(model, False))
                ),
            }
            weighted = 100 * (
                0.45 * objective_correctness
                + 0.25 * quality
                + 0.15 * tool_route
                + 0.15 * latency_score
            )
            detail = {
                "objective_correctness": objective_correctness,
                "blind_quality": quality,
                "tool_route_score": tool_route,
                "latency_score": latency_score,
                "hard_gates": hard_gates,
            }
        elif suite == "system":
            structured_rows = [
                row for row in model_rows if row["category"] != "tool_arguments"
            ]
            tool_rows = [
                row for row in model_rows if row["category"] == "tool_arguments"
            ]
            json_schema_rate = sum(
                bool(
                    row["first_pass_success"]
                    and row["json_parse_ok"]
                    and row["schema_ok"]
                )
                for row in structured_rows
            ) / len(structured_rows)
            semantic_correct = sum(int(row["semantic_correct"]) for row in model_rows)
            semantic_total = sum(int(row["semantic_total"]) for row in model_rows)
            semantic_accuracy = semantic_correct / semantic_total
            tool_quality = sum(
                bool(not row["semantic_mismatches"] and row["tool_parse_error"] is None)
                for row in tool_rows
            ) / len(tool_rows)
            case_groups: dict[str, list[Mapping[str, Any]]] = {}
            for row in model_rows:
                case_groups.setdefault(str(row["case_id"]), []).append(row)
            consistently_failing = [
                case_id
                for case_id, case_rows in case_groups.items()
                if all(
                    not row["first_pass_success"] or int(row["semantic_correct"]) == 0
                    for row in case_rows
                )
            ]
            hard_gates = {
                "no_consistently_failing_case": not consistently_failing,
                "no_critical_tool_argument_error": tool_quality == 1.0,
                "json_schema_at_least_97_5": json_schema_rate >= 0.975,
                "semantic_at_least_95": semantic_accuracy >= 0.95,
            }
            correctness = (json_schema_rate + semantic_accuracy) / 2
            weighted = 100 * (
                0.50 * correctness
                + 0.20 * reliability
                + 0.15 * tool_quality
                + 0.15 * latency_score
            )
            detail = {
                "json_schema_first_pass": json_schema_rate,
                "semantic_accuracy": semantic_accuracy,
                "reliability": reliability,
                "tool_quality": tool_quality,
                "reasoning_disable_honored": float(
                    aggregate["reasoning_disable_honored"]
                ),
                "latency_score": latency_score,
                "consistently_failing_cases": consistently_failing,
                "hard_gates": hard_gates,
            }
        else:
            raise ValueError(f"Unknown suite: {suite}")

        metric = CandidateMetrics(
            model=model,
            weighted_score=round(weighted, 3),
            hard_gates_passed=all(hard_gates.values()),
            reliability=reliability,
            p95_ms=p95_ms,
        )
        metrics.append(metric)
        detail["weighted_score"] = metric.weighted_score
        detail["hard_gates_passed"] = metric.hard_gates_passed
        detail["p95_ms"] = p95_ms
        details[model] = detail
    return metrics, details


async def run_battle(
    *,
    suites: Sequence[str],
    output_dir: Path,
    repetitions: int,
    seed: int,
    profile: str = ORIGINAL_PROFILE,
) -> None:
    """Execute selected suites sequentially and preserve durable evidence."""

    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    if profile in _HARD_PROFILES and repetitions != 3:
        raise ValueError("Hard profiles require exactly three staged repetitions")
    from scripts.model_battle_cases import validate_case_sets

    validate_case_sets()
    manifest_path = output_dir / "run_manifest.json"
    existing_manifest = (
        _read_json_object(manifest_path) if manifest_path.exists() else None
    )
    if existing_manifest is not None:
        assert_existing_run_evidence(output_dir, existing_manifest)
    merged_manifest = merge_run_manifest(
        existing_manifest,
        suites=suites,
        profile=profile,
        repetitions=repetitions,
        seed=seed,
    )
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://noor.starec.ai",
        "X-Title": "Noor Model Battle",
    }
    all_models = sorted(
        {model for suite in suites for model in models_for_profile(profile, suite)}
    )
    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url.rstrip("/"),
        headers=headers,
    ) as client:
        catalog = await _fetch_catalog(client, all_models)
        assert_catalog_capabilities(catalog, suites, profile=profile)
        catalog_path = output_dir / "model_catalog.json"
        existing_catalog = (
            _read_json_object(catalog_path) if catalog_path.exists() else {}
        )
        _write_json(catalog_path, {**existing_catalog, **catalog})
        for suite in suites:
            rows: list[dict[str, Any]] = []
            estimated_costs = estimate_model_costs(
                catalog,
                profile=profile,
                suite=suite,
            )
            over_budget = {
                model: estimate
                for model, estimate in estimated_costs.items()
                if estimate > 1.0
            }
            if over_budget:
                raise RuntimeError(
                    "Estimated per-model cost exceeds USD 1: "
                    + ", ".join(
                        f"{model}=${estimate:.6f}"
                        for model, estimate in sorted(over_budget.items())
                    )
                )
            _write_json(
                output_dir / f"{suite}_cost_preflight.json",
                {
                    "estimated_costs_usd": estimated_costs,
                    "caps_usd": {
                        model: min(1.0, estimate * 1.25)
                        for model, estimate in estimated_costs.items()
                    },
                },
            )
            cost_budget = RequestCostBudget(
                catalog=catalog,
                estimated_costs=estimated_costs,
            )
            round_zero_jobs = _build_jobs(
                suite=suite,
                repetitions=1 if profile in _HARD_PROFILES else repetitions,
                seed=seed,
                profile=profile,
            )
            jobs = list(round_zero_jobs)
            for index, (model, case, repetition) in enumerate(
                round_zero_jobs,
                start=1,
            ):
                print(
                    f"[{suite} round-0 {index}/{len(round_zero_jobs)}] "
                    f"{case.case_id} rep={repetition} model={model}",
                    flush=True,
                )
                if suite == "sales":
                    row = await _run_sales_case(
                        client,
                        model=model,
                        case=case,
                        repetition=repetition,
                        cost_budget=cost_budget,
                    )
                else:
                    row = await _run_system_case(
                        client,
                        model=model,
                        case=case,
                        repetition=repetition,
                        cost_budget=cost_budget,
                    )
                rows.append(row)
                _write_jsonl(output_dir / f"{suite}_results.jsonl", rows)
                enforce_model_cost_caps(rows, estimated_costs)

            if profile in _HARD_PROFILES:
                survivor_jobs = build_survivor_jobs(
                    suite=suite,
                    profile=profile,
                    round_zero_rows=rows,
                    seed=seed,
                )
                jobs.extend(survivor_jobs)
                for index, (model, case, repetition) in enumerate(
                    survivor_jobs,
                    start=1,
                ):
                    print(
                        f"[{suite} survivors {index}/{len(survivor_jobs)}] "
                        f"{case.case_id} rep={repetition} model={model}",
                        flush=True,
                    )
                    if suite == "sales":
                        row = await _run_sales_case(
                            client,
                            model=model,
                            case=case,
                            repetition=repetition,
                            cost_budget=cost_budget,
                        )
                    else:
                        row = await _run_system_case(
                            client,
                            model=model,
                            case=case,
                            repetition=repetition,
                            cost_budget=cost_budget,
                        )
                    rows.append(row)
                    _write_jsonl(output_dir / f"{suite}_results.jsonl", rows)
                    enforce_model_cost_caps(rows, estimated_costs)

            _write_json(
                output_dir / f"{suite}_aggregate.json",
                aggregate_rows(rows),
            )
            if suite == "sales":
                blind, reveal = _build_blind_files(
                    rows,
                    seed=seed,
                    profile=profile,
                )
                _write_json(output_dir / "sales_blind_review.json", blind)
                if profile == CORE_HARD_PROFILE:
                    _write_json(
                        output_dir / "sales_blind_key.commitment.json",
                        {"sha256": blind_scores_digest(reveal)},
                    )
                else:
                    _write_json(output_dir / "sales_blind_key.json", reveal)
            merged_manifest.setdefault("job_matrix", {})[suite] = [
                {
                    "model": model,
                    "case_id": case.case_id,
                    "repetition": repetition,
                }
                for model, case, repetition in jobs
            ]

    _write_json(manifest_path, merged_manifest)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=("sales", "system", "all"),
        default="all",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".codex/stages/tj-0j7o/results"),
    )
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--profile",
        choices=tuple(MODEL_PROFILES),
        default=ORIGINAL_PROFILE,
    )
    parser.add_argument(
        "--score-only",
        action="store_true",
        help="Score existing raw results using a completed blind review file.",
    )
    parser.add_argument(
        "--blind-scores",
        type=Path,
        help="Completed blinded sales rubric JSON used with --score-only.",
    )
    parser.add_argument(
        "--seal-blind-scores",
        action="store_true",
        help="Commit completed blind scores before the reveal/scoring step.",
    )
    parser.add_argument("--combine-core-dir", type=Path)
    parser.add_argument("--combine-background-dir", type=Path)
    parser.add_argument("--combined-output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    combine_args = (
        args.combine_core_dir,
        args.combine_background_dir,
        args.combined_output,
    )
    if any(value is not None for value in combine_args):
        if any(value is None for value in combine_args):
            raise SystemExit(
                "Combining selections requires --combine-core-dir, "
                "--combine-background-dir, and --combined-output"
            )
        assert args.combine_core_dir is not None
        assert args.combine_background_dir is not None
        assert args.combined_output is not None
        combine_hard_profile_selections(
            args.combine_core_dir,
            args.combine_background_dir,
            args.combined_output,
        )
        return
    if args.seal_blind_scores:
        if args.blind_scores is None:
            raise SystemExit("--seal-blind-scores requires --blind-scores")
        reviews = parse_json_content(args.blind_scores.read_text(encoding="utf-8"))
        if not isinstance(reviews, list):
            raise SystemExit("--blind-scores must contain a JSON array")
        reviews = normalize_blind_reviews(reviews)
        _write_json(
            args.output_dir / "sales_blind_scores.seal.json",
            {"sha256": blind_scores_digest(reviews)},
        )
        return
    if args.score_only:
        score_battle(args.output_dir, args.blind_scores)
        return
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be at least 1")
    if args.suite == "all" and args.profile == CORE_HARD_PROFILE:
        suites = ("sales",)
    elif args.suite == "all" and args.profile == BACKGROUND_HARD_PROFILE:
        suites = ("system",)
    else:
        suites = ("sales", "system") if args.suite == "all" else (args.suite,)
    asyncio.run(
        run_battle(
            suites=suites,
            output_dir=args.output_dir,
            repetitions=args.repetitions,
            seed=args.seed,
            profile=args.profile,
        )
    )


if __name__ == "__main__":
    main()
