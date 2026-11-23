"""Read-only E09 verifier process boundary over authenticated Unix sockets.

The verifier consumes an immutable Authority-published SQLite snapshot. The
snapshot is owned by the Authority account, readable only by the verifier
reader group, and opened with SQLite URI mode=ro plus query_only. Writer access
is granted only to explicitly allowlisted kernel peer UIDs and scopes.
"""
from __future__ import annotations

import os
import stat
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from prototype.e09_authority_services import E09Clock, E09VerifierService
from prototype.e09_domain_registry import E09DomainRegistry
from prototype.e12a6_unix_socket import E12A6PeerCredentials, E12A6UnixSocketServer
from prototype.shared_evidence_protocol import SQLiteEvidenceStore


class E09VerifierRuntimeError(RuntimeError):
    """The E09 verifier process boundary is not safely configured."""


class E09VerifierRuntime:
    """Run E09 verification in a distinct UID with read-only event access.

    snapshot_database_path must refer to a consistent, immutable snapshot
    published by Authority. It is deliberately not the live Authority DB:
    SQLite WAL sidecars and Authority write permissions must not be shared
    with the Verifier. Snapshot freshness/anti-rollback is a deployment gate.
    """

    def __init__(
        self,
        *,
        snapshot_database_path: str | Path,
        socket_path: str | Path,
        signature_verifier: Callable[[str, str, bytes, str], bool],
        verifier_id: str,
        receipt_signer: object,
        domain_registry: E09DomainRegistry,
        uid_to_scopes: Mapping[int, frozenset[str] | set[str]],
        snapshot_gid: int,
        socket_gid: int,
        receipt_ttl: timedelta = timedelta(minutes=1),
        clock: E09Clock | None = None,
    ) -> None:
        self.snapshot_database_path = Path(snapshot_database_path)
        self.socket_path = Path(socket_path)
        if not self.snapshot_database_path.is_absolute() or not self.socket_path.is_absolute():
            raise ValueError("E09 verifier snapshot and socket paths must be absolute")
        if self.snapshot_database_path.parent == self.socket_path.parent:
            raise ValueError("E09 verifier snapshot and IPC socket need separate directories")
        if not isinstance(uid_to_scopes, Mapping) or not uid_to_scopes:
            raise ValueError("uid_to_scopes must be a non-empty server-side UID policy")
        normalized: dict[int, frozenset[str]] = {}
        for uid, scopes in uid_to_scopes.items():
            if type(uid) is not int or uid < 0:
                raise ValueError("UID map keys must be non-negative integers")
            if not isinstance(scopes, (set, frozenset)) or not scopes:
                raise ValueError("each verifier client must have a non-empty scope allowlist")
            if any(not isinstance(scope, str) or not scope.strip() for scope in scopes):
                raise ValueError("scope allowlists must contain non-empty strings")
            normalized[uid] = frozenset(scopes)
        if type(snapshot_gid) is not int or snapshot_gid < 0:
            raise ValueError("snapshot_gid must be a non-negative integer")
        if type(socket_gid) is not int or socket_gid < 0:
            raise ValueError("socket_gid must be a non-negative integer")
        if os.geteuid() in normalized:
            raise E09VerifierRuntimeError("verifier clients must use UIDs distinct from the verifier")
        if snapshot_gid not in set(os.getgroups()) | {os.getegid()}:
            raise E09VerifierRuntimeError("verifier process is not a member of the snapshot reader group")
        self._uid_to_scopes = normalized
        self._snapshot_gid = snapshot_gid
        self._socket_gid = socket_gid
        self._signature_verifier = signature_verifier
        self._verifier_id = verifier_id
        self._receipt_signer = receipt_signer
        self._domain_registry = domain_registry
        self._receipt_ttl = receipt_ttl
        self._clock = clock
        self._store: SQLiteEvidenceStore | None = None
        self._verifier: E09VerifierService | None = None
        self._server: E12A6UnixSocketServer | None = None

    def _check_snapshot_permissions(self) -> None:
        parent = self.snapshot_database_path.parent
        try:
            directory = parent.lstat()
            database = self.snapshot_database_path.lstat()
        except OSError as exc:
            raise E09VerifierRuntimeError("Authority snapshot is unavailable") from exc
        if (not stat.S_ISDIR(directory.st_mode) or stat.S_ISLNK(directory.st_mode)
                or stat.S_IMODE(directory.st_mode) != 0o750
                or directory.st_gid != self._snapshot_gid):
            raise E09VerifierRuntimeError("snapshot directory must be group-owned mode 0750")
        if (not stat.S_ISREG(database.st_mode) or stat.S_ISLNK(database.st_mode)
                or stat.S_IMODE(database.st_mode) != 0o440
                or database.st_gid != self._snapshot_gid):
            raise E09VerifierRuntimeError("snapshot database must be group-readable mode 0440")
        if directory.st_uid == os.geteuid() or database.st_uid == os.geteuid():
            raise E09VerifierRuntimeError("Authority snapshot must not be owned by the Verifier UID")
        if directory.st_uid != database.st_uid:
            raise E09VerifierRuntimeError("snapshot directory and database must share the Authority owner")

    def _open_read_only_store(self) -> SQLiteEvidenceStore:
        self._check_snapshot_permissions()
        return SQLiteEvidenceStore.open_read_only(self.snapshot_database_path)

    @staticmethod
    def _validate_request(request: dict[str, Any]) -> dict[str, Any]:
        required = {
            "operation", "episode_id", "authorization_ref", "parent_state_ref",
            "branch_ids", "scope", "learner_track",
        }
        optional = {"candidate_evidence_refs"}
        if not isinstance(request, dict) or not required.issubset(request):
            raise E09VerifierRuntimeError("verifier request is missing required fields")
        if set(request) - required - optional:
            raise E09VerifierRuntimeError("verifier request contains unknown fields")
        if request.get("operation") != "issue_verification_receipt@1":
            raise E09VerifierRuntimeError("unsupported E09 verifier operation")
        return {key: value for key, value in request.items() if key != "operation"}

    def _dispatch(self, peer: E12A6PeerCredentials, request: dict[str, Any]) -> dict[str, Any]:
        scopes = self._uid_to_scopes.get(peer.uid)
        if scopes is None:
            raise E09VerifierRuntimeError("peer UID has no verifier workload binding")
        payload = self._validate_request(request)
        scope = payload.get("scope")
        if not isinstance(scope, str) or scope not in scopes:
            raise E09VerifierRuntimeError("peer UID is not authorized for the requested E09 scope")
        if self._verifier is None:
            raise E09VerifierRuntimeError("E09 verifier is not started")
        receipt = self._verifier.issue_verification_receipt(**payload)
        if not isinstance(receipt, dict) or receipt.get("schema_version") != "e09_verification_receipt@2":
            raise E09VerifierRuntimeError("verifier returned an invalid receipt")
        return {"receipt": receipt}

    def start(self) -> "E09VerifierRuntime":
        if self._server is not None:
            raise E09VerifierRuntimeError("E09 verifier runtime is already started")
        self._check_snapshot_permissions()
        socket_parent = self.socket_path.parent
        try:
            socket_info = socket_parent.lstat()
        except OSError as exc:
            raise E09VerifierRuntimeError("verifier socket directory is unavailable") from exc
        if (not stat.S_ISDIR(socket_info.st_mode) or stat.S_ISLNK(socket_info.st_mode)
                or socket_info.st_uid != os.geteuid()
                or stat.S_IMODE(socket_info.st_mode) != 0o710):
            raise E09VerifierRuntimeError("verifier socket directory must be verifier-owned mode 0710")
        try:
            self._store = self._open_read_only_store()
            self._verifier = E09VerifierService(
                self._store,
                signature_verifier=self._signature_verifier,
                verifier_id=self._verifier_id,
                receipt_signer=self._receipt_signer,
                receipt_ttl=self._receipt_ttl,
                domain_registry=self._domain_registry,
                clock=self._clock,
            )
            self._server = E12A6UnixSocketServer(
                self.socket_path, self._dispatch,
                allowed_uids=frozenset(self._uid_to_scopes),
                parent_mode=0o710, socket_mode=0o660, socket_gid=self._socket_gid,
            ).start()
            return self
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._store is not None:
            self._store.close()
            self._store = None
        self._verifier = None

    def __enter__(self) -> "E09VerifierRuntime":
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
