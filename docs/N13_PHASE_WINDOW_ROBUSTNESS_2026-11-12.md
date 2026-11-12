# N0.13：跨角色、跨相位窗口的 OOD 稳健性

**状态：已加入可执行 sweep 和单元测试，等待 CI 正式结果。**

## 为什么需要 N0.13

N0.11 只把角色 A 的一个固定四分之一圆相位区间留作测试。N0.12 的参数预算对照也沿用该划分。为了避免结果只是某个角色、某个相位边界的偶然现象，N0.13 将 OOD 区域系统扩展为：

- 三个角色分别作为 held-out role；
- 四个四分之一圆窗口分别作为 held-out phase region；
- 共 12 种分布偏移条件；
- 每个条件三个独立种子。

每个条件的训练集和验证集都排除对应角色的 held-out 窗口；测试集只从该窗口采样。其他两个角色在训练、验证和测试中均覆盖完整相位范围。

## 模型对照

每个条件训练相同的三种 SROK 特征阶数：

1. Unary；
2. Unary + Pairwise；
3. Unary + Pairwise + Triple。

每个模型只用对应训练分布内的 validation 选择 logit 方向。另对训练好的三阶模型屏蔽 triple block，作为归因干预。汇总每个角色/窗口的结果，不能只报告总体平均值。

## 默认复现

```bash
python -m unittest tests.test_n13_phase_window_robustness -v
python -m prototype.n13_phase_window_robustness --seeds 3 --start-seed 7 --train-samples 600 --validation-samples 300 --test-samples 300 --epochs 80 --json
```

CI 将检查 12 个条件全部出现、三阶模型总体和最差条件准确率、unary 基线以及 triple-mask 归因干预。阈值仅用于已知解析任务的实现验收。

## 解释边界

- 仍是已知解析目标 `1[cos(a+b+c)>0]` 的合成任务。
- Fourier/tensor-product 先验是显式提供的，不是模型从原始数据中发现的。
- 这测试相位区域和角色位置变化，不等同于语义规则族 OOD。
- 每个条件三个种子只是一轮稳健性筛查，不是高精度统计估计。
- 若结果通过，下一步仍需引入多个不同的组合运算规则和无先验可学习表示。
