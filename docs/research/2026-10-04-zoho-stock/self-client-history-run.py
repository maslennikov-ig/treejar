"""Local launcher; send reviewed read-only code to app through SSH stdin.

Credentials/token stay in the app's memory. No production token replacement.
One client_credentials exchange, <=16 GETs, no retries/refresh/data writes.
"""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build(source=None):
    if source is None:
        source = (ROOT / "self-client-readonly-probe.py").read_text()
    history = (ROOT / "readonly-history.py").read_text()
    if (
        hashlib.sha256(history.encode()).hexdigest()
        != "4d0206dd17f6827fd5164ff9a75a811817e3d1d91badc98e5b12c8f9511be1b8"
    ):
        raise ValueError("unexpected_history_source")
    marker = "from __future__ import annotations\n"
    entrypoint = "asyncio.run(probe())"
    if source.count(marker) != 1 or source.count(entrypoint) != 1:
        raise ValueError("unexpected_probe_shape")
    source = source.replace(marker, marker + f"HISTORY_AUDIT_SOURCE = {history!r}\n", 1)
    source = source.replace(entrypoint, "asyncio.run(probe(HISTORY_AUDIT_SOURCE))", 1)
    compile(source, "<read-only-self-client-stdin>", "exec")
    return source


def main():
    probe_source = (ROOT / "self-client-readonly-probe.py").read_text()
    submitted_source = build(probe_source)
    probe_digest = hashlib.sha256(probe_source.encode()).hexdigest()
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
        input=submitted_source,
        text=True,
        capture_output=True,
        timeout=180,
    )
    if completed.returncode:
        raise SystemExit("remote read-only diagnostic failed; no raw output emitted")
    result = json.loads(completed.stdout)
    if (
        not isinstance(result, dict)
        or result.get("provider_coverage_verified") is not False
    ):
        raise SystemExit("unexpected diagnostic result")
    result["probe_source_sha256"] = probe_digest
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
