# Zhouyi-AI 开发路线图（2026-11-19）

> 本路线图以 `dev` 当前集成状态为准；`main` 是稳定分支，未经明确发布决策不修改。状态只表示代码/实验资产的实际落地程度，不把设计文档、工具存在或历史 CI 结果等同于验收通过。

## 项目定位

研究组合并行生成与易象启发式认知架构（CPG-EI），重点探索动态关系组合、证据约束的结构学习、多路径推演与可检验的易象表征。项目尚不能宣称已实现通用认知系统、通用语言模型或 Transformer 替代品。

## 当前集成基线

- 集成分支：`dev`；稳定分支：`main`。
- 当前 `dev` HEAD：`20bd82b37ca053d915d6fc8132c08ba8b56e9adc`，相对 `main` ahead 79、behind 0；`main` 未修改。近期已提交 E12-A6 checkpoint 持久化、校验、分页流式恢复和基准工作流；N0.10 百万行基准工作流正在该 HEAD 上运行。
- 本轮已合并 PR #537（CPG-EI one-pass evaluation）和 PR #539（E12-A6 hard-process-termination recovery test）。#537 精确 head 的 22 项检查全部成功；#539 精确 head 的 unit-tests 与 detect-research 成功。
- #539 的强杀测试验证 SQLite 权威事件提交后、scratch-state mutation 前进程退出，再由新进程恢复；它不等同于断电、磁盘故障或完整 checkpoint 验收。
- `9452d6f` 的整仓 `tests` 工作流 #44390349072 已完成：`unit-tests` 与 `detect-research` 均 success，研究评估矩阵按路径条件 skipped；该结果验证的是代码提交 `9452d6f`，不是后续仅修改路线图的 `f4f5317`。
- 当前研发重点：E12-A6 安全快速恢复协议；N0.10 百万行真实训练与 RSS；CPG-EI 神经/非有限语法跨族学习；易象真实 Gold 数据校勘与独立标注。


## 能力状态

| 工作流 | 已落地 | 尚未通过的关键验收 |
|---|---|---|
| ZPCM / E12-A6 | 追加式权威事件日志、SQLite 持久化、事件摘要校验、授权 receipt/nonce 唯一索引、候选历史索引和授权历史 keyset 分页；候选/证据/动作投影与 high-water/count 元数据由同事务触发器维护；`PersistentLifecycleLedger` 使用临时 SQLite scratch state，普通写入不再 deepcopy 全账本；新增持久 checkpoint v2：事件前缀 digest、授权投影 digest、snapshot header digest、分类型有界 page、page digest/manifest digest；checkpoint 发布在 `BEGIN IMMEDIATE` 事务内原子完成；恢复校验通过后从 checkpoint 高水位只做 suffix 语义重放，损坏时回退权威日志全量重放 | checkpoint 的事件前缀完整性校验仍扫描 O(N) 权威事件，故不是 O(1) 启动；scratch state 仍是进程级临时库；50 万条合成候选历史中 checkpoint 恢复约 21.58 秒、全量重放约 26.27 秒，峰值 RSS 均约 31 MiB，ZPCM 初始化另约 12.6 秒；当前分页 checkpoint exact-head 完整测试、发布中断/磁盘故障、并发 adapter、清理失败及生产事件混合负载仍待验收 |
| M1 数据摄取 | UTF-8 分块读取、Manifest、Chunk Digest、SQLite 持久化、恢复和有界 chunk 读取 | 跨 Chunk tokenizer 一致性、整篇 reference 对照、大文本吞吐与 RSS exact-head 报告 |
| M2 Observation | Observation DTO、EvidenceRef、Lazy Store、SQLite 索引、Keyset Paging、来源校验与重启恢复 | 大规模 RSS 实测、Gold 标注、语义提取质量、abstention 与独立标注评估 |
| N0.10 / SROK | SROK 组合内核、LearnableSROK、JSONL 流式/out-of-core runner、SQLite 元数据、checkpoint 恢复、locked-test 评估与 RSS 工具；`20bd82b` exact-head 整仓测试和百万行专项工作流均成功；1K/10K/100K/1M 每 split 均执行两轮训练，1M 每 split（总计 200 万行）耗时 201.286 秒，峰值 RSS 27,508 KiB（相对基线 +5,348 KiB），loss 1.3863→0.7705，dev 100 万行完成流式读取 | 该结果来自合成数据，不能证明真实任务准确率/泛化；仍需独立验证 group-disjoint split、恢复一致性、materialized oracle 数值一致性，以及更丰富训练预算下的学习效果 |
| CPG-EI | 有限候选语法、符号搜索、经验贝叶斯 few-shot、混合算子发现、motif/optimizer 诊断、扩展合成语料；`45100bd` exact-head 的三种子组合语法 OOD 基准成功：24 个合成教师族/1,536 条记录，锁定集 bit accuracy：符号 68.95%、全多项式 46.68%、符号支持混合 56.84%；符号方法完整状态准确率 32.29%，优于另两者 | 该协议是 operator-grammar OOD、每个教师族都用自身 train split 适配，不是 held-out-family zero-shot；神经或非有限语法 meta-learner、预算公平强基线、更深组合 OOD 和跨分布验证仍未完成；结果只适用于声明的合成任务 |
| 易象 / Yixiang | 卦爻编码、状态转移、五行/类象关系工具、结构保持映射与多组合成 OOD 原型 | 真实古籍 Gold 语料、独立标注/仲裁、页码来源追踪、消融、因果/语义层级验证和真实任务评估 |
| 集成编排 | Orchestrator、实验协议、测试与工作流自动化 | 证据摄取→表征→候选发现→学习→评估→生命周期持久化的完整 clean-checkout E2E 闭环 |

## 优先级与交付门禁

### P0 — 工程持久化与可恢复性

1. 将 `memory_events` 保持为唯一权威事件源；SQLite current-state projection 只能是可重建投影。
2. candidate、evidence、action 当前状态投影已落地；补齐候选-证据、动作-证据关系的高效查询索引（按实际查询负载选择规范化表/索引），action_id 与 candidate_id 必须保持独立字段。
3. 当前投影元数据已记录 schema、lifecycle high-water sequence 和 event count；checkpoint v2 已增加权威事件前缀 digest、授权投影 digest、页面 digest manifest；projection generation 和完整版本迁移门禁仍需补齐。
4. 持久 checkpoint v2 已实现：先验证权威事件前缀和页面摘要，再将 checkpoint 状态流式 hydrate 到临时 SQLite scratch state，仅对 checkpoint 之后的 suffix 做语义重放；checkpoint 缺失/损坏时回退全量权威事件重放。当前前缀 digest 仍需 O(N) 扫描，因此只减少语义重放，不构成 O(1) 启动；下一步应评估可验证的分段事件链摘要/持久投影 generation，不能牺牲篡改检测。
5. append 与 candidate/evidence/action 投影已通过 SQLite 触发器置于同一事务；checkpoint 页面与 manifest 元数据也在单个 `BEGIN IMMEDIATE` 事务内发布。仍需针对 checkpoint 发布中断、磁盘故障和并发恢复增加故障注入；保留 E09 receipt/nonce、split、状态迁移、幂等和 digest 约束。
6. 保留 `ledger`/`snapshot()` 作为显式 O(total state) 兼容导出接口，普通启动和按需读取不得隐式调用。
7. 验收：投影删除/损坏重建、事件篡改拒绝、并发写入、崩溃注入、snapshot 与 replay oracle 一致；在 1K/10K/50K/100K/500K 事件规模报告 RSS、Python allocation、SQLite cache/page、恢复耗时。

**完成定义：** 不以“存在 SQLite 表”或单元测试通过作为完成；必须有 exact-head 测试、重建/崩溃测试和 OS RSS 结果。

### P1 — 数据管线与训练规模

1. M1：定义 tokenizer 跨块状态协议，使用 whole-document reference 做边界一致性验证。
2. M2：补齐 Gold Annotation、来源证据、语义单元和 abstention 的独立评估。
3. N0.10：增加版本化数据 Manifest、source/world/rule-family group-disjoint split 和数据摘要校验。
4. 将 locked-test 标签隔离在训练进程之外；训练、验证和最终评估使用明确的数据边界。
5. 在固定预算下比较 unary、pairwise、高阶 SROK、参数匹配 MLP、compute 匹配图模型、exact oracle 与不同 beam 宽度。
6. 报告多种子均值/方差、coverage、abstention、预算耗尽、参数量、耗时和峰值 RSS。

**完成定义：** 规模测试必须在目标规模真实执行；不把 benchmark 工具或小样本 smoke test 作为百万行通过证明。

### P2 — CPG-EI 学习与泛化

1. 将候选生成、候选评价、结构选择和跨域泛化分开度量。
2. 从固定候选枚举推进到预算约束的候选提议机制，并保留规范化、去重、可证伪和证据来源。
3. 实现神经/非有限语法 meta-learner；与符号经验贝叶斯、MLP 等强基线在同数据、同预算下比较。当前三种子组合 OOD 结果中全多项式和符号支持混合均未胜过符号搜索，应先诊断假设空间、训练预算和表示偏差，不以参数规模推断学习能力。
4. 扩大组合深度和规则族 OOD；固定 train/dev/locked-test 隔离，至少多种子复现。
5. 对 truth-function、operator、exact-rule 分层报告，处理结构等价别名。

**完成定义：** 不以有限语法符号搜索的高准确率宣称神经跨族学习或开放域关系发现已完成；组合语法 OOD 与 held-out-family zero-shot 必须分开报告。

### P3 — 易象真实数据验证

1. 建立许可清晰、版本固定、可追溯到书名/版本/页码/段落的古籍 Gold 语料。
2. 至少双人独立标注并仲裁，记录歧义和异文。
3. 分别检验结构同构、统计不变性、语义类比和因果等价，不跨层级推断。
4. 对无先验、随机编码、可学习编码、结构编码、传统关系先验进行预算匹配消融。
5. 发布错误案例、负结果和复现协议。

**完成定义：** 编码正确不等于解释正确；合成规则有效不等于真实古籍映射有效。

### P4 — 系统集成与发布

- 建立 clean checkout 的端到端路径：数据/证据摄取 → 类型化表征 → 候选生成 → 学习/筛选 → locked evaluation → 生命周期持久化 → 可追溯报告。
- 固定 API/schema 版本、运行配置、数据摘要、随机种子和代码 SHA。
- 验证可恢复、权限边界、资源预算、可观测性和故障关闭。
- 先完成 dev 验收，再进行发布审查；不得仅因 CI 通过就自动合并到 main。

## CI 与 PR 收敛原则

- `dev` 是唯一集成目标；禁止为同一功能继续制造平行长期分支。
- CI 以变更路径触发必要专项检查；全量测试保留为集成门禁，重型研究实验只在相关代码/数据变化时运行。
- 同一分支旧运行可取消；不得通过删减必要断言或跳过失败测试来“优化 CI”。
- 对开放 PR 先按 diff 与 dev 基线分类：已覆盖、被替代、仍有独立价值、依赖未满足、纯实验/过时。未完成逐项核对前不批量 merge/close/delete。
- 历史 PR 的 predecessor-head 成功不能代替当前 exact-head 验证。

## 当前未完成声明

截至 2026-11-19，项目仍处于多条研究原型并行推进阶段，尚未达到 P0–P4 全部验收条件。E12-A6 已有持久 checkpoint v2、分页流式恢复及 1K–500K 合成历史对照结果，但前缀完整性扫描仍为 O(N)，且分页 checkpoint 发布故障注入仍需持续验收；N0.10 已完成 1M/每 split、总计 2M 行的合成训练/RSS 基准，峰值 RSS 约 26.9 MiB，但真实任务语料和泛化验收仍未完成；CPG-EI 经验贝叶斯结果仍是有限语法符号方法，神经跨族学习未完成；易象案例库当前 26 条案例均为 unreviewed，不能计作 Gold。M1/M2 大规模资源曲线也未全部验收。任何项目完成度表述必须保留这些边界。


## P5 — 百万 Token 输入与百万连续输出（正式目标，实施启动）

**最终规格（不可降级）：**
- 单次完整输入 1,000,000 tokenizer tokens。
- 单次连续输出 1,000,000 tokenizer tokens。
- 普通消费级电脑和普通手机分别实测。
- 非 Transformer 序列主干优先；稀疏情景记忆、层级证据索引与 CPG-EI 认知层协同。
- 输入和输出分开验收，全部达标前不得宣称实现百万输入/输出。

**已有资产可复用：**
- N0.10 已证明百万行 JSONL out-of-core 合成数据训练/读取的工程管线可运行；这不是百万 Token 上下文训练，也不是自然语言模型的 1M 能力。
- M1 已有分块摄取与 Manifest/Chunk Digest 基础，但跨块 tokenizer 与 whole-document 一致性仍待验收。
- CPG-EI 提供关系/组合推理实验底座；类象主核心 PR #540 仍需独立 exact-head 验收，不能将其符号 MVP 计作神经认知模型。

**交付批次：**
1. **P5-A 协议与计量**：统一 tokenizer、token 级长度、chunk 边界、输入/输出完整性、locked-test、checkpoint 和资源记录。
2. **P5-B 循环主干基线**：在同一训练协议下比较 selective SSM、门控 RNN/线性递归、多尺度状态更新；建立最小可训练模型和可复现实验。
3. **P5-C 稀疏记忆**：原始证据持久化、稀疏情景记忆、层级索引和检索重放；执行有/无记忆消融。
4. **P5-D 认知耦合**：接入类象形成/修订、关系学习、组合 OOD、证据冲突与弃权。
5. **P5-E 长度扩展**：按 4K、16K、64K、256K、1M 课程训练；每级都记录保真、稳定性、吞吐、内存和泛化，最终完整 1M 输入与 1M 连续输出分别验收。
6. **P5-F 设备验收**：普通电脑与普通手机实机测试；不得把开发机/服务器结果冒充手机结果。

**关键指标：** 输入 token 完整率、跨块 tokenizer 等价性、远距离精确检索、多跳联合检索、关系保持、矛盾识别、类象修订、组合 OOD、输出 token 完整率、长输出逻辑漂移/重复/中断、checkpoint 恢复、峰值 RSS/显存、吞吐、延迟和功耗。

**失败边界：** 线性复杂度不等于长程保真；固定状态可能形成信息瓶颈；外部记忆提升不等于主干独立记忆；passkey/needle 单项通过不等于长程理解；摘要替代原文、滑窗丢弃、分段拼接或外部模型代答均不计入 1M/1M 验收。

详细协议：[docs/ONE_MILLION_SEQUENCE_TRAINING.md](docs/ONE_MILLION_SEQUENCE_TRAINING.md)。

**当前状态：** 研究规格与训练/评测协议已写入 dev；尚未实现或训练出达到 1M/1M 的模型。下一步是 P5-A token 级数据管线与评测驱动器，再进入可训练循环主干，不得将既有“百万行”基准误报为“百万 Token”能力。
