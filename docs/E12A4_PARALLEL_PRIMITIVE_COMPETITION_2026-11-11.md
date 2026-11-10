# E12-A4 — Parallel Primitive Competition and Sparse Composition

Date: 2026-11-11  
Status: architecture hypothesis and preregisterable experiment design; no implementation or performance claim.  
Dependency: E12-A0/A1 primitive identifiability and E12-A2-M exact-oracle validation. A4 may be prototyped in isolation, but it must not be presented as a validated replacement for the generic A2 measurement baseline.

## 1. Research question

Can a system discover reusable relational primitives by proposing multiple explanations in parallel, composing them through sparse non-contiguous relations, and selecting or combining them using predictive evidence and complexity control—without requiring each output element to be generated autoregressively from the previous output element?

The core object is not a fixed list of Yijing symbols. It is a learned, typed, reusable primitive with:
- an operational definition;
- a set of input conditions;
- a predicted relation or transformation;
- an uncertainty estimate;
- evidence provenance;
- a complexity and compute cost.

Yijing-derived ideas such as complementary polarity, phase, position, transformation, and nested structure are candidate inductive biases only. Each must be compared with generic and shuffled alternatives.

## 2. Separate the three mechanisms

Do not conflate parallel proposal, sparse composition, and competition into one module.

### A — Parallel proposal

Given an input representation x, multiple proposal heads produce a *set* of candidate primitives or structures in one forward pass:

`P(x) = {p_1, ..., p_K}`

No proposal head consumes another head's generated output token. Proposal order is not semantically meaningful.

### B — Sparse composition

A composition operator builds candidate structures from selected primitives. It may connect non-adjacent elements (for example, positions 1, 2, 4, 5), and may use typed edges or hyperedges.

A composition is represented as a graph/hypergraph, not a flattened string. The grammar records:
- operand types;
- relation type;
- optional skipped positions;
- composition depth;
- provenance of each operand;
- whether the composition is observed, proposed, or validated.

### C — Evidence-based competition and coalition

Candidate structures compete for limited compute and explanatory responsibility. A candidate may:
- survive independently;
- be merged with another candidate when their joint predictions add value;
- be specialized into sub-primitives;
- be rejected;
- abstain when evidence is insufficient.

A coalition is not accepted merely because its members are individually plausible. Its *joint predictive gain* must exceed added complexity and compute cost.

## 3. Candidate scoring

For candidate structure g on evidence set D, define a pre-registered score:

`Score(g) = -L_pred(g; D) - beta * L_complexity(g) - lambda * C_compute(g)`

where:
- `L_pred` is held-out predictive loss, not training fit;
- `L_complexity` is a declared description-length or parameter/edge penalty;
- `C_compute` is measured proposal, composition, and inference cost;
- beta and lambda are tuned on Train/Gate only and frozen before Test.

For uncertain predictions, report proper scoring rules (log loss or Brier score) and calibration. Do not treat raw confidence or internal agreement as evidence of correctness.

For a coalition g1+g2, require positive held-out incremental value:

`Delta = L_pred(g1) - L_pred(g1+g2) - beta * DeltaComplexity - lambda * DeltaCompute`

A coalition is retained only when Delta exceeds a predeclared threshold on Gate data. Test data is never used to grow or merge primitives.

## 4. Non-autoregressive claim: operational definition

The phrase "non-autoregressive" is reserved for a measurable property:

1. All K primitive proposals for an input are computed without consuming one another's generated outputs.
2. All candidate compositions for a fixed refinement round are computed from the same frozen proposal state.
3. The predicted output is emitted as a set/graph or as parallel slots, not by feeding output token t into the prediction of token t+1.
4. Any iterative refinement is counted explicitly as refinement rounds; it must not be described as one-pass generation.
5. If a downstream decoder is autoregressive, the whole system is hybrid, not fully non-autoregressive.

Primary latency is wall-clock end-to-end latency at matched hardware and batch size. Also report number of sequential dependency stages, memory, FLOPs or a documented compute proxy, and quality. Parallel proposal count alone does not prove faster inference.

## 5. Training objectives to compare

Do not assume one loss is sufficient. Run controlled ablations:

- **Task loss:** supervised prediction of target properties or output sets.
- **Set matching loss:** permutation-invariant matching between predicted slots and target elements (for example, Hungarian matching where applicable).
- **Relational consistency:** enforce typed relations among predicted primitives, with violations explicitly counted.
- **Contrastive discrimination:** distinguish valid compositions from capacity-matched corruptions.
- **Predictive reuse:** reward a primitive only when it transfers to held-out tasks or environments.
- **Calibration:** proper probabilistic loss and post-hoc calibration measured separately.
- **Complexity regularization:** discourage memorized one-off primitives and unbounded composition depth.

Every objective needs an ablation. A combined objective is not evidence that each component contributes.

## 6. Benchmark design

Use synthetic tasks first because the hidden generating rules can be enumerated and mutated.

### B1 — Non-contiguous composition

Rules depend on non-adjacent input elements. Train includes some gap patterns; Test holds out gap lengths and position combinations.

### B2 — Complementary relation

Rules depend on complementary binary or multi-state relations. Compare:
- generic learned relation embeddings;
- fixed complementary prior;
- shuffled complementary mapping;
- no relational prior.

### B3 — Hierarchical composition

Primitive relations combine into two- and three-level structures. Test unseen compositions from known primitives and unseen primitives from known relation families separately.

### B4 — Distractor and decoy primitives

Inputs contain high-correlation but non-causal distractors. Measure whether evidence-based competition rejects attractive but non-transferable primitives.

### B5 — Distribution shift / anti-aligned structure

The relation mapping changes between Train and Test. A system must reduce confidence or adapt from permitted evidence; it must not preserve a fixed symbolic mapping at all costs.

### B6 — Observational equivalence

Two candidate structures produce identical predictions for every permitted observation. The system must preserve ambiguity rather than invent a unique explanation.

## 7. Baselines

At matched data, parameter, tuning, and compute budgets compare:

1. Autoregressive Transformer or a suitable autoregressive baseline.
2. Parallel set-prediction model without primitive reuse.
3. Parallel proposal plus dense composition.
4. Parallel proposal plus sparse composition, no competition.
5. Sparse composition plus independent scoring, no coalition.
6. Full competition and coalition model.
7. Generic learned relation model.
8. Yijing-inspired structured prior.
9. Capacity-matched shuffled prior.
10. Exact solver on tiny enumerable tasks.

The baseline suite must include the simplest model that can solve each benchmark. Avoid comparing a large custom architecture only against a weak strawman.

## 8. Primary and secondary metrics

Primary:
- held-out task success at a fixed compute budget, reported by task family.

Secondary:
- generalization to unseen gap patterns and compositions;
- primitive reuse across independent tasks;
- rate of valid versus invalid compositions;
- false primitive discovery rate;
- coalition incremental predictive value;
- calibration and confidently-wrong rate;
- latency, sequential dependency depth, peak memory, and compute;
- performance under distribution shift;
- abstention under observational equivalence.

A4 does not pass because it generates many candidates. It passes only if reusable primitives improve held-out performance or compute-quality trade-offs over capacity-matched parallel baselines.

## 9. Leakage and anti-shortcut controls

- Hidden generator rules and Test labels remain evaluator-private.
- Randomize IDs, serialization order, and candidate ordering.
- Use disjoint rule families across Train/Gate/Test.
- Prevent primitive names, file paths, or graph node IDs from encoding rule labels.
- Mutate evaluator truth while keeping learner-visible inputs fixed; predictions must remain unchanged.
- Shuffle symbolic mappings and preserve parameter count.
- Audit whether proposal slots collapse to duplicates.
- Count every search and tuning trial against the compute budget.
- Freeze primitive library snapshots before locked Test.

## 10. Falsification conditions

The architecture hypothesis is weakened or rejected if:
- parallel proposal adds compute but no quality/latency benefit;
- sparse composition fails to generalize to unseen gaps;
- primitives do not transfer across task families;
- coalition gain disappears after complexity and compute penalties;
- shuffled mappings perform as well as the Yijing-inspired mapping;
- the system becomes confidently wrong under mapping reversal;
- improvements vanish against a capacity-matched parallel set-prediction baseline;
- outputs depend on ordering, IDs, or evaluator-private information;
- ambiguity is collapsed into unsupported certainty.

## 11. Implementation sequence

1. Freeze B1 and B6 tiny enumerable generators.
2. Implement a minimal typed primitive record and graph composition schema.
3. Implement parallel proposals with deterministic seeded initialization.
4. Add sparse composition enumeration with explicit depth/edge budgets.
5. Add held-out evidence scoring before any coalition learning.
6. Compare no-competition, independent scoring, and coalition variants.
7. Only after generic gains are reproduced, test Yijing-inspired priors against shuffled and generic controls.
8. Add realistic language tasks only after synthetic rule recovery and leakage tests pass.

## 12. Current conclusion

A4 is a falsifiable architecture hypothesis, not a demonstrated model. Its distinctive research contribution is the separation of (i) parallel candidate proposal, (ii) non-contiguous typed composition, and (iii) evidence-based competition/coalition under explicit complexity and compute budgets.

The non-autoregressive claim is restricted to proposal and composition dependency structure. It does not imply that the entire training or deployment pipeline is non-autoregressive, faster, or more intelligent.
