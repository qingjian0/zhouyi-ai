"""E12-A2-M: finite-hypothesis active measurement selection."""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Mapping, Sequence

@dataclass(frozen=True)
class Probe:
    action_id: str
    cost: float
    # outcome -> (hypothesis_id -> P(outcome | hypothesis, action))
    likelihoods: Mapping[str, Mapping[str, float]]

def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def _validate_priors(priors: Mapping[str, float]) -> dict[str, float]:
    if not priors or any(not isinstance(k, str) or not k for k in priors):
        raise ValueError("priors need non-empty hypothesis IDs")
    values = dict(priors)
    if any(not _finite_number(v) or v < 0 for v in values.values()):
        raise ValueError("prior weights must be finite and non-negative")
    total = sum(values.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("prior weights must have positive finite mass")
    return {k: v / total for k, v in values.items()}

def _validate_probe(probe: Probe, hypothesis_ids: set[str]) -> dict[str, dict[str, float]]:
    if not isinstance(probe.action_id, str) or not probe.action_id:
        raise ValueError("action_id must be a non-empty string")
    if not _finite_number(probe.cost) or probe.cost <= 0:
        raise ValueError("probe cost must be positive and finite")
    if not probe.likelihoods:
        raise ValueError("probe must declare at least one outcome")
    table = {}
    for outcome, row in probe.likelihoods.items():
        if not isinstance(outcome, str) or not outcome or set(row) != hypothesis_ids:
            raise ValueError("each outcome must define every candidate hypothesis")
        clean = {}
        for hypothesis, probability in row.items():
            if not _finite_number(probability) or probability < 0 or probability > 1:
                raise ValueError("likelihoods must be finite probabilities")
            clean[hypothesis] = probability
        table[outcome] = clean
    for hypothesis in hypothesis_ids:
        mass = sum(table[outcome][hypothesis] for outcome in table)
        if not math.isclose(mass, 1.0, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("outcome likelihoods must sum to one per hypothesis")
    return table

def _entropy(distribution: Mapping[str, float]) -> float:
    return -sum(p * math.log2(p) for p in distribution.values() if p > 0)

def posterior_after_observation(priors: Mapping[str, float], probe: Probe, observed_outcome: str) -> dict:
    """Bayes update after an environment-side reveal; never invents an outcome."""
    prior = _validate_priors(priors)
    table = _validate_probe(probe, set(prior))
    if observed_outcome not in table:
        raise ValueError("observed outcome is not declared by the selected probe")
    unnormalized = {h: w * table[observed_outcome][h] for h, w in prior.items()}
    evidence = sum(unnormalized.values())
    if evidence <= 0:
        return {"status": "INCONSISTENT", "posterior": None, "evidence_probability": 0.0}
    return {"status": "UPDATED",
            "posterior": {h: v / evidence for h, v in unnormalized.items()},
            "evidence_probability": evidence}

def expected_information_gain(priors: Mapping[str, float], probe: Probe) -> float:
    prior = _validate_priors(priors)
    table = _validate_probe(probe, set(prior))
    expected = 0.0
    for row in table.values():
        p_outcome = sum(prior[h] * row[h] for h in prior)
        if p_outcome <= 0:
            continue
        posterior = {h: prior[h] * row[h] / p_outcome for h in prior}
        expected += p_outcome * _entropy(posterior)
    return max(0.0, _entropy(prior) - expected)

def select_probe(priors: Mapping[str, float], probes: Sequence[Probe],
                 remaining_budget: float, *, tie_tolerance: float = 1e-12) -> dict:
    """Select max IG/cost among affordable probes, or explicitly abstain."""
    prior = _validate_priors(priors)
    if not _finite_number(remaining_budget) or remaining_budget < 0:
        raise ValueError("remaining_budget must be finite and non-negative")
    if not _finite_number(tie_tolerance) or tie_tolerance < 0:
        raise ValueError("tie_tolerance must be finite and non-negative")
    ids = [p.action_id for p in probes]
    if len(ids) != len(set(ids)):
        raise ValueError("probe action IDs must be unique")
    scored = []
    for probe in probes:
        table = _validate_probe(probe, set(prior))
        if probe.cost <= remaining_budget:
            gain = expected_information_gain(prior, probe)
            scored.append({"probe": probe, "information_gain": gain,
                           "utility": gain / probe.cost, "outcomes": tuple(sorted(table))})
    if not scored:
        return {"status": "BUDGET_EXHAUSTED", "selected": None, "candidates": []}
    best = max(item["utility"] for item in scored)
    if best <= tie_tolerance:
        return {"status": "NO_DISCRIMINATING_ACTION", "selected": None,
                "candidates": [{"action_id": x["probe"].action_id,
                                "information_gain": x["information_gain"],
                                "utility": x["utility"]}
                               for x in sorted(scored, key=lambda x: x["probe"].action_id)]}
    tied = [x for x in scored if best - x["utility"] <= tie_tolerance]
    winner = min(tied, key=lambda x: (x["probe"].cost, x["probe"].action_id))
    return {"status": "SELECTED", "selected": winner["probe"].action_id,
            "information_gain": winner["information_gain"], "utility": winner["utility"],
            "predicted_outcomes": winner["outcomes"],
            "candidates": [{"action_id": x["probe"].action_id,
                            "information_gain": x["information_gain"], "utility": x["utility"]}
                           for x in sorted(scored, key=lambda x: x["probe"].action_id)]}
