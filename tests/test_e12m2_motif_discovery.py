import unittest

from prototype.e12m2_motif_discovery import discover_motifs


class E12M2MotifDiscoveryTests(unittest.TestCase):
    def test_discovers_repeated_non_adjacent_motif_without_labels(self):
        rows = [
            {"a", "x", "c"}, {"a", "y", "c"}, {"a", "z", "c"},
            {"a", "w", "c"}, {"b", "x"}, {"d", "y"},
        ]
        motifs = discover_motifs(rows, min_support=0.5, max_order=2, min_lift=1.2)
        self.assertTrue(motifs)
        self.assertEqual(motifs[0].members, ("a", "c"))

    def test_duplicate_items_inside_row_do_not_inflate_support(self):
        motifs = discover_motifs([["a", "a", "b"], ["a", "b"], ["a"]],
                                 min_support=0.6, max_order=2, min_lift=1.0)
        pair = next(m for m in motifs if m.members == ("a", "b"))
        self.assertEqual(pair.count, 2)
        self.assertAlmostEqual(pair.support, 2 / 3)

    def test_row_and_item_order_do_not_change_results(self):
        rows = [{"a", "b", "c"}, {"a", "b"}, {"a", "c"}, {"z"}]
        first = discover_motifs(rows, min_support=0.25, min_lift=1.0)
        second = discover_motifs(reversed([list(reversed(sorted(r))) for r in rows]),
                                 min_support=0.25, min_lift=1.0)
        self.assertEqual(first, second)

    def test_empty_input_returns_empty(self):
        self.assertEqual(discover_motifs([]), [])

    def test_no_positive_association_returns_empty_at_high_lift(self):
        rows = [{"a", "x"}, {"a", "y"}, {"b", "x"}, {"b", "y"}]
        self.assertEqual(discover_motifs(rows, min_support=0.1, min_lift=1.1), [])

    def test_max_candidates_is_enforced(self):
        rows = [{"a", "b", "c", "d"}] * 10
        motifs = discover_motifs(rows, min_support=1.0, max_order=3,
                                 min_lift=1.0, max_candidates=2)
        self.assertEqual(len(motifs), 2)

    def test_invalid_parameters_are_rejected(self):
        for kwargs in ({"min_support": 0}, {"min_support": 1.1},
                       {"max_order": 1}, {"max_candidates": 0},
                       {"min_lift": 0}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    discover_motifs([{"a", "b"}], **kwargs)

    def test_invalid_item_is_rejected(self):
        with self.assertRaises(ValueError):
            discover_motifs([{"a", ""}])


if __name__ == "__main__":
    unittest.main()
