import unittest

from prototype.cpg_interop import CandidateProposal, StructureVersion
from prototype.e12a6_interop_adapter import adapt_candidate
from prototype.e12a6_lifecycle_contract import Candidate, CandidateState


def make_candidate(**overrides):
    values = {
        "candidate_id": "rel:greater-than",
        "version": 2,
        "canonical_expression": "x > y",
        "proposer_family": "relational",
        "supporting_families": ("relational", "residual"),
        "input_types": ("number", "number"),
        "operator": "GT",
        "conditions": ("x_is_finite",),
        "uncertainty": 0.4,
        "complexity": 2,
        "proposal_cost": 0.25,
        "parent_refs": ("rel:greater-than@1",),
        "evidence_ids": ("ev-2", "ev-1"),
        "state": CandidateState.REVALIDATION_PENDING,
    }
    values.update(overrides)
    return Candidate(**values)


class E12A6InteropAdapterTests(unittest.TestCase):
    def test_maps_candidate_to_shared_proposal_and_structure(self):
        candidate = make_candidate()
        adapted = adapt_candidate(candidate, scope="world/family-a", grammar_version="e12a6-grammar-v1")
        self.assertIsInstance(adapted.proposal, CandidateProposal)
        self.assertIsInstance(adapted.structure, StructureVersion)
        self.assertEqual(adapted.proposal.candidate_ref, "rel:greater-than@2")
        self.assertEqual(adapted.proposal.track_id, "e12a6")
        self.assertEqual(adapted.proposal.evidence_refs, ("ev-1", "ev-2"))
        self.assertEqual(adapted.structure.parent_refs, ("rel:greater-than@1",))
        self.assertEqual(adapted.structure.ref, "rel:greater-than@2")
        self.assertEqual(adapted.proposal.definition_digest, adapted.structure.definition_digest)

    def test_scope_and_grammar_are_explicit_and_validated(self):
        candidate = make_candidate()
        with self.assertRaisesRegex(ValueError, "scope"):
            adapt_candidate(candidate, scope=" ", grammar_version="v1")
        with self.assertRaisesRegex(ValueError, "grammar_version"):
            adapt_candidate(candidate, scope="scope", grammar_version="")

    def test_duplicate_evidence_refs_are_rejected_not_silently_deduplicated(self):
        candidate = make_candidate(evidence_ids=("ev-1", "ev-1"))
        with self.assertRaisesRegex(ValueError, "duplicates"):
            adapt_candidate(candidate, scope="scope", grammar_version="v1")

    def test_projection_does_not_change_native_lifecycle_state(self):
        candidate = make_candidate(state=CandidateState.CHALLENGED)
        before = candidate.state
        adapt_candidate(candidate, scope="scope", grammar_version="v1")
        self.assertIs(candidate.state, before)

    def test_definition_digest_changes_when_semantics_change(self):
        first = adapt_candidate(make_candidate(), scope="scope", grammar_version="v1")
        second = adapt_candidate(
            make_candidate(canonical_expression="x >= y", operator="GE"),
            scope="scope",
            grammar_version="v1",
        )
        self.assertNotEqual(first.proposal.definition_digest, second.proposal.definition_digest)


if __name__ == "__main__":
    unittest.main()
