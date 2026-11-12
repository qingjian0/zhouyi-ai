# Zhouyi-AI

**非 Transformer 原生认知计算研究项目**  
研究方向：结构化关系认知、非自回归组合、易象/类象算子、证据约束学习、持久认知记忆与资源受控执行。

## 当前架构决策（2026-11-11）

Zhouyi-AI 以**非序列中心认知计算**为顶层原则：内部认知以类型化结构和关系为中心，允许非连续、多段、跨距离组合及多候选并行协调。Transformer/LLM 可作为可插拔输入解析、语言表达、教师和对照基线，不是唯一认知核心。

统一分工：
- **CPG-EI**：研究总纲与实验范式；
- **ZNCA**：认知组织与状态框架；
- **TRLW**：类型化关系潜在工作空间；
- **SROK**：稀疏非连续关系组合内核；
- **CSG-GCR**：候选生成与全局约束协调；
- **RSDN**：关系状态动力学；
- **Yixiang / XSL**：可证伪的易象算子与跨域类象映射；
- **ZPCM / DCMF**：持久事件记忆与认知状态投影；
- **E09 / E12-A6**：证据治理与候选生命周期唯一权威；
- **CSL / MCRL / Hyper-Speed**：依赖失效、计算策略与执行调度。

## 架构与工程文档

- [全项目收敛执行基线 v1](docs/UNIFIED_CONVERGENCE_EXECUTION_V1_2026-11-11.md)
- [统一认知架构 v1](docs/MASTER_ARCHITECTURE_V1_2026-11-11.md)
- [模块契约 v1](docs/MODULE_CONTRACTS_V1_2026-11-11.md)
- [集成登记册 v1](docs/INTEGRATION_REGISTRY_V1_2026-11-11.md)
- [训练与评估路线 v1](docs/TRAINING_EVALUATION_V1_2026-11-11.md)
- [架构决策记录 v1](docs/ARCHITECTURE_DECISIONS_V1_2026-11-11.md)
- [开发路线图](ROADMAP.md)
- [研究总纲](docs/RESEARCH_CHARTER.md)
- [易象模块研究](docs/YIXIANG_MODULE.md)
- [实验计划](docs/EXPERIMENTS.md)
- [风险与证伪条件](docs/RISKS_AND_FALSIFICATION.md)

## 当前工程状态

- main 保持稳定的早期研究基线。
- 全项目收敛工作基于 E09 集成代码线建立独立工作分支，不直接修改 main。
- 旧 unified 架构分支与 E09 代码线存在分叉，必须逐项审计，不直接合并。
- 现有研究 PR 的文档、参考实现、可学习原型和集成切片成熟度不同；详见集成登记册。
- 当前没有规模化统一认知模型，也没有证明优于 Transformer 的端到端结果。
- 当前优先级是完成非连续结构组合、证据、生命周期、训练和持久记忆的最小闭环，再开展联合训练。

## 快速开始（main 当前原型）

    python -m unittest discover -s tests -v
    python -m prototype.e01_sparse_composition
    python -m prototype.e01_learned_ranker --json

## 研究纪律

每项能力必须标明假设、设计、实现、实验结果或发布状态。CI 通过不等于科学有效；研究分支存在不等于主线集成；可检索长记忆不等于原生长上下文。所有架构主张都接受公平基线、消融、OOD、资源成本和失败案例检验。

许可与引用要求见 [LICENSE](LICENSE) 与 [RELATED_WORK.md](docs/RELATED_WORK.md)。
