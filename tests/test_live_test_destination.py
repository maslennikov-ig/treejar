from __future__ import annotations

import asyncio
import builtins
import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

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
    # Structural E.164 mock outside NANPA's reserved 555-0100..0199 range.
    # This unit assertion does not claim that the number is deliverable.
    destination = "+12025552047"

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
        "+12025550100",
        "+12025550199",
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


def test_send_pdf_fails_before_third_party_external_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_WHATSAPP_PHONE_ENV, raising=False)
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "send_test_pdf.py"
    spec = importlib.util.spec_from_file_location(
        "scripts.send_test_pdf_import_guard",
        script_path,
    )
    assert spec is not None and spec.loader is not None
    module = ModuleType(spec.name)
    module.__file__ = str(script_path)
    module.__package__ = "scripts"
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "httpx" or name.startswith(("redis", "src.")):
            raise AssertionError(
                f"external import before destination validation: {name}"
            )
        return original_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(
        LiveDestinationError,
        match=f"{LIVE_WHATSAPP_PHONE_ENV} must be set explicitly",
    ):
        spec.loader.exec_module(module)
        asyncio.run(module.main())
