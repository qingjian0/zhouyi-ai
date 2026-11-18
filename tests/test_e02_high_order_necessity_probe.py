import unittest
from prototype.e02_high_order_necessity_probe import run_parity_probe

class HighOrderNecessityTests(unittest.TestCase):
    def test_pairwise_cannot_represent_three_way_parity_but_triple_can(self):
        result=run_parity_probe()
        self.assertEqual(result["examples"],8)
        self.assertEqual(result["pairwise_hypotheses_checked"],15625)
        self.assertEqual(result["pairwise_best_correct"],6)
        self.assertEqual(result["pairwise_best_accuracy"],0.75)
        self.assertEqual(result["third_order_correct"],8)
        self.assertEqual(result["third_order_accuracy"],1.0)
        self.assertIn("does not prove",result["interpretation"])

if __name__=="__main__":unittest.main()
