# ZNCA N3-D：持久化反事实分支与补偿事件

日期：2026-11-11  
状态：研究原型；基于 N3-C SQLite 追加式事件流；未合并 main。

## 目标

N3-C 已能持久化并恢复已提交认知状态，但仍缺少“如果另一个解释成立会怎样”的隔离推演、候选晋升和历史纠错机制。N3-D 在同一事件流中加入稀疏反事实分支，不复制完整基础状态。

## 核心模型

- **Canonical state**：唯一已采纳状态，由 HypothesisCommitted、BranchPromoted、CommitCompensated 事件投影。
- **Branch**：记录 branch_id、hypothesis_id、创建时 canonical_revision 与 canonical_hash、证据引用和稀疏 delta。
- **Shared base**：分支只保存变化字段；基础状态通过版本/hash 引用，不复制一份完整状态。
- **Promotion**：只有分支仍基于当前 canonical revision/hash、具有非空 delta 和证据引用时才能晋升。晋升使用事件流 CAS；过期分支 fail closed。
- **Rejection**：追加 BranchRejected，不删除候选或证据历史。
- **Compensation**：追加 CommitCompensated，保存目标事件影响字段的恢复值/缺失标记。原事件保留。

## 事件类型

| Event | 改变 canonical state | 作用 |
|---|---:|---|
| BranchCreated | 否 | 建立分支并锚定 canonical revision/hash |
| BranchDeltaRecorded | 否 | 记录稀疏字段变化 |
| BranchRejected | 否 | 保留并否决分支 |
| BranchPromoted | 是 | 将通过门控的分支增量晋升 |
| CommitCompensated | 是 | 用新事件补偿历史提交 |

## 并发与纠错边界

1. 事件追加沿用 N3-C 的 expected-version CAS、transaction_id 幂等和哈希链。
2. 分支基于 canonical revision/hash，而不是 event stream sequence。这样创建另一个分支等元数据事件不会无意义地使所有分支过期。
3. 任一 canonical mutation 都会推进 canonical revision；旧分支不能直接晋升，必须重新评估。
4. 补偿只允许目标是 canonical mutation 的事件；若目标影响字段后来被改写，拒绝自动补偿，避免覆盖更新知识。
5. 补偿事件要求 reason 与 evidence refs；当前引用只是标识符，尚未验证外部证据对象真实性。
6. 当前是单机 SQLite 参考实现，不提供多设备分布式共识、并发多分支调度或真正的模型反事实推理。

## 手机内存与上下文成本

分支采用 sparse delta，内存/持久化成本近似 O(分支数 × 每分支改动字段数)，而不是 O(分支数 × 完整认知状态)。当前实现仍会在投影时顺序扫描事件流；后续需增加 canonical snapshot + sequence cursor，避免启动时全量重放。快照只能加速恢复，事件流仍是事实来源。

## 验证

新增测试覆盖：
- 分支不复制基础状态，delta 不影响 canonical state；
- 晋升成功与 stale branch 拒绝；
- 被否决分支持久保留；
- 补偿恢复旧值且保留原事件；
- 后续写入覆盖目标字段时拒绝危险补偿；
- 关闭并重开数据库后重建分支与 canonical projection；
- N3-C 的 recover() 能跳过分支元数据并应用晋升/补偿事件。

## 不声称的能力

N3-D 不是 Transformer 替代网络，不会自动产生真实世界反事实，也没有训练算法。它是可审计的认知状态分支与事务原语，为后续学习系统提供安全的候选比较和历史纠错底座。
