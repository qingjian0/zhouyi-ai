# N0.7：认知算子代数、状态动力学与稀疏计算内核

日期：2026-11-11  
状态：研究设计与原型规格；不是已实现算法、已训练模型或性能结论。  
上游：N0.6 PR #177，head `8ee34c46e121742c07cf8673e10702d6a58f7965`

## 0. 本轮目标

N0.6 提出了 TRLW（Typed Relational Latent Workspace）。N0.7 将它进一步数学化，回答：

1. 什么是一个可计算、可版本化的认知状态？
2. 什么是可组合、可学习、可拒绝的认知算子？
3. 如何在不穷举所有元素组合的前提下发现非相邻关系？
4. 如何让多个候选分支共享计算、避免复制和坍缩？
5. 如何控制连续潜在更新与离散结构编辑的收敛、震荡和停止？

本轮建议把首个计算内核定义为：

**SROK：Sparse Relational Operator Kernel（稀疏关系算子内核）**

SROK 不是新的大模型名称，而是 TRLW 的最小可验证计算核心。它可以由 CPU 程序、小型神经网络和确定性约束求解器组成。先验证结构算法，再决定是否需要训练大模型。

## 1. 研究结论：不要把认知状态压成一张普通图

普通图的二元边不足以直接表达多前提推导、角色、时间、证据归属和不确定性。也不能把所有内容压成一个连续向量，否则会丢失可审计的结构边界。

定义工作空间：

`W = (V, H, X, Z, B, P, C, Σ, ν)`

- `V`：类型化对象槽位；
- `H`：关系超边集合；
- `X`：离散结构状态与角色分配；
- `Z`：连续潜在表示；
- `B`：候选分支及其差分；
- `P`：证据来源与版本引用；
- `C`：硬约束和软约束；
- `Σ`：类型签名、算子签名和 schema；
- `ν`：工作空间、索引、算子和策略版本。

关键原则：连续表示负责相似性和可学习参数；离散结构负责可验证组合；来源和版本负责证据追溯。三者不能互相替代。

## 2. 类型化关系超图

定义 `G=(V,H,I,τ_V,τ_H,ρ)`：

- `V` 是节点集合；
- `H` 是超边集合；
- `I ⊆ V × H` 是节点与超边关联关系；
- `τ_V` 给出节点类型；
- `τ_H` 给出关系类型；
- `ρ(v,h)` 给出节点在该关系中的角色。

每条超边必须定义：
- 关系类型；
- 参与节点及角色；
- 方向性与极性；
- 时间有效区间；
- 作用域；
- 来源引用；
- 约束和版本。

例如一个多前提结论不是简单 A→D，而是一个超边：
`{A:premise_1, B:premise_2, C:context} -> D:conclusion`。
其 AND 语义属于单个 justification 内部；多个独立 justification 支持同一结论则属于 OR。该语义继续遵守 ZPCM N0.3，不允许把来源相关的重复证据误当成独立支持。

## 3. 状态分层：不要把置信度、真值和支持度混成一个数

每个认知断言至少区分：

- truth/status：当前状态，如 supported、review、conflict、retracted；
- support：有哪些有效 justification；
- uncertainty：模型对当前结构/解释的不确定程度；
- confidence：特定预测器的校准输出；
- provenance：证据来源及共享祖先；
- validity：事实适用时间；
- knowledge time：系统何时获知或修订。

预测器输出 0.93 不等于事实真值为 93%。概率分数不能绕过证据契约或确定性约束。

## 4. 认知算子代数

### 4.1 算子规格

定义算子 `o`：

`o = (Sig_in, Sig_out, Pre, Post, Inv, T, Cost, Risk, EvidencePolicy, Version)`

- `Sig_in / Sig_out`：输入输出类型签名；
- `Pre`：前置条件；
- `Post`：后置条件；
- `Inv`：必须保持的不变量；
- `T`：状态变换；
- `Cost`：计算成本估计；
- `Risk`：潜在错误风险；
- `EvidencePolicy`：是否需要证据、证据级别和来源要求；
- `Version`：算子版本和训练数据版本。

算子是部分函数：输入不满足前置条件时，不得强行执行，应返回 NOT_APPLICABLE 或 NEED_MORE_EVIDENCE。

`T_o : W ⇀ W'`

对可学习算子，输出可包含多个候选：
`T_o(W) -> {(ΔW_i, score_i, trace_i)}`。
score 仅用于候选调度，不能自行确认为事实。

### 4.2 算子组合

`o_2 ∘ o_1` 只有在 `Post(o_1)` 与 `Pre(o_2)` 类型和约束兼容时才定义。

组合还必须检查：
- 不变量是否冲突；
- 证据范围是否保持；
- 时间和作用域是否兼容；
- 组合成本是否在预算内；
- 是否引入循环依赖。

不满足条件时组合失败，不能用向量相似度强行拼接。

### 4.3 易象类象算子族

将易象概念视为待学习的变换族，而非固定神秘标签：

| 算子族 | 结构作用候选 | 必须学习/验证的内容 |
|---|---|---|
| 取象 | 从观察提取结构角色和不变量 | 哪些特征是任务相关的 |
| 类象 | 对齐不同领域的关系结构 | 保持关系与辨别差异 |
| 变 | 改写局部状态或关系 | 触发条件、变换范围 |
| 互 | 从整体内部抽取子结构 | 非相邻选择与角色重组 |
| 错 | 在指定轴上反转/对照 | 哪些属性反转、哪些保持 |
| 综 | 视角、顺序或方向重组 | 可逆性与信息损失 |
| 应 | 建立远距离角色呼应 | 是否存在可验证关联 |
| 时 | 时间阶段和有效窗口变换 | 时间顺序、双时间语义 |
| 位 | 角色/层级/位置约束 | 角色类型和位置合法性 |

这些是操作假设，不是传统术语的唯一解释。每个算子都必须接受反例训练和消融检验；模型可以拒绝某次应用。

## 5. 学习型算子路由

不让所有算子都对所有节点运行。路由器根据任务、类型、结构特征和预算，产生候选算子：

`p(o | W,Q,b) = Router_θ(W,Q,b)`

执行流程：
1. 由类型签名过滤不可能的算子；
2. 由前置条件过滤不适用算子；
3. 学习路由器选择 top-k 候选；
4. 计算预计收益、成本和风险；
5. 运行算子并记录 delta；
6. 用约束验证器检查后置条件；
7. 把成功/失败信号反馈给路由器。

训练不能只依赖算子名称。路由器必须看到输入结构、可用证据、执行结果和失败类型。

## 6. 非相邻组合：稀疏候选发现而非全排列

如果活动节点数为 N，枚举所有子集是指数级；枚举所有 k 元组合也会快速失控。N0.7 禁止把“支持非相邻组合”实现成全量穷举。

建议两阶段：

### 阶段 A：候选召回
- 根据任务查询召回相关节点；
- 使用类型签名和角色需求筛除不匹配节点；
- 用关系依赖索引找可能互补的结构；
- 使用可学习路由器产生稀疏候选；
- 保留多种结构模板，不局限于单条关系路径。

### 阶段 B：预算化组合选择
在候选池中构造组合，满足硬约束后排序。可研究 beam search、best-first、局部交换、分支定界和学习型提案的混合方案。

目标函数示意：

`Score(S)=Utility(S)-λ Cost(S)-μ Redundancy(S)-ρ Risk(S)`

并施加硬约束 `C_hard(S)=true`。该目标是候选搜索目标，不是真值函数。

必须包含：
- 非相邻组合；
- 可跳过中间节点；
- 多前提 AND；
- 多解释 OR；
- 共享来源去重；
- 跨域类象；
- 反例与错误组合；
- 无解/欠定识别。

重要警告：NeurIPS 2025 的 NoRA 基准指出，很多系统把关系推理过度简化成路径组合，因而在更复杂关系结构上泛化不足。SROK 的基准必须包含非路径型结构，不可只用多跳路径任务证明能力。参考：https://proceedings.neurips.cc/paper_files/paper/2025/hash/167856a2bb094d44872c4a992bad49d0-Abstract-Datasets_and_Benchmarks_Track.html

## 7. 多分支共享：Persistent Base + Branch Delta

每个分支不能复制整个 W。定义：
`B_i=(base_snapshot, delta_i, score_i, status_i, parent_i)`

- 所有分支共享只读 base snapshot；
- delta 只记录节点/关系新增、删除标记、局部表示变化和假设差异；
- 分支可 fork、refine、compare、merge、prune；
- merge 必须检查版本、约束和证据兼容；
- 被 prune 的分支仍保留摘要与原因，以支持审计；
- 不能把不同假设合并成一个模糊平均向量。

分支调度应兼顾：
- 当前预期价值；
- 候选多样性；
- 与已探索分支的结构距离；
- 反证机会；
- 计算成本；
- 未解决约束的重要性。

避免单纯 top-k 分数造成 mode collapse。可用 diversity-aware selection，但多样性也不能凌驾于硬约束和证据质量。

## 8. 连续状态与离散结构的双动力学

TRLW 同时有连续潜在状态和离散结构编辑，两者不能用同一种收敛定义。

### 8.1 连续状态更新

`z_{t+1}=F_θ(z_t, G_t, Q)`

可研究残差/阻尼更新：
`z_{t+1}=(1-α)z_t+α Φ_θ(z_t,G_t,Q)`

若在指定范数和工作域内证明 `F` 是压缩映射（Lipschitz 常数小于 1），才可援引 Banach 固定点定理讨论唯一固定点和收敛。仅仅观察到损失下降或若干轮状态变化变小，不等于已经证明收敛。

### 8.2 离散结构编辑

结构编辑可采用有限状态、有限预算的事务式操作：
- 新增候选关系；
- 删除无效候选；
- 改变角色映射；
- 分裂/合并假设；
- 增补证据；
- 更新断言版本。

离散编辑可能来回翻转，不能依赖连续收敛条件。需要版本化、重复状态检测、编辑冷却/滞回、循环检测和最大操作预算。

### 8.3 混合收敛判据

停止条件不能只看 `||z_{t+1}-z_t||`。至少同时观察：
- 连续状态变化；
- 结构编辑数量与类型；
- 硬约束违反数；
- 目标能量/排序稳定性；
- 候选集合变化；
- 新证据的边际价值；
- 预算剩余。

输出状态区分 SOLVED、PARTIAL、UNDERDETERMINED、CONFLICTED、BUDGET_EXHAUSTED、NEED_EXTERNAL_EVIDENCE。

## 9. 全局约束与能量：分开硬约束和软偏好

候选结构的排序函数可写为：

`E(h)=E_local+E_global+E_provenance+E_uncertainty+E_cost`

但硬约束必须先行：
- 类型不兼容；
- 时间不可能；
- 作用域不匹配；
- 权限违反；
- 来源引用无效；
- ZPCM 版本冲突。

硬约束失败的候选不能通过降低能量“赎回”。软能量只对合法候选排序。

能量分数不等于事实概率。需要在留出集上做校准，报告 Brier score / ECE 等适合任务的指标，并对分布外输入检测失准。

## 10. 稀疏内核的复杂度预算

定义：
- N：活动节点数；
- E：活动超边数；
- K：每轮候选算子数；
- B：活跃分支数；
- D：潜在维度；
- T：更新轮数。

设计目标不是声称某个固定复杂度，而是让成本随活动子图和实际候选数增长，而不是随全部持久历史增长。

初步成本模型：
- 稀疏关系更新：目标约为 O((N+E)D)；
- 算子候选路由：取决于索引召回数与 K，而非全算子全集；
- 分支存储：base 一份 + 各分支 delta；
- 约束验证：按受影响依赖局部增量验证，必要时全局复核；
- 持久历史：由 ZPCM 管理，绝不直接全部载入工作集。

以上是实现目标和估算模型，必须由原型 profiling 验证。稀疏结构不保证总成本一定低：如果 E 接近 N² 或候选路由召回过多，优势会消失。

## 11. 学习闭环：SFT 覆盖原子能力，探索优化新组合

建议采用分阶段学习：

1. **原子能力覆盖**：监督学习基础算子输入、输出、前置条件和失败类型；
2. **复合轨迹训练**：训练算子在真实组合上下文中协同工作，而不只单独训练孤立算子；
3. **新组合探索**：用可验证奖励/反馈探索训练支持集之外的新组合；
4. **校准与拒绝**：学习不适用、证据不足、冲突和欠定；
5. **跨域迁移**：对类象算子做跨领域保持关系、辨别差异的训练。

ICML 2026 的研究指出，SFT 覆盖原子模块、RL 探索训练分布之外的新组合，可能比只训练孤立原子模块更有利于组合泛化。这支持“先覆盖、再探索”的实验方向，但不意味着必须采用 RL，也不证明本项目的算子设计有效。参考：https://proceedings.mlr.press/v306/kong26c.html

## 12. 原型规格：SROK-0

第一版不训练语言模型，先构建可复现的结构计算实验。

### 12.1 输入
- typed hypergraph；
- task query；
- evidence/provenance；
- operator registry；
- hard/soft constraints；
- compute budget。

### 12.2 输出
- candidate structures；
- selected operator sequence；
- branch deltas；
- constraint report；
- provenance trace；
- termination status；
- deterministic replay metadata。

### 12.3 最小组件
1. Schema / Type Checker；
2. Hypergraph Store；
3. Operator Registry；
4. Sparse Candidate Router；
5. Non-adjacent Composer；
6. Branch Delta Store；
7. Constraint Validator；
8. Energy Ranker；
9. Budget Controller；
10. Trace / Replay Recorder。

首版用确定性实现做基线；之后逐个替换路由器、算子参数和能量评分器为可训练模块。这样才能定位收益来自结构算法还是神经参数。

## 13. 基准任务与实验矩阵

必须包含：
- 多前提非路径型关系推理；
- 未见实体与未见关系；
- 未见算子组合；
- 非相邻元素组合；
- 角色映射和视角变换；
- 时间修订与冲突证据；
- 多条独立支持路径；
- 共享来源与重复证据；
- 反事实和最小反例；
- 欠定问题和拒绝；
- 新证据到来后的局部修订；
- 中断恢复和预算耗尽。

对照组：
A. 规则/约束求解器；  
B. 标准 GNN；  
C. 超图网络；  
D. 隐式/固定点超图网络；  
E. EpiGNN 等多路径关系推理方法；  
F. Transformer + RAG；  
G. SROK 确定性内核；  
H. SROK 学习型路由与算子；  
I. SROK 去掉易象类象先验的消融。

必须纳入 NoRA 或同等非路径型基准，避免只测路径任务。

指标：
- exact structural accuracy；
- constraint satisfaction；
- OOD composition accuracy；
- non-adjacent selection F1；
- calibration / abstention quality；
- evidence attribution accuracy；
- branch diversity / redundancy；
- incremental recomputation ratio；
- peak RSS / VRAM；
- CPU/GPU time；
- latency to first valid structure；
- total compute and energy where measurable。

## 14. 消融与失败判据

消融：
1. 去掉超边，只留二元边；
2. 去掉类型签名；
3. 去掉算子前后置条件；
4. 去掉稀疏候选路由，改全量枚举；
5. 去掉分支 delta，复制完整状态；
6. 去掉硬约束；
7. 去掉 provenance；
8. 去掉固定点/阻尼机制；
9. 去掉易象算子先验；
10. 仅用孤立原子算子训练，不用复合轨迹。

失败判据：
- 只在路径任务有效，在非路径型结构上失败；
- OOD 新组合不优于对照；
- 路由器只记住算子名称或领域表面词；
- 分支之间高度重复或错误合并；
- 固定点求解不稳定或成本高于显式有限迭代；
- 连续状态收敛但离散结构仍反复翻转；
- 证据归属或时间版本被算子破坏；
- 稀疏路由召回不足导致关键证据遗漏；
- 同等准确率下内存、延迟、能耗更差；
- 易象先验没有独立、可复现的增益。

## 15. 研究参考

1. Das et al., NeurIPS 2025, *When No Paths Lead to Rome: Benchmarking Systematic Neural Relational Reasoning*. https://proceedings.neurips.cc/paper_files/paper/2025/hash/167856a2bb094d44872c4a992bad49d0-Abstract-Datasets_and_Benchmarks_Track.html
2. Li et al., 2025, *Implicit Hypergraph Neural Networks: A Stable Framework for Higher-Order Relational Learning with Provable Guarantees*. https://arxiv.org/abs/2508.09427
3. Xiao et al., LoG 2022, *Sparse and Local Networks for Hypergraph Reasoning*. https://proceedings.mlr.press/v198/xiao22a.html
4. Khalid & Schockaert, ICLR 2025, *Systematic Relational Reasoning With Epistemic Graph Neural Networks*. https://proceedings.iclr.cc/paper_files/paper/2025/hash/6590cb829f5ffef50050f3e5845fbb4c-Abstract-Conference.html
5. Kong et al., ICML 2026, *From Reasoning Traces to Reusable Modules*. https://proceedings.mlr.press/v306/kong26c.html
6. Wittig et al., ICML 2026, *Which Algorithms Can Graph Neural Networks Learn?*. https://proceedings.mlr.press/v306/wittig26a.html

## 16. N0.7 最终决策

当前推荐的计算核心不是“全量超图网络”，也不是“无限深循环网络”，而是：

**类型化超图状态 + 可组合部分算子 + 稀疏候选路由 + 分支差分共享 + 硬约束验证 + 学习型软排序 + 有界自适应迭代。**

易象类象在其中扮演可学习的结构变换先验；ZPCM 保持证据与长期认知状态；N0.5 Context Compiler 决定当前工作集；TRLW/SROK 负责结构计算；语言生成只负责把已验证结构表达出来。

下一步不应继续堆叠概念。应进入 SROK-0 的数据结构、确定性算法和基准任务实现，并逐个做可复现实验。任何关于速度、参数效率或超越 Transformer 的结论，都必须等待测量。
