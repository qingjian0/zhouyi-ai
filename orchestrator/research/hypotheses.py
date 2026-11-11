"""Immutable, falsifiable hypothesis records stored as one JSON file each."""
from __future__ import annotations
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")

def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("hypothesis record must contain finite JSON values") from exc

@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    mechanism: str
    predicted_direction: str
    scope: str
    falsification_criteria: tuple[str, ...]
    parent_id: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        for name in ("hypothesis_id", "statement", "mechanism", "scope"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not _ID.fullmatch(self.hypothesis_id):
            raise ValueError("hypothesis_id contains unsupported characters")
        if self.predicted_direction not in {"positive", "negative"}:
            raise ValueError("predicted_direction must be positive or negative")
        if not isinstance(self.falsification_criteria, tuple) or not self.falsification_criteria or any(not isinstance(x, str) or not x.strip() for x in self.falsification_criteria):
            raise ValueError("falsification_criteria must be a non-empty tuple of strings")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version must be a positive integer")
        if self.parent_id is not None and (not isinstance(self.parent_id, str) or not _ID.fullmatch(self.parent_id)):
            raise ValueError("parent_id is invalid")

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(asdict(self))).hexdigest()

class HypothesisStore:
    """Filesystem store; IDs are immutable and cannot silently overwrite."""
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def add(self, hypothesis: Hypothesis) -> dict[str, str]:
        if not isinstance(hypothesis, Hypothesis):
            raise TypeError("hypothesis must be a Hypothesis instance")
        record = {**asdict(hypothesis), "digest": hypothesis.digest}
        data = _canonical(record) + b"\n"
        target = self.root / f"{hypothesis.hypothesis_id}.json"
        temp = self.root / f".{hypothesis.hypothesis_id}.{os.getpid()}.tmp"
        try:
            with temp.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temp, target)
        except FileExistsError as exc:
            raise FileExistsError(f"hypothesis already exists: {hypothesis.hypothesis_id}") from exc
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass
        return {"hypothesis_id": hypothesis.hypothesis_id, "digest": hypothesis.digest, "path": str(target)}

    def get(self, hypothesis_id: str) -> dict[str, Any]:
        if not isinstance(hypothesis_id, str) or not _ID.fullmatch(hypothesis_id):
            raise ValueError("hypothesis_id is invalid")
        path = self.root / f"{hypothesis_id}.json"
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(hypothesis_id) from None
        supplied_digest = record.pop("digest", None)
        actual_digest = hashlib.sha256(_canonical(record)).hexdigest()
        if supplied_digest != actual_digest:
            raise ValueError(f"hypothesis record integrity check failed: {hypothesis_id}")
        record["digest"] = supplied_digest
        return record
