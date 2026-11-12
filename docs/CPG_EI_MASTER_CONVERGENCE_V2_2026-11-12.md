# CPG-EI / Zhouyi-AI 主架构收敛 v2

日期：2026-11-12  
状态：架构决策基线与工程执行顺序；不是完整系统已实现或性能已达标的声明。  
父基线：`integration/per-file-runtime-map-2026-11-12` @ `564ac728620002f13db2d8b69975c2779a149e9f`  
本文件是当前主架构决策入口。逐文件证据仍以 `PER_FILE_RUNTIME_KV_INDEPENDENCE_MAP_V1_2026-11-12.md` 为准；PR/分支状态以 GitHub 实时状态为准。

## 0. 一句话结论

**Zhouyi-AI 是以结构化、非自回归认知计算为主，以可插拔语言模型为辅的组合认知系统。**

核心不是“把 Transformer 换成另一个 backbone”，而是把认知状态、关系组合、候选协调、证据验证、持续记忆和表达解耦，组成一个有界、可学习、可审计、可恢复的闭环。

- CPG-EI：研究总纲、实验范式与系统级目标。
- ZNCA：认知生命周期和状态组织。
- TRLW：当前任务的类型化关系工作空间。
- SROK：稀疏、非相邻、角色敏感的组合内核。
- CSG-GCR：候选结构的全局约束、分支协调和资源受限搜索。
- Yixiang / XSL：可学习、可证伪的易象算子与跨域类象映射。
- RSDN：关系状态随时间/事件/干预演化的更新机制。
- E09 / E12-A6 / ZPCM：证据权威、候选生命周期权威、持久事件与派生认知投影。
- CSL / MCRL / Hyper-Speed：依赖失效、计算策略、获准任务执行。
- Transformer/LLM：可选解析器、教师、表达器和对照基线，不是内部认知账本。

## 1. 不再变化的架构决策

### ADR-01：非 Transformer 是认知主路线，不是模型禁令

内部主要状态和推理对象是实体、属性、事件、角色、关系、超边、约束、候选、证据和状态差分，而不是 token 历史。Transformer 可用于语言接口、蒸馏和公平对照；不得把外部 LLM 的能力记到结构内核名下。

### ADR-02：CPG-EI 与各模块不争夺总架构身份

CPG-EI 是研究伞；ZNCA 是认知组织；TRLW 是工作空间；SROK/CSG-GCR 是结构计算。不得把它们实现成互相竞争的平行系统。

### ADR-03：连续与离散双态共存

连续表示负责相似性、参数学习、软评分和动态状态；离散类型/角色/关系/约束负责结构身份和硬约束；证据引用负责可追溯性。相似度不是事实，分数不是概率，类比不是因果。

### ADR-04：易象是算子族和先验候选，不是固定真理表

“象、数、理、变、类、择、综”必须落成有类型的 OperatorSpec：输入/输出签名、前后置条件、不变量、适用域、可学习参数、成本、证据、反例和版本。允许拒绝不适用映射，也允许学习出传统分类之外的新算子。所有先验都要与无先验、随机先验、可学习通用先验和错配先验做消融。

### ADR-05：每种权威状态只有一个所有者

| 责任 | 唯一权威 | 其他模块的权限 |
|---|---|---|
| 认知生命周期/状态语义 | ZNCA | 编排状态，不复制持久账本 |
| 活动关系工作集 | TRLW | 保存当前任务工作视图，不成为长期事件库 |
| 局部组合 | SROK | 提议候选，不提交生命周期 |
| 全局候选协调 | CSG-GCR | 约束/去重/协调，不改写证据 |
| 易象算子定义 | Yixiang | 提供版本化算子 |
| 跨域类象映射 | XSL | 提议映射、验证关系保持并登记反例 |
| 关系动力学 | RSDN | 提议状态更新，不越过证据门控 |
| 预测提交、证据揭示和可见性 | E09 | 唯一证据协议权威 |
| 候选生命周期转换 | E12-A6 | 唯一生命周期权威 |
| 持久事件源及派生投影 | ZPCM / DCMF | 一个事件源；多个可重建视图 |
| 依赖失效传播 | CSL | 维护依赖与 dirty set，不拥有生命周期 |
| 计算价值/停止策略 | MCRL | 预算、继续/停止/提问建议，不执行高权限动作 |
| DAG 任务执行 | Hyper-Speed | 执行已授权计划并回执，不决定证据真值 |

禁止新建第二套证据账本、生命周期状态机、持久事件源、依赖图或全局调度器。

## 2. 收敛后的运行架构

```
外部输入 / 工具 / 多模态
          |
          v
L0 Observation Ingress
          |
          v
L1 Parsing + Grounding
          |  候选语义单元、来源跨度、时间、模态、不确定性
          v
L2 ZNCA + TRLW
          |  连续潜在态 + 离散类型化关系工作集
          v
L3 Yixiang / XSL Operator Registry
          |  类型化算子、类象候选、适用域、不变量、反例
          v
L4 SROK
          |  稀疏非相邻组合、角色绑定、有界候选提议
          v
L5 CSG-GCR
          |  全局约束、跨候选协调、分支差分、预算/截断
          v
L6 Inference + RSDN
          |  推理结果、状态差分、置信/能量/不确定性分离
          v
L7 E09 -> E12-A6
          |  先提交预测、后揭示证据；生命周期唯一推进
          v
L8 ZPCM / DCMF
          |  追加事件、派生投影、按需检索、重启恢复
          v
L9 CSL + MCRL + Hyper-Speed
          |  失效传播、继续/停止/提问、获准 DAG 执行
          v
L10 Context Compiler -> Native Expression / Optional LLM
          |
          v
输出 / 动作 / 新 Observation
```

主闭环：

`Observe → Parse/Ground → Materialize TRLW → Retrieve → Apply Operators → Propose → Compose → Coordinate → Infer → Commit → Reveal → Revise → Validate → Persist → Express/Act`

失败、证据不足、冲突、歧义、预算耗尽、搜索截断、过期依赖和权限拒绝均为一等状态；不得伪装成确定答案。所有异步写入必须具备幂等键、回执和恢复语义。

## 3. 模块职责收敛与边界

### 3.1 输入与 grounding

Observation 只代表观测，不代表事实。解析输出必须保留原始载荷引用、source span/region、时间、模态、scope、解析置信度和状态。grounding 负责把输入映射成 SemanticUnit、Relation/Hyperedge 候选；事实可信度必须由证据流程确定，不得直接复制解析器 confidence。

### 3.2 TRLW 与 ZNCA

TRLW 是有界活动工作集，不是全部历史。建议工作状态包含：typed nodes、ordered role hyperedges、continuous latent state、candidate branches/deltas、constraints/goals、evidence refs、temporal metadata、schema/operator/model versions。ZNCA 管生命周期组织；不另建与 ZPCM 重复的长期存储。

### 3.3 SROK 与 CSG-GCR

SROK 只做局部稀疏组合：角色槽检索、非相邻元素组合、局部算子应用、类型/硬约束过滤、候选评分和预算报告。CSG-GCR 只做全局协调：跨候选约束、分支共享/合并、冲突检测、去重、排序和停止。两者不得重复枚举同一搜索空间。候选池截断必须标记不完整。

### 3.4 Yixiang / XSL / RSDN

Yixiang 管算子目录与算子学习；XSL 管跨域映射及关系保持审计；RSDN 管时间/事件/干预驱动的关系状态变化。三者均输出版本化候选和证据引用，不直接写 E09、E12-A6 或 ZPCM。易象算子必须可关闭、可替换、可消融。

### 3.5 E09 / E12-A6 / ZPCM

E09 管预测—揭示证据协议和学习可见性；E12-A6 管候选生命周期；ZPCM 管持久事件和可重建投影。单分支 typed-candidate 生命周期测试不等于 Observation 起点的完整 E2E；单进程检查不等于生产安全隔离。world-family/domain 必须由可信 E09 authority 或版本化 registry 派生，不能信任调用方自由填写（Issue #251）。

### 3.6 CSL / MCRL / Hyper-Speed

CSL 是依赖失效服务；MCRL 是策略/预算决策；Hyper-Speed 是获准 DAG 执行器。三者通过窄接口连接，避免职责重叠和权限蔓延。

### 3.7 语言接口

先把已验证认知结构编译成最小充分证据包与答案计划，再表达。原生表达器是目标能力，尚不能因为架构文档存在就视为已实现。外部 LLM 是可选适配器；输入解析、输出表达和结构认知内核的指标分别核算。

## 4. KV Cache 独立性与长上下文

KV Cache 不是持久记忆，也不应成为结构认知连续性的必要条件。必须区分三种验收：

| 门槛 | 目标 | 当前判断 |
|---|---|---|
| K0 结构内核独立 | SROK/超图/CSG-GCR/E09/E12-A6/ZPCM 结构路径不需要 Transformer KV | 已审阅切片不依赖 KV 接口；需在统一运行路径复测 |
| K1 长程认知独立 | 多轮任务依靠固定上限活动工作集 + 外部事件/语义记忆，跨重启恢复 | 未证明 |
| K2 原生表达独立 | 表达路径不调用 Transformer 自回归 KV | 未证明；尚需可运行 native expression |

### 4.1 内存预算的正确口径

必须分开报告模型权重、进程 RSS、活动工作集、索引/缓存、持久化存储、语言模型上下文。PR #256 的第一版规格目标是 **8K 活动上下文运行时 ≤16 MiB、1M ≤64 MiB**；更激进的 8K ≤8 MiB、1M ≤32 MiB 是优化挑战。以上只指上下文/认知运行时预算，不含模型权重，也不等于已达成的实测结果。

长期数据走磁盘优先、流式摄取、语义分块、按需检索、局部物化和增量更新；RAM 中只保留有界工作集。不能把百万 Token 可检索历史称为百万 Token 原生上下文。

### 4.2 M0/M1 当前工程边界

- PR #258（M0）：RSS 采样与逻辑内存池账本；逻辑池计数不是实际 RAM，精确峰值仍需隔离子进程/OS high-water 验证；当前 PR 仍 Draft，未证明 8K/1M 目标。
- PR #261（M1）：可恢复流式原始证据摄取；固定字节上限、UTF-8 安全边界、chunk hash/span、SQLite WAL、游标原子提交、重启续传和源前缀完整性检查。它只负责 raw evidence，不包含 grounding、检索质量、TRLW、SROK 或 KV 独立性证明；exact-head CI 仍需完成。
- 后续 M2：语义切分/grounding/来源保留；M3：有界活动工作集、检索、失效、恢复与 K1 长程压力测试。K2 单独推进。

## 5. 训练与实验路线

先验证组件，再训练闭环；不启动无边界全模型联合训练。

1. **T0 数据与协议**：固定 schema、数据生成器、scope、split、种子、provenance、独立 evaluator。
2. **T1 确定性内核**：SROK-0、类型化超图、CSG-GCR 的正确性、预算、截断、拒绝和 oracle 对照。
3. **T2 可学习结构评分**：角色绑定、unary/pairwise/third-order；必须排除 unary 泄漏，使用 pairwise-preserving parity/关系族，参数与 FLOPs 匹配。
4. **T3 易象/XSL 算子**：无先验、随机、通用可学习、传统固定、传统可学习、错配先验对照；关系保持、反例拒绝、跨域 OOD。
5. **T4 RSDN/分支动力学**：多步转移、干预、反事实、时间 OOD、增量更新。
6. **T5 证据—记忆闭环**：E09 commit/reveal、E12-A6 lifecycle、ZPCM replay、CSL invalidation、MCRL budgets、Hyper-Speed execution；加入跨进程隔离和故障注入。
7. **T6 表达**：native expression 与轻量/外部 LLM 对照；分离解析器、内核、解码器贡献。
8. **T7 设备部署**：桌面到移动端，测量 RSS、I/O、存储、延迟、吞吐、功耗、温控和重启恢复。

强制基线：线性/MLP、普通图网络、静态/动态超图、SROK 消融、匹配预算 Transformer、可复现 SSM/RWKV/xLSTM 等。不得只挑弱基线。

## 6. 当前真实成熟度（2026-11-12）

| 能力 | 当前证据 | 不能宣称 |
|---|---|---|
| SROK-0 | 确定性稀疏角色组合原型及测试 | 已训练的通用认知内核 |
| N0.10 learnable SROK | 可学习评分原型；现有任务存在 unary shortcut | 高阶推理能力已成立 |
| parity 高阶控制 | PR #262 数学控制：unary/pairwise 线性探针 chance，third-order 能拟合该 parity | LearnableSROK 已学会高阶泛化、XSL 有增益 |
| Yixiang/XSL → SROK | PR #257 窄桥接：显式角色置换、类型保持、有界组合；Draft | 自动发现类象、因果等价、完整 grounding |
| CSG-GCR → E09 → E12-A6 → ZPCM | 单分支生命周期/持久化/恢复切片 | Observation 起点完整 E2E、多进程安全 |
| E09 授权与 writer 安全 | 多个堆叠 Draft PR；部分 exact-head CI 通过 | 生产级 OS 隔离、认证 IPC、抗回滚 |
| M0/M1 记忆运行时 | #258/#261 Draft；规格与切片分开 | 已达成 1M 上下文内存目标 |
| 原生语言表达 | 尚无本轮确认的完整可运行实现 | K2 KV-free 生成完成 |
| 端到端统一训练 | 尚无闭环证据 | 完整模型可训练/可部署 |

成熟度按 R0–R5 管理：R0 规格；R1 确定性原型；R2 可学习组件并有隔离评估；R3 跨模块集成；R4 多任务/OOD/消融/资源门槛；R5 长期运行、恢复、安全和外部复现。CI 通过不等于科学有效性。

## 7. 唯一最高优先级：打通真实 Observation-to-Memory 垂直切片

停止继续扩展横向模块。下一阶段只围绕这一条链推进：

`Observation → Grounding → TRLW → Yixiang/XSL OperatorSpec → SROK → CSG-GCR → E09 → E12-A6 → ZPCM → Restart/Replay → AnswerPlan`

必须交付：

1. 一个真实输入格式与严格 Observation schema（保留原文跨度、来源、时间、scope）。
2. 一个可测的 grounding adapter，输出 SemanticUnit/Relation，不把解析置信当真值。
3. 一个最小 OperatorRegistry；先接 PR #257 的显式 XSL→SROK bridge，算子默认可禁用。
4. TRLW 工作集物化与版本绑定。
5. SROK 候选接入 CSG-GCR 的唯一组合/协调路径；预算耗尽显式返回。
6. E09 权威验证证据来源；Issue #251 的 domain provenance 缺口必须关闭或隔离相关能力。
7. 通过 E12-A6 唯一生命周期写入 ZPCM；使用事务 outbox/回执/幂等键，不能由 learner 直接写账本。
8. 新实例重启 replay 后得到相同的结构状态和可追溯证据。
9. 一条从原始 Observation 起步的完整 E2E 测试；不得直接 fixture 最终 typed candidate。
10. exact-head 全量 CI、失败注入、预算测试和可复现资源报告。

先完成单分支可信参考运行，再做多分支合并、生产 IPC 与端侧优化。不得将安全 PR 堆栈拆开批量合并；按依赖顺序逐项验收。

## 8. 研究线如何纳入而不污染核心

- E13-B3 主动区分性查询：作为 MCRL 的信息价值候选提供者，不拥有第二套策略状态。
- YJ 对称性/群结构：作为 Yixiang/XSL 的可选算子研究域，不把数学自同构直接解释为语义或因果。
- 其他周易、太玄、阴符表示：保持正交实验因子，先分别验证，不打包成一个混合先验。
- Transformer、SSM、RWKV、xLSTM、图/超图/EBM：作为可替换计算后端或对照，依据任务/预算选择，不预先宣布赢家。

## 9. 架构完成定义

只有同时满足以下条件，才称为“全项目架构收敛完成”：

- 一个主架构入口和一套版本化模块契约；
- 每个模块唯一所有者、清晰输入/输出和禁止越权清单；
- 一个真实 Observation 起点的结构认知 E2E；
- E09/E12-A6/ZPCM 的证据、生命周期、持久化和恢复闭环；
- Yixiang/XSL 在核心路径可开关、可追踪、可消融；
- K0/K1/K2 分层验收，未通过项明确标注；
- 训练、评估、内存和性能结果可复现；
- 分支/PR 按依赖顺序逐项集成，main 不被长分支覆盖。

**最终收敛原则：先把一条链做真，再扩展能力；先证明，再训练规模；先有界运行，再追求百万上下文。**
