# 类象学习后端训练入口 v1

## 能力边界

本入口把仓库已有的 N0.10 LearnableSROK 训练器接入可复现的数据集、训练/验证切分、评测报告和模型检查点流程。它训练的是**带人工/上游标注特征的结构关系模型**，不是从原始文本、图片或视频中自动取象的端到端模型。

- 输入特征、角色、约束、目标结构和证据 ID 必须由数据集提供方负责。
- 训练集与验证集按固定 seed 随机切分；验证集不参与梯度更新。
- 验证指标为结构角色绑定 exact-match；搜索预算耗尽或模型弃权不计正确。
- 输出检查点使用现有 SROK 完整性校验格式，并在训练结束时执行加载往返检查。
- 数据集 SHA-256、检查点 SHA-256、训练损失和验证指标写入报告。
- 这不是语义正确性证明；合成数据指标不能替代真实领域 Gold 数据评测。

## 数据格式

UTF-8 JSON，schema_version 固定为 1：

```json
{
  "schema_version": 1,
  "feature_dim": 2,
  "roles": [
    {"name": "source", "allowed_types": ["source"], "required_tags": ["reviewed"]},
    {"name": "target", "allowed_types": ["target"], "required_tags": ["reviewed"]}
  ],
  "examples": [
    {
      "role_candidates": [
        [
          {"node_id": "s1", "node_type": "source", "features": [1.0, 0.0], "tags": ["reviewed"], "evidence_ids": ["ev-1"]}
        ],
        [
          {"node_id": "t1", "node_type": "target", "features": [0.0, 1.0], "tags": ["reviewed"], "evidence_ids": ["ev-2"]}
        ]
      ],
      "target_ids": ["s1", "t1"]
    },
    {
      "role_candidates": [
        [
          {"node_id": "s2", "node_type": "source", "features": [0.8, 0.1], "tags": ["reviewed"], "evidence_ids": ["ev-3"]}
        ],
        [
          {"node_id": "t2", "node_type": "target", "features": [0.1, 0.8], "tags": ["reviewed"], "evidence_ids": ["ev-4"]}
        ]
      ],
      "target_ids": ["s2", "t2"]
    }
  ]
}
```

实际训练至少需要两个样本；建议使用独立对象/来源构造验证集，避免同一对象或同一证据泄漏到训练与验证两侧。

## 运行

```bash
python -m prototype.classiang_training DATASET.json \
  --checkpoint artifacts/classiang-srok.json \
  --report artifacts/classiang-training-report.json \
  --validation-fraction 0.2 --seed 17 --epochs 100
```

输出：
- 检查点：可由 `LearnableSROK.from_checkpoint_json(...)` 加载。
- 报告：训练/验证样本数、训练损失、验证 exact-match、弃权数和数据/检查点摘要。

## 后续集成约束

该训练器目前是类象引擎可调用的结构学习后端，不会自动把权重转换成 `ClassHypothesis` 或修改类象符号规则。只有在独立验证证明收益后，才应将预测结果接入迁移门控；不得把模型分数直接解释成校准置信度或语义真理。
