"""What the message processor must keep resolving through `src.llm.engine`.

`tj-rt7w.9`. The processor reaches most of its collaborators by importing them
from the module that defines them, which is what lets Mypy check the calls. A
handful it must not: the suite patches those names *on the engine module*, and
an import binds the original at import time, so a direct import silently
disconnects the patch. Nothing then fails loudly -- the test still passes, it
just no longer exercises what it says it does. Three did exactly that while this
split was being written, and only an unrelated assertion caught it.

So the load-bearing set is derived here from the suite itself rather than
written down twice. Adding a `patch.object(engine_module, "x")` anywhere makes
this test require that the processor still resolve `x` through the engine.
"""

from __future__ import annotations

import ast
import pathlib

ENGINE_ALIASES = {"engine", "engine_module", "llm_engine"}
_TESTS = pathlib.Path(__file__).parent
_PROCESSOR = _TESTS.parents[0] / "src" / "llm" / "message_processor.py"


def _names_patched_on_the_engine_module() -> set[str]:
    found: set[str] = set()
    for path in sorted(_TESTS.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if (
                isinstance(target, ast.Attribute)
                and target.attr in {"setattr", "object"}
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                subject = node.args[0]
                named = (
                    isinstance(subject, ast.Name) and subject.id in ENGINE_ALIASES
                ) or (
                    isinstance(subject, ast.Attribute)
                    and subject.attr in ENGINE_ALIASES
                )
                if named:
                    found.add(node.args[1].value)
            if (
                node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value.startswith("src.llm.engine.")
            ):
                found.add(node.args[0].value.rsplit(".", 1)[1])
    return found


def _processor_module() -> ast.Module:
    return ast.parse(_PROCESSOR.read_text(encoding="utf-8"))


def _names_resolved_through_the_engine() -> set[str]:
    return {
        node.attr
        for node in ast.walk(_processor_module())
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "engine"
    }


def _names_imported_directly() -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(_processor_module()):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.asname or alias.name for alias in node.names)
    return imported


def test_every_patched_engine_name_the_processor_uses_still_goes_through_engine() -> (
    None
):
    patched = _names_patched_on_the_engine_module()
    imported = _names_imported_directly()
    resolved = _names_resolved_through_the_engine()

    disconnected = sorted(patched & imported - resolved)

    assert not disconnected, (
        "the message processor imports these directly, so every "
        "patch.object(engine_module, ...) on them is now a no-op: "
        f"{disconnected}"
    )


def test_the_processor_takes_no_untyped_runtime_module() -> None:
    """The split used to hand the engine in as `runtime: Any`.

    Every one of the 160 names it then read off that object was `Any`, so Mypy
    checked nothing across the whole orchestration sequence -- a wrong-arity
    call to `_catalog_planning_for_turn` passed clean. Importing the module
    instead resolves the same attributes at the same moment and keeps the types.
    """
    impl = next(
        node
        for node in _processor_module().body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "process_message_impl"
    )
    arguments = impl.args
    annotations = {
        argument.arg: ast.unparse(argument.annotation) if argument.annotation else None
        for argument in (*arguments.args, *arguments.kwonlyargs)
    }

    assert "runtime" not in annotations
    assert annotations["conversation_id"] == "UUID"
    assert annotations["db"] == "AsyncSession"
