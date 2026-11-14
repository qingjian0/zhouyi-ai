# 开发路线图

> 项目最高研究优先级为易象理论与类象认知。清以前文献为研究主体，清代及以后用于校勘、辑佚、补漏和学术审查。

| 阶段 | 目标 | 交付物 | 状态 |
|---|---|---|---|
| P0-A | 类象理论本体 | 多维类象、关系保持、边界条件、反例与证据规范 | v0.1 本体草案与类象记录规范已建立，待文献校勘/专家审阅 |
| P0-B | 易学概念校勘 | 阴阳、四象、八卦、六十四卦、爻位、卦序、卦变规范 | 编码约定与结构转移原型已实现；经典来源校勘待开展 |
| P0-C | 类象数据体系 | 经典语料、结构数据、跨域案例、合成基准与数据卡 | 候选书目 111 项；结构化语料 41 条候选记录、46 条文本主张；全文入库与逐条校勘待开展 |
| P0-D | 类象计算引擎 | 类象发现、解释、验证、迁移、组合和拒绝机制 | 规则评估、有界图映射、M2.1 候选评分和 M3 证据剖面基线已实现；学习型抽取/迁移待开展 |
| P0-E | 易象状态引擎 | 层次状态、爻位、卦变、状态转移与路径 | 64态结构编码与显式动爻转移原型已实现；经典语义/路径模型待开展 |
| P0-F | 五行与时位势变 | 条件关系、制化、乘侮、消长及动态演化 | 设计草案，模型实验未开始 |
| P0-G | 多尺度时间与层级过程 | 事件时间/观测时间、多尺度阶段、局部—整体递归 | M1 时间层级/区间关系原型与合成基准已有记录；M2 typed relation、M2.1 双向候选约束已实现；结构扰动实验和真正递归消息传递待开展 |
| P0-H | 竞争类象与证据裁决 | 多假设保留、适用边界、未决机制、反例驱动更新 | M3 已实现证据分层、多维剖面、条件状态、反例保留及未决规则；概率校准、标注一致性与学习型裁决待开展 |
| P1-A | 反事实与干预边界 | 条件变化、反事实一致性、混杂识别与拒绝 | M4 显式条件干预规则基线已实现；混杂识别、真实干预验证与概率模型待开展 |
| P1-B | 主动观测 | 信息增益、预测分歧、观测成本与选择偏差 | M5 离散假设/结果的信息增益与成本—风险—可行性—选择偏差排序原型及合成测试已添加；真实观测校准、连续结果和序贯决策待开展 |
| P1-C | 新象发现与结构重组 | 残差聚类、候选新象、版本化、回滚 | M6 精确 typed-signature 残差分组、跨域/多来源门槛、人工审查版本与回滚原型已提交；独立留出验证和模糊聚类待开展 |
| P1-D | 多视角类象生成与组合 | 分轴候选、竞争解释、独立桥接证据、非单调拆解 | M9 多视角候选、独立桥接、情境失效重审与涌现主张结构审计已提交；run #43458221635 的 403 项单元测试及 E01/E02 全部步骤均成功；真实任务效益与 M8 分轴基准接入待开展 |
| P1 | 易象驱动的组合认知 | 动态超图、并行推演、证据协调、自组织 | M7 M3–M6 透明规则编排原型已提交；持久化事件账本、真实观测执行与在线学习待开展 |
| P1-E | 组合涌现实验审计 | 预注册、单体基线、桥接/成员消融、替代解释控制、情境外推检查 | M10 v0.1 实验审计原型、16 项专项测试与专题文档已提交；强制替代解释控制修复 head #ed3ad21 的完整 CI run #43478474906 成功；仅计算描述性对照，尚无真实实验数据 |
| P1-F | 动态类象网络 | 穷—变—通—久阶段证据、关系转移事件、循环/分叉轨迹、跨窗口持续性审计 | M11 v0.1 动态网络审计原型、14 项专项测试与专题文档已提交；包含持续性证据修复的 head #c8d506c 的完整 CI run #43478566944 成功；不做因果或预测主张 |
| P1-G | 条件约束的多路径竞争 | 同起点同终点、多条路径、情境轴门禁、失败/可行/未知分层 | M12 v0.1 原型、17 项专项测试与专题文档已提交；代码 head #47e27f9 与文档 head #596b60b 的完整 CI 均成功；保留竞争路径，不选最优路径 |
| P1-H | 角色—机制—条件联合迁移 | 角色双射、关系拓扑/极性/方向、机制步骤、条件变换、证据与反例门禁 | M13 v0.1 原型、24 项专项测试与专题文档已提交；最新 head #ad837f3 的完整 CI run #43481065110 成功；仅作范围内结构对应审计，不声称因果迁移 |
| P1-I | 文本见证谱系与主张证据审计 | 见证来源 DAG、转引依赖、共同祖先、证据立场、人工审查状态与冲突保留 | M14 v0.1 原型、26 项专项测试与专题文档已提交；最新 PR head #8d1fc27 的完整 CI run #43485420130 成功；只审计声明谱系，不认证真伪或语义蕴含 |
| P1-J | 文本片段—类象主张语义范围审计 | 主张原子化、片段覆盖范围、上下文适配、正文/注释/引文分层、异文保留与反例审计 | M15 v0.1 原型、24 项专项测试与专题文档已提交；新增未决证据门禁，阻止未审查证据与完整支持并存时误报完整覆盖；补强 head 的 CI 待验证（此前 head #9a743ea 的完整 CI run #43488706432 成功）；显式记录正文/注释/引文等文本层，不自动判断语义蕴含或真理 |
| P1-K | 古典论辩术语的竞争解释审计 | 解释史分层、原典锚点、逻辑分类/论辩过程/统一类比框架竞争、共享依据与解释独立性边界 | M16 v0.1 解释竞争登记原型、种子解释登记数据/Schema、15 项专项测试与专题文档已提交；不选胜者、不固化古典术语与现代逻辑类别的一对一映射；最新 head 完整 CI #43502670578 成功 |
| P1-L | 动态情境修订与旧主张失效传播 | 情境版本、目标/维度/前提变更、受影响类象主张局部重审 | M22 v0.1 原型、专项测试与专题文档已提交；显式审计扩展/收缩/修订、排除维度变化与 stale-claim；等待 exact-head CI；不认证语义有效性 |\n| P1-M | 观象—取象—立类形成机制 | 原始观察、特征选择、任务目的、类别判准、成员证据与反例的可追溯链 | M23 v0.1 原型、21 项专项测试与专题文档已提交；仅审计来源链完整性，不自动感知或判真；等待 exact-head CI |
| P1-EVAL | 理论贡献验证 | 消融、跨域迁移、错误类比拒绝、OOD 与成本评估 | M5/M6/M7 测试已接入；修正 M6 测试断言后，最新 CI 待验证；此前 head 曾因断言不匹配失败 |
| P1-EVAL-M8 | 类象有效性与迁移基准 | 独立 case schema、四态裁决 gold、来源谱系泄漏检测、分层指标 | M8 v0.1 schema/validator、四态评估、关系族/来源状态分层指标、来源谱系与独立性分组泄漏报告、gold 资格门禁、命令行报告入口及 47 条 synthetic fixtures 已提交；run #43458221635 的 403 项单元测试及 E01/E02 全部步骤成功；人工 gold 标注未开始 |
| P2 | 通用模型与工程 | 语言生成、训练优化、加速、部署 | 按核心研究需要推进 |

## 近期研究主线

1. M1：多尺度时间表示和合成基准。
2. M2：整体—局部 typed relation 与结构扰动实验。
3. M2.1：局部证据评分整体假设，整体预期反馈局部核验。
4. M3：竞争类象、证据分层、适用条件与未决裁决。
5. M4：反事实与干预边界（显式条件干预、未知保留、稳定性/状态变化判定）。
6. M5：主动观测的信息增益基线（见 `docs/YIXIANG_ACTIVE_OBSERVATION_M5_V0_1.md`、`prototype/yixiang_active_observation.py`）。
7. M6：残差驱动的新象提议、人工审查、版本化和回滚（见 `docs/YIXIANG_NOVELTY_DISCOVERY_M6_V0_1.md`、`prototype/yixiang_novelty.py`）。
8. M7：统一闭环与公平消融（见 `docs/YIXIANG_UNIFIED_COGNITIVE_LOOP_M7_V0_1.md`、`prototype/yixiang_m7_pipeline.py`）。
9. M9：多视角类象候选竞争与有独立桥接证据的显式组合（见 `docs/YIXIANG_M9_MULTIVIEW_COMPOSITION_V0_1.md`、`prototype/yixiang_multiview_composition.py`）。
10. M10：预注册组合涌现实验审计（见 `docs/YIXIANG_M10_EMERGENCE_EXPERIMENT_V0_1.md`、`prototype/yixiang_emergence_experiment.py`）。
11. M11：动态类象网络与穷—变—通—久阶段证据审计（见 `docs/YIXIANG_M11_DYNAMIC_NETWORK_V0_1.md`、`prototype/yixiang_dynamic_network.py`）。
12. M12：条件约束的多路径类象竞争审计（见 `docs/YIXIANG_M12_PATH_COMPETITION_V0_1.md`、`prototype/yixiang_path_competition.py`）。
13. M13：角色—机制—条件联合迁移审计（见 `docs/YIXIANG_M13_ROLE_CONDITIONED_TRANSFER_V0_1.md`、`prototype/yixiang_role_conditioned_transfer.py`）。
14. M14：文本见证谱系与类象主张证据审计（见 `docs/YIXIANG_M14_EVIDENCE_PROVENANCE_V0_1.md`、`prototype/yixiang_evidence_provenance.py`）。
15. M15：文本片段—类象主张语义范围审计（见 `docs/YIXIANG_M15_PASSAGE_CLAIM_SCOPE_AUDIT_V0_1.md`、`prototype/yixiang_passage_claim_audit.py`）。
16. M16：《墨子·小取》“七事”解释竞争与术语映射防固化（见 `docs/YIXIANG_M16_INTERPRETATION_COMPETITION_V0_1.md`、`prototype/yixiang_interpretation_competition.py`）。
17. M17：类推迁移门禁——同类不等于可推（见 `docs/YIXIANG_M17_ANALOGY_TRANSFER_AUDIT_V0_1.md`、`prototype/yixiang_analogy_transfer_audit.py`）。\n18. M22：动态情境修订与旧主张失效传播（见 `docs/YIXIANG_M22_CONTEXT_REVISION_V0_1.md`、`prototype/yixiang_context_revision_m22.py`）。\n19. M23：观象—取象—立类形成机制（见 `docs/YIXIANG_M23_FORMATION_V0_1.md`、`prototype/yixiang_formation.py`）。

M5/M6 当前均为透明规则原型；M6 的“新”只表示不在调用方提供的已知签名集合中，不代表发现了客观新规律。

M1 文档与实现见 `docs/YIXIANG_MULTISCALE_TIME_M1_V0_1.md`、`prototype/yixiang_multiscale_time.py`；M2 见 `docs/YIXIANG_HIERARCHICAL_STRUCTURE_M2_V0_1.md`、`prototype/yixiang_hierarchical_structure.py`；M2.1 见 `docs/YIXIANG_BIDIRECTIONAL_CONSTRAINTS_M2_1_V0_1.md`、`prototype/yixiang_bidirectional_constraints.py`；古籍类象校勘札记见 `docs/CLASSICAL_YIXIANG_THEORY_NOTES_PREQIN_HAN_V0_1.md`；《墨子·小取》类推与异文专题见 `docs/CLASSICAL_YIXIANG_MOZI_XIAOQU_ANALYSIS_V0_1.md`；跨时代综合框架见 `docs/CLASSICAL_YIXIANG_THEORY_SYNTHESIS_V0_2.md`；古籍数字来源与版本规程见 `docs/CLASSICAL_TEXT_DIGITAL_SOURCE_POLICY_V0_1.md`；M3 见 `docs/YIXIANG_COMPETING_HYPOTHESES_M3_V0_1.md`、`prototype/yixiang_competing_hypotheses.py`；M4 见 `docs/YIXIANG_COUNTERFACTUAL_M4_V0_1.md`、`prototype/yixiang_counterfactual.py`。

## 执行原则

1. 区分形态、属性、功能、关系、过程、时空、势象与综合象。
2. 建立经典概念和卦爻编码校勘表，保留不同传承/注本的差异。
3. 固定数据 schema、来源追溯、标注规范、反例和数据划分。
4. 实现类象发现—解释—验证—迁移的最小闭环。
5. 将阴阳、四象、八卦、六十四卦、爻位和卦变接入可执行计算图。
6. 实现五行条件关系及时间、位置、阶段和趋势建模。
7. 将 P0 机制与动态超图、并行推演、自组织机制集成。
8. 做参数/数据/算力匹配的消融与跨域实验，再决定是否扩大训练。

## 原有实验的处理

E01/E02、GF(2)、ANF、高阶关系和优化器研究不删除；保留为底层数学工具或对照实验。只有能明确支持 P0 理论机制、模型能力或评估的部分，才列入近期主线。


### M8 当前实现边界

`prototype/yixiang_benchmark.py` 提供 benchmark case/dataset/prediction 校验；`prototype/yixiang_benchmark_report.py` 提供 JSON 报告 CLI、四态混淆矩阵与 macro-F1、缺失预测按 abstain 计分、关系族/来源状态分层混淆矩阵与 Macro-F1、abstention coverage / selective risk，以及 `source_lineage` / `independence_group` 跨 split 泄漏报告。Schema 和 validator 以 `label_status` 区分 `fixture_expected`、`pending_review`、`adjudicated`；synthetic fixture 不允许伪造 reviewer 记录，人工 adjudicated 标签要求至少两个不同 reviewer ID（仍需人工核验其真实独立性）。`data/yixiang_benchmark_synthetic.v0.1.json` 的 12 条样本仅用于接口测试，不是古籍 gold 数据，不得用于声称类象理论有效。人工标注、标注一致性统计、关系族分层 F1/置信区间、M7 输出适配仍待实现。


### 本轮古典类象研究补充

新增《先秦两汉类象拒推机制专题》：对读《墨子·小取》《荀子·非相》《淮南子·说林训》《韩非子·难势》《论衡·感类》，归纳局部同不等于整体同、结果同不等于所以然同、表面代理不等于目标属性、推类不悖与辨异不过、同物异用与主体情境适配、势与材交互、时间先后不等于因果、抽象对应不能替代具体机制八类拒推机制。研究范围扩展至《荀子·正名》《论衡·物势》，共五部典籍、七篇重点篇章。所有文本仍是数字见证级研究，未升级为校勘定本或 M8 adjudicated gold。


### M9 当前实现边界

M9 v0.1 将形态、结构、功能、过程机制、时间、情境和象征规范七类关系轴作为彼此独立的候选视角。竞争分组不排名、不强制唯一赢家；复合提案要求同一有序观察对、不同关系轴、成员 ID 精确匹配、共同适用范围，以及不复用成员视图证据的独立桥接证据。组合结果固定为 HUMAN_REVIEW。该原型尚未接入 M7 自动编排或 M8 分轴留出评估；桥接证据的真实性、独立性和语义充分性仍需上游来源谱系系统及人工审查验证。


### M17 当前实现边界

M17 v0.1（19 项专项测试）将类推迁移拆为共同特征、迁移主张、推论根据、关系结构、适用范围、条件与反例七类审计字段。原型允许未知门禁并保持未决；反例优先阻断；全部声明门禁通过也只输出 PROVISIONAL_TRANSFER，不认证语义有效性或真理。原典案例集登记《墨子·小取》的白马/骊马、车/木、盗人/人、同然异所以然、同取异所以取五组，并新增《淮南子·说林训》的物种差异、材料来源、主体用途与姿态情境五组反例，以及《荀子·正名》《荀子·非相》的推类规范与外貌代理拒推两组案例。当前仍是结构审计框架，不是语义自动判真器；需后续接入 M14 来源谱系、M15 片段—主张审计、M16 解释框架选择，并以人工审定古籍案例验证。


### M18 当前实现边界

M18 v0.1 提供 M17 casebook 到 M8 benchmark 的安全适配器，当前 10 项专项测试。所有案例均保持 unverified_transcription + pending_review，gold_decision=abstain 仅为占位；reviewers 为空、split_group=exploratory，M8 evaluate_predictions 会拒绝评分。shared/non-shared basis、scope、invariants 与 counterexamples 不从 audit_focus 自动生成，未知映射直接报错。此批数据不是人工 gold，不得用于正式性能结论。


### M19 当前实现边界

M19 v0.1 提供人工审定包与状态机，当前 20 项专项测试。来源核验、两份独立标注、分歧登记和独立最终裁决分层保存；一致标注不会自动升级为 gold，未核验来源不能导出，裁决者必须明确给出最终 claim/文本层/关系族/依据/范围/不变量/反例/因果状态。只有显式裁决且来源核验、身份隔离等门禁通过，才可导出 M8 adjudicated case；导出时仅使用裁决者的最终标注，不从任一初审者记录中抽取字段。程序不能验证现实身份或判断文本真伪，仍需人工抽查和来源谱系审计。


### M20 当前实现边界

M20 v0.1 新增 16 条 synthetic_fixture，组成 8 组成对对抗样例，覆盖关系方向、材料来源与属性继承、同结果异机制、主体目标、姿态几何、物种条件、外观代理、类属与数量谓词。每一对共享 independence_group 且同 split；holdout 仅为模板留出，不等同真实世界 OOD。10 项专项测试验证数据契约、配对隔离、关键标签、反例字段与 M8 fixture opt-in。全部样例不是古籍 gold，不能用于理论有效性结论。


### M23 当前实现边界\n\nM23 v0.1 将观测、特征选择、类别归属分层保存，校验特征是否引用已有观察证据、选择理由与任务目的是否登记、类别判准和成员证据是否存在、反例是否得到显式处理。原型只审计来源链与声明完整性，不做自动感知、不强制单标签分类，也不认证类别真值。\n\n\n### M22 当前实现边界\n\nM22 v0.1 提供情境版本修订与 stale-claim 传播账本；仅验证声明完整性，不判定情境变化的语义正确性。\n\n\n### M21 当前实现边界

M21 v0.1 新增成对评估器与 12 项专项测试，使用 M20 的 contrastive independence_group 计算 pair_exact_accuracy、decision_flip_sensitivity、collapsed_pair_rate、pair_selective_coverage 和 pair_selective_risk。每组必须恰好两例、同 split、预期决策不同；fixture_expected 必须显式 opt-in，pending_review 和混合标签状态拒绝评分。该指标只补充 M8，不取代逐类指标；当前数据仍是合成夹具。
