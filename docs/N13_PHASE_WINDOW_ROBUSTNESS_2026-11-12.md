# N0.13：跨角色、跨相位窗口的 OOD 稳健性

**状态：12 条件、36 次运行的正式 sweep 已通过专项 CI gate，结果 artifact 已生成。**

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

## 正式结果

配置：3 个 held-out roles × 4 个 quarter-circle windows；每个条件 3 seeds，共 12 conditions / 36 runs。每次 600 train / 300 validation / 300 test，80 epochs。

| 指标 | 结果 |
|---|---:|
| 三阶模型总体 OOD accuracy | **84.76%** |
| 三阶模型总体 balanced accuracy | 84.57% |
| 12 条件中最差条件的三阶平均 accuracy | 79.33% |
| Unary 总体 accuracy | 50.72% |
| Pairwise 总体 accuracy | 23.35% |
| 三阶模型屏蔽三阶块后的 accuracy | 23.19% |

这里的 84.76% ± 5.15% 是 36 个 condition-seed 运行结果的 pooled mean / sample SD；不能把它误读为同一条件下仅由随机种子导致的标准差。每个条件均高于 79%，说明 N0.11 的结果没有只依赖角色 A 或单个固定相位窗口。

- CI workflow： [Run 43138859923](https://github.com/qingjian0/zhouyi-ai/actions/runs/43138859923)
- N0.13 专项 sweep 和 JSON artifact 上传步骤已通过。
- Artifact：`n13-phase-robustness-results`，ID `13908852185`。

## 解释边界

- 仍是已知解析目标 `1[cos(a+b+c)>0]` 的合成任务。
- Fourier/tensor-product 先验是显式提供的，不是模型从原始数据中发现的。
- 这测试相位区域和角色位置变化，不等同于语义规则族 OOD。
- 每个条件三个种子只是一轮稳健性筛查，不是高精度统计估计。
- 若结果通过，下一步仍需引入多个不同的组合运算规则和无先验可学习表示。
