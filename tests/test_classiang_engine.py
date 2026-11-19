import unittest

from prototype.classiang_engine import (
    ClassExample, FeatureAtom, FeatureCandidate, InductionStatus,
    MembershipDecision, Observation, assess_membership, induce_class,
    select_aspects,
)


def observation(name, atoms, *, domain="domain-a", contradictions=()):
    evidence = (f"evidence:{name}",)
    features = tuple(
        FeatureCandidate(
            feature_id=f"{name}:{i}", atom=atom, evidence_refs=evidence,
            purpose_scores=(
                ("recognition", 0.2 if atom.value == "red" else 0.9),
                ("diagnosis", 0.9 if atom.value == "red" else 0.2),
            ),
        )
        for i, atom in enumerate(atoms)
    )
    return Observation(
        name, f"subject:{name}", domain, evidence, features,
        explicit_contradictions=tuple(contradictions),
    )


def example(name, atoms, *, domain="domain-a"):
    item = observation(name, atoms, domain=domain)
    return ClassExample(item, "recognition", select_aspects(
        item, purpose="recognition"
    ).selected)


class ClassiangEngineTests(unittest.TestCase):
    def test_task_conditioned_aspect_selection_is_auditable(self):
        item = observation("a", (
            FeatureAtom("morphology", "ring"),
            FeatureAtom("attribute", "red"),
            FeatureAtom("function", "supports"),
        ))
        result = select_aspects(item, purpose="recognition")
        self.assertEqual(result.selected, (
            FeatureAtom("function", "supports"),
            FeatureAtom("morphology", "ring"),
        ))
        self.assertEqual(result.excluded, (FeatureAtom("attribute", "red"),))

    def test_unscored_feature_is_not_silently_selected(self):
        result = select_aspects(
            observation("a", (FeatureAtom("attribute", "red"),)),
            purpose="unseen-purpose",
        )
        self.assertEqual(result.selected, ())
        self.assertEqual(result.unscored, (FeatureAtom("attribute", "red"),))

    def test_rejects_feature_evidence_not_grounded_in_observation(self):
        item = Observation(
            "a", "s", "d", ("e1",),
            (FeatureCandidate("f", FeatureAtom("attribute", "red"), ("invented",), ()),),
        )
        with self.assertRaisesRegex(ValueError, "not grounded"):
            select_aspects(item, purpose="recognition")

    def test_induces_discriminative_rule_from_positive_and_negative_examples(self):
        shared = FeatureAtom("function", "transfers-load")
        nuisance = FeatureAtom("attribute", "blue")
        result = induce_class(
            class_id="load-transfer", purpose="recognition",
            positive_examples=(
                example("p1", (shared, nuisance), domain="mechanics"),
                example("p2", (shared,), domain="biology"),
            ),
            negative_examples=(example("n1", (nuisance,)),),
            validity_scope="recognition tasks in supplied evidence domains",
        )
        self.assertEqual(result.status, InductionStatus.DISCRIMINATIVE)
        self.assertEqual(result.hypothesis.required_features, (shared,))
        self.assertFalse(result.hypothesis.semantic_validity_established)
        self.assertEqual(set(result.hypothesis.domains), {"biology", "mechanics"})

    def test_without_negative_examples_boundary_remains_provisional(self):
        shared = FeatureAtom("relation", "contains")
        result = induce_class(
            class_id="container", purpose="recognition",
            positive_examples=(example("p1", (shared,)), example("p2", (shared,))),
            validity_scope="only supplied positive examples",
        )
        self.assertEqual(result.status, InductionStatus.PROVISIONAL)
        self.assertIn("NEGATIVE_BOUNDARY_NOT_TESTED", result.reason_codes)

    def test_no_shared_positive_aspect_is_underdetermined(self):
        result = induce_class(
            class_id="unknown", purpose="recognition",
            positive_examples=(
                example("p1", (FeatureAtom("attribute", "red"),)),
                example("p2", (FeatureAtom("attribute", "blue"),)),
            ),
            validity_scope="test",
        )
        self.assertEqual(result.status, InductionStatus.UNDERDETERMINED)
        self.assertIsNone(result.hypothesis)

    def test_negative_examples_remove_non_discriminative_common_feature(self):
        common, specific = FeatureAtom("function", "moves"), FeatureAtom("process", "cyclic")
        result = induce_class(
            class_id="cycle", purpose="recognition",
            positive_examples=(
                example("p1", (common, specific)), example("p2", (common, specific)),
            ),
            negative_examples=(example("n1", (common,)),),
            validity_scope="test",
        )
        self.assertEqual(result.hypothesis.required_features, (specific,))

    def test_membership_acceptance_is_provisional_and_evidence_gated(self):
        feature = FeatureAtom("function", "transfers-load")
        result = induce_class(
            class_id="load-transfer", purpose="recognition",
            positive_examples=(example("p1", (feature,)), example("p2", (feature,))),
            negative_examples=(example("n1", (FeatureAtom("attribute", "blue"),)),),
            validity_scope="test",
        )
        self.assertEqual(
            assess_membership(observation("new", (feature,)), result.hypothesis).decision,
            MembershipDecision.ACCEPT_PROVISIONAL,
        )

    def test_missing_aspect_abstains_instead_of_rejecting(self):
        feature = FeatureAtom("function", "transfers-load")
        result = induce_class(
            class_id="load-transfer", purpose="recognition",
            positive_examples=(example("p1", (feature,)), example("p2", (feature,))),
            negative_examples=(example("n1", (FeatureAtom("attribute", "blue"),)),),
            validity_scope="test",
        )
        assessment = assess_membership(
            observation("new", (FeatureAtom("attribute", "blue"),)), result.hypothesis
        )
        self.assertEqual(assessment.decision, MembershipDecision.ABSTAIN)
        self.assertIn("REQUIRED_ASPECTS_NOT_OBSERVED", assessment.reason_codes)

    def test_explicit_contradiction_rejects(self):
        feature = FeatureAtom("function", "transfers-load")
        result = induce_class(
            class_id="load-transfer", purpose="recognition",
            positive_examples=(example("p1", (feature,)), example("p2", (feature,))),
            negative_examples=(example("n1", (FeatureAtom("attribute", "blue"),)),),
            validity_scope="test",
        )
        item = observation("new", (), contradictions=(feature,))
        self.assertEqual(
            assess_membership(item, result.hypothesis).decision,
            MembershipDecision.REJECT,
        )

    def test_membership_uses_hypothesis_task_aspect_filter(self):
        feature = FeatureAtom("function", "transfers-load")
        result = induce_class(
            class_id="load-transfer", purpose="recognition",
            positive_examples=(example("p1", (feature,)), example("p2", (feature,))),
            negative_examples=(example("n1", (FeatureAtom("attribute", "blue"),)),),
            validity_scope="test",
        )
        self.assertEqual(
            assess_membership(observation("new", (FeatureAtom("attribute", "red"),)),
                              result.hypothesis).decision,
            MembershipDecision.ABSTAIN,
        )

    def test_rejects_mixed_task_purposes(self):
        feature = FeatureAtom("function", "transfers-load")
        invalid = ClassExample(observation("p2", (feature,)), "diagnosis", ())
        with self.assertRaisesRegex(ValueError, "induction purpose"):
            induce_class(
                class_id="load-transfer", purpose="recognition",
                positive_examples=(example("p1", (feature,)), invalid),
                validity_scope="test",
            )

    def test_requires_two_positive_examples(self):
        feature = FeatureAtom("function", "transfers-load")
        result = induce_class(
            class_id="load-transfer", purpose="recognition",
            positive_examples=(example("p1", (feature,)),), validity_scope="test",
        )
        self.assertEqual(result.status, InductionStatus.UNDERDETERMINED)

    def test_rejects_non_finite_relevance_threshold(self):
        with self.assertRaises(ValueError):
            select_aspects(
                observation("a", (FeatureAtom("attribute", "red"),)),
                purpose="recognition", min_relevance=float("nan"),
            )


if __name__ == "__main__":
    unittest.main()
