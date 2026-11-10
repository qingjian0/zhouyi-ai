# E09-B0.2：Prequential Runner（预测先行的批量重拟合基线）

日期：2026-11-11  
状态：新增实现与测试；尚未执行 CI，不宣称通过。  
基础分支：`research/e09-nongradient-learning-2026-11-10`

## 本次新增

- `prototype/e09_prequential.py`：提供 `predict_and_commit -> reveal -> revise` 状态机。
- `tests/test_e09_prequential.py`：覆盖预测先于标签揭示、无 commit 不得 reveal、重复操作拒绝、修订因果顺序和成本记录。
- 每条预测记录 observation ID、模型版本、预测/拒答状态与步骤序号。
- 每次揭示只关联一个先前预测；证据追加复用现有追加式账本。
- 每次修订保留前后结构快照、模型版本、训练样本数和候选评估数。

## 关键命名边界

本实现的修订模式固定标记为 `BATCH_REFIT`。每次 `revise()` 都调用现有 `EvidenceLedger.fit()`，后者把所有未争议训练证据重新交给 `CounterexampleRuleLearner.fit()`。

因此，本次完成的是**严格时间顺序的 prequential 评测外壳 + 可计量的批量重拟合对照臂**，不是增量算法本身，也不宣称在线学习已实现。它解决“不能把训练后回放准确率冒充预测前性能”的评测漏洞。

## 已知限制

- 账本与预测提交仍为进程内存结构，未实现崩溃恢复或跨进程事务持久化。
- `bootstrap()` 是已知历史训练集入口；测试流中的标签只能通过先 commit 后 reveal 加入。
- 目前只有 BATCH_REFIT 一种修订策略；下一阶段需要新增增量候选维护臂，并与冻结模型、周期性重放、批量重拟合等同预算比较。
- 目前只统计候选评估数与训练样本数，不代表真实 wall-clock 或峰值内存测量。

## 验收门槛

1. 所有预测在对应标签 reveal 前提交，且 commit 不可覆盖。
2. 无 commit 的 reveal、无 reveal 的 revision、重复 reveal/revision 均拒绝。
3. 结构修订必须引用已揭示证据。
4. prequential 指标仅由提交时预测与随后揭示标签计算。
5. 报告明确标记 BATCH_REFIT，不能将其称为增量学习。

## 后续研究

增量臂必须避免在每次更新时扫描全量历史样本；至少要有可复现的候选状态缓存、反例局部失效索引、规则 lineage，以及每次更新的增量计算计数。若最终结构与 batch baseline 不同，应分析顺序敏感性；若相同，也要比较达到该结构所需的边际成本。
