"""Append-only evidence storage and privacy validation for Noor E2E runs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,80}$")
_PHONE = re.compile(r"(?:\+\d[\d ().-]{8,24}\d|(?<![\w-])\d{10,15}(?![\w-]))")
_CREDENTIAL = re.compile(
    r"(?i)(?:bearer\s+[a-z0-9._~+/=-]{4,}|"
    r"(?:api[_ -]?key|token|password|secret)\s*[:=]\s*\S+)"
)
_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "credential",
        "credentials",
        "password",
        "secret",
        "token",
    }
)
_MANAGER_KEYS = frozenset(
    {"private_manager", "private_manager_data", "manager_private_data"}
)
_LOG_KEYS = frozenset(
    {
        "logs",
        "raw_log",
        "raw_logs",
        "production_log",
        "production_logs",
        "unrestricted_log",
        "unrestricted_logs",
    }
)
_REDACTED_SECRET = "[REDACTED_SECRET]"
_REDACTED_MANAGER = "[REDACTED_MANAGER_DATA]"
_REDACTED_LOG = "[REDACTED_UNRESTRICTED_LOG]"
_REDACTED_PHONE = "[REDACTED_PHONE]"
_TERMINAL_DISPOSITIONS = frozenset(
    {"voided", "closed", "resolved", "retained_as_test_evidence"}
)
_NONTERMINAL_DISPOSITIONS = frozenset({"cleanup_pending", "cleanup_blocked", "unknown"})
_TERMINAL_STATE_BY_DISPOSITION: dict[str, frozenset[str]] = {
    "voided": frozenset({"voided"}),
    "closed": frozenset({"closed"}),
    "resolved": frozenset({"resolved"}),
    "retained_as_test_evidence": frozenset({"retained"}),
}
_ARTIFACT_TYPES_BY_SUBSYSTEM: dict[str, frozenset[str]] = {
    "conversation": frozenset({"conversation", "audit", "feedback"}),
    "crm": frozenset({"crm_contact", "crm_deal", "crm_stage_transition"}),
    "escalation": frozenset({"escalation"}),
    "lifecycle": frozenset({"feedback", "followup", "payment_reminder"}),
    "quotation": frozenset({"quotation", "sale_order"}),
    "referral": frozenset({"referral", "reward"}),
    "telegram": frozenset({"callback", "telegram_alert"}),
}


class EvidenceError(ValueError):
    """Evidence is unsafe, mutable, malformed, or incomplete."""


@dataclass(frozen=True)
class EvidenceRecord:
    """Integrity identity for one stored evidence object."""

    relative_path: str
    path: Path
    sha256: str
    size_bytes: int

    def public_dict(self) -> dict[str, str | int]:
        return {
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def _normal_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _is_secret_key(value: str) -> bool:
    compact = value.replace("_", "")
    if value in {
        "authorization_id",
        "authorization_manifest_digest",
        "authorization_binding_verified",
        "token_count",
    }:
        return False
    return (
        value in _SECRET_KEYS
        or compact
        in {
            "apikey",
            "authtoken",
            "authorizationheader",
            "authorizationtoken",
            "clientsecret",
            "credential",
            "credentials",
            "password",
            "refreshtoken",
            "secret",
        }
        or value.startswith(
            ("authorization_header", "authorization_secret", "authorization_token")
        )
        or value.endswith(("_api_key", "_password", "_secret", "_token"))
    )


def _is_manager_key(value: str) -> bool:
    compact = value.replace("_", "")
    return (
        value in _MANAGER_KEYS
        or value.startswith(("private_manager_", "manager_private_"))
        or compact
        in {
            "managercontact",
            "manageremail",
            "managermobile",
            "managername",
            "managerphone",
            "managerwhatsapp",
        }
    )


def _is_log_key(value: str) -> bool:
    compact = value.replace("_", "")
    return (
        compact
        in {
            "fulllog",
            "fulllogs",
            "productionlog",
            "productionlogs",
            "rawlog",
            "rawlogs",
            "unrestrictedlog",
            "unrestrictedlogs",
        }
        or value in _LOG_KEYS
        or value.endswith(
            ("_raw_log", "_raw_logs", "_production_log", "_production_logs")
        )
    )


def _is_redacted(value: object, marker: str) -> bool:
    return isinstance(value, str) and value == marker


def _redact_string(value: str) -> str:
    value = _CREDENTIAL.sub(_REDACTED_SECRET, value)
    return _PHONE.sub(_REDACTED_PHONE, value)


def redact_payload(value: Any) -> Any:
    """Recursively remove sensitive fields and inline secrets/phone numbers."""

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized = _normal_key(key)
            if _is_secret_key(normalized):
                redacted[key] = _REDACTED_SECRET
            elif _is_manager_key(normalized):
                redacted[key] = _REDACTED_MANAGER
            elif _is_log_key(normalized):
                redacted[key] = _REDACTED_LOG
            else:
                redacted[key] = redact_payload(child)
        return redacted
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def validate_redacted_payload(value: Any, *, _path: str = "$") -> None:
    """Reject recursively leaked secrets, full phones, manager data, and logs."""

    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized = _normal_key(key)
            child_path = f"{_path}.{key}"
            if _is_secret_key(normalized) and not _is_redacted(child, _REDACTED_SECRET):
                raise EvidenceError(f"credential material at {child_path}")
            if _is_manager_key(normalized) and not _is_redacted(
                child, _REDACTED_MANAGER
            ):
                raise EvidenceError(f"private manager data at {child_path}")
            if _is_log_key(normalized) and not _is_redacted(child, _REDACTED_LOG):
                raise EvidenceError(f"unrestricted log at {child_path}")
            validate_redacted_payload(child, _path=child_path)
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_redacted_payload(child, _path=f"{_path}[{index}]")
        return
    if isinstance(value, str):
        if _CREDENTIAL.search(value):
            raise EvidenceError(f"credential material at {_path}")
        if _PHONE.search(value):
            raise EvidenceError(f"full phone number at {_path}")


def validate_redacted_serialized(payload: bytes) -> None:
    """Validate the final serialized evidence bytes before storage or reuse."""

    try:
        text = payload.decode("utf-8")
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(
            f"redacted evidence serialization is invalid: {exc}"
        ) from exc
    validate_redacted_payload(value)
    if _CREDENTIAL.search(text):
        raise EvidenceError("credential material in serialized evidence")
    if _PHONE.search(text):
        raise EvidenceError("full phone number in serialized evidence")


def validate_redacted_text(value: str) -> None:
    """Reject inline secret or full-phone material in a final text artifact."""

    if _CREDENTIAL.search(value):
        raise EvidenceError("credential material in serialized text")
    if _PHONE.search(value):
        raise EvidenceError("full phone number in serialized text")


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _validated_relative_path(value: str) -> Path:
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise EvidenceError(f"unsafe evidence path: {value}")
    return path


def _directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None or os.open not in os.supports_dir_fd:
        raise EvidenceError(
            "secure evidence I/O requires O_NOFOLLOW, O_DIRECTORY, and dir_fd"
        )
    return int(os.O_RDONLY | nofollow | directory | getattr(os, "O_CLOEXEC", 0))


def _open_directory_chain(root: Path, parts: tuple[str, ...], *, create: bool) -> int:
    flags = _directory_flags()
    try:
        descriptor = os.open(root, flags)
    except OSError as exc:
        raise EvidenceError(f"unsafe evidence root: {root}: {exc}") from exc
    try:
        for part in parts:
            try:
                child = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o700, dir_fd=descriptor)
                child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise EvidenceError(
            f"unsafe evidence directory chain under {root}: {exc}"
        ) from exc
    except Exception:
        os.close(descriptor)
        raise


def _secure_exclusive_write(
    root: Path,
    relative: Path,
    payload: bytes,
    *,
    mode: int,
) -> None:
    parent_fd = _open_directory_chain(root, relative.parts[:-1], create=True)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    file_fd = -1
    try:
        file_fd = os.open(relative.name, flags, mode, dir_fd=parent_fd)
        os.fchmod(file_fd, mode)
        with os.fdopen(file_fd, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(file_fd)
    except FileExistsError as exc:
        raise EvidenceError(
            f"append-only evidence already exists: {relative.as_posix()}"
        ) from exc
    except OSError as exc:
        raise EvidenceError(
            f"cannot securely create evidence: {relative.as_posix()}: {exc}"
        ) from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(parent_fd)


def _secure_read(root: Path, relative: Path) -> bytes:
    parent_fd = _open_directory_chain(root, relative.parts[:-1], create=False)
    file_fd = -1
    try:
        file_fd = os.open(
            relative.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            raise EvidenceError(f"evidence is not a regular file: {relative}")
        chunks: list[bytes] = []
        while block := os.read(file_fd, 65536):
            chunks.append(block)
        return b"".join(chunks)
    except EvidenceError:
        raise
    except OSError as exc:
        raise EvidenceError(
            f"cannot securely read evidence: {relative.as_posix()}: {exc}"
        ) from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        os.close(parent_fd)


def load_verified_evidence_index(root: Path) -> dict[str, dict[str, Any]]:
    """Resolve a tracked evidence index against no-follow file reads."""

    if root.is_symlink() or not root.is_dir():
        raise EvidenceError("evidence index root is not a safe directory")
    index_payload = _secure_read(root, Path("evidence-index.json"))
    try:
        index = json.loads(index_payload)
    except json.JSONDecodeError as exc:
        raise EvidenceError("evidence index JSON is invalid") from exc
    if (
        not isinstance(index, dict)
        or index.get("schema_version") != "noor-e2e-evidence-index/v1"
        or not isinstance(index.get("entries"), list)
    ):
        raise EvidenceError("evidence index contract is invalid")
    resolved: dict[str, dict[str, Any]] = {}
    for entry in index["entries"]:
        if not isinstance(entry, dict):
            raise EvidenceError("evidence index entry is invalid")
        relative_raw = entry.get("relative_path")
        expected_digest = entry.get("sha256")
        if not isinstance(relative_raw, str) or not isinstance(expected_digest, str):
            raise EvidenceError("evidence index identity is incomplete")
        relative = _validated_relative_path(relative_raw)
        if relative.as_posix() in resolved:
            raise EvidenceError("evidence index contains duplicate paths")
        payload = _secure_read(root, relative)
        if hashlib.sha256(payload).hexdigest() != expected_digest:
            raise EvidenceError(
                f"evidence index integrity mismatch: {relative.as_posix()}"
            )
        validate_redacted_serialized(payload)
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise EvidenceError(
                f"indexed evidence is not an object: {relative.as_posix()}"
            )
        resolved[relative.as_posix()] = parsed
    return resolved


class EvidenceStore:
    """Store protected raw and tracked redacted evidence in separate roots."""

    def __init__(
        self,
        *,
        repo_root: Path,
        protected_root: Path,
        stage_id: str = "tj-ee5f",
    ) -> None:
        if protected_root.is_symlink():
            raise EvidenceError("protected raw evidence root cannot be a symlink")
        self.repo_root = repo_root.resolve()
        self.protected_root = protected_root.resolve()
        try:
            self.protected_root.relative_to(self.repo_root)
        except ValueError:
            pass
        else:
            raise EvidenceError("protected raw evidence must stay outside repository")
        if self.repo_root == self.protected_root:
            raise EvidenceError("protected raw evidence must stay outside repository")
        self.stage_id = stage_id
        self.tracked_root = self.repo_root / ".codex" / "stages" / stage_id / "results"
        self.protected_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        protected_fd = _open_directory_chain(self.protected_root, (), create=False)
        try:
            os.fchmod(protected_fd, 0o700)
        finally:
            os.close(protected_fd)
        tracked_fd = _open_directory_chain(
            self.repo_root,
            (".codex", "stages", stage_id, "results"),
            create=True,
        )
        try:
            os.fchmod(tracked_fd, 0o755)
        finally:
            os.close(tracked_fd)

    @staticmethod
    def sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()

    def _run_root(self, run_id: str, *, raw: bool) -> Path:
        if not _RUN_ID.fullmatch(run_id):
            raise EvidenceError(f"invalid run_id: {run_id}")
        base = self.protected_root if raw else self.tracked_root
        root = base / run_id
        run_fd = _open_directory_chain(base, (run_id,), create=True)
        try:
            os.fchmod(run_fd, 0o700 if raw else 0o755)
        finally:
            os.close(run_fd)
        return root

    def _write(
        self,
        run_id: str,
        relative_path: str,
        value: object,
        *,
        raw: bool,
    ) -> EvidenceRecord:
        relative = _validated_relative_path(relative_path)
        root = self._run_root(run_id, raw=raw)
        path = root / relative
        payload = _canonical_json_bytes(value)
        if not raw:
            validate_redacted_serialized(payload)
        _secure_exclusive_write(
            root,
            relative,
            payload,
            mode=0o600 if raw else 0o644,
        )
        return EvidenceRecord(
            relative_path=relative.as_posix(),
            path=path,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        )

    def write_raw_json(
        self, run_id: str, relative_path: str, value: object
    ) -> EvidenceRecord:
        return self._write(run_id, relative_path, value, raw=True)

    def write_redacted_json(
        self, run_id: str, relative_path: str, value: object
    ) -> EvidenceRecord:
        redacted = redact_payload(value)
        validate_redacted_payload(redacted)
        return self._write(run_id, relative_path, redacted, raw=False)

    def append_attempt(
        self, run_id: str, attempt: Mapping[str, object]
    ) -> EvidenceRecord:
        scenario_id = str(attempt.get("scenario_id", ""))
        attempt_number = attempt.get("attempt_number")
        attempt_id = str(attempt.get("attempt_id", ""))
        if not _RUN_ID.fullmatch(scenario_id.lower()) or not isinstance(
            attempt_number, int
        ):
            raise EvidenceError("attempt needs safe scenario_id and integer number")
        run_root = self._run_root(run_id, raw=False)
        protected_run_root = self._run_root(run_id, raw=True)
        expected_id = (
            f"attempt-{attempt_number:03d}" if isinstance(attempt_number, int) else ""
        )
        attempts_fd = _open_directory_chain(
            run_root,
            ("attempts", scenario_id),
            create=True,
        )
        try:
            attempt_names = sorted(
                name for name in os.listdir(attempts_fd) if name.startswith("attempt-")
            )
        finally:
            os.close(attempts_fd)
        if expected_id and f"{expected_id}.json" in attempt_names:
            raise EvidenceError(
                f"append-only evidence already exists: {expected_id}.json"
            )
        previous_digest: str | None = None
        previous_anchor_digest: str | None = None
        for index, name in enumerate(attempt_names, start=1):
            expected_name = f"attempt-{index:03d}.json"
            if name != expected_name:
                raise EvidenceError("attempt integrity sequence is not contiguous")
            relative = Path("attempts") / scenario_id / name
            payload = _secure_read(run_root, relative)
            actual_digest = hashlib.sha256(payload).hexdigest()
            anchor_relative = Path(f"anchors/{scenario_id}/attempt-{index:03d}.json")
            anchor_payload = _secure_read(protected_run_root, anchor_relative)
            anchor_digest = hashlib.sha256(anchor_payload).hexdigest()
            try:
                anchor = json.loads(anchor_payload)
            except json.JSONDecodeError as exc:
                raise EvidenceError(f"protected anchor JSON invalid: {name}") from exc
            if (
                anchor.get("tracked_sha256") != actual_digest
                or anchor.get("previous_anchor_sha256") != previous_anchor_digest
                or anchor.get("previous_attempt_sha256") != previous_digest
                or anchor.get("attempt_id") != f"attempt-{index:03d}"
                or anchor.get("scenario_id") != scenario_id
            ):
                raise EvidenceError(f"protected anchor integrity mismatch: {name}")
            sidecar_relative = Path(
                f"integrity/{scenario_id}/attempt-{index:03d}.sha256"
            )
            try:
                index_record = json.loads(_secure_read(run_root, sidecar_relative))
            except json.JSONDecodeError as exc:
                raise EvidenceError(f"attempt integrity index invalid: {name}") from exc
            if (
                index_record.get("tracked_sha256") != actual_digest
                or index_record.get("protected_anchor_sha256") != anchor_digest
            ):
                raise EvidenceError(f"attempt integrity mismatch: {name}")
            try:
                recorded = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise EvidenceError(f"attempt integrity JSON invalid: {name}") from exc
            if (
                recorded.get("attempt_id") != f"attempt-{index:03d}"
                or recorded.get("attempt_number") != index
                or recorded.get("scenario_id") != scenario_id
                or recorded.get("previous_attempt_sha256") != previous_digest
            ):
                raise EvidenceError(f"attempt integrity chain invalid: {name}")
            previous_digest = actual_digest
            previous_anchor_digest = anchor_digest
        expected = len(attempt_names) + 1
        if attempt_number != expected:
            raise EvidenceError(
                f"next attempt number must be {expected}, got {attempt_number}"
            )
        if attempt_id != expected_id:
            raise EvidenceError(f"attempt_id must be {expected_id}")
        if attempt.get("previous_attempt_sha256") != previous_digest:
            raise EvidenceError("attempt previous hash does not match integrity chain")
        redacted_attempt = redact_payload(dict(attempt))
        if not isinstance(redacted_attempt, dict):
            raise EvidenceError("redacted attempt must remain an object")
        attempt_payload = _canonical_json_bytes(redacted_attempt)
        validate_redacted_serialized(attempt_payload)
        expected_tracked_digest = hashlib.sha256(attempt_payload).hexdigest()
        anchor_relative = Path(f"anchors/{scenario_id}/{expected_id}.json")
        anchor_record = {
            "schema_version": "noor-e2e-protected-anchor/v1",
            "scenario_id": scenario_id,
            "attempt_id": expected_id,
            "tracked_relative_path": (f"attempts/{scenario_id}/{expected_id}.json"),
            "tracked_sha256": expected_tracked_digest,
            "previous_attempt_sha256": previous_digest,
            "previous_anchor_sha256": previous_anchor_digest,
        }
        anchor_payload = _canonical_json_bytes(anchor_record)
        _secure_exclusive_write(
            protected_run_root,
            anchor_relative,
            anchor_payload,
            mode=0o600,
        )
        anchor_digest = hashlib.sha256(anchor_payload).hexdigest()
        record = self.write_redacted_json(
            run_id,
            f"attempts/{scenario_id}/{expected_id}.json",
            redacted_attempt,
        )
        if record.sha256 != expected_tracked_digest:
            raise EvidenceError("tracked attempt differs from protected anchor")
        sidecar_relative = Path(f"integrity/{scenario_id}/{expected_id}.sha256")
        index_payload = _canonical_json_bytes(
            {
                "schema_version": "noor-e2e-integrity-index/v1",
                "tracked_sha256": record.sha256,
                "protected_anchor_sha256": anchor_digest,
                "protected_anchor_locator_digest": hashlib.sha256(
                    anchor_relative.as_posix().encode("utf-8")
                ).hexdigest(),
            }
        )
        _secure_exclusive_write(
            run_root,
            sidecar_relative,
            index_payload,
            mode=0o644,
        )
        return record

    def verified_attempt_payloads(self, run_id: str) -> list[dict[str, Any]]:
        """Read every tracked attempt only after protected-anchor verification."""

        run_root = self._run_root(run_id, raw=False)
        protected_run_root = self._run_root(run_id, raw=True)
        attempts_fd = _open_directory_chain(run_root, ("attempts",), create=True)
        try:
            scenario_ids = sorted(os.listdir(attempts_fd))
        finally:
            os.close(attempts_fd)
        payloads: list[dict[str, Any]] = []
        for scenario_id in scenario_ids:
            if not _RUN_ID.fullmatch(scenario_id.lower()):
                raise EvidenceError("attempt inventory contains an unsafe scenario")
            scenario_fd = _open_directory_chain(
                run_root,
                ("attempts", scenario_id),
                create=False,
            )
            try:
                names = sorted(
                    name
                    for name in os.listdir(scenario_fd)
                    if name.startswith("attempt-")
                )
            finally:
                os.close(scenario_fd)
            previous_attempt_digest: str | None = None
            previous_anchor_digest: str | None = None
            for index, name in enumerate(names, start=1):
                if name != f"attempt-{index:03d}.json":
                    raise EvidenceError("attempt integrity sequence is not contiguous")
                tracked_relative = Path("attempts") / scenario_id / name
                tracked_payload = _secure_read(run_root, tracked_relative)
                tracked_digest = hashlib.sha256(tracked_payload).hexdigest()
                anchor_relative = Path(
                    f"anchors/{scenario_id}/attempt-{index:03d}.json"
                )
                anchor_payload = _secure_read(
                    protected_run_root,
                    anchor_relative,
                )
                anchor_digest = hashlib.sha256(anchor_payload).hexdigest()
                try:
                    anchor = json.loads(anchor_payload)
                    tracked = json.loads(tracked_payload)
                except json.JSONDecodeError as exc:
                    raise EvidenceError(
                        f"protected anchor integrity JSON invalid: {name}"
                    ) from exc
                if (
                    anchor.get("tracked_sha256") != tracked_digest
                    or anchor.get("previous_anchor_sha256") != previous_anchor_digest
                    or anchor.get("previous_attempt_sha256") != previous_attempt_digest
                    or tracked.get("previous_attempt_sha256") != previous_attempt_digest
                ):
                    raise EvidenceError(f"protected anchor integrity mismatch: {name}")
                index_relative = Path(
                    f"integrity/{scenario_id}/attempt-{index:03d}.sha256"
                )
                try:
                    index_record = json.loads(_secure_read(run_root, index_relative))
                except json.JSONDecodeError as exc:
                    raise EvidenceError(
                        f"attempt integrity index invalid: {name}"
                    ) from exc
                if (
                    index_record.get("tracked_sha256") != tracked_digest
                    or index_record.get("protected_anchor_sha256") != anchor_digest
                ):
                    raise EvidenceError(f"attempt integrity mismatch: {name}")
                if not isinstance(tracked, dict):
                    raise EvidenceError(f"attempt payload is not an object: {name}")
                payloads.append(tracked)
                previous_attempt_digest = tracked_digest
                previous_anchor_digest = anchor_digest
        return payloads

    def build_retention_manifest(
        self,
        run_id: str,
        *,
        raw_records: Sequence[EvidenceRecord],
        redacted_records: Sequence[EvidenceRecord],
        owner: str,
        created_at: str,
        expires_at: str,
    ) -> dict[str, object]:
        if not owner or not created_at or not expires_at:
            raise EvidenceError("retention owner, creation, and expiry are required")
        run_root = self._run_root(run_id, raw=False)
        for record in redacted_records:
            try:
                relative = record.path.relative_to(run_root)
            except ValueError as exc:
                raise EvidenceError(
                    "redacted retention record is outside the run evidence root"
                ) from exc
            payload = _secure_read(run_root, relative)
            if hashlib.sha256(payload).hexdigest() != record.sha256:
                raise EvidenceError(
                    f"redacted retention record integrity mismatch: "
                    f"{record.relative_path}"
                )
            validate_redacted_serialized(payload)
        return {
            "schema_version": "noor-e2e-evidence-retention/v1",
            "run_id": run_id,
            "protected_locator": "[PROTECTED_OUTSIDE_GIT]",
            "protected_locator_digest": hashlib.sha256(
                str(self.protected_root).encode("utf-8")
            ).hexdigest(),
            "owner": owner,
            "access_policy": "explicit acceptance-owner authorization only",
            "created_at": created_at,
            "expires_at": expires_at,
            "raw_records": [item.public_dict() for item in raw_records],
            "redacted_records": [item.public_dict() for item in redacted_records],
            "redaction_validation": "passed",
            "backup_restore_policy": "client-review-window protected storage",
            "final_disposition": "pending_client_review_closeout",
        }


def validate_side_effect_closeout(
    entries: Sequence[Mapping[str, object]],
    *,
    observed_inventory: Mapping[str, Mapping[str, object]],
) -> None:
    """Require exact coverage and verified safe terminal state for every artifact."""

    listed_ids = [str(entry.get("artifact_id", "")) for entry in entries]
    if not all(listed_ids) or len(listed_ids) != len(set(listed_ids)):
        raise EvidenceError(
            "side-effect ledger artifact IDs must be explicit and unique"
        )
    observed_artifact_ids = set(observed_inventory)
    unlisted = observed_artifact_ids - set(listed_ids)
    missing = set(listed_ids) - observed_artifact_ids
    if unlisted:
        raise EvidenceError(f"unlisted side-effect artifacts: {sorted(unlisted)}")
    if missing:
        raise EvidenceError(
            f"missing observed side-effect artifacts: {sorted(missing)}"
        )
    for entry in entries:
        artifact_id = str(entry["artifact_id"])
        disposition = str(entry.get("disposition", ""))
        if (
            disposition in _NONTERMINAL_DISPOSITIONS
            or disposition not in _TERMINAL_DISPOSITIONS
        ):
            raise EvidenceError(
                f"nonterminal side-effect disposition for {artifact_id}: {disposition}"
            )
        if not entry.get("final_readback"):
            raise EvidenceError(f"missing final readback for {artifact_id}")
        if not entry.get("baseline_readback"):
            raise EvidenceError(f"missing baseline readback for {artifact_id}")
        if not entry.get("expected_effect"):
            raise EvidenceError(f"missing expected side effect for {artifact_id}")
        if not entry.get("cleanup_owner") or not entry.get("cleanup_authority"):
            raise EvidenceError(f"missing cleanup ownership for {artifact_id}")
        subsystem = str(entry.get("subsystem", ""))
        artifact_type = str(entry.get("artifact_type", ""))
        allowed_types = _ARTIFACT_TYPES_BY_SUBSYSTEM.get(subsystem)
        if allowed_types is None or artifact_type not in allowed_types:
            raise EvidenceError(
                f"side-effect subsystem/artifact type is invalid for {artifact_id}"
            )
        final_readback = entry["final_readback"]
        if not isinstance(final_readback, Mapping):
            raise EvidenceError(f"final readback is not typed for {artifact_id}")
        final_state = final_readback.get("state")
        if final_state not in _TERMINAL_STATE_BY_DISPOSITION[disposition]:
            raise EvidenceError(
                f"terminal invariant mismatch for {artifact_id}: "
                f"{disposition}/{final_state}"
            )
        if dict(observed_inventory[artifact_id]) != dict(final_readback):
            raise EvidenceError(f"observed inventory mismatch for {artifact_id}")
        if entry.get("follow_up_suppressed") is not True:
            raise EvidenceError(f"follow-up suppression not verified for {artifact_id}")
        if disposition == "retained_as_test_evidence" and not all(
            (
                entry.get("retention_pre_authorized") is True,
                entry.get("retention_owner"),
                entry.get("retention_expires_at"),
                entry.get("final_disposition_date"),
            )
        ):
            raise EvidenceError(f"retention metadata is incomplete for {artifact_id}")
