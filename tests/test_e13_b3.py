import unittest

from prototype.e13_b3 import enumerate_bridge_candidates
from test_e13_bridge import make_graph


class BridgeCandidateDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.source = make_graph("s", "thermal", True)
        self.target = make_graph("t", "thermal", False)

    def test_enumerator_finds_explicitly_validated_bridge(self):
        result = enumerate_bridge_candidates(
            self.source, self.target, context_key_map=(("domain", "field"),),
            max_candidates=100
        )
        self.assertEqual(result.status, "COMPLETE")
        self.assertGreaterEqual(len(result.valid_candidates), 1)
        self.assertGreater(result.rejected_count, 0)
        self.assertTrue(all(v.status == "VALID" for _, v in result.valid_candidates))

    def test_budget_exhaustion_withholds_partial_acceptances(self):
        result = enumerate_bridge_candidates(
            self.source, self.target, context_key_map=(("domain", "field"),),
            max_candidates=1
        )
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertEqual(result.valid_candidates, ())

    def test_no_context_key_guessing(self):
        result = enumerate_bridge_candidates(
            self.source, self.target, context_key_map=(), max_candidates=100
        )
        self.assertEqual(result.status, "NO_VALID_CANDIDATES")


if __name__ == "__main__":
    unittest.main()
