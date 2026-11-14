"""Process boundary for the E09 authority and its private SQLite store.

The database directory is service-only (0700/0600). Clients receive access
only through a group-scoped Unix socket (0710/0660); kernel SO_PEERCRED maps
UIDs to server-side workload credentials. The request cannot choose its role,
credential, domain, or identity metadata.
"""
from __future__ import annotations

import os
import stat
from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping

from prototype.e09_authority_services import E09AuthorityService
from prototype.e09_domain_registry import E09DomainRegistry
from prototype.e12a6_unix_socket import E12A6PeerCredentials, E12A6UnixSocketServer
from prototype.shared_evidence_protocol import SQLiteEvidenceStore


class E09AuthorityRuntimeError(RuntimeError):
    """The E09 authority process boundary is not safely configured."""


class E09AuthorityRuntime:
    def __init__(
        self,
        *,
        database_path: str | Path,
        socket_path: str | Path,
        authenticator: object,
        signer: object,
        domain_registry: E09DomainRegistry,
        uid_to_credential: Mapping[int, object],
        socket_gid: int,
        test_only_allow_same_uid: bool = False,
    ) -> None:
        self.database_path = Path(database_path)
        self.socket_path = Path(socket_path)
        if not self.database_path.is_absolute() or not self.socket_path.is_absolute():
            raise ValueError("E09 database and socket paths must be absolute")
        if self.database_path.parent == self.socket_path.parent:
            raise ValueError("E09 database and IPC socket must use separate directories")
        if not isinstance(uid_to_credential, Mapping) or not uid_to_credential:
            raise ValueError("uid_to_credential must be a non-empty server-side mapping")
        if any(type(uid) is not int or uid < 0 for uid in uid_to_credential):
            raise ValueError("UID map keys must be non-negative integers")
        if type(socket_gid) is not int or socket_gid < 0:
            raise ValueError("socket_gid must be a non-negative integer")
        if type(test_only_allow_same_uid) is not bool:
            raise TypeError("test_only_allow_same_uid must be bool")
        if os.geteuid() in uid_to_credential and not test_only_allow_same_uid:
            raise E09AuthorityRuntimeError(
                "client UIDs must be distinct from the E09 database owner UID"
            )
        self._uid_to_credential = dict(uid_to_credential)
        self._socket_gid = socket_gid
        self._authenticator = authenticator
        self._signer = signer
        self._domain_registry = domain_registry
        self._store: SQLiteEvidenceStore | None = None
        self._authority: E09AuthorityService | None = None
        self._server: E12A6UnixSocketServer | None = None

    @staticmethod
    def _require_private_directory(path: Path) -> None:
        try:
            info = path.lstat()
        except OSError as exc:
            raise E09AuthorityRuntimeError("E09 database directory is unavailable") from exc
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise E09AuthorityRuntimeError("E09 database directory must be service-owned mode 0700")

    def _prepare_database_file(self) -> None:
        self._require_private_directory(self.database_path.parent)
        if self.database_path.is_symlink():
            raise E09AuthorityRuntimeError("refusing a symlink E09 database path")
        try:
            info = self.database_path.lstat()
        except FileNotFoundError:
            fd = os.open(self.database_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(fd)
            info = self.database_path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise E09AuthorityRuntimeError("E09 database file must be service-owned mode 0600")

    @staticmethod
    def _receipt_dict(receipt: Any) -> dict[str, Any]:
        return {
            "episode_id": receipt.episode_id,
            "event_id": receipt.event_id,
            "sequence_no": receipt.sequence_no,
            "payload_digest": receipt.payload_digest,
            "replayed": receipt.replayed,
        }

    def _dispatch(self, peer: E12A6PeerCredentials, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise E09AuthorityRuntimeError("request must be an object")
        credential = self._uid_to_credential.get(peer.uid)
        if credential is None:
            raise E09AuthorityRuntimeError("peer UID has no E09 workload binding")
        if self._authority is None:
            raise E09AuthorityRuntimeError("E09 authority is not started")
        operation = request.get("operation")
        if operation in ("append_observation", "append_prediction_commit", "append_evidence_reveal"):
            common = {"operation", "episode_id", "event_id", "idempotency_key", "payload"}
            expected = common | ({"expected_sequence"} if "expected_sequence" in request else set())
            if operation != "append_observation":
                expected |= {"causation_refs"}
            if set(request) != expected:
                raise E09AuthorityRuntimeError("E09 event request has unknown or missing fields")
            kwargs = {
                "episode_id": request["episode_id"],
                "event_id": request["event_id"],
                "idempotency_key": request["idempotency_key"],
                "payload": request["payload"],
                "expected_sequence": request.get("expected_sequence"),
            }
            if operation == "append_observation":
                receipt = self._authority.append_observation(credential, **kwargs)
            elif operation == "append_prediction_commit":
                receipt = self._authority.append_prediction_commit(
                    credential, causation_refs=request["causation_refs"], **kwargs,
                )
            else:
                receipt = self._authority.append_evidence_reveal(
                    credential, causation_refs=request["causation_refs"], **kwargs,
                )
            return self._receipt_dict(receipt)

        if operation == "issue_branch_merge_authorization":
            required = {
                "operation", "episode_id", "scope", "parent_state_ref",
                "branch_ids", "evidence_refs",
            }
            optional = {"ttl_seconds", "authorization_id"}
            if not required.issubset(request) or set(request) - required - optional:
                raise E09AuthorityRuntimeError("branch authorization request schema is invalid")
            ttl_seconds = request.get("ttl_seconds", 120)
            if type(ttl_seconds) not in (int, float) or ttl_seconds <= 0:
                raise E09AuthorityRuntimeError("ttl_seconds must be positive")
            receipt = self._authority.issue_branch_merge_authorization(
                credential,
                episode_id=request["episode_id"],
                scope=request["scope"],
                parent_state_ref=request["parent_state_ref"],
                branch_ids=request["branch_ids"],
                evidence_refs=request["evidence_refs"],
                ttl=timedelta(seconds=ttl_seconds),
                authorization_id=request.get("authorization_id"),
            )
            return self._receipt_dict(receipt)

        raise E09AuthorityRuntimeError("unsupported E09 authority operation")

    def start(self) -> "E09AuthorityRuntime":
        if self._server is not None:
            raise E09AuthorityRuntimeError("E09 authority runtime is already started")
        self._prepare_database_file()
        try:
            previous_umask = os.umask(0o077)
            try:
                self._store = SQLiteEvidenceStore(self.database_path)
            finally:
                os.umask(previous_umask)
            os.chmod(self.database_path, 0o600, follow_symlinks=False)
            info = self.database_path.lstat()
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise E09AuthorityRuntimeError("E09 database permissions changed during open")
            self._authority = E09AuthorityService(
                self._store, authenticator=self._authenticator,
                signer=self._signer, domain_registry=self._domain_registry,
            )
            self._server = E12A6UnixSocketServer(
                self.socket_path, self._dispatch,
                allowed_uids=frozenset(self._uid_to_credential),
                parent_mode=0o710, socket_mode=0o660, socket_gid=self._socket_gid,
            ).start()
            return self
        except Exception:
            if self._server is not None:
                self._server.close()
                self._server = None
            if self._store is not None:
                self._store.close()
                self._store = None
            raise

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._store is not None:
            self._store.close()
            self._store = None
        self._authority = None

    def __enter__(self) -> "E09AuthorityRuntime":
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
