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


### CPG-EI second parity teacher cross-check (2026-11-12)

- PR #363 exact head `75b8994567d8b2b07d1d7fa8589706a2f47e75df`, workflow #43213671969: success; 9 tests.
- Distinct GF(2) three-input parity teacher, 3 seeds: mean support precision 1.000, mean support recall 0.3056, mean validation bit accuracy 0.6337, zero false discoveries, exact support recovery 0/3. An exact 12-edge oracle reaches 100% bit and exact-state accuracy, so the representational basis is sufficient for this synthetic teacher while current greedy discovery remains incomplete.
- Joint motif matched-compute comparison on seed 11 remains mixed: full support recall and precision 1.000 vs greedy precision 0.923, but held-out bit accuracy 0.5365 vs greedy 0.8229. Joint proposal stays experimental only.

### N0.10 source-provenance completeness guard (2026-11-12)

- PR #368 exact head `d52dd388286deca056ee85149967886f36b352aa`, workflow #43216139061: success; 16 tests.
- Every record must declare at least one of `group_id`, `source_group_id`, or `episode_id`; records with no source-group identity now fail closed instead of passing an empty overlap check.
- This strengthens the #366 cross-artifact isolation guard but still relies on producer-supplied identifiers being truthful and complete. It is not a provenance attestation system.


### Exact-head refresh — N0.10 provenance integrity and RSS (2026-11-12 12:20Z)

- PR #367 exact head `22f7ad698d489367f649d3465e75001e1c5f3bf7`, workflow #43216548648: success. Latest subprocess sweep (1 epoch):

| Records per split | Total | Peak RSS | Peak minus baseline | Elapsed |
|---:|---:|---:|---:|---:|
| 1,000 | 2,000 | 25,004 KiB | 1,708 KiB | 0.286 s |
| 10,000 | 20,000 | 27,228 KiB | 5,128 KiB | 2.669 s |
| 100,000 | 200,000 | 27,208 KiB | 5,060 KiB | 27.520 s |

- On this synthetic profile, peak RSS remains approximately 25–27 MiB while records per split increase 100x. This is encouraging scaling evidence, not a hard memory bound; per-row payload size, candidate fan-out, concurrency, and long schedules remain untested.
- PR #368 exact head `d52dd388286deca056ee85149967886f36b352aa`, workflow #43216139061: success; 16 tests. Every record now must carry at least one declared grouping identifier, preventing an empty provenance row from passing the overlap guard.
- PR #369 exact head `3ffcee62937601066cf0440681406e7a11964e12`, workflow #43216816823: success; 17 tests. The persisted SQLite group-index sidecar is SHA-256-bound into the checkpoint and verified before resume and locked-test evaluation; tampering is rejected.
- PR #363 documentation/diagnostic exact head `176490351d4a3c5c62745f87834ce9ef48cde2b3`, workflow #43216313983: success; 9 tests. Second parity teacher: precision 1.000, recall 0.3056, validation bit accuracy 0.6337, exact support recovery 0/3. Joint-vs-greedy remains mixed (full support recall for both, but validation bit accuracy 0.5365 vs 0.8229); joint proposals remain experimental.
- PR #358 exact head `20b28bb3b3857fd68ca5c01f71abf07f0f569765`, workflow #43216324086: success. All work remains Draft/unmerged; no stable branch was changed.


### Exact-head refresh — architecture and N0.10 index snapshot (2026-11-12 12:26Z)

- PR #358 exact head `456a4930fcc3def3f0f738bb3ece225c2a87f73b`, workflow #43217031925: success. Unit tests plus E01/E02 demonstrations, five-seed and 100-seed diagnostics completed.
- E02-B ternary mod-3 additive relation: five seeds (7–11), each with 900 train / 180 validation / 180 test examples and 350 epochs. Pairwise test accuracy mean 0.3333 (SD 0); third-order test accuracy mean 1.0000 (SD 0); validation-gated third-order test accuracy mean 1.0000 (SD 0). Important limitation: only nine query values are repeated across train/validation/test; this is a controlled representational/optimization result, not unseen-symbol or unseen-rule-family generalization. Synthetic task only; no natural-language parsing, dynamic hypergraph learning, or Transformer/diffusion comparison.
- E02-D Z3 affine rule-family support sweep: 100 seeds. All-episode accuracy is 0 at support size 1, 0.1296 at size 2, 0.8704 at size 3, and 1.0000 at sizes 4–8; conditional accuracy when identified is 1.0000 for support sizes 2–8. This measures support-consistency identifiability/coverage, not neural model accuracy.
- PR #371 exact head `4e3e07d4e5092efba985bd81d24ae91ee8ad2615`, workflows #43217632211 and #43217603763: both succeeded. Adds a post-index SHA-256 recheck so the JSONL bytes must match the initial digest after SQLite metadata indexing; a deterministic regression test simulates a mid-build digest change. This closes the ordinary file-mutation window, but is not a filesystem snapshot against a hostile writer changing and restoring bytes between checks.
- #371 remains Draft, stacked on #369. No PR was merged into `main`.


### N0.10 million-scale RSS confirmation (2026-11-12 12:28Z)

- PR #367 exact head `7a0d937f8c14f833921651309309159a8ba30439`, workflow #43217463370: success. The sweep now includes 1,000, 10,000, 100,000, and 1,000,000 records per split (2,000,000 total at the largest point).
- Measured peak RSS: 25,088 KiB / 27,220 KiB / 27,176 KiB / 27,380 KiB respectively. Peak-minus-baseline: 1,772 / 5,144 / 5,060 / 5,120 KiB. Elapsed: 0.195 / 1.815 / 18.702 / 187.581 seconds.
- This is positive evidence that the current small-record, two-candidate-per-role synthetic profile scales to two million rows without a proportional RSS increase. It is not a universal constant-memory claim: record size, candidate fan-out, feature dimensionality, concurrent workers, storage throughput, and larger per-example assignment spaces remain untested.


### Exact-head refresh — E12-A6 projection foundation and million-scale N0.10 (2026-11-12 12:29Z)

- PR #370 exact head `dc49e69ac604787d7ff6e90ccbd37ef13e4cad72`, workflow #43217782060: success. Adds normalized SQLite current-state projections for candidate versions, evidence, and actions. SQLite triggers update the derived projections in the same transaction as lifecycle event appends; normal startup performs only a one-time historical backfill, with an explicit repair method.
- Important E12-A6 boundary: `PersistentLifecycleLedger._restore()` still reconstructs the full in-memory `LifecycleLedger`, and `ledger` still exposes a deep-copied materialization. The new projection is a foundation for lazy SQL-backed validation, not yet bounded-memory restore.
- PR #367 exact head `7a0d937f8c14f833921651309309159a8ba30439`, workflow #43217463370: success. One million records per split (two million total) streamed in 187.581 seconds at 27,380 KiB peak RSS in the synthetic Linux CI fixture.
- PR #358 exact head `0f6ea1f25e10f6a7540dd9f280b3c70ce5cd279c`, workflow #43217815409: success. Full unit tests and E01/E02 validation stages passed.
- All cited changes remain Draft/unmerged. No stable branch was changed.


### Exact-head refresh — million-row streaming and checkpoint semantics (2026-11-12 13:54Z)

- PR #367 exact head `7a0d937f8c14f833921651309309159a8ba30439`, workflow #43217463370: success. Expanded subprocess RSS sweep to 1,000,000 records per split (2,000,000 total), 1 epoch. Measurements: 1k/split peak 25,088 KiB (0.195 s); 10k/split 27,220 KiB (1.815 s); 100k/split 27,176 KiB (18.702 s); 1m/split 27,380 KiB (187.581 s). The 1m/split run streamed 1,000,000 dev rows; peak RSS was about 26.7 MiB. This is strong evidence of near-flat RSS for this exact synthetic row shape and serial 1-epoch workload, not a universal bound. Payload size is fixed/small, candidate fan-out is fixed at 2 per role, and no concurrent workers or long multi-epoch run were measured.
- PR #358 exact head `d5f06a192ad4e0633fecc53abc995759e1dd2998`, workflow #43218525308: success. This is the current architecture-doc PR head at this refresh.
- PR #371 was extended with checkpoint implementation fingerprints: SHA-256 of `prototype/n010_ooc.py` and the imported `LearnableSROK` implementation are persisted and checked on resume and before locked-test evaluation. A regression test corrupts the fingerprint and requires both paths to fail closed. Exact head `8565fdf49b749761e532f8f37e136937ff02db45`; workflows #43231692763 and #43231673908: both succeeded; 19 N0.10 tests passed. The implementation fingerprint is checked both on resume and before locked-test evaluation.
- Checkpoint semantics note: this implementation uses stateless SGD updates, so there is no momentum/Adam accumulator to persist today. If optimizer state is introduced later, it must be included in the checkpoint and fingerprinted before claiming exact resume equivalence.


- PR #358 exact head `fd111d0ae89e335cc72470c468bd3d5169b1a839`, workflow #43231791503: architecture-baseline update is undergoing its exact-head full test workflow; final result must be refreshed after completion.


### Exact-head refresh — CPG-EI selection protocol, bounded search, and E12-A6 replay state (2026-11-12 16:58Z)

#### CPG-EI candidate selection isolation

- PR #384 exact head `a87436d2068cce94257fcd99948d85848d9669ce`, full workflow #43263017253: success. The joint-motif routine now separates model fitting (train), candidate ranking (proposal-selection), and final locked evaluation (validation).
- Exact call-boundary regression instruments both `train()` and BCE: every fit uses only train rows; all baseline/candidate ranking calls use only proposal rows; train and locked-test diagnostics occur only after selection, with locked test last.
- The deterministic six-bit protocol partitions 64 possible inputs into 40 train / 12 proposal / 12 locked-test states. An alternate rule family is reported as a small diagnostic only; this is not statistically powered OOD evidence and does not prove general relation induction.
- Decision: this split is now the required protocol for future candidate-search comparisons. Legacy calls without `proposal_examples` remain exploratory because training data is also used for candidate ranking.

#### Exact-vs-beam search trade-off

- PR #382 exact head `003046c4ff01da9e872c773ea0374824b7a9f2b1`; push workflow #43263370449 and PR workflow #43263353057: both success.
- Five seeds × three candidate-pool sizes × ten beam widths = 150 comparisons. Reported Recall@5 0.7453, top-1 hit 0.7467, expanded-state ratio 0.8741, abstention 0.7000, complete-search rate 0.3000.
- The complete-search subset had Recall@5 and top-1 hit both 1.0000. This is a subset-conditioned result; it must not be substituted for overall recall. The high abstention rate is intentional under the fail-closed rule: incomplete/pruned searches do not claim a global optimum.
- Finite synthetic retrieval benchmark only; no natural-language grounding, learned-weight quality, distribution-shift robustness, or production latency claim.

#### E12-A6 disk-backed semantic replay state

- PR #385 introduces temporary SQLite-backed candidate/evidence/action-history/action-ID collections while preserving event-by-event semantic replay and validation. `.ledger` and `snapshot()` remain explicit full-materialization boundaries; `close()` and context-manager exit now remove the scratch database deterministically.
- Benchmark run #43263891152 on runtime HEAD `d703bcfacea87fca76fa55f266258ae2167a0a59` succeeded. Against the prior in-memory restore baseline from PR #349:
  - 1K events: 25.09 MB → 26.09 MB (about 1 MB fixed overhead).
  - 10K events: 34.17 MB → 28.68 MB (about 16.1% lower).
  - 50K events: 70.69 MB → 28.70 MB (about 59.4% lower).
  - 50K peak RSS: approximately 70.58 MB → 28.62 MB.
- These are observed Linux/Python 3.11.18 results, not a hard memory guarantee. The benchmark was subsequently extended to 100K and 500K events; exact latest-head run #43264128876 is pending. Full validation on latest PR #385 head `00ba6a48fad8967afc2af7367a992a9e78c82e05` is also pending at this refresh.
- Architectural boundary: event log remains authoritative; no projection-only startup shortcut is approved. This change moves the accumulated semantic state to disk but does not yet eliminate full-history replay CPU cost. Startup latency, 100K/500K RSS, disk-full, abrupt process death, concurrent adapters, and stale scratch-file cleanup remain acceptance gates.

#### Additional exact-head updates

- PR #379 E09/ZPCM crash-replay exact head `423c53a6b90bb71bfe97fbe9d6f08114d4b71057`: both full CI workflows #43253292643 and #43253306110 succeeded, including fail-closed replay after projection uncertainty.
- PR #381 execution snapshot head `1126a644e26458610ae8d867056551cfe5e819c0`: workflow #43253222365 succeeded.
- PR #383 N0.10 search-strategy propagation head `1d361399f4f9c6ec6564621fd1398728fe2a157a`: focused and full validation succeeded. Dev and locked-test evaluation now receive the configured search strategy and beam width; checkpoint resume rejects incompatible settings.

#### Current readiness decision

- Component-level controlled training and synthetic research experiments remain permitted.
- Unified end-to-end joint training is **not yet approved**. CPG-EI structure recovery and predictive generalization can diverge; E12-A6 startup cost and failure-mode acceptance remain open; N0.10's streaming evidence is specific to its measured row shape and execution profile.
- The next gates are: finish the 100K/500K E12-A6 RSS sweep; complete latest-head semantic CI; measure startup latency and write/query overhead; stress temp-state cleanup and disk-full/crash recovery; and run multi-seed CPG-EI candidate-selection studies with structure metrics, locked predictive metrics, and OOD results reported separately.
- `main` remains unchanged. All active work stays in Draft research stacks until exact-head evidence and dependency-chain review are complete.

### Exact-head refresh — 500K E12-A6 replay and CPG-EI selection ablation (2026-11-12 17:22Z)

#### E12-A6 memory/latency trade-off after batched replay

- PR #385 current code head `52f0a04d328937f491e0a9282b7a178748a61854`; full unit/E01/E02 workflow #43267236730 succeeded. The startup replay now stages all scratch SQLite writes in one transaction.
- PR #390 provides the in-memory baseline at 1K/10K/50K/100K/500K. PR #385's batched disk-backed replay benchmark #43267209703 also completed successfully.
- At 500K events: in-memory restore RSS 472.32 MB / 11.71 s; batched SQLite scratch restore RSS 28.54 MB / 28.17 s. This is about 94% lower RSS but 2.4× slower startup than in-memory. The first unbatched scratch implementation took 102.80 s; the bulk transaction improved it by 3.65×.
- At 10K–500K, observed scratch-state RSS remains around 28.5 MB. The 500K fixture is about 945 MB on disk; storage is not bounded. The benchmark is a synthetic candidate-registration-only history, not a production workload model.
- Decision: retain the disk-backed design as a memory-bounded research direction, but do not claim a speedup. Next performance work should consider a verified checkpoint/snapshot that can resume from a trusted event-log anchor, without replacing the event log as authority or skipping semantic validation.

#### CPG-EI proposal-selection ablation

- PR #388 introduces five seeds × three synthetic six-bit rule families, with disjoint 40 train / 12 proposal / 12 locked-test partitions and both 12- and 120-epoch candidate fits. Exact-head multi-budget artifact #43266823550 completed successfully.
- At 12 epochs, proposal-split selection selected no motifs in 15 experiments; legacy train-ranked selected all three motifs and recovered exact support in 12/15. At 120 epochs, proposal-split selected motifs in 3/15 (all three exact), while legacy train-ranked recovered exact support in 15/15.
- Despite exact support recovery in 15/15 legacy train-ranked experiments at 120 epochs, mean locked-test bit accuracy was only 43.33%, below the 50% bitwise chance baseline; alternate-family accuracy was 50.37%. Proposal split at 120 epochs had 32.59% locked accuracy and 49.44% alternate-family accuracy.
- The result separates three concerns: support discovery, candidate selection coverage, and predictive generalization. Structure recovery is not sufficient for a useful predictor. The 12-state locked sets are small and these are synthetic finite-state diagnostics only.
- A known-support oracle control and a precision metric correction for empty candidate sets are now added in PR #388; latest exact-head benchmark and full tests are pending.

#### Current training readiness

- Controlled component training and synthetic experiments may continue, but unified end-to-end joint training remains **not approved**.
- E12-A6 now has a large measured memory reduction but still a 2.4× startup latency penalty at 500K. A verified checkpoint design is the next architectural candidate, subject to event-log anchoring and corruption fallback.
- CPG-EI's structural support results are promising only under train-ranked selection; independent proposal ranking has low coverage, and prediction remains weak even with exact support. The oracle control must isolate optimizer/model limits before architecture changes.
- Keep all branches Draft and stacked; no changes to `main`. Do not merge until the exact-head oracle result, checkpoint threat model, write/query overhead, and failure-mode tests are reviewed.

### Latest evidence refresh — 2026-11-12 17:27Z (supersedes earlier status rows where they conflict)

#### E09 / E12-A6 exact-head status

- PR #379 E09 → ZPCM crash replay exact head `423c53a6b90bb71bfe97fbe9d6f08114d4b71057`: both workflows #43253292643 and #43253306110 succeeded. The new fail-closed replay assertion passed.
- PR #385 SQLite-backed E12-A6 replay state: bulk startup scratch transaction and fail-closed recovery passed full validation at HEAD `52f0a04d328937f491e0a9282b7a178748a61854` (workflow #43267236730). At 500K synthetic candidate events, batched scratch replay used 28.54 MB post-restore RSS and 28.17 s; in-memory baseline PR #390 used 472.32 MB and 11.71 s. This is ~94% lower RSS but ~2.4× slower. The first unbatched scratch version took 102.80 s; bulk transaction improved it 3.65×.
- PR #385 is currently testing an 8 MiB SQLite page cache against the prior 2 MiB setting. Exact benchmark #43268777016 is running and full validation #43268776886 is queued. Do not assume 8 MiB is better until the artifact is compared.
- PR #390 in-memory baseline exact workflow #43265737771 and full validation #43265737912 succeeded. Its 500K restore baseline was 11.708 s / 472.32 MB.
- This benchmark is candidate-registration-only. It establishes the scratch state memory/latency trade-off for that row shape, not a universal production guarantee. `ledger` and `snapshot()` remain explicit full-materialization boundaries.

#### CPG-EI: candidate selection and prediction are separate gates

- PR #384 exact head `a87436d2068cce94257fcd99948d85848d9669ce` passed full CI #43263017253. The implementation now fits on train, ranks on a disjoint proposal split, and evaluates locked test only after selection; tests instrument actual train/BCE call boundaries.
- PR #388 paired five-seed × three-family benchmark uses disjoint 40 train / 12 proposal / 12 locked-test states. At 120 epochs, legacy train-ranked selection recovered exact support in 15/15 experiments, but mean locked bit accuracy was only 43.33% and alternate-family accuracy 50.37%. Proposal-split selection selected a motif in 3/15 experiments (all three exact), with 20% support recall and 32.59% locked accuracy.
- Known-support oracle at 40 train / 12 locked reached only 33.89% locked accuracy at 12 epochs and 37.41% at 120 epochs. This is a different low-data six-bit parity regime from earlier 1024/256 synthetic oracle runs that achieved 100%; the two results are not contradictory, but the regime distinction must be preserved.
- Latest PR #388 adds training-set oracle accuracy and a full-64-state oracle fit to distinguish underfitting/overfitting from representation capacity. Latest exact-head benchmark and full suite are pending. Do not claim the CPG-EI predictor is ready.
- Metric correction: support precision is undefined when no edge is selected; report null/N/A and keep support recall at zero rather than assigning precision zero to an empty prediction set.

#### Bounded search

- PR #382 exact-head 150-comparison sweep passed both push/PR full workflows (#43263370449 / #43263353057). Overall Recall@5 0.7453, top-1 hit 0.7467, expansion ratio 0.8741, abstention 0.70, complete-search rate 0.30. Complete-search subset had 1.0 recall/top-1; do not present this subset-conditioned score as overall recall.
- The 70% abstention rate is a deliberate fail-closed consequence, not a retrieval failure to be hidden. Incomplete/pruned search does not claim a global optimum.

#### Training readiness decision

- Component-level training and synthetic experiments may continue. Unified end-to-end joint training remains **not approved**.
- The CPG-EI known-support oracle has not yet shown robust prediction in the 40/12/12 parity regime; exact support discovery does not imply predictive capability.
- E12-A6 now has strong measured memory reduction but still a startup latency penalty at 500K. A verified checkpoint with event-log anchoring and corruption fallback is a candidate next design, not yet implemented or approved.
- N0.10's million-row streaming evidence remains specific to its synthetic repeated-row benchmark. It is not evidence of complex relation learning.
- Keep all research PRs Draft and stacked. `main` remains unchanged. Training-readiness requires unified data/checkpoint/trainer/evaluator, independent locked-test isolation, multi-rule OOD, crash recovery, and measured resource/latency acceptance.

### Repeated-run and optimizer-regime refresh — 2026-11-12 17:44Z

#### E12-A6 cache-size and latency repeatability

- The 2 MiB SQLite scratch cache was measured three times at 500K: 39.31 s, 21.94 s, and 22.32 s (median 22.32 s). RSS remained about 28.5 MB. The first run is a large outlier; report the range and median, not just the best run.
- The in-memory baseline repeated at 11.708 s and 11.674 s (median 11.69 s). The 2 MiB disk-backed design is therefore about 1.9× slower at 500K but uses about 94% less RSS.
- The 8 MiB cache was repeated twice at 40.98 s and 39.14 s (median 40.06 s) with about 35.5 MB RSS. It is slower and uses about 7 MB more RSS than the 2 MiB runs. The 2 MiB setting remains selected.
- Exact comparison artifacts are in PR #385 workflow #43269750265 (2 MiB attempts 1–3), PR #390 workflow #43265737771 (baseline attempts 1–2), and PR #385 workflow #43268777016 (8 MiB attempts 1–2).

#### CPG-EI 500-epoch known-support oracle

- PR #388's 500-epoch oracle under the current search-strength regularization (gate L1 1e-3, group L1 1e-3) measured mean training accuracy 88.94%, full-64-state in-sample accuracy 87.50%, locked accuracy 52.04%, and alternate-family accuracy 50.00% (workflow #43270467094).
- This barely clears the bitwise chance baseline on the 12-state locked set, while the full-state in-sample fit remains incomplete. The optimizer/regularization regime is still a likely bottleneck.
- A paired oracle ablation now compares the search-strength regularization with the model's default gate L1 1e-4 and group L1 0, both at 500 epochs. Exact-head benchmark/full tests are running on PR #388. Do not change candidate-search regularization until the oracle ablation is measured.

#### Current decision

- E12-A6: retain 2 MiB cache and bulk startup transaction. Memory reduction is strong; latency remains a measured penalty. The next high-value direction is a verified persistent checkpoint anchored to the authoritative ZPCM event log, with full replay fallback on invalid checkpoint.
- CPG-EI: do not scale candidate search yet. First finish regularization oracle and training-convergence diagnostics; keep structure discovery, locked prediction, and OOD as separate metrics.
- Unified training remains not approved. `main` remains unchanged; all work stays in Draft stacks.