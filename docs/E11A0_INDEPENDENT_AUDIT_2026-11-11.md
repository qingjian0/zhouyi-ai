# E11-A0 独立审计：从频繁项集基线到可证伪的概念发现

日期：2026-11-11  
状态：独立审计与实验修订建议；不修改 E11 实现，不宣称实验通过  
审计对象：`research/e11-concept-hierarchy-2026-11-11`，commit `5528d6638e5cb77e10357594860a1a037326fc01`

## 1. 结论摘要

E11-A0 是合适的透明基线，但当前任务的可识别性远强于“自主概念发现”目标。它最多验证：在一个预先指定的三组属性合取生成器中，频繁项集枚举能否从对象身份隔离的样本中提出与潜在属性束相符的候选。

当前代码不应被解释为未知概念数发现、概念边界学习、层级发现或开放世界概念形成。PR 对这些限制已有诚实说明；本审计建议进一步把这些限制转化为可执行的证伪测试。

## 2. 代码级发现

### F1. 生成器把概念定义成无噪声的固定属性合取

`make_episode()` 固定创建三个 schema，每个 schema 恰好包含三个属性。对象一旦属于某概念，该概念的三个属性就全部加入；不属于时，三个属性都不会因该概念单独出现。噪声属性独立添加。

因此，对每个潜在概念，三属性合取是近乎直接可读的生成签名。当前实验没有检验概念边界在属性缺失、误报、属性替代或上下文变化下是否仍可恢复。

**建议：** 增加独立生成器臂，而不是只调当前生成器参数：
- 成员内部属性缺失 / 误报；
- 概念外属性共现的 hard-negative；
- 同一概念的多个表面实现（同义属性束 / 可替代槽位）；
- 与标签相关但非定义性的 nuisance 属性；
- 允许概念之间共享属性及重叠成员。

### F2. best-query-F1 是 oracle matching，不是学习器的概念分配能力

`evaluate()` 对每个隐藏概念，分别从所有候选中挑选 query F1 最高者。候选可被多个隐藏概念重复使用；评估阶段也没有固定的候选—概念匹配规则。

这能回答“候选集中是否存在一个像目标概念的模式”，不能回答“学习器是否知道自己发现的候选分别是什么、是否发现了正确数量的概念”。

**建议：** 保留当前分数作为诊断上界，同时增加：
- 一对一全局匹配（Hungarian / 明确的 dummy unmatched）；
- assignment-free 集合指标；
- 固定阈值 / 仅用 learner-side 统计确定的候选选择规则；
- 候选精确率、冗余率、重复率、遗漏率、错误创建率；
- 对未知概念数的估计误差及拒答质量。

不得把 oracle best-match 分数作为主性能指标。

### F3. 候选枚举成本没有预算约束

`propose_concepts()` 枚举词汇表中 1..max_order 的所有组合，并逐候选扫描全部对象。复杂度随属性词汇量和最大阶数组合增长。当前没有候选上限、匹配次数统计、墙钟时间或峰值内存记录。

**建议：** 报告候选总数、实际匹配次数、每个对象-候选检查数、运行时间、峰值内存；为所有基线设相同候选评估预算。预算耗尽时应显式返回 PARTIAL / ABSTAIN，不得静默截断。

### F4. 对象身份隔离不等于结构或环境泛化

训练与 query 对象 ID 不相交，但两者由同一个固定生成机制和同一组隐藏 schema 产生。它只排除了对象记忆，未隔离概念模板、生成器族、上下文或组合结构。

**建议：** 分开报告：
- object-disjoint；
- surface-symbol-disjoint；
- context-disjoint；
- generator-family-disjoint；
- schema-composition-disjoint。

这些 split 不可合并成一个“泛化”分数。

### F5. 符号重命名测试只比较数量与 oracle 分数

当前测试没有验证候选集合在置换映射下的结构等价，也没有检查重命名后 learner/query 两侧的符号映射是否严格一致。仅候选数量相同不足以证明语义不变性。

**建议：** 将候选先逆映射回原符号空间，比较 canonical candidate sets；再比较逐对象预测的映射等价性。增加字段顺序、对象顺序、属性集合顺序扰动。

### F6. learner/evaluator 边界是 API 约定，不是隔离边界

`Episode` 同时携带 learner/query 观察与 `truth`、`hidden_schemas`。当前提案和代码注释已承认这是 in-process benchmark，而不是安全边界。

**建议：** 后续正式确认实验把 learner payload 序列化到独立进程输入；evaluator truth 独立保存，只通过评测协议接收 learner 的候选输出。增加 query-label / hidden-schema canary：改变真值不得改变 learner 输入字节。

## 3. 额外的统计与协议问题

1. 当前默认单 seed 仅适合 smoke test；不得从单 seed 汇报方法优劣。
2. 当前没有 flat、random-pattern、single-feature、lookup、MDL / predictive-compression 基线的同预算对照。
3. `_f1()` 对 predicted 与 actual 同为空返回 1.0；未来应报告空类处理策略，并单独列出无正例 episode，避免空集抬高指标。
4. `truth` 的 key 是按对象 ID 索引，当前 split 逻辑本身没有泄漏，但必须加断言确保每个 query ID 都有且仅有 evaluator 记录，且 learner 函数不能访问该映射。
5. 当前每个 latent concept 的属性束互不重叠，缺少共享特征与多父层级，不能为 E11-B 提供有效压力测试。

## 4. 建议的最小下一步：E11-A0.1

不要立即实现复杂的自主概念系统。先把 baseline 变成可比较、可证伪的基准：

### A. 冻结当前基线
- 保留原始三合取生成器和原始输出作为 legacy control；
- 固定数据版本、种子范围和 learner/evaluator schema；
- 当前 oracle best-match F1 改名为 `oracle_candidate_recall_diagnostic`。

### B. 加入三种反例生成器
- `missing/noisy-membership`：概念成员属性不完整，非成员可出现少量定义属性；
- `shared-attribute`：概念共享部分属性，要求区分真正定义属性与公共属性；
- `nuisance-confounded`：高频 nuisance 模式与概念成员相关，但在 held-out environment 中反转。

### C. 加入四类基线
- 单属性频率；
- 随机候选（同数量、同阶数分布）；
- 固定频繁项集（当前方法）；
- 预测压缩 / MDL 候选选择。

全部方法匹配候选评估预算，并报告 oracle 诊断分数与 operational assignment 分数两套指标。

### D. 加入验收门
- symbol / object / field order invariance；
- nuisance-only attacker；
- query truth canary；
- seed-block 置信区间；
- 预算耗尽行为；
- 对不可识别 episode 的 ABSTAIN。

## 5. 建议的研究顺序

1. 先实现 F2/F3/F5 的指标和预算修正；
2. 再加入 noisy / shared / nuisance 三种生成器；
3. 做 20-seed development 与 100-seed locked confirmation；
4. 通过后再引入 E11-A 的 anti-unification、predictive compression 和 boundary counterexample search；
5. 最后才做 E11-B 多关系层级学习。

不要把 E11-A0.1 的通过称为概念自主发现。它只建立一个更可信的基准入口。

## 6. 与并行研究的边界

本审计分支以 E11 当前 head 为只读基线，只新增本审计文档：
- 不修改 E11 原分支；
- 不修改 E10 / E09 / E02 / main；
- 不运行、取消或重跑其他分支 CI；
- 不合并任何研究分支。

后续实现应在独立 E11-A0.1 分支中进行，并以本审计作为待审查建议，而非自动授权。
