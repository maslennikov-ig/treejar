"""The QA cost guard is about rate, not about the GLM-5 name."""

import pytest

from src.quality.config import (
    AIQualityControlsConfig,
    AIQualityScopeConfig,
    is_expensive_qa_model,
    warnings_for_ai_quality_config,
)

EXPENSIVE = (
    "z-ai/glm-5",
    "z-ai/glm-5.1",
    "z-ai/glm-5-turbo",
    "z-ai/glm-5v-turbo",
    "Z-AI/GLM-5",
    "glm5",
)

AFFORDABLE = (
    "z-ai/glm-5.2",
    "Z-AI/GLM-5.2",
    "  z-ai/glm-5.2  ",
    "z-ai/glm-5.2:free",
    "glm-5.2",
    "deepseek/deepseek-v4-flash",
    "anthropic/claude-sonnet-5",
)


@pytest.mark.parametrize("model_name", EXPENSIVE)
def test_expensive_models_still_trip_the_guard(model_name: str) -> None:
    assert is_expensive_qa_model(model_name)


@pytest.mark.parametrize("model_name", AFFORDABLE)
def test_glm_5_2_and_cheaper_models_do_not_trip_the_guard(model_name: str) -> None:
    assert not is_expensive_qa_model(model_name)


def test_glm_5_2_needs_no_override_to_construct() -> None:
    """The override box was the blocker on adopting glm-5.2 as the judge."""
    scope = AIQualityScopeConfig(model="z-ai/glm-5.2")

    assert scope.model == "z-ai/glm-5.2"
    assert scope.glm5_warning_override is False


def test_glm_5_still_needs_an_override_to_construct() -> None:
    with pytest.raises(ValueError, match="expensive QA model"):
        AIQualityScopeConfig(model="z-ai/glm-5")


def test_glm_5_2_raises_no_admin_warning() -> None:
    config = AIQualityControlsConfig(bot_qa=AIQualityScopeConfig(model="z-ai/glm-5.2"))

    codes = {warning.code for warning in warnings_for_ai_quality_config(config)}

    assert "glm5_qa" not in codes


def test_glm_5_warning_names_the_model_it_objects_to() -> None:
    config = AIQualityControlsConfig(
        bot_qa=AIQualityScopeConfig(model="z-ai/glm-5", glm5_warning_override=True)
    )

    warnings = [
        warning
        for warning in warnings_for_ai_quality_config(config)
        if warning.code == "glm5_qa"
    ]

    assert len(warnings) == 1
    assert "z-ai/glm-5" in warnings[0].message
