#!/usr/bin/env python3
"""Validate local acceptance contracts or an already anchored local run."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError
from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.policy import (
    PolicyValidationError,
    TrustedAcceptanceRegistry,
)
from scripts.e2e_acceptance.production import (
    CapabilityDispatcher,
    FakeHttpTransport,
    ProductionAdapterError,
    ProtectedRunPlan,
    dispatch_local_action,
    load_protected_baseline,
    load_sealed_run_plan,
    seal_run_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local-only Noor acceptance policy v2 verifier."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    contracts = subcommands.add_parser("validate-contracts")
    contracts.add_argument("--repo-root", type=Path, required=True)
    verify = subcommands.add_parser("verify-run")
    verify.add_argument("--repo-root", type=Path, required=True)
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--report-output", type=Path, required=True)
    for command in (
        "prepare",
        "preflight",
        "execute-resume",
        "record-gate",
        "finalize",
    ):
        lifecycle = subcommands.add_parser(command)
        lifecycle.add_argument("--repo-root", type=Path, required=True)
        lifecycle.add_argument("--protected-root", type=Path, required=True)
        lifecycle.add_argument("--run-id", required=True)
        if command in {"prepare", "execute-resume"}:
            lifecycle.add_argument("--run-plan", required=True)
        if command == "preflight":
            lifecycle.add_argument("--baseline", required=True)
        if command == "record-gate":
            lifecycle.add_argument("--gate-attempt", required=True)
    return parser


def _canonical_registry(repo_root: Path) -> TrustedAcceptanceRegistry:
    registry = TrustedAcceptanceRegistry.from_canonical_repo()
    if repo_root.resolve(strict=True) != registry.repo_root:
        raise PolicyValidationError("CLI repository root is not canonical")
    return registry


def _authority_and_journal(
    registry: TrustedAcceptanceRegistry,
    protected_root: Path,
    run_id: str,
    *,
    create: bool,
) -> tuple[execution.ExecutionAuthorizationHandle, execution.ProtectedExecutionJournal]:
    authority = execution.issue_execution_authorization_handle(
        registry=registry,
        protected_root=protected_root.resolve(strict=True),
        run_id=run_id,
        current_time=datetime.now(UTC),
    )
    if create:
        journal = execution.ProtectedExecutionJournal.create(
            protected_root=protected_root.resolve(strict=True),
            run_id=run_id,
            authority=authority,
        )
    else:
        journal = execution.ProtectedExecutionJournal.open(
            protected_root=protected_root.resolve(strict=True),
            run_id=run_id,
            authority=authority,
        )
    return authority, journal


def _lifecycle_result(args: argparse.Namespace) -> dict[str, object]:
    registry = _canonical_registry(args.repo_root)
    if args.command == "prepare":
        plan = ProtectedRunPlan.load(
            args.protected_root.resolve(strict=True), args.run_plan
        )
        _, journal = _authority_and_journal(
            registry, args.protected_root, args.run_id, create=True
        )
        seal_run_plan(journal, plan)
        return {
            "phase": journal.phase,
            "plan_digest": plan.plan_digest,
            "evaluator_digest": plan.evaluator_digest,
        }
    authority, journal = _authority_and_journal(
        registry, args.protected_root, args.run_id, create=False
    )
    if args.command == "preflight":
        observation = load_protected_baseline(
            journal,
            artifact_path=args.baseline,
            current_time=datetime.now(UTC),
        )
        journal.seal_baseline(observation)
        return {"phase": journal.phase, "baseline_digest": observation.content_digest}
    if args.command == "execute-resume":
        plan = ProtectedRunPlan.load(
            args.protected_root.resolve(strict=True), args.run_plan
        )
        plan = load_sealed_run_plan(journal, plan)
        if journal.phase == "baseline_sealed":
            journal.begin_execution()
        if journal.phase != "executing":
            raise ProductionAdapterError("resume requires an executing journal")
        if any(state in {"reserved", "unknown"} for state in journal._actions.values()):
            raise ProductionAdapterError("resume is blocked by nonterminal actions")
        transports = {
            str(item["spec"]["capability"]): FakeHttpTransport(
                responses={str(item["spec"]["capability"]): {"local": "accepted"}}
            )
            for item in plan.actions
        }
        dispatcher = CapabilityDispatcher(transports)
        for item in plan.actions:
            spec = dict(item["spec"])
            if spec["action_id"] in journal._actions:
                raise ProductionAdapterError("sealed action already has journal state")
            charge = dict(spec.pop("quota_charge"))
            reservation = journal.reserve_action(
                action_id=str(spec.pop("action_id")),
                adapter_id=str(spec.pop("adapter_id")),
                subsystem=str(spec.pop("subsystem")),
                messages=int(charge["messages"]),
                model_calls=int(charge["model_calls"]),
                cost_usd=float(charge["max_cost_usd"]),
                **spec,
            )
            dispatch_local_action(
                journal=journal,
                dispatcher=dispatcher,
                reservation=reservation,
                message_path=str(item["message_path"]),
                request=spec,
            )
            raise ProductionAdapterError(
                "local dispatch is unknown until independent reconciliation"
            )
        return {"phase": journal.phase, "plan_digest": plan.plan_digest}
    if args.command == "record-gate":
        payload = execution._read_protected(journal.run_root, args.gate_attempt)
        gate = execution.GateAttemptV2.model_validate(json.loads(payload))
        validated = execution.GenericAcceptanceRunner(
            registry=registry,
            authority=authority,
            journal=journal,
        ).validate_gate_attempt(gate, current_time=datetime.now(UTC))
        record_path = f"recorded-gates/{validated.execution_id}.json"
        try:
            existing = json.loads(
                execution._read_protected(journal.run_root, record_path)
            )
        except execution.ExecutionValidationError:
            existing = None
        if existing is not None:
            if (
                existing.get("gate_attempt_sha256")
                != hashlib.sha256(payload).hexdigest()
                or existing.get("execution_id") != validated.execution_id
                or existing.get("outcome") != validated.outcome
            ):
                raise ProductionAdapterError("gate record replay drift")
            return {
                "execution_id": validated.execution_id,
                "outcome": validated.outcome,
            }
        record = {
            "schema_version": "noor-e2e-recorded-gate/v2",
            "execution_id": validated.execution_id,
            "outcome": validated.outcome,
            "gate_attempt_sha256": hashlib.sha256(payload).hexdigest(),
            "journal_head_digest": journal.previous_event_digest,
        }
        execution._write_exclusive(journal.run_root, record_path, record)
        journal._append_event(
            phase="executing",
            kind="gate_recorded",
            data=record,
        )
        return {"execution_id": validated.execution_id, "outcome": validated.outcome}
    if args.command == "finalize":
        if journal.phase != "attempt_committed":
            raise ProductionAdapterError(
                "finalize requires a terminal committed journal"
            )
        registry.finalize_run(args.run_id)
        return {"run_id": args.run_id, "finalized": True}
    raise ProductionAdapterError("unknown local lifecycle command")


def main() -> int:
    args = build_parser().parse_args()
    try:
        result: dict[str, object]
        registry = _canonical_registry(args.repo_root)
        if args.command == "validate-contracts":
            result = {
                "policy_digest": registry.compiled_policy.policy_digest,
                "compiled_plan_digest": registry.compiled_plan.plan_digest,
                "scenario_count": len(registry.compiled_policy.scenarios),
                "evidence_block_count": len(registry.compiled_policy.evidence_blocks),
                "criterion_count": len(registry.compiled_plan.criteria),
                "adapter_ids": ["fake-local-adapter"],
            }
        elif args.command == "verify-run":
            registry.open_run(
                run_id=args.run_id,
            )
            registry.write_report(args.report_output.absolute())
            result = dict(registry.calculate_rollups())
        else:
            result = _lifecycle_result(args)
    except (
        OSError,
        PolicyValidationError,
        ValidationError,
        ValueError,
        ProductionAdapterError,
        execution.ExecutionValidationError,
    ) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
