"""Run the frozen real-opening set through Luna outside Git, and score it.

The judge is the orchestrator itself, reading blind: `run` stops after the
twenty generation calls and writes `reading-pack.json`, and `ingest-judgment`
takes the reading back. `preflight --second-reader` adds a paid model beside
that reading, never in place of it.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import pathlib
import random
import re
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict
from scripts.model_battle import (
    _extract_asserted_numeric_tokens,
    _fetch_catalog,
    _language_matches,
    build_base_payload,
    build_pinned_catalog_entry,
    conservative_input_token_bound,
    derive_quotation_arithmetic,
    parse_json_content,
)

from src.core.config import settings
from src.dialogue.state import DialogueState
from src.integrations.catalog.treejar_catalog import TreejarCatalogClient
from src.llm.communication_policy import (
    COMMUNICATION_RULES_POLICY,
    finalize_evidence_grounding_prompt,
)
from src.llm.grounding_output import enforce_grounding_output
from src.llm.opening_guard import apply_opening_guard
from src.llm.prompts import BASE_SYSTEM_PROMPT, LANGUAGE_DIRECTIVE, STAGE_RULES
from src.llm.sales_turn_guard import commit_to_what_you_deferred
from src.models.conversation import Conversation
from src.models.message import Message
from src.quality.evaluator import (
    EVALUATION_PROMPT,
    RED_FLAG_PROMPT,
    _build_applicability_assessment,
    _format_applicability_instructions,
)
from src.quality.schemas import (
    EvaluationResult,
    RedFlagEvaluationResult,
    attainable_weighted_score,
    finalize_evaluation_result,
    raw_total,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
GENERATOR_MODEL = "openai/gpt-5.6-luna"
SECOND_READER_MODEL = "z-ai/glm-5.2"
# The owner's standing decision, 2026-08-10 and reaffirmed 2026-08-11: the
# result judge is the orchestrator itself, reading blind. A paid model may be
# added beside it as a second reader, never in place of it. That is why the
# root judge is the default here and `--second-reader` is the thing you have to
# ask for: a deterministic guarantee beats a directive.
ROOT_JUDGE = "root-orchestrator"
GENERATOR_MAX_TOKENS = 1400
JUDGE_MAX_TOKENS = 4000
EXPECTED_OPENINGS = 20
SELECTION_SEED = 20260810
DEFAULT_MODEL_CAP_USD = 1.0
BOOTSTRAP_SEED = 20260810
BOOTSTRAP_SAMPLES = 10_000
_BROAD_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


class CombinedJudgeResult(BaseModel):
    """One GLM call returns the frozen final rubric and critical red flags."""

    model_config = ConfigDict(extra="forbid")

    evaluation: EvaluationResult
    red_flags: RedFlagEvaluationResult


def ensure_protected_output(
    path: pathlib.Path, *, repo_root: pathlib.Path
) -> pathlib.Path:
    root = repo_root.resolve()
    resolved = path.resolve()
    git_metadata = (root / ".git").resolve()
    inside_root = resolved == root or root in resolved.parents
    inside_git_metadata = resolved == git_metadata or git_metadata in resolved.parents
    if inside_root and not inside_git_metadata:
        raise ValueError("transcript-bearing output must stay outside the repository")
    if path.is_symlink():
        raise ValueError("protected output must not be a symlink")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.chmod(0o700)
    return resolved


def validate_complete_results(
    results: list[dict[str, object]],
    *,
    expected_dialog_ids: set[int],
    require_acceptance: bool = True,
) -> None:
    dialog_ids = [int(item["dialog_id"]) for item in results]
    if (
        len(dialog_ids) != len(set(dialog_ids))
        or set(dialog_ids) != expected_dialog_ids
    ):
        raise ValueError("results must contain exactly the frozen dialog ids once")
    for item in results:
        if item.get("generator_model") != "openai/gpt-5.6-luna":
            raise ValueError("every result must come from Luna")
        if item.get("judge_model") not in {SECOND_READER_MODEL, ROOT_JUDGE}:
            raise ValueError("every result must be scored by the root judge or GLM")
        if not str(item.get("response") or "").strip():
            raise ValueError("every frozen opening needs a non-empty Luna response")
        failures = item.get("critical_failures")
        if not isinstance(failures, list):
            raise ValueError("critical failures must be a list")
        if failures and require_acceptance:
            raise ValueError("critical failures cannot be averaged away")
        if item.get("language_ok") is not True:
            raise ValueError("every response must match the customer language")
        for key in (
            "weighted_score",
            "raw_total",
            "latency_ms",
            "luna_latency_ms",
            "glm_latency_ms",
            "prompt_tokens",
            "completion_tokens",
            "cost_micro_usd",
        ):
            value = item.get(key)
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")


def _nearest_percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * quantile)]


def _stratified_interval(
    results: list[dict[str, object]],
    *,
    samples: int,
    seed: int,
    value_key: str = "weighted_score",
) -> tuple[float, float, float]:
    by_stratum: dict[int, list[float]] = {}
    for item in results:
        by_stratum.setdefault(int(item["length_stratum"]), []).append(
            float(item[value_key])
        )
    mean = statistics.fmean(score for scores in by_stratum.values() for score in scores)
    if samples <= 0:
        return mean, mean, mean
    rng = random.Random(seed)
    estimates = [
        statistics.fmean(
            rng.choice(scores)
            for scores in by_stratum.values()
            for _ in range(len(scores))
        )
        for _ in range(samples)
    ]
    return (
        mean,
        _nearest_percentile(estimates, 0.025),
        _nearest_percentile(estimates, 0.975),
    )


def _stratified_median_interval(
    results: list[dict[str, object]], *, samples: int, seed: int
) -> tuple[float, float, float]:
    by_stratum: dict[int, list[float]] = {}
    for item in results:
        by_stratum.setdefault(int(item["length_stratum"]), []).append(
            float(item["luna_latency_ms"])
        )
    observed = statistics.median(
        value for values in by_stratum.values() for value in values
    )
    if samples <= 0:
        return observed, observed, observed
    rng = random.Random(seed)
    estimates = [
        statistics.median(
            rng.choice(values)
            for values in by_stratum.values()
            for _ in range(len(values))
        )
        for _ in range(samples)
    ]
    return (
        observed,
        _nearest_percentile(estimates, 0.025),
        _nearest_percentile(estimates, 0.975),
    )


# Frozen 2026-08-10 under `tj-vz7o.10.2`, before any rerun.
#
# The round before this one pre-registered "the lower bound of the weighted
# interval reaches 20.0/30" and the applicability maps then showed that eleven
# of the twenty openings have a deterministic ceiling of 9.6/30. The gate was
# unreachable by arithmetic rather than by quality, and it failed honestly
# instead of being lowered afterwards.
#
# The replacement states no absolute score at all, and that is the point. Two
# facts make an absolute level meaningless on this set: the openings have
# different ceilings, so their mean is an average of incommensurable numbers;
# and the judge is GLM, which does not bridge to the client's `claude-haiku-4.5`
# on any published figure. What survives both is a paired comparison of the same
# twenty openings, same judge, one build against another -- which is what
# `score_uncertainty.py` has enforced for the normalised axis all along.
ACCEPTANCE_CONTRACT: dict[str, Any] = {
    "frozen_on": "2026-08-10",
    "beads": "tj-vz7o.10.2",
    "required": [
        "20/20 non-empty Luna responses",
        "20/20 valid GLM evaluations",
        "20/20 responses in the customer's language",
        "zero critical failures: a fabricated figure is a defect at any score",
    ],
    "score_rule": (
        "No absolute /30 threshold. Report the score beside the attainable "
        "ceiling for that opening, and decide a build by a paired delta against "
        "the stored baseline over the same twenty openings and the same judge."
    ),
    "forbidden": [
        "an aggregate level quoted across openings with different ceilings",
        "any comparison with the client's figure: a different judge read it",
    ],
}


def _ceiling_bands(results: list[dict[str, object]]) -> list[dict[str, Any]]:
    """One row per attainable ceiling, because their mean is not a level.

    Eleven of the twenty openings top out at 9.6/30 and nine can reach 30.0.
    Averaging them produces a number no opening could have scored.
    """

    bands: dict[int, list[float]] = {}
    for item in results:
        ceiling = round(float(item.get("attainable_score") or 0.0) * 10)
        bands.setdefault(ceiling, []).append(float(item["weighted_score"]))
    return [
        {
            "attainable_tenths": ceiling,
            "openings": len(scores),
            "mean_tenths": round(statistics.fmean(scores) * 10),
            "share_of_ceiling_percent": (
                round(statistics.fmean(scores) / (ceiling / 10) * 100) if ceiling else 0
            ),
        }
        for ceiling, scores in sorted(bands.items())
    ]


def build_public_summary(
    results: list[dict[str, object]], *, bootstrap_samples: int, seed: int
) -> dict[str, Any]:
    if len(results) != 20:
        raise ValueError("public acceptance summary requires exactly 20 openings")
    expected = {int(item["dialog_id"]) for item in results}
    validate_complete_results(
        results,
        expected_dialog_ids=expected,
        require_acceptance=False,
    )
    mean, low, high = _stratified_interval(
        results, samples=bootstrap_samples, seed=seed
    )
    raw_mean, raw_low, raw_high = _stratified_interval(
        results,
        samples=bootstrap_samples,
        seed=seed,
        value_key="raw_total",
    )
    latency_median, latency_low, latency_high = _stratified_median_interval(
        results,
        samples=bootstrap_samples,
        seed=seed,
    )
    rows = [
        {
            "dialog_id": int(item["dialog_id"]),
            "length_stratum": int(item["length_stratum"]),
            "weighted_score_tenths": round(float(item["weighted_score"]) * 10),
            "raw_total": int(item["raw_total"]),
            "critical_failure_count": len(item["critical_failures"]),
            "critical_failure_codes": sorted(
                str(code) for code in item["critical_failures"]
            ),
            "language_ok": bool(item["language_ok"]),
            "latency_ms": int(item["latency_ms"]),
            "luna_latency_ms": int(item["luna_latency_ms"]),
            "glm_latency_ms": int(item["glm_latency_ms"]),
            "prompt_tokens": int(item["prompt_tokens"]),
            "completion_tokens": int(item["completion_tokens"]),
            "cost_micro_usd": int(item["cost_micro_usd"]),
        }
        for item in sorted(results, key=lambda row: int(row["dialog_id"]))
    ]
    critical_failure_count = sum(len(item["critical_failures"]) for item in results)
    low_tenths = round(low * 10)
    ceilings = _ceiling_bands(results)
    return {
        "schema_version": "treejar-real-opening-acceptance-public/v1",
        "generation_model": "openai/gpt-5.6-luna",
        "judge_model": "z-ai/glm-5.2",
        "coverage": {
            "frozen_openings": 20,
            "luna_responses": len(results),
            "glm_evaluations": len(results),
            "critical_failures": critical_failure_count,
        },
        "weighted_score_tenths": {
            "mean": round(mean * 10),
            "ci95_low": round(low * 10),
            "ci95_high": round(high * 10),
        },
        "raw_total_tenths": {
            "openings": len(results),
            "mean": round(raw_mean * 10),
            "ci95_low": round(raw_low * 10),
            "ci95_high": round(raw_high * 10),
        },
        "luna_time_to_first_reply_ms": {
            "responses": len(results),
            "median": round(latency_median),
            "ci95_low": round(latency_low),
            "ci95_high": round(latency_high),
        },
        "ceiling_bands": ceilings,
        "acceptance": ACCEPTANCE_CONTRACT
        | {
            "coverage_complete": len(results) == EXPECTED_OPENINGS,
            "critical_failure_count": critical_failure_count,
            "accepted": critical_failure_count == 0
            and len(results) == EXPECTED_OPENINGS,
            "score_verdict": "paired_comparison_required",
            "observed_ci95_low_tenths": low_tenths,
        },
        "bootstrap": {"samples": bootstrap_samples, "seed": seed},
        "scenarios": rows,
    }


def estimate_cost_usd(
    *,
    calls: int,
    max_input_tokens: int,
    max_output_tokens: int,
    prompt_price: float,
    completion_price: float,
) -> float:
    values = (
        calls,
        max_input_tokens,
        max_output_tokens,
        prompt_price,
        completion_price,
    )
    if any(isinstance(value, bool) for value in values) or any(
        not math.isfinite(float(value)) or float(value) < 0 for value in values
    ):
        raise ValueError("cost inputs must be finite and non-negative")
    return calls * (
        max_input_tokens * prompt_price + max_output_tokens * completion_price
    )


def expected_language(text: str) -> str:
    return (
        "ar" if any("\u0600" <= character <= "\u06ff" for character in text) else "en"
    )


def build_generation_messages(
    *, opening: str, language: str, catalog_evidence: list[dict[str, object]]
) -> list[dict[str, str]]:
    language_name = "Arabic" if language == "ar" else "English"
    evidence = json.dumps(
        catalog_evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    harness_contract = (
        "[ISOLATED ACCEPTANCE RUN]\n"
        "Do not call tools in this isolated acceptance run. The harness has "
        "already performed the read-only catalog lookup. Treat the evidence "
        "below as the complete result of search_products for this turn. Use "
        "only facts present there; if it is empty, ask one useful clarification "
        "and do not invent a product, price, stock, delivery, or commitment.\n\n"
        f"[READ-ONLY CATALOG EVIDENCE]\n{evidence}"
    )
    system = finalize_evidence_grounding_prompt(
        "\n\n".join(
            (
                BASE_SYSTEM_PROMPT.strip(),
                COMMUNICATION_RULES_POLICY.strip(),
                LANGUAGE_DIRECTIVE.format(language=language_name).strip(),
                STAGE_RULES["greeting"].strip(),
                harness_contract,
            )
        )
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": opening},
    ]


def apply_shipped_output_guards(
    raw_content: str,
    *,
    language: str,
    anchor_line: str | None,
    catalog_evidence: object,
) -> str:
    """Everything production would do to this text before the customer sees it.

    The 2026-08-10 round applied `apply_opening_guard` and stopped, so it
    measured the model plus one guard rather than the reply that would actually
    be sent. Neither failure it found was caused by that gap -- both survive the
    full pipeline, which is why they were real -- but a round that reports a
    defect production would have filtered is a round that sends us to fix
    nothing, and it cannot be told apart from a real one after the fact.

    `is_first_turn=True` and `customer_name=None` are properties of the frozen
    set: every case is one customer opening with no prior conversation.
    """

    text = apply_opening_guard(
        raw_content,
        language=language,
        is_first_turn=True,
        customer_name=None,
        anchor_line=anchor_line,
    )
    text = commit_to_what_you_deferred(text, language=language)
    grounded: list[object] = []
    if isinstance(catalog_evidence, list):
        for product in catalog_evidence:
            if isinstance(product, dict) and product.get("price_aed") is not None:
                grounded.append(product["price_aed"])
    return enforce_grounding_output(
        text,
        language=language,
        grounded_amounts=grounded,
    ).text


def catalog_matches(
    query: str, products: list[dict[str, object]], *, limit: int
) -> list[dict[str, object]]:
    if limit <= 0:
        return []
    stopwords = {
        "and",
        "for",
        "from",
        "have",
        "hello",
        "need",
        "please",
        "the",
        "want",
        "with",
        "you",
    }
    terms = {
        token
        for token in re.findall(r"[\w-]+", query.casefold())
        if len(token) >= 3 and token not in stopwords
    }
    if not terms:
        return []
    phrase = " ".join(query.casefold().split())
    ranked: list[tuple[int, str, dict[str, object]]] = []
    for product in products:
        haystack = " ".join(
            str(product.get(key) or "")
            for key in ("name", "name_en", "sku", "slug", "category", "description")
        ).casefold()
        score = sum(1 for term in terms if term in haystack)
        if phrase and phrase in haystack:
            score += len(terms)
        if score:
            ranked.append((score, str(product.get("sku") or ""), product))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:limit]]


def critical_failure_codes(
    *,
    red_flag_codes: list[str],
    ungrounded_numbers: list[str],
    language_ok: bool,
) -> list[str]:
    mapped = {
        "bad_tone": "bad_tone",
        "hard_deflection": "hard_deflection",
        "ignored_question": "ignored_request",
        "missing_identity": "missing_identity",
        "unverified_commitment": "unsafe_commitment",
    }
    failures = {mapped[code] for code in red_flag_codes if code in mapped}
    if ungrounded_numbers:
        failures.add("hallucination")
    if not language_ok:
        failures.add("wrong_language")
    order = (
        "hallucination",
        "ignored_request",
        "unsafe_commitment",
        "wrong_language",
        "hard_deflection",
        "missing_identity",
        "bad_tone",
    )
    return [code for code in order if code in failures]


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_protected_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.parent.chmod(0o700)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    os.replace(temporary, path)
    path.chmod(0o600)


def _read_object(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _load_frozen_scenarios(path: pathlib.Path) -> list[dict[str, Any]]:
    payload = _read_object(path)
    if payload.get("schema_version") != "treejar-real-openings/v1":
        raise ValueError("unexpected frozen opening schema")
    if payload.get("selection_seed") != SELECTION_SEED:
        raise ValueError(f"frozen set must record selection seed {SELECTION_SEED}")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != EXPECTED_OPENINGS:
        raise ValueError("frozen set must contain exactly 20 openings")
    rows: list[dict[str, Any]] = []
    for item in scenarios:
        if not isinstance(item, dict):
            raise ValueError("frozen scenario must be an object")
        opening = item.get("opening")
        if not isinstance(opening, str) or not opening.strip():
            raise ValueError("frozen scenario opening must be non-empty text")
        rows.append(dict(item))
    dialog_ids = [int(item["dialog_id"]) for item in rows]
    if len(set(dialog_ids)) != EXPECTED_OPENINGS:
        raise ValueError("frozen dialog ids must be unique")
    stratum_counts = {
        stratum: sum(int(item["length_stratum"]) == stratum for item in rows)
        for stratum in range(1, 5)
    }
    if stratum_counts != {1: 5, 2: 5, 3: 5, 4: 5}:
        raise ValueError("frozen set must contain five openings in each length stratum")
    return rows


def _flatten_categories(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for category in categories:
        flattened.append(category)
        children = category.get("children")
        if isinstance(children, list):
            flattened.extend(
                _flatten_categories(
                    [item for item in children if isinstance(item, dict)]
                )
            )
    return flattened


async def _fetch_catalog_summaries() -> list[dict[str, Any]]:
    products: dict[str, dict[str, Any]] = {}
    async with TreejarCatalogClient() as client:
        categories = _flatten_categories(await client.get_categories())
        for category in categories:
            slug = category.get("slug")
            if not isinstance(slug, str) or not slug.strip():
                continue
            offset = 0
            while True:
                page = await client.get_category_products(
                    slug, limit=settings.catalog_api_page_size, offset=offset
                )
                rows = page["products"]
                for raw in rows:
                    row = dict(raw)
                    row.setdefault("category", str(category.get("name") or slug))
                    key = str(row.get("sku") or row.get("slug") or "").strip()
                    if key:
                        products[key.casefold()] = row
                if not page["hasMore"] or not rows:
                    break
                offset += len(rows)
    return [products[key] for key in sorted(products)]


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value.replace(",", "").strip())
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _catalog_projection(product: dict[str, object]) -> dict[str, object]:
    projected: dict[str, object] = {}
    aliases = {
        "name": ("name", "name_en", "title"),
        "sku": ("sku",),
        "slug": ("slug",),
        "category": ("category", "category_name"),
        "price_aed": ("price", "sale_price", "regular_price"),
        "stock": ("stock", "stock_quantity", "quantity"),
    }
    for target, sources in aliases.items():
        value = next(
            (
                product.get(source)
                for source in sources
                if product.get(source) is not None
            ),
            None,
        )
        if target in {"price_aed", "stock"}:
            numeric = _number(value)
            if numeric is not None:
                projected[target] = round(numeric, 2)
        elif isinstance(value, str) and value.strip():
            projected[target] = " ".join(value.split())[:240]
    return projected


def _anchor_line(products: list[dict[str, object]], language: str) -> str | None:
    families = (
        (("chair",), "Chairs", "الكراسي"),
        (("desk", "workstation"), "desks and workstations", "المكاتب ومحطات العمل"),
    )
    parts: list[str] = []
    for terms, english, arabic in families:
        prices: list[float] = []
        for product in products:
            name = str(product.get("name") or product.get("name_en") or "").casefold()
            price = _number(product.get("price"))
            stock = _number(product.get("stock"))
            if (
                any(term in name for term in terms)
                and price is not None
                and price > 0
                and stock is not None
                and stock >= 5
            ):
                prices.append(price)
        if not prices:
            continue
        amount = f"{min(prices):,.0f}"
        parts.append(
            f"{arabic} من {amount} درهم"
            if language == "ar"
            else f"{english} from AED {amount}"
        )
    return (", ".join(parts) + ".") if parts else None


def _provider_headers(title: str) -> dict[str, str]:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://noor.starec.ai",
        "X-Title": title,
    }


async def _pinned_model_catalog(
    models: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url.rstrip("/"),
        headers=_provider_headers("Noor Real Opening Acceptance Preflight"),
    ) as client:
        catalog = await _fetch_catalog(client, models)
        pinned: dict[str, dict[str, Any]] = {}
        requirements = {
            GENERATOR_MODEL: {"max_tokens", "reasoning"},
            SECOND_READER_MODEL: {"max_tokens", "response_format"},
        }
        for model in models:
            response = await client.get(f"/models/{model}/endpoints", timeout=30.0)
            response.raise_for_status()
            pinned[model] = build_pinned_catalog_entry(
                model,
                catalog[model],
                response.json(),
                required_parameters=requirements[model],
            )
    return pinned


def _pricing(catalog: dict[str, dict[str, Any]], model: str) -> tuple[float, float]:
    pricing = catalog[model].get("pricing")
    if not isinstance(pricing, dict):
        raise ValueError(f"{model}: pricing missing from provider preflight")
    prompt = _number(pricing.get("prompt"))
    completion = _number(pricing.get("completion"))
    if prompt is None or completion is None:
        raise ValueError(f"{model}: invalid provider pricing")
    return prompt, completion


def _judge_system_prompt() -> str:
    schema = json.dumps(
        CombinedJudgeResult.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
    )
    return (
        "Complete two independent assessments of the same opening exchange.\n\n"
        "For the `evaluation` object follow these frozen instructions exactly:\n"
        f"{EVALUATION_PROMPT}\n\n"
        "For the `red_flags` object follow these frozen instructions exactly:\n"
        f"{RED_FLAG_PROMPT}\n\n"
        "Return one JSON object with exactly the keys `evaluation` and "
        "`red_flags`. It must conform to this schema:\n"
        f"{schema}"
    )


def _prepare_cases(
    scenarios: list[dict[str, Any]], products: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for scenario in scenarios:
        opening = str(scenario["opening"])
        language = expected_language(opening)
        matches = catalog_matches(opening, products, limit=3)
        evidence = [
            projection for item in matches if (projection := _catalog_projection(item))
        ]
        messages = build_generation_messages(
            opening=opening,
            language=language,
            catalog_evidence=evidence,
        )
        cases.append(
            {
                "dialog_id": int(scenario["dialog_id"]),
                "length_stratum": int(scenario["length_stratum"]),
                "opening": opening,
                "language": language,
                "catalog_evidence": evidence,
                "catalog_relevant": bool(evidence),
                "anchor_line": _anchor_line(products, language),
                "generation_messages": messages,
                "generation_prompt_digest": _sha256_json(messages),
            }
        )
    return cases


async def preflight(
    *,
    scenarios_path: pathlib.Path,
    output_dir: pathlib.Path,
    per_model_cap_usd: float,
    second_reader: bool = False,
) -> dict[str, Any]:
    output_dir = ensure_protected_output(output_dir, repo_root=REPO_ROOT)
    if (output_dir / "preflight.json").exists():
        raise ValueError(f"preflight already exists: {output_dir}")
    scenarios = _load_frozen_scenarios(scenarios_path)
    judge_model = SECOND_READER_MODEL if second_reader else ROOT_JUDGE
    models = (
        (GENERATOR_MODEL, SECOND_READER_MODEL) if second_reader else (GENERATOR_MODEL,)
    )
    catalog, products = await asyncio.gather(
        _pinned_model_catalog(models), _fetch_catalog_summaries()
    )
    if not products:
        raise ValueError("read-only catalog preflight returned no products")
    cases = _prepare_cases(scenarios, products)

    generator_input_bound = max(
        conservative_input_token_bound({"messages": case["generation_messages"]})
        for case in cases
    )
    judge_input_bound = conservative_input_token_bound(
        {
            "system": _judge_system_prompt(),
            "maximum_opening_bytes": max(
                len(str(case["opening"]).encode("utf-8")) for case in cases
            ),
            "maximum_luna_response_bytes": 24_000,
        }
    )
    generator_prices = _pricing(catalog, GENERATOR_MODEL)
    estimates = {
        GENERATOR_MODEL: estimate_cost_usd(
            calls=EXPECTED_OPENINGS,
            max_input_tokens=generator_input_bound,
            max_output_tokens=GENERATOR_MAX_TOKENS,
            prompt_price=generator_prices[0],
            completion_price=generator_prices[1],
        ),
    }
    if second_reader:
        judge_prices = _pricing(catalog, SECOND_READER_MODEL)
        estimates[SECOND_READER_MODEL] = estimate_cost_usd(
            calls=EXPECTED_OPENINGS,
            max_input_tokens=judge_input_bound,
            max_output_tokens=JUDGE_MAX_TOKENS,
            prompt_price=judge_prices[0],
            completion_price=judge_prices[1],
        )
    too_expensive = {
        model: estimate
        for model, estimate in estimates.items()
        if estimate > per_model_cap_usd
    }
    if too_expensive:
        raise ValueError(
            "preflight exceeds per-model cap: "
            + ", ".join(
                f"{model}=${estimate:.6f}" for model, estimate in too_expensive.items()
            )
        )
    public_catalog = {
        model: {
            "id": entry.get("id"),
            "pricing": entry.get("pricing"),
            "pinned_provider": entry.get("pinned_provider"),
            "first_party_available": entry.get("first_party_available"),
            "provider_order": entry.get("provider_order"),
            "provider_quantizations": entry.get("provider_quantizations"),
            "supported_parameters": entry.get("supported_parameters"),
        }
        for model, entry in catalog.items()
    }
    document = {
        "schema_version": "treejar-real-opening-preflight/v1",
        "created_at": datetime.now(UTC).isoformat(),
        "scenario_count": len(cases),
        "scenario_digest": _sha256_json(
            [
                {
                    "dialog_id": case["dialog_id"],
                    "opening": case["opening"],
                    "length_stratum": case["length_stratum"],
                }
                for case in cases
            ]
        ),
        "generation_model": GENERATOR_MODEL,
        "judge_model": judge_model,
        "calls_per_model": EXPECTED_OPENINGS,
        "estimated_cost_usd": estimates,
        "per_model_cap_usd": {
            model: (0.0 if model == ROOT_JUDGE else per_model_cap_usd)
            for model in (GENERATOR_MODEL, judge_model)
        },
        "input_token_upper_bounds": {
            GENERATOR_MODEL: generator_input_bound,
            judge_model: (0 if judge_model == ROOT_JUDGE else judge_input_bound),
        },
        "model_catalog": public_catalog,
        "catalog_products": len(products),
        "paid_calls_made": 0,
    }
    _write_protected_json(output_dir / "prepared-cases.json", cases)
    _write_protected_json(output_dir / "catalog-cache.json", products)
    _write_protected_json(output_dir / "preflight.json", document)
    return document


async def _request_once(
    client: httpx.AsyncClient, payload: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    started = time.perf_counter()
    response = await client.post("/chat/completions", json=payload, timeout=300.0)
    latency_ms = round((time.perf_counter() - started) * 1000)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("provider returned a non-object response")
    return body, latency_ms


def _message_content(body: dict[str, Any]) -> tuple[str, str | None]:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("provider response has no choice")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("provider response choice has no message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("provider returned an empty response")
    finish_reason = choice.get("finish_reason")
    return content.strip(), str(finish_reason) if finish_reason is not None else None


def _usage(body: dict[str, Any]) -> dict[str, int]:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0, "cost_micro_usd": 0}
    cost = _number(usage.get("cost")) or 0.0
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "cost_micro_usd": round(cost * 1_000_000),
    }


def _provider_route(
    preflight_doc: dict[str, Any], model: str
) -> tuple[list[str], list[str]]:
    catalog = preflight_doc["model_catalog"][model]
    order = catalog.get("provider_order")
    quantizations = catalog.get("provider_quantizations")
    return (
        [str(item) for item in order] if isinstance(order, list) else [],
        [str(item) for item in quantizations]
        if isinstance(quantizations, list)
        else [],
    )


def _assessment(
    *, opening: str, response: str, language: str, catalog_relevant: bool
) -> Any:
    conversation_id = uuid.uuid4()
    state = DialogueState(
        active_flow="catalog" if catalog_relevant else None,
        sales_stage="greeting",
    )
    conversation = Conversation(
        id=conversation_id,
        phone="protected-acceptance",
        language=language,
        sales_stage="greeting",
        metadata_=state.to_metadata(),
    )
    messages = [
        Message(
            conversation_id=conversation_id,
            role="user",
            content=opening,
            message_type="text",
        ),
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=response,
            message_type="text",
        ),
    ]
    return _build_applicability_assessment(messages, "greeting", conversation)


def _judge_messages(
    *, opening: str, response: str, language: str, assessment: Any
) -> list[dict[str, str]]:
    transcript = f"Customer: {opening}\nNoor: {response}"
    user = (
        f"{_format_applicability_instructions(assessment.rule_applicability)}\n\n"
        "Current sales stage: greeting\n\n"
        f"Conversation language: {language}\n\n"
        f"Conversation:\n{transcript}"
    )
    return [
        {"role": "system", "content": _judge_system_prompt()},
        {"role": "user", "content": user},
    ]


def _reading_entry(
    case: dict[str, Any], response: str, assessment: Any
) -> dict[str, Any]:
    """One opening exchange, prepared for the root judge to read blind.

    It carries exactly what the second reader would have been sent -- the same
    applicability instructions and the same frozen rubric text -- so the two
    judges are answering the same question when both are used.
    """

    return {
        "dialog_id": int(case["dialog_id"]),
        "length_stratum": int(case["length_stratum"]),
        "language": str(case["language"]),
        "opening": str(case["opening"]),
        "response": response,
        "applicability_instructions": _format_applicability_instructions(
            assessment.rule_applicability
        ),
        "rule_applicability": dict(assessment.rule_applicability),
        "blocking_reasons": dict(assessment.blocking_reasons),
    }


def ingest_root_judgment(
    output_dir: pathlib.Path, judgments_path: pathlib.Path
) -> dict[str, Any]:
    """Record the root judge's blind reading as this round's evaluation.

    The judgment file is a JSON array of objects shaped exactly like the second
    reader's reply -- `dialog_id`, `evaluation`, `red_flags` -- so the scoring,
    the applicability finalisation, and the critical-failure derivation below
    are the same code either way. Nothing here makes a model call.
    """

    output_dir = ensure_protected_output(output_dir, repo_root=REPO_ROOT)
    preflight_doc = _read_object(output_dir / "preflight.json")
    if str(preflight_doc["judge_model"]) != ROOT_JUDGE:
        raise ValueError("this round was preflighted for a paid second reader")
    cases_doc = json.loads(
        (output_dir / "prepared-cases.json").read_text(encoding="utf-8")
    )
    cases = {int(case["dialog_id"]): case for case in cases_doc}
    state_path = output_dir / "run-state.json"
    state = _read_object(state_path)
    records = state["records"]
    payload = json.loads(judgments_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or len(payload) != EXPECTED_OPENINGS:
        raise ValueError(f"expected {EXPECTED_OPENINGS} judgments")
    seen: set[int] = set()
    for item in payload:
        dialog_id = int(item["dialog_id"])
        if dialog_id in seen or dialog_id not in cases:
            raise ValueError(f"judgment {dialog_id} is duplicated or unknown")
        seen.add(dialog_id)
        case = cases[dialog_id]
        record = records[str(dialog_id)]
        response_text = str(record["generation"]["content"])
        assessment = _assessment(
            opening=str(case["opening"]),
            response=response_text,
            language=str(case["language"]),
            catalog_relevant=bool(case["catalog_relevant"]),
        )
        combined = CombinedJudgeResult.model_validate(
            {"evaluation": item["evaluation"], "red_flags": item["red_flags"]}
        )
        evaluation = finalize_evaluation_result(
            combined.evaluation,
            applicability_map=assessment.rule_applicability,
            diagnostic_blockers=assessment.blocking_reasons,
            applicability_signals=assessment.signals,
        )
        language_ok = _language_matches(response_text, str(case["language"]))
        ungrounded = find_ungrounded_numbers(response_text, case)
        record["judge"] = {
            "model": ROOT_JUDGE,
            "provider_model": None,
            "finish_reason": "stop",
            "latency_ms": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_micro_usd": 0,
            "evaluation": evaluation.model_dump(mode="json"),
            "red_flags": combined.red_flags.model_dump(mode="json"),
            "ungrounded_numbers": ungrounded,
            "language_ok": language_ok,
            "critical_failures": critical_failure_codes(
                red_flag_codes=[flag.code for flag in combined.red_flags.flags],
                ungrounded_numbers=ungrounded,
                language_ok=language_ok,
            ),
            "raw_verdict": None,
        }
    public = _analyze_completed_state(
        preflight_doc=preflight_doc,
        cases_doc=cases_doc,
        state=state,
    )
    state["completed_at"] = datetime.now(UTC).isoformat()
    state["public_summary"] = public
    state["actual_cost_usd"] = _actual_cost_by_model(state, ROOT_JUDGE)
    _write_protected_json(state_path, state)
    _write_protected_json(output_dir / "analysis.json", public)
    return public


def _canonical_numeric_token(token: str) -> str:
    cleaned = token.rstrip("%").replace(",", "")
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return cleaned
    if not number.is_finite():
        return cleaned
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _allowed_numbers(case: dict[str, Any]) -> set[str]:
    evidence_values = [str(case["opening"]), str(case.get("anchor_line") or "")]
    catalog_evidence = case.get("catalog_evidence")
    if isinstance(catalog_evidence, list):
        for product in catalog_evidence:
            if not isinstance(product, dict):
                continue
            evidence_values.extend(
                str(product[key])
                for key in ("name", "price_aed", "stock")
                if product.get(key) is not None
            )
    direct = {
        _canonical_numeric_token(token)
        for value in evidence_values
        for token in _BROAD_NUMBER_RE.findall(value)
    }
    return derive_quotation_arithmetic(direct)


def find_ungrounded_numbers(response: str, case: dict[str, Any]) -> list[str]:
    asserted = {
        _canonical_numeric_token(token)
        for token in _extract_asserted_numeric_tokens(response)
    }
    return sorted(asserted - _allowed_numbers(case))


def _actual_cost_by_model(
    state: dict[str, Any], judge_model: str = SECOND_READER_MODEL
) -> dict[str, float]:
    totals = {GENERATOR_MODEL: 0.0, judge_model: 0.0}
    records = state.get("records")
    if not isinstance(records, dict):
        return totals
    for record in records.values():
        if not isinstance(record, dict):
            continue
        generation = record.get("generation")
        judge = record.get("judge")
        if isinstance(generation, dict):
            totals[GENERATOR_MODEL] += (
                int(generation.get("cost_micro_usd") or 0) / 1_000_000
            )
        if isinstance(judge, dict):
            totals[judge_model] += int(judge.get("cost_micro_usd") or 0) / 1_000_000
    return totals


def _enforce_actual_caps(state: dict[str, Any], preflight_doc: dict[str, Any]) -> None:
    actual = _actual_cost_by_model(state, str(preflight_doc["judge_model"]))
    caps = preflight_doc["per_model_cap_usd"]
    exceeded = [
        f"{model}: ${cost:.6f} > ${float(caps[model]):.6f}"
        for model, cost in actual.items()
        if cost > float(caps[model]) + 1e-12
    ]
    if exceeded:
        raise RuntimeError("actual model cost cap exceeded: " + "; ".join(exceeded))


def _analyze_completed_state(
    *,
    preflight_doc: dict[str, Any],
    cases_doc: list[dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any]:
    records = state.get("records")
    calls_started = state.get("calls_started")
    if not isinstance(records, dict) or not isinstance(calls_started, dict):
        raise ValueError("protected run state is incomplete")
    judge_model = str(preflight_doc["judge_model"])
    if calls_started != {
        GENERATOR_MODEL: EXPECTED_OPENINGS,
        judge_model: 0 if judge_model == ROOT_JUDGE else EXPECTED_OPENINGS,
    }:
        raise RuntimeError(f"paid-call journal is incomplete: {calls_started}")

    results: list[dict[str, object]] = []
    for case in cases_doc:
        record = records[str(int(case["dialog_id"]))]
        generation = record["generation"]
        judge = record["judge"]
        evaluation = EvaluationResult.model_validate(judge["evaluation"])
        corrected_ungrounded = find_ungrounded_numbers(str(generation["content"]), case)
        corrected_failures = critical_failure_codes(
            red_flag_codes=[
                str(flag["code"])
                for flag in judge["red_flags"]["flags"]
                if isinstance(flag, dict)
            ],
            ungrounded_numbers=corrected_ungrounded,
            language_ok=bool(judge["language_ok"]),
        )
        results.append(
            {
                "dialog_id": int(record["dialog_id"]),
                "length_stratum": int(record["length_stratum"]),
                "opening": str(record["opening"]),
                "response": str(generation["content"]),
                "generator_model": GENERATOR_MODEL,
                "judge_model": judge_model,
                "latency_ms": int(generation["latency_ms"]) + int(judge["latency_ms"]),
                "luna_latency_ms": int(generation["latency_ms"]),
                "glm_latency_ms": int(judge["latency_ms"]),
                "prompt_tokens": int(generation["prompt_tokens"])
                + int(judge["prompt_tokens"]),
                "completion_tokens": int(generation["completion_tokens"])
                + int(judge["completion_tokens"]),
                "cost_micro_usd": int(generation["cost_micro_usd"])
                + int(judge["cost_micro_usd"]),
                "weighted_score": float(evaluation.total_score),
                "attainable_score": attainable_weighted_score(evaluation.criteria),
                "raw_total": raw_total(evaluation.criteria),
                "language_ok": bool(judge["language_ok"]),
                "critical_failures": corrected_failures,
            }
        )
    expected_ids = {int(case["dialog_id"]) for case in cases_doc}
    validate_complete_results(
        results,
        expected_dialog_ids=expected_ids,
        require_acceptance=False,
    )
    public = build_public_summary(
        results, bootstrap_samples=BOOTSTRAP_SAMPLES, seed=BOOTSTRAP_SEED
    )
    actual_costs = _actual_cost_by_model(state, judge_model)
    public["measurement"] = {
        "scenario_digest": str(preflight_doc["scenario_digest"]),
        "generation_prompt_set_digest": _sha256_json(
            [str(case["generation_prompt_digest"]) for case in cases_doc]
        ),
        "judge_prompt_digest": hashlib.sha256(
            _judge_system_prompt().encode("utf-8")
        ).hexdigest(),
        "model_catalog_digest": _sha256_json(preflight_doc["model_catalog"]),
        "calls_started": {
            GENERATOR_MODEL: int(calls_started[GENERATOR_MODEL]),
            judge_model: int(calls_started[judge_model]),
        },
        "actual_cost_micro_usd": {
            model: round(cost * 1_000_000) for model, cost in actual_costs.items()
        },
        "provider_model_ids": {
            model: sorted(
                {
                    str(record[arm].get("provider_model") or "")
                    for record in records.values()
                    if isinstance(record, dict) and isinstance(record.get(arm), dict)
                }
            )
            for model, arm in (
                (GENERATOR_MODEL, "generation"),
                (judge_model, "judge"),
            )
        },
    }
    return public


def analyze_protected_run(output_dir: pathlib.Path) -> dict[str, Any]:
    """Recompute derived gates without making any model or catalog request."""
    output_dir = ensure_protected_output(output_dir, repo_root=REPO_ROOT)
    preflight_doc = _read_object(output_dir / "preflight.json")
    cases_doc = json.loads(
        (output_dir / "prepared-cases.json").read_text(encoding="utf-8")
    )
    if not isinstance(cases_doc, list) or len(cases_doc) != EXPECTED_OPENINGS:
        raise ValueError("prepared cases are incomplete")
    state = _read_object(output_dir / "run-state.json")
    public = _analyze_completed_state(
        preflight_doc=preflight_doc,
        cases_doc=cases_doc,
        state=state,
    )
    _write_protected_json(output_dir / "analysis.json", public)
    return public


async def run_paid_round(output_dir: pathlib.Path) -> dict[str, Any]:
    output_dir = ensure_protected_output(output_dir, repo_root=REPO_ROOT)
    preflight_doc = _read_object(output_dir / "preflight.json")
    if preflight_doc.get("paid_calls_made") != 0:
        raise ValueError("preflight was not sealed before paid calls")
    cases_doc = json.loads(
        (output_dir / "prepared-cases.json").read_text(encoding="utf-8")
    )
    if not isinstance(cases_doc, list) or len(cases_doc) != EXPECTED_OPENINGS:
        raise ValueError("prepared cases are incomplete")
    judge_model = str(preflight_doc["judge_model"])
    state_path = output_dir / "run-state.json"
    state = (
        _read_object(state_path)
        if state_path.exists()
        else {
            "schema_version": "treejar-real-opening-run-state/v1",
            "started_at": datetime.now(UTC).isoformat(),
            "calls_started": {GENERATOR_MODEL: 0, judge_model: 0},
            "records": {},
        }
    )
    records = state.get("records")
    if not isinstance(records, dict):
        raise ValueError("invalid protected run state")
    calls_started = state.get("calls_started")
    if not isinstance(calls_started, dict):
        raise ValueError("protected run state has no call journal")

    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url.rstrip("/"),
        headers=_provider_headers("Noor Real Opening Acceptance"),
    ) as client:
        for index, case in enumerate(cases_doc, 1):
            if not isinstance(case, dict):
                raise ValueError("prepared case must be an object")
            dialog_id = int(case["dialog_id"])
            key = str(dialog_id)
            record = records.setdefault(
                key,
                {
                    "dialog_id": dialog_id,
                    "length_stratum": int(case["length_stratum"]),
                    "opening": str(case["opening"]),
                    "language": str(case["language"]),
                    "catalog_evidence": case["catalog_evidence"],
                    "anchor_line": case["anchor_line"],
                },
            )
            if not isinstance(record, dict):
                raise ValueError("protected record must be an object")
            if not isinstance(record.get("generation"), dict):
                if record.get("generation_request_started_at") is not None:
                    raise RuntimeError(
                        f"dialog {dialog_id}: Luna request outcome is ambiguous; "
                        "refusing a duplicate paid call"
                    )
                calls_started[GENERATOR_MODEL] = (
                    int(calls_started.get(GENERATOR_MODEL) or 0) + 1
                )
                if int(calls_started[GENERATOR_MODEL]) > EXPECTED_OPENINGS:
                    raise RuntimeError("Luna paid-call count would exceed 20")
                record["generation_request_started_at"] = datetime.now(UTC).isoformat()
                _write_protected_json(state_path, state)
                order, quantizations = _provider_route(preflight_doc, GENERATOR_MODEL)
                payload = build_base_payload(
                    model=GENERATOR_MODEL,
                    messages=case["generation_messages"],
                    max_tokens=GENERATOR_MAX_TOKENS,
                    reasoning_enabled=False,
                    provider_order=order,
                    provider_quantizations=quantizations,
                )
                body, latency_ms = await _request_once(client, payload)
                raw_content, finish_reason = _message_content(body)
                if finish_reason == "length":
                    raise RuntimeError(f"dialog {dialog_id}: Luna response truncated")
                response = apply_shipped_output_guards(
                    raw_content,
                    language=str(case["language"]),
                    anchor_line=(
                        str(case["anchor_line"])
                        if isinstance(case.get("anchor_line"), str)
                        else None
                    ),
                    catalog_evidence=case["catalog_evidence"],
                )
                record["generation"] = {
                    "model": GENERATOR_MODEL,
                    "provider_model": body.get("model"),
                    "content": response,
                    "raw_content": raw_content,
                    "finish_reason": finish_reason,
                    "latency_ms": latency_ms,
                    **_usage(body),
                }
                _write_protected_json(state_path, state)
                _enforce_actual_caps(state, preflight_doc)
                print(
                    f"[Luna {index}/{EXPECTED_OPENINGS}] dialog_id={dialog_id}",
                    flush=True,
                )

            generation = record["generation"]
            if not isinstance(generation, dict):
                raise ValueError("generation state is invalid")
            response_text = str(generation["content"])
            assessment = _assessment(
                opening=str(case["opening"]),
                response=response_text,
                language=str(case["language"]),
                catalog_relevant=bool(case["catalog_relevant"]),
            )
            if judge_model == ROOT_JUDGE:
                # No second reader was authorized, so the round stops at the
                # generation arm and writes the pack the root judge reads.
                record["reading"] = _reading_entry(case, response_text, assessment)
                _write_protected_json(state_path, state)
                continue
            if not isinstance(record.get("judge"), dict):
                if record.get("judge_request_started_at") is not None:
                    raise RuntimeError(
                        f"dialog {dialog_id}: GLM request outcome is ambiguous; "
                        "refusing a duplicate paid call"
                    )
                calls_started[SECOND_READER_MODEL] = (
                    int(calls_started.get(SECOND_READER_MODEL) or 0) + 1
                )
                if int(calls_started[SECOND_READER_MODEL]) > EXPECTED_OPENINGS:
                    raise RuntimeError("GLM paid-call count would exceed 20")
                record["judge_request_started_at"] = datetime.now(UTC).isoformat()
                _write_protected_json(state_path, state)
                order, quantizations = _provider_route(
                    preflight_doc, SECOND_READER_MODEL
                )
                messages = _judge_messages(
                    opening=str(case["opening"]),
                    response=response_text,
                    language=str(case["language"]),
                    assessment=assessment,
                )
                payload = build_base_payload(
                    model=SECOND_READER_MODEL,
                    messages=messages,
                    max_tokens=JUDGE_MAX_TOKENS,
                    reasoning_enabled=False,
                    provider_order=order,
                    provider_quantizations=quantizations,
                )
                payload["temperature"] = 0
                payload["response_format"] = {"type": "json_object"}
                body, latency_ms = await _request_once(client, payload)
                content, finish_reason = _message_content(body)
                if finish_reason == "length":
                    raise RuntimeError(f"dialog {dialog_id}: GLM evaluation truncated")
                combined = CombinedJudgeResult.model_validate(
                    parse_json_content(content)
                )
                evaluation = finalize_evaluation_result(
                    combined.evaluation,
                    applicability_map=assessment.rule_applicability,
                    diagnostic_blockers=assessment.blocking_reasons,
                    applicability_signals=assessment.signals,
                )
                language_ok = _language_matches(response_text, str(case["language"]))
                ungrounded = find_ungrounded_numbers(response_text, case)
                failures = critical_failure_codes(
                    red_flag_codes=[flag.code for flag in combined.red_flags.flags],
                    ungrounded_numbers=ungrounded,
                    language_ok=language_ok,
                )
                record["judge"] = {
                    "model": SECOND_READER_MODEL,
                    "provider_model": body.get("model"),
                    "finish_reason": finish_reason,
                    "latency_ms": latency_ms,
                    **_usage(body),
                    "evaluation": evaluation.model_dump(mode="json"),
                    "red_flags": combined.red_flags.model_dump(mode="json"),
                    "ungrounded_numbers": ungrounded,
                    "language_ok": language_ok,
                    "critical_failures": failures,
                    "raw_verdict": content,
                }
                _write_protected_json(state_path, state)
                _enforce_actual_caps(state, preflight_doc)
                print(
                    f"[GLM {index}/{EXPECTED_OPENINGS}] dialog_id={dialog_id}",
                    flush=True,
                )

    if judge_model == ROOT_JUDGE:
        pack = [records[str(int(case["dialog_id"]))]["reading"] for case in cases_doc]
        _write_protected_json(output_dir / "reading-pack.json", pack)
        state["actual_cost_usd"] = _actual_cost_by_model(state, judge_model)
        _write_protected_json(state_path, state)
        return {
            "judge_model": ROOT_JUDGE,
            "generation_complete": len(pack) == EXPECTED_OPENINGS,
            "next": (
                "read reading-pack.json, then `ingest-judgment --judgments <file>`"
            ),
        }

    public = _analyze_completed_state(
        preflight_doc=preflight_doc,
        cases_doc=cases_doc,
        state=state,
    )
    actual_costs = _actual_cost_by_model(state, judge_model)
    state["completed_at"] = datetime.now(UTC).isoformat()
    state["public_summary"] = public
    state["actual_cost_usd"] = actual_costs
    _write_protected_json(state_path, state)
    return public


def _public_preflight(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": document["schema_version"],
        "scenario_count": document["scenario_count"],
        "generation_model": document["generation_model"],
        "judge_model": document["judge_model"],
        "calls_per_model": document["calls_per_model"],
        "estimated_cost_usd": document["estimated_cost_usd"],
        "per_model_cap_usd": document["per_model_cap_usd"],
        "catalog_products": document["catalog_products"],
        "paid_calls_made": document["paid_calls_made"],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--scenarios", type=pathlib.Path, required=True)
    preflight_parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    preflight_parser.add_argument(
        "--per-model-cap-usd", type=float, default=DEFAULT_MODEL_CAP_USD
    )
    preflight_parser.add_argument(
        "--second-reader",
        action="store_true",
        help=(
            "also pay a second reader to score the round. The root judge "
            "reads it either way; this only adds a second scale beside it."
        ),
    )
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    ingest_parser = subparsers.add_parser("ingest-judgment")
    ingest_parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    ingest_parser.add_argument("--judgments", type=pathlib.Path, required=True)
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        if args.command == "preflight":
            document = asyncio.run(
                preflight(
                    scenarios_path=args.scenarios,
                    output_dir=args.output_dir,
                    per_model_cap_usd=args.per_model_cap_usd,
                    second_reader=args.second_reader,
                )
            )
            print(json.dumps(_public_preflight(document), indent=2, sort_keys=True))
        elif args.command == "run":
            public = asyncio.run(run_paid_round(args.output_dir))
            print(json.dumps(public, indent=2, sort_keys=True))
        elif args.command == "ingest-judgment":
            public = ingest_root_judgment(args.output_dir, args.judgments)
            print(json.dumps(public, indent=2, sort_keys=True))
        elif args.command == "analyze":
            public = analyze_protected_run(args.output_dir)
            print(json.dumps(public, indent=2, sort_keys=True))
        else:
            output_dir = ensure_protected_output(args.output_dir, repo_root=REPO_ROOT)
            analysis_path = output_dir / "analysis.json"
            public = (
                _read_object(analysis_path)
                if analysis_path.exists()
                else _read_object(output_dir / "run-state.json").get("public_summary")
            )
            if not isinstance(public, dict):
                raise ValueError("protected run has no completed public summary")
            print(json.dumps(public, indent=2, sort_keys=True))
    except (
        OSError,
        ValueError,
        RuntimeError,
        httpx.HTTPError,
        json.JSONDecodeError,
    ) as exc:
        print(f"real-opening acceptance failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
