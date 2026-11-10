import unittest

from prototype.e10a_structural_ood import build_structural_ood_task
from prototype.e10a_compositional_features import CompositionalFeatureLearner


def _episode(seed=9101):
    support, _, _ = build_structural_ood_task(seed)
    objects = []
    roles = [
        ("red", "rough"),
        ("red", "smooth"),
        ("blue", "rough"),
    ]
    for role, (color, texture) in enumerate(roles):
        for n in range(2):
            objects.append({
                "object_id": f"cf-{seed}-role-{role}-{n}",
                "attributes": [
                    ["color", color],
                    ["texture", texture],
                    ["irrelevant", f"noise-{(role+n)%2}"],
                ],
            })
    # A duplicate of role A is a role-composition near miss.
    objects.append({
        "object_id": f"cf-{seed}-duplicate-a",
        "attributes": [
            ["color", "red"], ["texture", "rough"], ["irrelevant", "noise-0"],
        ],
    })

    def row(oid, participants, phase="active", permission="granted"):
        return {
            "observation_id": oid,
            "relation_symbol": "composes",
            "participants": participants,
            "context": [["phase", phase], ["permission", permission]],
        }

    q = [
        row(f"cf-{seed}-q-pos-1", [f"cf-{seed}-role-0-0", f"cf-{seed}-role-1-0", f"cf-{seed}-role-2-0"]),
        row(f"cf-{seed}-q-neg-context", [f"cf-{seed}-role-0-0", f"cf-{seed}-role-1-0", f"cf-{seed}-role-2-0"], permission="denied"),
        row(f"cf-{seed}-q-pos-2", [f"cf-{seed}-role-0-1", f"cf-{seed}-role-1-1", f"cf-{seed}-role-2-1"]),
        row(f"cf-{seed}-q-neg-role", [f"cf-{seed}-role-0-1", f"cf-{seed}-role-1-1", f"cf-{seed}-duplicate-a"]),
        row(f"cf-{seed}-q-neg-phase", [f"cf-{seed}-role-0-1", f"cf-{seed}-role-1-1", f"cf-{seed}-role-2-1"], phase="inactive"),
    ]
    return support, objects, q, [True, False, True, False, False]


class CompositionalFeatureTests(unittest.TestCase):
    def test_discovers_pair_feature_when_no_single_attribute_separates_roles(self):
        support, objects, rows, labels = _episode()
        learner = CompositionalFeatureLearner(support, max_feature_terms=2)
        learner.add_query_objects(objects)
        first = learner.predict(rows[0])
        self.assertEqual(first["decision_status"], "ABSTAIN_INCONSISTENT")
        revision = learner.revise(rows[0], labels[0])
        self.assertEqual(revision["operation"], "expand")
        self.assertEqual(revision["status"], "PROVISIONAL")
        # A single positive is not sufficient for a prediction.
        self.assertEqual(learner.predict(rows[2])["decision_status"], "ABSTAIN_AMBIGUOUS")

        learner.revise(rows[1], labels[1])
        decision = learner.predict(rows[2])
        self.assertEqual(decision["decision_status"], "PREDICT")
        self.assertTrue(decision["prediction"])

        candidates = list(learner._candidates)
        self.assertTrue(any(candidate.feature_keys == ("color", "texture") for candidate in candidates))
        self.assertFalse(any(candidate.feature_keys == ("color",) for candidate in candidates))
        self.assertFalse(any(candidate.feature_keys == ("texture",) for candidate in candidates))

    def test_role_and_context_counterexamples_reject_composite_candidate(self):
        support, objects, rows, labels = _episode()
        learner = CompositionalFeatureLearner(support, max_feature_terms=2)
        learner.add_query_objects(objects)
        learner.revise(rows[0], labels[0])
        learner.revise(rows[1], labels[1])
        self.assertTrue(learner.predict(rows[3])["prediction"])
        learner.revise(rows[2], labels[2])
        role = learner.revise(rows[3], labels[3])
        self.assertEqual(role["status"], "IDENTIFIED")
        self.assertFalse(learner.predict(rows[3])["prediction"])
        phase = learner.revise(rows[4], labels[4])
        self.assertEqual(phase["status"], "IDENTIFIED")
        self.assertFalse(learner.predict(rows[4])["prediction"])

    def test_feature_proposal_budget_fails_closed(self):
        support, objects, rows, labels = _episode()
        learner = CompositionalFeatureLearner(support, proposal_budget=1, max_feature_terms=3)
        learner.add_query_objects(objects)
        result = learner.revise(rows[0], labels[0])
        self.assertTrue(result["budget_exceeded"])
        self.assertEqual(result["operation"], "abstain")
        self.assertEqual(learner.predict(rows[0])["decision_status"], "ABSTAIN_BUDGET")

    def test_duplicate_reveal_is_rejected(self):
        support, objects, rows, labels = _episode()
        learner = CompositionalFeatureLearner(support, max_feature_terms=2)
        learner.add_query_objects(objects)
        learner.revise(rows[0], labels[0])
        with self.assertRaisesRegex(ValueError, "already been revised"):
            learner.revise(rows[0], labels[0])


if __name__ == "__main__":
    unittest.main()
