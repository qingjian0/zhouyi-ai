import itertools
import json
import math
import random
import unittest
from itertools import product
from unittest.mock import patch

from prototype.cpg_ei_mvp import CpgEiTransitionModel, Example
import prototype.cpg_ei_joint_proposals as joint_proposals
from prototype.cpg_ei_joint_proposals import grow_relation_graph_joint_motifs
from prototype.cpg_ei_structure_discovery import grow_relation_graph


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


def support_metrics(result, expected):
    discovered = set(result["active_edges"])
    true_positive = len(discovered & expected)
    return {
        "support_recall": true_positive / len(expected),
        "support_precision": true_positive / len(discovered) if discovered else 0.0,
        "active_edges": len(discovered),
    }


def partition_parity_splits(seed, triples):
    states = list(product((0, 1), repeat=6))
    random.Random(seed).shuffle(states)

    def rows(part):
        return [
            Example(
                state,
                tuple(
                    sum(state[index] for index in triples[head // 2]) % 2
                    for head in range(6)
                ),
            )
            for state in part
        ]

    return rows(states[:40]), rows(states[40:52]), rows(states[52:64])


class TestCpgEiJointMotifProposals(unittest.TestCase):
    def test_proposal_selection_is_disjoint_from_train_and_locked_test(self):
        train_triples = ((0, 1, 2), (1, 3, 4), (2, 4, 5))
        ood_triples = ((0, 2, 4), (1, 2, 5), (0, 3, 5))
        train, proposal, locked_test = partition_parity_splits(77, train_triples)
        _, _, ood_test = partition_parity_splits(77, ood_triples)

        train_states = {row.state for row in train}
        proposal_states = {row.state for row in proposal}
        locked_states = {row.state for row in locked_test}
        self.assertFalse(train_states & proposal_states)
        self.assertFalse(train_states & locked_states)
        self.assertFalse(proposal_states & locked_states)

        model = CpgEiTransitionModel.create(active_relation_indices=set())
        seen_datasets = []
        fitted_datasets = []
        original_bce = joint_proposals._binary_cross_entropy
        original_train = CpgEiTransitionModel.train

        def tracked_bce(candidate, examples):
            seen_datasets.append(examples)
            return original_bce(candidate, examples)

        def tracked_train(candidate, examples, *args, **kwargs):
            fitted_datasets.append(examples)
            return original_train(candidate, examples, *args, **kwargs)

        with (
            patch.object(joint_proposals, "_binary_cross_entropy", tracked_bce),
            patch.object(CpgEiTransitionModel, "train", tracked_train),
        ):
            result = grow_relation_graph_joint_motifs(
                model,
                train,
                locked_test,
                proposal_examples=proposal,
                max_motifs=1,
                epochs_per_candidate=3,
                gate_l1=0.001,
                edge_group_l1=0.001,
            )

        # Baseline and every candidate are ranked only on proposal data.
        # Training must use only train data. Train/test BCE calls occur after
        # selection, in that order, and the locked test is the final read.
        ranking_calls = result["candidate_fits_total"] + 1
        self.assertEqual(len(seen_datasets), ranking_calls + 2)
        self.assertTrue(all(rows is proposal for rows in seen_datasets[:ranking_calls]))
        self.assertIs(seen_datasets[-2], train)
        self.assertIs(seen_datasets[-1], locked_test)
        self.assertGreater(len(fitted_datasets), 1)
        self.assertTrue(all(rows is train for rows in fitted_datasets))
        self.assertEqual(result["proposal_selection_examples"], len(proposal))
        self.assertTrue(math.isfinite(result["training_binary_cross_entropy"]))
        self.assertTrue(math.isfinite(result["validation_binary_cross_entropy"]))

        ood_metrics = joint_proposals.evaluate(model, ood_test)
        self.assertTrue(math.isfinite(ood_metrics["bit_accuracy"]))
        self.assertGreaterEqual(ood_metrics["bit_accuracy"], 0.0)
        self.assertLessEqual(ood_metrics["bit_accuracy"], 1.0)
        print("CPGEI_SPLIT_PROTOCOL " + json.dumps({
            "train_examples": len(train),
            "proposal_selection_examples": len(proposal),
            "locked_test_examples": len(locked_test),
            "ood_rule_family_bit_accuracy": ood_metrics["bit_accuracy"],
            "selected_motifs": result["selected_motifs"],
        }, sort_keys=True))
    def test_bounded_joint_search_recovers_synergistic_parity_motifs(self):
        expected = exact_parity_support()
        measurements = []
        for seed in (11, 23):
            train = parity_rows(128, seed)
            validation = parity_rows(64, seed + 1000)
            model = CpgEiTransitionModel.create(active_relation_indices=set())
            result = grow_relation_graph_joint_motifs(
                model,
                train,
                validation,
                max_motifs=1,
                epochs_per_candidate=12,
                gate_l1=0.001,
                edge_group_l1=0.001,
            )
            metrics = support_metrics(result, expected)
            self.assertEqual(result["candidate_motif_universe_size"], 20)
            self.assertLessEqual(len(result["selected_motifs"]), 1)
            self.assertTrue(math.isfinite(result["validation_binary_cross_entropy"]))
            self.assertGreater(metrics["support_recall"], 0.0)
            self.assertGreater(metrics["support_precision"], 0.0)
            measurements.append({"seed": seed, **metrics,
                                 "selected_motifs": len(result["selected_motifs"])})
        print("CPGEI_JOINT_MOTIF_DIAGNOSTIC " + json.dumps(measurements, sort_keys=True))

    def test_joint_vs_greedy_under_matched_training_pass_budget(self):
        # Joint: 12 baseline passes + (20 + 19 + 18) candidate fits * 12
        # passes = 696. Greedy: 13 growth rounds + final fit, each 50
        # passes = 700. The 0.57% difference is an explicit near-match.
        seed = 11
        train = parity_rows(128, seed)
        validation = parity_rows(64, seed + 1000)
        expected = exact_parity_support()

        joint_model = CpgEiTransitionModel.create(active_relation_indices=set())
        joint = grow_relation_graph_joint_motifs(
            joint_model,
            train,
            validation,
            max_motifs=3,
            epochs_per_candidate=12,
            gate_l1=0.001,
            edge_group_l1=0.001,
        )
        joint_rounds = len(joint["trace"])
        joint_passes = 12 * (
            1 + sum(20 - round_index for round_index in range(joint_rounds))
        )

        greedy_model = CpgEiTransitionModel.create(active_relation_indices=set())
        greedy = grow_relation_graph(
            greedy_model,
            train,
            validation,
            rounds=13,
            edges_per_round=1,
            epochs_per_round=50,
            gate_l1=0.001,
            edge_group_l1=0.001,
        )
        greedy_passes = (13 + 1) * 50
        relative_budget_gap = abs(joint_passes - greedy_passes) / max(
            joint_passes, greedy_passes
        )
        self.assertLessEqual(relative_budget_gap, 0.01)

        comparison = {
            "seed": seed,
            "joint_training_passes": joint_passes,
            "greedy_training_passes": greedy_passes,
            "relative_budget_gap": relative_budget_gap,
            "joint": support_metrics(joint, expected),
            "greedy": support_metrics(greedy, expected),
            "joint_validation_bit_accuracy": joint["validation"]["bit_accuracy"],
            "greedy_validation_bit_accuracy": greedy["validation"]["bit_accuracy"],
            "joint_selected_motifs": len(joint["selected_motifs"]),
        }
        print("CPGEI_MATCHED_COMPUTE_COMPARISON " +
              json.dumps(comparison, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
