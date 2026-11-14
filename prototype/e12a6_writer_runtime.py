"""Fail-closed POSIX single-writer runtime for the E12-A6 lifecycle database.

Acquire the process lock before opening SQLite. Keep the runtime alive for the
entire lifetime of the writer service; never unlink the lock file on release.
"""
from __future__ import annotations

import fcntl
import os
import stat
from pathlib import Path
from typing import Callable

from prototype.e09_authority_services import E09Clock
from prototype.e12a6_writer_service import (
    E12A6WorkloadAuthenticator,
    E12A6WriterService,
)
from prototype.e12a6_zpcm_persistence import PersistentLifecycleLedger
from prototype.zpcm_memory import ZPCMMemory


class E12A6WriterRuntimeError(RuntimeError):
    """The dedicated E12-A6 writer runtime cannot safely acquire its state."""


class E12A6WriterAlreadyRunning(E12A6WriterRuntimeError):
    """Another process already owns the writer lock for this state directory."""


class E12A6WriterProcessLock:
    """Advisory exclusive process lock stored in a private state directory."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._fd: int | None = None

    def acquire(self) -> "E12A6WriterProcessLock":
        if self._fd is not None:
            raise E12A6WriterRuntimeError("writer lock is already acquired by this object")
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
            raise E12A6WriterRuntimeError("E12-A6 process locking requires POSIX O_NOFOLLOW and flock")
        parent = self.path.parent
        try:
            parent_stat = parent.stat()
        except OSError as exc:
            raise E12A6WriterRuntimeError("writer state directory is unavailable") from exc
        if not stat.S_ISDIR(parent_stat.st_mode):
            raise E12A6WriterRuntimeError("writer state parent must be a directory")
        if parent_stat.st_uid != os.geteuid() or parent_stat.st_mode & 0o077:
            raise E12A6WriterRuntimeError(
                "writer state directory must be owned by the service user and mode 0700"
            )
        flags = os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            fd = os.open(self.path, flags, 0o600)
            file_stat = os.fstat(fd)
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != os.geteuid():
                raise E12A6WriterRuntimeError("writer lock must be a regular file owned by the service user")
            os.fchmod(fd, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise E12A6WriterAlreadyRunning("another E12-A6 writer owns this state directory") from exc
            os.ftruncate(fd, 0)
            os.write(fd, f"pid={os.getpid()}\\n".encode("ascii"))
            os.fsync(fd)
            self._fd = fd
            return self
        except E12A6WriterRuntimeError:
            os.close(fd) if "fd" in locals() else None
            raise
        except OSError as exc:
            os.close(fd) if "fd" in locals() else None
            raise E12A6WriterRuntimeError("could not acquire E12-A6 writer process lock") from exc

    @property
    def acquired(self) -> bool:
        return self._fd is not None

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def __enter__(self) -> "E12A6WriterProcessLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


class E12A6WriterRuntime:
    """Own the exclusive process lock, private SQLite store and writer service.

    Construct this in a dedicated OS service process. The state directory must
    already exist, be owned by the service account and have mode 0700. Acquire
    the lock before SQLite is opened, and retain it until close().
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        authenticator: E12A6WorkloadAuthenticator,
        receipt_signature_verifier: Callable[[str, str, bytes, str], bool],
        trusted_verifier_id: str,
        scope: str,
        clock: E09Clock | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self._lock = E12A6WriterProcessLock(
            self.database_path.with_name(self.database_path.name + ".writer.lock")
        )
        self._memory: ZPCMMemory | None = None
        self.ledger: PersistentLifecycleLedger | None = None
        self.service: E12A6WriterService | None = None
        self._lock.acquire()
        try:
            if self.database_path.is_symlink():
                raise E12A6WriterRuntimeError("writer database must not be a symbolic link")
            if self.database_path.exists() and not self.database_path.is_file():
                raise E12A6WriterRuntimeError("writer database path must be a regular file")
            self._memory = ZPCMMemory(self.database_path)
            os.chmod(self.database_path, 0o600)
            self.ledger = PersistentLifecycleLedger(self._memory, scope=scope)
            self.service = E12A6WriterService(
                self.ledger,
                authenticator=authenticator,
                receipt_signature_verifier=receipt_signature_verifier,
                trusted_verifier_id=trusted_verifier_id,
                clock=clock,
            )
        except Exception:
            if self._memory is not None:
                self._memory.close()
            self._lock.release()
            raise

    def close(self) -> None:
        memory, self._memory = self._memory, None
        self.service = None
        self.ledger = None
        try:
            if memory is not None:
                memory.close()
        finally:
            self._lock.release()

    def __enter__(self) -> "E12A6WriterRuntime":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
