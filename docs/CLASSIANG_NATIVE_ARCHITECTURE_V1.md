# 类象原生认知、计算与训练架构 v1

状态：设计契约（不是能力验收报告）  
目标分支：`dev`  
实现分支：`feat/classiang-native-core-v1`

## 0. 设计决策

Zhouyi-AI 的核心不是把类象标签附加到语言模型，也不是把 Transformer 换一个名称。核心计算对象是带证据、上下文、适用域和版本的**象—关系—过程结构**。系统以结构化对象和关系组合为基本计算单位；文本 token、图像 patch、音频帧仅属于外部模态编码接口。

核心架构分为三个共同设计、不可互相替代的部分：

1. **类象认知架构**：观象、取象、立类、比类、推类、验类、修类。
2. **类象计算架构**：象元、关系边/超边、角色绑定、组合算子、约束传播、候选搜索、证据门控、状态记忆。
3. **类象训练框架**：证据监督、正反对照、关系保持、组合泛化、反例修订、拒绝校准、持续学习和可复现实验。

不得以自洽分数替代外部证据，不得把相关性/结构对应升级为因果等价，不得将模型生成标签直接写入 Gold。

## 1. 原生表示：象元（Image-Concept Unit）

每个象元是一个可版本化的、具有证据来源的结构对象，至少包含：

- 稳定 ID、schema 版本、对象版本、生命周期状态；
- 观察对象/事件 ID、领域、任务目的和上下文；
- 多维属性：形态、属性、功能、关系、过程、时空、势态、整体；
- 角色与部分—整体结构；
- 证据引用、来源族、原文跨度/外部观测定位、许可状态；
- 不确定性、适用条件、有效范围和反例；
- 与其他象元的显式关系及关系方向、角色、时间和条件。

八个维度是可多选的观察切面，不是互斥类别，不构成先验真理。象元不要求必须有文本 embedding；可同时拥有符号字段、稀疏特征和可学习连续表征。

## 2. 原生关系与组合

关系不是简单的向量相似度。关系结构至少表示：

- relation type 与方向/对称性；
- 有序角色（source、target、agent、patient 等可扩展角色）；
- 二元边或多元超边；
- 时序、上下文、条件和作用范围；
- 证据与反例；
- 结构置信和校准状态。

组合操作定义为受约束的结构构造，而非拼接 token：

- **绑定**：把对象填入关系角色；
- **组合**：连接共享对象/角色兼容的关系结构；
- **投影**：在任务条件下选择相关子结构；
- **匹配**：计算角色、关系、过程与约束保持程度；
- **推演**：从已验证结构生成有限候选后果；
- **反证**：查找违反结构约束或预测后果的证据；
- **修订**：局部限缩、拆分、合并、降权、撤销或保留未知。

任何搜索必须有候选数、深度、时间/内存预算；超预算时返回截断状态，不得伪称穷举完成。

## 3. 认知闭环

`observe → select_aspect → form_class → compare → infer/transfer → verify → revise`

- 输入适配器只负责转换和定位，不替来源背书。
- 取象输出必须保留被选、被排除和未评分特征。
- 立类必须有正例、明确负例和未知例的区别。
- 比类输出角色映射、共享结构、差异及不可映射部分。
- 推类必须声明前提、条件和有效范围。
- 验类必须执行证据、反例、预测后果与冲突门控。
- 修类必须产生新版本和事件；证据不足则弃权。

认知阶段可回退：新证据可以要求重做解析、取象或映射，不允许把早期假设固化为事实。

## 4. 计算架构

计算核心由以下 backend-neutral 协议组成：

1. `SymbolStore`：对象、象元、关系、证据和版本的权威结构存储。
2. `FeatureProjector`：将多模态编码器输出转换为带来源的候选属性。
3. `RoleBinder`：执行类型/角色约束绑定。
4. `CompositionEngine`：生成稀疏、有界的关系组合候选。
5. `StructureScorer`：评分角色一致、关系保持、过程约束和证据支持。
6. `ConstraintPropagator`：执行冲突检测、约束传播与不确定性更新。
7. `EvidenceGate`：拒绝来源不明、证据冲突或超出适用范围的结论。
8. `RevisionController`：维护版本、反例、撤销和可重放修订事件。
9. `Scheduler`：按任务预算分配候选计算，可并行评估互相独立的路径。

核心语义与算子定义不得依赖某个深度学习框架。训练后端可选 PyTorch 等张量库，但不得引入 Transformer self-attention 作为核心推理路径。允许外部语言模型充当可替换输入/输出适配器，且必须单独报告其能力贡献。

## 5. 学习与训练架构

训练对象不是只有下一个 token，而是结构化类象能力：

- 证据跨度与属性提议；
- 任务条件取象；
- 象元/类别边界；
- 角色绑定与关系结构；
- 关系保持映射；
- 组合候选排序与组合泛化；
- 预测后果与反例识别；
- 未知检测、弃权与置信校准；
- 增量更新及旧域能力保持。

训练目标按可用监督组合：证据定位损失、正负边界损失、角色分配损失、关系结构损失、组合一致性损失、反例排序损失、校准损失及防遗忘正则。每个损失必须有独立可解释的标签来源与消融实验。纯粹的内部自一致性只能作为辅助正则，不能成为唯一学习信号。

数据集必须包含来源 ID、来源族、group ID、许可、标注者/仲裁状态、证据位置和 schema 版本。切分按来源族/对象族/关系模板族隔离；锁定测试标签不能进入训练或阈值选择。未标注不等于负例。

## 6. 模型形态与生成

第一代模型采用**关系结构驱动、组合式、非自回归候选推演**：并行产生有限的象元/关系候选，通过角色绑定和证据约束组合，再进行验证和排序。它不以 token-by-token 自回归作为内部认知机制。

语言生成是结构化结果的渲染过程：先形成可审计的结构结论，再由输出适配器表达为自然语言/JSON/代码。若语言接口使用外部模型，评测必须区分“原生类象核心结果”和“外部语言模型润色结果”。

这并不意味着禁止 tokenizer 或文本解码器；它们是 I/O 组件，不是核心认知计算单元。

## 7. MVP 垂直切片

第一条可验收路径：

`reviewed observation → evidence-bound aspect proposals → native symbol/role graph → bounded composition → structural inference → counterexample gate → versioned revision → report`

验收必须提供：

- clean-checkout 安装和运行命令；
- 确定性单元测试及端到端测试；
- 至少一个可复现的合成结构任务；
- 至少一个有许可、来源可追溯的真实任务集；若真实 Gold 不足，必须明确标记真实能力验收未通过；
- 同输入下的简单基线、消融和预算匹配对照；
- 组合 OOD、关系反转、表面相似但结构错误、低表面相似但结构保持、未知拒绝和反例局部修订测试；
- 数据摘要、配置、随机种子、代码 commit SHA、参数量、运行时和峰值资源。

## 8. 明确不算完成的情况

- 只有架构文档、接口空壳或随机权重；
- 只会输出文本或记忆训练样本；
- 只在合成数据上高分；
- 只用内部自一致性目标训练；
- 将人工提供的特征当成模型自主感知；
- 将关系相似当成语义/因果等价；
- 将 Transformer/外部 LLM 的输出能力算作原生核心能力；
- 仅有 CI 通过而没有能力评测。

## 9. 与现有项目资产的关系

现有 `classiang_engine.py`、`classiang_pipeline.py`、文本跨度学习器、对比学习器、SROK/CPG-EI、动态超图和易象状态模块均保留为可替换的基线/候选后端。先用统一数据契约接入并做消融；若不能提升类象任务指标，不因历史投入而保留为核心路径。

本设计不废弃既有 CPG-EI 研究，也不预设其已胜出。CPG-EI、SROK、易象先验必须在相同数据拆分、计算预算和指标下接受验证。

## 10. 状态声明

本文定义目标架构和实现约束，不证明模型已实现或能力已成立。实现状态以代码、测试、数据和精确 commit 为准。

## 11. 认知引擎到原生图的适配器

`prototype/classiang_native_adapter.py` 将现有证据约束类形成引擎接入原生符号图：

- 输入为已验证的 `Observation`、可选的 `ClassHypothesis` 和显式证据目录；
- 观察主体、观察属性、类别假设、必需属性和负边界分别映射为符号；
- `has_aspect`、`class_requires_aspect`、`class_excludes_boundary` 等关系保留角色方向和证据引用；
- 显式矛盾必须单独提供逐项证据映射；缺少映射、证据缺失或未审核证据均失败关闭；
- 适配器不生成证据元数据、不推断语义等价，也不把未评分属性当成负例。

最小示例：

```python
from prototype.classiang_native_adapter import observation_to_symbol_graph

graph = observation_to_symbol_graph(
    observation,
    evidence_catalog,  # {evidence_id: reviewed EvidenceRef}
    hypothesis=class_hypothesis,
)
graph.validate()
```

这一步打通了现有类形成/反例边界与原生计算图的数据通路；它仍然是人工/上游提供属性候选的结构适配，不代表模型已经自主感知或端到端学习类象。

## 12. 认知循环到原生计算的统一入口

`prototype/classiang_native_pipeline.py` 提供 `run_native_classiang_cycle`：

1. 调用现有 `run_classiang_cycle` 执行取象、立类、成员评估及可选反例修订；
2. 将查询观察和当前有效类别假设投影为带来源的原生符号图；
3. 执行有界关系组合并保留候选证据链；
4. 可选地用已训练且词表兼容的原生评分器排序。

它不自动生成证据、不绕过人工审核，也不会将结构匹配升级为语义或因果结论。若类别假设的证据未出现在证据目录中，适配过程直接失败。

## 13. Gold 文本数据到原生训练图

`prototype/classiang_native_dataset.py` 是数据准备阶段，先调用 Gold manifest 准入校验，再按 `--split train` 或 `--split dev` 分别导出原生图和标签；不允许导出 locked-test：

```bash
python -m prototype.classiang_native_dataset path/to/manifest.json \\
  --graph-out artifacts/native-train-graph.json \\
  --labels-out artifacts/native-train-labels.jsonl \\
  --report-out artifacts/native-dataset-report.json
```

也可以使用隔离编排入口一次完成数据准备和训练：

```bash
python -m prototype.classiang_native_train path/to/manifest.json \\
  --checkpoint artifacts/classiang-native-role-binding.json \\
  --training-report artifacts/classiang-native-training-report.json
```

该命令分别启动 train 与 dev 数据准备子进程，再启动学习器子进程：train 图/标签用于拟合，dev 图/标签用于独立验证；locked-test 标签不传入学习器。任一准入或导出阶段失败，均不会构造模型。

当前第一版监督语义明确限定为：

- 正例：同一人工审核记录中共同标注的两个正向类象属性；两条关系共享同一个 observed subject。
- 负例：同一 source family 中来自两个不同观察记录的正向属性配对；两条关系具有相同的 has_aspect 类型，但指向不同 observed subject。

正负样本共享基础关系类型，因此不能仅凭 has_aspect / negative-marker 关系类型读取标签。证据 ID 包含 observation ID，避免同一来源内不同记录的相同字符偏移发生碰撞。train 与 dev 分别导出，locked-test 记录不会进入任何学习器输入。

**重要限制：当前负例不是经过语义仲裁的 hard negative。** 它只是从同一来源族的不同 observation 中抽取关系对。正例共享 observed subject，负例不共享 observed subject，因此 shared-subject overlap 与标签完全混杂。模型可以只学习“关系对是否共享主体”而不学习类象兼容性或组合规律。当前数据只能用于验证数据管线和结构特征的可学习性，不得作为类象组合能力的证据。

下一阶段必须在 Gold schema 中加入独立人工审核的 relation-pair compatibility annotation（positive / explicit-negative / unknown，带 reviewer、adjudication、证据和条件范围），并按 source family、对象族和关系模板族隔离切分。只有这类独立标签才可用于组合泛化训练；跨记录抽样只能作为未标注候选，不得自动赋负标签。真实任务能力仍需独立 Gold、OOD、反事实和反例评测证明。

## 14. 当前可执行训练接口

当前实现包含两个层级：

- **结构基线评分器**：确定性逻辑回归，输入为五项显式结构描述特征。
- **原生角色绑定学习器**：学习象元类型、属性键/值、关系类型和角色的向量表征，通过关系—角色绑定能量与可学习的共享象元交互项对组合进行评分，不依赖 token 自注意力。

角色绑定学习器仍是小规模实验模型：它的输入属性来自已构造的符号图，不具备自主感知或通用语义理解能力；关系算子也尚未覆盖高阶过程、时序和反事实推演。当前 exporter 的 shared-subject 结构与标签混杂，训练报告必须输出该捷径诊断；验证报告同时输出符号类型、属性键和值的词表覆盖率，避免部分 OOV 被静默忽略后误读分数。

训练输入由两个文件组成：

- **图结构 JSON（schema_version: 1）**：包含 `evidence`、`symbols`、`relations` 三个数组，字段对应 `prototype/classiang_native.py` 中的数据结构。
- **标签 JSONL**：每行一条经审核的组合样本，字段包括 `example_id`、`group_id`、`source_family`、`relation_ids`、`evidence_ids`、二元标签 `label` 和 `reviewed: true`。

标签证据必须覆盖所引用关系的全部证据，且只能属于声明的来源族。训练/验证按来源族隔离，同一关系 ID 不允许跨越两个集合。至少需要两个来源族，并且训练集必须同时包含正例和负例。

运行命令：

```bash
python -m prototype.classiang_native_learning graph.json labels.jsonl \
  --model role-binding --dimension 16 \
  --checkpoint artifacts/classiang-role-binding.json \
  --report artifacts/classiang-role-binding-report.json
```

报告包含随机种子、来源族切分、混淆矩阵、准确率、精确率、召回率、Brier 分数，以及图结构、标签和检查点的 SHA-256 摘要。使用 --model linear 可运行结构基线。模型分数只表示结构兼容性排序；高分不证明语义同一、类比有效或因果关系成立。

该学习器与认知引擎适配器只是后续原生角色/关系参数化表示、多目标组合学习、拒答校准和独立 OOD 基准的起点。不得将其称为 Zhouyi-AI 基础模型。
