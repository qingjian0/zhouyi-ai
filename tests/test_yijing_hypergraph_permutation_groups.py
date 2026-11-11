import unittest

from prototype.yijing_hypergraph_permutation_groups import (
    PermutationGroupError,
    SlotPermutationEvidence,
    compare_symmetry_groups,
    learn_slot_permutation_group,
)


def ev(permutation, evidence_id, compatible=True):
    return SlotPermutationEvidence(tuple(permutation), evidence_id, compatible)


class PartialPermutationGroupTests(unittest.TestCase):
    def test_single_transposition_generates_order_two_subgroup(self):
        swap01 = (1, 0, 2)
        report = learn_slot_permutation_group(
            3, (ev(swap01, "e1"), ev(swap01, "e2"))
        )
        self.assertEqual(report.generated_group, ((0, 1, 2), swap01))
        self.assertEqual(report.directly_supported_generators, (swap01,))

    def test_two_transpositions_generate_full_s3(self):
        swap01 = (1, 0, 2)
        swap12 = (0, 2, 1)
        report = learn_slot_permutation_group(
            3, (
                ev(swap01, "a"), ev(swap01, "b"),
                ev(swap12, "c"), ev(swap12, "d"),
            )
        )
        self.assertEqual(len(report.generated_group), 6)
        self.assertEqual(len(report.closure_only_elements), 3)

    def test_conflicting_evidence_blocks_generator(self):
        swap01 = (1, 0, 2)
        report = learn_slot_permutation_group(
            3, (
                ev(swap01, "a"), ev(swap01, "b"),
                ev(swap01, "c", False),
            )
        )
        self.assertEqual(report.generated_group, ((0, 1, 2),))
        self.assertEqual(report.support[0].status, "CONTRADICTED")

    def test_distinct_evidence_support_required(self):
        swap01 = (1, 0, 2)
        report = learn_slot_permutation_group(
            3, (ev(swap01, "same"), ev(swap01, "same"))
        )
        self.assertEqual(report.generated_group, ((0, 1, 2),))
        self.assertEqual(report.support[0].status, "UNRESOLVED")

    def test_group_closure_budget_fails_closed(self):
        swap01 = (1, 0, 2)
        swap12 = (0, 2, 1)
        with self.assertRaises(PermutationGroupError):
            learn_slot_permutation_group(
                3, (ev(swap01, "a"), ev(swap01, "b"),
                    ev(swap12, "c"), ev(swap12, "d")),
                max_group_elements=4,
            )

    def test_invalid_permutation_fails_closed(self):
        with self.assertRaises(PermutationGroupError):
            learn_slot_permutation_group(
                3, (ev((0, 0, 2), "a"),)
            )

    def test_new_context_breaks_s3_to_c2(self):
        s3 = tuple(__import__("itertools").permutations(range(3)))
        c2 = ((0, 1, 2), (1, 0, 2))
        transition = compare_symmetry_groups(s3, c2)
        self.assertEqual(transition.relation, "SYMMETRY_BROKEN")
        self.assertEqual(transition.from_group_order, 6)
        self.assertEqual(transition.to_group_order, 2)
        self.assertEqual(len(transition.removed_permutations), 4)

    def test_non_group_input_fails_closed(self):
        identity = (0, 1, 2)
        swap01 = (1, 0, 2)
        swap12 = (0, 2, 1)
        with self.assertRaises(PermutationGroupError):
            compare_symmetry_groups((identity, swap01), (identity, swap12))

    def test_group_expansion_and_reconfiguration(self):
        identity = (0, 1, 2)
        swap01 = (1, 0, 2)
        swap12 = (0, 2, 1)
        self.assertEqual(
            compare_symmetry_groups((identity,), (identity, swap01)).relation,
            "SYMMETRY_EXPANDED",
        )
        self.assertEqual(
            compare_symmetry_groups(
                (identity, swap01), (identity, swap12)
            ).relation,
            "RECONFIGURED",
        )


if __name__ == "__main__":
    unittest.main()
