"""Transparent structural and decision metrics for benchmark comparisons."""
from dataclasses import dataclass

@dataclass(frozen=True)
class GraphMetrics:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    structural_hamming_distance: int

@dataclass(frozen=True)
class MethodResult:
    method: str
    scenario_id: str
    seed: int
    metrics: GraphMetrics
    ablation: str = "full"

def evaluate_graph(predicted_edges, true_edges):
    pred=set(predicted_edges); truth=set(true_edges)
    tp=len(pred & truth); fp=len(pred-truth); fn=len(truth-pred)
    precision=tp/(tp+fp) if tp+fp else (1.0 if not truth else 0.0)
    recall=tp/(tp+fn) if tp+fn else 1.0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    # Directed edge insertion/deletion; reversal costs two operations.
    shd=fp+fn
    return GraphMetrics(tp,fp,fn,precision,recall,f1,shd)

def compare_methods(results):
    results=tuple(results); grouped={}
    for r in results:
        if not r.method or not r.scenario_id: raise ValueError("missing_method_or_scenario")
        key=(r.method,r.ablation); grouped.setdefault(key,[]).append(r.metrics)
    summary={}
    for key,metrics in grouped.items():
        n=len(metrics)
        summary[key]={
            "runs":n,
            "mean_precision":sum(x.precision for x in metrics)/n,
            "mean_recall":sum(x.recall for x in metrics)/n,
            "mean_f1":sum(x.f1 for x in metrics)/n,
            "mean_shd":sum(x.structural_hamming_distance for x in metrics)/n,
        }
    return summary
