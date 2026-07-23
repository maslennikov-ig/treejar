from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.schemas.common import EscalationStatus
from src.services.escalation_state import (
    EscalationAction,
    classify_pending_escalation,
)

_SUPPRESSED_TELEGRAM_RESULT = {"ok": True, "result": {"suppressed": True}}
_MANIFEST_SCHEMA = "treejar-escalation-reconciliation/v1"


class ManifestValidationError(ValueError):
    """The archived manifest is invalid or no longer matches database state."""


@dataclass
class EscalationAlertMocks:
    send_message_with_inline_keyboard: AsyncMock
    send_document: AsyncMock


@contextmanager
def maybe_suppress_external_escalation_alerts() -> Iterator[
    EscalationAlertMocks | None
]:
    """Suppress Telegram sends while preserving notify_manager_escalation DB behavior."""
    if os.getenv("ALLOW_REAL_ESCALATIONS") == "1":
        yield None
        return

    with ExitStack() as stack:
        send_keyboard = stack.enter_context(
            patch(
                "src.integrations.notifications.escalation.TelegramClient.send_message_with_inline_keyboard",
                new=AsyncMock(return_value=_SUPPRESSED_TELEGRAM_RESULT),
            )
        )
        send_document = stack.enter_context(
            patch(
                "src.integrations.notifications.escalation.TelegramClient.send_document",
                new=AsyncMock(return_value=_SUPPRESSED_TELEGRAM_RESULT),
            )
        )
        yield EscalationAlertMocks(
            send_message_with_inline_keyboard=send_keyboard,
            send_document=send_document,
        )


def _manifest_digest(manifest: dict[str, Any]) -> str:
    digest_input = {key: value for key, value in manifest.items() if key != "digest"}
    encoded = json.dumps(
        digest_input,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _record_from_pair(
    escalation: Escalation,
    conversation: Conversation,
    *,
    now: datetime,
    stale_after_days: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    classification = classify_pending_escalation(
        escalation_id=escalation.id,
        conversation_id=conversation.id,
        phone=conversation.phone,
        conversation_status=conversation.status,
        conversation_escalation_status=conversation.escalation_status,
        escalation_status=escalation.status,
        escalation_created_at=escalation.created_at,
        now=now,
        stale_after_days=stale_after_days,
    )
    record = {
        "escalation_id": str(classification.escalation_id),
        "conversation_id": str(classification.conversation_id),
        "source": classification.source.value,
        "validity": classification.validity.value,
        "action": classification.action.value,
        "classification_reason": classification.reason,
        "age_days": classification.age_days,
        "conversation_status": classification.conversation_status,
        "conversation_escalation_status": (
            classification.conversation_escalation_status
        ),
        "escalation_status": classification.escalation_status,
    }
    if classification.action is not EscalationAction.RESOLVE:
        return record, None

    action = {
        "escalation_id": str(classification.escalation_id),
        "conversation_id": str(classification.conversation_id),
        "expected": {
            "escalation_status": classification.escalation_status,
            "conversation_status": classification.conversation_status,
            "conversation_escalation_status": (
                classification.conversation_escalation_status
            ),
        },
        "target": {
            "escalation_status": EscalationStatus.RESOLVED.value,
            "conversation_status": classification.conversation_status,
            "conversation_escalation_status": (
                classification.conversation_escalation_status
            ),
        },
        "classification_reason": classification.reason,
    }
    return record, action


def build_reconciliation_manifest(
    rows: list[tuple[Escalation, Conversation]],
    *,
    now: datetime,
    stale_after_days: int,
) -> dict[str, Any]:
    """Build a privacy-safe exact-ID audit manifest without writing state."""
    records: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    for escalation, conversation in sorted(rows, key=lambda row: str(row[0].id)):
        record, action = _record_from_pair(
            escalation,
            conversation,
            now=now,
            stale_after_days=stale_after_days,
        )
        records.append(record)
        if action is not None:
            actions.append(action)

    manifest: dict[str, Any] = {
        "schema_version": _MANIFEST_SCHEMA,
        "generated_at": now.astimezone(UTC).isoformat(),
        "stale_after_days": stale_after_days,
        "summary": {
            "total_pending": len(records),
            "safe_action_count": len(actions),
            "human_review_count": len(records) - len(actions),
            "source_counts": {
                source: sum(record["source"] == source for record in records)
                for source in sorted({record["source"] for record in records})
            },
        },
        "records": records,
        "actions": actions,
    }
    manifest["digest"] = _manifest_digest(manifest)
    return manifest


def _validated_actions(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != _MANIFEST_SCHEMA:
        raise ManifestValidationError("unsupported manifest schema")
    if manifest.get("digest") != _manifest_digest(manifest):
        raise ManifestValidationError("manifest digest mismatch")

    stale_after_days = manifest.get("stale_after_days")
    if (
        not isinstance(stale_after_days, int)
        or isinstance(stale_after_days, bool)
        or stale_after_days < 1
    ):
        raise ManifestValidationError(
            "manifest stale_after_days must be a positive integer"
        )

    actions = manifest.get("actions")
    if not isinstance(actions, list):
        raise ManifestValidationError("manifest actions must be a list")

    seen: set[str] = set()
    for action in actions:
        if not isinstance(action, dict):
            raise ManifestValidationError("manifest action must be an object")
        escalation_id = action.get("escalation_id")
        conversation_id = action.get("conversation_id")
        expected = action.get("expected")
        target = action.get("target")
        if not isinstance(escalation_id, str) or not isinstance(conversation_id, str):
            raise ManifestValidationError("manifest action IDs must be strings")
        try:
            uuid.UUID(escalation_id)
            uuid.UUID(conversation_id)
        except ValueError as exc:
            raise ManifestValidationError(
                "manifest action IDs must be valid UUIDs"
            ) from exc
        if escalation_id in seen:
            raise ManifestValidationError("manifest contains duplicate escalation IDs")
        seen.add(escalation_id)
        if not isinstance(expected, dict) or not isinstance(target, dict):
            raise ManifestValidationError("manifest action states must be objects")
        if expected.get("escalation_status") != EscalationStatus.PENDING.value:
            raise ManifestValidationError("manifest expected state must be pending")
        if target.get("escalation_status") != EscalationStatus.RESOLVED.value:
            raise ManifestValidationError("manifest target state must be resolved")
        if target.get("conversation_status") != expected.get(
            "conversation_status"
        ) or target.get("conversation_escalation_status") != expected.get(
            "conversation_escalation_status"
        ):
            raise ManifestValidationError(
                "reconciliation cannot change conversation state"
            )
    return actions


def load_reconciliation_manifest(path: Path) -> dict[str, Any]:
    """Load a previously archived regular-file manifest and verify its digest."""
    if path.is_symlink() or not path.is_file():
        raise ManifestValidationError("apply requires an archived regular file")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestValidationError("archived manifest is not valid JSON") from exc
    if not isinstance(loaded, dict):
        raise ManifestValidationError("archived manifest must contain a JSON object")
    _validated_actions(loaded)
    return loaded


async def audit_pending_escalations(
    db: AsyncSession,
) -> list[tuple[Escalation, Conversation]]:
    """Read every pending row with its current conversation; never mutate."""
    stmt = (
        select(Escalation, Conversation)
        .join(Conversation, Conversation.id == Escalation.conversation_id)
        .where(Escalation.status == EscalationStatus.PENDING.value)
        .order_by(Escalation.id)
    )
    result = await db.execute(stmt)
    return list(result.all())


async def apply_reconciliation_manifest(
    db: AsyncSession,
    manifest: dict[str, Any],
) -> dict[str, list[str]]:
    """Lock and apply only the exact manifest IDs after checking all preconditions."""
    actions = _validated_actions(manifest)
    if not actions:
        return {
            "changed_escalation_ids": [],
            "already_applied_escalation_ids": [],
        }

    action_by_id = {action["escalation_id"]: action for action in actions}
    escalation_ids = [uuid.UUID(escalation_id) for escalation_id in action_by_id]
    stmt = (
        select(Escalation, Conversation)
        .join(Conversation, Conversation.id == Escalation.conversation_id)
        .where(Escalation.id.in_(escalation_ids))
        .order_by(Escalation.id)
        .with_for_update()
    )
    result = await db.execute(stmt)
    rows = list(result.all())
    found_ids = {str(escalation.id) for escalation, _ in rows}
    missing = sorted(set(action_by_id) - found_ids)
    if missing:
        raise ManifestValidationError(
            f"manifest IDs not found; transaction aborted: {', '.join(missing)}"
        )

    changed: list[str] = []
    already_applied: list[str] = []
    for escalation, conversation in rows:
        escalation_id = str(escalation.id)
        action = action_by_id[escalation_id]
        if str(conversation.id) != action["conversation_id"]:
            raise ManifestValidationError(
                f"conversation precondition mismatch for {escalation_id}"
            )

        current = {
            "escalation_status": escalation.status,
            "conversation_status": conversation.status,
            "conversation_escalation_status": conversation.escalation_status,
        }
        if current == action["target"]:
            already_applied.append(escalation_id)
            continue
        if current != action["expected"]:
            raise ManifestValidationError(
                f"state precondition mismatch for {escalation_id}"
            )

        classification = classify_pending_escalation(
            escalation_id=escalation.id,
            conversation_id=conversation.id,
            phone=conversation.phone,
            conversation_status=conversation.status,
            conversation_escalation_status=conversation.escalation_status,
            escalation_status=escalation.status,
            escalation_created_at=escalation.created_at,
            now=datetime.now(UTC),
            stale_after_days=manifest["stale_after_days"],
        )
        if classification.action is not EscalationAction.RESOLVE:
            raise ManifestValidationError(
                f"current state is not safe to resolve for {escalation_id}"
            )

        escalation.status = action["target"]["escalation_status"]
        changed.append(escalation_id)

    return {
        "changed_escalation_ids": sorted(changed),
        "already_applied_escalation_ids": sorted(already_applied),
    }


async def apply_manifest_in_transaction(
    session_factory: Any,
    manifest: dict[str, Any],
) -> dict[str, list[str]]:
    """Commit the exact apply as one unit, rolling back every failure."""
    async with session_factory() as db:
        try:
            result = await apply_reconciliation_manifest(db, manifest)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return result


async def _run_audit(stale_after_days: int) -> dict[str, Any]:
    from src.core.database import async_session_factory

    async with async_session_factory() as db:
        rows = await audit_pending_escalations(db)
    return build_reconciliation_manifest(
        rows,
        now=datetime.now(UTC),
        stale_after_days=stale_after_days,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit pending escalations by default; apply only an archived exact-ID "
            "manifest."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the exact safe actions in --manifest transactionally.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Archived JSON output from a prior default audit run.",
    )
    parser.add_argument(
        "--stale-after-days",
        type=int,
        default=30,
        help="Minimum age for stale active/none mismatches. Default: 30.",
    )
    args = parser.parse_args(argv)
    if args.apply != (args.manifest is not None):
        parser.error("--apply and --manifest must be supplied together")
    if args.stale_after_days < 1:
        parser.error("--stale-after-days must be positive")
    return args


async def _async_main(args: argparse.Namespace) -> dict[str, Any]:
    if not args.apply:
        return await _run_audit(args.stale_after_days)

    from src.core.database import async_session_factory

    manifest = load_reconciliation_manifest(args.manifest)
    result = await apply_manifest_in_transaction(async_session_factory, manifest)
    return {
        "schema_version": "treejar-escalation-reconciliation-result/v1",
        "manifest_digest": manifest["digest"],
        **result,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
        result = asyncio.run(_async_main(args))
    except ManifestValidationError as exc:
        print(f"Escalation reconciliation refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
