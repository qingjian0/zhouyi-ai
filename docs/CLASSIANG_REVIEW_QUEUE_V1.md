# 类象主动审阅队列 v1

## 目的

将当前监督式文本跨度模型的未审阅候选转化为**有来源、有精确字符偏移、可复核的人工审阅队列**，帮助建立真实 Gold 标注集。它是学习闭环中的数据采集工具，不是自动标注器。

## 运行

先用已有的类象文本数据训练并保存检查点，再生成审阅队列：

```bash
python -m prototype.classiang_learning DATASET.json \
  --checkpoint artifacts/classiang-text.json \
  --report artifacts/classiang-text-report.json

python -m prototype.classiang_review_queue DATASET.json \
  --checkpoint artifacts/classiang-text.json \
  --output artifacts/classiang-review-queue.json \
  --max-items 200 --max-per-domain 50 \
  --max-per-group 10 --max-per-observation 3
```

每个队列项目保留 observation、subject、domain、source、group、原文跨度、精确证据引用、模型建议、各类别分数、熵、分数间隔及模型检查点摘要。选择按归一化熵降序、分数间隔升序，并对领域、来源组和 observation 设置上限，避免队列被单一来源垄断。

## 审阅与标签边界

- 队列项目初始状态固定为 `pending_review`。
- `suggested_annotation` 仅是模型建议；不能直接写入 Gold、训练集或负例集。
- 人工确认后，按既有 `TextRecord` / `append_reviewed_feedback` 数据协议提交完整审阅事件。
- 只有明确审阅为负的跨度才能进入 `negative_annotations`；未审阅跨度始终是 unknown。
- 已有精确正例和已审阅负例跨度会从队列排除；部分重叠跨度保留，以便审阅边界差异。

## 分数解释

`normalized_entropy` 和 `score_margin` 只用于同一检查点下的相对排序。当前朴素贝叶斯 softmax 分数未经校准，不是正确率、真实性或因果置信度。队列不自动接受、拒绝或修订任何类象假设。

## 预算与复现

每条记录的候选跨度数量受 `max_candidates_per_record` 约束；超限记录会被明确写入 `skipped_records`，不会静默截断。输出包含模型 SHA-256、稳定 review item ID、队列 SHA-256、候选数、选择策略和跳过原因。相同数据、模型与参数产生确定性相同的队列。

## 验收边界

单元测试只验证跨度来源、偏移、确定性、多样性预算与标签隔离。真正的类象能力仍须由许可清晰、独立人工标注、来源族隔离的真实多域 Gold 集验证。
