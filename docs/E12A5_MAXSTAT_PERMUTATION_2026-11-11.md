# E12-A5-2a：全扫描 max-statistic 置换检验

日期：2026-11-11  
阶段：研究原型  
上游：E12-A5-1 residual pair diagnosis

## 目标

A5-1 在全部数值特征对和阈值中搜索最高 balanced accuracy。若只对最终选中的候选做普通置换检验，会忽略“先搜索、再报告”的选择偏差。本阶段使用 max-statistic permutation：每次置换残差标签后，完整重跑所有 pair、threshold 和 polarity 搜索，并记录该次扫描的最大 balanced accuracy。

## 统计定义

给定 A3 的 OOF/prequential 残差标签：

`r_i = 1[\hat y_i \ne y_i]`

候选族 `H` 包含所有满足两侧最小支持度的：

- numeric feature pair `(f_j,f_k)`
- 相邻唯一绝对差值之间的阈值
- `HIGH_ERROR` / `LOW_ERROR` 两种方向

观测统计量：

`T_obs = max_{h in H} BA(h, r)`

第 b 次置换在固定特征和候选空间下打乱残差标签，保持错误/正确样本总数不变，并完整重新搜索：

`T_b = max_{h in H} BA(h, permute_b(r))`

全局 maxT p 值：

`p_global = (1 + count(T_b >= T_obs)) / (B + 1)`

每个已报告候选的 single-step maxT-adjusted p 值也使用同一组 `T_b`，比较其候选分数与全扫描 null maximum。这样控制的是整个已搜索候选族的 family-wise error，而不是未校正的单候选错误率。

## 实现约束

- 只接受 A5-1 已允许的 `prequential` 或 `out_of_fold` 残差视图。
- 不接收 Gate/Test；不读取 evaluator truth。
- 每次置换保留残差正负类数量。
- PRNG seed 显式输入，固定输入顺序下结果可复现。
- 显式计算总 threshold/polarity evaluations；超过预算返回 `BUDGET_EXHAUSTED`，不返回部分 p 值。
- p 值使用有限 Monte Carlo 修正，最小值为 `1/(B+1)`。
- 保存 prediction mode、A3 model version、evidence IDs、seed、B、扫描规模和 null maxima。

## 关键统计边界

**置换有效性依赖残差标签的可交换性（exchangeability）。** 对 IID 或合理随机化的 OOF 样本，普通标签置换可能成立；对时间序列、在线 prequential stream、同一实体重复观测、组内相关样本，直接打乱单条残差通常无效。此时需要按时间块、实体簇或任务组置换，并在设计中保留依赖结构。当前实现只提供 row-wise permutation，不能宣称适用于所有 prequential 数据。

本检验只控制当前固定候选族、固定阈值策略、固定数据集上的 family-wise selection error。它不证明候选关系具有因果性，也不保证跨数据分布稳定。若候选生成策略、特征筛选或参数在看到 Gate/Test 后调整，仍会引入额外选择偏差。

## 复杂度与预算

令 `S` 为所有 pair 的可用阈值数（含两个 polarity），置换次数为 `B`，候选评分总量为 `(B+1)S`。代码在运行前估算该数量，超过 `max_total_candidate_evaluations` 即 abstain。该预算计数是逻辑候选评分次数，不是 CPU 指令、wall-clock 或内存字节。

## 验证计划

- 强信号：固定 OOF 残差与单一数值 pair 强分离，应得到低 maxT-adjusted p 值。
- seed determinism：相同 seed、输入和参数产生完全相同 null maxima。
- full-scan 校正：每次 permutation 的统计量必须是所有 pair/threshold/polarity 的最大值。
- budget exhaustion：不得输出不完整置换的 p 值。
- provenance：拒绝 in-sample，保留 model version 和 evidence IDs。
- 后续对照：在 null 数据、相关特征、不同维度、不同样本量及时间相关数据上比较未经校正 A5-1 与 maxT 的 FWER、power 和 abstention。

## 当前限制

- 仅 row-wise residual-label permutation；尚无 block/cluster permutation。
- 仅数值 pair + 单阈值绝对差规则；不覆盖三元或任意稀疏高阶组合。
- Monte Carlo p 值精度由 B 决定；当前无置信区间报告。
- 结果为统计关联证据，不是因果归因或新原语发现。
- 测试文件是待 CI 执行的验证资产；提交后应单独确认 CI 状态。
