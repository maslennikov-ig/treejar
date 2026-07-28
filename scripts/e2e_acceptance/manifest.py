"""Load and validate immutable Noor E2E acceptance contracts."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import stat
import subprocess
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from scripts.e2e_acceptance.schemas import (
    AuthorizationManifest,
    AuthorizationStatus,
    ClientEvidenceRequirement,
    ClientGateResolution,
    EvidenceMode,
    FreshEvidenceRequirement,
    Outcome,
    PreflightObservation,
    PreflightRequest,
    ScenarioExecutionBinding,
    ScenarioSet,
    ScopeSnapshot,
    ScopeSourceProvenance,
    TraceabilityManifest,
)

CRITERION_EVIDENCE_MODE_POLICY: dict[EvidenceMode, frozenset[str]] = {
    EvidenceMode.FRESH: frozenset(
        {
            "AC-01",
            "AC-02",
            "AC-03",
            "AC-04",
            "AC-05",
            "AC-06",
            "AC-13",
            "AC-17",
            "AC-18",
            "AC-20",
            "AC-23",
            "AC-29",
        }
    ),
    EvidenceMode.REUSED_EXACT: frozenset({"AC-22"}),
    EvidenceMode.EXTERNAL_GATE: frozenset(
        {
            "AC-07",
            "AC-08",
            "AC-09",
            "AC-10",
            "AC-11",
            "AC-12",
            "AC-14",
            "AC-15",
            "AC-16",
            "AC-19",
            "AC-21",
            "AC-24",
            "AC-25",
            "AC-26",
            "AC-27",
            "AC-28",
            "AC-30",
        }
    ),
}
EVIDENCE_BLOCK_MODE_POLICY: dict[EvidenceMode, frozenset[str]] = {
    EvidenceMode.FRESH: frozenset({"EB-RUNTIME", "EB-QUALITY"}),
    EvidenceMode.REUSED_EXACT: frozenset({"EB-SECURITY"}),
    EvidenceMode.EXTERNAL_GATE: frozenset(
        {
            "EB-ADMIN",
            "EB-LOAD",
            "EB-BACKUP",
            "EB-AVAILABILITY",
            "EB-CATALOG-COVERAGE",
            "EB-REFERRAL",
        }
    ),
}
_FROZEN_BEADS_SOURCE_PATH = ".codex/stages/tj-ee5f/frozen-beads-records.jsonl"


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


def _canonical_json_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def build_scenario_binding(
    scenario_set: ScenarioSet,
    scenario_set_path: pathlib.Path,
    *,
    executable_input_digests: dict[str, str],
) -> ScenarioExecutionBinding:
    raw = _read_object(scenario_set_path)
    try:
        on_disk = ScenarioSet.model_validate(raw)
    except ValidationError as exc:
        raise ManifestValidationError(f"invalid canonical scenario set: {exc}") from exc
    if on_disk != scenario_set:
        raise ManifestValidationError("scenario set model differs from canonical file")
    return ScenarioExecutionBinding(
        scenario_set_digest=_canonical_json_digest(raw),
        scenario_set_version=scenario_set.scenario_set_version,
        deterministic_seed=scenario_set.deterministic_seed,
        scenario_ids=[item.scenario_id for item in scenario_set.scenarios],
        evidence_block_ids=[item.block_id for item in scenario_set.evidence_blocks],
        executable_input_digests=executable_input_digests,
    )


def _scope_provenance_digest(provenance: ScopeSourceProvenance) -> str:
    return _canonical_json_digest(
        {
            "criteria_digest": provenance.criteria_digest,
            "anchor_creation_commit": provenance.anchor_creation_commit,
            "anchor_blob_digest": provenance.anchor_blob_digest,
            "beads_records_digest": provenance.beads_records_digest,
        }
    )


def load_scope_provenance(
    path: pathlib.Path,
    *,
    snapshot: ScopeSnapshot,
    repo_root: pathlib.Path,
) -> ScopeSourceProvenance:
    provenance = _load_model(path, ScopeSourceProvenance, "scope provenance")
    if provenance.criteria_digest != snapshot.source_digest:
        raise ManifestValidationError("scope provenance criteria digest drift")
    issue_ids = [record.issue_id for record in provenance.beads_records]
    if sorted(issue_ids) != ["tj-ee5f", "tj-ee5f.1"] or len(set(issue_ids)) != 2:
        raise ManifestValidationError(
            "scope provenance must freeze exact tj-ee5f and tj-ee5f.1 records"
        )
    for record in provenance.beads_records:
        if record.canonical_record.get("id") != record.issue_id:
            raise ManifestValidationError(
                f"scope provenance issue identity drift: {record.issue_id}"
            )
        actual = _canonical_json_digest(record.canonical_record)
        if actual != record.canonical_record_digest:
            raise ManifestValidationError(
                f"scope provenance record digest drift: {record.issue_id}"
            )
    records_digest = _canonical_json_digest(
        [
            {
                "issue_id": record.issue_id,
                "canonical_record_digest": record.canonical_record_digest,
            }
            for record in sorted(
                provenance.beads_records, key=lambda item: item.issue_id
            )
        ]
    )
    if records_digest != provenance.beads_records_digest:
        raise ManifestValidationError("scope provenance Beads records digest drift")
    if provenance.provenance_digest != _scope_provenance_digest(provenance):
        raise ManifestValidationError("scope provenance digest drift")

    validate_scope_anchor_immutable(
        repo_root,
        repo_root / provenance.scope_anchor_path,
    )
    relative = provenance.scope_anchor_path
    created = subprocess.run(
        ["git", "show", f"{provenance.anchor_creation_commit}:{relative}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    if created.returncode != 0:
        raise ManifestValidationError("scope provenance creation commit is invalid")
    if hashlib.sha256(created.stdout).hexdigest() != provenance.anchor_blob_digest:
        raise ManifestValidationError("scope provenance anchor blob digest drift")
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
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    commits = [line for line in history.stdout.splitlines() if line]
    if not commits or commits[0] != provenance.anchor_creation_commit:
        raise ManifestValidationError("scope provenance creation commit drift")
    return provenance


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
            "content_digest": source.content_digest,
            "sections": [
                section.model_dump(mode="json") for section in source.sections
            ],
        }
        for source_id, source in sorted(traceability.source_registry.items())
    ]
    return _canonical_json_digest(payload)


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
    provenance: ScopeSourceProvenance,
    traceability: TraceabilityManifest,
    scenario_set: ScenarioSet,
) -> None:
    if traceability.scope_source_digest != snapshot.source_digest:
        raise ManifestValidationError("traceability scope digest drift")
    if (
        traceability.scope_provenance_path
        != ".codex/goals/tj-ee5f/scope-source-provenance.json"
        or traceability.scope_provenance_digest != provenance.provenance_digest
        or provenance.criteria_digest != snapshot.source_digest
    ):
        raise ManifestValidationError("traceability scope provenance drift")
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
    actual_criterion_modes = {
        mode: {
            item.criterion_id
            for item in traceability.criteria
            if item.evidence_mode is mode
        }
        for mode in EvidenceMode
    }
    if actual_criterion_modes != CRITERION_EVIDENCE_MODE_POLICY:
        raise ManifestValidationError("criterion evidence-mode policy drift")
    actual_block_modes = {
        mode: {
            item.block_id
            for item in scenario_set.evidence_blocks
            if item.evidence_mode is mode
        }
        for mode in EvidenceMode
    }
    if actual_block_modes != EVIDENCE_BLOCK_MODE_POLICY:
        raise ManifestValidationError("evidence-block mode policy drift")
    scenarios_by_id = {item.scenario_id: item for item in scenario_set.scenarios}
    blocks_by_id = {item.block_id: item for item in scenario_set.evidence_blocks}
    scenario_criteria = {
        criterion_id: {
            scenario.scenario_id
            for scenario in scenario_set.scenarios
            if criterion_id in scenario.criterion_ids
        }
        for criterion_id in known_criteria
    }
    block_criteria = {
        criterion_id: {
            block.block_id
            for block in scenario_set.evidence_blocks
            if criterion_id in block.criterion_ids
        }
        for criterion_id in known_criteria
    }

    for criterion in traceability.criteria:
        if _duplicates(criterion.scenario_ids) or _duplicates(
            criterion.evidence_block_ids
        ):
            raise ManifestValidationError(
                f"bidirectional mapping drift for {criterion.criterion_id}"
            )
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
        if (
            set(criterion.scenario_ids) != scenario_criteria[criterion.criterion_id]
            or set(criterion.evidence_block_ids)
            != block_criteria[criterion.criterion_id]
        ):
            raise ManifestValidationError(
                f"bidirectional mapping drift for {criterion.criterion_id}"
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
        if _duplicates(scenario.criterion_ids):
            raise ManifestValidationError(
                f"bidirectional mapping drift for {scenario.scenario_id}"
            )
        unknown = set(scenario.criterion_ids) - known_criteria
        if unknown:
            raise ManifestValidationError(
                f"scenario {scenario.scenario_id} has unknown criteria: {sorted(unknown)}"
            )
    for block in scenario_set.evidence_blocks:
        if _duplicates(block.criterion_ids):
            raise ManifestValidationError(
                f"bidirectional mapping drift for {block.block_id}"
            )
        unknown = set(block.criterion_ids) - known_criteria
        if unknown:
            raise ManifestValidationError(
                f"evidence block {block.block_id} has unknown criteria: "
                f"{sorted(unknown)}"
            )

    required_grounding_ids = {"AC-07", "AC-30"}
    grounding_criteria = [
        item
        for item in traceability.criteria
        if item.dependency is not None and item.dependency.issue_id == "tj-r1f3"
    ]
    grounding_ids = {item.criterion_id for item in grounding_criteria}
    if grounding_ids != required_grounding_ids:
        raise ManifestValidationError(
            "required grounding dependency set must be exactly AC-07 and AC-30"
        )
    statuses = {
        item.dependency.status for item in grounding_criteria if item.dependency
    }
    if len(statuses) != 1 or not statuses <= {"in_progress", "blocked", "closed"}:
        raise ManifestValidationError("tj-r1f3 dependency status drift")
    status = statuses.pop()
    required_evidence = set(FreshEvidenceRequirement)
    for criterion in grounding_criteria:
        dependency = criterion.dependency
        if (
            criterion.evidence_mode is not EvidenceMode.EXTERNAL_GATE
            or dependency is None
            or dependency.required_outcome is not Outcome.PASS
            or set(dependency.evidence_required) != required_evidence
            or dependency.resolution_outcomes is not None
        ):
            raise ManifestValidationError(
                "tj-r1f3 must remain a fail-closed external evidence gate"
            )
        required_disposition = (
            "dependency_closed_freshness_required"
            if status == "closed"
            else "hard_dependency_non_pass"
        )
        if criterion.precedence.disposition != required_disposition:
            raise ManifestValidationError(
                f"{criterion.criterion_id} grounding gate disposition drift"
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

    client_gate_criteria = [
        item
        for item in traceability.criteria
        if item.dependency is not None and item.dependency.issue_id == "tj-final27.6"
    ]
    if {item.criterion_id for item in client_gate_criteria} != {"AC-21"}:
        raise ManifestValidationError(
            "tj-final27.6 client gate must apply exactly to AC-21"
        )
    client_gate = client_gate_criteria[0]
    dependency = client_gate.dependency
    if dependency is None:
        raise ManifestValidationError("AC-21 client gate is missing")
    resolution_outcomes = dependency.resolution_outcomes or {}
    if resolution_outcomes.get(ClientGateResolution.EXCLUDED_BY_CLIENT) is Outcome.PASS:
        raise ManifestValidationError("client exclusion cannot contribute PASS")
    expected_resolution_outcomes = {
        ClientGateResolution.IMPLEMENTED: Outcome.PASS,
        ClientGateResolution.EXCLUDED_BY_CLIENT: Outcome.EXCLUDED_BY_CLIENT,
    }
    referral_block = blocks_by_id.get("EB-REFERRAL")
    if (
        client_gate.evidence_mode is not EvidenceMode.EXTERNAL_GATE
        or dependency.required_outcome is not Outcome.PASS
        or set(dependency.evidence_required) != set(ClientEvidenceRequirement)
        or resolution_outcomes != expected_resolution_outcomes
        or dependency.status not in {"blocked", "implemented", "excluded_by_client"}
        or referral_block is None
        or "referral_synthetic" not in referral_block.required_permissions
    ):
        raise ManifestValidationError("AC-21 typed client gate policy drift")


def _frozen_beads_digest(
    traceability: TraceabilityManifest,
    content: bytes,
    *,
    source_id: str,
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
    try:
        records = []
        for line in content.decode("utf-8").splitlines():
            record = json.loads(line)
            if (
                not isinstance(record, dict)
                or set(record) != {"canonical_record_digest", "id"}
                or not isinstance(record.get("id"), str)
                or not isinstance(record.get("canonical_record_digest"), str)
                or len(record["canonical_record_digest"]) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in record["canonical_record_digest"]
                )
            ):
                raise ManifestValidationError(
                    f"invalid frozen Beads record: {source_id}"
                )
            records.append(record)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestValidationError(
            f"cannot read frozen Beads provenance: {source_id}: {exc}"
        ) from exc
    record_ids = [record["id"] for record in records]
    missing = sorted(referenced - set(record_ids))
    if missing:
        raise ManifestValidationError(
            f"frozen Beads provenance is missing records: {missing}"
        )
    extra = sorted(set(record_ids) - referenced)
    if extra:
        raise ManifestValidationError(f"extra frozen Beads records: {extra}")
    if len(record_ids) != len(set(record_ids)):
        raise ManifestValidationError("duplicate frozen Beads record identity")
    if record_ids != sorted(record_ids):
        raise ManifestValidationError(
            "frozen Beads records must use canonical ordering"
        )
    canonical = b"".join(
        json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
        for record in records
    )
    if content != canonical:
        raise ManifestValidationError("frozen Beads source bytes are not canonical")
    return hashlib.sha256(content).hexdigest()


def _read_regular_file_at(
    base: pathlib.Path,
    relative: pathlib.PurePosixPath,
    *,
    label: str,
) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None or os.open not in os.supports_dir_fd:
        raise ManifestValidationError(
            "safe source validation requires O_NOFOLLOW, O_DIRECTORY, and dir_fd"
        )
    parts = relative.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ManifestValidationError(f"{label} has an unsafe source path")
    close_on_exec = getattr(os, "O_CLOEXEC", 0)
    root_fd = -1
    directory_fd = -1
    file_fd = -1
    try:
        root_fd = os.open(
            base,
            os.O_RDONLY | directory | nofollow | close_on_exec,
        )
        directory_fd = root_fd
        for component in parts[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | directory | nofollow | close_on_exec,
                dir_fd=directory_fd,
            )
            if directory_fd != root_fd:
                os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(
            parts[-1],
            os.O_RDONLY | nofollow | close_on_exec,
            dir_fd=directory_fd,
        )
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            raise ManifestValidationError(f"{label} source is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(file_fd, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    except ManifestValidationError:
        raise
    except OSError as exc:
        raise ManifestValidationError(
            f"{label} source path is unsafe or contains a symlink: {exc}"
        ) from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if directory_fd >= 0 and directory_fd != root_fd:
            os.close(directory_fd)
        if root_fd >= 0:
            os.close(root_fd)


def _git_common_repo_root(repo_root: pathlib.Path) -> pathlib.Path:
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if common.returncode != 0:
        raise ManifestValidationError("cannot resolve explicit git-common Beads path")
    common_path = pathlib.Path(common.stdout.strip())
    if not common_path.is_absolute():
        common_path = repo_root / common_path
    try:
        return common_path.resolve(strict=True).parent
    except OSError as exc:
        raise ManifestValidationError(
            "cannot resolve explicit git-common Beads root"
        ) from exc


def _section_bytes(
    content: bytes,
    *,
    source_id: str,
    start_locator: str,
    end_locator: str | None,
) -> bytes:
    try:
        lines = content.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError as exc:
        raise ManifestValidationError(
            f"{source_id} source section cannot be read: {exc}"
        ) from exc
    start_matches = [
        index
        for index, line in enumerate(lines)
        if line.rstrip("\r\n") == start_locator
    ]
    if len(start_matches) != 1:
        raise ManifestValidationError(
            f"{source_id} section locator must match exactly once: {start_locator!r}"
        )
    start = start_matches[0]
    end = len(lines)
    if end_locator is not None:
        end_matches = [
            index
            for index, line in enumerate(lines[start + 1 :], start=start + 1)
            if line.rstrip("\r\n") == end_locator
        ]
        if len(end_matches) != 1:
            raise ManifestValidationError(
                f"{source_id} section end locator must match exactly once: "
                f"{end_locator!r}"
            )
        end = end_matches[0]
    return "".join(lines[start:end]).encode("utf-8")


def validate_source_digests(
    traceability: TraceabilityManifest,
    repo_root: pathlib.Path,
) -> None:
    root = repo_root.resolve()
    for source_id, source in traceability.source_registry.items():
        relative = pathlib.PurePosixPath(source.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ManifestValidationError(f"{source_id} has an unsafe source path")
        content = _read_regular_file_at(
            root,
            relative,
            label=source_id,
        )
        if relative.as_posix() == _FROZEN_BEADS_SOURCE_PATH:
            actual = _frozen_beads_digest(
                traceability,
                content,
                source_id=source_id,
            )
            if (
                len(source.sections) != 1
                or source.sections[0].start_locator != "named_frozen_issue_records"
                or source.sections[0].end_locator is not None
                or source.sections[0].content_digest != actual
            ):
                raise ManifestValidationError(
                    "frozen Beads section locator/digest drift"
                )
        else:
            actual = hashlib.sha256(content).hexdigest()
            for section in source.sections:
                section_digest = hashlib.sha256(
                    _section_bytes(
                        content,
                        source_id=source_id,
                        start_locator=section.start_locator,
                        end_locator=section.end_locator,
                    )
                ).hexdigest()
                if section_digest != section.content_digest:
                    raise ManifestValidationError(
                        f"{source_id} section content digest drift: "
                        f"{section.start_locator!r}"
                    )
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

    def contains_placeholder(value: object) -> bool:
        if isinstance(value, str):
            upper = value.strip().upper()
            return (
                upper == "DRAFT"
                or upper.startswith(("DRAFT-", "DRAFT_"))
                or upper == "REPLACE"
                or upper.startswith(("REPLACE-", "REPLACE_"))
                or upper == "NO_LIVE_ACTION"
                or upper.startswith(("NO_LIVE_ACTION-", "NO_LIVE_ACTION_"))
                or (
                    len(upper) > 2
                    and upper.startswith("<")
                    and upper.endswith(">")
                    and "<" not in upper[1:-1]
                    and ">" not in upper[1:-1]
                )
            )
        if isinstance(value, dict):
            return any(
                contains_placeholder(key) or contains_placeholder(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple, set)):
            return any(contains_placeholder(item) for item in value)
        return False

    if contains_placeholder(authorization.model_dump(mode="json")):
        raise ManifestValidationError(
            "approved authorization contains an unresolved exact value"
        )
    if now < authorization.issued_at:
        raise ManifestValidationError("authorization is not yet valid")
    if now >= authorization.expires_at:
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
    if request.stop_conditions != authorization.stop_conditions:
        raise ManifestValidationError("authorization stop-condition drift")
    if request.scenario_binding != authorization.scenario_binding:
        raise ManifestValidationError("authorization scenario execution drift")
