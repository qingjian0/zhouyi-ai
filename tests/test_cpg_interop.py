import unittest
from prototype.cpg_interop import (
    CandidateProposal, ConsumerRole, EvidenceReveal, EvidenceSplit,
    InferenceResult, InferenceStatus, PredictionCommit, StructureVersion,
    canonical_json, digest_json, evidence_visible_to, validate_reveal_binding,
)
D = "a" * 64

class CpgInteropTests(unittest.TestCase):
    def commit(self, **changes):
        values = dict(commit_id="commit-1", candidate_ref="rule@1", query_id="q-1",
            scope="world-a", input_digest=D, identifiable=True,
            prediction_json=canonical_json({"answer": 2}), episode_id="episode-1", learner_track="track-a", split=EvidenceSplit.SUPPORT, model_version="model-1")
        values.update(changes)
        return PredictionCommit(**values)

    def reveal(self, commit, **changes):
        values = dict(evidence_id="e-1", commit_digest=commit.commit_digest,
            query_id=commit.query_id, scope=commit.scope, split=EvidenceSplit.SUPPORT,
            outcome_json=canonical_json({"label": 2}), source_ref="episode://1", episode_id=commit.episode_id, learner_track=commit.learner_track)
        values.update(changes)
        return EvidenceReveal(**values)

    def test_candidate_requires_version_and_digest(self):
        self.assertEqual(CandidateProposal("rule@1", "e12", "w", "g1", D).candidate_ref, "rule@1")
        with self.assertRaises(ValueError): CandidateProposal("rule", "e12", "w", "g1", D)
        with self.assertRaises(ValueError): CandidateProposal("rule@1", "e12", "w", "g1", "bad")

    def test_candidate_cost_and_complexity(self):
        with self.assertRaises(ValueError): CandidateProposal("r@1", "e12", "w", "g1", D, estimated_cost=float("inf"))
        with self.assertRaises(ValueError): CandidateProposal("r@1", "e12", "w", "g1", D, complexity=0)

    def test_commit_digest_is_deterministic(self):
        self.assertEqual(self.commit().commit_digest, self.commit().commit_digest)

    def test_prediction_json_must_be_canonical_and_finite(self):
        with self.assertRaises(ValueError): self.commit(prediction_json='{"answer": 2}')
        with self.assertRaises(ValueError): self.commit(prediction_json='{"x":NaN}')

    def test_abstention_has_no_prediction(self):
        with self.assertRaises(ValueError):
            self.commit(identifiable=False, prediction_json=canonical_json(2), abstention_reason="ambiguous")
        self.assertFalse(self.commit(identifiable=False, prediction_json=None, abstention_reason="ambiguous").identifiable)

    def test_reveal_binds_exact_commit(self):
        commit = self.commit()
        validate_reveal_binding(commit, self.reveal(commit))
        with self.assertRaises(ValueError):
            validate_reveal_binding(self.commit(commit_id="other"), self.reveal(commit))

    def test_reveal_query_and_scope_must_match(self):
        commit = self.commit()
        with self.assertRaises(ValueError): validate_reveal_binding(commit, self.reveal(commit, query_id="other"))
        with self.assertRaises(ValueError): validate_reveal_binding(commit, self.reveal(commit, scope="other"))

    def test_reveal_must_match_episode_track_and_split(self):
        commit = self.commit()
        with self.assertRaisesRegex(ValueError, "episode_id"):
            validate_reveal_binding(commit, self.reveal(commit, episode_id="other"))
        with self.assertRaisesRegex(ValueError, "learner_track"):
            validate_reveal_binding(commit, self.reveal(commit, learner_track="other"))
        with self.assertRaisesRegex(ValueError, "split"):
            validate_reveal_binding(commit, self.reveal(commit, split=EvidenceSplit.LOCKED_TEST))


    def test_reveal_must_match_episode_track_and_split(self):
        commit = self.commit()
        with self.assertRaisesRegex(ValueError, "episode_id"):
            validate_reveal_binding(commit, self.reveal(commit, episode_id="other"))
        with self.assertRaisesRegex(ValueError, "learner_track"):
            validate_reveal_binding(commit, self.reveal(commit, learner_track="other"))
        with self.assertRaisesRegex(ValueError, "split"):
            validate_reveal_binding(commit, self.reveal(commit, split=EvidenceSplit.LOCKED_TEST))

    def test_strict_binding_rejects_missing_context(self):
        legacy_commit = PredictionCommit(
            commit_id="c", candidate_ref="r@1", query_id="q", scope="s",
            input_digest=D, identifiable=True, prediction_json=canonical_json(1)
        )
        legacy_reveal = EvidenceReveal(
            evidence_id="e", commit_digest=legacy_commit.commit_digest,
            query_id="q", scope="s", split=EvidenceSplit.SUPPORT,
            outcome_json=canonical_json(1), source_ref="source"
        )
        with self.assertRaisesRegex(ValueError, "strict prediction commit"):
            validate_reveal_binding(legacy_commit, legacy_reveal, require_context=True)

    def test_abstained_is_distinct_from_unknown(self):
        result = InferenceResult("q", "w", InferenceStatus.ABSTAINED, (), (), ())
        self.assertEqual(result.status, InferenceStatus.ABSTAINED)

    def test_locked_test_is_not_visible_to_learner_or_selector(self):
        reveal = self.reveal(self.commit(), split=EvidenceSplit.LOCKED_TEST)
        self.assertFalse(evidence_visible_to(reveal, ConsumerRole.LEARNER))
        self.assertFalse(evidence_visible_to(reveal, ConsumerRole.SELECTOR))
        self.assertTrue(evidence_visible_to(reveal, ConsumerRole.EVALUATOR))

    def test_gate_dev_is_selector_only(self):
        reveal = self.reveal(self.commit(), split=EvidenceSplit.GATE_DEV)
        self.assertFalse(evidence_visible_to(reveal, ConsumerRole.LEARNER))
        self.assertTrue(evidence_visible_to(reveal, ConsumerRole.SELECTOR))

    def test_gate_final_is_evaluator_only(self):
        reveal = self.reveal(self.commit(), split=EvidenceSplit.GATE_FINAL)
        self.assertFalse(evidence_visible_to(reveal, ConsumerRole.LEARNER))
        self.assertFalse(evidence_visible_to(reveal, ConsumerRole.SELECTOR))
        self.assertTrue(evidence_visible_to(reveal, ConsumerRole.EVALUATOR))

    def test_structure_version_has_immutable_lineage(self):
        item = StructureVersion("concept", 2, "e11", "w", "g1", D, ("concept@1",), ("e1",))
        self.assertEqual(item.ref, "concept@2")
        with self.assertRaises(ValueError): StructureVersion("concept", 0, "e11", "w", "g1", D)
        with self.assertRaises(ValueError): StructureVersion("concept", 2, "e11", "w", "g1", D, ("concept@2",))

    def test_inference_result_preserves_rank_and_budget(self):
        result = InferenceResult("q", "w", InferenceStatus.IDENTIFIED, ("h2@1", "h1@1"), ("e1",),
                                 (("factor_evaluations", 12), ("message_updates", 8)))
        self.assertEqual(result.ranked_hypothesis_refs[0], "h2@1")
        with self.assertRaises(ValueError): InferenceResult("q", "w", InferenceStatus.IDENTIFIED, (), (), ())
        with self.assertRaises(ValueError): InferenceResult("q", "w", InferenceStatus.UNKNOWN, ("h@1",), (), ())

    def test_digest_is_mapping_order_independent(self):
        self.assertEqual(digest_json({"a": 1, "b": 2}), digest_json({"b": 2, "a": 1}))

    def test_split_must_be_typed(self):
        commit = self.commit()
        with self.assertRaises(ValueError): self.reveal(commit, split="locked_test")

if __name__ == "__main__":
    unittest.main()
