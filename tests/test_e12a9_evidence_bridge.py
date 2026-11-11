import unittest
from dataclasses import replace
from prototype.e12a7_orthogonal_lifecycle import CandidateVersion, EpistemicStatus, EventKind, OrthogonalLifecycleLedger
from prototype.e12a8_evaluator_firewall import Evaluator, run_learner_process
from prototype.e12a9_evidence_bridge import aggregate_evidence, append_evidence, bind_verdict

class E12A9EvidenceBridgeTests(unittest.TestCase):
    def _evaluations(self, count=30, gold=1):
        rows = []
        support = ((0,0,1),(1,0,0),(0,1,2),(1,1,1),(2,0,2),(0,2,0))
        for i in range(count):
            episode = f"e12a9-{i}"
            commit = run_learner_process(episode, support, (2,2))
            verdict = Evaluator({episode: gold}).evaluate(commit)
            rows.append(bind_verdict("rule@1", "z3-affine", commit, verdict))
        return rows

    def test_correct_verdicts_need_minimum_sample_and_confidence(self):
        batch = aggregate_evidence(self._evaluations())
        self.assertEqual(batch.epistemic_status, EpistemicStatus.SUPPORTED)
        self.assertEqual(batch.error_count, 0)
        self.assertGreaterEqual(batch.wilson_lower_bound, 0.80)

    def test_counterexample_contradicts_deterministic_candidate(self):
        rows = self._evaluations(9)
        support = ((0,0,1),(1,0,0),(0,1,2),(1,1,1),(2,0,2),(0,2,0))
        commit = run_learner_process("real-counterexample", support, (2,2))
        verdict = Evaluator({"real-counterexample": 2}).evaluate(commit)
        rows.append(bind_verdict("rule@1", "z3-affine", commit, verdict))
        batch = aggregate_evidence(rows)
        self.assertEqual(batch.epistemic_status, EpistemicStatus.CONTRADICTED)
        self.assertEqual(batch.error_count, 1)

    def test_small_all_correct_sample_is_underdetermined(self):
        self.assertEqual(aggregate_evidence(self._evaluations(5)).epistemic_status,
                         EpistemicStatus.UNDERDETERMINED)

    def test_mismatched_commit_digest_is_rejected(self):
        commit = run_learner_process("mismatch", ((0,0,1),(1,0,0)), (2,2))
        verdict = Evaluator({"mismatch": 1}).evaluate(commit)
        with self.assertRaises(ValueError):
            bind_verdict("rule@1", "scope", commit, replace(verdict, commit_digest="0"*64))

    def test_inconsistent_correctness_flag_is_rejected(self):
        commit = run_learner_process("bad-flag", ((0,0,1),(1,0,0),(0,1,2),(1,1,1),(2,0,2),(0,2,0)), (2,2))
        verdict = Evaluator({"bad-flag": 1}).evaluate(commit)
        with self.assertRaises(ValueError):
            bind_verdict("rule@1", "scope", commit, replace(verdict, correct=not verdict.correct))

    def test_mixed_scope_or_candidate_batches_are_rejected(self):
        rows = self._evaluations(2)
        with self.assertRaises(ValueError):
            aggregate_evidence([rows[0], replace(rows[1], scope_id="other")])

    def test_duplicate_commit_is_rejected(self):
        row = self._evaluations(1)[0]
        with self.assertRaises(ValueError):
            aggregate_evidence([row, row])

    def test_lifecycle_receives_evidence_without_workflow_promotion(self):
        batch = aggregate_evidence(self._evaluations())
        ledger = OrthogonalLifecycleLedger()
        ledger.register(CandidateVersion("rule", 1, "affine modular relation", "z3-v1"))
        event = append_evidence(ledger, batch)
        self.assertEqual(event.kind, EventKind.EPISTEMIC_ASSESSMENT)
        self.assertEqual(event.evidence_ids, (batch.evidence_id,))
        snapshot = ledger.snapshot("rule", 1, "z3-affine")
        self.assertEqual(snapshot["epistemic_status"], EpistemicStatus.SUPPORTED.value)
        self.assertEqual(snapshot["workflow_stage"], "observed")

if __name__ == "__main__":
    unittest.main()
