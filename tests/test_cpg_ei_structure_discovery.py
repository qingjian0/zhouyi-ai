import json
import math
import random
import unittest

from prototype.cpg_ei_mvp import CpgEiTransitionModel, Example, make_dataset
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



    def test_multiseed_structure_discovery_diagnostic(self):
        """Report seed sensitivity; this is a diagnostic, not an acceptance claim."""
        true_support = {
            "hyperedge_2_0_1",
            "hyperedge_2_0_5",
            "hyperedge_2_2_4",
            "hyperedge_3_0_1_3",
            "hyperedge_3_0_3_4",
            "hyperedge_3_1_4_5",
        }
        measurements = []
        for seed in (7, 17, 29):
            train = make_dataset(512, seed=seed, sparse_teacher=True)
            validation = make_dataset(128, seed=seed + 100, sparse_teacher=True)
            model = CpgEiTransitionModel.create(active_relation_indices=set())
            result = grow_relation_graph(
                model, train, validation, rounds=3, edges_per_round=3,
                epochs_per_round=60, gate_l1=0.01, edge_group_l1=0.03,
            )
            discovered = set(result["active_edges"])
            accuracy = result["validation"]["bit_accuracy"]
            recall = len(discovered & true_support) / len(true_support)
            self.assertTrue(math.isfinite(accuracy))
            self.assertGreaterEqual(accuracy, 0.0)
            self.assertLessEqual(accuracy, 1.0)
            self.assertGreaterEqual(recall, 0.0)
            self.assertLessEqual(recall, 1.0)
            self.assertLessEqual(len(discovered), 35)
            measurements.append({
                "seed": seed,
                "validation_bit_accuracy": accuracy,
                "support_recall": recall,
                "active_edges": len(discovered),
            })
        summary = {
            "seeds": len(measurements),
            "mean_validation_bit_accuracy": sum(
                item["validation_bit_accuracy"] for item in measurements
            ) / len(measurements),
            "mean_support_recall": sum(
                item["support_recall"] for item in measurements
            ) / len(measurements),
            "measurements": measurements,
            "candidate_universe_size": 35,
        }
        print("CPGEI_MULTISEED_DIAGNOSTIC " + json.dumps(summary, sort_keys=True))


    def test_label_shuffle_negative_control_reports_structure_recovery(self):
        """A shuffled-label control must be measured, not silently treated as evidence."""
        true_support = {
            "hyperedge_2_0_1",
            "hyperedge_2_0_5",
            "hyperedge_2_2_4",
            "hyperedge_3_0_1_3",
            "hyperedge_3_0_3_4",
            "hyperedge_3_1_4_5",
        }
        train = make_dataset(512, seed=211, sparse_teacher=True)
        validation = make_dataset(128, seed=311, sparse_teacher=True)
        shuffled_targets = [row.target for row in train]
        random.Random(20261112).shuffle(shuffled_targets)
        shuffled_train = [
            Example(row.state, target)
            for row, target in zip(train, shuffled_targets)
        ]
        model = CpgEiTransitionModel.create(active_relation_indices=set())
        result = grow_relation_graph(
            model, shuffled_train, validation, rounds=2, edges_per_round=2,
            epochs_per_round=40, gate_l1=0.01, edge_group_l1=0.03,
        )
        discovered = set(result["active_edges"])
        recall = len(discovered & true_support) / len(true_support)
        false_discovery_count = len(discovered - true_support)
        report = {
            "control": "train_labels_shuffled",
            "validation_bit_accuracy": result["validation"]["bit_accuracy"],
            "support_recall": recall,
            "false_discovery_count": false_discovery_count,
            "active_edge_count": len(discovered),
            "candidate_universe_size": 35,
        }
        self.assertTrue(math.isfinite(report["validation_bit_accuracy"]))
        self.assertGreaterEqual(recall, 0.0)
        self.assertLessEqual(recall, 1.0)
        print("CPGEI_NEGATIVE_CONTROL " + json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    unittest.main()
