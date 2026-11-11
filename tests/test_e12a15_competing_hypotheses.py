import unittest
from dataclasses import replace

from prototype.e12a11_active_measurement_evidence import (
    BudgetedMeasurementExecutor, MeasurementRequest, MeasurementSigner,
)
from prototype.e12a15_competing_hypotheses import (
    CompetingHypothesis, CompetingHypothesisPortfolio, ExplanationKind,
    MeasurementPlan, SelectionStatus, propose_revision,
)
from prototype.e12a7_orthogonal_lifecycle import CandidateVersion


def dist(**values):
    return tuple(sorted(values.items()))


def fixture():
    hypotheses = (
        CompetingHypothesis("environment", ExplanationKind.ENVIRONMENT_SHIFT, "cause:environment@1",
            0.25, (("probe", dist(yes=0.9, no=0.1)), ("weak", dist(yes=0.55, no=0.45)))),
        CompetingHypothesis("scope", ExplanationKind.SCOPE_TOO_BROAD, "cause:scope@1",
            0.25, (("probe", dist(yes=0.1, no=0.9)), ("weak", dist(yes=0.55, no=0.45)))),
        CompetingHypothesis("noise", ExplanationKind.MEASUREMENT_NOISE, "cause:noise@1",
            0.25, (("probe", dist(yes=0.5, no=0.5)), ("weak", dist(yes=0.5, no=0.5)))),
        CompetingHypothesis("composition", ExplanationKind.COMPOSITION_ERROR, "cause:composition@1",
            0.25, (("probe", dist(yes=0.2, no=0.8)), ("weak", dist(yes=0.45, no=0.55)))),
    )
    plans = (
        MeasurementPlan("probe", "probe-v1", "target-probe", "params-v1", 1.0, 1.5),
        MeasurementPlan("weak", "weak-v1", "target-weak", "params-v1", 0.5, 0.5),
    )
    return hypotheses, plans


class CompetingHypothesisTests(unittest.TestCase):
    def setUp(self):
        self.hypotheses, self.plans = fixture()
        self.portfolio = CompetingHypothesisPortfolio(anchor_candidate_ref="candidate:root@1",
            scope_id="world-A", scope_digest="scope-digest-A",
            hypotheses=self.hypotheses, plans=self.plans)

    def test_cost_aware_information_gain_selects_discriminating_measurement(self):
        decision = self.portfolio.select_measurement(request_id="req-1", remaining_budget=2)
        self.assertEqual(decision.status, SelectionStatus.SELECT)
        self.assertIsNotNone(decision.request)
        self.assertGreater(decision.expected_information_gain_bits, 0)

    def test_non_discriminating_measurements_cause_abstention(self):
        hypotheses = tuple(replace(h, predictions=(("probe", dist(yes=0.5, no=0.5)),))
                           for h in self.hypotheses)
        plan = (MeasurementPlan("probe", "probe-v1", "target", "params", 1, 1),)
        portfolio = CompetingHypothesisPortfolio(anchor_candidate_ref="candidate:root@1",
            scope_id="world-A", scope_digest="scope-digest-A", hypotheses=hypotheses, plans=plan)
        decision = portfolio.select_measurement(request_id="req-x", remaining_budget=2)
        self.assertEqual(decision.status, SelectionStatus.NO_DISCRIMINATING_MEASUREMENT)
        self.assertIsNone(decision.request)

    def test_budget_exhaustion_is_explicit(self):
        decision = self.portfolio.select_measurement(request_id="req-2", remaining_budget=0.1)
        self.assertEqual(decision.status, SelectionStatus.BUDGET_EXHAUSTED)

    def test_signed_receipt_updates_only_relative_posterior(self):
        decision = self.portfolio.select_measurement(request_id="req-3", remaining_budget=2)
        request = decision.request
        plan = next(p for p in self.plans if p.measurement_id == decision.measurement_id)
        signer = MeasurementSigner.generate("measurement-service", "key-a")
        executor = BudgetedMeasurementExecutor(signer,
            {plan.protocol_id: lambda target, params: ("yes", 0.75)},
            allowed_candidate_scopes={(request.candidate_ref, request.scope_id)}, budget=3)
        receipt = executor.execute(request)
        update = self.portfolio.update(request, receipt, signer.public_key_bytes(),
            executor_id="measurement-service", key_id="key-a")
        self.assertEqual(update.scope_id, "world-A")
        self.assertEqual(update.receipt_id, receipt.receipt_id)
        self.assertEqual(len(update.evidence_lineage), 1)
        self.assertAlmostEqual(sum(p for _, p in update.posterior), 1.0)
        self.assertLessEqual(update.entropy_after_bits, update.entropy_before_bits)

    def test_receipt_tampering_is_rejected(self):
        decision = self.portfolio.select_measurement(request_id="req-4", remaining_budget=2)
        request = decision.request
        plan = next(p for p in self.plans if p.measurement_id == decision.measurement_id)
        signer = MeasurementSigner.generate("measurement-service", "key-a")
        executor = BudgetedMeasurementExecutor(signer,
            {plan.protocol_id: lambda target, params: ("yes", 0.5)},
            allowed_candidate_scopes={(request.candidate_ref, request.scope_id)}, budget=3)
        receipt = executor.execute(request)
        with self.assertRaises(ValueError):
            self.portfolio.update(request, replace(receipt, outcome="forged"),
                signer.public_key_bytes(), executor_id="measurement-service", key_id="key-a")

    def test_cross_scope_receipt_is_rejected(self):
        decision = self.portfolio.select_measurement(request_id="req-5", remaining_budget=2)
        request = decision.request
        plan = next(p for p in self.plans if p.measurement_id == decision.measurement_id)
        signer = MeasurementSigner.generate("measurement-service", "key-a")
        executor = BudgetedMeasurementExecutor(signer,
            {plan.protocol_id: lambda target, params: ("yes", 0.5)},
            allowed_candidate_scopes={(request.candidate_ref, "world-B")}, budget=3)
        receipt = executor.execute(request)
        with self.assertRaises(ValueError):
            self.portfolio.update(request, receipt, signer.public_key_bytes(),
                executor_id="measurement-service", key_id="key-a")

    def test_unknown_outcome_does_not_consume_posterior(self):
        decision = self.portfolio.select_measurement(request_id="req-6", remaining_budget=2)
        request = decision.request
        plan = next(p for p in self.plans if p.measurement_id == decision.measurement_id)
        signer = MeasurementSigner.generate("measurement-service", "key-a")
        executor = BudgetedMeasurementExecutor(signer,
            {plan.protocol_id: lambda target, params: ("other", 0.5)},
            allowed_candidate_scopes={(request.candidate_ref, request.scope_id)}, budget=3)
        receipt = executor.execute(request)
        before = self.portfolio.posterior
        with self.assertRaises(ValueError):
            self.portfolio.update(request, receipt, signer.public_key_bytes(),
                executor_id="measurement-service", key_id="key-a")
        self.assertEqual(self.portfolio.posterior, before)

    def test_revision_creates_new_version_with_parent_lineage(self):
        parent = CandidateVersion("primitive:shape", 2, "old", "dsl-v1")
        child = propose_revision(parent, new_definition="narrowed scope", grammar_version="dsl-v1")
        self.assertEqual(child.version, 3)
        self.assertEqual(child.parent_refs, ("primitive:shape@2",))
        self.assertEqual(parent.definition, "old")


if __name__ == "__main__":
    unittest.main()
