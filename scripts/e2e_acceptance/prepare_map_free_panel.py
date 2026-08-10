#!/usr/bin/env python3
"""Prepare blind-reader inputs with the applicability map removed."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter


def _load_object(path: pathlib.Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--split", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    try:
        split = _load_object(args.split)
        assignments: dict[str, list[str]] = {}
        for reader, raw_packets in split.items():
            if not isinstance(raw_packets, list) or not all(
                isinstance(packet, str) and packet for packet in raw_packets
            ):
                raise ValueError(f"{args.split}: invalid assignment for {reader}")
            packets = list(raw_packets)
            if len(packets) > 13:
                raise ValueError(
                    f"{reader}: {len(packets)} packets exceeds the 13 limit"
                )
            if len(set(packets)) != len(packets):
                raise ValueError(f"{reader}: duplicate packet assignment")
            assignments[reader] = packets

        counts = Counter(
            packet for packets in assignments.values() for packet in packets
        )
        wrong = {packet: count for packet, count in counts.items() if count != 2}
        if wrong:
            raise ValueError(f"every packet needs two independent reads: {wrong}")
        if args.output.exists():
            raise ValueError(f"output already exists: {args.output}")

        args.output.mkdir(parents=True, mode=0o700)
        for reader, packets in assignments.items():
            source_input = _load_object(args.source / reader / "_input.json")
            sanitized: dict[str, dict[str, object]] = {}
            for packet in packets:
                raw_item = source_input.get(packet)
                if not isinstance(raw_item, dict) or "transcript" not in raw_item:
                    raise ValueError(f"{source_input}: missing transcript for {packet}")
                sanitized[packet] = {"transcript": raw_item["transcript"]}
            reader_dir = args.output / reader
            reader_dir.mkdir(mode=0o700)
            input_path = reader_dir / "_input.json"
            input_path.write_text(
                json.dumps(sanitized, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            input_path.chmod(0o600)

        manifest_path = args.output / "assignment-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "packets": len(counts),
                    "reads": sum(counts.values()),
                    "readers": len(assignments),
                    "max_packets_per_reader": max(map(len, assignments.values())),
                    "assignments": assignments,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        manifest_path.chmod(0o600)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"cannot prepare map-free panel: {exc}", file=sys.stderr)
        return 2

    print(
        f"prepared {len(counts)} packets, {sum(counts.values())} reads, "
        f"{len(assignments)} readers; no applicability fields copied"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
