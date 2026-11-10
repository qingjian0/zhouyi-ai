# CPG-EI Cross-Track Research Synthesis (2026-11-11)

Status: architecture synthesis and next-experiment proposal. This document does not claim a validated general intelligence result.

## 1. Executive finding

The repository's research has expanded from sparse composition into a layered program spanning E02-E12. The most important architectural question is no longer whether a model can select non-adjacent items or fit a higher-order relation. It is whether the system can close a grounded learning loop:

`observe -> propose primitives -> preserve ambiguity -> select measurements -> update evidence -> induce relations -> compose concepts -> transfer -> revise`

The project should treat this loop as the candidate core mechanism. Individual components (hypergraphs, active information gain, symbolic priors, compositional learning) are established research areas; novelty must be demonstrated by their controlled integration and measurable advantage.

## 2. Cross-track role separation

| Track | Proposed responsibility | Required input/output contract |
|---|---|---|
| E12 | Induce grounded predicates and measurement operators | raw observations -> typed, executable operator candidates with provenance |
| E11 | Build concepts and hierarchies | accepted predicates -> reusable concepts with scope and counterexamples |
| E10 | Learn role-sensitive structural mappings | source structures -> target structures with alignment uncertainty |
| E09 | Revise knowledge under streaming evidence | versioned structures + new evidence -> gated updates or abstention |
| E02 | Represent higher-order and non-contiguous relations | typed units -> sparse relation structures with evidence lineage |
| E03 | Coordinate parallel hypotheses | candidate paths -> calibrated, conflict-aware synthesis |
| E04 | Test Yijing-inspired priors | generic learner + controlled prior variants -> measured incremental benefit or rejection |

These are logical responsibilities, not proof that each track is complete or independently useful.

## 3. Critical architecture gap

The current program risks becoming a collection of successful toy solvers whose interfaces do not yet form one learning system. A closed-loop integration benchmark is required.

The loop must enforce:
1. **Grounding:** every operator is executable against observed channels or an explicitly authorized action.
2. **Identifiability:** observationally equivalent explanations remain an equivalence class; no arbitrary winner is selected.
3. **Active evidence acquisition:** when permitted measurements can separate candidates, choose probes under a declared cost budget.
4. **Relational induction:** learn role-sensitive relations, including sparse non-contiguous participation, without receiving hidden relation labels.
5. **Compositional reuse:** accepted primitives must transfer to held-out combinations and nuisance transformations.
6. **Revision safety:** contradictions trigger suspend/refine/split decisions; they do not silently overwrite accepted knowledge.
7. **Auditability:** all decisions retain source IDs, operator versions, counterexamples, compute cost, and evaluation split.

## 4. Recommended next benchmark: E12-Loop

### 4.1 Episode construction

Each independent episode contains:
- a hidden generative mechanism sampled from a preregistered family;
- raw numeric, categorical, temporal, and relational observation channels;
- nuisance variables, missingness, and optional noise;
- a small set of permitted passive measurements;
- optional interventions held for a later causal track;
- support evidence, an independent Gate, and a locked Test.

The learner sees only the observation schema, support records, permitted measurement descriptions, and returned measurement outcomes. It must never receive hidden generator state or locked Test.

### 4.2 Required episode families

A. **Unary predicate:** threshold, parity, change point, or invariant feature.

B. **Sparse relational predicate:** a relation depends on a non-contiguous subset of participants, with irrelevant distractors inserted between them.

C. **Role-sensitive relation:** the same entities produce different outcomes when roles are permuted.

D. **Observational equivalence:** two mechanisms agree on current support and all permitted passive measurements; learner must retain ambiguity.

E. **Discriminating measurement:** at least one permitted measurement separates candidate mechanisms.

F. **Nuisance shift:** irrelevant channels, order, scale, or object identities change between support and test.

G. **Counterexample regime:** a previously accepted operator fails outside its declared scope and must be suspended, split, or refined.

### 4.3 Baselines

Compare with equal observation, candidate-evaluation, and compute budgets:
- fixed handcrafted features;
- random candidate proposals;
- correlation/frequent-pattern baseline;
- exact search on tiny instances;
- fixed measurement policy;
- random measurement policy;
- maximum-disagreement probe;
- expected information gain (EIG);
- cost-normalized EIG;
- static relation model;
- ordinary graph model;
- sparse hypergraph / non-contiguous relation model;
- oracle upper bound, clearly labelled as non-deployable.

### 4.4 Metrics

Report episode-level means and uncertainty intervals for:
- candidate recall and false discovery;
- identifiable-case accuracy;
- ambiguity retention and false-identification rate;
- measurements to identification and acquisition cost;
- relation recovery and role-permutation robustness;
- held-out composition accuracy;
- nuisance-shift degradation;
- counterexample detection and recovery;
- calibration, abstention coverage, latency, and compute.

Do not count correlated observations within one episode as independent samples.

## 5. Experiment order

1. Stabilize E12-A1 typed predicate proposal and its candidate-budget accounting.
2. Implement E12-A2 passive measurement selection as a pure function; verify exact EIG against tiny exhaustive cases.
3. Validate sparse non-contiguous relational primitive induction independently of Yijing priors.
4. Integrate A1 + A2 + relational induction in a single episode runner.
5. Add held-out primitive compositions and nuisance shifts.
6. Add streaming counterexamples and immutable lifecycle transitions.
7. Only then compare Yijing-inspired priors against no-prior, learned-generic, random/permuted, and capacity-matched controls.
8. Keep intervention/causal claims in a separate track after passive measurement selection is validated.

## 6. Yijing integration: a disciplined hypothesis

Yijing-inspired structure should enter as a family of candidate inductive biases, not as fixed truth labels.

Test separately:
- binary complement partition (Yin/Yang);
- two-bit four-state partition (Four Symbols);
- three-bit factorization (Eight Trigrams);
- six-bit state space (64 hexagrams);
- state-transition priors;
- five-element signed relation priors.

For every variant include:
- no-symbolic-prior control;
- capacity-matched generic learned partition;
- random permutation of symbolic labels;
- deliberately incorrect prior;
- learnable prior with permission to reject or revise initialization.

Primary outcomes are sample efficiency, OOD transfer, calibration, and cost—not whether a model can reproduce the symbolic vocabulary. If a symbolic prior does not beat matched generic controls, do not retain it merely for interpretability.

## 7. Claims policy

The project may claim:
- a mechanism is implemented when code and tests exist;
- a result is observed when a reproducible run and configuration are recorded;
- a primitive is identifiable only within a declared hypothesis class and measurement regime;
- a relation is causal only under an appropriate intervention design.

The project must not infer:
- open-world concept discovery from finite grammar search;
- general reasoning from synthetic finite-domain tasks;
- dynamic-structure superiority from static-feature comparisons;
- causal direction from passive correlation;
- Yijing validity from hand-coded correspondence;
- architectural superiority without matched baselines and compute budgets.

## 8. Immediate engineering deliverables

- A shared typed record schema for Observation, OperatorCandidate, Probe, Evidence, RelationCandidate, LifecycleEvent, and EpisodeResult.
- A pure deterministic EIG selector with explicit invalid, ambiguous, no-information, and budget-exhausted states.
- A benchmark runner that physically separates learner-visible inputs from evaluator-only truth and locked Test.
- An append-only provenance ledger with content-addressed versions and reproducible seed/config metadata.
- A single end-to-end small benchmark whose every transition can be replayed and audited.

## 9. Decision

Prioritize **E12-Loop: grounded primitive induction with active measurement and sparse relational discovery** as the next cross-track integration milestone. Do not begin large-model training yet. A CPU-scale, fully auditable closed loop is the highest-value next step; it will reveal whether the proposed cognitive mechanism exists beyond disconnected toy demonstrations.
