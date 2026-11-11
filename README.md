# Zhouyi-AI / CPG-EI

**组合并行生成与易象启发式认知架构**  
*Combinatorial Parallel Generation & Epistemic Intelligence*

> 研究目标：探索一种不把自回归 Token 预测作为唯一内部计算范式的认知架构。通过动态语义组合、高阶关系建模、多路径并行推演、易象状态表征与证据约束的自组织学习，研究更灵活的组合泛化与推理机制。

## 项目状态（2026-11-11）

- **主线状态：** main 仍是保守的 M1/M2 基线，不代表全部研究分支的最新进度。
- **研究进展：** E02–E13 已有大量独立研究分支和草稿 PR，覆盖原语发现、关系归纳、概念重构、证据学习、并行假设推理、易象/太玄/阴符表示研究。
- **集成状态：** 多数成果仍是 branch-local 原型或协议；不能把它们描述为已集成的统一运行系统。
- **模型状态：** 尚无规模化 CPG-EI 模型，也没有证明优于 Transformer 的结果。
- **当前集成工作：** [CPG-EI v1 收敛基础](docs/CPG_EI_V1_CONVERGENCE_FOUNDATION_2026-11-11.md)，定义跨研究线接口、状态所有权和验收门槛。

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

- [ZNCA 原生认知架构研究提案](docs/ZNCA_NATIVE_COGNITIVE_ARCHITECTURE_2026-11-11.md)
- [ZNCA N1 可执行关系状态核心](docs/ZNCA_N1_REFERENCE_CORE_2026-11-11.md)
- [ZNCA N2 可学习关系动力学](docs/ZNCA_N2_RELATIONAL_DYNAMICS_2026-11-11.md)
- [ZNCA 可证伪实验协议](docs/ZNCA_EXPERIMENT_PROTOCOL_2026-11-11.md)
- [CPG-EI v1 收敛基础与跨线集成门槛](docs/CPG_EI_V1_CONVERGENCE_FOUNDATION_2026-11-11.md)
- [研究总纲与问题定义](docs/RESEARCH_CHARTER.md)
- [数学理论 v0.3](docs/THEORY_v0.3.md)
- [架构设计](docs/ARCHITECTURE.md)
- [易象模块：可检验化设计](docs/YIXIANG_MODULE.md)
- [第三轮：易象多维类象、五行历史分层与关系映射原型](docs/YIXIANG_TYPED_ANALOGY_AND_FIVE_PHASES_RESEARCH_2026-11-11.md)
- [E13：结构发现—类象迁移—主动验证联合闭环](docs/E13_JOINT_STRUCTURE_ANALOGY_DISCOVERY_LOOP_2026-11-11.md)
- [相关工作与文献](docs/RELATED_WORK.md)
- [2026-11-10 研究增量报告](docs/RESEARCH_FINDINGS_2026-11-10.md)
- [实验计划与验收标准](docs/EXPERIMENTS.md)
- [E02 动态超图实验设计](docs/E02_DYNAMIC_HYPERGRAPH.md)
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

## 快速开始（当前 main 原型）

当前 main 原型优先验证组合策略和跨位置组合，不代表完整模型：

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

本仓库初始阶段采用 MIT License。若后续引入外部数据集、论文代码或古籍数字化文本，须逐项核查其许可证、来源和引用要求。研究引用见 [RELATED_WORK.md](docs/RELATED_WORK.md)。
