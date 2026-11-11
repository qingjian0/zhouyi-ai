"""Evidence-driven research utilities for Zhouyi-AI."""
from .archive_adapter import evaluate_archived_evidence
from .evidence import evaluate_evidence
from .hypotheses import Hypothesis, HypothesisStore

__all__ = ["Hypothesis", "HypothesisStore", "evaluate_evidence", "evaluate_archived_evidence"]
