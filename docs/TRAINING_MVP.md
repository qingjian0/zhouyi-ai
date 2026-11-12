# CPG-EI 最小可训练闭环（MVP）

## 目标与边界

本增量提供第一个端到端、可复现、无第三方依赖的可训练模型闭环。它不代表完整认知架构，也不宣称语言理解或通用推理能力。

## 模型定义

- 输入：六位阴阳状态，位序沿用 `prototype/yixiang_encoding.py` 的自下而上约定。
- 表示：42 维显式特征，包含偏置、6 个一阶爻位、15 个二阶关系项和 20 个三阶关系项。
- 高阶项：每个二阶/三阶乘积视为一个候选关系超边特征；当前候选集合是静态枚举，但每条关系拥有跨输出共享的可学习 sigmoid gate。
- 输出：六个 logistic heads，共享关系门控后分别预测下一时刻六爻状态。
- 优化：二元交叉熵、全批量梯度下降、L2 权重正则与 gate-L1 稀疏惩罚。
- 数据：固定隐藏教师规则生成的合成有限状态转移样本；训练/测试使用不同采样种子。

## 运行

```bash
python -m unittest tests.test_cpg_ei_mvp -v
python -m prototype.cpg_ei_mvp --seed 7 --train-samples 1024 --test-samples 256 --epochs 120 --json
```

## 验收标准

1. 编码维度为 42，输入严格验证为六位二进制。
2. 训练损失下降。
3. 独立测试集 bit accuracy 达到测试门槛（当前单元测试门槛为 0.85）。
4. 同一种子生成的数据完全一致。
5. 报告训练样本、测试样本、种子、epoch、训练损失、测试指标和二阶/三阶 gate 均值。
6. gate 必须由训练更新，且输出保持在 (0, 1)。

## 不能据此声称

- 动态超图已能自主创建/合并/拆分/剪枝；
- 易象传统关系先验已优于随机编码；
- 模型具备自然语言理解、长上下文或通用智能；
- 已完成严格组合 OOD、跨领域类象迁移或与 Transformer 公平对照。

下一步应增加动态候选超边创建/剪枝，并分别比较一阶、二阶、三阶、随机编码、无易象和不可学习 gate 的严格消融。


## Learnable relation gates

The model now has 35 trainable gates: 15 pairwise and 20 third-order.
Each gate is shared by the six output heads and multiplies its corresponding
candidate hyperedge feature. Gates are optimized jointly with the output
weights; an L1 penalty encourages unnecessary relations to close.

This is a learnable soft-selection layer over a fixed candidate set. It is
**not** yet dynamic hypergraph structure discovery: the model cannot create a
new candidate edge, change its arity, or rewrite its topology. Gate magnitudes
are not probabilities that a relation is true.
