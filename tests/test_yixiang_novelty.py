import unittest

from prototype.yixiang_novelty import (
    ProposalStatus, ResidualCase, propose_novel_structures,
    review_proposal, rollback_proposal,
)


def case(rid, oid, domain, evidence, context=(), source_group=None):
    signature = (("relation", "participates_in", "feedback_loop"),)
    lineage = ((evidence, source_group),) if source_group else ()
    return ResidualCase(rid, oid, domain, signature, context, (evidence,), lineage)


class NoveltyDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.residuals = (
            case("r1", "o1", "ecology", "paper:a", (("season", "spring"),), "edition-family-a"),
            case("r2", "o2", "mechanics", "paper:b", (("scale", "micro"),), "edition-family-b"),
        )

    def test_recurring_cross_domain_residual_becomes_review_only_proposal(self):
        proposals = propose_novel_structures(self.residuals)
        self.assertEqual(len(proposals), 1)
        proposal = proposals[0]
        self.assertEqual(proposal.status, ProposalStatus.PROPOSED)
        self.assertEqual(len(proposal.domains), 2)
        self.assertEqual(len(proposal.evidence_refs), 2)
        self.assertEqual(proposal.evidence_independence_groups, ("edition-family-a", "edition-family-b"))
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
                self.residuals, known_signatures=((("z", "x", "y"), ("a", "x", "y")),)
            )

    def test_single_domain_or_single_support_does_not_pass_default_threshold(self):
        one = (self.residuals[0],)
        self.assertEqual(propose_novel_structures(one), ())
        same_domain = (
            self.residuals[0],
            case("r3", "o3", "ecology", "paper:c", source_group="edition-family-c"),
        )
        self.assertEqual(propose_novel_structures(same_domain), ())

    def test_multiple_urls_from_one_source_family_do_not_count_as_independent(self):
        same_family = (
            case("r1", "o1", "ecology", "mirror:a", source_group="same-base-text"),
            case("r2", "o2", "mechanics", "mirror:b", source_group="same-base-text"),
        )
        self.assertEqual(propose_novel_structures(same_family), ())

    def test_missing_lineage_cannot_satisfy_independence_threshold(self):
        unknown = (
            case("r1", "o1", "ecology", "paper:a"),
            case("r2", "o2", "mechanics", "paper:b"),
        )
        self.assertEqual(propose_novel_structures(unknown), ())

    def test_partial_or_unsorted_lineage_mapping_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "map every evidence ref"):
            ResidualCase("r", "o", "domain", (("relation", "x", "y"),), (),
                         ("a", "b"), (("a", "source-a"),)).validate()
        with self.assertRaisesRegex(ValueError, "sorted"):
            ResidualCase("r", "o", "domain", (("relation", "x", "y"),), (),
                         ("a", "b"), (("b", "source-b"), ("a", "source-a"))).validate()

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
