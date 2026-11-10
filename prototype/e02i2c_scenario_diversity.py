"""E02-I2-C-F scenario-diversity prototype.

Train uses generator families A/B; Gate uses family C only. Event truth,
seed, family, and split remain evaluator-side. This first implementation
reuses the adjudication contract fixtures as semantic seeds, then applies
family-specific nuisance mechanisms. It is a development prototype, not the
final independent-generator or locked-test claim.
"""
from __future__ import annotations

import argparse
import json
import random
import secrets
from dataclasses import dataclass, replace
from typing import Iterable

from prototype.e02i2c_hidden_event_benchmark import (
    Episode, EventType, ObservationView, SUPPORTED_EVENTS, build_episode,
)
from prototype.e02i2c_adjudication import (
    EvidencePacket, EvidencePolarity, MissingReason, ObservationOpportunity,
    adjudicate_event,
)
from prototype.e02i2c_metadata_attack import (
    CategoricalNaiveBayes, ShallowCategoricalTree, extract_features,
    _majority, _metrics,
)


FAMILIES = ("A", "B", "C")
ENVIRONMENTS = ("env-temperate", "env-arid", "env-coastal", "env-high-noise")


def _opaque_packet(template: EvidencePacket, *, window: int, environment: str,
                   ordinal: int) -> EvidencePacket:
    token = secrets.token_hex(16)
    return EvidencePacket(
        evidence_id=f"ev-{token}",
        sample_id=f"sample-{token}",
        window=window,
        environment=environment,
        split=template.split,
        polarity=template.polarity,
        source_version_id=template.source_version_id,
        candidate_signature=template.candidate_signature,
        raw_observation_ref=f"observation://{token}/{ordinal}",
    )


def _shift_windows(view: ObservationView, offset: int) -> ObservationView:
    return replace(
        view,
        opportunities=tuple(replace(x, window=x.window + offset) for x in view.opportunities),
        evidence=tuple(replace(x, window=x.window + offset) for x in view.evidence),
    )


def _family_a(view: ObservationView, rng: random.Random) -> ObservationView:
    # Temporal family: random origin and presentation-order permutation.
    shifted = _shift_windows(view, rng.randrange(1, 40))
    packets = list(shifted.evidence)
    rng.shuffle(packets)
    return replace(shifted, evidence=tuple(packets))


def _family_b(view: ObservationView, rng: random.Random) -> ObservationView:
    # Resampling family: alternate opaque provenance serialization and
    # independent observation grouping. The semantic windows remain intact.
    varied = []
    for item in view.opportunities:
        expected = item.expected_samples + rng.randrange(1, 8)
        if item.coverage < 0.5:
            # Preserve insufficient-sampling ABSTAIN subtypes.
            observed = min(expected, item.observed_samples)
            reason = item.missing_reason
        else:
            # A resampling nuisance must not silently cross the adjudicator's
            # sufficiency boundary.
            minimum_sufficient = (expected * 8 + 9) // 10
            observed = min(expected, max(
                minimum_sufficient, item.observed_samples + rng.randrange(1, 4)
            ))
            reason = None
        varied.append(replace(
            item, expected_samples=expected, observed_samples=observed,
            coverage=observed / expected, missing_reason=reason,
        ))
    opportunities = tuple(varied)
    packets = [_opaque_packet(p, window=p.window, environment=p.environment, ordinal=i)
               for i, p in enumerate(view.evidence)]
    rng.shuffle(packets)
    return replace(view, opportunities=opportunities, evidence=tuple(packets))


def _extra_semantic_packet(event: EventType, view: ObservationView,
                           window: int, environment: str) -> EvidencePacket | None:
    # Add only genuinely independent evidence that preserves the event rule.
    # ABSTAIN fixtures are intentionally not padded into a confirmable event.
    if event == EventType.ABSTAIN:
        return None
    template = view.evidence[-1]
    if event == EventType.KEEP:
        polarity, signature, source = EvidencePolarity.SUPPORTS, view.identity.signature, view.identity.version_id
    elif event == EventType.MODIFY:
        polarity, signature, source = EvidencePolarity.SUPPORTS, view.candidate_signature, view.identity.version_id
    elif event == EventType.CREATE:
        polarity, signature, source = EvidencePolarity.SUPPORTS, view.candidate_signature, None
    elif event == EventType.SUSPEND:
        polarity, signature, source = EvidencePolarity.ABSENCE, None, template.source_version_id
    elif event == EventType.REACTIVATE:
        polarity, signature, source = EvidencePolarity.SUPPORTS, view.identity.signature, view.identity.version_id
    elif event == EventType.REACTIVATE_MODIFY:
        polarity, signature, source = EvidencePolarity.SUPPORTS, view.candidate_signature, view.identity.version_id
    elif event == EventType.RETIRE:
        polarity, signature, source = EvidencePolarity.CONTRADICTS, None, view.identity.version_id
    else:
        return None
    token = secrets.token_hex(16)
    return EvidencePacket(
        evidence_id=f"ev-{token}", sample_id=f"sample-{token}", window=window,
        environment=environment, split=template.split, polarity=polarity,
        source_version_id=source, candidate_signature=signature,
        raw_observation_ref=f"field://{token}",
    )


def _family_c(event: EventType, view: ObservationView,
              rng: random.Random) -> ObservationView:
    # Environmental Gate family: environment shifts, coverage variation,
    # source-independent provenance and optional extra independent evidence.
    environment = rng.choice(ENVIRONMENTS)
    undersampled_abstain = (
        event == EventType.ABSTAIN
        and bool(view.opportunities)
        and all(item.coverage < 0.5 for item in view.opportunities)
    )
    opportunities = []
    for item in view.opportunities:
        if undersampled_abstain:
            opportunities.append(replace(item, environment=environment))
            continue
        expected = max(item.expected_samples, 12 + rng.randrange(0, 12))
        minimum_sufficient = (expected * 8 + 9) // 10
        observed = max(minimum_sufficient, int(expected * rng.uniform(0.82, 1.0)))
        opportunities.append(replace(
            item, environment=environment, expected_samples=expected,
            observed_samples=observed, coverage=observed / expected,
            missing_reason=None,
        ))
    packets = [
        replace(p, environment=environment)
        for p in view.evidence
    ]
    max_window = max((x.window for x in opportunities), default=0)
    # Extra no-exposure opportunities vary the sampling schedule without
    # becoming sufficient evidence or breaking a valid absence tail.
    if rng.random() < 0.65:
        opportunities.append(ObservationOpportunity(
            window=max_window + 3, environment=environment,
            expected_samples=10, observed_samples=0, coverage=0.0,
            missing_reason=MissingReason.NO_EXPOSURE,
        ))
    if event != EventType.ABSTAIN and rng.random() < 0.75:
        evidence_window = max_window + 1
        opportunities.append(ObservationOpportunity(
            window=evidence_window, environment=environment,
            expected_samples=16, observed_samples=14, coverage=0.875,
            missing_reason=None,
        ))
        extra = _extra_semantic_packet(event, view, evidence_window, environment)
        if extra is not None:
            packets.append(extra)
    rng.shuffle(packets)
    return replace(view, opportunities=tuple(opportunities), evidence=tuple(packets))


def generate_episode(event: EventType, seed: int, *, family: str,
                     split: str) -> Episode:
    if family not in FAMILIES:
        raise ValueError("family must be A, B or C; D is reserved")
    expected_split = "gate" if family == "C" else "train"
    if split != expected_split:
        raise ValueError("family/split violation: A+B are Train and C is Gate")
    base = build_episode(event, seed, split=split)
    rng = random.Random(f"e02i2cf:{family}:{seed}")
    if family == "A":
        view = _family_a(base.observation, rng)
    elif family == "B":
        view = _family_b(base.observation, rng)
    else:
        view = _family_c(event, base.observation, rng)
    return Episode(
        episode_id=f"eval-{family}-{split}-{seed}",
        truth=event,
        observation=view,
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


def run_scenario_diversity(*, seeds: int = 30, train_start_seed: int = 1000,
                           gate_start_seed: int = 50000) -> dict:
    if seeds < 30:
        raise ValueError("C-F development evaluation requires at least 30 seed blocks per event")
    train = [
        generate_episode(event, train_start_seed + block * 100 + index,
                         family=family, split="train")
        for family in ("A", "B")
        for block in range(seeds)
        for index, event in enumerate(SUPPORTED_EVENTS)
    ]
    gate = [
        generate_episode(event, gate_start_seed + block * 100 + index,
                         family="C", split="gate")
        for block in range(seeds)
        for index, event in enumerate(SUPPORTED_EVENTS)
    ]
    namespace = _namespace_check(train, gate)
    if not namespace["sample_disjoint"] or not namespace["evidence_disjoint"]:
        raise RuntimeError("Train/Gate provenance namespace collision")
    semantic_failures = [
        {"episode": ep.episode_id, "truth": ep.truth.value,
         "decision": adjudicate_event(
             ep.observation.identity, ep.observation.opportunities,
             ep.observation.evidence,
             candidate_signature=ep.observation.candidate_signature,
         ).event.value,
         "reason": adjudicate_event(
             ep.observation.identity, ep.observation.opportunities,
             ep.observation.evidence,
             candidate_signature=ep.observation.candidate_signature,
         ).reason,
         "opportunities": [
             {"window": x.window, "coverage": x.coverage,
              "observed": x.observed_samples, "expected": x.expected_samples}
             for x in ep.observation.opportunities
         ],
         "evidence": [
             {"window": x.window, "polarity": x.polarity.value,
              "source_version": x.source_version_id,
              "candidate": x.candidate_signature,
              "sample": x.sample_id}
             for x in ep.observation.evidence
         ]}
        for ep in train + gate if _decision(ep.observation) != ep.truth
    ]
    if semantic_failures:
        raise RuntimeError(f"nuisance transformation changed adjudication: {semantic_failures[:5]}")
    train_labels = [ep.truth.value for ep in train]
    gate_labels = [ep.truth.value for ep in gate]
    majority = _majority(train_labels)
    majority_predictions = [majority] * len(gate)
    attackers = {}
    for tier in ("M0", "M1", "M2"):
        train_rows = [extract_features(ep.observation, tier) for ep in train]
        gate_rows = [extract_features(ep.observation, tier) for ep in gate]
        attackers[tier] = {}
        for name, model in (
            ("categorical_naive_bayes", CategoricalNaiveBayes()),
            ("decision_tree_depth_3", ShallowCategoricalTree(max_depth=3)),
        ):
            model.fit(train_rows, train_labels)
            predictions = model.predict(gate_rows)
            attackers[tier][name] = _metrics(gate_labels, predictions)
        attackers[tier]["majority"] = _metrics(gate_labels, majority_predictions)
    evidence_predictions = [_decision(ep.observation).value for ep in gate]
    return {
        "benchmark": "E02-I2-C-F-scenario-diversity-prototype",
        "status": "development_prototype_not_locked_test",
        "families": {
            "train": ["A", "B"], "gate": ["C"], "reserved_locked_test": ["D", "new_family"],
        },
        "seeds_per_event": seeds,
        "train_episodes": len(train), "gate_episodes": len(gate),
        "event_classes": [x.value for x in SUPPORTED_EVENTS],
        "truth_seed_family_split_excluded_from_features": True,
        "namespace": namespace,
        "semantic_invariance": {
            "passed": not semantic_failures,
            "failure_count": len(semantic_failures),
            "failures": semantic_failures[:20],
        },
        "metadata_attackers": attackers,
        "evidence_aware_reference": _metrics(
            gate_labels, evidence_predictions
        ),
        "metadata_overlap": {
            "M0": _feature_overlap(train + gate, "M0"),
            "M1": _feature_overlap(train + gate, "M1"),
            "M2": _feature_overlap(train + gate, "M2"),
        },
        "limitations": [
            "Families A/B/C are distinct nuisance mechanisms layered on the existing event-semantic fixture; they are not yet fully independent generative theories.",
            "No family D locked test; no threshold tuning or open-world claim.",
            "Seed-block bootstrap and per-environment confidence intervals remain a follow-up before final preregistered acceptance.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--train-start-seed", type=int, default=1000)
    parser.add_argument("--gate-start-seed", type=int, default=50000)
    args = parser.parse_args()
    print(json.dumps(run_scenario_diversity(
        seeds=args.seeds, train_start_seed=args.train_start_seed,
        gate_start_seed=args.gate_start_seed,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
