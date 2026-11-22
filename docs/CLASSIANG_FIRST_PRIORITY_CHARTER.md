# Zhouyi-AI 类象认知主线与工程验收纲领

版本：v1.0  
生效基线：2026-11-19  
集成分支：`dev`；稳定分支：`main`

## 1. 定位

类象是 Zhouyi-AI 的主体能力，不是易象系统中的一个附属模块，也不等同于文本相似度、向量近邻或固定分类表。项目目标是建立领域无关、证据约束、可学习、可拒绝、可修正的类象认知引擎。

易象、周易经典、八卦、五行、墨家“类/故/理/譬”、荀子正名及其他领域知识是可接入的知识源、解释传统或结构先验。任何一种知识源都不能垄断通用类象的类别边界。

### 术语边界

本项目将“类象认知”作为整体工程主线的统称，但保留本体中的严格术语：**象类**是具有可说明共同结构的一组象/对象类别；**类象**是经过显式映射、关系保持、适用条件和证据审查后，在有限范围内成立的对应。立类与类象验证不是同一操作，频繁共现或共享特征不能直接证明类象成立。

当前 `classiang_engine.py` / `classiang_discovery.py` 主要覆盖任务条件取象、象类候选形成与边界基线；跨对象/跨领域的类象映射和验证继续复用 `analogy.py`、`dynamic_analogy.py`、`yixiang_analogy.py` 与 M58，不把本轮 MVP 宣称为完整类象能力。

`ANALOGY_COGNITION_SPEC.md` 中的八类维度是可多选的观察切面，不是互斥类别，也不是“九大类别”分类表。若要引入更高层类别本体，必须先从现有来源和数据中审计其定义、成员边界及版本，不得把八个观察维度直接改名为类别。

## 2. 统一认知闭环

`observe → select_aspect → form_class → compare → infer/transfer → verify → revise`

1. **观象（observe）**：接收对象、事件、文本片段或结构化观测，保留原始来源和上下文。
2. **取象（select_aspect）**：围绕当前任务选择形态、属性、功能、关系、过程、时空、势及综合特征；每项选择必须说明依据和被排除的替代特征。
3. **立类（form_class）**：形成可版本化的类别假设、成员规则、非成员边界、正例/负例/不确定例及开放集拒绝状态。
4. **比类（compare）**：比较对象或类别，建立角色映射、关系保持、差异和不可映射部分。
5. **推类/迁移（infer/transfer）**：在显式条件、上下文和有效范围内迁移关系、过程或机制；区分结构对应与因果等价。
6. **验类（verify）**：检查证据来源、结构保持、预测后果、反例、任务结果和不确定性。
7. **修类（revise）**：根据新证据执行保留、限缩、拆分、合并、降权、撤销或继续未知；所有修改保留版本和审计轨迹。

闭环应允许从任一阶段返回前序阶段。新证据可能改变取象目的、类别边界或映射范围，不能把类别当成永久标签。

## 3. 八类取象维度

- `morphology`：形态、组成、拓扑、边界、层次、部分—整体。
- `attribute`：性质、数量、强弱、方向、状态。
- `function`：功能、角色、用途、输入输出、作用。
- `relation`：对象间有向/无向及高阶关系，方向与对称策略必须显式定义。
- `process`：发生、发展、转折、衰退、循环及机制。
- `spatiotemporal`：位置、阶段、顺序、环境、尺度和时间。
- `potential`：趋势、潜势、稳定性、临界变化。
- `integrated`：多维特征和关系共同形成的整体模式。

这些维度是可多选的观察切面，不是互斥类别，也不是类别成立的证据。相同维度标签不能直接推出两个对象属于同一类。

## 4. 核心数据契约

统一类象记录至少包括：

- 稳定 ID、schema 版本、记录版本和生命周期状态；
- 源对象/目标对象、领域、任务目的和上下文版本；
- 原始观测、特征候选、选中特征、特征来源和选择理由；
- 类别假设、成员规则、边界条件、正例/负例/未知例；
- 类象维度、对象/角色映射、关系映射及未映射部分；
- 支持证据、反例、来源版本、定位信息和许可状态；
- 置信度、校准信息、适用条件、有效范围；
- 预测后果、验证结果、拒绝原因和修订事件。

置信度是模型输出，不是正确率。证据引用必须能回到真实来源；模型生成文本不能冒充原始文献证据。

## 5. 统一架构分层

- **Observation Adapter**：多模态/文本/结构化输入适配，不负责替证据背书。
- **Aspect Selector**：任务条件化的特征与关系选择，支持多维和不确定输出。
- **Class Inducer**：类别假设生成、边界发现、开放集识别和类别版本管理。
- **Analogy Mapper**：实体/角色/关系/过程映射，区分部分映射与完整映射。
- **Transfer & Inference Engine**：在条件约束下执行推类、组合与预测。
- **Evidence & Counterexample Gate**：来源追踪、冲突处理、反例门控、校准和拒绝。
- **Revision Controller**：执行类别/映射的限缩、拆分、合并、撤销和回滚。
- **Domain Knowledge Plugins**：易象、周易、古籍、五行及其他领域知识；可单独启用/禁用并做消融。
- **Learning Backends**：规则、符号搜索、图模型、神经模型和 CPG-EI/SROK；通过统一协议竞争，不预设某种后端必然胜出。

## 6. 现有成果复用与缺口

| 现有资产 | 在主线中的职责 | 不能夸大的能力 |
|---|---|---|
| `prototype/classiang_engine.py` | 任务条件取象、正负例差异立类、证据门控、暂定接受/拒绝/弃权 | 符号 MVP；上游 relevance 分数不是校准概率，类别规则不是语义真理 |
| `prototype/classiang_adapters.py` | 将通过 `assess_formation` 审计的观象→特征→类别轨迹转为类象 Observation，保留证据和上下文 | 只接入已审阅且完整的轨迹；维度和任务分数必须由调用方明确提供，不自动推断 |
| `prototype/classiang_discovery.py` | 有界 Apriori 无标签特征组合提议、支持度、成员及证据谱系 | 频繁共现基线，不是开放世界概念学习；搜索截断时不宣称完整 |
| `prototype/analogy.py` | 显式关系保持评估、证据门控、有限图映射搜索 | 不是从原始观测自动取象或学习映射 |
| `prototype/dynamic_analogy.py` | 状态事实、上下文和转移保持 | 不是因果发现或通用动态学习 |
| `prototype/yixiang_formation.py` | 观测→特征→类别声明的证据链完整性审计 | 不负责自动抽取特征或判断类别真伪 |
| `prototype/yixiang_m56_executable_core.py` | 类别形成/迁移/反例修正的隔离评测协议 | 合成生成器不等于被测认知模型 |
| `prototype/yixiang_analogy.py` | 显式类型/关系图映射校验 | 不等于真实语料理解 |
| `docs/ANALOGY_COGNITION_SPEC.md` | 八维类象记录、任务与指标规范 | 规范本身不是实现 |
| M56/M58 与 M20–M30 | 复用其任务协议、对抗样本和迁移审计 | 不把单一合成基准成绩外推到真实领域 |

首批 `classiang_engine.py`、`classiang_discovery.py` 与 `classiang_adapters.py` 已提供任务条件特征筛选、正负例差异立类、无标签频繁组合提议、成员三态判断，以及已审阅观象轨迹的证据保真接入；但仍依赖上游显式特征/ relevance 分数，频繁共现不等于语义概念。首要工程缺口转为原始观测解析、可学习特征提议、类别边界/开放集学习、反例驱动的局部修订、真实跨域数据和完整模型对照。

## 7. 研究与验收门禁

每项类象能力都必须同时有实现、测试、数据、基准和失败分析。最低评测矩阵：

- 表面相似但结构/机制不兼容；
- 表面差异很大但关系结构保持；
- 任务目的变化导致取象维度变化；
- 关系反转、角色置换、缺失/新增对象；
- 类别边界与开放集新类；
- 反例只应限缩局部范围，不得无依据全局推翻；
- 上下文/时空变化和动态状态迁移；
- 来源族、对象族、关系模板族和组合结构留出；
- 多种子、预算匹配、置信区间和错误类象拒绝率。

至少比较：无类象机制、表面相似度、特征匹配、关系图匹配、过程/机制匹配、符号类象基线和可学习模型。报告 precision/recall/F1、member/non-member 指标、映射覆盖率、invalid-transfer rate、abstention、校准、OOD 收益、成本和置信区间。

合成数据只验证受控结构。真实能力必须在有来源、许可、独立标注和仲裁记录的真实任务数据上验证。未运行的基准、未审阅的案例和历史 CI 均不得计为验收。

## 8. 研发优先级

- **P0 类象闭环**：统一协议与 API；整合现有模块；补齐任务条件取象、立类、比类、推类、验类和修类。
- **P1 真实数据与证据**：建立多领域、来源可追溯、双人独立标注/仲裁的 Gold 集及数据隔离。
- **P2 学习与泛化**：实现可学习特征选择、类别形成和映射提议；进行跨域、跨族和组合 OOD。
- **P3 计算基础设施**：按实际瓶颈调度 CPG-EI/SROK、M1/M2、N0.10、E12-A6 和并行推演；不得为基础设施指标牺牲类象任务效果。
- **P4 领域知识扩展**：接入易象/周易及其他领域知识，执行独立消融，保留流派差异和解释来源。
- **P5 集成发布**：clean-checkout E2E、权限/恢复/资源验收，先验收 dev，再审查是否发布 main。

## 9. 不可违反的边界

- 不把类象等同于易象；不把易象等同于全部类象。
- 不把相似度当作结构对应，不把结构对应当作因果等价。
- 不把候选、模型生成解释或未审阅案例升级为 Gold 事实。
- 不以模块数量、PR 数量、代码行数、合成数据规模代替认知能力。
- 不删除失败案例；不以跳过测试或放宽门槛制造绿色 CI。
- 所有结论绑定数据版本、协议、随机种子和精确 commit SHA。
- `dev` 是唯一集成目标；`main` 保持稳定，未经发布决策不修改。


## 10. Counterexample-driven local class revision (symbolic MVP)

`revise_class_with_counterexample` adds a deterministic revision primitive.
The caller supplies the complete positive and negative `ClassExample` sets
that produced the current hypothesis, plus one new evidence-grounded negative
example. The function verifies that supplied example IDs match the hypothesis
provenance, increments the version, and re-induces the discriminative feature
conjunction.

- If the new counterexample invalidates some required features but leaves a
  discriminative remainder, a new hypothesis version is returned with removed
  and added required features recorded.
- If the expanded evidence makes the rule underdetermined, the previous
  hypothesis remains active; the failed candidate is not silently installed.
- If the example provenance, purpose, or identity does not match, the update
  fails closed.

This is a pure symbolic proposal function. It does not persist revisions,
automatically discover semantic counterexamples, split/merge ontological
classes, or establish that upstream feature annotations are correct. Callers
must retain the complete evidence examples and persist accepted versions
through the project's lifecycle store if they need durable history.

## 11. Unified symbolic cycle API (P0 integration increment)

The prototype/classiang_pipeline.py module provides one orchestration entry
point for the currently implemented symbolic primitives:

- source-text span adapter that binds caller-reviewed feature annotations to exact Unicode character offsets and evidence references (without claiming autonomous text understanding);
- task-conditioned aspect selection;
- explicit pairwise observation comparison under one declared task, reporting shared and distinct aspects, evidence references and context without treating overlap as semantic equivalence;
- evidence-grounded class induction and query membership;
- optional bounded unsupervised feature-conjunction discovery;
- optional bounded injective entity-mapping discovery plus static and dynamic relation-preservation assessment;
- optional provenance-checked counterexample revision.

Transfer gating is deliberately fail-closed: the class must have a
discriminative boundary, the query must be provisionally accepted, at least
one explicit transfer candidate must be evaluated, and all supplied transfer
assessments must pass. A passed gate is only a structural/evidence result,
not proof of semantic or causal equivalence.

This API integrates the currently available symbolic components and now exposes each symbolic stage, including explicit observation comparison. It does not yet supply raw-text or multimodal feature extraction, learned feature proposal, calibrated confidence, ontology split/merge, persistent revision events, or real-domain Gold validation. These remain follow-on research and engineering work; the symbolic P0 integration must not be described as autonomous concept learning.