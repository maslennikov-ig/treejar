#!/usr/bin/env python3
"""Run stage close verification based on the repo-local orchestration contract."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tomllib

DEBT_MARKER_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
DEBT_POLICY_REFERENCE_PATTERNS = (
    "TODO/FIXME/HACK/XXX",
    "DEBT_MARKER_PATTERN",
    "debt marker",
    "debt markers",
)
PROJECT_INDEX_REVIEW_MARKER = "project-index: reviewed-no-change"
DOCS_REVIEW_MARKER = "docs-reviewed:"
PLACEHOLDERS = {"", "n/a", "<short cleanup result or blocker>"}
STRUCTURAL_CHANGE_PREFIXES = (
    "app/",
    "apps/",
    "api/",
    "pages/",
    "routes/",
    "packages/",
    "src/api/",
    "src/app/",
    "src/integrations/",
    "src/routes/",
    "src/server/",
    "src/services/",
    "migrations/",
    "db/migrations/",
    "supabase/migrations/",
    ".github/workflows/",
    "scripts/orchestration/",
    "frontend/",
)
STRUCTURAL_CHANGE_FILES = {
    "AGENTS.md",
    "README.md",
    "package.json",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.dev.yml",
    ".codex/orchestrator.toml",
    "src/main.py",
    "src/worker.py",
}
ORCHESTRATION_LEVEL_ORDER = (
    "inner_loop",
    "slice_acceptance",
    "integration",
    "release",
)
LEGACY_LEVEL_ALIASES = {
    "inner": "inner_loop",
    "delta": "slice_acceptance",
}
LEGACY_LEVEL_NAMES = {
    "inner_loop": "inner",
    "slice_acceptance": "delta",
    "integration": "integration",
    "release": "release",
}
VERIFICATION_TIER_ORDER = ("inner", "delta", "integration", "release")
MUST_RUN_REASONS = {
    "prior_failed",
    "missing_evidence",
    "invalid_evidence",
    "environment_changed",
    "provenance_changed",
    "source_changed",
    "required_release_freshness",
}


@dataclass(frozen=True)
class VerificationIdentity:
    level: str
    group: str
    command_digest: str
    source_paths: tuple[str, ...]
    source_digest: str
    artifact_digests: tuple[str, ...]
    environment_digest: str
    allowed_producers: tuple[str, ...]


@dataclass(frozen=True)
class VerificationExecution:
    group: str
    command: str
    identity: VerificationIdentity | None
    evidence_path: pathlib.Path | None
    reusable: bool


def repeated_full_verification_diagnostic(
    level: str,
    execution: VerificationExecution,
    *,
    decision: str,
    must_run_reason: str | None,
) -> str | None:
    """Use the exact reusable-evidence result; legal must-run retries are exempt."""
    if must_run_reason in MUST_RUN_REASONS:
        return None
    if (
        level in {"integration", "release"}
        and execution.reusable
        and decision == "run"
    ):
        return "repeated_full_verification_without_material_source_change"
    return None


def record_sizing_diagnostic(
    repo_root: pathlib.Path,
    stage_id: str,
    code: str,
    *,
    repeated_execution: VerificationExecution | None = None,
) -> None:
    recorder = repo_root / "scripts" / "orchestration" / "record_stage_telemetry.py"
    command = [
        sys.executable,
        str(recorder),
        "--stage",
        stage_id,
        "--sizing-diagnostic",
        code,
    ]
    if code == "repeated_full_verification_without_material_source_change":
        if repeated_execution is None or not repeated_execution.reusable:
            raise SystemExit("repeated verification diagnostic lacks exact reusable evidence")
        command.extend(
            [
                "--prior-result",
                "passed",
                "--prior-reusable",
                "--verification-decision",
                "run",
            ]
        )
    completed = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"failed to record sizing diagnostic through canonical telemetry: "
            f"{(completed.stderr or completed.stdout).strip()}"
        )


def normalize_orchestration_level(value: str | None, *, legacy_default: bool) -> str:
    if value is None or not value.strip():
        return "integration" if legacy_default else "slice_acceptance"
    raw = value.strip().lower()
    normalized = LEGACY_LEVEL_ALIASES.get(raw, raw)
    if normalized not in ORCHESTRATION_LEVEL_ORDER:
        accepted = ", ".join((*ORCHESTRATION_LEVEL_ORDER, *LEGACY_LEVEL_ALIASES))
        raise SystemExit(
            f"unsupported orchestration level: {value!r}; expected one of {accepted}"
        )
    return normalized


def compute_content_digest(
    repo_root: pathlib.Path, relative_paths: list[str]
) -> str:
    """Hash exact repo-relative paths without following symlinks or escapes."""
    root = repo_root.resolve()
    files: set[pathlib.Path] = set()
    for raw in relative_paths:
        relative = pathlib.Path(raw)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"evidence input escapes repository: {raw}")
        candidate = root / relative
        for component in (candidate, *candidate.parents):
            if component == root.parent:
                break
            if component.is_symlink():
                raise ValueError(f"evidence input may not be a symlink: {raw}")
            if component == root:
                break
        resolved = candidate.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"evidence input escapes repository: {raw}")
        if not candidate.exists():
            raise ValueError(f"evidence input does not exist: {raw}")
        if candidate.is_file():
            files.add(candidate)
            continue
        if not candidate.is_dir():
            raise ValueError(f"evidence input is not a file or directory: {raw}")
        for path in candidate.rglob("*"):
            if path.is_symlink():
                raise ValueError(
                    f"evidence input contains a symlink: {path.relative_to(root)}"
                )
            if path.is_file():
                files.add(path)

    hasher = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        hasher.update(len(relative).to_bytes(8, "big"))
        hasher.update(relative)
        hasher.update(len(content).to_bytes(8, "big"))
        hasher.update(content)
    return hasher.hexdigest()


def verification_fingerprint(
    level: str,
    group: str,
    command: str,
    source_digest: str,
    artifact_digests: tuple[str, ...],
    environment_digest: str,
) -> str:
    payload = {
        "level": normalize_orchestration_level(level, legacy_default=False),
        "group": group,
        "command_digest": hashlib.sha256(command.encode("utf-8")).hexdigest(),
        "source_digest": source_digest,
        "artifact_digests": list(artifact_digests),
        "environment_digest": environment_digest,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def load_reusable_evidence(
    path: pathlib.Path, expected: VerificationIdentity
) -> dict[str, object] | None:
    """Return passing evidence only when every reusable identity field matches."""
    if not path.is_file() or path.is_symlink():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    try:
        evidence_level = normalize_orchestration_level(
            document.get("level") if isinstance(document.get("level"), str) else None,
            legacy_default=False,
        )
        expected_level = normalize_orchestration_level(
            expected.level, legacy_default=False
        )
    except SystemExit:
        return None
    exact_fields = {
        "schema_version": "verification-evidence/v1",
        "group": expected.group,
        "command_digest": expected.command_digest,
        "source_paths": list(expected.source_paths),
        "source_digest": expected.source_digest,
        "artifact_digests": list(expected.artifact_digests),
        "environment_digest": expected.environment_digest,
        "result": "passed",
    }
    if evidence_level != expected_level:
        return None
    if any(document.get(key) != value for key, value in exact_fields.items()):
        return None
    producer = document.get("producer")
    if not isinstance(producer, str) or producer not in expected.allowed_producers:
        return None
    if producer == "ci":
        reference = document.get("ci_run_reference")
        if not isinstance(reference, str) or not reference.strip():
            return None
    return document


def _configured_string_list(
    table: object, group: str, *, allow_empty: bool
) -> tuple[str, ...] | None:
    if not isinstance(table, dict):
        return None
    value = table.get(group)
    if not isinstance(value, list) or (not value and not allow_empty):
        return None
    if any(not isinstance(item, str) or not item.strip() for item in value):
        return None
    return tuple(item.strip() for item in value)


def _evidence_directory(
    repo_root: pathlib.Path, contract: dict[str, object], stage_id: str
) -> pathlib.Path | None:
    evidence = contract.get("evidence")
    raw = evidence.get("directory") if isinstance(evidence, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        return None
    relative = pathlib.Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = repo_root / relative
    expected_stage = (repo_root / ".codex" / "stages" / stage_id).resolve()
    resolved = candidate.resolve()
    if resolved.parent != expected_stage or resolved.name != "evidence":
        return None
    for component in (candidate, *candidate.parents):
        if component.is_symlink():
            return None
        if component == repo_root:
            break
    return resolved


def build_verification_execution(
    repo_root: pathlib.Path,
    contract: dict[str, object],
    stage_id: str,
    level: str,
    group: str,
    command: str,
) -> VerificationExecution:
    """Build independently verifiable evidence identity, or fail closed to run."""
    evidence = contract.get("evidence")
    directory = _evidence_directory(repo_root, contract, stage_id)
    if not isinstance(evidence, dict) or directory is None:
        return VerificationExecution(group, command, None, None, False)
    source_paths = _configured_string_list(
        evidence.get("source_paths"), group, allow_empty=False
    )
    artifact_paths = _configured_string_list(
        evidence.get("artifact_paths"), group, allow_empty=True
    )
    environments = evidence.get("environment_digests")
    environment_digest = environments.get(group) if isinstance(environments, dict) else None
    allowed = evidence.get("allowed_producers")
    if (
        source_paths is None
        or artifact_paths is None
        or not isinstance(environment_digest, str)
        or not environment_digest.strip()
        or not isinstance(allowed, list)
        or not allowed
        or any(not isinstance(item, str) or not item.strip() for item in allowed)
    ):
        return VerificationExecution(group, command, None, None, False)
    try:
        source_digest = compute_content_digest(repo_root, list(source_paths))
        artifact_digests = tuple(
            compute_content_digest(repo_root, [path]) for path in artifact_paths
        )
    except ValueError:
        return VerificationExecution(group, command, None, None, False)
    command_digest = hashlib.sha256(command.encode("utf-8")).hexdigest()
    identity = VerificationIdentity(
        level=normalize_orchestration_level(level, legacy_default=False),
        group=group,
        command_digest=command_digest,
        source_paths=source_paths,
        source_digest=source_digest,
        artifact_digests=artifact_digests,
        environment_digest=environment_digest.strip(),
        allowed_producers=tuple(item.strip() for item in allowed),
    )
    evidence_path = directory / f"{group}-{command_digest}.json"
    reusable = load_reusable_evidence(evidence_path, identity) is not None
    return VerificationExecution(group, command, identity, evidence_path, reusable)


def record_verification_evidence(
    execution: VerificationExecution, contract: dict[str, object]
) -> None:
    if execution.identity is None or execution.evidence_path is None:
        return
    evidence = contract.get("evidence")
    producer = evidence.get("producer") if isinstance(evidence, dict) else None
    if not isinstance(producer, str) or producer not in execution.identity.allowed_producers:
        return
    payload: dict[str, object] = {
        "schema_version": "verification-evidence/v1",
        "level": execution.identity.level,
        "group": execution.identity.group,
        "command_digest": execution.identity.command_digest,
        "source_paths": list(execution.identity.source_paths),
        "source_digest": execution.identity.source_digest,
        "artifact_digests": list(execution.identity.artifact_digests),
        "environment_digest": execution.identity.environment_digest,
        "result": "passed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "producer": producer,
    }
    path = execution.evidence_path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _stage_path_error(
    repo_root: pathlib.Path,
    expected_stage: pathlib.Path,
    label: str,
    raw_value: object,
) -> str | None:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return f"{label} is missing"
    raw_path = pathlib.Path(raw_value)
    if raw_path.is_absolute() or ".." in raw_path.parts:
        return f"{label} must be a repo-relative path inside {expected_stage}"
    candidate = repo_root / raw_path
    for component in (candidate, *candidate.parents):
        if component.is_symlink():
            return f"{label} may not traverse a symlink: {raw_value}"
        if component == repo_root:
            break
    resolved = candidate.resolve()
    if resolved.parent != expected_stage:
        return f"{label} points outside exact stage root {expected_stage}: {raw_value}"
    return None


def validate_stage_state(
    repo_root: pathlib.Path, contract: dict[str, object], stage_id: str
) -> list[str]:
    """Return actionable exact-stage reconciliation errors."""
    root = repo_root.resolve()
    expected = root / ".codex" / "stages" / stage_id
    errors: list[str] = []
    if not expected.is_dir() or expected.is_symlink():
        errors.append(f"expected stage directory is missing or unsafe: {expected}")

    workspace = contract.get("workspace")
    current_stage = workspace.get("current_stage_id") if isinstance(workspace, dict) else None
    if current_stage != stage_id:
        errors.append(
            f"workspace.current_stage_id must equal requested stage {stage_id!r}; found {current_stage!r}"
        )

    artifacts = contract.get("artifacts")
    summary = artifacts.get("current_stage_summary") if isinstance(artifacts, dict) else None
    summary_error = _stage_path_error(
        root, expected, "artifacts.current_stage_summary", summary
    )
    if summary_error:
        errors.append(summary_error)

    delegation = contract.get("delegation")
    launcher = delegation.get("launcher") if isinstance(delegation, dict) else None
    inbox = contract.get("completion_inbox")
    if launcher != "none" or isinstance(inbox, dict):
        if not isinstance(inbox, dict):
            errors.append("completion_inbox is required for delegated stage state")
        else:
            for key in ("events_file", "review_state_file"):
                inbox_error = _stage_path_error(
                    root,
                    expected,
                    f"completion_inbox.{key}",
                    inbox.get(key),
                )
                if inbox_error:
                    errors.append(inbox_error)
    return errors


@contextmanager
def stage_closeout_lock(repo_root: pathlib.Path, stage_id: str):
    path = repo_root / ".codex" / "stages" / stage_id / ".closeout.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemExit(f"nested closeout detected for stage {stage_id}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def closeout_idempotency_key(
    stage_id: str, level: str, groups: list[str], fingerprint: str
) -> str:
    payload = {
        "stage_id": stage_id,
        "level": normalize_orchestration_level(level, legacy_default=False),
        "groups": groups,
        "verification_fingerprint": fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _closeout_fingerprint(
    repo_root: pathlib.Path,
    contract: dict[str, object],
    stage_id: str,
    level: str,
    groups: list[str],
    executions: list[VerificationExecution],
) -> str | None:
    if any(execution.identity is None for execution in executions):
        return None

    def file_state(path: pathlib.Path) -> dict[str, object]:
        if path.is_symlink():
            raise SystemExit(f"closeout state path may not be a symlink: {path}")
        if not path.exists():
            return {"path": str(path), "digest": None}
        if not path.is_file():
            raise SystemExit(f"closeout state path must be a file: {path}")
        return {
            "path": str(path),
            "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    stage_root = repo_root / ".codex" / "stages" / stage_id
    artifacts_dir = stage_root / "artifacts"
    state_paths = [
        repo_root / ".codex" / "orchestrator.toml",
        repo_root / str(contract.get("handoff_file", ".codex/handoff.md")),
        stage_root / "summary.md",
    ]
    baseline = contract.get("baseline")
    if isinstance(baseline, dict) and baseline.get("profile") == "balanced-v2.19":
        manifest_path = stage_root / "stage-manifest.json"
        state_paths.append(manifest_path)
        if manifest_path.is_file() and not manifest_path.is_symlink():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise SystemExit(f"cannot read stage sizing manifest: {exc}") from exc
            def sizing_state_path(raw: object, label: str) -> pathlib.Path | None:
                if not isinstance(raw, str) or raw in {"none", "n/a"}:
                    return None
                relative = pathlib.Path(raw)
                if relative.is_absolute() or ".." in relative.parts:
                    raise SystemExit(f"{label} path must be repo-relative")
                candidate = repo_root / relative
                for component in (candidate, *candidate.parents):
                    if component.is_symlink():
                        raise SystemExit(f"{label} path may not traverse a symlink")
                    if component == repo_root:
                        break
                resolved = candidate.resolve()
                root = repo_root.resolve()
                if resolved != root and root not in resolved.parents:
                    raise SystemExit(f"{label} path escapes repository")
                return candidate

            raw_anchor = manifest.get("scope_anchor") if isinstance(manifest, dict) else None
            anchor_path = sizing_state_path(raw_anchor, "scope_anchor")
            if anchor_path is not None:
                state_paths.append(anchor_path)
            raw_ledger = manifest.get("scope_ledger") if isinstance(manifest, dict) else None
            ledger_path = sizing_state_path(raw_ledger, "scope_ledger")
            if ledger_path is not None:
                state_paths.append(ledger_path)
                if ledger_path.is_file() and not ledger_path.is_symlink():
                    try:
                        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError) as exc:
                        raise SystemExit(f"cannot read scope ledger: {exc}") from exc
                    entries = ledger.get("criteria") if isinstance(ledger, dict) else None
                    if isinstance(entries, list):
                        for entry in entries:
                            if not isinstance(entry, dict):
                                continue
                            evidence_path = sizing_state_path(
                                entry.get("evidence_path"), "material boundary evidence"
                            )
                            if evidence_path is not None:
                                state_paths.append(evidence_path)
    inbox = contract.get("completion_inbox")
    if isinstance(inbox, dict):
        for key in ("events_file", "review_state_file"):
            state_paths.append(resolve_inbox_path(repo_root, inbox, key))
    if artifacts_dir.exists():
        state_paths.extend(sorted(artifacts_dir.glob("*.md")))
    payload = {
        "level": level,
        "groups": groups,
        "verification_identities": [
            asdict(execution.identity)
            for execution in executions
            if execution.identity is not None
        ],
        "state": [file_state(path) for path in state_paths],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _load_closeout_result(path: pathlib.Path, key: str) -> dict[str, object] | None:
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("idempotency_key") != key or payload.get("result") != "passed":
        return None
    return payload


def _save_closeout_result(path: pathlib.Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("file must start with YAML frontmatter")

    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("frontmatter closing marker not found")

    return text[4:end], text[end + 5 :]


def parse_artifact(path: pathlib.Path) -> dict[str, object]:
    frontmatter, _ = parse_frontmatter(path.read_text())
    data: dict[str, object] = {}
    current_key: str | None = None

    for raw_line in frontmatter.splitlines():
        if not raw_line:
            continue
        if raw_line.startswith("  - ") or raw_line.startswith("- "):
            if current_key is not None:
                values = data.setdefault(current_key, [])
                if isinstance(values, list):
                    values.append(raw_line.split("-", 1)[1].strip())
            continue
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            data[key] = value
            current_key = None
        else:
            data[key] = []
            current_key = key

    return data


def load_stage_artifacts(repo_root: pathlib.Path, stage_id: str) -> list[dict[str, object]]:
    artifacts_dir = repo_root / ".codex" / "stages" / stage_id / "artifacts"
    if not artifacts_dir.exists():
        return []

    artifacts: list[dict[str, object]] = []
    for path in sorted(artifacts_dir.glob("*.md")):
        artifact = parse_artifact(path)
        artifact_stage = artifact.get("stage_id")
        if artifact_stage != stage_id:
            raise SystemExit(
                f"artifact stage_id mismatch for {path}: "
                f"expected {stage_id!r}, found {artifact_stage!r}"
            )
        artifacts.append(artifact)
    return artifacts


def meaningful_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item.strip().lower()
        for item in value
        if isinstance(item, str)
        and item.strip()
        and not item.strip().startswith("<")
        and item.strip().lower() not in {"n/a", "none"}
    ]


def append_unique(groups: list[str], additions: object) -> None:
    if not isinstance(additions, list):
        return
    for group in additions:
        if isinstance(group, str) and group and group not in groups:
            groups.append(group)


def append_policy_groups(
    groups: list[str],
    verification: dict[str, object],
    mapping: dict[str, object],
    mapping_name: str,
    selector: str,
) -> None:
    additions = mapping.get(selector)
    if not isinstance(additions, list) or not additions:
        raise SystemExit(
            f"verification_policy.{mapping_name}.{selector!r} must be a non-empty command-group list"
        )
    for group in additions:
        if not isinstance(group, str) or not group:
            raise SystemExit(
                f"verification_policy.{mapping_name}.{selector!r} contains an invalid command group"
            )
        if not isinstance(verification.get(group), list) or not verification[group]:
            raise SystemExit(
                f"verification group {group!r} selected by {mapping_name}.{selector!r} is missing, empty, or not a list"
            )
        if group not in groups:
            groups.append(group)


def artifact_metadata(artifacts: list[dict[str, object]]) -> tuple[str, set[str], set[str], bool]:
    levels: set[str] = set()
    risk_tags: set[str] = set()
    surfaces: set[str] = set()
    present = False
    for artifact in artifacts:
        raw_level = artifact.get("orchestration_level")
        if not isinstance(raw_level, str):
            raw_level = artifact.get("verification_tier")
        if isinstance(raw_level, str) and raw_level.strip().lower() != "n/a":
            levels.add(
                normalize_orchestration_level(raw_level, legacy_default=False)
            )
            present = True
        tags = meaningful_list(artifact.get("risk_tags"))
        affected = meaningful_list(artifact.get("affected_surfaces"))
        if tags or affected:
            present = True
        risk_tags.update(tags)
        surfaces.update(affected)

    selected_level = ""
    for level in reversed(ORCHESTRATION_LEVEL_ORDER):
        if level in levels:
            selected_level = level
            break
    return selected_level, risk_tags, surfaces, present


def artifact_has_adaptive_metadata(artifact: dict[str, object]) -> bool:
    return artifact_metadata([artifact])[3]


def select_orchestration_level(
    explicit_level: str | None,
    artifacts: list[dict[str, object]],
    contract: dict[str, object],
) -> str:
    """Apply CLI > highest artifact > contract default precedence."""
    legacy_default = not isinstance(contract.get("orchestration_levels"), dict)
    if explicit_level is not None:
        return normalize_orchestration_level(
            explicit_level, legacy_default=legacy_default
        )
    artifact_level, _, _, _ = artifact_metadata(artifacts)
    if artifact_level:
        return artifact_level
    configured_default: object = None
    if not legacy_default:
        configured_default = contract["orchestration_levels"].get("default")
    return normalize_orchestration_level(
        configured_default if isinstance(configured_default, str) else None,
        legacy_default=legacy_default,
    )


def split_adaptive_artifacts(
    artifacts: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    modern: list[dict[str, object]] = []
    legacy: list[dict[str, object]] = []
    for artifact in artifacts:
        (modern if artifact_has_adaptive_metadata(artifact) else legacy).append(artifact)
    return modern, legacy


def infer_legacy_groups(contract: dict[str, object], artifacts: list[dict[str, object]], include_optional: bool) -> list[str]:
    verification = contract.get("verification", {})
    if not isinstance(verification, dict):
        return []

    groups: list[str] = []
    workspace = contract.get("workspace", {})
    multi_repo = bool(workspace.get("multi_repo")) if isinstance(workspace, dict) else False
    touched_repos: set[str] = set()
    has_changed_files = False

    for artifact in artifacts:
        repo = artifact.get("repo")
        if isinstance(repo, str) and repo and repo not in {"n/a", "<repo-or-n/a>"}:
            touched_repos.add(repo)

        changed_files = artifact.get("changed_files")
        if isinstance(changed_files, list) and any(item and not str(item).startswith("<") for item in changed_files):
            has_changed_files = True

    if multi_repo:
        for repo in sorted(touched_repos):
            group = f"{repo}_commands"
            if group in verification:
                groups.append(group)
    elif has_changed_files and "code_change_commands" in verification:
        groups.append("code_change_commands")

    if include_optional and "stage_level_optional_commands" in verification:
        groups.append("stage_level_optional_commands")

    return groups


def infer_adaptive_groups(
    contract: dict[str, object],
    artifacts: list[dict[str, object]],
    include_optional: bool,
    explicit_level: str | None = None,
) -> list[str]:
    verification = contract.get("verification", {})
    policy = contract.get("verification_policy")
    if not isinstance(verification, dict) or not isinstance(policy, dict):
        raise SystemExit("risk-adaptive verification requires [verification] and [verification_policy]")
    if policy.get("mode") != "risk_adaptive":
        raise SystemExit("verification_policy.mode must be 'risk_adaptive' for artifacts with adaptive metadata")

    artifact_level, risk_tags, surfaces, metadata_present = artifact_metadata(artifacts)
    if not metadata_present and explicit_level is None:
        raise SystemExit("adaptive verification requires artifact metadata")

    legacy_policy = not isinstance(policy.get("level_groups"), dict)
    default_value = policy.get(
        "default_tier" if legacy_policy else "default_level",
        "integration" if legacy_policy else "slice_acceptance",
    )
    raw_level = explicit_level or artifact_level or str(default_value)
    level = normalize_orchestration_level(raw_level, legacy_default=legacy_policy)
    mapping_name = "tier_groups" if legacy_policy else "level_groups"
    level_groups = policy.get(mapping_name)
    if not isinstance(level_groups, dict):
        raise SystemExit(f"verification_policy.{mapping_name} must be a table")
    selector = LEGACY_LEVEL_NAMES[level] if legacy_policy else level

    groups: list[str] = []
    append_policy_groups(groups, verification, level_groups, mapping_name, selector)

    risk_tag_groups = policy.get("risk_tag_groups", {})
    if not isinstance(risk_tag_groups, dict):
        raise SystemExit("verification_policy.risk_tag_groups must be a table")
    for tag in sorted(risk_tags):
        append_policy_groups(groups, verification, risk_tag_groups, "risk_tag_groups", tag)

    surface_groups = policy.get("surface_groups", {})
    if not isinstance(surface_groups, dict):
        raise SystemExit("verification_policy.surface_groups must be a table")
    for surface in sorted(surfaces):
        append_policy_groups(groups, verification, surface_groups, "surface_groups", surface)

    if include_optional and "stage_level_optional_commands" in verification:
        append_unique(groups, ["stage_level_optional_commands"])

    return groups


def infer_groups(
    contract: dict[str, object],
    artifacts: list[dict[str, object]],
    include_optional: bool,
    explicit_level: str | None = None,
) -> list[str]:
    """Choose adaptive groups per modern artifact and preserve legacy evidence for older artifacts."""
    policy = contract.get("verification_policy")
    modern, legacy = split_adaptive_artifacts(artifacts)
    if isinstance(policy, dict) and policy.get("mode") == "risk_adaptive" and high_risk_artifacts_missing_metadata(artifacts):
        raise SystemExit(
            "high-risk changed artifacts require verification_tier, risk_tags, affected_surfaces, and invariants"
        )
    if explicit_level is not None:
        if not isinstance(policy, dict) or policy.get("mode") != "risk_adaptive":
            raise SystemExit(
                "explicit orchestration level requires verification_policy.mode = 'risk_adaptive'"
            )
        return infer_adaptive_groups(
            contract, artifacts, include_optional, explicit_level=explicit_level
        )
    if not modern:
        return infer_legacy_groups(contract, artifacts, include_optional)
    if not isinstance(policy, dict) or policy.get("mode") != "risk_adaptive":
        raise SystemExit("artifacts with adaptive metadata require verification_policy.mode = 'risk_adaptive'")

    groups = infer_adaptive_groups(contract, modern, include_optional)
    if legacy:
        append_unique(groups, infer_legacy_groups(contract, legacy, include_optional))
    return groups


def artifact_has_changed_files(artifact: dict[str, object]) -> bool:
    changed_files = artifact.get("changed_files")
    return isinstance(changed_files, list) and any(
        item and not str(item).startswith("<") for item in changed_files
    )


def high_risk_artifacts_missing_metadata(artifacts: list[dict[str, object]]) -> bool:
    for artifact in artifacts:
        risk_level = artifact.get("risk_level")
        if not (
            artifact_has_changed_files(artifact)
            and isinstance(risk_level, str)
            and risk_level.lower() == "high"
        ):
            continue
        tier = artifact.get("orchestration_level", artifact.get("verification_tier"))
        if not isinstance(tier, str):
            return True
        try:
            normalize_orchestration_level(tier, legacy_default=False)
        except SystemExit:
            return True
        if not meaningful_list(artifact.get("risk_tags")):
            return True
        if not meaningful_list(artifact.get("affected_surfaces")):
            return True
        if not meaningful_list(artifact.get("invariants")):
            return True
    return False


def stage_has_high_risk_artifact(artifacts: list[dict[str, object]]) -> bool:
    for artifact in artifacts:
        risk_level = artifact.get("risk_level")
        if artifact_has_changed_files(artifact) and isinstance(risk_level, str) and risk_level.lower() == "high":
            return True
    return False


def meaningful_scalar(value: object) -> str:
    if not isinstance(value, str):
        return ""
    stripped = value.strip()
    if not stripped or (stripped.startswith("<") and stripped.endswith(">")):
        return ""
    if stripped in PLACEHOLDERS:
        return ""
    return stripped


def check_child_acceptance_cleanup(artifacts: list[dict[str, object]]) -> None:
    failures: list[str] = []
    for artifact in artifacts:
        task_id = meaningful_scalar(artifact.get("task_id")) or "<unknown-task>"
        status = meaningful_scalar(artifact.get("status"))
        accepted = meaningful_scalar(artifact.get("accepted_by_orchestrator"))
        if status not in {"accepted", "merged"} and accepted != "yes":
            continue

        delivery_method = meaningful_scalar(artifact.get("delivery_method"))
        cleanup_status = meaningful_scalar(artifact.get("cleanup_status"))
        cleanup_notes = meaningful_scalar(artifact.get("cleanup_notes"))

        if delivery_method in {"", "not accepted"}:
            failures.append(f"{task_id}: accepted stream missing delivery_method")
        if accepted != "yes":
            failures.append(f"{task_id}: accepted stream missing accepted_by_orchestrator: yes")
        if cleanup_status not in {"cleaned", "blocked"}:
            failures.append(f"{task_id}: accepted stream cleanup_status must be cleaned or blocked")
        if not cleanup_notes:
            failures.append(f"{task_id}: accepted stream missing cleanup_notes")

    if not failures:
        print("child acceptance cleanup OK")
        return

    print("Accepted child streams require mini-closeout before stage close:", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    raise SystemExit(1)


def resolve_inbox_path(
    repo_root: pathlib.Path, inbox: dict[str, object], key: str
) -> pathlib.Path:
    raw_path = inbox.get(key)
    if not isinstance(raw_path, str) or not raw_path:
        raise SystemExit(f"completion_inbox.{key} is required")
    path = pathlib.Path(raw_path)
    if inbox.get("scope", "repo_root") != "git_common_dir":
        return repo_root / path

    common_dir_raw = subprocess.check_output(
        ["git", "rev-parse", "--git-common-dir"], cwd=repo_root, text=True
    ).strip()
    common_dir = pathlib.Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    return common_dir / path


def resolve_review_state_path(repo_root: pathlib.Path, inbox: dict[str, object]) -> pathlib.Path:
    return resolve_inbox_path(repo_root, inbox, "review_state_file")


def load_completion_events(path: pathlib.Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events: list[dict[str, object]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SystemExit(f"cannot read completion events {path}: {exc}") from exc
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"invalid completion event JSON at {path}:{line_number}: {exc}"
            ) from exc
        if not isinstance(event, dict):
            raise SystemExit(f"completion event at {path}:{line_number} must be an object")
        events.append(event)
    return events


def validate_event_artifact_identity(
    repo_root: pathlib.Path, stage_id: str, event: dict[str, object]
) -> list[str]:
    errors: list[str] = []
    event_id = event.get("event_id")
    task_id = event.get("task_id")
    event_stage = event.get("stage_id")
    raw_artifact = event.get("artifact_path")
    if not isinstance(event_id, str) or not event_id:
        errors.append("completion event is missing event_id")
    if not isinstance(task_id, str) or not task_id:
        errors.append(f"event {event_id!r} is missing task_id")
    if event_stage != stage_id:
        errors.append(
            f"event {event_id!r} stage_id {event_stage!r} does not match {stage_id!r}"
        )
    if not isinstance(raw_artifact, str) or not raw_artifact:
        errors.append(f"event {event_id!r} is missing artifact_path")
        return errors
    relative = pathlib.Path(raw_artifact)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"event {event_id!r} artifact_path must be repo-relative")
        return errors
    candidate = repo_root / relative
    for component in (candidate, *candidate.parents):
        if component.is_symlink():
            errors.append(f"event {event_id!r} artifact_path traverses a symlink")
            return errors
        if component == repo_root:
            break
    expected_parent = (repo_root / ".codex" / "stages" / stage_id / "artifacts").resolve()
    try:
        artifact = candidate.resolve(strict=True)
    except OSError:
        errors.append(f"event {event_id!r} artifact does not exist: {raw_artifact}")
        return errors
    if artifact.parent != expected_parent:
        errors.append(f"event {event_id!r} artifact escapes exact stage artifacts root")
        return errors
    try:
        artifact_values = parse_artifact(artifact)
    except (OSError, ValueError) as exc:
        errors.append(f"event {event_id!r} artifact is unreadable: {exc}")
        return errors
    if artifact_values.get("task_id") != task_id:
        errors.append(f"event {event_id!r} task_id does not match artifact task_id")
    if artifact_values.get("stage_id") != stage_id:
        errors.append(f"event {event_id!r} stage_id does not match artifact stage_id")
    return errors


def check_pending_completion_events(
    repo_root: pathlib.Path,
    contract: dict[str, object],
    stage_id: str,
    *,
    exact_identity: bool,
) -> None:
    inbox = contract.get("completion_inbox")
    if not isinstance(inbox, dict):
        return
    events_path = resolve_inbox_path(repo_root, inbox, "events_file")
    state_path = resolve_inbox_path(repo_root, inbox, "review_state_file")
    events = load_completion_events(events_path)
    reviewed = load_reviewed_state(state_path)
    failures: list[str] = []
    relevant: list[dict[str, object]] = []
    for event in events:
        if exact_identity:
            failures.extend(validate_event_artifact_identity(repo_root, stage_id, event))
            relevant.append(event)
        elif event.get("stage_id") == stage_id:
            relevant.append(event)
    pending = [
        event.get("event_id")
        for event in relevant
        if event.get("event_id") not in reviewed
    ]
    if pending:
        failures.append(
            "relevant completion events remain pending: "
            + ", ".join(str(event_id) for event_id in pending)
        )
    if failures:
        raise SystemExit("completion inbox state mismatch:\n- " + "\n- ".join(failures))


def load_reviewed_state(path: pathlib.Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read completion review state {path}: {exc}") from exc
    reviewed = payload.get("reviewed") if isinstance(payload, dict) else None
    if not isinstance(reviewed, dict):
        raise SystemExit(f"completion review state {path} is missing a reviewed object")
    if any(not isinstance(event_id, str) or not isinstance(entry, dict) for event_id, entry in reviewed.items()):
        raise SystemExit(f"completion review state {path} contains an invalid reviewed entry")
    return reviewed


@contextmanager
def review_state_read_lock(path: pathlib.Path):
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def unresolved_blocking_review_findings(
    reviewed: dict[str, dict[str, object]], stage_id: str | None = None
) -> list[str]:
    scoped = {
        event_id: entry
        for event_id, entry in reviewed.items()
        if stage_id is None or entry.get("stage_id") == stage_id
    }
    resolved: set[str] = set()
    for entry in scoped.values():
        if entry.get("decision") != "accepted":
            continue
        if entry.get("verify") != "passed" or not isinstance(entry.get("artifact_path"), str):
            continue
        links = entry.get("resolves_review")
        if isinstance(links, list):
            resolved.update(link for link in links if isinstance(link, str) and link)

    failures: list[str] = []
    for event_id, entry in scoped.items():
        severity = entry.get("severity")
        if severity not in {"P0", "P1"}:
            continue
        decision = entry.get("decision")
        if decision == "accepted":
            failures.append(f"{event_id}: P0/P1 finding cannot be accepted directly; record a linked correction")
        elif event_id not in resolved:
            failures.append(f"{event_id}: {severity} finding has no linked accepted correction")
    return failures


def check_blocking_review_findings(
    repo_root: pathlib.Path, contract: dict[str, object], stage_id: str | None = None
) -> None:
    limits = contract.get("stage_limits")
    if not isinstance(limits, dict) or limits.get("p0_p1_block_acceptance") is not True:
        return
    inbox = contract.get("completion_inbox")
    if not isinstance(inbox, dict):
        raise SystemExit("p0_p1_block_acceptance requires a [completion_inbox] section")
    state_path = resolve_review_state_path(repo_root, inbox)
    with review_state_read_lock(state_path):
        reviewed = load_reviewed_state(state_path)
    failures = unresolved_blocking_review_findings(reviewed, stage_id)
    if not failures:
        print("blocking review findings OK")
        return
    print("P0/P1 review findings must be fixed before stage acceptance:", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    raise SystemExit(1)


def add_e2e_group_when_requested(
    groups: list[str],
    verification: dict[str, object],
    requested: bool,
) -> list[str]:
    if not requested:
        return groups

    commands = verification.get("e2e_commands")
    if not isinstance(commands, list) or not commands:
        print("E2E command is not configured (skipped)")
        return groups

    if "e2e_commands" not in groups:
        groups.append("e2e_commands")
    return groups


def run_shell(command: str, cwd: pathlib.Path, dry_run: bool) -> None:
    print(f"$ {command}")
    if dry_run:
        return
    subprocess.run(command, shell=True, cwd=cwd, executable="/bin/bash", check=True)


def git_available(repo_root: pathlib.Path) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    ).returncode == 0


def git_diff_text(repo_root: pathlib.Path) -> str:
    result = subprocess.run(
        ["git", "diff", "--unified=0", "HEAD", "--", "."],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        return result.stdout

    fallback = subprocess.run(
        ["git", "diff", "--unified=0", "--", "."],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    return fallback.stdout if fallback.returncode == 0 else ""


def changed_line_debt_hits(repo_root: pathlib.Path) -> list[str]:
    if not git_available(repo_root):
        return []

    hits: list[str] = []
    current_file = "<unknown>"
    for line in git_diff_text(repo_root).splitlines():
        if line.startswith("+++ b/"):
            current_file = line.removeprefix("+++ b/")
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:].strip()
        if any(pattern in content for pattern in DEBT_POLICY_REFERENCE_PATTERNS):
            continue
        if DEBT_MARKER_PATTERN.search(content):
            hits.append(f"{current_file}: {content}")

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if untracked.returncode != 0:
        return hits

    for raw_path in untracked.stdout.splitlines():
        path = repo_root / raw_path
        if not path.is_file():
            continue
        try:
            for line_number, line in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
                if any(pattern in line for pattern in DEBT_POLICY_REFERENCE_PATTERNS):
                    continue
                if DEBT_MARKER_PATTERN.search(line):
                    hits.append(f"{raw_path}:{line_number}: {line.strip()}")
        except OSError:
            continue

    return hits


def explicit_defers_body(repo_root: pathlib.Path, contract: dict[str, object]) -> str:
    handoff_path = repo_root / str(contract.get("handoff_file", ".codex/handoff.md"))
    if not handoff_path.exists():
        return ""

    match = re.search(
        r"^## Explicit defers\s*\n(?P<body>.*?)(?=^## |\Z)",
        handoff_path.read_text(),
        re.MULTILINE | re.DOTALL,
    )
    return match.group("body").strip() if match else ""


def git_changed_files(repo_root: pathlib.Path) -> list[str]:
    if not git_available(repo_root):
        return []

    changed: list[str] = []
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "."],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        changed.extend(line.strip() for line in result.stdout.splitlines() if line.strip())

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if untracked.returncode == 0:
        changed.extend(line.strip() for line in untracked.stdout.splitlines() if line.strip())

    return sorted(set(changed))


def stage_summary_text(repo_root: pathlib.Path, stage_id: str) -> str:
    summary = repo_root / ".codex" / "stages" / stage_id / "summary.md"
    if not summary.exists():
        return ""
    return summary.read_text(errors="ignore")


def check_project_index_review(repo_root: pathlib.Path, contract: dict[str, object], stage_id: str) -> None:
    project_index_path = str(contract.get("project_index_file", ".codex/project-index.md"))
    changed = git_changed_files(repo_root)
    if not changed:
        print("project index review OK (no changed files)")
        return

    if project_index_path in changed:
        print("project index review OK (index updated)")
        return

    structural_changes = [
        path
        for path in changed
        if path in STRUCTURAL_CHANGE_FILES
        or any(path.startswith(prefix) for prefix in STRUCTURAL_CHANGE_PREFIXES)
    ]
    if not structural_changes:
        print("project index review OK (no structural changes detected)")
        return

    summary = stage_summary_text(repo_root, stage_id).lower()
    if PROJECT_INDEX_REVIEW_MARKER in summary:
        print("project index review OK (stage summary records no-change review)")
        return

    print("Structural changes require project index review before stage close:", file=sys.stderr)
    for path in structural_changes[:20]:
        print(f"- {path}", file=sys.stderr)
    if len(structural_changes) > 20:
        print(f"- ... {len(structural_changes) - 20} more", file=sys.stderr)
    print(
        f"Update {project_index_path} or add `{PROJECT_INDEX_REVIEW_MARKER}` to the stage summary with a brief reason.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def documentation_impact(changed: list[str]) -> list[str]:
    if not changed:
        return ["none"]

    categories: set[str] = set()
    non_docs = [
        path
        for path in changed
        if not (
            path.endswith(".md")
            or path.startswith("docs/")
            or path.startswith(".codex/stages/")
            or path == ".codex/handoff.md"
        )
    ]
    if not non_docs:
        return ["docs-only"]

    if all(path.startswith("tests/") or "/tests/" in path or path.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", "_test.py")) for path in non_docs):
        categories.add("tests-only")

    structural = [
        path
        for path in non_docs
        if path in STRUCTURAL_CHANGE_FILES
        or any(path.startswith(prefix) for prefix in STRUCTURAL_CHANGE_PREFIXES)
    ]
    if structural:
        categories.add("structural")

    if any(path.startswith(("migrations/", "db/migrations/", "supabase/migrations/")) for path in non_docs):
        categories.add("migration")

    if any(
        path in {"Dockerfile", "docker-compose.yml", "docker-compose.dev.yml"}
        or path.startswith((".github/workflows/", "deploy/", "infra/", "ops/"))
        for path in non_docs
    ):
        categories.add("ops-deploy")

    if any(
        path.startswith(("api/", "src/api/", "src/server/", "packages/shared", "packages/shared-types"))
        or "contract" in path.lower()
        or "schema" in path.lower()
        for path in non_docs
    ):
        categories.add("api-contract")

    if not categories:
        categories.add("behavior")
    return sorted(categories)


def check_documentation_review(repo_root: pathlib.Path, stage_id: str) -> None:
    changed = git_changed_files(repo_root)
    if not changed:
        print("documentation review OK (no changed files)")
        return

    summary = stage_summary_text(repo_root, stage_id).lower()
    if DOCS_REVIEW_MARKER in summary:
        impact = ", ".join(documentation_impact(changed))
        print(f"documentation review OK ({impact})")
        return

    impact = documentation_impact(changed)
    print("Stage close requires a documentation review marker:", file=sys.stderr)
    print(f"- impact: {', '.join(impact)}", file=sys.stderr)
    print(
        "- add `docs-reviewed: updated - <what changed>` or "
        "`docs-reviewed: no-change-needed - <reason>` to the stage summary",
        file=sys.stderr,
    )
    print("- update stable docs first when the impact changes navigation, contracts, ops, migrations, integrations, or durable behavior", file=sys.stderr)
    raise SystemExit(1)


def has_tracked_defer(body: str) -> bool:
    normalized = body.strip().lower()
    if not normalized or normalized in {"none", "- none"}:
        return False
    return re.search(r"\b(bd|bead|beads|task|tracked)\b", normalized) is not None


def check_debt_markers(repo_root: pathlib.Path, contract: dict[str, object]) -> None:
    debt_scan = contract.get("debt_scan", {})
    if isinstance(debt_scan, dict) and debt_scan.get("enabled") is False:
        print("debt marker scan skipped (debt_scan.enabled = false)")
        return

    hits = changed_line_debt_hits(repo_root)
    if not hits:
        print("debt marker scan OK")
        return

    defer_body = explicit_defers_body(repo_root, contract)
    if has_tracked_defer(defer_body):
        print("debt marker scan OK (tracked defer recorded)")
        return

    print("Changed-line debt markers require action before stage close:", file=sys.stderr)
    for hit in hits[:20]:
        print(f"- {hit}", file=sys.stderr)
    if len(hits) > 20:
        print(f"- ... {len(hits) - 20} more", file=sys.stderr)
    print(
        "Fix the marker or create/update a Beads task and list the defer under ## Explicit defers.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", dest="stage_id")
    parser.add_argument("--level")
    parser.add_argument("--verify-group", action="append", default=[])
    parser.add_argument("--include-optional", action="store_true")
    parser.add_argument("--include-e2e", action="store_true")
    parser.add_argument("--skip-process-check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--must-run-reason", choices=sorted(MUST_RUN_REASONS))
    args = parser.parse_args(argv[1:])

    repo_root = pathlib.Path.cwd()
    contract = tomllib.loads((repo_root / ".codex" / "orchestrator.toml").read_text())
    legacy_default = not isinstance(contract.get("orchestration_levels"), dict)
    explicit_level = (
        normalize_orchestration_level(args.level, legacy_default=legacy_default)
        if args.level is not None
        else None
    )
    if explicit_level == "inner_loop" and args.stage_id:
        raise SystemExit("inner_loop is stage-less; omit --stage")
    artifacts = (
        []
        if explicit_level == "inner_loop" or not args.stage_id
        else load_stage_artifacts(repo_root, str(args.stage_id))
    )
    artifact_level = artifact_metadata(artifacts)[0]
    level = select_orchestration_level(args.level, artifacts, contract)
    if level == "inner_loop" and args.stage_id:
        raise SystemExit("inner_loop is stage-less; omit --stage")
    if level != "inner_loop" and not args.stage_id:
        raise SystemExit(f"--stage is required for orchestration level {level}")
    verification = contract.get("verification", {})
    if not isinstance(verification, dict):
        verification = {}
    verification_policy = contract.get("verification_policy")
    reuse_unchanged_evidence = not (
        isinstance(verification_policy, dict)
        and verification_policy.get("reuse_unchanged_evidence") is False
    )

    explicit_groups = bool(args.verify_group)
    _, legacy_artifacts = split_adaptive_artifacts(artifacts)
    route_explicitly = args.level is not None or (
        not artifact_level and not legacy_default
    )
    groups = (
        list(args.verify_group)
        if explicit_groups
        else infer_groups(
            contract,
            artifacts,
            args.include_optional,
            explicit_level=level if route_explicitly else None,
        )
    )
    if not groups and "stage_close_commands" in verification:
        groups = ["stage_close_commands"]
    groups = add_e2e_group_when_requested(
        groups,
        verification,
        requested=args.include_e2e
        or (not explicit_groups and stage_has_high_risk_artifact(legacy_artifacts)),
    )

    def build_executions(stage_id: str) -> list[VerificationExecution]:
        executions: list[VerificationExecution] = []
        for group in groups:
            commands = verification.get(group)
            if not isinstance(commands, list) or not commands:
                raise SystemExit(
                    f"Verification group {group!r} is missing, empty, or not a list"
                )
            for command in commands:
                executions.append(
                    build_verification_execution(
                        repo_root,
                        contract,
                        stage_id,
                        level,
                        group,
                        str(command),
                    )
                )
        return executions

    def run_selected_groups(
        executions: list[VerificationExecution], stage_id: str
    ) -> list[VerificationExecution]:
        completed: list[VerificationExecution] = []
        current_group = ""
        for execution in executions:
            if execution.group != current_group:
                current_group = execution.group
                print(f"== verification group: {current_group} ==")
            if (
                execution.reusable
                and reuse_unchanged_evidence
                and args.must_run_reason is None
            ):
                print(f"evidence reuse: {execution.group} {execution.identity.source_digest if execution.identity else ''}")
                completed.append(execution)
                continue
            run_shell(execution.command, repo_root, args.dry_run)
            if args.dry_run:
                completed.append(execution)
                continue
            refreshed = build_verification_execution(
                repo_root,
                contract,
                stage_id,
                level,
                execution.group,
                execution.command,
            )
            if (
                execution.identity is not None
                and refreshed.identity is not None
                and execution.identity.source_digest
                != refreshed.identity.source_digest
            ):
                print(
                    f"evidence not recorded: source set changed during {execution.group}",
                    file=sys.stderr,
                )
                completed.append(
                    VerificationExecution(
                        refreshed.group,
                        refreshed.command,
                        None,
                        None,
                        False,
                    )
                )
                continue
            record_verification_evidence(refreshed, contract)
            completed.append(
                build_verification_execution(
                    repo_root,
                    contract,
                    stage_id,
                    level,
                    execution.group,
                    execution.command,
                )
            )
        return completed

    if level == "inner_loop":
        executions = [
            VerificationExecution(group, str(command), None, None, False)
            for group in groups
            for command in verification.get(group, [])
        ]
        run_selected_groups(executions, "")
        print("inner_loop verification OK")
        return 0

    stage_id = str(args.stage_id)
    with stage_closeout_lock(repo_root, stage_id):
        baseline = contract.get("baseline")
        stage_state = contract.get("stage_state")
        exact_state_enabled = (
            isinstance(baseline, dict)
            and baseline.get("profile") in {"balanced-v2.18", "balanced-v2.19"}
        ) or (
            isinstance(stage_state, dict)
            and stage_state.get("exact_identity_required") is True
        )
        if isinstance(baseline, dict) and baseline.get("profile") == "balanced-v2.19":
            sizing_linter = (
                repo_root / "scripts" / "orchestration" / "lint_stage_sizing.py"
            )
            if not sizing_linter.is_file():
                raise SystemExit(f"missing stage sizing linter: {sizing_linter}")
            sizing = subprocess.run(
                [sys.executable, str(sizing_linter), "--stage", stage_id],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )
            if sizing.returncode != 0:
                detail = (sizing.stderr or sizing.stdout).strip()
                raise SystemExit(f"stage sizing mismatch:\n{detail}")
        if exact_state_enabled:
            state_errors = validate_stage_state(repo_root, contract, stage_id)
            if state_errors:
                raise SystemExit("stage state mismatch:\n- " + "\n- ".join(state_errors))
        check_pending_completion_events(
            repo_root,
            contract,
            stage_id,
            exact_identity=exact_state_enabled,
        )
        check_blocking_review_findings(repo_root, contract, stage_id)
        check_child_acceptance_cleanup(artifacts)
        check_project_index_review(repo_root, contract, stage_id)
        check_documentation_review(repo_root, stage_id)
        check_debt_markers(repo_root, contract)
        executions = build_executions(stage_id)
        repeated_execution = next(
            (
                execution
                for execution in executions
                if repeated_full_verification_diagnostic(
                    level,
                    execution,
                    decision=(
                        "reuse"
                        if execution.reusable
                        and reuse_unchanged_evidence
                        and args.must_run_reason is None
                        else "run"
                    ),
                    must_run_reason=args.must_run_reason,
                )
                is not None
            ),
            None,
        )
        if repeated_execution is not None:
            if not args.dry_run:
                record_sizing_diagnostic(
                    repo_root,
                    stage_id,
                    "repeated_full_verification_without_material_source_change",
                    repeated_execution=repeated_execution,
                )
            raise SystemExit(
                "repeated_full_verification_without_material_source_change: "
                "an exact passing integration/release identity was ignored; reuse it or record a legal --must-run-reason"
            )
        fingerprint = _closeout_fingerprint(
            repo_root, contract, stage_id, level, groups, executions
        )
        idempotency_key = (
            closeout_idempotency_key(stage_id, level, groups, fingerprint)
            if fingerprint is not None
            else None
        )
        result_path = (
            repo_root / ".codex" / "stages" / stage_id / "closeout-result.json"
        )
        if (
            idempotency_key is not None
            and reuse_unchanged_evidence
            and args.must_run_reason is None
            and all(execution.reusable for execution in executions)
            and _load_closeout_result(result_path, idempotency_key) is not None
        ):
            print(f"stage closeout already recorded: {idempotency_key}")
            return 0
        executions = run_selected_groups(executions, stage_id)

        if not args.skip_process_check:
            enforcement = contract.get("enforcement", {})
            if not isinstance(enforcement, dict):
                enforcement = {}
            entrypoint = enforcement.get(
                "process_verification_entrypoint",
                "scripts/orchestration/run_process_verification.sh",
            )
            if not isinstance(entrypoint, str) or not entrypoint:
                raise SystemExit("Missing process_verification_entrypoint")
            cmd = [str(repo_root / entrypoint), "--stage", stage_id]
            print("$ " + " ".join(cmd))
            if not args.dry_run:
                subprocess.run(cmd, cwd=repo_root, check=True)

        check_pending_completion_events(
            repo_root,
            contract,
            stage_id,
            exact_identity=exact_state_enabled,
        )
        check_blocking_review_findings(repo_root, contract, stage_id)
        final_fingerprint = _closeout_fingerprint(
            repo_root, contract, stage_id, level, groups, executions
        )
        final_key = (
            closeout_idempotency_key(stage_id, level, groups, final_fingerprint)
            if final_fingerprint is not None
            and all(execution.reusable for execution in executions)
            else None
        )
        if not args.dry_run and final_key is not None:
            _save_closeout_result(
                result_path,
                {
                    "schema_version": "stage-closeout-result/v1",
                    "idempotency_key": final_key,
                    "stage_id": stage_id,
                    "orchestration_level": level,
                    "groups": groups,
                    "verification_fingerprint": final_fingerprint,
                    "result": "passed",
                },
            )
    print("stage closeout verification OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
