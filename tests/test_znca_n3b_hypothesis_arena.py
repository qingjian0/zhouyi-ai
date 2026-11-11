import unittest

from prototype.znca_n3b_hypothesis_arena import (
    ArenaError, Hypothesis, HypothesisArena, HypothesisStatus, StateSnapshot,
)


def proposal(hypothesis_id, reads, writes, delta, evidence=("ev-1",)):
    return Hypothesis(
        hypothesis_id, 4, tuple(reads), tuple(writes),
        tuple(sorted(delta.items())), tuple(evidence),
    )


class HypothesisArenaTests(unittest.TestCase):
    def setUp(self):
        self.base = StateSnapshot.from_mapping(4, {"a": "0", "b": "0", "c": "0"})
        self.arena = HypothesisArena(self.base, {"ev-1", "ev-2"})

    def test_proposals_do_not_mutate_shared_state(self):
        self.arena.propose(proposal("h1", ("a",), ("b",), {"b": "1"}))
        self.arena.propose(proposal("h2", ("a",), ("c",), {"c": "1"}, ("ev-2",)))
        self.assertEqual(self.arena.snapshot, self.base)
        self.assertEqual(self.arena.snapshot.as_dict(), {"a": "0", "b": "0", "c": "0"})

    def test_hypotheses_are_returned_in_deterministic_order(self):
        self.arena.propose(proposal("z", ("a",), ("b",), {"b": "1"}))
        self.arena.propose(proposal("a", ("a",), ("c",), {"c": "1"}))
        self.assertEqual([h.hypothesis_id for h in self.arena.hypotheses()], ["a", "z"])

    def test_evidence_gate_marks_unknown_evidence_contested(self):
        self.arena.propose(proposal("h1", ("a",), ("b",), {"b": "1"}, ("missing",)))
        self.assertEqual(self.arena.assess("h1").status, HypothesisStatus.CONTESTED)
        with self.assertRaises(ArenaError):
            self.arena.commit("h1")

    def test_supported_hypothesis_commits_atomically(self):
        self.arena.propose(proposal("h1", ("a",), ("b",), {"b": "1"}))
        self.assertEqual(self.arena.assess("h1").status, HypothesisStatus.SUPPORTED)
        result = self.arena.commit("h1")
        self.assertEqual(result.status, HypothesisStatus.COMMITTED)
        self.assertEqual(result.snapshot.version, 5)
        self.assertEqual(result.snapshot.as_dict()["b"], "1")
        self.assertEqual(self.arena.snapshot, result.snapshot)

    def test_non_conflicting_sibling_can_commit_after_first(self):
        self.arena.propose(proposal("h1", ("a",), ("b",), {"b": "1"}))
        self.arena.propose(proposal("h2", ("a",), ("c",), {"c": "1"}, ("ev-2",)))
        self.arena.assess("h1")
        self.arena.assess("h2")
        self.arena.commit("h1")
        result = self.arena.commit("h2")
        self.assertEqual(result.status, HypothesisStatus.COMMITTED)
        self.assertEqual(result.snapshot.as_dict(), {"a": "0", "b": "1", "c": "1"})
        self.assertEqual(result.snapshot.version, 6)

    def test_read_write_conflict_marks_sibling_stale(self):
        self.arena.propose(proposal("h1", ("a",), ("b",), {"b": "1"}))
        self.arena.propose(proposal("h2", ("b",), ("c",), {"c": "1"}, ("ev-2",)))
        self.arena.assess("h1")
        self.arena.assess("h2")
        self.arena.commit("h1")
        result = self.arena.commit("h2")
        self.assertEqual(result.status, HypothesisStatus.STALE)
        self.assertEqual(result.conflict_keys, ("b",))
        self.assertEqual(self.arena.snapshot.as_dict()["c"], "0")

    def test_write_write_conflict_marks_sibling_stale(self):
        self.arena.propose(proposal("h1", ("a",), ("b",), {"b": "1"}))
        self.arena.propose(proposal("h2", ("a",), ("b",), {"b": "2"}, ("ev-2",)))
        self.arena.assess("h1")
        self.arena.assess("h2")
        self.arena.commit("h1")
        self.assertEqual(self.arena.commit("h2").status, HypothesisStatus.STALE)

    def test_commit_is_idempotent(self):
        self.arena.propose(proposal("h1", ("a",), ("b",), {"b": "1"}))
        self.arena.assess("h1")
        first = self.arena.commit("h1")
        second = self.arena.commit("h1")
        self.assertEqual(second.snapshot, first.snapshot)
        self.assertTrue(second.idempotent)
        self.assertEqual(second.snapshot.version, 5)

    def test_reject_is_terminal(self):
        self.arena.propose(proposal("h1", ("a",), ("b",), {"b": "1"}))
        self.assertEqual(self.arena.reject("h1").status, HypothesisStatus.REJECTED)
        with self.assertRaises(ArenaError):
            self.arena.commit("h1")

    def test_invalid_delta_and_unknown_read_keys_are_rejected(self):
        with self.assertRaises(ArenaError):
            proposal("bad", ("a",), ("b",), {"c": "1"})
        with self.assertRaises(ArenaError):
            self.arena.propose(proposal("bad-read", ("missing",), ("b",), {"b": "1"}))

    def test_cannot_bypass_evidence_gate_with_pre_supported_status(self):
        with self.assertRaises(ArenaError):
            Hypothesis(
                "forged", 4, ("a",), ("b",), (("b", "1"),), ("ev-1",),
                HypothesisStatus.SUPPORTED,
            )

    def test_empty_read_or_write_set_is_rejected(self):
        with self.assertRaises(ArenaError):
            Hypothesis("empty-read", 4, (), ("b",), (("b", "1"),), ("ev-1",))
        with self.assertRaises(ArenaError):
            Hypothesis("empty-write", 4, ("a",), (), (), ("ev-1",))

    def test_stale_base_version_is_rejected(self):
        bad = Hypothesis("old", 3, ("a",), ("b",), (("b", "1"),), ("ev-1",))
        with self.assertRaises(ArenaError):
            self.arena.propose(bad)


if __name__ == "__main__":
    unittest.main()
