# E12-A5-2b：稀疏非连续高阶关系候选发现

日期：2026-11-11  
阶段：研究原型  
上游：E12-A5-2a max-statistic permutation；A5-1 residual diagnosis

## 研究问题

从固定相邻 pair 扩展到任意稀疏 feature subset：能否发现例如 `(a,c,e)` 这样的非连续三元组合，并在 OOF/prequential 残差上表现出 pairwise 方法无法表达的交互关联？

## 本阶段候选语法

对任意特征子集 `S=(f_1,...,f_k)`，其中 `2 <= k <= max_order`：

1. 每个数值特征仅使用自身取值构造等频分位切分边界（feature-only quantile edges）。
2. 每条记录映射为该子集的离散联合签名 `s_S(x)`。
3. 对训练视图中出现的每个签名提出精确联合单元谓词：
   `MATCH(S, s) = 1[s_S(x)=s]`
4. 分别检验 `MATCHED_ERROR` 与 `UNMATCHED_ERROR` 两种方向。
5. 用 balanced accuracy 对残差标签排序，并保留匹配/不匹配两侧的证据 ID。

子集枚举使用 schema 顺序的组合，而不是相邻窗口，因此会自然考察 `(a,c,e)`、`(a,b,d)` 等跳过中间特征的结构。

## 关键性质

- 这是显式的高阶交互候选：联合签名可以表达单个特征或任意低阶 pair 无法表达的组合状态。
- 分位边界只依赖 feature values，不读取残差标签、Gate 或 Test。
- 每个候选都保存特征子集、联合签名、边界、方向、分数和两侧 evidence IDs。
- `skipped_positions` 用于记录子集在 schema 顺序中跳过了多少中间位置。
- `max_order`、`max_subset_count`、`max_candidate_evaluations` 显式限制搜索。
- 任一预算耗尽时返回 `BUDGET_EXHAUSTED` 和空诊断，不返回部分 top-k 结果。

## 复杂度

令 F 为特征数、K 为 max_order、N 为记录数。子集数上界为：

`sum_{k=2..K} C(F,k)`

每个子集需构造 N 个签名；候选数量由每个子集实际出现的联合签名数决定。候选评估上限由 `max_candidate_evaluations` 控制。该预算是逻辑候选评分次数，不代表 CPU 指令、内存字节或 wall-clock。

## 验证设计

测试使用三位 XOR/parity 交互：

`residual = a XOR b XOR c`

每个 `(a,b,c)` 状态重复采样，使任意两特征的联合状态对 residual 不提供超越 0.5 的 balanced accuracy，而三元联合签名能表达高阶交互。另验证：

- 任意非连续子集可被搜索；
- 二阶和三阶候选可在同一任务上比较；
- 子集预算和候选预算 fail closed；
- 固定输入时排序确定；
- evidence IDs 和 prediction provenance 保留；
- 拒绝 in-sample prediction。

## 解释边界与下一步

**这仍然是有界的候选语法，不是开放式原语创造。** 当前只使用 numeric quantile bins + exact joint-cell predicate。它可能对稀疏状态敏感，也可能过拟合；候选排序不是显著性检验，不能仅凭高 balanced accuracy 宣称发现真实结构。

下一阶段应当：
1. 为 subset/quantile/signature 的完整搜索族实现 max-statistic 或合适的条件置换校正；
2. 用独立 Gate 验证候选，锁定 Test 只用于最终评估；
3. 比较 pairwise、三元、四元、稀疏任意子集在 XOR、交互、噪声、OOD 任务上的 sample efficiency、coverage、abstention 和复杂度；
4. 加入更有表达力但受预算约束的组合算子，如 AND/OR、关系组成和多尺度离散签名；
5. 与随机子集、相邻窗口、全量子集及易象启发式先验作容量匹配消融。

当前原型只做 Train-view 残差关联提议，不具备因果解释能力，也不实现 block/cluster permutation。
