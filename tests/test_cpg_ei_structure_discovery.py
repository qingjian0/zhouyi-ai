import unittest

from prototype.cpg_ei_mvp import CpgEiTransitionModel, make_dataset
from prototype.cpg_ei_structure_discovery import grow_relation_graph


class TestCpgEiStructureDiscovery(unittest.TestCase):
    def test_residual_growth_and_group_pruning_recover_sparse_support(self):
        train = make_dataset(1024, seed=7, sparse_teacher=True)
        validation = make_dataset(256, seed=8, sparse_teacher=True)
        model = CpgEiTransitionModel.create(active_relation_indices=set())
        result = grow_relation_graph(
            model,
            train,
            validation,
            rounds=5,
            edges_per_round=3,
            epochs_per_round=100,
            gate_l1=0.01,
            edge_group_l1=0.03,
        )
        true_support = {
            "hyperedge_2_0_1",
            "hyperedge_2_0_5",
            "hyperedge_2_2_3",
            "hyperedge_3_0_1_3",
            "hyperedge_3_1_2_4",
            "hyperedge_3_2_3_5",
        }
        discovered = set(result["active_edges"])
        recall = len(discovered & true_support) / len(true_support)
        accuracy = result["validation"]["bit_accuracy"]
        print(
            f"CPGEI_DYNAMIC_STRUCTURE bit_accuracy={accuracy:.6f} "
            f"support_recall={recall:.3f} active_edges={len(discovered)}"
        )
        self.assertGreater(accuracy, 0.90)
        self.assertGreaterEqual(recall, 4 / 6)
        self.assertLessEqual(len(discovered), 18)
        self.assertTrue(all(item["added_edges"] for item in result["trace"]))


if __name__ == "__main__":
    unittest.main()
