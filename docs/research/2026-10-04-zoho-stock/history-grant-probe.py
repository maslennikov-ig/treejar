"""Use a separate online read-only grant for the existing bounded history audit.

No token is passed in arguments/environment or written to the server. The
in-memory diagnostic is sent over SSH stdin. No production grant, Redis or
configuration is changed. Run only after the owner completes history-access.py.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import stat
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "history_access", ROOT / "history-access.py"
)
access = importlib.util.module_from_spec(spec)
spec.loader.exec_module(access)
AUDIT_SHA256 = "4d0206dd17f6827fd5164ff9a75a811817e3d1d91badc98e5b12c8f9511be1b8"


def read_grant(path: Path) -> dict:
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("unsafe_token_path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > 16384
        ):
            raise ValueError("unsafe_token_file")
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError("malformed_grant")
    token, expiry = data.get("access_token"), data.get("expires_at")
    if not isinstance(token, str) or not 1 <= len(token) <= 4096:
        raise ValueError("missing_token")
    if (
        isinstance(expiry, bool)
        or not isinstance(expiry, (int, float))
        or not math.isfinite(expiry)
        or not time.time() < expiry <= time.time() + 3600
    ):
        raise ValueError("expired_or_invalid_grant")
    if (
        data.get("requested_scopes") != list(access.SCOPES)
        or data.get("organization_fingerprint") != access.ORGANIZATION_FINGERPRINT
    ):
        raise ValueError("unexpected_grant_context")
    return data


def build_probe(grant: dict, source: str) -> str:
    if hashlib.sha256(source.encode()).hexdigest() != AUDIT_SHA256:
        raise ValueError("diagnostic_source_changed_review_required")
    replacements = {
        'token = await redis.get("zoho:access_token")': "token = AUDIT_TOKEN",
        'org = os.environ.get("ZOHO_INVENTORY_ORG_ID", "")': (
            'org = os.environ.get("ZOHO_INVENTORY_ORG_ID", "")\n'
            "        if hashlib.sha256(org.encode()).hexdigest()[:16] != AUDIT_ORG or time.time() >= AUDIT_EXPIRY:\n"
            '            result["stopped"] = "unexpected_org_or_expired_grant_no_request"\n'
            "            return result"
        ),
        "async with httpx.AsyncClient(": (
            'if base != "https://www.zohoapis.eu/inventory/v1":\n'
            '            result["stopped"] = "unexpected_api_host_no_request"\n'
            "            return result\n"
            "        async with httpx.AsyncClient("
        ),
    }
    for before, after in replacements.items():
        if source.count(before) != 1:
            raise ValueError("unexpected_diagnostic_shape")
        source = source.replace(before, after, 1)
    prefix = (
        f"AUDIT_TOKEN = {grant['access_token']!r}\n"
        f"AUDIT_EXPIRY = {grant['expires_at']!r}\n"
        f"AUDIT_ORG = {access.ORGANIZATION_FINGERPRINT!r}\n"
    )
    # Keep the __future__ import first; insert private globals immediately after it.
    marker = "from __future__ import annotations\n"
    if source.count(marker) != 1:
        raise ValueError("unexpected_future_import")
    source = source.replace(marker, marker + prefix, 1)
    compile(source, "<read-only-history-stdin>", "exec")
    return source


def main():
    request_started = False
    try:
        grant = read_grant(access.PRIVATE_DIR / "access-token.json")
        source = (ROOT / "readonly-history.py").read_text()
        script = build_probe(grant, source)
        request_started = True
        completed = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                "noor-server",
                "cd /opt/noor && docker compose exec -T app python -",
            ],
            input=script,
            text=True,
            capture_output=True,
            timeout=180,
        )
        if completed.returncode != 0:
            raise ValueError("remote_diagnostic_failed")
        result = json.loads(completed.stdout)
        if (
            not isinstance(result, dict)
            or result.get("provider_coverage_verified") is not False
        ):
            raise ValueError("unexpected_diagnostic_result")
        result["token_source"] = "separate_online_readonly_grant"
        result["original_diagnostic_sha256"] = AUDIT_SHA256
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "stopped": "grant_probe_unavailable",
                    "error_type": type(exc).__name__,
                    "remote_started": request_started,
                    "inventory_requests": None if request_started else 0,
                    "provider_coverage_verified": False,
                }
            )
        )


if __name__ == "__main__":
    main()
