# E13-C.3.3：上下文条件概率机制与跨域轨迹验证

状态转移机制不总是无条件的。相同内生状态与动作可能因外生环境、任务阶段、资源约束或制度条件而产生不同转移。本阶段将条件变量从内生状态中分离，研究有限离散系统中的：

\[
P(s_{t+1}\mid s_t,a_t,c)
\]

其中一个 rollout 内的上下文 \(c\) 默认固定。若上下文本身会变化，必须另建上下文转移机制，不能由普通状态转移隐式修改。

## 数据模型

- `ContextualProbabilisticTransitionSystem`：状态变量、上下文变量、动作和条件转移行。
- `ContextualTransitionRule`：完整 context + action + state -> next-state distribution。
- `ContextualKernelMap`：显式状态变量/取值映射、上下文变量/取值映射、动作映射。
- `ContextualTrajectoryCase`：源/目标初态、源/目标上下文、动作序列。
- `validate_contextual_trajectory`：固定各自上下文，逐步传播并比较映射后的 latent distribution。

## 关键约束

1. Context variable 与 endogenous state variable 不可重名或混用。
2. 每条规则必须完整赋值所有状态和上下文变量；概率必须精确且归一。
3. 上下文在一次 rollout 内保持不变。
4. 跨领域 context mapping 必须显式、完整、双射；不根据名称、相关性或边际分布推断。
5. 上下文不对齐、动作/值映射缺失、目标上下文转移支持缺失均返回 UNKNOWN。
6. 每个时间步分别计算 exact total variation；任何局部分歧都不能被跨步平均掩盖。
7. PASS 只适用于给定上下文、初始状态和动作序列，不是全局机制等价或因果识别证明。

## 已加入的反例与测试

- 同一 state/action 在 hot 与 cold context 下转移不同。
- 一个 rollout 固定 context，验证多步转移没有悄悄切换条件。
- 源/目标上下文显式重命名映射后轨迹一致。
- 上下文值不对齐 -> UNKNOWN。
- 目标上下文转移支持缺失 -> UNKNOWN。
- 缺少 context variable mapping -> 拒绝验证。

## 易象研究接口（尚未实现为先验）

此处的 context 可以承载“时位/条件/势”的外部观测，但不应把卦象、五行或类象标签直接当成真实上下文变量。若后续引入易象结构先验，应比较：
- 无上下文结构先验；
- 随机置换的上下文分组；
- 通用上下文条件模型；
- 易象派生的分层/对偶上下文候选。

所有先验都必须在 held-out context 和跨域迁移上接受消融；若只提高训练拟合或降低 UNKNOWN 率却增加错误 PASS，则属于负结果。

## 范围边界

这是有限离散、精确有理数的上下文条件机制 oracle，不是开放世界上下文发现器。它不学习潜在上下文，不推断未观测混杂，不支持连续上下文、时间变化上下文、上下文后验不确定性或真实世界因果结论。
