"""Offline security checks. OAuth transport is intercepted in every test."""

import asyncio
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "access_under_test", ROOT / "history-access.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CLIENT_ID = "1000.NEWCLIENTONLYFOROFFLINETEST"
probe_spec = importlib.util.spec_from_file_location(
    "probe_under_test", ROOT / "history-grant-probe.py"
)
probe = importlib.util.module_from_spec(probe_spec)
probe_spec.loader.exec_module(probe)


def payload(**extra):
    return {
        "access_token": "do-not-print-offline-token",
        "expires_in": 3600,
        "api_domain": "https://www.zohoapis.eu",
        "scope": ",".join(module.SCOPES),
        **extra,
    }


class AccessGuards(unittest.TestCase):
    def test_online_scopes_are_exactly_read_only(self):
        parsed = urlsplit(module.authorization_url(CLIENT_ID, "state-for-test"))
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "accounts.zoho.eu")
        self.assertEqual(query["access_type"], ["online"])
        self.assertEqual(query["redirect_uri"], [module.CALLBACK])
        self.assertEqual(set(query["scope"][0].split(",")), set(module.SCOPES))
        self.assertTrue(all(scope.endswith(".READ") for scope in module.SCOPES))

    def test_production_client_is_rejected(self):
        with (
            patch.object(
                module,
                "LIVE_CLIENT_FINGERPRINT",
                hashlib.sha256(CLIENT_ID.encode()).hexdigest()[:16],
            ),
            self.assertRaisesRegex(ValueError, "production_client_forbidden"),
        ):
            module.validate_client(CLIENT_ID, "offline-client-secret-at-least16")

    def test_secret_file_and_directory_are_private(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary) / "task-private"
            receipt = module.save_token(payload(), private)
            self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o700)
            target = private / "access-token.json"
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertNotIn("do-not-print-offline-token", json.dumps(receipt))
            self.assertNotIn("client_secret", target.read_text())

    def test_existing_token_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            module.save_token(payload(), private)
            original = (private / "access-token.json").read_bytes()
            with self.assertRaises(FileExistsError):
                module.save_token(payload(access_token="replacement"), private)
            self.assertEqual((private / "access-token.json").read_bytes(), original)

    def test_offline_and_broad_grants_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            for extra in (
                {"refresh_token": "offline"},
                {"scope": "ZohoInventory.FullAccess.all"},
                {"api_domain": "https://other-domain.invalid"},
                {"expires_in": True},
            ):
                with self.assertRaises(ValueError):
                    module.save_token(payload(**extra), Path(temporary))
            self.assertFalse((Path(temporary) / "access-token.json").exists())

    def test_symlink_private_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "real").mkdir()
            (directory / "link").symlink_to(
                directory / "real", target_is_directory=True
            )
            with self.assertRaisesRegex(ValueError, "unsafe_private_directory"):
                module.save_token(payload(), directory / "link")

    def test_symlink_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "real").mkdir()
            (directory / "link").symlink_to(
                directory / "real", target_is_directory=True
            )
            with self.assertRaisesRegex(ValueError, "unsafe_private_directory"):
                module.save_token(payload(), directory / "link/child")

    def test_absent_scope_is_reported_as_unobserved(self):
        data = payload()
        del data["scope"]
        with tempfile.TemporaryDirectory() as temporary:
            receipt = module.save_token(data, Path(temporary))
            self.assertFalse(receipt["granted_scopes_reported"])
            self.assertEqual(receipt["requested_read_scopes"], list(module.SCOPES))

    def test_invalid_state_never_exchanges(self):
        session = module.Onboarding()
        session.client_id = CLIENT_ID
        with patch.object(module.httpx, "post") as post:
            with self.assertRaisesRegex(ValueError, "invalid_oauth_state"):
                session.exchange("wrong-state", "do-not-print-code")
            post.assert_not_called()

    def test_callback_is_exchanged_once_and_secret_cleared(self):
        session = module.Onboarding()
        session.client_id = CLIENT_ID
        session.client_secret = "do-not-print-client-secret"
        response = httpx.Response(200, json=payload())
        with tempfile.TemporaryDirectory() as temporary:
            original = module.save_token
            with (
                patch.object(module.httpx, "post", return_value=response) as post,
                patch.object(
                    module,
                    "save_token",
                    side_effect=lambda data: original(data, Path(temporary)),
                ),
            ):
                receipt = session.exchange(session.state, "do-not-print-code")
                self.assertEqual(post.call_count, 1)
                self.assertEqual(
                    post.call_args.args[0], "https://accounts.zoho.eu/oauth/v2/token"
                )
                self.assertEqual(
                    post.call_args.kwargs["data"]["grant_type"], "authorization_code"
                )
                self.assertEqual(session.client_secret, "")
                self.assertTrue(session.done)
                with self.assertRaisesRegex(ValueError, "callback_replay"):
                    session.exchange(session.state, "do-not-print-code")
                self.assertEqual(post.call_count, 1)
                self.assertNotIn("do-not-print", json.dumps(receipt))

    def test_refused_exchange_is_not_retried(self):
        session = module.Onboarding()
        session.client_id = CLIENT_ID
        session.client_secret = "do-not-print-client-secret"
        with patch.object(
            module.httpx, "post", return_value=httpx.Response(401)
        ) as post:
            with self.assertRaises(ValueError):
                session.exchange(session.state, "do-not-print-code")
            self.assertEqual(session.client_secret, "")
            with self.assertRaises(ValueError):
                session.exchange(session.state, "do-not-print-code")
            self.assertEqual(post.call_count, 1)


class GrantProbeGuards(unittest.TestCase):
    def grant(self):
        return {
            "access_token": "separate-offline-token'\n",
            "expires_at": time.time() + 600,
            "requested_scopes": list(probe.access.SCOPES),
            "organization_fingerprint": probe.access.ORGANIZATION_FINGERPRINT,
        }

    def test_private_file_is_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "access-token.json"
            target.write_text(json.dumps(self.grant()))
            target.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "unsafe_token_file"):
                probe.read_grant(target)
            target.chmod(0o600)
            self.assertEqual(
                probe.read_grant(target)["access_token"], self.grant()["access_token"]
            )
            link = Path(temporary) / "link"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "unsafe_token_path"):
                probe.read_grant(link)

    def test_expired_or_different_grant_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "access-token.json"
            for extra in (
                {"expires_at": time.time() - 1},
                {"expires_at": True},
                {"requested_scopes": ["ZohoInventory.FullAccess.all"]},
                {"organization_fingerprint": "different"},
            ):
                target.write_text(json.dumps({**self.grant(), **extra}))
                target.chmod(0o600)
                with self.assertRaises(ValueError):
                    probe.read_grant(target)

    def test_pinned_diagnostic_source_is_required(self):
        source = (ROOT / "readonly-history.py").read_text()
        probe.build_probe(self.grant(), source)
        with self.assertRaisesRegex(ValueError, "diagnostic_source_changed"):
            probe.build_probe(self.grant(), source + "\n")

    def test_token_uses_stdin_only(self):
        grant = self.grant()
        output = io.StringIO()
        reply = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"provider_coverage_verified": False, "requests": []}),
        )
        with (
            patch.object(probe, "read_grant", return_value=grant),
            patch.object(probe.subprocess, "run", return_value=reply) as run,
            contextlib.redirect_stdout(output),
        ):
            probe.main()
        self.assertNotIn(grant["access_token"], str(run.call_args.args[0]))
        self.assertNotIn("env", run.call_args.kwargs)
        self.assertIn(repr(grant["access_token"]), run.call_args.kwargs["input"])
        self.assertNotIn("separate-offline-token", output.getvalue())

    def test_missing_token_never_starts_ssh(self):
        with (
            patch.object(probe, "read_grant", side_effect=FileNotFoundError),
            patch.object(probe.subprocess, "run") as run,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            probe.main()
        run.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["inventory_requests"], 0)

    def test_org_host_and_401_guards_use_only_the_separate_token(self):
        class ReadOnlyRedis:
            @classmethod
            def from_url(cls, *args, **kwargs):
                return cls()

            async def get(self, key):
                self_test.assertEqual(key, "zoho:inventory:rate_limited_until")
                return None

            async def aclose(self):
                pass

        self_test = self
        grant = self.grant()
        grant["access_token"] = "separate-offline-token"
        expected_org = hashlib.sha256(b"offline-org").hexdigest()[:16]
        with patch.object(probe.access, "ORGANIZATION_FINGERPRINT", expected_org):
            script = probe.build_probe(
                grant, (ROOT / "readonly-history.py").read_text()
            )
        globals_under_test = {"__name__": "offline_probe"}
        exec(script, globals_under_test)
        globals_under_test["Redis"] = ReadOnlyRedis
        original_client = httpx.AsyncClient
        sent = []

        def handler(request):
            self.assertEqual(request.method, "GET")
            self.assertEqual(
                request.headers["Authorization"],
                "Zoho-oauthtoken separate-offline-token",
            )
            sent.append(request)
            return httpx.Response(401, json={"code": 57})

        def intercepted_client(**kwargs):
            return original_client(**kwargs, transport=httpx.MockTransport(handler))

        for organization, host, expected in (
            (
                "different-org",
                "https://www.zohoapis.eu/inventory/v1",
                "unexpected_org_or_expired_grant_no_request",
            ),
            (
                "offline-org",
                "https://other-host.invalid",
                "unexpected_api_host_no_request",
            ),
            (
                "offline-org",
                "https://www.zohoapis.eu/inventory/v1",
                "http_401_no_refresh_or_retry",
            ),
        ):
            with (
                patch.dict(
                    os.environ,
                    {
                        "ZOHO_INVENTORY_ORG_ID": organization,
                        "ZOHO_INVENTORY_API_URL": host,
                    },
                ),
                patch.object(
                    httpx, "AsyncClient", side_effect=intercepted_client
                ) as client,
            ):
                result = asyncio.run(globals_under_test["audit"]())
            self.assertEqual(result["stopped"], expected)
            if expected.startswith("http_401"):
                self.assertEqual(len(sent), 1)
                self.assertEqual(len(result["requests"]), 1)
                self.assertEqual(client.call_count, 1)
            else:
                client.assert_not_called()
                self.assertEqual(result["requests"], [])
                self.assertEqual(sent, [])
            self.assertNotIn("separate-offline-token", json.dumps(result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
