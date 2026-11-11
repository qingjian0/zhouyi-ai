"""Lifecycle management for isolated per-task working directories.

This is workspace isolation for file organization, not an OS security sandbox.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class Workspace:
    task_id: str
    path: Path


class WorkspaceManager:
    def __init__(self, root: str | Path):
        candidate = Path(root)
        candidate.mkdir(parents=True, exist_ok=True)
        self.root = candidate.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("workspace root must be a directory")

    def create(self, task_id: str) -> Workspace:
        if not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id):
            raise ValueError("task_id must be 1-64 safe filename characters")
        path = Path(tempfile.mkdtemp(prefix=f"{task_id}-", dir=self.root))
        return Workspace(task_id, path)

    def cleanup(self, workspace: Workspace) -> None:
        if not isinstance(workspace, Workspace):
            raise TypeError("workspace must be Workspace")
        path = workspace.path
        # Do not follow a replaced workspace symlink or delete outside the managed root.
        if path.is_symlink():
            raise ValueError("refusing to clean a symlink workspace")
        parent = path.parent.resolve(strict=True)
        if parent != self.root or not path.name.startswith(f"{workspace.task_id}-"):
            raise ValueError("workspace is outside the managed root or has an invalid name")
        if not path.exists():
            return
        resolved = path.resolve(strict=True)
        if resolved.parent != self.root or not resolved.is_dir():
            raise ValueError("workspace path escaped the managed root")
        shutil.rmtree(resolved)

    def cleanup_all(self, workspaces: Iterable[Workspace]) -> None:
        for workspace in workspaces:
            self.cleanup(workspace)
