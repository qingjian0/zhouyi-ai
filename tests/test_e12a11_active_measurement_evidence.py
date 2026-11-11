import unittest
from dataclasses import replace
from prototype.e12a11_active_measurement_evidence import (
    BudgetedMeasurementExecutor, MeasurementRequest, MeasurementSigner,
    MeasurementStatus, MeasurementReplayGuard, verify_receipt, receipt_to_evidence,
)

def request(**kw):
    data = dict(request_id="req-1", candidate_ref="rule@1", scope_id="scope-a",
        scope_digest="scope-digest-a", protocol_id="probe-v1", target_digest="target-a",
        params_digest="params-a", estimated_cost=1.0, max_cost=2.0)
    data.update(kw)
    return MeasurementRequest(**data)

class ActiveMeasurementEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.signer = MeasurementSigner.generate("measurement-service", "key-a")
        self.executor = BudgetedMeasurementExecutor(self.signer,
            {"probe-v1": lambda target, params: ("observed-yes", 1.25)},
            allowed_candidate_scopes={("rule@1", "scope-a")}, budget=5.0)

    def test_executor_observes_and_signs_result(self):
        receipt = self.executor.execute(request())
        self.assertEqual(receipt.status, MeasurementStatus.SELECT.value)
        self.assertEqual(receipt.outcome, "observed-yes")
        self.assertEqual(self.executor.remaining_budget, 3.75)
        self.assertTrue(verify_receipt(receipt, self.signer.public_key_bytes()))

    def test_learner_cannot_supply_outcome(self):
        self.assertNotIn("outcome", request().payload())

    def test_scope_mismatch_is_rejected_without_execution(self):
        receipt = self.executor.execute(request(scope_id="other"))
        self.assertEqual(receipt.status, MeasurementStatus.INVALID_INPUT.value)
        self.assertEqual(self.executor.remaining_budget, 5.0)

    def test_budget_exhaustion_is_signed_but_not_evidence(self):
        receipt = self.executor.execute(request(estimated_cost=9, max_cost=10))
        self.assertEqual(receipt.status, MeasurementStatus.BUDGET_EXHAUSTED.value)
        with self.assertRaises(ValueError):
            receipt_to_evidence(receipt, self.signer.public_key_bytes(),
                expected_scope_digest="scope-digest-a", replay_guard=MeasurementReplayGuard())

    def test_non_discriminating_measurement_is_not_evidence(self):
        ex = BudgetedMeasurementExecutor(self.signer,
            {"probe-v1": lambda target, params: ("NO_DISCRIMINATION", 0.5)},
            allowed_candidate_scopes={("rule@1", "scope-a")}, budget=2)
        receipt = ex.execute(request())
        self.assertEqual(receipt.status, MeasurementStatus.NO_DISCRIMINATING_MEASUREMENT.value)
        with self.assertRaises(ValueError):
            receipt_to_evidence(receipt, self.signer.public_key_bytes(),
                expected_scope_digest="scope-digest-a", replay_guard=MeasurementReplayGuard())

    def test_signed_observation_converts_to_scoped_evidence(self):
        receipt = self.executor.execute(request())
        evidence = receipt_to_evidence(receipt, self.signer.public_key_bytes(),
            expected_scope_digest="scope-digest-a", replay_guard=MeasurementReplayGuard())
        self.assertEqual(evidence.outcome, "observed-yes")
        self.assertEqual(evidence.candidate_ref, "rule@1")

    def test_tampering_and_context_substitution_fail(self):
        receipt = self.executor.execute(request())
        with self.assertRaises(ValueError):
            verify_receipt(replace(receipt, outcome="forged"), self.signer.public_key_bytes())
        with self.assertRaises(ValueError):
            verify_receipt(receipt, self.signer.public_key_bytes(),
                expected_context={"scope_digest": "wrong"})

    def test_replay_and_duplicate_request_are_rejected(self):
        receipt = self.executor.execute(request())
        guard = MeasurementReplayGuard()
        verify_receipt(receipt, self.signer.public_key_bytes(), replay_guard=guard)
        with self.assertRaises(ValueError):
            verify_receipt(receipt, self.signer.public_key_bytes(), replay_guard=guard)
        with self.assertRaises(ValueError):
            self.executor.execute(request())

    def test_actual_cost_ceiling_is_enforced(self):
        ex = BudgetedMeasurementExecutor(self.signer,
            {"probe-v1": lambda target, params: ("yes", 3.0)},
            allowed_candidate_scopes={("rule@1", "scope-a")}, budget=5)
        receipt = ex.execute(request(max_cost=2))
        self.assertEqual(receipt.status, MeasurementStatus.EXECUTION_FAILED.value)
        self.assertEqual(ex.remaining_budget, 5)

    def test_actual_cost_overrun_consumes_remaining_budget(self):
        ex = BudgetedMeasurementExecutor(self.signer,
            {"probe-v1": lambda target, params: ("observed", 4.0)},
            allowed_candidate_scopes={("rule@1", "scope-a")}, budget=2)
        receipt = ex.execute(request(estimated_cost=1, max_cost=5))
        self.assertEqual(receipt.status, MeasurementStatus.BUDGET_EXHAUSTED.value)
        self.assertEqual(receipt.actual_cost, 4.0)
        self.assertEqual(ex.remaining_budget, 0.0)

    def test_failed_protocol_does_not_create_evidence(self):
        ex = BudgetedMeasurementExecutor(self.signer,
            {"probe-v1": lambda target, params: (_ for _ in ()).throw(RuntimeError())},
            allowed_candidate_scopes={("rule@1", "scope-a")}, budget=5)
        receipt = ex.execute(request())
        self.assertEqual(receipt.status, MeasurementStatus.EXECUTION_FAILED.value)

if __name__ == "__main__":
    unittest.main()
