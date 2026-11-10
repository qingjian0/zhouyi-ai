# E10-A Split 语义统一与验收矩阵（2026-11-11）

状态：独立研究补充文档。综合 PR #42（label-blind participant-group split）、PR #45（object-overlap audit）及本分支的 source-group 派生样本审计。未修改其他分支代码，未运行测试。

## 1. 先把四种“隔离”拆开命名

当前讨论中容易把 group-disjoint、source-instance-disjoint 和 object-disjoint 混为一谈。它们不是同一个保证。

| Track | 隔离单位 | 允许跨 Support/Query 重用 | 能回答的问题 |
|---|---|---|---|
| A-P：Participant-set group | `(relation_symbol, unordered participants)` | 对象可重用；不同 participant set 可共享对象 | 已知对象上的新参与者集合/上下文组合 |
| A-S：Source-instance group | 一个基础实例及其全部派生观测 | 对象可重用；同源派生样本不可跨集合 | 对未见基础实例的关系应用，避免正例/近失变体近重复泄漏 |
| A-O：Object-disjoint | 对象 ID 集合 | Support/Query 对象必须互斥 | 未见对象上的关系迁移 |
| A-C：Connected-component-disjoint | 对象—观测二部图的连通分量 | 任意对象或观测关联链路不可跨集合 | 更严格的实体隔离 |

当前 PR #42 实际实现的是 A-P，不是 A-S/A-O/A-C。PR #45 已指出 A-P 不保证对象互斥；本审计补充 A-S 也尚未保证。

## 2. A-S：为什么 source provenance 不能由 participant set 代替

v2 生成器以一个基础 `role_objects` 实例派生 positive、context-negative 和 role-near-miss。role-near-miss 会替换一个参与者，因此它与基础正例的 participant set 不同。

PR #42 的 `_group_key` 只读取 relation symbol 和排序后的 participant IDs。于是：
- positive 与 context-negative 通常进入同一个 A-P group；
- role-near-miss 通常进入不同 A-P group；
- 独立洗牌 A-P groups 时，同一基础实例的派生观测可能分到两侧。

这是一条高相关样本跨集合通道。它不等同于标签泄漏，但会使“基础实例隔离”声明不成立。

**最小修复**：生成器在每个基础实例创建时生成 evaluator-only `source_group_id`，其所有派生 observation 共享该 ID。Splitter 以 source_group_id 为 A-S 的分配单位；source_group_id、template_id、role map、violation 均不得进入 learner payload。不能在 task adapter 中通过参与者重叠猜测 source provenance。

必须测试：同一 source_group 的正例、上下文负例、所有 near-miss 必须全部落在同一分区；即使 near-miss 的 participant set 不同也成立。修改 evaluator labels/violations/template IDs 不得改变 source-group assignment。

## 3. A-O：不能事后过滤跨对象观测

A-O 的正确构造顺序应是：

1. 在潜在世界生成阶段，将对象池分成 disjoint 的 Support pool 与 Query pool。
2. 在两个对象池中分别实例化同一声明机制的观测。
3. Support learner payload 只包含 Support 对象及其属性、带标签观测。
4. Query learner payload 只包含 Query 对象及其属性、无标签观测。
5. evaluator 在分区后检查 object-ID 交集为空，并记录每侧对象、关系、正负例覆盖。

不能先用共享对象生成全部观测，再删除跨分区记录：这种事后过滤会改变样本分布，且容易造成覆盖偏差。

需要明确：Query 对象属性可作为预测输入提供给 learner；但 Query object IDs 和属性不能同时出现在 Support object table。所谓 object-disjoint 是身份互斥，不是把 Query 输入属性也隐藏。

## 4. A-C：连通分量隔离与生成器可行性

构造二部图 (G=(O\cup R,E))：
- (O)：object IDs；
- (R)：observation IDs；
- 若 observation 的 participants 包含 object，则连接对应边。

按连通分量分配 Support/Query，能保证不存在共享对象的跨边界关联链路。分量不足时应返回 `UNSPLITTABLE` 或 `INSUFFICIENT_COMPONENTS`，不能退化成 A-P 后仍标记 A-C。

当前生成器会在多个基础实例、near-miss 和关系模板间复用对象，因此 A-C 可能只有很少连通分量。必须先测量 component-size 分布；若形成一个巨大分量，应调整生成器为多个独立 object shard/world shard。

## 5. 统一验收不变量

所有 track：
- Support/Query observation IDs 不相交，且并集等于源 observation IDs；
- Query outcome、valid、violation、template/family/source-group/role map/seed 不可递归出现在 learner payload；
- evaluator label mutation 不改变 learner payload bytes，也不改变 label-blind partition assignment；
- 每条 observation 恰好映射到一个 evaluator truth；
- seed、split policy、失败 episode 和所有排除原因均记录。

A-P：
- 同一 relation symbol + unordered participant set 不跨集合；
- 报告跨集合 object overlap 数和比例。

A-S：
- 同一 source_group_id 不跨集合；
- 报告 source groups 数、每组 observation 数分布。

A-O：
- Support object IDs 与 Query object IDs 交集为空；
- 每个对象的全部关联观测均在同一侧；
- 报告对象数、关系数、正负例覆盖和不可评估 episode 比例。

A-C：
- 每个 connected component 只属于一侧；
- 报告 component 数量、最大分量占比及可分割 episode 比例。

## 6. 统计与能力声明

- 观测行不是独立统计样本；置信区间应以 episode/world seed 为聚类单位。
- A-P/A-S/A-O/A-C 应分别报告，不得挑选最容易通过的一条作为整体结论。
- A-P 高分不等于对象迁移；A-S 高分不等于对象隔离；A-O 高分仍不等于 relation-family OOD。
- 跨 episode 机制迁移是独立 Track B；关系族 OOD 是独立 Track C。
- 即使 A-C 通过，也不能单独证明开放环境概念形成或新原语发明。

## 7. 实施优先级

P0：在生成器 truth 中增加 source_group_id，并实现 A-S；保留 A-P 作为现有对照。
P1：增加对象交集审计和 A-O 独立对象池生成。
P2：计算 A-C 连通分量可行性；若不足，改生成器而不是放宽定义。
P3：在上述 split 语义稳定后实现有限 DSL identifiability oracle 和 learner baselines。

本文件是协议统一与静态审计，不代表以上实现或测试已经完成。
