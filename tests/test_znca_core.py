import unittest

from prototype.znca_core import (
    AnalogyMap, CognitiveState, Entity, Evidence, ObservationEvent,
    QueryStatus, Relation, RelationQuery, RoleBinding, StateError, audit_analogy,
)


def rel(assertion_id, relation_type, left, right, evidence="ev1",
        valid_from=1, valid_until=None):
    return Relation(
        assertion_id, relation_type,
        (RoleBinding("source", left), RoleBinding("target", right)),
        (evidence,), valid_from, valid_until,
    )


class ZNCACoreTests(unittest.TestCase):
    def setUp(self):
        self.state = CognitiveState()
        self.state.apply(ObservationEvent(
            "event-1", 1,
            evidence=(Evidence("ev1", "conversation://1", 1),),
            entities=(Entity("alice", "person"), Entity("bob", "person"),
                      Entity("carol", "person")),
            relations=(rel("r1", "trusts", "alice", "bob"),
                       rel("r2", "trusts", "carol", "bob")),
        ))

    def test_event_sourcing_and_provenance(self):
        found = self.state.query(RelationQuery("trusts", (("target", "bob"),)))
        self.assertEqual(found.status, QueryStatus.FOUND)
        self.assertEqual({r.assertion_id for r in found.relations}, {"r1", "r2"})
        self.assertEqual(self.state.source_refs(found.relations[0]), ("conversation://1",))
        self.assertEqual(len(self.state.event_ledger), 1)

    def test_role_direction_is_not_collapsed(self):
        found = self.state.query(RelationQuery("trusts", (("source", "bob"),)))
        self.assertEqual(found.status, QueryStatus.NOT_FOUND)
        self.assertEqual(found.relations, ())

    def test_temporal_validity(self):
        self.state.apply(ObservationEvent(
            "event-2", 5, retract_assertion_ids=("r1",)))
        self.assertEqual(len(self.state.query(RelationQuery("trusts"))), 1)

    def test_retraction_preserves_original_event(self):
        self.state.apply(ObservationEvent(
            "event-2", 5, retract_assertion_ids=("r1",)))
        self.assertEqual(len(self.state.event_ledger), 2)
        self.assertIn("r1", self.state.assertions)
        self.assertIn("r1", self.state.retracted)

    def test_unknown_evidence_rejected_atomically(self):
        bad = ObservationEvent(
            "event-bad", 2,
            relations=(rel("bad", "trusts", "alice", "bob", "missing"),))
        with self.assertRaises(StateError):
            self.state.apply(bad)
        self.assertNotIn("event-bad", self.state.event_ids)
        self.assertNotIn("bad", self.state.assertions)

    def test_duplicate_event_rejected(self):
        event = ObservationEvent("event-1", 1)
        with self.assertRaises(StateError):
            self.state.apply(event)

    def test_scan_budget_rejected(self):
        with self.assertRaises(StateError):
            self.state.query(RelationQuery("trusts"), scan_budget=0)
        result = self.state.query(RelationQuery("missing"), scan_budget=1)
        self.assertEqual(result.status, QueryStatus.BUDGET_EXHAUSTED)
        self.assertEqual(result.scanned, 1)

    def test_query_limit(self):
        found = self.state.query(RelationQuery("trusts", limit=1))
        self.assertEqual(len(found.relations), 1)
        self.assertEqual(found.status, QueryStatus.FOUND)

    def test_analogy_audit_preserves_roles_and_relations(self):
        source = [rel("s1", "supports", "s-agent", "s-object")]
        target = [rel("t1", "enables", "t-agent", "t-object", "ev1")]
        mapping = AnalogyMap(
            (("s-agent", "t-agent"), ("s-object", "t-object")),
            (("supports", "enables"),),
            (("source", "source"), ("target", "target")),
            ("ev1",), "toy-domain-transfer",
        )
        audit = audit_analogy(source, target, mapping)
        self.assertEqual(audit.preserved_relations, 1)
        self.assertEqual(audit.preservation_ratio, 1.0)

    def test_analogy_role_reversal_is_detected(self):
        source = [rel("s1", "supports", "s-agent", "s-object")]
        target = [rel("t1", "enables", "t-agent", "t-object", "ev1")]
        mapping = AnalogyMap(
            (("s-agent", "t-agent"), ("s-object", "t-object")),
            (("supports", "enables"),),
            (("source", "target"), ("target", "source")),
            ("ev1",), "role-reversal-negative",
        )
        audit = audit_analogy(source, target, mapping)
        self.assertEqual(audit.preserved_relations, 0)
        self.assertEqual(len(audit.violations), 1)


if __name__ == "__main__":
    unittest.main()
