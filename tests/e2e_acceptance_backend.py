"""Test-only registry backend for isolated canonical-layout fixtures."""

from __future__ import annotations

from pathlib import Path

from scripts.e2e_acceptance.policy import (
    CompiledPolicy,
    ReadbackObservation,
    TrustedAcceptanceRegistry,
    VerifiedEvidenceContext,
)


def build_test_registry(
    repo_root: Path,
    compiled_policy: CompiledPolicy,
) -> TrustedAcceptanceRegistry:
    class TestAcceptanceRegistryBackend(TrustedAcceptanceRegistry):
        _test_context = VerifiedEvidenceContext()

        @classmethod
        def _canonical_repo_root(cls) -> Path:
            return repo_root

        @classmethod
        def _load_canonical_policy(cls, root: Path) -> CompiledPolicy:
            if root != repo_root:
                raise AssertionError("test registry root drift")
            return compiled_policy

        def _verified_evidence_context(self) -> VerifiedEvidenceContext:
            return self._test_context

        def _set_test_context(self, context: VerifiedEvidenceContext) -> None:
            self._test_context = context

        def _load_execution_authorization(self, authorization: object) -> None:
            from scripts.e2e_acceptance.execution import (
                authorization_digest,
                validate_execution_authorization,
            )

            validated = validate_execution_authorization(
                authorization,
                policy=self.compiled_policy,
                plan=self.compiled_plan,
                registry_id=self.registry_id,
            )
            context = self._test_context
            self._test_context = context.model_copy(
                update={
                    "authorization_digests": context.authorization_digests
                    | {authorization_digest(validated)},
                    "preflight_collectors": context.preflight_collectors
                    | {
                        (
                            validated.preflight_digest,
                            validated.readback_collector_digest,
                        )
                    },
                }
            )

        def _load_trusted_readback(self, observation: ReadbackObservation) -> None:
            context = self._test_context
            self._test_context = context.model_copy(
                update={
                    "readback_digests": context.readback_digests
                    | {observation.content_digest}
                }
            )

    return TestAcceptanceRegistryBackend()


def build_canonical_test_registry() -> TrustedAcceptanceRegistry:
    canonical = TrustedAcceptanceRegistry.from_canonical_repo()
    return build_test_registry(canonical.repo_root, canonical.compiled_policy)
