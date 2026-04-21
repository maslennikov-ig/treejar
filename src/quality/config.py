"""SystemConfig-backed Admin AI Quality Controls."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select

from src.core.config import settings
from src.core.database import async_session_factory
from src.core.redis import get_redis_client
from src.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

AI_QUALITY_CONTROLS_KEY = "ai_quality_controls"

MAX_DAILY_BUDGET_CENTS = 20_000
MAX_CALLS_PER_RUN = 100
MAX_CALLS_PER_DAY = 500
MAX_RETRY_BACKOFF_SECONDS = 3600

AIQualityRunTrigger = Literal["manual", "scheduled"]


class AIQualityScope(StrEnum):
    BOT_QA = "bot_qa"
    MANAGER_QA = "manager_qa"
    RED_FLAGS = "red_flags"


class AIQualityMode(StrEnum):
    DISABLED = "disabled"
    MANUAL = "manual"
    DAILY_SAMPLE = "daily_sample"
    SCHEDULED = "scheduled"


class AIQualityTranscriptMode(StrEnum):
    DISABLED = "disabled"
    SUMMARY = "summary"
    FULL = "full"


class AIQualityRetryPolicy(BaseModel):
    """Retry bounds for non-core QA LLM work."""

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=2, ge=1, le=2)
    backoff_seconds: int = Field(default=60, ge=0, le=MAX_RETRY_BACKOFF_SECONDS)


class AIQualityRetryPolicyUpdate(BaseModel):
    """Partial retry policy update payload."""

    model_config = ConfigDict(extra="forbid")

    max_attempts: int | None = Field(default=None, ge=1, le=2)
    backoff_seconds: int | None = Field(
        default=None, ge=0, le=MAX_RETRY_BACKOFF_SECONDS
    )


def _default_qa_model() -> str:
    return settings.openrouter_model_fast


def is_glm5_model(model_name: str) -> bool:
    normalized = model_name.lower()
    return "glm-5" in normalized or "glm5" in normalized


class AIQualityScopeConfig(BaseModel):
    """Admin-owned controls for one AI quality scope."""

    model_config = ConfigDict(extra="forbid")

    mode: AIQualityMode = AIQualityMode.DISABLED
    transcript_mode: AIQualityTranscriptMode = AIQualityTranscriptMode.SUMMARY
    model: str = Field(default_factory=_default_qa_model, min_length=1)
    daily_budget_cents: int = Field(default=100, ge=0, le=MAX_DAILY_BUDGET_CENTS)
    max_calls_per_run: int = Field(default=1, ge=0, le=MAX_CALLS_PER_RUN)
    max_calls_per_day: int = Field(default=5, ge=0, le=MAX_CALLS_PER_DAY)
    retry: AIQualityRetryPolicy = Field(default_factory=AIQualityRetryPolicy)
    criteria: dict[str, bool] = Field(default_factory=dict)
    cache_telemetry_enabled: bool = True
    alert_on_failure: bool = True
    full_transcript_warning_override: bool = False
    glm5_warning_override: bool = False

    @model_validator(mode="after")
    def validate_risky_settings(self) -> Self:
        if (
            self.transcript_mode == AIQualityTranscriptMode.FULL
            and not self.full_transcript_warning_override
        ):
            raise ValueError(
                "full transcript mode requires full_transcript_warning_override"
            )
        if is_glm5_model(self.model) and not self.glm5_warning_override:
            raise ValueError("GLM-5 QA model requires glm5_warning_override")
        if (
            self.max_calls_per_run > 0
            and self.max_calls_per_day > 0
            and self.max_calls_per_run > self.max_calls_per_day
        ):
            raise ValueError("max_calls_per_run cannot exceed max_calls_per_day")
        return self


class AIQualityScopeConfigUpdate(BaseModel):
    """Partial update payload for one AI quality scope."""

    model_config = ConfigDict(extra="forbid")

    mode: AIQualityMode | None = None
    transcript_mode: AIQualityTranscriptMode | None = None
    model: str | None = Field(default=None, min_length=1)
    daily_budget_cents: int | None = Field(
        default=None, ge=0, le=MAX_DAILY_BUDGET_CENTS
    )
    max_calls_per_run: int | None = Field(default=None, ge=0, le=MAX_CALLS_PER_RUN)
    max_calls_per_day: int | None = Field(default=None, ge=0, le=MAX_CALLS_PER_DAY)
    retry: AIQualityRetryPolicyUpdate | None = None
    criteria: dict[str, bool] | None = None
    cache_telemetry_enabled: bool | None = None
    alert_on_failure: bool | None = None
    full_transcript_warning_override: bool | None = None
    glm5_warning_override: bool | None = None


class AIQualityControlsConfig(BaseModel):
    """Full Admin AI Quality Controls payload stored in SystemConfig JSON."""

    model_config = ConfigDict(extra="forbid")

    bot_qa: AIQualityScopeConfig = Field(default_factory=AIQualityScopeConfig)
    manager_qa: AIQualityScopeConfig = Field(default_factory=AIQualityScopeConfig)
    red_flags: AIQualityScopeConfig = Field(default_factory=AIQualityScopeConfig)


class AIQualityControlsUpdate(BaseModel):
    """Partial update payload for Admin AI Quality Controls."""

    model_config = ConfigDict(extra="forbid")

    bot_qa: AIQualityScopeConfigUpdate | None = None
    manager_qa: AIQualityScopeConfigUpdate | None = None
    red_flags: AIQualityScopeConfigUpdate | None = None


class AIQualityWarning(BaseModel):
    scope: AIQualityScope
    code: Literal["full_transcript", "glm5_qa"]
    severity: Literal["warning"] = "warning"
    message: str


class AIQualityControlsResponse(BaseModel):
    config: AIQualityControlsConfig
    warnings: list[AIQualityWarning] = Field(default_factory=list)


class AIQualityRunGate(BaseModel):
    scope: AIQualityScope
    trigger: AIQualityRunTrigger
    mode: AIQualityMode
    allowed: bool
    reason: str | None = None
    model: str
    max_calls: int = 0
    max_calls_per_day: int = 0


def _scope_items(
    config: AIQualityControlsConfig,
) -> tuple[tuple[AIQualityScope, AIQualityScopeConfig], ...]:
    return (
        (AIQualityScope.BOT_QA, config.bot_qa),
        (AIQualityScope.MANAGER_QA, config.manager_qa),
        (AIQualityScope.RED_FLAGS, config.red_flags),
    )


def scope_config(
    config: AIQualityControlsConfig,
    scope: AIQualityScope,
) -> AIQualityScopeConfig:
    match scope:
        case AIQualityScope.BOT_QA:
            return config.bot_qa
        case AIQualityScope.MANAGER_QA:
            return config.manager_qa
        case AIQualityScope.RED_FLAGS:
            return config.red_flags
    raise ValueError(f"Unknown AI quality scope: {scope}")


def warnings_for_ai_quality_config(
    config: AIQualityControlsConfig,
) -> list[AIQualityWarning]:
    warnings: list[AIQualityWarning] = []
    for scope, scope_settings in _scope_items(config):
        if scope_settings.transcript_mode == AIQualityTranscriptMode.FULL:
            warnings.append(
                AIQualityWarning(
                    scope=scope,
                    code="full_transcript",
                    message=(
                        "Full transcript QA can send large conversations to the LLM "
                        "and should stay exceptional."
                    ),
                )
            )
        if is_glm5_model(scope_settings.model):
            warnings.append(
                AIQualityWarning(
                    scope=scope,
                    code="glm5_qa",
                    message=(
                        "GLM-5 is expensive for QA automation and requires an "
                        "explicit admin override."
                    ),
                )
            )
    return warnings


def build_ai_quality_response(
    config: AIQualityControlsConfig,
) -> AIQualityControlsResponse:
    return AIQualityControlsResponse(
        config=config,
        warnings=warnings_for_ai_quality_config(config),
    )


def evaluate_ai_quality_run_gate(
    config: AIQualityControlsConfig,
    *,
    scope: AIQualityScope,
    trigger: AIQualityRunTrigger,
) -> AIQualityRunGate:
    scope_settings = scope_config(config, scope)

    def blocked(reason: str) -> AIQualityRunGate:
        return AIQualityRunGate(
            scope=scope,
            trigger=trigger,
            mode=scope_settings.mode,
            allowed=False,
            reason=reason,
            model=scope_settings.model,
            max_calls=0,
            max_calls_per_day=scope_settings.max_calls_per_day,
        )

    if scope_settings.mode == AIQualityMode.DISABLED:
        return blocked("disabled")
    if trigger == "scheduled" and scope_settings.mode == AIQualityMode.MANUAL:
        return blocked("manual_only")
    if scope_settings.daily_budget_cents <= 0:
        return blocked("daily_budget_zero")
    if scope_settings.max_calls_per_run <= 0:
        return blocked("max_calls_per_run_zero")
    if scope_settings.max_calls_per_day <= 0:
        return blocked("max_calls_per_day_zero")

    return AIQualityRunGate(
        scope=scope,
        trigger=trigger,
        mode=scope_settings.mode,
        allowed=True,
        reason=None,
        model=scope_settings.model,
        max_calls=min(
            scope_settings.max_calls_per_run, scope_settings.max_calls_per_day
        ),
        max_calls_per_day=scope_settings.max_calls_per_day,
    )


def _blocked_run_gate(gate: AIQualityRunGate, reason: str) -> AIQualityRunGate:
    return gate.model_copy(update={"allowed": False, "reason": reason, "max_calls": 0})


def _utc_day(now: datetime | None = None) -> tuple[str, int]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    current = current.astimezone(UTC)
    next_day = (current + timedelta(days=1)).date()
    next_midnight = datetime.combine(next_day, datetime.min.time(), tzinfo=UTC)
    ttl_seconds = max(int((next_midnight - current).total_seconds()), 1)
    return current.strftime("%Y%m%d"), ttl_seconds


def _daily_sample_key(scope: AIQualityScope, day: str) -> str:
    return f"quality:ai_controls:daily_sample:{scope.value}:{day}"


def _daily_calls_key(scope: AIQualityScope, day: str) -> str:
    return f"quality:ai_controls:daily_calls:{scope.value}:{day}"


def parse_ai_quality_controls(raw: Any) -> AIQualityControlsConfig:
    if isinstance(raw, AIQualityControlsConfig):
        return raw
    if isinstance(raw, Mapping):
        return AIQualityControlsConfig.model_validate(raw)
    return AIQualityControlsConfig()


def _deep_merge(
    base: dict[str, Any],
    patch: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def merge_ai_quality_controls_update(
    current: AIQualityControlsConfig,
    update: AIQualityControlsUpdate,
) -> AIQualityControlsConfig:
    merged = _deep_merge(
        current.model_dump(mode="json"),
        update.model_dump(mode="json", exclude_unset=True),
    )
    return AIQualityControlsConfig.model_validate(merged)


async def get_ai_quality_controls_config(db: Any) -> AIQualityControlsConfig:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == AI_QUALITY_CONTROLS_KEY)
    )
    row = result.scalar_one_or_none()
    value = getattr(row, "value", None)
    if value is None:
        return AIQualityControlsConfig()

    try:
        return parse_ai_quality_controls(value)
    except ValidationError:
        logger.warning(
            "Invalid SystemConfig %s; falling back to safe defaults",
            AI_QUALITY_CONTROLS_KEY,
            exc_info=True,
        )
        return AIQualityControlsConfig()


async def save_ai_quality_controls_config(
    db: Any,
    config: AIQualityControlsConfig,
) -> AIQualityControlsConfig:
    value = config.model_dump(mode="json")
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == AI_QUALITY_CONTROLS_KEY)
    )
    row = result.scalar_one_or_none()
    if row is None:
        db.add(
            SystemConfig(
                key=AI_QUALITY_CONTROLS_KEY,
                value=value,
                description="Admin AI Quality Controls JSON configuration",
            )
        )
    else:
        # SQLAlchemy JSON does not track deep in-place mutations without MutableDict.
        row.value = value
    await db.commit()
    return config


async def get_ai_quality_run_gate_from_ctx(
    ctx: Mapping[str, Any],
    *,
    scope: AIQualityScope,
    trigger: AIQualityRunTrigger,
) -> AIQualityRunGate:
    raw_config = ctx.get("ai_quality_controls")
    if raw_config is not None:
        try:
            config = parse_ai_quality_controls(raw_config)
        except ValidationError:
            logger.warning(
                "Invalid ctx AI Quality Controls; using safe defaults",
                exc_info=True,
            )
            config = AIQualityControlsConfig()
        return evaluate_ai_quality_run_gate(config, scope=scope, trigger=trigger)

    try:
        async with async_session_factory() as db:
            config = await get_ai_quality_controls_config(db)
    except Exception:
        logger.warning("Failed to read AI Quality Controls; using safe defaults")
        config = AIQualityControlsConfig()

    return evaluate_ai_quality_run_gate(config, scope=scope, trigger=trigger)


def _ctx_redis(ctx: Mapping[str, Any]) -> Any:
    return ctx.get("redis") or get_redis_client()


async def reserve_ai_quality_daily_sample_from_ctx(
    ctx: Mapping[str, Any],
    gate: AIQualityRunGate,
    *,
    now: datetime | None = None,
) -> AIQualityRunGate:
    """Reserve the one scheduled daily-sample run for this UTC day."""
    if (
        not gate.allowed
        or gate.trigger != "scheduled"
        or gate.mode != AIQualityMode.DAILY_SAMPLE
    ):
        return gate

    redis = _ctx_redis(ctx)
    if redis is None:
        logger.warning("AI Quality daily-sample reservation skipped: missing Redis")
        return _blocked_run_gate(gate, "daily_sample_redis_unavailable")

    day, ttl_seconds = _utc_day(now)
    key = _daily_sample_key(gate.scope, day)
    try:
        reserved = bool(await redis.set(key, "1", nx=True, ex=ttl_seconds))
    except Exception:
        logger.warning(
            "Failed to reserve AI Quality daily-sample run for %s",
            gate.scope.value,
            exc_info=True,
        )
        return _blocked_run_gate(gate, "daily_sample_reservation_failed")

    if not reserved:
        return _blocked_run_gate(gate, "daily_sample_already_run")
    return gate


async def consume_ai_quality_daily_call_from_ctx(
    ctx: Mapping[str, Any],
    gate: AIQualityRunGate,
    *,
    now: datetime | None = None,
) -> bool:
    """Consume one UTC-day call slot before non-core QA opens a provider call."""
    if not gate.allowed or gate.max_calls_per_day <= 0:
        return False

    redis = _ctx_redis(ctx)
    if redis is None:
        logger.warning("AI Quality daily call quota skipped: missing Redis")
        return False

    day, ttl_seconds = _utc_day(now)
    key = _daily_calls_key(gate.scope, day)
    try:
        current = await redis.incr(key)
        if not isinstance(current, int):
            current = int(current)
        if current == 1:
            await redis.expire(key, ttl_seconds)
    except Exception:
        logger.warning(
            "Failed to consume AI Quality daily call quota for %s",
            gate.scope.value,
            exc_info=True,
        )
        return False

    if current > gate.max_calls_per_day:
        try:
            await redis.decr(key)
        except Exception:
            logger.warning(
                "Failed to release AI Quality daily call quota for %s",
                gate.scope.value,
                exc_info=True,
            )
        return False
    return True
