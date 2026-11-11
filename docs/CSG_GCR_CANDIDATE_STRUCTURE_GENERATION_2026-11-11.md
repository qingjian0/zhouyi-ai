# CSG-GCR：候选结构生成与全局约束求解架构

日期：2026-11-11  
阶段：研究设计 / 可执行原型规格（尚非训练模型）  
上游：RSDN-N2.1（PR #160）  
状态：Draft

## 0. 本文要解决的问题

RSDN-N2 将学习目标从单纯预测下一个 Token 转向预测关系状态编辑；RSDN-N2.1 又要求训练模型理解多步组合约束。本设计继续向前推进：定义一个不依赖左到右 Token 顺序的内部候选生成与求解机制。

目标不是把多个完整答案交给投票器，也不是把离散扩散直接等同于新认知架构。目标是让系统围绕认知状态产生局部结构假设，在显式依赖、条件、证据和资源预算下，将它们组合为可验证的状态编辑集合。

本设计必须区分四件事：

1. **候选并行提出**：多个 proposer 同时提出局部假设。
2. **结构组合**：候选按共享变量、关系、条件和依赖连接；允许跨越非必要中间节点。
3. **全局协调**：求解候选之间的兼容、冲突、覆盖和预算分配。
4. **结果实现**：把验证后的结构转成语言、工具调用或行动计划。

前 3 项属于内部认知计算；第 4 项是外部实现。不能用流畅的语言输出替代内部验证。

## 1. 设计原则

- 结构优先：基本计算对象是对象、关系、超边、条件、时间、证据和状态编辑，不是自然语言 Token。
- 非顺序依赖：内部节点不要求按文本位置排序；依赖边由语义和证据决定。
- 可跳跃组合：允许组合非相邻候选，但每条组合边必须说明变量绑定、前置条件和证据来源。
- 局部提出、全局验证：proposer 可以提出假设，但不能自行把假设升级为事实。
- 保留分歧：冲突候选可以并存于不同分支，不通过平均或多数票抹掉。
- 显式拒绝：无足够证据时允许 NOOP、ABSTAIN、NEED_MORE_EVIDENCE。
- 预算硬约束：候选数量、图节点数、分支深度、验证次数和 RAM 均有上限。
- 可回溯：每个结果保存父状态版本、推导链、证据引用和算子版本。
- 易象先验可消融：阴阳、错综互变、类象等作为可检验的结构先验/算子，不作为不可质疑的真理标签。

## 2. 核心数据结构

### 2.1 Candidate Atom

候选原子是最小可组合假设：

```
CandidateAtom {
  candidate_id
  kind: ENTITY | RELATION | HYPEREDGE | CONDITION |
        TEMPORAL | STATE_EDIT | OPERATOR_APPLICATION
  variables[]
  payload
  preconditions[]
  effects[]
  evidence_refs[]
  provenance
  epistemic_status
  confidence_vector
  resource_cost
  parent_state_version
  proposer_id
}
```

confidence_vector 不应只保存单一置信分数，至少分开：
- model_score：提出器自身评分；
- evidence_support：证据支持强度；
- constraint_compatibility：与当前约束兼容程度；
- calibration：该类预测在验证集上的校准质量。

### 2.2 Candidate Hypergraph

使用带类型超图表达候选组合：

```
CandidateHypergraph {
  nodes: CandidateAtom[]
  hyperedges: CandidateComposition[]
  conflicts: ConflictRecord[]
  branches: BranchRecord[]
  constraints: ConstraintRecord[]
  state_version
  budget_snapshot
}
```

CandidateComposition 至少包括：
- members：参与组合的候选 ID；
- variable_bindings：变量统一/绑定；
- composition_operator：使用的组合算子；
- required_conditions：必须成立的条件；
- dependency_refs：依赖的父节点或证据；
- validity：VALID / INVALID / UNKNOWN；
- explanation_trace：可机读推导轨迹。

超边用于表达三元及更高阶关系，不应强行把所有结构拆成二元边。

### 2.3 Candidate Edit Set

全局协调器的输出不是一个答案字符串，而是一组候选状态编辑：

```
CandidateEditSet {
  edits[]
  dependency_dag
  unresolved_conflicts[]
  proof_trace[]
  evidence_coverage
  objective_vector
  terminal_status
}
```

terminal_status：
- VERIFIED：所有硬约束满足，必要证据完整；
- PARTIALLY_VERIFIED：部分编辑可提交，其他部分待定；
- HYPOTHESIS_ONLY：可保留为假设，不可写入事实状态；
- CONFLICTED：存在无法消解的硬冲突；
- ABSTAINED：预算耗尽或证据不足，拒绝确定结论。

## 3. 候选发生器（Proposer Bank）

Proposer 不必是多个完整大模型。它们可以是同一轻量模型的不同查询头、规则算子、检索器或局部神经网络。

建议第一版包含：

1. Forward Proposer：从当前状态和观察预测可能的局部编辑。
2. Backward Proposer：从目标约束逆向提出必要前提。
3. Analogy Proposer：从 XSL 类象映射提出结构候选。
4. Transformation Proposer：应用错、综、互、变及其他版本化关系算子。
5. Counterfactual Proposer：提出反事实分支，用于测试因果/条件依赖。
6. Memory Proposer：从长期事件和关系索引召回相关状态片段。
7. Null Proposer：显式提出 NOOP / ABSTAIN，防止系统被迫编造变化。

每个 proposer 只负责产生候选，不负责最终裁决。多个 proposer 可以共享一个小型 State Encoder，但必须保留 proposer 身份和各自的校准数据。

## 4. 组合规则与“跳过中间元素”

设候选原子集合为 C。组合函数：

`Compose(C_i, C_j, θ) -> {C_k, proof, status}`

组合至少要通过以下检查：

1. 类型兼容：变量和关系类型是否可统一；
2. 角色兼容：主体、客体、工具、条件、受体等角色是否匹配；
3. 条件兼容：前置条件是否矛盾；
4. 时间兼容：有效时间区间是否相交或存在合法先后关系；
5. 证据可追溯：是否能回溯到观察或可信推断；
6. 不变量保持：是否破坏已验证状态约束；
7. 依赖闭合：是否缺失必要的中间依据。

允许 A 与 D 组合而不显式选择 B、C，但不是允许忽略所有中间因果链。必须区分：

- **结构跳跃**：A、D 之间存在直接可验证的关系或共享约束；
- **路径压缩**：A→B→C→D 被压缩表达，但 B、C 的必要依赖仍保留在 proof_trace；
- **无依据跳跃**：没有合法关系、条件或证据连接，必须拒绝或标记 UNKNOWN。

示例：若 A→B、B→C、C→D 是一条已知链，另有 A→E、E→D 的候选路径，则协调器可以比较两条路径。它不能仅因为 A 和 D 同时出现就断言 A→D。

## 5. 全局协调器

协调器解决的是受约束的候选集合选择，而不是单一分数排序。

设 x_i∈{0,1} 表示候选是否进入当前分支。目标可以表示为多目标优化：

```
maximize:
  evidence_support(x)
  constraint_coverage(x)
  explanatory_compactness(x)
  candidate_diversity(x)
  goal_progress(x)

minimize:
  contradiction_cost(x)
  unsupported_dependency_cost(x)
  compute_cost(x)
  memory_cost(x)
```

硬约束：
- 不能同时选择不可共存的候选；
- 不允许循环依赖，除非该循环被定义为显式动态系统；
- 不允许缺失必要前置条件；
- 不允许把 HYPOTHESIS 自动升级成 OBSERVED；
- 不允许超过当前预算；
- 不允许丢失证据引用。

### 5.1 候选多样性

只按模型分数取 Top-K 会造成模式坍缩。建议组合使用：
- 结构签名去重；
- proposer 来源配额；
- 关系路径差异；
- 目标覆盖差异；
- 基于相似度惩罚的多样性选择；
- Pareto 前沿保留。

可研究 DPP/近似 DPP，但第一版不强制引入矩阵分解；手机端可先用结构签名 + 贪心最大边际相关性（MMR）实现。

### 5.2 搜索策略

不采用无界全量枚举。建议分层：

- L0：局部兼容检查；
- L1：候选原子合并；
- L2：小型组合束搜索；
- L3：对高价值未决区域局部扩展；
- L4：证据验证和状态提交。

优先采用 best-first + bounded beam，而不是对所有分支统一扩展。预算耗尽时保留 continuation_cursor，后续可恢复，而不是伪装成搜索完成。

剪枝优先级：
1. 硬约束冲突；
2. 类型/角色不兼容；
3. 必要条件不可满足；
4. 证据链断裂；
5. 被严格支配的 Pareto 候选；
6. 超出预算的低价值分支。

## 6. 与易象 / 类象 / 象数理的关系

易象不是候选的装饰标签，而应作用于候选结构的生成和变换。

建议把易象计算分为四类：

- 象：对象、关系形态、结构角色及可映射的类象特征；
- 数：状态计数、位置、次序、比例、变化量及其约束；
- 理：关系成立条件、因果/制约、不变量和推演规则；
- 变：在时间、条件或状态变化下的结构编辑。

阴阳不应简单编码成两个类别后直接参与分类。它可以作为互补、对待、消长、制约等关系假设的结构参数，但每个具体语义必须有可操作定义和反例。

错、综、互、变等算子必须：
- 有 operator_id 和版本；
- 声明输入输出 schema；
- 声明保持不变量和适用条件；
- 产生可追溯的 proof_trace；
- 可以被拒绝、消融或替换；
- 不得将结构变换自动等同于现实事实。

## 7. 生成器与语言模型的关系

内部结构生成和语言表面生成分开训练、分开评估。

推荐三种实现路线并行比较：

A. 结构编辑预测器：直接预测 CandidateAtom / EditSet。适合作为第一阶段基线，容易验证和部署。

B. 离散扩散候选生成器：在候选槽位/关系槽位上迭代提出、遮蔽、修订结构。必须解决候选间联合依赖，不能使用简单独立采样后直接接受。

C. 混合生成器：神经模型提出候选，符号协调器组合和验证；必要时使用语言模型提出难以规则化的候选，再由结构层校验。

禁止将“多个候选并行提出”描述成“完整非自回归语言生成”。真正的非自回归语言生成是另一个评测维度。当前阶段首先验证非顺序的内部认知结构生成。

## 8. 移动端资源模型

不把完整 CandidateHypergraph 常驻 RAM。

建议分层存储：
- 冷层：原始事件、完整证据、旧分支，磁盘持久化；
- 温层：索引、状态摘要、常用关系，内存映射/分页；
- 热层：当前任务活动子图、候选束、局部 proof_trace，严格 RAM 预算；
- 临时层：proposer 中间结果，生命周期结束即回收。

采用共享只读父状态 + 稀疏 delta。分支只存变更，不复制整张图。

每次运行必须记录：
- peak_rss_bytes；
- active_node_count；
- candidate_count；
- branch_count；
- max_branch_depth；
- verifier_calls；
- proposer_latency；
- coordinator_latency；
- disk_read_bytes / disk_write_bytes；
- total_wall_time；
- budget_exhausted；
- quality metrics。

不得以“有效上下文容量”替代真实 RAM、磁盘 IO 和延迟指标。百万条事件可存储/检索，不等于百万 Token 同时进入活动推理。

## 9. 最小可执行原型路线

### CSG-0：确定性候选协调器
不训练神经模型。输入人工构造的候选原子，执行类型检查、条件检查、冲突检测、Top-K、多样性选择、proof_trace 和预算截断。

### CSG-1：学习型候选发生器
用 RSDN 状态和观察生成候选编辑；协调器仍保持确定性。

### CSG-2：组合式候选训练
训练模型提出可组合候选，而不只拟合局部下一状态。加入隐藏中间节点、逆向推导、路径重组、反事实和 proof-depth 评测。

### CSG-3：易象算子学习
比较无先验、随机先验、通用算子、易象结构先验四种条件。必须在 OOD 和反例集上验证收益。

### CSG-4：移动端部署
先在桌面跑功能和复杂度实验，再做 Android 真机 RSS、延迟、耗电、温升和磁盘 IO 测量。

## 10. 关键实验与消融

基线：
- AR Transformer；
- 离散扩散模型；
- GNN；
- 规则求解器；
- RSDN 单步编辑预测；
- CSG 确定性协调器；
- RSDN + CSG；
- RSDN + CSG + 易象算子。

任务：
1. 非相邻候选组合；
2. 隐藏中间节点的路径重建；
3. 多条路径的冲突与选择；
4. 多条件约束传播；
5. 反事实分支；
6. OOD 关系组合；
7. 证据不足时拒绝；
8. 预算耗尽时正确报告不完整。

指标：
- Exact Edit Set Match；
- Valid Composition Rate；
- Unsupported Jump Rate；
- Constraint Satisfaction；
- Proof Trace Completeness；
- OOD Generalization；
- Candidate Diversity；
- Duplicate Candidate Ratio；
- Invalid Edit Rejection；
- Abstention Calibration；
- Quality / Latency；
- Quality / Peak RAM；
- Energy per verified edit。

关键消融：
- 去掉全局协调器；
- 去掉证据约束；
- 去掉多样性选择；
- 去掉反向 proposer；
- 去掉类象 proposer；
- 去掉易象算子；
- 将超边降为二元边；
- 禁止非相邻组合；
- 将共享父状态改为全量复制；
- 将 bounded beam 改成无差别扩展。

## 11. 失败判据

出现以下任一情况，不得宣称架构有效：
- 候选数量增加但有效候选覆盖率没有提高；
- 组合成功率提高是靠放宽约束或隐藏反例；
- Unsupported Jump Rate 上升；
- proof_trace 无法复现；
- 仅在训练分布内有效，组合 OOD 明显崩溃；
- 易象版本相对通用算子没有可重复收益；
- 多样性指标提高但正确性显著下降；
- 在目标手机上超出内存/延迟/能耗预算；
- 仅生成了更多文本，却没有提高结构编辑正确率。

## 12. 与现有模块的边界

- ZNCA：持久认知状态、证据和事件账本。
- XSL：类象发现、映射和结构变换候选。
- YXO：版本化易象算子。
- RSDN：学习状态变化和候选编辑。
- CSG-GCR：组织候选、执行组合搜索、全局约束协调。
- Realizer：语言、工具和行动输出。

CSG-GCR 不取代 ZNCA/RSDN/XSL，而是连接候选发生与状态提交的中间计算层。

## 13. 当前结论与未解决问题

当前最值得优先实现的是 CSG-0：一个小型、确定性、可测量的候选超图协调器。它能先验证数据结构、组合规则、分支策略和预算控制，不需要等待大模型训练。

但它只能证明候选协调机制可执行，不能证明模型已学会自主发现高质量候选。后续必须用 RSDN 学习型 proposer 和严格 OOD 实验验证。

仍需研究：
1. 候选结构的最小通用表示是否会过度抽象；
2. 关系组合的可判定边界和近似求解策略；
3. 如何学习 proposer 间的互补性，而非重复提案；
4. 如何把易象算子转成可学习又可证伪的先验；
5. 如何在低 RAM 下实现增量超图查询和分支恢复；
6. 何时应该结束搜索、请求新观察或明确拒绝。

## 参考研究

- Breaking the Factorization Barrier in Diffusion Language Models, ICML 2026: https://proceedings.mlr.press/v306/li26fd.html
- Parallelism and Generation Order in Masked Diffusion Language Models, Findings of ACL 2026: https://aclanthology.org/2026.findings-acl.357/
- D5P4: Partition Determinantal Point Process for Diversity in Parallel Discrete Diffusion Decoding, 2026: https://arxiv.org/abs/2603.19146
- PRISM: Efficient Test-Time Scaling via Hierarchical Search and Self-Verification for Discrete Diffusion Language Models, ICML 2026: https://proceedings.mlr.press/v306/bai26f.html
- Graph of States: Solving Abductive Tasks with Large Language Models, ICML 2026: https://proceedings.mlr.press/v306/luo26f.html
- Constraining Generative Models: A Survey from the Constraint Programming Perspective, IJCAI 2026: https://ijcai.org/proceedings/2026/864

以上资料用于提出设计假设，不代表 CSG-GCR 已被实验验证。
