"""Structural acceptance checks for the message-processing split."""

from __future__ import annotations

import ast
from pathlib import Path

ENGINE_PATH = Path(__file__).parents[1] / "src" / "llm" / "engine.py"


def test_engine_and_process_message_stay_below_settled_size_limits() -> None:
    source = ENGINE_PATH.read_text(encoding="utf-8")
    module = ast.parse(source)
    process_message = next(
        node
        for node in module.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "process_message"
    )

    assert process_message.end_lineno is not None
    assert process_message.end_lineno - process_message.lineno + 1 < 300
    assert len(source.splitlines()) < 12_000

    llm_sources = (
        ENGINE_PATH.parent / name for name in ("engine.py", "message_processor.py")
    )
    public_process_functions = [
        node
        for path in llm_sources
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "process_message"
    ]
    assert len(public_process_functions) == 1
