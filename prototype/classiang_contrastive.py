"""Deterministic contrastive span learner for evidence-grounded classiang text input.

This CPU-only learner uses a multiclass margin objective and mined hard negatives.
It deliberately does not memorize exact phrases. Scores are ranking signals, not
calibrated probabilities; predictions retain source offsets and can abstain.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re
from typing import Iterable

from prototype.classiang_engine import FeatureAtom, FeatureCandidate, Observation
from prototype.classiang_learning import (
    NONE_LABEL, TextRecord, _candidate_spans, _label, _span_features,
    _validate_record, _split_groups, evaluate,
)


def _sparse(surface: str) -> Counter[str]:
    return Counter(_span_features(surface))


def _dot(left: Counter[str], right: Counter[str]) -> float:
    return sum(value * right.get(key, 0) for key, value in left.items())


def _similarity(left: Counter[str], right: Counter[str]) -> float:
    a, b = set(left), set(right)
    return len(a & b) / len(a | b) if a or b else 0.0


class ContrastiveSpanEncoder:
    """Sparse multiclass margin learner with per-record hard-negative mining."""

    model_type = "classiang-contrastive-span-v1"

    def __init__(self, *, epochs: int = 12, learning_rate: float = 0.25,
                 margin: float = 1.0, hard_negatives_per_record: int = 48,
                 max_tokens: int = 6, max_span_chars: int = 32,
                 max_candidates: int = 20000):
        if isinstance(epochs, bool) or not isinstance(epochs, int) or not 1 <= epochs <= 100:
            raise ValueError("epochs must be an integer in [1, 100]")
        if not math.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("learning_rate must be positive and finite")
        if not math.isfinite(margin) or margin <= 0:
            raise ValueError("margin must be positive and finite")
        if isinstance(hard_negatives_per_record, bool) or not isinstance(hard_negatives_per_record, int) or hard_negatives_per_record < 1:
            raise ValueError("hard_negatives_per_record must be positive")
        self.epochs = epochs
        self.learning_rate = float(learning_rate)
        self.margin = float(margin)
        self.hard_negatives_per_record = hard_negatives_per_record
        self.max_tokens = max_tokens
        self.max_span_chars = max_span_chars
        self.max_candidates = max_candidates
        self.weights: dict[str, Counter[str]] = defaultdict(Counter)
        self.classes: tuple[str, ...] = ()
        self.purpose_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.label_counts: Counter[str] = Counter()
        self.training_records = 0
        self.training_samples = 0
        self.hard_negative_samples = 0
        self.vocabulary_size = 0

    def fit(self, records: Iterable[TextRecord], *, seed: int = 17) -> "ContrastiveSpanEncoder":
        rows = tuple(records)
        if not rows:
            raise ValueError("training records must not be empty")
        samples: list[tuple[Counter[str], str, str]] = []
        self.weights.clear()
        self.purpose_counts.clear()
        self.label_counts.clear()
        hard_count = 0
        rng = random.Random(seed)
        for row in rows:
            _validate_record(row)
            positives = {(a.start_char, a.end_char): a for a in row.annotations}
            positive_vectors = [
                _sparse(row.text[start:end]) for start, end in positives
            ]
            reviewed_negatives = []
            for start, end in row.negative_annotations:
                vector = _sparse(row.text[start:end])
                similarity = max(
                    (_similarity(vector, pos) for pos in positive_vectors),
                    default=0.0,
                )
                reviewed_negatives.append((similarity, start, end, vector))
            # Only explicitly reviewed negative spans are eligible. Unannotated
            # spans are unknown, not negative examples.
            reviewed_negatives.sort(key=lambda item: (-item[0], item[1], item[2]))
            hard = reviewed_negatives[:self.hard_negatives_per_record]
            hard_count += len(hard)
            for (start, end), annotation in positives.items():
                label = _label(annotation)
                samples.append((_sparse(row.text[start:end]), label, "positive"))
                self.label_counts[label] += 1
                for purpose in annotation.purposes:
                    self.purpose_counts[label][purpose] += 1
            samples.extend(
                (vector, NONE_LABEL, "reviewed_hard_negative")
                for _, _, _, vector in hard
            )
        if not any(label != NONE_LABEL for _, label, _ in samples):
            raise ValueError("training data contains no positive annotations")
        if hard_count == 0:
            raise ValueError(
                "contrastive training requires explicitly reviewed negative_annotations; "
                "unannotated spans are unknown, not negatives"
            )
        self.classes = tuple(sorted({label for _, label, _ in samples}))
        for label in self.classes:
            self.weights[label] = Counter()
        positive_order = [i for i, sample in enumerate(samples) if sample[1] != NONE_LABEL]
        negative_order = [i for i, sample in enumerate(samples) if sample[1] == NONE_LABEL]
        hard_start_epoch = max(1, self.epochs // 3)
        for epoch in range(self.epochs):
            # Curriculum: establish positive class structure first, then add
            # reviewed hard negatives to refine the decision boundary.
            order = list(positive_order)
            if epoch >= hard_start_epoch:
                order.extend(negative_order)
            rng.shuffle(order)
            rate = self.learning_rate / math.sqrt(epoch + 1)
            for index in order:
                vector, gold, _kind = samples[index]
                scores = {label: _dot(vector, self.weights[label]) for label in self.classes}
                predicted = max(self.classes, key=lambda label: (scores[label], label))
                best_other = max((scores[label] for label in self.classes if label != gold), default=0.0)
                if predicted != gold or scores[gold] < best_other + self.margin:
                    for feature, value in vector.items():
                        self.weights[gold][feature] += rate * value
                        if predicted != gold:
                            self.weights[predicted][feature] -= rate * value
        self.training_records = len(rows)
        self.training_samples = len(samples)
        self.hard_negative_samples = hard_count
        self.vocabulary_size = len({feature for vector, _, _ in samples for feature in vector})
        return self

    def _scores(self, surface: str) -> dict[str, float]:
        vector = _sparse(surface)
        return {label: _dot(vector, self.weights[label]) for label in self.classes}

    def predict(self, *, observation_id: str, subject_id: str, domain: str,
                source_id: str, text: str, context: tuple[str, ...] = (),
                threshold: float = 0.55, max_features: int = 64) -> Observation:
        for value in (observation_id, subject_id, domain, source_id, text):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("prediction identifiers and text must be non-empty")
        if not 0.0 < threshold < 1.0 or max_features < 1:
            raise ValueError("invalid prediction threshold or feature budget")
        if not self.classes:
            raise ValueError("model has not been trained")
        candidates = _candidate_spans(
            text, max_tokens=self.max_tokens, max_span_chars=self.max_span_chars,
            max_candidates=self.max_candidates,
        )
        proposed = []
        for start, end in candidates:
            scores = self._scores(text[start:end])
            peak = max(scores.values())
            exp_scores = {key: math.exp(max(-60.0, min(60.0, value - peak))) for key, value in scores.items()}
            total = sum(exp_scores.values())
            probabilities = {key: value / total for key, value in exp_scores.items()}
            label = max(self.classes, key=lambda key: (scores[key], key))
            confidence = probabilities[label]
            if label == NONE_LABEL or confidence < threshold:
                continue
            dimension, value = json.loads(label)
            total_annotations = self.label_counts[label]
            purposes = tuple(sorted(
                (purpose, count / total_annotations)
                for purpose, count in self.purpose_counts[label].items()
            )) if total_annotations else ()
            proposed.append((confidence, start, end, dimension, value, purposes))
        proposed.sort(key=lambda item: (-item[0], item[1], -(item[2] - item[1])))
        accepted = []
        for item in proposed:
            _, start, end, *_ = item
            if any(start < other[2] and other[1] < end for other in accepted):
                continue
            accepted.append(item)
            if len(accepted) >= max_features:
                break
        accepted.sort(key=lambda item: (item[1], item[2]))
        features = tuple(
            FeatureCandidate(
                feature_id=f"{observation_id}:contrastive:{index:04d}",
                atom=FeatureAtom(dimension, value),
                evidence_refs=(f"text:{source_id}:chars:{start}-{end}",),
                purpose_scores=purposes,
            )
            for index, (_, start, end, dimension, value, purposes) in enumerate(accepted)
        )
        evidence = tuple(sorted({
            ref for feature in features for ref in feature.evidence_refs
        })) or (f"text:{source_id}:document",)
        result = Observation(observation_id, subject_id, domain, evidence, features, context)
        result.validate()
        return result

    def to_dict(self) -> dict:
        return {
            "schema_version": 1, "model_type": self.model_type,
            "epochs": self.epochs, "learning_rate": self.learning_rate,
            "margin": self.margin, "hard_negatives_per_record": self.hard_negatives_per_record,
            "max_tokens": self.max_tokens, "max_span_chars": self.max_span_chars,
            "max_candidates": self.max_candidates, "classes": list(self.classes),
            "weights": {label: dict(weights) for label, weights in self.weights.items()},
            "purpose_counts": {label: dict(counts) for label, counts in self.purpose_counts.items()},
            "label_counts": dict(self.label_counts), "training_records": self.training_records,
            "training_samples": self.training_samples, "hard_negative_samples": self.hard_negative_samples,
            "vocabulary_size": self.vocabulary_size,
        }

    def save(self, path: str | Path) -> str:
        payload = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(payload).hexdigest()
        envelope = json.dumps({"sha256": digest, "model": self.to_dict()}, ensure_ascii=False, sort_keys=True, indent=2)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(envelope + "\n", encoding="utf-8")
        return digest

    @classmethod
    def load(cls, path: str | Path) -> "ContrastiveSpanEncoder":
        envelope = json.loads(Path(path).read_text(encoding="utf-8"))
        model_data = envelope["model"]
        raw = json.dumps(model_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        if hashlib.sha256(raw).hexdigest() != envelope.get("sha256"):
            raise ValueError("checkpoint digest mismatch")
        if model_data.get("schema_version") != 1 or model_data.get("model_type") != cls.model_type:
            raise ValueError("unsupported contrastive checkpoint")
        model = cls(
            epochs=model_data["epochs"], learning_rate=model_data["learning_rate"],
            margin=model_data["margin"], hard_negatives_per_record=model_data["hard_negatives_per_record"],
            max_tokens=model_data["max_tokens"], max_span_chars=model_data["max_span_chars"],
            max_candidates=model_data["max_candidates"],
        )
        model.classes = tuple(model_data["classes"])
        model.weights = defaultdict(Counter, {label: Counter(values) for label, values in model_data["weights"].items()})
        model.purpose_counts = defaultdict(Counter, {label: Counter(values) for label, values in model_data["purpose_counts"].items()})
        model.label_counts = Counter(model_data["label_counts"])
        model.training_records = model_data["training_records"]
        model.training_samples = model_data["training_samples"]
        model.hard_negative_samples = model_data["hard_negative_samples"]
        model.vocabulary_size = model_data["vocabulary_size"]
        if set(model.classes) != set(model.weights) or not model.classes:
            raise ValueError("checkpoint class index is inconsistent")
        return model


def train_contrastive(records: tuple[TextRecord, ...], *, seed: int = 17,
                      validation_fraction: float = 0.2, threshold: float = 0.55):
    train, validation = _split_groups(records, validation_fraction, seed)
    model = ContrastiveSpanEncoder().fit(train, seed=seed)
    report = {
        "schema_version": 1, "model_type": model.model_type, "seed": seed,
        "train_records": len(train), "validation_records": len(validation),
        "train_groups": sorted({row.group_id or row.subject_id for row in train}),
        "validation_groups": sorted({row.group_id or row.subject_id for row in validation}),
        "group_disjoint": not bool(
            {row.group_id or row.subject_id for row in train}
            & {row.group_id or row.subject_id for row in validation}
        ),
        "training": {
            "records": model.training_records, "samples": model.training_samples,
            "hard_negatives": model.hard_negative_samples,
            "classes": len(model.classes), "vocabulary_size": model.vocabulary_size,
        },
        "validation": evaluate(model, validation, threshold=threshold),
        "limitations": [
            "CPU sparse linear margin baseline, not a pretrained language model",
            "hard negatives are selected only from explicitly reviewed negative_annotations",
            "unannotated spans are treated as unknown, never as negative labels",
            "hard negatives enter after a positive-only warmup curriculum",
            "scores are not calibrated probabilities",
            "no cross-chunk memory or semantic truth guarantee",
        ],
    }
    return model, report
