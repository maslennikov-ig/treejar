from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
SUITE_MODULE_PATH = SCRIPTS_DIR / "bot_test_suite.py"


def _load_bot_test_suite_module():
    scripts_str = str(SCRIPTS_DIR)
    added = False
    if scripts_str not in sys.path:
        sys.path.insert(0, scripts_str)
        added = True
    try:
        spec = importlib.util.spec_from_file_location(
            "scripts.bot_test_suite",
            SUITE_MODULE_PATH,
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if added:
            sys.path.remove(scripts_str)


def test_mock_messaging_provider_exposes_channel_id_and_outbound_chat_id() -> None:
    module = _load_bot_test_suite_module()
    provider = module.MockMessagingProvider(channel_id="chan-test-123")

    assert provider.channel_id == "chan-test-123"
    assert provider.outbound_chat_id("+971000000099#test-9_1") == (
        "+971000000099#test-9_1"
    )


@pytest.mark.asyncio
async def test_order_status_no_deal_accepts_couldnt_find_with_typographic_apostrophe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_bot_test_suite_module()
    monkeypatch.setattr(module, "cleanup_phone", AsyncMock())
    monkeypatch.setattr(
        module,
        "send_message",
        AsyncMock(
            return_value=(
                "Hello, I'm Noor from Treejar. I couldn’t find an order linked to "
                "this conversation. Could you share your order number?",
                module.MockMessagingProvider(channel_id="chan-1"),
            )
        ),
    )

    suite = module.TestSuite()
    result = await suite.test_3_2_order_status_no_deal()
    assert "couldn’t find" in result["response"]


@pytest.mark.asyncio
async def test_sample_request_expects_conditional_capability_without_forced_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_bot_test_suite_module()
    monkeypatch.setattr(module, "cleanup_phone", AsyncMock())
    monkeypatch.setattr(
        module,
        "send_message",
        AsyncMock(
            return_value=(
                "Yes, we can arrange physical samples depending on your project "
                "requirements, or welcome you at our Dubai showroom.",
                module.MockMessagingProvider(channel_id="chan-1"),
            )
        ),
    )
    monkeypatch.setattr(
        module,
        "get_conversation_state",
        AsyncMock(return_value={"escalation_status": "none"}),
    )

    suite = module.TestSuite()
    result = await suite.test_4_5_sample_request_escalation()
    assert result["escalation_status"] == "none"


@pytest.mark.asyncio
async def test_arabic_product_search_rejects_duplicate_transliterated_intro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_bot_test_suite_module()
    monkeypatch.setattr(module, "cleanup_phone", AsyncMock())
    monkeypatch.setattr(
        module,
        "send_message",
        AsyncMock(
            return_value=(
                "مرحبًا، أنا Noor من Treejar. أهلاً بك، أنا نور من تريجار 🌿",
                module.MockMessagingProvider(channel_id="chan-1"),
            )
        ),
    )
    monkeypatch.setattr(
        module,
        "get_conversation_state",
        AsyncMock(return_value={"language": "ar"}),
    )

    suite = module.TestSuite()
    with pytest.raises(AssertionError, match="Duplicate Arabic introduction"):
        await suite.test_2_3_product_search_arabic()
