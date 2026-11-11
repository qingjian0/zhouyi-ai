# E13-C.3.4：上下文条件机制的主动轨迹选择

## 目的

C.3.3 已能在显式给定上下文的前提下传播和比较概率轨迹。本阶段进一步研究：在多个候选机制仍然成立时，选择哪条动作序列最有可能区分这些候选，同时严格遵守授权、风险和成本边界。

## 方法

对候选机制 (M_i)、初始状态 (s_0)、固定上下文 (c) 和候选动作序列 (q=(a_0,ldots,a_{T-1}))，分别计算完整轨迹分布：

[
mathcal{T}_i(q,c)=left(P_i(s_0),P_i(s_1mid q,c),ldots,P_i(s_Tmid q,c)ight)
]

候选对之间逐步计算总变差距离，并对时间步、候选对取平均，形成有限样本的轨迹分歧分数：

[
D(q)=rac{1}{|pairs|T}sum_{i<j}sum_{t=0}^{T}TV(P_i^t,P_j^t)
]

实现采用精确 Fraction。它是候选预测分歧，不是 Bayesian EIG，也不是观测后的真实信息增益。

## 安全与成本顺序

1. 未授权查询直接拒绝。
2. 超过硬风险阈值直接拒绝。
3. 超过成本预算直接拒绝。
4. 任一候选缺失转移行/上下文支持，则该查询标记 UNKNOWN，不参与排名。
5. 只有通过上述门槛的查询才计算效用：
   (U(q)=D(q)-lambda_R R(q)-lambda_C C(q))。
6. 稳定平局按 query_id 排序。

风险权重不能覆盖硬风险门；高分也不能让未授权动作重新进入候选。

## 原型与边界

`prototype/e13_contextual_active.py` 提供候选、动作序列查询、逐候选轨迹预测、分歧计算、硬门过滤和确定性排序。

当前假设：
- 同一查询在所有候选模型中使用相同状态变量、初态和上下文编码；
- 查询列表由外部给出，尚未自动合成动作序列；
- 每个候选是有限离散精确概率系统；
- 上下文在一次 rollout 内固定；
- 观测噪声未进入本选择器；
- 不做 posterior update，不宣称 EIG；
- 轨迹分歧基于 latent state distribution，若真实观测通道不同，必须另行映射到 observation space 后再做决策。

## 测试

- 同一状态下 action a 对候选无区分，action b 可区分，选择 b。
- 未授权和超风险查询被硬拒绝。
- 任一候选缺失转移支持，查询变为 UNKNOWN。
- 零分歧时按 query_id 稳定打破平局。
- 风险/成本效用只在硬门通过后影响排序。

## 下一步研究

1. 将候选查询从手工枚举推进到有界动作序列生成，并防止组合爆炸。
2. 分离 latent mechanism disagreement 与 observation-channel disagreement。
3. 引入上下文分层的 held-out query 评估。
4. 为 PASS/MISMATCH/UNKNOWN 建立带 provenance 的 Evidence Ledger。
5. 只有在候选先验与观测似然可校准后，才研究真正的 Bayesian EIG。
