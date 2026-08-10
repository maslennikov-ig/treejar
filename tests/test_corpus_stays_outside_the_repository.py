"""The client corpus must never enter the working tree.

There is no commit-time net in this repository: no hooks, no secret scanner. The
only things standing between 1400 real customer conversations and git history
are `.gitignore` and this file, and `.gitignore` does not match `dialogs.jsonl`.

The client's note is explicit. Phone numbers and e-mails were removed before the
handover and that was verified, but **client company names and deal amounts
remain in the message text**, so the package is commercially sensitive and lives
in a private store. Their instruction, verbatim: keep it in a private
repository or store, do not commit it to public git.

`.codex/handoff.md` adds the reason a leak is not a thing we could quietly fix
afterwards: "repository-history privacy cleanup is a separate destructive
decision". Prevention is the only control available, so it is tested.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Names that only ever appear in the client package. Deliberately not a content
# scan: a content scan over a 21 MB corpus would be slow and would itself have
# to read the data. These are the filenames the export ships with.
_CORPUS_FILENAMES = frozenset(
    {
        "dialogs.jsonl",
        "dialogs_summary.csv",
        "messages.csv",
        "ПОЯСНИТЕЛЬНАЯ_ЗАПИСКА.md",
    }
)


def _protected_root() -> pathlib.Path:
    """Where the corpus is allowed to be: inside the git common dir, never the tree.

    Resolved through `--git-common-dir` rather than a literal `.git` so a
    worktree lands in the main repository's store instead of its own, which is
    the same rule `scripts/e2e_acceptance/evidence.py` follows for raw evidence.
    """

    common = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    root = pathlib.Path(common)
    if not root.is_absolute():
        root = REPO_ROOT / root
    return root / "codex-orchestration" / "treejar-dialogs-corpus"


def test_no_corpus_file_is_tracked_by_git() -> None:
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    offenders = [
        path for path in tracked if pathlib.PurePath(path).name in _CORPUS_FILENAMES
    ]

    assert not offenders, f"client corpus files are tracked in git: {offenders}"


def test_no_corpus_file_sits_in_the_working_tree() -> None:
    """Untracked counts too: the next `git add -A` would take it."""

    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for name in _CORPUS_FILENAMES
        for path in REPO_ROOT.rglob(name)
        if ".git/" not in path.as_posix()
    ]

    assert not offenders, f"client corpus files are in the working tree: {offenders}"


def test_the_protected_root_is_outside_the_working_tree() -> None:
    root = _protected_root()

    assert ".git" in root.parts, f"corpus store must live under the git dir: {root}"
    assert root.is_relative_to(REPO_ROOT / ".git"), (
        f"corpus store escaped the git dir: {root}"
    )


def test_the_protected_root_is_private_when_it_exists() -> None:
    """Modes match `EvidenceStore`: 0700 on directories, 0600 on files.

    Skipped rather than failed when the corpus is absent, because a clone that
    never received it is a legitimate state and this suite runs in CI.
    """

    root = _protected_root()
    if not root.exists():
        return

    assert root.is_dir() and not root.is_symlink()
    assert root.stat().st_mode & 0o077 == 0, f"{root} is readable by others"
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_dir() or path.is_file():
            assert path.stat().st_mode & 0o077 == 0, f"{path} is readable by others"


def test_no_derived_artifact_carries_corpus_message_text() -> None:
    """Derived artefacts carry ids and integers, never a sentence.

    The rule from the plan: a `dialog_id` may be tracked, the message beside it
    may not. This catches the shape of a leak -- a tracked JSON that has both a
    corpus dialogue id and free text -- without reading the corpus itself.
    """

    offenders: list[str] = []
    for path in (REPO_ROOT / ".codex").rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        serialised = json.dumps(payload, ensure_ascii=False)
        if '"dialog_id"' in serialised and '"text"' in serialised:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert not offenders, f"tracked artifacts pair a dialog_id with text: {offenders}"
