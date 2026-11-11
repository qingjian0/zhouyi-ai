"""Minimal Unix-domain-socket Evidence Broker prototype.

Security posture:
- The broker process creates and owns the SQLite store.
- Clients submit only strict JSON requests over a local Unix socket.
- On Linux, the server maps SO_PEERCRED UID to a server-side principal policy.
- No actor_role or learner_track supplied by the client grants authority.

This is an experimental MVP, not a complete production security boundary:
deployment must still run distinct OS identities and protect the DB directory.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import socket
import socketserver
import sqlite3
import struct
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from prototype.shared_evidence_protocol_v03 import SQLiteEvidenceStoreV03
from prototype.trusted_evidence_broker_contract import (
    BrokerContractError,
    LearnerSnapshotDTO,
)


MAX_REQUEST_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 4_194_304
PROTOCOL_VERSION = "0.1"
SO_PEERCRED = getattr(socket, "SO_PEERCRED", 17)  # Linux constant; guarded by platform check.


class BrokerIPCError(RuntimeError):
    """A broker request was denied or malformed."""


@dataclass(frozen=True)
class PrincipalPolicy:
    principal_id: str
    role: str
    learner_track: str | None = None
    allowed_episodes: frozenset[str] = frozenset()


def linux_peer_credentials(conn: socket.socket) -> tuple[int, int, int]:
    """Return (pid, uid, gid) from kernel-supplied Linux SO_PEERCRED."""
    if not hasattr(socket, "SO_PEERCRED") and not sys_platform_linux():
        raise BrokerIPCError("kernel peer credentials are unavailable on this platform")
    if not sys_platform_linux():
        raise BrokerIPCError("this broker build supports Linux SO_PEERCRED only")
    raw = conn.getsockopt(socket.SOL_SOCKET, SO_PEERCRED, struct.calcsize("3i"))
    if len(raw) != struct.calcsize("3i"):
        raise BrokerIPCError("invalid kernel peer credential response")
    return struct.unpack("3i", raw)


def sys_platform_linux() -> bool:
    return os.name == "posix" and Path("/proc/sys/kernel/ostype").exists()


class TrustedEvidenceBroker:
    """Owns the only store handle and exposes a narrow, role-scoped API."""

    def __init__(
        self,
        database_path: str | os.PathLike[str],
        *,
        principals_by_uid: Mapping[int, PrincipalPolicy],
        cursor_secret: bytes,
    ) -> None:
        if not cursor_secret or len(cursor_secret) < 32:
            raise ValueError("cursor_secret must contain at least 32 bytes")
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.database_path.parent, 0o700)
        if self.database_path.parent.stat().st_mode & 0o077:
            raise BrokerIPCError("database directory must be private to the broker service account")
        self.principals_by_uid = dict(principals_by_uid)
        self._cursor_secret = bytes(cursor_secret)
        self._lock = threading.RLock()
        # This is the sole SQLite owner in the service process.
        self._store = SQLiteEvidenceStoreV03(str(self.database_path))
        try:
            os.chmod(self.database_path, 0o600)
        except OSError as exc:
            self._store.close()
            raise BrokerIPCError("could not enforce database file permissions") from exc

    def close(self) -> None:
        with self._lock:
            self._store.close()

    def principal_for_uid(self, uid: int) -> PrincipalPolicy:
        principal = self.principals_by_uid.get(uid)
        if principal is None:
            raise BrokerIPCError("not authorized")
        return principal

    def _opaque_cursor(self, principal: PrincipalPolicy, episode_id: str, dto_payload: dict[str, Any]) -> str:
        material = json.dumps(
            {"principal": principal.principal_id, "episode": episode_id, "snapshot": dto_payload},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        return hmac.new(self._cursor_secret, material, hashlib.sha256).hexdigest()

    def dispatch(self, principal: PrincipalPolicy, request: Any) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise BrokerIPCError("request must be an object")
        if set(request) != {"protocol_version", "request_id", "operation", "payload"}:
            raise BrokerIPCError("request envelope has unknown or missing fields")
        if request["protocol_version"] != PROTOCOL_VERSION:
            raise BrokerIPCError("unsupported protocol version")
        request_id = request["request_id"]
        operation = request["operation"]
        payload = request["payload"]
        if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
            raise BrokerIPCError("invalid request_id")
        if not isinstance(operation, str) or not isinstance(payload, dict):
            raise BrokerIPCError("invalid operation or payload")

        if operation == "get_snapshot":
            if principal.role != "learner" or not principal.learner_track:
                raise BrokerIPCError("not authorized")
            if set(payload) != {"episode_id"}:
                raise BrokerIPCError("get_snapshot accepts exactly episode_id")
            episode_id = payload["episode_id"]
            if not isinstance(episode_id, str) or not episode_id.strip():
                raise BrokerIPCError("invalid episode_id")
            if principal.allowed_episodes and episode_id not in principal.allowed_episodes:
                raise BrokerIPCError("not authorized")
            with self._lock:
                projection = self._store.replay_learner_projection(episode_id, principal.learner_track)
            # The first pass uses a fixed placeholder solely to compute the DTO body.
            dto = LearnerSnapshotDTO.from_projection(projection, opaque_cursor="pending")
            body = dto.to_dict()
            cursor = self._opaque_cursor(principal, episode_id, body)
            body["cursor"] = cursor
            return {"protocol_version": PROTOCOL_VERSION, "request_id": request_id, "result": body}

        # Evaluator/policy writes are intentionally absent until separately
        # authenticated capabilities and their typed schemas are implemented.
        raise BrokerIPCError("operation is not available")


class _BrokerRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        server: "BrokerUnixServer" = self.server  # type: ignore[assignment]
        try:
            _, uid, _ = linux_peer_credentials(self.request)
            principal = server.broker.principal_for_uid(uid)
            raw = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if not raw or len(raw) > MAX_REQUEST_BYTES or not raw.endswith(b"\n"):
                raise BrokerIPCError("invalid or oversized request frame")
            try:
                request = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BrokerIPCError("invalid JSON request") from exc
            response = server.broker.dispatch(principal, request)
            encoded = json.dumps(response, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            if len(encoded) > MAX_RESPONSE_BYTES:
                raise BrokerIPCError("response exceeds size limit")
        except Exception:
            # Do not disclose whether an episode, track, or evaluator record exists.
            encoded = b'{"error":"request_denied","protocol_version":"0.1"}'
        self.wfile.write(encoded + b"\n")


class BrokerUnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, socket_path: str | os.PathLike[str], broker: TrustedEvidenceBroker):
        if not sys_platform_linux():
            raise BrokerIPCError("Unix broker server currently requires Linux")
        self.socket_path = Path(socket_path)
        self.broker = broker
        self.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        os.chmod(self.socket_path.parent, 0o750)
        if self.socket_path.exists() or self.socket_path.is_symlink():
            raise BrokerIPCError("refusing to replace an existing socket path")
        super().__init__(str(self.socket_path), _BrokerRequestHandler)
        os.chmod(self.socket_path, 0o660)

    def server_close(self) -> None:
        super().server_close()
        try:
            self.socket_path.unlink()
        except FileNotFoundError:
            pass


def request_snapshot(socket_path: str | os.PathLike[str], episode_id: str, *, timeout: float = 2.0) -> dict[str, Any]:
    request = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": "snapshot-read",
        "operation": "get_snapshot",
        "payload": {"episode_id": episode_id},
    }
    encoded = json.dumps(request, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(socket_path))
        client.sendall(encoded)
        chunks = bytearray()
        while not chunks.endswith(b"\n"):
            part = client.recv(65536)
            if not part:
                break
            chunks.extend(part)
            if len(chunks) > MAX_REQUEST_BYTES:
                raise BrokerIPCError("broker response exceeds size limit")
    try:
        response = json.loads(chunks.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrokerIPCError("invalid broker response") from exc
    if "error" in response:
        raise BrokerIPCError(response["error"])
    return response



def main() -> None:
    """Run a single-track learner broker using deployment-supplied UID and key."""
    parser = argparse.ArgumentParser(description="Trusted Evidence Broker (experimental Linux MVP)")
    parser.add_argument("--socket", required=True, help="Unix-domain socket path")
    parser.add_argument("--database", required=True, help="private SQLite database path")
    args = parser.parse_args()

    uid_raw = os.environ.get("EVIDENCE_BROKER_LEARNER_UID")
    track = os.environ.get("EVIDENCE_BROKER_LEARNER_TRACK")
    secret_hex = os.environ.get("EVIDENCE_BROKER_CURSOR_SECRET_HEX")
    if not uid_raw or not track or not secret_hex:
        raise SystemExit(
            "set EVIDENCE_BROKER_LEARNER_UID, EVIDENCE_BROKER_LEARNER_TRACK "
            "and EVIDENCE_BROKER_CURSOR_SECRET_HEX"
        )
    try:
        uid = int(uid_raw)
        secret = bytes.fromhex(secret_hex)
    except ValueError as exc:
        raise SystemExit("invalid broker UID or cursor secret encoding") from exc

    principal = PrincipalPolicy(
        principal_id=f"learner-uid-{uid}",
        role="learner",
        learner_track=track,
    )
    broker = TrustedEvidenceBroker(
        args.database,
        principals_by_uid={uid: principal},
        cursor_secret=secret,
    )
    server = BrokerUnixServer(args.socket, broker)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        broker.close()


if __name__ == "__main__":
    main()
