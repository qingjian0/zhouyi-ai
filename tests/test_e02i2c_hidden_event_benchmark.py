import unittest
from dataclasses import fields, replace

from prototype.e02i2c_adjudication import EvidencePacket, EvidencePolarity, EventType
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
                self.assertEqual(_adjudicator(episode.observation), event)

    def test_evaluator_truth_is_not_an_evidence_packet_field(self):
        names = {field.name for field in fields(EvidencePacket)}
        self.assertFalse({
            "truth", "true_event", "true_identity_id",
            "latent_identity", "generator_transition",
        }.intersection(names))

    def test_observation_view_has_no_evaluator_truth_field(self):
        episode = build_episode(EventType.CREATE, 77, split="gate")
        view_names = {field.name for field in fields(type(episode.observation))}
        self.assertFalse({"truth", "true_event", "true_identity_id",
                          "latent_identity", "generator_transition"}.intersection(view_names))

    def test_episode_truth_is_separate_from_adjudicator_arguments(self):
        episode = build_episode(EventType.MODIFY, 202, split="train")
        # The adjudicator wrapper passes only observable contracts, never Episode.truth.
        decision = _adjudicator(episode.observation)
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

    def test_benchmark_counts_false_create_and_evidence_gate_avoids_it(self):
        result = run_benchmark(seeds=8, start_seed=1000, split="train")
        self.assertGreater(result["policies"]["similarity_only"]["false_create"], 0)
        self.assertEqual(result["policies"]["evidence_gated"]["false_create"], 0)

    def test_benchmark_evidence_ids_are_unique_across_episodes(self):
        from prototype.e02i2c_hidden_event_benchmark import _build_episodes
        episodes = _build_episodes(seeds=5, start_seed=600, split="gate")
        evidence_ids = [
            packet.evidence_id
            for episode in episodes
            for packet in episode.observation.evidence
        ]
        sample_ids = [
            packet.sample_id
            for episode in episodes
            for packet in episode.observation.evidence
        ]
        self.assertEqual(len(evidence_ids), len(set(evidence_ids)))
        self.assertEqual(len(sample_ids), len(set(sample_ids)))

    def test_train_and_gate_sample_namespaces_are_disjoint(self):
        train = [
            build_episode(event, 1000 + seed, split="train")
            for seed in range(4) for event in SUPPORTED_EVENTS
        ]
        gate = [
            build_episode(event, 2000 + seed, split="gate")
            for seed in range(4) for event in SUPPORTED_EVENTS
        ]
        train_samples = {packet.sample_id for episode in train for packet in episode.observation.evidence}
        gate_samples = {packet.sample_id for episode in gate for packet in episode.observation.evidence}
        self.assertFalse(train_samples.intersection(gate_samples))
        self.assertTrue(all(packet.split == "train" for episode in train for packet in episode.observation.evidence))
        self.assertTrue(all(packet.split == "gate" for episode in gate for packet in episode.observation.evidence))

    def test_abstain_class_covers_four_distinct_failure_modes(self):
        modes = [build_episode(EventType.ABSTAIN, seed, split="gate") for seed in range(4)]
        self.assertEqual([_adjudicator(episode.observation) for episode in modes],
                         [EventType.ABSTAIN] * 4)
        self.assertIsNone(modes[0].observation.identity)
        self.assertIsNotNone(modes[1].observation.identity)
        self.assertFalse(modes[2].observation.opportunities[0].sufficient())
        self.assertEqual(
            {packet.polarity for packet in modes[3].observation.evidence},
            {EvidencePolarity.SUPPORTS, EvidencePolarity.CONTRADICTS},
        )

    def test_observable_provenance_ids_do_not_encode_event_labels(self):
        forbidden = tuple(event.value.lower() for event in SUPPORTED_EVENTS)
        for seed in range(40):
            for event in SUPPORTED_EVENTS:
                episode = build_episode(event, 10000 + seed, split="gate")
                for packet in episode.observation.evidence:
                    metadata = " ".join((
                        packet.evidence_id, packet.sample_id,
                        packet.raw_observation_ref,
                    )).lower()
                    self.assertFalse(any(label in metadata for label in forbidden))
                    self.assertNotIn("unconfirmed-new", metadata)
                    self.assertNotIn("conflict-positive", metadata)
                    self.assertNotIn("undersampled", metadata)

    def test_random_bijective_provenance_renaming_preserves_semantic_decision(self):
        episode = build_episode(EventType.MODIFY, 31337, split="gate")
        renamed = []
        for index, packet in enumerate(episode.observation.evidence):
            renamed.append(replace(
                packet,
                evidence_id=f"opaque-e-{index}-x",
                sample_id=f"opaque-s-{index}-y",
                raw_observation_ref=f"opaque://{index}/z",
            ))
        original = _adjudicator(episode.observation)
        transformed = replace(episode.observation, evidence=tuple(renamed))
        self.assertEqual(_adjudicator(transformed), original)

    def test_locked_test_is_not_available_during_development(self):
        with self.assertRaisesRegex(ValueError, "locked Test"):
            run_benchmark(seeds=1, split="test")

    def test_similarity_only_baseline_false_creates_without_repeated_support(self):
        episode = build_episode(EventType.ABSTAIN, 300, split="gate")
        self.assertEqual(_similarity_only(episode.observation), EventType.CREATE)
        self.assertEqual(_adjudicator(episode.observation), EventType.ABSTAIN)


if __name__ == "__main__":
    unittest.main()
