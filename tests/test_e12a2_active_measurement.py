import unittest
from prototype.e12a2_active_measurement import Probe, expected_information_gain, posterior_after_observation, select_probe

class ActiveMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.priors = {"H0": 0.5, "H1": 0.5}

    def test_balanced_split_yields_one_bit_and_is_selected(self):
        p = Probe("split", 1.0, {"zero":{"H0":1.0,"H1":0.0},"one":{"H0":0.0,"H1":1.0}})
        self.assertAlmostEqual(expected_information_gain(self.priors, p), 1.0)
        self.assertEqual(select_probe(self.priors, [p], 1.0)["selected"], "split")

    def test_agreement_probe_has_zero_information(self):
        p = Probe("same", 1.0, {"yes":{"H0":1.0,"H1":1.0}})
        self.assertEqual(select_probe(self.priors, [p], 1.0)["status"], "NO_DISCRIMINATING_ACTION")

    def test_cost_normalization_can_prefer_cheaper_lower_gain(self):
        high = Probe("high", 10.0, {"a":{"H0":0.75,"H1":0.25},"b":{"H0":0.25,"H1":0.75}})
        low = Probe("low", 1.0, {"a":{"H0":0.6,"H1":0.4},"b":{"H0":0.4,"H1":0.6}})
        self.assertEqual(select_probe(self.priors, [high, low], 10.0)["selected"], "low")

    def test_tie_breaks_by_cost_then_id(self):
        a = Probe("z-action", 2.0, {"a":{"H0":1.0,"H1":0.0},"b":{"H0":0.0,"H1":1.0}})
        b = Probe("a-action", 1.0, {"a":{"H0":1.0,"H1":0.0},"b":{"H0":0.0,"H1":1.0}})
        self.assertEqual(select_probe(self.priors, [a, b], 2.0)["selected"], "a-action")

    def test_budget_exhaustion_is_explicit(self):
        p = Probe("costly", 3.0, {"x":{"H0":1.0,"H1":1.0}})
        self.assertEqual(select_probe(self.priors, [p], 2.0)["status"], "BUDGET_EXHAUSTED")

    def test_impossible_revealed_outcome_is_inconsistent(self):
        p = Probe("split", 1.0, {"zero":{"H0":1.0,"H1":0.0},"one":{"H0":0.0,"H1":1.0}})
        r = posterior_after_observation({"H0": 1.0, "H1": 0.0}, p, "one")
        self.assertEqual(r["status"], "INCONSISTENT")
        self.assertIsNone(r["posterior"])

    def test_noisy_bayes_update(self):
        p = Probe("noisy", 1.0, {"positive":{"H0":0.8,"H1":0.2},"negative":{"H0":0.2,"H1":0.8}})
        r = posterior_after_observation(self.priors, p, "positive")
        self.assertAlmostEqual(r["posterior"]["H0"], 0.8)
        self.assertAlmostEqual(r["posterior"]["H1"], 0.2)

    def test_invalid_likelihood_mass_fails_closed(self):
        p = Probe("bad", 1.0, {"only":{"H0":0.4,"H1":0.4}})
        with self.assertRaises(ValueError):
            select_probe(self.priors, [p], 1.0)

    def test_probe_order_does_not_change_selection(self):
        a = Probe("alpha", 1.0, {"x":{"H0":1.0,"H1":0.0},"y":{"H0":0.0,"H1":1.0}})
        b = Probe("beta", 2.0, {"x":{"H0":0.7,"H1":0.3},"y":{"H0":0.3,"H1":0.7}})
        self.assertEqual(select_probe(self.priors,[a,b],2.0)["selected"],
                         select_probe(self.priors,[b,a],2.0)["selected"])

if __name__ == "__main__":
    unittest.main()
