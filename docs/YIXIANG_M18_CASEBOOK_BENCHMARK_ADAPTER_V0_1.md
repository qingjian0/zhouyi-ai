# M18 古典案例集到 M8 基准的安全接入 v0.1

## 1. 目标

M17 已将《墨子·小取》《淮南子·说林训》《荀子·正名》《荀子·非相》的案例整理为可审计 casebook。M18 将这些案例映射到 M8 benchmark 的数据契约，但不把研究者的解释或模型输出伪装成人工 gold。

## 2. 映射规则

- 所有新案例默认 source_status=unverified_transcription：数字文本尚未逐条对照底本影像。
- 所有案例默认 label_status=pending_review，reviewers 为空，split_group=exploratory。
- gold_decision 使用 abstain 作为占位值，gold_rationale 显式写入 PENDING REVIEW；这不是人工裁决。
- M8 evaluate_predictions 会拒绝 pending_review，因此这些数据不能进入正式准确率/F1 评估。
- 共同依据、关键差异、适用条件、必要不变量、已知反例保持空列表，除非经过人工逐条标注；不能从 audit_focus 自动捏造。
- independence_group 按原典作品归组，避免同一文本的不同案例被错误拆进训练/测试两侧。
- 未知 audit_focus 映射会直接报错，不允许静默映射到“其他”。

## 3. 当前映射

M17 三组案例集共 12 条：
- 《墨子·小取》5 条；
- 《淮南子·说林训》5 条；
- 《荀子·正名》《荀子·非相》2 条。

关系族映射仅用于数据组织，不是学术裁决。例如物种摄取方式映射到 functional/situated，结果与所以然映射到 empirical_correlation/causal_analogy，外貌映射到 morphological。若后续专家认为映射不当，应修改映射表并保留版本记录。

## 4. 关键防护

1. 不能将 pending_review 数据计入 gold 指标。
2. 不能因某案例来自古籍就自动标记 verified_primary。
3. 不能把古代反例的原文摘录直接当成已 adjudicated 的现代实验真值。
4. 不能把同一作品不同数字转录误当作独立样本。
5. 不能因模型输出稳定就把 pending_review 自动升级为 adjudicated。

## 5. 测试

10 项测试覆盖三组 casebook 转换、来源谱系保留、未审状态、abstain 占位、禁止评分、探索集隔离、未知映射拒绝和来源缺失门禁。

## 6. 后续人工审定入口

每个案例需逐项补齐：影印本定位、版本/卷篇、文本见证谱系、异文、逐句断读、共享依据、非共享依据、适用范围、必要不变量、反例、解释框架、审查理由与审查者记录。只有满足 M8 adjudicated 标签门禁后，才允许形成 gold 子集；正式测试集须按来源谱系与作品分组切分。
