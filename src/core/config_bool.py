from __future__ import annotations

from typing import Any

_TRUE_STRINGS = frozenset({"true", "1", "yes", "on", "y", "t"})
_FALSE_STRINGS = frozenset({"false", "0", "no", "off", "n", "f", ""})


def parse_config_bool(value: Any, *, default: bool = False) -> bool:
    """Parse SystemConfig or JSON boolean values safely without bool('false') == True."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_STRINGS:
            return True
        if normalized in _FALSE_STRINGS:
            return False
        return default
    if isinstance(value, dict):
        for key in ("enabled", "value"):
            if key in value:
                return parse_config_bool(value[key], default=default)
        return default
    return default
