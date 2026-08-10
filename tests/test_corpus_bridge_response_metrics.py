"""Aggregate response metrics without carrying corpus text into artefacts."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path("scripts/corpus_bridge/response_metrics.py")


def _message(role: str, sent_at: str, text: str) -> dict[str, object]:
    return {"role": role, "sent_at": sent_at, "text": text, "type": "text"}


def test_response_metrics_exclude_repeated_boilerplate_and_emit_only_aggregates(
    tmp_path: pathlib.Path,
) -> None:
    corpus = tmp_path / "dialogs.jsonl"
    packets = tmp_path / "packets"
    packets.mkdir()
    boilerplate = "Call us at <PHONE>. " + "x" * 220
    dialogs = [
        {
            "dialog_id": 1,
            "manager": "A",
            "messages": [
                _message("client", "2026-01-01T00:00:00+00:00", "alpha"),
                _message("seller", "2026-01-01T00:00:01+00:00", boilerplate),
                _message("seller", "2026-01-01T00:00:10+00:00", "real answer"),
                _message("client", "2026-01-01T00:00:20+00:00", "omega"),
            ],
            "continuity": {
                "ends_client_no_seller_answer": True,
                "ends_seller_no_client_reply": False,
                "boilerplate_call_footer": True,
            },
        },
        {
            "dialog_id": 2,
            "manager": "B",
            "messages": [
                _message("client", "2026-01-02T00:00:00+00:00", "beta"),
                _message("seller", "2026-01-02T00:00:01+00:00", boilerplate),
                _message("seller", "2026-01-02T00:00:05+00:00", "another answer"),
            ],
            "continuity": {
                "ends_client_no_seller_answer": False,
                "ends_seller_no_client_reply": True,
                "boilerplate_call_footer": True,
            },
        },
    ]
    corpus.write_text(
        "".join(json.dumps(dialog) + "\n" for dialog in dialogs), encoding="utf-8"
    )
    (packets / "S01-r1.json").write_text(
        json.dumps(
            {
                "scenario": "S01",
                "turns": [
                    {
                        "assistant": {"content": "bot answer"},
                        "duration_seconds": 2.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--corpus",
            str(corpus),
            "--packets",
            str(packets),
            "--boilerplate-min-dialogues",
            "2",
            "--bootstrap-samples",
            "200",
            "--seed",
            "7",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["corpus"]["customer_messages"] == 3
    assert result["corpus"]["answered_customer_messages"] == 2
    assert result["corpus"]["coverage_pct"] == 66.67
    assert result["corpus"]["first_reply_observed_dialogues"] == 2
    assert result["corpus"]["first_reply_median_seconds"] == 7.5
    assert result["corpus"]["ends_client_no_seller_answer"] == 1
    assert result["corpus"]["ends_seller_no_client_reply"] == 1
    assert result["corpus"]["excluded_boilerplate_messages"] == 2
    assert result["bot"]["packets"] == 1
    assert result["bot"]["answered_customer_messages"] == 1
    assert result["bot"]["first_reply_median_seconds"] == 2.5
    assert "alpha" not in completed.stdout
    assert "real answer" not in completed.stdout
