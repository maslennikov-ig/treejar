"""Assemble the live-acceptance authority bundle from owner decisions.

`tj-hr0z`. Nothing wrote these eight files and no document said how, so
`tj-ee5f.1` sat blocked from 2026-07-28: the previous bundle expired at 17:12
that day and the procedure lived only in the head of whoever ran it.

The timings are why this has to be a script rather than a checklist. A preflight
observation is stale after 15 minutes and the authority receipt window is 5, so
the bundle cannot be prepared in advance and filled in later. Everything has to
land in one sitting.

What the script does **not** do is decide. Quotas, the recipient, permissions,
callback types and the cleanup method come from a decisions file the owner
writes, and the grant is a transcription of that file, not an invention of it.
Run `--template` to get the decisions file to fill in.

    uv run python scripts/e2e_acceptance/prepare_live_authority.py --template > decisions.json
    # ... owner edits decisions.json, someone gathers a fresh identity readback ...
    uv run python scripts/e2e_acceptance/prepare_live_authority.py \
        --decisions decisions.json --identity identity.json

Read `docs/runbooks/live-acceptance-authority.md` first.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.e2e_acceptance.execution import store_root_digest  # noqa: E402

LIVE_ROOT = REPO_ROOT / ".git" / "codex-orchestration" / "noor-e2e-acceptance" / "live"

_SUBSYSTEMS = (
    "application_native_webhook",
    "crm_contact_create",
    "crm_deal_create",
    "crm_stage_transition",
    "feedback_synthetic",
    "followup_synthetic",
    "load_conversations",
    "outbound_media",
    "outbound_text",
    "provider_originated_canary",
    "quotation_create",
    "referral_synthetic",
    "sale_order_create",
    "telegram_alert",
    "telegram_callback",
    "voice_fixture",
)

DECISIONS_TEMPLATE: dict[str, Any] = {
    "_readme": (
        "Owner decisions. Every field here is a grant of permission. A dry gate "
        "keeps quotas at 0 with empty permissions and produces a BLOCKED result "
        "by construction, which is what the 2026-07-28 run did. A scoring run "
        "needs non-zero quotas and real permissions, and will send real "
        "WhatsApp messages and write real Zoho records."
    ),
    "issuer": "project-owner-explicit-goal-authorization",
    "allowed_executor": "codex-primary-agent",
    "allowed_source": "owner-confirmed-goal-and-fresh-production-readbacks",
    "window_minutes": 20,
    "targets": {
        "recipient": "<owner-provided isolated test number, e.g. +7...>",
        "telegram_target": "<telegram chat id>",
        "wazzup_channel": "<wazzup channel id the bot listens on>",
    },
    "test_data_identities": ["owner-provided-isolated-synthetic-recipient"],
    "quotas": {
        "max_cost_usd": 0.0,
        "max_messages": 0,
        "max_model_calls": 0,
        "max_scenarios": 29,
        "subsystem_quotas": dict.fromkeys(_SUBSYSTEMS, 0),
    },
    "permissions": [],
    "callback_types": [],
    "cleanup_method": "gate-only-zero-external-action-no-cleanup-required",
    "adapter_ids": ["fake-local-adapter"],
    "authorized_action_specs": [],
    "stop_conditions": [
        "stop on runtime identity drift",
        "stop on protected target drift",
        "stop before any external action",
        "stop if a terminal disposition cannot be independently proven",
    ],
}

IDENTITY_TEMPLATE: dict[str, Any] = {
    "_readme": "Fresh production readback. Stale after 15 minutes.",
    "repository_commit": "<deployed commit sha>",
    "deployed_release_sha": "<same sha>",
    "ci_run_id": "github-actions-<run id>",
    "endpoint": "https://noor.starec.ai",
    "app_version": "<from pyproject>",
    "migration_head": "<alembic_version>",
    "main_model": "<system_configs openrouter_model_main>",
    "fast_model": "<effective fast model>",
    "readback_content_digest": "<sha256 of the readback bundle>",
}

_READBACKS = [
    "production-health-api",
    "production-release-file",
    "production-release-run-file",
    "production-migration-current",
    "production-env-whitelist",
]


def _strip(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if not k.startswith("_")}


def _scenario_binding(previous: pathlib.Path) -> dict[str, Any]:
    """Carry the accepted scenario binding forward.

    The scope is frozen at `AC-01..AC-30`, so the binding does not move between
    runs. Reading it from the last bundle keeps this script from becoming a
    second, divergent definition of the accepted scope.
    """
    request = json.loads((previous / "preflight-request.json").read_text("utf-8"))
    return dict(request["scenario_binding"])


def build_bundle(
    *,
    run_id: str,
    decisions: dict[str, Any],
    identity: dict[str, Any],
    protected_root: pathlib.Path,
    previous_bundle: pathlib.Path,
    now: datetime,
) -> dict[str, Any]:
    decisions = _strip(decisions)
    identity = _strip(identity)
    binding = _scenario_binding(previous_bundle)
    readback_digest = identity.pop("readback_content_digest")

    published = (
        REPO_ROOT
        / ".git"
        / "codex-orchestration"
        / "noor-e2e-acceptance"
        / "published-runs"
        / run_id
    )
    tracked = REPO_ROOT / ".codex" / "stages" / "tj-ee5f" / "results" / run_id

    expires = now + timedelta(minutes=int(decisions["window_minutes"]))
    shared = {
        "quotas": decisions["quotas"],
        "permissions": decisions["permissions"],
        "callback_types": decisions["callback_types"],
        "test_data_identities": decisions["test_data_identities"],
        "cleanup_method": decisions["cleanup_method"],
        "readbacks": _READBACKS,
        "stop_conditions": decisions["stop_conditions"],
        "scenario_binding": binding,
    }

    return {
        "authorization-v1.json": {
            "schema_version": "noor-e2e-authorization/v1",
            "authorization_id": run_id,
            "status": "approved",
            "issuer": decisions["issuer"],
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
            "allowed_executor": decisions["allowed_executor"],
            "allowed_source": decisions["allowed_source"],
            "expected_identity": identity,
            "targets": decisions["targets"],
            **shared,
        },
        "preflight-request.json": shared,
        "preflight-observation.json": {
            "executor": decisions["allowed_executor"],
            "source": decisions["allowed_source"],
            "identity": identity,
            "targets": decisions["targets"],
            "readback_identity": {
                "source_id": "fresh-production-readback-bundle-v1",
                "observed_at": now.isoformat().replace("+00:00", "Z"),
                "content_digest": readback_digest,
            },
        },
        "store-identities.json": {
            "anchor_store_id": "protected-anchor-store",
            "raw_store_id": "protected-published-run-store",
            "tracked_store_id": "tracked-redacted-result-store",
            "anchor_root_digest": store_root_digest(published),
            "raw_root_digest": store_root_digest(published),
            "tracked_root_digest": store_root_digest(tracked),
        },
        "adapter-ids.json": {
            "schema_version": "noor-e2e-authority-adapter-ids/v2",
            "values": decisions["adapter_ids"],
        },
        "authorized-action-specs.json": {
            "schema_version": "noor-e2e-authorized-action-specs/v2",
            "specs": decisions["authorized_action_specs"],
        },
        "collector-ids.json": {
            "schema_version": "noor-e2e-authority-collector-ids/v2",
            "values": ["independent-readback-collector"],
        },
        "execution-authorities.json": {
            "schema_version": "noor-e2e-protected-execution-authorities/v2",
            "client_exclusions": [],
            "side_effect_authority": {
                "issuer": "protected-side-effect-authority",
                "cleanup_authority": decisions["cleanup_method"],
                "cleanup_owner": decisions["allowed_executor"],
                "retention_authorities": [],
            },
        },
    }


def write_bundle(
    bundle: dict[str, Any], *, protected_root: pathlib.Path, run_id: str
) -> pathlib.Path:
    target = protected_root / "live-authority-inputs" / run_id
    target.mkdir(parents=True, exist_ok=False)
    target.chmod(0o700)
    for name, payload in bundle.items():
        path = target / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", "utf-8"
        )
        path.chmod(0o600)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--identity-template", action="store_true")
    parser.add_argument("--decisions", type=pathlib.Path)
    parser.add_argument("--identity", type=pathlib.Path)
    parser.add_argument("--run-id")
    parser.add_argument("--protected-root", type=pathlib.Path, default=LIVE_ROOT)
    parser.add_argument("--previous-bundle", type=pathlib.Path)
    args = parser.parse_args()

    if args.template:
        print(json.dumps(DECISIONS_TEMPLATE, ensure_ascii=False, indent=2))
        return 0
    if args.identity_template:
        print(json.dumps(IDENTITY_TEMPLATE, ensure_ascii=False, indent=2))
        return 0
    if not args.decisions or not args.identity:
        parser.error("--decisions and --identity are required")

    now = datetime.now(UTC).replace(microsecond=0)
    run_id = args.run_id or f"tj-ee5f-live-{now.strftime('%Y%m%dt%H%M%S')}z"
    previous = args.previous_bundle
    if previous is None:
        candidates = sorted((args.protected_root / "live-authority-inputs").iterdir())
        if not candidates:
            parser.error("no previous bundle to read the scenario binding from")
        previous = candidates[-1]

    bundle = build_bundle(
        run_id=run_id,
        decisions=json.loads(args.decisions.read_text("utf-8")),
        identity=json.loads(args.identity.read_text("utf-8")),
        protected_root=args.protected_root,
        previous_bundle=previous,
        now=now,
    )
    target = write_bundle(bundle, protected_root=args.protected_root, run_id=run_id)
    grant = bundle["authorization-v1.json"]
    print(f"run id:     {run_id}")
    print(f"written:    {target}")
    print(f"window:     {grant['issued_at']} .. {grant['expires_at']}")
    print(
        f"quotas:     {json.dumps(grant['quotas']['max_messages'])} messages, "
        f"${grant['quotas']['max_cost_usd']}"
    )
    print("Start the run now; the receipt window is five minutes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
