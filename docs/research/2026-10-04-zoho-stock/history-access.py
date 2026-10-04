"""Local, short-lived, read-only Zoho OAuth onboarding for the stock audit.

Run with the existing uv environment. Register a NEW server-based OAuth client
in the EU console, homepage https://noor.starec.ai, redirect URI as printed here.
Client credentials are entered in the local browser, never the chat/terminal.
Only an owner-approved online authorization-code exchange is performed. No
Inventory requests, production config/Redis writes, refresh or revoke calls.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import secrets
import stat
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

PORT = 8769
ORIGIN = f"http://127.0.0.1:{PORT}"
CALLBACK = ORIGIN + "/zoho-history/callback"
LIVE_CLIENT_FINGERPRINT = "ecf28d8fc9037516"
ORGANIZATION_FINGERPRINT = "544f8528f9db448a"
PRIVATE_DIR = Path.home() / ".local/state/treejar/tj-uvld/zoho-history"
SCOPES = (
    "ZohoInventory.items.READ",
    "ZohoInventory.inventoryadjustments.READ",
    "ZohoInventory.purchasereceives.READ",
    "ZohoInventory.salesreturns.READ",
    "ZohoInventory.transferorders.READ",
    "ZohoInventory.packages.READ",
)


def validate_client(client_id: str, client_secret: str) -> None:
    if not client_id.startswith("1000.") or not 10 <= len(client_id) <= 256:
        raise ValueError("invalid_client_id")
    if not 16 <= len(client_secret) <= 512:
        raise ValueError("invalid_client_secret")
    if hashlib.sha256(client_id.encode()).hexdigest()[:16] == LIVE_CLIENT_FINGERPRINT:
        raise ValueError("production_client_forbidden_use_a_new_client")


def authorization_url(client_id: str, state: str) -> str:
    return "https://accounts.zoho.eu/oauth/v2/auth?" + urlencode(
        {
            "client_id": client_id,
            "scope": ",".join(SCOPES),
            "response_type": "code",
            "redirect_uri": CALLBACK,
            "access_type": "online",
            "prompt": "consent",
            "state": state,
        }
    )


def save_token(payload: dict, private_dir: Path = PRIVATE_DIR) -> dict:
    token = payload.get("access_token")
    if not isinstance(token, str) or not token or len(token) > 4096:
        raise ValueError("missing_access_token")
    if payload.get("refresh_token"):
        raise ValueError("unexpected_offline_grant")
    if (
        payload.get("api_domain", "https://www.zohoapis.eu")
        != "https://www.zohoapis.eu"
    ):
        raise ValueError("unexpected_data_center")
    reported_scope = payload.get("scope")
    if reported_scope is not None:
        if not isinstance(reported_scope, str):
            raise ValueError("unexpected_scope_format")
        actual = set(reported_scope.replace(",", " ").split())
        if actual != set(SCOPES):
            raise ValueError("unexpected_granted_scopes")
    lifetime = payload.get("expires_in")
    if (
        isinstance(lifetime, bool)
        or not isinstance(lifetime, int)
        or not 1 <= lifetime <= 3600
    ):
        raise ValueError("unexpected_token_lifetime")
    if any(path.is_symlink() for path in (private_dir, *private_dir.parents)):
        raise ValueError("unsafe_private_directory")
    private_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = private_dir.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("unsafe_private_directory")
    os.chmod(private_dir, 0o700)
    target = private_dir / "access-token.json"
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    stored = {
        "access_token": token,
        "expires_at": time.time() + lifetime,
        "requested_scopes": list(SCOPES),
        "organization_fingerprint": ORGANIZATION_FINGERPRINT,
    }
    with os.fdopen(fd, "w") as stream:
        json.dump(stored, stream)
    return {
        "stored": True,
        "path": str(target),
        "expires_in_seconds": lifetime,
        "requested_read_scopes": list(SCOPES),
        "granted_scopes_reported": reported_scope is not None,
        "oauth_refreshes": 0,
        "inventory_requests": 0,
    }


class Onboarding:
    def __init__(self):
        self.csrf = secrets.token_urlsafe(32)
        self.state = secrets.token_urlsafe(32)
        self.client_id = ""
        self.client_secret = ""
        self.exchange_attempted = False
        self.done = False

    def exchange(self, state: str, code: str) -> dict:
        if (
            not state
            or not secrets.compare_digest(state, self.state)
            or not self.client_id
        ):
            raise ValueError("invalid_oauth_state")
        if self.exchange_attempted or not code or len(code) > 4096:
            raise ValueError("callback_replay_or_invalid_code")
        self.exchange_attempted = True
        try:
            response = httpx.post(
                "https://accounts.zoho.eu/oauth/v2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": CALLBACK,
                },
                timeout=8,
                follow_redirects=False,
            )
            if response.status_code != 200:
                raise ValueError("oauth_exchange_refused_no_retry")
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("malformed_oauth_response")
            receipt = save_token(payload)
            self.done = True
            return receipt
        finally:
            self.client_secret = ""


def handler_for(session: Onboarding):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # callback URL contains a one-time code; do not log it.

        def reply(self, status: int, body: str, location: str | None = None):
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; form-action 'self' https://accounts.zoho.eu; frame-ancestors 'none'",
            )
            if location:
                self.send_header("Location", location)
            self.end_headers()
            self.wfile.write(body.encode())

        def valid_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{PORT}"

        def do_GET(self):
            if not self.valid_host():
                self.reply(403, "Forbidden host")
                return
            parsed = urlsplit(self.path)
            if parsed.path == "/":
                self.reply(
                    200,
                    '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Zoho: только чтение</title>'
                    "<h1>Отдельный доступ Zoho только на чтение</h1>"
                    '<p>В <a href="https://api-console.zoho.eu/" rel="noreferrer noopener" target="_blank">Zoho API Console</a> '
                    "создайте новый клиент: Add Client → Server-based Applications. "
                    "Существующий рабочий клиент не меняйте.</p>"
                    "<dl><dt>Client Name</dt><dd>Noor stock audit read-only</dd>"
                    "<dt>Homepage URL</dt><dd>https://noor.starec.ai</dd>"
                    "<dt>Authorized Redirect URI</dt><dd><code>"
                    + CALLBACK
                    + "</code></dd></dl>"
                    "<p>Введите данные нового клиента только в этой локальной форме. "
                    "После перехода Zoho запросит согласие на чтение. "
                    "Токен действует до часа; постоянный refresh token не запрашивается.</p>"
                    '<form method="post" action="/authorize" autocomplete="off"><input type="hidden" name="csrf" value="'
                    + html.escape(session.csrf)
                    + '">'
                    '<p><label>Client ID <input name="client_id" required></label></p>'
                    '<p><label>Client secret <input type="password" name="client_secret" required></label></p>'
                    "<button>Перейти к разрешению в Zoho</button></form></html>",
                )
            elif parsed.path == "/zoho-history/callback":
                try:
                    params = parse_qs(parsed.query, max_num_fields=12)
                    if (
                        len(params.get("state", [])) != 1
                        or len(params.get("code", [])) != 1
                    ):
                        raise ValueError("missing_or_duplicate_callback_fields")
                    receipt = session.exchange(params["state"][0], params["code"][0])
                    print(json.dumps(receipt), flush=True)
                    self.reply(
                        200,
                        "Готово. Отдельный токен сохранён локально; можно вернуться в Codex.",
                    )
                except Exception as exc:
                    print(
                        json.dumps(
                            {
                                "stopped": "onboarding_failed",
                                "error_type": type(exc).__name__,
                            }
                        ),
                        flush=True,
                    )
                    self.reply(
                        400,
                        "Авторизация не завершилась. Секреты сохранены только при успешном обмене; повторного обмена нет.",
                    )
            else:
                self.reply(404, "Not found")

        def do_POST(self):
            if (
                not self.valid_host()
                or self.headers.get("Origin") != ORIGIN
                or self.path != "/authorize"
            ):
                self.reply(403, "Forbidden origin")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 4096:
                    raise ValueError("invalid_form_size")
                params = parse_qs(self.rfile.read(length).decode(), max_num_fields=3)
                if any(
                    len(params.get(key, [])) != 1
                    for key in ("csrf", "client_id", "client_secret")
                ):
                    raise ValueError("invalid_form_fields")
                if (
                    not secrets.compare_digest(params["csrf"][0], session.csrf)
                    or session.exchange_attempted
                ):
                    raise ValueError("invalid_csrf_or_completed_flow")
                validate_client(params["client_id"][0], params["client_secret"][0])
                session.client_id, session.client_secret = (
                    params["client_id"][0],
                    params["client_secret"][0],
                )
                self.reply(303, "", authorization_url(session.client_id, session.state))
            except (ValueError, UnicodeError):
                self.reply(
                    400,
                    "Проверьте данные нового клиента. Рабочий production client здесь запрещён.",
                )

    return Handler


def main():
    target = PRIVATE_DIR / "access-token.json"
    if target.exists() or target.is_symlink():
        print(json.dumps({"stopped": "existing_token_not_overwritten"}), flush=True)
        return
    session = Onboarding()
    deadline = time.monotonic() + 900
    with HTTPServer(("127.0.0.1", PORT), handler_for(session)) as server:
        server.timeout = 1
        print(
            json.dumps(
                {
                    "local_url": ORIGIN,
                    "redirect_uri": CALLBACK,
                    "scopes": SCOPES,
                    "private_token_directory": str(PRIVATE_DIR),
                    "lifetime_seconds": 900,
                }
            ),
            flush=True,
        )
        try:
            while not session.done and time.monotonic() < deadline:
                server.handle_request()
        except KeyboardInterrupt:
            pass
        finally:
            session.client_secret = ""


if __name__ == "__main__":
    main()
