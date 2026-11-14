"""M51 heterogeneous SCM family suite: binary-logistic and nonlinear-interaction mechanisms."""
from dataclasses import dataclass
from math import exp, isfinite
import random


@dataclass(frozen=True)
class FamilyNode:
    name: str
    parents: tuple
    coefficients: tuple
    mechanism: str = "linear_gaussian"
    intercept: float = 0.0
    noise_scale: float = 1.0
    interaction_coefficient: float = 0.0


@dataclass(frozen=True)
class FamilySpec:
    family_id: str
    nodes: tuple
    seed: int
    population_size: int


@dataclass(frozen=True)
class FamilySample:
    unit_id: int
    values: tuple
    intervention: tuple


class FamilyValidationError(ValueError):
    pass


class FamilyEnvironment:
    """Persistent finite SCM population with heterogeneous node mechanisms.

    Supported mechanisms:
      * linear_gaussian: intercept + weighted parents + fixed Gaussian exogenous noise
      * nonlinear_interaction: linear terms + interaction_coefficient * product(parents)
      * binary_logistic: Bernoulli(logistic(intercept + weighted parents)) using fixed
        per-unit uniform exogenous noise, preserving paired potential outcomes.
    """
    MECHANISMS = {"linear_gaussian", "nonlinear_interaction", "binary_logistic"}

    def __init__(self, spec):
        self.spec = spec
        if not spec.family_id or not spec.nodes or not isinstance(spec.population_size, int) or spec.population_size < 1:
            raise FamilyValidationError("invalid_family_or_population")
        names = [n.name for n in spec.nodes]
        if any(not n for n in names) or len(names) != len(set(names)):
            raise FamilyValidationError("invalid_or_duplicate_node")
        known = set(names)
        for node in spec.nodes:
            if node.mechanism not in self.MECHANISMS:
                raise FamilyValidationError("unsupported_mechanism:" + node.mechanism)
            if len(node.parents) != len(node.coefficients):
                raise FamilyValidationError("parent_coefficient_mismatch:" + node.name)
            if len(set(node.parents)) != len(node.parents) or any(p not in known for p in node.parents):
                raise FamilyValidationError("invalid_parent:" + node.name)
            if node.name in node.parents:
                raise FamilyValidationError("self_cycle:" + node.name)
            params = (node.intercept, node.noise_scale, node.interaction_coefficient, *node.coefficients)
            if any(not isfinite(x) for x in params) or node.noise_scale < 0:
                raise FamilyValidationError("invalid_node_parameter:" + node.name)
            if node.mechanism == "binary_logistic" and node.noise_scale != 0:
                # Binary randomness comes from a fixed uniform, not Gaussian noise.
                raise FamilyValidationError("binary_logistic_noise_scale_must_be_zero:" + node.name)
        self.order = self._topological_order()
        rng = random.Random(spec.seed)
        self._exogenous = {}
        for unit in range(spec.population_size):
            self._exogenous[unit] = {}
            for node in self.order:
                self._exogenous[unit][node.name] = (
                    rng.random() if node.mechanism == "binary_logistic"
                    else rng.gauss(0.0, node.noise_scale)
                )

    def _topological_order(self):
        by_name = {n.name: n for n in self.spec.nodes}
        pending = {n.name: set(n.parents) for n in self.spec.nodes}
        ordered = []
        while pending:
            ready = sorted(name for name, deps in pending.items() if not deps)
            if not ready:
                raise FamilyValidationError("cyclic_graph")
            for name in ready:
                ordered.append(by_name[name])
                pending.pop(name)
            for deps in pending.values():
                deps.difference_update(ready)
        return tuple(ordered)

    @property
    def node_names(self):
        return tuple(n.name for n in self.order)

    def sample(self, unit_ids, interventions=None):
        interventions = dict(interventions or {})
        if any(name not in self.node_names for name in interventions):
            raise FamilyValidationError("unknown_intervention_target")
        if any(not isinstance(value, (int, float)) or not isfinite(value)
               for value in interventions.values()):
            raise FamilyValidationError("non_finite_intervention")
        by_name = {n.name: n for n in self.order}
        for name, value in interventions.items():
            if by_name[name].mechanism == "binary_logistic" and value not in (0, 1, 0.0, 1.0):
                raise FamilyValidationError("binary_intervention_must_be_zero_or_one")
        rows = []
        for unit_id in unit_ids:
            if not isinstance(unit_id, int) or unit_id < 0 or unit_id >= self.spec.population_size:
                raise FamilyValidationError("unit_id_out_of_range")
            values = {}
            for node in self.order:
                if node.name in interventions:
                    values[node.name] = float(interventions[node.name])
                    continue
                parents = [values[p] for p in node.parents]
                linear = node.intercept + sum(c * values[p] for p, c in zip(node.parents, node.coefficients))
                if node.mechanism == "linear_gaussian":
                    value = linear + self._exogenous[unit_id][node.name]
                elif node.mechanism == "nonlinear_interaction":
                    interaction = 1.0
                    for parent in parents:
                        interaction *= parent
                    value = linear + node.interaction_coefficient * interaction + self._exogenous[unit_id][node.name]
                else:
                    logit = max(-60.0, min(60.0, linear))
                    probability = 1.0 / (1.0 + exp(-logit))
                    value = float(self._exogenous[unit_id][node.name] < probability)
                values[node.name] = value
            rows.append(FamilySample(
                unit_id, tuple((name, values[name]) for name in self.node_names),
                tuple(sorted((name, float(value)) for name, value in interventions.items()))
            ))
        return tuple(rows)

    def direct_parents(self, target):
        if target not in self.node_names:
            raise FamilyValidationError("unknown_target")
        return tuple(next(n for n in self.order if n.name == target).parents)

    def ancestors(self, target):
        if target not in self.node_names:
            raise FamilyValidationError("unknown_target")
        by_name = {n.name: n for n in self.order}
        found, pending = set(), list(by_name[target].parents)
        while pending:
            name = pending.pop()
            if name not in found:
                found.add(name)
                pending.extend(by_name[name].parents)
        return tuple(sorted(found))

    def oracle(self, target):
        return {"target": target, "direct_parents": self.direct_parents(target),
                "ancestors": self.ancestors(target), "family_id": self.spec.family_id,
                "ground_truth_available_to_evaluator_only": True}


def binary_confounded_family(seed=17, population_size=512):
    return FamilySpec("binary-logistic-confounded-v1", (
        FamilyNode("q", (), (), "binary_logistic", intercept=0.0),
        FamilyNode("a", ("q",), (2.0,), "binary_logistic", intercept=-1.0),
        FamilyNode("b", (), (), "binary_logistic", intercept=0.0),
        FamilyNode("c", ("q",), (2.0,), "binary_logistic", intercept=-1.0),
        FamilyNode("y", ("a", "b"), (2.5, 2.0), "binary_logistic", intercept=-2.0),
    ), seed, population_size)


def nonlinear_interaction_family(seed=23, population_size=512):
    return FamilySpec("nonlinear-interaction-continuous-v1", (
        FamilyNode("x", (), (), "linear_gaussian", noise_scale=1.0),
        FamilyNode("z", (), (), "linear_gaussian", noise_scale=1.0),
        FamilyNode("w", ("x",), (1.0,), "linear_gaussian", noise_scale=0.2),
        FamilyNode("y", ("x", "z"), (0.0, 0.0), "nonlinear_interaction",
                   noise_scale=0.1, interaction_coefficient=2.0),
    ), seed, population_size)


def evaluate_family(spec, target, candidates, top_k):
    """Run paired do(0)/do(1) contrasts; oracle is read only after selection."""
    env = FamilyEnvironment(spec)
    units = tuple(range(spec.population_size))
    effects = {}
    for candidate in candidates:
        zero = env.sample(units, {candidate: 0.0})
        one = env.sample(units, {candidate: 1.0})
        mean_zero = sum(dict(row.values)[target] for row in zero) / len(zero)
        mean_one = sum(dict(row.values)[target] for row in one) / len(one)
        effects[candidate] = mean_one - mean_zero
    selected = tuple(sorted(candidates, key=lambda name: (-abs(effects[name]), name))[:top_k])
    truth = env.oracle(target)["direct_parents"]
    truth_set, selected_set = set(truth), set(selected)
    tp = len(truth_set & selected_set)
    precision = tp / len(selected_set) if selected_set else 0.0
    recall = tp / len(truth_set) if truth_set else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "family_id": spec.family_id, "target": target, "effects": effects,
        "selected": selected, "truth_evaluator_only": tuple(sorted(truth)),
        "precision": precision, "recall": recall, "f1": f1,
        "population_size": spec.population_size,
        "paired_unit_ids": units,
        "oracle_used_after_selection": True,
    }


def run_family_suite(seed=17, population_size=512):
    binary = evaluate_family(
        binary_confounded_family(seed, population_size), "y", ("a", "b", "c"), 2
    )
    nonlinear = evaluate_family(
        nonlinear_interaction_family(seed + 1, population_size), "y", ("x", "z", "w"), 2
    )
    return {
        "protocol": "m51-heterogeneous-scm-family-suite-v0.1",
        "results": (binary, nonlinear),
        "mean_f1": (binary["f1"] + nonlinear["f1"]) / 2,
        "limitations": (
            "synthetic_families_only",
            "binary_logistic_and_nonlinear_interaction_families_only",
            "handwritten_intervention_effect_selector_not_an_llm",
            "two_family_suite_not_a_general_causal_discovery_benchmark",
            "oracle_used_for_evaluation_only_after_selection",
        ),
    }
