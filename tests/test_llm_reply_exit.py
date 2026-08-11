from __future__ import annotations

import ast
import inspect
import textwrap

from src.llm.engine import process_message


def test_process_message_has_no_direct_reply_exit_around_rendering() -> None:
    tree = ast.parse(textwrap.dedent(inspect.getsource(process_message)))
    direct_response_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "LLMResponse"
    ]

    assert direct_response_calls == []
