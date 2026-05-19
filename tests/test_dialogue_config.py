from src.core.config import settings


def test_dialogue_kernel_config_defaults_to_legacy_shadow_trace() -> None:
    assert settings.dialogue_kernel_mode == "legacy"
    assert settings.dialogue_kernel_trace_enabled is True
    assert settings.dialogue_kernel_enforced_flows == ""
