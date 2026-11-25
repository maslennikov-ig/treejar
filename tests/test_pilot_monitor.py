from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest
from scripts.pilot.check_pilot import REMOTE_SCRIPT


@pytest.mark.parametrize(
    ("account_credits", "key_remaining", "effective"),
    [
        (20, 10.1783, 0.1783),
        (60, 10.1783, 10.1783),
        (20, None, 0.1783),
        (None, 10.1783, None),
    ],
)
def test_pilot_credit_uses_the_spendable_balance(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    account_credits: int | None,
    key_remaining: float | None,
    effective: float | None,
) -> None:
    def urlopen(request: urllib.request.Request, *, timeout: int) -> io.StringIO:
        if request.full_url.endswith("/key"):
            data = {"limit": 30, "limit_remaining": key_remaining, "usage": 19.8217}
        elif account_credits is None:
            raise urllib.error.URLError("credits unavailable")
        else:
            data = {"total_credits": account_credits, "total_usage": 19.8217}
        return io.StringIO(json.dumps({"data": data}))

    section = REMOTE_SCRIPT.split('echo "--- [5] OPENROUTER CREDIT ---"', 1)[1]
    code = section.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-test-key")
    exec(compile(code, "pilot-credit", "exec"), {})

    lines = capsys.readouterr().out.splitlines()
    balance = json.loads(lines[-1])
    assert balance["limit_remaining"] == effective
    assert balance["key_limit_remaining"] == key_remaining
    assert any("OPENROUTER_ACCOUNT_BALANCE_UNAVAILABLE" in line for line in lines) is (
        account_credits is None
    )
