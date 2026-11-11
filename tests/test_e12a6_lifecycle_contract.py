import unittest

from prototype.e12a6_lifecycle_contract import (
    Action, ActionType, Candidate, CandidateState, Evidence,
    LifecycleLedger, SplitRole,
)


def candidate():
    return Candidate(
        candidate_id="rel:greater-than",
        version=1,
        canonical_expression="x > y",
        proposer_family="relational",
        supporting_families=("relational", "residual"),
        input_types=("number", "number"),
        operator="GT",
        uncertainty=0.4,
        complexity=2,
        proposal_cost=0.1,
    )


def evidence(eid, role, *, commit=1, reveal=2):
    return Evidence(
        evidence_id=eid,
        episode_id="ep-1",
        world_family="finite-rule-world",
        split_role=role,
        observation_id=f"obs-{eid}",
        outcome="true",
        model_version="model-0",
        measurement_cost=0.2,
        prediction_commit_step=commit,
        label_visibility_step=reveal,
        provenance="unit-test",
    )


def promote_to_gate_validated(ledger, candidate_id):
    ledger.add_evidence(evidence("train-" + candidate_id, SplitRole.TRAIN))
    ledger.add_evidence(evidence("final-" + candidate_id, SplitRole.GATE_FINAL))
    ledger.apply(Action("propose-" + candidate_id, ActionType.PROPOSE, candidate_id, 1,
                        from_state=CandidateState.OBSERVED,
                        to_state=CandidateState.PROPOSED))
    ledger.apply(Action("discriminate-" + candidate_id,
                        ActionType.REQUEST_DISCRIMINATION, candidate_id, 1,
                        from_state=CandidateState.PROPOSED,
                        to_state=CandidateState.DISCRIMINATION_PENDING))
    ledger.apply(Action("train-" + candidate_id, ActionType.TRAIN_SUPPORT,
                        candidate_id, 1, evidence_ids=("train-" + candidate_id,),
                        from_state=CandidateState.DISCRIMINATION_PENDING,
                        to_state=CandidateState.TRAIN_SUPPORTED))
    ledger.apply(Action("gate-" + candidate_id, ActionType.GATE_VALIDATE,
                        candidate_id, 1, evidence_ids=("final-" + candidate_id,),
                        from_state=CandidateState.TRAIN_SUPPORTED,
                        to_state=CandidateState.GATE_VALIDATED))


class E12A6LifecycleContractTests(unittest.TestCase):
    def test_candidate_identity_is_versioned_and_immutable(self):
        item = candidate()
        self.assertEqual((item.candidate_id, item.version), ("rel:greater-than", 1))
        with self.assertRaises(Exception):
            item.version = 2

    def test_evidence_rejects_label_leakage_order(self):
        with self.assertRaises(ValueError):
            evidence("bad", SplitRole.TRAIN, commit=3, reveal=2)

    def test_candidate_moves_only_through_declared_transitions(self):
        ledger = LifecycleLedger()
        ledger.add_candidate(candidate())
        ledger.apply(Action("a1", ActionType.PROPOSE, "rel:greater-than", 1,
                            from_state=CandidateState.OBSERVED,
                            to_state=CandidateState.PROPOSED))
        self.assertEqual(
            ledger.candidates[("rel:greater-than", 1)].state,
            CandidateState.PROPOSED,
        )
        with self.assertRaises(ValueError):
            ledger.apply(Action("a2", ActionType.GATE_VALIDATE, "rel:greater-than", 1,
                                from_state=CandidateState.PROPOSED,
                                to_state=CandidateState.GATE_VALIDATED))

    def test_gate_validation_requires_gate_final_evidence(self):
        ledger = LifecycleLedger()
        ledger.add_candidate(candidate())
        ledger.add_evidence(evidence("train", SplitRole.TRAIN))
        ledger.add_evidence(evidence("dev", SplitRole.GATE_DEV))
        ledger.add_evidence(evidence("final", SplitRole.GATE_FINAL))
        transitions = [
            (ActionType.PROPOSE, CandidateState.OBSERVED, CandidateState.PROPOSED, ()),
            (ActionType.REQUEST_DISCRIMINATION, CandidateState.PROPOSED,
             CandidateState.DISCRIMINATION_PENDING, ()),
            (ActionType.TRAIN_SUPPORT, CandidateState.DISCRIMINATION_PENDING,
             CandidateState.TRAIN_SUPPORTED, ("train",)),
        ]
        for index, (kind, before, after, refs) in enumerate(transitions):
            ledger.apply(Action(f"step-{index}", kind, "rel:greater-than", 1,
                                evidence_ids=refs, from_state=before, to_state=after))
        with self.assertRaises(ValueError):
            ledger.apply(Action("gate-bad", ActionType.GATE_VALIDATE,
                                "rel:greater-than", 1, evidence_ids=("dev",),
                                from_state=CandidateState.TRAIN_SUPPORTED,
                                to_state=CandidateState.GATE_VALIDATED))
        ledger.apply(Action("gate-ok", ActionType.GATE_VALIDATE,
                            "rel:greater-than", 1, evidence_ids=("final",),
                            from_state=CandidateState.TRAIN_SUPPORTED,
                            to_state=CandidateState.GATE_VALIDATED))
        self.assertEqual(
            ledger.candidates[("rel:greater-than", 1)].state,
            CandidateState.GATE_VALIDATED,
        )

    def test_challenge_requires_locked_or_post_deploy_evidence(self):
        ledger = LifecycleLedger()
        ledger.add_candidate(candidate())
        promote_to_gate_validated(ledger, "rel:greater-than")
        ledger.add_evidence(evidence("dev", SplitRole.GATE_DEV))
        with self.assertRaises(ValueError):
            ledger.apply(Action("challenge", ActionType.CHALLENGE,
                                "rel:greater-than", 1, evidence_ids=("dev",),
                                from_state=CandidateState.GATE_VALIDATED,
                                to_state=CandidateState.CHALLENGED))

    def test_revision_creates_new_version_and_preserves_old(self):
        ledger = LifecycleLedger()
        old = candidate()
        ledger.add_candidate(old)
        promote_to_gate_validated(ledger, old.candidate_id)
        ledger.add_evidence(evidence("counter", SplitRole.LOCKED_TEST))
        ledger.apply(Action("challenge", ActionType.CHALLENGE, old.candidate_id, 1,
                            evidence_ids=("counter",),
                            from_state=CandidateState.GATE_VALIDATED,
                            to_state=CandidateState.CHALLENGED))
        ledger.apply(Action("revise", ActionType.REVISE, old.candidate_id, 1,
                            evidence_ids=("counter",),
                            from_state=CandidateState.CHALLENGED,
                            to_state=CandidateState.REVISED))
        new = ledger.create_revision(
            old.candidate_id, 1,
            canonical_expression="x - y > threshold",
            operator="THRESHOLD_DIFF",
            conditions=("threshold>=0",),
            proposer_family="residual-expansion",
            supporting_families=("residual-expansion",),
            input_types=("number", "number"),
            complexity=3,
            proposal_cost=0.3,
            evidence_ids=("counter",),
        )
        self.assertEqual(new.version, 2)
        self.assertEqual(new.state, CandidateState.REVALIDATION_PENDING)
        self.assertEqual(ledger.candidates[(old.candidate_id, 1)].state,
                         CandidateState.REVISED)
        self.assertEqual(ledger.candidates[(old.candidate_id, 2)].parent_refs,
                         ("rel:greater-than@1",))

    def test_duplicate_evidence_and_actions_are_rejected(self):
        ledger = LifecycleLedger()
        ledger.add_evidence(evidence("e1", SplitRole.TRAIN))
        with self.assertRaises(ValueError):
            ledger.add_evidence(evidence("e1", SplitRole.TRAIN))
        action = Action("a1", ActionType.MEASURE, evidence_ids=("e1",))
        ledger.apply(action)
        with self.assertRaises(ValueError):
            ledger.apply(action)


if __name__ == "__main__":
    unittest.main()
