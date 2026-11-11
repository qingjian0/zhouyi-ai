# Zhouyi-AI 全项目收敛基线审计 v2

审计日期：2026-11-12  
审计类型：只读仓库拓扑、分支关系、PR 堆叠与架构治理审计  
工作基线：`architecture/production-trust-boundary-v1-2026-11-12` @ `7416cea5a4dc1b83ae85154e782bbf965aea76ce`  
稳定基线：`main` @ `ec77dcb3ef56f80b2a68dc23a6f1bdcbb381574f`  
E09 集成祖先：`integration/e09-v03-evidence-binding-2026-11-11` @ `e90f7eb210db456a541eb9f45ec39f64ebb934a5`

> 本文件记录审计事实和集成决策，不代表任何分支已经合并，也不代表系统达到生产级安全或 R4/R5 成熟度。

## 1. 审计结论

当前最主要的工程风险不是缺少模块，而是多个长分支、堆叠 PR 和独立研究线并存，造成代码基线、架构文档和验证状态不易区分。

本轮确认：

1. `main` 仍是早期稳定研究基线；不应以整体合并长分支的方式收敛。
2. `architecture/production-trust-boundary-v1-2026-11-12` 是从 E09 集成祖先连续推进的架构/集成候选线。
3. 安全 PR 堆叠链继续建立在该架构工作之上；最新 PR #245 head 为 `dc221a7d0b1c4e08ae0a812998464ea335a32918`。
4. `integration/zhouyi-unified-convergence-2026-11-11` 是较早的统一收敛分支，不应与新架构线直接合并；需按文件和能力选择性迁移。
5. main 上的 E13-B3 与 YJ 对称性研究增量必须保留，但不应因此把研究支线变成认知内核的强制依赖。

## 2. 已核实的 Git 拓扑

| 比较 | GitHub compare 结果 | 含义 |
|---|---|---|
| E09 集成祖先 → 架构分支 | ahead 115 / behind 0 | 架构分支从 E09 祖先连续演进 |
| main → 架构分支 | ahead 234 / behind 12 | 与 main 已分叉；不能直接整体合并 |
| main → 旧统一收敛分支 | ahead 159 / behind 12 | 旧线同样与 main 分叉 |
| 架构分支 → PR #245 head | ahead 79 / behind 0 | 安全 PR 堆叠 head 是架构分支的后继 |
| main → PR #245 head | ahead 313 / behind 13 | 最新安全堆叠 head 尚未包含 main 的全部后续提交 |

上述 ahead/behind 是 Git 提交图关系，不是 PR 数量，也不等于可无冲突合并。

## 3. 稳定主线独有的 13 个提交

共同祖先之后，main 有以下 13 个提交未包含在 PR #245 head 的共同历史中：

| 短 SHA | 提交主题 | 收敛处理 |
|---|---|---|
| `92e31361e7` | E13-B3 disagreement-driven query selection | 保留为主动查询/证据选择研究能力，评估后选择性迁移 |
| `2137900c51` | active discriminating query 与 version-space filtering 测试 | 与 E13-B3 一起迁移 |
| `0806ae2bc2` | E13-B3 独立 brute-force oracle | 与 E13-B3 一起迁移，保留独立 oracle |
| `bc6b476bb9` | E13-B3 文档 | 同步迁移 |
| `168e2d0d54` | 撤销误加研究文件 | 作为历史清理，不单独 cherry-pick |
| `dffcc89684` | 撤销误加研究文件 | 作为历史清理，不单独 cherry-pick |
| `7932697c1e` | 撤销误加研究文件 | 作为历史清理，不单独 cherry-pick |
| `6983791646` | 撤销误加研究文件 | 作为历史清理，不单独 cherry-pick |
| `b8b43926e6` | 明确目标关系对称策略 | 纳入 YJ 对称性研究契约审查 |
| `8805bbd7ff` | 有界精确群验证测试 | 纳入 YJ-10.4 验证线 |
| `d4f01fc72b` | 时间元数据传播测试 | 纳入 YJ-10.4/10.5 兼容性审查 |
| `ec77dcb3ef` | 有界群验证与持久化语义文档 | 纳入 YJ 研究文档审查 |
| `778bb7ef75` | 保留逐观测时间元数据与全局上下文 | 纳入 YJ-10.5 研究线 |

处理原则：不要把 13 个提交作为一个整体 merge 到长分支。E13-B3 是独立主动查询研究能力；YJ-10.4/10.5 是结构对称性与时间演化研究能力；四个 revert 是历史清理。分别验证、分别迁移。

## 4. 安全 PR 堆叠关系

当前可见链路：

```
PR #242  E09 signed verification receipt
  └─ PR #243  atomic receipt/nonce consumption
       └─ PR #244  E12-A6 receipt-authorized single writer
            └─ PR #245  persist authenticated writer identity
```

已核实状态：

- #242：Draft，exact-head workflow run 43076140738 成功。
- #243：Draft，exact-head workflow run 43078795252 成功。
- #244：Draft，exact-head workflow run 43080177000 成功；PR 描述报告 336 项单元测试及 E01–E02-D 流程通过。
- #245：Draft，exact-head workflow run 43085647834 已完成且成功；job 为 unit-tests。
- 这些 PR 仍然是堆叠关系；不得把子 PR 当成独立于父 PR 的可合并增量。

#245 的成功 CI 不等于生产安全验收。PR 文档仍明确保留 OS/进程隔离、认证 IPC、专用数据库写权限、HSM/KMS、外部 anti-rollback checkpoint、崩溃/负载测试等未完成项。

## 5. 独立研究线

### YJ-10.4 / YJ-10.5

- PR #247 是 YJ-10.5 Draft，堆叠于 YJ-10.4 PR #238。
- PR #246 标记为 validation-only，描述明确要求不要合并。
- YJ 研究线应作为可选结构算子研究域；精确群/自同构结果不能自动解释成语义或因果。
- 时间演化的 CONFIRMED 仅表示确定性快照持续性，不是统计置信或因果确认。
- 不自动写入永久记忆、不自动晋升算子、不绕过 E09/E12-A6。

### E13-B3

主动区分性查询属于元认知/主动学习研究能力。它应通过明确接口向 MCRL 提供信息价值候选，不应在未经契约审查时直接成为 MCRL 的第二套策略实现。

## 6. 统一架构所有权（不变）

| 责任 | 唯一权威 |
|---|---|
| 研究总纲/实验范式 | CPG-EI |
| 认知组织与状态 | ZNCA |
| 类型化工作空间 | TRLW |
| 稀疏局部组合 | SROK |
| 候选生成与全局协调 | CSG-GCR |
| 关系状态动力学 | RSDN |
| 易象算子/类象映射 | Yixiang / XSL |
| 证据提交、揭示与可见性 | E09 |
| 候选生命周期状态机 | E12-A6 |
| 持久事件源及其投影 | ZPCM / DCMF（一个权威事件源，多个派生视图） |
| 依赖失效传播 | CSL |
| 计算价值、继续/停止策略 | MCRL |
| 获准任务的 DAG 执行 | Hyper-Speed |
| 语言输入/输出 | 可插拔适配器 |

不得新建第二套证据账本、生命周期状态机、权威事件源或全局调度器。

## 7. 推荐的集成顺序

1. **冻结 main 的稳定角色**：不移动 main，不重写历史。
2. **以架构分支作为架构审查基线**：所有模块按单一所有权和契约检查。
3. **按 #242 → #243 → #244 → #245 的依赖顺序审查安全链**：保持 Draft，逐个验证 exact head；不能只看最终 PR 描述。
4. **将 main 的 E13-B3 作为独立切片迁移**：保留 oracle、测试和数据隔离。
5. **将 YJ-10.4/10.5 作为独立研究切片迁移**：不与核心运行时强耦合。
6. **逐项审计旧 unified 分支**：只迁移有唯一所有者、无重复账本/状态机、且测试可复现的能力。
7. **建立单一可运行闭环**：Observation → Grounding → TRLW → SROK → CSG-GCR → E09 → E12-A6 → ZPCM → 输出；RSDN/Yixiang 通过可插拔算子契约接入。
8. **完整验证**：全量单元测试、exact-head CI、跨模块端到端、失败/崩溃/恢复、OOD、消融和资源测量。

## 8. 本次审计的非目标

- 不批量合并 PR。
- 不把 Draft PR 转为 Ready。
- 不把架构文档完成视为运行时完成。
- 不开始全模型联合训练。
- 不宣称非 Transformer 架构已经优于 Transformer。
- 不宣称当前参考服务已达到生产级安全隔离。

## 9. 下一项工程任务

下一步不是再写一份总架构文档，而是建立**逐文件、逐测试、逐依赖的集成映射表**，重点核验：

- CSG-GCR 的 typed hyperedge / branch delta / E12-A6 adapter 是否在同一 exact head 上。
- E09 receipt / atomic consume / writer identity 是否在同一 PR 链上完整可重放。
- ZPCM 的事件源、投影、恢复与生命周期是否仍只有一个权威。
- E13-B3、YJ-10.4/10.5 是否能作为独立插件/算子域接入而不复制核心职责。
- 每个迁移项的源 SHA、目标 SHA、文件冲突、测试命令、测试结果、成熟度和回滚方式。

只有逐项完成以上映射，才允许建立最终集成 PR；最终 PR 的目标必须是经过审计的集成分支，而不是直接改写 main。
