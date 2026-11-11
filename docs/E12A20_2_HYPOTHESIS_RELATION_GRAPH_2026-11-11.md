# E12-A20-2：类型化假设关系图

状态：确定性关系图构建器首版；只表达可证明的结构关系，不自动决定哪个假设为真。

## 节点

### HypothesisNode

- hypothesis_id / query_id / scope；
- partial assignments（变量和值）；
- 使用的因子 ID；
- 明确关联的 evidence IDs；
- parent IDs（派生 lineage）；
- 可选 competition_set_id。

### EvidenceNode

- evidence_id / evidence_ref；
- query_id / scope；
- kind：OBSERVATION、MEASUREMENT_RECEIPT、SIGNED_EVALUATOR_RECEIPT；
- 可选内容摘要 digest。

注意：kind 和 evidence_ref 只是类型化引用。该图构建器不验证签名、不验证 receipt 内容，也不把引用本身当作已认证事实。必须由上游 A8/A10/A11 验证器完成验证后再接入。

## 边语义

| 边 | 方向 | 生成条件 |
|---|---|---|
| SUPPORTS | Evidence → Hypothesis | Hypothesis 显式列出该 evidence ID，且 query/scope 一致 |
| CONTRADICTS | Hypothesis ↔ Hypothesis（规范化为一条边） | 同一 query/scope 对同一变量给出不同值 |
| REFINES | Specific → General | 同一 query/scope，specific assignment 是 general 的严格超集 |
| ALTERNATIVE | Hypothesis ↔ Hypothesis（规范化为一条边） | 同一 query/scope 且 competition_set_id 相同 |
| DERIVED_FROM | Child → Parent | child 显式列出 parent ID |

CONTRADICTS 与 ALTERNATIVE 不等价：前者是共享变量上的逻辑不兼容；后者只表示同一竞争集合中的候选，不保证逻辑互斥。REFINES 是信息/约束更具体，不等于更正确。

## 安全与确定性

- evidence 和 hypothesis ID 全局唯一。
- 不允许跨 query/scope 的 evidence 或 parent lineage 偷渡。
- 未知 evidence/parent、重复变量赋值、lineage cycle 均 fail closed。
- 输入节点顺序不影响规范化图输出。
- 没有证据引用就不会自动生成 SUPPORTS。
- 不从 embedding 相似度推导逻辑冲突。
- 不根据能量或边数自动把候选升级为事实。

## 局限

- 只支持离散变量的部分赋值；连续约束和概率区间未实现。
- contradiction 只检查同名变量的显式赋值冲突；跨变量逻辑冲突需要约束求解器。
- competition set 由上游指定，构建器不自动猜测任务意图。
- 没有图数据库、增量更新、置信度传播或冲突消解策略。
- SUPPORTS 只表示显式证据关联，不代表证据足够或独立。
- 不对假设节点进行排序，也不选择唯一 winner。

## 下一步

A20-3 将把 A20-0 因子图与 A20-1 边缘概率接入此关系图：明确区分局部概率、候选排名、证据支持与 epistemic status；再实现冲突传播和候选集协调。之后才将 A16-A19 原语及阴阳/四象/八卦/六十四卦/太玄三分作为候选因子模板进行同预算比较。
