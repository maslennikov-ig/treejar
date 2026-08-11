"""The replay that proves a guard change kept the stored replies."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "corpus_bridge"
    / "replay_policy_chain.py"
)
_spec = importlib.util.spec_from_file_location("replay_policy_chain", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
replay_policy_chain = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(replay_policy_chain)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_the_two_conventions_read_different_stored_fields() -> None:
    """`raw` is the model's text; `baseline` is whatever the fixture stored.

    They differ on the rounds recorded after the harness started shipping its
    own output, where `content` is already past the guards. Naming both is the
    point: a replay that silently picks one cannot be checked by a reader.
    """

    generation = {"content": "shipped text", "raw_content": "model text"}

    assert replay_policy_chain._source_text(generation, "raw") == "model text"
    assert replay_policy_chain._source_text(generation, "baseline") == "shipped text"
    assert replay_policy_chain._source_text({"content": "only"}, "raw") == "only"


def test_the_aggregate_digest_ignores_the_order_records_arrive_in() -> None:
    first = {
        "run": "b",
        "dialog_id": 2,
        "raw_digest": _digest("b"),
        "rendered_digest": _digest("B"),
    }
    second = {
        "run": "a",
        "dialog_id": 1,
        "raw_digest": _digest("a"),
        "rendered_digest": _digest("A"),
    }

    assert replay_policy_chain.aggregate_digest(
        [first, second]
    ) == replay_policy_chain.aggregate_digest([second, first])


def test_compare_names_a_changed_reply_a_changed_source_and_a_missing_record() -> None:
    """Three failures that mean different things, reported as three lines.

    A changed reply is the thing this replay exists to catch. A changed source
    means the protected store moved under us, which is not a guard defect and
    must not be reported as one. A missing record means the replay covered less
    than the baseline, which would otherwise read as a pass.
    """

    baseline: dict[str, Any] = {
        "records": [
            {"run": "r", "dialog_id": 1, "raw_digest": "x", "rendered_digest": "y"},
            {"run": "r", "dialog_id": 2, "raw_digest": "x", "rendered_digest": "y"},
            {"run": "r", "dialog_id": 3, "raw_digest": "x", "rendered_digest": "y"},
        ]
    }
    replayed = [
        {"run": "r", "dialog_id": 1, "raw_digest": "x", "rendered_digest": "y"},
        {"run": "r", "dialog_id": 2, "raw_digest": "x", "rendered_digest": "CHANGED"},
        {"run": "r", "dialog_id": 4, "raw_digest": "x", "rendered_digest": "y"},
    ]

    mismatches = replay_policy_chain.compare(baseline, replayed)

    assert "r/2: rendered reply changed" in mismatches
    assert "r/4: not in baseline" in mismatches
    assert "r/3: not replayed" in mismatches
    assert replay_policy_chain.compare(baseline, baseline["records"]) == []


def test_a_written_baseline_carries_its_schema_and_can_be_compared_back(
    tmp_path: Path,
) -> None:
    records = [
        {
            "run": "r",
            "dialog_id": 1,
            "raw_digest": _digest("a"),
            "rendered_digest": _digest("A"),
            "flags": [],
        }
    ]
    written = {
        "schema_version": replay_policy_chain.SCHEMA_VERSION,
        "source_runs": ["r"],
        "record_count": len(records),
        "aggregate_digest": replay_policy_chain.aggregate_digest(records),
        "records": records,
    }
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(written), encoding="utf-8")

    reloaded = json.loads(path.read_text(encoding="utf-8"))

    assert reloaded["schema_version"] == "treejar-protected-policy-replay/v1"
    assert replay_policy_chain.compare(reloaded, records) == []
