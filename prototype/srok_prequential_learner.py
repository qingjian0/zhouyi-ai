"""SROK learnable scorer wrapped in the existing E09 prequential protocol."""
from __future__ import annotations
import json, math
from typing import Iterable, Sequence
from prototype.cpg_interop import canonical_json
from prototype.e09_counterexample_learner import Example
from prototype.n09_learnable_srok import LearnableSROK, LearnableSROKError, Node, RoleSpec, TrainingExample

OBSERVATION_SCHEMA = "srok-observation-v1"

def encode_srok_observation(nodes: Sequence[Node]) -> str:
    if not nodes:
        raise ValueError("an SROK observation requires nodes")
    ids=[n.node_id for n in nodes]
    if len(ids)!=len(set(ids)):
        raise ValueError("node IDs must be unique")
    return canonical_json({"schema_version":OBSERVATION_SCHEMA,"nodes":[
        {"node_id":n.node_id,"node_type":n.node_type,"features":list(n.features),
         "tags":sorted(n.tags),"evidence_ids":list(n.evidence_ids)} for n in nodes]})

class SROKPrequentialLearner:
    """Implements fit/predict/snapshot/report for PrequentialRunner BATCH_REFIT."""
    def __init__(self, roles: Sequence[RoleSpec], feature_dim: int, *,
                 epochs: int=80, learning_rate: float=0.2, l2: float=1e-4,
                 max_assignments_per_example: int=4096, top_k_per_role: int=8,
                 max_expansions: int=4096, result_limit: int=5,
                 abstain_margin: float=0.0):
        self.roles=tuple(roles); self.feature_dim=feature_dim
        self.epochs=epochs; self.learning_rate=learning_rate; self.l2=l2
        self.max_assignments_per_example=max_assignments_per_example
        self.top_k_per_role=top_k_per_role; self.max_expansions=max_expansions
        self.result_limit=result_limit; self.abstain_margin=abstain_margin
        self.model=LearnableSROK(self.roles,feature_dim)
        self.report={"fitted":False,"training_examples":0,"candidate_patterns_evaluated":0}
        self.last_inference={"status":"NOT_RUN"}
        self._cumulative_evaluations=0

    @staticmethod
    def _decode(inputs: Sequence[object]) -> tuple[Node,...]:
        if not isinstance(inputs,(tuple,list)) or len(inputs)!=1 or not isinstance(inputs[0],str):
            raise LearnableSROKError("input must contain one canonical SROK observation")
        try: payload=json.loads(inputs[0])
        except (TypeError,json.JSONDecodeError) as exc: raise LearnableSROKError("invalid observation JSON") from exc
        if canonical_json(payload)!=inputs[0] or payload.get("schema_version")!=OBSERVATION_SCHEMA:
            raise LearnableSROKError("unsupported or non-canonical SROK observation")
        if not isinstance(payload.get("nodes"),list): raise LearnableSROKError("nodes must be a list")
        nodes=[]
        for item in payload["nodes"]:
            try:
                nodes.append(Node(item["node_id"],item["node_type"],tuple(item["features"]),
                                  frozenset(item.get("tags",[])),tuple(item.get("evidence_ids",[]))))
            except (KeyError,TypeError) as exc: raise LearnableSROKError("malformed node") from exc
        if not nodes or len({n.node_id for n in nodes})!=len(nodes):
            raise LearnableSROKError("observation requires unique nodes")
        return tuple(nodes)

    @staticmethod
    def _compatible(node: Node, role: RoleSpec) -> bool:
        return ((not role.allowed_types or node.node_type in role.allowed_types)
                and role.required_tags.issubset(node.tags))

    def fit(self, examples: Iterable[Example]):
        rows=tuple(examples)
        if not rows: raise LearnableSROKError("no uncontested SUPPORT examples")
        prepared=[]; work=0
        for row in rows:
            if not isinstance(row.label,tuple) or any(not isinstance(x,str) or not x for x in row.label):
                raise LearnableSROKError("target label must be ordered node ID tuple")
            nodes=self._decode(row.inputs)
            pools=tuple(tuple(n for n in nodes if self._compatible(n,role)) for role in self.roles)
            if any(not pool for pool in pools): raise LearnableSROKError("empty role pool in training observation")
            work += math.prod(len(pool) for pool in pools)
            prepared.append(TrainingExample(pools,row.label))
        model=LearnableSROK(self.roles,self.feature_dim)
        history=model.fit(prepared,epochs=self.epochs,learning_rate=self.learning_rate,l2=self.l2,
                          max_assignments_per_example=self.max_assignments_per_example)
        self.model=model
        fit_work=work*self.epochs
        self._cumulative_evaluations += fit_work
        self.report={"fitted":True,"training_examples":len(rows),
                     "candidate_patterns_evaluated":self._cumulative_evaluations,
                     "last_fit_candidate_patterns":fit_work,"initial_loss":history[0],
                     "final_loss":history[-1],"training_steps":model.training_steps}
        return self

    def predict(self, inputs: Sequence[object]):
        if not self.report.get("fitted"): raise LearnableSROKError("model not fitted")
        nodes=self._decode(inputs)
        pools=tuple(tuple(n for n in nodes if self._compatible(n,r)) for r in self.roles)
        sizes=tuple((r.name,len(p)) for r,p in zip(self.roles,pools))
        truncated=tuple(r.name for r,p in zip(self.roles,pools) if len(p)>self.top_k_per_role)
        if truncated:
            self.last_inference={"status":"ROLE_POOL_TRUNCATED","truncated_roles":truncated,"role_pool_sizes":sizes}
            return None
        pred=self.model.predict(nodes,top_k_per_role=self.top_k_per_role,max_expansions=self.max_expansions,
                                result_limit=self.result_limit,abstain_margin=self.abstain_margin)
        if pred.budget_exhausted:
            self.last_inference={"status":"BUDGET_EXHAUSTED","expanded_assignments":pred.expanded_assignments,"role_pool_sizes":sizes}
            return None
        if pred.abstained or not pred.candidates:
            self.last_inference={"status":pred.reason,"expanded_assignments":pred.expanded_assignments,"role_pool_sizes":sizes}
            return None
        chosen=pred.candidates[0]
        self.last_inference={"status":"RANKED","expanded_assignments":pred.expanded_assignments,
                             "role_pool_sizes":sizes,"raw_score":chosen.score,
                             "score_semantics":"uncalibrated_ranking_score"}
        return tuple(node_id for _,node_id in chosen.role_bindings)

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "SROKPrequentialLearner":
        """Restore a validated learner checkpoint; caller owns event/ledger replay."""
        if not isinstance(snapshot, dict) or snapshot.get("learner_type") != "srok_learnable_role_binding":
            raise LearnableSROKError("unsupported SROK learner snapshot")
        try:
            roles = tuple(RoleSpec(
                item["name"], frozenset(item.get("allowed_types", [])),
                frozenset(item.get("required_tags", [])),
            ) for item in snapshot["roles"])
            learner = cls(
                roles, snapshot["feature_dim"],
                epochs=snapshot.get("epochs", 80),
                learning_rate=snapshot.get("learning_rate", 0.2),
                l2=snapshot.get("l2", 1e-4),
                max_assignments_per_example=snapshot.get("max_assignments_per_example", 4096),
                top_k_per_role=snapshot.get("top_k_per_role", 8),
                max_expansions=snapshot.get("max_expansions", 4096),
                result_limit=snapshot.get("result_limit", 5),
                abstain_margin=snapshot.get("abstain_margin", 0.0),
            )
            weights = snapshot["weights"]
            steps = snapshot["training_steps"]
            report = snapshot["report"]
            last = snapshot.get("last_inference", {"status": "NOT_RUN"})
            if not isinstance(weights, list) or len(weights) != len(learner.model.weights):
                raise LearnableSROKError("snapshot weight dimension mismatch")
            if any(not isinstance(w, (int, float)) or isinstance(w, bool) or not math.isfinite(w) for w in weights):
                raise LearnableSROKError("snapshot contains non-finite weights")
            if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
                raise LearnableSROKError("invalid snapshot training step")
            if not isinstance(report, dict) or not isinstance(last, dict):
                raise LearnableSROKError("invalid snapshot report")
            learner.model.weights = [float(w) for w in weights]
            learner.model.training_steps = steps
            learner.report = dict(report)
            learner.last_inference = dict(last)
            learner._cumulative_evaluations = int(report.get("candidate_patterns_evaluated", 0))
            if learner._cumulative_evaluations < 0:
                raise LearnableSROKError("invalid cumulative evaluation count")
            return learner
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, LearnableSROKError):
                raise
            raise LearnableSROKError("malformed SROK learner snapshot") from exc

    def snapshot(self) -> dict:
        return {"learner_type":"srok_learnable_role_binding",
                "roles":[{"name":r.name,"allowed_types":sorted(r.allowed_types),
                          "required_tags":sorted(r.required_tags)} for r in self.roles],
                "feature_dim":self.feature_dim,"weights":list(self.model.weights),
                "training_steps":self.model.training_steps,"report":dict(self.report),
                "last_inference":dict(self.last_inference),
                "epochs":self.epochs,"learning_rate":self.learning_rate,"l2":self.l2,
                "max_assignments_per_example":self.max_assignments_per_example,
                "top_k_per_role":self.top_k_per_role,"max_expansions":self.max_expansions,
                "result_limit":self.result_limit,"abstain_margin":self.abstain_margin}
