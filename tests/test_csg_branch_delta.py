import unittest

from prototype.csg_branch_delta import (
    BranchDelta, BranchSnapshot, DeltaOperation, MergeStatus,
    canonical_hash, merge_branch_deltas,
)


class BranchDeltaTests(unittest.TestCase):
    def event(self, event_id, op, target, before, value, version=1, parent=None):
        return BranchDelta(event_id, op, target, before, value, (), parent, version)

    def snap(self, branch, events, reads=()):
        return BranchSnapshot("parent-1", branch, 7, tuple(events), tuple(reads),
                              tuple(e.target_ref for e in events),
                              tuple(sorted({r for e in events for r in e.evidence_refs})),
                              ("root", branch))

    def test_disjoint_deltas_merge_deterministically(self):
        base = {"n:1": {"kind": "node"}, "n:2": {"kind": "node"}}
        a = self.event("a1", DeltaOperation.UPDATE_ATTRIBUTE, "n:1",
                       canonical_hash(base["n:1"]), {"kind": "node", "x": 1})
        b = self.event("b1", DeltaOperation.REMOVE_NODE, "n:2",
                       canonical_hash(base["n:2"]), None)
        result = merge_branch_deltas(base, (self.snap("a", [a]), self.snap("b", [b])))
        self.assertEqual(result.status, MergeStatus.MERGED)
        self.assertEqual(dict(result.state), {"n:1": {"kind": "node", "x": 1}})
        self.assertEqual(result.applied_event_ids, ("a1", "b1"))

    def test_shared_parent_and_version_are_mandatory(self):
        a = self.snap("a", [])
        b = BranchSnapshot("other-parent", "b", 7, (), (), (), (), ("root", "b"))
        self.assertEqual(merge_branch_deltas({}, (a, b)).status, MergeStatus.REJECTED)

    def test_same_target_write_is_conflict_not_last_writer_wins(self):
        base = {"n": 0}
        a = self.event("a1", DeltaOperation.UPDATE_ATTRIBUTE, "n", canonical_hash(0), 1)
        b = self.event("b1", DeltaOperation.UPDATE_ATTRIBUTE, "n", canonical_hash(0), 2)
        result = merge_branch_deltas(base, (self.snap("a", [a]), self.snap("b", [b])))
        self.assertEqual(result.status, MergeStatus.CONFLICT)
        self.assertEqual(dict(result.state), base)

    def test_stale_before_hash_rejected(self):
        base = {"n": 3}
        e = self.event("a1", DeltaOperation.UPDATE_ATTRIBUTE, "n", canonical_hash(2), 4)
        result = merge_branch_deltas(base, (self.snap("a", [e]),))
        self.assertEqual(result.status, MergeStatus.STALE)

    def test_write_read_dependency_conflict(self):
        base = {"n": 0}
        e = self.event("a1", DeltaOperation.UPDATE_ATTRIBUTE, "n", canonical_hash(0), 1)
        a = self.snap("a", [e])
        b = BranchSnapshot("parent-1", "b", 7, (), ("n",), (), (), ("root", "b"))
        self.assertEqual(merge_branch_deltas(base, (a, b)).status, MergeStatus.CONFLICT)

    def test_identical_event_replay_is_idempotent(self):
        e = self.event("a1", DeltaOperation.ADD_NODE, "new", None, {"kind": "node"})
        a = self.snap("a", [e])
        b = self.snap("b", [e])
        result = merge_branch_deltas({}, (a, b))
        self.assertEqual(result.status, MergeStatus.MERGED)
        self.assertEqual(result.applied_event_ids, ("a1",))

    def test_event_id_reuse_with_different_payload_is_rejected(self):
        a = self.event("same", DeltaOperation.ADD_NODE, "a", None, 1)
        b = self.event("same", DeltaOperation.ADD_NODE, "b", None, 2)
        result = merge_branch_deltas({}, (self.snap("a", [a]), self.snap("b", [b])))
        self.assertEqual(result.status, MergeStatus.CONFLICT)

    def test_invalid_write_set_is_rejected(self):
        e = self.event("a1", DeltaOperation.ADD_NODE, "n", None, {})
        bad = BranchSnapshot("parent-1", "a", 7, (e,), (), (), (), ("root", "a"))
        self.assertEqual(merge_branch_deltas({}, (bad,)).status, MergeStatus.REJECTED)

    def test_add_existing_target_conflicts(self):
        e = self.event("a1", DeltaOperation.ADD_NODE, "n", None, {})
        self.assertEqual(merge_branch_deltas({"n": 1}, (self.snap("a", [e]),)).status,
                         MergeStatus.CONFLICT)


if __name__ == "__main__":
    unittest.main()
