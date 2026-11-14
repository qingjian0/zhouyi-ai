"""M34 mechanism decomposition audit; declaration checker, not a causal estimator."""
from dataclasses import dataclass
from enum import Enum
class EstimandKind(str,Enum):
 TOTAL_EFFECT="total_effect"; CONTROLLED_DIRECT="controlled_direct_effect"; NATURAL_DIRECT="natural_direct_effect"; NATURAL_INDIRECT="natural_indirect_effect"; INTERVENTIONAL_INDIRECT="interventional_indirect_effect"; FACTORIAL_INTERACTION="factorial_interaction"; CATE="conditional_average_treatment_effect"
class AssignmentDesign(str,Enum):
 RANDOMIZED="randomized"; QUASI_EXPERIMENTAL="quasi_experimental"; OBSERVATIONAL="observational"; SIMULATED="simulated"
@dataclass(frozen=True)
class MechanismVariable:
 variable_id:str; role:str; measurement:str; temporal_order:str; context_family:str
@dataclass(frozen=True)
class MediatorSpec:
 mediator_id:str; treatment_id:str; outcome_id:str; mediator_variable_id:str; identification_assumptions:tuple; treatment_induced_confounding:str; cross_world_assumption:str; alternative_paths:tuple
@dataclass(frozen=True)
class FactorialCell:
 cell_id:str; composition_id:str; context_family:str; object_family:str; source_family:str; factor_levels:tuple; outcome:float; outcome_scale:str; assignment:AssignmentDesign; evidence_refs:tuple
@dataclass(frozen=True)
class EffectEstimand:
 estimand_id:str; kind:EstimandKind; treatment_id:str; outcome_id:str; target_population:str; scale:str; identification_strategy:str; assumptions:tuple; preregistration_ref:str
@dataclass(frozen=True)
class EffectEstimate:
 estimate_id:str; estimand_id:str; estimate:float; standard_error:str; confidence_interval:str; estimator:str; data_split:str; reviewer_ids:tuple; evidence_refs:tuple
@dataclass(frozen=True)
class ContextStratum:
 stratum_id:str; context_family:str; object_family:str; measurement_instrument:str; population_definition:str
@dataclass(frozen=True)
class MeasurementInvarianceAudit:
 audit_id:str; instrument:str; compared_strata:tuple; invariance_level:str; evidence_refs:tuple; reviewer_ids:tuple
@dataclass(frozen=True)
class MechanismPath:
 path_id:str; node_ids:tuple; edge_evidence_refs:tuple; context_family:str; status:str
@dataclass(frozen=True)
class AttributionRecord:
 method:str; value:str; interpretation:str
@dataclass(frozen=True)
class MechanismDecompositionAudit:
 valid:bool; issues:tuple; disposition:str; causal_truth_established:bool=False
def factorial_interaction_contrast(y00,y10,y01,y11):
 """Additive-scale 2x2 interaction contrast, not a generic causal estimator."""
 return y11-y10-y01+y00
def audit_mechanism_decomposition(variables=(),mediators=(),cells=(),estimands=(),estimates=(),strata=(),invariance_audits=(),paths=(),attributions=()):
 variables,mediators,cells=tuple(variables),tuple(mediators),tuple(cells)
 estimands,estimates=tuple(estimands),tuple(estimates); strata,invariance_audits,paths=tuple(strata),tuple(invariance_audits),tuple(paths)
 issues=[]; vm={x.variable_id:x for x in variables}; em={x.estimand_id:x for x in estimands}; sm={x.stratum_id:x for x in strata}
 if len(vm)!=len(variables): issues.append("duplicate_variable_id")
 if len(em)!=len(estimands): issues.append("duplicate_estimand_id")
 if len(sm)!=len(strata): issues.append("duplicate_stratum_id")
 for v in variables:
  if not all((v.variable_id,v.role,v.measurement,v.temporal_order,v.context_family)): issues.append("incomplete_mechanism_variable:"+v.variable_id)
 for m in mediators:
  if m.mediator_variable_id not in vm: issues.append("unknown_mediator_variable:"+m.mediator_id)
  elif vm[m.mediator_variable_id].role!="mediator": issues.append("mediator_role_mismatch:"+m.mediator_id)
  if not m.identification_assumptions: issues.append("mediator_requires_identification_assumptions:"+m.mediator_id)
  if not m.treatment_induced_confounding.strip(): issues.append("mediator_requires_treatment_induced_confounding_audit:"+m.mediator_id)
  if not m.cross_world_assumption.strip(): issues.append("mediator_requires_cross_world_assumption_audit:"+m.mediator_id)
  if not m.alternative_paths: issues.append("mediator_requires_alternative_paths:"+m.mediator_id)
 for e in estimands:
  if not all((e.estimand_id,e.treatment_id,e.outcome_id,e.target_population,e.scale,e.identification_strategy,e.preregistration_ref)): issues.append("incomplete_estimand:"+e.estimand_id)
  if not e.assumptions: issues.append("estimand_requires_assumptions:"+e.estimand_id)
  if e.kind in (EstimandKind.NATURAL_DIRECT,EstimandKind.NATURAL_INDIRECT) and not any(m.treatment_id==e.treatment_id and m.outcome_id==e.outcome_id for m in mediators): issues.append("natural_mediation_estimand_requires_mediator_spec:"+e.estimand_id)
 ids=[c.cell_id for c in cells]
 if len(ids)!=len(set(ids)): issues.append("duplicate_factorial_cell_id")
 for c in cells:
  if not all((c.cell_id,c.composition_id,c.context_family,c.object_family,c.source_family,c.outcome_scale)) or not c.factor_levels: issues.append("incomplete_factorial_cell:"+c.cell_id)
  if len(dict(c.factor_levels))!=len(c.factor_levels): issues.append("duplicate_factor_level:"+c.cell_id)
  if not c.evidence_refs: issues.append("factorial_cell_requires_evidence:"+c.cell_id)
 for x in estimates:
  if x.estimand_id not in em: issues.append("unknown_estimate_estimand:"+x.estimate_id); continue
  if not all((x.estimate_id,x.standard_error,x.confidence_interval,x.estimator,x.data_split)) or not x.reviewer_ids or not x.evidence_refs: issues.append("incomplete_effect_estimate:"+x.estimate_id)
  if x.data_split in ("discovery","mechanism_discovery"): issues.append("discovery_split_cannot_validate_effect:"+x.estimate_id)
 for a in invariance_audits:
  if not a.instrument or len(a.compared_strata)<2 or not a.evidence_refs or not a.reviewer_ids: issues.append("incomplete_measurement_invariance_audit:"+a.audit_id)
  if any(s not in sm for s in a.compared_strata): issues.append("unknown_invariance_stratum:"+a.audit_id)
 for p in paths:
  if len(p.node_ids)<2 or not p.edge_evidence_refs or not p.context_family: issues.append("incomplete_mechanism_path:"+p.path_id)
  if len(p.node_ids)!=len(set(p.node_ids)): issues.append("cyclic_or_repeated_mechanism_node:"+p.path_id)
 for a in attributions:
  if a.interpretation.lower() in ("causal","causal_contribution","causal_effect"): issues.append("predictive_attribution_cannot_be_causal:"+a.method)
 for s in strata:
  if not all((s.context_family,s.object_family,s.measurement_instrument,s.population_definition)): issues.append("incomplete_context_stratum:"+s.stratum_id)
 valid=not issues
 return MechanismDecompositionAudit(valid,tuple(sorted(set(issues))),"review_required" if valid else "blocked",False)
