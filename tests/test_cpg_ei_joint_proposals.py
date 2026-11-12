import itertools
import math
import unittest

from prototype.cpg_ei_mvp import CpgEiTransitionModel, Example, FEATURE_NAMES
from prototype.cpg_ei_joint_proposals import grow_relation_graph_joint_motifs


def parity_rows(count, seed):
    rng = __import__("random").Random(seed)
    triples = ((0, 1, 2), (1, 3, 4), (2, 4, 5))
    rows = []
    for _ in range(count):
        state = tuple(rng.randrange(2) for _ in range(6))
        target = tuple(
            sum(state[index] for index in triples[head // 2]) % 2
            for head in range(6)
        )
        rows.append(Example(state, target))
    return rows


def exact_parity_support():
    support = set()
    for triple in ((0, 1, 2), (1, 3, 4), (2, 4, 5)):
        support.add("hyperedge_3_" + "_".join(map(str, triple)))
        support.update(
            "hyperedge_2_" + "_".join(map(str, pair))
            for pair in itertools.combinations(triple, 2)
        )
    return support


class TestCpgEiJointMotifProposals(unittest.TestCase):
    def test_bounded_joint_search_recovers_synergistic_parity_motifs(self):
        expected = exact_parity_support()
        measurements = []
        for seed in (11, 23):
            train = parity_rows(192, seed)
            validation = parity_rows(128, seed + 1000)
            model = CpgEiTransitionModel.create(active_relation_indices=set())
            result = grow_relation_graph_joint_motifs(
                model,
                train,
                validation,
                max_motifs=3,
                epochs_per_candidate=30,
                gate_l1=0.001,
                edge_group_l1=0.001,
            )
            discovered = set(result["active_edges"])
            recall = len(discovered & expected) / len(expected)
            precision = len(discovered & expected) / len(discovered) if discovered else 0.0
            self.assertEqual(result["candidate_motif_universe_size"], 20)
            self.assertLessEqual(len(result["selected_motifs"]), 3)
            self.assertTrue(math.isfinite(result["validation_binary_cross_entropy"]))
            self.assertGreater(recall, 0.0)
            self.assertGreater(precision, 0.0)
            measurements.append({
                "seed": seed,
                "support_recall": recall,
                "support_precision": precision,
                "active_edges": len(discovered),
                "selected_motifs": len(result["selected_motifs"]),
            })
        print("CPGEI_JOINT_MOTIF_DIAGNOSTIC " + str(measurements))


if __name__ == "__main__":
    unittest.main()
