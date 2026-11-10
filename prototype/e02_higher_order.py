"""E02-A controlled third-order synergy benchmark (dependency-free).

Candidates are role-ordered triples in {-1,+1}. The target is their parity
product. Balanced first/second-order marginals prevent pairwise shortcuts.
This is a diagnostic toy task, not a natural-language reasoning benchmark.
"""
from __future__ import annotations
import argparse, json, math, random
from dataclasses import dataclass
from typing import Iterable

PATTERNS = [(a,b,c) for a in (-1,1) for b in (-1,1) for c in (-1,1)]

@dataclass(frozen=True)
class Example:
    candidates: tuple[tuple[int,int,int], ...]
    target: int

def make_dataset(n: int, seed: int) -> list[Example]:
    rng=random.Random(seed)
    pos=[p for p in PATTERNS if p[0]*p[1]*p[2]==1]
    neg=[p for p in PATTERNS if p[0]*p[1]*p[2]==-1]
    out=[]
    for _ in range(n):
        p=rng.choice(pos); candidates=[p,*rng.sample(neg,3)]; rng.shuffle(candidates)
        out.append(Example(tuple(candidates),candidates.index(p)))
    return out

def features(x: tuple[int,int,int], order: int) -> list[float]:
    a,b,c=x
    f=[1.,float(a),float(b),float(c),float(a*b),float(a*c),float(b*c)]
    if order>=3: f.append(float(a*b*c))
    return f

def fit(examples: Iterable[Example], order: int, epochs: int=250,
        lr: float=.12, l2: float=.002) -> list[float]:
    rows=[(features(x,order),1. if i==ex.target else 0.)
          for ex in examples for i,x in enumerate(ex.candidates)]
    if not rows: raise ValueError("training data must not be empty")
    w=[0.] * len(rows[0][0])
    for _ in range(epochs):
        g=[0.] * len(w)
        for x,y in rows:
            z=max(-30.,min(30.,sum(a*b for a,b in zip(w,x))))
            p=1./(1.+math.exp(-z)); err=p-y
            for j,v in enumerate(x): g[j]+=err*v
        scale=1./len(rows)
        for j in range(len(w)):
            w[j]-=lr*(g[j]*scale+(0. if j==0 else l2*w[j]))
    return w

def predict(ex: Example, weights: list[float], order: int) -> int:
    scores=[sum(a*b for a,b in zip(weights,features(x,order))) for x in ex.candidates]
    return max(range(len(scores)),key=lambda i:(scores[i],-i))

def accuracy(data: list[Example], weights: list[float], order: int) -> float:
    if not data: raise ValueError("dataset must not be empty")
    return sum(predict(ex,weights,order)==ex.target for ex in data)/len(data)

def run_seed(seed: int, train_n: int=1200, val_n: int=300, test_n: int=500) -> dict:
    train=make_dataset(train_n,seed*10+1)
    val=make_dataset(val_n,seed*10+2)
    test=make_dataset(test_n,seed*10+3)
    pair=fit(train,2); static=fit(train,3)
    pv=accuracy(val,pair,2); sv=accuracy(val,static,3)
    create=sv>pv+.01
    chosen,order=(static,3) if create else (pair,2)
    return {"seed":seed,"pairwise_test_accuracy":accuracy(test,pair,2),
            "static_order3_test_accuracy":accuracy(test,static,3),
            "dynamic_test_accuracy":accuracy(test,chosen,order),
            "dynamic_created_order3":create,
            "validation_pairwise_accuracy":pv,"validation_static_order3_accuracy":sv}

def run(seeds: int=5,start_seed: int=7) -> dict:
    if seeds<1: raise ValueError("seeds must be >= 1")
    results=[run_seed(start_seed+i) for i in range(seeds)]
    summary={}
    for key in ("pairwise_test_accuracy","static_order3_test_accuracy","dynamic_test_accuracy"):
        vals=[r[key] for r in results]; mean=sum(vals)/len(vals)
        var=sum((x-mean)**2 for x in vals)/max(1,len(vals)-1)
        summary[key]={"mean":mean,"sample_std":math.sqrt(var)}
    summary["dynamic_create_rate"]=sum(r["dynamic_created_order3"] for r in results)/len(results)
    return {"task":"third_order_parity_hard_negative","seeds":results,"summary":summary,
            "caveat":"Synthetic parity diagnostic only; not a natural-language or general-intelligence result."}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--seeds",type=int,default=5)
    p.add_argument("--start-seed",type=int,default=7); p.add_argument("--json",action="store_true")
    a=p.parse_args(); result=run(a.seeds,a.start_seed)
    print(json.dumps(result,indent=2) if a.json else result)

if __name__=="__main__": main()
