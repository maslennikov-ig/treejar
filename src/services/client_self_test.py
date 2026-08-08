from __future__ import annotations

from collections import Counter
from html import escape

from src.schemas import ClientSelfTestStatus, ClientSelfTestSubmitRequest

CLIENT_SELF_TEST_STATUS_LABELS: dict[ClientSelfTestStatus, str] = {
    "passed": "Passed",
    "failed": "Incorrect",
    "skipped": "Skipped",
    "not_tested": "Not tested",
}


def clean_optional_text(value: str | None, *, fallback: str = "not specified") -> str:
    cleaned = value.strip() if value else ""
    return cleaned or fallback


def format_client_self_test_summary(body: ClientSelfTestSubmitRequest) -> str:
    counts: Counter[ClientSelfTestStatus] = Counter(item.status for item in body.items)
    tester = escape(clean_optional_text(body.tester_name))
    comment = escape(clean_optional_text(body.overall_comment, fallback="no comment"))

    status_lines = "\n".join(
        f"{label}: {counts.get(status, 0)}"
        for status, label in CLIENT_SELF_TEST_STATUS_LABELS.items()
    )
    failed_items = [item for item in body.items if item.status == "failed"]

    message = (
        "🧪 <b>Customer completed the TreeJar self-test</b>\n\n"
        f"<b>Tester:</b> {tester}\n"
        f"<b>Scenarios submitted:</b> {len(body.items)}\n\n"
        f"<b>Result:</b>\n{status_lines}\n\n"
    )

    if failed_items:
        failed_lines = []
        for item in failed_items[:10]:
            note = clean_optional_text(item.note, fallback="no note")
            failed_lines.append(f"• {escape(item.title)} — {escape(note)}")
        message += "<b>What came out wrong:</b>\n" + "\n".join(failed_lines) + "\n\n"

    message += f"<b>Comment:</b> {comment}"
    return message
