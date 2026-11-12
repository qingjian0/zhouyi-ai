"""Bounded Linux Unix-domain JSON RPC transport with kernel peer identity.

This module provides transport mechanics only. Service handlers must still
perform role/scope/episode authorization and must never expose generic DB APIs.
"""
from __future__ import annotations

import json
import os
import socket
import struct
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


IPC_PROTOCOL = "zhouyi-ipc/1"
_DEFAULT_MAX_FRAME_BYTES = 4 * 1024 * 1024


class IPCTransportError(RuntimeError):
    """Base transport or protocol error."""


class IPCRemoteError(IPCTransportError):
    """A remote service returned a structured error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class IPCRequestError(IPCTransportError):
    """A handler rejected a request with a safe public error."""

    def __init__(self, code: str, message: str) -> None:
        if not isinstance(code, str) or not code or len(code) > 64:
            raise ValueError("error code must be a short non-empty string")
        if not isinstance(message, str) or not message or len(message) > 256:
            raise ValueError("error message must be a short non-empty string")
        super().__init__(message)
        self.code = code
        self.public_message = message


@dataclass(frozen=True)
class UnixPeerIdentity:
    """Peer identity read from the kernel, never decoded from request JSON."""

    pid: int
    uid: int
    gid: int
    workload_id: str
    roles: frozenset[str]
    scopes: frozenset[str]

    def __post_init__(self) -> None:
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
               for value in (self.pid, self.uid, self.gid)):
            raise ValueError("peer pid/uid/gid must be non-negative integers")
        for field in ("workload_id",):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        for field in ("roles", "scopes"):
            values = getattr(self, field)
            if not isinstance(values, (set, frozenset, tuple, list)):
                raise TypeError(f"{field} must be a collection")
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError(f"{field} must contain non-empty strings")
            object.__setattr__(self, field, frozenset(values))


class UnixPeerResolver(Protocol):
    def resolve(self, *, pid: int, uid: int, gid: int) -> UnixPeerIdentity:
        """Map kernel peer credentials to a configured workload identity."""


class StaticUnixPeerResolver:
    """Exact UID/GID allowlist suitable for tests and small single-host installs."""

    def __init__(self, identities: Mapping[tuple[int, int], tuple[str, set[str] | frozenset[str], set[str] | frozenset[str]]]):
        normalized: dict[tuple[int, int], tuple[str, frozenset[str], frozenset[str]]] = {}
        for key, value in identities.items():
            if (not isinstance(key, tuple) or len(key) != 2
                    or any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in key)):
                raise ValueError("peer mapping keys must be (uid, gid) non-negative integer pairs")
            if not isinstance(value, tuple) or len(value) != 3:
                raise ValueError("peer mapping values must be (workload_id, roles, scopes)")
            workload_id, roles, scopes = value
            if not isinstance(workload_id, str) or not workload_id.strip():
                raise ValueError("workload_id must be non-empty")
            role_set, scope_set = frozenset(roles), frozenset(scopes)
            if (not role_set or any(not isinstance(x, str) or not x.strip() for x in role_set)
                    or not scope_set or any(not isinstance(x, str) or not x.strip() for x in scope_set)):
                raise ValueError("peer roles and scopes must be non-empty string sets")
            normalized[key] = (workload_id, role_set, scope_set)
        self._identities = normalized

    def resolve(self, *, pid: int, uid: int, gid: int) -> UnixPeerIdentity:
        value = self._identities.get((uid, gid))
        if value is None:
            raise IPCRequestError("peer_unauthorized", "Unix socket peer is not authorized")
        workload_id, roles, scopes = value
        return UnixPeerIdentity(pid, uid, gid, workload_id, roles, scopes)


@dataclass(frozen=True)
class IPCRequestContext:
    peer: UnixPeerIdentity
    request_id: str
    operation_id: str
    operation: str
    deadline_monotonic: float

    def remaining_seconds(self) -> float:
        remaining = self.deadline_monotonic - time.monotonic()
        if remaining <= 0:
            raise IPCRequestError("deadline_exceeded", "Request deadline exceeded")
        return remaining


Handler = Callable[[IPCRequestContext, dict[str, Any]], dict[str, Any]]


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _validate_json_shape(value: Any, *, depth: int = 0) -> None:
    if depth > 32:
        raise ValueError("JSON nesting exceeds maximum depth")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 256:
                raise ValueError("JSON object key is invalid or too long")
            _validate_json_shape(item, depth=depth + 1)
    elif isinstance(value, list):
        if len(value) > 10_000:
            raise ValueError("JSON list exceeds maximum length")
        for item in value:
            _validate_json_shape(item, depth=depth + 1)
    elif isinstance(value, str):
        if len(value) > 256 * 1024:
            raise ValueError("JSON string exceeds maximum length")
    elif value is None or isinstance(value, (bool, int, float)):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            raise ValueError("non-finite numbers are not permitted")
    else:
        raise ValueError("unsupported JSON value")


def _encode_frame(value: dict[str, Any], max_frame_bytes: int) -> bytes:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    if not raw or len(raw) > max_frame_bytes:
        raise IPCTransportError("outgoing IPC frame exceeds configured limit")
    return struct.pack("!I", len(raw)) + raw


def _recv_exact(conn: socket.socket, count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining:
        chunk = conn.recv(remaining)
        if not chunk:
            raise IPCTransportError("peer closed an incomplete IPC frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _recv_frame(conn: socket.socket, max_frame_bytes: int) -> dict[str, Any]:
    header = _recv_exact(conn, 4)
    size = struct.unpack("!I", header)[0]
    if size < 2 or size > max_frame_bytes:
        raise IPCTransportError("incoming IPC frame length is invalid")
    raw = _recv_exact(conn, size)
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )
    _validate_json_shape(value)
    if not isinstance(value, dict):
        raise IPCTransportError("IPC frame must contain a JSON object")
    return value


def _peer_credentials(conn: socket.socket) -> tuple[int, int, int]:
    if not hasattr(socket, "SO_PEERCRED"):
        raise IPCTransportError("SO_PEERCRED is unavailable on this platform")
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, gid = struct.unpack("3i", raw)
    return pid, uid, gid


class UnixJSONRPCServer:
    """One-request-per-connection Linux UDS server with bounded framing."""

    def __init__(
        self,
        socket_path: str | Path,
        *,
        peer_resolver: UnixPeerResolver,
        handlers: Mapping[str, Handler],
        socket_mode: int = 0o660,
        max_frame_bytes: int = _DEFAULT_MAX_FRAME_BYTES,
        max_deadline_ms: int = 30_000,
        max_workers: int = 32,
        io_timeout_seconds: float = 5.0,
    ) -> None:
        if not hasattr(socket, "SO_PEERCRED"):
            raise RuntimeError("UnixJSONRPCServer currently requires Linux SO_PEERCRED")
        if not callable(getattr(peer_resolver, "resolve", None)):
            raise TypeError("peer_resolver must implement resolve")
        if not handlers or any(not isinstance(k, str) or not k or not callable(v) for k, v in handlers.items()):
            raise ValueError("handlers must be a non-empty operation-to-callable mapping")
        if socket_mode & ~0o777:
            raise ValueError("socket_mode contains invalid permission bits")
        if isinstance(max_frame_bytes, bool) or not 2 <= max_frame_bytes <= 64 * 1024 * 1024:
            raise ValueError("max_frame_bytes is outside the supported range")
        if isinstance(max_deadline_ms, bool) or not 1 <= max_deadline_ms <= 300_000:
            raise ValueError("max_deadline_ms is outside the supported range")
        if isinstance(max_workers, bool) or not 1 <= max_workers <= 1024:
            raise ValueError("max_workers is outside the supported range")
        if io_timeout_seconds <= 0:
            raise ValueError("io_timeout_seconds must be positive")
        self.socket_path = Path(socket_path)
        self.peer_resolver = peer_resolver
        self.handlers = dict(handlers)
        self.socket_mode = socket_mode
        self.max_frame_bytes = max_frame_bytes
        self.max_deadline_ms = max_deadline_ms
        self.io_timeout_seconds = io_timeout_seconds
        self._workers = threading.BoundedSemaphore(max_workers)
        self._stop = threading.Event()
        self._listener: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._client_threads: set[threading.Thread] = set()
        self._threads_lock = threading.Lock()
        self._socket_inode: tuple[int, int] | None = None

    def start(self) -> None:
        if self._listener is not None:
            raise IPCTransportError("IPC server is already started")
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists() or self.socket_path.is_symlink():
            raise IPCTransportError("refusing to replace an existing IPC socket path")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self.socket_path))
            os.chmod(self.socket_path, self.socket_mode, follow_symlinks=False)
            listener.listen()
            listener.settimeout(0.2)
            stat = self.socket_path.lstat()
            self._socket_inode = (stat.st_dev, stat.st_ino)
            self._listener = listener
            self._stop.clear()
            self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._accept_thread.start()
        except Exception:
            listener.close()
            try:
                if self.socket_path.is_socket():
                    self.socket_path.unlink()
            except OSError:
                pass
            raise

    def _accept_loop(self) -> None:
        assert self._listener is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                continue
            if not self._workers.acquire(blocking=False):
                conn.close()
                continue
            thread = threading.Thread(target=self._serve_connection, args=(conn,), daemon=True)
            with self._threads_lock:
                self._client_threads.add(thread)
            thread.start()

    def _serve_connection(self, conn: socket.socket) -> None:
        request_id: str | None = None
        try:
            conn.settimeout(self.io_timeout_seconds)
            pid, uid, gid = _peer_credentials(conn)
            request = _recv_frame(conn, self.max_frame_bytes)
            expected = {"protocol", "request_id", "operation_id", "operation", "deadline_ms", "body"}
            if set(request) != expected:
                raise IPCRequestError("invalid_envelope", "IPC request envelope fields are invalid")
            if request["protocol"] != IPC_PROTOCOL:
                raise IPCRequestError("protocol_mismatch", "IPC protocol version is not supported")
            request_id = request["request_id"]
            try:
                if not isinstance(request_id, str) or str(uuid.UUID(request_id)) != request_id:
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                raise IPCRequestError("invalid_request_id", "request_id must be a canonical UUID")
            operation_id = request["operation_id"]
            if not isinstance(operation_id, str) or not operation_id.strip() or len(operation_id) > 128:
                raise IPCRequestError("invalid_operation_id", "operation_id must be a non-empty string")
            operation = request["operation"]
            if not isinstance(operation, str) or operation not in self.handlers:
                raise IPCRequestError("unknown_operation", "IPC operation is not allowlisted")
            deadline_ms = request["deadline_ms"]
            if (isinstance(deadline_ms, bool) or not isinstance(deadline_ms, int)
                    or not 1 <= deadline_ms <= self.max_deadline_ms):
                raise IPCRequestError("invalid_deadline", "deadline_ms is outside server policy")
            body = request["body"]
            if not isinstance(body, dict):
                raise IPCRequestError("invalid_body", "IPC request body must be an object")
            # Authenticate the kernel peer only after a valid request ID is
            # available, so authorization errors can be correlated safely.
            peer = self.peer_resolver.resolve(pid=pid, uid=uid, gid=gid)
            context = IPCRequestContext(
                peer=peer, request_id=request_id, operation_id=operation_id,
                operation=operation, deadline_monotonic=time.monotonic() + deadline_ms / 1000,
            )
            context.remaining_seconds()
            # Handlers must check the deadline before committing durable state.
            # Do not turn a successful post-commit response into a timeout error:
            # clients resolve an ambiguous disconnect by retrying operation_id.
            result = self.handlers[operation](context, body)
            if not isinstance(result, dict):
                raise IPCRequestError("invalid_handler_result", "IPC handler returned an invalid response")
            response = {
                "protocol": IPC_PROTOCOL, "request_id": request_id,
                "status": "ok", "body": result,
            }
        except IPCRequestError as exc:
            response = {
                "protocol": IPC_PROTOCOL, "request_id": request_id,
                "status": "error", "body": {"code": exc.code, "message": exc.public_message},
            }
        except (IPCTransportError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, OSError):
            response = {
                "protocol": IPC_PROTOCOL, "request_id": request_id,
                "status": "error", "body": {"code": "invalid_request", "message": "IPC request could not be processed"},
            }
        except Exception:
            response = {
                "protocol": IPC_PROTOCOL, "request_id": request_id,
                "status": "error", "body": {"code": "internal_error", "message": "IPC service failed"},
            }
        try:
            conn.sendall(_encode_frame(response, self.max_frame_bytes))
        except (OSError, IPCTransportError):
            pass
        finally:
            conn.close()
            self._workers.release()
            current = threading.current_thread()
            with self._threads_lock:
                self._client_threads.discard(current)

    def close(self) -> None:
        self._stop.set()
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.close()
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2)
            self._accept_thread = None
        with self._threads_lock:
            threads = tuple(self._client_threads)
        for thread in threads:
            thread.join(timeout=2)
        if self._socket_inode is not None:
            try:
                stat = self.socket_path.lstat()
                if (stat.st_dev, stat.st_ino) == self._socket_inode and self.socket_path.is_socket():
                    self.socket_path.unlink()
            except FileNotFoundError:
                pass
            self._socket_inode = None

    def __enter__(self) -> "UnixJSONRPCServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


class UnixJSONRPCClient:
    """Synchronous UDS client; the kernel supplies the server's peer identity."""

    def __init__(
        self,
        socket_path: str | Path,
        *,
        max_frame_bytes: int = _DEFAULT_MAX_FRAME_BYTES,
        connect_timeout_seconds: float = 5.0,
    ) -> None:
        if max_frame_bytes < 2:
            raise ValueError("max_frame_bytes must be at least two")
        if connect_timeout_seconds <= 0:
            raise ValueError("connect_timeout_seconds must be positive")
        self.socket_path = str(socket_path)
        self.max_frame_bytes = max_frame_bytes
        self.connect_timeout_seconds = connect_timeout_seconds

    def request(
        self,
        operation: str,
        body: dict[str, Any],
        *,
        operation_id: str,
        deadline_ms: int = 5_000,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(operation, str) or not operation:
            raise ValueError("operation must be non-empty")
        if not isinstance(body, dict):
            raise TypeError("body must be a dictionary")
        if not isinstance(operation_id, str) or not operation_id.strip() or len(operation_id) > 128:
            raise ValueError("operation_id must be a non-empty string of at most 128 characters")
        if isinstance(deadline_ms, bool) or not isinstance(deadline_ms, int) or deadline_ms < 1:
            raise ValueError("deadline_ms must be a positive integer")
        rid = request_id or str(uuid.uuid4())
        request = {
            "protocol": IPC_PROTOCOL, "request_id": rid,
            "operation_id": operation_id, "operation": operation,
            "deadline_ms": deadline_ms, "body": body,
        }
        frame = _encode_frame(request, self.max_frame_bytes)
        timeout = max(self.connect_timeout_seconds, deadline_ms / 1000 + 1)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(timeout)
            conn.connect(self.socket_path)
            conn.sendall(frame)
            response = _recv_frame(conn, self.max_frame_bytes)
        if response.get("protocol") != IPC_PROTOCOL or response.get("request_id") != rid:
            raise IPCTransportError("IPC response correlation or protocol mismatch")
        if response.get("status") == "error":
            error = response.get("body")
            if not isinstance(error, dict):
                raise IPCTransportError("IPC error response is malformed")
            raise IPCRemoteError(str(error.get("code", "remote_error")), str(error.get("message", "remote request failed")))
        if response.get("status") != "ok" or not isinstance(response.get("body"), dict):
            raise IPCTransportError("IPC success response is malformed")
        return response["body"]
