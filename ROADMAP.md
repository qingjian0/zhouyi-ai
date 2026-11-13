# 开发路线图

> 项目最高研究优先级为易象理论与类象认知。清以前文献为研究主体，清代及以后用于校勘、辑佚、补漏和学术审查。

| 阶段 | 目标 | 交付物 | 状态 |
|---|---|---|---|
| P0-A | 类象理论本体 | 多维类象、关系保持、边界条件、反例与证据规范 | v0.1 本体草案与类象记录规范已建立，待文献校勘/专家审阅 |
| P0-B | 易学概念校勘 | 阴阳、四象、八卦、六十四卦、爻位、卦序、卦变规范 | 编码约定与结构转移原型已实现；经典来源校勘待开展 |
| P0-C | 类象数据体系 | 经典语料、结构数据、跨域案例、合成基准与数据卡 | 候选书目 111 项；结构化语料 41 条候选记录、46 条文本主张；全文入库与逐条校勘待开展 |
| P0-D | 类象计算引擎 | 类象发现、解释、验证、迁移、组合和拒绝机制 | 规则评估、有界图映射、M2.1 候选评分和 M3 证据剖面基线已实现；学习型抽取/迁移待开展 |
| P0-E | 易象状态引擎 | 层次状态、爻位、卦变、状态转移与路径 | 64态结构编码与显式动爻转移原型已实现；经典语义/路径模型待开展 |
| P0-F | 五行与时位势变 | 条件关系、制化、乘侮、消长及动态演化 | 设计草案，模型实验未开始 |
| P0-G | 多尺度时间与层级过程 | 事件时间/观测时间、多尺度阶段、局部—整体递归 | M1 时间层级/区间关系原型与合成基准已有记录；M2 typed relation、M2.1 双向候选约束已实现；结构扰动实验和真正递归消息传递待开展 |
| P0-H | 竞争类象与证据裁决 | 多假设保留、适用边界、未决机制、反例驱动更新 | M3 已实现证据分层、多维剖面、条件状态、反例保留及未决规则；概率校准、标注一致性与学习型裁决待开展 |
| P1-A | 反事实与干预边界 | 条件变化、反事实一致性、混杂识别与拒绝 | M4 显式条件干预规则基线已实现；混杂识别、真实干预验证与概率模型待开展 |
| P1-B | 主动观测 | 信息增益、预测分歧、观测成本与选择偏差 | M5 离散假设/结果的信息增益与成本—风险—可行性—选择偏差排序原型及合成测试已添加；真实观测校准、连续结果和序贯决策待开展 |
| P1-C | 新象发现与结构重组 | 残差聚类、候选新象、版本化、回滚 | M6 精确 typed-signature 残差分组、跨域/多来源门槛、人工审查版本与回滚原型已提交；独立留出验证和模糊聚类待开展 |
| P1 | 易象驱动的组合认知 | 动态超图、并行推演、证据协调、自组织 | M7 M3–M6 透明规则编排原型已提交；持久化事件账本、真实观测执行与在线学习待开展 |
| P1-EVAL | 理论贡献验证 | 消融、跨域迁移、错误类比拒绝、OOD 与成本评估 | M5/M6/M7 测试已接入；修正 M6 测试断言后，最新 CI 待验证；此前 head 曾因断言不匹配失败 |
| P1-EVAL-M8 | 类象有效性与迁移基准 | 独立 case schema、四态裁决 gold、来源谱系泄漏检测、分层指标 | M8 v0.1 schema/validator、四态评估、关系族/来源状态分层指标、来源谱系与独立性分组泄漏报告、gold 资格门禁、M8 命令行报告入口及 12 条 synthetic fixtures 已提交；CI 待核，人工 gold 标注未开始 |
| P2 | 通用模型与工程 | 语言生成、训练优化、加速、部署 | 按核心研究需要推进 |

## 近期研究主线

1. M1：多尺度时间表示和合成基准。
2. M2：整体—局部 typed relation 与结构扰动实验。
3. M2.1：局部证据评分整体假设，整体预期反馈局部核验。
4. M3：竞争类象、证据分层、适用条件与未决裁决。
5. M4：反事实与干预边界（显式条件干预、未知保留、稳定性/状态变化判定）。
6. M5：主动观测的信息增益基线（见 `docs/YIXIANG_ACTIVE_OBSERVATION_M5_V0_1.md`、`prototype/yixiang_active_observation.py`）。
7. M6：残差驱动的新象提议、人工审查、版本化和回滚（见 `docs/YIXIANG_NOVELTY_DISCOVERY_M6_V0_1.md`、`prototype/yixiang_novelty.py`）。
8. M7：统一闭环与公平消融（见 `docs/YIXIANG_UNIFIED_COGNITIVE_LOOP_M7_V0_1.md`、`prototype/yixiang_m7_pipeline.py`）。

M5/M6 当前均为透明规则原型；M6 的“新”只表示不在调用方提供的已知签名集合中，不代表发现了客观新规律。

M1 文档与实现见 `docs/YIXIANG_MULTISCALE_TIME_M1_V0_1.md`、`prototype/yixiang_multiscale_time.py`；M2 见 `docs/YIXIANG_HIERARCHICAL_STRUCTURE_M2_V0_1.md`、`prototype/yixiang_hierarchical_structure.py`；M2.1 见 `docs/YIXIANG_BIDIRECTIONAL_CONSTRAINTS_M2_1_V0_1.md`、`prototype/yixiang_bidirectional_constraints.py`；古籍类象校勘札记见 `docs/CLASSICAL_YIXIANG_THEORY_NOTES_PREQIN_HAN_V0_1.md`；《墨子·小取》类推与异文专题见 `docs/CLASSICAL_YIXIANG_MOZI_XIAOQU_ANALYSIS_V0_1.md`；跨时代综合框架见 `docs/CLASSICAL_YIXIANG_THEORY_SYNTHESIS_V0_2.md`；古籍数字来源与版本规程见 `docs/CLASSICAL_TEXT_DIGITAL_SOURCE_POLICY_V0_1.md`；M3 见 `docs/YIXIANG_COMPETING_HYPOTHESES_M3_V0_1.md`、`prototype/yixiang_competing_hypotheses.py`；M4 见 `docs/YIXIANG_COUNTERFACTUAL_M4_V0_1.md`、`prototype/yixiang_counterfactual.py`。

## 执行原则

1. 区分形态、属性、功能、关系、过程、时空、势象与综合象。
2. 建立经典概念和卦爻编码校勘表，保留不同传承/注本的差异。
3. 固定数据 schema、来源追溯、标注规范、反例和数据划分。
4. 实现类象发现—解释—验证—迁移的最小闭环。
5. 将阴阳、四象、八卦、六十四卦、爻位和卦变接入可执行计算图。
6. 实现五行条件关系及时间、位置、阶段和趋势建模。
7. 将 P0 机制与动态超图、并行推演、自组织机制集成。
8. 做参数/数据/算力匹配的消融与跨域实验，再决定是否扩大训练。

## 原有实验的处理

E01/E02、GF(2)、ANF、高阶关系和优化器研究不删除；保留为底层数学工具或对照实验。只有能明确支持 P0 理论机制、模型能力或评估的部分，才列入近期主线。


### M8 当前实现边界

`prototype/yixiang_benchmark.py` 提供 benchmark case/dataset/prediction 校验；`prototype/yixiang_benchmark_report.py` 提供 JSON 报告 CLI、四态混淆矩阵与 macro-F1、缺失预测按 abstain 计分、关系族/来源状态分层混淆矩阵与 Macro-F1、abstention coverage / selective risk，以及 `source_lineage` / `independence_group` 跨 split 泄漏报告。Schema 和 validator 以 `label_status` 区分 `fixture_expected`、`pending_review`、`adjudicated`；synthetic fixture 不允许伪造 reviewer 记录，人工 adjudicated 标签要求至少两个不同 reviewer ID（仍需人工核验其真实独立性）。`data/yixiang_benchmark_synthetic.v0.1.json` 的 12 条样本仅用于接口测试，不是古籍 gold 数据，不得用于声称类象理论有效。人工标注、标注一致性统计、关系族分层 F1/置信区间、M7 输出适配仍待实现。


### 本轮古典类象研究补充

新增《先秦两汉类象拒推机制专题》：对读《墨子·小取》《荀子·非相》《淮南子·说林训》《韩非子·难势》《论衡·感类》，归纳局部同不等于整体同、结果同不等于所以然同、表面代理不等于目标属性、同物异用与主体情境适配、势与材交互、时间先后不等于因果六类拒推机制。所有文本仍是数字见证级研究，未升级为校勘定本或 M8 adjudicated gold。
