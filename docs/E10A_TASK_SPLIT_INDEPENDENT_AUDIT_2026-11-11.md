# E10-A Task Split 独立实现审计（2026-11-11）

状态：对 `research/e10a-task-split-hardening-2026-11-11` 的静态源码审计。本文未修改该分支代码，未运行该分支测试；本分支仅增加审计文档。

审计对象：
- `prototype/e10a_task_split.py`
- `tests/test_e10a_task_split.py`
- `prototype/e10a_latent_generator.py`
- `docs/E10A_TASK_SPLIT_HARDENING_2026-11-11.md`

## 1. 结论

该实现比早期 label-aware split 明显更严谨：Query 组分配由固定 seed 和结构键决定，不读取标签；Query 通过显式 allowlist 序列化；Evaluator ID 重复、标签类型错误、learner/evaluator 标签不一致等情况会 fail-closed。

但当前实现仍不能保证“同一个基础实例的所有派生样本永不跨 Support/Query”。原因是它用：

`(relation_symbol, sorted(participants))`

作为分组键。生成器为每个基础正例产生：
- 一个正例；
- 一个相同参与者集合、不同 context 的负例；
- 每个角色槽位最多一个替换参与者的 role-near-miss 负例。

前两类共享 participant set，会被放在同一组；role-near-miss 会替换一个参与者，因此 participant set 通常改变，会被分到另一个组。两个组随后独立洗牌，故同一基础实例的近失变体可能进入 Support，而其正例进入 Query，或反过来。

这会留下高相关样本跨边界泄漏通道。它不是 query label 泄漏，但会使评测不再满足“按 base instance/source group 隔离”的预注册要求。

## 2. 具体证据链

生成器 `generate_episode()` 对每个 `role_objects` 先构造 positive 与 context-negative，再循环替换各角色对象构造 `role_constraint_<slot>` near-miss。每条 case 独立生成 observation ID；`InstanceTruth` 当前只保存 observation_id、template_id、role_objects、valid、violation，没有 base-instance/source-group 标识。

Task splitter 的 `_group_key()` 只返回 relation symbol 与排序后的参与者集合。因而它无法识别由同一基础正例派生、但参与者集合发生变化的 near-miss。

现有测试 `test_related_participant_groups_never_cross_partitions` 只验证“完全相同的无序参与者集合”不跨边界，不能捕获同一 base instance 的替换对象近失例。测试没有构造或断言 source-group 完整性。

## 3. 建议的最小修复

不要从 learner-visible 特征推断派生关系。将 provenance 作为 evaluator-only truth：

1. 在生成器内部为每个基础 `role_objects` 实例分配唯一 `source_group_id`（例如 episode-local opaque ID）。
2. 同一基础实例产生的 positive、context-negative、所有 role-near-miss 均携带同一个 source_group_id。
3. 只把 source_group_id 写入 `audit_view()` / evaluator truth；绝不进入 learner support、query、manifest 的 learner-visible 部分。
4. splitter 先验证每个 observation 恰好对应一个 truth/source_group，再按 source_group_id 分组与分配。
5. manifest 记录 evaluator-only 的 group ID hash / group counts；不要暴露原始 group IDs 给 learner。
6. 将当前 participant-set grouping 保留为次级审计键，而不是主隔离键。

如果暂时不能改生成器，临时保守方案是按模板或整个 episode 分组；但这会显著减少有效独立组，不适合作为最终 Track A 评测。

## 4. 必须增加的回归测试

- 同一 source_group 的 positive、context-negative、每个 near-miss 必须全部在 Support 或全部在 Query。
- 特意构造两个 observation：相同 relation symbol、near-miss 替换一个 participant；即使 participant set 不同，也必须保持同组。
- 改变 evaluator 的 valid、violation、role_objects、template_id，不得改变 source-group 分配或 learner payload。
- Query 不得含 source_group_id、template_id、family、seed、violation、outcome；递归扫描嵌套对象。
- source_group 缺失、重复映射、未知 observation 或多 truth 映射必须 fail-closed。
- 不同 source_group 即使 participant set 相同，也应由显式 policy 决定是否合并；不能让隐式 key 语义代替协议。
- 统计每个 split 的 source-group 数、观测数、正负标签数；支持集单类别时必须显式报告，不得回看 Query 标签后重抽样。

## 5. 另两个边界

### 5.1 这仍是 episode-local group holdout，不是对象隔离

即使按 source_group 修复，Support 与 Query 仍可能复用相同对象，或部分重叠对象。对象属性对角色识别可能被 Support 直接揭示。因此应把评测名称限定为“source-group-disjoint within-episode induction”，另设 object-disjoint / participant-overlap-controlled track。

### 5.2 Label-blind 不等于统计独立

随机按组分配避免直接读取标签，但同一 episode 的对象池、模板和属性分布共享，组间仍存在依赖。报告应以 episode/seed 为统计单元，避免把每条 observation 当成独立样本计算过窄置信区间。

## 6. 当前可支持的声明

若现有 task splitter 测试通过，只能支持：
- 对已知 learner/evaluator 输入结构的严格校验；
- 基于 relation symbol + unordered participant set 的 label-blind 分组；
- Query 行显式去除 outcome；
- Support/Query observation ID 完整划分。

在 source_group 修复和验证前，不能声称基础实例的全部派生样本被隔离。更不能声称对象 OOD、跨 episode 迁移、关系族 OOD 或开放环境自主发现。

## 7. 下一步顺序

P0：source_group provenance 与 split 绑定，并增加 near-miss 跨组反例测试。
P1：递归 learner-payload canary、object-overlap 指标和按 episode 聚类的统计报告。
P2：再实现有限 DSL Oracle，明确 IDENTIFIABLE / AMBIGUOUS / INCONSISTENT / BUDGET_EXHAUSTED。

本审计不要求推翻 task splitter；建议在现有实现上做小幅、可验证的 provenance 修复。
