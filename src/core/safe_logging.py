"""Process-wide log record redaction for credential-bearing URLs."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from urllib.parse import urlsplit

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:!?)]}"
_REDACTED_PATH = "[redacted-url]"


def redact_urls(value: object) -> str:
    """Keep an HTTP origin visible while removing every access-bearing part."""

    text = str(value)

    def replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        url = raw.rstrip(_TRAILING_PUNCTUATION)
        trailing = raw[len(url) :]
        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
            if not hostname:
                return f"{_REDACTED_PATH}{trailing}"
            if ":" in hostname and not hostname.startswith("["):
                hostname = f"[{hostname}]"
            port = f":{parsed.port}" if parsed.port is not None else ""
            origin = f"{parsed.scheme}://{hostname}{port}"
        except ValueError:
            return f"{_REDACTED_PATH}{trailing}"
        return f"{origin}/{_REDACTED_PATH}{trailing}"

    return _URL_RE.sub(replace, text)


class SensitiveUrlFilter(logging.Filter):
    """Edit the record before any configured handler can serialize it."""

    def filter(self, record: logging.LogRecord) -> bool:
        if (
            record.name == "uvicorn.access"
            and isinstance(record.args, tuple)
            and len(record.args) == 5
        ):
            # Uvicorn's AccessFormatter unpacks this five-item tuple after
            # handler filters run. Preserve the formatter contract while
            # redacting any absolute URL carried by a structured argument.
            record.msg = redact_urls(record.msg)
            record.args = tuple(
                redact_urls(value) if isinstance(value, str) else value
                for value in record.args
            )
        else:
            try:
                message = record.getMessage()
            except Exception:
                message = str(record.msg)
            record.msg = redact_urls(message)
            record.args = ()

        if record.exc_info is not None:
            exception_text = logging.Formatter().formatException(record.exc_info)
            record.exc_text = redact_urls(exception_text)
        if record.stack_info:
            record.stack_info = redact_urls(record.stack_info)
        return True


def _configured_handlers() -> Iterable[logging.Handler]:
    seen: set[int] = set()
    loggers: list[logging.Logger] = [logging.getLogger()]
    loggers.extend(
        logger
        for logger in logging.Logger.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    )
    for logger in loggers:
        for handler in logger.handlers:
            marker = id(handler)
            if marker in seen:
                continue
            seen.add(marker)
            yield handler


def install_sensitive_url_filter() -> int:
    """Attach one idempotent record editor to every active log handler."""

    installed = 0
    for handler in _configured_handlers():
        if any(isinstance(item, SensitiveUrlFilter) for item in handler.filters):
            continue
        handler.addFilter(SensitiveUrlFilter())
        installed += 1
    return installed
