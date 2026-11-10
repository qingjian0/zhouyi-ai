# Zhouyi-AI / CPG-EI

**组合并行生成与易象启发式认知架构**  
*Combinatorial Parallel Generation & Epistemic Intelligence*

> 研究目标：探索一种不把自回归 Token 预测作为唯一内部计算范式的认知架构。通过动态语义组合、高阶关系建模、多路径并行推演、易象状态表征与证据约束的自组织学习，研究更灵活的组合泛化与推理机制。

## 项目状态

- 当前研究阶段：E02-I 七场景关系生命周期验证已完成；E02-I2 关系身份与谱系进入设计审查
- 理论版本：CPG-EI v0.3（研究草案，尚待进一步数学审查）
- 已有实验：E02-F/G 有限定合成任务结果；E02-H 在 30 个种子上完成成员与真值表恢复；E02-I 在 7 场景 × 20 seeds 下完成 140 个 episode
- 当前验证：E02-I 全流程 CI 成功，160 个无关系窗口 false CREATE 为 0；结果仅适用于当前有限合成协议
- 尚未实现：开放世界关系发现、因果发现、规模化模型及完整 E03 并行组合引擎
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
- [E02-I 关系演化协议](docs/E02I_RELATION_EVOLUTION.md)
- [E02-I 完整 CI 结果（2026-11-10）](docs/E02I_CI_RESULTS_2026-11-10.md)
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


## E02-I

Evidence-gated relation structure evolution prototype and reproducible experiment: `docs/E02I_RELATION_EVOLUTION.md`.


E02-I seven-scenario lifecycle validation completed successfully in GitHub Actions run 42821097953.


E02-I distinguishes candidate quality from persistent relation quality.
