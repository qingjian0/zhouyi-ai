# Zhouyi-AI / CPG-EI

**组合并行生成与易象启发式认知架构**  
*Combinatorial Parallel Generation & Epistemic Intelligence*

> 研究目标：探索一种不把自回归 Token 预测作为唯一内部计算范式的认知架构。通过动态语义组合、高阶关系建模、多路径并行推演、易象状态表征与证据约束的自组织学习，研究更灵活的组合泛化与推理机制。

## 项目状态

- 当前阶段：M1 数学理论定稿与 M2 最小原型准备
- 理论版本：CPG-EI v0.3（研究草案）
- 代码状态：E01 组合选择基线原型正在建立；尚无规模化模型或性能结论
- 验证原则：所有架构主张均须通过可复现实验、消融和公平对照验证

## 核心研究问题

1. **动态组合**：系统能否自主发现、创建、合并、拆分和淘汰语义组合？
2. **非 Token 中心的内部表示**：能否以概念、事件、属性和关系作为内部计算单元，同时保留 Token 输入/输出接口？
3. **高阶关系与跨距离组合**：能否表达不连续元素之间的组合，例如从 a,b,c,d,e 中选出 a,b,c,e？
4. **易象状态表征**：阴阳、四象、八卦、六十四卦、卦变及五行关系能否成为可学习、可证伪的状态与关系先验？
5. **自组织与证据约束**：结构能否根据任务反馈更新，同时避免无证据的类比和自我强化？
6. **并行推演**：多条候选组合路径能否并行评估，并由全局协调器进行证据整合？
7. **多状态表示自主选择**：系统能否在二值、三值、混合和自主学习表示之间按任务选择，必要时提出新的状态基数？

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
- [太玄经三值结构 TX-01：可检验化研究设计](docs/TAIXUAN_TERNARY_COGNITION_TX01.md)
- [TX-02 多状态表示竞争与自主选择基准](docs/TX02_MULTISTATE_REPRESENTATION_BENCHMARK.md)
- [相关工作与文献](docs/RELATED_WORK.md)
- [2026-11-10 研究增量报告](docs/RESEARCH_FINDINGS_2026-11-10.md)
- [实验计划与验收标准](docs/EXPERIMENTS.md)
- [E02 动态超图实验设计](docs/E02_DYNAMIC_HYPERGRAPH.md)
- [E12 基础认知单元自主生成研究](docs/E12_GROUNDED_PRIMITIVE_INDUCTION_2026-11-11.md)
- [E12-A0 可辨识性基线协议](docs/E12A0_IDENTIFIABILITY_BASELINE.md)
- [E12-A1 类型化谓词生成基线](docs/E12A1_TYPED_PREDICATE_INDUCTION.md)
- [E12-A1.1 证据溯源与候选谱系](docs/E12A1P_EVIDENCE_PROVENANCE.md)
- [E12-A2 主动观测选择研究协议与实现](docs/E12A2_ACTIVE_MEASUREMENT_SELECTION.md)
- [E12-A2-B 主动测量策略对照基准](docs/E12A2B_POLICY_BENCHMARK.md)
- [E12-A2-D 噪声观测与先验错配压力测试](docs/E12A2D_NOISY_PRIOR_STRESS.md)
- [YF-01 阴符经启发的动态观测实验](docs/YINFU_DYNAMIC_OBSERVATION.md)
- [YF-02～YF-06 竞争解释、三元交互与反转研究协议](docs/YF02_YF06_RESEARCH_PROTOCOL.md)
- [E12-A1 类型化谓词原型](prototype/e12a1_typed_predicate_induction.py)
- [E12-A1.1 证据溯源原型](prototype/e12a1p_evidence_provenance.py)
- [E12-A2 主动观测选择器](prototype/e12a2_active_measurement.py)
- [太玄经 81 首 / 9 赞 / 729 状态可逆编码原型](prototype/taixuan_ternary_encoding.py)
- [TX-02A 跨状态基数 episode 生成器](prototype/tx02_multistate_benchmark.py)
- [YF-01 动态观测策略原型](prototype/yinfu_active_observation.py)
- [YF-03 三元反馈与关系反转原型](prototype/yinfu_interaction_dynamics.py)
- [E12-A2-B 策略对照实验](prototype/e12a2b_policy_benchmark.py)
- [E12-A2-D 噪声先验压力实验](prototype/e12a2d_noisy_prior_stress.py)
- [E02-A 结果审计与下一阶段协议](docs/E02A_NEXT_RESEARCH_2026-11-10.md)
- [E02-B 三元有限域关系诊断协议](docs/E02B_TERNARY_PROTOCOL.md)
- [E02-B 学习器对照原型](prototype/e02_ternary_learners.py)
- [E02-C 超边生命周期原型](prototype/e02_edge_lifecycle.py)
- [E02-B 三元有限域学习器对照结果](docs/E02B_RESULTS_2026-11-10.md)
- [E02-D 未见规则族归纳基准](prototype/e02_rule_ood.py)
- [E02-D 实验协议](docs/E02D_RULE_FAMILY_OOD.md)
- [E02-D 支持样本量扫描结果](docs/E02D_SUPPORT_SWEEP_RESULTS_2026-11-10.md)
- [E01-B 五种子结果报告](docs/E01B_RESULTS_2026-11-10.md)
- [E01-C 组合 OOD 结果报告](docs/E01C_RESULTS_2026-11-10.md)
- [研究风险与证伪条件](docs/RISKS_AND_FALSIFICATION.md)
- [开发路线图](ROADMAP.md)
- [原型代码](prototype/)

## 快速开始（当前原型）

当前原型优先验证组合策略和跨位置组合，不代表完整模型：

```bash
python -m unittest discover -s tests -v
python -m prototype.e01_sparse_composition
python -m prototype.e01_learned_ranker --json
python -m prototype.e12a2_active_measurement --json
python -m prototype.e12a2b_policy_benchmark --seeds 20 --budget 4 --json
python -m prototype.e12a2d_noisy_prior_stress --episodes 100 --budget 3 --json
python -m prototype.yinfu_active_observation
python -m prototype.yinfu_interaction_dynamics --horizon 8
python -m prototype.taixuan_ternary_encoding
python -m prototype.tx02_multistate_benchmark --episodes-per-cardinality 20 --support-size 4 --query-count 2
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
