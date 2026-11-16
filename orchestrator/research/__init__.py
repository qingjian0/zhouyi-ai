"""Research hypothesis and evidence utilities."""
from .active_design import design_next_experiment
from .archive_adapter import evaluate_archived_evidence
from .evidence import evaluate_evidence
from .hypotheses import Hypothesis, HypothesisStore
from .raw_analyzer import analyze_raw_observations, task_manifest_from_specs

__all__ = ["Hypothesis", "HypothesisStore", "evaluate_evidence",
           "evaluate_archived_evidence", "analyze_raw_observations", "task_manifest_from_specs", "design_next_experiment"]
