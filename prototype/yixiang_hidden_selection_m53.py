"""M53: hidden confounding, collider selection, measurement error and drift.

Agent-facing rows are separated from evaluator-only truth. Synthetic data are
for protocol validation, not evidence about real-world causal discovery.
"""
from dataclasses import dataclass
from math import exp, isfinite
import random


@dataclass(frozen=True)
class ObservedRow:
    unit_id: int
    environment: str
    x_observed: float
    y_observed: float
    selected: bool


@dataclass(frozen=True)
class EvaluatorTruth:
    scenario: str
    causal_effect_by_environment: tuple
    hidden_confounder_present: bool
    selection_on_collider: bool
    measurement_error_sd: float


@dataclass(frozen=True)
class M53Dataset:
    scenario: str
    agent_rows: tuple
    evaluator_truth: EvaluatorTruth
    protocol: str = "m53-observation-intervention-separation-v0.1"


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _validate_size(size):
    if not isinstance(size, int) or isinstance(size, bool) or size < 20:
        raise ValueError("population_size_must_be_integer_at_least_20")


def _logistic(value):
    value = max(-40.0, min(40.0, value))
    return 1.0 / (1.0 + exp(-value))


def hidden_confounding_dataset(seed=17, population_size=1000,
                               treatment_effect=1.5, confounder_x=1.2,
                               confounder_y=1.8, measurement_error_sd=0.0):
    """U -> X, U -> Y, X -> Y; U is never included in agent-facing rows."""
    _validate_size(population_size)
    params = (treatment_effect, confounder_x, confounder_y, measurement_error_sd)
    if any(not _finite(x) for x in params) or measurement_error_sd < 0:
        raise ValueError("invalid_generator_parameter")
    rng = random.Random(seed)
    rows = []
    for unit in range(population_size):
        u = rng.gauss(0.0, 1.0)
        ex = rng.gauss(0.0, 1.0)
        ey = rng.gauss(0.0, 1.0)
        x = confounder_x * u + ex
        y = treatment_effect * x + confounder_y * u + ey
        x_obs = x + rng.gauss(0.0, measurement_error_sd)
        rows.append(ObservedRow(unit, "stable", x_obs, y, True))
    return M53Dataset(
        "hidden_confounding", tuple(rows),
        EvaluatorTruth("hidden_confounding", (("stable", treatment_effect),),
                       True, False, measurement_error_sd),
    )


def collider_selection_dataset(seed=23, population_size=1000,
                               selection_threshold=1.0, treatment_effect=0.0):
    """X -> S <- Y with independent exogenous X and Y when effect is zero."""
    _validate_size(population_size)
    if not _finite(selection_threshold) or not _finite(treatment_effect):
        raise ValueError("invalid_generator_parameter")
    rng = random.Random(seed)
    rows = []
    for unit in range(population_size):
        x = rng.gauss(0.0, 1.0)
        y = treatment_effect * x + rng.gauss(0.0, 1.0)
        selected = (x + y) > selection_threshold
        rows.append(ObservedRow(unit, "selected_population", x, y, selected))
    return M53Dataset(
        "collider_selection", tuple(rows),
        EvaluatorTruth("collider_selection", (("selected_population", treatment_effect),),
                       False, True, 0.0),
    )


def measurement_error_dataset(seed=31, population_size=1000,
                              treatment_effect=1.5, measurement_error_sd=1.0):
    """Classical additive error affects X measurement, not the structural X -> Y."""
    _validate_size(population_size)
    if (not _finite(treatment_effect) or not _finite(measurement_error_sd)
            or measurement_error_sd < 0):
        raise ValueError("invalid_generator_parameter")
    rng = random.Random(seed)
    rows = []
    for unit in range(population_size):
        x = rng.gauss(0.0, 1.0)
        y = treatment_effect * x + rng.gauss(0.0, 1.0)
        x_obs = x + rng.gauss(0.0, measurement_error_sd)
        rows.append(ObservedRow(unit, "stable", x_obs, y, True))
    return M53Dataset(
        "measurement_error", tuple(rows),
        EvaluatorTruth("measurement_error", (("stable", treatment_effect),),
                       False, False, measurement_error_sd),
    )


def mechanism_drift_dataset(seed=43, population_size=1000,
                            effects=(1.0, 2.0, -0.5)):
    """Same X distribution, environment-specific structural effect on Y."""
    _validate_size(population_size)
    if not effects or any(not _finite(effect) for effect in effects):
        raise ValueError("invalid_environment_effects")
    rng = random.Random(seed)
    rows = []
    per_environment = population_size // len(effects)
    if per_environment < 1:
        raise ValueError("population_too_small_for_environments")
    truth = []
    unit = 0
    for index, effect in enumerate(effects):
        environment = "env_" + str(index)
        truth.append((environment, float(effect)))
        for _ in range(per_environment):
            x = rng.gauss(0.0, 1.0)
            y = effect * x + rng.gauss(0.0, 1.0)
            rows.append(ObservedRow(unit, environment, x, y, True))
            unit += 1
    return M53Dataset(
        "mechanism_drift", tuple(rows),
        EvaluatorTruth("mechanism_drift", tuple(truth), False, False, 0.0),
    )


def audit_m53_dataset(dataset):
    """Fail closed on malformed rows and accidental evaluator-field leakage."""
    errors = []
    if not isinstance(dataset, M53Dataset):
        return (False, ("invalid_dataset_type",))
    if not dataset.agent_rows:
        errors.append("empty_agent_rows")
    seen = set()
    for row in dataset.agent_rows:
        if not isinstance(row, ObservedRow):
            errors.append("invalid_observed_row")
            continue
        if row.unit_id in seen:
            errors.append("duplicate_unit_id:" + str(row.unit_id))
        seen.add(row.unit_id)
        if not row.environment:
            errors.append("empty_environment:" + str(row.unit_id))
        if not _finite(row.x_observed) or not _finite(row.y_observed):
            errors.append("non_finite_observation:" + str(row.unit_id))
        if not isinstance(row.selected, bool):
            errors.append("invalid_selection_flag:" + str(row.unit_id))
        if hasattr(row, "latent_u") or hasattr(row, "x_true"):
            errors.append("evaluator_field_leakage:" + str(row.unit_id))
    truth = dataset.evaluator_truth
    if not isinstance(truth, EvaluatorTruth):
        errors.append("invalid_evaluator_truth")
    elif any(not _finite(effect) for _, effect in truth.causal_effect_by_environment):
        errors.append("invalid_evaluator_effect")
    return (not errors, tuple(sorted(set(errors))))


def paired_intervention_effect(seed=53, population_size=1000, treatment_effect=1.5):
    """Estimate do(X=1)-do(X=0) with common exogenous noise per unit."""
    _validate_size(population_size)
    if not _finite(treatment_effect):
        raise ValueError("invalid_treatment_effect")
    rng = random.Random(seed)
    differences = []
    for _ in range(population_size):
        exogenous_y = rng.gauss(0.0, 1.0)
        y_do_0 = treatment_effect * 0.0 + exogenous_y
        y_do_1 = treatment_effect * 1.0 + exogenous_y
        differences.append(y_do_1 - y_do_0)
    return sum(differences) / len(differences)


def selected_correlation(dataset):
    """Descriptive statistic only; never returns a causal-effect estimate."""
    if not isinstance(dataset, M53Dataset):
        raise ValueError("invalid_dataset")
    rows = [row for row in dataset.agent_rows if row.selected]
    if len(rows) < 2:
        raise ValueError("insufficient_selected_rows")
    xs = [row.x_observed for row in rows]
    ys = [row.y_observed for row in rows]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        raise ValueError("zero_variance")
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (vx * vy) ** 0.5
