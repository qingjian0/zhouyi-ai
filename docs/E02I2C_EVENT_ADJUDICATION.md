# E02-I2-C：关系身份事件裁决协议（设计审查稿）

## 1. 研究问题

I2-A 建立身份/版本/谱系账本；I2-B 提供确定性候选匹配；I2-E 的隐藏身份基准暴露了一个核心边界：单窗口结构相似度不能独立决定关系身份事件。

同成员但规则签名变化时，观察结果可能对应原身份的 MODIFY、独立新身份的 CREATE，或证据不足的 ABSTAIN。匹配器不得把三者压缩成一个最高相似度身份。

本阶段目标是拆分候选匹配与事件裁决，建立有证据来源、有时序约束、可证伪的确定性事件裁决基线。

## 2. 输入契约

事件裁决器输入：
- 当前候选及其结构版本；
- 历史身份和版本账本；
- I2-B 匹配结果（包括 ABSTAIN 原因和候选竞争信息）；
- 按窗口、环境、样本分割保存的支持证据与反例；
- 观测机会质量（采样覆盖率、有效样本数、缺失原因）；
- 已验证的身份连续性证据或结构变化证据。

禁止输入：
- 隐藏 identity_id、hidden event type、generator transition plan；
- locked Test 标签；
- 由测试结果反向挑选的阈值；
- 仅凭类象相似度推断的身份继承。

每个证据包至少包含 evidence_id、sample_id、window、environment、split、polarity、source_version_id、member_role_projection、raw_observation_ref。支持与反例必须分别保存，不能将冲突证据平均成一个置信度。

## 3. 事件决策矩阵

| 事件 | 必要条件 | 禁止条件 | 账本效果 |
|---|---|---|---|
| KEEP | 身份连续性证据充分；结构签名不变；当前环境 Gate 通过 | 只有成员相似，没有独立证据 | 同身份、同版本，追加 KEEP |
| MODIFY | 有跨窗口连续性证据；结构差异被直接观测；变化后版本通过 Gate | 仅因最高匹配分数；新规则没有独立验证 | 同身份新增不可变版本 |
| CREATE | 候选独立成立；与现有身份的区分证据充分 | 匹配器弃权但没有新身份成立证据 | 创建全新身份和初始版本 |
| ABSTAIN | 身份连续性、修改或新建均无法区分 | 不允许强制选择最高分 | 不改变身份状态，记录弃权理由 |
| SUSPEND | 有足够观测机会，但连续缺少确认；超过预注册缺失门槛 | 数据缺失、采样覆盖不足、环境未观测 | 保留身份，进入 SUSPENDED |
| REACTIVATE | 先前为 SUSPENDED；有新窗口独立确认；身份连续性可追溯 | 只凭成员相似；终态身份复活 | 恢复原身份；必要时再创建新版本 |
| REPLACE | 新关系成立且与旧身份不连续；旧身份终止证据充分 | 把旧身份支持证据直接继承给新身份 | 旧身份终止，新身份创建，记录 REPLACED_BY |
| RETIRE | 有重复、独立、强反例；采样机会充分；不再有支持证据 | 单窗口消失、无观测、单次噪声失败 | 进入终态 RETIRED |
| SPLIT | 父关系真实分化；每个子关系有独立 Gate；子关系的成员/角色投影可审计 | 只按成员重叠拆分；子关系复制父证据 | 父身份终止为 SPLIT，创建多个子身份和谱系边 |
| MERGE | 多个父关系存在联合约束证据；新关系整体通过 Gate | 父关系各自成立就推断合并成立；平均冲突证据 | 创建新身份，保留所有父来源和冲突记录 |

## 4. 事件优先级与裁决流程

1. **观测机会审计**：判断当前窗口是否有足够采样机会。无观测不能作为反例。
2. **证据分层**：分别计算支持、反例、环境覆盖和来源连续性；Train/Gate/Test 严格隔离。
3. **候选匹配**：调用 I2-B。匹配器弃权不等于 CREATE。
4. **结构差异分类**：判断是结构不变、成员/角色变化、规则变化、环境变化，还是不可识别。
5. **事件证据裁决**：应用决策矩阵；SPLIT/MERGE 必须走多对多谱系证据分支。
6. **账本预检**：验证所有目标状态、版本 ID、证据引用和谱系边，确保失败时无部分写入。
7. **原子提交**：写入事件、版本和 lineage edges；保存裁决依据与反例。
8. **锁定测试审计**：只在所有规则和阈值冻结后评估，不回流到状态机。

建议确定性基线的保守规则：
- 单个合格窗口缺失：不改变身份状态，只记录 observation miss。
- 连续两个有充分采样机会的窗口没有确认：允许 SUSPEND。
- SUSPENDED 后至少两个独立反例窗口持续否定旧关系，才允许 RETIRE。
- REACTIVATE 必须有新证据；若恢复时结构不同，恢复与 MODIFY 应作为一个原子事务。
- 以上窗口数是待 Gate 校准的初始协议参数，不是自然定律；锁定 Test 前固定。

## 5. 特殊边界

### 5.1 规则变化：MODIFY 还是 CREATE

I2-B 的规则签名门控会对规则变化返回 ABSTAIN。I2-C 只有在存在跨窗口证据链时，才能把变化解释为同一身份的 MODIFY。若没有连续性证据，应保持 ABSTAIN；只有新关系独立成立且身份区分证据充分时，才 CREATE。

### 5.2 缺失与反例

- 缺失：当前没有观测到关系，不说明关系不成立。
- 反例：在充分观测机会下，关系预测与观测结果发生明确冲突。
- 采样覆盖不足：既不是支持，也不是反例。

这三类数据必须使用不同事件类型和计数器。

### 5.3 SPLIT / MERGE

SPLIT / MERGE 不由一对一 Hungarian 结果推断。它们需要独立的谱系图证据：
- SPLIT：每个子关系都必须单独验证；父证据仅按成员/角色/规则投影引用。
- MERGE：新整体关系必须有联合证据；父关系冲突不能被平均消除。
- 任一子关系/合并关系证据不足时，允许部分 ABSTAIN，不得为了谱系完整而强制补边。

### 5.4 REACTIVATE 与结构变化的原子性

账本现已提供 `reactivate_and_modify()` 组合操作：先验证身份状态、结构变化、证据引用和新版本构造，再一次性写入版本、身份状态、版本迁移与单个组合事件。验证失败不应留下部分状态；相关回归测试位于 `tests/test_e02i2_lineage.py`。

## 6. 初始证伪条件

任一情况发生，I2-C 不通过：
- 单窗口缺失被判定为 RETIRE；
- 采样覆盖不足被当成反例；
- 规则变化在无连续性证据时被强制判定 MODIFY；
- 新关系只因旧匹配器 ABSTAIN 就被 CREATE；
- REACTIVATE 没有新证据，或终态身份被复活；
- SPLIT 子关系继承了不相关父证据；
- MERGE 抹掉父关系之间的冲突；
- 事件写入发生部分提交；
- Test 标签、隐藏身份或生成器事件计划泄漏到决策器。

## 7. 实验协议

对每个事件场景使用隐藏 identity 与隐藏 event truth：
- stable / KEEP；
- structural drift / MODIFY；
- same members, changed rule：有连续性证据、无连续性证据两种；
- one-window missing / no transition；
- repeated qualified absence / SUSPEND；
- independent counterevidence / RETIRE；
- fresh evidence after suspension / REACTIVATE；
- reappearance after terminal retirement / CREATE new identity；
- replacement with similar members / REPLACE；
- SPLIT / MERGE with partial or conflicting evidence；
- insufficient sampling / ABSTAIN。

必须比较：
1. 相似度最高者强制决策；
2. I2-B + 保守 ABSTAIN；
3. 固定窗口规则事件裁决；
4. 证据连续性事件裁决。

指标：event macro-F1、identity switch rate、false suspend/retire、false CREATE、false MODIFY、false REACTIVATE、lineage edge F1、evidence provenance completeness、partial-write count、decision latency 和 abstention risk/coverage。

训练/门控/测试按 episode 和 sample_id 双重隔离。阈值只在 Gate 选择，Test 锁定。每种事件需报告置信区间与失败样本。

## 8. 当前实现状态（第一阶段）

代码位于 `prototype/e02i2c_adjudication.py`，专项测试位于 `tests/test_e02i2c_adjudication.py`。

已实现：
- `ObservationOpportunity`：窗口、环境、期望/实际样本数、覆盖率和缺失原因；不足采样不会成为 absence。
- `EvidencePacket`：证据/样本/窗口/环境/split/polarity/source-version/candidate-signature/raw provenance；不包含 hidden identity 或 hidden event truth；`split=test` 的原始观测可以作为推理输入，但隐藏身份/事件真值只保留在 evaluator，绝不进入裁决器。
- 支持与反例同时出现时强制 ABSTAIN，并将冲突证据引用保留在裁决结果中，不做置信度平均。
- `IdentitySnapshot`：裁决器只接收当前身份状态与版本摘要，不读取生成器转换计划。
- 确定性 `adjudicate_event`：支持 CREATE、KEEP、MODIFY、ABSTAIN、SUSPEND、REACTIVATE、REACTIVATE_MODIFY、RETIRE 的保守提案。
- CREATE/MODIFY 需要跨多个独立窗口和样本的支持；SUSPEND 需要连续且充分观测的 ABSENCE；采样不足会打断缺失连续段；CONTRADICTION 不等同于 ABSENCE；RETIRE 仅对已暂停身份开放并要求重复反例。
- 18 项专项单测覆盖核心边界；另有 2 项账本原子事务测试；完整 CI 尚待结果确认。

仍未实现：
- REPLACE、SPLIT、MERGE 的自动事件推断与多身份图证据。
- 将裁决提案自动、事务性地应用到账本的统一 orchestration 层；目前原子账本操作已实现，但 adjudicator proposal 到 ledger command 的安全映射尚未完成。
- 证据投影/迁移、多身份事件推断、完整 Train/Gate/locked-Test 泛化评估与置信区间。隐藏事件开发基准已在 `prototype/e02i2c_hidden_event_benchmark.py` 中建立，当前仅支持 Train/Gate，不提供 locked Test。
- E03 集成。

因此当前仍是 I2-C 的可执行基线，不代表完整事件裁决器通过。下一步完善多身份事件证据和独立泛化评估；在 I2-F 通过前不接入 E03 主引擎。
