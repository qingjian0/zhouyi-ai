# Zhouyi-AI / 类象认知引擎

**证据约束的类象认知与跨领域迁移**  
*Evidence-Grounded Classiang Cognition & Cross-Domain Transfer*

> 研究目标：构建领域无关的类象认知能力，使系统能够从观测中取象、形成和辨析类别、发现关系保持的跨域对应、执行有边界的推类迁移，并根据证据与反例持续修正。CPG-EI、SROK、动态超图和易象状态表征均作为可替换的计算后端或领域知识先验，服务于类象主线。

## 项目状态

- 稳定分支：main（本轮未修改）。
- 研发集成分支：dev（当前唯一研发集成目标）；新成果先在 dev 验收，再决定是否进入 main。
- 已进入 dev：类象关系保持 OOD 基准、易象 M22–M26 模块、卦爻编码状态转移与 M21 配对输入校验，以及 N0.10、M1/M2、CPG-EI 等计算与数据支撑资产。
- 类象认知核心已通过 PR #543 合并到 dev：任务条件取象、证据约束立类、无标签候选发现和已审阅观象轨迹适配；当前仍是符号 MVP，完整学习和真实跨域验收未完成。
- E12-A6/ZPCM：权威事件日志、candidate/evidence/action SQLite 当前状态投影（事务触发器）、digest 校验与原子重建、SQLite scratch 有界重放已进入 dev；启动仍为 O(N) 语义重放，持久化快速 checkpoint、故障压力和 exact-head RSS 验收未完成。
- 近期已合并：PR #543（类象认知核心）、#544–#550（循环模型基线、评测协议、持久记忆包与证据恢复）、#551（有界词法检索）；更早成果见 Git 历史。
- 已清理重复/过时 PR：#433、#438、#445–#449、#518。M22、M24–M26 文件与测试已在 dev；M23 的 dev 版本比旧 PR 分支更新。#433 的旧聚合分支没有带来 dev 缺失文件，保留的编码转移和配对校验改进已单独移植。
- CI 按变更路径执行必要验证；dev 集成提交仍须通过全量测试。研究评测只在对应研究路径变更时触发。
- 科学边界：合成基准、有限规则语法和声明审计原型不等同于真实古籍 Gold 证据、自然语言能力、因果发现或通用认知能力。

## 核心研究问题

1. **观象与取象**：能否从不同模态和领域的观测中，按任务选择有证据依据的特征、关系、过程与状态？
2. **立类与辨类**：能否从正例、负例和不确定例中形成类别假设，发现边界并识别开放集新类？
3. **比类与映射**：能否发现跨对象、跨关系和跨领域的结构对应，同时区分表面相似与关系保持？
4. **推类与迁移**：能否在明确条件、上下文和有效范围内迁移关系、过程或机制，并拒绝错误类比？
5. **验类与修类**：能否根据证据、反例和任务反馈执行拒绝、限缩、拆分、合并和撤销？
6. **计算支撑**：动态超图、CPG-EI/SROK、并行推演与易象先验能否在类象任务上带来可复现增益？

## 架构边界

- 不宣称完全不使用 Token：Tokenizer/Decoder 可作为外部语言接口；研究重点是内部计算不再以 Token 序列作为唯一基本单元。
- 不把并行预测多个 Token 当作核心创新；离散扩散、非自回归生成和并行解码已有大量研究。
- 类象是主体能力；易象/周易是可插拔领域知识源，不得垄断通用类象边界。
- 不预设任何传统映射天然正确；所有映射必须可学习、可调整、可拒绝，并接受消融验证。
- 类比不等于因果；每条关键推断应记录来源、置信度、反例与验证状态。
- 不预设 CPG-EI 优于 Transformer；必须在相同数据、参数量和计算预算下比较。
- 组合搜索采用稀疏候选与预算约束，避免组合爆炸。

## 文档导航

- [权限、授权与执行限制记录](docs/ACCESS_AND_EXECUTION_LIMITATIONS.md)

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
- [类象认知主线与工程验收纲领](docs/CLASSIANG_FIRST_PRIORITY_CHARTER.md)
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
