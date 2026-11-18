import unittest

from prototype.csg_branch_delta import (
    BranchDelta, BranchSnapshot, DeltaOperation, MergeStatus,
    canonical_hash, merge_branch_deltas,
)


class BranchDeltaTests(unittest.TestCase):
    def event(self, event_id, op, target, before, value, version=8, parent=None):
        return BranchDelta(event_id, op, target, before, value, ("evidence:fixture",), parent, version)

    def snap(self, branch, events, reads=(), base=None):
        base = {} if base is None else base
        return BranchSnapshot("parent-1", canonical_hash(base), branch, 7, tuple(events), tuple(reads),
                              tuple(sorted({e.target_ref for e in events})),
                              tuple(sorted({r for e in events for r in e.evidence_refs})),
                              ("root", branch))

    def test_disjoint_deltas_merge_deterministically(self):
        base = {"n:1": {"kind": "node"}, "n:2": {"kind": "node"}}
        a = self.event("a1", DeltaOperation.UPDATE_ATTRIBUTE, "n:1",
                       canonical_hash(base["n:1"]), {"kind": "node", "x": 1})
        b = self.event("b1", DeltaOperation.REMOVE_NODE, "n:2",
                       canonical_hash(base["n:2"]), None)
        result = merge_branch_deltas(base, (self.snap("a", [a], base=base), self.snap("b", [b], base=base)))
        self.assertEqual(result.status, MergeStatus.MERGED)
        self.assertEqual(dict(result.state), {"n:1": {"kind": "node", "x": 1}})
        self.assertEqual(result.applied_event_ids, ("a1", "b1"))

    def test_sequential_same_branch_edits_are_applied_in_order(self):
        base = {"n": 0}
        first = self.event("a1", DeltaOperation.UPDATE_ATTRIBUTE, "n",
                           canonical_hash(0), 1, version=8)
        second = self.event("a2", DeltaOperation.UPDATE_ATTRIBUTE, "n",
                            canonical_hash(1), 2, version=9, parent="a1")
        result = merge_branch_deltas(base, (self.snap("a", [first, second], base=base),))
        self.assertEqual(result.status, MergeStatus.MERGED)
        self.assertEqual(dict(result.state), {"n": 2})

    def test_delta_payload_is_deeply_immutable(self):
        source = {"nested": {"value": 1}}
        e = self.event("a1", DeltaOperation.ADD_NODE, "n", None, source)
        source["nested"]["value"] = 99
        returned = e.after_value
        returned["nested"]["value"] = 42
        self.assertEqual(e.after_value, {"nested": {"value": 1}})

    def test_declared_parent_hash_must_match_supplied_state(self):
        base = {"n": 1}
        wrong_parent = {"n": 2}
        e = self.event("a1", DeltaOperation.UPDATE_ATTRIBUTE, "n",
                       canonical_hash(1), 3)
        result = merge_branch_deltas(base, (self.snap("a", [e], base=wrong_parent),))
        self.assertEqual(result.status, MergeStatus.STALE)

    def test_delta_event_requires_provenance_reference(self):
        e = BranchDelta("a1", DeltaOperation.ADD_NODE, "n", None, {},
                        (), None, 8)
        result = merge_branch_deltas({}, (self.snap("a", [e]),))
        self.assertEqual(result.status, MergeStatus.REJECTED)

    def test_shared_parent_and_version_are_mandatory(self):
        a = self.snap("a", [])
        b = BranchSnapshot("other-parent", canonical_hash({}), "b", 7, (), (), (), (), ("root", "b"))
        self.assertEqual(merge_branch_deltas({}, (a, b)).status, MergeStatus.REJECTED)

    def test_same_target_write_is_conflict_not_last_writer_wins(self):
        base = {"n": 0}
        a = self.event("a1", DeltaOperation.UPDATE_ATTRIBUTE, "n", canonical_hash(0), 1)
        b = self.event("b1", DeltaOperation.UPDATE_ATTRIBUTE, "n", canonical_hash(0), 2)
        result = merge_branch_deltas(base, (self.snap("a", [a], base=base), self.snap("b", [b], base=base)))
        self.assertEqual(result.status, MergeStatus.CONFLICT)
        self.assertEqual(dict(result.state), base)

    def test_stale_before_hash_rejected(self):
        base = {"n": 3}
        e = self.event("a1", DeltaOperation.UPDATE_ATTRIBUTE, "n", canonical_hash(2), 4)
        result = merge_branch_deltas(base, (self.snap("a", [e], base={}),))
        self.assertEqual(result.status, MergeStatus.STALE)

    def test_write_read_dependency_conflict(self):
        base = {"n": 0}
        e = self.event("a1", DeltaOperation.UPDATE_ATTRIBUTE, "n", canonical_hash(0), 1)
        a = self.snap("a", [e], base=base)
        b = BranchSnapshot("parent-1", canonical_hash(base), "b", 7, (), ("n",), (), (), ("root", "b"))
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
        result = merge_branch_deltas({}, (self.snap("a", [a], base={}), self.snap("b", [b], base={})))
        self.assertEqual(result.status, MergeStatus.CONFLICT)

    def test_invalid_write_set_is_rejected(self):
        e = self.event("a1", DeltaOperation.ADD_NODE, "n", None, {})
        bad = BranchSnapshot("parent-1", canonical_hash({}), "a", 7, (e,), (), (), (), ("root", "a"))
        self.assertEqual(merge_branch_deltas({}, (bad,)).status, MergeStatus.REJECTED)

    def test_add_existing_target_conflicts(self):
        e = self.event("a1", DeltaOperation.ADD_NODE, "n", None, {})
        self.assertEqual(merge_branch_deltas({"n": 1}, (self.snap("a", [e], base={"n": 1}),)).status,
                         MergeStatus.CONFLICT)


if __name__ == "__main__":
    unittest.main()
