"""E13-C finite dynamic-mechanism analogy and intervention evaluator.

This is a bounded deterministic research DSL, not a general causal discovery
system. A mapping predicts target responses from source responses; an
independent target simulator supplies the observed response.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

from .e13_b3_active import CandidateForecast, QuerySelection, select_discriminating_query


class MechanismContractError(ValueError):
    pass


@dataclass(frozen=True)
class MechanismRule:
    intervention_variable: str
    intervention_value: str
    outcome_variable: str
    outcome_value: str
    delay_steps: int
    context: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MechanismModel:
    model_id: str
    variables: tuple[str, ...]
    rules: tuple[MechanismRule, ...]

    def __post_init__(self) -> None:
        if not self.model_id or not self.variables or len(set(self.variables)) != len(self.variables):
            raise MechanismContractError("MODEL_ID_AND_UNIQUE_VARIABLES_REQUIRED")
        known = set(self.variables)
        seen = set()
        for rule in self.rules:
            if rule.intervention_variable not in known or rule.outcome_variable not in known:
                raise MechanismContractError("RULE_REFERENCES_UNKNOWN_VARIABLE")
            if rule.delay_steps < 0:
                raise MechanismContractError("NEGATIVE_DELAY")
            if len(dict(rule.context)) != len(rule.context):
                raise MechanismContractError("DUPLICATE_CONTEXT_KEY")
            key = (rule.intervention_variable, rule.intervention_value, tuple(sorted(rule.context)))
            if key in seen:
                raise MechanismContractError("AMBIGUOUS_RESPONSE_RULE")
            seen.add(key)


@dataclass(frozen=True)
class InterventionQuery:
    query_id: str
    variable: str
    value: str
    context: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MechanismMap:
    candidate_id: str
    intervention_variables: tuple[tuple[str, str], ...]
    outcome_variables: tuple[tuple[str, str], ...]
    intervention_values: tuple[tuple[str, str], ...]
    outcome_values: tuple[tuple[str, str], ...]
    context_keys: tuple[tuple[str, str], ...] = ()
    provenance: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.provenance.strip() or not self.rationale.strip():
            raise MechanismContractError("CANDIDATE_ID_PROVENANCE_RATIONALE_REQUIRED")
        for pairs in (self.intervention_variables, self.outcome_variables,
                      self.intervention_values, self.outcome_values, self.context_keys):
            src = [x[0] for x in pairs]
            dst = [x[1] for x in pairs]
            if len(src) != len(set(src)) or len(dst) != len(set(dst)):
                raise MechanismContractError("MAPPING_MUST_BE_INJECTIVE")


@dataclass(frozen=True)
class MechanismResponse:
    variable: str
    value: str
    delay_steps: int


def _lookup(pairs: Iterable[tuple[str, str]], key: str) -> str | None:
    return dict(pairs).get(key)


def _canonical(response: MechanismResponse) -> str:
    return json.dumps(
        {"variable": response.variable, "value": response.value,
         "delay_steps": response.delay_steps},
        sort_keys=True, separators=(",", ":"),
    )


def _find_rule(model: MechanismModel, variable: str, value: str,
               context: tuple[tuple[str, str], ...]) -> MechanismResponse | None:
    matches = [r for r in model.rules
               if r.intervention_variable == variable
               and r.intervention_value == value
               and tuple(sorted(r.context)) == tuple(sorted(context))]
    if len(matches) != 1:
        return None
    rule = matches[0]
    return MechanismResponse(rule.outcome_variable, rule.outcome_value, rule.delay_steps)


def _translate_query(query: InterventionQuery, mapping: MechanismMap) -> tuple[str, str, tuple[tuple[str, str], ...]] | None:
    variable = _lookup(mapping.intervention_variables, query.variable)
    value = _lookup(mapping.intervention_values, query.value)
    context_map = dict(mapping.context_keys)
    if variable is None or value is None:
        return None
    translated_context = []
    for key, context_value in query.context:
        target_key = context_map.get(key)
        if target_key is None:
            return None
        translated_context.append((target_key, context_value))
    return variable, value, tuple(sorted(translated_context))


def forecast_target_response(source: MechanismModel, mapping: MechanismMap,
                              query: InterventionQuery) -> MechanismResponse | None:
    """Translate a source model's response into a target-domain prediction."""
    if query.variable not in source.variables:
        return None
    source_response = _find_rule(source, query.variable, query.value, query.context)
    translated = _translate_query(query, mapping)
    if source_response is None or translated is None:
        return None
    target_outcome_variable = _lookup(mapping.outcome_variables, source_response.variable)
    target_outcome_value = _lookup(mapping.outcome_values, source_response.value)
    if target_outcome_variable is None or target_outcome_value is None:
        return None
    return MechanismResponse(target_outcome_variable, target_outcome_value,
                             source_response.delay_steps)


def observe_target_response(target: MechanismModel, mapping: MechanismMap,
                            query: InterventionQuery) -> MechanismResponse | None:
    """Read the target simulator independently after translating the intervention."""
    translated = _translate_query(query, mapping)
    if translated is None:
        return None
    variable, value, context = translated
    return _find_rule(target, variable, value, context)


def forecast_record(candidate_id: str, query: InterventionQuery,
                    source: MechanismModel, mapping: MechanismMap) -> CandidateForecast | None:
    response = forecast_target_response(source, mapping, query)
    if response is None:
        return None
    return CandidateForecast(candidate_id, query.query_id, _canonical(response))


def select_mechanism_query(source: MechanismModel, target: MechanismModel,
                           mappings: tuple[MechanismMap, ...],
                           queries: tuple[InterventionQuery, ...]) -> QuerySelection:
    """Use the existing B3-D selector over complete candidate forecasts.

    Target outcomes are intentionally not read during query selection. They
    are consulted only after a query is selected by candidate disagreement.
    """
    forecasts = []
    for query in queries:
        for mapping in mappings:
            record = forecast_record(mapping.candidate_id, query, source, mapping)
            if record is not None:
                forecasts.append(record)
    return select_discriminating_query(
        (m.candidate_id for m in mappings), forecasts
    )
