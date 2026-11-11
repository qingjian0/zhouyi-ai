# E12-A16：开放集原语自主发现与复杂度约束

日期：2026-11-11  
状态：研究原型；尚未证明真实任务上的泛化收益。

## 目标

A15 在冻结的竞争假设集合内选择解释。A16 进一步允许提出此前不存在的候选原语，同时约束候选搜索复杂度，避免把每个反例都变成一条记忆规则。

## 当前可执行假设空间

首版使用稀疏合取语法：一个原语由若干输入 atom 的集合构成，满足所有 atom 时触发条件分布。组合按 atom 排序，不要求相邻，因此支持从 `a,b,c,d,e` 中发现 `a,c,e` 这样的非连续组合。

这只是有限语法，不代表已能自动发现任意关系、否定关系、时序关系或高阶函数。后续需要扩展有类型 AST、关系边、算子与组合图。

## 候选发现流程

1. 接收 observation：稳定 ID、atom 集合、结果 outcome，以及可选 incumbent 对实际 outcome 的预测概率。
2. 按稳定 observation ID 排序，确定性划分 train/validation。
3. 枚举不超过 max_arity 的稀疏 atom 子集；由 max_candidates 限制组合爆炸。
4. 在训练集估计条件 outcome 分布，使用 Laplace 平滑。
5. 计算相对全局基线的训练对数似然增益（bits）。
6. 使用通用码长近似惩罚候选结构复杂度：规则头、选择 atom 子集、编码 atom。
7. 仅保留训练 MDL 净增益为正且独立 validation 增益达到门槛的候选。
8. 通过内容摘要生成稳定 primitive ID，并记录 parent refs 与 grammar version。

## 复杂度与泛化约束

- `max_arity`：限制每个原语包含的 atom 数。
- `max_candidates`：限制候选枚举量，并明确报告是否截断。
- `max_complexity_bits`：拒绝结构描述长度过大的候选。
- `min_train_support` 与 `min_validation_support`：避免极少样本偶然拟合。
- validation 独立增益：训练集拟合不能单独让候选入库。
- 稳定排序与确定性 split：保证相同数据和配置产生相同结果。

复杂度码长目前是研究用近似，不是严格的通用 MDL 最优编码；验证集重复调参会造成泄漏，因此正式评测应使用 train/validation/locked-test 三分区，locked-test 只由 evaluator 访问。

## 新颖性信号

若调用方提供 incumbent 对真实 outcome 的概率，系统统计低似然观测比例，输出 novelty report。该指标仅是触发进一步发现的信号，不等于证明现有模型集合不完备。概率必须来自冻结 incumbent，不能用发现器自己的拟合结果代替。

## 与前序模块的边界

- A13/A14：环境漂移与检测器校准；用于判断是否可能是分布变化。
- A15：保留竞争解释并主动测量。
- A16：在已有解释不足时提出新候选原语。
- A7：候选进入生命周期前仍需注册、训练支持、独立 gate 验证。
- A8：locked-test 标签不可被 learner 读取。
- A9/A10/A11/A12：证据需经 evaluator/签名测量链路，A16 不得自行签发证据或升级 epistemic status。

## 周易、太玄经的接入方式

阴阳、四象、八卦、六十四卦、卦变、五行与太玄三分结构可作为候选语法/关系算子的来源。例如提出二态对立、四态分化、三值分支、状态变换或跨位置关系。但每个映射必须编译成明确的 atom/算子/预测分布，接受同样的 MDL、held-out、消融和反例检验。古典结构本身不构成统计证据。

## 当前限制与下一步

1. 首版只发现稀疏合取，不能处理因果、时序或连续变量。
2. 数据划分为确定性 ID 排序切分，生产实验应使用预注册 split manifest，防止 ID 可操纵。
3. 目前单一 outcome 分类，需扩展多标签、回归和概率校准。
4. 候选间重复/等价检测尚未实现；需要 canonical AST 与 E12-A6 可辨识性审计。
5. 未实现开放世界假设的自动出生/淘汰与候选族谱事务。
6. 必须在 locked-test、分布外组合任务和参数/计算预算匹配的基线下验证，才能讨论性能优势。

## 测试

`python -m unittest tests.test_e12a16_open_set_primitive_discovery -v`
