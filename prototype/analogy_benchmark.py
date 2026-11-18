"""Leakage-resistant synthetic benchmark for relation-preserving analogy.

This is a controlled evaluator fixture, not a learned analogy model or a
claim about real-world Zhouyi cognition. Template families are split as groups
so variants of one structural motif cannot leak across train/validation/test.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

from prototype.analogy import AnalogyCandidate, Evidence, Relation, assess_analogy


@dataclass(frozen=True)
class BenchmarkExample:
    example_id: str
    template_family: str
    split: str
    expected_valid: bool
    candidate: AnalogyCandidate


# Directed, typed motifs. Distinct families provide different graph structures.
_TEMPLATES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "chain": (("a", "b", "enables"), ("b", "c", "enables"), ("c", "d", "limits")),
    "fork": (("a", "b", "supports"), ("a", "c", "supports"), ("c", "d", "limits")),
    "cycle": (("a", "b", "feeds"), ("b", "c", "feeds"), ("c", "a", "feeds")),
    "hierarchy": (("a", "b", "contains"), ("a", "c", "contains"), ("b", "d", "contains")),
    "competition": (("a", "b", "competes"), ("b", "c", "blocks"), ("c", "d", "competes")),
    "feedback": (("a", "b", "amplifies"), ("b", "c", "dampens"), ("c", "a", "regulates")),
}
_SPLITS = {
    "chain": "train",
    "fork": "train",
    "cycle": "validation",
    "hierarchy": "validation",
    "competition": "test",
    "feedback": "test",
}


def build_analogy_benchmark(*, variants_per_family: int = 3) -> tuple[BenchmarkExample, ...]:
    """Build paired valid/invalid candidates with family-level OOD splits."""
    if type(variants_per_family) is not int or variants_per_family < 1:
        raise ValueError("variants_per_family must be a positive integer")

    examples: list[BenchmarkExample] = []
    for family, edges in _TEMPLATES.items():
        split = _SPLITS[family]
        for variant in range(variants_per_family):
            suffix = f"{variant}"
            source_entities = tuple(f"s{node}" for node in "abcd")
            target_entities = tuple(f"t{node}_{suffix}" for node in "abcd")
            source_relations = tuple(Relation(f"s{a}", f"s{b}", kind) for a, b, kind in edges)
            target_relations = tuple(Relation(f"t{a}_{suffix}", f"t{b}_{suffix}", kind) for a, b, kind in edges)
            mapping = {f"s{node}": f"t{node}_{suffix}" for node in "abcd"}
            common = dict(
                source_domain=f"source:{family}",
                target_domain=f"target:{family}",
                source_entities=source_entities,
                target_entities=target_entities,
                mapping=mapping,
                dimensions=("relation", "function"),
                source_relations=source_relations,
                conditions=("same declared graph snapshot",),
                evidence=(Evidence(f"synthetic:{family}:{variant}", True),),
                validity_scope=f"synthetic motif family {family} only",
            )
            positive = AnalogyCandidate(
                candidate_id=f"{family}-{variant}-valid",
                target_relations=target_relations,
                **common,
            )
            # A controlled counterfactual: preserve nodes and mapping, corrupt
            # exactly one relation type. It must be rejected by exact semantics.
            corrupted = list(target_relations)
            first = corrupted[0]
            corrupted[0] = Relation(first.source, first.target, "counterfactual_mismatch")
            negative = AnalogyCandidate(
                candidate_id=f"{family}-{variant}-invalid",
                target_relations=tuple(corrupted),
                **common,
            )
            examples.append(BenchmarkExample(positive.candidate_id, family, split, True, positive))
            examples.append(BenchmarkExample(negative.candidate_id, family, split, False, negative))
    return tuple(examples)


def evaluate_analogy_benchmark(
    examples: Iterable[BenchmarkExample] | None = None,
) -> dict[str, object]:
    """Evaluate deterministic relation-preservation baseline and report splits."""
    rows = tuple(build_analogy_benchmark() if examples is None else examples)
    if not rows:
        raise ValueError("benchmark must contain at least one example")
    if len({row.example_id for row in rows}) != len(rows):
        raise ValueError("example ids must be unique")

    def summarize(selected: tuple[BenchmarkExample, ...]) -> dict[str, float | int]:
        tp = fp = tn = fn = 0
        for row in selected:
            predicted = assess_analogy(row.candidate).accepted
            if predicted and row.expected_valid:
                tp += 1
            elif predicted and not row.expected_valid:
                fp += 1
            elif not predicted and not row.expected_valid:
                tn += 1
            else:
                fn += 1
        total = tp + fp + tn + fn
        return {
            "examples": total,
            "accuracy": (tp + tn) / total,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "false_accept_rate": fp / (fp + tn) if fp + tn else 0.0,
            "true_positive": tp,
            "false_positive": fp,
            "true_negative": tn,
            "false_negative": fn,
        }

    splits = {name: summarize(tuple(row for row in rows if row.split == name))
              for name in ("train", "validation", "test")}
    family_splits: dict[str, set[str]] = {}
    for row in rows:
        family_splits.setdefault(row.template_family, set()).add(row.split)
    if any(len(split_names) != 1 for split_names in family_splits.values()):
        raise ValueError("template family leakage across splits")
    return {
        "benchmark": "relation-preservation-analogy-v1",
        "examples": len(rows),
        "template_families": len(family_splits),
        "family_split_isolation": True,
        "overall": summarize(rows),
        "splits": splits,
        "interpretation": (
            "Deterministic rule-baseline sanity check only; not a learned model, "
            "not a real-world accuracy estimate, and not evidence of theoretical superiority."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_analogy_benchmark(), ensure_ascii=False, indent=2))
