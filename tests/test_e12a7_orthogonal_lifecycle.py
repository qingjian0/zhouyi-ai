import unittest

from prototype.e12a7_orthogonal_lifecycle import (
    CandidateVersion,
    EpistemicStatus,
    EventKind,
    InvocationPolicy,
    LifecycleEvent,
    OrthogonalLifecycleLedger,
    ScopeStatus,
    WorkflowStage,
)


def event(seq, event_id, ref, kind, **kwargs):
    return LifecycleEvent(sequence=seq, event_id=event_id,
                          candidate_ref=ref, kind=kind, **kwargs)


def ready_ledger():
    ledger = OrthogonalLifecycleLedger()
    ledger.register(CandidateVersion("primitive:delta", 1, "x-y>0", "dsl-v1"))
    ref = "primitive:delta@1"
    ledger.append(event(1, "propose", ref, EventKind.WORKFLOW_TRANSITION,
                        workflow_from=WorkflowStage.OBSERVED,
                        workflow_to=WorkflowStage.PROPOSED))
    ledger.append(event(2, "discriminate", ref, EventKind.WORKFLOW_TRANSITION,
                        workflow_from=WorkflowStage.PROPOSED,
                        workflow_to=WorkflowStage.DISCRIMINATION_PENDING))
    ledger.append(event(3, "train", ref, EventKind.WORKFLOW_TRANSITION,
                        workflow_from=WorkflowStage.DISCRIMINATION_PENDING,
                        workflow_to=WorkflowStage.TRAIN_SUPPORTED))
    ledger.append(event(4, "gate", ref, EventKind.WORKFLOW_TRANSITION,
                        workflow_from=WorkflowStage.TRAIN_SUPPORTED,
                        workflow_to=WorkflowStage.GATE_VALIDATED))
    ledger.append(event(5, "support-a", ref, EventKind.EPISTEMIC_ASSESSMENT,
                        scope_id="world-A", epistemic_status=EpistemicStatus.SUPPORTED,
                        evidence_ids=("gate-A-01",)))
    ledger.append(event(6, "scope-a", ref, EventKind.SCOPE_ASSESSMENT,
                        scope_id="world-A", scope_status=ScopeStatus.IN_SCOPE_SUPPORTED))
    return ledger


class OrthogonalLifecycleTests(unittest.TestCase):
    def test_allow_requires_all_three_dimensions(self):
        ledger = ready_ledger()
        state = ledger.snapshot("primitive:delta", 1, "world-A")
        self.assertEqual(state["invocation_policy"], InvocationPolicy.ALLOW.value)
        unknown = ledger.snapshot("primitive:delta", 1, "world-B")
        self.assertEqual(unknown["invocation_policy"], InvocationPolicy.ABSTAIN.value)

    def test_scope_evidence_isolated_between_worlds(self):
        ledger = ready_ledger()
        ref = "primitive:delta@1"
        ledger.append(event(7, "contradict-b", ref, EventKind.EPISTEMIC_ASSESSMENT,
                            scope_id="world-B",
                            epistemic_status=EpistemicStatus.REFUTED_IN_SCOPE,
                            evidence_ids=("counterexample-B",)))
        ledger.append(event(8, "scope-b", ref, EventKind.SCOPE_ASSESSMENT,
                            scope_id="world-B", scope_status=ScopeStatus.IN_SCOPE_SUPPORTED))
        self.assertEqual(ledger.snapshot("primitive:delta", 1, "world-A")["invocation_policy"],
                         InvocationPolicy.ALLOW.value)
        self.assertEqual(ledger.snapshot("primitive:delta", 1, "world-B")["invocation_policy"],
                         InvocationPolicy.ABSTAIN.value)

    def test_gate_validation_alone_does_not_allow_invocation(self):
        ledger = OrthogonalLifecycleLedger()
        ledger.register(CandidateVersion("p", 1, "a AND b", "dsl-v1"))
        ref = "p@1"
        ledger.append(event(1, "p1", ref, EventKind.WORKFLOW_TRANSITION,
                            workflow_from=WorkflowStage.OBSERVED,
                            workflow_to=WorkflowStage.PROPOSED))
        ledger.append(event(2, "p2", ref, EventKind.WORKFLOW_TRANSITION,
                            workflow_from=WorkflowStage.PROPOSED,
                            workflow_to=WorkflowStage.DISCRIMINATION_PENDING))
        ledger.append(event(3, "p3", ref, EventKind.WORKFLOW_TRANSITION,
                            workflow_from=WorkflowStage.DISCRIMINATION_PENDING,
                            workflow_to=WorkflowStage.TRAIN_SUPPORTED))
        ledger.append(event(4, "p4", ref, EventKind.WORKFLOW_TRANSITION,
                            workflow_from=WorkflowStage.TRAIN_SUPPORTED,
                            workflow_to=WorkflowStage.GATE_VALIDATED))
        self.assertEqual(ledger.snapshot("p", 1, "world-A")["invocation_policy"],
                         InvocationPolicy.ABSTAIN.value)

    def test_stale_and_illegal_workflow_transitions_are_rejected(self):
        ledger = ready_ledger()
        ref = "primitive:delta@1"
        with self.assertRaises(ValueError):
            ledger.append(event(7, "stale", ref, EventKind.WORKFLOW_TRANSITION,
                                workflow_from=WorkflowStage.PROPOSED,
                                workflow_to=WorkflowStage.REUSED))
        with self.assertRaises(ValueError):
            ledger.append(event(7, "skip", ref, EventKind.WORKFLOW_TRANSITION,
                                workflow_from=WorkflowStage.GATE_VALIDATED,
                                workflow_to=WorkflowStage.RETIRED))

    def test_supported_status_requires_evidence(self):
        ledger = ready_ledger()
        with self.assertRaises(ValueError):
            event(7, "no-evidence", "primitive:delta@1",
                  EventKind.EPISTEMIC_ASSESSMENT, scope_id="world-C",
                  epistemic_status=EpistemicStatus.SUPPORTED)

    def test_event_ids_and_sequence_are_append_only(self):
        ledger = ready_ledger()
        ref = "primitive:delta@1"
        with self.assertRaises(ValueError):
            ledger.append(event(7, "scope-a", ref, EventKind.SCOPE_ASSESSMENT,
                                scope_id="world-A", scope_status=ScopeStatus.IN_SCOPE_SUPPORTED))
        with self.assertRaises(ValueError):
            ledger.append(event(9, "gap", ref, EventKind.SCOPE_ASSESSMENT,
                                scope_id="world-C", scope_status=ScopeStatus.UNTESTED))

    def test_replay_is_deterministic(self):
        ledger = ready_ledger()
        first = ledger.replay()
        second = ledger.replay()
        self.assertEqual(first, second)

    def test_candidate_versions_are_immutable_and_distinct(self):
        ledger = OrthogonalLifecycleLedger()
        first = CandidateVersion("p", 1, "x>0", "dsl-v1")
        second = CandidateVersion("p", 2, "x>=0", "dsl-v1",
                                  parent_refs=("p@1",))
        ledger.register(first)
        ledger.register(second)
        with self.assertRaises(ValueError):
            ledger.register(first)
        with self.assertRaises(Exception):
            first.version = 3
        self.assertEqual(ledger.snapshot("p", 1, "A")["candidate_ref"], "p@1")
        self.assertEqual(ledger.snapshot("p", 2, "A")["candidate_ref"], "p@2")


if __name__ == "__main__":
    unittest.main()
