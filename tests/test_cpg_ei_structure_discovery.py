import itertools
import json
import math
import random
import unittest

from prototype.cpg_ei_mvp import CpgEiTransitionModel, Example, make_dataset
from prototype.cpg_ei_structure_discovery import grow_relation_graph



def make_parity_teacher_dataset(count, seed):
    """Generate a distinct GF(2) parity teacher, not a sampled linear-logit teacher."""
    rng = random.Random(seed)
    triples = ((0, 1, 2), (1, 3, 4), (2, 4, 5))
    rows = []
    for _ in range(count):
        state = tuple(rng.randrange(2) for _ in range(6))
        targets = tuple(
            sum(state[index] for index in triples[head // 2]) % 2
            for head in range(6)
        )
        rows.append(Example(state, targets))
    return rows


def parity_teacher_support():
    triples = ((0, 1, 2), (1, 3, 4), (2, 4, 5))
    support = set()
    for triple in triples:
        support.add("hyperedge_3_" + "_".join(map(str, triple)))
        for pair in itertools.combinations(triple, 2):
            support.add("hyperedge_2_" + "_".join(map(str, pair)))
    return support


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
        for seed in (7, 17, 29, 41, 53, 67, 79, 83, 97, 109):
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
            false_discoveries = len(discovered - true_support)
            measurements.append({
                "seed": seed,
                "validation_bit_accuracy": accuracy,
                "support_recall": recall,
                "support_precision": (
                    len(discovered & true_support) / len(discovered)
                    if discovered else 0.0
                ),
                "false_discovery_count": false_discoveries,
                "active_edges": len(discovered),
                "exact_support_recovered": discovered == true_support,
            })
        accuracies = [item["validation_bit_accuracy"] for item in measurements]
        recalls = [item["support_recall"] for item in measurements]
        active_counts = [item["active_edges"] for item in measurements]
        summary = {
            "seeds": len(measurements),
            "mean_validation_bit_accuracy": sum(accuracies) / len(accuracies),
            "std_validation_bit_accuracy": math.sqrt(
                sum((value - sum(accuracies) / len(accuracies)) ** 2
                    for value in accuracies) / len(accuracies)
            ),
            "min_validation_bit_accuracy": min(accuracies),
            "max_validation_bit_accuracy": max(accuracies),
            "mean_support_recall": sum(recalls) / len(recalls),
            "min_support_recall": min(recalls),
            "max_support_recall": max(recalls),
            "mean_active_edges": sum(active_counts) / len(active_counts),
            "exact_support_recovery_count": sum(
                item["exact_support_recovered"] for item in measurements
            ),
            "total_false_discoveries": sum(
                item["false_discovery_count"] for item in measurements
            ),
            "measurements": measurements,
            "candidate_universe_size": 35,
        }
        print("CPGEI_MULTISEED_DIAGNOSTIC " + json.dumps(summary, sort_keys=True))


    def test_label_shuffle_negative_control_reports_structure_recovery(self):
        """A shuffled-label control must be measured, not silently treated as evidence."""
        true_support = {
            "hyperedge_2_0_1", "hyperedge_2_0_5", "hyperedge_2_2_4",
            "hyperedge_3_0_1_3", "hyperedge_3_0_3_4", "hyperedge_3_1_4_5",
        }
        train = make_dataset(512, seed=211, sparse_teacher=True)
        validation = make_dataset(128, seed=311, sparse_teacher=True)
        shuffled_targets = [row.target for row in train]
        random.Random(20261112).shuffle(shuffled_targets)
        shuffled_train = [Example(row.state, target)
                          for row, target in zip(train, shuffled_targets)]
        model = CpgEiTransitionModel.create(active_relation_indices=set())
        result = grow_relation_graph(
            model, shuffled_train, validation, rounds=2, edges_per_round=2,
            epochs_per_round=40, gate_l1=0.01, edge_group_l1=0.03,
        )
        discovered = set(result["active_edges"])
        report = {
            "control": "train_labels_shuffled",
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


    def test_normalized_candidate_score_ablation(self):
        """Paired diagnostic: compare raw vs residual-norm-normalized edge ranking."""
        true_support = {
            "hyperedge_2_0_1", "hyperedge_2_0_5", "hyperedge_2_2_4",
            "hyperedge_3_0_1_3", "hyperedge_3_0_3_4", "hyperedge_3_1_4_5",
        }
        paired = []
        for seed in (7, 17, 29, 41, 53):
            train = make_dataset(512, seed=seed, sparse_teacher=True)
            validation = make_dataset(128, seed=seed + 100, sparse_teacher=True)
            results = {}
            for mode, normalized in (("raw", False), ("normalized", True)):
                model = CpgEiTransitionModel.create(active_relation_indices=set())
                result = grow_relation_graph(
                    model, train, validation, rounds=3, edges_per_round=3,
                    epochs_per_round=60, gate_l1=0.01, edge_group_l1=0.03,
                    normalize_candidate_scores=normalized,
                )
                discovered = set(result["active_edges"])
                results[mode] = {
                    "bit_accuracy": result["validation"]["bit_accuracy"],
                    "support_recall": len(discovered & true_support) / len(true_support),
                    "false_discoveries": len(discovered - true_support),
                    "active_edges": len(discovered),
                    "exact_support": discovered == true_support,
                }
            paired.append({"seed": seed, **results})
        summary = {
            "seeds": len(paired),
            "raw_mean_recall": sum(x["raw"]["support_recall"] for x in paired) / len(paired),
            "normalized_mean_recall": sum(x["normalized"]["support_recall"] for x in paired) / len(paired),
            "raw_exact_recovery": sum(x["raw"]["exact_support"] for x in paired),
            "normalized_exact_recovery": sum(x["normalized"]["exact_support"] for x in paired),
            "raw_mean_false_discoveries": sum(x["raw"]["false_discoveries"] for x in paired) / len(paired),
            "normalized_mean_false_discoveries": sum(x["normalized"]["false_discoveries"] for x in paired) / len(paired),
            "paired": paired,
        }
        print("CPGEI_NORMALIZED_SCORE_ABLATION " + json.dumps(summary, sort_keys=True))


    def test_second_teacher_family_gf2_parity_structure_diagnostic(self):
        """Measure recovery on a distinct deterministic parity-generating mechanism."""
        true_support = parity_teacher_support()
        measurements = []
        for seed in (11, 23, 37):
            train = make_parity_teacher_dataset(512, seed)
            validation = make_parity_teacher_dataset(128, seed + 1000)
            model = CpgEiTransitionModel.create(active_relation_indices=set())
            result = grow_relation_graph(
                model, train, validation, rounds=4, edges_per_round=3,
                epochs_per_round=60, gate_l1=0.01, edge_group_l1=0.03,
            )
            discovered = set(result["active_edges"])
            accuracy = result["validation"]["bit_accuracy"]
            recall = len(discovered & true_support) / len(true_support)
            precision = len(discovered & true_support) / len(discovered) if discovered else 0.0
            self.assertTrue(math.isfinite(accuracy))
            self.assertGreaterEqual(accuracy, 0.0)
            self.assertLessEqual(accuracy, 1.0)
            self.assertGreaterEqual(recall, 0.0)
            self.assertLessEqual(recall, 1.0)
            self.assertGreaterEqual(precision, 0.0)
            self.assertLessEqual(precision, 1.0)
            measurements.append({
                "seed": seed,
                "validation_bit_accuracy": accuracy,
                "support_recall": recall,
                "support_precision": precision,
                "false_discovery_count": len(discovered - true_support),
                "active_edges": len(discovered),
                "exact_support_recovered": discovered == true_support,
            })
        summary = {
            "teacher_family": "gf2_three_input_parity",
            "seeds": len(measurements),
            "candidate_universe_size": 35,
            "true_support_size": len(true_support),
            "mean_validation_bit_accuracy": sum(x["validation_bit_accuracy"] for x in measurements) / len(measurements),
            "mean_support_recall": sum(x["support_recall"] for x in measurements) / len(measurements),
            "mean_support_precision": sum(x["support_precision"] for x in measurements) / len(measurements),
            "total_false_discoveries": sum(x["false_discovery_count"] for x in measurements),
            "exact_support_recovery_count": sum(x["exact_support_recovered"] for x in measurements),
            "measurements": measurements,
        }
        print("CPGEI_SECOND_TEACHER " + json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
