#!/usr/bin/env python3
"""Aggregate privacy-safe Noor chat latency log records."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path

from src.services.chat_latency import parse_chat_latency_line, summarize_chat_latency


def _lines(path: str) -> Iterable[str]:
    if path == "-":
        yield from sys.stdin
        return
    with Path(path).open(encoding="utf-8") as handle:
        yield from handle


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize allowlisted noor_chat_latency JSON records without "
            "reading message text or identifiers."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="-",
        help="application log path, or '-' for stdin",
    )
    args = parser.parse_args()

    samples = [
        sample
        for line in _lines(args.path)
        if (sample := parse_chat_latency_line(line)) is not None
    ]
    print(json.dumps(summarize_chat_latency(samples), indent=2, sort_keys=True))
    return 0 if samples else 2


if __name__ == "__main__":
    raise SystemExit(main())
