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
import os
import random
import re
import secrets
import statistics
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import httpx
from scripts.model_battle_rubric import (
    RUBRIC_VERSION,
    evaluate_claim_reviews,
    is_claim_review,
)

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
_PROVIDER_CHAIN_LIMIT = 3
# An fp4-class serving answers as a measurably different artefact than the
# weights its publisher hosts. Comparing one candidate's fp4 serving against
# another's native precision would measure the host, not the model.
_EXCLUDED_QUANTIZATIONS = {"fp4", "int4", "q4", "int3", "q3", "q2"}

_JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
_PATH_PART_RE = re.compile(r"([^[.\]]+)|\[(\d+)\]")
_NUMBER_RE = re.compile(r"(?<![\w-])\d[\d,]*(?:\.\d+)?%?")
_ISO_TIMESTAMP_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?"
)
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


def _finite_number(value: Any, field: str, *, nonnegative: bool = True) -> float:
    if isinstance(value, bool):
        raise RuntimeError(f"{field} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{field} must be a finite number") from exc
    if not math.isfinite(number) or (nonnegative and number < 0):
        qualifier = "finite non-negative" if nonnegative else "finite"
        raise RuntimeError(f"{field} must be a {qualifier} number")
    return number


def conservative_input_token_bound(payload: Mapping[str, Any]) -> int:
    """Bound input tokens by the complete billable request's UTF-8 byte count."""

    try:
        encoded = json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Request payload must be finite JSON") from exc
    # Every token contains at least one byte, so bytes is conservative for any
    # UTF-8 tokenizer while avoiding an unproved characters/4 approximation.
    return max(1, len(encoded))


DEFAULT_PER_MODEL_CAP_USD = 1.0
_JSON_RESPONSE_FORMAT_NOTICE = "Answer with a single json object and nothing else."


class CostCapExhausted(RuntimeError):
    """A candidate reached its own limit; the round continues without it."""

    def __init__(
        self,
        model: str,
        *,
        committed: float,
        cap: float,
        limit: str = "cost cap",
    ) -> None:
        super().__init__(
            f"Model {limit} reached before provider request: {model} "
            f"committed ${committed:.6f}, limit ${cap:.6f}"
        )
        self.model = model
        self.committed = committed
        self.cap = cap
        self.limit = limit


def resolve_model_caps(
    estimated_costs: Mapping[str, float],
    *,
    policy: str = "fixed",
    default_cap: float = DEFAULT_PER_MODEL_CAP_USD,
    overrides: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Resolve one auditable cap per model before any paid request.

    ``fixed`` keeps the accepted flat cap. ``cover-estimate`` raises a cap only
    as far as that model's own conservative worst-case estimate, which is what
    lets every candidate finish the complete matrix instead of stopping early.
    """

    if policy not in {"fixed", "cover-estimate"}:
        raise ValueError(f"Unknown cap policy: {policy}")
    default_cap = _finite_number(default_cap, "Default per-model cap")
    resolved: dict[str, float] = {}
    for model, estimate in estimated_costs.items():
        cap = default_cap
        if policy == "cover-estimate":
            finite_estimate = _finite_number(estimate, f"Estimate for {model}")
            cap = max(cap, math.ceil(finite_estimate * 100) / 100)
        resolved[model] = cap
    for model, override in (overrides or {}).items():
        if model not in resolved:
            raise ValueError(f"Cap override names an unconfigured model: {model}")
        resolved[model] = _finite_number(override, f"Cap override for {model}")
    return resolved


class RequestCostBudget:
    """Reserve each request, then replace it with provider-reported cost."""

    def __init__(
        self,
        *,
        catalog: Mapping[str, Mapping[str, Any]],
        estimated_costs: Mapping[str, float],
        caps: Mapping[str, float] | None = None,
    ) -> None:
        self._catalog = catalog
        resolved_caps = (
            resolve_model_caps(estimated_costs) if caps is None else dict(caps)
        )
        missing_caps = set(estimated_costs) - set(resolved_caps)
        if missing_caps:
            raise RuntimeError(
                "No cost cap configured for " + ", ".join(sorted(missing_caps))
            )
        self._caps = {
            model: _finite_number(resolved_caps[model], f"Cost cap for {model}")
            for model in estimated_costs
        }
        self._batch_allowances = {}
        self._pricing: dict[str, tuple[float, float]] = {}
        for model, estimate in estimated_costs.items():
            finite_estimate = _finite_number(estimate, f"Estimate for {model}")
            self._batch_allowances[model] = min(
                self._caps[model], finite_estimate * 1.25
            )
            pricing = catalog.get(model, {}).get("pricing", {})
            if not isinstance(pricing, Mapping):
                raise RuntimeError(f"Missing catalog pricing for {model}")
            try:
                self._pricing[model] = (
                    _finite_number(pricing["prompt"], f"Prompt price for {model}"),
                    _finite_number(
                        pricing["completion"], f"Completion price for {model}"
                    ),
                )
            except KeyError as exc:
                raise RuntimeError(f"Invalid catalog pricing for {model}") from exc
        self._pending = {model: 0.0 for model in estimated_costs}
        self._actual = {model: 0.0 for model in estimated_costs}
        self._own_available = dict(self._batch_allowances)
        self._carry_available = 0.0
        self._reservations: dict[str, list[tuple[float, float, float]]] = {
            model: [] for model in estimated_costs
        }
        self._finished: set[str] = set()

    @property
    def actual_spend(self) -> dict[str, float]:
        return {
            model: round(cost, 12) for model, cost in self._actual.items() if cost > 0
        }

    @property
    def caps(self) -> dict[str, float]:
        return dict(self._caps)

    def _require_active(self, model: str) -> None:
        if model not in self._batch_allowances:
            raise RuntimeError(f"No cost allowance configured for {model}")
        if model in self._finished:
            raise RuntimeError(f"Cost allowance for {model} is already finished")

    def reserve_request(self, model: str, payload: Mapping[str, Any]) -> float:
        self._require_active(model)
        prompt_price, completion_price = self._pricing[model]
        prompt_tokens = conservative_input_token_bound(payload)
        max_tokens = _finite_number(payload.get("max_tokens", 0), "Request max_tokens")
        worst_case = prompt_tokens * prompt_price + max_tokens * completion_price
        cap = self._caps.get(model)
        if cap is None:
            raise RuntimeError(f"No cost cap configured for {model}")
        committed = self._actual.get(model, 0.0) + self._pending.get(model, 0.0)
        if committed + worst_case > cap + 1e-12:
            raise CostCapExhausted(model, committed=committed, cap=cap)
        available = self._own_available[model] + self._carry_available
        if worst_case > available + 1e-12:
            raise CostCapExhausted(
                model,
                committed=committed,
                cap=available,
                limit="battle allowance",
            )
        own_used = min(worst_case, self._own_available[model])
        carry_used = worst_case - own_used
        self._own_available[model] -= own_used
        self._carry_available -= carry_used
        self._pending[model] += worst_case
        self._reservations[model].append((worst_case, own_used, carry_used))
        return worst_case

    def reconcile_request(
        self,
        model: str,
        reservation: float,
        *,
        actual_cost: float,
    ) -> None:
        actual_cost = _finite_number(actual_cost, "Provider-reported actual cost")
        reservation = _finite_number(reservation, "Cost reservation")
        reservations = self._reservations.get(model, [])
        match_index = next(
            (
                index
                for index, item in enumerate(reservations)
                if abs(item[0] - reservation) <= 1e-12
            ),
            None,
        )
        if match_index is None:
            raise RuntimeError(f"Unknown cost reservation for {model}")
        reserved, own_used, carry_used = reservations.pop(match_index)
        if actual_cost > reserved + 1e-12:
            raise RuntimeError(
                f"Provider-reported cost exceeded conservative reservation for {model}"
            )
        next_actual = self._actual.get(model, 0.0) + actual_cost
        if next_actual > self._caps.get(model, 0.0) + 1e-12:
            raise RuntimeError(
                f"Model cost cap exceeded after provider response: {model} "
                f"spent ${next_actual:.6f}, cap ${self._caps.get(model, 0.0):.6f}"
            )
        own_actual = min(actual_cost, own_used)
        carry_actual = actual_cost - own_actual
        self._own_available[model] += own_used - own_actual
        self._carry_available += carry_used - carry_actual
        self._pending[model] -= reserved
        self._actual[model] = next_actual

    def finish_candidate(self, model: str) -> None:
        """Release only a completed or eliminated candidate's unused allowance."""

        self._require_active(model)
        if self._pending[model] > 1e-12:
            raise RuntimeError(f"Cannot finish {model} with pending cost reservations")
        self._carry_available += self._own_available[model]
        self._own_available[model] = 0.0
        self._finished.add(model)


def parse_json_content(content: str) -> Any:
    """Parse a JSON response, accepting a single common Markdown fence."""

    candidate = content.strip()
    match = _JSON_FENCE_RE.fullmatch(candidate)
    if match:
        candidate = match.group(1).strip()
    try:
        return json.loads(
            candidate,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"Non-finite JSON number: {value}")
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        message = exc.msg if isinstance(exc, json.JSONDecodeError) else str(exc)
        raise ValueError(f"Response is not valid JSON: {message}") from exc


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
    candidates: Mapping[str, Any],
    seed: int,
    assignment_index: int | None = None,
    entropy: bytes | None = None,
) -> dict[str, Any]:
    """Build a cryptographically randomized anonymous group and reveal key."""

    if len(candidates) < 2:
        raise ValueError("Blinded review requires at least two candidates")
    if len(candidates) > 26:
        raise ValueError("Blinded review supports at most 26 candidates")
    del seed, assignment_index
    random_material = secrets.token_bytes(32) if entropy is None else entropy
    if len(random_material) < 16:
        raise ValueError("Blind permutation entropy must contain at least 16 bytes")
    model_names = sorted(
        candidates,
        key=lambda model: hashlib.sha256(
            random_material + b"\0" + model.encode("utf-8")
        ).digest(),
    )
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
        allow_nan=False,
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


def _paired_instrument_scores(
    evaluator_rows: Sequence[Mapping[str, Any]],
    blind_audits: Sequence[Mapping[str, Any]],
    key_rows: Sequence[Mapping[str, Any]],
) -> Iterator[dict[str, Any]]:
    """Walk the sealed reveal once and pair both instruments per response."""

    evaluator_by_key = {
        (str(row["case_id"]), int(row["repetition"]), str(row["model"])): row
        for row in evaluator_rows
    }
    key_by_pair = {
        (str(row["case_id"]), int(row["repetition"])): row for row in key_rows
    }
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
            yield {
                "case_id": pair[0],
                "repetition": pair[1],
                "model": model,
                "checklist_score": float(evaluator.get("score_out_of_30", 0)),
                "judge_score": float(audit_score.get("score_out_of_30", 0)),
                "checklist_rules": {
                    str(item) for item in evaluator.get("applicable_rules", [])
                },
                "judge_rules": {
                    str(item) for item in audit_score.get("applicable_rules", [])
                },
            }


def detect_rank_inversions(
    paired: Sequence[Mapping[str, Any]],
    *,
    tolerance: float = 2.0,
) -> list[dict[str, Any]]:
    """Find candidate pairs the two instruments order in opposite directions."""

    checklist: dict[str, list[float]] = {}
    judge: dict[str, list[float]] = {}
    for entry in paired:
        model = str(entry["model"])
        checklist.setdefault(model, []).append(float(entry["checklist_score"]))
        judge.setdefault(model, []).append(float(entry["judge_score"]))
    means = {
        model: (statistics.fmean(values), statistics.fmean(judge[model]))
        for model, values in checklist.items()
        if values and judge.get(model)
    }
    inversions: list[dict[str, Any]] = []
    for first, second in combinations(sorted(means), 2):
        checklist_delta = means[first][0] - means[second][0]
        judge_delta = means[first][1] - means[second][1]
        # Only an ordering that both instruments state clearly can be
        # contradicted; a gap inside the tolerance is noise on either side.
        if min(abs(checklist_delta), abs(judge_delta)) <= tolerance:
            continue
        if (checklist_delta > 0) == (judge_delta > 0):
            continue
        inversions.append(
            {
                "status": "EVAL_DISAGREEMENT",
                "reason": "rank_inversion",
                "models": [first, second],
                "checklist_delta": round(checklist_delta, 4),
                "judge_delta": round(judge_delta, 4),
            }
        )
    return inversions


def detect_evaluator_disagreements(
    evaluator_rows: Sequence[Mapping[str, Any]],
    blind_audits: Sequence[Mapping[str, Any]],
    key_rows: Sequence[Mapping[str, Any]],
    *,
    tolerance: float = 2.0,
) -> list[dict[str, Any]]:
    """Report blocking cross-instrument conflicts after identity reveal.

    Two comparisons are valid here. Applicability asks both instruments the
    same question - which rubric rules govern this scenario - so a mismatch is
    a real conflict. Ordering asks whether the deterministic checklist and the
    blind judge disagree about which candidate is better, which is the only
    score comparison a selection round actually depends on.

    Absolute `score_out_of_30` is deliberately not compared. The checklist
    score measures rule coverage while the judge score measures holistic
    quality, so the offset between them is calibration between two different
    instruments, not disagreement about a candidate.
    `summarize_evaluator_calibration` publishes that offset as a diagnostic.
    """

    paired = list(_paired_instrument_scores(evaluator_rows, blind_audits, key_rows))
    disagreements: list[dict[str, Any]] = [
        {
            "status": "EVAL_DISAGREEMENT",
            "case_id": entry["case_id"],
            "repetition": entry["repetition"],
            "model": entry["model"],
            "reason": "applicability",
        }
        for entry in paired
        if entry["checklist_rules"] != entry["judge_rules"]
    ]
    disagreements.extend(detect_rank_inversions(paired, tolerance=tolerance))
    return disagreements


def summarize_evaluator_calibration(
    evaluator_rows: Sequence[Mapping[str, Any]],
    blind_audits: Sequence[Mapping[str, Any]],
    key_rows: Sequence[Mapping[str, Any]],
    *,
    tolerance: float = 2.0,
) -> dict[str, Any]:
    """Publish the checklist/judge offset that no longer blocks acceptance."""

    paired = list(_paired_instrument_scores(evaluator_rows, blind_audits, key_rows))
    deltas = [
        entry["checklist_score"] - entry["judge_score"]
        for entry in paired
        if entry["checklist_rules"] == entry["judge_rules"]
    ]
    per_model: dict[str, dict[str, float | int]] = {}
    for entry in paired:
        bucket = per_model.setdefault(
            str(entry["model"]),
            {"observations": 0, "checklist_mean": 0.0, "judge_mean": 0.0},
        )
        bucket["observations"] = int(bucket["observations"]) + 1
        bucket["checklist_mean"] += entry["checklist_score"]
        bucket["judge_mean"] += entry["judge_score"]
    for bucket in per_model.values():
        observations = int(bucket["observations"])
        bucket["checklist_mean"] = round(bucket["checklist_mean"] / observations, 4)
        bucket["judge_mean"] = round(bucket["judge_mean"] / observations, 4)
        bucket["mean_signed_delta"] = round(
            float(bucket["checklist_mean"]) - float(bucket["judge_mean"]), 4
        )
    return {
        "tolerance": tolerance,
        "responses_compared": len(deltas),
        "responses_within_tolerance": sum(
            1 for delta in deltas if abs(delta) <= tolerance
        ),
        "mean_signed_delta": round(sum(deltas) / len(deltas), 4) if deltas else 0.0,
        "mean_absolute_delta": (
            round(sum(abs(delta) for delta in deltas) / len(deltas), 4)
            if deltas
            else 0.0
        ),
        "per_model": dict(sorted(per_model.items())),
    }


def apply_blind_audit_scores(
    rows: Sequence[Mapping[str, Any]],
    blind_audits: Sequence[Mapping[str, Any]],
    key_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Map sealed judge scores to rows and combine them with objective quality."""

    key_by_pair = {
        (str(row["case_id"]), int(row["repetition"])): row for row in key_rows
    }
    judge_by_row: dict[tuple[str, int, str], float] = {}
    for audit in blind_audits:
        pair = (str(audit["case_id"]), int(audit["repetition"]))
        key_row = key_by_pair.get(pair)
        reveal = key_row.get("reveal") if isinstance(key_row, Mapping) else None
        scores = audit.get("scores")
        if not isinstance(reveal, Mapping) or not isinstance(scores, Mapping):
            raise ValueError(f"{pair}: blind audit lacks sealed reveal mapping")
        for label, audit_score in scores.items():
            model = reveal.get(label)
            if not isinstance(model, str) or not isinstance(audit_score, Mapping):
                raise ValueError(f"{pair}: incomplete blind audit label {label}")
            score = audit_score.get("score_out_of_30")
            if (
                isinstance(score, bool)
                or not isinstance(score, int | float)
                or not 0 <= float(score) <= 30
            ):
                raise ValueError(f"{pair}: judge score for {label} must be 0..30")
            judge_by_row[(*pair, model)] = float(score)

    mapped: list[dict[str, Any]] = []
    for source_row in rows:
        row = dict(source_row)
        objective = dict(row.get("objective", {}))
        key = (str(row["case_id"]), int(row["repetition"]), str(row["model"]))
        judge_score = judge_by_row.get(key)
        if judge_score is not None:
            evaluator_score = float(objective["score_out_of_30"])
            objective["judge_score_out_of_30"] = judge_score
            objective["selection_score_out_of_30"] = round(
                (evaluator_score + judge_score) / 2,
                3,
            )
        row["objective"] = objective
        mapped.append(row)
    return mapped


def finalize_blind_scored_rows(
    rows: Sequence[Mapping[str, Any]],
    blind_audits: Sequence[Mapping[str, Any]],
    key_rows: Sequence[Mapping[str, Any]],
    blind_hard_gates: Mapping[str, bool],
) -> list[dict[str, Any]]:
    """Return the one immutable scored row set used by artifacts and selection."""

    finalized = apply_blind_audit_scores(rows, blind_audits, key_rows)
    for row in finalized:
        model = str(row["model"])
        if not blind_hard_gates.get(model, False):
            objective = dict(row.get("objective", {}))
            objective["hard_gate_passed"] = False
            row["objective"] = objective
    return finalized


def build_blind_evaluator_rows(
    rows: Sequence[Mapping[str, Any]],
    key_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Expose only completed, actually blinded responses for audit comparison."""

    revealed = {
        (str(key_row["case_id"]), int(key_row["repetition"]), str(model))
        for key_row in key_rows
        for model in (
            key_row.get("reveal", {}).values()
            if isinstance(key_row.get("reveal"), Mapping)
            else ()
        )
    }
    result: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row["case_id"]), int(row["repetition"]), str(row["model"]))
        if row.get("status", "COMPLETED") != "COMPLETED" or key not in revealed:
            continue
        objective = row["objective"]
        result.append(
            {
                "case_id": row["case_id"],
                "repetition": row["repetition"],
                "model": row["model"],
                "score_out_of_30": objective["score_out_of_30"],
                "applicable_rules": objective["applicable_rules"],
            }
        )
    return result


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


def apply_claim_hard_gates(
    rows: Sequence[Mapping[str, Any]],
    hard_gates: Mapping[str, bool],
) -> list[dict[str, Any]]:
    """Carry the claim-rubric gate into the rows the selection reads.

    The deterministic objective score is untouched. Only the gate moves, so a
    model that fabricates cannot be selected however well it writes.
    """
    gated: list[dict[str, Any]] = []
    for row in rows:
        copied = dict(row)
        objective = dict(copied.get("objective") or {})
        if not hard_gates.get(str(copied.get("model")), True):
            objective["hard_gate_passed"] = False
            objective["hard_gate_reason"] = "claim rubric critical failure"
        copied["objective"] = objective
        gated.append(copied)
    return gated


def _score_with_claim_rubric(
    blind_scores: Sequence[Mapping[str, Any]],
    *,
    output_dir: Path,
    evidence_dir: Path,
    profile: str,
    sales_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Reveal and select from a round scored by the tj-feet.4 rubric.

    Three axes are reported per model beside the selection score. There is no
    blended quality figure, and these numbers are not comparable with the
    superseded rounds.
    """
    blind_key = json.loads(
        (evidence_dir / "sales_blind_key.json").read_text(encoding="utf-8")
    )
    if not isinstance(blind_key, list):
        raise ValueError("Blind key must be a JSON array")
    commitment = _read_json_object(output_dir / "sales_blind_key.commitment.json")
    verify_blind_scores_seal(blind_key, str(commitment.get("sha256", "")))

    reports, hard_gates = evaluate_claim_reviews(blind_scores, blind_key)
    gated_rows = apply_claim_hard_gates(sales_rows, hard_gates)
    decision = select_hard_profile_winner(profile, gated_rows)

    result: dict[str, Any] = {
        "openrouter_model_main": asdict(decision),
        "openrouter_model_fast": None,
        "rubric_version": RUBRIC_VERSION,
        "comparable_with_superseded_rounds": False,
        "axes": {
            model: {
                "responses": report.responses,
                "groundedness": report.groundedness,
                "grounded_claims_scored": report.grounded_claims_scored,
                "grounded_claims_failed": report.grounded_claims_failed,
                "tool_obedience_rate": report.tool_obedience_rate,
                "conversational_quality": report.conversational_quality,
                "critical_failures": report.critical_failures,
            }
            for model, report in sorted(reports.items())
        },
        "hard_gates": dict(sorted(hard_gates.items())),
        "eval_disagreements": [],
        "eval_score_calibration": None,
        "production_changed": False,
    }
    _write_json(output_dir / "sales_blind_scores.json", list(blind_scores))
    _write_jsonl(evidence_dir / "sales_scored_results.jsonl", gated_rows)
    _write_json(
        evidence_dir / "sales_scored_aggregate.json", aggregate_rows(gated_rows)
    )
    _write_json(output_dir / "model_selection.json", result)
    return result


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
        ranked: list[tuple[str, float, float, float, float, float]] = []
        for model, model_rows in by_model.items():
            if any(
                row.get("status", "COMPLETED") != "COMPLETED"
                or not bool(row.get("objective", {}).get("hard_gate_passed"))
                for row in model_rows
            ):
                continue
            case_scores: list[float] = []
            case_spreads: list[float] = []
            complete = True
            for case_id in expected_cases:
                scores = [
                    float(
                        row["objective"].get(
                            "selection_score_out_of_30",
                            row["objective"]["score_out_of_30"],
                        )
                    )
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
                case_spreads.append(
                    statistics.pstdev(scores) if len(scores) > 1 else 0.0
                )
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
            spread = max(case_spreads, default=0.0)
            tool_discipline = statistics.fmean(
                (
                    float(bool(row["objective"].get("tool_sequence_ok")))
                    + float(bool(row["objective"].get("tool_arguments_ok")))
                )
                / 2
                for row in model_rows
            )
            ranked.append(
                (
                    model,
                    statistics.fmean(case_scores),
                    spread,
                    tool_discipline,
                    p95,
                    cost,
                )
            )
    elif profile == BACKGROUND_HARD_PROFILE:
        baseline = "deepseek/deepseek-v4-flash"
        by_model = {}
        for row in rows:
            by_model.setdefault(str(row["model"]), []).append(row)
        ranked = []
        for model, model_rows in by_model.items():
            if not all(
                row.get("status", "COMPLETED") == "COMPLETED"
                and bool(row.get("success", row.get("first_pass_success")))
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
            ranked.append((model, accuracy * 30, spread, 1.0, p95, cost))
    else:
        raise ValueError(f"Not a hard profile: {profile}")

    if not ranked:
        return WinnerDecision(
            outcome="no_safe_replacement",
            winner=None,
            reason="All candidates failed at least one hard-profile gate.",
        )
    ranked.sort(
        key=lambda item: (-item[1], item[2], -item[3], item[4], item[5], item[0])
    )
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
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def plaintext_results_dir(blind_output_dir: Path) -> Path:
    """Keep identified transcripts in a sibling directory, never with blind input."""

    return blind_output_dir.parent / f"{blind_output_dir.name}-plaintext"


def persist_blind_material(
    output_dir: Path,
    blind_rows: Sequence[Mapping[str, Any]],
    reveal_rows: Sequence[Mapping[str, Any]],
) -> Path:
    """Persist reviewer input publicly and the reveal in a mode-0600 sibling."""

    (output_dir / "sales_blind_key.json").unlink(missing_ok=True)
    _write_json(output_dir / "sales_blind_review.json", list(blind_rows))
    _write_json(
        output_dir / "sales_blind_key.commitment.json",
        {"sha256": blind_scores_digest(reveal_rows)},
    )
    private_path = plaintext_results_dir(output_dir) / "sales_blind_key.json"
    private_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            list(reveal_rows),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, encoded.encode("utf-8"))
    finally:
        os.close(fd)
    private_path.chmod(0o600)
    return private_path


def _manifest_plaintext_results_dir(
    output_dir: Path,
    manifest: Mapping[str, Any],
) -> Path:
    value = manifest.get("plaintext_results_dir")
    if not isinstance(value, str) or not value:
        return output_dir
    path = Path(value)
    return path if path.is_absolute() else output_dir / path


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
        evidence_dir = _manifest_plaintext_results_dir(output_dir, manifest)
        path = evidence_dir / f"{suite}_results.jsonl"
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
    after_request: Callable[[object | None, ProviderAttempt], None] | None = None,
) -> list[ProviderAttempt]:
    attempts: list[ProviderAttempt] = []
    for attempt_number in (1, 2):
        reservation = before_request() if before_request is not None else None
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
            attempt = ProviderAttempt(
                attempt=attempt_number,
                ok=ok,
                status_code=response.status_code,
                elapsed_ms=round(elapsed_ms, 3),
                response=parsed,
                error=error,
            )
            attempts.append(attempt)
        except (httpx.HTTPError, TimeoutError) as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            attempt = ProviderAttempt(
                attempt=attempt_number,
                ok=False,
                status_code=None,
                elapsed_ms=round(elapsed_ms, 3),
                response=None,
                error=_safe_error_text(exc),
            )
            attempts.append(attempt)
        if after_request is not None:
            after_request(reservation, attempts[-1])
        if attempts[-1].ok:
            break
        if attempts[-1].status_code is not None and not should_retry_status(
            attempts[-1].status_code
        ):
            break
    return attempts


def _served_providers(attempts: Sequence[ProviderAttempt]) -> list[str]:
    """Name who actually answered, in order, so a chain stays auditable."""

    served: list[str] = []
    for attempt in attempts:
        response = attempt.response
        if not isinstance(response, Mapping):
            continue
        provider = response.get("provider")
        if isinstance(provider, str) and provider and provider not in served:
            served.append(provider)
    return served


def _provider_attempt_cost(
    _reservation: object | None,
    attempt: ProviderAttempt,
) -> float:
    response = attempt.response
    if isinstance(response, Mapping):
        usage = response.get("usage")
        if isinstance(usage, Mapping):
            cost = usage.get("cost")
            if isinstance(cost, int | float) and not isinstance(cost, bool):
                return _finite_number(cost, "Provider usage.cost")
    if not attempt.ok:
        return 0.0
    raise RuntimeError("Successful provider response omitted usage.cost")


def _choice_message(attempts: Sequence[ProviderAttempt]) -> dict[str, Any] | None:
    if not attempts or not attempts[-1].ok or attempts[-1].response is None:
        return None
    choices = attempts[-1].response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message")
    return message if isinstance(message, dict) else None


def _finish_reason(attempts: Sequence[ProviderAttempt]) -> str | None:
    if not attempts or attempts[-1].response is None:
        return None
    choices = attempts[-1].response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    value = choices[0].get("finish_reason")
    return str(value) if value is not None else None


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
        if isinstance(elapsed_ms, int | float) and not isinstance(elapsed_ms, bool):
            totals["latency_ms"] += _finite_number(elapsed_ms, "Attempt latency")
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
                finite = _finite_number(value, f"Usage {source}")
                if not finite.is_integer():
                    raise RuntimeError(f"Usage {source} must be a finite integer")
                totals[target] += int(finite)
        prompt_details = usage.get("prompt_tokens_details")
        if isinstance(prompt_details, Mapping):
            cached = prompt_details.get("cached_tokens", 0)
            if isinstance(cached, int | float) and not isinstance(cached, bool):
                finite = _finite_number(cached, "Usage cached_tokens")
                if not finite.is_integer():
                    raise RuntimeError("Usage cached_tokens must be a finite integer")
                totals["cached_tokens"] += int(finite)
        cost = usage.get("cost", 0)
        if isinstance(cost, int | float) and not isinstance(cost, bool):
            totals["cost_usd"] += _finite_number(cost, "Usage cost")
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
    caps: Mapping[str, float] | None = None,
) -> None:
    """Fail closed when provider-reported spend exceeds a model's own cap."""

    actual: dict[str, float] = {}
    for row in rows:
        model = str(row["model"])
        accounting = row.get("accounting")
        if not isinstance(accounting, Mapping):
            continue
        cost = accounting.get("cost_usd", 0)
        if isinstance(cost, int | float) and not isinstance(cost, bool):
            actual[model] = actual.get(model, 0.0) + _finite_number(
                cost, f"Accounting cost for {model}"
            )
    resolved_caps = resolve_model_caps(estimated_costs) if caps is None else dict(caps)
    exceeded: list[str] = []
    for model in estimated_costs:
        cap = _finite_number(
            resolved_caps.get(model, DEFAULT_PER_MODEL_CAP_USD), f"Cost cap for {model}"
        )
        if actual.get(model, 0.0) > cap + 1e-12:
            exceeded.append(f"{model}: spent ${actual[model]:.6f}, cap ${cap:.6f}")
    if exceeded:
        raise RuntimeError("Model cost cap exceeded: " + "; ".join(exceeded))


def build_cost_preflight(
    estimated_costs: Mapping[str, float],
    caps: Mapping[str, float] | None = None,
    *,
    cap_policy: str = "fixed",
) -> dict[str, Any]:
    """Describe reservations without treating a conservative estimate as spend."""

    finite_estimates = {
        model: _finite_number(estimate, f"Estimate for {model}")
        for model, estimate in estimated_costs.items()
    }
    resolved_caps = (
        resolve_model_caps(finite_estimates, policy=cap_policy)
        if caps is None
        else {
            model: _finite_number(caps[model], f"Cost cap for {model}")
            for model in finite_estimates
        }
    )
    order = sorted(finite_estimates, key=lambda model: (finite_estimates[model], model))
    return {
        "estimated_costs_usd": finite_estimates,
        "batch_allowances_usd": {
            model: min(resolved_caps[model], estimate * 1.25)
            for model, estimate in finite_estimates.items()
        },
        "per_model_caps_usd": resolved_caps,
        "cap_policy": cap_policy,
        "caps_raised_above_default": {
            model: cap
            for model, cap in resolved_caps.items()
            if cap > DEFAULT_PER_MODEL_CAP_USD + 1e-12
        },
        "maximum_total_usd": sum(resolved_caps.values()),
        "execution_order": order,
        "estimate_is_reservation_not_spend": True,
    }


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
            len(
                json.dumps(
                    {
                        "system_prompt": case.system_prompt,
                        "user_prompt": case.user_prompt,
                        "conversation": (
                            list(case.conversation) if suite == "sales" else []
                        ),
                        "tools": list(case.tools) if suite == "sales" else [],
                        "tool_results": (
                            [case.tool_results] * 3 if suite == "sales" else []
                        ),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
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
            prompt_price = _finite_number(
                pricing["prompt"], f"Prompt price for {model}"
            )
            completion_price = _finite_number(
                pricing["completion"], f"Completion price for {model}"
            )
        except KeyError as exc:
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
    provider_order: Sequence[str] | None = None,
    provider_quantizations: Sequence[str] | None = None,
) -> dict[str, Any]:
    owner = model.partition("/")[0]
    provider: dict[str, Any] = {"require_parameters": True}
    provider_slug = _FIRST_PARTY_PROVIDERS.get(owner)
    if provider_order:
        # An ordered chain with fallbacks off stays inside the resolved list and
        # tries it in sequence, so a provider outage costs the next entry rather
        # than the candidate's whole matrix. The order names providers, so the
        # quantization allowlist is what keeps a vetted serving vetted.
        provider.update(
            {
                "order": list(provider_order),
                "allow_fallbacks": False,
            }
        )
        if provider_quantizations:
            provider["quantizations"] = list(provider_quantizations)
    elif provider_slug is not None:
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
        "usage": {"include": True},
    }
    if reasoning_enabled is not None:
        payload["reasoning"] = {"enabled": reasoning_enabled}
    return payload


def _render_required_schema(schema: Mapping[str, Any]) -> str:
    """State the required JSON contract that portable `json_object` cannot carry."""

    return (
        "The json object must conform exactly to this JSON Schema. Use these "
        "property names verbatim and include every required property:\n"
        + json.dumps(dict(schema), ensure_ascii=False, sort_keys=True)
    )


def build_system_response_format(
    profile: str,
    schema: Mapping[str, Any],
    *,
    name: str = "model_battle_result",
) -> dict[str, Any]:
    """Use portable JSON mode for hard profiles and validate schemas locally."""

    if profile in _HARD_PROFILES:
        return {"type": "json_object"}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": dict(schema),
        },
    }


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
            "usage",
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


def _extract_asserted_numeric_tokens(value: str) -> set[str]:
    without_list_markers = re.sub(r"(?m)^\s*\d+[.)]\s+", "", value)
    return extract_numeric_tokens(without_list_markers)


def _numeric_token(value: float) -> str:
    """Render a derived value in the same normalized form as an extracted one."""

    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def derive_quotation_arithmetic(tokens: set[str], *, limit: int = 120) -> set[str]:
    """Admit the arithmetic a quotation must perform on grounded numbers.

    A sales answer that multiplies a grounded unit price by a grounded quantity,
    or adds two grounded line totals, is not inventing a commercial fact. Without
    this closure the grounding gate rejects every competent quotation, which is
    what eliminated the whole candidate field in the first core round.
    """

    values: list[float] = []
    for token in tokens:
        try:
            values.append(float(token))
        except ValueError:
            continue
    if len(values) > limit:
        return set(tokens)
    derived = set(tokens)
    for index, left in enumerate(values):
        for right in values[index:]:
            candidates = [left * right, left + right, abs(left - right)]
            # Division recovers the per-unit price from a grounded line total,
            # which is the other half of ordinary quotation arithmetic.
            if right:
                candidates.append(left / right)
            if left:
                candidates.append(right / left)
            for candidate in candidates:
                if math.isfinite(candidate) and candidate >= 0:
                    derived.add(_numeric_token(candidate))
    return derived


def timestamp_component_tokens(value: str) -> set[str]:
    """Expose the parts of an ISO timestamp the SKU-safe number regex hides.

    ``_NUMBER_RE`` refuses digits preceded by a hyphen or letter so that SKUs
    like ``AX-E1`` are never read as numbers. That also hides the month, day and
    hour of ``2026-08-03T10:00:00Z``, so a model restating the same timestamp in
    words looks like it invented ``3`` and ``10``.
    """

    tokens: set[str] = set()
    for match in _ISO_TIMESTAMP_RE.finditer(value):
        for part in match.groups():
            if part is None:
                continue
            tokens.add(part)
            tokens.add(str(int(part)))
    return tokens


def build_sales_grounding_numbers(case: Any) -> set[str]:
    """Build the one numeric evidence set used by live and offline scoring."""

    grounding_evidence = json.dumps(
        {
            "system_prompt": case.system_prompt,
            "conversation": case.conversation,
            "user_prompt": case.user_prompt,
            "tool_results": case.tool_results,
        },
        ensure_ascii=False,
    )
    grounded = extract_numeric_tokens(grounding_evidence)
    grounded |= timestamp_component_tokens(grounding_evidence)
    return derive_quotation_arithmetic(grounded)


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
    ungrounded_numbers = sorted(
        _extract_asserted_numeric_tokens(content) - allowed_numbers
    )
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
    provider_order: Sequence[str] | None = None,
    provider_quantizations: Sequence[str] | None = None,
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
    finish_reason: str | None = None
    request_parameters: list[dict[str, Any]] = []

    for _round in range(3):
        payload = build_base_payload(
            model=model,
            messages=messages,
            max_tokens=2200,
            reasoning_enabled=False,
            provider_order=provider_order,
            provider_quantizations=provider_quantizations,
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
            after_request=(
                None
                if cost_budget is None
                else lambda reservation, attempt: cost_budget.reconcile_request(
                    model,
                    float(reservation),
                    actual_cost=_provider_attempt_cost(reservation, attempt),
                )
            ),
        )
        all_attempts.extend(attempts)
        attempt_counts_by_round.append(len(attempts))
        message = _choice_message(attempts)
        if message is None:
            break
        finish_reason = _finish_reason(attempts)
        if finish_reason == "length":
            final_content = str(message.get("content") or "").strip()
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

    status = "TRUNCATED" if finish_reason == "length" else "COMPLETED"
    if not final_content and status == "COMPLETED":
        status = "PROVIDER_ERROR"
    objective = (
        {"scored": False, "reason": "TRUNCATED"}
        if status == "TRUNCATED"
        else score_sales_response(
            content=final_content,
            required_phrases=case.required_phrases,
            forbidden_phrases=case.forbidden_phrases,
            expected_tools=case.expected_tools,
            observed_tools=observed_tools,
            expected_language=case.expected_language,
            allowed_numbers=build_sales_grounding_numbers(case),
            critical_required_phrases=case.critical_required_phrases,
        )
    )
    tool_args_ok = all(
        item["parse_error"] is None and item["correct"] == item["total"]
        for item in tool_argument_results
    )
    if status != "TRUNCATED":
        objective["tool_arguments_ok"] = tool_args_ok
        objective["passed"] = objective["passed"] and tool_args_ok
        objective["hard_gate_passed"] = objective["hard_gate_passed"] and tool_args_ok
    return {
        "suite": "sales",
        "case_id": case.case_id,
        "category": case.category,
        "model": model,
        "repetition": repetition,
        "status": status,
        "finish_reason": finish_reason,
        "success": bool(final_content),
        "first_pass_success": bool(all_attempts and all_attempts[0].ok),
        "retry_used": retry_was_used(attempt_counts_by_round),
        "latency_ms": round(sum(item.elapsed_ms for item in all_attempts), 3),
        "provider_attempts": [asdict(item) for item in all_attempts],
        "provider_order": list(provider_order or []),
        "served_providers": _served_providers(all_attempts),
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
    profile: str = ORIGINAL_PROFILE,
    cost_budget: RequestCostBudget | None = None,
    provider_order: Sequence[str] | None = None,
    provider_quantizations: Sequence[str] | None = None,
) -> dict[str, Any]:
    system_prompt = case.system_prompt
    if not case.tools:
        # Two provider-neutral additions, identical for every candidate, so
        # comparability is unchanged. OpenAI rejects a JSON response format
        # unless the messages contain the word "json". And a hard profile uses
        # portable `json_object`, which carries no schema, so the required shape
        # has to be stated in the prompt or every candidate answers a contract
        # it was never shown.
        system_prompt = f"{system_prompt}\n{_JSON_RESPONSE_FORMAT_NOTICE}"
        if profile in _HARD_PROFILES:
            system_prompt = f"{system_prompt}\n{_render_required_schema(case.schema)}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": case.user_prompt},
    ]
    payload = build_base_payload(
        model=model,
        messages=messages,
        max_tokens=900,
        reasoning_enabled=False,
        provider_order=provider_order,
        provider_quantizations=provider_quantizations,
    )
    if case.tools:
        payload["tools"] = list(case.tools)
        payload["tool_choice"] = "auto"
    else:
        payload["response_format"] = build_system_response_format(
            profile,
            case.schema,
            name=case.case_id.replace("-", "_"),
        )
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
        after_request=(
            None
            if cost_budget is None
            else lambda reservation, attempt: cost_budget.reconcile_request(
                model,
                float(reservation),
                actual_cost=_provider_attempt_cost(reservation, attempt),
            )
        ),
    )
    message = _choice_message(attempts)
    finish_reason = _finish_reason(attempts)
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

    if finish_reason == "length":
        parsed = None
        parse_ok = False
        schema_errors = ["TRUNCATED: response was not quality-scored"]
        semantic_correct = 0
        semantic_total = 0
        semantic_mismatches = ["TRUNCATED: response was not quality-scored"]
        critical_fields_ok = False

    return {
        "suite": "system",
        "case_id": case.case_id,
        "category": case.category,
        "model": model,
        "repetition": repetition,
        "status": (
            "TRUNCATED"
            if finish_reason == "length"
            else "COMPLETED"
            if message
            else "PROVIDER_ERROR"
        ),
        "finish_reason": finish_reason,
        "success": bool(message),
        "first_pass_success": bool(attempts and attempts[0].ok),
        "retry_used": len(attempts) > 1,
        "reasoning_requested": False,
        "reasoning_observed": reasoning_was_observed(attempts),
        "latency_ms": round(sum(item.elapsed_ms for item in attempts), 3),
        "provider_attempts": [asdict(item) for item in attempts],
        "provider_order": list(provider_order or []),
        "served_providers": _served_providers(attempts),
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
    *,
    require_all: bool = True,
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
    if missing and require_all:
        raise RuntimeError(f"Models missing from OpenRouter catalog: {missing}")
    return {model: by_id[model] for model in models if model in by_id}


def _normalized_provider_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _required_parameters_by_model(
    suites: Sequence[str],
    *,
    profile: str,
) -> dict[str, set[str]]:
    requirements: dict[str, set[str]] = {}
    if "sales" in suites:
        for model in models_for_profile(profile, "sales"):
            requirements.setdefault(model, set()).update({"tools", "tool_choice"})
    if "system" in suites:
        system_parameters = {
            "tools",
            "tool_choice",
            "response_format",
            "reasoning",
        }
        if profile not in _HARD_PROFILES:
            system_parameters.add("structured_outputs")
        for model in models_for_profile(profile, "system"):
            requirements.setdefault(model, set()).update(system_parameters)
    if profile in _HARD_PROFILES:
        for required in requirements.values():
            required.update({"max_tokens", "reasoning"})
    return requirements


def _endpoint_price(endpoint: Mapping[str, Any], field: str) -> float:
    """Price an endpoint for ordering; an unpriced endpoint sorts last."""

    pricing = endpoint.get("pricing")
    if isinstance(pricing, Mapping) and field in pricing:
        try:
            return float(pricing[field])
        except (TypeError, ValueError):
            return math.inf
    return math.inf


def _endpoint_provider_slug(endpoint: Mapping[str, Any]) -> str:
    """Prefer the tag's own prefix; it is the slug routing actually accepts.

    A display name does not survive normalization reliably - "AtlasCloud"
    becomes `atlascloud` while the routable slug is `atlas-cloud`, and an order
    entry that names no real provider is silently dropped.
    """

    tag = endpoint.get("tag")
    if isinstance(tag, str) and tag.strip():
        return tag.partition("/")[0].strip()
    return _normalized_provider_name(str(endpoint.get("provider_name") or ""))


def resolve_provider_chain(
    model: str,
    endpoint_catalog: Mapping[str, Any],
    *,
    required_parameters: set[str],
    limit: int = _PROVIDER_CHAIN_LIMIT,
) -> list[dict[str, Any]]:
    """Order the endpoints a candidate may be served by, first party first.

    The publisher's own endpoint is the reference serving of a model, so it
    always leads and every comparison prefers it. It can also be down, and a
    round that dies on one provider outage buys nothing, so a bounded number of
    alternates follows it in published order. Aggressively quantized servings
    are excluded outright rather than ranked last, because they answer as a
    different artefact and would silently turn a model comparison into a host
    comparison.
    """

    owner = model.partition("/")[0]
    first_party = _FIRST_PARTY_PROVIDERS.get(owner)
    if first_party is None:
        raise RuntimeError(f"No first-party provider pin configured for {model}")
    data = endpoint_catalog.get("data")
    endpoints = data.get("endpoints") if isinstance(data, Mapping) else None
    eligible: list[dict[str, Any]] = []
    for endpoint in endpoints or []:
        if not isinstance(endpoint, Mapping):
            continue
        supported = {
            str(parameter)
            for parameter in endpoint.get("supported_parameters", [])
            if isinstance(parameter, str)
        }
        if not required_parameters <= supported:
            continue
        quantization = str(endpoint.get("quantization") or "unknown").casefold()
        if quantization in _EXCLUDED_QUANTIZATIONS:
            continue
        eligible.append(dict(endpoint))
    if not eligible:
        raise RuntimeError(
            f"No unquantized endpoint for {model} supports required parameters: "
            + ", ".join(sorted(required_parameters))
        )

    def _rank(endpoint: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            0 if _endpoint_provider_slug(endpoint) == first_party else 1,
            _endpoint_price(endpoint, "completion"),
            _endpoint_price(endpoint, "prompt"),
            -float(endpoint.get("uptime_last_1d") or 0.0),
            _endpoint_provider_slug(endpoint),
        )

    ranked = sorted(eligible, key=_rank)
    admitted: list[str] = []
    for endpoint in ranked:
        slug = _endpoint_provider_slug(endpoint)
        if slug not in admitted:
            if len(admitted) >= limit:
                continue
            admitted.append(slug)
    # Every eligible endpoint of an admitted provider stays in the chain. The
    # chain is what cost and capability evidence is computed over, so dropping a
    # provider's dearer endpoint would understate what a run can actually cost.
    return [
        endpoint for endpoint in ranked if _endpoint_provider_slug(endpoint) in admitted
    ]


def provider_order_from_chain(chain: Sequence[Mapping[str, Any]]) -> list[str]:
    """Name each distinct chain provider as `provider.order` expects it.

    Provider slugs, not endpoint tags. A tag also selects a serving variant, so
    ordering by tag would let the cheapest variant of the publisher's own
    endpoint - a flex or batch tier - replace the standard serving a previous
    round measured, and quietly change latency as well as the provider.
    """

    order: list[str] = []
    claimed: set[str] = set()
    for endpoint in chain:
        slug = _endpoint_provider_slug(endpoint)
        if slug in claimed:
            continue
        claimed.add(slug)
        order.append(slug)
    return order


def provider_quantizations_from_chain(chain: Sequence[Mapping[str, Any]]) -> list[str]:
    """Allow only the servings the chain vetted, since order names providers."""

    return sorted(
        {
            str(endpoint.get("quantization") or "unknown").casefold()
            for endpoint in chain
        }
    )


def build_pinned_catalog_entry(
    model: str,
    model_entry: Mapping[str, Any],
    endpoint_catalog: Mapping[str, Any],
    *,
    required_parameters: set[str],
) -> dict[str, Any]:
    """Bind capability and cost evidence to the providers used in requests."""

    owner = model.partition("/")[0]
    provider_slug = _FIRST_PARTY_PROVIDERS.get(owner)
    if provider_slug is None:
        raise RuntimeError(f"No first-party provider pin configured for {model}")
    chain = resolve_provider_chain(
        model,
        endpoint_catalog,
        required_parameters=required_parameters,
    )

    def _highest_price(field: str) -> str:
        values = [
            str(pricing[field])
            for endpoint in chain
            if isinstance((pricing := endpoint.get("pricing")), Mapping)
            and field in pricing
        ]
        if not values:
            raise RuntimeError(f"Missing {field} pricing for {model}")
        return max(values, key=float)

    supported_sets = [
        {
            str(parameter)
            for parameter in endpoint.get("supported_parameters", [])
            if isinstance(parameter, str)
        }
        for endpoint in chain
    ]
    supported = set.intersection(*supported_sets)
    result = dict(model_entry)
    result.update(
        {
            "pricing": {
                "prompt": _highest_price("prompt"),
                "completion": _highest_price("completion"),
            },
            "supported_parameters": sorted(supported),
            "pinned_provider": provider_slug,
            "first_party_available": any(
                _endpoint_provider_slug(endpoint) == provider_slug for endpoint in chain
            ),
            "provider_order": provider_order_from_chain(chain),
            "provider_quantizations": provider_quantizations_from_chain(chain),
            "pinned_endpoints": [
                {
                    key: endpoint[key]
                    for key in (
                        "name",
                        "provider_name",
                        "tag",
                        "quantization",
                        "supported_parameters",
                        "pricing",
                    )
                    if key in endpoint
                }
                for endpoint in chain
            ],
        }
    )
    return result


async def _fetch_pinned_catalog(
    client: httpx.AsyncClient,
    models: Sequence[str],
    *,
    suites: Sequence[str],
    profile: str,
) -> dict[str, Any]:
    catalog = await _fetch_catalog(client, models, require_all=False)
    requirements = _required_parameters_by_model(suites, profile=profile)
    pinned: dict[str, Any] = {}
    for model in models:
        if model not in catalog:
            continue
        try:
            response = await client.get(f"/models/{model}/endpoints", timeout=30.0)
            response.raise_for_status()
            pinned[model] = build_pinned_catalog_entry(
                model,
                catalog[model],
                response.json(),
                required_parameters=requirements.get(model, set()),
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            pinned[model] = {
                "id": model,
                "supported_parameters": [],
                "unsupported_reason": _safe_error_text(exc),
            }
    return pinned


def assert_catalog_capabilities(
    catalog: Mapping[str, Mapping[str, Any]],
    suites: Sequence[str],
    *,
    profile: str = ORIGINAL_PROFILE,
) -> None:
    """Fail before paid calls when a candidate lacks a required API feature."""

    statuses = catalog_capability_statuses(catalog, suites, profile=profile)
    failures = [
        f"{model}: "
        + (
            "missing " + ", ".join(status["missing_parameters"])
            if status["missing_parameters"]
            else str(status["reason"])
        )
        for model, status in statuses.items()
        if status["status"] == "UNSUPPORTED"
    ]
    if failures:
        raise RuntimeError(
            "OpenRouter catalog capability preflight failed: " + "; ".join(failures)
        )


def catalog_capability_statuses(
    catalog: Mapping[str, Mapping[str, Any]],
    suites: Sequence[str],
    *,
    profile: str = ORIGINAL_PROFILE,
) -> dict[str, dict[str, Any]]:
    """Return machine-readable support status for every configured candidate."""

    requirements = _required_parameters_by_model(suites, profile=profile)
    statuses: dict[str, dict[str, Any]] = {}
    for model, required in requirements.items():
        if model not in catalog:
            statuses[model] = {
                "status": "UNSUPPORTED",
                "reason": "missing_from_catalog",
                "missing_parameters": [],
            }
            continue
        unsupported_reason = catalog[model].get("unsupported_reason")
        if isinstance(unsupported_reason, str) and unsupported_reason:
            statuses[model] = {
                "status": "UNSUPPORTED",
                "reason": unsupported_reason,
                "missing_parameters": sorted(required),
            }
            continue
        supported_raw = catalog[model].get("supported_parameters", [])
        supported = (
            {str(item) for item in supported_raw}
            if isinstance(supported_raw, list)
            else set()
        )
        missing = sorted(required - supported)
        statuses[model] = {
            "status": "SUPPORTED" if not missing else "UNSUPPORTED",
            "reason": "supported" if not missing else "missing_required_parameters",
            "missing_parameters": missing,
        }
    return statuses


def _build_jobs(
    *,
    suite: str,
    repetitions: int,
    seed: int,
    profile: str = ORIGINAL_PROFILE,
    estimated_costs: Mapping[str, float] | None = None,
) -> list[tuple[str, Any, int]]:
    models = models_for_profile(profile, suite)
    cases = cases_for_profile(profile, suite)
    if estimated_costs is None:
        jobs = [
            (model, case, repetition)
            for case in cases
            for repetition in range(1, repetitions + 1)
            for model in models
        ]
        random.Random(f"{seed}:{suite}").shuffle(jobs)
        return jobs
    ordered_models = sorted(models, key=lambda model: (estimated_costs[model], model))
    jobs = []
    for model in ordered_models:
        model_jobs = [
            (model, case, repetition)
            for case in cases
            for repetition in range(1, repetitions + 1)
        ]
        random.Random(f"{seed}:{suite}:{model}").shuffle(model_jobs)
        jobs.extend(model_jobs)
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
    for model, all_model_rows in by_model.items():
        # A truncated answer is a harness budget event, not a quality failure,
        # so it is left unscored instead of eliminating the candidate. A model
        # with nothing but truncated rows has no evidence and cannot advance.
        model_rows = [row for row in all_model_rows if row.get("status") != "TRUNCATED"]
        if not model_rows:
            continue
        if suite == "sales":
            passed = all(
                row.get("status", "COMPLETED") == "COMPLETED"
                and bool(row.get("objective", {}).get("hard_gate_passed"))
                for row in model_rows
            )
        elif suite == "system":
            schema_passed = all(
                row.get("status", "COMPLETED") == "COMPLETED"
                and bool(row.get("success", row.get("first_pass_success")))
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
    estimated_costs: Mapping[str, float] | None = None,
) -> list[tuple[str, Any, int]]:
    """Build repetitions two and three only for round-zero survivors."""

    survivors = _round_zero_survivors(suite, round_zero_rows)
    cases = cases_for_profile(profile, suite)
    if profile == BACKGROUND_HARD_PROFILE and suite == "system":
        differentiating = set(
            select_differentiating_system_cases(round_zero_rows, limit=3)
        )
        cases = tuple(case for case in cases if case.case_id in differentiating)
    if estimated_costs is None:
        jobs = [
            (model, case, repetition)
            for case in cases
            for repetition in (2, 3)
            for model in survivors
        ]
        random.Random(f"{seed}:{suite}:survivors").shuffle(jobs)
        return jobs
    jobs = []
    for model in sorted(
        survivors,
        key=lambda candidate: (estimated_costs[candidate], candidate),
    ):
        model_jobs = [
            (model, case, repetition) for case in cases for repetition in (2, 3)
        ]
        random.Random(f"{seed}:{suite}:survivors:{model}").shuffle(model_jobs)
        jobs.extend(model_jobs)
    return jobs


def validate_hard_profile_result_matrix(
    profile: str,
    suite: str,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    """Require the exact staged model × case × repetition matrix before ranking."""

    if profile not in _HARD_PROFILES:
        raise ValueError(f"Not a hard profile: {profile}")
    actual_keys = [
        (str(row["model"]), str(row["case_id"]), int(row["repetition"])) for row in rows
    ]
    if len(actual_keys) != len(set(actual_keys)):
        raise ValueError("Hard-profile result matrix contains duplicate rows")

    models = models_for_profile(profile, suite)
    cases = cases_for_profile(profile, suite)
    round_zero = {(model, case.case_id, 1) for model in models for case in cases}
    actual = set(actual_keys)
    missing_round_zero = round_zero - actual
    if missing_round_zero:
        raise ValueError(
            "Hard-profile result matrix is incomplete: "
            f"missing {len(missing_round_zero)} round-zero rows"
        )

    round_zero_rows = [row for row in rows if int(row["repetition"]) == 1]
    survivors = _round_zero_survivors(suite, round_zero_rows)
    repeated_cases = cases
    if profile == BACKGROUND_HARD_PROFILE and suite == "system":
        differentiating = set(
            select_differentiating_system_cases(round_zero_rows, limit=3)
        )
        repeated_cases = tuple(
            case for case in cases if case.case_id in differentiating
        )
    expected = round_zero | {
        (model, case.case_id, repetition)
        for model in survivors
        for case in repeated_cases
        for repetition in (2, 3)
    }
    missing = expected - actual
    unexpected = actual - expected
    if missing or unexpected:
        raise ValueError(
            "Hard-profile result matrix is incomplete or unexpected: "
            f"missing={len(missing)}, unexpected={len(unexpected)}"
        )


def _sales_rule_labels(case: Any) -> dict[str, str]:
    labels = {
        **{
            f"required:{phrase}": f"Response explicitly covers: {phrase}"
            for phrase in case.required_phrases
        },
        **{
            f"forbidden:{phrase}": f"Response does not assert: {phrase}"
            for phrase in case.forbidden_phrases
        },
        "tool_sequence": "Observed tool names exactly match the required sequence",
        "language": f"Response language is {case.expected_language or 'unrestricted'}",
        "numeric_grounding": "Every asserted number exists in the synthetic evidence",
    }
    return dict(sorted(labels.items()))


def _build_blind_files(
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    profile: str = ORIGINAL_PROFILE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases_by_id = {case.case_id: case for case in cases_for_profile(profile, "sales")}
    grouped: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for row in rows:
        if row.get("suite") != "sales" or row.get("status", "COMPLETED") != "COMPLETED":
            continue
        key = (str(row["case_id"]), int(row["repetition"]))
        grouped.setdefault(key, {})[str(row["model"])] = {
            "response": str(row["final_content"]),
            "observed_tools": list(row.get("observed_tools", [])),
            "tool_arguments": list(row.get("tool_arguments", [])),
        }

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
                    "tool_results": cases_by_id[case_id].tool_results,
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
                        "applicable_rule_labels": _sales_rule_labels(
                            cases_by_id[case_id]
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
    evidence_dir = _manifest_plaintext_results_dir(output_dir, manifest)
    profile = str(manifest["profile"])
    if profile == BACKGROUND_HARD_PROFILE:
        system_rows = rescore_system_rows(
            _read_jsonl(evidence_dir / "system_results.jsonl"),
            profile=profile,
        )
        validate_hard_profile_result_matrix(profile, "system", system_rows)
        decision = select_hard_profile_winner(profile, system_rows)
        result: dict[str, Any] = {
            "openrouter_model_main": None,
            "openrouter_model_fast": asdict(decision),
            "eval_disagreements": [],
            "eval_score_calibration": None,
            "production_changed": False,
        }
        _write_jsonl(evidence_dir / "system_scored_results.jsonl", system_rows)
        _write_json(output_dir / "model_selection.json", result)
        return result

    if blind_scores_path is None:
        raise ValueError("Sales scoring requires a completed blind review file")
    sales_rows = rescore_sales_rows(
        _read_jsonl(evidence_dir / "sales_results.jsonl"),
        profile=profile,
    )
    if profile == CORE_HARD_PROFILE:
        validate_hard_profile_result_matrix(profile, "sales", sales_rows)
    blind_scores = parse_json_content(blind_scores_path.read_text(encoding="utf-8"))
    if not isinstance(blind_scores, list):
        raise ValueError("Blind scores must be a JSON array")
    if is_claim_review(blind_scores):
        # tj-feet.4 rubric. Kept behind format detection so a superseded round
        # scored by the old instrument still loads through the old path.
        return _score_with_claim_rubric(
            blind_scores,
            output_dir=output_dir,
            evidence_dir=evidence_dir,
            profile=profile,
            sales_rows=sales_rows,
        )
    blind_scores = normalize_blind_reviews(blind_scores)
    if profile == CORE_HARD_PROFILE:
        seal_path = output_dir / "sales_blind_scores.seal.json"
        seal = _read_json_object(seal_path)
        verify_blind_scores_seal(blind_scores, str(seal.get("sha256", "")))
    blind_key = json.loads(
        (evidence_dir / "sales_blind_key.json").read_text(encoding="utf-8")
    )
    if not isinstance(blind_key, list):
        raise ValueError("Blind key must be a JSON array")
    commitment = _read_json_object(output_dir / "sales_blind_key.commitment.json")
    verify_blind_scores_seal(blind_key, str(commitment.get("sha256", "")))
    blind_quality, blind_hard_gates = evaluate_blind_reviews(
        blind_scores,
        blind_key,
    )

    if profile == CORE_HARD_PROFILE:
        sales_rows = finalize_blind_scored_rows(
            sales_rows,
            blind_scores,
            blind_key,
            blind_hard_gates,
        )
        _write_json(output_dir / "sales_blind_scores.json", blind_scores)
        _write_jsonl(evidence_dir / "sales_scored_results.jsonl", sales_rows)
        _write_json(
            evidence_dir / "sales_scored_aggregate.json",
            aggregate_rows(sales_rows),
        )
        evaluator_rows = build_blind_evaluator_rows(sales_rows, blind_key)
        disagreements = detect_evaluator_disagreements(
            evaluator_rows,
            blind_scores,
            blind_key,
        )
        calibration = summarize_evaluator_calibration(
            evaluator_rows,
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
            "eval_score_calibration": calibration,
            "production_changed": False,
        }
        _write_json(output_dir / "model_selection.json", result)
        return result

    _write_json(output_dir / "sales_blind_scores.json", blind_scores)
    _write_jsonl(evidence_dir / "sales_scored_results.jsonl", sales_rows)
    _write_json(
        evidence_dir / "sales_scored_aggregate.json",
        aggregate_rows(sales_rows),
    )

    system_rows = rescore_system_rows(
        _read_jsonl(evidence_dir / "system_results.jsonl")
    )
    _write_jsonl(evidence_dir / "system_scored_results.jsonl", system_rows)
    _write_json(
        evidence_dir / "system_scored_aggregate.json",
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
        if row.get("status") == "TRUNCATED":
            row["objective"] = {"scored": False, "reason": "TRUNCATED"}
            rescored.append(row)
            continue
        objective = score_sales_response(
            content=str(row["final_content"]),
            required_phrases=case.required_phrases,
            forbidden_phrases=case.forbidden_phrases,
            expected_tools=case.expected_tools,
            observed_tools=[str(item) for item in row["observed_tools"]],
            expected_language=case.expected_language,
            allowed_numbers=build_sales_grounding_numbers(case),
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
    for row in rows:
        model = str(row.get("model", "unknown"))
        _finite_number(row.get("latency_ms", 0), f"Latency for {model}")
        accounting = row.get("accounting", {})
        if isinstance(accounting, Mapping):
            for field in (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cached_tokens",
                "cost_usd",
                "latency_ms",
            ):
                if field in accounting:
                    _finite_number(accounting[field], f"Accounting {field} for {model}")
    aggregate: dict[str, Any] = {}
    for model in sorted({str(row["model"]) for row in rows}):
        model_rows = [row for row in rows if row["model"] == model]
        latencies = [float(row["latency_ms"]) for row in model_rows]
        first_pass = sum(bool(row["first_pass_success"]) for row in model_rows)
        entry: dict[str, Any] = {
            "model": model,
            "runs": len(model_rows),
            "statuses": {
                status: sum(
                    row.get("status", "COMPLETED") == status for row in model_rows
                )
                for status in sorted(
                    {str(row.get("status", "COMPLETED")) for row in model_rows}
                )
            },
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
            scored_rows = [
                row
                for row in model_rows
                if row.get("status", "COMPLETED") == "COMPLETED"
                and row.get("objective", {}).get("scored", True)
            ]
            entry["objective_correctness"] = (
                statistics.fmean(
                    int(row["objective"]["checks_passed"])
                    / int(row["objective"]["checks_total"])
                    for row in scored_rows
                )
                if scored_rows
                else None
            )
            entry["case_pass_rate"] = (
                sum(bool(row["objective"]["passed"]) for row in scored_rows)
                / len(scored_rows)
                if scored_rows
                else None
            )
        else:
            structured_rows = [
                row
                for row in model_rows
                if row["category"] != "tool_arguments"
                and row.get("status", "COMPLETED") == "COMPLETED"
            ]
            semantic_correct = sum(int(row["semantic_correct"]) for row in model_rows)
            semantic_total = sum(int(row["semantic_total"]) for row in model_rows)
            entry["json_schema_first_pass"] = (
                sum(
                    bool(
                        row["first_pass_success"]
                        and row["json_parse_ok"]
                        and row["schema_ok"]
                    )
                    for row in structured_rows
                )
                / len(structured_rows)
                if structured_rows
                else None
            )
            entry["semantic_accuracy"] = (
                semantic_correct / semantic_total if semantic_total else None
            )
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


async def run_metadata_preflight(
    *,
    suites: Sequence[str],
    output_dir: Path,
    profile: str,
    cap_policy: str = "fixed",
    per_model_cap_usd: float = DEFAULT_PER_MODEL_CAP_USD,
    cap_overrides: Mapping[str, float] | None = None,
) -> None:
    """Fetch exact pinned-endpoint metadata and cost caps without paid calls."""

    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    from scripts.model_battle_cases import validate_case_sets

    validate_case_sets()
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
        catalog = (
            await _fetch_pinned_catalog(
                client,
                all_models,
                suites=suites,
                profile=profile,
            )
            if profile in _HARD_PROFILES
            else await _fetch_catalog(client, all_models)
        )
    _write_json(output_dir / "model_catalog.json", catalog)
    _write_json(
        output_dir / "model_capabilities.json",
        catalog_capability_statuses(catalog, suites, profile=profile),
    )
    assert_catalog_capabilities(catalog, suites, profile=profile)
    for suite in suites:
        estimated_costs = estimate_model_costs(
            catalog,
            profile=profile,
            suite=suite,
        )
        _write_json(
            output_dir / f"{suite}_cost_preflight.json",
            build_cost_preflight(
                estimated_costs,
                resolve_model_caps(
                    estimated_costs,
                    policy=cap_policy,
                    default_cap=per_model_cap_usd,
                    overrides=cap_overrides,
                ),
                cap_policy=cap_policy,
            ),
        )


async def run_battle(
    *,
    suites: Sequence[str],
    output_dir: Path,
    repetitions: int,
    seed: int,
    profile: str = ORIGINAL_PROFILE,
    cap_policy: str = "fixed",
    per_model_cap_usd: float = DEFAULT_PER_MODEL_CAP_USD,
    cap_overrides: Mapping[str, float] | None = None,
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
    evidence_dir = plaintext_results_dir(output_dir)
    merged_manifest["plaintext_results_dir"] = str(Path("..") / evidence_dir.name)
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
        catalog = (
            await _fetch_pinned_catalog(
                client,
                all_models,
                suites=suites,
                profile=profile,
            )
            if profile in _HARD_PROFILES
            else await _fetch_catalog(client, all_models)
        )
        _write_json(
            output_dir / "model_capabilities.json",
            catalog_capability_statuses(catalog, suites, profile=profile),
        )
        assert_catalog_capabilities(catalog, suites, profile=profile)
        catalog_path = output_dir / "model_catalog.json"
        existing_catalog = (
            _read_json_object(catalog_path) if catalog_path.exists() else {}
        )
        _write_json(catalog_path, {**existing_catalog, **catalog})
        provider_orders = {
            model: list(order)
            for model, entry in catalog.items()
            if isinstance(entry, Mapping)
            and isinstance((order := entry.get("provider_order")), list)
        }
        provider_quantizations = {
            model: list(allowed)
            for model, entry in catalog.items()
            if isinstance(entry, Mapping)
            and isinstance((allowed := entry.get("provider_quantizations")), list)
        }
        for suite in suites:
            rows: list[dict[str, Any]] = []
            estimated_costs = estimate_model_costs(
                catalog,
                profile=profile,
                suite=suite,
            )
            model_caps = resolve_model_caps(
                estimated_costs,
                policy=cap_policy,
                default_cap=per_model_cap_usd,
                overrides=cap_overrides,
            )
            _write_json(
                output_dir / f"{suite}_cost_preflight.json",
                build_cost_preflight(
                    estimated_costs,
                    model_caps,
                    cap_policy=cap_policy,
                ),
            )
            cost_budget = RequestCostBudget(
                catalog=catalog,
                estimated_costs=estimated_costs,
                caps=model_caps,
            )
            round_zero_jobs = _build_jobs(
                suite=suite,
                repetitions=1 if profile in _HARD_PROFILES else repetitions,
                seed=seed,
                profile=profile,
                estimated_costs=estimated_costs,
            )
            jobs: list[tuple[str, Any, int]] = []
            exhausted_models: set[str] = set()
            cap_exhaustion: list[dict[str, Any]] = []

            def _record_exhaustion(
                exc: CostCapExhausted,
                *,
                stage: str,
                case_id: str,
                repetition: int,
                suite: str = suite,
                budget: RequestCostBudget = cost_budget,
                stopped: set[str] = exhausted_models,
                ledger: list[dict[str, Any]] = cap_exhaustion,
            ) -> None:
                """Stop one candidate on its own cap and keep the round running."""

                stopped.add(exc.model)
                ledger.append(
                    {
                        "model": exc.model,
                        "stage": stage,
                        "stopped_before_case_id": case_id,
                        "stopped_before_repetition": repetition,
                        "committed_usd": round(exc.committed, 12),
                        "cap_usd": round(exc.cap, 12),
                        "limit": exc.limit,
                        "reason": "CAP_EXHAUSTED",
                    }
                )
                budget.finish_candidate(exc.model)
                print(
                    f"[{suite} {stage}] {exc.model} stopped: {exc.limit} "
                    f"${exc.cap:.6f} reached with ${exc.committed:.6f} committed",
                    flush=True,
                )

            for index, (model, case, repetition) in enumerate(
                round_zero_jobs,
                start=1,
            ):
                if model in exhausted_models:
                    continue
                print(
                    f"[{suite} round-0 {index}/{len(round_zero_jobs)}] "
                    f"{case.case_id} rep={repetition} model={model}",
                    flush=True,
                )
                try:
                    if suite == "sales":
                        row = await _run_sales_case(
                            client,
                            model=model,
                            case=case,
                            repetition=repetition,
                            cost_budget=cost_budget,
                            provider_order=provider_orders.get(model),
                            provider_quantizations=provider_quantizations.get(model),
                        )
                    else:
                        row = await _run_system_case(
                            client,
                            model=model,
                            case=case,
                            repetition=repetition,
                            profile=profile,
                            cost_budget=cost_budget,
                            provider_order=provider_orders.get(model),
                            provider_quantizations=provider_quantizations.get(model),
                        )
                except CostCapExhausted as exc:
                    _record_exhaustion(
                        exc,
                        stage="round-0",
                        case_id=case.case_id,
                        repetition=repetition,
                    )
                    continue
                rows.append(row)
                jobs.append((model, case, repetition))
                _write_jsonl(evidence_dir / f"{suite}_results.jsonl", rows)
                enforce_model_cost_caps(rows, estimated_costs, model_caps)

            if profile in _HARD_PROFILES:
                survivor_jobs = build_survivor_jobs(
                    suite=suite,
                    profile=profile,
                    round_zero_rows=rows,
                    seed=seed,
                    estimated_costs=estimated_costs,
                )
                survivor_models = {model for model, _case, _rep in survivor_jobs}
                for eliminated_model in (
                    set(estimated_costs) - survivor_models - exhausted_models
                ):
                    cost_budget.finish_candidate(eliminated_model)
                for index, (model, case, repetition) in enumerate(
                    survivor_jobs,
                    start=1,
                ):
                    next_model = (
                        survivor_jobs[index][0] if index < len(survivor_jobs) else None
                    )
                    if model in exhausted_models:
                        continue
                    print(
                        f"[{suite} survivors {index}/{len(survivor_jobs)}] "
                        f"{case.case_id} rep={repetition} model={model}",
                        flush=True,
                    )
                    try:
                        if suite == "sales":
                            row = await _run_sales_case(
                                client,
                                model=model,
                                case=case,
                                repetition=repetition,
                                cost_budget=cost_budget,
                                provider_order=provider_orders.get(model),
                                provider_quantizations=provider_quantizations.get(
                                    model
                                ),
                            )
                        else:
                            row = await _run_system_case(
                                client,
                                model=model,
                                case=case,
                                repetition=repetition,
                                profile=profile,
                                cost_budget=cost_budget,
                                provider_order=provider_orders.get(model),
                                provider_quantizations=provider_quantizations.get(
                                    model
                                ),
                            )
                    except CostCapExhausted as exc:
                        _record_exhaustion(
                            exc,
                            stage="survivors",
                            case_id=case.case_id,
                            repetition=repetition,
                        )
                        continue
                    rows.append(row)
                    jobs.append((model, case, repetition))
                    _write_jsonl(evidence_dir / f"{suite}_results.jsonl", rows)
                    enforce_model_cost_caps(rows, estimated_costs, model_caps)
                    if next_model != model:
                        cost_budget.finish_candidate(model)
            else:
                for completed_model in set(estimated_costs) - exhausted_models:
                    cost_budget.finish_candidate(completed_model)

            _write_json(
                evidence_dir / f"{suite}_cap_exhaustion.json",
                {
                    "cap_policy": cap_policy,
                    "per_model_caps_usd": model_caps,
                    "stopped_candidates": cap_exhaustion,
                },
            )

            _write_json(
                evidence_dir / f"{suite}_aggregate.json",
                aggregate_rows(rows),
            )
            if suite == "sales":
                blind, reveal = _build_blind_files(
                    rows,
                    seed=seed,
                    profile=profile,
                )
                persist_blind_material(output_dir, blind, reveal)
            merged_manifest.setdefault("job_matrix", {})[suite] = [
                {
                    "model": model,
                    "case_id": case.case_id,
                    "repetition": repetition,
                }
                for model, case, repetition in jobs
            ]

    _write_json(manifest_path, merged_manifest)


def _parse_cap_overrides(values: Sequence[str]) -> dict[str, float]:
    overrides: dict[str, float] = {}
    for item in values:
        model, separator, raw_cap = item.partition("=")
        if not separator or not model.strip():
            raise SystemExit(f"--model-cap expects MODEL=USD, received {item!r}")
        try:
            overrides[model.strip()] = _finite_number(raw_cap, "Cap override")
        except RuntimeError as exc:
            raise SystemExit(f"--model-cap {item!r}: {exc}") from exc
    return overrides


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
        default=Path(".codex/stages/tj-ee5f/model-battle-results"),
    )
    parser.add_argument("--repetitions", type=int, default=3)
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
        "--preflight-only",
        action="store_true",
        help="Write exact provider capability and cost evidence without model calls.",
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
    parser.add_argument(
        "--cap-policy",
        choices=("fixed", "cover-estimate"),
        default="fixed",
        help=(
            "fixed keeps the accepted flat per-model cap; cover-estimate raises "
            "a cap only to that model's own worst-case estimate so the complete "
            "matrix can finish."
        ),
    )
    parser.add_argument(
        "--per-model-cap-usd",
        type=float,
        default=DEFAULT_PER_MODEL_CAP_USD,
        help="Default per-model USD cap before any policy or override.",
    )
    parser.add_argument(
        "--model-cap",
        action="append",
        default=[],
        metavar="MODEL=USD",
        help="Explicit per-model USD cap; repeatable.",
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
    cap_overrides = _parse_cap_overrides(args.model_cap)
    if args.preflight_only:
        asyncio.run(
            run_metadata_preflight(
                suites=suites,
                output_dir=args.output_dir,
                profile=args.profile,
                cap_policy=args.cap_policy,
                per_model_cap_usd=args.per_model_cap_usd,
                cap_overrides=cap_overrides,
            )
        )
        return
    asyncio.run(
        run_battle(
            suites=suites,
            output_dir=args.output_dir,
            repetitions=args.repetitions,
            seed=args.seed,
            profile=args.profile,
            cap_policy=args.cap_policy,
            per_model_cap_usd=args.per_model_cap_usd,
            cap_overrides=cap_overrides,
        )
    )


if __name__ == "__main__":
    main()
