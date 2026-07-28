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
from scripts.e2e_acceptance.coordinator import (
    ProductionRunCoordinator,
    ProtectedJournalAcceptancePort,
)
from scripts.e2e_acceptance.live_authority import build_live_authority_bundle
from scripts.e2e_acceptance.live_producer import materialize_next_conservative_gate
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
    issue_decisive_producer_handle,
    load_protected_baseline,
    load_sealed_run_plan,
    seal_fixed_final_readback,
    seal_run_plan,
)
from scripts.e2e_acceptance.trusted_run import materialize_execution_snapshot


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
        "authorize-live",
        "prepare",
        "preflight",
        "execute-resume",
        "reconcile-action",
        "record-attempt",
        "record-blocked",
        "close-execution",
        "finalize",
    ):
        lifecycle = subcommands.add_parser(command)
        lifecycle.add_argument("--repo-root", type=Path, required=True)
        lifecycle.add_argument("--protected-root", type=Path, required=True)
        lifecycle.add_argument("--run-id", required=True)
        if command in {
            "prepare",
            "execute-resume",
            "record-attempt",
            "record-blocked",
            "close-execution",
            "finalize",
        }:
            lifecycle.add_argument("--run-plan", required=True)
        if command == "preflight":
            lifecycle.add_argument("--baseline", required=True)
        if command == "reconcile-action":
            lifecycle.add_argument("--action-id", required=True)
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
        journal = execution.ProtectedExecutionJournal.create_or_open(
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


def _coordinator(
    registry: TrustedAcceptanceRegistry,
    authority: execution.ExecutionAuthorizationHandle,
    journal: execution.ProtectedExecutionJournal,
) -> ProductionRunCoordinator:
    return ProductionRunCoordinator(
        registry=registry,
        authorization=authority._authorization,
        protected_root=journal.protected_root,
        run_id=journal.run_id,
        journal=ProtectedJournalAcceptancePort(journal=journal),
        current_time=datetime.now(UTC),
    )


def _lifecycle_result(args: argparse.Namespace) -> dict[str, object]:
    registry = _canonical_registry(args.repo_root)
    if args.command == "authorize-live":
        bundle = build_live_authority_bundle(
            registry=registry,
            protected_root=args.protected_root.resolve(strict=True),
            run_id=args.run_id,
            current_time=datetime.now(UTC),
        )
        return {
            "run_id": args.run_id,
            "authority_receipt_digest": bundle.receipt_digest,
            "authority_receipt_ref": bundle.receipt_ref,
            "input_refs": bundle.input_refs,
        }
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
        if args.baseline != "collector-artifacts/baseline-readback.json":
            raise ProductionAdapterError("baseline must select the producer artifact")
        if journal.phase == "baseline_sealed":
            if journal._baseline_content_digest is None:
                raise ProductionAdapterError("baseline seal is missing its digest")
            return {
                "phase": journal.phase,
                "baseline_digest": journal._baseline_content_digest,
            }
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
        if any(state == "unknown" for state in journal._actions.values()):
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
            charge = dict(spec.pop("quota_charge"))
            action_id = str(spec.pop("action_id"))
            adapter_id = str(spec.pop("adapter_id"))
            subsystem = str(spec.pop("subsystem"))
            if action_id in journal._actions:
                if (
                    journal._actions[action_id] == "reserved"
                    and action_id in journal._reservations
                ):
                    reservation = journal._reservations[action_id]
                else:
                    if (
                        journal._actions[action_id] not in {"succeeded", "failed"}
                        or action_id not in journal._journal_cost_settlements
                    ):
                        raise ProductionAdapterError(
                            "sealed action is not terminally settled"
                        )
                    continue
            else:
                reservation = journal.reserve_action(
                    action_id=action_id,
                    adapter_id=adapter_id,
                    subsystem=subsystem,
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
            return {
                "phase": journal.phase,
                "plan_digest": plan.plan_digest,
                "action_id": action_id,
                "state": "unknown",
            }
        return {
            "phase": journal.phase,
            "plan_digest": plan.plan_digest,
            "state": "complete",
        }
    if args.command == "reconcile-action":
        action_id = args.action_id
        payload = execution._read_protected(
            journal.run_root, f"independent-reconciliation/{action_id}.json"
        )
        receipt_digest = hashlib.sha256(payload).hexdigest()
        settlement = journal.reconcile_and_settle_action(
            action_id=action_id, receipt_digest=receipt_digest
        )
        return {
            "action_id": action_id,
            "state": journal._actions[action_id],
            "settled_reserved_max_cost_usd": settlement.actual_cost_usd,
        }
    if args.command == "record-attempt":
        plan = load_sealed_run_plan(
            journal,
            ProtectedRunPlan.load(
                args.protected_root.resolve(strict=True), args.run_plan
            ),
        )
        record = _coordinator(registry, authority, journal).accept_next()
        return {
            "phase": journal.phase,
            "plan_digest": plan.plan_digest,
            "ordinal": record.ordinal,
            "execution_id": record.artifact.execution_id,
            "outcome": record.artifact.outcome,
        }
    if args.command == "record-blocked":
        plan = load_sealed_run_plan(
            journal,
            ProtectedRunPlan.load(
                args.protected_root.resolve(strict=True), args.run_plan
            ),
        )
        if journal.phase == "baseline_sealed":
            journal.begin_execution()
        if journal.phase != "executing":
            raise ProductionAdapterError(
                "record-blocked requires a baseline-sealed or executing journal"
            )
        handle = issue_decisive_producer_handle(
            registry=registry,
            journal=journal,
            authority=authority,
            sealed_plan=plan,
        )
        source_ref = materialize_next_conservative_gate(
            producer_handle=handle,
            current_time=datetime.now(UTC),
        )
        coordinator = _coordinator(registry, authority, journal)
        artifact = coordinator.publish_next_from_decisive_producer(handle, source_ref)
        accepted = _coordinator(registry, authority, journal).accept_next()
        return {
            "phase": journal.phase,
            "plan_digest": plan.plan_digest,
            "ordinal": accepted.ordinal,
            "execution_id": artifact.execution_id,
            "outcome": artifact.outcome,
        }
    if args.command == "close-execution":
        load_sealed_run_plan(
            journal,
            ProtectedRunPlan.load(
                args.protected_root.resolve(strict=True), args.run_plan
            ),
        )
        result = _coordinator(registry, authority, journal).finalize()
        if journal.phase == "executing":
            journal.anchor_final_turn(
                event_digest=result.final_activity.receipt_digest,
                occurred_at=result.final_activity.issued_at,
            )
        elif journal.phase == "final_turn_anchored" and (
            journal._final_turn_event_digest != result.final_activity.receipt_digest
            or journal._final_turn_occurred_at != result.final_activity.issued_at
        ):
            raise ProductionAdapterError("final activity anchor replay drift")
        if journal.phase == "final_turn_anchored":
            seal_fixed_final_readback(journal, current_time=datetime.now(UTC))
        if journal.phase == "final_readback_sealed":
            journal.mark_evaluated(evaluation_digest=result.evaluation.bundle_digest)
        elif journal.phase == "evaluated" and (
            journal._evaluation_digest != result.evaluation.bundle_digest
        ):
            raise ProductionAdapterError("coordinator evaluation replay drift")
        if journal.phase == "evaluated":
            journal.commit_phase(
                attempt_chain_digest=result.final_activity.accepted_fold_digest
            )
        elif journal.phase == "attempt_committed" and (
            journal._attempt_chain_digest != result.final_activity.accepted_fold_digest
        ):
            raise ProductionAdapterError("coordinator attempt-chain replay drift")
        return {"run_id": journal.run_id, "phase": journal.phase}
    if args.command == "finalize":
        if journal.phase != "attempt_committed":
            raise ProductionAdapterError(
                "finalize requires a terminal committed journal"
            )
        plan = load_sealed_run_plan(
            journal,
            ProtectedRunPlan.load(
                args.protected_root.resolve(strict=True), args.run_plan
            ),
        )
        materialize_execution_snapshot(registry, journal, plan)
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
