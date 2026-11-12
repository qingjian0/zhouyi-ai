# Zhouyi-AI 全项目架构收敛与阶段收尾基线

日期：2026-11-12  
状态：工程治理基线 / 文档 exact-head CI 已通过（本次增补后需重新验证）；不是全项目已集成、训练就绪或生产就绪声明。  
稳定基线：`main` @ `b8b43926e666d83a9ce09d2e71eb9294b2d86c97`

## 0. 收敛结论

当前仓库的主要问题已从“缺少模块设计”转为“实现分支、验证分支、集成祖先和稳定主线之间存在大量并行堆叠”。截至本审计，开放 PR 数量较多，多个子 PR 依赖父分支；仅凭 PR 可合并标志或单测通过不能证明整条链可集成。

本轮采用以下最终治理原则：

1. `main` 继续作为稳定、可复现研究基线，不批量合并长分支，不重写历史。
2. 架构收敛文档是唯一责任边界与集成顺序的决策入口；模块实现仍以各 PR 的 exact-head 源码、测试和 CI 为准。
3. 按能力切片集成，禁止按“分支数量”或“PR 数量”合并。
4. 先完成可运行、可恢复、可测量的最小闭环，再扩大训练；不启动无界全模型联合训练。
5. 所有“完成”必须同时标明代码状态、测试范围、数据范围、性能范围和未验证边界。

## 1. 唯一模块所有权

| 域 | 唯一责任 | 明确禁止 |
|---|---|---|
| CPG-EI | 总研究纲领、问题定义、实验协议与证伪标准 | 不再实现第二套认知内核 |
| ZNCA | 认知状态组织与生命周期语义 | 不复制 ZPCM 持久事件账本 |
| TRLW | 有界、类型化的当前工作集 | 不成为全历史数据库 |
| SROK | 局部稀疏、角色敏感、非相邻组合 | 不承担全局分支合并与调度 |
| CSG-GCR | 全局候选约束、分支协调、预算与停止 | 不重复 SROK 搜索，不改写证据 |
| Yixiang | 易象算子目录、版本、学习参数与适用域 | 不把传统映射当作固定真理 |
| XSL | 跨域类象映射、关系保持验证与反例 | 不将类比直接升级为因果 |
| RSDN | 时间、事件、干预驱动的关系状态动力学 | 不绕过证据和生命周期门控 |
| E09 | 预测提交、证据揭示、权限和学习可见性 | 不允许调用方自报可信身份/证据域 |
| E12-A6 | 候选生命周期状态机与授权消费 | 不建立第二套生命周期状态机 |
| ZPCM / DCMF | 唯一权威追加事件源及可重建投影 | 投影不得成为第二权威，不复制全量事件正文 |
| CSL | 依赖关系、失效传播与 dirty-set | 不拥有候选生命周期 |
| MCRL | 计算价值、预算、继续/停止/提问策略 | 不执行高权限操作 |
| Hyper-Speed | 执行已授权 DAG 并返回回执 | 不决定证据真值或授权 |
| Parser / LLM / Native Expression | 可插拔解析、教师、表达和对照基线 | 不把外部 LLM 能力计入结构内核成绩 |

## 2. 收敛后的唯一运行闭环

```
Observation
  -> Parse / Ground
  -> ZNCA + bounded TRLW
  -> Yixiang / XSL operators (optional, versioned)
  -> SROK local sparse composition
  -> CSG-GCR global coordination
  -> RSDN state update / inference
  -> E09 prediction commit and evidence reveal
  -> E12-A6 lifecycle transition
  -> ZPCM authoritative event append
  -> rebuildable projections / bounded retrieval
  -> CSL invalidation + MCRL budget decision
  -> Hyper-Speed authorized DAG execution
  -> Native expression or optional LLM adapter
  -> next Observation
```

不确定、拒绝、证据冲突、预算耗尽、截断、超时、重启恢复失败均须保留为显式状态，不得伪装为成功或确定答案。

## 3. 当前并行工程线与处理顺序

以下是 2026-11-12 仓库快照中的代表性开放 PR。状态会随 CI 和后续提交变化；合并前必须重新读取 GitHub 实时状态。

### A. 运行时持久化 / 内存有界（P0）

- #293：ZPCM paging 与 M2 lifecycle writer 的有界性问题。
- #303 / #346：ZPCM 事件索引、查询计划、按索引和 payload bytes 限制回放。
- #335 / #336 / #337：ZPCM streaming lifecycle replay、E12-A6 streaming restore、按需读取 payload。
- #341 / #342：删除重复 payload cache 和 full-ledger deep copy。
- #348 / #349 / #350 / #354 / #356：E12-A6 receipt metadata、restore RSS benchmark、projection contract、candidate/action history index。
- #326 / #340：M2 bounded SQLite projection 与语义单元生命周期投影。
- #345：M1 持久 manifest 和有界 chunk reads。

集成要求：memory_events 保持唯一事件权威；projection 需有 schema version、generation、high-water sequence、digest/checkpoint；重建必须 keyset-paged、事务原子、可回滚；候选 ID 与 action ID 必须分列索引。报告实际 RSS/high-water、事件数、payload bytes、启动/恢复延迟和查询计划。不能以逻辑内存池计数替代 OS RSS。

### B. E09 / E12-A6 安全隔离（P0）

- #282 / #274：Authority 与 Writer 的隔离、Adapter 迁移。
- #288 / #289 / #295–#297：IPC 合约、Linux UDS、Authority RPC、Verifier 只读证据快照。
- #301–#306：E12-A6 Writer RPC、SUPPORT feedback read、redacted learner replay、atomic verifier snapshot。
- #315：E09 到 E12-A6 UDS receipt E2E。
- #323 / #355：receipt reservation 与 Writer post-commit crash recovery。
- #327 / #331–#334：可信 Learner assignment、checkpoint read、RPC client / ZPCM role ports、Adapter lifecycle remote ports。

集成要求：身份从 kernel peer credentials / trusted workload registry 派生；Observation 的 learner ownership 不接受 caller-supplied ID；SUPPORT 与 replay 共用严格 lineage validator；Writer 单写者、receipt/nonce 原子消费、幂等回执、崩溃恢复和 anti-rollback 必须有故障注入证据。单进程 mock 不等于 OS 进程隔离。所有安全 PR 保持 Draft，直到父依赖、exact-head CI、跨进程 E2E 和 crash/restart 证据齐全。

### C. M1/M2 证据与语义 grounding（P1）

- #287 / #292 / #294：M1/M2、E09、Yixiang/SROK 的集成线；#294 是 validation-only，不作为代码合并依据。
- #299 / #305 / #309：Observation 到 SemanticUnitCandidate 的有界抽取、receipt 对 durable event 的验证、evidence-preserving grounding。
- #321 / #322 / #325：gold extraction dataset、leakage-safe split、immutable M1 byte span provenance。

集成要求：每个 SemanticUnit 必须回溯到不可变原始 bytes、source span/region、时间、模态和 receipt；gold annotation 必须校验真实 source span；数据切分按 source/group/world 隔离；解析器 confidence 不得冒充证据可信度。

### D. 认知结构学习与训练评估（P1）

- #339：首个可训练 CPG-EI MVP。
- #344：pairwise / third-order learnable gates。
- #347 / #352 / #359：N0.10 relation learner checkpoint、streaming JSONL、group-disjoint split、reiterable full-batch gradient accumulation。
- #360：rebased multi-seed structure discovery diagnostics（原 #353 已关闭未合并，由 #360 接续）。
- #351：training readiness / convergence gates。

集成要求：拆开 candidate generation、candidate scoring、structure selection、OOD transfer；固定数据版本、split provenance、seed、代码 SHA、超参和 evaluator；加入 label shuffle、feature permutation、pairwise-only、matched MLP/graph/tensor/Transformer baselines；记录 FDR、support precision/recall、参数量、FLOPs、延迟和 RSS。固定有限候选集上的门控学习不能宣称 open-ended relation discovery。

### E. 旧研究与可选算子线

- YJ / 高阶群与对称性研究、E13 主动查询、XSL/Yixiang/RSDN 等保留为可选研究能力。
- 仅通过版本化 OperatorSpec / narrow interface 接入；必须可禁用、可替换、可消融。
- 不允许把结构对称性直接解释为语义/因果，不允许把主动查询做成 MCRL 的第二套策略实现。

## 4. 训练准备度：当前判定

**判定：可启动受控的组件级训练与实验；不可宣称统一认知系统已准备好端到端联合训练。**

阻塞条件：

1. E12-A6 restore 和写入仍需证明不随事件历史在 Python 内存中线性增长。
2. M2 grounding / corpus loader / evaluation contract 尚需验证大规模流式数据和严格 group-disjoint split。
3. CPG-EI 当前 learnable gates 主要是在预先定义的有限候选集合中学习权重；尚未证明开放式关系发现。
4. N0.10 checkpoint resume 需绑定 code/data/config/optimizer fingerprints；改变任一语义后不能声称精确恢复。
5. 统一闭环缺少足够的跨进程、重启、故障注入和资源曲线证据。

允许开展：小规模、可复现、组件级训练；多种子诊断；负对照；matched baseline；严格留出 OOD 实验。

禁止宣称：生产可用、通用推理、开放式关系发现、百万上下文原生运行、非 Transformer 已胜过 Transformer、统一端到端训练已就绪。

## 5. 合并与发布门禁

每个 PR 合并前必须满足：

- 父 PR 已合并或变更已 rebase 到明确、稳定的集成祖先；禁止依赖未合并的隐式分支链。
- exact-head push CI 和 PR CI 均成功；不能用旧 SHA 的成功结果覆盖新 SHA。
- 相关单测、协议测试、集成测试和回归测试均执行；测试范围与未执行范围写明。
- 跨模块接口 schema 有版本，兼容性与迁移路径明确。
- 持久化变更有旧 schema 读取、升级、回滚和 rebuild 测试。
- 安全变更有拒绝路径、跨身份隔离、崩溃/重放/重复请求测试。
- 性能变更提供 before/after 数据、数据规模、机器、测量方法和误差范围。
- Draft / validation-only / research-only PR 不因 mergeable=true 自动转为 Ready。
- main 只接收独立、可回滚、已验证的切片；不直接合并几千行堆叠总分支。

## 6. 最终集成顺序

1. 冻结 main；记录基线 SHA 和全量测试结果。
2. 选定唯一 integration branch；从 main 最新提交创建，不从任意深层 feature branch 继承全部历史。
3. 先集成 ZPCM bounded event read / replay，再集成 E12-A6 projection / streaming restore / crash recovery。
4. 再集成 E09 Authority / UDS / Writer / Verifier，确保身份、receipt、lineage 与事件写入闭环。
5. 集成 M1 immutable evidence manifest 与 M2 bounded grounding / TRLW。
6. 集成 SROK / CSG-GCR / Yixiang / RSDN 的单一 runtime adapter。
7. 集成 N0.10 checkpoint + streaming loader + group-disjoint split，并跑 matched baselines。
8. 最后集成可选 Hyper-Speed、CSL、MCRL、Native Expression 和移动端资源优化。
9. 全量回归、端到端、故障注入、OOD、消融和资源测量通过后，才发布一个经过审计的集成 PR。

## 7. 收尾清单与 Definition of Done

| 范围 | Done 条件 | 当前状态 |
|---|---|---|
| 架构所有权 | 每个责任唯一 owner，无重复账本/状态机/调度器 | 设计已定义，代码映射仍需逐文件核验 |
| ZPCM | 单一事件源、bounded paging、digest 验证、可重建投影 | 多个 PR 分段实现，尚未收敛到一个集成 head |
| E12-A6 | bounded restore/write、candidate/action 正确索引、crash recovery | 多个 PR 分段实现，未完成端到端收敛 |
| E09 | trusted identity、lineage-safe learner reads、UDS isolation、receipt replay safety | 多个 Draft PR，尚未证明生产隔离 |
| M1/M2 | immutable source spans、bounded streaming、grounding receipts、leakage-safe data | 多个 Draft PR / validation line |
| SROK/CSG-GCR | correctness oracle、budget/truncation、partial pruning、typed branch merge | 有切片测试，仍需统一 runtime head |
| CPG-EI | learnable gates、multi-seed、negative controls、matched baselines | 实验正在推进，不是开放式学习结论 |
| N0.10 | checkpoint fingerprint、streaming loader、group-disjoint OOD、resume equivalence | 组件分支存在，exact-head 与集成仍进行中 |
| Native expression | 不依赖外部 LLM 的可运行表达器及对照 | 未证明 |
| 设备与 KV 独立性 | OS RSS / latency / restart 曲线；K0/K1/K2 分开验收 | 未证明 |

## 8. 执行原则

- 并行开发可以加速独立模块；共享接口、同一文件、同一 schema 的写入必须串行化。
- 先批量审计、再分组提交；避免为了“高速”制造重复实现和难以回滚的分支拓扑。
- 每轮只更新可证明的事实：commit SHA、测试命令、CI run、数据规模、性能数据。
- 当测试失败时，先定位最小失败集，修复后重跑 exact head；不得把失败测试改成更宽松的预期来掩盖实现问题。
- 不以 PR 数量、代码行数或 CI 数量作为架构成熟度指标。


## 9. Exact-head CI snapshot (2026-11-12)

The following results were checked against GitHub Actions run records. They are branch-local evidence only; successful jobs do not imply the PRs have been merged or that their parent branches are integrated.

| Workstream | Exact head | Observed result | Scope boundary |
|---|---|---|---|
| E09 trusted learner binding (#327) | `591507b6d5cdd502d0e21d180099bb81945a8157` | push + PR unit-test workflows succeeded | Does not prove cross-process OS isolation or full E01/E02 acceptance |
| N0.10 checkpoint integration (#347) | `dc6af2540ea9459d927ff212ace07055f0fbbe6e` | exact-head checkpoint-integration + tests succeeded | Component/integration branch only; parent benchmark branch is not merged |
| N0.10 streaming manifest guards (#352) | `3977ee14456c5c0b55832c0d806b58ff1fdd80ae` | checkpoint-integration succeeded | Must retain group-disjoint and data fingerprint guarantees |
| N0.10 reiterable full-batch gradient (#359) | `e6b7b176494a951252fdfa2a732ba3c6b5e18381` | exact-head push + PR CI succeeded (run #43200865402 / #43200874953); 21 tests | Full-batch equivalence plus same-count content/order drift rejection; runner still materializes split rows, so end-to-end out-of-core training remains incomplete |
| CPG-EI learnable gates (#344) | `03b3b14d28842763b0f3fef76f683d1cc5643ca6` | push + PR unit-test workflows succeeded | Finite predefined candidate universe; not open-world discovery |
| CPG-EI multi-seed diagnostics (#360; replaces closed #353) | `0dc9c0a664485aac8f4e432a927dce07b47b034b` | exact-head diagnostic workflow succeeded (run #43201228903) | 10 seeds: mean bit accuracy 0.92344, support recall 0.58333, exact 6-edge recovery 0/10, 8 false discoveries; finite synthetic universe only |
| CPG-EI second teacher family (#362; supersedes closed stale #361) | `6cef996d9394aae021359c26868c0a650b98543d` | exact-head diagnostic workflow succeeded (run #43201905650; 7 tests) | GF(2) parity: mean bit accuracy 0.63368, support recall 0.30556, precision 1.0, exact 12-edge recovery 0/3; exact-support oracle 100% bit/state accuracy. Greedy discovery limitation, not representational impossibility |
| Training readiness gates (#351) | `e8edf9bfa1eb77ca398a10f904164528fb1b13cb` | PR unit-test workflow succeeded | Specification/tests; not an end-to-end training certification |
| E12-A6 indexed lifecycle projection (#350) | `a4c7bb35888f02e693dda728dfc8ba4926bb6d28` | tests + RSS benchmark workflows succeeded | Benchmark evidence is environment-specific; restore architecture still needs integration |
| M2 paged TRLW/Yixiang/CSG integration (#294 validation / #292 stack) | `52baa8f0d2f4703544b15c941ac1c56b3e6ecba5` | research-branch validation + tests succeeded | #294 is validation-only; no code merge implied |
| This convergence baseline (#358) | `21414401faec9820bc24a463c0cd73d59624579e` | exact-head PR unit-test workflow succeeded (run #43195657234) | Documentation-only change; any subsequent documentation commit must receive its own exact-head CI |



### Latest research interpretation (2026-11-12 17:53 +08:00)

- CPG-EI's original sparse random-logit teacher remains prediction-stable but does **not** recover the planted six-edge topology in any seed (0/10 exact recovery; mean support recall 0.58333; eight false discoveries). The independent GF(2) parity teacher is harder: mean bit accuracy 0.63368, support recall 0.30556, precision 1.0 and exact recovery 0/3. An exact 12-edge support oracle reaches 100% bit and exact-state accuracy, proving the current feature basis can represent the teacher while the greedy residual-correlation proposal method fails to discover its complete support. Under independent uniform bits, parity's pairwise conjunction terms have zero marginal covariance with the target; the next experiment should test joint/conditional feature proposals and bounded subset search with matched-compute controls.
- N0.10 now has a tested reiterable full-batch learner primitive with numerical equivalence to materialized training. The experiment runner still materializes split rows, so the next memory milestone is a file-backed/reopenable dataset stream through the complete runner, not another learner-only optimization.
- PR #353 was closed without merge after its branch became stale; PR #360 is the rebased active replacement. PR #361 was closed without merge after its base moved; PR #362 is the clean rebased second-teacher extension. Keep superseded PR runs as historical evidence only.

A failed earlier run on an older SHA is not evidence that the current exact head fails; conversely, an older successful SHA cannot certify a newer head. The table deliberately reports only observed exact-head outcomes and their scope limits.


### Second teacher family exact-head result (2026-11-12 18:39 +08:00)

- PR #362 head `6cef996d9394aae021359c26868c0a650b98543d`, run #43201905650: success; 7 tests.
- Three GF(2) parity seeds: mean validation bit accuracy 0.6336806; mean support recall 0.3055556; mean support precision 1.0; false discoveries 0; exact 12-edge support recovery 0/3.
- Exact-support oracle: bit accuracy 1.0 and exact-state accuracy 1.0 with the known 12-edge polynomial.
- Interpretation: the feature basis is expressive enough, but the current residual-driven greedy proposal path is not structurally identifiable on this teacher. This is a concrete failure mode to address with joint/conditional proposal search, not a reason to increase epochs or relax pruning without preregistered controls.


### Candidate-score normalization result (2026-11-12)

- PR #360 exact-head `0dc9c0a664485aac8f4e432a927dce07b47b034b`, workflow run #43201228903: success; 5 tests.
- Paired five-seed raw vs residual-norm-normalized scoring: mean support recall 0.5667 vs 0.4667; exact six-edge recovery 0/5 for both; mean false discoveries 0.8 for both. Per-seed validation bit accuracy was unchanged.
- Decision: raw scoring remains the default. Normalization reduced active edges but also reduced recall, with no exact-recovery or false-discovery improvement. Keep normalized scoring as an explicit ablation only; do not present it as a structural-discovery fix.


### Bounded joint-motif proposal result (2026-11-12)

- PR #363 head `a036e4c7a70da02c68b429db04ec55be89bc97ed`, workflow run #43210009367: success; 8 tests.
- The new proposal operator searches a bounded universe of 20 four-edge motifs (three pairwise conjunctions plus the corresponding third-order edge). On two GF(2) parity seeds, it selected one motif and recovered 4/12 planted edges per seed (support recall 0.3333, precision 1.0).
- This is preliminary evidence that joint proposals can recover a synergistic motif missed by marginal residual scoring. It is not yet a matched-compute comparison, full-support recovery, or open-ended discovery result. Next validation: compare joint and greedy proposals on identical seeds/data/splits and report cost, recall, false discoveries, and exact support.


### N0.10 file-backed runner exact-head result (2026-11-12)

- PR #364 head `e51d0d7b46c63de0b3ad54d51f6a7eab3dafd8b1`, push + PR workflows #43211118291 / #43211108372: both succeeded; 13 tests each.
- The opt-in `prototype/n010_streaming_runner.py` performs JSONL preflight with disk-backed SQLite uniqueness/group indexes, compact split fingerprints, reiterable full-batch training, streaming aggregate-only dev/locked-test evaluation, and atomic checkpoint replacement.
- Tests establish numerical equivalence with the materialized runner on the fixture, resume equivalence, group-leakage rejection, and compact manifest behavior.
- Scope boundary: this is Python-level row-streaming evidence, not an OS RSS guarantee. Large-corpus peak RSS, throughput, and disk-index scaling must be benchmarked before claiming bounded-memory production readiness. The original `run_experiment` path still materializes split rows; #364 adds a separate opt-in path.


### CPG-EI joint-vs-greedy matched-compute result (2026-11-12)

- PR #363 exact head `5f7b0933404cd7344e2aa41c86d308272d40ed9b`, workflow run #43211461122: success; 9 tests (203.58 s).
- On seed 11, joint motifs used 696 training passes vs greedy 700 (0.571% budget gap). Both recovered all 12 planted support edges; joint precision was 1.000 (12 active edges) vs greedy 0.923 (13 active edges).
- Important counter-signal: held-out validation bit accuracy was 0.5365 for joint vs 0.8229 for greedy. Thus support recovery on this synthetic seed did not translate to held-out predictive quality. Joint selection is promising as a structural proposal mechanism, but the current train-BCE selection is likely overfitting or otherwise misaligned with held-out generalization. Do not promote it as the default; next study should add multiple-seed matched-compute evaluation and separate structure metrics from predictive metrics.


### N0.10 isolated locked-test evaluator and cross-artifact group guard (2026-11-12)

- PR #365 exact head `25316bd14dd9c331eb7b3825e6e1e20b01090ca2`, workflow run #43213101734: success; 14 tests.
- PR #366 exact head `9299a9b54c8bc3fd5a5a800e14554cc98d914437`, workflow run #43213940381: success; 15 tests.
- #365 separates train/dev JSONL from the locked-test artifact and exposes a separate locked-test evaluator. It streams evaluation predictions directly to JSONL and uses a SQLite metadata-only index.
- #366 persists field-scoped SHA-256 fingerprints for declared group/source-group/episode IDs in a SQLite sidecar and rejects held-out group overlap with train/dev before locked-test prediction.
- Boundary: the guard can only enforce identifiers actually supplied by dataset producers. Missing source provenance cannot be inferred. The group sidecar must travel with the checkpoint. These tests establish logical isolation checks, not OS-level process sandboxing or measured RSS bounds.


### N0.10 subprocess RSS sweep (2026-11-12)

- PR #367 exact head `ebea32ea82193ba08e2e75de6d25086595c8f776`, workflow run #43214345607: success.
- Fresh-process measurements, one full-batch epoch, 100,000 train + 100,000 dev records at the largest point:

| Records per split | Total records | Peak RSS | Peak minus process baseline | Elapsed |
|---:|---:|---:|---:|---:|
| 1,000 | 2,000 | 25,032 KiB | 1,748 KiB | 0.147 s |
| 10,000 | 20,000 | 27,156 KiB | 5,112 KiB | 1.288 s |
| 100,000 | 200,000 | 27,172 KiB | 5,192 KiB | 13.095 s |

- In this synthetic fixture, increasing from 10k to 100k records per split added only 16 KiB to absolute peak RSS; 100x more rows than the 1k point added about 2.1 MiB to absolute peak RSS. This is encouraging evidence for the SQLite-indexed streaming path.
- Scope limitation: each row has only four small nodes, two-dimensional features, one epoch, and the benchmark is a single Ubuntu CI environment. It does not establish production memory bounds for large feature vectors, large per-row candidate pools, concurrent runs, or long training schedules. Continue measuring RSS and throughput on representative corpora.


### Exact-head refresh — N0.10 RSS and evaluator validation (2026-11-12 12:04Z)

- PR #365 advanced to `974d7ae9f3b3178e3bae5b5e708c3adc6d108925`; workflow run #43214491147 succeeded with 15 tests, including a subprocess RSS scaling test comparing 1,000 and 20,000 examples.
- PR #367 advanced to `fcd1d4ac0f0c5a83df76cc6c1e2dd5db7834b483`; workflow run #43214382087 succeeded. The fresh-process sweep reported:

| Records per split | Total | Peak RSS | Peak minus baseline | Elapsed |
|---:|---:|---:|---:|---:|
| 1,000 | 2,000 | 25,032 KiB | 1,680 KiB | 0.287 s |
| 10,000 | 20,000 | 27,292 KiB | 5,228 KiB | 2.748 s |
| 100,000 | 200,000 | 26,992 KiB | 4,908 KiB | 27.323 s |

- The 10k and 100k measurements are effectively flat in absolute peak RSS (~27 MiB), while row count increases 10x. Across 1k to 100k per split, peak RSS rises by about 1.9 MiB. This supports the streaming-memory hypothesis for this synthetic profile, but is not a universal upper bound.
- PR #366 remains the explicit held-out source-group overlap guard; PR #367 is stacked on it. These PRs are Draft and remain unmerged.
