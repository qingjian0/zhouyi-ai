# Zhouyi-AI / CPG-EI

**组合并行生成与易象启发式认知架构**  
*Combinatorial Parallel Generation & Epistemic Intelligence*

> 研究目标：探索一种不把自回归 Token 预测作为唯一内部计算范式的认知架构。通过动态语义组合、高阶关系建模、多路径并行推演、易象状态表征与证据约束的自组织学习，研究更灵活的组合泛化与推理机制。

## 项目状态

- 当前阶段：M1–M4 基础机制已建立研究原型；M5/M6/M7 透明规则原型与测试已提交；M7 完整 CI 曾通过，最新古籍语料扩充的完整工作流正在复核
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
- [传统类象理论综合框架 v0.2](docs/CLASSICAL_YIXIANG_THEORY_SYNTHESIS_V0_2.md)
- [《周易》变—通—时—位动态类象专题](docs/CLASSICAL_YIXIANG_CHANGE_TIME_POSITION_V0_1.md)
- [先秦至两汉类比适切性与推类边界研究](docs/CLASSICAL_YIXIANG_ANALOGY_VALIDITY_HAN_PREQIN_HAN_V0_1.md)
- [《墨子·小取》类推结构与异文专题](docs/CLASSICAL_YIXIANG_MOZI_XIAOQU_ANALYSIS_V0_1.md)
- [《墨子·大取》与《墨经》同异—类—故专题](docs/CLASSICAL_YIXIANG_MOZI_DAQU_MOJING_ANALYSIS_V0_1.md)
- [M5 主动观测与信息增益基线](docs/YIXIANG_ACTIVE_OBSERVATION_M5_V0_1.md)
- [M6 新象发现与版本治理](docs/YIXIANG_NOVELTY_DISCOVERY_M6_V0_1.md)
- [M7 统一类象认知闭环](docs/YIXIANG_UNIFIED_COGNITIVE_LOOP_M7_V0_1.md)
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
- [传统古籍候选来源目录（111 项）](data/classical_yixiang_source_catalog.json)
- [结构化类象古籍语料](docs/CLASSICAL_XIANG_CORPUS_V0_1.md)
- [类象语料 Schema](schemas/classical-xiang-corpus.schema.json)
- [类象抽象与反例修正原型](prototype/yixiang_process.py)
- [类象多元关系原型](prototype/yixiang_relations.py)
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
