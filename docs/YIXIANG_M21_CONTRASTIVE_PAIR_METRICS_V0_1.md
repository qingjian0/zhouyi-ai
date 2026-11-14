# M21 成对类推迁移评估指标 v0.1

## 1. 动机

M20 的 8 组成对样例刻意让同一组中的两个案例具有不同预期裁决。如果只看逐案例准确率，系统可能学会对一组中的两例都输出同一标签，掩盖它没有识别关键差异的问题。M21 增加成对评估，不替代 M8 的四态分类指标。

## 2. 指标

- pair_exact_accuracy：一组两例均预测正确的比例。
- decision_flip_sensitivity：预期裁决不同的两例，预测是否也能区分。
- collapsed_pair_count/rate：两例被预测成同一决策的组数与比例。
- pair_selective_coverage：两例均非 abstain 的组比例。
- pair_selective_risk：在完整作答的组中，至少一例预测错误的组比例。

缺失预测按 abstain 处理；不将部分答题的 pair 算作完整覆盖。所有指标均需与 M8 的 per-class 指标、关系族分层指标和来源泄漏报告共同呈现。

## 3. 数据约束

- 每个 independence_group 必须恰好包含两例。
- 两例必须属于同一 split_group。
- 两例的预期决策必须不同，否则不是有效的对比对。
- prediction 不得重复或引用未知 case_id。
- 该指标不判断 gold 是否正确；只有输入标签质量决定评估上限。

## 4. 当前验证

原型：prototype/yixiang_contrastive_pair_metrics.py；专项测试 10 项；测试数据来自 M20 的 16 条 synthetic_fixture。完美预测、全 abstain、单侧缺失、同标签塌缩、重复/未知预测和 pair 数据结构错误均有覆盖。

## 5. 边界

成对敏感性不是普遍推理能力。M20 仅是模板化合成样例，M21 的分数只能描述模型对这些预设差异的响应。正式结论仍需要 M19 审定的古籍 gold、预注册划分、独立基线和 OOD 样本。