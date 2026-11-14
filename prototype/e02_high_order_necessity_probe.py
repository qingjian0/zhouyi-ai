"""Exhaustive parity probe: prove a third-order term is necessary here.

This is a representational-capacity test, not a learned accuracy claim.
"""
from __future__ import annotations
from itertools import product
from prototype.n09_learnable_srok import LearnableSROK, Node, RoleSpec


def run_parity_probe() -> dict:
    roles=tuple(RoleSpec(f"r{i}") for i in range(3))
    model=LearnableSROK(roles,feature_dim=1)
    rows=[]
    for bits in product((-1.0,1.0),repeat=3):
        assignment=tuple(Node(f"r{i}:{int(bit)}",f"r{i}",(bit,)) for i,bit in enumerate(bits))
        features=model._assignment_features(assignment)
        target=1 if bits[0]*bits[1]*bits[2]>0 else -1
        rows.append((features,target))
    # Exhaustive bounded coefficient search for the additive + pairwise
    # baseline. The first six features are unary and pairwise; no bias.
    best=0
    for weights in product(range(-2,3),repeat=6):
        correct=0
        for features,target in rows:
            score=sum(w*x for w,x in zip(weights,features[:6]))
            prediction=1 if score>0 else -1 if score<0 else 0
            correct += prediction==target
        best=max(best,correct)
    # The model's seventh feature is the elementwise third-order product.
    third_correct=sum(
        (1 if features[6]>0 else -1 if features[6]<0 else 0)==target
        for features,target in rows
    )
    return {
        "task":"three-variable parity over all 8 assignments",
        "examples":len(rows),
        "pairwise_coefficient_domain":[-2,2],
        "pairwise_hypotheses_checked":5**6,
        "pairwise_best_correct":best,
        "pairwise_best_accuracy":best/len(rows),
        "third_order_correct":third_correct,
        "third_order_accuracy":third_correct/len(rows),
        "interpretation":"third-order interaction is representationally necessary for this parity task; this does not prove general high-order superiority or learned convergence",
    }


if __name__=="__main__":
    import json
    print(json.dumps(run_parity_probe(),ensure_ascii=False,indent=2))
