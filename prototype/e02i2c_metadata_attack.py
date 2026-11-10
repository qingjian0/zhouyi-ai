"""E02-I2-C-E metadata-only leakage attackers.

The attacker receives ObservationView fields only. Evaluator-owned labels,
episode IDs, seeds and split routing metadata are handled outside this module.
No evidence polarity or literal candidate signature is read by M0/M1.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

from prototype.e02i2c_hidden_event_benchmark import (
    EventType,
    ObservationView,
    SUPPORTED_EVENTS,
    _build_episodes,
    _adjudicator,
)


FeatureRow = dict[str, str]


def _bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    if value == 2:
        return "2"
    if value <= 4:
        return "3-4"
    return "5+"


def _length_bucket(value: str) -> str:
    size = len(value)
    if size <= 8:
        return "0-8"
    if size <= 16:
        return "9-16"
    if size <= 32:
        return "17-32"
    return "33+"


def _char_shape(value: str) -> str:
    has_alpha = any(ch.isalpha() for ch in value)
    has_digit = any(ch.isdigit() for ch in value)
    has_punct = any(not ch.isalnum() for ch in value)
    return f"a{int(has_alpha)}d{int(has_digit)}p{int(has_punct)}"


def _add_identifier_features(features: FeatureRow, observation: ObservationView) -> None:
    packets = observation.evidence
    features["id.evidence_count"] = _bucket(len(packets))
    features["id.evidence_prefixes"] = ",".join(sorted({
        packet.evidence_id.split("-", 1)[0] for packet in packets
    })) or "none"
    features["id.sample_prefixes"] = ",".join(sorted({
        packet.sample_id.split("-", 1)[0] for packet in packets
    })) or "none"
    features["id.raw_schemes"] = ",".join(sorted({
        packet.raw_observation_ref.split(":", 1)[0] for packet in packets
    })) or "none"
    for field_name, values in (
        ("evidence", [packet.evidence_id for packet in packets]),
        ("sample", [packet.sample_id for packet in packets]),
        ("raw", [packet.raw_observation_ref for packet in packets]),
    ):
        features[f"id.{field_name}_lengths"] = ",".join(sorted({
            _length_bucket(value) for value in values
        })) or "none"
        features[f"id.{field_name}_shapes"] = ",".join(sorted({
            _char_shape(value) for value in values
        })) or "none"
        features[f"id.{field_name}_duplicates"] = _bucket(
            len(values) - len(set(values))
        )
    features["id.same_value_cross_field"] = str(any(
        packet.evidence_id == packet.sample_id
        or packet.evidence_id == packet.raw_observation_ref
        or packet.sample_id == packet.raw_observation_ref
        for packet in packets
    ))
    features["id.token_length_relation"] = str(all(
        len(packet.evidence_id.removeprefix("ev-"))
        == len(packet.sample_id.removeprefix("sample-"))
        for packet in packets
    ))


def _add_operational_features(
    features: FeatureRow, observation: ObservationView
) -> None:
    packets = observation.evidence
    opportunities = observation.opportunities
    windows = sorted({item.window for item in opportunities})
    features["op.environment_values"] = ",".join(sorted({
        item.environment for item in opportunities
    })) or "none"
    features["op.evidence_count"] = _bucket(len(packets))
    features["op.sample_count"] = _bucket(len({item.sample_id for item in packets}))
    features["op.window_count"] = _bucket(len(windows))
    features["op.window_pattern"] = ",".join(
        str(value) for value in (
            windows if len(windows) <= 5 else [windows[0], windows[-1]]
        )
    ) or "none"
    features["op.window_gaps"] = ",".join(
        str(right - left) for left, right in zip(windows, windows[1:])
    ) or "none"
    per_window = Counter(item.window for item in packets)
    features["op.records_per_window"] = ",".join(
        _bucket(per_window.get(window, 0)) for window in windows
    ) or "none"
    features["op.expected_samples"] = ",".join(sorted({
        _bucket(item.expected_samples) for item in opportunities
    })) or "none"
    features["op.observed_samples"] = ",".join(sorted({
        _bucket(item.observed_samples) for item in opportunities
    })) or "none"
    features["op.coverage"] = ",".join(sorted({
        "low" if item.coverage < 0.5 else "mid" if item.coverage < 0.8 else "high"
        for item in opportunities
    })) or "none"
    features["op.missing_reason"] = ",".join(sorted({
        item.missing_reason.value if item.missing_reason else "complete"
        for item in opportunities
    })) or "none"
    features["op.source_version_present"] = str(any(
        item.source_version_id is not None for item in packets
    ))
    features["op.source_version_count"] = _bucket(len({
        item.source_version_id for item in packets
        if item.source_version_id is not None
    }))
    features["op.sample_reuse"] = _bucket(
        len(packets) - len({item.sample_id for item in packets})
    )
    features["op.evidence_sample_cardinality"] = (
        f"{len(packets)}:{len({item.sample_id for item in packets})}"
    )


def _add_context_shape_features(
    features: FeatureRow, observation: ObservationView
) -> None:
    identity = observation.identity
    features["ctx.identity_present"] = str(identity is not None)
    features["ctx.identity_status"] = identity.status if identity else "none"
    signature = observation.candidate_signature or ""
    features["ctx.candidate_length"] = _length_bucket(signature) if signature else "none"
    features["ctx.candidate_shape"] = (
        f"amp{int('&' in signature)}"
        f"xor{int('^' in signature)}"
        f"or{int('|' in signature)}"
        f"punct{sum(not ch.isalnum() for ch in signature)}"
        if signature else "none"
    )


def extract_features(observation: ObservationView, tier: str) -> FeatureRow:
    """Extract a strict feature allowlist for M0, M1 or M2.

    Deliberately does not read packet.polarity, packet.candidate_signature,
    packet.split, identity.signature, identity.identity_id, or version IDs.
    """
    if tier not in {"M0", "M1", "M2"}:
        raise ValueError("tier must be M0, M1 or M2")
    features: FeatureRow = {}
    _add_identifier_features(features, observation)
    if tier in {"M1", "M2"}:
        _add_operational_features(features, observation)
    if tier == "M2":
        _add_context_shape_features(features, observation)
    return features


def _majority(labels: Iterable[str]) -> str:
    counts = Counter(labels)
    if not counts:
        raise ValueError("training labels cannot be empty")
    maximum = max(counts.values())
    return sorted(label for label, count in counts.items() if count == maximum)[0]


def predict_majority(train_labels: list[str], count: int) -> list[str]:
    return [_majority(train_labels)] * count


@dataclass
class CategoricalNaiveBayes:
    alpha: float = 1.0

    def fit(self, rows: list[FeatureRow], labels: list[str]) -> "CategoricalNaiveBayes":
        if not rows or len(rows) != len(labels):
            raise ValueError("rows and labels must be non-empty and aligned")
        self.classes = tuple(sorted(set(labels)))
        self.class_counts = Counter(labels)
        self.feature_counts: dict[str, dict[str, Counter[str]]] = defaultdict(
            lambda: defaultdict(Counter)
        )
        self.vocabularies: dict[str, set[str]] = defaultdict(set)
        for row, label in zip(rows, labels):
            for feature, value in row.items():
                self.feature_counts[feature][label][value] += 1
                self.vocabularies[feature].add(value)
        self.feature_names = tuple(sorted({
            feature for row in rows for feature in row
        }))
        return self

    def predict_one(self, row: FeatureRow) -> str:
        total = sum(self.class_counts.values())
        scores: dict[str, float] = {}
        for label in self.classes:
            score = math.log(self.class_counts[label] / total)
            for feature in self.feature_names:
                value = row.get(feature, "<missing>")
                vocabulary_size = len(self.vocabularies[feature]) + 1
                denominator = (
                    self.class_counts[label]
                    + self.alpha * vocabulary_size
                )
                numerator = (
                    self.feature_counts[feature][label][value] + self.alpha
                )
                score += math.log(numerator / denominator)
            scores[label] = score
        best = max(scores.values())
        return sorted(label for label, score in scores.items()
                      if abs(score - best) < 1e-12)[0]

    def predict(self, rows: list[FeatureRow]) -> list[str]:
        return [self.predict_one(row) for row in rows]


def _entropy(labels: list[str]) -> float:
    counts = Counter(labels)
    total = len(labels)
    return -sum(
        (count / total) * math.log2(count / total)
        for count in counts.values()
    )


@dataclass
class ShallowCategoricalTree:
    max_depth: int = 3

    def fit(self, rows: list[FeatureRow], labels: list[str]) -> "ShallowCategoricalTree":
        if not rows or len(rows) != len(labels):
            raise ValueError("rows and labels must be non-empty and aligned")
        self.feature_names = tuple(sorted({
            feature for row in rows for feature in row
        }))
        self.tree = self._build(rows, labels, self.feature_names, 0)
        return self

    def _build(
        self, rows: list[FeatureRow], labels: list[str],
        available: tuple[str, ...], depth: int,
    ):
        majority = _majority(labels)
        if depth >= self.max_depth or len(set(labels)) == 1 or not available:
            return ("leaf", majority)
        parent_entropy = _entropy(labels)
        best = None
        for feature in available:
            values = sorted({row.get(feature, "<missing>") for row in rows})
            for value in values:
                left_indices = [i for i, row in enumerate(rows)
                                if row.get(feature, "<missing>") == value]
                left_set = set(left_indices)
                right_indices = [i for i in range(len(rows)) if i not in left_set]
                if not left_indices or not right_indices:
                    continue
                left_labels = [labels[i] for i in left_indices]
                right_labels = [labels[i] for i in right_indices]
                remainder = (
                    len(left_labels) / len(labels) * _entropy(left_labels)
                    + len(right_labels) / len(labels) * _entropy(right_labels)
                )
                gain = parent_entropy - remainder
                candidate = (gain, feature, value, left_indices, right_indices)
                if best is None or (gain, feature, value) > (best[0], best[1], best[2]):
                    best = candidate
        if best is None or best[0] <= 1e-12:
            return ("leaf", majority)
        _, feature, value, left_indices, right_indices = best
        next_available = tuple(item for item in available if item != feature)
        left = self._build(
            [rows[i] for i in left_indices], [labels[i] for i in left_indices],
            next_available, depth + 1,
        )
        right = self._build(
            [rows[i] for i in right_indices], [labels[i] for i in right_indices],
            next_available, depth + 1,
        )
        return ("split", feature, value, left, right, majority)

    def predict_one(self, row: FeatureRow) -> str:
        node = self.tree
        while node[0] == "split":
            _, feature, value, left, right, fallback = node
            node = left if row.get(feature, "<missing>") == value else right
            if node is None:
                return fallback
        return node[1]

    def predict(self, rows: list[FeatureRow]) -> list[str]:
        return [self.predict_one(row) for row in rows]


def _metrics(truth: list[str], predicted: list[str]) -> dict:
    labels = tuple(sorted(set(truth) | set(predicted)))
    per_class = {}
    f1_values = []
    confusion = {actual: {guess: 0 for guess in labels} for actual in labels}
    for actual, guess in zip(truth, predicted):
        confusion[actual][guess] += 1
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[actual][label] for actual in labels if actual != label)
        fn = sum(confusion[label][guess] for guess in labels if guess != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(value == label for value in truth),
        }
    return {
        "accuracy": sum(a == p for a, p in zip(truth, predicted)) / len(truth),
        "macro_f1": sum(f1_values) / len(f1_values),
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def _seed_block(episode_id: str, start_seed: int) -> int:
    seed = int(episode_id.rsplit("-", 1)[1])
    return (seed - start_seed) // len(SUPPORTED_EVENTS)


def _percentile_interval(values: list[float]) -> list[float]:
    ordered = sorted(values)
    return [
        round(ordered[int(0.025 * (len(ordered) - 1))], 4),
        round(ordered[int(0.975 * (len(ordered) - 1))], 4),
    ]


def _bootstrap_metrics(
    truth: list[str], predictions: list[str], majority_predictions: list[str],
    blocks: list[int], *, samples: int, seed: int,
) -> dict:
    grouped: dict[int, list[int]] = defaultdict(list)
    for index, block in enumerate(blocks):
        grouped[block].append(index)
    block_ids = sorted(grouped)
    rng = random.Random(seed)
    attack_f1, attack_accuracy, baseline_f1, lifts = [], [], [], []
    for _ in range(samples):
        selected = [rng.choice(block_ids) for _ in block_ids]
        indices = [index for block in selected for index in grouped[block]]
        truth_sample = [truth[i] for i in indices]
        attack = _metrics(truth_sample, [predictions[i] for i in indices])
        baseline = _metrics(truth_sample, [majority_predictions[i] for i in indices])
        attack_f1.append(attack["macro_f1"])
        attack_accuracy.append(attack["accuracy"])
        baseline_f1.append(baseline["macro_f1"])
        lifts.append(attack["macro_f1"] - baseline["macro_f1"])
    return {
        "macro_f1_ci_95": _percentile_interval(attack_f1),
        "accuracy_ci_95": _percentile_interval(attack_accuracy),
        "majority_macro_f1_ci_95": _percentile_interval(baseline_f1),
        "macro_f1_lift_ci_95": _percentile_interval(lifts),
        "bootstrap_samples": samples,
        "resampling_unit": "seed_block",
    }


def run_metadata_attack(
    *, seeds: int = 30, train_start_seed: int = 1000,
    gate_start_seed: int = 10000, bootstrap_samples: int = 1000,
) -> dict:
    if seeds < 30:
        raise ValueError("the preregistered attack requires at least 30 seeds per event")
    train_end = train_start_seed + seeds * len(SUPPORTED_EVENTS)
    gate_end = gate_start_seed + seeds * len(SUPPORTED_EVENTS)
    if train_start_seed < 0 or gate_start_seed < 0 or not (
        train_end <= gate_start_seed or gate_end <= train_start_seed
    ):
        raise ValueError("Train and Gate seed ranges must be disjoint")
    if bootstrap_samples < 100:
        raise ValueError("at least 100 bootstrap samples are required")

    train_episodes = _build_episodes(
        seeds=seeds, start_seed=train_start_seed, split="train"
    )
    gate_episodes = _build_episodes(
        seeds=seeds, start_seed=gate_start_seed, split="gate"
    )
    train_labels = [episode.truth.value for episode in train_episodes]
    gate_labels = [episode.truth.value for episode in gate_episodes]
    results = {}
    for tier in ("M0", "M1", "M2"):
        train_rows = [extract_features(ep.observation, tier) for ep in train_episodes]
        gate_rows = [extract_features(ep.observation, tier) for ep in gate_episodes]
        majority_label = _majority(train_labels)
        majority_predictions = [majority_label] * len(gate_labels)
        attackers = {
            "majority": majority_predictions,
            "categorical_naive_bayes": CategoricalNaiveBayes().fit(
                train_rows, train_labels
            ).predict(gate_rows),
            "decision_tree_depth_3": ShallowCategoricalTree(max_depth=3).fit(
                train_rows, train_labels
            ).predict(gate_rows),
        }
        blocks = [
            _seed_block(ep.episode_id, gate_start_seed) for ep in gate_episodes
        ]
        tier_results = {}
        for name, predictions in attackers.items():
            tier_results[name] = _metrics(gate_labels, predictions)
            tier_results[name]["per_seed_block"] = {
                str(block): _metrics(
                    [gate_labels[i] for i, value in enumerate(blocks) if value == block],
                    [predictions[i] for i, value in enumerate(blocks) if value == block],
                )
                for block in sorted(set(blocks))
            }
            interval = _bootstrap_metrics(
                gate_labels, predictions, majority_predictions, blocks,
                samples=bootstrap_samples, seed=20261110,
            )
            tier_results[name]["seed_block_bootstrap"] = interval
            if name != "majority":
                lift = tier_results[name]["macro_f1"] - tier_results["majority"]["macro_f1"]
                tier_results[name]["majority_macro_f1_lift"] = round(lift, 4)
                tier_results[name]["leakage_alarm"] = (
                    tier == "M0"
                    and lift >= 0.05
                    and interval["macro_f1_lift_ci_95"][0] > 0.0
                )

        # Negative control: shuffle Train labels independently of all features.
        # A metadata attacker should lose its predictive signal under this
        # permutation; Gate labels remain untouched and evaluator-only.
        permuted_labels = list(train_labels)
        random.Random(20261110).shuffle(permuted_labels)
        tier_results["negative_control_train_label_permutation"] = {
            "categorical_naive_bayes": _metrics(
                gate_labels,
                CategoricalNaiveBayes().fit(train_rows, permuted_labels).predict(gate_rows),
            ),
            "decision_tree_depth_3": _metrics(
                gate_labels,
                ShallowCategoricalTree(max_depth=3).fit(train_rows, permuted_labels).predict(gate_rows),
            ),
        }
        results[tier] = tier_results
    evidence_aware_predictions = [
        _adjudicator(ep.observation).value for ep in gate_episodes
    ]
    return {
        "benchmark": "E02-I2-C-E-metadata-only-attack",
        "seeds_per_event": seeds,
        "train_episodes": len(train_episodes),
        "gate_episodes": len(gate_episodes),
        "train_seed_range": [train_start_seed, train_end - 1],
        "gate_seed_range": [gate_start_seed, gate_end - 1],
        "split_marker_used_as_feature": False,
        "evaluator_truth_is_attacker_input": False,
        "evidence_aware_reference": _metrics(gate_labels, evidence_aware_predictions),
        "tiers": results,
        "interpretation": (
            "Finite-template leakage audit only; not an open-world generalization result."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--train-start-seed", type=int, default=1000)
    parser.add_argument("--gate-start-seed", type=int, default=10000)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    args = parser.parse_args()
    print(json.dumps(run_metadata_attack(
        seeds=args.seeds,
        train_start_seed=args.train_start_seed,
        gate_start_seed=args.gate_start_seed,
        bootstrap_samples=args.bootstrap_samples,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
