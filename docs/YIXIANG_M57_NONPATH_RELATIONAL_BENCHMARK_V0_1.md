# M57 — Non-path relational transfer benchmark v0.1

Status: executable synthetic benchmark slice; exact-head CI required  
Base: M56 executable core  
Research question: can a system preserve a relational structure when validity depends on more than composing one binary relation path?

## Motivation

Recent systematic-relational-reasoning work shows that path-composition benchmarks can reward methods whose inductive bias is path-specific. M57 therefore adds a controlled task where a correct mapping must jointly satisfy binary relations, ordered hyperedges, forbidden relations, injective role assignment, and a graph-wide cardinality constraint. This is aligned with the NoRA benchmark's motivation, but M57 is an independent small synthetic diagnostic, not a reproduction of NoRA.

## Implemented

- Three actual structural difficulty levels: basic binary chain; compositional branching with a ternary hyperedge and negative relation; nonpath disconnected binary components plus multiple hyperedges, all-different constraints, forbidden relations, and a global count.
- Target graphs contain same-type distractor nodes and relation noise.
- Candidate role mappings are public; exactly one satisfies all declared constraints. In compositional/nonpath levels, all candidates deliberately satisfy the binary-relation subset, so only hyperedge/negative/global constraints can distinguish the planted mapping.
- Agent-visible case JSON and evaluator-only answer/split metadata are written separately.
- Constraint-level diagnostics identify failed type, binary, hyperedge, negative, injectivity, all-different, and global-count requirements. The hard-level test explicitly proves binary-only ambiguity.
- Deterministic generation and split/difficulty auditing.

## Critical interpretation boundary

M57 is a candidate-selection benchmark. Candidate mappings are supplied to isolate structural evaluation from entity-alignment search. It does not test autonomous role discovery, learned representations, text extraction, perception, causal inference, or human-level analogy. The planted synthetic labels are not classical-text gold data. A passing generator/test suite validates the benchmark contract, not a model's capability or Zhouyi-AI superiority.

## Experimental protocol for the next integrated study

1. Freeze generator version, seeds, family-level split rules, and scoring before running models.
2. Compare path-only, typed-graph, hypergraph/neuro-symbolic, Transformer/LLM, and Zhouyi/Yixiang adapters on identical public cases.
3. Give every adapter the same candidate mappings, public graph, token/context budget, tool permissions, and wall-clock/compute budget.
4. Report exact candidate accuracy, constraint-level precision/recall, per-difficulty and per-split scores, abstention coverage/risk, calibration, and paired family-cluster bootstrap intervals.
5. Add mutation controls: reverse one relation; remove one hyperedge; violate one forbidden relation; alter the global count; permute role names; add irrelevant nodes/edges; hold out entire generator families.
6. Keep evaluator truth unavailable until predictions are immutable. Reject any adapter that reads evaluator artifacts.
7. Add independently authored and adjudicated classical-text cases only after source witnesses, edition/variant provenance, textual dependence, and two independent annotations are audited.

## Known remaining gates

- No learned model adapters are included.
- Candidate mappings are supplied; autonomous mapping discovery is future work.
- Synthetic generator families are few; family-held-out OOD is not yet a real-world OOD estimate.
- No human gold or classical corpus evaluation is claimed.
- No result here establishes causal validity or the empirical truth of traditional 易象 mappings.

## Literature anchors

- Das et al., *When No Paths Lead to Rome: Benchmarking Systematic Neural Relational Reasoning*, NeurIPS 2025: motivates going beyond path-only relational reasoning.
- Wu et al., *A Systematic Review of Analogy Generation and Evaluation: Methods, Metrics, and Challenges*, Findings of EMNLP 2026: emphasizes analogy granularity and human-in-the-loop evaluation.
- Mitchell, *On Evaluating Abstraction and Analogy in Humans and Machines*, 2026: motivates robustness, process transparency, and scientifically controlled comparisons.
