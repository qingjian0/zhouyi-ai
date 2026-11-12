"""Atomic, verifier-owned SQLite snapshots for the E09 evidence database.

The publisher uses SQLite's online backup API, not a byte copy of a live
main/WAL pair. It publishes a standalone rollback-journal database by fsync +
atomic rename. Linux flock serializes publishers so an older snapshot cannot
finish after and overwrite a newer publication.
"""
from __future__ import annotations

import fcntl
import os
import sqlite3
import stat
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class SnapshotPublicationError(RuntimeError):
    """A consistent private snapshot could not be safely published."""


@dataclass(frozen=True)
class SnapshotPublication:
    path: str
    published_at: str
    event_count: int
    episode_count: int
    byte_size: int
    journal_mode: str


class SQLiteEvidenceSnapshotPublisher:
    """Publish read-only verifier snapshots from a live Authority database.

    The destination directory must already exist and must not be group/world
    writable. The resulting file is mode 0600. Source DB and its SQLite sidecars
    must be readable by the publisher; callers must not use immutable=1 because
    that would bypass WAL visibility.
    """

    REQUIRED_TABLES = frozenset({"events", "idempotency", "payload_vault"})

    def __init__(self, source_path: str | Path, destination_path: str | Path):
        source_input = Path(source_path)
        destination_input = Path(destination_path)
        if source_input.is_symlink():
            raise SnapshotPublicationError("source database must not be a symlink")
        if destination_input.is_symlink():
            raise SnapshotPublicationError("snapshot destination must not be a symlink")
        try:
            self.source = source_input.resolve(strict=True)
            self.destination = destination_input.parent.resolve(strict=True) / destination_input.name
        except OSError as exc:
            raise SnapshotPublicationError("source and destination directory must exist") from exc
        if not self.source.is_file():
            raise SnapshotPublicationError("source database must be a regular file")
        if not self.destination.parent.is_dir():
            raise SnapshotPublicationError("snapshot parent must be a directory")
        try:
            if self.destination.exists() and os.path.samefile(self.source, self.destination):
                raise SnapshotPublicationError("source and snapshot destination must differ")
        except OSError as exc:
            raise SnapshotPublicationError("unable to inspect snapshot destination") from exc
        parent_mode = stat.S_IMODE(self.destination.parent.stat().st_mode)
        if parent_mode & 0o022:
            raise SnapshotPublicationError("snapshot directory must not be group/world writable")
        if self.destination.exists() and not self.destination.is_file():
            raise SnapshotPublicationError("existing snapshot destination must be a regular file")
        self._thread_lock = threading.Lock()

    def publish(self) -> SnapshotPublication:
        """Create and atomically publish one consistent SQLite backup."""
        with self._thread_lock:
            lock_path = self.destination.with_name(self.destination.name + ".lock")
            lock_fd = self._open_lock_file(lock_path)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                return self._publish_locked()
            finally:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(lock_fd)

    @staticmethod
    def _open_lock_file(path: Path) -> int:
        flags = os.O_CREAT | os.O_RDWR
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                os.close(fd)
                raise SnapshotPublicationError("snapshot lock must be a regular file")
            os.fchmod(fd, 0o600)
            return fd
        except OSError as exc:
            raise SnapshotPublicationError("unable to open private snapshot lock") from exc

    def _publish_locked(self) -> SnapshotPublication:
        # A leftover WAL/SHM beside the destination could be replayed against a
        # newly replaced main file. Refuse rather than guessing whether it is stale.
        for suffix in ("-wal", "-shm"):
            if Path(str(self.destination) + suffix).exists():
                raise SnapshotPublicationError(f"refusing destination with existing SQLite {suffix} sidecar")

        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.destination.name}.", suffix=".snapshot-tmp",
            dir=self.destination.parent,
        )
        os.fchmod(fd, 0o600)
        os.close(fd)
        temporary = Path(temporary_name)
        source_db: sqlite3.Connection | None = None
        snapshot_db: sqlite3.Connection | None = None
        try:
            source_uri = self.source.as_uri() + "?mode=ro"
            source_db = sqlite3.connect(source_uri, uri=True, timeout=10.0)
            source_db.execute("PRAGMA query_only=ON")
            source_db.execute("PRAGMA busy_timeout=10000")
            snapshot_db = sqlite3.connect(str(temporary), timeout=10.0)
            snapshot_db.execute("PRAGMA busy_timeout=10000")
            source_db.backup(snapshot_db, pages=256, sleep=0.05)

            journal_row = snapshot_db.execute("PRAGMA journal_mode=DELETE").fetchone()
            journal_mode = str(journal_row[0]).upper()
            if journal_mode != "DELETE":
                raise SnapshotPublicationError("snapshot must use standalone DELETE journal mode")
            integrity = snapshot_db.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise SnapshotPublicationError("snapshot integrity_check failed")

            tables = {
                row[0] for row in snapshot_db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            missing = self.REQUIRED_TABLES - tables
            if missing:
                raise SnapshotPublicationError(
                    f"source database is missing required tables: {', '.join(sorted(missing))}"
                )
            event_count, episode_count = snapshot_db.execute(
                "SELECT COUNT(*), COUNT(DISTINCT episode_id) FROM events"
            ).fetchone()
            snapshot_db.execute("PRAGMA optimize")
            snapshot_db.close()
            snapshot_db = None
            source_db.close()
            source_db = None

            # Ensure the complete database contents and directory entry are durable
            # before reporting publication success.
            file_fd = os.open(temporary, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
            try:
                os.fchmod(file_fd, 0o600)
                os.fsync(file_fd)
                byte_size = os.fstat(file_fd).st_size
            finally:
                os.close(file_fd)
            os.replace(temporary, self.destination)
            directory_fd = os.open(
                self.destination.parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return SnapshotPublication(
                path=str(self.destination),
                published_at=datetime.now(timezone.utc).isoformat(),
                event_count=int(event_count),
                episode_count=int(episode_count),
                byte_size=int(byte_size),
                journal_mode=journal_mode,
            )
        except SnapshotPublicationError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise SnapshotPublicationError("consistent SQLite snapshot publication failed") from exc
        finally:
            if snapshot_db is not None:
                snapshot_db.close()
            if source_db is not None:
                source_db.close()
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
