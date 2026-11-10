"""E02-I2-E: hidden-identity benchmark for candidate-to-identity matching.

The generator keeps latent identity labels in a separate audit object. The
resolver receives only historical RelationVersion objects and observed
RelationCandidate objects. This benchmark evaluates identity continuity, not
end-to-end relation discovery or split/merge inference.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from typing import Mapping

from prototype.e02i2_lineage import RelationVersion
from prototype.e02i2_matching import (
    MatchingMethod,
    RelationCandidate,
    match_candidates,
)


@dataclass(frozen=True)
class HiddenIdentityEpisode:
    """Observed resolver inputs and evaluator-only labels are kept separate."""

    scenario: str
    history: Mapping[str, RelationVersion]
    candidates: tuple[RelationCandidate, ...]
    # None means a genuinely new identity; "AMBIGUOUS" means truth is
    # observationally non-identifiable and the only correct output is abstain.
    hidden_truth: Mapping[str, str | None]


def _version(identity_id: str, members: tuple[str, ...],
             roles: tuple[str, ...], rule: str) -> RelationVersion:
    return RelationVersion(
        version_id=f"{identity_id}-v1",
        identity_id=identity_id,
        version_index=1,
        members=members,
        roles=roles,
        operator="AND",
        rule_signature=rule,
        context_signature="lab",
        valid_from_window=0,
        evidence_refs=("historical-evidence",),
    )


def _candidate(candidate_id: str, members: tuple[str, ...],
               roles: tuple[str, ...], rule: str) -> RelationCandidate:
    return RelationCandidate(
        candidate_id=candidate_id,
        members=members,
        roles=roles,
        operator="AND",
        rule_signature=rule,
        context_signature="lab",
    )


def generate_episode(scenario: str, seed: int) -> HiddenIdentityEpisode:
    """Generate one episode; never encode latent identity in observed IDs."""
    rng = random.Random(seed)
    token = f"s{seed:05d}"
    a, b, c, d, e = (f"{token}-{x}" for x in "abcde")
    cid = f"obs-{rng.getrandbits(48):012x}"

    if scenario == "stable":
        history = {"hist-A": _version("hist-A", (a, b), ("source", "target"), "a&b")}
        candidates = (_candidate(cid, (a, b), ("source", "target"), "a&b"),)
        truth = {cid: "hist-A"}
    elif scenario == "role_permutation":
        history = {"hist-A": _version("hist-A", (a, b), ("source", "target"), "a&b")}
        candidates = (_candidate(cid, (b, a), ("target", "source"), "a&b"),)
        truth = {cid: "hist-A"}
    elif scenario == "member_drift":
        history = {"hist-A": _version("hist-A", (a, b, c), ("source", "bridge", "target"), "ordered-chain")}
        candidates = (_candidate(cid, (a, b, e), ("source", "bridge", "target"), "ordered-chain"),)
        truth = {cid: "hist-A"}
    elif scenario == "same_members_new_semantics":
        # The candidate is a new identity despite exact member overlap.
        history = {"hist-A": _version("hist-A", (a, b), ("source", "target"), "a&b")}
        candidates = (_candidate(cid, (a, b), ("source", "target"), "a^b"),)
        truth = {cid: None}
    elif scenario == "overlapping_independent":
        history = {
            "hist-A": _version("hist-A", (a, b), ("source", "target"), "a&b"),
            "hist-B": _version("hist-B", (b, c), ("source", "target"), "b|c"),
        }
        cid2 = f"obs-{rng.getrandbits(48):012x}"
        candidates = (
            _candidate(cid, (a, b), ("source", "target"), "a&b"),
            _candidate(cid2, (b, c), ("source", "target"), "b|c"),
        )
        truth = {cid: "hist-A", cid2: "hist-B"}
    elif scenario == "temporary_dropout":
        # No observation is not evidence that an identity ceased to exist.
        history = {"hist-A": _version("hist-A", (a, b), ("source", "target"), "a&b")}
        candidates = ()
        truth = {}
    elif scenario == "indistinguishable":
        # Two latent identities have exactly the same observable signature.
        history = {
            "hist-A": _version("hist-A", (a, b), ("source", "target"), "a&b"),
            "hist-B": _version("hist-B", (a, b), ("source", "target"), "a&b"),
        }
        candidates = (_candidate(cid, (a, b), ("source", "target"), "a&b"),)
        truth = {cid: "AMBIGUOUS"}
    else:
        raise ValueError(f"unknown scenario: {scenario}")

    return HiddenIdentityEpisode(scenario, history, candidates, truth)


SCENARIOS = (
    "stable",
    "role_permutation",
    "member_drift",
    "same_members_new_semantics",
    "overlapping_independent",
    "temporary_dropout",
    "indistinguishable",
)


def evaluate(method: MatchingMethod, *, seeds: int = 50,
             start_seed: int = 7000, min_score: float = 0.70,
             min_margin: float = 0.05) -> dict:
    """Evaluate resolver output against labels unavailable to the resolver."""
    totals = {
        "decisions": 0, "correct_matches": 0, "wrong_matches": 0,
        "correct_abstentions": 0, "missed_matches": 0,
        "false_merges": 0, "ambiguous_forced_matches": 0,
        "dropout_episodes": 0,
    }
    by_scenario: dict[str, dict[str, int]] = {}
    for scenario in SCENARIOS:
        stats = {key: 0 for key in (
            "decisions", "correct_matches", "wrong_matches",
            "correct_abstentions", "missed_matches", "false_merges",
            "ambiguous_forced_matches", "dropout_episodes",
        )}
        for offset in range(seeds):
            episode = generate_episode(scenario, start_seed + offset)
            # Critical leakage boundary: hidden_truth is never passed here.
            decisions = match_candidates(
                episode.candidates,
                dict(episode.history),
                method=method,
                min_score=min_score,
                min_margin=min_margin,
            )
            if scenario == "temporary_dropout":
                stats["dropout_episodes"] += 1
                continue
            for decision in decisions:
                stats["decisions"] += 1
                expected = episode.hidden_truth[decision.candidate_id]
                if expected == "AMBIGUOUS":
                    if decision.abstained:
                        stats["correct_abstentions"] += 1
                    else:
                        stats["ambiguous_forced_matches"] += 1
                        stats["wrong_matches"] += 1
                elif expected is None:
                    if decision.abstained:
                        stats["correct_abstentions"] += 1
                    else:
                        stats["false_merges"] += 1
                        stats["wrong_matches"] += 1
                elif decision.identity_id == expected:
                    stats["correct_matches"] += 1
                elif decision.abstained:
                    stats["missed_matches"] += 1
                else:
                    stats["wrong_matches"] += 1
        by_scenario[scenario] = stats
        for key, value in stats.items():
            totals[key] += value

    labelled = totals["correct_matches"] + totals["wrong_matches"] + totals["missed_matches"]
    matched = totals["correct_matches"] + totals["wrong_matches"]
    precision = totals["correct_matches"] / matched if matched else 0.0
    recall = totals["correct_matches"] / labelled if labelled else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "method": method.value,
        "seeds_per_scenario": seeds,
        "start_seed": start_seed,
        "thresholds": {"min_score": min_score, "min_margin": min_margin},
        "totals": totals,
        "metrics": {
            "identity_precision": round(precision, 6),
            "identity_recall": round(recall, 6),
            "identity_f1": round(f1, 6),
            "false_merge_rate": round(
                totals["false_merges"] / max(1, totals["decisions"]), 6
            ),
            "abstention_count": totals["correct_abstentions"] + totals["missed_matches"],
            "abstention_coverage": round(
                (totals["correct_abstentions"] + totals["missed_matches"])
                / max(1, totals["decisions"]), 6
            ),
        },
        "by_scenario": by_scenario,
        "scope": (
            "synthetic identity-resolution benchmark only; candidate generation "
            "is oracle-controlled; no claim of end-to-end relation discovery"
        ),
    }


def run_benchmark(*, seeds: int = 50, start_seed: int = 7000) -> dict:
    return {
        "benchmark": "E02-I2-E hidden identity resolution",
        "scenarios": list(SCENARIOS),
        "results": [
            evaluate(method, seeds=seeds, start_seed=start_seed)
            for method in MatchingMethod
        ],
        "leakage_contract": {
            "hidden_truth_in_candidate": False,
            "hidden_truth_passed_to_matcher": False,
            "test_labels_used_for_threshold_selection": False,
            "note": "thresholds are fixed pre-registered engineering baselines",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--start-seed", type=int, default=7000)
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be >= 1")
    print(json.dumps(run_benchmark(seeds=args.seeds, start_seed=args.start_seed),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
