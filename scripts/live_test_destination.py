"""Fail-closed destination binding for scripts that send live WhatsApp messages."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

LIVE_WHATSAPP_PHONE_ENV = "NOOR_LIVE_TEST_WHATSAPP_PHONE"

_E164_PHONE = re.compile(r"^\+[1-9]\d{7,14}$")
_NANPA_FICTIONAL_PHONE = re.compile(r"^\+1[2-9]\d{2}55501\d{2}$")


class LiveDestinationError(ValueError):
    """Raised when a live delivery destination is absent or unsafe."""


def load_live_whatsapp_phone(
    environ: Mapping[str, str] | None = None,
    *,
    required: bool = True,
) -> str | None:
    """Load an explicitly authorized E.164 destination without a live default."""
    source = os.environ if environ is None else environ
    value = source.get(LIVE_WHATSAPP_PHONE_ENV, "").strip()
    if not value:
        if required:
            raise LiveDestinationError(
                f"{LIVE_WHATSAPP_PHONE_ENV} must be set explicitly "
                "before live WhatsApp delivery"
            )
        return None

    is_placeholder = (
        "PROTECTED_TEST_PHONE" in value.upper()
        or value.startswith("+1555")
        or value.startswith("+971000")
        or _NANPA_FICTIONAL_PHONE.fullmatch(value) is not None
    )
    if is_placeholder or _E164_PHONE.fullmatch(value) is None:
        raise LiveDestinationError(
            f"{LIVE_WHATSAPP_PHONE_ENV} must be an authorized E.164 destination, "
            "not a test fixture or protected placeholder"
        )

    return value
