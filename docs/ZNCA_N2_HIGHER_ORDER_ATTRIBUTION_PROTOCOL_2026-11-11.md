# ZNCA N2：高阶关系贡献归因实验协议

日期：2026-11-11  
状态：研究协议 / Draft  
适用对象：`prototype/znca_dynamics.py`

## 1. 为什么需要这份协议

N2 已能学习 pairwise 与 higher-order influence terms。但“高阶模型性能更高”不等于“高阶关系本身带来了增益”。参数量、更多传播步骤、更强归一化、数据泄漏或更好的优化都可能解释差距。

2026 年 10 月的研究 *Do Higher-Order Models Win for Higher-Order Reasons?* 提出一个关键警告：对高阶信息进行扰动、同时保留低阶 pairwise 信息后，部分高阶模型仍保留原先的大部分性能优势。这意味着不能仅凭总分提升就把收益归因于高阶结构：
https://arxiv.org/abs/2610.07981

因此 N2 的验证必须区分：
- **模型优势**：N2 是否取得更低损失或更高 OOD 准确率；
- **高阶信息贡献**：破坏高阶结构但保留 pairwise 统计后，性能是否显著下降；
- **高阶算子贡献**：保持模型预算和优化预算时，高阶项是否比强 pairwise 模型提供额外信息。

## 2. 必需对照组

A. Pairwise-linear：仅使用 pairwise influence terms。

B. Pairwise-strong：允许更丰富的 pairwise 权重、多个同步传播步骤和合理归一化，避免用弱基线衬托高阶项。

C. Higher-order-native：使用原始高阶关系项。

D. Higher-order-perturbed：对超边/高阶组合作受控扰动，但保持 pairwise co-occurrence 矩阵、节点度及任务样本分布不变。

E. Higher-order-random：随机高阶项，控制参数数量和项数量。

F. Role-shuffled：打乱角色槽位，检验结果是否真的依赖有语义的角色绑定。

## 3. 核心归因对比

对同一测试任务和相同训练预算，计算：
- `L_pairwise_strong`；
- `L_higher_order_native`；
- `L_higher_order_perturbed`；
- `L_higher_order_random`。

若 native 优于 pairwise，但 perturbed 与 native 相近，则没有证据说明优势来自正确的高阶结构。若 native 明显优于 perturbed，且 pairwise-strong 无法复现，同时跨种子稳定，才支持“高阶结构有独立贡献”的有限结论。

高阶结构扰动必须通过断言验证 pairwise co-occurrence matrix 完全相同；否则该消融无效。

## 4. 数据拆分和预算公平

- 训练/验证/锁定测试集按组合规则或机制家族切分，不能随机拆分近重复样本；
- 对 unseen combinations、unseen role assignment、unseen mechanism family 分别报告；
- 所有模型使用相同训练样本、优化器预算、早停规则、随机种子集合；
- 报告可训练参数、关系项数量、每步乘加量、训练时间、推理时间、峰值内存；
- 不允许为高阶模型单独调参后与未调优的 pairwise 模型比较；
- 至少 10 个固定种子，报告均值、标准差和置信区间；
- 预先锁定主指标和停止规则。

## 5. 必须分离的语义

- 关系项的 sigmoid 激活不是校准概率；
- 证据权重不是模型置信度；
- 高阶关系数量不等于信息量；
- pairwise 投影相同不意味着完整语义相同，但它是检验高阶结构增量信息的关键控制；
- 角色语义不能在数据处理中被无意抹除；
- 更好的 OOD 表现仍不自动证明模型具有通用认知能力。

## 6. 证伪条件

遇到以下任一情况，必须降低或撤回 N2 的高阶机制主张：
1. 高阶结构扰动后性能几乎不变；
2. Pairwise-strong 追平或超过 higher-order-native；
3. 角色打乱不影响性能；
4. 提升只在随机拆分存在，机制家族 OOD 消失；
5. 提升可由更多参数、更多传播步骤或归一化解释；
6. 推理成本增长超过任务收益，且移动端预算不满足。

## 7. 对下一代 N3 的约束

N3 不应只是堆更多高阶项。它应研究：
- 从事件流中动态提出关系候选；
- 用主动观测区分竞争关系假设；
- 将候选结构的证据质量与动力学预测误差分开；
- 在新证据到来时局部更新状态，而非无条件全图重算；
- 对候选爆炸实行预算、剪枝、撤销和可恢复检查点；
- 对错误关系的传播范围设置隔离与回滚。

在 N2 完成上述归因实验前，不应宣称 N3 的高阶机制已被证实。
