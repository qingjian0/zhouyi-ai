# 易象驱动的持续认知架构：象数理类变进入核心计算

日期：2026-11-11  
优先级：P0 核心理论架构  
状态：研究设计 / 待实现、消融与基准验证  
关联文档：
- MOBILE_1M_EFFECTIVE_CONTEXT_ARCHITECTURE_2026-11-11.md
- CPG_EI_PERSISTENT_COGNITION_MOBILE_ARCHITECTURE_2026-11-11.md

## 0. 核心架构修正

易象、类象、象数理不应被放在知识库中作为一个普通领域插件。它们应进入 CPG-EI 的表征、检索、记忆更新、组合生成、推演和上下文编译路径。

核心原则：

**以象组织认知，以数约束计算，以理建立关系，以类发现候选映射，以变驱动推演，以证据校验结论。**

这不是把现代知识强行归入八卦，也不是用卦象取代数学、逻辑、概率或实验。易象提供的是可学习、可修订、可拒绝的结构先验和候选算子。

## 1. 象数理类变：五类认知职责

### 1.1 象：结构化表征（Representation）

“象”描述对象在某一观察尺度下呈现的结构、属性、状态、关系与整体形态。

计算对象不应只有文本 embedding，还应支持：
- entity / attribute / state；
- relation / event / process；
- part-whole / topology / role；
- temporal phase / transition；
- context-dependent feature；
- multi-scale pattern。

同一对象可以有多个观察视角和多个尺度的象；表征不是对象本体的唯一真相。象必须绑定观察条件、来源和版本。

### 1.2 数：可计算结构（Quantification & Combinatorics）

“数”承担离散编码、数量关系、组合空间、位置、约束、变化幅度和统计评价。

需要严格区分：
- 形式编码（如阴阳二值）；
- 数学量（计数、距离、概率、权重）；
- 传统数象解释；
- 从数据中学习到的统计规律。

它们不能混为一个数值字段。每种数值都要有定义、单位、尺度和适用范围。

### 1.3 理：关系与约束（Relations & Constraints）

“理”表达可检验的关系结构：
- 条件关系；
- 依赖关系；
- 对称/互补/相反；
- 约束与不变量；
- 时序与状态转移；
- 因果候选及其证据要求；
- 适用条件、例外和边界。

类比关系不能自动升级为因果关系；规则要标注是定义、假设、经验规律还是已验证机制。

### 1.4 类：结构类比与迁移（Analogy & Transfer）

取象比类应作为跨领域结构匹配机制，而不是关键词相似或表面形状相似。

匹配至少比较：
- 角色对应；
- 关系拓扑；
- 状态转换模式；
- 约束结构；
- 边界条件；
- 反例与不匹配部分；
- 映射的可逆性和置信度。

输出必须是 CandidateMapping，包含 source domain、target domain、matched invariants、unmatched features、supporting evidence、counterexamples、confidence 和 validation plan。

类象只生成可检验假设。未经验证不得作为因果事实或稳定规则。

### 1.5 变：动态状态与推演（Change & Transformation）

“变”不是简单的状态标签切换，而是状态在条件、时间、关系和外部作用下的转换。

系统需记录：
- 起始状态与目标状态；
- 触发条件；
- 变化对象和作用位置；
- 不变量与可变项；
- 变化路径、分支和概率/置信；
- 预测与实际结果的差异。

变化模型要允许多条路径并行，不预设只有一条线性序列。

## 2. 易象编码层：保留传统结构，避免僵化

先建立明确、可互操作的形式编码：
- 阴爻 = 0，阳爻 = 1；
- 八卦 = 三位状态模式；
- 六十四卦 = 六爻二进制复合状态；
- 爻序自下而上，初爻索引为 0；
- 上卦与下卦分别由上三爻、下三爻构成；
- 动爻变化表示相应位置的状态翻转；
- 内部二进制 ID 与传统文王卦序是不同标识，必须显式映射，不能混淆。

这些约定是形式化表示，不意味着自然界或所有知识都只有 2、8、64 种状态。模型必须支持非易象表示、连续变量、多值状态和不确定状态。

八卦、六十四卦以及卦变首先作为结构化状态空间和转换算子候选；传统卦义、象义解释作为独立语义层，保留出处、版本、解释流派和歧义，不能直接混进二进制编码。

## 3. CPG-EI 核心对象模型

增加统一的 Cognition Primitive 与 Symbolic Pattern：

### CognitionPrimitive
- id / version / type；
- observed representation；
- symbolic features；
- numerical features；
- relation refs；
- temporal scope；
- source evidence refs；
- uncertainty / confidence；
- abstraction level。

### SymbolicPattern
- pattern id / version；
- symbol system（Yijing / Taixuan / learned / domain-specific）；
- pattern structure；
- position and role constraints；
- allowed transformations；
- interpretation refs；
- scope / assumptions；
- empirical status。

### AnalogyMapping
- source pattern / target pattern；
- role correspondence；
- preserved invariants；
- mismatches；
- support / counter-evidence；
- transfer hypothesis；
- validation outcome。

### TransformationHypothesis
- initial state；
- changed positions / relations；
- trigger conditions；
- candidate next states；
- predicted observations；
- outcome evidence。

### EvidenceBinding
所有对象都必须引用原始事件、文档片段、观察数据或实验结果。传统经典文本引用、现代数据和模型推断必须区分来源类型。

## 4. 动态超图：让类象与多组合直接参与计算

采用动态超图，而不是只依赖简单实体-关系三元组。

超图节点可以是概念、状态、事件、象、数、规则和证据；超边允许多个元素共同形成一个结构。

需要支持：
- CREATE：提出新结构；
- MERGE：合并等价或互补结构；
- SPLIT：拆分混合概念；
- REVISE：按新证据修订；
- RETRACT：撤回失效结构；
- TRANSFORM：按条件产生新状态；
- ANALOGIZE：跨领域提出类象映射。

组合生成允许非连续选择和多元素组合，例如 A-B-C-E，不要求必须经过 D；同时保留顺序、位置、角色和依赖约束。多个组合可以并行生成，再按证据、约束、覆盖率、成本和任务目标综合评估。

## 5. 易象进入 Context Compiler：不是只检索文本

Context Compiler 升级为 Symbolic-Evidence Context Compiler。

输入：
- 当前任务与目标；
- Persistent Cognitive State；
- 原始事件和证据索引；
- 易象/类象候选模式；
- 设备 RAM、IO、compute、token 预算。

处理步骤：
1. 任务辨识：确定问题类型、目标、约束和时间范围；
2. 取象：提取问题中的实体、状态、关系、过程与观察尺度；
3. 类象召回：从领域内和跨领域模式库召回结构候选；
4. 象数约束：检查编码、数量、位置、组合空间和适用范围；
5. 理关系展开：构建局部依赖/关系超图；
6. 证据召回：加载支持、反证、边界条件和必要原文；
7. 多路径装配：生成若干候选认知工作集；
8. 预算优化：在 RAM/IO/compute/token 预算内选择信息覆盖最好的工作集；
9. 推理交接：交给 CPG-EI operator 或语言模型；
10. 结果回写：保留预测、证据、推演路径和未决问题。

输出 PromptManifest + CognitiveWorkset。每个装入项必须注明是原始证据、结构状态、类象假设、规则还是模型生成的推断。

## 6. 易象进入 Persistent Cognitive State

PCS 不应只有实体、关系、事件、目标和信念，还应增加：
- Image/Pattern State：多尺度象与结构模式；
- Number/Constraint State：形式编码、数量约束和组合关系；
- Analogy State：候选类象映射、适用范围和验证状态；
- Transformation State：状态变换、触发条件、预测和实际结果。

PCS 的状态变化通过 append-only event log 记录。每次象、数、理或类象映射变化都必须可回溯；错误映射可以撤回，不得覆盖原始证据。

## 7. 易象与神经记忆双向协同

神经长期记忆负责快速压缩表征、模式召回和在线适应；易象/CPG-EI 结构负责显式关系、组合、约束、状态变化与证据链。

协作方式：
- Neural -> Symbolic：提出模式、聚类、候选关系和异常；
- Symbolic -> Neural：提供结构先验、检索条件和任务相关状态；
- Evidence -> Both：新观察可修订两侧状态；
- Arbitration：发生冲突时保留分歧、回查原文和实验，不允许任一侧自动覆盖另一侧。

不能将神经隐状态直接解释为某个卦象；任何映射都需要独立定义与验证。

## 8. 周易、太玄、阴符经的分工与正交性

- **周易易象**：关系结构、状态模式、位置、变爻、类象映射和变换路径；
- **太玄**：研究不同基数/多值状态空间、组合结构和状态粒度，不把其数制与周易二值编码混为一谈；
- **阴符经**：研究观察、时机、信息获取、主动探测、反馈与策略调整。

三条理论线可以共同作用于一个任务，但应保持独立参数、独立算子和独立实验开关。先做正交实验与 factorial ablation，再研究组合收益；不能因为理论上可以互补就假设组合一定有效。

## 9. 证据与科学验证约束

所有易象机制必须有基线和消融：
- 无易象随机/学习表征基线；
- 仅周易二值结构；
- 周易 + 类象映射；
- 象数理分离 vs 混合编码；
- 有/无变换算子；
- 周易、太玄、阴符分别启用；
- 三者组合的 factorial design。

评估：
- pattern retrieval recall/precision；
- analogy transfer accuracy；
- negative transfer rate；
- counterexample sensitivity；
- state transition prediction；
- calibration / abstention；
- provenance correctness；
- compute / memory / latency；
- mobile energy and thermal cost。

禁止：
- 把类比当因果；
- 把卦象解释当普适定律；
- 把传统数象附会当数学证明；
- 只报告成功例子；
- 忽略反例和负迁移；
- 将模型自生成的象义引用当经典原文；
- 将形式编码和传统卦序混淆。

## 10. 移动端效率：象结构帮助缩小工作集

易象不是额外的大型 token 负担。它的移动端价值在于将长文本历史转化为可寻址的结构对象和局部关系子图。

查询时先读取紧凑的模式/状态索引，再按需展开证据；对高频模式缓存结构摘要，对低频模式磁盘分页。局部更新只重算受影响的超图邻域和派生索引。

每轮成本应由候选模式数 K、局部子图规模 G、证据片段数 E、活动 token 预算 T 决定，而不是把全部 N 条历史输入模型。不能承诺所有查询严格 O(1)；必须测量 N 增长时的 P50/P95 延迟、召回率和内存曲线。

## 11. 实施顺序

### P0-1：统一形式与接口
定义 CognitionPrimitive、SymbolicPattern、AnalogyMapping、TransformationHypothesis、EvidenceBinding、CognitiveWorkset 和 PromptManifest。

### P0-2：易象最小算子
实现阴阳/八卦/六十四卦编码、爻位、卦变、上/下卦拆分、传统卦序映射与 round-trip tests。

### P0-3：类象匹配引擎
基于角色、关系拓扑、状态变化和约束结构提出候选映射；输出反例和验证计划。

### P0-4：Context Compiler 集成
让取象、类象、象数约束、证据召回和预算编译形成可运行闭环。

### P0-5：PCS / Hypergraph 集成
事件驱动地更新象、数、理、类、变状态；支持局部失效、回滚、恢复与版本比较。

### P1：多理论正交实验
独立接入太玄、阴符经算子，执行 factorial ablation 与跨任务迁移测试。

### P2：神经记忆与非自回归组合生成
研究神经长期记忆与符号结构的协同，以及多组合并行生成、跳跃式选择和全局协调。

## 12. 最终定位

这套系统不应只是“会使用易经知识的语言模型”，而应成为：

**以多尺度象表征世界，以数构造可计算空间，以理组织关系和约束，以类进行结构迁移，以变进行动态推演，并由证据持续修订自身认知的系统。**

易象理论必须进入核心计算，而非停留在提示词、知识库或 UI 层。其有效性最终由消融实验、跨领域迁移、反例测试和移动端资源曲线决定。
