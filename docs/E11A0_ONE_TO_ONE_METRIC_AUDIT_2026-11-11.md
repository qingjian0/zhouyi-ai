# E11-A0.1 独立补充审计：一对一匹配指标的空集与阈值问题

日期：2026-11-11  
审计对象：PR #44 head `7c70fc4047aeced3ed7e5188a1d390db5d272b70`  
状态：静态代码审计；未执行测试或 CI；不否定该 PR 对候选重复计分问题的修复

## 1. 摘要

PR #44 已正确推进一项关键修复：将同一候选重复匹配多个隐藏概念的问题改为候选扩展去重与一对一最大权匹配，并加入了针对候选复用和重复扩展的测试。这是对原 E11-A0 oracle metric 的实质改进。

但新指标仍有两个可能产生虚假概念发现的边界：

1. `_f1()` 将 predicted 与 actual 同为空集定义为 1.0；这会让一个在 Query 上什么都没预测出的空候选，与一个 Query 上没有正例的隐藏概念获得完美匹配。
2. 一对一匹配只要求 F1 大于 0；极低重叠候选也会计为一个“matched concept”，从而提高 `one_to_one_concept_recall` 与 `one_to_one_candidate_precision`，即使其预测质量几乎为零。

因此，PR #44 的一对一约束值得保留，但 matched count 指标需要更严格的可观测性和匹配门槛。

## 2. 发现

### F1. Empty-empty F1=1 会造成空候选被当作概念发现

现有 `_f1(predicted, actual)` 对两个集合都为空时返回 1.0。新 matcher 对每个 candidate extension 与 latent concept 的 query membership 计算该 F1。

若某个 latent concept 在 Query 中没有实例：
- `actual_by_latent[concept] == empty`；
- 任一在 Query 上没有预测对象的 candidate extension 也为空；
- 二者 F1=1.0；
- DP 会将该空候选与该隐藏概念匹配，并增加 matched count。

这不是有证据支持的概念发现，而是 Query 上没有可观测正例造成的空集一致。

**建议：**
- Query actual 为空的隐藏概念标记为 `UNOBSERVABLE_IN_QUERY`，不能进入正向匹配；
- 空预测与空真值的 F1 不作为成功匹配；
- 报告 query-observable concept count 与 total latent concept count；
- 将不可观测概念纳入覆盖率/拒答报告，而非静默从总体结论中消失。

### F2. F1>0 作为匹配条件过宽

当前 DP 跳过 `value <= 0`，但任意正重叠都可计为一次成功匹配。例如，候选只命中一个对象，而真实概念有数百个成员，只要 F1 非零，就会增加匹配数。

于是：
- `one_to_one_concept_recall` 不是达到质量标准的概念召回率；
- `one_to_one_candidate_precision` 不是达到质量标准的候选精确率；
- 这两个 count 指标可能与实际 F1 质量脱节。

**建议：**
- 预注册一个匹配阈值 `tau`，只有 F1 >= tau 才可计为有效匹配；
- 不只报告单一阈值，另报告阈值—precision/recall 曲线；
- 阈值只能在 development seeds 上确定，在 locked seeds 上冻结；
- 同时保留最大权匹配平均 F1，避免阈值指标掩盖质量差异。

### F3. 空候选与无候选的 precision 约定需要显式说明

当 unique candidate extension count 为 0 时，当前 precision 返回 1.0。对于“没有提出任何候选”的学习器，将 precision 记为完美并不直观。

建议报告：
- candidate_count=0；
- precision=null / undefined；
- concept_recall=0（若存在可观测目标概念）；
- abstention rate=100%。

若项目选择其他 convention，必须在协议中预注册，并同时报告分母。

### F4. 一对一 DP 还需要预算与规模报告

隐藏概念数量上限 16 控制了 bitmask 维度，但候选扩展数仍可能很大。应报告：
- 原始候选数；
- 去重后 extension 数；
- DP 状态/转移数；
- 运行时间与峰值内存；
- 超出预算时的明确 PARTIAL / ABSTAIN 行为。

## 3. 最小修订建议

1. 新增 Query 空概念测试：空 extension 不得与 Query 无正例概念获得成功发现 credit。
2. 新增低重叠测试：F1 小于冻结阈值时不计入 matched count。
3. 新增零候选测试：precision 不得静默显示为 1.0 而不说明 undefined convention。
4. 对 observable/unobservable concepts 分开报告。
5. 在 locked multi-seed confirmation 前冻结阈值与匹配策略。

## 4. 结论边界

PR #44 的一对一匹配解决了“一个候选被重复计入多个概念”的主要问题；它尚未证明学习器能自行识别候选语义，也尚未证明概念边界可靠。

在空集处理和匹配阈值修正前，建议把 `one_to_one_concept_recall` / `one_to_one_candidate_precision` 称为 preliminary matching-count diagnostics，而不是正式概念发现 precision/recall。

## 5. 协作边界

本 PR 只增加独立审计文档：
- 不修改 PR #44 的代码或测试；
- 不修改 E11 原分支、E10、E09、E02 或 main；
- 不运行、取消或重跑其他 AI 的 CI；
- 由 PR #44 作者决定是否采纳修订。
