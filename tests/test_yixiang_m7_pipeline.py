import unittest

from prototype.yixiang_active_observation import (
    HypothesisPrior, ObservationCandidate,
)
from prototype.yixiang_competing_hypotheses import (
    EvidenceLayer, EvidenceRecord, EvidenceStance, XiangCandidate,
)
from prototype.yixiang_counterfactual import (
    ConditionIntervention, ConditionOrigin, ConditionValue,
    ConditionalMapping, TruthValue, ComparisonKind,
)
from prototype.yixiang_novelty import ResidualCase
from prototype.yixiang_m7_pipeline import M7Input, run_m7


def evidence(eid):
    return EvidenceRecord(
        eid, "relation", EvidenceStance.SUPPORTS, 0.9,
        EvidenceLayer.OBSERVATION, f"source:{eid}",
    )


class M7PipelineTests(unittest.TestCase):
    def setUp(self):
        self.candidates = (
            XiangCandidate("H1", "mapping one", (), (), (), (), (evidence("e1"),)),
            XiangCandidate("H2", "mapping two", (), (), (), (), (evidence("e2"),)),
        )
        self.priors = (HypothesisPrior("H1", 0.5), HypothesisPrior("H2", 0.5))
        self.observations = (
            ObservationCandidate(
                "observe-season", "observe phase",
                (("H1", "early", 1.0), ("H1", "late", 0.0),
                 ("H2", "early", 0.0), ("H2", "late", 1.0)),
            ),
        )
        self.mapping = ConditionalMapping(
            "growth-rule", "growth relation", ("moisture",), ("frost",)
        )
        self.baseline = (
            ConditionValue("moisture", TruthValue.TRUE, ConditionOrigin.OBSERVED, "obs:1"),
            ConditionValue("frost", TruthValue.FALSE, ConditionOrigin.OBSERVED, "obs:2"),
        )
        signature = (("relation", "participates_in", "feedback"),)
        self.residuals = (
            ResidualCase("r1", "o1", "ecology", signature, (("phase", "spring"),), ("paper:a",)),
            ResidualCase("r2", "o2", "mechanics", signature, (("scale", "micro"),), ("paper:b",)),
        )

    def test_pipeline_connects_m3_m4_m5_m6_with_boundaries(self):
        result = run_m7(M7Input(
            candidates=self.candidates,
            priors=self.priors,
            observation_candidates=self.observations,
            mappings=(self.mapping,),
            mapping_to_candidate=(("growth-rule", "H1"),),
            baseline_conditions=self.baseline,
            interventions=(("growth-rule", (
                ConditionIntervention("moisture", TruthValue.FALSE),
            )),),
            residual_cases=self.residuals,
        ))
        self.assertEqual(result.arbitration.viable_candidate_ids, ("H1", "H2"))
        self.assertTrue(result.arbitration.unresolved)
        self.assertEqual(result.counterfactuals[0][0], "H1")
        self.assertEqual(result.counterfactuals[0][1].comparison, ComparisonKind.CHANGED)
        self.assertEqual(result.observation_selection.selected.observation_id, "observe-season")
        self.assertEqual(result.observation_selection.evidence_status, "prospective_only")
        self.assertEqual(len(result.novelty_proposals), 1)
        self.assertEqual(result.novelty_proposals[0].status.value, "proposed")
        self.assertEqual(result.stages_executed, ("M3", "M4", "M5", "M6"))
        self.assertIn("not_promoted_automatically", result.evidence_boundary)

    def test_resolved_m3_does_not_force_an_m5_observation(self):
        only = (self.candidates[0],)
        result = run_m7(M7Input(
            candidates=only,
            priors=(HypothesisPrior("H1", 1.0),),
            observation_candidates=self.observations[:0],
        ))
        self.assertFalse(result.arbitration.unresolved)
        self.assertIsNone(result.observation_selection)
        self.assertEqual(result.stages_executed, ("M3",))

    def test_m5_hypothesis_ids_must_match_m3_candidates(self):
        with self.assertRaisesRegex(ValueError, "exactly match"):
            run_m7(M7Input(
                candidates=self.candidates,
                priors=(HypothesisPrior("H1", 0.5), HypothesisPrior("other", 0.5)),
                observation_candidates=self.observations,
            ))

    def test_every_mapping_must_be_linked_to_a_candidate(self):
        with self.assertRaisesRegex(ValueError, "associated"):
            run_m7(M7Input(
                candidates=self.candidates,
                priors=self.priors,
                observation_candidates=(),
                mappings=(self.mapping,),
            ))

    def test_m6_does_not_create_proposals_without_explicit_residuals(self):
        result = run_m7(M7Input(
            candidates=self.candidates,
            priors=self.priors,
            observation_candidates=(),
        ))
        self.assertEqual(result.novelty_proposals, ())


if __name__ == "__main__":
    unittest.main()
