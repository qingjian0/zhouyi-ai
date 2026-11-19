# Zhouyi-AI / CPG-EI

**组合并行生成与易象启发式认知架构**  
*Combinatorial Parallel Generation & Epistemic Intelligence*

> 研究目标：探索一种不把自回归 Token 预测作为唯一内部计算范式的认知架构。通过动态语义组合、高阶关系建模、多路径并行推演、易象状态表征与证据约束的自组织学习，研究更灵活的组合泛化与推理机制。

## 项目状态

- 稳定分支：main（本轮未修改）。
- 研发集成分支：dev（当前唯一研发集成目标）；新成果先在 dev 验收，再决定是否进入 main。
- 已进入 dev：N0.10 SQLite 索引与 out-of-core 流式训练、M1 Manifest/有界读取、M2 延迟加载/分页、CPG-EI 扩展合成语料 v2、经验贝叶斯 few-shot 基线、优化器与 motif 诊断、类象关系保持 OOD 基准、易象 M22–M26 模块、卦爻编码状态转移与 M21 配对输入校验强化。
- E12-A6/ZPCM：权威事件日志、candidate/evidence/action SQLite 当前状态投影（事务触发器）、digest 校验与原子重建、SQLite scratch 有界重放已进入 dev；启动仍为 O(N) 语义重放，持久化快速 checkpoint、故障压力和 exact-head RSS 验收未完成。
- 本轮已合并：PR #517、#529、#530；此前已合并 #519、#520、#521、#523、#524、#526、#527、#528。
- CI 已收敛：dev 代码变更走一次全量 tests；文档变更不触发全量测试；Orchestrator 专项工作流仅在主分支/feature 分支且相关路径变化时运行；大型 CPG-EI 扩展语料工作流已限定到其自身代码和测试路径，并为全量工作流启用并发取消旧运行。
- 科学边界：合成基准、有限规则语法和声明审计原型不等同于真实古籍 Gold 证据、自然语言能力、因果发现或通用认知能力。
- **百万序列目标已列为正式研究规格**：1M tokenizer-token 输入与 1M 连续输出分别验收；非 Transformer 序列主干优先，配合稀疏情景记忆、层级索引和 CPG-EI 认知层。当前为协议与工程启动状态，不代表模型已达到该能力。

## 核心研究问题

1. **动态组合**：系统能否自主发现、创建、合并、拆分和淘汰语义组合？
2. **非 Token 中心的内部表示**：能否以概念、事件、属性和关系作为内部计算单元，同时保留 Token 输入/输出接口？
3. **高阶关系与跨距离组合**：能否表达不连续元素之间的组合，例如从 a,b,c,d,e 中选出 a,b,c,e？
4. **易象状态表征**：阴阳、四象、八卦、六十四卦、卦变及五行关系能否成为可学习、可证伪的状态与关系先验？
5. **自组织与证据约束**：结构能否根据任务反馈更新，同时避免无证据的类比和自我强化？
6. **并行推演**：多条候选组合路径能否并行评估，并由全局协调器进行证据整合？
7. **超长连续序列**：非 Transformer 主干如何在普通设备上保持百万 Token 输入的证据可追溯性，并稳定完成百万 Token 连续生成？

## 架构边界

- 不宣称完全不使用 Token：Tokenizer/Decoder 可作为外部语言接口；研究重点是内部计算不再以 Token 序列作为唯一基本单元。
- 不把并行预测多个 Token 当作核心创新；离散扩散、非自回归生成和并行解码已有大量研究。
- 不预设易学映射天然正确；所有映射必须可学习、可调整、可拒绝，并接受消融验证。
- 类比不等于因果；每条关键推断应记录来源、置信度、反例与验证状态。
- 不预设 CPG-EI 优于 Transformer；必须在相同数据、参数量和计算预算下比较。
- 组合搜索采用稀疏候选与预算约束，避免组合爆炸。
- 百万上下文不等于百万长度理解；百万输入和百万连续输出是独立验收项。不得以摘要替代原文、滑窗丢弃或外部模型代答冒充端到端能力。

## 文档导航

- [权限、授权与执行限制记录](docs/ACCESS_AND_EXECUTION_LIMITATIONS.md)
- [研究总纲与问题定义](docs/RESEARCH_CHARTER.md)
- [数学理论 v0.3](docs/THEORY_v0.3.md)
- [架构设计](docs/ARCHITECTURE.md)
- [百万输入 / 百万连续输出架构与训练协议](docs/ONE_MILLION_SEQUENCE_TRAINING.md)
- [P5-A 流式精确 Token 计量](docs/P5A_STREAMING_TOKEN_COUNT.md)
- [易象模块：可检验化设计](docs/YIXIANG_MODULE.md)
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
- [E02-I 关系演化协议（独立于 streaming drift 生命周期实验）](docs/E02I_RELATION_EVOLUTION.md)
- [E02-I 关系演化原型](prototype/e02i_relation_evolution.py)
- [原型代码](prototype/)

## 快速开始（当前原型）

当前原型优先验证组合策略和跨位置组合，不代表完整模型：

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

## E02-I 关系演化（Persistent Evidence）

本实验独立于主线已有的 E02-I streaming drift lifecycle，研究候选关系与持久关系分别接受 Gate 验证、两窗口确认重配置，以及连续失败退役。当前仅适用于预注册的有限布尔合成场景。
