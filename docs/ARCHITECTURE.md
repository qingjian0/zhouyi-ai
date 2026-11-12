# Zhouyi-AI 架构入口

本文件是兼容旧链接的稳定入口。当前主架构决策以 [CPG-EI / Zhouyi-AI 主架构收敛 v2](CPG_EI_MASTER_CONVERGENCE_V2_2026-11-12.md) 为准。

## 权威文档

- [主架构收敛 v2](CPG_EI_MASTER_CONVERGENCE_V2_2026-11-12.md)：系统边界、模块所有权、核心闭环、KV 独立性、训练路线与最高优先级。
- [统一认知架构 v1](MASTER_ARCHITECTURE_V1_2026-11-11.md)：分层设计的详细历史基线。
- [模块契约 v1](MODULE_CONTRACTS_V1_2026-11-11.md)：跨模块 DTO、唯一权威所有权和错误语义。
- [集成登记册 v1](INTEGRATION_REGISTRY_V1_2026-11-11.md)：模块成熟度和分支/PR 集成状态快照。
- [训练与评估路线 v1](TRAINING_EVALUATION_V1_2026-11-11.md)：训练阶段、基线、指标和评估隔离。
- [逐文件运行时与 KV 独立性映射 v1](PER_FILE_RUNTIME_KV_INDEPENDENCE_MAP_V1_2026-11-12.md)：源码、测试、依赖、真实缺口。
- [全项目收敛基线审计 v2](CONVERGENCE_AUDIT_V2_2026-11-12.md)：分支拓扑、安全 PR 堆叠和审计事实。
- [架构决策记录 v1](ARCHITECTURE_DECISIONS_V1_2026-11-11.md)：不可随意漂移的 ADR。

## 一句话架构

**非 Transformer 原生结构认知系统：以 ZNCA 组织认知状态，以 TRLW 表示类型化关系工作空间，以 SROK 做稀疏非相邻组合，以 CSG-GCR 做全局协调，以 Yixiang/XSL 提供可证伪易象/类象算子，以 E09/E12-A6/ZPCM 管证据、生命周期和持久记忆。**

语言模型是可插拔的解析/表达/蒸馏接口，不是认知账本或唯一推理核心。

## 核心计算闭环

`Observe → Ground → TRLW → Yixiang/XSL → SROK → CSG-GCR → Infer → E09 → E12-A6 → ZPCM → Replay → Express/Act`

## 当前最高优先级

不是继续增加模块，而是打通一条从真实 Observation 出发、经过 grounding、结构组合、证据验证、持久化和重启恢复的端到端垂直切片。K0/K1/K2 KV-cache 独立性必须分别验收；架构文档或单分支生命周期测试不能替代完整 E2E 证据。
