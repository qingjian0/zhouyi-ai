# E12-A15：多假设竞争与主动区分测量

日期：2026-11-11  
状态：可执行原型；后验是注册假设集合内的相对权重，不是校准真值概率。

## 研究问题

遇到反例时，不允许直接把现有原语判错或就地改写。至少保留以下竞争解释：

1. 环境发生变化，但原语机制仍成立；
2. 原语适用范围过宽，需要 scope specialization；
3. 原语组合/关系结构错误；
4. 测量链路存在噪声；
5. 当前候选集合不完备，无法解释观测。

第五类是必要的开放集假设：有限候选集合内的最大后验不代表真实解释一定在集合中。当前原型把它作为显式候选类别，但尚未实现自动生成未知机制。

## 数据结构与边界

- `CompetingHypothesis`：不可变 hypothesis id、解释类型、候选版本引用、先验权重、每个测量方案的 outcome likelihood。
- `MeasurementPlan`：协议、目标摘要、参数摘要、预计成本和硬成本上限。
- `CompetingHypothesisPortfolio`：绑定一个 anchor candidate version 与一个 scope；所有竞争假设共享相同 outcome space。
- 所有预测分布在注册时校验归一化、有限且非零；测量方案必须被所有假设显式预测。
- 候选假设与测量方案冻结后，语义改变应创建新版本，不得覆盖旧定义。

## 主动测量选择

对当前假设分布 (P(H))，对每个可执行测量 (M) 计算：

[
IG(M)=H(H)-sum_o P(omid M)H(Hmid o,M)
]

选择满足预算约束的最大 (IG(M)/cost(M))。确定性 tie-break 为 utility、信息增益、measurement id。

若没有方案满足成本约束，返回 `BUDGET_EXHAUSTED`；若所有方案的信息增益不超过阈值，返回 `NO_DISCRIMINATING_MEASUREMENT`，不伪造确定答案。测量 request 绑定 candidate version、scope、scope digest、protocol、target 和 params。

## 证据更新

只接受 E12-A11 Ed25519 签名的 `SELECT` receipt。验证签名、request digest、executor/key、candidate、scope、scope digest、protocol、target、params 与成本。确认 outcome 属于已注册 outcome space 后才提交 replay guard，再执行 log-space Bayes 更新。

后验更新记录 receipt lineage。重复回执、篡改回执、跨 scope 回执和未知 outcome 均拒绝。非 SELECT 结果不构成测量证据。

## 修订规则

`propose_revision` 只创建新的不可变 CandidateVersion，version + 1，并记录 parent_refs。它不会自动批准、替换或部署候选，也不会删除旧证据。是否采纳修订仍需独立训练、验证集和 gate。

## 易象先验的使用边界

阴阳、四象、八卦、卦变、五行等可用于提出候选解释类型、关系结构或测量方向，但不得直接抬高 evidence status。要把易象映射加入本模块，必须给出明确的预测分布、适用 scope、对照解释与可区分测量；否则只能作为 hypothesis generator，不能作为证据。

## 关键限制

1. Bayes posterior 只在当前有限假设集合和给定似然模型条件下成立；漏掉真实机制会造成封闭世界过度自信。
2. 先验和 likelihood 需要预注册、版本化并经独立校准；当前原型不做校准保证。
3. 观测依赖、选择偏差、漂移和似然失配会破坏朴素更新的解释。
4. A11 replay guard 仍是内存实现；生产需要持久化、事务原子性和 key registry。
5. 目前不自动写 A7 epistemic status，也不推进 workflow stage；相对 posterior 不是支持/反驳证明。
6. 尚未实现 hypothesis birth/death、开放集 novelty detection、候选复杂度惩罚与多 scope 迁移。

## 测试

`python -m unittest tests.test_e12a15_competing_hypotheses -v`

覆盖信息增益选择、无区分测量弃答、预算耗尽、签名 receipt 更新、篡改、跨 scope、未知 outcome 与不可变版本修订。
