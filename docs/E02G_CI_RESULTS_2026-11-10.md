# E02-G 正式 CI 结果（2026-11-10）

来源：GitHub Actions run 42814173387，PR #3，完整工作流 job `unit-tests`。

## 运行结论

- 完整工作流：success。
- 全部单元测试：success。
- E01 至 E02-F 既有步骤：success。
- E02-G 五项单元测试：success。
- E02-G 50-seed × 3-regime 实验：success。

## E02-G 汇总

每个 regime 50 个随机种子；每个环境 512 个训练样本；每个环境 5 份独立 gate，每份 256 个样本；标签噪声 2%。

| 真实状态 | 正确分类 | 目标成员恢复率 | 分类计数 |
|---|---:|---:|---|
| stable | 50/50 | 100% | stable 50 |
| conditional | 50/50 | 100% | conditional 50 |
| drift | 50/50 | 100% | drift 50 |

总计 150/150 个 episode 分类正确，150/150 个候选成员集合恢复正确；没有 unresolved 或跨类别误判。

判定使用各环境训练数据估计方向，独立 gate 重复样本合并计算 95% Wilson 区间：
- active：Wilson 下界 > 0.75；
- inactive：Wilson 上界 < 0.75；
- 两环境 active 且同向：stable；
- 仅一环境 active：conditional；
- 两环境 active 但方向相反：drift；
- 其他情况：unresolved。

## 解释与边界

结果支持一个明确但狭窄的结论：在预设的两环境、二值三阶乘积关系、三种预定义状态和当前样本量下，系统能恢复候选成员，并区分稳定、条件成立和方向反转。

这并不证明一般环境迁移、连续时间漂移、因果发现或开放域关系理解。Wilson 区间也没有解决候选搜索的全局后选择推断问题。下一阶段应扩大到更多环境、非乘法规则族、关系成员改变，以及未知状态数。
