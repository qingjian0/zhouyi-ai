import unittest

from prototype.yixiang_dynamics import (
    StateObservation, classify_transition, derive_transition_pattern,
)


def state(oid, entity, step, mode, evidence=True):
    return StateObservation(
        oid, entity, "fluid-system", step, {"mode": mode},
        {"mode": "process"}, (f"src:{oid}",) if evidence else (),
    )


class DynamicYixiangTests(unittest.TestCase):
    def test_extracts_directed_transition_across_trajectories(self):
        pattern = derive_transition_pattern(
            (
                (state("a1", "a", 0, "still"), state("a2", "a", 1, "flow")),
                (state("b1", "b", 0, "still"), state("b2", "b", 1, "flow")),
            ),
            pattern_id="onset", dimensions=("process",), scope="two examples",
        )
        self.assertEqual(pattern.transitions, {"mode": ("still", "flow")})
        self.assertEqual(len(pattern.evidence_refs), 4)
        self.assertEqual(pattern.transition_support_ids["mode"], ("trajectory-1", "trajectory-2"))

    def test_transition_direction_matters(self):
        pattern = derive_transition_pattern(
            ((state("a1", "a", 0, "still"), state("a2", "a", 1, "flow")),),
            pattern_id="onset", dimensions=("process",), scope="one trajectory",
        )
        result = classify_transition(
            pattern, state("c1", "c", 0, "flow"), state("c2", "c", 1, "still"),
        )
        self.assertFalse(result.accepted)
        self.assertIn("TRANSITION_MISMATCH", result.reason_codes)

    def test_tied_transition_patterns_are_not_forced(self):
        pattern = derive_transition_pattern(
            (
                (state("a1", "a", 0, "still"), state("a2", "a", 1, "flow")),
                (state("b1", "b", 0, "still"), state("b2", "b", 1, "reverse")),
            ),
            pattern_id="ambiguous", dimensions=("process",), scope="two trajectories",
            min_support_ratio=0.5,
        )
        self.assertEqual(pattern.transitions, {})
        self.assertIn("mode", pattern.variable_features)

    def test_rejects_non_monotonic_time_and_missing_evidence(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            derive_transition_pattern(
                ((state("a1", "a", 1, "still"), state("a2", "a", 1, "flow")),),
                pattern_id="bad", dimensions=("process",), scope="test",
            )
        pattern = derive_transition_pattern(
            ((state("b1", "b", 0, "still"), state("b2", "b", 1, "flow")),),
            pattern_id="p", dimensions=("process",), scope="test",
        )
        result = classify_transition(
            pattern, state("c1", "c", 0, "still", False),
            state("c2", "c", 1, "flow"),
        )
        self.assertFalse(result.accepted)
        self.assertIn("MISSING_TRANSITION_EVIDENCE", result.reason_codes)


if __name__ == "__main__":
    unittest.main()
