import unittest
from prototype.e12m2_state_space_sweep import run_tiny_state_space_sweep

class E12M2StateSpaceSweepTests(unittest.TestCase):
    def test_exhaustive_tiny_sweep_checks_connectivity_and_kernel(self):
        report = run_tiny_state_space_sweep()
        self.assertGreater(report["profile_count"], 0)
        self.assertTrue(report["all_state_spaces_connected"])
        self.assertTrue(report["all_transition_kernels_symmetric"])
        self.assertTrue(report["all_transition_matrices_doubly_stochastic"])
        self.assertEqual(report["disconnected_profiles"], [])
        self.assertEqual(report["asymmetric_profiles"], [])

    def test_sweep_is_deterministic_and_reports_shapes(self):
        shapes = ((2, 2), (2, 3))
        first = run_tiny_state_space_sweep(shapes=shapes)
        self.assertEqual(first, run_tiny_state_space_sweep(shapes=shapes))
        self.assertEqual(first["shapes"], [[2, 2], [2, 3]])

    def test_shape_and_state_cap_validation(self):
        for kwargs in ({"shapes": ()}, {"shapes": ((4, 2),)}, {"max_states": 0}):
            with self.assertRaises(ValueError):
                run_tiny_state_space_sweep(**kwargs)

if __name__ == "__main__":
    unittest.main()
