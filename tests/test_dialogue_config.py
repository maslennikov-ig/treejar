from src.core.config import settings


def test_dialogue_kernel_config_defaults_to_legacy_shadow_trace() -> None:
    assert settings.dialogue_kernel_mode == "legacy"
    assert settings.dialogue_kernel_trace_enabled is True
    assert settings.dialogue_kernel_enforced_flows == ""


def test_customer_facts_config_defaults_to_disabled_traceable_rollout() -> None:
    assert settings.customer_facts_mode == "disabled"
    assert settings.customer_facts_trace_enabled is True
    assert settings.customer_facts_fast_extractor_enabled is True
    assert settings.customer_facts_max_context_orders == 3
