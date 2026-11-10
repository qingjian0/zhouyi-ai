# E12-A7 原型实现与 E12-A6 集成缺口审计

日期：2026-11-11  
分支：research/e12a7-orthogonal-lifecycle-prototype-2026-11-11  
状态：最小原型已提交；CI 状态待确认；未宣称测试通过。

## 1. 本轮检查的既有实现

检查基线：`research/e12a6-identifiability-audit-2026-11-11`

- `prototype/e12a6_lifecycle_contract.py`
- `prototype/e12a6_e02_lifecycle_runner.py`
- `tests/test_e12a6_lifecycle_contract.py`
- `tests/test_e12a6_e02_lifecycle_runner.py`

### 已有能力

1. Candidate、Evidence、Action 使用 frozen dataclass。
2. 有显式 workflow transition map。
3. 对 TRAIN、GATE_FINAL、LOCKED_TEST/POST_DEPLOY 的部分 split role 做了检查。
4. 通过 E02-D 27-rule 有限假设枚举测试机制可辨识性和 abstention。
5. A2 已有有限假设 expected information gain 选择器；A3 已有有界稀疏组合原型。

### 关键缺口

1. LifecycleLedger.apply 使用 `replace(current, state=...)` 更新当前候选状态；actions 虽被追加，但没有从不可变事件流确定性重建全部投影的 reducer。
2. CandidateState 是单一全局状态，没有按 scope_id 记录 epistemic status 和 scope status。
3. GATE_VALIDATE 检查证据 split role，但契约没有把候选的已提交预测与 evaluator 的独立判定绑定成不可伪造的验证记录。
4. E02-D runner 把 Gate-Final 的 gold outcome 放进与候选生命周期相同的 ledger。预测提交时间字段有记录，但 learner/evaluator 访问隔离尚未形成。
5. 现有 E02-D 生命周期测试只覆盖四类基本行为，尚未覆盖多 scope 冲突、确定性事件重放、隐藏标签 mutation noninterference。

## 2. 本轮新增的最小原型

- `prototype/e12a7_orthogonal_lifecycle.py`
- `tests/test_e12a7_orthogonal_lifecycle.py`

设计边界：
- CandidateVersion 不可变并按 candidate_id/version 区分。
- LifecycleEvent 追加式记录，带连续 sequence 和唯一 event_id。
- WorkflowStage、EpistemicStatus、ScopeStatus 分开存储。
- snapshot() 根据完整事件流重建投影。
- invocation policy 从 workflow、scope、epistemic 三个维度派生。
- 同一候选在 scope A 与 scope B 可以拥有不同证据状态。
- scope B 的局部 challenge 不会自动废弃 scope A；受挑战范围 abstain，未受影响的已支持范围降级为 ALLOW_WITH_WARNING。
- Gate validated 但没有 scope-specific support 证据时仍然 abstain。

这只是单进程 Python contract prototype。事件尚未持久化到数据库或文件，未实现哈希链、并发写入控制、完整 evaluator service boundary，也没有接入 E12-A1/A2/A3/A5 提议器。

## 3. 新增测试覆盖

测试文件针对：
- 三维条件共同满足后才允许调用；
- 未知范围必须 abstain；
- 跨 scope 反例隔离；
- 局部 challenge 不影响其他已支持范围；
- Gate 状态不能单独授权调用；
- 非法/过期 workflow transition 拒绝；
- SUPPORTED 必须绑定 evidence IDs；
- 重复 event_id 与非连续 sequence 拒绝；
- replay 投影确定性；
- CandidateVersion 不可变与版本隔离。

## 4. CI 变更

`.github/workflows/tests.yml` 已把本分支加入 push / pull_request 触发分支，并增加 E12-A7 focused unit test step。

CI 结果必须以 GitHub Actions 实际运行状态为准。本文件创建时没有测试通过声明。

## 5. 下一轮必须完成的安全边界

### 5.1 Evaluator firewall

Learner 只接收 observation、合法 measurement result、公开 split metadata。Evaluator gold labels 保留在单独对象/进程中。预测必须先提交并冻结，再由 evaluator 产生只读判定记录。Learner 不得查询 gold label。

Mutation test：
- 固定 learner 可见输入，仅改变 evaluator hidden labels；
- learner 的候选、动作和预测 trace 必须逐字节相同；
- 只允许 evaluator score 变化。

### 5.2 证据语义

区分：
- 机制可辨识；
- 当前 query 的预测可辨识；
- 当前范围内的经验支持；
- 因果识别。

不能把唯一 support-consistent hypothesis 等同于一般意义的因果发现。

### 5.3 组合与主动测量

先将 A2 measurement decision 接入 event ledger，明确 SELECT / NO_DISCRIMINATING_MEASUREMENT / BUDGET_EXHAUSTED / INVALID_INPUT。随后将 A3 composition output 作为候选 proposal，必须保留 parent version lineage 和独立验证。

## 6. 本轮结论

E12-A7 已从设计文档推进到独立的 scope-aware lifecycle contract prototype。它解决了单一全局状态导致的范围污染问题，但尚未解决真正的 learner/evaluator 隔离，也未证明系统能够自主发现新原语。

下一阶段优先实现 evaluator firewall 和 mutation tests；在这之前，不得宣称完整生命周期认知内核已经成立。
