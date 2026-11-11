# Zhouyi-AI 集成登记册 v1

日期：2026-11-11  
用途：统一研究分支、PR、成熟度和集成顺序。状态以 GitHub 实际分支/PR/CI 为准，本文件是审计快照，不是动态 API。

## 1. 成熟度定义

| 等级 | 定义 | 可否作为正式能力 |
|---|---|---|
| R0 | 研究假设/文档 | 否 |
| R1 | 确定性参考实现和测试 | 仅限明确范围 |
| R2 | 可学习原型，有训练/验证隔离 | 通过独立验证后可有限使用 |
| R3 | 跨模块集成切片，契约与 CI 通过 | 可作为受限集成能力 |
| R4 | 多任务、OOD、消融、资源预算和设备测试通过 | 可发布能力 |
| R5 | 长期运行、恢复、安全与外部复现 | 稳定能力 |

CI 通过不是科学有效性证明；研究文档存在不是代码完成；可学习原型不是通用模型。

## 2. 重要集成轨迹（2026-11-11 快照）

| PR | 主题 | 当前分类 | 集成判断 |
|---|---|---|---|
| #146 | CPG-EI v1 跨线 DTO 与收敛基础 | R3 候选 | 基础契约切片 |
| #147 | E12-A20 推理引擎适配 | R3 候选 | 保留原生推理语义 |
| #148 | E12-A6 生命周期投影 | R3 候选 | 生命周期唯一所有权 |
| #149 | E09 v0.3 严格证据绑定/MTS-0 | R3 候选 | 当前 head 50104ed 的 Actions 已通过；仍是堆叠集成分支，尚非 main |
| #150 | CPG-EI v1 执行蓝图 | R0/R1 文档 | 研究规格，不是运行时 |
| #151 | 移动端百万级有效上下文与易象认知 | R0/R1 文档/研究 | 有效记忆不等于原生上下文 |
| #155 | ZNCA 原生认知架构与 N1 参考核心 | R1 候选 | 符号参考底座，不是训练模型 |
| #158/#160 | RSDN 关系状态动力学 | R0/R1/R2 视具体 PR | 需分开看协议、代码和实验 |
| #164 | CSG-GCR 候选生成与全局约束 | R0/R1 | 需要与 SROK 去重分工 |
| #166 | MCRL 元认知资源控制 | R0/R1 | 与 Hyper-Speed 分离策略/执行 |
| #167/#169 | ZPCM/DCMF 与 SQLite 事件账本 | R0/R1 | 研究规格与原型分开；尚无移动设备基准 |
| #176 | ZPCM N0.5 结构认知与语言解耦 | R0 | 文档规格 |
| #177 | N0.6 非自回归结构认知学习 | R0 | TRLW 研究提案 |
| #178 | N0.7 认知算子代数/SROK 规格 | R0 | 规格，不等于可执行内核 |
| #179 / #188 | N0.8 SROK-0 稀疏关系组合 | R1 | 原研究 PR 保持 Draft；#188 已合入 E09 集成分支，完整 CI 通过 |
| #180 | N0.9 神经符号学习协议 | R0 | 训练协议 |
| #181 / #189 | N0.10 角色绑定与高阶评分器 | R2 候选 | 原研究 PR 保持 Draft；#189 已合入；当前合成数据存在 unary 泄漏，高阶必要性未证实 |
| #182 | MTS-0 预序列训练/证据门控 runner | R1/R2 候选 | 需核验与 #149 的职责重叠，不能形成双 runner 真相源 |
| #183 | N0.11 有界组合算子归纳 | R1 候选 | 有界 DSL 枚举，不是神经语义算子发现；保持独立评估 |
| #191 | SROK → E12-A6 生命周期适配 | R3 候选 | 已合入；E12-A6 保持唯一生命周期所有权，SROK 原始分数不映射为置信概率 |
| #193 | SROK → E09 durable prequential loop | R3 候选 | 已合入；完整 CI 通过，SUPPORT commit/reveal/refit 与 LOCKED_TEST 隔离在可信单进程参考运行器中通过测试 |
| #202 | E09/SROK digest-verified crash resume | R3 候选 | 已合入 E09 集成分支；恢复学习器快照、证据账本、预测输入、揭示和修订去重；仅可信单进程恢复，不提供 OS 级隔离或原子跨进程 outbox |

新增 P1 集成记录：#188 SROK-0、#189 可学习评分器、#190 候选池截断报告、#191 SROK→E12-A6 生命周期适配器、#193 SROK→E09 prequential loop 均已合入 E09 集成分支，相关 exact-head CI 通过。#189 仍只是可学习原型，不证明高阶必要性；#193 是可信单进程参考闭环，不代表进程隔离、崩溃恢复或 ZPCM 已完成。上述合入仅进入 E09 集成分支，不代表进入 main。

注意：其他状态仍基于 PR 描述和可见实现范围初步分级；不把文档、测试通过或研究分支存在当作能力证明。

## 3. 合并策略

### A. 先合并可运行契约切片
#146 → #147 → #148 → #149 按堆叠依赖顺序审查；每个 head 重新跑完整 CI，不能用父分支 CI 代替当前 head。

### B. 再集成认知计算内核
#188 SROK-0、#189 可选学习评分器、#190 搜索不完整性报告、#191 E12-A6 生命周期投影、#193 E09 预测提交/揭示/修订参考闭环已进入集成分支。ZPCM 已有 E09 生命周期投影、标签脱敏和可信单进程 checkpoint/recovery 切片；仍需事务 outbox、进程级 evaluator/learner 隔离及故障注入。下一步优先接入 CSG-GCR，并建立 pairwise-preserving 高阶必要性基准；#180 作为训练协议，#183 作为有限 DSL 算子归纳对照。

### C. 再接入记忆和认知状态
#155 ZNCA、#167/#169 ZPCM、#176 结构认知/语言解耦、#177 TRLW 需先确定唯一事件账本、状态语义、工作集和 Context Compiler；不能重复引入 store 或 state owner。

### D. 最后接入横切治理
CSL 负责依赖与失效，MCRL 负责价值/预算策略，Hyper-Speed 负责执行调度；E09 与 E12-A6 作为证据和生命周期权威。所有服务采用适配器接入。

### E. 易象/类象独立因子
XSL、E10、E13、太玄、阴符等研究线必须正交化；先定义任务、grounding、适用域和反例，再与核心认知内核做消融。不可把多套传统系统一次性混合成一个先验。

## 4. PR 审查硬门槛

- 明确基线 SHA、base branch 和上游依赖。
- 说明新增能力属于 R0–R5 哪一级。
- 不能复制权威状态机、证据账本、存储或调度器。
- 有完整测试、错误路径、预算耗尽、恢复和兼容性说明。
- 关键学习结果必须有预注册 split、独立 evaluator 和锁定测试集。
- 资源成本和失败案例必须报告。
- 未验证 PR 保持 Draft；不因数量或日期批量合并。


## 5. Canonical baseline and snapshot caveat (2026-11-11)

Use [BASELINE_MANIFEST](BASELINE_MANIFEST_V1_2026-11-11.md) as the single authority for branch and commit identity. This registry is a dated maturity snapshot, not live branch metadata. In particular, the earlier #149 row reference to `50104ed` is historical; the selected convergence source baseline is `e90f7eb210db456a541eb9f45ec39f64ebb934a5`. PR #202's single-process crash-resume increment is recorded in the convergence execution audit and roadmap; it does not imply OS-level process isolation or an atomic cross-process outbox.


## 6. Live PR dependency audit (2026-11-11)

The canonical branch and SHA values are in [BASELINE_MANIFEST](BASELINE_MANIFEST_V1_2026-11-11.md). The active PR graph is not a flat merge queue:

- **#206** is the documentation/convergence line based on E09 `e90f7eb`.
- **#208** is a separate CSG-GCR branch also based on E09, not on #206. It must be reviewed as a parallel integration candidate.
- **#212** is stacked on an earlier #208 branch commit (`91f6ae4`); #208 head (`5f886df`) is one commit ahead. Its typed unification kernel is standalone and is not yet called by CSG-GCR.
- **#185** is based on `main`, not E09. Reuse its CandidateBundle content/provenance/validation design only after removing its independent lifecycle authority or delegating lifecycle transitions to E12-A6.
- **#213 → #215** is a separate YJ-07/YJ-08 research stack. Neither is a prerequisite for the P1 runtime closure.

All these PRs were Draft at audit time. GitHub reporting `mergeable=true` is not sufficient for approval. Each stack must be rebased or otherwise reconciled against its actual parent head, then tested as a combined exact head.


## 7. CSG-GCR lifecycle persistence stack (2026-11-11)

| PR | Scope | Exact-head CI | Maturity/status |
|---|---|---|---|
| [#217](https://github.com/qingjian0/zhouyi-ai/pull/217) | Typed hyperedge unification bridge into CSG-GCR | `43027843058` success | Draft integration slice |
| [#218](https://github.com/qingjian0/zhouyi-ai/pull/218) | Immutable branch delta and deterministic merge | `43030468165` success | Draft integration slice |
| [#221](https://github.com/qingjian0/zhouyi-ai/pull/221) | Monotonic partial feasibility pruning | `43031651288` success | Draft integration slice |
| [#222](https://github.com/qingjian0/zhouyi-ai/pull/222) | Typed CSG-GCR ↔ Branch Delta bridge | `43032951104` success | Draft integration slice |
| [#223](https://github.com/qingjian0/zhouyi-ai/pull/223) | Typed CSG-GCR → E12-A6 OBSERVED projection | `43034178683` success | Draft integration slice |
| [#226](https://github.com/qingjian0/zhouyi-ai/pull/226) | E12-A6 lifecycle append/replay persistence through ZPCM | `43036878778` success | Draft integration slice |

The #223 adapter is read-only: it creates a typed E12-A6 candidate projection but does not apply lifecycle actions. PR #226 adds the durable lifecycle event path and reconstructs state by replaying through E12-A6. E12-A6 remains lifecycle authority; ZPCM remains durable event-history authority; E09 remains evidence payload and authorization authority.

PR #226 validates append-before-swap behavior, append-failure non-mutation, crash-after-append replay, idempotent action/revision retries, content conflicts, stale cursors, scope isolation, and payload digest integrity. Raw evidence outcome/provenance values are not copied into ZPCM lifecycle records; they are replaced by opaque references.

**Remaining P1 work:** connect E09-verified evidence references to E12-A6 Evidence registration without bypassing split visibility; wire the typed CSG-GCR projection into PersistentLifecycleLedger as one supported ingestion path; then exercise the complete CSG-GCR → E09 evidence validation → E12-A6 transition → ZPCM persistence/restart flow. Cross-process evaluator/learner isolation, authenticated IPC, and transactional outbox remain separate gates. Full CI success validates software behavior and experiment scripts, not scientific validity or production readiness.
