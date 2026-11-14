import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from prototype.e12a6_writer_runtime import (
    E12A6WriterAlreadyRunning,
    E12A6WriterProcessLock,
    E12A6WriterRuntime,
    E12A6WriterRuntimeError,
)


class _Authenticator:
    def authenticate(self, credential):
        raise ValueError("test runtime does not accept credentials")


class E12A6WriterRuntimeTests(unittest.TestCase):
    def test_process_lock_is_exclusive_and_reusable_after_release(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            path = Path(directory) / "writer.lock"
            first = E12A6WriterProcessLock(path).acquire()
            self.assertTrue(first.acquired)
            with self.assertRaises(E12A6WriterAlreadyRunning):
                E12A6WriterProcessLock(path).acquire()
            first.release()
            with E12A6WriterProcessLock(path) as second:
                self.assertTrue(second.acquired)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_lock_excludes_a_separate_process(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            path = Path(directory) / "writer.lock"
            with E12A6WriterProcessLock(path):
                script = (
                    "from prototype.e12a6_writer_runtime import "
                    "E12A6WriterAlreadyRunning, E12A6WriterProcessLock\n"
                    "import sys\n"
                    "lock = E12A6WriterProcessLock(sys.argv[1])\n"
                    "try:\n"
                    "    lock.acquire()\n"
                    "except E12A6WriterAlreadyRunning:\n"
                    "    raise SystemExit(0)\n"
                    "raise SystemExit(3)\n"
                )
                result = subprocess.run(
                    [sys.executable, "-c", script, str(path)],
                    cwd=Path(__file__).resolve().parents[1],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_lock_fails_closed_for_group_or_world_accessible_state_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o755)
            with self.assertRaises(E12A6WriterRuntimeError):
                E12A6WriterProcessLock(Path(directory) / "writer.lock").acquire()

    def test_lock_rejects_symlink_lock_file(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            target = Path(directory) / "target"
            target.write_text("do-not-touch")
            link = Path(directory) / "writer.lock"
            link.symlink_to(target)
            with self.assertRaises(E12A6WriterRuntimeError):
                E12A6WriterProcessLock(link).acquire()
            self.assertEqual(target.read_text(), "do-not-touch")

    def test_runtime_holds_lock_and_restricts_database_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            database = Path(directory) / "writer.sqlite"
            runtime = E12A6WriterRuntime(
                database,
                authenticator=_Authenticator(),
                receipt_signature_verifier=lambda *_: False,
                trusted_verifier_id="trusted-verifier",
                scope="world/runtime-test",
            )
            self.assertIsNotNone(runtime.service)
            self.assertEqual(stat.S_IMODE(database.stat().st_mode), 0o600)
            with self.assertRaises(E12A6WriterAlreadyRunning):
                E12A6WriterProcessLock(str(database) + ".writer.lock").acquire()
            runtime.close()
            with E12A6WriterProcessLock(str(database) + ".writer.lock"):
                pass

    def test_runtime_rejects_symlink_database(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            target = Path(directory) / "target.sqlite"
            target.touch()
            link = Path(directory) / "writer.sqlite"
            link.symlink_to(target)
            with self.assertRaises(E12A6WriterRuntimeError):
                E12A6WriterRuntime(
                    link,
                    authenticator=_Authenticator(),
                    receipt_signature_verifier=lambda *_: False,
                    trusted_verifier_id="trusted-verifier",
                    scope="world/runtime-test",
                )
            self.assertEqual(target.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
