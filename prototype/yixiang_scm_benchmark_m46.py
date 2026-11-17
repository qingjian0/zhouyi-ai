"""M46 persistent-population structural causal model benchmark environment."""
from dataclasses import dataclass
from math import isfinite
import random

@dataclass(frozen=True)
class SCMNode:
    name: str
    parents: tuple
    coefficients: tuple
    intercept: float = 0.0
    noise_scale: float = 1.0

@dataclass(frozen=True)
class SCMSpec:
    model_id: str
    nodes: tuple
    seed: int
    population_size: int

@dataclass(frozen=True)
class BenchmarkSample:
    unit_id: int
    values: tuple
    intervention: tuple

class SCMValidationError(ValueError):
    pass

class SCMEnvironment:
    """Finite persistent population: each unit's exogenous noise is reused across queries."""
    def __init__(self,spec):
        self.spec=spec
        if not spec.model_id or not spec.nodes or spec.population_size<1:
            raise SCMValidationError("invalid_model_or_population")
        names=[n.name for n in spec.nodes]
        if any(not n for n in names) or len(names)!=len(set(names)):
            raise SCMValidationError("invalid_or_duplicate_node")
        known=set(names)
        for n in spec.nodes:
            if len(n.parents)!=len(n.coefficients): raise SCMValidationError("parent_coefficient_mismatch:"+n.name)
            if len(set(n.parents))!=len(n.parents): raise SCMValidationError("duplicate_parent:"+n.name)
            if any(p not in known for p in n.parents): raise SCMValidationError("unknown_parent:"+n.name)
            if n.name in n.parents: raise SCMValidationError("self_cycle:"+n.name)
            if not isfinite(n.intercept) or not isfinite(n.noise_scale) or n.noise_scale<0:
                raise SCMValidationError("invalid_node_parameter:"+n.name)
            if any(not isfinite(c) for c in n.coefficients): raise SCMValidationError("invalid_coefficient:"+n.name)
        self.order=self._topological_order()
        rng=random.Random(spec.seed)
        self._noise={u:{n.name:rng.gauss(0,n.noise_scale) for n in self.order}
                     for u in range(spec.population_size)}

    def _topological_order(self):
        by_name={n.name:n for n in self.spec.nodes}
        pending={n.name:set(n.parents) for n in self.spec.nodes}
        ordered=[]
        while pending:
            ready=sorted(k for k,v in pending.items() if not v)
            if not ready: raise SCMValidationError("cyclic_graph")
            for name in ready:
                ordered.append(by_name[name]); pending.pop(name)
            for deps in pending.values(): deps.difference_update(ready)
        return tuple(ordered)

    @property
    def node_names(self):
        return tuple(n.name for n in self.order)

    def sample(self,unit_ids,interventions=None):
        interventions=dict(interventions or {})
        if any(k not in self.node_names for k in interventions): raise SCMValidationError("unknown_intervention_target")
        if any(not isfinite(v) for v in interventions.values()): raise SCMValidationError("non_finite_intervention")
        rows=[]
        for unit_id in unit_ids:
            if not isinstance(unit_id,int) or unit_id<0 or unit_id>=self.spec.population_size:
                raise SCMValidationError("unit_id_out_of_range")
            values={}
            for node in self.order:
                if node.name in interventions:
                    values[node.name]=float(interventions[node.name])
                else:
                    values[node.name]=node.intercept+sum(c*values[p] for p,c in zip(node.parents,node.coefficients))+self._noise[unit_id][node.name]
            rows.append(BenchmarkSample(unit_id,tuple((k,values[k]) for k in self.node_names),
                                         tuple(sorted((k,float(v)) for k,v in interventions.items()))))
        return tuple(rows)

    def direct_parents(self,target):
        if target not in self.node_names: raise SCMValidationError("unknown_target")
        return tuple(next(n for n in self.order if n.name==target).parents)

    def ancestors(self,target):
        if target not in self.node_names: raise SCMValidationError("unknown_target")
        by_name={n.name:n for n in self.order}; found=set(); frontier=list(by_name[target].parents)
        while frontier:
            name=frontier.pop()
            if name not in found:
                found.add(name); frontier.extend(by_name[name].parents)
        return tuple(sorted(found))

    def oracle(self,target):
        return {"target":target,"direct_parents":self.direct_parents(target),
                "ancestors":self.ancestors(target),"model_id":self.spec.model_id,
                "ground_truth_available_to_evaluator_only":True}
