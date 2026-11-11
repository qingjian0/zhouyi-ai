# Zhouyi-AI / CPG-EI

**组合并行生成与易象启发式认知架构**  
*Combinatorial Parallel Generation & Epistemic Intelligence*

> 研究目标：探索一种不把自回归 Token 预测作为唯一内部计算范式的认知架构。通过动态语义组合、高阶关系建模、多路径并行推演、易象状态表征与证据约束的自组织学习，研究更灵活的组合泛化与推理机制。

## 项目状态

- 当前阶段：E12 原语发现与评估闭环研究；E12-A19 多规则联合判别原型；E12-A20 有限域精确参考求解与同步信念传播
- 理论版本：CPG-EI v0.3（研究草案）
- 代码状态：A19-C 完整 CI 已通过；A20-0 精确参考求解器 CI 已通过；A20-1 同步 Sum-Product 信念传播已提交，CI 验证中。当前实现是单进程同步更新，不代表多核并行或已证明性能优势
- 尚无规模化模型或性能优势结论
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
- [相关工作与文献](docs/RELATED_WORK.md)
- [实验计划与验收标准](docs/EXPERIMENTS.md)
- [E12 基础认知单元自主生成研究](docs/E12_GROUNDED_PRIMITIVE_INDUCTION_2026-11-11.md)
- [E12-A7 正交认知生命周期设计](docs/E12A7_ORTHOGONAL_EPISTEMIC_LIFECYCLE_2026-11-11.md)
- [E12-A7 原型实现与集成缺口审计](docs/E12A7_IMPLEMENTATION_AUDIT_2026-11-11.md)
- [E12-A7 正交生命周期原型](prototype/e12a7_orthogonal_lifecycle.py)
- [E12-A7 正交生命周期测试](tests/test_e12a7_orthogonal_lifecycle.py)
- [E12-A8 Evaluator Firewall 设计与实现审计](docs/E12A8_EVALUATOR_FIREWALL_2026-11-11.md)
- [E12-A8 Evaluator Firewall 原型](prototype/e12a8_evaluator_firewall.py)
- [E12-A8 Learner 子进程入口](prototype/e12a8_learner_worker.py)
- [E12-A8 非干扰与提交完整性测试](tests/test_e12a8_evaluator_firewall.py)
- [E12-A8 × E02-D 进程隔离实验 runner](prototype/e12a8_e02d_runner.py)
- [E12-A8 × E02-D 集成测试](tests/test_e12a8_e02d_runner.py)
- [E12-A9 Evaluator 证据桥接设计](docs/E12A9_EVIDENCE_BRIDGE_2026-11-11.md)
- [E12-A9 证据聚合与生命周期桥接](prototype/e12a9_evidence_bridge.py)
- [E12-A9 证据桥接测试](tests/test_e12a9_evidence_bridge.py)
- [E12-A10 Ed25519 签名评估回执](prototype/e12a10_signed_evaluator_receipts.py)
- [E12-A10 签名与重放保护测试](tests/test_e12a10_signed_evaluator_receipts.py)
- [E12-A10 安全协议文档](docs/E12A10_SIGNED_EVALUATOR_RECEIPTS_2026-11-11.md)
- [E12-A11 主动测量证据协议](docs/E12A11_ACTIVE_MEASUREMENT_EVIDENCE_2026-11-11.md)
- [E12-A11 主动测量执行器原型](prototype/e12a11_active_measurement_evidence.py)
- [E12-A11 签名测量证据测试](tests/test_e12a11_active_measurement_evidence.py)
- [E12-A12 噪声感知证据更新设计](docs/E12A12_NOISE_AWARE_EVIDENCE_UPDATE_2026-11-11.md)
- [E12-A12 序贯似然证据更新原型](prototype/e12a12_noise_aware_evidence_update.py)
- [E12-A12 噪声感知证据更新测试](tests/test_e12a12_noise_aware_evidence_update.py)
- [E12-A13 模型失配与环境漂移诊断设计](docs/E12A13_DRIFT_MISMATCH_DIAGNOSTICS_2026-11-11.md)
- [E12-A13 漂移与候选失配诊断原型](prototype/e12a13_drift_mismatch_diagnostics.py)
- [E12-A13 漂移诊断测试](tests/test_e12a13_drift_mismatch_diagnostics.py)
- [E12-A14 漂移检测算法校准协议](docs/E12A14_DRIFT_DETECTOR_CALIBRATION_2026-11-11.md)
- [E12-A14 漂移检测对照基准](prototype/e12a14_drift_detector_calibration.py)
- [E12-A14 基准测试](tests/test_e12a14_drift_detector_calibration.py)
- [E12-A15 多假设竞争与主动区分测量设计](docs/E12A15_COMPETING_HYPOTHESES_2026-11-11.md)
- [E12-A15 竞争假设与信息增益选择原型](prototype/e12a15_competing_hypotheses.py)
- [E12-A15 证据闭环测试](tests/test_e12a15_competing_hypotheses.py)
- [E12-A16 开放集原语自主发现设计](docs/E12A16_OPEN_SET_PRIMITIVE_DISCOVERY_2026-11-11.md)
- [E12-A16 稀疏原语发现器](prototype/e12a16_open_set_primitive_discovery.py)
- [E12-A16 复杂度与泛化测试](tests/test_e12a16_open_set_primitive_discovery.py)
- [E12-A17 类型化关系图发现设计](docs/E12A17_TYPED_RELATION_GRAPH_DISCOVERY_2026-11-11.md)
- [E12-A17 类型化关系图发现器](prototype/e12a17_typed_relation_graph_discovery.py)
- [E12-A17 类型化关系图发现测试](tests/test_e12a17_typed_relation_graph_discovery.py)
- [E12-A18 分叉汇合状态转移设计](docs/E12A18_BRANCH_MERGE_STATE_TRANSITION_DISCOVERY_2026-11-11.md)
- [E12-A18 分叉汇合发现器](prototype/e12a18_branch_merge_transition_discovery.py)
- [E12-A18 分叉汇合专项测试](tests/test_e12a18_branch_merge_transition_discovery.py)
- [E12-A19 统一结构竞争协议](docs/E12A19_UNIFIED_STRUCTURE_COMPETITION_2026-11-11.md)
- [E12-A19 统一结构竞争原型](prototype/e12a19_unified_structure_competition.py)
- [E12-A19 统一结构竞争测试](tests/test_e12a19_unified_structure_competition.py)
- [E12-A19-C 多规则联合推理与随机对照设计](docs/E12A19C_MULTI_RULE_CONTROLS_2026-11-11.md)
- [E12-A19-C 多规则联合推理原型](prototype/e12a19c_multi_rule_controls.py)
- [E12-A19-C 专项测试](tests/test_e12a19c_multi_rule_controls.py)
- [E12-A20 并行假设图推理运行时设计](docs/E12A20_PARALLEL_HYPOTHESIS_RUNTIME_DESIGN_2026-11-11.md)
- [E12-A20-0 有限域因子图参考推理器](prototype/e12a20_factor_graph.py)
- [E12-A20-1 同步 Sum-Product 信念传播](prototype/e12a20a1_belief_propagation.py)
- [E12-A20-1 专项测试](tests/test_e12a20a1_belief_propagation.py)
- [E12-A20-0 参考推理器测试](tests/test_e12a20_factor_graph.py)
- [E12-A20-0 实现说明与限制](docs/E12A20_0_FACTOR_GRAPH_REFERENCE_2026-11-11.md)
- [E12-A0 可辨识性基线协议](docs/E12A0_IDENTIFIABILITY_BASELINE.md)
- [E12-A1 类型化谓词生成基线](docs/E12A1_TYPED_PREDICATE_INDUCTION.md)
- [E12-A2 主动观测选择研究协议](docs/E12A2_ACTIVE_MEASUREMENT_SELECTION.md)
- [E12-A2 实现审查与验证门槛](docs/E12A2_IMPLEMENTATION_AUDIT_2026-11-11.md)
- [E12-A2-M 选择器实现记录](docs/E12A2_M_IMPLEMENTATION_2026-11-11.md)
- [E12-A3 稀疏组合原语自主归纳协议](docs/E12A3_COMPOSITIONAL_PRIMITIVE_INDUCTION.md)
- [E12-A3 初步 20 种子基准结果审计](docs/E12A3_PRELIMINARY_BENCHMARK_AUDIT_2026-11-11.md)
- [E12-A3 双实现比较与统一接口设计](docs/E12A3_IMPLEMENTATION_COMPARISON_2026-11-11.md)
- [E12-A3-M0 组合引擎实现记录](docs/E12A3_M0_IMPLEMENTATION_2026-11-11.md)
- [E12-A3-M0 组合引擎原型](prototype/e12a3_compositional_induction.py)
- [E12-A3-M0 单元测试](tests/test_e12a3_compositional_induction.py)
- [E12 组合泛化与神经符号相关工作](docs/RELATED_WORK_E12_COMPOSITIONALITY_2026-11-11.md)
- [E12-A1 类型化谓词原型](prototype/e12a1_typed_predicate_induction.py)
- [E12-A2-M 主动观测选择器](prototype/e12a2_active_measurement_selector.py)
- [E12-A2-M 单元测试](tests/test_e12a2_active_measurement_selector.py)
- [E02 动态超图实验设计](docs/E02_DYNAMIC_HYPERGRAPH.md)
- [E02-A 结果审计与下一阶段协议](docs/E02A_NEXT_RESEARCH_2026-11-10.md)
- [E02-B 三元有限域关系诊断协议](docs/E02B_TERNARY_PROTOCOL.md)
- [E02-B 学习器对照原型](prototype/e02_ternary_learners.py)
- [E02-C 超边生命周期原型](prototype/e02_edge_lifecycle.py)
- [E02-B 三元有限域学习器对照结果](docs/E02B_RESULTS_2026-11-10.md)
- [E02-D 未见规则族归纳基准](prototype/e02_rule_ood.py)
- [E02-D 实验协议](docs/E02D_RULE_FAMILY_OOD.md)
- [研究风险与证伪条件](docs/RISKS_AND_FALSIFICATION.md)
- [开发路线图](ROADMAP.md)
- [原型代码](prototype/)

## 快速开始

```bash
python -m unittest discover -s tests -v
python -m prototype.e01_sparse_composition
python -m prototype.e01_learned_ranker --json
python -m prototype.e12a2_active_measurement_selector
python -m prototype.e12a3_compositional_induction
```

## 研究状态标记

| 标记 | 含义 |
|---|---|
| [事实] | 可由公开文献或可复现实验支持 |
| [假设] | 尚待实验验证的研究假设 |
| [设计] | 当前工程方案，不代表有效性已证实 |
| [结果] | 已执行并记录数据、配置和代码版本的实验结果 |

## 许可与引用

本仓库初始阶段采用 MIT License。若后续引入外部数据集、论文代码或古籍数字化文本，须逐项核查其许可证、来源和引用要求。研究引用见 [RELATED_WORK.md](docs/RELATED_WORK.md)。
