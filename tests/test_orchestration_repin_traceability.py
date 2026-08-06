"""The current-state re-pin step (tj-feet.11).

A traceability manifest pins the exact text an acceptance was written against.
Two of its sources — `.codex/orchestrator.toml` and `.codex/handoff.md` — are
declared by `AGENTS.md` to be current state, so every stage that does its
ordinary job moves them and three manifest tests fail on a digest mismatch that
says nothing about what changed.

The re-pin step records that movement. What matters is that it records only
that movement: a frozen requirement drifting must still fail loudly, or the
step becomes a way to launder a real change.

These run against a copy of the repository's own manifest rather than a
hand-built one, because the step reloads what it writes through the real
validator and a fixture that could not survive that check would prove nothing.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

import pytest
from scripts.orchestration.repin_traceability_sources import (
    MUTABLE_SOURCE_PATHS,
    repin,
)

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_REAL_MANIFEST = (
    _REPO_ROOT / ".codex" / "stages" / "tj-ee5f" / "traceability-manifest.json"
)
_STALE = "0" * 64


def _digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A throwaway repository root whose current state has moved on."""
    (tmp_path / ".codex").mkdir()
    for name in ("handoff.md", "orchestrator.toml"):
        shutil.copy(_REPO_ROOT / ".codex" / name, tmp_path / ".codex" / name)
    shutil.copy(_REPO_ROOT / "AGENTS.md", tmp_path / "AGENTS.md")
    with (tmp_path / ".codex" / "handoff.md").open("a", encoding="utf-8") as handle:
        handle.write("\nA later stage moved current state.\n")
    return tmp_path


@pytest.fixture
def manifest(repo: pathlib.Path) -> pathlib.Path:
    path = repo / "traceability-manifest.json"
    shutil.copy(_REAL_MANIFEST, path)
    return path


def _registry(manifest: pathlib.Path) -> dict:
    return json.loads(manifest.read_text(encoding="utf-8"))["source_registry"]


def test_check_reports_drift_and_writes_nothing(
    repo: pathlib.Path, manifest: pathlib.Path
) -> None:
    before = manifest.read_text(encoding="utf-8")

    assert repin(manifest, repo_root=repo, check=True) == 1
    assert manifest.read_text(encoding="utf-8") == before


def test_a_current_state_file_is_re_pinned_to_what_it_now_says(
    repo: pathlib.Path, manifest: pathlib.Path
) -> None:
    assert repin(manifest, repo_root=repo, check=False) == 0

    handoff = _registry(manifest)["runtime-truth"]

    assert handoff["content_digest"] == _digest(repo / ".codex" / "handoff.md")


def test_a_frozen_source_is_left_drifted_on_purpose(
    repo: pathlib.Path, manifest: pathlib.Path
) -> None:
    """The safety property. `AGENTS.md` is not current state, so it still fails.

    Widening this is a contract change, not a bug fix — which is why the set is
    a module constant and why this test names it.
    """
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["source_registry"]["repo-contract"]["content_digest"] = _STALE
    manifest.write_text(json.dumps(document), encoding="utf-8")

    repin(manifest, repo_root=repo, check=False)

    assert _registry(manifest)["repo-contract"]["content_digest"] == _STALE


def test_re_pinning_is_idempotent(repo: pathlib.Path, manifest: pathlib.Path) -> None:
    repin(manifest, repo_root=repo, check=False)

    assert repin(manifest, repo_root=repo, check=True) == 0


def test_an_unmoved_manifest_reports_nothing_to_do(manifest: pathlib.Path) -> None:
    """Against the repository as it stands, the pins are already current."""
    assert repin(manifest, repo_root=_REPO_ROOT, check=True) == 0


def test_the_mutable_set_is_exactly_what_the_contract_declares() -> None:
    assert set(MUTABLE_SOURCE_PATHS) == {
        ".codex/orchestrator.toml",
        ".codex/handoff.md",
    }
