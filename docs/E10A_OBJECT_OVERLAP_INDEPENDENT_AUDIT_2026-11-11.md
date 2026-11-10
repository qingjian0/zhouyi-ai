# E10-A 独立补充审计：Support/Query 对象重叠与泛化声明

日期：2026-11-11  
审计对象：PR #42 head `03f13b701009bac7d99efb6928e70bf298e46ad6`（基于 PR #37 task-view adapter）  
状态：静态审计与协议建议；未执行 CI；不宣称 benchmark 已验证

## 1. 摘要

PR #42 正确修复了一个重要问题：Support/Query group assignment 不再查看 evaluator labels；输入验证也比 v1 严格。

但当前 split 的隔离单位是：
`(relation_symbol, unordered_participant_set)`

它保证同一关系符号下、同一无序参与者集合的多条观测不会跨 Support/Query；它**不保证参与者对象本身互斥**。两个不同 participant set 可以共享一个或多个 object ID。不同 relation symbol 的组也可能包含相同对象。

这不是当前实现隐藏的错误：PR #42 的说明已经承认对象可能在 Support/Query 间重叠。真正需要解决的是实验命名和分轨，不能把 group-disjoint 误写成 object-disjoint。

## 2. 代码级判断

### F1. 当前 split 测试验证的是 group disjoint，不是 object disjoint

测试 `test_related_participant_groups_never_cross_partitions` 比较的是 relation symbol 与排序后的 participant set。它没有计算：

- Support 所有参与者对象 ID 的并集；
- Query 所有参与者对象 ID 的并集；
- 两者交集是否为空。

因此当前测试不能支持“对象隔离”或“新对象泛化”声明。

### F2. 对象属性表在两侧共享

Task 的 Support 与 Query 都返回完整 `objects` 列表。Query 没有 outcome 标签，但查询参与者的属性在 Support 侧也可能通过对象表和其他 Support 关系观测被学习器看到。

这适合测试“已知对象及其属性，在新参与者组合上应用关系机制”；不适合测试“对从未见过的对象发现角色”。

这两者是不同任务，应该分别报告。

### F3. 当前按 relation_symbol 分组，允许跨关系的对象复用

分组键包含 relation symbol，因此同一对象集合在 relation A 中进入 Query、在 relation B 中进入 Support 是允许的。若目标是测试多关系组合或共享对象的跨关系推理，这可能是合理设置；若声称跨对象泛化，则构成身份复用。

需要通过独立实验臂明确区分。

## 3. 建议建立三个不同的 E10-A split track

### Track A-G：Group-disjoint / known-object recombination

保留当前 PR #42 策略：
- 同一 relation symbol + participant set 的全部观测留在同一侧；
- 对象可在 Support 与 Query 复用；
- 测试新参与者组合、上下文与角色模式上的关系应用；
- 明确称为 group-disjoint，不称 object-disjoint。

这是当前 adapter 最适合支持的声明。

### Track A-O：Object-disjoint / unseen-object transfer

新增真正对象互斥的 split：
- Support 与 Query 参与者对象集合必须不相交；
- 每个对象的所有关联观测必须被分配到同一侧；
- 先按对象分区，再在各侧构造观测；不能事后简单丢弃交叉记录而改变样本分布；
- evaluator 只用于事后检查分区，不参与分配；
- 记录对象数、关系数、正负例覆盖和不可评估 episode 数。

如果对象—观测二部图形成一个巨大连通分量，说明当前生成器无法提供有意义的对象互斥 split；应改生成器，创建独立对象池或独立 world shard，而不是强行切分。

### Track A-C：Connected-component disjoint / no shared-entity leakage

将对象与观测构造成二部图：
- 一侧为 object IDs；
- 另一侧为 observation IDs；
- participant 关系形成边；
- 以连通分量为最小分配单元，整个分量只进入 Support 或 Query。

此设置比简单对象划分更严格，可避免任何共享实体链路跨越两侧。若 component 数量不足，应明确报告 benchmark 不支持该 split。

## 4. 必须新增的测试与指标

1. `support_object_ids ∩ query_object_ids == ∅`（仅 A-O/A-C）。
2. 对所有对象关联观测做闭包检查，不能有对象跨分区。
3. 对所有 relation symbols 检查跨关系对象复用。
4. 对对象属性表做 Query-only 与 Support-only 可见性审计。
5. 分别报告 group-disjoint、object-disjoint、component-disjoint 三种 split。
6. 报告每个 split 的有效 episode 比例、正负样本覆盖、对象数量、关系模板数和拒答率。
7. 使用相同 seed-block 和生成器预算比较，不得只报告最容易成功的 split。

## 5. 重要解释边界

- A-G 高分：支持已知对象集合上的新组合应用。
- A-O 高分：支持在未见对象上迁移关系结构（仍需控制机制/模板泄漏）。
- A-C 高分：支持更严格的实体连通块隔离。
- 跨 episode 机制迁移必须另设 Track B；relation-family OOD 必须另设 Track C。

即使 A-O 通过，也不能单独证明开放世界自主关系发现。还需要未知规则族、符号置换、可识别性 oracle、反例和同预算基线。

## 6. 协作边界

本 PR 仅增加独立审计文档：
- 不修改 PR #37 或 PR #42；
- 不修改 E10 generator、E09、E11、E02 或 main；
- 不运行、取消或重跑其他 AI 的 CI；
- 本文是 split 语义与后续实验建议，不是实现或性能结果。
