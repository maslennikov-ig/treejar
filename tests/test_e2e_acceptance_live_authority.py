"""Regression coverage for the protected live-authority input bridge."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.e2e_acceptance import execution


def _authority_inputs(registry, *, root: Path, run_id: str, now: datetime):
    from tests.test_e2e_acceptance_trusted_execution import _authority_bundle_inputs

    return _authority_bundle_inputs(
        registry,
        protected_root=root,
        run_id=run_id,
        now=now,
    )


def _write_live_inputs(root: Path, run_id: str, inputs: dict[str, object]) -> None:
    from scripts.e2e_acceptance.live_authority import INPUT_REFS

    directory = root / "live-authority-inputs" / run_id
    directory.mkdir(parents=True)
    os.chmod(root, 0o700)
    os.chmod(root / "live-authority-inputs", 0o700)
    os.chmod(directory, 0o700)
    values = {
        "authorization-v1.json": inputs["authorization"],
        "preflight-request.json": inputs["request"],
        "preflight-observation.json": inputs["observation"],
        "authorized-action-specs.json": inputs["action_specs"],
        "store-identities.json": inputs["store_ids"],
        "adapter-ids.json": inputs["adapter_ids"],
        "collector-ids.json": inputs["collector_ids"],
        "execution-authorities.json": inputs["execution_authorities"],
    }
    assert tuple(values) == tuple(Path(reference).name for reference in INPUT_REFS)
    for filename, value in values.items():
        path = directory / filename
        path.write_text(
            json.dumps(value.model_dump(mode="json"), sort_keys=True),
            encoding="utf-8",
        )
        os.chmod(path, 0o600)


def _bind_expected_stores(registry, run_id: str, inputs: dict[str, object]) -> None:
    expected = execution._expected_store_root_digests(registry, run_id)
    inputs["store_ids"] = execution.StoreIdentities(
        raw_store_id="synthetic-raw-store",
        tracked_store_id="synthetic-tracked-store",
        anchor_store_id="synthetic-anchor-store",
        raw_root_digest=expected["raw"],
        tracked_root_digest=expected["tracked"],
        anchor_root_digest=expected["anchor"],
    )


def _registry():
    from tests.e2e_acceptance_backend import build_canonical_test_registry

    return build_canonical_test_registry()


def test_build_live_authority_bundle_commits_only_fixed_redacted_receipt(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.live_authority import build_live_authority_bundle

    now = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    registry = _registry()
    root = tmp_path / "protected"
    root.mkdir(mode=0o700)
    run_id = "live-local-valid"
    inputs = _authority_inputs(registry, root=root, run_id=run_id, now=now)
    _bind_expected_stores(registry, run_id, inputs)
    _write_live_inputs(root, run_id, inputs)

    result = build_live_authority_bundle(
        registry=registry,
        protected_root=root,
        run_id=run_id,
        current_time=now,
    )

    assert result.receipt.run_id == run_id
    assert len(result.input_digests) == 8
    assert (
        result.receipt_digest
        == hashlib.sha256(
            execution._canonical_bytes(result.receipt.model_dump(mode="json"))
        ).hexdigest()
    )
    rendered = repr(result)
    for raw_value in (
        "synthetic-recipient",
        "synthetic-channel",
        "synthetic-telegram-target",
    ):
        assert raw_value not in rendered


@pytest.mark.parametrize("field", ["identity", "targets"])
def test_build_live_authority_bundle_rejects_preflight_drift(
    tmp_path: Path,
    field: str,
) -> None:
    from scripts.e2e_acceptance.live_authority import (
        LiveAuthorityValidationError,
        build_live_authority_bundle,
    )

    now = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    registry = _registry()
    root = tmp_path / "protected"
    root.mkdir(mode=0o700)
    run_id = f"live-local-{field}"
    inputs = _authority_inputs(registry, root=root, run_id=run_id, now=now)
    observation = inputs["observation"]
    if field == "identity":
        observation = observation.model_copy(
            update={
                "identity": observation.identity.model_copy(
                    update={"app_version": "drift"}
                )
            }
        )
    else:
        observation = observation.model_copy(
            update={
                "targets": observation.targets.model_copy(update={"recipient": "drift"})
            }
        )
    inputs["observation"] = observation
    _write_live_inputs(root, run_id, inputs)

    with pytest.raises(LiveAuthorityValidationError, match="preflight|drift"):
        build_live_authority_bundle(
            registry=registry,
            protected_root=root,
            run_id=run_id,
            current_time=now,
        )


def test_build_live_authority_bundle_rejects_preflight_input_digest_drift(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.live_authority import (
        LiveAuthorityValidationError,
        build_live_authority_bundle,
    )

    now = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    registry = _registry()
    root = tmp_path / "protected"
    root.mkdir(mode=0o700)
    run_id = "live-local-input-drift"
    inputs = _authority_inputs(registry, root=root, run_id=run_id, now=now)
    request = inputs["request"]
    changed_digests = dict(request.scenario_binding.executable_input_digests)
    changed_digests[registry.compiled_plan.execution_ids[0]] = "f" * 64
    inputs["request"] = request.model_copy(
        update={
            "scenario_binding": request.scenario_binding.model_copy(
                update={"executable_input_digests": changed_digests}
            )
        }
    )
    _write_live_inputs(root, run_id, inputs)

    with pytest.raises(LiveAuthorityValidationError, match="preflight|drift"):
        build_live_authority_bundle(
            registry=registry,
            protected_root=root,
            run_id=run_id,
            current_time=now,
        )


def test_build_live_authority_bundle_rejects_expired_manifest(tmp_path: Path) -> None:
    from scripts.e2e_acceptance.live_authority import (
        LiveAuthorityValidationError,
        build_live_authority_bundle,
    )

    now = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    registry = _registry()
    root = tmp_path / "protected"
    root.mkdir(mode=0o700)
    run_id = "live-local-expired"
    inputs = _authority_inputs(registry, root=root, run_id=run_id, now=now)
    authorization = inputs["authorization"]
    inputs["authorization"] = authorization.model_copy(
        update={"expires_at": now - timedelta(seconds=1)}
    )
    _write_live_inputs(root, run_id, inputs)

    with pytest.raises(LiveAuthorityValidationError, match="preflight|expired|drift"):
        build_live_authority_bundle(
            registry=registry,
            protected_root=root,
            run_id=run_id,
            current_time=now,
        )


def test_build_live_authority_bundle_rejects_unsafe_run_path(tmp_path: Path) -> None:
    from scripts.e2e_acceptance.live_authority import (
        LiveAuthorityValidationError,
        build_live_authority_bundle,
    )

    root = tmp_path / "protected"
    root.mkdir(mode=0o700)

    with pytest.raises(LiveAuthorityValidationError, match="identity|unsafe"):
        build_live_authority_bundle(
            registry=_registry(),
            protected_root=root,
            run_id="../escape",
            current_time=datetime(2026, 7, 28, 10, 0, tzinfo=UTC),
        )


def test_build_live_authority_bundle_rejects_non_private_input_file(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance.live_authority import (
        LiveAuthorityValidationError,
        build_live_authority_bundle,
    )

    now = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    registry = _registry()
    root = tmp_path / "protected"
    root.mkdir(mode=0o700)
    run_id = "live-local-permissions"
    inputs = _authority_inputs(registry, root=root, run_id=run_id, now=now)
    _write_live_inputs(root, run_id, inputs)
    os.chmod(root / "live-authority-inputs" / run_id / "preflight-request.json", 0o644)

    with pytest.raises(LiveAuthorityValidationError, match="permissions|unsafe"):
        build_live_authority_bundle(
            registry=registry,
            protected_root=root,
            run_id=run_id,
            current_time=now,
        )


def test_build_live_authority_bundle_rejects_symlinked_input(tmp_path: Path) -> None:
    from scripts.e2e_acceptance.live_authority import (
        LiveAuthorityValidationError,
        build_live_authority_bundle,
    )

    now = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    registry = _registry()
    root = tmp_path / "protected"
    root.mkdir(mode=0o700)
    run_id = "live-local-symlink"
    inputs = _authority_inputs(registry, root=root, run_id=run_id, now=now)
    _write_live_inputs(root, run_id, inputs)
    source = root / "live-authority-inputs" / run_id / "preflight-request.json"
    replacement = root / "replacement.json"
    replacement.write_bytes(source.read_bytes())
    os.chmod(replacement, 0o600)
    source.unlink()
    source.symlink_to(replacement)

    with pytest.raises(LiveAuthorityValidationError, match="symlink|protected"):
        build_live_authority_bundle(
            registry=registry,
            protected_root=root,
            run_id=run_id,
            current_time=now,
        )
