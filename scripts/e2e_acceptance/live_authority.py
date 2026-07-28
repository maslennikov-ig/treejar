"""Local-only bridge from protected live inputs to an authority bundle.

The module intentionally has no command-line or transport surface.  Its
single builder reads a closed set of owner-provided files from a mode-0700
directory and returns only digest-bound receipt metadata.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ValidationError
from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.manifest import ManifestValidationError, validate_preflight
from scripts.e2e_acceptance.policy import TrustedAcceptanceRegistry
from scripts.e2e_acceptance.schemas import (
    AuthorizationManifest,
    PreflightObservation,
    PreflightRequest,
)


class LiveAuthorityValidationError(ValueError):
    """Protected live input is missing, unsafe, or differs from its binding."""


_INPUT_DIRECTORY = "live-authority-inputs"
INPUT_REFS = (
    "authorization-v1.json",
    "preflight-request.json",
    "preflight-observation.json",
    "authorized-action-specs.json",
    "store-identities.json",
    "adapter-ids.json",
    "collector-ids.json",
    "execution-authorities.json",
)


@dataclass(frozen=True)
class LiveAuthorityBundle:
    """Redacted result of committing the fixed protected authority inputs."""

    receipt: execution.AuthorityBundleReceipt
    receipt_digest: str
    input_digests: tuple[tuple[str, str], ...]
    input_refs: tuple[str, ...]
    receipt_ref: str


def _safe_run_id(run_id: str) -> None:
    try:
        execution._validate_run_id(run_id)
    except execution.ExecutionValidationError as exc:
        raise LiveAuthorityValidationError(
            "live authority run identity is unsafe"
        ) from exc


def _assert_mode(path: Path, *, directory: bool) -> None:
    try:
        metadata = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise LiveAuthorityValidationError(
            "protected live authority input is missing"
        ) from exc
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    expected_mode = 0o700 if directory else 0o600
    if stat.S_ISLNK(metadata.st_mode) or not expected_type(metadata.st_mode):
        raise LiveAuthorityValidationError(
            "protected live authority input is a symlink or unsafe type"
        )
    if stat.S_IMODE(metadata.st_mode) != expected_mode:
        raise LiveAuthorityValidationError(
            "protected live authority input permissions are unsafe"
        )


def _input_directory(root: Path, run_id: str) -> Path:
    if not root.is_absolute() or any(
        part in {"", ".", ".."} for part in root.parts[1:]
    ):
        raise LiveAuthorityValidationError("protected live authority root is unsafe")
    try:
        execution._validated_protected_root(root, create=False)
    except execution.ExecutionValidationError as exc:
        raise LiveAuthorityValidationError(
            "protected live authority root is unsafe"
        ) from exc
    _assert_mode(root, directory=True)
    parent = root / _INPUT_DIRECTORY
    directory = parent / run_id
    _assert_mode(parent, directory=True)
    _assert_mode(directory, directory=True)
    try:
        names = set(os.listdir(directory))
    except OSError as exc:
        raise LiveAuthorityValidationError(
            "protected live authority inputs are unreadable"
        ) from exc
    if names != set(INPUT_REFS):
        raise LiveAuthorityValidationError(
            "protected live authority input path-set drift"
        )
    return directory


def _read_model[ModelT: BaseModel](
    root: Path,
    relative: str,
    model: type[ModelT],
    *,
    label: str,
) -> tuple[ModelT, str]:
    _assert_mode(root / relative, directory=False)
    try:
        payload = execution._read_protected(root, relative)
        value = model.model_validate(json.loads(payload))
    except (
        execution.ExecutionValidationError,
        ValidationError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise LiveAuthorityValidationError(
            f"protected {label} input is invalid"
        ) from exc
    return value, hashlib.sha256(payload).hexdigest()


def _receipt_window(
    authorization: AuthorizationManifest, now: datetime
) -> tuple[datetime, datetime]:
    expires_at = min(authorization.expires_at, now + timedelta(minutes=5))
    if now >= expires_at:
        raise LiveAuthorityValidationError("live authority receipt window is expired")
    return now, expires_at


def _input_ref(run_id: str, name: str) -> str:
    return f"{_INPUT_DIRECTORY}/{run_id}/{name}"


def build_live_authority_bundle(
    *,
    registry: TrustedAcceptanceRegistry,
    protected_root: Path,
    run_id: str,
    current_time: datetime | None = None,
) -> LiveAuthorityBundle:
    """Commit the exact live inputs from fixed protected references.

    No action outcome, digest, target, permission, quota, or authority value is
    accepted from the caller.  Those facts are only read from the protected
    input directory and checked by the established manifest and execution
    contracts before the bundle is committed.
    """

    if not isinstance(registry, TrustedAcceptanceRegistry):
        raise LiveAuthorityValidationError("trusted acceptance registry is required")
    _safe_run_id(run_id)
    now = current_time or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise LiveAuthorityValidationError("live authority time must be timezone-aware")
    _input_directory(protected_root, run_id)
    authorization, authorization_digest = _read_model(
        protected_root,
        _input_ref(run_id, "authorization-v1.json"),
        AuthorizationManifest,
        label="authorization manifest",
    )
    request, request_digest = _read_model(
        protected_root,
        _input_ref(run_id, "preflight-request.json"),
        PreflightRequest,
        label="preflight request",
    )
    observation, observation_digest = _read_model(
        protected_root,
        _input_ref(run_id, "preflight-observation.json"),
        PreflightObservation,
        label="preflight observation",
    )
    action_specs, action_specs_digest = _read_model(
        protected_root,
        _input_ref(run_id, "authorized-action-specs.json"),
        execution.AuthorizedActionSpecs,
        label="action specs",
    )
    stores, stores_digest = _read_model(
        protected_root,
        _input_ref(run_id, "store-identities.json"),
        execution.StoreIdentities,
        label="store identities",
    )
    adapters, adapters_digest = _read_model(
        protected_root,
        _input_ref(run_id, "adapter-ids.json"),
        execution.AuthorityAdapterIds,
        label="adapter IDs",
    )
    collectors, collectors_digest = _read_model(
        protected_root,
        _input_ref(run_id, "collector-ids.json"),
        execution.AuthorityCollectorIds,
        label="collector IDs",
    )
    authorities, authorities_digest = _read_model(
        protected_root,
        _input_ref(run_id, "execution-authorities.json"),
        execution.ProtectedExecutionAuthorities,
        label="execution authorities",
    )
    try:
        validate_preflight(authorization, observation, request, now=now)
        exact_ids = tuple(
            [
                *authorization.scenario_binding.scenario_ids,
                *authorization.scenario_binding.evidence_block_ids,
            ]
        )
        if (
            len(exact_ids) != 29
            or exact_ids != registry.compiled_plan.execution_ids
            or set(authorization.scenario_binding.executable_input_digests)
            != set(registry.compiled_plan.execution_ids)
        ):
            raise LiveAuthorityValidationError(
                "live authority execution/input binding drift"
            )
        issued_at, expires_at = _receipt_window(authorization, now)
        receipt = execution.commit_execution_authority_bundle(
            registry=registry,
            protected_root=protected_root,
            run_id=run_id,
            authorization=authorization,
            request=request,
            observation=observation,
            action_specs=action_specs,
            store_ids=stores,
            adapter_ids=adapters,
            collector_ids=collectors,
            task1_bindings=execution.Task1AuthorityBindings(
                schema_version="noor-e2e-task1-authority-bindings/v2",
                authorization_digest=registry.task1_authorization_digest,
                input_digests=registry.task1_input_digests,
            ),
            execution_authorities=authorities,
            receipt_issued_at=issued_at,
            receipt_expires_at=expires_at,
        )
    except ManifestValidationError as exc:
        raise LiveAuthorityValidationError("live preflight validation drift") from exc
    except execution.ExecutionValidationError as exc:
        raise LiveAuthorityValidationError("live authority binding drift") from exc

    digest_pairs = (
        (INPUT_REFS[0], authorization_digest),
        (INPUT_REFS[1], request_digest),
        (INPUT_REFS[2], observation_digest),
        (INPUT_REFS[3], action_specs_digest),
        (INPUT_REFS[4], stores_digest),
        (INPUT_REFS[5], adapters_digest),
        (INPUT_REFS[6], collectors_digest),
        (INPUT_REFS[7], authorities_digest),
    )
    return LiveAuthorityBundle(
        receipt=receipt,
        receipt_digest=hashlib.sha256(
            execution._canonical_bytes(receipt.model_dump(mode="json"))
        ).hexdigest(),
        input_digests=digest_pairs,
        input_refs=tuple(_input_ref(run_id, name) for name in INPUT_REFS),
        receipt_ref=f"authority-bundles/{run_id}/receipt.json",
    )
