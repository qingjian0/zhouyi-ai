import unittest

from prototype.yixiang_perspectives import (
    AnalogyPerspective,
    EvidencePolarity,
    PerspectiveError,
    PerspectiveEvidence,
    PerspectiveSet,
    PerspectiveStatus,
    assess_perspective,
    build_perspective_set,
    validate_perspective,
)


def perspective(perspective_id="p1", lens="FUNCTION", evidence=()):
    return AnalogyPerspective(
        perspective_id=perspective_id,
        source_concept="water",
        target_concept="knowledge",
        lens=lens,
        tradition_or_source="explicitly cited interpretive tradition",
        applicability_conditions=("flow and transfer are in scope",),
        evidence=tuple(evidence),
        counterexample_notes=("stagnation is a counterexample candidate",),
        limitations=("does not imply physical identity or causal equivalence",),
        provenance="human-authored hypothesis",
    )


class MultiPerspectiveTests(unittest.TestCase):
    def test_distinct_lenses_are_preserved_for_same_concept_pair(self):
        first = perspective("p-function", "FUNCTION")
        second = perspective("p-form", "NATURAL_FORM")
        result = build_perspective_set("set-1", (first, second))
        self.assertEqual(len(result.perspectives), 2)
        self.assertEqual(
            {item.lens for item in result.perspectives},
            {"FUNCTION", "NATURAL_FORM"},
        )

    def test_no_evidence_is_explicitly_untested(self):
        result = assess_perspective(perspective())
        self.assertEqual(result.status, PerspectiveStatus.UNTESTED)
        self.assertEqual(result.support_count, 0)

    def test_conflicting_evidence_remains_contested(self):
        evidence = (
            PerspectiveEvidence("e1", "source:a", EvidencePolarity.SUPPORTS,
                                "within stated scope", "supports transfer relation"),
            PerspectiveEvidence("e2", "source:b", EvidencePolarity.COUNTERS,
                                "under stagnant conditions", "transfer relation fails"),
        )
        result = assess_perspective(perspective(evidence=evidence))
        self.assertEqual(result.status, PerspectiveStatus.CONTESTED)
        self.assertEqual(result.support_count, 1)
        self.assertEqual(result.counter_count, 1)

    def test_context_only_evidence_is_not_counted_as_support(self):
        evidence = (
            PerspectiveEvidence("e1", "source:a", EvidencePolarity.CONTEXT_ONLY,
                                "historical context", "documents a traditional usage"),
        )
        result = assess_perspective(perspective(evidence=evidence))
        self.assertEqual(result.status, PerspectiveStatus.EVIDENCE_ATTACHED)
        self.assertEqual(result.support_count, 0)
        self.assertEqual(result.context_count, 1)

    def test_unknown_polarity_is_not_upgraded(self):
        evidence = (
            PerspectiveEvidence("e1", "source:a", EvidencePolarity.UNKNOWN,
                                "scope unresolved", "claim not evaluated"),
        )
        result = assess_perspective(perspective(evidence=evidence))
        self.assertEqual(result.unknown_count, 1)
        self.assertEqual(result.support_count, 0)

    def test_scope_and_limitations_are_mandatory(self):
        item = perspective()
        with self.assertRaises(PerspectiveError):
            validate_perspective(AnalogyPerspective(
                item.perspective_id, item.source_concept, item.target_concept,
                item.lens, item.tradition_or_source, (), item.evidence,
                item.counterexample_notes, item.limitations, item.provenance
            ))
        with self.assertRaises(PerspectiveError):
            validate_perspective(AnalogyPerspective(
                item.perspective_id, item.source_concept, item.target_concept,
                item.lens, item.tradition_or_source, item.applicability_conditions,
                item.evidence, item.counterexample_notes, (), item.provenance
            ))

    def test_duplicate_perspective_ids_rejected_not_silently_merged(self):
        with self.assertRaises(PerspectiveError):
            build_perspective_set("set-1", (perspective("same"), perspective("same")))

    def test_duplicate_evidence_ids_rejected(self):
        e = PerspectiveEvidence("same", "source:a", EvidencePolarity.SUPPORTS,
                                "scope", "claim")
        with self.assertRaises(PerspectiveError):
            validate_perspective(perspective(evidence=(e, e)))

    def test_evidence_requires_source_and_scope(self):
        e = PerspectiveEvidence("e1", "", EvidencePolarity.SUPPORTS, "scope", "claim")
        with self.assertRaises(PerspectiveError):
            validate_perspective(perspective(evidence=(e,)))


if __name__ == "__main__":
    unittest.main()
