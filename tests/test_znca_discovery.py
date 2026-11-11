import unittest

from prototype.znca_dynamics import StateSnapshot, TransitionExample
from prototype.znca_discovery import DiscoveryError, discover_candidates


def snap(**values):
    return StateSnapshot.from_mapping(values)


class CandidateDiscoveryTests(unittest.TestCase):
    def test_discovers_joint_higher_order_association(self):
        rows = []
        for a in (0.0, 1.0):
            for b in (0.0, 1.0):
                for c in (0.0, 1.0):
                    z = 1.0 if a == b == c == 1.0 else 0.0
                    rows.append(TransitionExample(
                        snap(a=a, b=b, c=c, z=0.0),
                        snap(a=a, b=b, c=c, z=z),
                        f"synthetic:{int(a)}:{int(b)}:{int(c)}",
                    ))
        report = discover_candidates(
            rows, max_arity=3, candidate_budget=100, max_terms_per_target=20
        )
        z_scores = [s for s in report.scores if s.target == "z"]
        self.assertTrue(any(s.source_keys == ("a", "b", "c") for s in z_scores))
        self.assertEqual(report.candidates_considered, 28)
        joint = next(s for s in z_scores if s.source_keys == ("a", "b", "c"))
        self.assertEqual(joint.polarity, 1)

    def test_discovers_negative_association(self):
        rows = []
        for a in (0.0, 1.0):
            rows.append(TransitionExample(
                snap(a=a, z=0.0), snap(a=a, z=1.0-a), f"ev:{int(a)}"
            ))
        report = discover_candidates(rows, max_arity=1, candidate_budget=10)
        candidate = next(s for s in report.scores if s.target == "z")
        self.assertEqual(candidate.polarity, -1)

    def test_budget_exhaustion_is_explicit_and_deterministic(self):
        rows = [
            TransitionExample(snap(a=0, b=0, z=0), snap(a=0, b=0, z=0), "e1"),
            TransitionExample(snap(a=1, b=1, z=0), snap(a=1, b=1, z=1), "e2"),
        ]
        first = discover_candidates(rows, max_arity=2, candidate_budget=1)
        second = discover_candidates(rows, max_arity=2, candidate_budget=1)
        self.assertTrue(first.budget_exhausted)
        self.assertEqual(first, second)
        self.assertEqual(first.candidates_considered, 1)

    def test_no_signal_returns_no_candidates(self):
        rows = [
            TransitionExample(snap(a=0, z=0), snap(a=0, z=0), "e1"),
            TransitionExample(snap(a=1, z=0), snap(a=1, z=0), "e2"),
        ]
        report = discover_candidates(rows, max_arity=1)
        self.assertEqual(report.terms, ())

    def test_rejects_inconsistent_schema(self):
        rows = [
            TransitionExample(snap(a=0, z=0), snap(a=0, z=1), "e1"),
            TransitionExample(snap(a=0, b=0, z=0), snap(a=0, b=0, z=1), "e2"),
        ]
        with self.assertRaises(DiscoveryError):
            discover_candidates(rows)

    def test_candidate_terms_keep_evidence_refs(self):
        rows = [
            TransitionExample(snap(a=0, z=0), snap(a=0, z=0), "e1"),
            TransitionExample(snap(a=1, z=0), snap(a=1, z=1), "e2"),
        ]
        report = discover_candidates(rows, max_arity=1)
        self.assertEqual(report.terms[0].evidence_refs, ("e1", "e2"))


if __name__ == "__main__":
    unittest.main()
