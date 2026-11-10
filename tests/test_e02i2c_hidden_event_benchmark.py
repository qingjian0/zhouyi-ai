import unittest
from dataclasses import fields

from prototype.e02i2c_adjudication import EvidencePacket, EventType
from prototype.e02i2c_hidden_event_benchmark import (
    SUPPORTED_EVENTS,
    _adjudicator,
    _similarity_only,
    build_episode,
    run_benchmark,
)


class E02I2CHiddenEventBenchmarkTests(unittest.TestCase):
    def test_all_supported_hidden_events_have_expected_adjudication(self):
        for event in SUPPORTED_EVENTS:
            with self.subTest(event=event.value):
                episode = build_episode(event, 101, split="gate")
                self.assertEqual(_adjudicator(episode), event)

    def test_evaluator_truth_is_not_an_evidence_packet_field(self):
        names = {field.name for field in fields(EvidencePacket)}
        self.assertFalse({
            "truth", "true_event", "true_identity_id",
            "latent_identity", "generator_transition",
        }.intersection(names))

    def test_episode_truth_is_separate_from_adjudicator_arguments(self):
        episode = build_episode(EventType.MODIFY, 202, split="train")
        # The adjudicator wrapper passes only observable contracts, never Episode.truth.
        decision = _adjudicator(episode)
        self.assertEqual(decision, EventType.MODIFY)
        self.assertEqual(episode.truth, EventType.MODIFY)

    def test_development_benchmark_is_deterministic_and_reports_selective_metrics(self):
        first = run_benchmark(seeds=3, start_seed=500, split="train")
        second = run_benchmark(seeds=3, start_seed=500, split="train")
        self.assertEqual(first, second)
        self.assertEqual(first["episodes"], 3 * len(SUPPORTED_EVENTS))
        self.assertFalse(first["locked_test_available"])
        self.assertTrue(first["truth_is_evaluator_only"])
        for metrics in first["policies"].values():
            self.assertIn("macro_f1", metrics)
            self.assertIn("coverage", metrics)
            self.assertIn("selective_risk", metrics)
            self.assertIn("false_create", metrics)

    def test_locked_test_is_not_available_during_development(self):
        with self.assertRaisesRegex(ValueError, "locked Test"):
            run_benchmark(seeds=1, split="test")

    def test_similarity_only_baseline_exposes_false_create_on_ambiguous_case(self):
        episode = build_episode(EventType.ABSTAIN, 303, split="gate")
        self.assertEqual(_similarity_only(episode), EventType.MODIFY)
        self.assertEqual(_adjudicator(episode), EventType.ABSTAIN)


if __name__ == "__main__":
    unittest.main()
