import unittest
from prototype.yixiang_path_competition import (
    PathCandidate, PathCompetitionDecision, PathOutcome, audit_path_competition,
)


def path(pid, states, relations, outcome=PathOutcome.VIABLE, axes=None, refs=None,
         source="start", target="goal"):
    return PathCandidate(pid, source, target, tuple(states), tuple(relations),
                         tuple(axes or (("time", "t1"), ("position", "inner"))),
                         outcome, tuple(refs or (f"evidence-{pid}",)))


class PathCompetitionTests(unittest.TestCase):
    def test_two_viable_routes_are_preserved_without_winner(self):
        result = audit_path_competition(
            (path("p1", ("a", "b", "z"), ("r1", "r2")),
             path("p2", ("a", "c", "z"), ("r3", "r4"))),
            required_context_axes=("time", "position"),
            target_context_axes=(("time", "t1"), ("position", "inner")))
        self.assertEqual(result.decision, PathCompetitionDecision.HUMAN_REVIEW)
        self.assertEqual(result.viable_path_ids, ("p1", "p2"))
        self.assertEqual(result.failed_path_ids, ())
        self.assertEqual(result.unresolved_path_ids, ())

    def test_failed_route_is_not_counted_viable(self):
        result = audit_path_competition(
            (path("p1", ("a", "b"), ("r1",), PathOutcome.FAILED),
             path("p2", ("a", "c"), ("r2",))),
            required_context_axes=("time",),
            target_context_axes=(("time", "t1"),))
        self.assertEqual(result.failed_path_ids, ("p1",))
        self.assertEqual(result.viable_path_ids, ("p2",))

    def test_unknown_outcome_remains_unresolved(self):
        result = audit_path_competition(
            (path("p1", ("a", "b"), ("r1",), PathOutcome.UNKNOWN),
             path("p2", ("a", "c"), ("r2",))),
            required_context_axes=("time",),
            target_context_axes=(("time", "t1"),))
        self.assertEqual(result.unresolved_path_ids, ("p1",))

    def test_context_mismatch_is_abstained_not_rejected(self):
        result = audit_path_competition(
            (path("p1", ("a", "b"), ("r1",), axes=(("time", "t2"),)),
             path("p2", ("a", "c"), ("r2",))),
            required_context_axes=("time",),
            target_context_axes=(("time", "t1"),))
        self.assertEqual(result.context_mismatch_path_ids, ("p1",))
        self.assertEqual(result.unresolved_path_ids, ("p1",))

    def test_missing_path_context_is_blocked(self):
        result = audit_path_competition(
            (path("p1", ("a", "b"), ("r1",), axes=(("time", "t1"),)),
             path("p2", ("a", "c"), ("r2",))),
            required_context_axes=("time", "position"),
            target_context_axes=(("time", "t1"), ("position", "inner")))
        self.assertIn("PATH_REQUIRED_CONTEXT_MISSING:p1", result.reason_codes)

    def test_competing_paths_must_share_endpoints(self):
        result = audit_path_competition(
            (path("p1", ("a", "b"), ("r1",)),
             path("p2", ("a", "c"), ("r2",), target="other")),
            required_context_axes=("time",),
            target_context_axes=(("time", "t1"),))
        self.assertIn("COMPETING_PATHS_MUST_SHARE_ENDPOINTS", result.reason_codes)

    def test_evidence_cannot_be_reused_across_paths(self):
        result = audit_path_competition(
            (path("p1", ("a", "b"), ("r1",), refs=("same",)),
             path("p2", ("a", "c"), ("r2",), refs=("same",))),
            required_context_axes=("time",),
            target_context_axes=(("time", "t1"),))
        self.assertIn("EVIDENCE_REUSED_ACROSS_COMPETING_PATHS", result.reason_codes)

    def test_duplicate_path_ids_are_blocked(self):
        result = audit_path_competition(
            (path("p", ("a", "b"), ("r1",)),
             path("p", ("a", "c"), ("r2",))),
            required_context_axes=("time",),
            target_context_axes=(("time", "t1"),))
        self.assertIn("PATH_IDS_MUST_BE_UNIQUE", result.reason_codes)

    def test_requires_two_candidates(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            audit_path_competition((path("p1", ("a", "b"), ("r1",)),),
                required_context_axes=("time",),
                target_context_axes=(("time", "t1"),))

    def test_target_must_define_required_axes(self):
        with self.assertRaisesRegex(ValueError, "target_context_axes must define"):
            audit_path_competition(
                (path("p1", ("a", "b"), ("r1",)), path("p2", ("a", "c"), ("r2",))),
                required_context_axes=("time", "position"),
                target_context_axes=(("time", "t1"),))

    def test_relation_signatures_must_be_nonempty(self):
        with self.assertRaises(ValueError):
            audit_path_competition(
                (path("p1", ("a", "b"), ()), path("p2", ("a", "c"), ("r2",))),
                required_context_axes=("time",),
                target_context_axes=(("time", "t1"),))

    def test_recurrent_state_and_relation_are_allowed_within_route(self):
        result = audit_path_competition(
            (path("p1", ("start", "middle", "start", "goal"), ("r1", "r2", "r1")),
             path("p2", ("start", "alternate", "goal"), ("r3", "r4"))),
            required_context_axes=("time",),
            target_context_axes=(("time", "t1"),))
        self.assertEqual(result.viable_path_ids, ("p1", "p2"))

    def test_endpoint_sequence_must_match_declared_endpoints(self):
        result = audit_path_competition(
            (path("p1", ("wrong", "goal"), ("r1",)),
             path("p2", ("start", "goal"), ("r2",))),
            required_context_axes=("time",),
            target_context_axes=(("time", "t1"),))
        self.assertIn("PATH_ENDPOINT_SEQUENCE_MISMATCH:p1", result.reason_codes)

    def test_required_axes_must_be_unique(self):
        with self.assertRaisesRegex(ValueError, "entries must be unique"):
            audit_path_competition(
                (path("p1", ("a", "b"), ("r1",)), path("p2", ("a", "c"), ("r2",))),
                required_context_axes=("time", "time"),
                target_context_axes=(("time", "t1"),))

    def test_context_axis_names_must_be_unique(self):
        with self.assertRaisesRegex(ValueError, "axis names must be unique"):
            audit_path_competition(
                (path("p1", ("a", "b"), ("r1",), axes=(("time", "t1"), ("time", "t2"))),
                 path("p2", ("a", "c"), ("r2",))),
                required_context_axes=("time",),
                target_context_axes=(("time", "t1"),))

    def test_evidence_reference_is_required(self):
        with self.assertRaises(ValueError):
            audit_path_competition(
                (path("p1", ("a", "b"), ("r1",), refs=()),
                 path("p2", ("a", "c"), ("r2",))),
                required_context_axes=("time",),
                target_context_axes=(("time", "t1"),))


if __name__ == "__main__":
    unittest.main()
