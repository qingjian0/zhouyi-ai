# E13-B3-D：分歧驱动观测与版本空间更新

## 研究目的

当有限候选空间中存在多个结构上可行的类象映射时，系统不应立即挑选一个。应当寻找能让候选产生不同预测的观测，再用真实观测收缩候选集。

## 数据流

1. 每个候选由独立 simulator/evaluator 对同一 query 生成预测。
2. 只接受覆盖当前全部候选、每候选每 query 恰好一条的预测集合。
3. 以候选两两预测不同的比例计算 query disagreement。
4. 选择 disagreement 最大的 query；并列时按 query_id 稳定排序。
5. 收到实际观测后，只保留预测与观测完全一致的候选。
6. 若所有候选都被排除，返回 CONTRADICTION，不凭空发明替代候选。

## 当前实现

- `prototype/e13_b3_active.py`
- `tests/test_e13_b3_active.py`
- `tests/test_e13_b3_oracle.py`

当前 disagreement 使用 pairwise disagreement ratio，不使用熵，避免在标签类别分布和概率校准缺失时伪装成概率信息增益。它是有限候选的区分性指标，不是完整 Bayesian expected information gain。

## 安全边界

- 预测由外部 evaluator 提供；选择器不读取隐藏标签。
- 不完整预测集合不参与 query 排名。
- 不接受重复预测。
- 证据只能过滤候选，不能直接改写候选结构。
- 候选全灭时显式报告矛盾，等待新观测或候选空间扩展。
- 该方法假定观测标签可靠；未来应加入测量噪声、代价、风险和反事实干预设计。

## 验收范围

测试覆盖最大分歧 query 选择、确定性并列处理、不完整预测拒绝、证据筛选、全候选冲突，以及 B3 枚举结果与独立小规模排列 oracle 一致。

这些测试验证算法实现和契约，不证明开放世界类象发现能力。
