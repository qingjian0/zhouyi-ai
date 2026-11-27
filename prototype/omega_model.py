"""ZhouyiAI Omega: first trainable hybrid foundation-model prototype.

This is a research MVP, not a claim of general intelligence or Transformer
replacement. It combines token-level language processing with recurrent state
updates and a learned classiang relational workspace. The classiang workspace
is internal to the model and is trained jointly with the language objective.

Install the optional dependency with pip install -e .[model].
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

try:
    import torch
    from torch import Tensor, nn
except ImportError as exc:  # pragma: no cover - exercised on minimal installs
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

    def __post_init__(self) -> None:
        if self.vocab_size < 2:
            raise ValueError("vocab_size must be >= 2")
        if self.d_model < 8 or self.d_model % self.n_heads:
            raise ValueError("d_model must be >= 8 and divisible by n_heads")
        if self.n_heads < 1 or self.n_layers < 1:
            raise ValueError("n_heads and n_layers must be positive")
        if self.num_classiang_slots < 2 or self.max_seq_len < 2:
            raise ValueError("num_classiang_slots and max_seq_len must be >= 2")
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("dropout must be in [0, 1)")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ClassiangWorkspace(nn.Module):
    """Learned latent aspects and typed relational message passing."""

    def __init__(self, config: OmegaConfig) -> None:
        super().__init__()
        d_model = config.d_model
        self.slots = nn.Parameter(torch.randn(config.num_classiang_slots, d_model) * 0.02)
        self.read = nn.MultiheadAttention(d_model, config.n_heads, batch_first=True,
                                          dropout=config.dropout)
        self.token_read = nn.MultiheadAttention(d_model, config.n_heads, batch_first=True,
                                                dropout=config.dropout)
        self.relation_q = nn.Linear(d_model, d_model, bias=False)
        self.relation_k = nn.Linear(d_model, d_model, bias=False)
        self.relation_v = nn.Linear(d_model, d_model, bias=False)
        self.relation_out = nn.Linear(d_model, d_model)
        self.slot_norm = nn.LayerNorm(d_model)
        self.token_norm = nn.LayerNorm(d_model)
        self.scale = d_model ** -0.5

    def forward(self, tokens: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        batch = tokens.shape[0]
        slots = self.slots.unsqueeze(0).expand(batch, -1, -1)
        observed_slots, _ = self.read(slots, tokens, tokens, need_weights=False)
        slots = self.slot_norm(slots + observed_slots)

        q = self.relation_q(slots)
        k = self.relation_k(slots)
        v = self.relation_v(slots)
        relation_logits = torch.matmul(q, k.transpose(-1, -2)) * self.scale
        relation_weights = torch.softmax(relation_logits, dim=-1)
        related = torch.matmul(relation_weights, v)
        slots = self.slot_norm(slots + self.relation_out(related))

        token_context, _assignments = self.token_read(
            tokens, slots, slots, need_weights=True, average_attn_weights=True
        )
        return self.token_norm(tokens + token_context), slots, relation_logits


class OmegaBlock(nn.Module):
    """Hybrid block: attention, recurrent state update, and classiang workspace."""

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

    def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
        attended = self.attention(x)
        recurrent, _ = self.recurrent(x)
        classiang, _slots, relation_logits = self.classiang(x)
        gates = torch.softmax(self.mix(torch.cat((attended, recurrent, classiang), dim=-1)), dim=-1)
        stacked = torch.stack((attended, recurrent, classiang), dim=-2)
        mixed = torch.sum(stacked * gates.unsqueeze(-1), dim=-2)
        return self.output_norm(x + self.dropout(mixed)), relation_logits


class OmegaModel(nn.Module):
    """A small, independently initialized hybrid language/类象 model."""

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
        batch, seq_len = input_ids.shape
        if seq_len > self.config.max_seq_len:
            raise ValueError(
                f"sequence length {seq_len} exceeds max_seq_len={self.config.max_seq_len}"
            )
        positions = torch.arange(seq_len, device=input_ids.device).unsqueeze(0)
        x = self.token_embedding(input_ids) + self.position_embedding(positions)
        relation_logits = []
        for block in self.blocks:
            x, relation = block(x)
            relation_logits.append(relation)
        hidden = self.final_norm(x)
        return {
            "logits": self.lm_head(hidden),
            "hidden_states": hidden,
            "relation_logits": torch.stack(relation_logits, dim=0),
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
    """Save portable model configuration and independently learned parameters."""
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
    payload = torch.load(path, map_location=map_location, weights_only=False)
    if payload.get("format") != "zhouyi-ai-omega-v1":
        raise ValueError("unsupported ZhouyiAI Omega checkpoint format")
    model = OmegaModel(OmegaConfig(**payload["config"]))
    model.load_state_dict(payload["state_dict"], strict=True)
    return model
