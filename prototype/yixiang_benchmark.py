"""M8 benchmark contracts and deterministic evaluation utilities."""
from __future__ import annotations
from collections import defaultdict
from collections.abc import Mapping, Sequence
RELATIONS={"morphological","structural","functional","process_mechanism","temporal","situated","symbolic_normative","empirical_correlation","causal_analogy"}
DECISIONS={"accept","reject","conditional","abstain"}
CAUSAL={"symbolic","normative","co_occurrence","correlational","mechanistic_hypothesis","intervention_supported","unknown"}
SOURCE_STATUS={"verified_primary","critical_edition","unverified_transcription","secondary_quotation","research_hypothesis","synthetic_fixture"}
REQUIRED={"case_id","source_lineage","source_status","target_claim","relation_families","shared_basis","non_shared_basis","scope_conditions","required_invariants","known_counterexamples","causal_status","evidence_refs","independence_group","gold_decision","gold_rationale","reviewers","split_group"}
def _strings(v,f,nonempty=True):
    if not isinstance(v,list) or (nonempty and not v): raise ValueError(f"{f} must be a {'non-empty ' if nonempty else ''}list")
    if any(not isinstance(x,str) or not x.strip() for x in v): raise ValueError(f"{f} entries must be non-empty strings")
    if len(v)!=len(set(v)): raise ValueError(f"{f} entries must be unique")
    return v
def validate_case(c:Mapping)->None:
    if not isinstance(c,Mapping): raise ValueError("benchmark case must be an object")
    missing,extra=REQUIRED-set(c),set(c)-REQUIRED
    if missing: raise ValueError(f"missing fields: {', '.join(sorted(missing))}")
    if extra: raise ValueError(f"unknown fields: {', '.join(sorted(extra))}")
    for f in ("case_id","target_claim","independence_group","gold_rationale","split_group"):
        if not isinstance(c[f],str) or not c[f].strip(): raise ValueError(f"{f} must be non-empty")
    _strings(c["source_lineage"],"source_lineage"); _strings(c["relation_families"],"relation_families")
    if not set(c["relation_families"])<=RELATIONS: raise ValueError("unknown relation family")
    for f in ("shared_basis","non_shared_basis","scope_conditions","required_invariants","known_counterexamples"): _strings(c[f],f,False)
    _strings(c["evidence_refs"],"evidence_refs"); _strings(c["reviewers"],"reviewers")
    if len(c["reviewers"]) < 2: raise ValueError("gold labels require at least two independent reviewers")
    if c["source_status"] not in SOURCE_STATUS: raise ValueError("unknown source_status")
    if c["causal_status"] not in CAUSAL: raise ValueError("unknown causal_status")
    if c["gold_decision"] not in DECISIONS: raise ValueError("unknown gold_decision")
    if c["gold_decision"]=="conditional" and not c["scope_conditions"]: raise ValueError("conditional decision requires explicit scope_conditions")
    if c["gold_decision"]=="abstain" and len(c["gold_rationale"].strip())<20: raise ValueError("abstain rationale must explain unresolved uncertainty")
    if c["source_status"]=="synthetic_fixture" and not any(x.startswith("fixture:") for x in c["evidence_refs"]): raise ValueError("synthetic fixtures require fixture: evidence refs")
def validate_dataset(cases:Sequence[Mapping])->None:
    if not isinstance(cases,Sequence) or isinstance(cases,(str,bytes)) or not cases: raise ValueError("benchmark dataset must be a non-empty sequence")
    ids=set()
    for c in cases:
        validate_case(c)
        if c["case_id"] in ids: raise ValueError("case_id values must be globally unique")
        ids.add(c["case_id"])
def validate_prediction(p:Mapping)->None:
    if not isinstance(p,Mapping) or set(p)!={"case_id","decision"}: raise ValueError("prediction requires exactly case_id and decision")
    if not isinstance(p["case_id"],str) or not p["case_id"].strip(): raise ValueError("prediction case_id must be non-empty")
    if p["decision"] not in DECISIONS: raise ValueError("unknown prediction decision")
def evaluate_predictions(cases:Sequence[Mapping],predictions:Sequence[Mapping])->dict:
    """Score submitted labels against gold; absent outputs count as abstain."""
    validate_dataset(cases); pred={}
    for p in predictions:
        validate_prediction(p)
        if p["case_id"] in pred: raise ValueError("duplicate prediction case_id")
        pred[p["case_id"]]=p["decision"]
    known={c["case_id"] for c in cases}
    if set(pred)-known: raise ValueError("prediction references unknown case_id")
    labels=sorted(DECISIONS); matrix={g:{p:0 for p in labels} for g in labels}; correct=0
    for c in cases:
        g=c["gold_decision"]; p=pred.get(c["case_id"],"abstain"); matrix[g][p]+=1; correct+=g==p
    metrics={}
    for label in labels:
        tp=matrix[label][label]; fp=sum(matrix[g][label] for g in labels if g!=label); fn=sum(matrix[label][p] for p in labels if p!=label)
        precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/(tp+fn) if tp+fn else 0.0
        f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
        metrics[label]={"precision":precision,"recall":recall,"f1":f1,"support":sum(matrix[label].values())}
    n=len(cases)
    def stratify(field, values):
        result={}
        for value in sorted(values):
            subset=[c for c in cases if value in (c[field] if field=="relation_families" else [c[field]])]
            if subset:
                hit=sum(pred.get(c["case_id"],"abstain")==c["gold_decision"] for c in subset)
                result[value]={"n":len(subset),"accuracy":hit/len(subset)}
        return result
    return {"n":n,"accuracy":correct/n,"macro_f1":sum(x["f1"] for x in metrics.values())/len(labels),
            "per_class":metrics,"confusion_matrix":matrix,
            "missing_predictions":sum(c["case_id"] not in pred for c in cases),
            "by_relation_family":stratify("relation_families",set(v for c in cases for v in c["relation_families"])),
            "by_source_status":stratify("source_status",set(c["source_status"] for c in cases))}
def group_leakage(cases:Sequence[Mapping],*,group_field="source_lineage")->dict:
    """Report source groups spanning splits; never silently repair leakage."""
    if group_field not in {"source_lineage","independence_group","split_group"}: raise ValueError("unsupported grouping field")
    validate_dataset(cases); memberships=defaultdict(set)
    for c in cases:
        values=c[group_field] if group_field=="source_lineage" else [c[group_field]]
        for value in values: memberships[value].add(c["split_group"])
    leaks=sorted(k for k,v in memberships.items() if len(v)>1)
    return {"group_field":group_field,"leakage_groups":leaks,"leakage_count":len(leaks),"group_count":len(memberships)}
