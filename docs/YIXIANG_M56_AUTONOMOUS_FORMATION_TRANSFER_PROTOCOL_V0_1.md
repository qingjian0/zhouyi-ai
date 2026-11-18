# M56 autonomous yixiang formation and relational transfer protocol v0.1

Status: research protocol / preregistration draft  
Depends on: M55.1 repaired benchmark protocol  
Scope: autonomous feature selection, category formation, analogy transfer, and counterexample-driven revision

## 1. Research question

Can a system construct task-relevant classes from observations, preserve relational structure across domains, and revise or reject a class when counterevidence appears—without receiving the target class label or the correct analogy during candidate formation?

M56 does **not** assume that yixiang is equivalent to nearest-neighbor similarity, a fixed taxonomy, causal discovery, or a preloaded mapping from the Eight Trigrams. Those are distinct hypotheses and must be separately operationalized.

## 2. Classical research anchors and interpretation boundary

The initial primary-source corpus should prioritize pre-Qing materials and preserve original text, edition, chapter, and variant information.

| Source | Research question | Constraint on the modern model |
|---|---|---|
| 《周易·系辞》 | 观物取象、立象尽意及象—意关系 | Separate observed phenomenon, selected representation, and intended meaning |
| 《周易·说卦》 | 象类、方位、属性与关系的组织 | Treat traditional correspondences as historically situated hypotheses, not immutable labels |
| 《墨子·小取》 | 类、故、理、譬及推类边界 | Shared appearance or outcome does not prove shared underlying reason |
| 《荀子·正名》 | 名实、同异、约定与辨析 | Distinguish object properties from names and category conventions |
| 《淮南子·说林训》 | 比类、譬喻、情境和变化 | Record the context and purpose under which an analogy is asserted |
| 《庄子·齐物论》 | 视角、分别与判断边界 | Preserve competing descriptions and viewpoint dependence |

Classical passages must be transcribed and source-checked before annotation. Original text, punctuation supplied by editors, modern paraphrase, commentary, and model interpretation are separate fields. Do not silently treat later commentaries as the wording of an early source. The protocol does not claim that these texts contain modern machine-learning algorithms.

## 3. Operational ontology

Each case is represented as a provenance-linked record:

1. **Observation (O):** directly recorded object, event, or textual passage.
2. **Context / purpose (G):** the task and conditions that determine which properties may be relevant.
3. **Candidate features (F):** observable properties, positions, functions, temporal patterns, and relations.
4. **Selected image / aspect (X):** the subset of features and relations selected for the declared purpose.
5. **Class hypothesis (C):** a provisional membership rule with positive, negative, and uncertain examples.
6. **Relational mapping (M):** source-to-target role correspondences and preserved relations.
7. **Evidence (E):** source locator, observation method, provenance lineage, confidence status, and review state.
8. **Counterexample (K):** a case that violates a feature, relation, mechanism, or context condition.
9. **Revision event (R):** split, merge, narrow, broaden, weaken, reject, or retain-as-unknown.

A class is not represented by a name alone. It must include a decision rule, scope, positive evidence, boundary cases, counterexamples, and version history.

## 4. Four-stage cognitive hypothesis

### M56-A — 观象与取象 (observation and task-conditioned feature selection)

Input: observations plus a declared task/context.  
Output: ranked candidate features and a traceable selected subset.

Tests:
- relevant-feature recovery against independently annotated human judgments;
- nuisance-feature resistance after adding irrelevant color, position, wording, or frequency cues;
- task shift: the same object may legitimately yield different selected features for different purposes;
- evidence traceability: each selected feature must point to source observations.

A system must not receive the gold selected-feature set during candidate generation.

### M56-B — 立类与辨类 (provisional category formation)

Input: selected feature/relation records and unlabeled or weakly labeled examples.  
Output: versioned class hypotheses, membership decisions, and explicit unknown/reject states.

Tests:
- held-out member recognition;
- non-member rejection;
- open-set recognition for genuinely new cases;
- boundary stability under nuisance perturbation;
- class split when one apparent class contains incompatible relation or mechanism subfamilies.

Do not reward a system merely for assigning every example to some class. Abstention and unresolved status are valid outputs.

### M56-C — 推类与迁移 (relational analogy transfer)

Input: a source case/class and a target-domain problem.  
Output: a role mapping, preserved relation set, required conditions, and transfer decision.

Test conditions must include:
- high surface similarity but incompatible structure;
- low surface similarity but preserved relational structure;
- relation reversal;
- role permutation;
- missing or additional members;
- context change;
- mechanism change with the same observed outcome;
- paraphrase and answer-order changes.

The score must separate feature overlap, relation preservation, process/mechanism correspondence, and context compatibility. A single scalar similarity score is insufficient as the only audit.

### M56-D — 反例与修正 (counterexample-driven revision)

Input: an existing class/transfer hypothesis and a counterexample with provenance.  
Output: retain, narrow, split, weaken, reject, or request more evidence.

Tests:
- false analogy rejection;
- local rather than indiscriminate global invalidation;
- preservation of unaffected members and relations;
- revision trace with before/after scope;
- no automatic promotion of one counterexample to universal negation when the evidence only narrows scope.

## 5. Benchmark design

### 5.1 Synthetic controlled suite

Construct tasks where the generator independently controls:

- surface attributes;
- task-relevant features;
- relation graph / hypergraph;
- role labels;
- process or mechanism;
- context conditions;
- nuisance variables;
- counterexample type.

The evaluator stores hidden truth separately. Candidate adapters receive only observations, declared context, and permitted evidence. Generator metadata, gold mappings, and target labels must never enter adapter-visible rows.

### 5.2 Classical-source case suite

Create a human-adjudicated corpus from pre-Qing sources. Each case requires:

- work / chapter / passage locator and edition;
- original text and variant witnesses;
- source-family and textual-dependency metadata;
- context and interpretive question;
- candidate features and relations;
- selected image with evidence spans;
- at least one competing interpretation where appropriate;
- boundary case and counterexample status;
- two independent annotations and adjudication record.

Keep primary text, later commentary, modern scholarship, and synthetic examples in separate provenance classes. Do not treat a model-generated paraphrase as primary-source evidence.

### 5.3 Split protocol

Random row splitting is prohibited as the sole OOD evaluation. Use:
- source-family-held-out split;
- work/genre-held-out split;
- period-held-out split;
- relation-template-held-out split;
- object-family-held-out split;
- paraphrase and witness-family leakage checks.

A source and its quotations, paraphrases, commentaries, and dependent compilations must not be split across train and test as if they were independent sources.

## 6. Baselines and ablations

Required baselines, once executable adapters exist:

1. surface-feature similarity;
2. task-conditioned feature matching;
3. relation-graph matching;
4. structure-mapping / role-alignment baseline;
5. mechanism/process matching where mechanism evidence is available;
6. nearest-neighbor retrieval;
7. a Transformer-based model with a fixed prompt and model/version record;
8. CPG-EI without yixiang-specific structure;
9. CPG-EI with each yixiang component added separately;
10. full yixiang-enhanced system.

No model should be listed as measured until its executable adapter is implemented and run. Keep training data, validation data, and test data isolated. Match compute budgets and disclose any human or tool assistance.

## 7. Metrics

| Dimension | Metrics |
|---|---|
| Feature selection | precision/recall against adjudicated relevant features; nuisance sensitivity |
| Category formation | member F1, non-member rejection, open-set AUROC where appropriate |
| Relation mapping | role mapping accuracy, relation preservation, direction/polarity error |
| Transfer | target task success, condition coverage, invalid-transfer rate |
| Counterexample handling | revision accuracy, scope overcorrection, stale-claim rate |
| Epistemic behavior | abstention quality, calibration, unresolved/conflict retention |
| Robustness | paraphrase, order, role permutation, context shift, source-family OOD |
| Cost | latency, tokens, memory, search steps, compute budget |

Report per-condition results and uncertainty. Macro-average across source families rather than allowing a large source family to dominate. Preserve failure cases and raw predictions.

## 8. Literature-derived benchmark requirements

The analogy benchmark literature warns that performance on short or surface-level analogies does not establish robust long-context retrieval or structural mapping. ANALOBENCH evaluates retrieval of related narratives from a large bank and application to complex, lengthy scenarios, using 340 human-written analogies. M56 should therefore separate retrieval from mapping and include long-context/source-bank retrieval rather than testing only isolated pairs.

Robustness work on story analogies reports sensitivity to candidate ordering and paraphrasing for tested GPT models. M56 must therefore include order-invariance and paraphrase-invariance controls; these should be measured, not assumed.

These works are benchmark-design references, not evidence that any particular Zhouyi architecture will outperform a Transformer.

## 9. Preregistered acceptance gates

M56 may be called an executed benchmark only after:
1. schema and validators are implemented;
2. synthetic generator truth is isolated and tested;
3. source provenance and text-layer separation are validated;
4. human annotation agreement and adjudication are reported;
5. source-family and relation-template leakage audits pass;
6. every baseline has a real adapter and identical permitted inputs;
7. ablations and negative controls are run;
8. confidence intervals and multiple-comparison policy are preregistered;
9. raw predictions, failures, configs, and exact commit are archived.

A positive result requires repeatable gains on held-out source/object/relation families without an unacceptable increase in false analogies or computational cost. If the yixiang-specific components do not add reliable value over simpler feature/structure baselines, they should be narrowed or removed.

## 10. Immediate implementation sequence

- M56-A1: schema for observation, task/context, candidate feature, selected image, evidence span, and source provenance.
- M56-A2: synthetic task-conditioned feature-selection generator with hidden evaluator truth.
- M56-A3: nuisance injection and task-shift controls.
- M56-B1: provisional category and open-set rejection contract.
- M56-C1: relation-preserving transfer benchmark with surface-conflict adversaries.
- M56-D1: counterexample-driven versioned revision contract.
- M56-E1: source-family-held-out human annotation pilot.

M56 begins with a small, fully audited slice. Scale only after generator semantics, annotation agreement, and leakage controls pass.
