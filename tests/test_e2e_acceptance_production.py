"""Contract tests for the local-only production adapter boundary."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI = PROJECT_ROOT / "scripts/run_noor_e2e_acceptance.py"


def test_cli_exposes_resumable_local_only_lifecycle() -> None:
    completed = subprocess.run(
        [sys.executable, str(CLI), "--help"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    for command in (
        "prepare",
        "preflight",
        "execute-resume",
        "record-gate",
        "finalize",
    ):
        assert command in completed.stdout


def test_capability_dispatch_never_uses_scenario_identity() -> None:
    from scripts.e2e_acceptance.production import (
        CapabilityDispatcher,
        FakeHttpTransport,
        ProductionAdapterError,
    )

    transport = FakeHttpTransport(responses={"webhook.inbound": {"ok": True}})
    dispatcher = CapabilityDispatcher({"webhook.inbound": transport})

    assert dispatcher.dispatch(
        capability="webhook.inbound",
        request={"event": "message"},
    ) == {"ok": True}
    with pytest.raises(ProductionAdapterError, match="capability"):
        dispatcher.dispatch(capability="scenario-en-new-customer", request={})


def test_fake_transport_marks_post_dispatch_failure_uncertain() -> None:
    from scripts.e2e_acceptance.production import (
        DispatchUncertainError,
        FakeHttpTransport,
    )

    transport = FakeHttpTransport(
        responses={"webhook.inbound": {"ok": True}},
        uncertain_capabilities={"webhook.inbound"},
    )

    with pytest.raises(DispatchUncertainError, match="after dispatch"):
        transport.request("webhook.inbound", {"event": "message"})
    assert transport.calls == (("webhook.inbound", {"event": "message"}),)


def test_read_only_collector_has_no_mutating_transport_surface() -> None:
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
    )

    raw = b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
    transport = FakeReadOnlySshTransport(responses={"inventory": raw})
    collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=transport,
    )

    observation = collector.observe(
        source_id="baseline",
        run_id="local-run",
        preflight_digest="a" * 64,
        collector_artifact_digest="b" * 64,
        causal_event_digest="c" * 64,
    )

    assert observation.inventory == {"synthetic:item": {"state": "absent"}}
    assert observation.collector_artifact_digest == "b" * 64
    assert not hasattr(collector, "execute")
    assert not hasattr(transport, "execute")
    assert hashlib.sha256(raw).hexdigest() == transport.response_digests["inventory"]


def test_collector_emits_task1_final_artifact_and_receipt_layout(
    tmp_path: Path,
) -> None:
    from scripts.e2e_acceptance import execution
    from scripts.e2e_acceptance.production import (
        FakeReadOnlySshTransport,
        IndependentReadOnlyCollector,
    )

    from tests.e2e_acceptance_backend import build_canonical_test_registry
    from tests.test_e2e_acceptance_trusted_execution import _issued_authority

    registry = build_canonical_test_registry()
    root = tmp_path / "protected"
    authority = _issued_authority(registry, protected_root=root, run_id="local-run")
    journal = execution.ProtectedExecutionJournal.create(
        protected_root=root, run_id="local-run", authority=authority
    )
    now = datetime.now(UTC)
    baseline = execution.ReadbackObservation.build(
        phase="baseline",
        collector_id="independent-readback-collector",
        source_id="baseline",
        run_id="local-run",
        preflight_digest=journal.authorization.preflight_digest,
        collector_artifact_digest=journal.authorization.readback_collector_digest,
        causal_event_digest="a" * 64,
        observed_at=now - timedelta(seconds=2),
        inventory={"synthetic:item": {"state": "absent"}},
    )
    journal.seal_baseline(baseline)
    journal.begin_execution()
    journal.anchor_final_turn(
        event_digest="b" * 64, occurred_at=now - timedelta(seconds=1)
    )
    collector = IndependentReadOnlyCollector(
        collector_id="independent-readback-collector",
        transport=FakeReadOnlySshTransport(
            responses={
                "inventory": b'{"inventory":{"synthetic:item":{"state":"absent"}}}'
            }
        ),
    )

    final = collector.seal_final(journal, source_id="final", observed_at=now)

    assert final.phase == "final"
    assert journal.phase == "final_readback_sealed"
    receipt = json.loads(
        execution._read_protected(
            journal.run_root, "producer-receipts/final-readback.json"
        )
    )
    assert receipt["producer"] == "independent-readback-collector"
