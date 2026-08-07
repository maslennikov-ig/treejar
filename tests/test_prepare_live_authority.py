"""The authority bundle generator (tj-hr0z).

It exists because `tj-ee5f.1` sat blocked from 2026-07-28 with no documented way
to issue a bundle, and because the timings make a checklist impossible: an
observation is stale after 15 minutes and the receipt window is 5.

What these tests protect is the line the generator must not cross. It assembles;
it does not decide. Every field that grants permission has to come from the
owner's decisions file, so that a bundle can never say more than the owner said.
"""

from __future__ import annotations

import json
import pathlib
from datetime import UTC, datetime

import pytest
from scripts.e2e_acceptance.prepare_live_authority import (
    DECISIONS_TEMPLATE,
    build_bundle,
    write_bundle,
)

_NOW = datetime(2026, 8, 7, 5, 0, 0, tzinfo=UTC)

_IDENTITY = {
    "_readme": "ignored",
    "repository_commit": "c977b07c977b07c977b07c977b07c977b07c977b",
    "deployed_release_sha": "c977b07c977b07c977b07c977b07c977b07c977b",
    "ci_run_id": "github-actions-31119246666",
    "endpoint": "https://noor.starec.ai",
    "app_version": "0.4.0",
    "migration_head": "2026_06_04_customer_memory",
    "main_model": "openai/gpt-5.6-luna",
    "fast_model": "deepseek/deepseek-v4-flash",
    "readback_content_digest": "a" * 64,
}


@pytest.fixture
def previous_bundle(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / "prev"
    d.mkdir()
    (d / "preflight-request.json").write_text(
        json.dumps(
            {
                "scenario_binding": {
                    "deterministic_seed": 20260727,
                    "scenario_ids": ["SC-OPEN-EN"],
                    "evidence_block_ids": ["EB-RUNTIME"],
                    "executable_input_digests": ["SC-OPEN-EN", "EB-RUNTIME"],
                    "scenario_set_digest": "b" * 64,
                    "scenario_set_version": "noor-e2e-scenarios/v1",
                }
            }
        ),
        encoding="utf-8",
    )
    return d


def _decisions(**overrides: object) -> dict:
    values = json.loads(json.dumps(DECISIONS_TEMPLATE))
    values["targets"] = {
        "recipient": "+79990000000",
        "telegram_target": "-100",
        "wazzup_channel": "b49b1b9d",
    }
    values.update(overrides)
    return values


def _build(previous_bundle: pathlib.Path, tmp_path: pathlib.Path, **overrides):
    return build_bundle(
        run_id="tj-ee5f-live-20260807t050000z",
        decisions=_decisions(**overrides),
        identity=dict(_IDENTITY),
        protected_root=tmp_path,
        previous_bundle=previous_bundle,
        now=_NOW,
    )


def test_the_bundle_has_exactly_the_eight_expected_files(
    previous_bundle: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """The path set is validated exactly, so a missing file fails the run."""
    bundle = _build(previous_bundle, tmp_path)

    assert set(bundle) == {
        "authorization-v1.json",
        "preflight-request.json",
        "preflight-observation.json",
        "store-identities.json",
        "adapter-ids.json",
        "authorized-action-specs.json",
        "collector-ids.json",
        "execution-authorities.json",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("permissions", ["send_whatsapp"]),
        ("callback_types", ["delivery"]),
        ("cleanup_method", "owner-managed-cleanup"),
        ("adapter_ids", ["live-wazzup-adapter"]),
    ],
)
def test_no_grant_is_invented(
    field: str, value: object, previous_bundle: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Every permission-bearing field is a transcription, never a default.

    If the generator could widen any of these on its own, the executing agent
    would be authorising itself and the control would be gone.
    """
    bundle = _build(previous_bundle, tmp_path, **{field: value})
    grant = bundle["authorization-v1.json"]
    request = bundle["preflight-request.json"]

    if field == "adapter_ids":
        assert bundle["adapter-ids.json"]["values"] == value
    else:
        assert grant[field] == value
        assert request[field] == value


def test_the_default_template_grants_nothing(
    previous_bundle: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """An owner who edits only the targets gets a dry gate, not a live run."""
    grant = _build(previous_bundle, tmp_path)["authorization-v1.json"]

    assert grant["permissions"] == []
    assert grant["callback_types"] == []
    assert grant["quotas"]["max_messages"] == 0
    assert grant["quotas"]["max_cost_usd"] == 0.0
    assert all(v == 0 for v in grant["quotas"]["subsystem_quotas"].values())


def test_the_grant_and_the_observation_pin_the_same_identity(
    previous_bundle: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """The preflight refuses if the live runtime disagrees with either."""
    bundle = _build(previous_bundle, tmp_path)

    assert (
        bundle["authorization-v1.json"]["expected_identity"]
        == bundle["preflight-observation.json"]["identity"]
    )
    assert (
        "readback_content_digest"
        not in bundle["authorization-v1.json"]["expected_identity"]
    )
    assert "_readme" not in bundle["authorization-v1.json"]["expected_identity"]


def test_the_window_comes_from_the_owner(
    previous_bundle: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    grant = _build(previous_bundle, tmp_path, window_minutes=5)["authorization-v1.json"]

    assert grant["issued_at"] == "2026-08-07T05:00:00Z"
    assert grant["expires_at"] == "2026-08-07T05:05:00Z"


def test_the_written_bundle_is_owner_only(
    previous_bundle: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """The loader refuses inputs that are group or world readable."""
    bundle = _build(previous_bundle, tmp_path)

    target = write_bundle(
        bundle, protected_root=tmp_path, run_id="tj-ee5f-live-20260807t050000z"
    )

    assert target.stat().st_mode & 0o077 == 0
    for path in target.iterdir():
        assert path.stat().st_mode & 0o077 == 0, path.name
