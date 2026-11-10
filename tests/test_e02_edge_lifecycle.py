import unittest

from prototype.e02_edge_lifecycle import (
    EdgeProposal, HyperedgeLifecycle, LifecycleError,
)


def proposal(edge_id, members=("a", "b", "c"), roles=("x", "y", "z"),
             gain=0.1, support=("s1", "s2", "s3"), counter=()):
    return EdgeProposal(edge_id, members, roles, "constraint",
                        support, counter, gain, 1.0)


class HyperedgeLifecycleTests(unittest.TestCase):
    def test_create_requires_independent_support_and_validation_gain(self):
        manager = HyperedgeLifecycle(min_support=3)
        with self.assertRaises(LifecycleError):
            manager.create(proposal("e", support=("s1", "s1", "s1")))
        with self.assertRaises(LifecycleError):
            manager.create(proposal("e", gain=0.0))

    def test_create_rejects_non_finite_gain_and_cost(self):
        manager = HyperedgeLifecycle()
        for gain in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(LifecycleError):
                manager.create(proposal("edge-" + str(gain), gain=gain))
        with self.assertRaises(LifecycleError):
            manager.create(EdgeProposal(
                "bad-cost", ("a", "b"), ("x", "y"), "constraint",
                ("s1", "s2", "s3"), (), 0.1, float("nan"),
            ))

    def test_observe_rejects_non_finite_metrics_without_mutation(self):
        manager = HyperedgeLifecycle()
        manager.create(proposal("e"))
        original = manager.edges["e"]
        for gain in (float("nan"), float("inf")):
            with self.assertRaises(LifecycleError):
                manager.observe("e", support_ids=(), counterexample_ids=(),
                                validation_gain=gain, cost=1.0)
        self.assertIs(manager.edges["e"], original)
        self.assertEqual(len(manager.audit_log()), 1)

    def test_merge_split_and_configuration_reject_non_finite_metrics(self):
        with self.assertRaises(ValueError):
            HyperedgeLifecycle(min_gain=float("nan"))
        manager = HyperedgeLifecycle()
        manager.create(proposal("a"))
        manager.create(proposal("b", members=("a", "b", "d")))
        with self.assertRaises(LifecycleError):
            manager.merge("a", "b", new_edge_id="m",
                          measured_validation_gain=float("nan"))
        self.assertIn("a", manager.edges)
        self.assertIn("b", manager.edges)

        split_manager = HyperedgeLifecycle()
        split_manager.create(proposal(
            "parent", members=("a", "b", "c", "d"),
            roles=("w", "x", "y", "z"),
        ))
        children = (
            proposal("left", members=("a", "b"), roles=("w", "x")),
            proposal("right", members=("c", "d"), roles=("y", "z"),
                     support=("s4", "s5", "s6")),
        )
        with self.assertRaises(LifecycleError):
            split_manager.split("parent", children,
                                measured_total_validation_gain=float("inf"))
        self.assertIn("parent", split_manager.edges)

    def test_create_rejects_conflicting_evidence_sets(self):
        manager = HyperedgeLifecycle()
        with self.assertRaises(LifecycleError):
            manager.create(proposal("e", support=("s1", "s2", "s3"),
                                    counter=("s1",)))

    def test_create_and_audit_event(self):
        manager = HyperedgeLifecycle()
        edge = manager.create(proposal("e"))
        self.assertEqual(edge.version, 1)
        self.assertEqual(manager.audit_log()[0]["op"], "CREATE")

    def test_merge_requires_overlap_roles_and_non_regression(self):
        manager = HyperedgeLifecycle(merge_jaccard=0.5)
        manager.create(proposal("a", members=("x", "y", "z")))
        manager.create(proposal("b", members=("x", "y", "w")))
        merged = manager.merge("a", "b", new_edge_id="m",
                               measured_validation_gain=0.09)
        self.assertEqual(set(merged.members), {"x", "y", "z", "w"})
        self.assertNotIn("a", manager.edges)
        self.assertIn("m", manager.edges)

    def test_merge_rejects_below_threshold_gain_after_stale_observations(self):
        manager = HyperedgeLifecycle(min_gain=0.01, prune_patience=5)
        manager.create(proposal("a"))
        manager.create(proposal("b", members=("a", "b", "d")))
        manager.observe("a", support_ids=(), counterexample_ids=("n1",),
                        validation_gain=-0.2, cost=1.0)
        manager.observe("b", support_ids=(), counterexample_ids=("n2",),
                        validation_gain=-0.1, cost=1.0)
        before = dict(manager.edges)
        with self.assertRaises(LifecycleError):
            manager.merge("a", "b", new_edge_id="m",
                          measured_validation_gain=-0.05)
        self.assertEqual(manager.edges, before)

    def test_merge_rejects_cost_overflow_without_mutation(self):
        manager = HyperedgeLifecycle()
        manager.create(EdgeProposal(
            "a", ("x", "y", "z"), ("r", "s", "t"), "constraint",
            ("s1", "s2", "s3"), (), 0.1, 1.0e308,
        ))
        manager.create(EdgeProposal(
            "b", ("x", "y", "w"), ("r", "s", "u"), "constraint",
            ("s4", "s5", "s6"), (), 0.1, 1.0e308,
        ))
        before = dict(manager.edges)
        with self.assertRaises(LifecycleError):
            manager.merge("a", "b", new_edge_id="m",
                          measured_validation_gain=0.1)
        self.assertEqual(manager.edges, before)

    def test_merge_rejects_role_mismatch(self):
        manager = HyperedgeLifecycle()
        manager.create(proposal("a"))
        manager.create(proposal("b", members=("a", "b", "d"),
                                roles=("r", "s", "t")))
        with self.assertRaises(LifecycleError):
            manager.merge("a", "b", new_edge_id="m",
                          measured_validation_gain=0.1)

    def test_split_requires_partition_and_gain(self):
        manager = HyperedgeLifecycle()
        manager.create(proposal("parent", members=("a", "b", "c", "d"),
                                roles=("w", "x", "y", "z")))
        children = (
            proposal("left", members=("a", "b"), roles=("w", "x"), gain=0.08),
            proposal("right", members=("c", "d"), roles=("y", "z"), gain=0.08,
                     support=("s4", "s5", "s6")),
        )
        result = manager.split("parent", children,
                               measured_total_validation_gain=0.15)
        self.assertEqual({e.edge_id for e in result}, {"left", "right"})
        self.assertNotIn("parent", manager.edges)

    def test_split_rejects_role_relabeling(self):
        manager = HyperedgeLifecycle()
        manager.create(proposal("parent", members=("a", "b", "c", "d"),
                                roles=("w", "x", "y", "z")))
        children = (
            proposal("left", members=("a", "b"), roles=("wrong", "x")),
            proposal("right", members=("c", "d"), roles=("y", "z"),
                     support=("s4", "s5", "s6")),
        )
        with self.assertRaises(LifecycleError):
            manager.split("parent", children,
                          measured_total_validation_gain=0.2)

    def test_split_rejects_incomplete_partition(self):
        manager = HyperedgeLifecycle()
        manager.create(proposal("parent", members=("a", "b", "c", "d"),
                                roles=("w", "x", "y", "z")))
        children = (proposal("left", members=("a", "b"), roles=("w", "x")),
                    proposal("right", members=("c",), roles=("y",)))
        with self.assertRaises(LifecycleError):
            manager.split("parent", children,
                          measured_total_validation_gain=0.2)

    def test_prune_requires_patience(self):
        manager = HyperedgeLifecycle(prune_patience=2)
        manager.create(proposal("e"))
        manager.observe("e", support_ids=(), counterexample_ids=("n1",),
                        validation_gain=0.0, cost=1.0)
        with self.assertRaises(LifecycleError):
            manager.prune("e")
        manager.observe("e", support_ids=(), counterexample_ids=("n2",),
                        validation_gain=0.0, cost=1.0)
        manager.prune("e")
        self.assertNotIn("e", manager.edges)

    def test_rollback_restores_previous_structure(self):
        manager = HyperedgeLifecycle()
        manager.create(proposal("e"))
        manager.observe("e", support_ids=("s4",), counterexample_ids=(),
                        validation_gain=0.12, cost=0.9)
        self.assertEqual(manager.edges["e"].version, 2)
        manager.rollback_last()
        self.assertEqual(manager.edges["e"].version, 1)
        self.assertEqual(len(manager.audit_log()), 1)


if __name__ == "__main__":
    unittest.main()
