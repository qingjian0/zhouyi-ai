"""Exact identifiability audit for TX-02A hidden affine episodes.

The auditor consumes learner-visible episode fields only. It enumerates all
coefficient triples and, for the permuted track, all bijections from latent
canonical symbols to visible symbols. It reports rule-hypothesis ambiguity
separately from query-answer ambiguity.
"""
from __future__ import annotations

import itertools
import math
from typing import Any


def _validate_payload(payload: dict[str, Any]) -> tuple[int, str, tuple, tuple, tuple]:
    if not isinstance(payload, dict):
        raise TypeError("episode payload must be a dictionary")
    k = payload.get("cardinality")
    if type(k) is not int or k < 2:
        raise ValueError("cardinality must be an integer >= 2")
    mapping_mode = payload.get("symbol_mapping")
    if mapping_mode not in ("canonical", "permuted"):
        raise ValueError("symbol_mapping must be 'canonical' or 'permuted'")

    support = payload.get("support")
    queries = payload.get("queries")
    candidates = payload.get("candidates")
    if not isinstance(support, (list, tuple)) or not support:
        raise ValueError("support must be a non-empty sequence")
    if not isinstance(queries, (list, tuple)) or not queries:
        raise ValueError("queries must be a non-empty sequence")
    if not isinstance(candidates, (list, tuple)) or len(candidates) != len(queries):
        raise ValueError("candidates must have one row per query")

    def symbol(value: Any) -> int:
        if type(value) is not int or not 0 <= value < k:
            raise ValueError(f"visible symbols must be integers in [0, {k})")
        return value

    clean_support = []
    for row in support:
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError("each support row must contain (a, b, c)")
        clean_support.append(tuple(symbol(v) for v in row))

    clean_queries = []
    for row in queries:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError("each query must contain (a, b)")
        clean_queries.append(tuple(symbol(v) for v in row))

    clean_candidates = []
    for row in candidates:
        if not isinstance(row, (list, tuple)) or len(row) != k:
            raise ValueError("each candidate row must contain exactly K symbols")
        values = tuple(symbol(v) for v in row)
        if set(values) != set(range(k)):
            raise ValueError("each candidate row must be a permutation of all symbols")
        clean_candidates.append(values)

    return k, mapping_mode, tuple(clean_support), tuple(clean_queries), tuple(clean_candidates)


def audit_episode(payload: dict[str, Any], max_hypotheses: int = 2_000_000) -> dict[str, Any]:
    """Exactly enumerate hypotheses and posterior answer counts.

    Prior: uniform over coefficient triples (alpha,beta,delta) in Z_K^3 and
    over symbol bijections. In canonical mode, only the identity bijection is
    allowed. This is the generator-aligned hypothesis class, not a universal
    prior over arbitrary functions.
    """
    k, mapping_mode, support, queries, candidates = _validate_payload(payload)
    mapping_count = 1 if mapping_mode == "canonical" else math.factorial(k)
    hypothesis_space_size = (k ** 3) * mapping_count
    if hypothesis_space_size > max_hypotheses:
        raise ValueError(
            f"exact hypothesis space ({hypothesis_space_size}) exceeds "
            f"max_hypotheses ({max_hypotheses}); use a smaller K or an explicitly "
            "labelled approximate audit"
        )

    mappings = (tuple(range(k)),) if mapping_mode == "canonical" else itertools.permutations(range(k))
    answer_counts = [[0] * k for _ in queries]
    consistent_hypotheses = 0

    # mapping[latent_symbol] = visible_symbol
    for mapping in mappings:
        inverse = [0] * k
        for latent, visible in enumerate(mapping):
            inverse[visible] = latent

        latent_support = tuple((inverse[a], inverse[b], inverse[c]) for a, b, c in support)
        latent_queries = tuple((inverse[a], inverse[b]) for a, b in queries)

        for alpha in range(k):
            for beta in range(k):
                for delta in range(k):
                    valid = True
                    for a, b, observed_c in latent_support:
                        predicted = (alpha * a + beta * b + delta) % k
                        if predicted != observed_c:
                            valid = False
                            break
                    if not valid:
                        continue

                    consistent_hypotheses += 1
                    for qi, (a, b) in enumerate(latent_queries):
                        visible_prediction = mapping[(alpha * a + beta * b + delta) % k]
                        # Candidate order is arbitrary; posterior is accumulated
                        # in candidate-index space so shuffled rows are handled.
                        candidate_index = candidates[qi].index(visible_prediction)
                        answer_counts[qi][candidate_index] += 1

    if consistent_hypotheses == 0:
        return {
            "status": "inconsistent",
            "cardinality": k,
            "symbol_mapping": mapping_mode,
            "hypothesis_space_size": hypothesis_space_size,
            "consistent_hypotheses": 0,
            "queries": [],
            "limitations": ["No hypothesis in the TX-02A affine generator family explains the support set."],
        }

    query_results = []
    bayes_accuracy_sum = 0.0
    identifiable_count = 0
    for qi, counts in enumerate(answer_counts):
        probabilities = [count / consistent_hypotheses for count in counts]
        bayes_accuracy = max(probabilities)
        entropy = -sum(p * math.log2(p) for p in probabilities if p > 0.0)
        identifiable = sum(count > 0 for count in counts) == 1
        identifiable_count += int(identifiable)
        bayes_accuracy_sum += bayes_accuracy
        query_results.append({
            "query_index": qi,
            "query": list(queries[qi]),
            "candidate_order": list(candidates[qi]),
            "candidate_hypothesis_counts": counts,
            "candidate_posterior": probabilities,
            "bayes_optimal_accuracy": bayes_accuracy,
            "answer_entropy_bits": entropy,
            "answer_identifiable": identifiable,
        })

    query_count = len(queries)
    return {
        "status": "ok",
        "cardinality": k,
        "symbol_mapping": mapping_mode,
        "prior": "uniform_over_affine_coefficients_and_allowed_symbol_bijections",
        "hypothesis_space_size": hypothesis_space_size,
        "consistent_hypotheses": consistent_hypotheses,
        "rule_hypothesis_identifiable": consistent_hypotheses == 1,
        "query_count": query_count,
        "identifiable_query_count": identifiable_count,
        "identifiable_query_rate": identifiable_count / query_count,
        "mean_bayes_optimal_query_accuracy": bayes_accuracy_sum / query_count,
        "queries": query_results,
        "limitations": [
            "Exact only within the TX-02A affine-rule hypothesis class.",
            "Posterior assumes a uniform prior over coefficients and allowed symbol bijections.",
            "A unique rule is sufficient but not necessary for a query answer to be identifiable.",
            "This is an evaluator-side audit; hidden metadata and target labels are not used.",
        ],
    }


def main() -> None:
    import argparse
    import json
    from prototype.tx02_multistate_benchmark import make_episode, episode_to_dict

    parser = argparse.ArgumentParser()
    parser.add_argument("--cardinality", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--support-size", type=int, default=2)
    parser.add_argument("--query-count", type=int, default=2)
    parser.add_argument("--symbol-mapping", choices=("canonical", "permuted"), default="canonical")
    parser.add_argument("--max-hypotheses", type=int, default=2_000_000)
    args = parser.parse_args()

    episode = make_episode(
        args.cardinality, args.seed, args.support_size,
        args.query_count, args.symbol_mapping,
    )
    result = audit_episode(episode_to_dict(episode), args.max_hypotheses)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
