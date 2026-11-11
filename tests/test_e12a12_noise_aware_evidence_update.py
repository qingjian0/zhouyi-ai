import unittest
from prototype.e12a7_orthogonal_lifecycle import CandidateVersion, EpistemicStatus, OrthogonalLifecycleLedger
from prototype.e12a11_active_measurement_evidence import BudgetedMeasurementExecutor, MeasurementRequest, MeasurementSigner
from prototype.e12a12_noise_aware_evidence_update import LikelihoodModel, SequentialEvidenceUpdater

def req(i, scope_digest="scope-d"):
    return MeasurementRequest(f"req-{i}", "primitive:shape@1", "world-A", scope_digest,
        "probe-v1", f"target-{i}", "params-v1", 1.0, 1.0)

class NoiseAwareEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.signer = MeasurementSigner.generate("measurement-service", "key-1")
        self.ledger = OrthogonalLifecycleLedger()
        self.ledger.register(CandidateVersion("primitive:shape", 1,
            "candidate predicts positive relation", "dsl-v1"))
        self.model = LikelihoodModel.create(model_id="shape-probe", model_version="1",
            candidate_ref="primitive:shape@1", scope_id="world-A", scope_digest="scope-d",
            protocol_id="probe-v1", candidate_probabilities={"yes": 0.8, "no": 0.2},
            alternative_probabilities={"yes": 0.2, "no": 0.8}, alpha=0.05, beta=0.05)
        self.updater = SequentialEvidenceUpdater(self.model, self.signer.public_key_bytes(),
            executor_id="measurement-service", key_id="key-1", ledger=self.ledger)

    def executor(self, outcome):
        return BudgetedMeasurementExecutor(self.signer,
            {"probe-v1": lambda target, params: (outcome, 0.5)},
            allowed_candidate_scopes={("primitive:shape@1", "world-A")}, budget=20)

    def test_one_noisy_counter_observation_does_not_refute_candidate(self):
        update = self.updater.update(self.executor("no").execute(req(1)))
        self.assertEqual(update.epistemic_status, EpistemicStatus.UNDERDETERMINED)
        self.assertAlmostEqual(update.cumulative_log_likelihood_ratio, -1.38629436112)
        self.assertEqual(self.updater.observation_count, 1)

    def test_repeated_candidate_consistent_observations_support(self):
        ex = self.executor("yes")
        updates = [self.updater.update(ex.execute(req(i))) for i in range(1, 4)]
        self.assertEqual(updates[-1].epistemic_status, EpistemicStatus.SUPPORTED)
        self.assertGreater(updates[-1].cumulative_log_likelihood_ratio, self.model.upper_threshold)
        with self.assertRaises(ValueError):
            self.updater.update(ex.execute(req(4)))
        self.assertEqual(self.updater.observation_count, 3)

    def test_repeated_alternative_consistent_observations_refute_in_scope(self):
        ex = self.executor("no")
        updates = [self.updater.update(ex.execute(req(i))) for i in range(1, 4)]
        self.assertEqual(updates[-1].epistemic_status, EpistemicStatus.REFUTED_IN_SCOPE)

    def test_mixed_observations_accumulate_and_can_cancel(self):
        ex = BudgetedMeasurementExecutor(self.signer,
            {"probe-v1": lambda target, params: ("yes" if target.endswith("-1") else "no", 0.5)},
            allowed_candidate_scopes={("primitive:shape@1", "world-A")}, budget=20)
        first = self.updater.update(ex.execute(req(1)))
        second = self.updater.update(ex.execute(req(2)))
        self.assertAlmostEqual(second.cumulative_log_likelihood_ratio, 0.0)
        self.assertEqual(second.epistemic_status, EpistemicStatus.UNDERDETERMINED)

    def test_wrong_scope_digest_rejected_without_state_update(self):
        receipt = self.executor("yes").execute(req(1, scope_digest="other"))
        with self.assertRaises(ValueError):
            self.updater.update(receipt)
        self.assertEqual(self.updater.observation_count, 0)

    def test_unknown_outcome_rejected(self):
        with self.assertRaises(ValueError):
            self.updater.update(self.executor("maybe").execute(req(1)))
        self.assertEqual(self.updater.observation_count, 0)

    def test_model_requires_normalized_nonzero_distributions(self):
        args = dict(model_id="m", model_version="1", candidate_ref="p@1",
            scope_id="s", scope_digest="d", protocol_id="p")
        with self.assertRaises(ValueError):
            LikelihoodModel.create(**args, candidate_probabilities={"yes": 0.7, "no": 0.2},
                alternative_probabilities={"yes": 0.5, "no": 0.5})
        with self.assertRaises(ValueError):
            LikelihoodModel.create(**args, candidate_probabilities={"yes": 1.0, "no": 0.0},
                alternative_probabilities={"yes": 0.5, "no": 0.5})

    def test_lifecycle_event_is_scope_local(self):
        update = self.updater.update(self.executor("yes").execute(req(1)))
        state_a = self.ledger.snapshot("primitive:shape", 1, "world-A")
        state_b = self.ledger.snapshot("primitive:shape", 1, "world-B")
        self.assertEqual(state_a["epistemic_status"], update.epistemic_status.value)
        self.assertEqual(state_b["epistemic_status"], EpistemicStatus.UNKNOWN.value)

if __name__ == "__main__":
    unittest.main()
