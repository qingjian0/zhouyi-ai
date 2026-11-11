"""Evidence-driven research utilities for Zhouyi-AI."""
from .evidence import evaluate_evidence
from .hypotheses import Hypothesis, HypothesisStore
__all__ = ["Hypothesis", "HypothesisStore", "evaluate_evidence"]
