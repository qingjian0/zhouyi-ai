"""E12-M3: factorized three-bit trigram relation induction.

The 3-bit state is a structural representation only. This finite symbolic
baseline tests whether a line-factorized affine grammar generalizes to unseen
lower-trigram states; it is not a neural model or a semantic theory.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import dataclass
from typing import Iterable, Literal

FAMILY_SIZE = 1344  # 168 invertible 3x3 GF(2) matrices times 8 offsets.
TASK_FAMILIES = ("affine", "nonlinear", "permuted_code")


@dataclass(frozen=True, order=True)
class AffineRule:
    rows: tuple[int, int, int]
    offset: int

    def apply(self, state: int) -> int:
        _validate_state(state)
        out = 0
        for bit, mask in enumerate(self.rows):
            parity = (mask & state).bit_count() & 1
            out |= (parity ^ ((self.offset >> bit) & 1)) << bit
        return out


@dataclass(frozen=True)
class PairObservation:
    lower: int
    upper: int


@dataclass(frozen=True)
class InferenceResult:
    status: str
    survivors: tuple[AffineRule, ...]
    candidates_considered: int


@dataclass(frozen=True)
class Episode:
    support: tuple[PairObservation, ...]
    gate: tuple[PairObservation, ...]
    test: tuple[PairObservation, ...]
    family: str


def _validate_state(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 8:
        raise ValueError("trigram state must be an integer in [0, 7]")


def _gf2_rank(rows: Iterable[int], width: int = 3) -> int:
    basis = [0] * width
    rank = 0
    for raw in rows:
        value = raw
        for bit in range(width - 1, -1, -1):
            if not ((value >> bit) & 1):
                continue
            if basis[bit]:
                value ^= basis[bit]
            else:
                basis[bit] = value
                rank += 1
                break
    return rank


def invertible_matrices() -> tuple[tuple[int, int, int], ...]:
    matrices = []
    for rows in itertools.product(range(1, 8), repeat=3):
        if _gf2_rank(rows) == 3:
            matrices.append(tuple(rows))
    return tuple(sorted(matrices))


def affine_rules() -> tuple[AffineRule, ...]:
    return tuple(
        AffineRule(rows, offset)
        for rows in invertible_matrices()
        for offset in range(8)
    )


def _validate_observations(observations: Iterable[PairObservation], name: str) -> tuple[PairObservation, ...]:
    result = tuple(observations)
    if not result:
        raise ValueError(f"{name} must not be empty")
    seen: set[int] = set()
    for item in result:
        if not isinstance(item, PairObservation):
            raise ValueError(f"{name} entries must be PairObservation")
        _validate_state(item.lower)
        _validate_state(item.upper)
        if item.lower in seen:
            raise ValueError(f"{name} contains duplicate lower-trigram state")
        seen.add(item.lower)
    return result


def infer_affine_rule(
    support: Iterable[PairObservation],
    gate: Iterable[PairObservation],
    *,
    max_candidates: int = FAMILY_SIZE,
) -> InferenceResult:
    """Generate from Support, filter independently on Gate, and fail closed."""
    support_rows = _validate_observations(support, "support")
    gate_rows = _validate_observations(gate, "gate")
    if {x.lower for x in support_rows} & {x.lower for x in gate_rows}:
        raise ValueError("Support and Gate lower-trigram states must be disjoint")
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")
    if max_candidates < FAMILY_SIZE:
        return InferenceResult("BUDGET_EXHAUSTED", (), 0)

    train_fit = [
        rule for rule in affine_rules()
        if all(rule.apply(row.lower) == row.upper for row in support_rows)
    ]
    if not train_fit:
        return InferenceResult("INCONSISTENT", (), FAMILY_SIZE)
    gate_fit = tuple(
        rule for rule in train_fit
        if all(rule.apply(row.lower) == row.upper for row in gate_rows)
    )
    if not gate_fit:
        return InferenceResult("INCONSISTENT", (), FAMILY_SIZE)
    status = "IDENTIFIABLE_WITHIN_AFFINE_GF2" if len(gate_fit) == 1 else "AMBIGUOUS"
    return InferenceResult(status, gate_fit, FAMILY_SIZE)


def lookup_predict(
    visible: Iterable[PairObservation], lower: int
) -> int | None:
    """Capacity-heavier memorization control; unseen inputs abstain."""
    _validate_state(lower)
    table = {row.lower: row.upper for row in visible}
    return table.get(lower)


def _affine_basis_subsets() -> tuple[tuple[int, ...], ...]:
    # Augment each 3-bit input with a constant 1; four affinely independent
    # points span the four-dimensional affine feature space.
    result = []
    for subset in itertools.combinations(range(8), 4):
        augmented = tuple(1 | (state << 1) for state in subset)
        if _gf2_rank(augmented, width=4) == 4:
            result.append(subset)
    return tuple(result)


def _nonlinear_map(state: int) -> int:
    b0, b1, b2 = ((state >> i) & 1 for i in range(3))
    return (b0 ^ (b1 & b2)) | (b1 << 1) | (b2 << 2)


def _permuted_non_affine_map(rule: AffineRule, rng: random.Random) -> tuple[tuple[int, ...], tuple[int, ...]]:
    while True:
        permutation = list(range(8))
        rng.shuffle(permutation)
        inverse = [0] * 8
        for old, new in enumerate(permutation):
            inverse[new] = old
        outputs = tuple(permutation[rule.apply(inverse[x])] for x in range(8))
        if not any(all(candidate.apply(x) == outputs[x] for x in range(8)) for candidate in affine_rules()):
            return tuple(permutation), outputs


def make_episode(seed: int, family: Literal["affine", "nonlinear", "permuted_code"]) -> Episode:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if family not in TASK_FAMILIES:
        raise ValueError(f"unknown task family: {family}")
    rng = random.Random(seed)
    rule = rng.choice(affine_rules())
    support_states = rng.choice(_affine_basis_subsets())
    remaining = [state for state in range(8) if state not in support_states]
    rng.shuffle(remaining)
    gate_states, test_states = remaining[:2], remaining[2:]

    if family == "affine":
        transform = rule.apply
        encode = lambda value: value
    elif family == "nonlinear":
        transform = _nonlinear_map
        encode = lambda value: value
    else:
        permutation, outputs = _permuted_non_affine_map(rule, rng)
        transform = lambda value: outputs[value]
        encode = lambda value: permutation[value]

    def rows(states: Iterable[int]) -> tuple[PairObservation, ...]:
        return tuple(PairObservation(encode(x), encode(transform(x))) for x in states)

    return Episode(rows(support_states), rows(gate_states), rows(test_states), family)


def evaluate_episode(episode: Episode, *, max_candidates: int = FAMILY_SIZE) -> dict[str, object]:
    inferred = infer_affine_rule(episode.support, episode.gate, max_candidates=max_candidates)
    visible = episode.support + episode.gate
    correct = covered = 0
    lookup_correct = lookup_covered = 0
    for row in episode.test:
        predicted = inferred.survivors[0].apply(row.lower) if inferred.status == "IDENTIFIABLE_WITHIN_AFFINE_GF2" else None
        if predicted is not None:
            covered += 1
            correct += int(predicted == row.upper)
        lookup = lookup_predict(visible, row.lower)
        if lookup is not None:
            lookup_covered += 1
            lookup_correct += int(lookup == row.upper)
    total = len(episode.test)
    return {
        "family": episode.family,
        "status": inferred.status,
        "survivor_count": len(inferred.survivors),
        "candidates_considered": inferred.candidates_considered,
        "factorized_coverage": covered / total,
        "factorized_selective_accuracy": correct / covered if covered else None,
        "factorized_strict_accuracy": correct / total,
        "lookup_coverage": lookup_covered / total,
        "lookup_selective_accuracy": lookup_correct / lookup_covered if lookup_covered else None,
        "lookup_strict_accuracy": lookup_correct / total,
        "test_count": total,
        "factorized_correct": correct,
        "factorized_covered": covered,
        "lookup_correct": lookup_correct,
        "lookup_covered": lookup_covered,
    }


def _wilson_interval(successes: int, trials: int) -> list[float] | None:
    if trials <= 0:
        return None
    z = 1.959963984540054
    p = successes / trials
    denominator = 1.0 + (z * z / trials)
    center = (p + (z * z / (2.0 * trials))) / denominator
    margin = (
        z * ((p * (1.0 - p) / trials) + (z * z / (4.0 * trials * trials))) ** 0.5
        / denominator
    )
    return [center - margin, center + margin]


def run_benchmark(*, seeds: int = 100, seed_start: int = 1) -> dict[str, object]:
    if isinstance(seeds, bool) or not isinstance(seeds, int) or seeds < 1:
        raise ValueError("seeds must be a positive integer")
    if isinstance(seed_start, bool) or not isinstance(seed_start, int):
        raise ValueError("seed_start must be an integer")
    episodes = [
        evaluate_episode(make_episode(seed_start + offset, family))
        for family in TASK_FAMILIES
        for offset in range(seeds)
    ]
    summary = {}
    for family in TASK_FAMILIES:
        rows = [row for row in episodes if row["family"] == family]
        test_count = sum(int(row["test_count"]) for row in rows)
        factorized_covered = sum(int(row["factorized_covered"]) for row in rows)
        factorized_correct = sum(int(row["factorized_correct"]) for row in rows)
        lookup_covered = sum(int(row["lookup_covered"]) for row in rows)
        lookup_correct = sum(int(row["lookup_correct"]) for row in rows)
        summary[family] = {
            "episodes": len(rows),
            "test_examples": test_count,
            "identifiable_rate": sum(row["status"] == "IDENTIFIABLE_WITHIN_AFFINE_GF2" for row in rows) / len(rows),
            "ambiguous_rate": sum(row["status"] == "AMBIGUOUS" for row in rows) / len(rows),
            "inconsistent_rate": sum(row["status"] == "INCONSISTENT" for row in rows) / len(rows),
            "factorized_coverage": factorized_covered / test_count,
            "factorized_coverage_95ci": _wilson_interval(factorized_covered, test_count),
            "factorized_selective_accuracy": factorized_correct / factorized_covered if factorized_covered else None,
            "factorized_selective_accuracy_95ci": _wilson_interval(factorized_correct, factorized_covered),
            "factorized_strict_accuracy": factorized_correct / test_count,
            "factorized_strict_accuracy_95ci": _wilson_interval(factorized_correct, test_count),
            "lookup_coverage": lookup_covered / test_count,
            "lookup_selective_accuracy": lookup_correct / lookup_covered if lookup_covered else None,
            "lookup_strict_accuracy": lookup_correct / test_count,
            "mean_survivors": sum(int(row["survivor_count"]) for row in rows) / len(rows),
            "candidate_evaluations": FAMILY_SIZE * len(rows),
        }
    return {
        "benchmark": "E12-M3 trigram-factorized affine generalization",
        "seeds": seeds,
        "seed_start": seed_start,
        "candidate_family_size": FAMILY_SIZE,
        "matrix_count": len(invertible_matrices()),
        "episodes": len(episodes),
        "summary": summary,
        "episodes_detail": episodes,
        "limitations": [
            "finite synthetic 3-bit relation family",
            "the affine GF(2) grammar is a candidate structural bias, not a universal Yijing law",
            "no neural training or natural-language/perception evaluation",
            "the lookup baseline intentionally abstains on unseen inputs",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_benchmark(seeds=args.seeds, seed_start=args.seed_start)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
