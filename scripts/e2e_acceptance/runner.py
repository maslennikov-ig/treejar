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

RunnerError = ExecutionValidationError


def open_local_registry() -> TrustedAcceptanceRegistry:
    """Compile exact Task 1 contracts without opening any network adapter."""

    return TrustedAcceptanceRegistry.from_canonical_repo()


__all__ = [
    "ExecutionAuthorizationV2",
    "FakeLocalAdapter",
    "GenericAcceptanceRunner",
    "ProtectedExecutionJournal",
    "RunnerError",
    "ScenarioAttemptV2",
    "ValidatedAttempt",
    "open_local_registry",
]
