import unittest

from prototype.e02_edge_lifecycle import HyperedgeLifecycle, LifecycleError
from prototype.e09_counterexample_learner import Example
from prototype.e09_evidence_ledger import EvidenceError, EvidenceLedger
from prototype.e09_lifecycle_bridge import proposal_from_ledger


class E09LifecycleBridgeTests(unittest.TestCase):
    def make_ledger(self):
        ledger = EvidenceLedger()
        ledger.append("p1", Example((0,), "yes"), source_id="source-A")
        ledger.append("p2", Example((1,), "yes"), source_id="source-B")
        ledger.append("p3", Example((2,), "yes"), source_id="source-C")
        ledger.append("n1", Example((3,), "no"), source_id="source-N")
        return ledger

    def test_builds_auditable_lifecycle_proposal(self):
        proposal = proposal_from_ledger(
            self.make_ledger(), edge_id="edge-1", members=("node-a", "node-b"),
            roles=("subject", "object"), relation_type="causal_candidate",
            positive_label="yes", validation_gain=0.12, cost=1.0,
        )
        self.assertEqual(proposal.support_ids, ("p1", "p2", "p3"))
        self.assertEqual(proposal.counterexample_ids, ("n1",))
        lifecycle = HyperedgeLifecycle(min_support=3)
        edge = lifecycle.create(proposal)
        self.assertEqual(edge.support_ids, ("p1", "p2", "p3"))

    def test_rejects_repeated_samples_from_one_source(self):
        ledger = EvidenceLedger()
        ledger.append("p1", Example((0,), "yes"), source_id="same-source")
        ledger.append("p2", Example((1,), "yes"), source_id="same-source")
        ledger.append("p3", Example((2,), "yes"), source_id="same-source")
        with self.assertRaises(EvidenceError):
            proposal_from_ledger(
                ledger, edge_id="e", members=("a", "b"), roles=("x", "y"),
                relation_type="r", positive_label="yes", validation_gain=0.2,
                cost=1.0, min_independent_sources=3,
            )

    def test_excludes_contested_inputs_from_support_and_counterexamples(self):
        ledger = self.make_ledger()
        ledger.append("p1-conflict", Example((0,), "no"), source_id="source-X")
        proposal = proposal_from_ledger(
            ledger, edge_id="e", members=("a", "b"), roles=("x", "y"),
            relation_type="r", positive_label="yes", validation_gain=0.2,
            cost=1.0, min_independent_sources=2,
        )
        self.assertNotIn("p1", proposal.support_ids)
        self.assertNotIn("p1-conflict", proposal.counterexample_ids)

    def test_lifecycle_still_enforces_validation_and_support_gates(self):
        proposal = proposal_from_ledger(
            self.make_ledger(), edge_id="e", members=("a", "b"), roles=("x", "y"),
            relation_type="r", positive_label="yes", validation_gain=0.0,
            cost=1.0,
        )
        with self.assertRaises(LifecycleError):
            HyperedgeLifecycle(min_support=3).create(proposal)


if __name__ == "__main__":
    unittest.main()
