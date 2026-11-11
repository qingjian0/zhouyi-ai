"""Conservative validation for agent-produced unified diff artifacts.

Validation only: this module never applies patches or executes their contents.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class ValidatedPatch:
    paths: tuple[str, ...]
    patch_bytes: int
    file_count: int


class PatchValidator:
    def __init__(
        self,
        max_patch_bytes: int = 512 * 1024,
        max_files: int = 32,
        max_path_chars: int = 240,
    ):
        for name, value in (
            ("max_patch_bytes", max_patch_bytes),
            ("max_files", max_files),
            ("max_path_chars", max_path_chars),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        self.max_patch_bytes = max_patch_bytes
        self.max_files = max_files
        self.max_path_chars = max_path_chars

    def _path(self, raw: str, prefix: str) -> str | None:
        if raw == "/dev/null":
            return None
        expected = prefix + "/"
        if not raw.startswith(expected):
            raise ValueError("patch paths must use a/ and b/ relative prefixes")
        value = raw[len(expected):]
        if (
            not value
            or len(value) > self.max_path_chars
            or "\\" in value
            or value.startswith("/")
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
        ):
            raise ValueError("unsafe patch path")
        parts = value.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("patch path traversal or non-canonical path rejected")
        if parts[0].lower() == ".git":
            raise ValueError("patches may not modify Git metadata")
        if PurePosixPath(value).is_absolute():
            raise ValueError("absolute patch path rejected")
        return value

    def validate(self, patch: str) -> ValidatedPatch:
        if not isinstance(patch, str) or not patch:
            raise ValueError("patch must be non-empty text")
        encoded = patch.encode("utf-8")
        if len(encoded) > self.max_patch_bytes:
            raise ValueError("patch exceeds max_patch_bytes")
        if "\x00" in patch or "\r" in patch:
            raise ValueError("patch contains unsupported control data")
        forbidden = (
            "GIT binary patch",
            "Binary files ",
            "rename from ",
            "rename to ",
            "copy from ",
            "copy to ",
            "new file mode 120000",
            "old mode ",
            "new mode ",
        )
        if any(token in patch for token in forbidden):
            raise ValueError("binary, rename, symlink, and mode-change patches are rejected")

        lines = patch.splitlines()
        paths: list[str] = []
        index = 0
        while index < len(lines):
            line = lines[index]
            if not line.startswith("--- "):
                if line.startswith(("diff --git ", "index ", "+++ ", "@@ ", "+", "-", " ")):
                    index += 1
                    continue
                raise ValueError(f"unexpected unified diff line at {index + 1}")
            if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
                raise ValueError("each file diff must contain paired --- and +++ headers")
            old_raw = line[4:].split("\t", 1)[0]
            new_raw = lines[index + 1][4:].split("\t", 1)[0]
            old_path = self._path(old_raw, "a")
            new_path = self._path(new_raw, "b")
            if old_path is None and new_path is None:
                raise ValueError("a diff cannot add and delete /dev/null")
            path = new_path if new_path is not None else old_path
            assert path is not None
            if path in paths:
                raise ValueError("duplicate file path in patch")
            paths.append(path)
            index += 2

        if not paths:
            raise ValueError("patch contains no file changes")
        if len(paths) > self.max_files:
            raise ValueError("patch exceeds max_files")
        return ValidatedPatch(tuple(paths), len(encoded), len(paths))
