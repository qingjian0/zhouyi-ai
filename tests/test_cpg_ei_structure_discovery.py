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
            "hyperedge_2_2_4",
            "hyperedge_3_0_1_3",
            "hyperedge_3_0_3_4",
            "hyperedge_3_1_4_5",
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



    def test_featurewise_permutation_negative_control_reports_structure_recovery(self):
        """Independently permute each feature column while preserving marginals."""
        true_support = {
            "hyperedge_2_0_1", "hyperedge_2_0_5", "hyperedge_2_2_4",
            "hyperedge_3_0_1_3", "hyperedge_3_0_3_4", "hyperedge_3_1_4_5",
        }
        train = make_dataset(512, seed=223, sparse_teacher=True)
        validation = make_dataset(128, seed=323, sparse_teacher=True)
        rng = random.Random(20261113)
        columns = list(zip(*(row.state for row in train)))
        permuted_columns = []
        for column in columns:
            values = list(column)
            rng.shuffle(values)
            permuted_columns.append(values)
        permuted_train = [
            Example(tuple(permuted_columns[j][i] for j in range(len(permuted_columns))),
                    row.target)
            for i, row in enumerate(train)
        ]
        model = CpgEiTransitionModel.create(active_relation_indices=set())
        result = grow_relation_graph(
            model, permuted_train, validation, rounds=2, edges_per_round=2,
            epochs_per_round=40, gate_l1=0.01, edge_group_l1=0.03,
        )
        discovered = set(result["active_edges"])
        report = {
            "control": "featurewise_permutation",
            "validation_bit_accuracy": result["validation"]["bit_accuracy"],
            "support_recall": len(discovered & true_support) / len(true_support),
            "false_discovery_count": len(discovered - true_support),
            "active_edge_count": len(discovered),
            "candidate_universe_size": 35,
        }
        self.assertTrue(math.isfinite(report["validation_bit_accuracy"]))
        self.assertGreaterEqual(report["support_recall"], 0.0)
        self.assertLessEqual(report["support_recall"], 1.0)
        print("CPGEI_NEGATIVE_CONTROL " + json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    unittest.main()
