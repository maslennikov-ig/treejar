"""Minimal real transports for authorized Noor acceptance execution.

These transports intentionally contain no retry, logging, CLI, or producer
policy. Callers must reserve authorization before invoking them and reconcile a
``DispatchUncertainError`` independently.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from scripts.e2e_acceptance import execution
from scripts.e2e_acceptance.production import (
    Capability,
    CapabilityDispatcher,
    DispatchUncertainError,
    IndependentReadOnlyCollector,
    ProductionAdapterError,
)

_WEBHOOK_PATH = "/api/v1/webhook/wazzup"
_TRANSPORT_TIMEOUT_SECONDS = 10.0
_HOST_ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_OBSERVER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,239}$")
_SERVER_OBSERVER_PREFIX = (
    "/usr/bin/docker",
    "compose",
    "--project-directory",
    "/opt/noor",
    "--project-name",
    "noor",
    "exec",
    "-T",
    "app",
    "/app/.venv/bin/noor-e2e-observe",
)
_READ_ONLY_EXECUTABLES = frozenset(
    {"cat", "grep", "head", "jq", "sha256sum", "stat", "tail"}
)
_MUTATING_COMMAND_TOKENS = frozenset(
    {
        "-delete",
        "-exec",
        "-execdir",
        "-f",
        "bash",
        "chmod",
        "chown",
        "cp",
        "curl",
        "docker",
        "git",
        "kubectl",
        "mkdir",
        "mv",
        "perl",
        "psql",
        "python",
        "python3",
        "redis-cli",
        "rm",
        "rsync",
        "scp",
        "sed",
        "service",
        "sftp",
        "sh",
        "ssh",
        "sudo",
        "systemctl",
        "tee",
        "touch",
        "wget",
    }
)
_SHELL_METACHARACTERS = frozenset(
    (";", "&", "|", "`", "$", "<", ">", "(", ")", "\n", "\r")
)


class _WazzupMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    messageId: str = Field(min_length=1)
    chatId: str = Field(min_length=1)
    chatType: Literal["whatsapp"]
    authorType: Literal["client", "manager", "bot"]
    channelId: str = Field(min_length=1)
    text: str = Field(min_length=1)
    dateTime: str = Field(min_length=1)
    type: Literal["text"]
    status: Literal["inbound"]


class _WazzupInboundPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    messages: list[_WazzupMessage] = Field(min_length=1, max_length=1)


LiveRuntimeConfig = execution.RuntimeTransportConfig


class _HttpResponse(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> object: ...


class _HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        json: Mapping[str, Any],
        timeout: float,
        follow_redirects: bool,
    ) -> _HttpResponse: ...


class _SshRunner(Protocol):
    def run(
        self,
        args: list[str],
        *,
        capture_output: bool,
        check: bool,
        shell: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[bytes]: ...


def _validate_webhook_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path != _WEBHOOK_PATH
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ProductionAdapterError(
            "webhook endpoint must be the configured HTTPS path"
        )
    return endpoint


def _validated_wazzup_request(request: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return _WazzupInboundPayload.model_validate(dict(request)).model_dump(
            mode="json"
        )
    except (TypeError, ValidationError):
        raise ProductionAdapterError("Wazzup inbound payload is invalid") from None


@dataclass(frozen=True)
class OneShotWazzupWebhookTransport:
    """HTTPS-only, single-attempt transport for the native inbound webhook."""

    endpoint: str
    client: _HttpClient

    def __post_init__(self) -> None:
        object.__setattr__(self, "endpoint", _validate_webhook_endpoint(self.endpoint))

    def preflight(self, capability: Capability, request: Mapping[str, Any]) -> None:
        if capability is not Capability.WEBHOOK_INBOUND:
            raise ProductionAdapterError("webhook transport rejects this capability")
        _validated_wazzup_request(request)

    def request(self, capability: str, request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            typed_capability = Capability(capability)
        except ValueError as exc:
            raise ProductionAdapterError(
                "webhook transport rejects this capability"
            ) from exc
        self.preflight(typed_capability, request)
        payload = _validated_wazzup_request(request)

        # Calling the client begins dispatch. No exception below is safe to retry.
        try:
            response = self.client.post(
                self.endpoint,
                json=payload,
                timeout=_TRANSPORT_TIMEOUT_SECONDS,
                follow_redirects=False,
            )
            response.raise_for_status()
            parsed = response.json()
            if not isinstance(parsed, Mapping):
                raise TypeError("webhook response is not a JSON object")
            return dict(parsed)
        except Exception:
            raise DispatchUncertainError(
                "webhook response or dispatch outcome is uncertain"
            ) from None


def _canonical_command_identity(
    host_alias: str, source: str, command: tuple[str, ...]
) -> bytes:
    return json.dumps(
        {"host_alias": host_alias, "source": source, "command": command},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _validate_read_only_command(command: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(command)
    if not normalized or any(
        not isinstance(token, str) or not token for token in normalized
    ):
        raise ProductionAdapterError("read-only command is invalid")
    if any(
        any(character in _SHELL_METACHARACTERS for character in token)
        for token in normalized
    ):
        raise ProductionAdapterError("read-only command contains shell syntax")

    if _is_server_observer_command(normalized):
        return normalized

    executable = Path(normalized[0]).name
    if executable not in _READ_ONLY_EXECUTABLES or any(
        Path(token).name in _MUTATING_COMMAND_TOKENS
        or token in _MUTATING_COMMAND_TOKENS
        for token in normalized
    ):
        raise ProductionAdapterError(
            "read-only command rejects mutation-capable vocabulary"
        )
    return normalized


def _is_server_observer_command(command: tuple[str, ...]) -> bool:
    """Allow one code-owned read-only DB observer inside the fixed app container."""

    prefix_length = len(_SERVER_OBSERVER_PREFIX)
    if command[:prefix_length] != _SERVER_OBSERVER_PREFIX:
        return False
    suffix = command[prefix_length:]
    if len(suffix) < 5 or suffix[0] not in {"execution", "reconciliation"}:
        return False
    identity_flag = "--execution-id" if suffix[0] == "execution" else "--action-id"
    if suffix[1] != identity_flag or not _OBSERVER_ID_PATTERN.fullmatch(suffix[2]):
        return False
    turn_args = suffix[3:]
    if len(turn_args) % 2 != 0 or not turn_args:
        return False
    for flag, binding in zip(turn_args[::2], turn_args[1::2], strict=True):
        turn_id, separator, message_id = binding.partition("=")
        if (
            flag != "--turn"
            or separator != "="
            or not _OBSERVER_ID_PATTERN.fullmatch(turn_id)
            or not _OBSERVER_ID_PATTERN.fullmatch(message_id)
        ):
            return False
    return True


@dataclass(frozen=True)
class ReadOnlySshTransport:
    """Fixed-host, source-allowlisted collector transport with no command API."""

    host_alias: str
    source_commands: Mapping[str, Sequence[str]]
    runner: _SshRunner = field(default=subprocess)

    def __post_init__(self) -> None:
        if not _HOST_ALIAS_PATTERN.fullmatch(self.host_alias):
            raise ProductionAdapterError("read-only SSH host alias is invalid")
        normalized: dict[str, tuple[str, ...]] = {}
        for source, command in self.source_commands.items():
            if not isinstance(source, str) or not source:
                raise ProductionAdapterError("read-only source identity is invalid")
            if source in normalized:
                raise ProductionAdapterError("read-only source identity is duplicated")
            normalized[source] = _validate_read_only_command(command)
        if not normalized:
            raise ProductionAdapterError("read-only source allowlist is empty")
        object.__setattr__(self, "source_commands", MappingProxyType(normalized))

    def command_identity(self, source: str) -> dict[str, object]:
        try:
            command = self.source_commands[source]
        except KeyError as exc:
            raise ProductionAdapterError("read-only source is not allowlisted") from exc
        return {
            "host_alias": self.host_alias,
            "source": source,
            "command": list(command),
        }

    def command_digest(self, source: str) -> str:
        try:
            command = self.source_commands[source]
        except KeyError as exc:
            raise ProductionAdapterError("read-only source is not allowlisted") from exc
        return hashlib.sha256(
            _canonical_command_identity(self.host_alias, source, tuple(command))
        ).hexdigest()

    @property
    def command_digests(self) -> Mapping[str, str]:
        return MappingProxyType(
            {source: self.command_digest(source) for source in self.source_commands}
        )

    def read(self, source: str) -> bytes:
        try:
            command = self.source_commands[source]
        except KeyError as exc:
            raise ProductionAdapterError("read-only source is not allowlisted") from exc

        try:
            completed = self.runner.run(
                ["ssh", self.host_alias, "--", *command],
                capture_output=True,
                check=False,
                shell=False,
                timeout=_TRANSPORT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProductionAdapterError("read-only SSH collection timed out") from exc
        except OSError as exc:
            raise ProductionAdapterError("read-only SSH collection failed") from exc

        if completed.returncode != 0:
            raise ProductionAdapterError("read-only SSH command failed")
        return bytes(completed.stdout)


@dataclass(frozen=True)
class LiveRuntimeComponents:
    dispatcher: CapabilityDispatcher
    collector: IndependentReadOnlyCollector
    producer: Any
    reconciler: Any


def build_live_runtime_components(
    *,
    config: LiveRuntimeConfig,
    authorization: Any,
    http_client: _HttpClient,
    ssh_runner: _SshRunner = subprocess,
) -> LiveRuntimeComponents:
    """Build only transports whose identities match the protected authority."""

    from scripts.e2e_acceptance.live_producer import (
        IndependentActionReconciler,
        IndependentExecutionProducer,
    )

    if (
        tuple(authorization.adapter_ids) != (config.adapter_id,)
        or config.collector_id not in authorization.collector_ids
    ):
        raise ProductionAdapterError("live runtime adapter/collector authority drift")
    if authorization.live_binding.target_digest != config.target_digest:
        raise ProductionAdapterError("live runtime target authority drift")
    if (
        authorization.live_binding.runtime_transport_digest is None
        or authorization.live_binding.runtime_transport_digest
        != execution.runtime_transport_digest(config)
    ):
        raise ProductionAdapterError("live runtime transport authority drift")
    ssh = ReadOnlySshTransport(
        host_alias=config.ssh_host_alias,
        source_commands=config.source_commands,
        runner=ssh_runner,
    )
    return LiveRuntimeComponents(
        dispatcher=CapabilityDispatcher(
            {
                Capability.WEBHOOK_INBOUND: OneShotWazzupWebhookTransport(
                    endpoint=config.webhook_endpoint,
                    client=http_client,
                )
            }
        ),
        collector=IndependentReadOnlyCollector(
            collector_id=config.collector_id,
            transport=ssh,
            source_names={"baseline": "baseline", "final": "final"},
        ),
        producer=IndependentExecutionProducer(
            collector_id=config.collector_id,
            transport=ssh,
        ),
        reconciler=IndependentActionReconciler(
            collector_id=config.collector_id,
            transport=ssh,
        ),
    )


__all__ = [
    "LiveRuntimeComponents",
    "LiveRuntimeConfig",
    "OneShotWazzupWebhookTransport",
    "ReadOnlySshTransport",
    "build_live_runtime_components",
]
