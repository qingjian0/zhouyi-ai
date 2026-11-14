# Zhouyi-AI / CPG-EI

**组合并行生成与易象启发式认知架构**  
*Combinatorial Parallel Generation & Epistemic Intelligence*

> 研究目标：探索一种不把自回归 Token 预测作为唯一内部计算范式的认知架构。通过动态语义组合、高阶关系建模、多路径并行推演、易象状态表征与证据约束的自组织学习，研究更灵活的组合泛化与推理机制。

## 项目状态

- 当前阶段：M1–M15 研究原型、基准与透明规则门禁持续扩展；M10 现有 16 项专项测试并强制替代解释控制臂；M11 现有 14 项专项测试审计穷—变—通—久证据；M12 现有 17 项专项测试审计条件约束下的多路径竞争、循环路径与证据复用；M10 强制替代解释控制修复 head 的完整 CI #43478474906 成功；M11 动态网络及持续性证据修复 head 的完整 CI #43478566944 成功；M12 代码 head CI #43479385893 与文档 head CI #43479614973 均完整成功，Unit Tests、E01/E02 全部步骤通过；M13 角色—机制—条件联合迁移审计原型、21 项专项测试与专题文档已提交，最新 head 完整 CI 成功；M14 文本见证谱系与主张证据审计原型、26 项专项测试与专题文档已提交，最新 PR head 完整 CI 成功；M15 文本片段—类象主张语义范围审计原型、24 项专项测试与专题文档已提交；新增未决证据门禁，阻止未审查证据与完整支持并存时误报完整覆盖；补强 head CI 待验证（此前 head #9a743ea 的完整 CI run #43488706432 成功）；M16 七事解释竞争登记原型、种子解释登记数据/Schema、15 项专项测试与专题文档已提交；最新 head 1e77fe7 完整 CI #43502670578 成功；M17–M21 已扩展迁移审计、人工审定、对抗基准与成对指标；M22 动态情境修订原型和专项测试已新增，等待 exact-head CI；真实任务效益、M8 人工 gold 与分轴基准接入仍待开展；传统类象语料 43 条候选记录、52 条文本主张
- 理论版本：CPG-EI v0.3（研究草案，持续修订）
- 代码状态：已有多尺度时间、typed relations、整体—局部候选约束、竞争类象证据剖面、未决裁决及 M4 条件干预原型；尚无规模化模型或性能结论
- 验证原则：所有架构主张均须通过可复现实验、消融和公平对照验证

## 核心研究问题

1. **动态组合**：系统能否自主发现、创建、合并、拆分和淘汰语义组合？
2. **非 Token 中心的内部表示**：能否以概念、事件、属性和关系作为内部计算单元，同时保留 Token 输入/输出接口？
3. **高阶关系与跨距离组合**：能否表达不连续元素之间的组合，例如从 a,b,c,d,e 中选出 a,b,c,e？
4. **易象状态表征**：阴阳、四象、八卦、六十四卦、卦变及五行关系能否成为可学习、可证伪的状态与关系先验？
5. **自组织与证据约束**：结构能否根据任务反馈更新，同时避免无证据的类比和自我强化？
6. **并行推演**：多条候选组合路径能否并行评估，并由全局协调器进行证据整合？

## 架构边界

- 不宣称完全不使用 Token：Tokenizer/Decoder 可作为外部语言接口；研究重点是内部计算不再以 Token 序列作为唯一基本单元。
- 不把并行预测多个 Token 当作核心创新；离散扩散、非自回归生成和并行解码已有大量研究。
- 不预设易学映射天然正确；所有映射必须可学习、可调整、可拒绝，并接受消融验证。
- 类比不等于因果；每条关键推断应记录来源、置信度、反例与验证状态。
- 不预设 CPG-EI 优于 Transformer；必须在相同数据、参数量和计算预算下比较。
- 组合搜索采用稀疏候选与预算约束，避免组合爆炸。

## 文档导航

- [研究总纲与问题定义](docs/RESEARCH_CHARTER.md)
- [数学理论 v0.3](docs/THEORY_v0.3.md)
- [架构设计](docs/ARCHITECTURE.md)
- [易象模块：可检验化设计](docs/YIXIANG_MODULE.md)
- [类象认知下一阶段研究计划 v0.1](docs/YIXIANG_NEXT_RESEARCH_PROGRAM_V0_1.md)
- [传统类象研究文献地图与校勘计划 v0.1](docs/CLASSICAL_YIXIANG_SOURCE_MAP_V0_1.md)
- [先秦两汉类象理论校勘札记 v0.1](docs/CLASSICAL_YIXIANG_THEORY_NOTES_PREQIN_HAN_V0_1.md)
- [先秦两汉类象拒推机制专题 v0.1](docs/CLASSICAL_YIXIANG_REJECTION_MECHANISMS_PREQIN_HAN_V0_1.md)
- [传统类象理论综合框架 v0.2](docs/CLASSICAL_YIXIANG_THEORY_SYNTHESIS_V0_2.md)
- [类象关系类型学与迁移门禁 v0.1](docs/CLASSICAL_YIXIANG_RELATION_TAXONOMY_V0_1.md)
- [类象关系不变量与角色结构迁移 v0.1](docs/CLASSICAL_YIXIANG_RELATION_INVARIANTS_V0_1.md)
- [《淮南子·说林训》功能关系、维度譬喻与多路径结果研究](docs/CLASSICAL_YIXIANG_HUAINAN_SHUOLIN_RELATION_ANALYSIS_V0_1.md)
- [类象候选生成：观察、取征、关系发现与证据门禁](docs/CLASSICAL_YIXIANG_CANDIDATE_GENERATION_V0_1.md)
- [类象候选生成原型](prototype/yixiang_candidate_generation.py)
- [类象候选生成测试](tests/test_yixiang_candidate_generation.py)
- [类象推论操作审计：辟、侔、援、推、效](docs/CLASSICAL_YIXIANG_INFERENCE_MOVES_V0_1.md)
- [类象推论操作审计原型](prototype/yixiang_inference_audit.py)
- [类象推论操作审计测试](tests/test_yixiang_inference_audit.py)
- [M9 多视角类象生成、竞争与组合专题](docs/YIXIANG_M9_MULTIVIEW_COMPOSITION_V0_1.md)
- [M9 多视角类象组合原型](prototype/yixiang_multiview_composition.py)
- [M9 多视角类象组合测试](tests/test_yixiang_multiview_composition.py)
- [类象组合涌现主张审计专题](docs/YIXIANG_EMERGENCE_AUDIT_V0_1.md)
- [类象组合涌现审计原型](prototype/yixiang_emergence_audit.py)
- [类象组合涌现审计测试](tests/test_yixiang_emergence_audit.py)
- [M10 类象组合涌现实验审计专题](docs/YIXIANG_M10_EMERGENCE_EXPERIMENT_V0_1.md)
- [M10 预注册涌现实验审计原型](prototype/yixiang_emergence_experiment.py)
- [M10 预注册涌现实验审计测试](tests/test_yixiang_emergence_experiment.py)
- [M11 动态类象网络审计专题](docs/YIXIANG_M11_DYNAMIC_NETWORK_V0_1.md)
- [M11 动态类象网络审计原型](prototype/yixiang_dynamic_network.py)
- [M11 动态类象网络审计测试](tests/test_yixiang_dynamic_network.py)
- [M12 条件约束多路径竞争专题](docs/YIXIANG_M12_PATH_COMPETITION_V0_1.md)
- [M12 多路径竞争审计原型](prototype/yixiang_path_competition.py)
- [M12 多路径竞争专项测试](tests/test_yixiang_path_competition.py)
- [M13 角色—机制—条件联合迁移审计专题](docs/YIXIANG_M13_ROLE_CONDITIONED_TRANSFER_V0_1.md)
- [M13 联合迁移审计原型](prototype/yixiang_role_conditioned_transfer.py)
- [M13 联合迁移专项测试](tests/test_yixiang_role_conditioned_transfer.py)
- [类象候选生成对照证据机制](docs/CLASSICAL_YIXIANG_CANDIDATE_GENERATION_V0_1.md#3-候选生成流程)
- [关系不变量迁移原型](prototype/yixiang_relation_invariants.py)
- [关系不变量迁移测试](tests/test_yixiang_relation_invariants.py)
- [有证据约束的条件变换迁移专题](docs/CLASSICAL_YIXIANG_RELATION_INVARIANTS_V0_1.md)
- [古籍证据来源谱系与独立见证审计 v0.1](docs/CLASSICAL_YIXIANG_EVIDENCE_LINEAGE_AUDIT_V0_1.md)
- [古籍证据来源谱系审计原型](prototype/yixiang_evidence_independence.py)
- [古籍证据来源谱系审计测试](tests/test_yixiang_evidence_independence.py)
- [古典类象词义、名物与推类分层研究 v0.1](docs/CLASSICAL_YIXIANG_LEXICAL_NOMENCLATURE_INFERENCE_V0_1.md)
- [古典类象四层解释防混淆门禁 v0.1](docs/CLASSICAL_YIXIANG_INTERPRETATION_FIREWALL_V0_1.md)
- [四层解释防混淆门禁原型](prototype/yixiang_interpretation_firewall.py)
- [四层解释防混淆门禁测试](tests/test_yixiang_interpretation_firewall.py)
- [古籍候选来源目录（148 项，均为待核验候选）](data/classical_yixiang_source_catalog.json)
- [古典类象案例集 v0.1（26 条原典案例，数字转录候选）](data/classical_yixiang_casebook.v0.1.json)
- [古典类象案例集研究说明与校勘门槛](docs/CLASSICAL_YIXIANG_CASEBOOK_V0_1.md)
- [古典类象案例集 Schema](schemas/classical-yixiang-casebook.schema.json)
- [古典类象案例集测试](tests/test_classical_yixiang_casebook.py)
- [类象迁移有效性：关系保持、条件约束与拒绝推演](docs/CLASSICAL_YIXIANG_ANALOGY_TRANSFER_VALIDITY_V0_1.md)
- [类象迁移有效性门控原型](prototype/yixiang_analogy_validity.py)
- [动态情境类象迁移门禁实现说明](docs/YIXIANG_CONTEXTUAL_TRANSFER_GATE_V0_1.md)
- [动态情境类象迁移门禁原型](prototype/yixiang_contextual_transfer.py)
- [动态情境类象迁移门禁测试](tests/test_yixiang_contextual_transfer.py)
- [类象迁移有效性测试](tests/test_yixiang_analogy_validity.py)
- [《周易》变—通—时—位动态类象专题](docs/CLASSICAL_YIXIANG_CHANGE_TIME_POSITION_V0_1.md)
- [先秦至两汉类比适切性与推类边界研究](docs/CLASSICAL_YIXIANG_ANALOGY_VALIDITY_HAN_PREQIN_HAN_V0_1.md)
- [《论衡·感类篇》与感应因果辨析专题](docs/CLASSICAL_YIXIANG_CORRESPONDENCE_CRITIQUE_LUNHENG_GANLEI_V0_1.md)
- [《墨子·小取》类推结构与异文专题](docs/CLASSICAL_YIXIANG_MOZI_XIAOQU_ANALYSIS_V0_1.md)
- [《墨子·小取》类象论辩操作矩阵 v0.2（辟/侔/援/推及七术分层）](docs/CLASSICAL_YIXIANG_MOZI_XIAOQU_OPERATION_MATRIX_V0_2.md)
- [《墨子·小取》辩学七事与推类边界 v0.2](docs/CLASSICAL_YIXIANG_MOZI_INFERENCE_MOVES_V0_1.md)
- [《小取》论辩操作门禁原型](prototype/yixiang_mozi_inference.py)
- [《小取》论辩操作门禁测试](tests/test_yixiang_mozi_inference.py)
- [《墨子·非攻上》递进类推与规范一致性专题 v0.1](docs/CLASSICAL_YIXIANG_MOZI_FEIGONG_ANALYSIS_V0_1.md)
- [《非攻上》双论证链结构化图谱](data/mozi_feigong_argument_graph.v0.1.json)
- [《非攻上》论证图 Schema](schemas/mozi-feigong-argument-graph.schema.json)
- [《非攻上》论证图测试](tests/test_mozi_feigong_argument_graph.py)
- [《墨子·大取》与《墨经》同异—类—故专题](docs/CLASSICAL_YIXIANG_MOZI_DAQU_MOJING_ANALYSIS_V0_1.md)
- [《大取》《墨经》同异—类—故的多层判断结构 v0.1](docs/CLASSICAL_YIXIANG_MOZI_SAMENESS_BASIS_AND_GU_V0_1.md)
- [《庄子·齐物论》视域转换、彼是互因与类象稳定性研究](docs/CLASSICAL_YIXIANG_ZHUANGZI_QIWULUN_VIEWPOINT_TRANSFER_V0_1.md)
- [先秦至两汉类象的动态条件、视域与适用域研究 v0.2](docs/CLASSICAL_YIXIANG_DYNAMIC_CONTEXT_STANDPOINT_V0_2.md)
- [《吕氏春秋·别类》《淮南子·说山训》：非单调组合与尺度迁移边界](docs/CLASSICAL_YIXIANG_NONMONOTONIC_COMPOSITION_AND_SCALE_V0_1.md)
- [《吕氏春秋》“类”观念与说理情境解释分歧](docs/CLASSICAL_YIXIANG_LUSHI_CATEGORY_AND_ARGUMENT_CONTEXT_V0_1.md)
- [古典“类”六种论证用途与行动结果账本 v0.1](docs/CLASSICAL_YIXIANG_FOUR_LEI_CLAIM_TYPES_AND_OUTCOME_LEDGER_V0_1.md)
- [古典“类”论证用途账本原型](prototype/yixiang_lei_claims.py)
- [古典“类”论证用途账本测试](tests/test_yixiang_lei_claims.py)
- [《荀子·正名》天官—征知—同异—名实—化认知链研究](docs/CLASSICAL_YIXIANG_XUNZI_ZHENGMING_COGNITIVE_CHAIN_V0_1.md)
- [《荀子·正名》感官根据与对象连续性门禁](docs/CLASSICAL_YIXIANG_XUNZI_OBSERVATION_GROUNDING_V0_1.md)
- [观察证据与对象连续性原型](prototype/yixiang_observation_grounding.py)
- [观察证据与对象连续性测试](tests/test_yixiang_observation_grounding.py)
- [《墨经》名类层级与《荀子·正名》推类层级门禁](docs/CLASSICAL_YIXIANG_TAXONOMIC_SCOPE_MOZI_XUNZI_V0_1.md)
- [类属层级与谓词迁移门禁原型](prototype/yixiang_taxonomic_scope.py)
- [类属层级与谓词迁移门禁测试](tests/test_yixiang_taxonomic_scope.py)
- [《正名》认知链结构化图谱](data/xunzi_zhengming_cognitive_chain.v0.1.json)
- [《正名》认知链 JSON Schema](schemas/xunzi-zhengming-cognitive-chain.schema.json)
- [《正名》认知链测试](tests/test_xunzi_zhengming_cognitive_chain.py)
- [M5 主动观测与信息增益基线](docs/YIXIANG_ACTIVE_OBSERVATION_M5_V0_1.md)
- [M6 新象发现与版本治理](docs/YIXIANG_NOVELTY_DISCOVERY_M6_V0_1.md)
- [M7 统一类象认知闭环](docs/YIXIANG_UNIFIED_COGNITIVE_LOOP_M7_V0_1.md)
- [M8 类象有效性与迁移评估基准](docs/YIXIANG_VALIDITY_TRANSFER_BENCHMARK_M8_V0_1.md)
- [M8 benchmark schema](schemas/yixiang-benchmark-case.schema.json)
- [M8 benchmark validator and metrics](prototype/yixiang_benchmark.py)
- [M8 benchmark report CLI](prototype/yixiang_benchmark_report.py)
- [M8 synthetic fixtures（47 条、六种 claim kind 分层的合成对抗样例，非古籍 gold）](data/yixiang_benchmark_synthetic.v0.1.json)
- [M8 benchmark tests](tests/test_yixiang_benchmark.py)
- [M14 文本见证谱系与类象主张证据审计](docs/YIXIANG_M14_EVIDENCE_PROVENANCE_V0_1.md)
- [M14 来源谱系与证据审计原型](prototype/yixiang_evidence_provenance.py)
- [M14 专项测试](tests/test_yixiang_evidence_provenance.py)
- [M15 文本片段—类象主张语义范围审计](docs/YIXIANG_M15_PASSAGE_CLAIM_SCOPE_AUDIT_V0_1.md)
- [M15 片段—主张语义范围审计原型](prototype/yixiang_passage_claim_audit.py)
- [M15 专项测试](tests/test_yixiang_passage_claim_audit.py)
- [M16 《墨子·小取》七事解释竞争专题](docs/YIXIANG_M16_INTERPRETATION_COMPETITION_V0_1.md)
- [M16 解释竞争登记原型](prototype/yixiang_interpretation_competition.py)
- [M16 专项测试](tests/test_yixiang_interpretation_competition.py)
- [M16 解释竞争种子数据](data/yixiang_interpretation_competition_m16.v0.1.json)
- [M16 解释竞争 Schema](schemas/yixiang-interpretation-competition.schema.json)
- [M17 类推迁移门禁专题](docs/YIXIANG_M17_ANALOGY_TRANSFER_AUDIT_V0_1.md)
- [M17 类推迁移审计原型](prototype/yixiang_analogy_transfer_audit.py)
- [M17 专项测试](tests/test_yixiang_analogy_transfer_audit.py)
- [M17 原典案例集](data/yixiang_analogy_transfer_m17.v0.1.json)
- [M17《淮南子·说林训》反例案例集](data/yixiang_analogy_transfer_huainanzi_m17.v0.1.json)
- [M17《荀子·正名》《荀子·非相》案例集](data/yixiang_analogy_transfer_xunzi_m17.v0.1.json)
- [M18 古典案例集到 M8 基准适配专题](docs/YIXIANG_M18_CASEBOOK_BENCHMARK_ADAPTER_V0_1.md)
- [M18 基准适配器](prototype/yixiang_casebook_benchmark_adapter.py)
- [M18 专项测试](tests/test_yixiang_casebook_benchmark_adapter.py)
- [M19 人工标注与最终裁决专题](docs/YIXIANG_M19_ANNOTATION_ADJUDICATION_V0_1.md)
- [M19 审定工作流原型](prototype/yixiang_annotation_adjudication.py)
- [M19 专项测试](tests/test_yixiang_annotation_adjudication.py)
- [M19 审定包 Schema](schemas/yixiang-annotation-review-packet.schema.json)
- [M20 类推迁移对抗式成对基准](docs/YIXIANG_M20_ADVERSARIAL_ANALOGY_BENCHMARK_V0_1.md)
- [M20 16 条合成对抗案例](data/yixiang_analogy_transfer_adversarial_m20.v0.1.json)
- [M20 专项测试](tests/test_yixiang_analogy_transfer_adversarial_m20.py)
- [M21 成对类推迁移评估指标](docs/YIXIANG_M21_CONTRASTIVE_PAIR_METRICS_V0_1.md)
- [M21 成对评估器](prototype/yixiang_contrastive_pair_metrics.py)
- [M21 专项测试](tests/test_yixiang_contrastive_pair_metrics.py)
- [M22 动态情境修订与主张失效传播专题](docs/YIXIANG_M22_CONTEXT_REVISION_V0_1.md)
- [M22 情境修订审计原型](prototype/yixiang_context_revision_m22.py)
- [M22 专项测试](tests/test_yixiang_context_revision_m22.py)
- [M23 观象—取象—立类形成机制专题](docs/YIXIANG_M23_FORMATION_V0_1.md)
- [M23 形成链审计原型](prototype/yixiang_formation.py)
- [M23 专项测试](tests/test_yixiang_formation.py)
- [M17 案例集 Schema](schemas/yixiang-analogy-transfer-casebook.schema.json)
- [古籍数字来源、版本见证与校勘工作规程 v0.1](docs/CLASSICAL_TEXT_DIGITAL_SOURCE_POLICY_V0_1.md)
- [M2 整体—局部关系结构说明](docs/YIXIANG_HIERARCHICAL_STRUCTURE_M2_V0_1.md)
- [M2.1 双向整体—局部约束说明](docs/YIXIANG_BIDIRECTIONAL_CONSTRAINTS_M2_1_V0_1.md)
- [M3 竞争类象与证据裁决说明](docs/YIXIANG_COMPETING_HYPOTHESES_M3_V0_1.md)
- [M4 反事实与条件干预说明](docs/YIXIANG_COUNTERFACTUAL_M4_V0_1.md)
- [M2 结构原型](prototype/yixiang_hierarchical_structure.py)
- [M2.1 双向约束原型](prototype/yixiang_bidirectional_constraints.py)
- [M3 竞争类象原型](prototype/yixiang_competing_hypotheses.py)
- [M4 反事实条件干预原型](prototype/yixiang_counterfactual.py)
- [M5 主动观测原型](prototype/yixiang_active_observation.py)
- [M6 新象发现原型](prototype/yixiang_novelty.py)
- [M7 统一闭环编排原型](prototype/yixiang_m7_pipeline.py)
- [M2 测试](tests/test_yixiang_hierarchical_structure.py)
- [M2.1 测试](tests/test_yixiang_bidirectional_constraints.py)
- [M3 测试](tests/test_yixiang_competing_hypotheses.py)
- [M4 测试](tests/test_yixiang_counterfactual.py)
- [M5 测试](tests/test_yixiang_active_observation.py)
- [M6 测试](tests/test_yixiang_novelty.py)
- [M7 测试](tests/test_yixiang_m7_pipeline.py)
- [M1 多尺度时间模型](prototype/yixiang_multiscale_time.py)
- [M1 合成时间基准](docs/YIXIANG_TEMPORAL_BENCHMARK_M1_V0_1.md)
- [传统古籍类象研究总纲](docs/CLASSICAL_YIXIANG_CORPUS_AND_RESEARCH_PROTOCOL.md)
- [结构化类象古籍语料](docs/CLASSICAL_XIANG_CORPUS_V0_1.md)
- [类象语料 Schema](schemas/classical-xiang-corpus.schema.json)
- [M23 观象—取象—立类形成机制](docs/YIXIANG_M23_FORMATION_V0_1.md)\n- [M24 多重归属、类别层级与动态边界](docs/YIXIANG_M24_BOUNDARY_HIERARCHY_V0_1.md)\n- [M24 类别边界与层级审计原型](prototype/yixiang_boundary.py)\n- [M24 类别边界与层级测试](tests/test_yixiang_boundary.py)\n- [M25 类间关系、跨轴映射与推论权限](docs/YIXIANG_M25_INTERCATEGORY_RELATIONS_V0_1.md)\n- [M25 类间关系审计原型](prototype/yixiang_intercategory.py)\n- [M25 类间关系测试](tests/test_yixiang_intercategory.py)
- [M26 类象组合语义与涌现审计专题](docs/YIXIANG_M26_COMPOSITION_EMERGENCE_V0_1.md)
- [M26 组合结构审计原型](prototype/yixiang_composition_m26.py)
- [M26 专项测试](tests/test_yixiang_composition_m26.py)
- [M27 统一类象声明图与跨模块失效传播专题](docs/YIXIANG_M27_UNIFIED_CLAIM_GRAPH_V0_1.md)
- [M27 统一声明图与失效传播原型](prototype/yixiang_unified_claim_graph_m27.py)
- [M27 专项测试](tests/test_yixiang_unified_claim_graph_m27.py)\n- [类象抽象与反例修正原型](prototype/yixiang_process.py)
- [类象多元关系原型](prototype/yixiang_relations.py)
- [类象关系类型与迁移门禁原型](prototype/yixiang_relation_taxonomy.py)
- [类象关系类型与迁移门禁测试](tests/test_yixiang_relation_taxonomy.py)
- [古典词义与名物分析原型](prototype/classical_lexical_analysis.py)
- [古典词义与名物分析测试](tests/test_classical_lexical_analysis.py)
- [古典词义—名物语料 Schema](schemas/classical-lexical-occurrence.schema.json)
- [动态类象状态转移原型](prototype/yixiang_dynamics.py)
- [时空情境联合比较原型](prototype/yixiang_situated.py)
- [时序轨迹对齐原型](prototype/yixiang_trajectory.py)
- [相关工作与文献](docs/RELATED_WORK.md)
- [实验计划与验收标准](docs/EXPERIMENTS.md)
- [研究风险与证伪条件](docs/RISKS_AND_FALSIFICATION.md)
- [开发路线图](ROADMAP.md)
- [原型代码](prototype/)

## 快速开始

```bash
python -m unittest discover -s tests -v
python -m prototype.e01_sparse_composition
python -m prototype.e01_learned_ranker --json
```

## 研究状态标记

| 标记 | 含义 |
|---|---|
| [事实] | 可由公开文献或可复现实验支持 |
| [假设] | 尚待实验验证的研究假设 |
| [设计] | 当前工程方案，不代表有效性已证实 |
| [结果] | 已执行并记录数据、配置和代码版本的实验结果 |

## 许可与引用

本仓库初始阶段采用 MIT License。引入外部数据集、论文代码或古籍数字化文本前，须逐项核查许可证、来源和引用要求。研究引用见 [RELATED_WORK.md](docs/RELATED_WORK.md)。

- [M28 类象证据独立性与共同来源污染审计](docs/YIXIANG_M28_EVIDENCE_INDEPENDENCE_V0_1.md)
- [M28 证据独立性审计原型](prototype/yixiang_evidence_independence_m28.py)
- [M28 专项测试](tests/test_yixiang_evidence_independence_m28.py)

- [M29 类象认知不确定性与依赖传播](docs/YIXIANG_M29_EPISTEMIC_UNCERTAINTY_V0_1.md)
- [M29 认知状态与不确定性传播原型](prototype/yixiang_epistemic_uncertainty_m29.py)
- [M29 专项测试](tests/test_yixiang_epistemic_uncertainty_m29.py)

- [M30 跨情境迁移与类象认知稳定性专题](docs/YIXIANG_M30_CONTEXT_TRANSFER_STABILITY_V0_1.md)
- [M30 跨情境迁移审计原型](prototype/yixiang_context_transfer_m30.py)
- [M30 专项测试](tests/test_yixiang_context_transfer_m30.py)

- [M31 类象不变量发现、反证与适用边界专题](docs/YIXIANG_M31_INVARIANT_DISCOVERY_V0_1.md)
- [M31 不变量发现与反证审计原型](prototype/yixiang_invariant_discovery_m31.py)
- [M31 专项测试](tests/test_yixiang_invariant_discovery_m31.py)

- [M32 类象不变量组合与层级涌现专题](docs/YIXIANG_M32_INVARIANT_COMPOSITION_V0_1.md)
- [M32 不变量组合审计原型](prototype/yixiang_invariant_composition_m32.py)
- [M32 专项测试](tests/test_yixiang_invariant_composition_m32.py)

- [M33 类象组合因果干预与反事实分解专题](docs/YIXIANG_M33_CAUSAL_INTERVENTION_V0_1.md)
- [M33 因果干预审计原型](prototype/yixiang_causal_intervention_m33.py)
- [M33 专项测试](tests/test_yixiang_causal_intervention_m33.py)


### M34 当前实现边界

M34 v0.1 新增因果机制分解声明审计：区分总效应、直接/间接效应、析因交互和 CATE；显式记录中介识别假设、处理后混杂与 cross-world 假设；记录跨情境测量不变性和机制路径；禁止将 SHAP/attention 等预测归因直接声明为因果贡献。26 项专项测试已编写，尚未执行；本原型不估计真实效应、不认证因果真值，M31/M32/M33 尚未端到端自动适配。


### M35 当前实现边界

M35 v0.1 新增跨情境因果运输声明审计：显式记录源域/目标域、机制、域差异、不变性主张、选择图与识别论证；区分总体分布、机制函数、测量、处理版本、选择过程和结果定义变化。26 项专项测试已编写，尚未执行。本原型不运行 do-calculus、不生成运输公式、不估计目标域效应、不认证因果真值。


### M36 当前实现边界

M36 v0.1 新增类象因果机制发现声明审计：区分观察、干预与反事实证据，登记竞争机制、混杂/潜变量、发现—验证数据隔离及反例检验。观察性证据单独仅输出关联性；反事实模拟不等同实测干预；结构完整也不认证因果真值。31 项专项测试已编写，尚未执行；无自动 DAG/SCM 学习、效应估计、潜变量发现或主动实验执行器。


### M37 当前实现边界

M37 v0.1 新增竞争机制驱动的候选实验排序基线：以最差竞争对的标准化预测分离度排序，并施加成本、风险、可行性、安全审查和选择/验证集隔离约束。该分数不是 EIG、因果识别或效应估计；不自动生成/执行实验，不认证机制真值。专项测试已编写，尚未执行。


### M38 当前实现边界

M38 v0.1 新增有限深度序贯实验策略树审计：显式登记竞争机制先验、按动作区分的结果似然、策略分支、停止叶节点、成本/风险预算与数据划分；在多个校准模型情景下分别计算策略 EIG，并报告情景集合内最差 EIG。原型只评估调用方提供的策略树，不自动搜索策略、不估计/校准概率、不执行实验、不认证因果真值。专项测试已编写，尚未执行；exact-head CI 待查询。


### M39 当前实现边界

M39 v0.1 新增有界 beam search，在显式候选实验动作中搜索固定长度内的 open-loop 序列，以已登记模型情景的最差 EIG 减去成本/风险惩罚进行排序，并报告逐步增量贪心对照；增加结果路径枚举上限以限制组合爆炸。它尚不搜索根据中间结果分支的自适应策略树，也不保证全局最优；不估计/校准概率、不执行实验、不认证因果真值。专项测试已编写，尚未执行；exact-head CI 待核查。


### M40 当前实现边界

M40 v0.1 将 M39 固定实验序列扩展为结果条件式有限策略树：策略按可观察结果分支，并在登记模型情景间以最差期望终端效用选择动作。终端奖励只是最大机制后验概率代理，不是因果真值；节点预算耗尽时搜索可能不完整。测试已编写，尚未执行。


### M41 当前实现边界

M41 v0.1 新增基于声明效用的 STOP / CONTINUE / REVIEW 审计，显式计入当前决策损失、未来实验奖励、成本、风险、不确定性惩罚、验证集锁定和最大实验轮数。它不估计效用、不校准置信度、不生成 anytime-valid 推断，也不证明因果真值。测试已编写，尚未执行。


### M42 当前实现边界

M42 v0.1 对先验、似然、测量偏移及潜在混杂处理状态执行登记压力情景审计，报告最差/最好策略价值，并在混杂未解决或偏移超界时要求复核。它不发现潜在混杂、不估计敏感性参数、不证明情景覆盖真实世界。测试已编写，尚未执行。


### M43 当前实现边界

M43 v0.1 审计自适应实验策略从源情境迁移到目标情境时的总体、测量、动作版本、结果定义、机制、选择差异、目标域重叠和验证证据。目标域价值由调用方提供；本模块不估计目标域效果、不运行 do-calculus、不自动部署策略。测试已编写，尚未执行。


### M44 当前实现边界

M44 v0.1 将 M37–M43 阶段引用、策略搜索、停止审计、模型稳健性和跨情境迁移状态统一为 BLOCKED / REVIEW_REQUIRED / READY_FOR_HUMAN_REVIEW / STOPPED_FOR_HUMAN_REVIEW 门禁。当前只做引用级编排，不是对象级端到端集成；即使 READY 也不授权执行或证明因果真值。测试已编写，尚未执行。


### M45 当前实现边界

M45 v0.1 新增内存追加式证据事件账本，记录行动、观察、证据/信念更新、策略/停止决策和最终主张；使用规范化载荷与前序摘要链审计记录完整性。持久化、并发、身份签名和跨模块自动埋点未实现。测试已编写，尚未执行。


### M46 当前实现边界

M46 v0.1 新增有限总体线性 SCM 基准环境，固定随机种子并复用 unit-level 外生噪声，支持拓扑排序、DAG 校验、观察、do-干预及 evaluator oracle。当前不支持离散/非线性机制、隐藏选择、干扰效应或异质系数。测试已编写，尚未执行。


### M47 当前实现边界

M47 v0.1 统一直接父节点 Precision/Recall/F1、SHD、干预覆盖、预算利用、提前提交、轨迹有效率与工具错误指标；提供 seeded-random、相关性筛选和 evaluator-only oracle 对照。当前只评估单目标父集，不评价完整 DAG、效应估计或语言解释。测试已编写，尚未执行。


### M48 当前实现边界

M48 v0.1 新增按 episode 配对的消融比较、方向统一的指标差值和可复现 bootstrap 区间，并检查 episode 集合、指标字段和 seed 一致性。该结果仅适用于登记的 benchmark 配置，不自动证明一般性理论因果。测试已编写，尚未执行。


### M49 当前实现边界

M49 v0.1 新增运行清单摘要、代码/依赖/数据/协议/配置/种子/事件账本和工件引用登记，并检查对象家族与来源家族跨 train/validation/test 泄漏。它只审计清单与声明，不下载验证工件、不封装运行环境、不保证外部非确定性受控。测试已编写，尚未执行。
