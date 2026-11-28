"""ZhouyiAI Omega: first trainable hybrid foundation-model prototype.

This research MVP combines causal language processing, recurrent state updates,
a learned classiang relational workspace, and a pairwise CPG-EI composition
proposal head. It is independently initialized and trained; it does not load
another model's weights. It is not a claim of general intelligence or
Transformer replacement.

Install the optional dependency with: pip install -e .[model]
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

try:
    import torch
    from torch import Tensor, nn
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "ZhouyiAI Omega requires PyTorch. Install the optional model dependency."
    ) from exc


@dataclass(frozen=True)
class OmegaConfig:
    vocab_size: int
    d_model: int = 128
    n_heads: int = 4
    n_layers: int = 2
    num_classiang_slots: int = 16
    max_seq_len: int = 512
    dropout: float = 0.1
    branch_mode: str = "hybrid"

    def __post_init__(self) -> None:
        if self.vocab_size < 2:
            raise ValueError("vocab_size must be >= 2")
        if self.n_heads < 1 or self.d_model < 8 or self.d_model % self.n_heads:
            raise ValueError("d_model must be >= 8 and divisible by positive n_heads")
        if self.n_layers < 1 or self.num_classiang_slots < 2 or self.max_seq_len < 2:
            raise ValueError("n_layers, slots and max_seq_len must be positive (slots >= 2)")
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("dropout must be in [0, 1)")
        if self.branch_mode not in {"hybrid", "attention_only", "recurrent_only", "classiang_only"}:
            raise ValueError("unsupported branch_mode")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CPGEIComposer(nn.Module):
    """Bounded pairwise composition proposal scorer over learned classiang slots.

    This is an initial trainable composition head, not the full CPG-EI search
    algorithm. Higher-order and non-adjacent composition policies remain
    separately testable extensions.
    """

    def __init__(self, d_model: int) -> None:
        super().__init__()
        self.score = nn.Sequential(
            nn.Linear(2 * d_model, d_model),
            nn.GELU(),
            nn.Linear(d_model, 1),
        )

    def forward(self, slots: Tensor) -> Tensor:
        # Supports [B,S,D] and context-conditioned [B,T,S,D] slot tensors.
        count = slots.shape[-2]
        left = slots.unsqueeze(-2).expand(*slots.shape[:-2], count, count, slots.shape[-1])
        right = slots.unsqueeze(-3).expand(*slots.shape[:-2], count, count, slots.shape[-1])
        pair_features = torch.cat((left + right, left * right), dim=-1)
        return self.score(pair_features).squeeze(-1)


class ClassiangWorkspace(nn.Module):
    """Per-position latent-aspect assignment plus learned slot relations."""

    def __init__(self, config: OmegaConfig) -> None:
        super().__init__()
        self.config = config
        d_model = config.d_model
        self.slots = nn.Parameter(torch.randn(config.num_classiang_slots, d_model) * 0.02)
        self.assignment = nn.Linear(d_model, d_model, bias=False)
        self.context_to_slots = nn.Linear(d_model, d_model, bias=False)
        self.relation_q = nn.Linear(d_model, d_model, bias=False)
        self.relation_k = nn.Linear(d_model, d_model, bias=False)
        self.relation_v = nn.Linear(d_model, d_model, bias=False)
        self.relation_out = nn.Linear(d_model, d_model)
        self.output = nn.Linear(d_model, d_model)
        self.norm = nn.LayerNorm(d_model)
        self.composer = CPGEIComposer(d_model)
        self.scale = d_model ** -0.5

    def forward(self, causal_tokens: Tensor) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        # Each time position gets its own context-conditioned relation graph.
        # Since causal_tokens comes from a forward-only GRU, no future token leaks in.
        batch, seq_len, _ = causal_tokens.shape
        slots = self.slots.view(1, 1, self.slots.shape[0], self.slots.shape[1])
        slots = slots + self.context_to_slots(causal_tokens).unsqueeze(-2)
        q = self.relation_q(slots)
        k = self.relation_k(slots)
        v = self.relation_v(slots)
        relation_logits = torch.matmul(q, k.transpose(-1, -2)) * self.scale
        relation_weights = torch.softmax(relation_logits, dim=-1)
        related_slots = slots + self.relation_out(torch.matmul(relation_weights, v))

        token_queries = self.assignment(causal_tokens)
        assignment_logits = torch.einsum("btd,btsd->bts", token_queries, related_slots) * self.scale
        assignments = torch.softmax(assignment_logits, dim=-1)
        context = torch.einsum("bts,btsd->btd", assignments, related_slots)
        composition_logits = self.composer(related_slots)
        return self.norm(causal_tokens + self.output(context)), assignments, relation_logits, composition_logits


class OmegaBlock(nn.Module):
    """Hybrid block: causal attention, recurrent state, and classiang relations."""

    def __init__(self, config: OmegaConfig) -> None:
        super().__init__()
        d_model = config.d_model
        self.attention = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=config.n_heads,
            dim_feedforward=4 * d_model,
            dropout=config.dropout,
            batch_first=True,
            norm_first=True,
            activation="gelu",
        )
        self.recurrent = nn.GRU(d_model, d_model, batch_first=True)
        self.classiang = ClassiangWorkspace(config)
        self.mix = nn.Sequential(
            nn.Linear(3 * d_model, d_model),
            nn.GELU(),
            nn.Linear(d_model, 3),
        )
        self.output_norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        mode = self.config.branch_mode
        batch, seq_len, width = x.shape
        empty_rel = x.new_zeros((batch, seq_len, self.config.num_classiang_slots,
                                 self.config.num_classiang_slots))
        if mode == "attention_only":
            causal_mask = torch.triu(
                torch.ones(seq_len, seq_len, dtype=torch.bool, device=x.device), diagonal=1
            )
            attended = self.attention(x, src_mask=causal_mask)
            return self.output_norm(x + self.dropout(attended)), empty_rel, empty_rel
        if mode == "recurrent_only":
            recurrent, _ = self.recurrent(x)
            return self.output_norm(x + self.dropout(recurrent)), empty_rel, empty_rel
        if mode == "classiang_only":
            recurrent, _ = self.recurrent(x)
            classiang, _assignments, relation_logits, composition_logits = self.classiang(recurrent)
            return self.output_norm(x + self.dropout(classiang)), relation_logits, composition_logits

        causal_mask = torch.triu(
            torch.ones(seq_len, seq_len, dtype=torch.bool, device=x.device), diagonal=1
        )
        attended = self.attention(x, src_mask=causal_mask)
        recurrent, _ = self.recurrent(x)
        classiang, _assignments, relation_logits, composition_logits = self.classiang(recurrent)
        gates = torch.softmax(
            self.mix(torch.cat((attended, recurrent, classiang), dim=-1)), dim=-1
        )
        branches = torch.stack((attended, recurrent, classiang), dim=-2)
        mixed = torch.sum(branches * gates.unsqueeze(-1), dim=-2)
        return self.output_norm(x + self.dropout(mixed)), relation_logits, composition_logits


class OmegaModel(nn.Module):
    """An independently initialized hybrid language/类象 model."""

    def __init__(self, config: OmegaConfig) -> None:
        super().__init__()
        self.config = config
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.position_embedding = nn.Embedding(config.max_seq_len, config.d_model)
        self.blocks = nn.ModuleList([OmegaBlock(config) for _ in range(config.n_layers)])
        self.final_norm = nn.LayerNorm(config.d_model)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
        self.lm_head.weight = self.token_embedding.weight

    def forward(self, input_ids: Tensor) -> dict[str, Tensor]:
        if input_ids.ndim != 2:
            raise ValueError("input_ids must have shape [batch, sequence]")
        _, seq_len = input_ids.shape
        if seq_len > self.config.max_seq_len:
            raise ValueError(
                f"sequence length {seq_len} exceeds max_seq_len={self.config.max_seq_len}"
            )
        positions = torch.arange(seq_len, device=input_ids.device).unsqueeze(0)
        x = self.token_embedding(input_ids) + self.position_embedding(positions)
        relation_logits = []
        composition_logits = []
        for block in self.blocks:
            x, relation, composition = block(x)
            relation_logits.append(relation)
            composition_logits.append(composition)
        hidden = self.final_norm(x)
        return {
            "logits": self.lm_head(hidden),
            "hidden_states": hidden,
            "relation_logits": torch.stack(relation_logits, dim=0),
            "composition_logits": torch.stack(composition_logits, dim=0),
        }

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters() if parameter.requires_grad)


def causal_language_loss(logits: Tensor, input_ids: Tensor) -> Tensor:
    """Next-token cross entropy for teacher-forced language-model training."""
    if logits.ndim != 3 or input_ids.ndim != 2:
        raise ValueError("expected logits [B,T,V] and input_ids [B,T]")
    if logits.shape[:2] != input_ids.shape:
        raise ValueError("logits and input_ids batch/sequence dimensions must match")
    if input_ids.shape[1] < 2:
        raise ValueError("at least two tokens are required")
    return nn.functional.cross_entropy(
        logits[:, :-1, :].contiguous().view(-1, logits.shape[-1]),
        input_ids[:, 1:].contiguous().view(-1),
    )


def save_checkpoint(model: OmegaModel, path: str) -> None:
    """Save model configuration and independently learned parameters."""
    torch.save(
        {
            "format": "zhouyi-ai-omega-v1",
            "config": model.config.to_dict(),
            "state_dict": model.state_dict(),
            "parameter_count": model.parameter_count(),
        },
        path,
    )


def load_checkpoint(path: str, *, map_location: str = "cpu") -> OmegaModel:
    payload = torch.load(path, map_location=map_location, weights_only=True)
    if payload.get("format") != "zhouyi-ai-omega-v1":
        raise ValueError("unsupported ZhouyiAI Omega checkpoint format")
    model = OmegaModel(OmegaConfig(**payload["config"]))
    model.load_state_dict(payload["state_dict"], strict=True)
    return model


@torch.no_grad()
def generate(
    model: OmegaModel,
    input_ids: Tensor,
    *,
    max_new_tokens: int = 64,
    temperature: float = 0.0,
    top_k: int | None = None,
) -> Tensor:
    """Generate tokens autoregressively; temperature=0 selects greedy decoding."""
    if input_ids.ndim != 2 or input_ids.shape[1] < 1:
        raise ValueError("input_ids must have shape [batch, non-empty sequence]")
    if max_new_tokens < 0 or input_ids.shape[1] + max_new_tokens > model.config.max_seq_len:
        raise ValueError("prompt plus max_new_tokens must fit max_seq_len")
    if temperature < 0:
        raise ValueError("temperature must be >= 0")
    if top_k is not None and top_k < 1:
        raise ValueError("top_k must be >= 1")
    model.eval()
    output = input_ids
    for _ in range(max_new_tokens):
        logits = model(output)["logits"][:, -1, :]
        if temperature == 0:
            next_token = logits.argmax(dim=-1, keepdim=True)
        else:
            logits = logits / temperature
            if top_k is not None:
                k = min(top_k, logits.shape[-1])
                threshold = torch.topk(logits, k, dim=-1).values[:, -1:]
                logits = logits.masked_fill(logits < threshold, float("-inf"))
            probabilities = torch.softmax(logits, dim=-1)
            next_token = torch.multinomial(probabilities, num_samples=1)
        output = torch.cat((output, next_token), dim=1)
    return output



def classiang_composition_consistency_loss(
    relation_logits: Tensor, composition_logits: Tensor
) -> Tensor:
    """Train the CPG-EI proposal head to approximate a symmetric relation prior.

    The target is detached and derived from the learned relation graph in both
    directions. This is an internal consistency regularizer, not semantic
    supervision or proof that a proposed composition is valid.
    """
    if relation_logits.shape != composition_logits.shape or relation_logits.ndim < 2:
        raise ValueError("relation and composition logits must have identical [..., S, S] shapes")
    forward = torch.softmax(relation_logits.detach(), dim=-1)
    reverse = torch.softmax(relation_logits.detach().transpose(-1, -2), dim=-1)
    target = 0.5 * (forward + reverse)
    prediction = torch.softmax(composition_logits, dim=-1)
    return nn.functional.mse_loss(prediction, target)
