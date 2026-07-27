"""Load and validate immutable Noor E2E acceptance contracts."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from scripts.e2e_acceptance.schemas import (
    AuthorizationManifest,
    AuthorizationStatus,
    EvidenceMode,
    Outcome,
    PreflightObservation,
    PreflightRequest,
    ScenarioSet,
    ScopeSnapshot,
    TraceabilityManifest,
)


class ManifestValidationError(ValueError):
    """A manifest is malformed, inconsistent, or unsafe to execute."""


def _read_object(path: pathlib.Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ManifestValidationError(f"manifest is not a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestValidationError(
            f"manifest is not valid JSON: {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ManifestValidationError(f"manifest root must be an object: {path}")
    return value


def _load_model[ManifestModel: BaseModel](
    path: pathlib.Path,
    model: type[ManifestModel],
    label: str,
) -> ManifestModel:
    try:
        return model.model_validate(_read_object(path))
    except ValidationError as exc:
        raise ManifestValidationError(f"invalid {label}: {exc}") from exc


def _canonical_scope_digest(snapshot: ScopeSnapshot) -> str:
    payload = [
        {
            "criterion_id": item.criterion_id,
            "text_digest": item.text_digest,
        }
        for item in sorted(snapshot.criteria, key=lambda item: item.criterion_id)
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def load_scope_snapshot(path: pathlib.Path) -> ScopeSnapshot:
    snapshot = _load_model(path, ScopeSnapshot, "scope criterion contract")
    criterion_ids: set[str] = set()
    for criterion in snapshot.criteria:
        if criterion.criterion_id in criterion_ids:
            raise ManifestValidationError(
                f"duplicate scope criterion: {criterion.criterion_id}"
            )
        criterion_ids.add(criterion.criterion_id)
        expected = hashlib.sha256(criterion.text.encode("utf-8")).hexdigest()
        if criterion.text_digest != expected:
            raise ManifestValidationError(
                f"scope criterion digest mismatch: {criterion.criterion_id}"
            )
    if snapshot.source_digest != _canonical_scope_digest(snapshot):
        raise ManifestValidationError("scope source digest does not match criteria")
    return snapshot


def load_traceability_manifest(path: pathlib.Path) -> TraceabilityManifest:
    return _load_model(path, TraceabilityManifest, "traceability manifest")


def load_scenario_set(path: pathlib.Path) -> ScenarioSet:
    return _load_model(path, ScenarioSet, "scenario set")


def load_authorization_manifest(path: pathlib.Path) -> AuthorizationManifest:
    return _load_model(path, AuthorizationManifest, "authorization manifest")


def validate_scope_anchor_immutable(
    repo_root: pathlib.Path,
    anchor_path: pathlib.Path,
) -> None:
    repo = repo_root.resolve()
    try:
        relative = anchor_path.resolve(strict=True).relative_to(repo).as_posix()
    except (OSError, ValueError) as exc:
        raise ManifestValidationError("scope anchor is outside the repository") from exc
    history = subprocess.run(
        [
            "git",
            "log",
            "--reverse",
            "--diff-filter=A",
            "--format=%H",
            "--",
            relative,
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    commits = [line for line in history.stdout.splitlines() if line]
    if history.returncode != 0 or not commits:
        raise ManifestValidationError("scope anchor lacks Git creation provenance")
    created = subprocess.run(
        ["git", "show", f"{commits[0]}:{relative}"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if created.returncode != 0:
        raise ManifestValidationError("scope anchor creation blob is unreadable")
    if anchor_path.read_bytes() != created.stdout:
        raise ManifestValidationError(
            "scope anchor differs from immutable creation blob"
        )


def _source_set_digest(traceability: TraceabilityManifest) -> str:
    payload = [
        {
            "source_id": source_id,
            "path": source.path,
            "section": source.section,
            "content_digest": source.content_digest,
        }
        for source_id, source in sorted(traceability.source_registry.items())
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def validate_contract_bundle(
    snapshot: ScopeSnapshot,
    traceability: TraceabilityManifest,
    scenario_set: ScenarioSet,
) -> None:
    if traceability.scope_source_digest != snapshot.source_digest:
        raise ManifestValidationError("traceability scope digest drift")
    if traceability.source_set_digest != _source_set_digest(traceability):
        raise ManifestValidationError("traceability source-set digest drift")
    if set(traceability.outcome_values) != set(Outcome):
        raise ManifestValidationError("traceability outcome vocabulary drift")
    if set(traceability.evidence_mode_values) != set(EvidenceMode):
        raise ManifestValidationError("traceability evidence-mode vocabulary drift")

    scope_by_id = {item.criterion_id: item for item in snapshot.criteria}
    trace_ids = [item.criterion_id for item in traceability.criteria]
    duplicate_trace_ids = _duplicates(trace_ids)
    if duplicate_trace_ids:
        raise ManifestValidationError(
            f"duplicate traceability criteria: {sorted(duplicate_trace_ids)}"
        )
    if set(trace_ids) != set(scope_by_id):
        missing = sorted(set(scope_by_id) - set(trace_ids))
        extra = sorted(set(trace_ids) - set(scope_by_id))
        raise ManifestValidationError(
            f"traceability coverage drift: missing={missing}, extra={extra}"
        )

    scenario_ids = [item.scenario_id for item in scenario_set.scenarios]
    block_ids = [item.block_id for item in scenario_set.evidence_blocks]
    if _duplicates(scenario_ids) or _duplicates(block_ids):
        raise ManifestValidationError("scenario or evidence-block IDs are duplicated")
    known_scenarios = set(scenario_ids)
    known_blocks = set(block_ids)
    known_criteria = set(scope_by_id)
    scenarios_by_id = {item.scenario_id: item for item in scenario_set.scenarios}
    blocks_by_id = {item.block_id: item for item in scenario_set.evidence_blocks}

    for criterion in traceability.criteria:
        if (
            criterion.criterion_text_digest
            != scope_by_id[criterion.criterion_id].text_digest
        ):
            raise ManifestValidationError(
                f"criterion text identity drift: {criterion.criterion_id}"
            )
        missing_scenarios = set(criterion.scenario_ids) - known_scenarios
        missing_blocks = set(criterion.evidence_block_ids) - known_blocks
        if missing_scenarios or missing_blocks:
            raise ManifestValidationError(
                f"unknown evidence owner for {criterion.criterion_id}: "
                f"scenarios={sorted(missing_scenarios)}, "
                f"blocks={sorted(missing_blocks)}"
            )
        mismatched_scenarios = [
            scenario_id
            for scenario_id in criterion.scenario_ids
            if criterion.criterion_id not in scenarios_by_id[scenario_id].criterion_ids
        ]
        mismatched_blocks = [
            block_id
            for block_id in criterion.evidence_block_ids
            if criterion.criterion_id not in blocks_by_id[block_id].criterion_ids
        ]
        if mismatched_scenarios or mismatched_blocks:
            raise ManifestValidationError(
                f"traceability owner mismatch for {criterion.criterion_id}: "
                f"scenarios={mismatched_scenarios}, blocks={mismatched_blocks}"
            )
        unknown_sources = set(criterion.sources) - set(traceability.source_registry)
        if unknown_sources:
            raise ManifestValidationError(
                f"unknown source for {criterion.criterion_id}: "
                f"{sorted(unknown_sources)}"
            )
        for source_id in criterion.sources:
            source = traceability.source_registry[source_id]
            source_path = pathlib.PurePosixPath(source.path)
            if source_path.is_absolute() or ".." in source_path.parts:
                raise ManifestValidationError(
                    f"unsafe source path for {criterion.criterion_id}"
                )

    for scenario in scenario_set.scenarios:
        unknown = set(scenario.criterion_ids) - known_criteria
        if unknown:
            raise ManifestValidationError(
                f"scenario {scenario.scenario_id} has unknown criteria: {sorted(unknown)}"
            )
    for block in scenario_set.evidence_blocks:
        unknown = set(block.criterion_ids) - known_criteria
        if unknown:
            raise ManifestValidationError(
                f"evidence block {block.block_id} has unknown criteria: "
                f"{sorted(unknown)}"
            )

    grounding_criteria = [
        item
        for item in traceability.criteria
        if item.dependency is not None and item.dependency.issue_id == "tj-r1f3"
    ]
    if not grounding_criteria:
        raise ManifestValidationError("tj-r1f3 dependency gate is missing")
    statuses = {
        item.dependency.status for item in grounding_criteria if item.dependency
    }
    if len(statuses) != 1 or not statuses <= {"in_progress", "blocked", "closed"}:
        raise ManifestValidationError("tj-r1f3 dependency status drift")
    status = statuses.pop()
    for criterion in grounding_criteria:
        dependency = criterion.dependency
        if (
            criterion.evidence_mode is not EvidenceMode.EXTERNAL_GATE
            or dependency is None
            or dependency.required_outcome is not Outcome.PASS
            or not dependency.evidence_required
        ):
            raise ManifestValidationError(
                "tj-r1f3 must remain a fail-closed external evidence gate"
            )
        if status == "closed":
            if "tj-r1f3" in criterion.open_known_risks:
                raise ManifestValidationError(
                    "closed tj-r1f3 requires a versioned freshness transition"
                )
        elif "tj-r1f3" not in criterion.open_known_risks:
            raise ManifestValidationError(
                "unresolved tj-r1f3 must remain an explicit non-passing risk"
            )
    grounding = next(
        item for item in grounding_criteria if item.criterion_id == "AC-30"
    )
    required_disposition = (
        "dependency_closed_freshness_required"
        if status == "closed"
        else "hard_dependency_non_pass"
    )
    if grounding.precedence.disposition != required_disposition:
        raise ManifestValidationError(
            "tj-r1f3 gate disposition does not match its versioned state"
        )


def _beads_digest(
    traceability: TraceabilityManifest,
    issues_path: pathlib.Path,
) -> str:
    referenced = {
        issue_id
        for criterion in traceability.criteria
        for issue_id in (
            *criterion.accepted_regressions,
            *criterion.open_known_risks,
        )
        if issue_id.startswith("tj-")
    }
    referenced.update(
        criterion.dependency.issue_id
        for criterion in traceability.criteria
        if criterion.dependency is not None
    )
    records: dict[str, dict[str, Any]] = {}
    try:
        for line in issues_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if isinstance(record, dict) and record.get("id") in referenced:
                records[str(record["id"])] = record
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestValidationError(
            f"cannot read relevant Beads provenance: {issues_path}: {exc}"
        ) from exc
    missing = sorted(referenced - set(records))
    if missing:
        raise ManifestValidationError(
            f"relevant Beads provenance is missing records: {missing}"
        )
    payload = [records[issue_id] for issue_id in sorted(records)]
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _source_path(
    repo_root: pathlib.Path, relative: pathlib.PurePosixPath
) -> pathlib.Path:
    candidate = repo_root / relative
    if candidate.is_file():
        return candidate
    if relative.as_posix() != ".beads/issues.jsonl":
        return candidate
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if common.returncode != 0:
        return candidate
    common_path = pathlib.Path(common.stdout.strip())
    if not common_path.is_absolute():
        common_path = repo_root / common_path
    return common_path.resolve().parent / relative


def validate_source_digests(
    traceability: TraceabilityManifest,
    repo_root: pathlib.Path,
) -> None:
    root = repo_root.resolve()
    for source_id, source in traceability.source_registry.items():
        relative = pathlib.PurePosixPath(source.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ManifestValidationError(f"{source_id} has an unsafe source path")
        path = _source_path(root, relative)
        if path.is_symlink() or not path.is_file():
            raise ManifestValidationError(
                f"{source_id} source is not a regular file: {path}"
            )
        if relative.as_posix() == ".beads/issues.jsonl":
            actual = _beads_digest(traceability, path)
        else:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != source.content_digest:
            raise ManifestValidationError(
                f"{source_id} content digest drift: "
                f"expected {source.content_digest}, found {actual}"
            )


def validate_preflight(
    authorization: AuthorizationManifest,
    observation: PreflightObservation,
    request: PreflightRequest,
    *,
    now: datetime,
) -> None:
    if now.tzinfo is None:
        raise ManifestValidationError("preflight time must be timezone-aware")
    if authorization.status is not AuthorizationStatus.APPROVED:
        raise ManifestValidationError("authorization is not approved")
    for field in ("repository_commit", "deployed_release_sha"):
        value = getattr(authorization.expected_identity, field)
        if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
            raise ManifestValidationError(
                f"approved authorization has unresolved exact {field}"
            )
    exact_values = [
        authorization.authorization_id,
        authorization.issuer,
        authorization.allowed_executor,
        authorization.allowed_source,
        *(
            str(value)
            for value in authorization.expected_identity.model_dump().values()
        ),
        *(str(value) for value in authorization.targets.model_dump().values()),
        *authorization.test_data_identities,
        authorization.cleanup_method,
    ]
    unresolved_markers = ("REPLACE", "DRAFT", "NO_LIVE_ACTION", "<", ">")
    if any(
        any(marker in value.upper() for marker in unresolved_markers)
        for value in exact_values
    ):
        raise ManifestValidationError(
            "approved authorization contains an unresolved exact value"
        )
    if now < authorization.issued_at:
        raise ManifestValidationError("authorization is not yet valid")
    if now > authorization.expires_at:
        raise ManifestValidationError("authorization has expired")
    if observation.identity != authorization.expected_identity:
        raise ManifestValidationError("runtime identity drift")
    if observation.targets != authorization.targets:
        raise ManifestValidationError("authorization target drift")
    if (
        observation.executor != authorization.allowed_executor
        or observation.source != authorization.allowed_source
    ):
        raise ManifestValidationError("executor or source drift")
    if request.quotas != authorization.quotas:
        raise ManifestValidationError("authorization quota drift")
    if request.permissions != authorization.permissions:
        raise ManifestValidationError("authorization permission drift")
    if request.callback_types != authorization.callback_types:
        raise ManifestValidationError("authorization callback drift")
    if request.test_data_identities != authorization.test_data_identities:
        raise ManifestValidationError("authorization test-data identity drift")
    if request.cleanup_method != authorization.cleanup_method:
        raise ManifestValidationError("authorization cleanup-method drift")
    if request.readbacks != authorization.readbacks:
        raise ManifestValidationError("authorization readback drift")
