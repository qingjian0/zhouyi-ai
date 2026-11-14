"""MTS-0 integration smoke: candidate -> inference -> evidence -> revision -> transfer."""
import tempfile
import unittest
from pathlib import Path

from prototype.e09_counterexample_learner import CounterexampleRuleLearner, Example
from prototype.e09_incremental_learner import IncrementalConjunctionLearner
from prototype.e09_prequential import PrequentialRunner
from prototype.e09_shared_protocol_adapter import E09SharedProtocolAdapter
from prototype.e09_evaluator_projection import E09EvaluatorProjection
from prototype.e12a6_lifecycle_contract import (
    Action, ActionType, Candidate, CandidateState, LifecycleLedger,
)
from prototype.e12a6_interop_adapter import adapt_candidate
from prototype.e12a20_factor_graph import Factor, Problem, Variable, infer
from prototype.e12a20_interop_adapter import adapt_exact_result
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
from prototype.cpg_interop import InferenceStatus


DOMAINS = ((0, 1), (0, 1), (0, 1, 2))
BOOTSTRAP = [
    ("seed-1", Example((0, 0, 0), "yes")),
    ("seed-2", Example((0, 1, 0), "yes")),
    ("seed-3", Example((1, 0, 0), "no")),
    ("seed-4", Example((1, 1, 0), "no")),
]


class MTS0SmokeTests(unittest.TestCase):
    def test_candidate_inference_evidence_revision_and_locked_transfer(self):
        candidate = Candidate(
            candidate_id="mts0:relation", version=1,
            canonical_expression="x > y", proposer_family="relational",
            supporting_families=("relational",), input_types=("number", "number"),
            operator="GT", complexity=2, proposal_cost=0.1,
        )
        lifecycle = LifecycleLedger()
        lifecycle.add_candidate(candidate)
        lifecycle.apply(Action(
            "mts0-propose", ActionType.PROPOSE, candidate.candidate_id, 1,
            from_state=CandidateState.OBSERVED, to_state=CandidateState.PROPOSED,
        ))
        projected = adapt_candidate(
            lifecycle.candidates[(candidate.candidate_id, 1)],
            scope="mts0/support", grammar_version="mts0-g1",
        )
        self.assertEqual(projected.proposal.candidate_ref, "mts0:relation@1")

        problem = Problem(
            variables=(Variable("x", ("0", "1")),),
            factors=(
                Factor("hard-valid", ("x",), "HARD",
                       forbidden_assignments=(("1",),), default_cost=None),
                Factor("support-evidence", ("x",), "EVIDENCE",
                       costs=((("0",), 0.0), (("1",), 1.0)),
                       default_cost=2.0, evidence_refs=("mts0:evidence-1",)),
            ),
        )
        exact = infer(problem)
        inference = adapt_exact_result(
            exact, query_id="mts0-query", scope="mts0/support"
        ).inference
        self.assertEqual(inference.status, InferenceStatus.IDENTIFIED)
        self.assertEqual(len(inference.ranked_hypothesis_refs), 1)

        with tempfile.TemporaryDirectory() as temp:
            store = SQLiteEvidenceStore(Path(temp) / "mts0.sqlite3")
            try:
                for mode, track in (
                    ("INCREMENTAL_INDEX", "e09-incremental"),
                    ("BATCH_REFIT", "e09-batch"),
                ):
                    if mode == "INCREMENTAL_INDEX":
                        learner = IncrementalConjunctionLearner(DOMAINS, min_support=2)
                    else:
                        learner = CounterexampleRuleLearner(DOMAINS, min_support=2)
                    runner = PrequentialRunner(learner, revision_mode=mode)
                    runner.bootstrap(BOOTSTRAP)

                    support = E09SharedProtocolAdapter(
                        runner, store, episode_id=f"mts0-{track}-support",
                        scope="mts0/support", split="SUPPORT", learner_track=track,
                    )
                    support_commit = support.predict_and_commit(
                        f"{track}-support-obs", (0, 0, 2)
                    )
                    support.reveal(support_commit["prediction_id"], "yes")
                    revision = support.revise(support_commit["prediction_id"])
                    self.assertEqual(revision["after_version_id"], "e09-v2")

                    locked = E09SharedProtocolAdapter(
                        runner, store, episode_id=f"mts0-{track}-locked",
                        scope="mts0/held-out", split="LOCKED_TEST", learner_track=track,
                    )
                    locked_commit = locked.predict_and_commit(
                        f"{track}-held-out-obs", (0, 1, 2)
                    )
                    locked.reveal(locked_commit["prediction_id"], "yes")

                    # Locked truth is visible to evaluator scoring but not to learner state.
                    self.assertEqual(runner.score()["revealed_observations"], 1)
                    self.assertEqual(runner.model_version, 2)
                    metrics = E09EvaluatorProjection(
                        store, f"mts0-{track}-locked"
                    ).score()["by_split"]["LOCKED_TEST"]
                    self.assertEqual(metrics["prediction_commits"], 1)
                    self.assertEqual(metrics["revealed_observations"], 1)
                    self.assertEqual(metrics["scored_predictions"], 1)
                    self.assertEqual(metrics["coverage"], 1.0)
                    self.assertIsNotNone(metrics["selective_accuracy"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
