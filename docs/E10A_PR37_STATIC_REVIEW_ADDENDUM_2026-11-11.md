# E10-A PR #37 Static Review Addendum (2026-11-11)

Status: static source review only. No tests were executed in this review and no CI pass is claimed.
Reviewed branch: `research/e10a-support-query-boundary-2026-11-10` (PR #37).
Related independent audit: PR #38.

## 1. Correction to the earlier audit

The earlier PR #38 audit described the v2 generator branch, where `learner_view()` exposes all observation outcomes and no support/query adapter exists. A concurrent branch now supplies that adapter in PR #37. Therefore the repository-level statement "there is no support/query partition" is no longer accurate when PR #37 is included.

PR #37 materially addresses the first gap: it creates episode-local support and query partitions, hides query outcomes from the query rows, and groups identical (relation symbol, unordered participant set) combinations together. This addendum supersedes that specific status statement while preserving the broader OOD and identifiability concerns.

## 2. What PR #37 correctly improves

- The adapter accepts separately serialized learner and evaluator views rather than an Episode object.
- Query rows are constructed with an explicit allowlist and omit outcome, validity, violation, and template identifiers.
- Positive, context-negative, and duplicate-context records for the same relation/participant set are kept in one partition.
- Support is required to retain both positive and negative labels for each relation.
- Observation assignment is exact and deterministic for a fixed seed.
- The PR explicitly disclaims object-disjoint/OOD generalization, identifiability, process isolation, and empirical results.

These are useful and appropriately scoped improvements.

## 3. Static review findings and remaining risks

### R1 — The split is label-aware and can induce query-selection bias

The splitter reads evaluator `valid` labels to ensure the support side retains both classes. This is defensible as a task-construction constraint, but the query sample is consequently not an unconditional random sample of participant groups. Query inclusion probabilities depend on label composition and on the order in which candidate groups are considered.

Required follow-up:
- Record the selection algorithm and realized class/group counts in the manifest.
- Compare against a predeclared label-blind group split.
- Report per-class query coverage and selection rates.
- Do not interpret query metrics as unbiased population estimates without accounting for this selection policy.

### R2 — Group-disjoint is not object-disjoint or structure-disjoint

Grouping by relation symbol plus unordered participant set prevents exact participant-combination leakage. It does not prevent:
- the same individual object appearing in both support and query;
- highly overlapping participant sets;
- repeated attribute-role patterns across the split;
- query examples being inferable from support examples sharing most participants.

Required follow-up: add object-disjoint, participant-overlap-controlled, and attribute-pattern/role-composition OOD tracks. Keep them separate from the episode-local interpolation result.

### R3 — Evaluator truth is returned beside learner views

The function returns `support`, `query`, `evaluator_truth`, and `manifest` in one Python dictionary. The documentation correctly says this is not a security boundary. A benchmark runner must pass only serialized support/query payloads to the learner and keep evaluator truth in a separate process or access-controlled service.

Required follow-up: add an executable runner contract and a test that inspects the exact serialized learner input, not only the QueryView row keys.

### R4 — Input validation is weaker than the boundary claim

The adapter checks observation-ID uniqueness on the learner side and compares ID sets, but it builds `truth_by_id` by dictionary comprehension without first rejecting duplicate evaluator observation IDs. It also coerces evaluator values with `bool(...)`, so malformed values can silently become labels. It does not fully validate row schemas, participant uniqueness, or learner outcome/evaluator validity consistency.

Required follow-up:
- reject duplicate evaluator IDs before dictionary construction;
- require exact booleans for `outcome` and `valid`;
- validate required fields and participant uniqueness;
- verify `outcome == valid` for each observation before splitting;
- fail closed on unknown or unexpected schema versions.

### R5 — Existing tests are necessary but not sufficient

The current tests cover query field omission, exact participant-group separation, support class retention, deterministic output, exact assignment, and basic invalid inputs. They do not yet cover:
- duplicate evaluator IDs and malformed truth types;
- query-label canary mutation while preserving learner input byte-for-byte;
- recursive forbidden-field scans of the complete serialized learner payload;
- adversarial ID/order/cardinality shortcuts;
- object-overlap and near-duplicate structure leakage;
- identifiability/ambiguity on support-only evidence;
- selection-bias characterization.

The PR states that its exact tests have not been run locally or in GitHub Actions. Treat all of them as authored tests, not passing validation.

## 4. Updated claim boundary

If PR #37's implementation and tests are later validated, it can support a narrow claim:

**L1-task-view infrastructure:** a deterministic, episode-local, participant-group-disjoint support/query representation with query labels omitted from the query payload.

It does not by itself establish:
- relation structure recovery;
- object-disjoint generalization;
- cross-episode transfer;
- unseen relation-family OOD;
- unique identifiability;
- autonomous concept or operator invention.

## 5. Recommended next experiment

Before implementing a learner, add a small adversarial audit suite for the splitter:
1. duplicate/malformed evaluator truth rejection;
2. label-blind versus label-aware split comparison;
3. query-label canary and byte-identical learner payload;
4. participant overlap and attribute-pattern leakage reports;
5. support-only oracle identifiability and ambiguity labels.

Then implement the smallest transparent learner and compare it with lookup, fixed-rule, nearest-neighbour, finite-DSL, graph/hypergraph, and random-prior baselines under matched support/query samples and compute budgets.

## 6. Coordination

This addendum is documentation-only on the independent PR #38 branch. It does not modify PR #37, its branch, E09, E02, or main. It corrects the earlier audit's repository-level status while preserving a clear list of remaining research gates.
