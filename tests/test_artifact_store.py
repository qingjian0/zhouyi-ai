import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.agents.artifact_store import ArtifactRef, FileArtifactStore
from orchestrator.agents.protocol import AgentArtifact


class FileArtifactStoreTests(unittest.TestCase):
    def test_round_trip_and_content_addressing(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FileArtifactStore(temp)
            artifact = AgentArtifact("report-1", "research", {"结论": ["a", "b"]})
            ref = store.put(artifact)
            self.assertEqual(store.get(ref), artifact)
            self.assertEqual(store.put(artifact), ref)
            self.assertTrue((Path(temp) / ref.digest[:2] / (ref.digest + ".json")).exists())

    def test_different_content_has_different_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FileArtifactStore(temp)
            a = store.put(AgentArtifact("a", "note", {"x": 1}))
            b = store.put(AgentArtifact("b", "note", {"x": 2}))
            self.assertNotEqual(a.digest, b.digest)

    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FileArtifactStore(temp, max_artifact_bytes=5)
            with self.assertRaisesRegex(ValueError, "max_artifact_bytes"):
                store.put(AgentArtifact("large", "note", "long-content"))

    def test_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FileArtifactStore(temp)
            ref = store.put(AgentArtifact("r", "note", {"v": 1}))
            path = Path(temp) / ref.digest[:2] / (ref.digest + ".json")
            envelope = json.loads(path.read_text())
            envelope["content"]["v"] = 2
            path.write_text(json.dumps(envelope))
            with self.assertRaisesRegex(ValueError, "integrity"):
                store.get(ref)

    def test_reference_metadata_mismatch_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            store = FileArtifactStore(temp)
            ref = store.put(AgentArtifact("r", "note", {"v": 1}))
            wrong = ArtifactRef("other", "note", ref.digest)
            with self.assertRaisesRegex(ValueError, "metadata"):
                store.get(wrong)

    def test_invalid_digest_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            ArtifactRef("r", "note", "../not-a-digest")


if __name__ == "__main__":
    unittest.main()
