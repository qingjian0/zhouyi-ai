# E12-A17：类型化关系图与组合原语发现

日期：2026-11-11  
阶段：研究原型 / 需独立基准验证

## 目标

E12-A16 从观测 atom 集合中发现稀疏合取。本阶段把搜索对象扩展为有向、类型化关系路径，使候选原语能够表达：

- 有方向的二元关系：`Agent --supports--> Object`
- 有序组合关系：`Agent --supports--> Object --transforms--> State`
- 状态变换可用显式关系标签表示，但标签本身不自动意味着因果。

## 实现

`prototype/e12a17_typed_relation_graph_discovery.py` 提供：

1. 类型化节点、带标签有向边和图观测的数据结构；
2. 从实际观测图枚举长度受限的有向路径 motif；
3. 对每个 motif 估计 outcome 条件分布；
4. 使用训练集 log-likelihood gain 减去近似结构码长；
5. 使用独立 validation split 检查 held-out gain；
6. 使用候选数、路径长度、最小支持度和复杂度预算约束搜索；
7. 使用 canonical serialization + SHA-256 生成稳定 motif ID 和数据集摘要；
8. 保存 parent refs 与 grammar version，供后续 lineage 系统接入。

## 与易象/太玄结构的关系

阴阳二态、四象四态、八卦状态、六十四卦以及太玄三分结构，未来可以作为**候选语法生成器**，提供有限的状态类型、关系模板或转移模板。

本阶段不把任何传统符号直接映射为固定语义，也不把卦象/三分标签当作训练 gold label。传统语法必须与通用关系语法在相同数据、候选预算、参数预算和评估协议下比较，并通过消融确认是否提供增益。若无增益，应允许拒绝或淘汰该语法。

## 重要边界

- 有向关系不等于因果关系；本原型只发现预测性共现路径。
- 节点类型和关系标签是观测 schema，不是天然语义。
- 当前只搜索长度 1..N 的简单有向路径，不搜索任意分叉 DAG、超图、环、时间窗口或连续状态。
- 训练/验证划分按 observation ID 排序，可能受 ID 设计影响；正式实验必须使用预注册且不可由 learner 修改的 split manifest。
- MDL 复杂度是工程近似码长，不是已证明最优的 universal code。
- 在大量候选上反复调参仍可能污染 validation；正式结论必须保留 locked test。
- 多个 motif 之间的等价性、包含关系和多重比较校正尚未实现。
- A17 不签发 evaluator receipt、不改变 A7 epistemic status；证据必须继续走 A8 firewall、A9/A10 receipt 和 A7 lifecycle。

## 验收

专项测试覆盖：两段有向类型路径发现、方向/关系标签保留、无信息图拒绝、预算截断确定性、非法端点拒绝、重复 observation ID 拒绝、复杂度预算拒绝。

CI 通过只说明实现与合成测试满足当前契约，不说明真实任务性能优于 Transformer 或 A16。

## 下一步

1. 建立 A16 atom-conjunction 与 A17 typed-path 的同数据配对比较。
2. 增加随机图、关系反转、节点重命名、类型置换和 OOD 关系组合测试。
3. 增加分叉结构与状态转移的独立语法，不将所有结构硬塞入路径枚举。
4. 引入预注册 split manifest、locked test 和多重假设校正。
5. 比较通用语法、阴阳二态、四象、八卦和太玄三分语法；严格匹配搜索预算并执行消融。
