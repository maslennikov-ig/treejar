"""Who wrote each turn of an acceptance run.

The runtime has recorded ``text_provenance`` per turn since the runtime-turn
evidence block existed, and the scenario capture has carried it all along,
buried in ``detail.metadata.runtime_execution_evidence``. Nothing read it. It
took scoring a whole run turn by turn, by hand, to notice that the scenarios
with a template in them averaged 13.3 against 22.8 for the ones the model
wrote — a split that was sitting in the captures the entire time.

This turns that read into a number. Point it at the scenario captures from a
run and it reports the split, per scenario and in aggregate, alongside the
route labels that produced the deterministic turns.

No message text, no identifiers, and no customer data leave this module: it
reports counts and route labels only.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_EVIDENCE_KEY = "runtime_execution_evidence"
MODEL_WRITTEN = frozenset({"model", "model_repaired"})


@dataclass(frozen=True, slots=True)
class ScenarioProvenance:
    scenario: str
    provenance: Counter[str] = field(default_factory=Counter)
    deterministic_routes: Counter[str] = field(default_factory=Counter)

    @property
    def turns(self) -> int:
        return sum(self.provenance.values())

    @property
    def model_written(self) -> int:
        return sum(count for k, count in self.provenance.items() if k in MODEL_WRITTEN)

    @property
    def fully_model_written(self) -> bool:
        return self.turns > 0 and self.model_written == self.turns


def _route_label(model: str | None) -> str | None:
    """The route behind a reply, however the engine happened to spell it.

    Most routes are recorded as "<model>|<route>", but several of the oldest
    ones are stored as the bare label. A provider model name always carries a
    slash, so a bare string without one is a route -- including a route that
    has since been retired and is no longer in the registry, which is what a
    capture from an earlier run will contain.
    """

    if not model:
        return None
    if "|" in model:
        return model.rsplit("|", 1)[-1]
    if "/" in model:
        return None
    return model or None


def _provenance_by_assistant_message(detail: Mapping[str, Any]) -> dict[str, str]:
    metadata = detail.get("metadata")
    if not isinstance(metadata, Mapping):
        return {}
    evidence = metadata.get(_EVIDENCE_KEY)
    if not isinstance(evidence, Mapping):
        return {}
    recorded: dict[str, str] = {}
    for turn in evidence.get("turns", ()):
        if not isinstance(turn, Mapping):
            continue
        message_id = turn.get("assistant_message_id")
        provenance = turn.get("text_provenance")
        if isinstance(message_id, str) and isinstance(provenance, str):
            recorded[message_id] = provenance
    return recorded


def summarise_capture(capture: Mapping[str, Any]) -> ScenarioProvenance:
    """Read one scenario capture into counts.

    The evidence block is cumulative — the last turn's copy holds every turn —
    so it is read once from the final turn and matched to each reply by
    assistant message id. A turn the runtime never recorded is counted as
    ``unrecorded`` rather than guessed at.
    """

    scenario = str(capture.get("scenario") or "unknown")
    turns = [turn for turn in capture.get("turns", ()) if isinstance(turn, Mapping)]
    recorded: dict[str, str] = {}
    for turn in reversed(turns):
        detail = turn.get("detail")
        if isinstance(detail, Mapping):
            recorded = _provenance_by_assistant_message(detail)
            if recorded:
                break

    summary = ScenarioProvenance(scenario=scenario)
    for turn in turns:
        assistant = turn.get("assistant")
        if not isinstance(assistant, Mapping):
            continue
        message_id = assistant.get("id")
        provenance = recorded.get(str(message_id), "unrecorded")
        summary.provenance[provenance] += 1
        if provenance not in MODEL_WRITTEN:
            label = _route_label(assistant.get("model"))
            summary.deterministic_routes[label or "unlabelled"] += 1
    return summary


def is_scenario_capture(payload: object) -> bool:
    """A run directory also holds score files and readbacks; skip those."""

    return (
        isinstance(payload, Mapping)
        and isinstance(payload.get("scenario"), str)
        and isinstance(payload.get("turns"), list)
        and bool(payload["turns"])
    )


def summarise_run(
    captures: Iterable[Mapping[str, Any]],
) -> tuple[tuple[ScenarioProvenance, ...], ScenarioProvenance]:
    scenarios = tuple(
        sorted(
            (summarise_capture(c) for c in captures if is_scenario_capture(c)),
            key=lambda s: s.scenario,
        )
    )
    total = ScenarioProvenance(scenario="ALL")
    for item in scenarios:
        total.provenance.update(item.provenance)
        total.deterministic_routes.update(item.deterministic_routes)
    return scenarios, total


def format_summary(
    scenarios: Sequence[ScenarioProvenance], total: ScenarioProvenance
) -> str:
    lines = [f"{'scenario':<10}{'turns':>6}{'model':>7}{'template':>10}  routes"]
    for item in scenarios:
        template = item.turns - item.model_written
        routes = ", ".join(
            f"{label} x{count}"
            for label, count in sorted(item.deterministic_routes.most_common())
        )
        lines.append(
            f"{item.scenario:<10}{item.turns:>6}{item.model_written:>7}"
            f"{template:>10}  {routes}"
        )
    fully = sum(1 for item in scenarios if item.fully_model_written)
    lines.append("")
    lines.append(
        f"{len(scenarios)} scenarios, {fully} of them model-written throughout; "
        f"{total.turns - total.model_written} of {total.turns} turns came from a "
        "deterministic route."
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "captures",
        nargs="+",
        type=Path,
        help="scenario capture JSON files from one acceptance run",
    )
    args = parser.parse_args(argv)
    captures = [json.loads(path.read_text(encoding="utf-8")) for path in args.captures]
    skipped = sum(1 for payload in captures if not is_scenario_capture(payload))
    scenarios, total = summarise_run(captures)
    if skipped:
        print(f"({skipped} of {len(captures)} inputs are not scenario captures)")
    print(format_summary(scenarios, total))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
