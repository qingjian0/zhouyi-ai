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

这是 TX-02D 的计算账本和校准工具基础，尚未接入完整实验 runner，也没有实现 validation 驱动的表示选择器。尚无任何表示优劣结论。
