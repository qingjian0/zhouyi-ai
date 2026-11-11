"""E12-A9: controlled symbolic-prior ablation for active measurement."""
from __future__ import annotations
import argparse, json, math, random
from typing import Mapping, Sequence
from prototype.e12a2_active_measurement_selector import select_measurement, update_weights

HYPOTHESES = tuple(f"h{i:03b}" for i in range(8))
SIGNATURES = {h: tuple(int(bit) for bit in h[1:]) for h in HYPOTHESES}
ACTIONS = ("measure_factor_0", "measure_factor_1", "measure_factor_2")
COSTS = dict(zip(ACTIONS, (1.0, 1.2, 1.4)))
BUDGET = 2.4
YANG_PROBABILITIES = (0.78, 0.68, 0.58)

def _normalize(weights):
    total = sum(weights.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("prior must have positive finite mass")
    return {k: v / total for k, v in weights.items()}

def _factorized_weights(signatures, probabilities):
    if len(probabilities) != 3 or any(not math.isfinite(float(p)) or not 0 < float(p) < 1 for p in probabilities):
        raise ValueError("three factor probabilities strictly between 0 and 1 required")
    weights = {}
    for h, bits in signatures.items():
        if len(bits) != 3 or any(bit not in (0, 1) for bit in bits):
            raise ValueError("each hypothesis requires a three-bit signature")
        mass = 1.0
        for bit, p in zip(bits, probabilities):
            mass *= float(p) if bit else 1.0 - float(p)
        weights[h] = mass
    return _normalize(weights)

def prior_weights(arm: str, *, seed: int = 0) -> dict[str, float]:
    if arm == "uniform":
        return {h: 1 / len(HYPOTHESES) for h in HYPOTHESES}
    if arm == "yijing_factorized":
        return _factorized_weights(SIGNATURES, YANG_PROBABILITIES)
    if arm == "anti_aligned":
        return _factorized_weights(SIGNATURES, tuple(1-p for p in YANG_PROBABILITIES))
    if arm == "shuffled_mapping":
        base = _factorized_weights(SIGNATURES, YANG_PROBABILITIES)
        ids = list(HYPOTHESES)
        rotated = ids[3:] + ids[:3]
        return _normalize(dict(zip(ids, (base[h] for h in rotated))))
    if arm == "random":
        rng = random.Random(seed)
        return _normalize({h: rng.gammavariate(1.0, 1.0) for h in HYPOTHESES})
    raise ValueError(f"unknown prior arm: {arm}")

def world_distribution(family: str):
    if family == "aligned": return prior_weights("yijing_factorized")
    if family == "uniform": return prior_weights("uniform")
    if family == "misaligned": return prior_weights("anti_aligned")
    if family == "permuted": return prior_weights("shuffled_mapping")
    raise ValueError(f"unknown world family: {family}")

def _likelihoods(action):
    factor = ACTIONS.index(action)
    return {h: {str(SIGNATURES[h][factor]): 0.9, str(1-SIGNATURES[h][factor]): 0.1} for h in HYPOTHESES}

def _draw_truth(distribution, rng):
    draw, cumulative = rng.random(), 0.0
    for h, p in distribution.items():
        cumulative += p
        if draw <= cumulative: return h
    return next(reversed(distribution))

def _sample_observation(truth, action, seed):
    rng = random.Random(f"{seed}:{action}:measurement")
    bit = SIGNATURES[truth][ACTIONS.index(action)]
    return str(bit if rng.random() < 0.9 else 1-bit)

def run_episode(family: str, arm: str, seed: int) -> dict:
    truth = _draw_truth(world_distribution(family), random.Random(f"{seed}:{family}:truth"))
    weights = prior_weights(arm, seed=seed)
    available, remaining, ledger = list(ACTIONS), BUDGET, []
    initial_entropy = -sum(p*math.log2(p) for p in weights.values() if p > 0)
    while available:
        predictions = {a: _likelihoods(a) for a in available}
        choice = select_measurement(weights, predictions, {a:COSTS[a] for a in available}, remaining)
        action = choice.get("selected_action")
        if action is None: break
        # Commit before query; potential measurement noise is keyed by action and episode.
        record = {"action": action, "cost": COSTS[action], "committed": True}
        observed = _sample_observation(truth, action, seed)
        record.update({"observation": observed, "revealed": True})
        weights = update_weights(weights, _likelihoods(action), observed)
        ledger.append(record)
        remaining -= COSTS[action]
        available.remove(action)
    entropy = -sum(p*math.log2(p) for p in weights.values() if p > 0)
    ranked = max(weights, key=weights.get)
    confidence = weights[ranked]
    return {"family":family,"arm":arm,"seed":seed,"correct":ranked==truth,
        "predicted":ranked,"truth":truth,"confidence":confidence,
        "confident_wrong":confidence>=0.8 and ranked!=truth,
        "initial_entropy":initial_entropy,"final_entropy":entropy,
        "realized_entropy_reduction":initial_entropy-entropy,
        "spent":sum(x["cost"] for x in ledger),"steps":len(ledger),"ledger":ledger}

def run_ablation(*, seeds: Sequence[int] = tuple(range(100))) -> dict:
    arms=("uniform","yijing_factorized","shuffled_mapping","anti_aligned","random")
    families=("aligned","uniform","misaligned","permuted")
    results={}
    for family in families:
        results[family]={}
        for arm in arms:
            episodes=[run_episode(family,arm,seed) for seed in seeds]
            n=len(episodes)
            results[family][arm]={
                "episodes":n,
                "accuracy":sum(e["correct"] for e in episodes)/n,
                "mean_realized_entropy_reduction":sum(e["realized_entropy_reduction"] for e in episodes)/n,
                "mean_cost":sum(e["spent"] for e in episodes)/n,
                "mean_steps":sum(e["steps"] for e in episodes)/n,
                "confident_wrong_rate":sum(e["confident_wrong"] for e in episodes)/n,
                "mean_final_confidence":sum(e["confidence"] for e in episodes)/n}
    return {"task":"E12A9_symbolic_prior_ablation","seed_count":len(seeds),
        "families":list(families),"arms":list(arms),"budget":BUDGET,
        "measurement_noise":0.1,"results":results,
        "limitations":["Eight fixed hypotheses with three predeclared binary factors.",
        "The symbolic factorization is an experimental operationalization, not a canonical classical mapping.",
        "World-family distributions are deliberately aligned, uniform, anti-aligned, or permuted.",
        "Only initial hypothesis weights vary; likelihoods, actions, costs, and observations are held fixed.",
        "Finite synthetic Bayesian model selection, not open-world concept discovery."]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--json",action="store_true")
    parser.add_argument("--seeds",type=int,default=100)
    args=parser.parse_args()
    if args.seeds<1: parser.error("--seeds must be positive")
    result=run_ablation(seeds=tuple(range(args.seeds)))
    print(json.dumps(result,indent=2,ensure_ascii=False) if args.json else result)

if __name__=="__main__": main()
