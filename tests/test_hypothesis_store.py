import json
import tempfile
import unittest
from pathlib import Path
from orchestrator.research.hypotheses import Hypothesis, HypothesisStore

class HypothesisStoreTests(unittest.TestCase):
    def make_hypothesis(self, **overrides):
        values = {"hypothesis_id": "ternary-ood-v1", "statement": "A ternary representation improves OOD relational induction.", "mechanism": "Three-valued states preserve an explicit indeterminate relation.", "predicted_direction": "positive", "scope": "relational-induction-v1", "falsification_criteria": ("OOD confidence interval crosses zero", "Shuffled prior matches the effect")}
        values.update(overrides)
        return Hypothesis(**values)
    def test_add_and_read_with_integrity_digest(self):
        with tempfile.TemporaryDirectory() as root:
            store = HypothesisStore(root)
            created = store.add(self.make_hypothesis())
            loaded = store.get("ternary-ood-v1")
            self.assertEqual(loaded["digest"], created["digest"])
            self.assertEqual(loaded["statement"], self.make_hypothesis().statement)
    def test_duplicate_id_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            store = HypothesisStore(root)
            store.add(self.make_hypothesis())
            with self.assertRaises(FileExistsError):
                store.add(self.make_hypothesis())
    def test_missing_falsification_criteria_rejected(self):
        with self.assertRaises(ValueError):
            self.make_hypothesis(falsification_criteria=())
    def test_tampering_detected(self):
        with tempfile.TemporaryDirectory() as root:
            store = HypothesisStore(root)
            store.add(self.make_hypothesis())
            path = Path(root) / "ternary-ood-v1.json"
            record = json.loads(path.read_text())
            record["statement"] = "tampered"
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "integrity"):
                store.get("ternary-ood-v1")

if __name__ == "__main__":
    unittest.main()
