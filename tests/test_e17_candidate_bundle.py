import unittest

from prototype.e17_candidate_bundle import (
    BundleKind, CandidateBundle, CandidateContractError, CandidateRegistry,
    CandidateStateError, ChangeItem, ChangeLayer, ChangeOperation,
    EvidenceProvenance, EvidenceStance, GateDecision, LifecycleState,
    ResourceEstimate, ValidationReceipt, VersionConflictError,
    assess_evidence_independence, validate_candidate_bundle,
)


def make_bundle(**overrides):
    values = dict(
        bundle_id="bundle-1",
        schema_version="e17.candidate.v1",
        kind=BundleKind.PRIMITIVE_ONLY,
        created_at="2026-11-11T07:00:00Z",
        proposer_id="proposer-A",
        proposer_version="0.1",
        generation_method="unit-test",
        parent_version_refs=("structure-v1",),
        proposed_version_ref="structure-v2",
        evidence_snapshot_refs=("snapshot-1",),
        proposed_scope=(("domain", "synthetic"),),
        changes=(
            ChangeItem(
                change_id="change-1",
                target_layer=ChangeLayer.PRIMITIVE,
                operation=ChangeOperation.CREATE,
                target_refs=(),
                proposed_definition_ref="dsl://primitive/new",
                input_output_contract_ref="contract://primitive/new",
            ),
        ),
        predicted_effects=(("ood_accuracy", "improve"),),
        required_observations=("obs-1",),
        validation_plan_refs=("plan-1",),
        resource_estimate=ResourceEstimate(wall_clock_ms=10.0, peak_memory_bytes=1024),
        risk_score=0.2,
        provenance=(),
    )
    values.update(overrides)
    return CandidateBundle(**values)


def make_receipt(bundle, **overrides):
    values = dict(
        receipt_id="receipt-1",
        bundle_id=bundle.bundle_id,
        bundle_digest=bundle.content_digest,
        parent_version_refs=bundle.parent_version_refs,
        evaluator_id="independent-evaluator",
        evaluation_partition_id="gate-worlds-v1",
        independent_gate=True,
        decision=GateDecision.PASS,
        metrics=(("accuracy", 0.9),),
    )
    values.update(overrides)
    return ValidationReceipt(**values)


class CandidateBundleContractTests(unittest.TestCase):
    def test_digest_is_stable(self):
        self.assertEqual(make_bundle().content_digest, make_bundle().content_digest)

    def test_digest_changes_when_semantics_change(self):
        a = make_bundle()
        b = make_bundle(risk_score=0.3)
        self.assertNotEqual(a.content_digest, b.content_digest)

    def test_valid_bundle_passes_static_contract(self):
        validate_candidate_bundle(make_bundle())

    def test_nan_risk_is_rejected(self):
        with self.assertRaises(CandidateContractError):
            validate_candidate_bundle(make_bundle(risk_score=float("nan")))

    def test_infinite_resource_estimate_is_rejected(self):
        bundle = make_bundle(resource_estimate=ResourceEstimate(wall_clock_ms=float("inf")))
        with self.assertRaises(CandidateContractError):
            validate_candidate_bundle(bundle)

    def test_duplicate_change_ids_are_rejected(self):
        item = make_bundle().changes[0]
        with self.assertRaises(CandidateContractError):
            validate_candidate_bundle(make_bundle(changes=(item, item)))

    def test_bundle_kind_must_match_changed_layers(self):
        item = make_bundle().changes[0]
        relation = ChangeItem(
            change_id="change-2", target_layer=ChangeLayer.RELATION,
            operation=ChangeOperation.CREATE, target_refs=(),
            proposed_definition_ref="dsl://relation/new",
            input_output_contract_ref="contract://relation/new",
        )
        with self.assertRaises(CandidateContractError):
            validate_candidate_bundle(make_bundle(
                kind=BundleKind.PRIMITIVE_ONLY, changes=(item, relation)
            ))

    def test_unknown_change_dependency_is_rejected(self):
        item = make_bundle().changes[0]
        item = ChangeItem(**{**item.__dict__, "depends_on_change_ids": ("missing",)})
        with self.assertRaises(CandidateContractError):
            validate_candidate_bundle(make_bundle(changes=(item,)))

    def test_change_dependency_cycle_is_rejected(self):
        a = ChangeItem("a", ChangeLayer.PRIMITIVE, ChangeOperation.CREATE, (),
                       "dsl://a", "contract://a", depends_on_change_ids=("b",))
        b = ChangeItem("b", ChangeLayer.RELATION, ChangeOperation.CREATE, (),
                       "dsl://b", "contract://b", depends_on_change_ids=("a",))
        with self.assertRaises(CandidateContractError):
            validate_candidate_bundle(make_bundle(
                kind=BundleKind.CROSS_LAYER, changes=(a, b)
            ))


class EvidenceIndependenceTests(unittest.TestCase):
    def test_same_source_group_counts_once(self):
        records = (
            EvidenceProvenance("e1", EvidenceStance.SUPPORTS, source_group_id="source-A"),
            EvidenceProvenance("e2", EvidenceStance.SUPPORTS, source_group_id="source-A"),
        )
        report = assess_evidence_independence(records)
        self.assertEqual(report.independent_support_groups, 1)

    def test_shared_batch_connects_different_source_groups(self):
        records = (
            EvidenceProvenance("e1", EvidenceStance.SUPPORTS,
                               source_group_id="source-A", acquisition_batch_id="batch-1"),
            EvidenceProvenance("e2", EvidenceStance.SUPPORTS,
                               source_group_id="source-B", acquisition_batch_id="batch-1"),
            EvidenceProvenance("e3", EvidenceStance.SUPPORTS,
                               source_group_id="source-C", acquisition_batch_id="batch-2"),
        )
        report = assess_evidence_independence(records)
        self.assertEqual(report.independent_support_groups, 2)

    def test_missing_provenance_is_unknown_not_independent(self):
        records = (
            EvidenceProvenance("e1", EvidenceStance.SUPPORTS),
            EvidenceProvenance("e2", EvidenceStance.SUPPORTS),
        )
        report = assess_evidence_independence(records)
        self.assertEqual(report.independent_support_groups, 0)
        self.assertEqual(report.unknown_provenance_evidence_ids, ("e1", "e2"))

    def test_support_and_counterexample_groups_are_separate(self):
        records = (
            EvidenceProvenance("s1", EvidenceStance.SUPPORTS, source_group_id="src-1"),
            EvidenceProvenance("c1", EvidenceStance.CONTRADICTS, source_group_id="src-2"),
        )
        report = assess_evidence_independence(records)
        self.assertEqual(report.independent_support_groups, 1)
        self.assertEqual(report.independent_counterexample_groups, 1)


class CandidateRegistryTests(unittest.TestCase):
    def setUp(self):
        self.bundle = make_bundle()
        self.registry = CandidateRegistry(
            active_version_refs=("structure-v1",),
            trusted_gate_evaluator_ids=("independent-evaluator", "proposer-A"),
        )
        self.registry.propose(self.bundle)
        self.registry.static_validate(self.bundle.bundle_id)

    def test_commit_requires_independent_gate(self):
        with self.assertRaises(CandidateStateError):
            self.registry.commit(self.bundle.bundle_id)

    def test_successful_gate_then_commit_replaces_parent(self):
        self.registry.submit_for_gate(self.bundle.bundle_id)
        self.registry.record_gate_receipt(make_receipt(self.bundle))
        published = self.registry.commit(self.bundle.bundle_id)
        self.assertEqual(published, "structure-v2")
        self.assertEqual(self.registry.state_of("bundle-1"), LifecycleState.COMMITTED)
        self.assertEqual(self.registry.active_version_refs, {"structure-v2"})

    def test_receipt_digest_must_match_frozen_bundle(self):
        self.registry.submit_for_gate(self.bundle.bundle_id)
        receipt = make_receipt(self.bundle, bundle_digest="wrong")
        with self.assertRaises(CandidateContractError):
            self.registry.record_gate_receipt(receipt)

    def test_evaluator_must_be_distinct_from_proposer(self):
        self.registry.submit_for_gate(self.bundle.bundle_id)
        receipt = make_receipt(self.bundle, evaluator_id=self.bundle.proposer_id)
        with self.assertRaises(CandidateContractError):
            self.registry.record_gate_receipt(receipt)

    def test_untrusted_gate_evaluator_is_rejected(self):
        self.registry.submit_for_gate(self.bundle.bundle_id)
        receipt = make_receipt(self.bundle, evaluator_id="unknown-evaluator")
        with self.assertRaises(CandidateContractError):
            self.registry.record_gate_receipt(receipt)

    def test_non_independent_gate_is_rejected(self):
        self.registry.submit_for_gate(self.bundle.bundle_id)
        receipt = make_receipt(self.bundle, independent_gate=False)
        with self.assertRaises(CandidateContractError):
            self.registry.record_gate_receipt(receipt)

    def test_non_finite_gate_metric_is_rejected(self):
        self.registry.submit_for_gate(self.bundle.bundle_id)
        receipt = make_receipt(self.bundle, metrics=(("accuracy", float("nan")),))
        with self.assertRaises(CandidateContractError):
            self.registry.record_gate_receipt(receipt)

    def test_stale_parent_prevents_commit_without_publishing(self):
        self.registry.submit_for_gate(self.bundle.bundle_id)
        self.registry.record_gate_receipt(make_receipt(self.bundle))
        self.registry.advance_version_projection(
            ("structure-v1",), "structure-v1-newer"
        )
        with self.assertRaises(VersionConflictError):
            self.registry.commit(self.bundle.bundle_id)
        self.assertEqual(self.registry.state_of("bundle-1"), LifecycleState.GATE_PASSED)
        self.assertEqual(self.registry.active_version_refs, {"structure-v1-newer"})
        self.assertEqual(self.registry.events[-1]["event"], "COMMIT_CONFLICT")

    def test_gate_fail_is_terminal(self):
        self.registry.submit_for_gate(self.bundle.bundle_id)
        self.registry.record_gate_receipt(
            make_receipt(self.bundle, decision=GateDecision.FAIL)
        )
        self.assertEqual(self.registry.state_of("bundle-1"), LifecycleState.GATE_FAILED)
        with self.assertRaises(CandidateStateError):
            self.registry.commit(self.bundle.bundle_id)

    def test_active_version_projection_is_read_only(self):
        with self.assertRaises(AttributeError):
            self.registry.active_version_refs = {"bypass"}

    def test_returned_audit_events_cannot_mutate_internal_history(self):
        event = self.registry.events[0]
        event["details"] = {"tampered": True}
        self.assertNotIn("details", self.registry.events[0])

    def test_lifecycle_events_are_append_only(self):
        self.registry.submit_for_gate(self.bundle.bundle_id)
        self.registry.record_gate_receipt(make_receipt(self.bundle))
        self.registry.commit(self.bundle.bundle_id)
        names = [event["event"] for event in self.registry.events]
        self.assertEqual(names, [
            "PROPOSED", "STATIC_VALID", "GATE_PENDING", "GATE_PASSED", "COMMITTED"
        ])


if __name__ == "__main__":
    unittest.main()
