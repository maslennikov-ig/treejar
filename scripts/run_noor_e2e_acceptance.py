#!/usr/bin/env python3
"""Run the local Noor E2E acceptance fixture harness."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError
from scripts.e2e_acceptance.manifest import (
    ManifestValidationError,
    load_authorization_manifest,
    load_scenario_set,
)
from scripts.e2e_acceptance.runner import (
    AcceptanceRunner,
    RunnerError,
    load_dry_run_fixture,
    load_side_effect_readback,
)
from scripts.e2e_acceptance.schemas import PreflightObservation, PreflightRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Noor E2E acceptance fixtures (Task 2 dry-run only)."
    )
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--protected-root", type=Path, required=True)
    parser.add_argument("--scenario-set", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--readback", type=Path, required=True)
    parser.add_argument("--preflight-now", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        scenario_set = load_scenario_set(args.scenario_set)
        authorization = load_authorization_manifest(args.authorization)
        observation = PreflightObservation.model_validate_json(
            args.observation.read_text(encoding="utf-8")
        )
        request = PreflightRequest.model_validate_json(
            args.request.read_text(encoding="utf-8")
        )
        readback = load_side_effect_readback(args.readback)
        preflight_now = datetime.fromisoformat(args.preflight_now)
        fixture = load_dry_run_fixture(args.fixture)
        result = AcceptanceRunner(
            repo_root=args.repo_root,
            protected_root=args.protected_root,
            dry_run=args.dry_run,
            scenario_set=scenario_set,
            scenario_set_path=args.scenario_set,
            authorization=authorization,
            observation=observation,
            request=request,
            readback=readback,
            preflight_now=preflight_now,
        ).run_fixture(
            run_id=args.run_id,
            fixture=fixture,
        )
    except (
        ManifestValidationError,
        OSError,
        RunnerError,
        ValidationError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
