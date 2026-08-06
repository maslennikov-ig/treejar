"""Re-pin the traceability digests of the files the contract calls current state.

`tj-feet.11`. A traceability manifest freezes the exact text an acceptance was
written against, which is right for a requirement and wrong for a pointer.
`.codex/orchestrator.toml` and `.codex/handoff.md` are declared by `AGENTS.md`
to be current state: `orchestrator.toml` carries `current_stage_id` and the
handoff carries nothing else. Any later stage that does its ordinary job moves
both, and three manifest tests fail with a digest mismatch that says nothing
about what actually changed. `tj-feet` hit this twice on 2026-08-05 and re-pinned
by hand both times.

So the drift is expected maintenance, and this is the maintenance step.

The narrowness is the safety property. Only the paths the repository contract
itself declares mutable are re-pinned; a frozen requirement, a scenario set or
the scope snapshot drifting still fails loudly, exactly as it should. This is a
way to record that current state moved, never a way to launder a real change.

    uv run python scripts/orchestration/repin_traceability_sources.py --check
    uv run python scripts/orchestration/repin_traceability_sources.py

`--check` reports drift and exits non-zero without writing, so it can gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.e2e_acceptance.manifest import (  # noqa: E402
    ManifestValidationError,
    _canonical_json_digest,
    _read_regular_file_at,
    _section_bytes,
    load_traceability_manifest,
)

MUTABLE_SOURCE_PATHS = frozenset(
    {
        ".codex/orchestrator.toml",
        ".codex/handoff.md",
    }
)
"""Exactly the two files `AGENTS.md` declares to be current state.

Adding to this set widens what may drift silently, so it is a contract change
and belongs in a review, not in a bug fix.
"""


def _source_set_digest(registry: dict[str, dict]) -> str:
    """The derived digest over the registry, in the validator's own shape.

    Built on the validator's own `_canonical_json_digest`. Restating it here
    once looked harmless and was not: the local copy defaulted to
    `ensure_ascii=True` and reported permanent drift against a manifest that was
    correctly pinned.
    """
    payload = [
        {
            "source_id": source_id,
            "path": source["path"],
            "content_digest": source["content_digest"],
            "sections": source["sections"],
        }
        for source_id, source in sorted(registry.items())
    ]
    return _canonical_json_digest(payload)


def repin(manifest_path: pathlib.Path, *, repo_root: pathlib.Path, check: bool) -> int:
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    registry = document.get("source_registry") or {}
    drifted: list[str] = []

    for source_id, source in registry.items():
        if source.get("path") not in MUTABLE_SOURCE_PATHS:
            continue
        content = _read_regular_file_at(
            repo_root,
            pathlib.PurePosixPath(source["path"]),
            label=source_id,
        )
        actual = hashlib.sha256(content).hexdigest()
        if source.get("content_digest") != actual:
            drifted.append(f"{source_id}: whole-file digest")
            source["content_digest"] = actual
        for index, section in enumerate(source.get("sections") or []):
            section_digest = hashlib.sha256(
                _section_bytes(
                    content,
                    source_id=source_id,
                    start_locator=section["start_locator"],
                    end_locator=section.get("end_locator"),
                )
            ).hexdigest()
            if section.get("content_digest") != section_digest:
                drifted.append(f"{source_id}: section {index}")
                section["content_digest"] = section_digest

    derived = _source_set_digest(registry)
    if document.get("source_set_digest") != derived:
        drifted.append("source_set_digest")
        document["source_set_digest"] = derived

    if not drifted:
        print("current-state sources are pinned to their present content")
        return 0
    for entry in drifted:
        print(f"drift: {entry}")
    if check:
        print(
            f"{len(drifted)} pin(s) stale; re-run without --check to record "
            "the current state"
        )
        return 1
    manifest_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # Reload through the validator so a re-pin can never produce a manifest the
    # gate then rejects.
    load_traceability_manifest(manifest_path)
    print(f"re-pinned {len(drifted)} digest(s) in {manifest_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="tj-ee5f")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest_path = (
        REPO_ROOT / ".codex" / "stages" / args.stage / "traceability-manifest.json"
    )
    if not manifest_path.is_file():
        print(f"no traceability manifest for stage {args.stage}", file=sys.stderr)
        return 2
    try:
        return repin(manifest_path, repo_root=REPO_ROOT, check=args.check)
    except ManifestValidationError as exc:
        print(f"manifest error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
