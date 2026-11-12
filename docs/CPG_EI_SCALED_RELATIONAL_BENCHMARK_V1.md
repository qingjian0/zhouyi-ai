# CPG-EI scaled relational benchmark v1

Status: research design; implementation and empirical results are not yet claimed.
Base: random-teacher-family research line, following the state-disjoint protocol.

## Decision

Expand the current six-input, 64-state, ten-teacher diagnostic along two independent axes:

- Teacher diversity: 10 -> 40 independent teacher families (4x).
- Input-state coverage per teacher: 6 Boolean inputs / 64 states -> 8 inputs / 256 states (4x).

The planned complete corpus therefore grows from 10 x 64 = 640 teacher-state examples to 40 x 256 = 10,240 examples (16x overall), before optional noisy replicas, counterfactuals, and alternate modalities. The 16x figure is a generation target, not a measured training gain. Keep the six-bit benchmark unchanged as a regression control.

Do not inflate the corpus by repeating the same 64 states or by counting duplicated rows as independent evidence. The primary expansion comes from a larger state space and independently sampled rule structures.

## Why this expansion is necessary

The current conditional-motif benchmark has a strict but very small domain: six Boolean inputs, only 64 possible states, three planted triples, six output heads, and ten teacher families in the next research increment. Repeating samples cannot create new input-state coverage. The current feature vocabulary and learner are also six-input-specific. A larger benchmark must therefore generalize the generator, relation feature schema, learner dimensions, and split audit together.

The previous six-bit row-sampled experiment accidentally reused states across splits. The state-disjoint protocol corrected this by partitioning the complete 64-state domain. This scaled protocol preserves that invariant at 256 states per eight-input teacher.

## Relation taxonomy to cover

The benchmark should make relation identity explicit rather than treating every interaction as an unordered set.

1. **Unary / attribute relations**: membership, threshold, polarity, category, and state predicates. These are controls and primitives, not evidence of higher-order reasoning.
2. **Binary relations**: symmetric (co-membership, equivalence), asymmetric (precedes, contains, implies), inverse pairs, signed/weighted influence, and typed role pairs.
3. **Conditional relations**: A relates to B only under context C; context may be a state bit, another relation, or a conjunction of attributes. Include context-present and context-absent counterfactual pairs.
4. **Higher-order joint relations**: ternary through six-ary rules. Compare a true joint rule against the pairwise projection that preserves pairwise marginals but destroys the joint dependency.
5. **Ordered / role-sensitive relations**: subject-predicate-object, source-target, before-after, cause-effect candidates, and n-ary tuples with named slots. Permuting roles must change labels where the relation is directional.
6. **Compositional / path relations**: two-hop and multi-hop chains, shared-intermediate constraints, branching, joins, and ordered rule bodies. Explicitly include negative cases where pairwise edges exist but do not belong to one coherent path.
7. **Hierarchical / part-whole relations**: containment, component-of, parent-child, abstraction/refinement, and depth-sensitive transitive closure.
8. **Constraint relations**: mutual exclusion, implication, equivalence, parity, cardinality, and satisfiability constraints; include satisfiable and minimally inconsistent cases.
9. **Temporal / dynamic relations**: before, after, overlap, persistence, transition, lagged dependence, event co-occurrence, and relation creation/removal under controlled distribution shift.
10. **Analogy / cross-domain relations**: structure-preserving mappings across different symbol vocabularies, with hard negatives that are lexically similar but structurally incompatible.
11. **Signed and antagonistic relations**: support, inhibit, compete, suppress, and balanced opposing influences. Do not collapse negative evidence into absence.
12. **Uncertain / incomplete relations**: missing observations, noisy labels, ambiguous role assignments, confidence intervals, and explicit abstention when evidence cannot identify a unique rule.

Causal language is used only for synthetic structural mechanisms with known interventions. Observational correlation alone must never be labelled as causal discovery.

## Generator v1: scalable parity core

First implement a parameterized generator before mixing in every relation family.

- Input dimensions: n = 8 Boolean variables; enumerate all 2^8 = 256 states.
- Output dimensions: m = 8 relation targets (no longer hard-code six output heads).
- Candidate support: all subsets of input variables with arity 2 through 6. For n=8 this gives 238 candidate subsets: C(8,2)+...+C(8,6).
- Teacher family: sample 2-5 active relation supports, with configurable arity mix; enforce unique supports and record the exact teacher manifest.
- Output rule: each target has an explicit operator and ordered/unordered role schema. Initial parity track uses XOR over its support; later tracks add modular, conjunction, implication, threshold, and mixed conditional operators.
- Teacher generation seed and state-split seed must be separate. Store both, plus generator version and canonical teacher digest.
- Include easy, medium, and hard regimes: sparse low-arity; mixed 2-4 arity; dense 3-6 arity with overlapping supports and correlated distractors.
- Generate matched negative controls: shuffled labels, null teachers, pairwise-marginal-preserving controls, role permutations, and false path compositions.

The CPG-EI learner and feature construction must become dimension-generic. Do not silently pad/truncate the old six-dimensional learner and call it eight-dimensional.

## Data volume and splits

Target corpus, before optional augmentation:

| Quantity | Current reference | Scaled v1 target | Multiplier |
|---|---:|---:|---:|
| Input variables | 6 | 8 | 1.33x |
| Unique states per teacher | 64 | 256 | 4x |
| Independent teacher families | 10 | 40 | 4x |
| Teacher-state rows | 640 | 10,240 | 16x |
| Candidate relation supports | 20 triples | 238 subsets, arity 2-6 | 11.9x vs triple-only candidate pool |

The candidate-pool ratio is descriptive, not a data-row multiplier.

Two complementary evaluation protocols are required:

### Protocol A: state-disjoint within-family generalization

For each teacher, partition all 256 unique states into 128 train / 64 development / 64 locked-test states. Assert exact union of 256, uniqueness, and zero pairwise overlap. Proposal generation and fitting may see train only; configuration selection may see development only; locked test is opened only after freezing the configuration.

### Protocol B: unseen-teacher few-shot adaptation

Split the 40 teacher IDs before generating training examples into 24 meta-train / 8 meta-development / 8 locked teacher families. For each held-out teacher, provide a separately declared support set for adaptation and a disjoint query set for evaluation. No teacher ID, support/query state, or teacher digest may cross the family split. Report zero-shot and support-conditioned results separately. Never use locked query labels for proposal selection, threshold tuning, early stopping, or model selection.

Protocol A measures unseen states under known teacher families. Protocol B measures transfer to unseen teacher structures with explicit support evidence. Do not merge their scores.

## Relationship discovery measurements

Report each relation family and arity separately:

- Candidate recall@K and candidate precision@K before fitting.
- Exact support recovery and partial support precision/recall.
- Relation-type accuracy and ordered-role accuracy.
- Conditional effect recovery with context-on/context-off counterfactuals.
- Joint-synergy recovery against pairwise-marginal controls.
- Path coherence and false-composition rate.
- Hierarchy/transitive-closure accuracy.
- Signed-edge polarity accuracy.
- Temporal transition and change-point performance.
- Analogy transfer accuracy and structurally invalid analogy acceptance rate.
- Abstention coverage, selective accuracy, Brier score, and calibration error.
- Downstream bit/tuple accuracy, exact-state accuracy, and OOD-family accuracy.

Separate structure recovery from prediction. A model can recover a planted support but still fail to predict; it can also predict through a shortcut without recovering the intended structure.

## Baselines and controls

At minimum compare:

- Majority / random / frequency baselines.
- Lookup-table and exact finite hypothesis-space solver where feasible.
- Pairwise-only graph learner.
- Static hypergraph learner.
- Dynamic hypergraph learner.
- Existing CPG-EI six-bit implementation as a regression reference.
- Dimension-generalized CPG-EI without conditional motifs.
- CPG-EI with conditional/higher-order relation proposals.
- Oracle-support learner (diagnostic upper bound only).
- Parameter- and compute-matched MLP / Transformer or autoregressive control when the benchmark is ready for that comparison.

Tune every trainable baseline on development data under matched compute budgets. Oracle support is never a fair headline baseline.

## Noise, robustness, and distribution shift

After the clean generator passes, independently vary:

- Observation noise: 0%, 1%, 5%, 10%.
- Missing observations: 0%, 10%, 25%.
- Distractor relation density.
- Label corruption and ambiguous role assignment.
- Input-variable permutation and renaming.
- Relation-type permutation.
- Support-set size in few-shot adaptation.
- Teacher-family shift and operator-family shift.
- Temporal drift and controlled rule replacement.

Do not multiply the clean corpus by near-identical noise copies and report them as independent teacher families. Track base teacher identity and augmentation lineage.

## Statistical and reproducibility contract

- At least 10 generator seeds for smoke/diagnostic runs; target 20 independent teacher-generation seeds for final aggregate claims.
- Report mean, standard deviation, confidence intervals, per-family distributions, and worst-family performance.
- Use paired comparisons on identical teachers and splits; apply a predeclared multiple-comparison correction when testing many relation types.
- Save machine-readable JSONL/Parquet rows plus a manifest containing generator version, schema version, seed, teacher ID/digest, split, relation supports, noise parameters, and provenance.
- Verify train/dev/test family isolation and state isolation with executable assertions.
- Deduplicate exact rows and near-identical generated cases; retain augmentation lineage.
- Keep locked-test data inaccessible to proposal ranking and hyperparameter selection.
- Preserve failed seeds and negative results.

## Implementation sequence

1. Extract the current six-bit assumptions into explicit dimensions and add dimension-generic teacher/state generation.
2. Add eight-input/eight-output tests and exact 256-state split audits.
3. Add 40 teacher families and produce the 10,240-row corpus manifest.
4. Generalize conditional motif proposal features from six inputs to arbitrary n and arity 2-6.
5. Run Protocol A before Protocol B; keep both artifacts separate.
6. Add relation-family generators incrementally: conditional, ordered-role, path, constraint, temporal, signed, hierarchy, analogy.
7. Add noise and hard-negative controls only after clean baselines are stable.
8. Publish an experiment report with actual artifacts and exact commit SHA.

## Acceptance gates

- No train/dev/locked leakage in either protocol.
- Generator is deterministic for fixed version and seeds.
- 256 unique states per eight-input teacher; 40 unique teacher digests.
- Candidate support indexing is dimension-generic and validated against brute-force enumeration on small n.
- All losses and reported metrics are finite; undefined metrics remain null rather than being coerced to zero.
- All core baselines run on the same generated examples and budget.
- No claim of broad relational intelligence until unseen-teacher, relation-family, and operator-family tests all pass.

## Claim boundary

This is a proposed scaled synthetic benchmark. It is not a result, a real-world semantic dataset, or evidence that CPG-EI outperforms Transformer architectures. The 16x data target is achieved by increasing both independent teacher count and state-space size; it must be verified by the generator and manifest before being reported as delivered.


## External benchmark design references

These works inform benchmark construction and evaluation design; they are not evidence that this repository's model already has the corresponding capabilities.

- **GraphLog / logical generalization**: diverse procedurally generated logical domains and rule-family transfer. Use it as a reminder that the number and diversity of rule systems matter, not just the number of rows. https://arxiv.org/abs/2003.06560
- **Synthetic datasets and evaluation tools for inductive neural reasoning**: emphasizes interpretable rules, diverse dependencies, and adequate dataset scale; useful for rule-generator and metric design. https://lr2020.iit.demokritos.gr/online/Cornelio.pdf
- **ReAlE / relational algebra over hypergraphs**: motivates operation-complete and depth-varying relation compositions, including renaming, projection, selection, union, and difference. https://jmlr.org/papers/volume24/22-063/22-063.pdf
- **HYPER (ICLR 2026)**: studies inductive link prediction over unseen entities and relation types with varying arities; supports explicitly separating entity-inductive, relation-inductive, and arity-transfer tests. https://proceedings.iclr.cc/paper_files/paper/2026/hash/cdf80d651420b47da80f789f2631b1b5-Abstract-Conference.html

The scaled benchmark should borrow the evaluation discipline and task diversity, not assume that its synthetic operators are equivalent to real-world semantics.
