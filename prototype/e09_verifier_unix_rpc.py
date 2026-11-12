"""Authenticated E09 Verifier RPC and durable receipt idempotency ledger."""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from prototype.e09_authority_services import E09AuthenticationError, E09AuthorizationError
from prototype.e09_e12a6_evidence_bridge import E09EvidenceBindingError
from prototype.shared_evidence_protocol import canonical_json, digest_payload
from prototype.unix_ipc import (
    IPCRequestContext,
    IPCRequestError,
    UnixJSONRPCServer,
    UnixPeerResolver,
)


class VerifierReceiptIdempotencyConflict(RuntimeError):
    """An RPC operation ID was reused for a different receipt request."""


class SQLiteVerifierReceiptLedger:
    """Durable, verifier-owned receipt retry cache, separate from the E09 event DB."""

    def __init__(self, path: str | Path):
        candidate = Path(path)
        try:
            parent = candidate.parent.resolve(strict=True)
            parent_stat = parent.stat()
        except OSError as exc:
            raise ValueError("verifier receipt ledger parent directory must exist") from exc
        if not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_mode & 0o022:
            raise ValueError("verifier receipt ledger directory must not be group/world writable")
        self.path = parent / candidate.name
        if self.path.is_symlink():
            raise ValueError("verifier receipt ledger must not be a symlink")
        if self.path.exists():
            file_stat = self.path.stat()
            if (
                not stat.S_ISREG(file_stat.st_mode)
                or file_stat.st_mode & 0o077
                or file_stat.st_uid != os.geteuid()
            ):
                raise ValueError("existing verifier receipt ledger must be owned by this service and private")
        else:
            descriptor = os.open(
                self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600
            )
            os.close(descriptor)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(
            self.path, isolation_level=None, check_same_thread=False
        )
        self._db.execute("PRAGMA journal_mode=DELETE")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS issued_receipts (
                operation_id TEXT PRIMARY KEY,
                request_digest TEXT NOT NULL,
                receipt_id TEXT NOT NULL UNIQUE,
                nonce TEXT NOT NULL UNIQUE,
                receipt_json TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        # Upgrade the pre-reservation schema without losing already issued receipts.
        receipt_columns = {
            row[1]: row for row in self._db.execute("PRAGMA table_info(issued_receipts)")
        }
        if receipt_columns["receipt_json"][3]:
            self._db.executescript(
                """
                BEGIN IMMEDIATE;
                ALTER TABLE issued_receipts RENAME TO issued_receipts_legacy;
                CREATE TABLE issued_receipts (
                    operation_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    receipt_id TEXT NOT NULL UNIQUE,
                    nonce TEXT NOT NULL UNIQUE,
                    receipt_json TEXT,
                    created_at TEXT NOT NULL
                );
                INSERT INTO issued_receipts
                    (operation_id, request_digest, receipt_id, nonce, receipt_json, created_at)
                SELECT operation_id, request_digest, receipt_id, nonce, receipt_json, created_at
                FROM issued_receipts_legacy;
                DROP TABLE issued_receipts_legacy;
                COMMIT;
                """
            )

    def issue_once(
        self,
        operation_id: str,
        request: Mapping[str, Any],
        issuer: Callable[[Mapping[str, str]], dict[str, Any]],
    ) -> dict[str, Any]:
        if not isinstance(operation_id, str) or not operation_id.strip() or len(operation_id) > 128:
            raise ValueError("operation_id must be a non-empty string of at most 128 characters")
        if not isinstance(request, Mapping):
            raise TypeError("receipt request must be a mapping")
        if not callable(issuer):
            raise TypeError("issuer must be callable")
        request_value = dict(request)
        request_digest = digest_payload(request_value)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT request_digest, receipt_id, nonce, receipt_json, created_at "
                    "FROM issued_receipts WHERE operation_id=?",
                    (operation_id,),
                ).fetchone()
                if row is not None:
                    if row[0] != request_digest:
                        raise VerifierReceiptIdempotencyConflict(
                            "operation_id was already used for a different receipt request"
                        )
                    if row[3] is not None:
                        self._db.execute("COMMIT")
                        return json.loads(row[3])
                    identity = {
                        "receipt_id": row[1], "nonce": row[2], "issued_at": row[4],
                    }
                else:
                    import secrets
                    identity = {
                        "receipt_id": secrets.token_hex(16),
                        "nonce": secrets.token_urlsafe(32),
                        "issued_at": datetime.now(timezone.utc).isoformat(),
                    }
                    self._db.execute(
                        "INSERT INTO issued_receipts"
                        "(operation_id,request_digest,receipt_id,nonce,receipt_json,created_at) "
                        "VALUES(?,?,?,?,NULL,?)",
                        (
                            operation_id, request_digest, identity["receipt_id"],
                            identity["nonce"], identity["issued_at"],
                        ),
                    )
                # Commit the stable receipt identity before calling the verifier.
                self._db.execute("COMMIT")
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise
            receipt = issuer(identity)
            if not isinstance(receipt, dict):
                raise TypeError("verifier must return a receipt object")
            if receipt.get("receipt_id") != identity["receipt_id"] or receipt.get("nonce") != identity["nonce"]:
                raise ValueError("verifier receipt identity does not match durable reservation")
            receipt_json = canonical_json(receipt)
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT request_digest, receipt_id, nonce, receipt_json "
                    "FROM issued_receipts WHERE operation_id=?",
                    (operation_id,),
                ).fetchone()
                if row is None or row[0] != request_digest or row[1] != identity["receipt_id"] or row[2] != identity["nonce"]:
                    raise VerifierReceiptIdempotencyConflict("durable receipt reservation changed")
                if row[3] is not None and row[3] != receipt_json:
                    raise VerifierReceiptIdempotencyConflict("receipt retry produced a different signed payload")
                if row[3] is None:
                    self._db.execute(
                        "UPDATE issued_receipts SET receipt_json=? WHERE operation_id=?",
                        (receipt_json, operation_id),
                    )
                self._db.execute("COMMIT")
                return json.loads(row[3] or receipt_json)
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._db.close()


def _fields(body: dict[str, Any], required: set[str], optional: set[str] = frozenset()) -> None:
    if not isinstance(body, dict) or required - set(body) or set(body) - required - optional:
        raise IPCRequestError("invalid_body", "Receipt request fields do not match schema")


def _text_fields(body: dict[str, Any], *names: str) -> None:
    for name in names:
        value = body.get(name)
        if not isinstance(value, str) or not value.strip():
            raise IPCRequestError("invalid_body", f"{name} must be a non-empty string")


def _string_array(body: dict[str, Any], name: str, *, required: bool = True) -> None:
    if name not in body and not required:
        return
    values = body.get(name)
    if not isinstance(values, list) or not values:
        raise IPCRequestError("invalid_body", f"{name} must be a non-empty JSON array")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise IPCRequestError("invalid_body", f"{name} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise IPCRequestError("invalid_body", f"{name} must not contain duplicates")


def _string_mapping(body: dict[str, Any], name: str) -> None:
    if name not in body:
        return
    value = body[name]
    if not isinstance(value, dict) or any(
        not isinstance(key, str) or not key.strip()
        or not isinstance(item, str) or not item.strip()
        for key, item in value.items()
    ):
        raise IPCRequestError("invalid_body", f"{name} must map non-empty strings to non-empty strings")


class E09VerifierUnixRPC:
    """Expose receipt issuance only to the explicitly provisioned E12-A6 Writer."""

    def __init__(
        self,
        verifier: Any,
        *,
        peer_resolver: UnixPeerResolver,
        socket_path: str,
        receipt_ledger: SQLiteVerifierReceiptLedger,
        allowed_writer_workload_ids: set[str] | frozenset[str],
        socket_mode: int = 0o660,
    ) -> None:
        if not callable(getattr(verifier, "issue_verification_receipt_with_identity", None)):
            raise TypeError("verifier must implement issue_verification_receipt_with_identity")
        if not isinstance(receipt_ledger, SQLiteVerifierReceiptLedger):
            raise TypeError("receipt_ledger must be SQLiteVerifierReceiptLedger")
        if isinstance(allowed_writer_workload_ids, str):
            raise ValueError("allowed_writer_workload_ids must be a collection, not a string")
        writers = frozenset(allowed_writer_workload_ids)
        if not writers or any(not isinstance(value, str) or not value.strip() for value in writers):
            raise ValueError("allowed_writer_workload_ids must be non-empty strings")
        self.verifier = verifier
        self.receipt_ledger = receipt_ledger
        self.allowed_writer_workload_ids = writers
        self.server = UnixJSONRPCServer(
            socket_path,
            peer_resolver=peer_resolver,
            handlers={
                "health": self._health,
                "receipt.issue": self._issue_receipt,
            },
            socket_mode=socket_mode,
        )

    def _authorize_writer(self, context: IPCRequestContext, scope: str) -> None:
        peer = context.peer
        if (
            "e12a6-writer" not in peer.roles
            or peer.workload_id not in self.allowed_writer_workload_ids
            or scope not in peer.scopes
        ):
            raise IPCRequestError("permission_denied", "Peer is not an authorized E12-A6 Writer")

    def _health(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(body, required=set())
        if (
            "e12a6-writer" not in context.peer.roles
            or context.peer.workload_id not in self.allowed_writer_workload_ids
        ):
            raise IPCRequestError("permission_denied", "Peer is not an authorized E12-A6 Writer")
        return {"service": "e09-verifier", "protocol": "zhouyi-ipc/1", "ready": True}

    def _issue_receipt(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        required = {
            "episode_id", "authorization_ref", "parent_state_ref",
            "branch_ids", "scope", "learner_track",
        }
        optional = {
            "candidate_evidence_refs", "world_family_by_evidence",
            "candidate_evidence_world_family_by_ref",
        }
        _fields(body, required=required, optional=optional)
        _text_fields(
            body, "episode_id", "authorization_ref", "parent_state_ref", "scope", "learner_track"
        )
        _string_array(body, "branch_ids")
        _string_array(body, "candidate_evidence_refs", required=False)
        _string_mapping(body, "world_family_by_evidence")
        _string_mapping(body, "candidate_evidence_world_family_by_ref")
        self._authorize_writer(context, body["scope"])
        request = dict(body)
        ledger_request = {
            "authenticated_workload_id": context.peer.workload_id,
            "request": request,
        }
        try:
            return self.receipt_ledger.issue_once(
                context.operation_id,
                ledger_request,
                lambda identity: self.verifier.issue_verification_receipt_with_identity(
                    **request,
                    _receipt_id=identity["receipt_id"],
                    _nonce=identity["nonce"],
                    _issued_at=identity["issued_at"],
                ),
            )
        except VerifierReceiptIdempotencyConflict as exc:
            raise IPCRequestError("idempotency_conflict", "Operation ID was reused for a different receipt request") from exc
        except (E09AuthenticationError, E09AuthorizationError, E09EvidenceBindingError) as exc:
            raise IPCRequestError("verification_rejected", "E09 evidence verification rejected the receipt request") from exc
        except (TypeError, ValueError) as exc:
            raise IPCRequestError("invalid_request", "Receipt request failed validation") from exc

    def start(self) -> None:
        self.server.start()

    def close(self) -> None:
        self.server.close()

    def __enter__(self) -> "E09VerifierUnixRPC":
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
