# E02-I2-E：隐藏身份基准（预注册版）

## 目标与边界

本基准只评估**候选关系到历史身份的解析层**。候选生成由受控合成生成器提供，因此本实验不能证明端到端自主关系发现能力。

生成器保留潜在身份标签供评估器事后审计；匹配器只接收历史 `RelationVersion` 和观测到的 `RelationCandidate`。候选 ID 使用随机种子生成的 opaque ID，不编码身份或事件类型。

## 场景

每个场景默认 50 个独立种子：

1. `stable`：结构保持不变。
2. `role_permutation`：成员顺序置换，但成员-角色语义配对不变。
3. `member_drift`：同一身份成员小幅变化，抽象规则签名保持不变。
4. `same_members_new_semantics`：成员相同但规则不同，正确身份应是新身份，不得错误继承旧身份。
5. `overlapping_independent`：两个独立身份共享成员，测试全局一对一分配。
6. `temporary_dropout`：某窗口没有观测候选；缺失本身不产生 RETIRE 决策。
7. `indistinguishable`：两个历史身份在全部可观测特征上完全相同，正确输出只能是 ABSTAIN。

## 防泄漏合同

- `hidden_truth` 只保存在 `HiddenIdentityEpisode` 的评估字段。
- `match_candidates` 的调用只传 `candidates` 与 `history`，不传隐藏标签。
- candidate_id 不含 identity_id、场景名或事件类型。
- 阈值固定为 `min_score=0.70`、`min_margin=0.05`；本轮不使用 Test 结果调参。
- 历史身份 ID 对匹配器可见，这是身份解析问题的必要输入；隐藏的是候选对应哪个历史身份的真值。

## 基线

- Exact signature
- Member Jaccard
- Role-aligned similarity
- Hungarian one-to-one assignment

Jaccard 在“同成员、不同规则”场景中的错误匹配是预期的负面基线结果，不是推荐行为。

## 指标

报告 identity precision / recall / F1、false merge、正确弃权、已知身份漏匹配、歧义强制匹配、弃权覆盖率，并按场景拆分。

对 `indistinguishable` 场景，不能用强制匹配准确率衡量；唯一正确动作是弃权。对 `temporary_dropout`，只统计缺失观测，不将其算成身份匹配成功或退役成功。

## 执行

```bash
python -m unittest tests.test_e02i2_hidden_identity -v
python -m prototype.e02i2_hidden_identity --seeds 50 --start-seed 7000
```

CI 使用 30 seeds/场景作为回归运行；正式研究结果应使用预注册种子清单、更多独立种子、置信区间和锁定测试集。

## 当前限制与下一步

- 本基准尚不评估多窗口事件裁决、SPLIT/MERGE 推断、证据继承或端到端候选发现。
- 当前候选生成器是 oracle-controlled，不能把身份匹配结果外推为关系发现能力。
- 需要后续 I2-C 增加事件裁决基准，I2-D 单独评估谱系边与证据 provenance。
- 如果修改匹配器或阈值，应使用新的种子范围和独立锁定测试集重新评估。
