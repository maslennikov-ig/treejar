#!/usr/bin/env python3
"""Validate local acceptance contracts or an already anchored local run."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError
from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.coordinator import (
    ProductionRunCoordinator,
    ProtectedJournalAcceptancePort,
)
from scripts.e2e_acceptance.live_authority import build_live_authority_bundle
from scripts.e2e_acceptance.live_producer import materialize_next_conservative_gate
from scripts.e2e_acceptance.live_transport import (
    LiveRuntimeComponents,
    LiveRuntimeConfig,
    build_live_runtime_components,
)
from scripts.e2e_acceptance.policy import (
    PolicyValidationError,
    TrustedAcceptanceRegistry,
)
from scripts.e2e_acceptance.production import (
    CapabilityDispatcher,
    FakeHttpTransport,
    ProductionAdapterError,
    ProtectedRunPlan,
    _write_or_validate_exact,
    dispatch_local_action,
    issue_decisive_producer_handle,
    load_protected_baseline,
    load_sealed_run_plan,
    seal_fixed_final_readback,
    seal_run_plan,
)
from scripts.e2e_acceptance.trusted_run import materialize_execution_snapshot

_http_client_factory = httpx.Client
_ssh_runner = subprocess


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
            lifecycle.add_argument("--run-plan", required=True)
        if command == "reconcile-action":
            lifecycle.add_argument("--action-id", required=True)
            lifecycle.add_argument("--run-plan", required=True)
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


def _live_components(
    plan: ProtectedRunPlan,
    journal: execution.ProtectedExecutionJournal,
) -> tuple[LiveRuntimeComponents, object] | None:
    if plan.runtime is None:
        return None
    try:
        config = LiveRuntimeConfig.model_validate(plan.runtime)
    except ValidationError as exc:
        raise ProductionAdapterError(
            "sealed live runtime configuration is invalid"
        ) from exc
    client = _http_client_factory()
    return (
        build_live_runtime_components(
            config=config,
            authorization=journal.authorization,
            http_client=client,
            ssh_runner=_ssh_runner,
        ),
        client,
    )


def _close_client(client: object) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        close()


def _record_committed_gate(
    journal: execution.ProtectedExecutionJournal, execution_id: str, ordinal: int
) -> None:
    payload = execution._read_protected(
        journal.run_root, f"produced-attempts/{ordinal:02d}.json"
    )
    produced = json.loads(payload)
    if (
        produced.get("execution_id") != execution_id
        or produced.get("attempt_kind") != "gate"
        or not isinstance(produced.get("gate_attempt"), dict)
    ):
        raise ProductionAdapterError("committed gate publication is invalid")
    attempt = execution.GateAttemptV2.model_validate(produced["gate_attempt"])
    journal.record_gate_attempt(
        attempt,
        protected_attempt_digest=execution._digest(attempt.model_dump(mode="json")),
    )


def _seal_zero_turn_manifest_if_complete(
    *,
    registry: TrustedAcceptanceRegistry,
    journal: execution.ProtectedExecutionJournal,
    accepted_ordinal: int,
) -> None:
    """Compatibility entrypoint; mixed runs use the same truthful builder."""

    _seal_transcript_manifest_if_complete(
        registry=registry,
        journal=journal,
        accepted_ordinal=accepted_ordinal,
    )


def _seal_transcript_manifest_if_complete(
    *,
    registry: TrustedAcceptanceRegistry,
    journal: execution.ProtectedExecutionJournal,
    accepted_ordinal: int,
) -> None:
    """Seal all real transcript pairs in canonical execution/turn order."""

    if accepted_ordinal != len(registry.compiled_plan.execution_ids):
        return
    ordered_turns: list[list[str]] = []
    seen: set[tuple[str, str]] = set()
    for ordinal, execution_id in enumerate(
        registry.compiled_plan.execution_ids, start=1
    ):
        try:
            source = json.loads(
                execution._read_protected(
                    journal.run_root, f"producer-observations/{ordinal:02d}.json"
                )
            )
        except FileNotFoundError:
            continue
        except (json.JSONDecodeError, execution.ExecutionValidationError) as exc:
            if isinstance(exc.__cause__, FileNotFoundError):
                continue
            raise ProductionAdapterError(
                "protected transcript source is invalid"
            ) from exc
        if source.get("execution_id") != execution_id:
            raise ProductionAdapterError(
                "protected transcript source execution order drift"
            )
        facts = source.get("transcript_facts")
        if not isinstance(facts, list):
            raise ProductionAdapterError(
                "protected transcript source facts are invalid"
            )
        attempt_id = f"attempt:{execution_id}"
        for fact in facts:
            turn_id = fact.get("turn_id") if isinstance(fact, dict) else None
            identity = (execution_id, str(turn_id))
            if not isinstance(turn_id, str) or not turn_id or identity in seen:
                raise ProductionAdapterError(
                    "protected transcript source turn order drift"
                )
            seen.add(identity)
            transcript_ref = f"transcripts/{execution_id}/{attempt_id}/{turn_id}.json"
            receipt_ref = (
                f"producer-receipts/transcripts/{execution_id}/"
                f"{attempt_id}/{turn_id}.json"
            )
            ordered_turns.append(
                [
                    execution_id,
                    attempt_id,
                    turn_id,
                    hashlib.sha256(
                        execution._read_protected(journal.run_root, transcript_ref)
                    ).hexdigest(),
                    hashlib.sha256(
                        execution._read_protected(journal.run_root, receipt_ref)
                    ).hexdigest(),
                ]
            )
    _write_or_validate_exact(
        journal.run_root,
        "transcripts/manifest.json",
        {
            "schema_version": "noor-e2e-protected-transcript-manifest/v2",
            "registry_id": registry.registry_id,
            "run_id": journal.run_id,
            "ordered_turns": ordered_turns,
        },
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
        plan = load_sealed_run_plan(
            journal,
            ProtectedRunPlan.load(
                args.protected_root.resolve(strict=True), args.run_plan
            ),
        )
        live = _live_components(plan, journal)
        if live is None:
            observation = load_protected_baseline(
                journal,
                artifact_path=args.baseline,
                current_time=datetime.now(UTC),
            )
            journal.seal_baseline(observation)
        else:
            components, client = live
            try:
                observation = components.collector.seal_baseline(
                    journal, source_id="baseline"
                )
                journal.seal_baseline(observation)
            finally:
                _close_client(client)
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
        live = _live_components(plan, journal)
        client: object | None = None
        if live is None:
            transports = {
                str(item["spec"]["capability"]): FakeHttpTransport(
                    responses={str(item["spec"]["capability"]): {"local": "accepted"}}
                )
                for item in plan.actions
            }
            dispatcher = CapabilityDispatcher(transports)
        else:
            components, client = live
            dispatcher = components.dispatcher
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
            try:
                dispatch_local_action(
                    journal=journal,
                    dispatcher=dispatcher,
                    reservation=reservation,
                    message_path=str(item["message_path"]),
                    request=spec,
                )
            finally:
                if client is not None:
                    _close_client(client)
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
        plan = load_sealed_run_plan(
            journal,
            ProtectedRunPlan.load(
                args.protected_root.resolve(strict=True), args.run_plan
            ),
        )
        live = _live_components(plan, journal)
        if live is not None:
            components, client = live
            try:
                components.reconciler.materialize(journal, action_id=action_id)
            finally:
                _close_client(client)
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
            "settled_actual_cost_usd": settlement.actual_cost_usd,
        }
    if args.command == "record-attempt":
        plan = load_sealed_run_plan(
            journal,
            ProtectedRunPlan.load(
                args.protected_root.resolve(strict=True), args.run_plan
            ),
        )
        coordinator = _coordinator(registry, authority, journal)
        live = _live_components(plan, journal)
        if live is not None:
            components, client = live
            try:
                handle = issue_decisive_producer_handle(
                    registry=registry,
                    journal=journal,
                    authority=authority,
                    sealed_plan=plan,
                )
                source_ref = components.producer.materialize_next(
                    producer_handle=handle,
                    observed_at=datetime.now(UTC),
                )
                coordinator.publish_next_from_decisive_producer(handle, source_ref)
            finally:
                _close_client(client)
        record = coordinator.accept_next()
        _seal_transcript_manifest_if_complete(
            registry=registry,
            journal=journal,
            accepted_ordinal=record.ordinal,
        )
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
        _record_committed_gate(journal, artifact.execution_id, artifact.ordinal)
        accepted = _coordinator(registry, authority, journal).accept_next()
        _seal_zero_turn_manifest_if_complete(
            registry=registry,
            journal=journal,
            accepted_ordinal=accepted.ordinal,
        )
        return {
            "phase": journal.phase,
            "plan_digest": plan.plan_digest,
            "ordinal": accepted.ordinal,
            "execution_id": artifact.execution_id,
            "outcome": artifact.outcome,
        }
    if args.command == "close-execution":
        plan = load_sealed_run_plan(
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
            live = _live_components(plan, journal)
            if live is None:
                seal_fixed_final_readback(journal, current_time=datetime.now(UTC))
            else:
                components, client = live
                try:
                    components.collector.seal_final(journal, source_id="final")
                finally:
                    _close_client(client)
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
                "adapter_ids": [
                    "fake-local-adapter",
                    "wazzup-webhook-adapter",
                ],
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
