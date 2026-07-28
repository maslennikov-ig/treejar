from __future__ import annotations

import json
import subprocess

import pytest
from scripts.e2e_acceptance.production import (
    DispatchUncertainError,
    ProductionAdapterError,
)


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class _HttpClient:
    def __init__(self, response: _Response | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> _Response:
        self.calls.append({"url": url, **kwargs})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _wazzup_payload() -> dict[str, object]:
    return {
        "messages": [
            {
                "messageId": "synthetic-message",
                "chatId": "synthetic-chat",
                "chatType": "whatsapp",
                "authorType": "client",
                "channelId": "synthetic-channel",
                "text": "synthetic text",
                "dateTime": "2026-07-28T12:00:00Z",
                "type": "text",
                "status": "inbound",
            }
        ]
    }


def test_wazzup_transport_posts_exact_endpoint_once_without_redirect_or_retry() -> None:
    from scripts.e2e_acceptance.live_transport import OneShotWazzupWebhookTransport

    client = _HttpClient(_Response({"ok": True}))
    transport = OneShotWazzupWebhookTransport(
        endpoint="https://noor.starec.ai/api/v1/webhook/wazzup", client=client
    )

    assert transport.request("webhook.inbound", _wazzup_payload()) == {"ok": True}
    assert client.calls == [
        {
            "url": "https://noor.starec.ai/api/v1/webhook/wazzup",
            "json": _wazzup_payload(),
            "timeout": 10.0,
            "follow_redirects": False,
        }
    ]


def test_wazzup_transport_rejects_non_native_payload_before_dispatch() -> None:
    from scripts.e2e_acceptance.live_transport import OneShotWazzupWebhookTransport

    client = _HttpClient(_Response({"ok": True}))
    transport = OneShotWazzupWebhookTransport(
        endpoint="https://noor.starec.ai/api/v1/webhook/wazzup", client=client
    )

    with pytest.raises(ProductionAdapterError, match="Wazzup"):
        transport.request("webhook.inbound", {"test": True})
    assert client.calls == []


def test_wazzup_transport_marks_post_dispatch_errors_uncertain_without_secret_output() -> (
    None
):
    from scripts.e2e_acceptance.live_transport import OneShotWazzupWebhookTransport

    secret = "do-not-print-this-destination-or-body"
    client = _HttpClient(RuntimeError(secret))
    transport = OneShotWazzupWebhookTransport(
        endpoint="https://private.example/api/v1/webhook/wazzup", client=client
    )

    with pytest.raises(DispatchUncertainError) as raised:
        transport.request("webhook.inbound", _wazzup_payload())

    assert len(client.calls) == 1
    assert secret not in str(raised.value)
    assert raised.value.__cause__ is None


def test_wazzup_transport_rejects_non_object_json_response_as_uncertain() -> None:
    from scripts.e2e_acceptance.live_transport import OneShotWazzupWebhookTransport

    client = _HttpClient(_Response(["not", "an", "object"]))
    transport = OneShotWazzupWebhookTransport(
        endpoint="https://noor.starec.ai/api/v1/webhook/wazzup", client=client
    )

    with pytest.raises(DispatchUncertainError, match="response"):
        transport.request("webhook.inbound", _wazzup_payload())


class _SshRunner:
    def __init__(self, outcome: subprocess.CompletedProcess[bytes] | Exception) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, object]] = []

    def run(
        self, args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        self.calls.append({"args": args, **kwargs})
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_read_only_ssh_runs_only_allowlisted_command_and_exposes_identity_digest() -> (
    None
):
    from scripts.e2e_acceptance.live_transport import ReadOnlySshTransport

    runner = _SshRunner(subprocess.CompletedProcess([], 0, stdout=b'{"ok":true}'))
    transport = ReadOnlySshTransport(
        host_alias="noor-production",
        source_commands={"inventory": ("/usr/bin/cat", "/var/lib/noor/inventory")},
        runner=runner,
    )

    assert transport.read("inventory") == b'{"ok":true}'
    assert runner.calls == [
        {
            "args": [
                "ssh",
                "noor-production",
                "--",
                "/usr/bin/cat",
                "/var/lib/noor/inventory",
            ],
            "capture_output": True,
            "check": False,
            "shell": False,
            "timeout": 10.0,
        }
    ]
    assert transport.command_digests["inventory"] == transport.command_digest(
        "inventory"
    )
    assert len(transport.command_digest("inventory")) == 64


def test_read_only_ssh_rejects_unknown_or_mutating_commands_without_running() -> None:
    from scripts.e2e_acceptance.live_transport import ReadOnlySshTransport

    runner = _SshRunner(subprocess.CompletedProcess([], 0, stdout=b""))
    with pytest.raises(ProductionAdapterError, match="read-only"):
        ReadOnlySshTransport(
            host_alias="noor-production",
            source_commands={"inventory": ("rm", "-rf", "/tmp/x")},
            runner=runner,
        )

    transport = ReadOnlySshTransport(
        host_alias="noor-production",
        source_commands={"inventory": ("/usr/bin/cat", "/var/lib/noor/inventory")},
        runner=runner,
    )
    with pytest.raises(ProductionAdapterError, match="source"):
        transport.read("not-allowlisted")
    assert runner.calls == []


@pytest.mark.parametrize(
    "command",
    [
        ("find", "/tmp", "-maxdepth", "0", "-fprint", "/tmp/collector-write"),
        ("find", "/tmp", "-ok", "rm", "{}", ";"),
        ("journalctl", "--vacuum-time=1s"),
        ("journalctl", "--rotate"),
    ],
)
def test_read_only_ssh_rejects_binaries_with_mutating_argument_surfaces(
    command: tuple[str, ...],
) -> None:
    from scripts.e2e_acceptance.live_transport import ReadOnlySshTransport

    runner = _SshRunner(subprocess.CompletedProcess([], 0, stdout=b""))

    with pytest.raises(ProductionAdapterError, match="read-only"):
        ReadOnlySshTransport(
            host_alias="noor-production",
            source_commands={"inventory": command},
            runner=runner,
        )
    assert runner.calls == []


@pytest.mark.parametrize(
    "outcome",
    [
        subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"private failure"),
        subprocess.TimeoutExpired("ssh", 10),
    ],
)
def test_read_only_ssh_fails_closed_without_emitting_stderr(
    outcome: subprocess.CompletedProcess[bytes] | Exception,
) -> None:
    from scripts.e2e_acceptance.live_transport import ReadOnlySshTransport

    runner = _SshRunner(outcome)
    transport = ReadOnlySshTransport(
        host_alias="noor-production",
        source_commands={"inventory": ("/usr/bin/cat", "/var/lib/noor/inventory")},
        runner=runner,
    )

    with pytest.raises(ProductionAdapterError) as raised:
        transport.read("inventory")
    assert "private failure" not in str(raised.value)


def test_transport_module_does_not_emit_destination_or_body(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts.e2e_acceptance.live_transport import OneShotWazzupWebhookTransport

    payload = _wazzup_payload()
    client = _HttpClient(_Response({"ok": True}))
    OneShotWazzupWebhookTransport(
        endpoint="https://private.example/api/v1/webhook/wazzup", client=client
    ).request("webhook.inbound", payload)

    output = capsys.readouterr()
    assert "private.example" not in output.out + output.err
    assert json.dumps(payload) not in output.out + output.err
