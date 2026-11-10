# E10-A1 有限机制 Oracle 与可识别性协议 v0.1（2026-11-10）

状态：设计规格；基于 v2 源码静态审查。未实现 oracle，未运行仓库测试，不构成实验结果。

目标：把“可识别”从生成器启发式检查提升为有限假设空间上的可验证结论，并为 support/query 任务提供精确判定基准。

## 1. 当前 v2 的准确边界

v2 的每条 learner-visible observation 含有 relation_symbol、participants、context、outcome。参与者列表被随机打乱。潜在模板保存 feature_key、role_values、context_key、required_context；实例真值保存 role_objects、valid、violation。

当前 learner_view 暴露全部 observation outcome，没有 support/query 拆分。因此不能将其直接作为 hidden-query benchmark 输入。

当前 identifiability_report 统计正例、每个角色的支持数、角色属性值是否不同、正例角色属性是否可见。这些是数据质量/必要条件检查，不是有限假设空间的唯一性证明。

## 2. 重要的语义边界：无序参与者只允许恢复角色集合

v2 对 participants 做随机排列，真值 role_objects 保留生成时角色顺序。若学习器只能看到无序 participants，且没有角色专属的外部结果通道，则 role slot 的绝对名称没有可观测意义。

因此 oracle 的等价关系必须把全局角色置换视为同一机制。当前任务可验证的是：
- 使用哪个属性键；
- 哪组互异属性值构成参与者角色集合；
- 哪个上下文键值门控关系；
- 关系元数与参与者集合约束。

不能把任意 role_a/role_b/role_c 的命名顺序恢复当作正确性要求。若未来要评估有向角色顺序，必须增加真正依赖角色位置的可观测结果/状态，并单独预注册。

## 3. 有限 DSL 定义

对每个 relation_symbol 独立枚举机制：

M = (r, k, f, V, c, q)

- r：可见关系符号；
- k：元数，来自该关系符号观测的参与者数量（仅允许固定元数模板）；
- f：对象属性键；
- V：大小为 k 的互异属性值集合，作为无序角色集合；
- c：上下文键；
- q：要求的上下文值。

预测规则：

predict_M(obs) = (arity(obs)=k) AND (context[c]=q) AND (multiset(attribute(obj,f) for obj in participants)=V)

若任一对象缺少属性键 f，候选机制对此观测的预测记为 UNKNOWN；正式主实验应先限定无缺失数据，缺失数据作为独立实验臂处理。不能把 UNKNOWN 默认为 false。

候选域只从 learner-visible support/query schema 的可见属性键、属性值、上下文键和值枚举；不得读取 TemplateTruth、InstanceTruth、seed 或生成器内部类别编号。

## 4. Oracle 枚举与三态结果

输入：relation symbol 的 support observations（含 outcome）、公开 DSL 边界和统一枚举预算。

1. 枚举合法候选 M。
2. 对每个 support 样本计算 predict_M。
3. 若预测为 UNKNOWN，则候选不满足“完全解释 support”的强版本；可在缺失实验臂另设三值逻辑版本。
4. 保留所有对每条 support 标签均一致的候选。
5. 按结构同构归并：角色值集合本身无序；若属性键/上下文键/值符号只是允许的全局双射重命名，比较 canonicalized mechanism。
6. 输出：
   - IDENTIFIABLE：恰有一个同构等价类；
   - AMBIGUOUS：多于一个同构等价类；
   - INCONSISTENT：零个等价类。
7. 保存候选数、等价类数、枚举预算、耗时和截断标志。若达到预算上限仍未枚举完，不得误报 IDENTIFIABLE，必须返回 BUDGET_EXHAUSTED。

Oracle 的唯一性只相对于该明示有限 DSL 成立，不能解释为现实世界机制唯一。

## 5. Query 的评测规则

LearnerTask：
- objects
- labeled support
- unlabeled query
- schema_version
- public DSL constraints（若任务事先公开）

EvaluatorTruth：
- query labels
- query violation
- latent mechanism
- oracle state / candidate equivalence classes
- source-group IDs 与生成审计信息

硬性不变量：
- support/query observation IDs 不相交；
- 同一个 base instance 产生的 positive/context-negative/role-near-miss 变体必须放在同一 split，避免近重复跨边界；
- query 的 outcome/violation/template ID/role mapping/base group ID 不进入 learner payload；
- 修改 evaluator truth 不改变 learner payload 的 canonical bytes/hash；
- 只有 IDENTIFIABLE query/episode 纳入结构恢复主指标；AMBIGUOUS 评价 abstention；INCONSISTENT 评价异常检测/拒答；
- 另行报告所有样本的 coverage，禁止只报告可识别子集准确率。

## 6. 必须构造的 Oracle fixtures

| Fixture | 构造方式 | 期望状态 |
|---|---|---|
| unique | 多个正例覆盖每个角色值，负例分别打破 context 与角色集合 | IDENTIFIABLE |
| role-permutation | 只改变真值 role slot 命名/排列，观测不变 | 同一等价类 |
| ambiguous-feature | 两个属性键在所有 support 上完全共变，但 query 上不同 | AMBIGUOUS |
| ambiguous-context | support 只出现单一 context 值，多个门控机制都解释 support | AMBIGUOUS |
| inconsistent | support 对同一完全相同可见条件给出冲突标签 | INCONSISTENT |
| missing-feature | 某 support 对象缺少候选属性键 | 主 DSL 中 UNKNOWN/拒绝候选 |
| budget-exhausted | 枚举空间超过固定预算 | BUDGET_EXHAUSTED |

尤其注意：若 support 中只有正例，候选机制通常存在大量超集/替代条件；必须让负例或反事实 query 区分竞争机制。生成器不应通过隐藏真值过滤掉这些歧义样本。

## 7. v2 生成器的额外审查点

- 生成器对每个 base positive 派生 context-negative 与 role-near-miss；随机切分 observation 会让高度相关变体跨 support/query。应在生成阶段保存 evaluator-only source_group_id，按组切分。
- context_values 应显式断言互异，避免随机碰撞使预期 context-negative 退化成正例条件。
- learner/evaluator 边界必须以序列化 payload 测试，而不是仅断言字段名不存在。
- 若未来启用属性缺失，当前二值 oracle 必须升级为明确三值逻辑；不允许把缺失当作负例。
- query 预测正确与机制结构恢复正确是两个指标；需分别评估。

## 8. 验收门槛

A1 Oracle 最小验收：
1. 七类 fixture 全部通过；
2. 角色置换等价性通过；
3. 同一潜在世界符号双射后 canonical mechanism 不变；
4. support/query 按 source group 隔离；
5. learner payload 对 evaluator truth mutation 不变；
6. Oracle 不访问任何真值字段；
7. budget exhaustion fail-closed；
8. 输出 oracle candidate/equivalence-class trace，便于复核。

只有这些门槛通过后，才把 A1 数据交给 E09 或 CPG-EI 学习器。有限 DSL Oracle 是评测器，不得作为被测学习器的标签捷径。

## 9. 研究结论边界

即使学习器在此任务上超过 lookup、nearest-neighbour 与固定模板基线，结论也只能是：在声明的有限关系机制 DSL 内，学习器能从 support 恢复可识别机制并泛化到 held-out query。

这仍不证明开放世界概念形成、未知关系原语发明或通用自主智能。
