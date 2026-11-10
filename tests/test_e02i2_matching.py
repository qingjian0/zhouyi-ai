import unittest

from prototype.e02i2_lineage import RelationLineageLedger
from prototype.e02i2_matching import (
    MatchingMethod,
    RelationCandidate,
    match_candidates,
    similarity,
)


def version(identity_id, members, roles, rule, operator="AND", context="lab"):
    ledger = RelationLineageLedger()
    ledger.create(
        identity_id=identity_id,
        version_id=identity_id + "-v1",
        members=members,
        roles=roles,
        operator=operator,
        rule_signature=rule,
        context_signature=context,
        window=0,
        evidence_refs=("evidence",),
    )
    return ledger.versions[identity_id + "-v1"]


class E02I2MatchingTests(unittest.TestCase):
    def setUp(self):
        self.old = {
            "r1": version("r1", ("a", "b"), ("source", "target"), "a&b"),
            "r2": version("r2", ("c", "d"), ("source", "target"), "c&d"),
        }

    def test_exact_signature_matches_and_rejects_semantic_change(self):
        same = RelationCandidate("c1", ("a", "b"), ("source", "target"), "AND", "a&b", "lab")
        changed = RelationCandidate("c2", ("a", "b"), ("source", "target"), "OR", "a|b", "lab")
        decisions = match_candidates((same, changed), self.old, method=MatchingMethod.EXACT)
        self.assertEqual(decisions[0].identity_id, "r1")
        self.assertIsNone(decisions[1].identity_id)
        self.assertTrue(decisions[1].abstained)

    def test_jaccard_baseline_exposes_same_member_semantic_blindness(self):
        changed = RelationCandidate("c1", ("a", "b"), ("left", "right"), "XOR", "a^b", "new")
        decision = match_candidates(
            (changed,), self.old, method=MatchingMethod.JACCARD,
            min_score=0.9, min_margin=0.01,
        )[0]
        # This is an intentional baseline limitation, not an endorsed decision.
        self.assertEqual(decision.identity_id, "r1")

    def test_role_aligned_score_is_order_invariant_but_role_sensitive(self):
        base = RelationCandidate("c1", ("a", "b"), ("source", "target"), "AND", "a&b", "lab")
        permuted = RelationCandidate("c2", ("b", "a"), ("target", "source"), "AND", "a&b", "lab")
        swapped = RelationCandidate("c3", ("a", "b"), ("target", "source"), "AND", "a&b", "lab")
        self.assertEqual(similarity(base, self.old["r1"]), similarity(permuted, self.old["r1"]))
        self.assertGreater(similarity(base, self.old["r1"]), similarity(swapped, self.old["r1"]))

    def test_ambiguous_candidates_abstain(self):
        near = version("r3", ("a", "b"), ("source", "target"), "a&b", context="lab")
        candidates = (RelationCandidate("c1", ("a", "b"), ("source", "target"), "AND", "a&b", "lab"),)
        decisions = match_candidates(
            candidates, {"r1": self.old["r1"], "r3": near},
            method=MatchingMethod.ROLE_ALIGNED, min_score=0.7, min_margin=0.05,
        )
        self.assertTrue(decisions[0].abstained)
        self.assertIsNone(decisions[0].identity_id)

    def test_hungarian_assignment_is_one_to_one_and_can_abstain(self):
        candidates = (
            RelationCandidate("c1", ("a", "b"), ("source", "target"), "AND", "a&b", "lab"),
            RelationCandidate("c2", ("a", "b"), ("source", "target"), "AND", "a&b", "lab"),
            RelationCandidate("c3", ("x", "y"), ("source", "target"), "OR", "x|y", "other"),
        )
        decisions = match_candidates(
            candidates, self.old, method=MatchingMethod.HUNGARIAN,
            min_score=0.7, min_margin=0.05,
        )
        matched = [d.identity_id for d in decisions if d.identity_id is not None]
        self.assertEqual(len(matched), len(set(matched)))
        self.assertTrue(any(d.abstained for d in decisions))

    def test_greedy_matching_is_independent_of_candidate_input_order(self):
        exact = RelationCandidate("a-exact", ("a", "b"), ("source", "target"), "AND", "a&b", "lab")
        partial = RelationCandidate("b-partial", ("a", "b", "e"), ("source", "target", "extra"), "AND", "other", "lab")
        kwargs = dict(method=MatchingMethod.ROLE_ALIGNED, min_score=0.3, min_margin=0.01)
        forward = match_candidates((partial, exact), {"r1": self.old["r1"]}, **kwargs)
        reverse = match_candidates((exact, partial), {"r1": self.old["r1"]}, **kwargs)
        by_id_forward = {d.candidate_id: d.identity_id for d in forward}
        by_id_reverse = {d.candidate_id: d.identity_id for d in reverse}
        self.assertEqual(by_id_forward, by_id_reverse)
        self.assertEqual(by_id_forward["a-exact"], "r1")
        self.assertIsNone(by_id_forward["b-partial"])

    def test_empty_identity_set_abstains(self):
        candidate = RelationCandidate("c1", ("x", "y"), ("a", "b"), "AND", "x&y")
        result = match_candidates((candidate,), {}, method=MatchingMethod.HUNGARIAN)
        self.assertTrue(result[0].abstained)
        self.assertIsNone(result[0].identity_id)

    def test_duplicate_candidate_ids_are_rejected(self):
        c1 = RelationCandidate("same", ("a", "b"), ("source", "target"), "AND", "a&b")
        c2 = RelationCandidate("same", ("c", "d"), ("source", "target"), "AND", "c&d")
        with self.assertRaises(ValueError):
            match_candidates((c1, c2), self.old, method=MatchingMethod.EXACT)

    def test_thresholds_are_validated(self):
        candidate = RelationCandidate("c1", ("a", "b"), ("source", "target"), "AND", "a&b")
        with self.assertRaises(ValueError):
            match_candidates((candidate,), self.old, method=MatchingMethod.EXACT, min_score=1.1)


if __name__ == "__main__":
    unittest.main()
