import unittest
from prototype.e10a_structural_ood import build_structural_ood_task
from prototype.e10a_mechanism_learner import E10AMechanismLearner


class StructuralOODTests(unittest.TestCase):
    def test_context_conjunction_composes_on_unseen_query_rows(self):
        support, query, evaluator = build_structural_ood_task(2201)
        learner = E10AMechanismLearner(support)
        learner.add_query_objects(query["objects"])
        truth = {x["observation_id"]: x["valid"] for x in evaluator["query_truth"]}
        predictions = [(learner.predict(row), truth[row["observation_id"]]) for row in query["observations"]]
        self.assertTrue(all(p["decision_status"] == "PREDICT" for p, _ in predictions))
        self.assertTrue(all(p["prediction"] == y for p, y in predictions))
        self.assertEqual(len(learner._candidates), 1)

    def test_support_and_query_object_pools_are_disjoint(self):
        support, query, _ = build_structural_ood_task(2202)
        s = {x["object_id"] for x in support["objects"]}
        q = {x["object_id"] for x in query["objects"]}
        self.assertFalse(s & q)
        self.assertTrue(all(set(row["participants"]) <= q for row in query["observations"]))

    def test_missing_context_conjunct_is_rejected(self):
        support, query, _ = build_structural_ood_task(2203)
        learner = E10AMechanismLearner(support)
        learner.add_query_objects(query["objects"])
        row = dict(query["observations"][0])
        row["context"] = [["phase", "active"]]
        self.assertFalse(learner.predict(row)["prediction"])


if __name__ == "__main__":
    unittest.main()
