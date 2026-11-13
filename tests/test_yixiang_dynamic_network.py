import unittest
from prototype.yixiang_dynamic_network import (
    DynamicDecision, DynamicSnapshot, Phase, PhaseEvidence,
    RelationTransition, audit_dynamic_network,
)


def snap(sid, step, state, relations, evidence=None):
    return DynamicSnapshot(sid, "subject-1", step, state, "ctx",
                           tuple(relations), (evidence or f"src-{sid}",))


def phase(kind, sid, relation, window, outcome, ref):
    return PhaseEvidence(kind, sid, relation, window, outcome, ref)


class DynamicNetworkAuditTests(unittest.TestCase):
    def test_full_qiong_bian_tong_jiu_path_enters_human_review(self):
        snapshots = (snap("s1", 1, "A", ("old",)), snap("s2", 2, "B", ("new",)),
                     snap("s3", 3, "B", ("new",)), snap("s4", 4, "B", ("new",)))
        transitions = (RelationTransition("e1", "subject-1", "s1", "s2",
            "old path blocked", "reorganization", ("new",), ("event-e1",)),)
        evidence = (
            phase(Phase.QIONG, "s1", "old", "w1", "failed", "phase-q"),
            phase(Phase.BIAN, "s2", "new", "w2", "changed", "phase-b"),
            phase(Phase.TONG, "s2", "new", "w2", "viable", "phase-t"),
            phase(Phase.JIU, "s3", "new", "w3", "maintained", "phase-j1"),
            phase(Phase.JIU, "s4", "new", "w4", "maintained", "phase-j2"),
        )
        result = audit_dynamic_network(snapshots, transitions, evidence)
        self.assertEqual(result.decision, DynamicDecision.HUMAN_REVIEW)
        self.assertEqual(result.durable_relation_signatures, ("new",))
        self.assertEqual(result.reason_codes, ())

    def test_recurrent_state_signature_is_allowed(self):
        snapshots = (snap("s1", 1, "A", ("r",)), snap("s2", 2, "B", ("r2",)),
                     snap("s3", 3, "A", ("r",)))
        self.assertEqual(audit_dynamic_network(snapshots, (), ()).decision,
                         DynamicDecision.HUMAN_REVIEW)

    def test_transition_must_move_forward_in_time(self):
        snapshots = (snap("s1", 1, "A", ("r",)), snap("s2", 2, "B", ("r2",)))
        event = RelationTransition("e", "subject-1", "s2", "s1", "trigger",
                                   "change", ("r",), ("ev",))
        result = audit_dynamic_network(snapshots, (event,), ())
        self.assertIn("TRANSITION_TIME_ORDER_INVALID", result.reason_codes)

    def test_unknown_snapshot_is_blocked(self):
        snapshots = (snap("s1", 1, "A", ("r",)),)
        event = RelationTransition("e", "subject-1", "s1", "missing", "trigger",
                                   "change", ("r",), ("ev",))
        self.assertIn("TRANSITION_REFERENCES_UNKNOWN_SNAPSHOT",
                      audit_dynamic_network(snapshots, (event,), ()).reason_codes)

    def test_bian_requires_incoming_change_evidence(self):
        snapshots = (snap("s1", 1, "A", ("r",)),)
        evidence = (phase(Phase.BIAN, "s1", "r", "w1", "changed", "phase"),)
        self.assertIn("BIAN_REQUIRES_EVIDENCED_INCOMING_CHANGE",
                      audit_dynamic_network(snapshots, (), evidence).reason_codes)

    def test_tong_requires_relation_present_in_snapshot(self):
        snapshots = (snap("s1", 1, "A", ("r",)),)
        evidence = (phase(Phase.TONG, "s1", "absent", "w1", "viable", "phase"),)
        self.assertIn("TONG_REQUIRES_OBSERVED_VIABLE_RELATION",
                      audit_dynamic_network(snapshots, (), evidence).reason_codes)

    def test_jiu_requires_distinct_windows(self):
        snapshots = (snap("s1", 1, "A", ("r",)), snap("s2", 2, "A", ("r",)))
        evidence = (phase(Phase.JIU, "s1", "r", "same", "maintained", "p1"),
                    phase(Phase.JIU, "s2", "r", "same", "maintained", "p2"))
        self.assertIn("INSUFFICIENT_DURABILITY_WINDOWS:r",
                      audit_dynamic_network(snapshots, (), evidence).reason_codes)

    def test_evidence_reference_cannot_be_reused(self):
        snapshots = (snap("s1", 1, "A", ("r",)),)
        evidence = (phase(Phase.QIONG, "s1", "r", "w1", "failed", "src-s1"),)
        self.assertIn("EVIDENCE_REFERENCE_REUSED",
                      audit_dynamic_network(snapshots, (), evidence).reason_codes)

    def test_snapshot_subject_must_be_continuous(self):
        snapshots = (snap("s1", 1, "A", ("r",)),
                     DynamicSnapshot("s2", "other", 2, "B", "ctx", ("r",), ("src-s2",)))
        with self.assertRaises(ValueError):
            audit_dynamic_network(snapshots, (), ())

    def test_snapshot_order_must_be_strict(self):
        snapshots = (snap("s1", 1, "A", ("r",)), snap("s2", 1, "B", ("r2",)))
        with self.assertRaises(ValueError):
            audit_dynamic_network(snapshots, (), ())

    def test_phase_evidence_cannot_reference_unknown_snapshot(self):
        snapshots = (snap("s1", 1, "A", ("r",)),)
        evidence = (phase(Phase.QIONG, "missing", "r", "w1", "failed", "p"),)
        self.assertIn("PHASE_EVIDENCE_REFERENCES_UNKNOWN_SNAPSHOT",
                      audit_dynamic_network(snapshots, (), evidence).reason_codes)

    def test_cycle_is_not_mistaken_for_durability(self):
        snapshots = (snap("s1", 1, "A", ("r",)), snap("s2", 2, "B", ("x",)),
                     snap("s3", 3, "A", ("r",)))
        evidence = (phase(Phase.JIU, "s1", "r", "w1", "maintained", "p1"),
                    phase(Phase.JIU, "s3", "r", "w2", "maintained", "p2"))
        result = audit_dynamic_network(snapshots, (), evidence)
        self.assertEqual(result.durable_relation_signatures, ("r",))
        self.assertEqual(result.decision, DynamicDecision.HUMAN_REVIEW)

    def test_invalid_minimum_durability_is_rejected(self):
        with self.assertRaises(ValueError):
            audit_dynamic_network((snap("s1", 1, "A", ("r",)),), (), (),
                                  minimum_durable_windows=1)


if __name__ == "__main__":
    unittest.main()
