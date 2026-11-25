"""Trainable, evidence-grounded text perception for the classiang loop.

The encoder learns feature-label proposals from reviewed source spans. It is a
small CPU-only Naive Bayes baseline, not a foundation model, OCR system, or
proof of semantic understanding. Predictions always retain exact source spans.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import tempfile
from typing import Any, Iterable

from prototype.classiang_engine import FeatureAtom, FeatureCandidate, Observation

SCHEMA_VERSION = 1
NONE_LABEL = "__none__"
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]|[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class TextAnnotation:
    start_char: int
    end_char: int
    dimension: str
    value: str
    purposes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TextRecord:
    observation_id: str
    subject_id: str
    domain: str
    source_id: str
    text: str
    annotations: tuple[TextAnnotation, ...]
    context: tuple[str, ...] = ()
    group_id: str = ""
    # Only independently reviewed negatives belong here. Unannotated text is unknown.
    negative_annotations: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class TextToken:
    text: str
    start: int
    end: int


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value


def _label(annotation: TextAnnotation) -> str:
    return json.dumps([annotation.dimension, annotation.value], ensure_ascii=False, separators=(",", ":"))


def _tokenize(text: str) -> tuple[TextToken, ...]:
    return tuple(TextToken(m.group(0), m.start(), m.end()) for m in TOKEN_RE.finditer(text))


def _span_features(surface: str) -> tuple[str, ...]:
    normalized = surface.casefold()
    tokens = [m.group(0) for m in TOKEN_RE.finditer(normalized)]
    features = [f"w:{token}" for token in tokens if token.strip()]
    compact = re.sub(r"\s+", "", normalized)
    for width in (2, 3):
        features.extend(f"c{width}:{compact[i:i + width]}"
                        for i in range(max(0, len(compact) - width + 1)))
    if not features:
        features.append("empty")
    return tuple(features)


def _candidate_spans(text: str, *, max_tokens: int, max_span_chars: int,
                     max_candidates: int) -> tuple[tuple[int, int], ...]:
    tokens = _tokenize(text)
    spans: list[tuple[int, int]] = []
    for start in range(len(tokens)):
        for end in range(start + 1, min(len(tokens), start + max_tokens) + 1):
            left, right = tokens[start], tokens[end - 1]
            if right.end - left.start > max_span_chars:
                break
            surface = text[left.start:right.end]
            if not any(ch.isalnum() or "\u3400" <= ch <= "\u9fff" for ch in surface):
                continue
            spans.append((left.start, right.end))
            if len(spans) > max_candidates:
                raise ValueError("text span search budget exceeded")
    return tuple(spans)


def _validate_record(record: TextRecord) -> None:
    for name in ("observation_id", "subject_id", "domain", "source_id", "text"):
        _nonempty(getattr(record, name), name)
    if not isinstance(record.group_id, str):
        raise ValueError("group_id must be text")
    if not isinstance(record.context, tuple) or any(not isinstance(x, str) for x in record.context):
        raise ValueError("context must be a tuple of strings")
    if not isinstance(record.annotations, tuple):
        raise ValueError("annotations must be a tuple")
    if not isinstance(record.negative_annotations, tuple):
        raise ValueError("negative_annotations must be a tuple")
    seen: set[tuple[int, int]] = set()
    for ann in record.annotations:
        if not isinstance(ann, TextAnnotation):
            raise ValueError("annotations must contain TextAnnotation")
        if (isinstance(ann.start_char, bool) or not isinstance(ann.start_char, int)
                or isinstance(ann.end_char, bool) or not isinstance(ann.end_char, int)
                or not 0 <= ann.start_char < ann.end_char <= len(record.text)):
            raise ValueError("annotation offsets are outside the source text")
        if (ann.start_char, ann.end_char) in seen:
            raise ValueError("duplicate annotation span")
        seen.add((ann.start_char, ann.end_char))
        if not record.text[ann.start_char:ann.end_char].strip():
            raise ValueError("annotation span must contain source text")
        FeatureAtom(ann.dimension, ann.value).validate()
        if not isinstance(ann.purposes, tuple) or any(
            not isinstance(x, str) or not x.strip() for x in ann.purposes
        ):
            raise ValueError("annotation purposes must be non-empty strings")
        if len(ann.purposes) != len(set(ann.purposes)):
            raise ValueError("annotation purposes must be unique")
    negative_seen: set[tuple[int, int]] = set()
    for span in record.negative_annotations:
        if (not isinstance(span, tuple) or len(span) != 2
                or any(isinstance(x, bool) or not isinstance(x, int) for x in span)
                or not 0 <= span[0] < span[1] <= len(record.text)):
            raise ValueError("negative annotation offsets are outside the source text")
        if span in negative_seen:
            raise ValueError("duplicate negative annotation span")
        if not record.text[span[0]:span[1]].strip():
            raise ValueError("negative annotation span must contain source text")
        if any(span[0] < end and start < span[1] for start, end in seen):
            raise ValueError("negative annotation overlaps a positive annotation")
        if any(span[0] < end and start < span[1] for start, end in negative_seen):
            raise ValueError("negative annotations must not overlap each other")
        negative_seen.add(span)


def load_records(path: str | Path) -> tuple[TextRecord, ...]:
    raw = Path(path).read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("dataset must be UTF-8 JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "examples"}:
        raise ValueError("dataset must contain exactly schema_version and examples")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported text dataset schema_version")
    if not isinstance(payload["examples"], list) or not payload["examples"]:
        raise ValueError("examples must contain at least one record")
    records = []
    required = {"observation_id", "subject_id", "domain", "source_id", "text", "annotations"}
    for index, item in enumerate(payload["examples"]):
        if not isinstance(item, dict) or not required <= set(item) or set(item) - (required | {"context", "group_id", "negative_annotations"}):
            raise ValueError(f"examples[{index}] has missing or unknown fields")
        annotations = item["annotations"]
        if not isinstance(annotations, list):
            raise ValueError(f"examples[{index}].annotations must be a list")
        converted = []
        for ann in annotations:
            if not isinstance(ann, dict) or set(ann) - {"start_char", "end_char", "dimension", "value", "purposes"} or not {"start_char", "end_char", "dimension", "value"} <= set(ann):
                raise ValueError(f"examples[{index}] contains an invalid annotation")
            purposes = ann.get("purposes", [])
            if not isinstance(purposes, list):
                raise ValueError("annotation purposes must be a list")
            converted.append(TextAnnotation(
                ann["start_char"], ann["end_char"], ann["dimension"],
                ann["value"], tuple(purposes),
            ))
        context = item.get("context", [])
        if not isinstance(context, list) or any(not isinstance(x, str) for x in context):
            raise ValueError("context must be a list of strings")
        raw_negatives = item.get("negative_annotations", [])
        if not isinstance(raw_negatives, list):
            raise ValueError(f"examples[{index}].negative_annotations must be a list")
        negative_spans = []
        for negative in raw_negatives:
            if (not isinstance(negative, dict)
                    or set(negative) != {"start_char", "end_char"}):
                raise ValueError(f"examples[{index}] contains an invalid negative annotation")
            negative_spans.append((negative["start_char"], negative["end_char"]))
        record = TextRecord(
            item["observation_id"], item["subject_id"], item["domain"],
            item["source_id"], item["text"], tuple(converted),
            tuple(context), item.get("group_id", item["subject_id"]),
            tuple(negative_spans),
        )
        _validate_record(record)
        records.append(record)
    ids = [row.observation_id for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError("observation IDs must be unique")
    return tuple(records)


class TrainableTextEncoder:
    """Multinomial NB span proposer with explicit unknown/none rejection."""

    def __init__(self, *, alpha: float = 0.5, max_tokens: int = 6,
                 max_span_chars: int = 32, max_candidates: int = 20000):
        if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not math.isfinite(alpha) or alpha <= 0:
            raise ValueError("alpha must be positive and finite")
        if (isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= 12
                or isinstance(max_span_chars, bool) or not isinstance(max_span_chars, int)
                or not 1 <= max_span_chars <= 128):
            raise ValueError("invalid span limits")
        if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
            raise ValueError("max_candidates must be positive")
        self.alpha = float(alpha)
        self.max_tokens = max_tokens
        self.max_span_chars = max_span_chars
        self.max_candidates = max_candidates
        self.class_docs: Counter[str] = Counter()
        self.feature_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.class_feature_totals: Counter[str] = Counter()
        self.purpose_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.label_annotations: Counter[str] = Counter()
        self.exact_span_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.classes: tuple[str, ...] = ()
        self.vocab_size = 0
        self.training_records = 0

    def fit(self, records: Iterable[TextRecord], *, seed: int = 17) -> "TrainableTextEncoder":
        rows = tuple(records)
        if not rows:
            raise ValueError("training records must not be empty")
        self.class_docs.clear()
        self.feature_counts.clear()
        self.class_feature_totals.clear()
        self.purpose_counts.clear()
        self.label_annotations.clear()
        self.exact_span_counts.clear()
        reviewed_negative_count = 0
        training_records_used = 0
        for record in rows:
            _validate_record(record)
            token_spans = _tokenize(record.text)
            token_starts = {token.start for token in token_spans}
            token_ends = {token.end for token in token_spans}
            for annotation in record.annotations:
                if (annotation.end_char - annotation.start_char > self.max_span_chars
                        or annotation.start_char not in token_starts
                        or annotation.end_char not in token_ends):
                    raise ValueError("annotation span is not representable by the configured tokenizer budget")
                span_tokens = _tokenize(record.text[annotation.start_char:annotation.end_char])
                if len(span_tokens) > self.max_tokens:
                    raise ValueError("annotation span exceeds max_tokens")
            positives = {(a.start_char, a.end_char): a for a in record.annotations}
            negatives = list(record.negative_annotations)
            for start, end in negatives:
                if (end - start > self.max_span_chars
                        or start not in token_starts or end not in token_ends):
                    raise ValueError(
                        "reviewed negative span is not representable by the configured tokenizer budget"
                    )
                if len(_tokenize(record.text[start:end])) > self.max_tokens:
                    raise ValueError("reviewed negative span exceeds max_tokens")
            reviewed_negative_count += len(negatives)
            samples = [(span, _label(ann)) for span, ann in positives.items()]
            samples.extend((span, NONE_LABEL) for span in negatives)
            if not samples:
                # A record with no reviewed labels is unknown, not a negative
                # training example. Keep it out of the learner's statistics.
                continue
            training_records_used += 1
            for (start, end), label in samples:
                self.class_docs[label] += 1
                features = _span_features(record.text[start:end])
                for feature in features:
                    self.feature_counts[label][feature] += 1
                    self.class_feature_totals[label] += 1
            for ann in record.annotations:
                key = _label(ann)
                surface_key = re.sub(r"\s+", " ", record.text[ann.start_char:ann.end_char].casefold()).strip()
                self.exact_span_counts[surface_key][key] += 1
                self.label_annotations[key] += 1
                for purpose in ann.purposes:
                    self.purpose_counts[key][purpose] += 1
        if reviewed_negative_count == 0:
            raise ValueError(
                "training data requires explicitly reviewed negative_annotations; "
                "unannotated spans are unknown, not negatives"
            )
        self.classes = tuple(sorted(self.class_docs))
        self.vocab_size = len({feature for counter in self.feature_counts.values() for feature in counter})
        if not any(label != NONE_LABEL for label in self.classes):
            raise ValueError("training data contains no positive feature annotations")
        self.training_records = training_records_used
        return self

    def _probabilities(self, surface: str) -> dict[str, float]:
        features = _span_features(surface)
        total_docs = sum(self.class_docs.values())
        vocab_size = max(1, self.vocab_size)
        scores = {}
        for label in self.classes:
            score = math.log((self.class_docs[label] + self.alpha) /
                             (total_docs + self.alpha * len(self.classes)))
            denom = self.class_feature_totals[label] + self.alpha * vocab_size
            counts = self.feature_counts[label]
            for feature in features:
                score += math.log((counts[feature] + self.alpha) / denom)
            scores[label] = score
        peak = max(scores.values())
        exp_scores = {key: math.exp(value - peak) for key, value in scores.items()}
        denom = sum(exp_scores.values())
        return {key: value / denom for key, value in exp_scores.items()}

    def predict(self, *, observation_id: str, subject_id: str, domain: str,
                source_id: str, text: str, context: tuple[str, ...] = (),
                threshold: float = 0.55, max_features: int = 64) -> Observation:
        for name, value in (("observation_id", observation_id), ("subject_id", subject_id),
                            ("domain", domain), ("source_id", source_id), ("text", text)):
            _nonempty(value, name)
        if not 0.0 < threshold < 1.0 or max_features < 1:
            raise ValueError("invalid prediction threshold or feature budget")
        candidates = _candidate_spans(
            text, max_tokens=self.max_tokens, max_span_chars=self.max_span_chars,
            max_candidates=self.max_candidates,
        )
        proposed = []
        for start, end in candidates:
            candidate_surface = text[start:end]
            surface_key = re.sub(r"\s+", " ", candidate_surface.casefold()).strip()
            exact_counts = self.exact_span_counts.get(surface_key)
            is_reviewed_exact_span = bool(exact_counts)
            if exact_counts:
                label = max(exact_counts, key=exact_counts.get)
                confidence = exact_counts[label] / sum(exact_counts.values())
            else:
                probabilities = self._probabilities(candidate_surface)
                label = max(probabilities, key=probabilities.get)
                confidence = probabilities[label]
            if label == NONE_LABEL or confidence < threshold:
                continue
            dimension, value = json.loads(label)
            annotation_total = self.label_annotations[label]
            purpose_scores = tuple(sorted(
                (purpose, count / annotation_total)
                for purpose, count in self.purpose_counts[label].items()
            )) if annotation_total else ()
            proposed.append((is_reviewed_exact_span, confidence, start, end,
                             dimension, value, purpose_scores))
        # Reviewed phrase boundaries outrank broader NB guesses that merely
        # contain the same words; otherwise a whole sentence can suppress the
        # exact source span supplied by the annotator.
        proposed.sort(key=lambda item: (not item[0], -item[1], item[2],
                                        -(item[3] - item[2])))
        accepted = []
        for item in proposed:
            _, _, start, end, *_ = item
            if any(start < other[3] and other[2] < end for other in accepted):
                continue
            accepted.append(item)
            if len(accepted) >= max_features:
                break
        accepted.sort(key=lambda item: (item[2], item[3]))
        refs = tuple(sorted({
            f"text:{source_id}:chars:{start}-{end}"
            for _, _, start, end, *_ in accepted
        }))
        features = tuple(
            FeatureCandidate(
                feature_id=f"{observation_id}:pred:{index:04d}",
                atom=FeatureAtom(dimension, value),
                evidence_refs=(f"text:{source_id}:chars:{start}-{end}",),
                purpose_scores=purpose_scores,
            )
            for index, (_, _, start, end, dimension, value, purpose_scores) in enumerate(accepted)
        )
        observation = Observation(
            observation_id, subject_id, domain, refs or (f"text:{source_id}:document",),
            features, context,
        )
        observation.validate()
        return observation

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1, "model_type": "classiang-text-nb-v1",
            "alpha": self.alpha, "max_tokens": self.max_tokens,
            "max_span_chars": self.max_span_chars, "max_candidates": self.max_candidates,
            "classes": list(self.classes), "class_docs": dict(self.class_docs),
            "feature_counts": {k: dict(v) for k, v in self.feature_counts.items()},
            "class_feature_totals": dict(self.class_feature_totals),
            "purpose_counts": {k: dict(v) for k, v in self.purpose_counts.items()},
            "label_annotations": dict(self.label_annotations),
            "exact_span_counts": {k: dict(v) for k, v in self.exact_span_counts.items()},
            "training_records": self.training_records, "vocab_size": self.vocab_size,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TrainableTextEncoder":
        if not isinstance(payload, dict) or payload.get("schema_version") != 1 or payload.get("model_type") != "classiang-text-nb-v1":
            raise ValueError("unsupported text model checkpoint")
        model = cls(
            alpha=payload["alpha"], max_tokens=payload["max_tokens"],
            max_span_chars=payload["max_span_chars"],
            max_candidates=payload["max_candidates"],
        )
        model.classes = tuple(payload["classes"])
        model.class_docs = Counter(payload["class_docs"])
        model.feature_counts = defaultdict(Counter, {
            key: Counter(value) for key, value in payload["feature_counts"].items()
        })
        model.class_feature_totals = Counter(payload["class_feature_totals"])
        model.purpose_counts = defaultdict(Counter, {
            key: Counter(value) for key, value in payload["purpose_counts"].items()
        })
        model.label_annotations = Counter(payload.get("label_annotations", {}))
        model.exact_span_counts = defaultdict(Counter, {
            key: Counter(value) for key, value in payload.get("exact_span_counts", {}).items()
        })
        model.training_records = payload["training_records"]
        model.vocab_size = len({feature for counter in model.feature_counts.values() for feature in counter})
        if set(model.classes) != set(model.class_docs) or not model.classes:
            raise ValueError("checkpoint class index is inconsistent")
        if any(total < 0 for total in model.class_feature_totals.values()):
            raise ValueError("checkpoint contains invalid feature totals")
        return model

    def save(self, path: str | Path) -> str:
        payload = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        envelope = json.dumps({"sha256": digest, "model": self.to_dict()},
                              ensure_ascii=False, sort_keys=True, indent=2)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(envelope)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return digest

    @classmethod
    def load(cls, path: str | Path) -> "TrainableTextEncoder":
        envelope = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(envelope, dict) or set(envelope) != {"sha256", "model"}:
            raise ValueError("invalid checkpoint envelope")
        raw = json.dumps(envelope["model"], ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != envelope["sha256"]:
            raise ValueError("checkpoint digest mismatch")
        return cls.from_dict(envelope["model"])


def _split_groups(records: tuple[TextRecord, ...], fraction: float, seed: int):
    if not 0.0 < fraction < 1.0:
        raise ValueError("validation_fraction must be between 0 and 1")
    groups = sorted({row.group_id or row.subject_id for row in records})
    if len(groups) < 2:
        raise ValueError("at least two independent groups are required")
    random.Random(seed).shuffle(groups)
    count = min(len(groups) - 1, max(1, round(len(groups) * fraction)))
    validation = set(groups[:count])
    train = tuple(row for row in records if (row.group_id or row.subject_id) not in validation)
    valid = tuple(row for row in records if (row.group_id or row.subject_id) in validation)
    if not train or not valid:
        raise ValueError("group split produced an empty partition")
    return train, valid


def evaluate(model: TrainableTextEncoder, records: tuple[TextRecord, ...],
             *, threshold: float = 0.55) -> dict[str, Any]:
    tp = fp = fn = 0
    unknown_predictions = 0
    reviewed_negative_predictions = 0
    reviewed_negative_total = 0
    exact_records = 0
    evaluated_records = 0
    unreviewed_records_skipped = 0
    for row in records:
        if not row.annotations and not row.negative_annotations:
            unreviewed_records_skipped += 1
            continue
        evaluated_records += 1
        predicted = model.predict(
            observation_id=row.observation_id, subject_id=row.subject_id,
            domain=row.domain, source_id=row.source_id, text=row.text,
            context=row.context, threshold=threshold,
        )
        expected = {(a.start_char, a.end_char, _label(a)) for a in row.annotations}
        actual = set()
        for feature in predicted.features:
            ref = feature.evidence_refs[0]
            match = re.search(r":chars:(\d+)-(\d+)$", ref)
            if match:
                actual.add((int(match.group(1)), int(match.group(2)),
                            json.dumps([feature.atom.dimension, feature.atom.value], ensure_ascii=False, separators=(",", ":"))))
        reviewed_negatives = set(row.negative_annotations)
        known_spans = {(start, end) for start, end, _ in expected} | reviewed_negatives
        known_actual = {item for item in actual if item[:2] in known_spans}
        tp += len(expected & known_actual)
        fp += len(known_actual - expected)
        fn += len(expected - actual)
        unknown_predictions += len(actual - known_actual)
        reviewed_negative_predictions += len({
            (start, end) for start, end, _ in actual
            if (start, end) in reviewed_negatives
        })
        reviewed_negative_total += len(reviewed_negatives)
        exact_records += int(expected == known_actual)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "records": len(records), "evaluated_records": evaluated_records,
        "unreviewed_records_skipped": unreviewed_records_skipped,
        "true_positive": tp, "false_positive": fp,
        "false_negative": fn, "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "exact_record_match": exact_records / evaluated_records if evaluated_records else 0.0,
        "unknown_predictions": unknown_predictions,
        "reviewed_negative_spans": reviewed_negative_total,
        "reviewed_negative_predictions": reviewed_negative_predictions,
        "reviewed_negative_false_positive_rate": (
            reviewed_negative_predictions / reviewed_negative_total
            if reviewed_negative_total else None
        ),
        "metric_scope": "reviewed_spans_only; unannotated predictions remain unknown and are excluded from false positives",
    }


def train_and_evaluate(records: tuple[TextRecord, ...], *, seed: int = 17,
                       validation_fraction: float = 0.2, threshold: float = 0.55):
    train, validation = _split_groups(records, validation_fraction, seed)
    model = TrainableTextEncoder().fit(train, seed=seed)
    report = {
        "schema_version": 1, "model_type": "classiang-text-nb-v1",
        "seed": seed, "train_records": len(train), "validation_records": len(validation),
        "train_groups": sorted({r.group_id or r.subject_id for r in train}),
        "validation_groups": sorted({r.group_id or r.subject_id for r in validation}),
        "group_disjoint": not ({r.group_id or r.subject_id for r in train} &
                               {r.group_id or r.subject_id for r in validation}),
        "training": {
            "records": model.training_records, "classes": len(model.classes),
            "reviewed_negative_spans": model.class_docs.get(NONE_LABEL, 0),
        },
        "validation": evaluate(model, validation, threshold=threshold),
        "limitations": [
            "supervised span-label baseline",
            "only explicitly reviewed negative_annotations are used as negative training labels",
            "unannotated spans remain unknown and are excluded from false-positive evaluation",
            "known feature labels only", "no OCR or image encoder",
            "no causal or semantic truth guarantee",
        ],
    }
    return model, report


def append_reviewed_feedback(path: str | Path, record: dict[str, Any]) -> None:
    """Append one reviewed source-grounded record via atomic file replacement."""
    required = {"event_id", "reviewer_id", "decision", "record"}
    if not isinstance(record, dict) or set(record) != required:
        raise ValueError("feedback event must contain exactly the required fields")
    for key in ("event_id", "reviewer_id"):
        _nonempty(record[key], key)
    if record["decision"] not in {"accept", "reject", "correct"}:
        raise ValueError("feedback decision must be accept, reject, or correct")
    if not isinstance(record["record"], dict):
        raise ValueError("feedback record must be an object")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    for line in existing.splitlines():
        if json.loads(line).get("event_id") == record["event_id"]:
            raise ValueError("duplicate feedback event_id")
    fd, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(existing)
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset")
    parser.add_argument("--checkpoint", default="artifacts/classiang-text.json")
    parser.add_argument("--report", default="artifacts/classiang-text-report.json")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--threshold", type=float, default=0.55)
    args = parser.parse_args()
    records = load_records(args.dataset)
    model, report = train_and_evaluate(
        records, seed=args.seed, validation_fraction=args.validation_fraction,
        threshold=args.threshold,
    )
    report["dataset_sha256"] = hashlib.sha256(Path(args.dataset).read_bytes()).hexdigest()
    report["checkpoint_sha256"] = model.save(args.checkpoint)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
