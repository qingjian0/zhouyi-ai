# E13-B3-D：分歧驱动观测与版本空间更新

## 目的
多个结构可行候选并存时，不立即挑选唯一映射；由独立 simulator/evaluator 为每个候选预测同一 query，再选择最能区分候选的 query，最后用真实观测收缩版本空间。

## 算法
1. 每个 query 必须有覆盖全部候选的预测，每候选恰好一条。
2. disagreement = 候选两两预测不同的比例。
3. 选择 disagreement 最大的 query；并列按 query_id 稳定排序。
4. 观测后保留预测值与观测完全一致的候选。
5. 若全部候选被排除，返回 CONTRADICTION，不自动编造新候选。

## 实现
- `prototype/e13_b3_active.py`：预测分歧评分、query 选择、证据过滤。
- `tests/test_e13_b3_active.py`：最大分歧、并列稳定性、不完整预测、版本空间更新和矛盾。
- `tests/test_e13_b3_oracle.py`：与独立小规模排列 oracle 对照 B3 枚举。

当前采用 pairwise disagreement ratio，不把它冒充 Bayesian expected information gain。预测必须来自独立 evaluator；选择器不读取隐藏标签。

## 限制
该实现只处理有限候选、确定性预测和可靠观测。尚未建模噪声、测量成本、干预风险或概率校准，也不证明开放世界语义类象能力。
