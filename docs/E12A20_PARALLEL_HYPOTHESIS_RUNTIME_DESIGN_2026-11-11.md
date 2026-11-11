# E12-A20：并行假设图推理运行时（架构研究设计）

日期：2026-11-11  
状态：设计提案，尚未实现；不代表已验证的模型能力。

## 1. 为什么从 A19-C 转向 A20

E12-A16～A19 已形成从开放集候选原语、类型关系图、分叉/汇合 motif，到统一候选比较和多规则判别的实验链。A19-C 的 softmax/logistic 模型可以联合使用多个二值规则特征，但它仍然是一个判别器：

- 它不显式表示一个假设由哪些实体、关系、约束和证据构成；
- 它不表示多个假设之间的支持、冲突、包含或互斥关系；
- 它不能直接回答“哪些局部关系组合成了当前解释”；
- 它不是一个非自回归生成/推理架构，也没有与 Transformer 做过公平比较。

A20 的任务是把候选规则提升为可组合、可审计的结构化假设，并在多个假设之间并行计算和协调。

## 2. 核心对象

### 2.1 变量与状态域

每个待推断变量定义为：

`Variable = (id, type, domain, provenance, scope)`

domain 是有限或可枚举状态集合。第一阶段只支持离散域；连续变量以后通过离散化/概率分布接口扩展。

### 2.2 因子

因子是变量子集上的局部约束或软关系：

`Factor = (id, variable_ids, relation, potential, evidence_refs, cost)`

因子分为：
- HARD：违反时该假设不可行；
- SOFT：违反时增加能量/代价；
- EVIDENCE：来自观测证据的似然或支持度；
- PRIOR：来自通用结构语法或易象候选语法的先验。

任何因子必须声明来源、适用 scope、版本和是否可学习。易象因子只能作为可比较、可消融的候选先验，不得被标记成事实真理。

### 2.3 假设

`Hypothesis = (partial_assignment, active_factor_ids, evidence_refs, contradictions, energy, status)`

假设可以是不完整赋值。未知变量不能被默认补成确定状态。每个派生结论都必须能够回溯到变量、因子、规则版本和证据。

### 2.4 假设关系图

节点为假设，边类型至少包括：
- SUPPORTS：一假设提供另一假设的支持；
- CONTRADICTS：两假设不能同时成立；
- REFINES：更具体的假设约束更少的上位假设；
- ALTERNATIVE：互斥或竞争解释；
- DERIVED_FROM：保留推导 lineage。

图关系不能仅由 embedding 相似度决定；必须由显式变量/约束冲突或可追溯推导建立。

## 3. 统一评分

对候选赋值 h 定义能量：

`E(h) = E_evidence(h) + λ_r E_relation(h) + λ_c C(h) + λ_p E_prior(h)`

其中：
- `E_evidence`：观测与假设的负对数似然；
- `E_relation`：软关系约束违反代价；
- `C(h)`：描述长度/复杂度惩罚；
- `E_prior`：可选先验代价。

HARD 因子违反时直接判为 INFEASIBLE，不通过有限大惩罚伪装成可接受候选。

不同因子量纲必须校准。不能把任意分数直接相加后称为概率。只有经过校准的能量/似然模型才允许输出概率；否则只输出排序分数和不确定状态。

## 4. 非自回归并行推理流程

每一轮采用同步批处理：

1. **Proposal**：从输入解析、A16～A19 原语和已注册语法中并行提出局部假设。
2. **Local evaluation**：各因子独立计算局部消息/代价，不等待自然语言 token 逐个生成。
3. **Conflict detection**：并行检测硬约束冲突、证据矛盾和 scope 不匹配。
4. **Message aggregation**：按变量/假设 ID 做确定性聚合，更新边缘分数或候选能量。
5. **Prune / expand**：根据预算、复杂度、信息增益和不确定性保留或扩展候选。
6. **Convergence check**：检查候选排序、边缘状态和能量变化是否收敛；达到预算上限时显式返回 BUDGET_EXHAUSTED。
7. **Evidence arbitration**：仅把有来源、可验证的观测证据用于结论；模型内部消息不伪装成外部证据。

轮次内部的因子计算可以并行；跨轮迭代是同步更新。A20 不要求把所有计算都变成并行硬件执行，但要求推理语义不依赖 token-by-token 自回归展开。

## 5. 输出接口

输出为结构化结果集合，而不是必须按 token 顺序生成的内部推理轨迹：

`InferenceResult = (ranked_hypotheses, abstentions, conflicts, evidence_trace, budget_report)`

必须支持：
- 多个并列候选；
- 明确的 UNKNOWN / AMBIGUOUS / INFEASIBLE；
- 每个结论的 evidence trace；
- 预算耗尽时返回部分结果和停止原因；
- 自然语言生成仅作为独立 renderer，不计入核心推理器能力。

若接入外部 Transformer/LLM 做解析或文字润色，必须分别报告其输入输出和消融结果，避免把外部模型能力归功于 A20。

## 6. 与传统自回归和其他非自回归方法的比较

至少设置：
1. AR Transformer/LLM：相同输入、输出任务、数据拆分与可用计算预算；
2. NAR slot/set predictor：并行预测固定结构槽位；
3. Graph neural baseline：同一节点/边信息；
4. Factor-graph baseline：相同变量域和因子；
5. CPG-EI A20：原语发现、候选假设图和证据协调。

比较指标：
- exact match / task accuracy；
- log loss、Brier、ECE 等校准指标；
- coverage-risk 曲线与 abstention；
- OOD 组合泛化；
- 推理延迟、吞吐、峰值内存、算力预算；
- 对输入/节点/边顺序置换的不变性；
- 证据追溯完整率；
- 约束冲突检出率和误报率。

参数量、训练数据、外部工具访问和推理预算必须报告。不能仅凭“并行”推断速度会快几倍。

## 7. 易象与太玄语法接入原则

易象和太玄进入 A20 的方式是**候选状态域/因子模板**，不是固定答案：

- 阴阳：二值互补域；
- 四象：二位组合形成的四状态；
- 八卦：三位二值结构；
- 六十四卦：六位二值结构；
- 卦变：状态转移因子；
- 太玄三分：三值类别域或三元状态组合候选。

关键区分：太玄三值状态的 radix-3 编码，不等于 E02-B 的模 3 加法群运算。类别状态 0/1/2 不自动具有加法、循环或群结构；只有任务数据和干预支持时才能引入相应运算。

公平对照：
- 通用可学习状态域；
- 随机状态编码；
- 置换语义标签；
- 易象/太玄结构编码；
- 去掉关系因子的消融；
- 固定先验与可学习先验。

所有方法使用同一数据、拆分、候选数、参数量和计算预算。

## 8. 分阶段实现

### A20-0：最小离散约束引擎
目标能力：二值/三值变量、unary/binary/ternary factors、partial assignment、hard/soft constraints、deterministic synchronous update、evidence trace、budget and abstention。

当前已提交的 A20-0 仅实现其中的**有限域完整赋值精确枚举参考求解器**：支持 HARD/SOFT/EVIDENCE/PRIOR 因子、硬约束拒绝、证据引用、top-k、顺序不变性和预算耗尽状态。partial assignment、同步消息更新、近似推理和实际并行执行尚未实现。详见 [A20-0 实现说明](E12A20_0_FACTOR_GRAPH_REFERENCE_2026-11-11.md)。

### A20-1：多假设竞争图
目标能力：SUPPORTS / CONTRADICTS / REFINES / ALTERNATIVE、假设 lineage、证据去重和局部冲突传播。

前置基础已实现同步 Sum-Product 信念传播：复用 A20-0 因子语义，在 log-space 更新变量/因子消息，具备 damping、收敛判据和硬预算。核心完整 CI #42954798842 已通过；精确边缘校准基准仍在 CI 验证。当前是单进程同步参考实现，不等于多核并行。

**A20-2 类型化假设关系图已提交首版**：显式区分证据节点与假设节点，支持 SUPPORTS、CONTRADICTS、REFINES、ALTERNATIVE、DERIVED_FROM；按 query/scope 隔离，拒绝跨 scope 证据迁移和 lineage cycle。该图只建立结构关系，不排序、不裁决真伪，也不把 evidence reference 本身当作已验证证据。

### A20-2：结构语法接入
- A16/A17/A18/A19 候选规则适配成因子模板；
- 通用、随机、置换和易象语法同预算对照。

### A20-3：多任务/OOD 基准
- 二元 XOR 与高阶 parity；
- Z3 关系和未见符号映射；
- 组合 holdout；
- 关系 holdout；
- 状态转移 holdout；
- 噪声、缺失观测和分布漂移。

### A20-4：与 AR/NAR/Graph/Factor baselines 公平比较
在前三阶段稳定后再开展，不提前宣称性能优势。

## 9. 验收与证伪条件

- 输入变量、因子和候选顺序随机置换，不改变规范化输出。
- 任一硬约束冲突必须阻止该假设被标记为可行。
- 删除/修改证据后，相关结论的 lineage 和评分必须按预期变化。
- 改变隐藏测试标签不能改变 learner-side proposal 或 prediction commit。
- 同一输入与预算下重复运行必须确定性或明确记录随机源。
- 预算耗尽不能静默返回“已收敛”。
- 易象/太玄先验若没有在多 seed、OOD、消融和同预算比较中稳定增益，不得保留为默认先验。
- 若 A20 在同等预算下不优于简单图/因子基线，应保留更简单的基线，不强行复杂化。

## 10. 当前边界

本文是架构设计，不是性能结果。A19-C 仍是候选规则特征上的判别模型；A20-0 已有小规模精确参考求解器，但尚无同步消息传递、近似推理或并行执行引擎。任何速度、泛化、认知能力提升都必须等待后续实现和对照实验。
