"""Replay stored model outputs through the reply policy, and diff the digests.

The behaviour-preserving claim every guard change in `tj-n7p4` rests on is that
the 60 raw outputs of the three measured rounds still render to the same text.
That replay was run by hand each time. A proof nobody else can re-run is a
claim, so this is the same replay with a name and an entry point.

It reads the protected runs and writes digests. No reply text, no customer
opening, no company and no amount crosses back into the repository, and no
provider is called: this is the deterministic half of the chain only, which is
the half a guard declaration can change.

Two conventions, because the stored runs are not all the same shape. `raw`
replays `generation.raw_content`, the model's own text, which is the transition
a guard actually performs. `baseline` replays `generation.content`, which is
what the 2026-08-11 fixture used -- and which, in the round recorded after the
harness started shipping its output, is already past the guards. That fixture
still detects any change to the chain, so it is kept and compared against; it
just does not mean what its field name suggests.

    uv run python scripts/corpus_bridge/replay_policy_chain.py \
        --convention baseline \
        --baseline <protected>/tj-mshi.4-replay-baseline.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.llm.response_policy import ReplyPolicyState, render_reply  # noqa: E402

SCHEMA_VERSION = "treejar-protected-policy-replay/v1"


def protected_root() -> Path:
    """The store that holds transcript-bearing evidence, never the work tree."""

    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return Path(common).resolve() / "codex-orchestration" / "corpus-bridge"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _grounded_amounts(catalog_evidence: object) -> tuple[object, ...] | None:
    """The same evidence reading the acceptance harness does, kept in one shape."""

    grounded: list[object] = []
    if isinstance(catalog_evidence, list):
        for product in catalog_evidence:
            if isinstance(product, dict) and product.get("price_aed") is not None:
                grounded.append(product["price_aed"])
    return tuple(grounded) if grounded else None


def _source_text(generation: dict[str, Any], convention: str) -> str:
    if convention == "baseline":
        return str(generation.get("content") or "")
    return str(generation.get("raw_content") or generation.get("content") or "")


def replay_run(run_dir: Path, *, convention: str) -> list[dict[str, Any]]:
    """Render every stored output of one run under its own turn state."""

    state_file = run_dir / "run-state.json"
    records = json.loads(state_file.read_text(encoding="utf-8"))["records"]
    replayed: list[dict[str, Any]] = []
    for record in records.values():
        generation = record.get("generation") or {}
        raw = _source_text(generation, convention)
        state = ReplyPolicyState(
            language=str(record.get("language") or "en"),
            is_first_turn=True,
            customer_name=None,
            anchor_line=record.get("anchor_line"),
            grounded_amounts=_grounded_amounts(record.get("catalog_evidence")),
        )
        rendered = render_reply(raw, state=state, provenance="model")
        replayed.append(
            {
                "run": run_dir.name,
                "dialog_id": record.get("dialog_id"),
                "raw_digest": _digest(raw),
                "rendered_digest": _digest(rendered.text),
                "flags": sorted(flag.guard_name for flag in rendered.flags),
            }
        )
    return replayed


def aggregate_digest(records: list[dict[str, Any]]) -> str:
    ordered = sorted(records, key=lambda item: (item["run"], item["dialog_id"]))
    payload = json.dumps(
        [
            [
                item["run"],
                item["dialog_id"],
                item["raw_digest"],
                item["rendered_digest"],
            ]
            for item in ordered
        ],
        separators=(",", ":"),
    )
    return _digest(payload)


def compare(baseline: dict[str, Any], replayed: list[dict[str, Any]]) -> list[str]:
    """Every stored record the current chain no longer reproduces."""

    stored = {
        (item["run"], item["dialog_id"]): item for item in baseline.get("records", [])
    }
    mismatches: list[str] = []
    for item in replayed:
        key = (item["run"], item["dialog_id"])
        before = stored.get(key)
        if before is None:
            mismatches.append(f"{key[0]}/{key[1]}: not in baseline")
            continue
        if before["raw_digest"] != item["raw_digest"]:
            mismatches.append(f"{key[0]}/{key[1]}: stored raw output differs")
        if before["rendered_digest"] != item["rendered_digest"]:
            mismatches.append(f"{key[0]}/{key[1]}: rendered reply changed")
    missing = set(stored) - {(item["run"], item["dialog_id"]) for item in replayed}
    mismatches.extend(
        f"{run}/{dialog}: not replayed" for run, dialog in sorted(missing)
    )
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        help="protected replay baseline to compare against",
    )
    parser.add_argument(
        "--run",
        action="append",
        dest="runs",
        help="protected run directory name; repeatable, defaults to the baseline's",
    )
    parser.add_argument(
        "--write-baseline",
        type=Path,
        help="write the replayed digests as a new protected baseline",
    )
    parser.add_argument(
        "--convention",
        choices=("raw", "baseline"),
        default="raw",
        help="which stored field to replay; see the module docstring",
    )
    args = parser.parse_args()

    root = protected_root()
    baseline: dict[str, Any] | None = None
    runs = args.runs or []
    if args.baseline is not None:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        runs = runs or list(baseline.get("source_runs", []))
    if not runs:
        parser.error("give --baseline or at least one --run")

    replayed: list[dict[str, Any]] = []
    for name in runs:
        replayed.extend(replay_run(root / name, convention=args.convention))

    digest = aggregate_digest(replayed)
    flagged = [item for item in replayed if item["flags"]]
    print(
        f"replayed {len(replayed)} stored outputs from {len(runs)} runs "
        f"under the {args.convention} convention"
    )
    print(f"aggregate digest {digest}")
    for item in flagged:
        print(f"flag {item['run']}/{item['dialog_id']}: {','.join(item['flags'])}")

    if args.write_baseline is not None:
        args.write_baseline.write_text(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "source_runs": runs,
                    "record_count": len(replayed),
                    "aggregate_digest": digest,
                    "records": sorted(
                        replayed, key=lambda item: (item["run"], item["dialog_id"])
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote baseline {args.write_baseline}")

    if baseline is None:
        return 0

    mismatches = compare(baseline, replayed)
    stored_digest = baseline.get("aggregate_digest")
    if stored_digest and stored_digest != digest:
        print(f"baseline aggregate digest {stored_digest}")
    for line in mismatches:
        print(f"MISMATCH {line}")
    if mismatches:
        print(f"replay FAILED with {len(mismatches)} mismatches")
        return 1
    print("replay OK: every stored reply renders unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
