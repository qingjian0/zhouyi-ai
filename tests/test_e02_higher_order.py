import unittest
from prototype.e02_higher_order import accuracy, features, make_dataset, run_seed

class E02HigherOrderTests(unittest.TestCase):
    def test_feature_order(self):
        self.assertEqual(len(features((1,-1,1),2)),7)
        self.assertEqual(len(features((1,-1,1),3)),8)
        self.assertEqual(features((1,-1,1),3)[-1],-1.)
    def test_hard_negatives(self):
        for ex in make_dataset(40,19):
            self.assertEqual(len(ex.candidates),4)
            self.assertEqual(len(set(ex.candidates)),4)
            self.assertEqual(ex.candidates[ex.target][0]*ex.candidates[ex.target][1]*ex.candidates[ex.target][2],1)
            for i,x in enumerate(ex.candidates):
                if i!=ex.target: self.assertEqual(x[0]*x[1]*x[2],-1)
    def test_metrics_bounded(self):
        r=run_seed(7,200,60,80)
        for k in ("pairwise_test_accuracy","static_order3_test_accuracy","dynamic_test_accuracy"):
            self.assertGreaterEqual(r[k],0.); self.assertLessEqual(r[k],1.)
    def test_empty_accuracy_rejected(self):
        with self.assertRaises(ValueError): accuracy([], [0.]*7,2)

if __name__=="__main__": unittest.main()
