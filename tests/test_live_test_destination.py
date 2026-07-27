from __future__ import annotations

import asyncio
import importlib

import pytest
from scripts.live_test_destination import (
    LIVE_WHATSAPP_PHONE_ENV,
    LiveDestinationError,
    load_live_whatsapp_phone,
)


def test_live_destination_has_no_default() -> None:
    with pytest.raises(
        LiveDestinationError,
        match=f"{LIVE_WHATSAPP_PHONE_ENV} must be set explicitly",
    ):
        load_live_whatsapp_phone({})


def test_live_destination_binds_explicit_environment_value() -> None:
    destination = "+12025550147"

    assert (
        load_live_whatsapp_phone({LIVE_WHATSAPP_PHONE_ENV: destination}) == destination
    )


@pytest.mark.parametrize(
    "destination",
    [
        "15550001111",
        "+15550001111",
        "[PROTECTED_TEST_PHONE]",
        "+971000000001",
    ],
)
def test_live_destination_rejects_placeholder_values(destination: str) -> None:
    with pytest.raises(LiveDestinationError, match="must be an authorized"):
        load_live_whatsapp_phone({LIVE_WHATSAPP_PHONE_ENV: destination})


def test_optional_live_destination_allows_missing_value_for_pytest_skip_gate() -> None:
    assert load_live_whatsapp_phone({}, required=False) is None


@pytest.mark.parametrize(
    "module_name",
    [
        "scripts.run_integration_tests",
        "scripts.send_test_pdf",
    ],
)
def test_live_delivery_scripts_fail_before_external_work_without_destination(
    module_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_WHATSAPP_PHONE_ENV, raising=False)
    module = importlib.import_module(module_name)

    assert not hasattr(module, "USER_WHATSAPP_PHONE")
    with pytest.raises(
        LiveDestinationError,
        match=f"{LIVE_WHATSAPP_PHONE_ENV} must be set explicitly",
    ):
        asyncio.run(module.main())
