"""Experimental learnable Xiang basis for N0.10 role-bound relation scoring.

This module is intentionally separate from LearnableSROK until controlled
baselines demonstrate transfer gains. It consumes observable node features
only; rule-family metadata and target IDs are never model inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import random
from typing import Iterable, Sequence

from prototype.n09_learnable_srok import (
    LearnableSROKError, Node, RoleSpec, RelationClassificationExample,
)


@dataclass(frozen=True)
class XiangConfig:
    latent_dim: int
    basis_mode: str = "learnable"  # learnable | fixed_random
    seed: int = 0


class LearnableXiangOperator:
    """Shared latent Xiang basis with role unary/pair/triple composition.

    z(x)=tanh(Wx+b); score is a linear readout over role-conditioned
    z, z_i*z_j and z_i*z_j*z_k blocks. Training uses deterministic
    full-batch binary cross-entropy and analytic gradients.
    """

    FORMAT = "zhouyi-ai.n010.learnable-xiang"
    VERSION = 1

    def __init__(self, roles: Sequence[RoleSpec], feature_dim: int,
                 config: XiangConfig) -> None:
        self.roles = tuple(roles)
        self.feature_dim = feature_dim
        self.config = config
        if len(self.roles) < 2 or len({r.name for r in self.roles}) != len(self.roles):
            raise LearnableSROKError("Xiang operator requires at least two uniquely named roles")
        if isinstance(feature_dim, bool) or not isinstance(feature_dim, int) or feature_dim < 1:
            raise LearnableSROKError("feature_dim must be positive")
        if not isinstance(config, XiangConfig):
            raise LearnableSROKError("config must be XiangConfig")
        if isinstance(config.latent_dim, bool) or not isinstance(config.latent_dim, int) or config.latent_dim < 1:
            raise LearnableSROKError("latent_dim must be positive")
        if config.basis_mode not in ("learnable", "fixed_random"):
            raise LearnableSROKError("basis_mode must be learnable or fixed_random")
        if isinstance(config.seed, bool) or not isinstance(config.seed, int) or config.seed < 0:
            raise LearnableSROKError("seed must be a non-negative integer")
        self.pairs = tuple((i, j) for i in range(len(self.roles)) for j in range(i + 1, len(self.roles)))
        self.triples = tuple((i, j, k) for i in range(len(self.roles))
                             for j in range(i + 1, len(self.roles))
                             for k in range(j + 1, len(self.roles)))
        rng = random.Random(config.seed)
        scale = 1.0 / math.sqrt(feature_dim)
        self.basis = [[rng.uniform(-scale, scale) for _ in range(feature_dim)]
                      for _ in range(config.latent_dim)]
        self.bias = [0.0] * config.latent_dim
        width = config.latent_dim * (len(self.roles) + len(self.pairs) + len(self.triples))
        self.readout = [0.0] * width
        self.training_steps = 0

    def _validate_assignment(self, assignment: Sequence[Node]) -> None:
        if len(assignment) != len(self.roles):
            raise LearnableSROKError("assignment role count mismatch")
        ids = set()
        for node, role in zip(assignment, self.roles):
            if not isinstance(node, Node):
                raise LearnableSROKError("assignment members must be Nodes")
            if node.node_id in ids:
                raise LearnableSROKError("assignment members must be distinct")
            ids.add(node.node_id)
            if len(node.features) != self.feature_dim:
                raise LearnableSROKError("node feature dimension mismatch")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in node.features):
                raise LearnableSROKError("node features must be finite")
            if role.allowed_types and node.node_type not in role.allowed_types:
                raise LearnableSROKError("assignment violates role type constraint")
            if not role.required_tags.issubset(node.tags):
                raise LearnableSROKError("assignment violates role tag constraint")

    def _embed(self, node: Node) -> list[float]:
        return [math.tanh(math.fsum(w * x for w, x in zip(row, node.features)) + bias)
                for row, bias in zip(self.basis, self.bias)]

    def _features_and_embeddings(self, assignment: Sequence[Node]):
        self._validate_assignment(assignment)
        z = [self._embed(node) for node in assignment]
        out = []
        for i in range(len(z)):
            out.extend(z[i])
        for i, j in self.pairs:
            out.extend(a * b for a, b in zip(z[i], z[j]))
        for i, j, k in self.triples:
            out.extend(a * b * c for a, b, c in zip(z[i], z[j], z[k]))
        return out, z

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            e = math.exp(-min(value, 60.0))
            return 1.0 / (1.0 + e)
        e = math.exp(max(value, -60.0))
        return e / (1.0 + e)

    def score(self, assignment: Sequence[Node]) -> float:
        features, _ = self._features_and_embeddings(assignment)
        return math.fsum(w * x for w, x in zip(self.readout, features))

    def predict_probability(self, assignment: Sequence[Node]) -> float:
        return self._sigmoid(self.score(assignment))

    def fit(self, examples: Iterable[RelationClassificationExample], *,
            epochs: int = 100, learning_rate: float = 0.03,
            l2: float = 1e-4) -> list[float]:
        """Train readout and (when enabled) shared basis by exact full-batch gradients."""
        rows = tuple(examples)
        if not rows:
            raise LearnableSROKError("relation examples must not be empty")
        if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
            raise LearnableSROKError("epochs must be positive")
        if isinstance(learning_rate, bool) or not isinstance(learning_rate, (int, float)) or not math.isfinite(learning_rate) or learning_rate <= 0:
            raise LearnableSROKError("learning_rate must be finite and positive")
        if isinstance(l2, bool) or not isinstance(l2, (int, float)) or not math.isfinite(l2) or l2 < 0:
            raise LearnableSROKError("l2 must be finite and non-negative")
        prepared = []
        for row in rows:
            if not isinstance(row, RelationClassificationExample) or type(row.label) is not int or row.label not in (-1, 1):
                raise LearnableSROKError("invalid relation classification row")
            features, embeddings = self._features_and_embeddings(row.assignment)
            prepared.append((row.assignment, features, embeddings, 1.0 if row.label == 1 else 0.0))

        n, width, latent = len(prepared), len(self.readout), self.config.latent_dim
        history = []
        for _ in range(epochs):
            grad_readout = [0.0] * width
            grad_basis = [[0.0] * self.feature_dim for _ in range(latent)]
            grad_bias = [0.0] * latent
            loss = 0.0
            # All gradients use the same pre-update parameter snapshot.
            for assignment, features, z, target in prepared:
                logit = math.fsum(w * x for w, x in zip(self.readout, features))
                probability = self._sigmoid(logit)
                clipped = min(max(probability, 1e-15), 1.0 - 1e-15)
                loss -= target * math.log(clipped) + (1.0 - target) * math.log(1.0 - clipped)
                error = probability - target
                for q, value in enumerate(features):
                    grad_readout[q] += error * value

                grad_z = [[0.0] * latent for _ in self.roles]
                cursor = 0
                for role_index in range(len(self.roles)):
                    for q in range(latent):
                        grad_z[role_index][q] += error * self.readout[cursor + q]
                    cursor += latent
                for i, j in self.pairs:
                    for q in range(latent):
                        w = error * self.readout[cursor + q]
                        grad_z[i][q] += w * z[j][q]
                        grad_z[j][q] += w * z[i][q]
                    cursor += latent
                for i, j, k in self.triples:
                    for q in range(latent):
                        w = error * self.readout[cursor + q]
                        grad_z[i][q] += w * z[j][q] * z[k][q]
                        grad_z[j][q] += w * z[i][q] * z[k][q]
                        grad_z[k][q] += w * z[i][q] * z[j][q]
                    cursor += latent

                if self.config.basis_mode == "learnable":
                    for role_index, node in enumerate(assignment):
                        for q in range(latent):
                            delta = grad_z[role_index][q] * (1.0 - z[role_index][q] ** 2)
                            grad_bias[q] += delta
                            for f_index, value in enumerate(node.features):
                                grad_basis[q][f_index] += delta * value

            for q in range(width):
                gradient = grad_readout[q] / n + l2 * self.readout[q]
                if not math.isfinite(gradient):
                    raise LearnableSROKError("non-finite Xiang readout gradient")
                self.readout[q] -= learning_rate * gradient
            if self.config.basis_mode == "learnable":
                for q in range(latent):
                    for f_index in range(self.feature_dim):
                        gradient = grad_basis[q][f_index] / n + l2 * self.basis[q][f_index]
                        if not math.isfinite(gradient):
                            raise LearnableSROKError("non-finite Xiang basis gradient")
                        self.basis[q][f_index] -= learning_rate * gradient
                    self.bias[q] -= learning_rate * grad_bias[q] / n
            if any(not math.isfinite(v) for row in self.basis for v in row) or any(not math.isfinite(v) for v in self.bias + self.readout):
                raise LearnableSROKError("Xiang parameters became non-finite")
            history.append(loss / n)
            self.training_steps += 1
        return history

    def checkpoint_json(self) -> str:
        payload = {
            "format": self.FORMAT, "schema_version": self.VERSION,
            "feature_dim": self.feature_dim,
            "roles": [{"name": r.name, "allowed_types": sorted(r.allowed_types),
                       "required_tags": sorted(r.required_tags)} for r in self.roles],
            "config": {"latent_dim": self.config.latent_dim,
                       "basis_mode": self.config.basis_mode, "seed": self.config.seed},
            "basis": self.basis, "bias": self.bias, "readout": self.readout,
            "training_steps": self.training_steps,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
        envelope = dict(payload)
        envelope["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return json.dumps(envelope, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    @classmethod
    def from_checkpoint_json(cls, raw: str) -> "LearnableXiangOperator":
        try:
            env = json.loads(raw)
            digest = env.pop("sha256")
            canonical = json.dumps(env, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, KeyError) as exc:
            raise LearnableSROKError("invalid Xiang checkpoint") from exc
        if digest != hashlib.sha256(canonical.encode("utf-8")).hexdigest():
            raise LearnableSROKError("Xiang checkpoint digest mismatch")
        if set(env) != {"format", "schema_version", "feature_dim", "roles", "config",
                        "basis", "bias", "readout", "training_steps"}:
            raise LearnableSROKError("Xiang checkpoint fields mismatch")
        if env["format"] != cls.FORMAT or env["schema_version"] != cls.VERSION:
            raise LearnableSROKError("unsupported Xiang checkpoint")
        roles = tuple(RoleSpec(x["name"], frozenset(x["allowed_types"]),
                               frozenset(x["required_tags"])) for x in env["roles"])
        config = XiangConfig(**env["config"])
        model = cls(roles, env["feature_dim"], config)
        for name in ("basis", "bias", "readout"):
            values = env[name]
            flat = [v for row in values for v in row] if name == "basis" else values
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in flat):
                raise LearnableSROKError("Xiang checkpoint contains non-finite parameters")
        if len(env["basis"]) != config.latent_dim or any(len(row) != model.feature_dim for row in env["basis"]):
            raise LearnableSROKError("Xiang basis shape mismatch")
        if len(env["bias"]) != config.latent_dim or len(env["readout"]) != len(model.readout):
            raise LearnableSROKError("Xiang parameter shape mismatch")
        model.basis = [[float(v) for v in row] for row in env["basis"]]
        model.bias = [float(v) for v in env["bias"]]
        model.readout = [float(v) for v in env["readout"]]
        if isinstance(env["training_steps"], bool) or not isinstance(env["training_steps"], int) or env["training_steps"] < 0:
            raise LearnableSROKError("invalid Xiang training_steps")
        model.training_steps = env["training_steps"]
        return model
