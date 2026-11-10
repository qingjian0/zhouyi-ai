# 2026-11-10 研究增量：组合泛化与架构差异定位

## 本轮结论

本轮文献检索发现，CPG-EI 原先的创新表述需要进一步收紧。**动态超图、组合泛化、符号程序图、反馈式规则学习和神经符号验证都已有直接相关工作。** 因此不能把这些单项技术拼接后就称为全新范式。项目必须证明的是特定机制组合的独立贡献，以及其在统一任务上的可测优势。

## 新增相关工作

### 1. NeSyCoCo（AAAI 2025）

Danial Kamali, Elham J. Barezi, Parisa Kordjamshidi, *NeSyCoCo: A Neuro-Symbolic Concept Composer for Compositional Generalization*, AAAI 2025.
- 论文：https://doi.org/10.1609/aaai.v39i4.32439
- 贡献：利用符号表示和可微神经计算进行软组合；在 ReaSCAN、CLEVR-CoGenT、CLEVR-SYN 等组合泛化任务评估。
- 对 CPG-EI 的影响：概念组合器和可微组合不能作为独立创新点。需要比较 CPG-EI 的动态超边创建/拆分/合并、证据追踪与状态先验是否提供额外贡献。

### 2. Scalable Evaluation and Neural Models for Compositional Generalization（NeurIPS 2025）

Giacomo Camposampiero et al., *Scalable Evaluation and Neural Models for Compositional Generalization*, NeurIPS 2025.
- 论文：https://proceedings.neurips.cc/paper_files/paper/2025/hash/0ae7b78781ced49b2b0b542b30154a1c-Abstract-Conference.html
- 贡献：指出组合泛化评估协议本身存在问题，并提出更可扩展的评估框架；研究大量视觉模型及 Attribute Invariant Networks。
- 对 CPG-EI 的影响：E01–E08 必须明确 IID/OOD 划分、组合覆盖率、概念覆盖率和任务难度，不能只随机拆分样本。

### 3. Scaling can lead to compositional generalization（NeurIPS 2025）

Florian Redhardt, Yassir Akram, Simon Schug, *Scaling can lead to compositional generalization*, NeurIPS 2025.
- 论文：https://proceedings.neurips.cc/paper_files/paper/2025/hash/5047b64366bc0dbf5047de85f1e0c7be-Abstract-Conference.html
- 贡献：报告标准神经网络在足够数据和模型规模、任务空间覆盖充分时也能获得组合泛化。
- 对 CPG-EI 的影响：不能把组合泛化失败描述为 Transformer/神经网络的必然限制。必须与参数量、训练样本量和计算预算匹配的 MLP/Transformer 基线比较，并测试数据覆盖不足时的样本效率。

### 4. AGEL-Comp（2026 预印本）

Mahnoor Shahid, Hannes Rothe, *AGEL-Comp: A Neuro-Symbolic Framework for Compositional Generalization in Interactive Agents*.
- 论文：https://arxiv.org/abs/2604.26522
- 贡献：动态因果程序图（有向超图）、ILP 从交互反馈中归纳 Horn clauses、LLM 提议子目标并由神经定理证明器检查。
- 对 CPG-EI 的影响：动态超图 + 反馈式规则生成 + 候选验证的组合已有近邻。必须把差异具体化到通用语义单元、可学习高阶关系、结构演化策略、易象先验的受控验证和证据溯源，而不能只说“动态超图自组织”。

### 5. Dynamic hypergraph structure learning for spatio-temporal time series forecasting（2026）

论文：https://doi.org/10.1016/j.neucom.2026.133014
- 贡献：从时序数据学习动态超图结构，强调避免直接学习完整关联矩阵造成的参数冗余和过拟合。
- 对 CPG-EI 的影响：动态结构学习已有专门研究。E02 应比较稀疏候选生成、动态路由、静态超图和普通图，并报告结构参数量、边更新成本和过拟合风险。

### 6. Neuro-symbolic NLP: taxonomy, assessment, and directions（2026）

论文：https://doi.org/10.3389/frai.2026.1797587
- 贡献：按神经与符号模块的集成方式分类，讨论组合泛化、推理、验证和稳健性。
- 对 CPG-EI 的影响：架构设计应明确采用紧耦合（injective）还是模块联邦式（federative）集成，或采用混合层次。当前建议：语义感知保持可学习，结构验证和证据治理作为独立模块，允许两者双向反馈。

## 研究差异矩阵（当前假设）

| 已有方向 | 已覆盖能力 | CPG-EI 不能重复宣称 | 需要验证的差异 |
|---|---|---|---|
| NeSyCoCo | 可微概念组合 | “首次概念组合” | 动态超边生命周期和证据约束是否有增益 |
| AGEL-Comp | 动态程序超图、ILP 反馈、候选验证 | “首次动态超图+反馈学习” | 通用语义/事件空间及易象先验的独立价值 |
| 动态超图时序模型 | 数据驱动结构变化 | “首次学习动态超图” | 非时序语义关系的稀疏高阶组合 |
| NeurIPS 2025 组合泛化研究 | 规模可带来组合泛化 | “神经网络无法组合泛化” | 低数据/组合覆盖不足时的样本效率与鲁棒性 |
| 离散扩散/NAR | 并行多位置生成 | “并行生成本身是创新” | 语义结构组合与生成过程如何解耦协作 |

## E01 方法修订

E01 不再只展示手工分数的 top-k。新增一个 CPU 友好的可学习线性兼容打分器：
- 每个样本包含一个查询向量和多个候选语义特征向量；
- 隐藏规则根据查询与候选的逐维交互分数确定目标集合；
- 模型用训练样本学习交互权重；
- 测试集使用独立随机种子生成，候选身份和组合均未见；
- 对比随机选择、固定邻接前缀和 oracle；
- 报告 exact match、micro precision/recall/F1。

该实验仅验证“能否从数据中学习非相邻集合选择”，不等同自然语言理解或完整动态超图能力。后续必须增加组合规则变化、关系角色和高阶约束任务，防止任务过于简单。

## 本轮后续优先级

1. 执行 E01 学习器测试，保存实际指标和运行配置。
2. 做 5 个以上随机种子，报告均值/标准差。
3. 建立 E01 OOD split：训练中留出特定查询-属性组合，测试系统能否组合已知原语。
4. E02 先实现小规模可解释超图结构学习，避免直接引入大型神经网络。
5. 之后再开展易象模块对照，不与组合器同时改动。
