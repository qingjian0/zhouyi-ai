import tempfile
import unittest
from pathlib import Path

from orchestrator.agents.patch_validation import PatchValidator
from orchestrator.agents.workspace import WorkspaceManager


class WorkspaceManagerTests(unittest.TestCase):
    def test_create_and_cleanup_is_scoped_to_root(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = WorkspaceManager(temp)
            workspace = manager.create("task-01")
            self.assertTrue(workspace.path.is_dir())
            self.assertEqual(workspace.path.parent, Path(temp).resolve())
            manager.cleanup(workspace)
            self.assertFalse(workspace.path.exists())

    def test_rejects_unsafe_task_id(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = WorkspaceManager(temp)
            for task_id in ("../escape", "", "a/b", "a\\b"):
                with self.subTest(task_id=task_id), self.assertRaises(ValueError):
                    manager.create(task_id)

    def test_refuses_symlink_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = WorkspaceManager(Path(temp) / "root")
            outside = Path(temp) / "outside"
            outside.mkdir()
            workspace = manager.create("task")
            workspace.path.rmdir()
            try:
                workspace.path.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable on this platform: {exc}")
            with self.assertRaisesRegex(ValueError, "symlink"):
                manager.cleanup(workspace)


class PatchValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = PatchValidator()

    def test_accepts_simple_modification(self):
        patch = (
            "diff --git a/src/example.py b/src/example.py\n"
            "--- a/src/example.py\n"
            "+++ b/src/example.py\n"
            "@@ -1 +1 @@\n-old\n+new\n"
        )
        result = self.validator.validate(patch)
        self.assertEqual(result.paths, ("src/example.py",))
        self.assertEqual(result.file_count, 1)

    def test_accepts_addition_and_deletion(self):
        addition = "--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1 @@\n+x\n"
        deletion = "--- a/old.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
        self.assertEqual(self.validator.validate(addition).paths, ("new.txt",))
        self.assertEqual(self.validator.validate(deletion).paths, ("old.txt",))

    def test_rejects_path_traversal_and_absolute_paths(self):
        for path in ("a/../secret", "a//secret", "/etc/passwd", "a/.git/config"):
            patch = f"--- {path}\n+++ b/ok.txt\n@@ -1 +1 @@\n-x\n+y\n"
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.validator.validate(patch)

    def test_rejects_binary_symlink_rename_and_mode_changes(self):
        cases = (
            "GIT binary patch\n",
            "new file mode 120000\n",
            "rename from a.txt\n",
            "old mode 100644\n",
        )
        for marker in cases:
            patch = (
                "diff --git a/a.txt b/a.txt\n" + marker
                + "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-a\n+b\n"
            )
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                self.validator.validate(patch)

    def test_rejects_windows_drive_ads_and_reserved_names(self):
        for path in ("a/C:/Windows/system.ini", "a/file:stream", "a/NUL.txt", "a/trailing."):
            patch = f"--- {path}\\n+++ b/ok.txt\\n@@ -1 +1 @@\\n-x\\n+y\\n"
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.validator.validate(patch)

    def test_rejects_duplicate_paths_and_limits(self):
        one = "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-a\n+b\n"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.validator.validate(one + one)
        with self.assertRaisesRegex(ValueError, "max_patch_bytes"):
            PatchValidator(max_patch_bytes=5).validate(one)
        with self.assertRaisesRegex(ValueError, "max_files"):
            PatchValidator(max_files=1).validate(one + "--- a/b.txt\n+++ b/b.txt\n@@ -1 +1 @@\n-a\n+b\n")


if __name__ == "__main__":
    unittest.main()
