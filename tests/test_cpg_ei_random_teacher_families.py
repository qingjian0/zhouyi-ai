import unittest

from prototype.cpg_ei_random_teacher_families import (
    make_splits,
    make_teacher,
    run_benchmark,
)


class TestRandomTeacherFamilies(unittest.TestCase):
    def test_teacher_families_are_distinct_and_splits_disjoint(self):
        first = make_teacher(101)
        second = make_teacher(102)
        self.assertEqual(len(first), 3)
        self.assertEqual(len(set(first)), 3)
        self.assertNotEqual(first, second)
        train, dev, locked = make_splits(first, 10101)
        a, b, c = ({x.state for x in part} for part in (train, dev, locked))
        self.assertEqual((len(a), len(b), len(c)), (32, 16, 16))
        self.assertFalse(a & b)
        self.assertFalse(a & c)
        self.assertFalse(b & c)
        self.assertEqual(len(a | b | c), 64)

    def test_small_benchmark_emits_bounded_metrics(self):
        report = run_benchmark(family_seeds=(101, 102), epochs=2)
        self.assertEqual(report["teacher_family_count"], 2)
        self.assertEqual(len(report["records"]), 2)
        self.assertTrue(report["summary"]["all_losses_finite"])
        self.assertEqual(report["summary"]["exact_support_recovery_count"] >= 0, True)
        self.assertEqual(
            all(a["union_states"] == 64 for a in report["split_audits"]),
            True,
        )


if __name__ == "__main__":
    unittest.main()
