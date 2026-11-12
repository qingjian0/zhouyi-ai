# Zhouyi-AI 逐文件 / 逐测试 / 逐依赖运行时映射 v1

日期：2026-11-12  
工作基线：`architecture/production-trust-boundary-v1-2026-11-12` @ `7416cea5a4dc1b83ae85154e782bbf965aea76ce`  
审计承接：`audit/zhouyi-convergence-baseline-v2-2026-11-12`  
稳定基线：`main` @ `ec77dcb3ef56f80b2a68dc23a6f1bdcbb381574f`  
状态：代码级映射与缺口登记；不代表模块已全部集成，不代表端到端 KV-cache-free 运行已实现。

## 1. 本轮结论

项目已有非 Transformer 结构认知的明确架构决策和多个可运行切片。当前真正的缺口不是再增加一个象数理模块，而是**把已有计算切片连成一条由观测输入到结构推理、记忆更新和结果表达的可运行路径，并证明各环节不依赖 Transformer KV Cache**。

已核实：
- 类型化超边统一、变量约束和单调部分剪枝已进入 CSG-GCR 参考实现。
- SROK-0 有确定性稀疏角色组合内核；N0.10 有可学习结构评分原型，但其高阶必要性尚未被证明。
- CSG-GCR → E09 → E12-A6 → ZPCM 的单分支生命周期 E2E 测试存在，包含重启恢复。
- 该 E2E 测试直接构造 typed candidate，**没有从 Observation/grounding/TRLW/SROK 开始**，因此不能称为完整认知链路 E2E。
- ZPCM 已有持久事件与生命周期投影/回放能力，但不能等同于完整语义记忆、自动概念巩固或长期认知状态引擎。
- 可信 world-family/domain 来源仍有缺口，已由 Issue #251 跟踪。
- 尚未在本轮证据中确认完整的原生语言生成器。因此“内部结构计算不使用 KV Cache”和“端到端语言生成不使用 KV Cache”必须分开验收。

## 2. 模块—源码—测试映射

| 模块 / 所有者 | 已核实源码 | 已核实测试 / 证据 | 当前成熟度与边界 |
|---|---|---|---|
| SROK-0 稀疏关系组合 | `prototype/srok0_kernel.py` | `tests/test_srok0_kernel.py`（需在最终 exact head 重新运行） | R1 确定性基线；按角色类型/标签检索并做有界组合；候选池截断和扩展预算会损失召回；不是语言模型，不是完整可学习认知内核 |
| SROK 可学习评分 | `prototype/n09_learnable_srok.py` | `tests/test_n09_learnable_srok.py` | 可学习结构评分原型；包含 unary/pair/triple 交互特征；现有合成任务有 unary 泄漏，高阶必要性未证实；不可把 margin 当校准概率 |
| 类型化超图统一 | `prototype/typed_hypergraph_unifier.py` | `tests/test_typed_csg_gcr.py` | 类型化变量、角色绑定、等/不等约束、子类型关系与证据来源聚合；是结构约束计算，不是自然语言语义 grounding |
| CSG-GCR | `prototype/typed_csg_gcr.py`、`prototype/csg_gcr_coordinator.py`、`prototype/csg_branch_delta.py` | `tests/test_typed_csg_gcr.py`、相关 coordinator / branch-delta 测试 | 类型化候选协调、部分剪枝、分支差分；剪枝需与未剪枝 oracle 等价；跨分支合并还受 E09 授权约束 |
| CSG-GCR → E09 → E12-A6 → ZPCM | `prototype/csg_gcr_e12a6_ingestion.py`、`prototype/csg_gcr_e12a6_adapter.py`、`prototype/e12a6_zpcm_persistence.py`、`prototype/zpcm_memory.py` | `tests/test_csg_gcr_e12a6_lifecycle_e2e.py`、`tests/test_zpcm_memory.py` | 已有单分支候选生命周期与持久化恢复切片；测试中的候选由 fixture 直接构造，尚未覆盖 SROK 输入端到端 |
| E09 证据协议 | `prototype/shared_evidence_protocol.py`、`prototype/e09_e12a6_evidence_bridge.py`、authority/verifier service 文件 | E09 协议、receipt、lifecycle 集成测试 | 预测提交/揭示与证据可见性有参考实现；world-family 仍由调用方提供，不能视为可信来源；Issue #251 未关闭前不得宣称 domain provenance 完整 |
| E12-A6 生命周期 | `prototype/e12a6_lifecycle_contract.py`、`prototype/e12a6_zpcm_persistence.py` | `tests/test_csg_gcr_e12a6_lifecycle_e2e.py` 及生命周期测试 | 生命周期唯一权威；ZPCM 负责持久化事件，E12-A6 负责状态转换；不可在其他模块复制状态机 |
| ZPCM / DCMF | `prototype/zpcm_memory.py`、`prototype/e12a6_zpcm_persistence.py` | `tests/test_zpcm_memory.py`、生命周期 E2E | SQLite 追加事件、幂等、完整性摘要、有限检索、断言状态、生命周期回放；当前投影/检索有界且派生，不等于自动语义巩固、完整情景/程序/类象记忆或移动端性能验证 |
| Yixiang / XSL | 架构与模块契约已定义算子/跨域映射责任；本轮尚未将可执行算子实现、注册表、训练入口和核心调用点逐一定位到同一 exact head | 需补齐算子级单测、保持关系测试、错配先验/反例测试与核心闭环集成测试 | 不能仅凭卦象编码或研究文档宣称类象认知已进入主计算路径；暂列为“接口/研究线已定义，运行时接线待核” |
| RSDN | 架构定义关系状态动力学职责；本轮未确认与 SROK/CSG-GCR/ZPCM 同一运行闭环的训练/更新调用链 | 需补齐状态转移、干预、反例、增量更新和恢复测试 | 不把设计规格或独立原型当作集成动力学引擎 |
| ZNCA / TRLW | `docs/MASTER_ARCHITECTURE_V1_2026-11-11.md`、`docs/MODULE_CONTRACTS_V1_2026-11-11.md` 定义统一工作状态与 DTO | 需将状态构造、状态版本、工作集物化、grounding 输出和算子消费测试映射到具体源文件 | 当前文档契约比可验证的全链路运行实现更完整；需避免第二套状态库/事件源 |

## 3. 关键 E2E 边界

现有测试 `tests/test_csg_gcr_e12a6_lifecycle_e2e.py` 覆盖：

`typed candidate fixture → CSG-GCR typed coordination → E09 reveal validation → E12-A6 lifecycle → ZPCM persistence → new-instance replay/recovery`

它证明的是**单分支生命周期持久化切片**，不是：

`Observation → Grounding → Yixiang/XSL → TRLW → SROK → CSG-GCR → RSDN → E09 → E12-A6 → ZPCM → native expression`

后者才是目标闭环，当前不能标记为完成。

另外，跨分支授权合并、signed receipt nonce 原子消费、writer identity 和部署级身份隔离属于独立安全链；不得把单分支 E2E 成功外推为多进程/生产安全闭环。

## 4. KV Cache 独立性：必须分三层验收

### K0：结构认知内核不依赖 KV Cache
SROK、typed hypergraph unification、CSG-GCR、E09/E12-A6/ZPCM 的已审阅代码路径以结构对象、关系、候选、事件和 SQLite 状态工作；这些切片本身没有显示出对 Transformer K/V 历史缓存的接口依赖。

### K1：长程认知连续性不依赖 KV Cache
尚未证明。需要用固定大小活动状态 + 外部持久事件/语义记忆，在长交互中持续更新并恢复；必须测量信息保真、冲突处理、遗忘、恢复、工作集大小、峰值 RSS 和每轮增量计算。不能把磁盘可存储历史量称为活动上下文容量。

### K2：端到端生成不依赖 KV Cache
尚未证明。本轮没有确认项目已有可运行的原生非自回归语言表达器。若输出仍调用自回归 Transformer，则输出端仍可能产生 KV Cache。必须将“认知结构计算”与“自然语言表达”分开测量，并实现/验证不调用 Transformer 的表达路径，或明确将语言模型标为可选适配器而非必需依赖。

## 5. 主要架构缺口与优先级

### P0 — 补齐真实输入到输出的最短结构认知链路
1. 定义 Observation → SemanticUnit / Relation 的 grounding 契约，保留来源跨度与不确定性。
2. 将 Yixiang/XSL 算子注册为类型化 OperatorSpec：输入/输出类型、前置/后置条件、保持不变量、适用域、参数、成本、证据、反例和版本。
3. 将 grounding 输出接入 TRLW 工作状态，再由 SROK 提出非相邻角色组合。
4. 将 SROK 结果接入 CSG-GCR typed coordination；保留预算、截断、歧义和拒答状态。
5. 复用现有 E09/E12-A6/ZPCM 权威路径，不创建新账本或生命周期状态机。
6. 建立一条真实输入的端到端测试；不能再由测试直接构造最终 typed candidate 代替前半链路。

### P0 — 关闭证据域来源缺口
按 Issue #251：world-family/domain ID 必须由可信 E09 事件 schema 或受信任、版本化 registry 派生；验证 observation/commit/reveal 一致性；拒绝调用方覆盖；增加跨域和伪造负向测试。

### P1 — 证明类象/高阶结构的独立贡献
构建 unary/pairwise 统计匹配、三阶结构区分、角色置换反例、保留二元投影的高阶扰动实验。对比无先验、随机先验、通用结构先验、易象算子先验和错配先验；匹配参数量、数据、候选池和计算预算。高阶必要性未通过前，不宣称类象算子带来独立增益。

### P1 — 证明持续状态与记忆替代 KV Cache
定义有界活动工作集与持久记忆分离；设计增量更新、依赖失效、压缩/巩固、冲突保留和按需恢复。长对话测试应跨进程重启，报告细节召回、关系召回、错误巩固率、遗忘率、每轮状态增量和 RAM。

### P1 — 独立验证非自回归表达
先定义输出语义目标：由结构化事实/关系/推理轨迹生成答案计划，再进行短文本表层实现。对照自回归模型评估事实覆盖、语义一致、可读性、延迟、RAM；认知内核成绩不得计入外部 LLM 能力。

## 6. 最小验收矩阵

| 验收编号 | 必须通过的测试 | 通过意味着什么 | 不意味着什么 |
|---|---|---|---|
| E2E-01 | 原始 Observation 到 TRLW typed state | 输入 grounding 可运行且有来源 | 证明开放域理解 |
| E2E-02 | Yixiang/XSL operator contract + ablation | 算子契约有效、先验贡献可归因 | 证明传统理论普遍正确 |
| E2E-03 | TRLW → SROK → CSG-GCR | 真实候选组合链路打通 | 证明高阶能力优于强基线 |
| E2E-04 | CSG-GCR → E09 → E12-A6 → ZPCM → restart | 生命周期与持久恢复闭环 | 证明多进程安全隔离 |
| E2E-05 | 长交互、多次重启、受限 RAM | 持续认知不依赖历史 K/V 缓存 | 证明无限上下文 |
| E2E-06 | native expression without Transformer | 输出端不依赖 Transformer/KV Cache | 自动达到人类语言质量 |
| SCI-01 | pairwise-preserving high-order attribution | 高阶/类象结构是否有独立贡献 | 证明普遍智能 |
| SCI-02 | OOD + counterexample + locked test | 有界分布外迁移与证据修订 | 证明开放世界通用学习 |

## 7. 代码集成规则

- 不直接合并长分支，不移动 `main`。
- 不创建第二套证据账本、生命周期状态机、持久事件源或全局调度器。
- 每个迁移项记录源 SHA、目标 SHA、文件冲突、测试命令、exact-head CI、成熟度和回滚方式。
- 保持 #242 → #243 → #244 → #245 安全 PR 堆叠顺序；子 PR 不得脱离父依赖单独宣称可合并。
- E13-B3 与 YJ-10.4/10.5 作为独立研究切片接入，不强制成为认知内核依赖。
- 未通过高阶必要性和 OOD 门槛前，不启动全项目联合训练，也不宣称 Transformer 替代完成。

## 8. 本轮最终判断

Zhouyi-AI 已经具备“结构化、非 Token 中心”认知计算的若干真实组成部分，但还没有证据证明象数理/类象算子已经贯穿真实输入、组合推理、持续记忆和原生表达的完整运行链。

下一阶段的主任务是：**把现有模块接成一条可运行、可复现、可消融、可恢复的结构认知闭环，并分别通过 K0/K1/K2 三层 KV Cache 独立性验收。**


## 9. E12-A6 本地生产边界：PR #248 / #252 代码审计

### 9.1 已有实现的分层

| 层 | PR / 源码 | 已实现 | 未证明 |
|---|---|---|---|
| 单写者进程 | #248 `prototype/e12a6_writer_runtime.py` | POSIX `flock`；先锁后开 SQLite；目录 0700、DB/lock 0600；拒绝最终 DB 路径 symlink；锁随 runtime 生命周期持有 | 不认证 IPC；不阻止 root 或同 UID 进程；不提供 Windows 后端 |
| 本地 IPC 传输 | #252 `prototype/e12a6_unix_socket.py` | Linux `SO_PEERCRED` 取 PID/UID/GID；UID allowlist；私有 socket 目录；请求大小/超时/重复 JSON key/额外 frame 校验 | 不负责 workload 身份映射；不解析 CSG-GCR 业务协议；不自动调用 writer service |
| 业务授权 | #244/#245 `prototype/e12a6_writer_service.py` 及 receipt 链 | receipt 验签、绑定与一次性消费；writer identity 审计 | 尚未由 #252 的真实 UDS dispatcher 端到端接线验证 |
| 部署隔离 | 专用 OS UID + 私有目录 + DB ACL | 文档给出部署要求 | 未证明 learner/runner 进程无法直接打开 E09/ZPCM 数据库；未证明同 UID 恶意进程隔离 |

### 9.2 最关键的集成缺口：SO_PEERCRED 尚未接入 writer service

PR #252 的 `E12A6UnixSocketServer` 接受任意 dispatcher callback。它把内核读取的 `E12A6PeerCredentials(pid, uid, gid)` 传给 callback，并在 transport 层检查 UID allowlist；但仓库当前 PR 改动没有提供一个生产 dispatcher，将 peer tuple 映射成 server-owned workload credential，再调用 `E12A6WriterRuntime.service.submit_authorized_merge_candidate`。

现有测试证明的是：

- 内核 peer credentials 与 JSON 中伪造的 pid/uid/gid 分离；
- 非 allowlisted UID 不会进入 dispatcher；
- framing、重复 key、长度、socket path 等 transport 约束。

它**没有**证明：

- UID/GID → workload principal 的映射来自服务端固定配置，而非请求 JSON；
- dispatcher 只允许一个明确 operation/schema，并将 scope、branch、parent、evidence refs 交给 writer service 校验；
- 从真实 UDS 请求到 receipt 验签、nonce 原子消费、durable writer audit event 的完整调用链；
- 重启后该链路仍可正确 replay；
- learner/runner OS account 无权读取或直接打开 writer 数据库。

PR #252 exact head `ee13ffd9ca8a9b1a596a2c28a0c06f0b0e4691a7` 在本次检查时没有返回关联 workflow run；因此不能报告该 PR 的 CI 已通过。

### 9.3 PR #248 的路径处理补强项

`E12A6WriterProcessLock.acquire` 对父目录使用 `Path.stat()`，该调用会跟随父目录 symlink；runtime 对数据库路径的 `is_symlink()` 检查只覆盖最终路径组件。现有测试覆盖最终 lock/DB symlink，但没有覆盖 symlink parent path。

当前文档要求父目录由专用 service UID 持有且为 0700，这降低了常规部署风险；但更强的路径边界应使用 `lstat()` 明确拒绝 symlink parent，并考虑基于已打开目录 FD 的 `openat/O_DIRECTORY/O_NOFOLLOW` 方式完成 lock/DB 创建与检查，避免路径组件替换竞态。此项是防御性加固建议，不是已证明的可利用漏洞。

### 9.4 下一步最小集成验收

1. 新增唯一生产 composition root：创建 `E12A6WriterRuntime`，再启动 UDS server；关闭顺序必须先停止/等待 IPC server，再关闭 writer runtime 和释放 flock。
2. 提供显式 UID/GID → workload principal 配置表；peer credentials 是唯一身份输入，JSON 身份字段一律忽略或拒绝。
3. dispatcher 实施 operation 与请求 schema allowlist；未知 operation/字段、重复 evidence refs、错误 scope、过期/重放 receipt 全部 fail closed。
4. 增加真实集成测试：UDS client → kernel peer credentials → dispatcher → `E12A6WriterService` → receipt verification → nonce consume → persistent audit → process restart/replay。
5. 在不同 OS 用户下验证 learner 无法访问 E09/ZPCM 文件；同时记录 root、同 UID、allowlisted UID compromise 的明确威胁模型。
6. CI 至少覆盖 Linux IPC 集成测试；Windows 目标必须另行实现并验证锁/IPC backend，不能将 POSIX 通过结果外推到 Windows。

**成熟度结论：** #248 提供单写者本地进程基线，#252 提供可复用的 Linux peer-authenticated transport primitive；二者尚未形成可验收的端到端生产 writer 服务。不要把“SO_PEERCRED 已实现”表述为“writer IPC 安全链已完成”。
