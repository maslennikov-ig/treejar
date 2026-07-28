"""Public local-only facade for the generic acceptance runner v2."""

from __future__ import annotations

from scripts.e2e_acceptance.execution import (
    ExecutionAuthorizationV2,
    ExecutionValidationError,
    FakeLocalAdapter,
    GenericAcceptanceRunner,
    ProtectedExecutionJournal,
    ScenarioAttemptV2,
    ValidatedAttempt,
)
from scripts.e2e_acceptance.policy import TrustedAcceptanceRegistry
from scripts.e2e_acceptance.production import (
    CapabilityDispatcher,
    FakeHttpTransport,
    FakeReadOnlySshTransport,
    IndependentReadOnlyCollector,
    ProtectedRunPlan,
    WazzupWebhookAdapter,
)

RunnerError = ExecutionValidationError


def open_local_registry() -> TrustedAcceptanceRegistry:
    """Compile exact Task 1 contracts without opening any network adapter."""

    return TrustedAcceptanceRegistry.from_canonical_repo()


__all__ = [
    "ExecutionAuthorizationV2",
    "CapabilityDispatcher",
    "FakeLocalAdapter",
    "FakeHttpTransport",
    "FakeReadOnlySshTransport",
    "GenericAcceptanceRunner",
    "IndependentReadOnlyCollector",
    "ProtectedExecutionJournal",
    "ProtectedRunPlan",
    "RunnerError",
    "ScenarioAttemptV2",
    "ValidatedAttempt",
    "WazzupWebhookAdapter",
    "open_local_registry",
]
