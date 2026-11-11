# TX-02D-0：计算预算与可信预测度量

日期：2026-11-11

## 计算预算定义

当前 learner 对每个 (query, candidate, support-row) 组合执行一次共享 MLP 评分。令编码维度为 D、隐藏宽度为 H，则输入维度 I=6D。隐藏层与标量读出层的前向乘加代理为：

MAC_row = H(6D + 1)

MAC_episode = support_size × query_count × candidate_count × H(6D + 1)

默认 candidate_count=K。工具按给定 episode 形状，选择不超过共同 forward-MAC 预算的最大整数 hidden size；低于最小模型成本则显式报错。

该代理只统计隐藏层点积和标量读出点积，不包含偏置加法、tanh、support 聚合、softmax、特征构造、内存访问、Python 开销、反向传播或优化器更新。因此它不是完整 FLOPs，也不是训练总成本。报告必须称为 forward-MAC proxy。

参数匹配和 MAC 匹配应并列报告。进一步研究应增加反向计算代理，并在固定软硬件环境下测量吞吐与峰值内存。

## 校准与拒绝预测

probability_metrics 提供多分类 NLL、Brier score、固定宽度 top-label ECE、准确率及非空分箱明细。ECE 默认 10 bins，必须报告分箱方案；它依赖分箱，不是无偏估计。

choose_abstention_threshold 在 validation 概率和标签上选择满足经验 selective-risk 上限时覆盖率最大的置信度阈值；apply_abstention 将低置信度预测标为 None（DEFER）。

阈值只能由 validation 选择，locked-test 只能在阈值冻结后评估。经验风险上限不是分布无关保证；验证集过小时可能得到零覆盖。正式报告还应提供完整 risk-coverage 曲线。

## 测试

运行：python -m unittest tests.test_tx02_compute -v

## 当前边界

TX-02D-0 的计算账本和校准工具现已接入实验 Runner，具体流程见下方 TX-02D-1。当前尚无任何表示优劣结论。


## Validation-only representation arbitration

The module also provides select_representation(). It consumes only per-family validation metrics and deterministically ranks by higher validation accuracy, lower NLL, lower forward-MAC estimate, lower parameter count, then family name. The selector is frozen before any locked-test labels are inspected. This is a baseline arbitration policy, not a learned meta-controller; its selection can overfit a small validation set and should be evaluated across independent outer seeds or nested splits.


## TX-02D-1：接入完整实验 Runner

`prototype/tx02_experiment.py` 已将基础工具接入 train/validation/locked-test 流程：

1. **计算匹配模式**：`compute_matched=True` 时，以共同 forward-MAC budget 选择各表示的最大合法隐藏层宽度；与参数匹配互斥。CLI 使用 `--compute-match`，可用 `--forward-mac-budget` 覆盖默认预算。
2. **概率评估**：每种表示均输出 Validation 和 Locked-test 的 accuracy、NLL、Brier、ECE。
3. **拒绝预测**：每种表示的阈值仅由 Validation 选择；Locked-test 报告 coverage、selective risk、deferred 数量及 risk-coverage 曲线。
4. **自适应表示**：先完成所有候选的 Validation 评估并冻结选择结果，再评估固定表示基线与已选策略；任何 Locked-test 指标都不会反馈给选择器。
5. **固定表示对照**：多种子 aggregate 同时报告每种固定表示与 `ADAPTIVE_VALIDATION_SELECTED` 的测试表现及所选家族。

### 运行方式

参数量匹配（默认）：

```bash
python -m prototype.tx02_experiment --cardinalities 3 --support-sizes 2 4 --seeds 11 29 47 --json
```

forward-MAC 匹配：

```bash
python -m prototype.tx02_experiment --cardinalities 3 --support-sizes 2 4 --seeds 11 29 47 --compute-match --json
```

### 关键解释边界

- MAC budget 是每个 episode 的前向代理预算；训练总代理按 train episode 数、epoch 数和每 episode MAC 估算，**不计反向传播**。
- 各家族的实际 MAC 可能因整数隐藏层宽度而低于预算；报告 delta，不声称精确相等。
- Validation 选择器目前是单次 holdout 上的确定性仲裁规则，不是可学习的元控制器。其结果可能对 validation 采样噪声敏感；必须跨独立外层 seed 报告选择频率与泛化表现。
- Locked-test risk-coverage 曲线只作最终描述；阈值不在 test 上调节。
- 这仍是有限仿射规则族合成实验，不代表自然语言或通用智能表现。


## TX-02D-2：有限样本拒绝风险校准

原先的拒绝阈值只约束 validation 上的经验错误率，样本很小时容易出现“只接受一个正确样本、经验风险为 0”的虚假安全感。现改为：

- 对每个置信度阈值，按完整同置信度组计算接受样本数与错误数。
- 计算单侧 Wilson score 上界（默认 z=1.95996，对应约 97.5% 双侧/95% 单侧常用正态临界值约定需注意：这里明确按单侧上界公式使用该 z）。
- 只有 Wilson 上界不超过目标风险时，才接受该阈值。
- 在满足约束的阈值中选择覆盖率最高者。
- 报告经验 selective risk、Wilson risk upper bound、接受数、覆盖率和 z 值。

这是有限样本保守校准启发式，不是任意分布漂移下的分布无关保证，也不能消除重复调参导致的选择偏差。小 validation 集合可能产生零覆盖；此时正确行为是 DEFER，而不是放宽测试集阈值。

测试：40 个高置信正确样本可被接受；另 40 个低置信错误样本被拒绝；单样本零错误的 Wilson 上界仍显著大于零。
