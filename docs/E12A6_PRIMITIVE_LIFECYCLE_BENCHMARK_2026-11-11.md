# E12-A6：Primitive Lifecycle Benchmark — 原语生命周期统一基准

日期：2026-11-11  
分支：research/e12a6-primitive-lifecycle-benchmark-2026-11-11  
状态：研究协议草案；尚无实现、运行结果或 CI 通过声明。  
依赖：E12-A1/A2、E12-A3、E12-A4-P、E12-A5、E12-M2.1；E02-D 作为有限规则辨识任务。

## 0. 为什么需要 E12-A6

当前研究线已经分别覆盖：
- 从类型化谓词和关系假设提出原语（A1/A2）；
- 通过主动测量减少有限假设集的不确定性（A2×E02）；
- 多提议器并行竞争和预算分配（A3）；
- 稀疏非连续组合（A4）；
- 根据 prequential/out-of-fold 残差提出待调查特征对（A5）；
- 从无标签离散事务挖掘统计 motif（M2）。

但目前尚无统一基准回答一个更根本的问题：

**一个系统能否从原始观测出发，提出一个新候选结构，找到能区分它与竞争解释的观测，验证它是否可复用，将它组合进新任务，并在后续反例出现时正确修订或撤销它？**

E12-A6 不新增一种更复杂的搜索器，而是把已有机制放入同一个生命周期任务，测量它们是否真正构成闭环。它是集成基准，不是新的认知能力主张。

## 1. 原语生命周期状态机

每个候选原语具有不可变 ID、版本和证据谱系，并且只能通过显式状态迁移：

1. **OBSERVED**：只有原始观测或统计共现，尚未提出机制。
2. **PROPOSED**：提议器给出可执行定义、类型、适用条件和预测。
3. **DISCRIMINATION_PENDING**：存在竞争解释，系统选择区分性观测。
4. **TRAIN_SUPPORTED**：候选在 Train 证据上满足预注册约束。
5. **GATE_VALIDATED**：独立 Gate 支持候选，且相对简单基线具有增量收益。
6. **REUSED**：候选在新组合/新任务中被调用，并产生可测预测。
7. **CHALLENGED**：新反例与候选预测冲突。
8. **REVISED / SPECIALIZED / RETIRED**：候选被修订、拆分为适用子域，或退役。
9. **REVALIDATION_PENDING**：任何语义定义变化均视为新版本，必须重新验证。

不得把频繁共现、训练拟合、单次 Gate 胜出或模型自我解释直接提升为 ACCEPTED primitive。REUSED 也不是永久正确的证明。

## 2. 统一任务生成器

每个 episode 由隐藏世界生成器产生观测流和任务序列。生成器内部真值仅由外部 evaluator 持有。

### 2.1 世界族

- **Known mechanism / novel composition**：原语已出现，测试组合未出现。
- **Novel mechanism within bounded meta-grammar**：机制算子族在声明范围内可发现，但具体参数/关系未出现。
- **Observational equivalence**：两个机制在现有观测下完全等价，只有指定额外测量才能区分。
- **Confounded co-occurrence**：引入共同原因或环境变量，使表面相关不等于机制。
- **Context-dependent relation**：同一关系在不同环境中成立条件不同。
- **Noise and missingness**：标签噪声、缺失属性、测量误差。
- **Distribution shift**：数值尺度、对象身份、特征位置或环境分布变化。
- **False analogy**：两个领域共享表面统计特征但生成机制不同。
- **Delayed counterexample**：候选先在若干环境成立，随后出现合法反例，测试是否修订而非过度坚持。
- **Null world**：不存在可复用结构，正确行为应是 abstain。

### 2.2 生成器隔离

Train、Gate-Dev、Gate-Final、Locked-Test 必须使用独立 episode seed 和独立对象/世界组。若任务有环境或实体身份，必须按实体/环境分组隔离，不能仅随机拆分行。

隐藏机制 ID、生成器 seed、候选答案数量、文件名、排序顺序和数据生成元信息不得进入学习器可见输入。

## 3. 统一接口契约

### Candidate
- candidate_id、version、canonical_expression；
- proposer_family、supporting_families；
- typed_inputs、operator_definition、applicability_conditions；
- predicted_relation / transformation；
- uncertainty、complexity、declared_cost；
- parent_candidate_ids；
- source_evidence_ids；
- lifecycle_state。

### Evidence
- immutable evidence_id、episode_id、world_group_id；
- split_role（Train / Gate-Dev / Gate-Final / Locked-Test）；
- observation、label_visibility_time；
- prediction_commit_time、model_version；
- prediction、outcome、measurement_cost；
- provenance and integrity digest。

### Action
- PROPOSE、MEASURE、COMPOSE、PREDICT、REVISE、SPECIALIZE、RETIRE、ABSTAIN。
- 每个动作记录前置状态、输入证据、消耗的 proposal/evaluation/measurement/compute budget 和结果。

学习器 API 不得接收 Gate-Final 或 Locked-Test 标签。最终评估器单独持有它们。任何使用 Gate-Dev 做选择的流程，必须在 Gate-Final 和 Locked-Test 上冻结后评估。

## 4. 生命周期任务流程

对每个 episode：

1. 系统读取初始 Support 观测，构建候选集合或明确 abstain。
2. 提议器提交候选原语；同一 canonical expression 只保留一个候选对象，但记录全部 supporting_families。
3. 系统构建竞争解释集，估计哪些允许的测量能够区分它们。
4. 主动测量策略在相同测量成本预算下选择查询；随机、固定顺序、信息增益和有限 exact oracle 作为对照。
5. Train 只负责拟合/过滤；Gate-Dev 负责选择和增量效用；Gate-Final 只做一次冻结验证。
6. 已验证原语进入新组合任务。组合器可创建非连续稀疏图结构，但不能暗中改写原语定义。
7. 任务流引入延迟反例或环境变化，系统需选择保留、修订、专门化、退役或 abstain。
8. Locked-Test 由独立 evaluator 运行，整个 episode 完成后才揭示汇总结果。

## 5. 必须比较的系统臂

A. **Simple baseline**：单一固定规则/统计提议器 + 固定组合器。  
B. **A1/A2**：类型化候选与主动测量，但无多提议器。  
C. **A3**：多提议器竞争，固定分配。  
D. **A3-adaptive**：真实 proposer 集成的自适应分配；不得使用预生成奖励流替代。  
E. **A4**：固定 proposer + 稀疏组合。  
F. **A5→A4**：Train-only 残差诊断触发有界算子扩展。  
G. **M2→A1**：无监督 motif 只产生候选，不直接接受为语义原语。  
H. **Full lifecycle**：提议、主动辨识、稀疏组合、预算竞争、反例修订完整闭环。  
I. **Ablations**：移除主动测量、移除组合、移除反例修订、移除去重谱系、移除成本惩罚。  
J. **Oracle controls**：仅在明确有限的假设/动作空间中提供上界，不与开放式系统混淆。

## 6. 核心指标

### Discovery
- candidate recall / precision（只在生成器定义真值的合成任务报告）；
- false primitive acceptance rate；
- abstention coverage；
- proposal diversity 与 canonical duplicate ratio。

### Identification
- 识别率；
- 平均/最大测量次数；
- 测量成本；
- 未可辨识时的正确 abstention 率。

### Composition
- unseen composition accuracy；
- novel gap / position / depth generalization；
- composition validity；
- coalition incremental utility。

### Continual revision
- prequential predictive loss；
- delayed-counterexample detection delay；
- false revision / missed revision；
- old-world retention 与 new-world adaptation；
- retired primitive resurrection rate。

### Efficiency and calibration
- proposal、evaluation、measurement、inference 分项成本；
- wall-clock、peak memory、候选数；
- proper scoring rules、calibration error；
- coverage-risk curve。

不能只报告“被选中候选的条件准确率”；必须同时报告 coverage 和 abstention。

## 7. 统计与泄漏控制

- 至少 5 个独立 world families；每个 family 至少 100 个 episode，最终样本量按功效分析调整。
- 预注册主要指标、次要指标、停止规则、阈值和排除规则。
- 对同一 episode 内重复测量不得当作独立样本；统计单位为 world/episode。
- 多特征对、多阈值扫描必须用 max-statistic permutation 或经校准的多重比较程序；同时报告置换次数、最小可分辨 p 值和效应量。
- permutation 必须保留相应边际/分组结构；若目标是检测 pair interaction，应使用保持单变量边际的适当零模型，而不是任意打乱所有字段。
- 所有调参只使用 Train/Gate-Dev；Gate-Final 和 Locked-Test 不可反复查看。
- 运行 label mutation、target mutation、metadata-only attacker、split mutation 和 candidate-order mutation 测试。
- 所有失败 episode、abstention 和预算耗尽均纳入统计。

## 8. 预注册失败条件

以下任一情况均不得宣称完整生命周期能力成立：

1. Null world 中仍大量接受伪原语。
2. 观察等价任务中系统未能 abstain。
3. 错误类比环境中，结构先验使置信度升高但泛化下降。
4. 多提议器系统在匹配预算下不优于最佳单提议器，且没有其他明确收益。
5. 完整系统的增益在移除某个声称关键模块后不变。
6. 延迟反例出现后，系统持续复用已被证伪原语且没有记录风险。
7. 新版本修订未触发重新验证。
8. 仅在合成训练分布上成功，遇到实体/环境/组合 OOD 即崩溃。
9. 性能增益来自更高实际计算量或数据泄漏。
10. 结果对种子、候选顺序或轻微噪声高度敏感。

## 9. 易象先验的嵌入方式

易象结构不得成为固定标签或隐藏答案编码。每一种先验单独作为可替换模块：
- 阴阳互补：二元互补/对偶结构假设；
- 四象：两位状态的分层组织假设；
- 八卦：三位结构与层级分解假设；
- 六十四卦：六位复合状态空间假设；
- 卦变：状态转移候选；
- 五行：多关系作用图候选；
- 类象：跨域结构映射候选。

对每个模块至少比较：
1. 无先验；
2. 通用随机初始化且容量匹配；
3. 传统结构初始化；
4. 标签/位置打乱先验；
5. 反向或 anti-aligned 先验；
6. 从数据学习的结构先验。

先验只允许影响候选提议/归纳偏置，不得读取隐藏世界标签。任何收益必须在跨世界、错配世界和 OOD 测试中复现。

## 10. 与相关研究的边界

概念中心神经符号智能体、概念组合、持续组合学习和组合泛化基准均已有活跃研究。E12-A6 的目标不是声称首次提出这些组成部分，而是提供一个可复现的统一生命周期评测：候选发现、主动区分、组合复用、延迟反例修订、证据谱系和实际成本在同一协议内共同受检。

参考：
- Mao, Tenenbaum & Wu (2026), Building Intelligent Agents with Neuro-Symbolic Concepts, Communications of the ACM. https://doi.org/10.1145/3715316
- Li et al. (2026), Composition-Incremental Learning for Compositional Generalization, AAAI 2026. https://doi.org/10.1609/aaai.v40i8.37605
- Fu & Liu (2026), Compositional Generalization with Outcome-Level Optimization, Findings of EMNLP 2026. https://aclanthology.org/2026.findings-emnlp.1496/
- Redhardt et al. (2025), Scaling can lead to compositional generalization, NeurIPS 2025. https://proceedings.neurips.cc/paper_files/paper/2025/hash/5047b64366bc0dbf5047de85f1e0c7be-Abstract-Conference.html
- Camposampiero et al. (2025), Scalable Evaluation and Neural Models for Compositional Generalization, NeurIPS 2025. https://proceedings.neurips.cc/paper_files/paper/2025/hash/0ae7b78781ced49b2b0b542b30154a1c-Abstract-Conference.html

## 11. 执行建议

1. 先把 Candidate/Evidence/Action schema 作为独立 JSON Schema/Python dataclass 实现，不合并各研究分支的算法。
2. 用 E02-D 27-rule finite world 做最小生命周期闭环，确保每个状态迁移可追踪。
3. 接入 A2 active measurement；先证明 abstention 与 query isolation。
4. 接入 A3 proposer 并保持相同 proposal/evaluation budget。
5. 接入 A4 稀疏组合；执行 2×2 proposer×composition 因子实验。
6. 最后接入 A5 residual trigger 和 M2 motif 候选；对多重扫描先做 max-statistic 校准。
7. 只有符号生命周期基准通过后，才引入神经编码器/提议器。

本文件只定义研究协议。尚未实现统一 runner，也没有任何 E12-A6 实验结果或 CI 通过声明。
