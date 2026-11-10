"""E02-I2-C-F independent scenario-family development benchmark.

A/B are independently parameterized Train generators; C is a held-out Gate
generator. Event truth and seed remain evaluator-owned. All generators obey
the same explicit event-feasibility contract but do not reuse hidden-event
benchmark fixtures. This is not a locked-Test or open-world claim.
"""
from __future__ import annotations

import argparse
import json
import random
import secrets
from typing import Iterable

from prototype.e02i2c_hidden_event_benchmark import (
    Episode, EventType, ObservationView, SUPPORTED_EVENTS,
)
from prototype.e02i2c_adjudication import (
    EvidencePacket, EvidencePolarity, IdentitySnapshot, MissingReason, ObservationOpportunity,
    adjudicate_event,
)
from prototype.e02i2c_metadata_attack import (
    CategoricalNaiveBayes, ShallowCategoricalTree, extract_features,
    _majority, _metrics,
)


FAMILIES = ("A", "B", "C")

def _independent_view(event: EventType, seed: int, family: str, split: str) -> ObservationView:
    """Independent event-valid simulator; does not reuse hidden-event fixtures."""
    rng = random.Random(f"independent:{family}:{seed}")
    alphabet = "abcdefghjkmnpqrstuvwxyz"
    def sig(prefix: str) -> str:
        return prefix + "-" + "".join(rng.choice(alphabet) for _ in range(rng.randint(4, 9)))
    old, changed = sig("r"), sig("x")
    while old == changed:
        changed = sig("x")
    identity_id, version_id = secrets.token_hex(8), secrets.token_hex(8)
    if family == "A":
        first, lo, hi = rng.randint(0, 80), 8, 18
        envs = ("temporal-stable", "temporal-seasonal", "temporal-bursty")
    elif family == "B":
        first, lo, hi = rng.randint(10, 300), 18, 40
        envs = ("batch-alpha", "batch-beta", "batch-gamma")
    elif family == "C":
        first, lo, hi = rng.randint(1000, 9000), 30, 90
        envs = ("site-north-dry", "site-south-wet", "site-coastal", "site-altitude", "site-urban")
    else:
        raise ValueError("unknown family")
    identity = IdentitySnapshot(identity_id, "ACTIVE", version_id, old)
    candidate: str | None = old
    if event == EventType.KEEP:
        windows, specs = [first], [(first, EvidencePolarity.SUPPORTS, old, version_id)]
    elif event == EventType.MODIFY:
        candidate, windows = changed, [first, first + 1]
        specs = [(w, EvidencePolarity.SUPPORTS, changed, version_id) for w in windows]
    elif event == EventType.CREATE:
        identity, candidate, windows = None, changed, [first, first + 1]
        specs = [(w, EvidencePolarity.SUPPORTS, changed, None) for w in windows]
    elif event == EventType.ABSTAIN:
        mode = seed % 4
        if mode == 0:
            identity, candidate, windows = None, changed, [first]
            specs = [(first, EvidencePolarity.SUPPORTS, changed, None)]
        elif mode == 1:
            candidate, windows = changed, [first]
            specs = [(first, EvidencePolarity.SUPPORTS, changed, "unlinked-" + version_id)]
        elif mode == 2:
            windows = [first, first + 1]
            specs = [(w, EvidencePolarity.ABSENCE, None, version_id) for w in windows]
        else:
            candidate, windows = changed, [first]
            specs = [(first, EvidencePolarity.SUPPORTS, changed, version_id),
                     (first, EvidencePolarity.CONTRADICTS, None, version_id)]
    elif event == EventType.SUSPEND:
        windows = [first, first + 1]
        specs = [(w, EvidencePolarity.ABSENCE, None, version_id) for w in windows]
    elif event == EventType.REACTIVATE:
        identity = IdentitySnapshot(identity_id, "SUSPENDED", version_id, old)
        windows = [first, first + 1]
        specs = [(w, EvidencePolarity.SUPPORTS, old, version_id) for w in windows]
    elif event == EventType.REACTIVATE_MODIFY:
        identity, candidate, windows = IdentitySnapshot(identity_id, "SUSPENDED", version_id, old), changed, [first, first + 1]
        specs = [(w, EvidencePolarity.SUPPORTS, changed, version_id) for w in windows]
    elif event == EventType.RETIRE:
        identity = IdentitySnapshot(identity_id, "SUSPENDED", version_id, old)
        candidate, windows = None, [first, first + 1]
        specs = [(w, EvidencePolarity.CONTRADICTS, None, version_id) for w in windows]
    else:
        raise ValueError(f"unsupported event {event}")
    opportunities, packets = [], []
    # Environment selection uses an independent stream so event-specific
    # control-flow cannot shift environment assignments.
    env_rng = random.Random(f"environment:{family}:{seed}")
    environment = env_rng.choice(envs)
    for w in windows:
        expected = rng.randint(lo, hi)
        insufficient = event == EventType.ABSTAIN and seed % 4 == 2
        if insufficient:
            observed = rng.randint(0, 1)
            coverage = observed / expected
            reason = MissingReason.NO_EXPOSURE
        else:
            coverage = rng.uniform(0.84, 1.0)
            observed = min(expected, max((expected * 8 + 9) // 10, int(expected * coverage)))
            coverage, reason = observed / expected, None
        opportunities.append(ObservationOpportunity(
            window=w, environment=environment, expected_samples=expected,
            observed_samples=observed, coverage=coverage, missing_reason=reason))
    env_by_window = {o.window: environment for o in opportunities}
    for w, polarity, signature, source in specs:
        # Add independent same-polarity observations at a variable rate. These
        # increase evidence volume without manufacturing new windows or
        # changing the event's semantic confirmation rule.
        extra_count = (
            rng.randint(0, 3) if family == "C"
            else rng.randint(0, 2) if family == "B"
            else rng.randint(0, 1)
        )
        for _ in range(1 + extra_count):
            token = secrets.token_hex(16)
            packets.append(EvidencePacket(
                evidence_id="evidence-" + token, sample_id="sample-" + token,
                window=w, environment=env_by_window[w], split=split, polarity=polarity,
                source_version_id=source, candidate_signature=signature,
                raw_observation_ref="observation://" + token))
    rng.shuffle(opportunities)
    rng.shuffle(packets)
    return ObservationView(identity, candidate, tuple(opportunities), tuple(packets))


def generate_episode(event: EventType, seed: int, *, family: str, split: str) -> Episode:
    if family not in FAMILIES:
        raise ValueError("family must be A, B or C; D is reserved")
    expected_split = "gate" if family == "C" else "train"
    if split != expected_split:
        raise ValueError("family/split violation: A+B are Train and C is Gate")
    return Episode(
        episode_id=f"eval-{family}-{split}-{seed}",
        truth=event,
        observation=_independent_view(event, seed, family, split),
    )


def _decision(view: ObservationView) -> EventType:
    return adjudicate_event(
        view.identity, view.opportunities, view.evidence,
        candidate_signature=view.candidate_signature,
    ).event


def _feature_overlap(episodes: list[Episode], tier: str) -> dict:
    rows = [(ep.truth.value, extract_features(ep.observation, tier)) for ep in episodes]
    keys = sorted({key for _, row in rows for key in row})
    per_event = {}
    for event in (x.value for x in SUPPORTED_EVENTS):
        selected = [row for label, row in rows if label == event]
        per_event[event] = {
            key: sorted({row[key] for row in selected if key in row})
            for key in keys
        }
    overlaps = {}
    events = [x.value for x in SUPPORTED_EVENTS]
    for i, left in enumerate(events):
        for right in events[i + 1:]:
            shared = {}
            for key in keys:
                a, b = set(per_event[left][key]), set(per_event[right][key])
                if a and b:
                    shared[key] = round(len(a & b) / len(a | b), 4)
            overlaps[f"{left}|{right}"] = shared
    return {"per_event_values": per_event, "pairwise_value_jaccard": overlaps}


def _namespace_check(train: list[Episode], gate: list[Episode]) -> dict:
    def collect(episodes: Iterable[Episode], field: str) -> set[str]:
        return {
            getattr(packet, field)
            for ep in episodes for packet in ep.observation.evidence
        }
    train_samples, gate_samples = collect(train, "sample_id"), collect(gate, "sample_id")
    train_evidence, gate_evidence = collect(train, "evidence_id"), collect(gate, "evidence_id")
    return {
        "sample_disjoint": not train_samples.intersection(gate_samples),
        "evidence_disjoint": not train_evidence.intersection(gate_evidence),
        "train_sample_count": len(train_samples), "gate_sample_count": len(gate_samples),
        "train_evidence_count": len(train_evidence), "gate_evidence_count": len(gate_evidence),
    }


def _build_family_episodes(family: str, split: str, start_seed: int,
                            seeds: int, family_offset: int) -> list[Episode]:
    episodes = []
    for block in range(seeds):
        block_seeds = list(range(
            start_seed + family_offset + block * 100,
            start_seed + family_offset + block * 100 + len(SUPPORTED_EVENTS),
        ))
        assignment_rng = random.Random(f"event-seed-assignment:{family}:{block}:{start_seed}")
        assignment_rng.shuffle(block_seeds)
        episodes.extend(
            generate_episode(event, seed, family=family, split=split)
            for event, seed in zip(SUPPORTED_EVENTS, block_seeds)
        )
    return episodes


def _bootstrap_intervals(truths: list[str], predictions: list[str],
                          block_ids: list[int], *, replicates: int,
                          seed: int) -> dict:
    if len(truths) != len(predictions) or len(truths) != len(block_ids):
        raise ValueError("bootstrap arrays must be aligned")
    groups: dict[int, list[int]] = {}
    for index, block in enumerate(block_ids):
        groups.setdefault(block, []).append(index)
    blocks = sorted(groups)
    if len(blocks) < 2:
        raise ValueError("at least two seed blocks are required")
    rng = random.Random(seed)
    f1_values, accuracy_values = [], []
    for _ in range(replicates):
        selected = [rng.choice(blocks) for _ in blocks]
        indices = [index for block in selected for index in groups[block]]
        metrics = _metrics([truths[i] for i in indices],
                           [predictions[i] for i in indices])
        f1_values.append(metrics["macro_f1"])
        accuracy_values.append(metrics["accuracy"])
    def ci(values: list[float]) -> list[float]:
        values.sort()
        return [round(values[max(0, int(.025 * len(values)) - 1)], 4),
                round(values[min(len(values) - 1, int(.975 * len(values)))], 4)]
    return {"replicates": replicates, "resampling_unit": "gate_seed_block",
            "macro_f1_95_ci": ci(f1_values), "accuracy_95_ci": ci(accuracy_values)}


def _environment_metrics(gate: list[Episode], truths: list[str],
                         predictions: list[str]) -> dict:
    groups: dict[str, list[int]] = {}
    for index, episode in enumerate(gate):
        environments = {item.environment for item in episode.observation.opportunities}
        if len(environments) != 1:
            raise RuntimeError("per-environment metrics require one environment per episode")
        groups.setdefault(next(iter(environments)), []).append(index)
    return {
        env: {"episodes": len(indices), **_metrics(
            [truths[i] for i in indices], [predictions[i] for i in indices])}
        for env, indices in sorted(groups.items())
    }


def run_scenario_diversity(*, seeds: int = 30, train_start_seed: int = 1000,
                           gate_start_seed: int = 50000,
                           bootstrap_samples: int = 1000) -> dict:
    if seeds < 30:
        raise ValueError("C-F development evaluation requires at least 30 seed blocks per event")
    if bootstrap_samples < 100:
        raise ValueError("at least 100 bootstrap replicates are required")
    train = (
        _build_family_episodes("A", "train", train_start_seed, seeds, 0)
        + _build_family_episodes("B", "train", train_start_seed, seeds, 1_000_000)
    )
    gate = _build_family_episodes("C", "gate", gate_start_seed, seeds, 2_000_000)
    gate_blocks = [block for block in range(seeds) for _ in SUPPORTED_EVENTS]
    namespace = _namespace_check(train, gate)
    if not namespace["sample_disjoint"] or not namespace["evidence_disjoint"]:
        raise RuntimeError("Train/Gate provenance namespace collision")
    failures = [
        {"episode": ep.episode_id, "truth": ep.truth.value,
         "decision": _decision(ep.observation).value}
        for ep in train + gate if _decision(ep.observation) != ep.truth
    ]
    if failures:
        raise RuntimeError(f"independent generator violated event semantics: {failures[:5]}")
    train_labels = [ep.truth.value for ep in train]
    gate_labels = [ep.truth.value for ep in gate]
    majority = _majority(train_labels)
    majority_predictions = [majority] * len(gate)
    attackers, prediction_sets = {}, {}
    for tier in ("M0", "M1", "M2"):
        train_rows = [extract_features(ep.observation, tier) for ep in train]
        gate_rows = [extract_features(ep.observation, tier) for ep in gate]
        attackers[tier], prediction_sets[tier] = {}, {}
        for name, model in (
            ("categorical_naive_bayes", CategoricalNaiveBayes()),
            ("decision_tree_depth_3", ShallowCategoricalTree(max_depth=3)),
        ):
            model.fit(train_rows, train_labels)
            preds = model.predict(gate_rows)
            prediction_sets[tier][name] = preds
            attackers[tier][name] = {
                **_metrics(gate_labels, preds),
                "seed_block_bootstrap": _bootstrap_intervals(
                    gate_labels, preds, gate_blocks, replicates=bootstrap_samples,
                    seed=20261110 + (0 if tier == "M0" else 100 if tier == "M1" else 200)
                    + (0 if name == "categorical_naive_bayes" else 1)),
                "per_environment": _environment_metrics(gate, gate_labels, preds),
            }
        attackers[tier]["majority"] = {
            **_metrics(gate_labels, majority_predictions),
            "seed_block_bootstrap": _bootstrap_intervals(
                gate_labels, majority_predictions, gate_blocks,
                replicates=bootstrap_samples, seed=20261200),
            "per_environment": _environment_metrics(gate, gate_labels, majority_predictions),
        }
    evidence_predictions = [_decision(ep.observation).value for ep in gate]
    evidence_reference = {
        **_metrics(gate_labels, evidence_predictions),
        "seed_block_bootstrap": _bootstrap_intervals(
            gate_labels, evidence_predictions, gate_blocks,
            replicates=bootstrap_samples, seed=20261300),
        "per_environment": _environment_metrics(gate, gate_labels, evidence_predictions),
    }
    return {
        "benchmark": "E02-I2-C-F-independent-scenario-families",
        "status": "development_gate_not_locked_test",
        "families": {"train": ["A", "B"], "gate": ["C"],
                     "reserved_locked_test": ["D", "new_family"]},
        "seeds_per_event": seeds, "train_episodes": len(train),
        "gate_episodes": len(gate),
        "event_classes": [x.value for x in SUPPORTED_EVENTS],
        "truth_seed_family_split_excluded_from_features": True,
        "namespace": namespace,
        "semantic_invariance": {"passed": True, "failure_count": 0, "failures": []},
        "metadata_attackers": attackers,
        "evidence_aware_reference": evidence_reference,
        "metadata_overlap": {
            "M0": _feature_overlap(train + gate, "M0"),
            "M1": _feature_overlap(train + gate, "M1"),
            "M2": _feature_overlap(train + gate, "M2"),
        },
        "limitations": [
            "A/B/C are separate simulator mechanisms sharing the adjudicator's event-feasibility contract; this is not open-world relation discovery.",
            "Family D and any new family remain reserved for a frozen locked test; no locked-test result is reported.",
            "The event is a simulator-side intervention used to construct controlled episodes, not something autonomously discovered by the generator.",
            "M2 context contains semantically relevant identity state and candidate shape; high attacker scores require ablation and causal controls before being called leakage.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--train-start-seed", type=int, default=1000)
    parser.add_argument("--gate-start-seed", type=int, default=50000)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    args = parser.parse_args()
    print(json.dumps(run_scenario_diversity(
        seeds=args.seeds, train_start_seed=args.train_start_seed,
        gate_start_seed=args.gate_start_seed,
        bootstrap_samples=args.bootstrap_samples,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
