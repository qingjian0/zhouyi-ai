"""Authenticated local IPC transport for the E12-A6 single-writer service.

The transport obtains caller identity exclusively from Linux SO_PEERCRED.
Request JSON is data only; caller-supplied pid/uid/gid fields are never trusted.
"""
from __future__ import annotations

import json
import os
import socket
import stat
import struct
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class E12A6IPCError(RuntimeError):
    """The local IPC endpoint could not be safely started or used."""


@dataclass(frozen=True)
class E12A6PeerCredentials:
    pid: int
    uid: int
    gid: int


class E12A6UnixSocketServer:
    """One-request-per-connection Linux UDS server with kernel peer identity.

    The dispatcher must map peer credentials to a server-side workload
    credential and call E12A6WriterService. It must never read identity claims
    from the request object.
    """

    def __init__(
        self,
        path: str | Path,
        dispatcher: Callable[[E12A6PeerCredentials, dict[str, Any]], dict[str, Any]],
        *,
        allowed_uids: set[int] | frozenset[int],
        max_frame_bytes: int = 1_048_576,
        client_timeout: float = 5.0,
        backlog: int = 16,
        parent_mode: int = 0o700,
        socket_mode: int = 0o600,
        socket_gid: int | None = None,
    ) -> None:
        self.path = Path(path)
        if not callable(dispatcher):
            raise TypeError("dispatcher must be callable")
        if not allowed_uids or any(type(uid) is not int or uid < 0 for uid in allowed_uids):
            raise ValueError("allowed_uids must contain non-negative integer UIDs")
        if type(max_frame_bytes) is not int or not 64 <= max_frame_bytes <= 16_777_216:
            raise ValueError("max_frame_bytes must be between 64 and 16777216")
        if client_timeout <= 0 or backlog < 1:
            raise ValueError("client_timeout and backlog must be positive")
        if parent_mode not in (0o700, 0o710):
            raise ValueError("parent_mode must be 0700 or 0710")
        if socket_mode not in (0o600, 0o660):
            raise ValueError("socket_mode must be 0600 or 0660")
        if socket_mode == 0o660:
            if parent_mode != 0o710 or type(socket_gid) is not int or socket_gid < 0:
                raise ValueError("group IPC requires parent_mode=0710 and a socket_gid")
        elif socket_gid is not None:
            raise ValueError("socket_gid is only valid with socket_mode=0660")
        self._dispatcher = dispatcher
        self._allowed_uids = frozenset(allowed_uids)
        self._max_frame_bytes = max_frame_bytes
        self._client_timeout = client_timeout
        self._backlog = backlog
        self._parent_mode = parent_mode
        self._socket_mode = socket_mode
        self._socket_gid = socket_gid
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._inode: tuple[int, int] | None = None
        self._errors: list[str] = []

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(self._errors)

    def start(self) -> "E12A6UnixSocketServer":
        if os.name != "posix" or not hasattr(socket, "SO_PEERCRED"):
            raise E12A6IPCError("E12-A6 IPC requires Linux Unix sockets with SO_PEERCRED")
        if self._socket is not None:
            raise E12A6IPCError("IPC server is already started")
        parent = self.path.parent
        try:
            st = parent.lstat()
        except OSError as exc:
            raise E12A6IPCError("IPC parent directory is unavailable") from exc
        if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
            raise E12A6IPCError("IPC parent must be a real directory, not a symlink")
        if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != self._parent_mode:
            raise E12A6IPCError("IPC parent directory ownership or mode does not match policy")
        if self._socket_gid is not None and st.st_gid != self._socket_gid:
            raise E12A6IPCError("IPC parent group does not match the configured client group")
        if len(os.fsencode(str(self.path))) >= 104:
            raise E12A6IPCError("IPC socket path exceeds the Linux AF_UNIX path limit")
        try:
            existing = self.path.lstat()
        except FileNotFoundError:
            existing = None
        if existing is not None:
            raise E12A6IPCError("refusing to replace an existing IPC path")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(self.path))
            st = self.path.lstat()
            if not stat.S_ISSOCK(st.st_mode) or st.st_uid != os.geteuid():
                raise E12A6IPCError("bound IPC path failed socket ownership validation")
            self._inode = (st.st_dev, st.st_ino)
            if self._socket_gid is not None:
                os.chown(self.path, -1, self._socket_gid, follow_symlinks=False)
            os.chmod(self.path, self._socket_mode, follow_symlinks=False)
            st = self.path.lstat()
            if (not stat.S_ISSOCK(st.st_mode)
                    or (st.st_dev, st.st_ino) != self._inode
                    or stat.S_IMODE(st.st_mode) != self._socket_mode
                    or (self._socket_gid is not None and st.st_gid != self._socket_gid)):
                raise E12A6IPCError("bound IPC socket ownership or mode changed during setup")
            sock.listen(self._backlog)
            sock.settimeout(0.2)
            self._socket = sock
            self._stop.clear()
            self._thread = threading.Thread(target=self._serve, name="e12a6-uds", daemon=True)
            self._thread.start()
            return self
        except Exception:
            sock.close()
            self._remove_owned_socket()
            raise

    def _peer(self, conn: socket.socket) -> E12A6PeerCredentials:
        raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", raw)
        if pid <= 0 or uid < 0 or gid < 0:
            raise E12A6IPCError("kernel returned invalid peer credentials")
        if uid not in self._allowed_uids:
            raise E12A6IPCError("peer UID is not allowlisted")
        return E12A6PeerCredentials(pid=pid, uid=uid, gid=gid)

    def _read_frame(self, conn: socket.socket) -> dict[str, Any]:
        data = bytearray()
        while True:
            chunk = conn.recv(min(65536, self._max_frame_bytes + 1 - len(data)))
            if not chunk:
                raise E12A6IPCError("client closed before completing a frame")
            data.extend(chunk)
            if len(data) > self._max_frame_bytes:
                raise E12A6IPCError("request frame exceeds configured limit")
            newline = data.find(b"\n")
            if newline >= 0:
                if newline != len(data) - 1:
                    raise E12A6IPCError("exactly one newline-terminated request is allowed")
                raw = bytes(data[:newline])
                break
        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON object key")
                result[key] = value
            return result
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise E12A6IPCError("request must be valid UTF-8 JSON without duplicate keys") from exc
        if not isinstance(value, dict):
            raise E12A6IPCError("request root must be a JSON object")
        return value

    def _send(self, conn: socket.socket, value: dict[str, Any]) -> None:
        try:
            raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        except (TypeError, ValueError) as exc:
            raise E12A6IPCError("dispatcher returned a non-JSON response") from exc
        if len(raw) > self._max_frame_bytes:
            raise E12A6IPCError("response frame exceeds configured limit")
        conn.sendall(raw)

    def _handle(self, conn: socket.socket) -> None:
        conn.settimeout(self._client_timeout)
        try:
            peer = self._peer(conn)
            request = self._read_frame(conn)
            response = self._dispatcher(peer, request)
            if not isinstance(response, dict):
                raise E12A6IPCError("dispatcher must return a JSON object")
            self._send(conn, {"ok": True, "result": response})
        except Exception as exc:
            self._errors.append(type(exc).__name__ + ": " + str(exc))
            try:
                self._send(conn, {"ok": False, "error": "request_rejected"})
            except Exception:
                pass

    def _serve(self) -> None:
        while not self._stop.is_set():
            server = self._socket
            if server is None:
                break
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                self._errors.append("accept_failed")
                continue
            with conn:
                self._handle(conn)

    def _remove_owned_socket(self) -> None:
        if self._inode is None:
            return
        try:
            st = self.path.lstat()
            if stat.S_ISSOCK(st.st_mode) and (st.st_dev, st.st_ino) == self._inode:
                self.path.unlink()
        except FileNotFoundError:
            pass
        finally:
            self._inode = None

    def close(self) -> None:
        self._stop.set()
        server, self._socket = self._socket, None
        if server is not None:
            server.close()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=self._client_timeout + 1.0)
            if thread.is_alive():
                self._errors.append("server_thread_did_not_stop")
        self._remove_owned_socket()

    def __enter__(self) -> "E12A6UnixSocketServer":
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
