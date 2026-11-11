"""Content-addressed, local artifact storage for agent deliverables."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .protocol import AgentArtifact, _require_text

_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    kind: str
    digest: str

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.kind, "artifact kind")
        if (
            not isinstance(self.digest, str)
            or len(self.digest) != 64
            or any(ch not in "0123456789abcdef" for ch in self.digest)
        ):
            raise ValueError("digest must be a lowercase SHA-256 hex digest")


class ArtifactStore(Protocol):
    def put(self, artifact: AgentArtifact) -> ArtifactRef:
        ...

    def get(self, ref: ArtifactRef) -> AgentArtifact:
        ...


class FileArtifactStore:
    """Atomic JSON artifact store; filenames are derived only from content hashes."""

    def __init__(self, root: str | Path, max_artifact_bytes: int = 8 * 1024 * 1024):
        if (
            isinstance(max_artifact_bytes, bool)
            or not isinstance(max_artifact_bytes, int)
            or max_artifact_bytes < 1
        ):
            raise ValueError("max_artifact_bytes must be a positive integer")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.root = self.root.resolve()
        if not self.root.is_dir():
            raise ValueError("artifact root must be a directory")
        self.max_artifact_bytes = max_artifact_bytes

    @staticmethod
    def _canonical_content(content: Any) -> bytes:
        try:
            encoded = json.dumps(
                content, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("artifact content must be finite JSON data") from exc
        return encoded

    def _path_for(self, digest: str) -> Path:
        # Digest validation happens before this method; no caller-controlled path parts.
        return self.root / digest[:2] / f"{digest}.json"

    def put(self, artifact: AgentArtifact) -> ArtifactRef:
        if not isinstance(artifact, AgentArtifact):
            raise TypeError("artifact must be AgentArtifact")
        content_bytes = self._canonical_content(artifact.content)
        if len(content_bytes) > self.max_artifact_bytes:
            raise ValueError("artifact exceeds max_artifact_bytes")
        digest = hashlib.sha256(content_bytes).hexdigest()
        ref = ArtifactRef(artifact.artifact_id, artifact.kind, digest)
        destination = self._path_for(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "schema_version": _SCHEMA_VERSION,
            "artifact_id": artifact.artifact_id,
            "kind": artifact.kind,
            "digest": digest,
            "content": artifact.content,
        }
        payload = json.dumps(
            envelope, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        ).encode("utf-8")
        if destination.exists():
            # Existing content-addressed objects must be identical and valid.
            self.get(ref)
            return ref
        fd, temp_name = tempfile.mkstemp(prefix=".artifact-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temp_name, destination)
            except FileExistsError:
                self.get(ref)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return ref

    def get(self, ref: ArtifactRef) -> AgentArtifact:
        if not isinstance(ref, ArtifactRef):
            raise TypeError("ref must be ArtifactRef")
        path = self._path_for(ref.digest)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KeyError(f"artifact not found: {ref.digest}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("artifact object is unreadable or invalid JSON") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != _SCHEMA_VERSION:
            raise ValueError("unsupported artifact envelope")
        if raw.get("artifact_id") != ref.artifact_id or raw.get("kind") != ref.kind:
            raise ValueError("artifact reference metadata does not match stored object")
        content_bytes = self._canonical_content(raw.get("content"))
        actual_digest = hashlib.sha256(content_bytes).hexdigest()
        if actual_digest != ref.digest or raw.get("digest") != ref.digest:
            raise ValueError("artifact integrity check failed")
        if len(content_bytes) > self.max_artifact_bytes:
            raise ValueError("stored artifact exceeds configured size limit")
        return AgentArtifact(ref.artifact_id, ref.kind, raw["content"])
