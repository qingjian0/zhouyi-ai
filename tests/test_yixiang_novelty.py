import unittest

from prototype.yixiang_novelty import (
    ProposalStatus, ResidualCase, propose_novel_structures,
    review_proposal, rollback_proposal,
)


def case(rid, oid, domain, evidence, context=()):
    signature = (("relation", "participates_in", "feedback_loop"),)
    return ResidualCase(rid, oid, domain, signature, context, (evidence,))


class NoveltyDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.residuals = (
            case("r1", "o1", "ecology", "paper:a", (("season", "spring"),)),
            case("r2", "o2", "mechanics", "paper:b", (("scale", "micro"),)),
        )

    def test_recurring_cross_domain_residual_becomes_review_only_proposal(self):
        proposals = propose_novel_structures(self.residuals)
        self.assertEqual(len(proposals), 1)
        proposal = proposals[0]
        self.assertEqual(proposal.status, ProposalStatus.PROPOSED)
        self.assertEqual(len(proposal.domains), 2)
        self.assertEqual(len(proposal.evidence_refs), 2)
        self.assertEqual(len(proposal.context_records), 2)

    def test_known_signature_is_not_proposed_again(self):
        signature = self.residuals[0].signature
        self.assertEqual(
            propose_novel_structures(self.residuals, known_signatures=(signature,)), ()
        )

    def test_malformed_known_signatures_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "known signature entries"):
            propose_novel_structures(
                self.residuals, known_signatures=((["relation", "x", "y"],),)
            )
        with self.assertRaisesRegex(ValueError, "known signatures"):
            propose_novel_structures(
                self.residuals, known_signatures=((("relation", "x", "y"), ("bad",)),)
            )

    def test_single_domain_or_single_support_does_not_pass_default_threshold(self):
        one = (self.residuals[0],)
        self.assertEqual(propose_novel_structures(one), ())
        same_domain = (
            self.residuals[0],
            case("r3", "o3", "ecology", "paper:c"),
        )
        self.assertEqual(propose_novel_structures(same_domain), ())

    def test_review_creates_immutable_new_version(self):
        proposal = propose_novel_structures(self.residuals)[0]
        accepted = review_proposal(
            proposal, decision=ProposalStatus.ACCEPTED,
            reviewer="human-reviewer", note="independent replication checked",
        )
        self.assertEqual(proposal.status, ProposalStatus.PROPOSED)
        self.assertEqual(accepted.status, ProposalStatus.ACCEPTED)
        self.assertEqual(accepted.version, 2)
        self.assertEqual(accepted.parent_version_id, proposal.proposal_id + ":v1")

    def test_rollback_creates_new_proposed_version(self):
        proposal = propose_novel_structures(self.residuals)[0]
        accepted = review_proposal(
            proposal, decision=ProposalStatus.ACCEPTED,
            reviewer="reviewer", note="reviewed",
        )
        rolled = rollback_proposal(accepted, reason="new counterexample invalidates scope")
        self.assertEqual(rolled.status, ProposalStatus.PROPOSED)
        self.assertEqual(rolled.version, 3)
        self.assertEqual(rolled.parent_version_id, accepted.proposal_id + ":v2")

    def test_invalid_residual_metadata_is_rejected(self):
        bad = ResidualCase("r", "o", "domain", (("relation", "x", "y"),),
                           (), ())
        with self.assertRaisesRegex(ValueError, "evidence references"):
            propose_novel_structures((bad,))


if __name__ == "__main__":
    unittest.main()
