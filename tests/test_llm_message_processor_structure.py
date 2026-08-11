"""The bound `tj-rt7w.6` reported and did not hold.

`tests/test_llm_engine_structure.py` asserts on `process_message`, which is a
forty-line facade. That is true and says nothing: the sequence it delegates to
was 2,044 lines with fifteen nested closures in a new file, and no test could
see it. These two assertions are on the sequence itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

PROCESSOR_PATH = Path(__file__).parents[1] / "src" / "llm" / "message_processor.py"
MAX_FUNCTION_LINES = 300


def _module() -> ast.Module:
    return ast.parse(PROCESSOR_PATH.read_text(encoding="utf-8"))


def test_no_function_in_the_turn_sequence_is_longer_than_the_settled_limit() -> None:
    too_long = []
    for node in ast.walk(_module()):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        assert node.end_lineno is not None
        length = node.end_lineno - node.lineno + 1
        if length > MAX_FUNCTION_LINES:
            too_long.append((node.name, length))
    assert too_long == []


def test_the_turn_sequence_holds_no_closures() -> None:
    """A closure here is state that only the function it hides in can read.

    Every phase of a turn is a module-level function over `_Turn`, so a method
    on a class is expected and a function nested in a function is not.
    """

    nested = []

    def scan(node: ast.AST, inside_function: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                if inside_function:
                    nested.append(child.name)
                scan(child, True)
            elif isinstance(child, ast.ClassDef):
                scan(child, False)

    scan(_module(), False)
    assert nested == []
