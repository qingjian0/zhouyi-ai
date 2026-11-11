import unittest
from prototype.e12a9_symbolic_prior_ablation import ACTIONS, HYPOTHESES, prior_weights, run_episode, run_ablation

class SymbolicPriorAblationTests(unittest.TestCase):
    def test_all_arms_share_support_and_normalize(self):
        for arm in ("uniform","yijing_factorized","shuffled_mapping","anti_aligned","random"):
            w=prior_weights(arm,seed=17)
            self.assertEqual(set(w),set(HYPOTHESES))
            self.assertAlmostEqual(sum(w.values()),1.0)
            self.assertTrue(all(v>0 for v in w.values()))
    def test_uniform_prior(self):
        self.assertTrue(all(abs(v-.125)<1e-12 for v in prior_weights("uniform").values()))
    def test_shuffled_control_preserves_weight_multiset(self):
        a=sorted(prior_weights("yijing_factorized").values())
        b=sorted(prior_weights("shuffled_mapping").values())
        for x,y in zip(a,b): self.assertAlmostEqual(x,y)
    def test_random_reproducible(self):
        self.assertEqual(prior_weights("random",seed=3),prior_weights("random",seed=3))
        self.assertNotEqual(prior_weights("random",seed=3),prior_weights("random",seed=4))
    def test_anti_aligned_differs(self):
        self.assertNotEqual(prior_weights("anti_aligned"),prior_weights("yijing_factorized"))
    def test_episode_reproducible_and_commit_precedes_reveal(self):
        a=run_episode("aligned","yijing_factorized",12)
        self.assertEqual(a,run_episode("aligned","yijing_factorized",12))
        for row in a["ledger"]:
            self.assertTrue(row["committed"])
            self.assertTrue(row["revealed"])
    def test_budget_respected(self):
        self.assertLessEqual(run_episode("uniform","uniform",9)["spent"],2.4+1e-12)
    def test_benchmark_families_and_arms(self):
        r=run_ablation(seeds=(0,1,2))
        self.assertEqual(set(r["families"]),{"aligned","uniform","misaligned","permuted"})
        self.assertEqual(set(r["arms"]),{"uniform","yijing_factorized","shuffled_mapping","anti_aligned","random"})
        self.assertEqual(set(r["results"]),set(r["families"]))

if __name__=="__main__": unittest.main()
