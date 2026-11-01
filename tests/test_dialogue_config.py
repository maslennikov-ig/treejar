from src.core.config import settings


def test_customer_facts_config_defaults_to_disabled_rollout() -> None:
    assert settings.customer_facts_mode == "disabled"
    assert settings.customer_facts_max_context_orders == 3


def test_pii_masking_defaults_to_disabled() -> None:
    assert settings.pii_masking_enabled is False
