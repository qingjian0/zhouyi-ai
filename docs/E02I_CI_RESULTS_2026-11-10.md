# E02-I CI 结果（2026-11-10）

## 来源与范围

- GitHub Actions run: [42821097953](https://github.com/qingjian0/zhouyi-ai/actions/runs/42821097953)
- PR: [#9](https://github.com/qingjian0/zhouyi-ai/pull/9)
- Workflow conclusion: **success**
- Unit tests: success
- Workflow experiment steps: all 18 completed successfully
- E02-I: 7 scenarios × 20 seeds × 5 windows = 140 episodes / 700 windows
- Train / Gate / Test sample IDs are disjoint in every window.

## E02-I acceptance metrics

| Scenario | Metric | Result |
|---|---|---:|
| stable | No reconfiguration | 20/20 (100%) |
| stable | Final structure correct | 20/20 (100%) |
| member_add | Reconfigured | 20/20 (100%) |
| member_add | Final structure correct | 20/20 (100%) |
| member_remove | Reconfigured | 20/20 (100%) |
| member_remove | Final structure correct | 20/20 (100%) |
| rule_change | Reconfigured | 20/20 (100%) |
| rule_change | Final structure correct | 20/20 (100%) |
| transient_rule_change | No reconfiguration | 20/20 (100%) |
| transient_rule_change | Final structure correct | 20/20 (100%) |
| disappear | Retired | 20/20 (100%) |
| disappear | Finally absent | 20/20 (100%) |
| never_present | No false CREATE | 20/20 (100%) |
| never_present | Finally absent | 20/20 (100%) |

Across all null-target windows (60 disappearance windows + 100 never-present windows), the observed false CREATE rate was **0/160 (0%)**.

## Independent test-set observations

Mean candidate test accuracy by scenario:

| Scenario | Mean |
|---|---:|
| stable | 0.9797 |
| member_add | 0.9797 |
| member_remove | 0.9797 |
| rule_change | 0.9797 |
| transient_rule_change | 0.9797 |
| disappear | 0.6907 |
| never_present | 0.4982 |

Mean persistent-relation test accuracy where a persistent relation existed:

| Scenario | Mean |
|---|---:|
| stable | 0.9797 |
| member_add | 0.9188 |
| member_remove | 0.9188 |
| rule_change | 0.7870 |
| transient_rule_change | 0.7870 |
| disappear | 0.8235 |
| never_present | not applicable (no relation was created) |

Persistent-relation coverage was 100% for stable, member-add, member-remove, rule-change and transient-change scenarios; 60% for disappearance (the first three of five windows); and 0% for never-present.

The lower persistent accuracy during member/rule changes reflects the controller retaining the old structure while a new candidate is pending its second confirming window. This is the intended confirmation latency, not a candidate-discovery failure. It also exposes a real trade-off: conservative confirmation reduces transient false reconfiguration but temporarily preserves a stale relation.

## Interpretation

The run supports a narrow conclusion: under this bounded synthetic Boolean grammar, sample size, noise level and seven predeclared scenarios, the two-window evidence-gated controller correctly handled stable relations, member changes, rule changes, a one-window shock, disappearance and a null world in all 20 seeds per scenario.

It does **not** establish open-world relation discovery, causal discovery, learned transition policies, robustness to arbitrary environments, or general intelligence. The scenarios and transition schedule are predeclared; candidate discovery still enumerates a bounded 2/3-feature truth-table grammar. The 20 seeds per scenario are an initial validation scale, not a substitute for broader distributions, confidence intervals and multiple-comparison controls.

## Next research question

E02-I2 should separate relation identity from structure version and test lineage-aware KEEP / MODIFY / SPLIT / MERGE / SUSPEND / REACTIVATE / REPLACE / RETIRE decisions. It must use hidden identity ground truth only for post-hoc scoring and compare against exact-signature, Jaccard, embedding-similarity and bipartite-matching baselines.
