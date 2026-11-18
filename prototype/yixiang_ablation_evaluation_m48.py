"""M48 paired ablation evaluation with episode matching and bootstrap intervals."""
from dataclasses import dataclass
from math import isfinite
import random

@dataclass(frozen=True)
class MetricSpec:
    name: str
    higher_is_better: bool

@dataclass(frozen=True)
class EpisodeRun:
    variant_id: str
    episode_id: str
    seed: int
    metrics: tuple

@dataclass(frozen=True)
class AblationEffect:
    variant_id: str
    metric: str
    paired_episodes: int
    mean_effect: float
    lower_bound: float
    upper_bound: float

@dataclass(frozen=True)
class AblationAudit:
    valid: bool
    effects: tuple
    issues: tuple
    warnings: tuple

def _metric_map(run):
    values=dict(run.metrics)
    if len(values)!=len(run.metrics): raise ValueError("duplicate_metric")
    if any(not isfinite(v) for v in values.values()): raise ValueError("non_finite_metric")
    return values

def compare_ablation(full_runs,ablation_runs,metric_specs,bootstrap_samples=1000,seed=0):
    full_runs=tuple(full_runs); ablation_runs=tuple(ablation_runs); specs=tuple(metric_specs)
    issues=[]; warnings=[]; effects=[]
    if bootstrap_samples<1: issues.append("bootstrap_samples_must_be_positive")
    if not full_runs or not ablation_runs or not specs: issues.append("runs_and_metrics_required")
    if len({r.episode_id for r in full_runs})!=len(full_runs): issues.append("duplicate_full_episode")
    if len({r.episode_id for r in ablation_runs})!=len(ablation_runs): issues.append("duplicate_ablation_episode")
    full={r.episode_id:r for r in full_runs}; ablated={r.episode_id:r for r in ablation_runs}
    if set(full)!=set(ablated): issues.append("episode_sets_not_paired")
    if issues: return AblationAudit(False,(),tuple(issues),())
    if len({r.seed for r in full_runs})!=1 or len({r.seed for r in ablation_runs})!=1:
        warnings.append("multiple_seeds_within_variant_require_stratified_analysis")
    if next(iter(full.values())).variant_id!="full": issues.append("full_variant_id_must_be_full")
    ablation_ids={r.variant_id for r in ablation_runs}
    if len(ablation_ids)!=1: issues.append("ablation_variant_mismatch")
    if issues: return AblationAudit(False,(),tuple(issues),tuple(warnings))
    variant_id=next(iter(ablation_ids))
    rng=random.Random(seed)
    for spec in specs:
        deltas=[]
        for episode_id in sorted(full):
            try:
                fv=_metric_map(full[episode_id])[spec.name]
                av=_metric_map(ablated[episode_id])[spec.name]
            except (ValueError,KeyError):
                issues.append("missing_or_invalid_metric:"+spec.name); deltas=[]; break
            delta=(fv-av)*(1 if spec.higher_is_better else -1)
            deltas.append(delta)
        if not deltas: continue
        mean=sum(deltas)/len(deltas)
        samples=[]
        for _ in range(bootstrap_samples):
            draw=[deltas[rng.randrange(len(deltas))] for _ in deltas]
            samples.append(sum(draw)/len(draw))
        samples.sort()
        lower=samples[int(0.025*(len(samples)-1))]
        upper=samples[int(0.975*(len(samples)-1))]
        effects.append(AblationEffect(variant_id,spec.name,len(deltas),mean,lower,upper))
    if issues: return AblationAudit(False,(),tuple(sorted(set(issues))),tuple(warnings))
    warnings.append("paired_ablation_effect_is_benchmark_specific_not_universal_causal_explanation")
    return AblationAudit(True,tuple(effects),(),tuple(warnings))
