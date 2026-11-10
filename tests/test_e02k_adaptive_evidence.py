import unittest

from prototype.e02k_adaptive_evidence import (
    AdaptiveEvidenceController, EvidenceObservation,
)


OLD = ((0, 1, 2), 173)
NEW = ((0, 1, 3), 173)


class E02KAdaptiveEvidenceTests(unittest.TestCase):

    def test_rejects_non_finite_controller_parameters(self):
        with self.assertRaises(ValueError):
            AdaptiveEvidenceController(alpha=float("nan"))

    def test_rejects_noncanonical_relation_signature(self):
        state = AdaptiveEvidenceController()
        with self.assertRaises(ValueError):
            state.observe(EvidenceObservation(((1, 0), 173)), window=0)

    def test_rejects_repeated_or_reversed_window_ids(self):
        state = AdaptiveEvidenceController()
        state.observe(EvidenceObservation(OLD), window=3)
        with self.assertRaises(ValueError):
            state.observe(EvidenceObservation(OLD), window=3)
        with self.assertRaises(ValueError):
            state.observe(EvidenceObservation(OLD), window=2)

    def test_candidate_losses_can_reverse_accumulated_evidence(self):
        state = AdaptiveEvidenceController()
        state.observe(EvidenceObservation(OLD), window=0)
        positive = EvidenceObservation(NEW, candidate_wins=100)
        negative = EvidenceObservation(NEW, candidate_losses=100)
        self.assertEqual(state.observe(positive, window=1), "HOLD_PENDING")
        self.assertEqual(state.observe(negative, window=2), "HOLD_PENDING")
        self.assertLess(state.pending_score, state.threshold)
        self.assertEqual(state.current_signature, OLD)

    def test_first_discovery_bootstraps_immediately(self):
        state = AdaptiveEvidenceController()
        self.assertEqual(
            state.observe(EvidenceObservation(OLD), window=0), "CREATE"
        )
        self.assertEqual(state.current_signature, OLD)

    def test_one_strong_transient_window_cannot_reconfigure(self):
        state = AdaptiveEvidenceController()
        state.observe(EvidenceObservation(OLD), window=0)
        action = state.observe(
            EvidenceObservation(NEW, candidate_wins=100, candidate_losses=0),
            window=1,
        )
        self.assertEqual(action, "HOLD_PENDING")
        self.assertEqual(state.current_signature, OLD)
        self.assertLess(state.pending_score, state.threshold)

        action = state.observe(EvidenceObservation(OLD), window=2)
        self.assertEqual(action, "KEEP")
        self.assertEqual(state.current_signature, OLD)
        self.assertEqual(state.pending_score, 0.0)

    def test_strong_persistent_change_reconfigures_after_two_windows(self):
        state = AdaptiveEvidenceController()
        state.observe(EvidenceObservation(OLD), window=0)
        evidence = EvidenceObservation(NEW, candidate_wins=100, candidate_losses=0)
        self.assertEqual(state.observe(evidence, window=1), "HOLD_PENDING")
        self.assertEqual(state.observe(evidence, window=2), "RECONFIGURE")
        self.assertEqual(state.current_signature, NEW)

    def test_weak_evidence_requires_more_windows_than_strong_evidence(self):
        state = AdaptiveEvidenceController()
        state.observe(EvidenceObservation(OLD), window=0)
        weak = EvidenceObservation(NEW, candidate_wins=3, candidate_losses=1)
        actions = [state.observe(weak, window=i) for i in range(1, 8)]
        self.assertEqual(actions[0], "HOLD_PENDING")
        self.assertEqual(actions[-1], "RECONFIGURE")
        self.assertEqual(state.current_signature, NEW)

    def test_one_bad_health_window_does_not_retire(self):
        state = AdaptiveEvidenceController()
        state.observe(EvidenceObservation(OLD), window=0)
        action = state.observe(
            EvidenceObservation(None, current_invalid_evidence=100), window=1
        )
        self.assertEqual(action, "DEGRADE")
        self.assertEqual(state.current_signature, OLD)

    def test_sustained_health_failure_retires(self):
        state = AdaptiveEvidenceController()
        state.observe(EvidenceObservation(OLD), window=0)
        bad = EvidenceObservation(None, current_invalid_evidence=100)
        self.assertEqual(state.observe(bad, window=1), "DEGRADE")
        self.assertEqual(state.observe(bad, window=2), "RETIRE")
        self.assertIsNone(state.current_signature)

    def test_recovery_cancels_accumulated_invalid_evidence(self):
        state = AdaptiveEvidenceController()
        state.observe(EvidenceObservation(OLD), window=0)
        state.observe(EvidenceObservation(None, current_invalid_evidence=100), window=1)
        self.assertEqual(
            state.observe(EvidenceObservation(OLD, current_invalid_evidence=-100), window=2), "KEEP"
        )
        self.assertEqual(state.invalid_score, 0.0)


    def test_same_candidate_signature_does_not_hide_sustained_health_failure(self):
        state = AdaptiveEvidenceController()
        state.observe(EvidenceObservation(OLD), window=0)
        bad_same = EvidenceObservation(OLD, current_invalid_evidence=100)
        self.assertEqual(state.observe(bad_same, window=1), "DEGRADE")
        self.assertEqual(state.observe(bad_same, window=2), "RETIRE")
        self.assertIsNone(state.current_signature)

    def test_non_finite_health_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceObservation(OLD, current_invalid_evidence=float("nan"))

    def test_resurrection_after_retirement_requires_confirmation(self):
        state = AdaptiveEvidenceController()
        state.observe(EvidenceObservation(OLD), window=0)
        bad = EvidenceObservation(None, current_invalid_evidence=100)
        state.observe(bad, window=1)
        self.assertEqual(state.observe(bad, window=2), "RETIRE")
        evidence = EvidenceObservation(NEW, candidate_wins=100, candidate_losses=0)
        self.assertEqual(state.observe(evidence, window=3), "HOLD_PENDING")
        self.assertEqual(state.current_signature, None)
        self.assertEqual(state.observe(evidence, window=4), "CREATE")
        self.assertEqual(state.current_signature, NEW)


if __name__ == "__main__":
    unittest.main()
