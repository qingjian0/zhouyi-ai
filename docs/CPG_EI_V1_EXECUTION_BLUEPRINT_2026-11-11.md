# CPG-EI v1 执行蓝图：从研究分支到可运行认知系统

日期：2026-11-11  
状态：研究与工程执行方案；不是性能结论，不代表所有组件已经集成。  
基线：`integration/cpg-ei-v1-foundation-2026-11-11`  
原则：`main` 保持稳定；以小切片、显式依赖、可回滚集成推进。

## 0. 核心判断

当前仓库的瓶颈已经从“缺少研究方向”转为“研究成果过多、接口与验证边界尚未收敛”。E02/E09/E10/E11/E12、CSL、易象/太玄/阴符和 Hyper-Speed 已形成多条并行研究线，但分支局部实现不能等同于统一运行系统。

v1 的目标不是一次性合并所有分支，而是建立一条可复现、可审计、可恢复的最小认知闭环：

`Observe -> Propose -> Commit -> Reveal -> Revise -> Validate -> Transfer`

每一步都必须有明确的数据所有权、协议版本、资源成本和失败状态。

## 1. 架构分层与唯一所有权

| 层 | 组件 | 唯一权威/职责 | 禁止事项 |
|---|---|---|---|
| L0 感知与输入 | 文本/多模态适配、观测规范化 | 产生带来源的 Observation | 不直接写长期结构 |
| L1 语义与结构 | 原语、概念、关系、超边提议器 | 产生候选 Proposal 与结构版本 | 不自行决定跨轨生命周期 |
| L2 推演 | 有限域求解、因子图、BP、多路径搜索 | 输出带状态的 InferenceResult | 不把分数伪装成校准概率 |
| L3 证据治理 | E09 共享证据协议 / Trusted Evidence Broker | 事件追加、commit/reveal 绑定、可见性授权 | 不由 learner 进程持有 locked truth |
| L4 生命周期 | E12-A6 | 候选状态与转换的唯一权威 | 其他模块不复制状态机 |
| L5 依赖与协调 | CSL | 结构依赖、失效传播、重验证队列 | 不成为第二个生命周期账本 |
| L6 调度与执行 | Hyper-Speed | DAG 调度、预算、并行度、重试、checkpoint | 不隐式获得 shell/GitHub 写权限 |
| L7 表征研究 | Zhouyi / Taixuan / Yinfu | 独立实验因素及适配器 | 不预设先验有效，不混为同一变量 |

跨模块只传递不可变 DTO、稳定引用和内容摘要。任何持久化写入必须经过其权威所有者。

## 2. 统一数据契约

### 2.1 Observation

至少包含：
- `observation_id`、`episode_id`、`query_id`
- `scope`、`split`、`learner_track`
- 观测 payload digest、来源组/对象身份的评估侧 provenance
- 时间、协议版本、输入模式

学习器可见字段必须由 allowlist 投影产生，不能通过“隐藏字段约定”隔离。

### 2.2 PredictionCommit

提交必须在 reveal 之前不可变地写入：
- prediction id、query/observation id、episode id
- learner track、scope、split
- 预测或显式 abstention
- 结构版本、模型版本、策略版本
- canonical digest、资源计数、时间戳

### 2.3 EvidenceReveal

Reveal 必须绑定到唯一先前 commit，逐字段验证 query、episode、track、scope、split 与 digest。任何字段缺失或多重匹配均 fail closed。旧 v0.1/v0.2 事件可以审计重放，但不得伪造其历史上不存在的 scope/split/digest。

### 2.4 StructureVersion 与 CandidateProposal

结构版本不可变，必须保留 parent lineage、evidence refs、grammar version、scope、definition digest。提议与接受状态分离；提议不自动成为有效知识。

### 2.5 InferenceResult

状态至少区分：
- `IDENTIFIED`
- `AMBIGUOUS`
- `INCONSISTENT`
- `BUDGET_EXHAUSTED`
- `ABSTAINED`

保留排序分数、能量、边际和联合分布的语义差异；没有联合分布时不得合成联合假设。

## 3. 学习闭环与隔离边界

规范顺序：

1. Evaluator 准备任务并隔离 truth。
2. Learner 只获得 allowlisted observation/support view。
3. Learner 生成预测或 abstention。
4. Commit 被持久化并冻结。
5. Evaluator 验证 commit 绑定。
6. Broker 按策略释放最小 reveal/challenge。
7. Evidence 被追加到权威账本。
8. Learner 通过明确的 revision API 更新。
9. 结构版本与 revision event 被记录。
10. 独立 Gate/Evaluator 测试泛化与回归。

数据库中的 actor 字符串、split 标签或同进程对象封装都不是安全边界。生产级隔离需要不同进程/服务、受限 IPC、认证主体、最小化 DTO、存储权限和审计日志。Linux broker IPC MVP 也必须经过威胁模型、凭据验证、重放测试和故障恢复验收后才能作为可信边界。

## 4. 并行研究与调度

Hyper-Speed 应把研究工作表示为 DAG，而不是无约束并发的 agent 群。

任务节点必须声明：
- 输入 artifact digest 与预期输出 schema
- 依赖任务、角色 handler、最大并发与资源预算
- 重试上限、超时、checkpoint 和幂等键
- 允许的能力（read / propose / write-branch / run-tests 等）
- 验收命令、验收证据与失败处理

角色建议：Research、Architecture、Implementation、Experiment、IndependentReview。每个实现切片至少经过独立 Review；实验结论不能由实现该实验的同一 handler 单独签发。

并行规则：
- 可并行：互不写同一文件/分支、依赖已冻结、输入摘要一致的研究与测试任务。
- 必须串行：同一文件写入、同一 SQLite schema migration、同一分支 ref 更新、依赖尚未合并的 stacked PR。
- 失败任务不得自动扩大权限或无限重试。
- 调度器的“并行数”不等于实际吞吐提升；必须报告 wall-clock、CPU、内存、任务等待和协调开销。

## 5. 证据驱动实验标准

每项能力主张必须先注册 Hypothesis 与 ExperimentSpec，再运行实验。至少记录：
- hypothesis id、预注册时间、代码 commit、数据 digest、模型/策略版本
- 随机种子、环境、预算、基线、对照组、指标定义
- 原始观测、预测 commit、reveal、revision、运行日志
- 所有失败/abstention、资源消耗和排除规则

统计要求：
- 配对单位必须是真正独立或满足交换性假设的 episode/seed；不能把相关行当独立样本。
- 同时报告 micro 与 macro 指标、覆盖率、选择性准确率、abstention 和置信区间。
- 多重比较使用预先定义的检验族与校正方法。
- 报告 effect size、原始配对差值、样本量和计算成本。
- Locked Test 只用于最终评价；不能用于调参、阈值选择或主动候选排序。
- 负结果必须保留；不得只发布成功种子。

## 6. 关键能力验证矩阵

| 能力 | 最小证明 | 必需对照 | 不能据此宣称 |
|---|---|---|---|
| 非连续组合 | 在 A+C+E 类任务中正确选择稀疏成员 | 随机、邻接、MLP/Transformer、oracle | 通用语义推理 |
| 高阶关系 | 未见成员组合/关系角色迁移 | 普通图、静态超图、动态超图 | 自主发现普遍规律 |
| 原语发现 | Support-only 识别且可 abstain | 固定词表、随机候选、oracle | 开放世界概念理解 |
| 结构演化 | CREATE/MERGE/SPLIT/PRUNE 在变化分布下收益 | 冻结、无约束更新、门控更新 | 永久自我改进 |
| 多路径推演 | 固定总预算下提高覆盖或质量 | 单路径、并行无协调、并行协调 | 并行必然更快 |
| 易象先验 | 预注册任务上的稳定增益 | 无先验、随机置换、反向先验、可学习先验 | 传统映射天然正确 |
| 跨表征互补 | 正交因素设计与交互项分析 | Zhouyi/Taixuan/Yinfu 单独与组合 | 三者可无损合并 |
| 自主研究 | 可复现地发现缺口、提议实验、执行与独立审查 | 人工计划、固定计划、无审查 agent | 完全自主科学发现 |

## 7. 表征因素的正交化

不要把“符号系统”作为一个不可分解的总变量。至少分离：
1. 语义状态基数 K；
2. 坐标编码基数/位宽；
3. 状态空间因子分解；
4. 结构先验与关系算子；
5. 观察/主动测量策略；
6. 记忆与更新规则。

例如 K=3 可以用两个二进制位或一个三进制位编码；不能把坐标 radix 的不同误判为语义表达能力的差异。周易二元结构、太玄三值状态和阴符观察策略应通过 factorial design 检验主效应与交互效应。

## 8. MTS-0 最小可运行系统验收

MTS-0 不追求大模型能力，先证明闭环完整：
- 一个可控有限世界生成器；
- 至少两个互相独立的 learner track；
- 一个唯一 lifecycle owner；
- 一个共享 append-only evidence protocol；
- commit-before-reveal 与 process isolation；
- 一个结构提议器和一个推演器；
- 明确的 abstention/ambiguity/inconsistency/budget exhaustion；
- 完整 train -> commit -> reveal -> revise -> gate -> locked transfer episode；
- 崩溃后可恢复或明确声明不可恢复；
- 一键测试、固定 seed、可审计 artifact。

通过 MTS-0 后才连接连续 embedding、神经候选提议器和更复杂的多模态解析器。

## 9. 集成顺序与依赖

建议按以下顺序推进，禁止批量合并所有分支：

1. **Contract freeze**：审查并冻结 PR #146 的 DTO/哈希/可见性合同。
2. **Inference adapter**：在 #146 之上验证 #147，保留 E12-A20 原生语义。
3. **Lifecycle adapter**：验证 #148，保证 E12-A6 仍是唯一生命周期权威。
4. **Evidence v0.3**：审查 #121/#129 及 E09 adapter；补齐 query/scope/split/commit digest 和真正的 learner/evaluator 隔离。
5. **Trusted broker**：审查 #140/#144；先做威胁模型和故障测试，再判断是否可作为服务边界。
6. **CSL projection**：只投影依赖与重验证，不复制状态机。
7. **Hyper-Speed**：先验证 #123 scheduler，再验证 #124 agent protocol；之后才连接 provider 和受限执行 handler。
8. **Experiment loop**：审查 #134 的矩阵、注册表、归档、分析和候选排序，补齐 producer provenance 与独立执行验证。
9. **Representation experiments**：将 Zhouyi/Taixuan/Yinfu 作为独立实验因子接入。
10. **MTS-0**：端到端闭环与锁定测试隔离验收。

每个步骤均需 pin source SHA、比较 base divergence、重跑全量测试和适配器契约测试。PR 描述中写有 CI 通过不代表当前 head 仍通过；必须核对实际 head SHA 对应的最新 workflow run。

## 10. 当前优先级与下一步

### P0：先解决集成正确性
- 冻结统一 DTO 与字段语义；
- 明确唯一生命周期/证据所有权；
- 补齐 E09 v0.3 commit/reveal 绑定缺口；
- 证明 learner/evaluator 进程隔离；
- 处理 stacked PR 的依赖与 base SHA。

### P1：让研究闭环可执行
- Hyper-Speed DAG + role protocol + artifact handoff；
- ExperimentSpec、Hypothesis、append-only archive；
- 原始观测分析、配对统计、多重比较；
- 失败重试、断点恢复、资源账本。

### P2：开始真实认知能力比较
- E02 高阶关系 OOD；
- E10 object-disjoint mechanism transfer；
- E11 concept hierarchy/discovery；
- E12 primitive induction and active measurement；
- E03 cross-domain analogy/arbitration；
- Zhouyi/Taixuan/Yinfu orthogonal ablations。

### P3：连续神经组件与规模化
只有 MTS-0 和关键 benchmark 的数据边界可信后，才引入神经编码器、神经 proposal model、持续学习与多模态端到端系统。

## 11. 明确的停止条件

出现以下任一情况，相关能力不得标记为通过：
- learner 能从 payload、日志、缓存或同进程引用读取 locked truth；
- commit/reveal 无法唯一绑定；
- 评估组或对象身份跨 split 泄漏；
- 预测在 reveal 后补写或被修改；
- 资源成本未计量却声称效率提升；
- 统计单位不独立却使用独立样本检验；
- 置信度未经校准却被描述为概率；
- 失败与 abstention 被从分母中静默删除；
- PR head、CI head 与文档报告的 commit 不一致。

## 12. 结论

CPG-EI v1 的第一目标不是“立刻做出比 Transformer 更强的模型”，而是先做出一个结构清楚、证据可信、能够独立运行、能够持续实验和安全演化的认知系统。

最重要的工程原则：**先统一协议和状态所有权，再接入并行研究；先证明可观察、可复现的能力，再扩大模型规模；先保证证据隔离，再谈自主学习。**
