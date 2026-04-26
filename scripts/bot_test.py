#!/usr/bin/env python3
"""Reliable live smoke helper for the Noor bot webhook."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load_dotenv_values() -> dict[str, str]:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if not candidate.exists():
            continue

        values: dict[str, str] = {}
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    return {}


def env_default(name: str, dotenv_values: dict[str, str], fallback: str = "") -> str:
    return os.getenv(name) or dotenv_values.get(name, fallback)


def build_conversations_url(base_url: str, phone: str, page_size: int = 5) -> str:
    query = urllib.parse.urlencode({"phone": phone, "page_size": page_size})
    return f"{base_url.rstrip('/')}/api/v1/conversations/?{query}"


def build_conversation_detail_url(base_url: str, conversation_id: str) -> str:
    return f"{base_url.rstrip('/')}/api/v1/conversations/{conversation_id}"


def build_api_headers(api_key: str) -> dict[str, str]:
    if not api_key:
        return {}
    return {"X-API-Key": api_key}


def parse_json_response(
    body: str, url: str, content_type: str | None
) -> dict[str, Any]:
    normalized_content_type = (content_type or "").lower()
    stripped = body.lstrip()
    if stripped.startswith("<") or (
        normalized_content_type and "json" not in normalized_content_type
    ):
        raise ValueError(
            f"Expected JSON from {url}, got {content_type or 'unknown content type'}"
        )

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Expected JSON from {url}, got invalid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object from {url}, got {type(data).__name__}")

    return data


def parse_api_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def normalize_started_at(started_at: datetime) -> datetime:
    """Align local timestamps with second-precision API message timestamps."""
    return started_at.astimezone(UTC).replace(microsecond=0)


def find_matching_assistant_reply(
    messages: list[dict[str, Any]],
    marker: str,
    started_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    matching_user = find_matching_user_message(messages, marker, started_at)
    if matching_user is None:
        return None

    matching_user_time = parse_api_datetime(str(matching_user["created_at"]))

    sorted_messages = sorted(
        messages,
        key=lambda message: parse_api_datetime(
            message.get("created_at", started_at.isoformat())
        ),
    )

    for message in sorted_messages:
        created_at_raw = message.get("created_at")
        if not created_at_raw:
            continue
        created_at = parse_api_datetime(created_at_raw)
        role = message.get("role")

        if role == "assistant" and created_at >= matching_user_time:
            return matching_user, message

    return None


def find_matching_user_message(
    messages: list[dict[str, Any]],
    marker: str,
    started_at: datetime,
) -> dict[str, Any] | None:
    started_at = normalize_started_at(started_at)
    matching_user: dict[str, Any] | None = None

    sorted_messages = sorted(
        messages,
        key=lambda message: parse_api_datetime(
            message.get("created_at", started_at.isoformat())
        ),
    )

    for message in sorted_messages:
        created_at_raw = message.get("created_at")
        if not created_at_raw:
            continue
        created_at = parse_api_datetime(created_at_raw)
        role = message.get("role")
        content = message.get("content") or ""

        if role == "user" and marker in content and created_at >= started_at:
            matching_user = message

    return matching_user


def http_json(
    url: str,
    *,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> tuple[int, dict[str, Any]]:
    payload = None if data is None else json.dumps(data).encode("utf-8")
    request_headers = dict(headers or {})
    if payload is not None:
        request_headers.setdefault("Content-Type", "application/json")
    last_incomplete_error: http.client.IncompleteRead | None = None

    for _ in range(3):
        request = urllib.request.Request(
            url,
            data=payload,
            headers=request_headers,
            method="POST" if payload is not None else "GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                parsed = parse_json_response(
                    body,
                    url,
                    response.headers.get("Content-Type"),
                )
                return response.status, parsed
        except http.client.IncompleteRead as exc:
            last_incomplete_error = exc
            time.sleep(1)
            continue
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{url} returned HTTP {exc.code}: {body}") from exc

    raise RuntimeError(
        f"{url} returned an incomplete HTTP body"
    ) from last_incomplete_error


def send_webhook_message(
    base_url: str,
    phone: str,
    author_type: str,
    text: str,
    message_id: str,
    sent_at: datetime,
    channel_id: str,
) -> int:
    payload = build_webhook_payload(
        phone=phone,
        author_type=author_type,
        text=text,
        message_id=message_id,
        sent_at=sent_at,
        channel_id=channel_id,
    )
    status, _ = http_json(
        f"{base_url.rstrip('/')}/api/v1/webhook/wazzup",
        data=payload,
    )
    return status


def build_webhook_payload(
    *,
    phone: str,
    author_type: str,
    text: str,
    message_id: str,
    sent_at: datetime,
    channel_id: str,
) -> dict[str, Any]:
    return {
        "messages": [
            {
                "messageId": message_id,
                "chatId": phone,
                "chatType": "whatsapp",
                "authorType": author_type,
                "channelId": channel_id,
                "text": text,
                "dateTime": sent_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "type": "text",
                "status": "inbound",
            }
        ]
    }


def poll_for_reply(
    base_url: str,
    phone: str,
    marker: str,
    started_at: datetime,
    wait_secs: int,
    api_key: str,
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    last_seen_conversations: list[str] = []
    candidate_conversation_ids: list[str] = []
    conversation_headers = build_api_headers(api_key)

    for _ in range(wait_secs):
        time.sleep(1)
        _, conversations = http_json(
            build_conversations_url(base_url, phone),
            headers=conversation_headers,
        )
        items = conversations.get("items", [])

        if not isinstance(items, list):
            raise RuntimeError("Conversation list returned unexpected payload shape")

        last_seen_conversations = [str(item.get("id", "")) for item in items]

        for item in items:
            conversation_id = item.get("id")
            if not conversation_id:
                continue

            _, detail = http_json(
                build_conversation_detail_url(base_url, str(conversation_id)),
                headers=conversation_headers,
            )
            messages = detail.get("messages", [])
            if not isinstance(messages, list):
                raise RuntimeError(
                    "Conversation detail returned unexpected messages shape"
                )

            if (
                str(conversation_id) not in candidate_conversation_ids
                and find_matching_user_message(messages, marker, started_at) is not None
            ):
                candidate_conversation_ids.append(str(conversation_id))

            matched = find_matching_assistant_reply(messages, marker, started_at)
            if matched is None:
                continue

            user_message, assistant_message = matched
            return str(conversation_id), detail, user_message, assistant_message

    for _ in range(3):
        for conversation_id in candidate_conversation_ids:
            _, detail = http_json(
                build_conversation_detail_url(base_url, conversation_id),
                headers=conversation_headers,
            )
            messages = detail.get("messages", [])
            if not isinstance(messages, list):
                continue

            matched = find_matching_assistant_reply(messages, marker, started_at)
            if matched is None:
                continue

            user_message, assistant_message = matched
            return conversation_id, detail, user_message, assistant_message
        time.sleep(1)

    raise RuntimeError(
        "No matching assistant reply received within wait window. "
        f"Last conversations checked: {last_seen_conversations}"
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    dotenv_values = load_dotenv_values()
    parser = argparse.ArgumentParser(
        description="Send a single message to the bot webhook and wait for a correlated reply.",
    )
    parser.add_argument("message", help="Message text to send to the bot")
    parser.add_argument(
        "-p",
        "--phone",
        default=env_default("BOT_TEST_PHONE", dotenv_values, "+70000000099"),
        help="Chat phone number (default: +70000000099)",
    )
    parser.add_argument(
        "-u",
        "--url",
        default=env_default("BOT_TEST_URL", dotenv_values, "https://noor.starec.ai"),
        help="Base URL (default: https://noor.starec.ai)",
    )
    parser.add_argument(
        "-a",
        "--author",
        default="client",
        choices=["client", "manager", "bot"],
        help="Author type: client|manager|bot (default: client)",
    )
    parser.add_argument(
        "-w",
        "--wait",
        default=20,
        type=int,
        help="Seconds to wait for a correlated bot reply (default: 20)",
    )
    parser.add_argument(
        "-c",
        "--channel-id",
        default=env_default(
            "BOT_TEST_CHANNEL_ID",
            dotenv_values,
            env_default("WAZZUP_CHANNEL_ID", dotenv_values),
        ),
        help="Wazzup channelId used by the live runtime",
    )
    parser.add_argument(
        "--api-key",
        default=env_default(
            "BOT_TEST_API_KEY",
            dotenv_values,
            env_default("API_KEY", dotenv_values),
        ),
        help="Internal API key for protected conversation polling",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    marker = f"[smoke:{uuid.uuid4().hex[:8]}]"
    message_id = f"smoke-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    started_at = normalize_started_at(datetime.now(UTC))
    sent_text = f"{args.message}\n{marker}"
    api_key = args.api_key.strip()

    print("=" * 57)
    print(f"Bot Test | {started_at.strftime('%H:%M:%S UTC')}")
    print(f"URL:      {args.url}")
    print(f"Phone:    {args.phone}")
    print(f"Author:   {args.author}")
    print(f"Channel:  {args.channel_id or '(missing)'}")
    print(f"API key:  {'configured' if api_key else '(missing)'}")
    print(f"Marker:   {marker}")
    print(f"Msg ID:   {message_id}")
    print(f"Message:  {args.message}")
    print("=" * 57)

    if not args.channel_id:
        print(
            "ERROR: channel id is required; set --channel-id or WAZZUP_CHANNEL_ID/BOT_TEST_CHANNEL_ID.",
            file=sys.stderr,
        )
        return 1

    if not api_key:
        print(
            "ERROR: API key is required for conversation polling; set --api-key, BOT_TEST_API_KEY, or API_KEY.",
            file=sys.stderr,
        )
        return 1

    try:
        webhook_status = send_webhook_message(
            base_url=args.url,
            phone=args.phone,
            author_type=args.author,
            text=sent_text,
            message_id=message_id,
            sent_at=started_at,
            channel_id=args.channel_id,
        )
        if webhook_status != 200:
            print(f"ERROR: webhook returned HTTP {webhook_status}", file=sys.stderr)
            return 1

        print("Webhook accepted (HTTP 200)")
        print(f"Waiting up to {args.wait}s for a correlated reply...")

        conversation_id, detail, user_message, assistant_message = poll_for_reply(
            base_url=args.url,
            phone=args.phone,
            marker=marker,
            started_at=started_at,
            wait_secs=args.wait,
            api_key=api_key,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("=" * 57)
    print(f"Conversation ID: {conversation_id}")
    print(f"Conversation Updated: {detail.get('updated_at')}")
    print(f"Sales Stage: {detail.get('sales_stage')}")
    print(f"Escalation Status: {detail.get('escalation_status')}")
    print(f"User Message Time: {user_message.get('created_at')}")
    print(f"Assistant Time:    {assistant_message.get('created_at')}")
    print(f"Assistant Model:   {assistant_message.get('model')}")
    print()
    print("Assistant Reply:")
    print(assistant_message.get("content", "")[:1200])
    print("=" * 57)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
