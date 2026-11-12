"""Guard the E09 low-level event-store writer surface.

The authority facade is the intended writer. The shared protocol adapter is
temporarily allowlisted as a documented legacy, non-receipt-eligible path.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "prototype"
LOW_LEVEL_WRITER = re.compile(
    r"\.(?:append_event|commit_prediction|reveal_evidence|append_revision)\s*\("
)
ALLOWLIST = {
    "e09_authority_services.py",
    "e09_shared_protocol_adapter.py",
}


class E09StoreWriteAllowlistTests(unittest.TestCase):
    def test_only_reviewed_runtime_modules_call_low_level_store_writers(self):
        offenders = set()
        for path in sorted(PROTOTYPE.glob("*.py")):
            if path.name == "shared_evidence_protocol.py":
                # This module implements the low-level store API itself.
                continue
            if LOW_LEVEL_WRITER.search(path.read_text(encoding="utf-8")):
                offenders.add(path.name)
        self.assertEqual(
            offenders,
            ALLOWLIST,
            "New low-level E09 store writers require explicit security review",
        )

    def test_legacy_adapter_is_explicitly_non_authoritative(self):
        source = (PROTOTYPE / "e09_shared_protocol_adapter.py").read_text(encoding="utf-8")
        self.assertIn("trusted-runner", source)
        self.assertIn("actor_role=\"runner\"", source)


if __name__ == "__main__":
    unittest.main()
